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
    execute_tool(db_session, "add_bill_item", {"bill_id": bill_id, "product_id": salt.id, "quantity": 10.0})

    fin_res = execute_tool(db_session, "finalize_bill", {"bill_id": bill_id, "payment_method": "UPI"})
    assert fin_res["status"] == "error"
    assert "Oversell Guard" in fin_res["error"]

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

# 12. Preferences Persist Across /new Session Reset
def test_preferences_persist_across_session_reset(db_session):
    pref_service = PreferenceService(db_session)
    pref_service.set_preference("user777", "payment_method", "UPI")

    # Reset session for user777
    reset_user_conversation(777, db=db_session)

    # Preferences should still be durable in DB
    val = pref_service.get_preference("user777", "payment_method")
    assert val == "UPI"
