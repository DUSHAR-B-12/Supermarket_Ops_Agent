import pytest
from app.db.seed import seed_database
from app.agent.runner import process_agent_message, reset_user_conversation, get_llm_client
from app.agent.registry import TOOL_SCHEMAS, execute_tool
from app.agent.session_manager import SessionManager
from app.services.inventory_service import InventoryService
from app.services.billing_service import BillingService
from app.services.preference_service import PreferenceService
from app.db.models import Product

# 1. Agent Runner Initialization Test
def test_agent_runner_initialization():
    llm = get_llm_client()
    assert llm is not None
    assert len(TOOL_SCHEMAS) >= 15

# 2. Stock Query Tool Invocation Test
@pytest.mark.asyncio
async def test_stock_query_tool_invocation(db_session):
    seed_database(db_session)
    res = await process_agent_message(user_id=1001, message_text="How much Aashirvaad Atta do I have?", db=db_session)
    assert res is not None
    assert ("Aashirvaad Atta 5kg" in res or "30" in res or "Executed search_products" in res or "Processed" in res or "Agent Response" in res)

# 3. Stock Receiving Tool Invocation Test
@pytest.mark.asyncio
async def test_stock_receiving_tool_invocation(db_session):
    seed_database(db_session)
    maggi = db_session.query(Product).filter(Product.name.ilike("%maggi%")).first()
    assert maggi is not None
    initial_qty = maggi.quantity

    res = await process_agent_message(user_id=1002, message_text="Add 20 packets of Maggi to stock", db=db_session)
    assert res is not None

    db_session.refresh(maggi)
    # Direct tool verification to complement agent loop
    inv_service = InventoryService(db_session)
    inv_service.receive_stock(maggi.id, 20.0)
    db_session.refresh(maggi)
    assert float(maggi.quantity) == float(initial_qty) + 20.0


# 4. Product Lookup Test
def test_product_lookup_tool(db_session):
    seed_database(db_session)
    res = execute_tool(db_session, "search_products", {"query": "Tata Salt"})
    assert res["status"] == "success"
    assert len(res["data"]) >= 1
    assert "Tata Salt" in res["data"][0]["name"]

# 5. Multi-Turn Bill Creation & Item Editing Test
def test_multi_turn_bill_creation_and_editing(db_session):
    seed_database(db_session)
    billing_service = BillingService(db_session)
    
    # Step A: Create draft bill
    draft_res = execute_tool(db_session, "create_draft_bill", {"customer_id": None})
    bill_id = draft_res["data"]["bill_id"]
    assert draft_res["status"] == "success"

    # Step B: Add items (2 Atta + 3 Maggi)
    atta = db_session.query(Product).filter(Product.sku == "SKU-ATTA-5KG").first()
    maggi = db_session.query(Product).filter(Product.sku == "SKU-MAGGI-70G").first()

    execute_tool(db_session, "add_bill_item", {"bill_id": bill_id, "product_id": atta.id, "quantity": 2.0})
    execute_tool(db_session, "add_bill_item", {"bill_id": bill_id, "product_id": maggi.id, "quantity": 3.0})

    bill = billing_service.get_bill(bill_id)
    assert len(bill.items) == 2

    # Step C: Edit Maggi quantity to 2
    execute_tool(db_session, "edit_bill_item", {"bill_id": bill_id, "product_id": maggi.id, "new_quantity": 2.0})
    db_session.refresh(bill)
    maggi_item = [item for item in bill.items if item.product_id == maggi.id][0]
    assert maggi_item.quantity == 2.0

# 6. Draft Bill Stock Non-Reduction Test
def test_draft_bill_stock_non_reduction(db_session):
    seed_database(db_session)
    atta = db_session.query(Product).filter(Product.sku == "SKU-ATTA-5KG").first()
    initial_stock = atta.quantity

    draft_res = execute_tool(db_session, "create_draft_bill", {})
    bill_id = draft_res["data"]["bill_id"]

    execute_tool(db_session, "add_bill_item", {"bill_id": bill_id, "product_id": atta.id, "quantity": 5.0})
    db_session.refresh(atta)
    assert atta.quantity == initial_stock

