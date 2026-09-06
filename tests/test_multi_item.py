import pytest
from app.db.models import Product, Bill, BillItem
from app.agent.runner import process_agent_message
from app.agent.session_manager import SessionManager
from app.tools.billing_tools import create_draft_bill

@pytest.mark.asyncio
async def test_multi_item_billing(db_session):
    # Setup the mock catalog items
    from app.db.seed import seed_database
    seed_database(db_session)
    
    # Give user a draft bill
    draft_res = create_draft_bill(db_session)
    bill_id = draft_res["bill_id"]
    SessionManager(db_session).set_active_draft_bill("100", bill_id)
    
    # Message to add multiple items
    reply = await process_agent_message(100, "Add 2 Tata Salt 1kg, 3 Maggi 70g, and 1 Amul Butter 100g", db=db_session)
    
    # Check that they were added
    db_session.commit()
    bill = db_session.query(Bill).filter_by(id=bill_id).first()
    
    items = {item.product.name: float(item.quantity) for item in bill.items}
    
    assert "Tata Salt 1kg" in items, f"Tata Salt missing. Items: {items}"
    assert items["Tata Salt 1kg"] == 2.0
    
    assert "Maggi 70g" in items, f"Maggi missing. Items: {items}"
    assert items["Maggi 70g"] == 3.0
    
    assert "Amul Butter 100g" in items, f"Butter missing. Items: {items}"
    assert items["Amul Butter 100g"] == 1.0


@pytest.mark.asyncio
async def test_sequential_multi_item_billing_preserves_third_call(db_session):
    """
    Regression test explicitly ensuring that the final/third tool call (Butter)
    is not dropped when the LLM/provider executes them sequentially over multiple turns.
    """
    from app.db.seed import seed_database
    seed_database(db_session)
    
    draft_res = create_draft_bill(db_session)
    bill_id = draft_res["bill_id"]
    SessionManager(db_session).set_active_draft_bill("101", bill_id)
    
    # Message to add 3 items sequentially via the mock LLM
    await process_agent_message(101, "Add 1 Tata Salt 1kg, 2 Maggi 70g, 3 Amul Butter 100g", db=db_session)
    
    db_session.commit()
    bill = db_session.query(Bill).filter_by(id=bill_id).first()
    items = {item.product.name: float(item.quantity) for item in bill.items}
    
    # Verify the 3rd item is present
    assert "Amul Butter 100g" in items, "The third requested item was dropped during sequential execution!"
    assert items["Amul Butter 100g"] == 3.0
    assert len(items) == 3
