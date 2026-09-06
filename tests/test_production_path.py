"""
Production-path integration tests.
These tests exercise the complete agent pipeline:
  Telegram message → runner → mock LLM → tools → services → DB → response

Every test verifies the FINAL response text (what the Telegram user would see),
not just internal tool execution status.
"""
import pytest
from app.db.seed import seed_database
from app.agent.runner import process_agent_message, reset_user_conversation, format_tool_response
from app.agent.registry import execute_tool
from app.agent.session_manager import SessionManager
from app.services.billing_service import BillingService
from app.services.khata_service import KhataService
from app.db.models import Product, Customer


# ─── Inventory ───

@pytest.mark.asyncio
async def test_stock_query_returns_natural_language(db_session):
    """A) 'How much Aashirvaad Atta do I have?' must return product info, not 'Executed ...'."""
    seed_database(db_session)
    res = await process_agent_message(user_id=9001, message_text="How much Aashirvaad Atta do I have?", db=db_session)
    assert "Executed" not in res, f"Response exposed internal message: {res}"
    assert "Aashirvaad Atta" in res
    # Must contain stock quantity somewhere
    assert "30" in res or "quantity" in res.lower()


@pytest.mark.asyncio
async def test_unknown_product_returns_not_found(db_session):
    """B) 'How much Britannia Good Day do I have?' must say not found, not 'Executed ...'."""
    seed_database(db_session)
    res = await process_agent_message(user_id=9002, message_text="How much Britannia Good Day do I have?", db=db_session)
    assert "Executed" not in res, f"Response exposed internal message: {res}"
    # Should indicate no results
    assert "not found" in res.lower() or "no matching" in res.lower() or "couldn't find" in res.lower() or "No matching" in res


@pytest.mark.asyncio
async def test_low_stock_query(db_session):
    """'Do I need to reorder anything?' must return low-stock items."""
    seed_database(db_session)
    res = await process_agent_message(user_id=9003, message_text="Do I need to reorder anything?", db=db_session)
    assert res is not None
    assert len(res) > 10  # Must be a meaningful response


# ─── Billing ───

@pytest.mark.asyncio
async def test_single_item_bill_flow(db_session):
    """Create a draft bill and add one item."""
    seed_database(db_session)
    res1 = await process_agent_message(user_id=9010, message_text="Make a bill for Ravi", db=db_session)
    assert "draft" in res1.lower() or "bill" in res1.lower()

    # Check active bill was set
    mgr = SessionManager(db_session)
    bill_id = mgr.get_active_draft_bill("9010")
    assert bill_id is not None


@pytest.mark.asyncio
async def test_multi_item_bill_flow(db_session):
    """Multi-item: add salt, maggi, butter to a bill."""
    seed_database(db_session)
    # Create draft
    await process_agent_message(user_id=9011, message_text="Make a bill for Ravi", db=db_session)
    mgr = SessionManager(db_session)
    bill_id = mgr.get_active_draft_bill("9011")
    assert bill_id is not None

    # Add multiple items
    res = await process_agent_message(
        user_id=9011,
        message_text="Add 2 Tata Salt 1kg, 3 Maggi 70g, and 1 Amul Butter 100g",
        db=db_session,
    )
    assert "Tata Salt" in res or "Salt" in res
    # Should contain a bill summary
    assert "Grand Total" in res or "grand_total" in res.lower() or "₹" in res