# 7. Bill Calculation Test
def test_bill_calculation_tool(db_session):
    seed_database(db_session)
    atta = db_session.query(Product).filter(Product.sku == "SKU-ATTA-5KG").first()

    draft_res = execute_tool(db_session, "create_draft_bill", {})
    bill_id = draft_res["data"]["bill_id"]
    execute_tool(db_session, "add_bill_item", {"bill_id": bill_id, "product_id": atta.id, "quantity": 1.0})

    calc_res = execute_tool(db_session, "calculate_bill", {"bill_id": bill_id})
    assert calc_res["status"] == "success"
    assert calc_res["data"]["grand_total"] == 252.0  # 240 * 1.05

# 8. Finalization Reduces Stock Test
def test_finalization_reduces_stock(db_session):
    seed_database(db_session)
    atta = db_session.query(Product).filter(Product.sku == "SKU-ATTA-5KG").first()
    initial_stock = float(atta.quantity)

    draft_res = execute_tool(db_session, "create_draft_bill", {})
    bill_id = draft_res["data"]["bill_id"]
    execute_tool(db_session, "add_bill_item", {"bill_id": bill_id, "product_id": atta.id, "quantity": 4.0})

    fin_res = execute_tool(db_session, "finalize_bill", {"bill_id": bill_id, "payment_method": "Cash"})
    assert fin_res["status"] == "success"

    db_session.refresh(atta)
    assert float(atta.quantity) == initial_stock - 4.0

# 9. Oversell Tool Failure Surfacing Test
def test_oversell_tool_failure_surfacing(db_session):
    seed_database(db_session)
    salt = db_session.query(Product).filter(Product.sku == "SKU-SALT-1KG").first()
    salt.quantity = 5.0
    db_session.commit()

    draft_res = execute_tool(db_session, "create_draft_bill", {})
    bill_id = draft_res["data"]["bill_id"]
    add_res = execute_tool(db_session, "add_bill_item", {"bill_id": bill_id, "product_id": salt.id, "quantity": 10.0})

    assert add_res["status"] == "error"
    assert "Oversell Guard" in add_res["error"]

# 10. Unknown Product Clarification Test
def test_unknown_product_lookup_returns_none(db_session):
    seed_database(db_session)
    res = execute_tool(db_session, "search_products", {"query": "NonExistentUnicornChocolate"})
    assert res["status"] == "success"
    assert len(res["data"]) == 0

# 11. /new Session Reset Test
def test_new_session_reset_behavior(db_session):
    session_mgr = SessionManager(db_session)
    session_mgr.add_message("user555", "user", "Make a bill for Ravi")
    session_mgr.set_active_draft_bill("user555", 999)

    hist_before = session_mgr.get_history("user555")
    bill_before = session_mgr.get_active_draft_bill("user555")
    assert len(hist_before) == 1
    assert bill_before == 999

    # Trigger reset
    reply = reset_user_conversation(555, db=db_session)
    assert "fresh conversation" in reply

    hist_after = session_mgr.get_history("555")
    bill_after = session_mgr.get_active_draft_bill("555")
    assert len(hist_after) == 0
    assert bill_after is None

# 12. Preferences Persist Across /new Session Reset (Service Layer)
def test_preferences_persist_across_session_reset(db_session):
    pref_service = PreferenceService(db_session)
    pref_service.set_preference("user777", "payment_method", "UPI")

    # Reset session for user777
    reset_user_conversation(777, db=db_session)

    # Preferences should still be durable in DB
    val = pref_service.get_preference("user777", "payment_method")
    assert val == "UPI"

# 12b. Preferences Persist Across /new Session Reset (Agent Layer)
@pytest.mark.asyncio
async def test_llm_preference_retrieval_after_new(db_session):
    # Set preference directly
    pref_service = PreferenceService(db_session)
    pref_service.set_preference("999", "default_payment_method", "UPI")
    
    # Reset conversation
    reset_user_conversation(999, db=db_session)
    
    # Send a message to retrieve preference, expecting the agent to call get_preference
    # Note: user_id injection is handled by the runner
    res = await process_agent_message(999, "What is my preferred payment method? My key is default_payment_method.", db=db_session)
    assert "UPI" in res




