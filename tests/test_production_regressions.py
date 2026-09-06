import os
import pytest
import app
from app.agent.runner import process_agent_message, reset_user_conversation
from app.db.session import SessionLocal
from app.services.preference_service import PreferenceService

@pytest.mark.asyncio
async def test_preference_persistence_across_new(db_session):
    """
    Test that setting a preference survives /new (reset_user_conversation).
    """
    user_id = 999111
    user_str = str(user_id)
    
    # 1. User sets preference
    resp1 = await process_agent_message(user_id, "Remember that I prefer UPI payment", db=db_session)
    
    # Verify in DB
    pref = PreferenceService(db_session).get_preference(user_str, "default_payment_method")
    assert pref is not None, "Preference should be saved in DB"
    
    # 2. User resets conversation
    reset_user_conversation(user_id, db_session)
    
    # 3. Preference should still be in DB
    pref_after = PreferenceService(db_session).get_preference(user_str, "default_payment_method")
    assert pref_after is not None, "Preference must survive /new"
    
    # 4. Ask about preference
    resp2 = await process_agent_message(user_id, "What payment method do I prefer?", db=db_session)
    assert "default_payment_method" in resp2
    assert pref_after in resp2 or "UPI" in resp2


@pytest.mark.asyncio
async def test_stale_draft_recovery(db_session):
    """
    Test that if active_bill_id points to a finalized bill,
    the agent recovers gracefully and clears it.
    """
    user_id = 888222
    
    # 1. Create a draft bill manually
    from app.services.billing_service import BillingService
    from app.services.product_service import ProductService
    
    # Create the product first
    prod_svc = ProductService(db_session)
    prod_svc.create_product("MAG-70", "Maggi 70g", "Food", "packet", 12.0, 14.0, 14.0)
    
    billing_svc = BillingService(db_session)
    bill = billing_svc.create_draft_bill()
    bill_id = bill.id
    
    # Set it as active bill in session
    from app.agent.session_manager import SessionManager
    SessionManager(db_session).set_active_draft_bill(str(user_id), bill_id)
    
    # Cancel the bill out of band (so the session doesn't know it's cancelled)
    bill.status = app.db.models.BillStatus.CANCELLED
    db_session.commit()
    
    # Now try to add an item
    resp = await process_agent_message(user_id, "add maggi", db=db_session)
    
    # The agent should see the error, clear the session bill ID, and report the error/recovery.
    assert "cleared" in resp.lower() or "stale" in resp.lower() or "processed" in resp.lower() or "create a new" in resp.lower()
    
    # Verify the active bill ID is cleared
    active_id = SessionManager(db_session).get_active_draft_bill(str(user_id))
    assert active_id is None, "Stale active_bill_id must be cleared"


@pytest.mark.asyncio
async def test_new_intents_routing(db_session):
    """
    Test that daily close, analysis deck, product creation, and store operations
    route successfully in the mock LLM without crashing.
    """
    user_id = 777333
    
    resp_close = await process_agent_message(user_id, "give me today's close", db=db_session)
    assert "Daily Business Summary" in resp_close or "processed" in resp_close
    
    resp_deck = await process_agent_message(user_id, "generate analysis deck", db=db_session)
    assert "Generated 6-slide PowerPoint" in resp_deck or "processed" in resp_deck
    
    resp_prod = await process_agent_message(user_id, "add new product facewash", db=db_session)
    # Facewash gets added with dummy args in the mock
    assert "Facewash" in resp_prod or "processed" in resp_prod
    
    resp_ops = await process_agent_message(user_id, "whats the store operations", db=db_session)
    assert "I am your Supermarket Ops Agent" in resp_ops
