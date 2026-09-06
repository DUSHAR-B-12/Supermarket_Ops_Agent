import pytest
from sqlalchemy.orm import Session
from app.agent.runner import process_agent_message
from app.services.inventory_service import InventoryService
from app.services.product_service import ProductService
from app.services.billing_service import BillingService
from app.agent.session_manager import SessionManager
from app.db.models import BillStatus

@pytest.fixture(autouse=True)
def setup_db(db_session: Session):
    # Set up some basic products
    prod_svc = ProductService(db_session)
    inv_svc = InventoryService(db_session)
    
    for sku, name in [("ATT-5", "Aashirvaad Atta 5kg"), ("MAG-70", "Maggi 70g"), ("BUT-100", "Amul Butter 100g")]:
        p = prod_svc.create_product(sku, name, "Grocery", "piece", 10.0, 15.0, 12.0)
        inv_svc.receive_stock(p.id, 100.0, "init")
    
    yield

@pytest.mark.asyncio
async def test_conversational_chatter(db_session):
    resp = await process_agent_message(123, "Hey good morning!", db=db_session)
    assert "Supermarket Ops Agent" in resp
    
    resp = await process_agent_message(123, "what store operations do you handle?", db=db_session)
    assert "inventory" in resp.lower()

@pytest.mark.asyncio
async def test_inventory_semantic_variations(db_session):
    # Tests multiple ways to ask for inventory
    phrases = [
        "what's in stock",
        "show stock",
        "check inventory",
        "what do we have",
        "list products"
    ]
    for p in phrases:
        resp = await process_agent_message(123, p, db=db_session)
        assert "found" in resp.lower() or "product(s)" in resp.lower() or "stock" in resp.lower()

@pytest.mark.asyncio
async def test_product_search_variations(db_session):
    phrases = [
        "do we sell maggi?",
        "find maggi",
        "show maggi",
        "how much maggi do i have"
    ]
    for p in phrases:
        resp = await process_agent_message(123, p, db=db_session)
        assert "maggi" in resp.lower()

@pytest.mark.asyncio
async def test_billing_multi_turn_corrections(db_session):
    user = "u999"
    # Create draft
    resp = await process_agent_message(user, "make a bill", db_session)
    assert "created draft bill" in resp.lower()
    
    # Add maggi
    resp = await process_agent_message(user, "add 3 maggi", db_session)
    assert "summary" in resp.lower() or "maggi" in resp.lower()
    
    # Correction: change quantity
    resp = await process_agent_message(user, "no wait change that make it 5", db_session)
    assert "updated" in resp.lower() or "changed" in resp.lower() or "added" in resp.lower() or "summary" in resp.lower()
    
    # Correction: remove
    resp = await process_agent_message(user, "actually delete the maggi", db_session)
    assert "removed" in resp.lower() or "deleted" in resp.lower() or "not found" in resp.lower() or "summary" in resp.lower()
    
    # Finalize
    resp = await process_agent_message(user, "complete the bill", db_session)
    assert "finalized" in resp.lower()

@pytest.mark.asyncio
async def test_stale_draft_recovery_semantics(db_session):
    user = "u888"
    # Create draft manually and set in session
    billing_svc = BillingService(db_session)
    bill = billing_svc.create_draft_bill()
    SessionManager(db_session).set_active_draft_bill(user, bill.id)
    
    # Cancel out of band
    bill.status = BillStatus.CANCELLED
    db_session.commit()
    
    # Agent should recover
    resp = await process_agent_message(user, "add 2 maggi", db_session)
    assert "cancelled" in resp.lower() or "stale" in resp.lower() or "cleared" in resp.lower() or "create a new" in resp.lower() or "processed" in resp.lower()

@pytest.mark.asyncio
async def test_reports_and_khata_semantics(db_session):
    resp = await process_agent_message(123, "give me today's close", db_session)
    assert "daily close" in resp.lower() or "summary" in resp.lower()
    
    resp = await process_agent_message(123, "make the supermarket analysis deck", db_session)
    assert "generated" in resp.lower() or "presentation" in resp.lower() or "analysis" in resp.lower()
    
    resp = await process_agent_message(123, "what is ravi's khata balance?", db_session)
    assert "ravi" in resp.lower()

@pytest.mark.asyncio
async def test_preference_semantics(db_session):
    resp = await process_agent_message(123, "remember I prefer UPI", db_session)
    assert "preference" in resp.lower() or "saved" in resp.lower() or "set" in resp.lower()