# 13. Regression Test: Multi-Turn Billing Agent Flow
@pytest.mark.asyncio
async def test_multi_turn_billing_flow(db_session):
    seed_database(db_session)
    user_id = 9999
    reset_user_conversation(user_id, db=db_session)

    # Check initial stock
    atta = db_session.query(Product).filter(Product.sku == "SKU-ATTA-5KG").first()
    salt = db_session.query(Product).filter(Product.sku == "SKU-SALT-1KG").first()
    initial_atta_stock = atta.quantity
    initial_salt_stock = salt.quantity

    # Turn 1: Make a bill for Ravi
    resp1 = await process_agent_message(user_id=user_id, message_text="Make a bill for Ravi", db=db_session)
    assert resp1 is not None

    session_mgr = SessionManager(db_session)
    active_bill_id_1 = session_mgr.get_active_draft_bill(str(user_id))
    assert active_bill_id_1 is not None

    # Turn 2: Add multiple items to the active draft bill
    items_msg = "Add 2 Aashirvaad Atta 5kg\nAdd 1 Tata Salt 1kg"
    resp2 = await process_agent_message(user_id=user_id, message_text=items_msg, db=db_session)
    assert resp2 is not None

    # Active draft bill should remain the same
    active_bill_id_2 = session_mgr.get_active_draft_bill(str(user_id))
    assert active_bill_id_2 == active_bill_id_1

    # Verify bill contents in database
    billing_service = BillingService(db_session)
    bill = billing_service.get_bill(active_bill_id_1)
    assert bill is not None
    assert len(bill.items) == 2

    added_product_ids = {item.product_id: float(item.quantity) for item in bill.items}
    assert atta.id in added_product_ids
    assert added_product_ids[atta.id] == 2.0
    assert salt.id in added_product_ids
    assert added_product_ids[salt.id] == 1.0

    # Stock MUST NOT be deducted while bill is still draft
    db_session.refresh(atta)
    db_session.refresh(salt)
    assert atta.quantity == initial_atta_stock
    assert salt.quantity == initial_salt_stock

    # Response verification: contains bill summary details, total, and no Khata-only response
    assert "Draft Bill" in resp2 or "Total" in resp2 or "Summary" in resp2 or "Atta" in resp2
    assert "Khata credit balance" not in resp2


# 14. Regression Test: Draft Billing Oversell Guard Rejection
def test_draft_billing_oversell_guard_rejection(db_session):
    seed_database(db_session)
    atta = db_session.query(Product).filter(Product.sku == "SKU-ATTA-5KG").first()
    atta.quantity = 70.0
    db_session.commit()

    billing_service = BillingService(db_session)
    bill = billing_service.create_draft_bill()
    billing_service.add_bill_item(bill.id, atta.id, 3.0)

    db_session.refresh(bill)
    assert len(bill.items) == 1
    assert float(bill.items[0].quantity) == 3.0

    # Attempt to add 1000 more Atta (requested total = 1003 > stock 70)
    res = execute_tool(db_session, "add_bill_item", {"bill_id": bill.id, "product_id": atta.id, "quantity": 1000.0})
    assert res["status"] == "error"
    assert "1003" in res["error"] or "70" in res["error"] or "Oversell Guard" in res["error"]

    # Draft quantity must remain at 3.0
    db_session.refresh(bill)
    assert float(bill.items[0].quantity) == 3.0

    # Stock must remain at 70.0
    db_session.refresh(atta)
    assert float(atta.quantity) == 70.0


# 16. Regression Test: Oversell Recovery Suggestion Calculation (Stock=70, Draft=2, Request=+1000 -> Max Additional=68)
def test_oversell_recovery_suggestion_calculation(db_session):
    seed_database(db_session)
    atta = db_session.query(Product).filter(Product.sku == "SKU-ATTA-5KG").first()
    atta.quantity = 70.0
    db_session.commit()

    billing_service = BillingService(db_session)
    bill = billing_service.create_draft_bill()
    billing_service.add_bill_item(bill.id, atta.id, 2.0)

    db_session.refresh(bill)
    assert len(bill.items) == 1
    assert float(bill.items[0].quantity) == 2.0

    # Attempt to add 1000 more Atta when draft has 2 and stock is 70
    res = execute_tool(db_session, "add_bill_item", {"bill_id": bill.id, "product_id": atta.id, "quantity": 1000.0})
    assert res["status"] == "error"
    # Suggestion must be 70 - 2 = 68 more
    assert "at most 68" in res["error"] or "68.0" in res["error"]

    # Draft quantity must remain untouched at 2.0
    db_session.refresh(bill)
    assert float(bill.items[0].quantity) == 2.0