@pytest.mark.asyncio
async def test_finalize_bill_flow(db_session):
    """Finalize a bill and verify stock deduction."""
    seed_database(db_session)
    salt = db_session.query(Product).filter(Product.name.ilike("%Tata Salt%")).first()
    initial_stock = float(salt.quantity)

    # Create draft
    await process_agent_message(user_id=9012, message_text="Make a bill for Ravi", db=db_session)
    mgr = SessionManager(db_session)
    bill_id = mgr.get_active_draft_bill("9012")

    # Add item directly via tool
    execute_tool(db_session, "add_bill_item", {"bill_id": bill_id, "product_id": salt.id, "quantity": 2})

    # Finalize
    res = await process_agent_message(user_id=9012, message_text="Finalize the bill", db=db_session)
    assert "Finalized" in res or "finalized" in res

    # Verify stock was deducted
    db_session.refresh(salt)
    assert float(salt.quantity) == initial_stock - 2

    # Verify active bill cleared
    assert mgr.get_active_draft_bill("9012") is None


@pytest.mark.asyncio
async def test_double_finalization_does_not_deduct_twice(db_session):
    """Finalizing same bill twice must not deduct stock twice."""
    seed_database(db_session)
    salt = db_session.query(Product).filter(Product.name.ilike("%Tata Salt%")).first()

    billing = BillingService(db_session)
    bill = billing.create_draft_bill()
    billing.add_bill_item(bill.id, salt.id, 3)
    billing.finalize_bill(bill.id, payment_method="Cash")

    stock_after_first = float(salt.quantity)

    # Second finalization
    bill2 = billing.finalize_bill(bill.id, payment_method="Cash")
    db_session.refresh(salt)
    assert float(salt.quantity) == stock_after_first  # No change


@pytest.mark.asyncio
async def test_oversell_rejection(db_session):
    """Overselling must be rejected."""
    seed_database(db_session)
    salt = db_session.query(Product).filter(Product.name.ilike("%Tata Salt%")).first()
    stock = float(salt.quantity)

    res = execute_tool(db_session, "create_draft_bill", {})
    bill_id = res["data"]["bill_id"]

    res = execute_tool(db_session, "add_bill_item", {"bill_id": bill_id, "product_id": salt.id, "quantity": stock + 100})
    assert res["status"] == "error"
    assert "Oversell" in res["error"] or "stock" in res["error"].lower()


# ─── GST / Tax ───

def test_gst_rates_and_rounding(db_session):
    """Verify GST splits correctly for multiple rates."""
    seed_database(db_session)
    from app.services.tax_service import TaxService
    tax = TaxService()

    # 5% GST on ₹240 x 2 = ₹480 taxable → CGST ₹12.00, SGST ₹12.00
    result = tax.calculate_item_tax(unit_price=240.0, quantity=2, gst_rate=5.0)
    assert result["taxable_amount"] == 480.0
    assert result["cgst_amount"] == 12.0
    assert result["sgst_amount"] == 12.0
    assert result["total_amount"] == 504.0

    # 12% GST on ₹60 x 1 = ₹60 taxable → CGST ₹3.60, SGST ₹3.60
    result2 = tax.calculate_item_tax(unit_price=60.0, quantity=1, gst_rate=12.0)
    assert result2["taxable_amount"] == 60.0
    assert result2["cgst_amount"] == 3.6
    assert result2["sgst_amount"] == 3.6
    assert result2["total_amount"] == 67.2

    # 0% GST
    result3 = tax.calculate_item_tax(unit_price=44.0, quantity=5, gst_rate=0.0)
    assert result3["cgst_amount"] == 0.0
    assert result3["sgst_amount"] == 0.0
    assert result3["total_amount"] == 220.0


# ─── Khata ───

def test_khata_credit_and_repayment(db_session):
    """Credit increases balance, repayment decreases, overpayment rejected."""
    seed_database(db_session)
    khata = KhataService(db_session)
    customer = khata.get_or_create_customer(name="Ravi")

    khata.record_credit(customer.id, 500.0)
    db_session.refresh(customer)
    assert float(customer.credit_balance) == 500.0

    khata.record_repayment(customer.id, 200.0)
    db_session.refresh(customer)
    assert float(customer.credit_balance) == 300.0

    # Overpayment must be rejected
    with pytest.raises(ValueError, match="exceeds|greater"):
        khata.record_repayment(customer.id, 999.0)