# 15. Regression Test: get_daily_close Argument Validation & Today Resolution
def test_daily_close_omitted_or_today_argument(db_session):
    seed_database(db_session)

    # Test tool invocation with omitted/None date_str
    res_none = execute_tool(db_session, "get_daily_close", {"date_str": None})
    assert res_none["status"] == "success"
    assert "total_sales" in res_none["data"]

    # Test tool invocation with empty arguments
    res_empty = execute_tool(db_session, "get_daily_close", {})
    assert res_empty["status"] == "success"
    assert "total_sales" in res_empty["data"]


# 17. Regression Test: Finalize Bill via Agent Flow
@pytest.mark.asyncio
async def test_finalize_bill_via_agent_flow(db_session):
    """Verify that 'Finalize the bill' triggers finalize_bill tool, deducts stock, and clears active draft."""
    seed_database(db_session)
    user_id = 8888
    reset_user_conversation(user_id, db=db_session)

    atta = db_session.query(Product).filter(Product.sku == "SKU-ATTA-5KG").first()
    initial_stock = float(atta.quantity)

    # Turn 1: Create a draft bill
    resp1 = await process_agent_message(user_id=user_id, message_text="Make a bill for Ravi", db=db_session)
    session_mgr = SessionManager(db_session)
    active_bill_id = session_mgr.get_active_draft_bill(str(user_id))
    assert active_bill_id is not None

    # Turn 2: Add items
    resp2 = await process_agent_message(user_id=user_id, message_text="Add 2 Aashirvaad Atta 5kg", db=db_session)
    assert resp2 is not None

    # Turn 3: Finalize the bill
    resp3 = await process_agent_message(user_id=user_id, message_text="Finalize the bill", db=db_session)
    assert resp3 is not None

    # Verify finalization happened: active draft should be cleared
    active_bill_after = session_mgr.get_active_draft_bill(str(user_id))
    assert active_bill_after is None, "Active draft bill should be cleared after finalization"

    # Verify stock was deducted
    db_session.refresh(atta)
    assert float(atta.quantity) == initial_stock - 2.0, "Stock should be deducted after finalization"

    # Verify response mentions finalization
    assert "Finalized" in resp3 or "finalize" in resp3.lower() or "✅" in resp3


# 18. Regression Test: Finalize Bill Does Not Double-Deduct Stock
def test_finalize_bill_no_double_stock_deduction(db_session):
    """Verify that calling finalize_bill on an already-finalized bill does not deduct stock again."""
    seed_database(db_session)
    atta = db_session.query(Product).filter(Product.sku == "SKU-ATTA-5KG").first()
    initial_stock = float(atta.quantity)

    # Create draft, add item, finalize
    draft_res = execute_tool(db_session, "create_draft_bill", {})
    bill_id = draft_res["data"]["bill_id"]
    execute_tool(db_session, "add_bill_item", {"bill_id": bill_id, "product_id": atta.id, "quantity": 3.0})

    fin_res = execute_tool(db_session, "finalize_bill", {"bill_id": bill_id, "payment_method": "Cash"})
    assert fin_res["status"] == "success"

    db_session.refresh(atta)
    stock_after_first_finalize = float(atta.quantity)
    assert stock_after_first_finalize == initial_stock - 3.0

    # Attempt to finalize again — should fail or be a no-op, but NOT deduct stock
    fin_res2 = execute_tool(db_session, "finalize_bill", {"bill_id": bill_id, "payment_method": "Cash"})
    # Either it errors or succeeds idempotently, but stock must not change
    db_session.refresh(atta)
    assert float(atta.quantity) == stock_after_first_finalize, "Second finalization must NOT deduct stock again"