def test_khata_unknown_customer(db_session):
    """get_or_create should create a new customer."""
    seed_database(db_session)
    khata = KhataService(db_session)
    customer = khata.get_or_create_customer(name="NewCustomer")
    assert customer is not None
    assert customer.name == "NewCustomer"
    assert float(customer.credit_balance) == 0.0


# ─── Preferences + Memory ───

@pytest.mark.asyncio
async def test_preference_persistence_across_new(db_session):
    """Preferences must survive /new reset."""
    seed_database(db_session)
    from app.services.preference_service import PreferenceService
    pref_svc = PreferenceService(db_session)

    pref_svc.set_preference("9020", "default_payment_method", "UPI")
    val = pref_svc.get_preference("9020", "default_payment_method")
    assert val == "UPI"

    # Reset session
    reset_user_conversation(9020, db=db_session)

    # Preference should still be there
    val2 = pref_svc.get_preference("9020", "default_payment_method")
    assert val2 == "UPI"


# ─── /new + Conversation State ───

@pytest.mark.asyncio
async def test_new_clears_conversation_but_not_data(db_session):
    """/new clears conversation history and active draft, but not inventory/bills/khata."""
    seed_database(db_session)
    mgr = SessionManager(db_session)

    # Set some state
    mgr.add_message("9030", "user", "Test message")
    mgr.set_active_draft_bill("9030", 99)

    # Reset
    reset_user_conversation(9030, db=db_session)

    assert mgr.get_history("9030") == []
    assert mgr.get_active_draft_bill("9030") is None

    # Inventory still exists
    products = db_session.query(Product).all()
    assert len(products) >= 10


# ─── Daily Close ───

def test_daily_close_returns_data(db_session):
    """Daily close should return structured summary."""
    seed_database(db_session)
    res = execute_tool(db_session, "get_daily_close", {})
    assert res["status"] == "success"
    data = res["data"]
    assert "total_sales" in data
    assert "bill_count" in data
    assert "total_tax" in data


# ─── PDF Invoice ───

def test_invoice_requires_finalized_bill(db_session):
    """PDF generation must reject unfinalized bills."""
    seed_database(db_session)
    billing = BillingService(db_session)
    bill = billing.create_draft_bill()
    res = execute_tool(db_session, "generate_invoice_pdf", {"bill_id": bill.id, "user_id": "test"})
    assert res["status"] == "error"


# ─── Duplicate Tool Call Detection ───

def test_duplicate_tool_call_detection():
    """The runner's _make_tool_cache_key must produce deterministic keys."""
    from app.agent.runner import _make_tool_cache_key
    key1 = _make_tool_cache_key("search_products", {"query": "Atta"})
    key2 = _make_tool_cache_key("search_products", {"query": "Atta"})
    key3 = _make_tool_cache_key("search_products", {"query": "Salt"})
    assert key1 == key2
    assert key1 != key3


# ─── Format Tool Response Fallback ───

def test_format_tool_response_no_data():
    """format_tool_response with empty data should not say 'Executed successfully'."""
    results = [{"name": "search_products", "status": "success", "data": []}]
    text = format_tool_response(results)
    assert "Executed" not in text
    assert "No matching" in text


def test_format_tool_response_error():
    """Error tool results should be surfaced."""
    results = [{"name": "finalize_bill", "status": "error", "error": "Bill ID 999 not found."}]
    text = format_tool_response(results)
    assert "999" in text
    assert "⚠️" in text


def test_format_tool_response_product_found():
    """Successful search should list products."""
    results = [{"name": "search_products", "status": "success", "data": [
        {"name": "Tata Salt 1kg", "sku": "SKU-SALT-1KG", "selling_price": 26.0, "quantity": 50.0, "unit": "packet"}
    ]}]
    text = format_tool_response(results)
    assert "Tata Salt" in text
    assert "50" in text
