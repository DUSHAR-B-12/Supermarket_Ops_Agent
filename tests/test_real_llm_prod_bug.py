import asyncio
import json
import logging
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, init_db
from app.agent.runner import process_agent_message, reset_user_conversation
from app.services.product_service import ProductService
from app.services.inventory_service import InventoryService

logging.basicConfig(level=logging.WARNING)

async def main():
    init_db()
    db = SessionLocal()
    
    # Ensure Maggi exists
    prod_svc = ProductService(db)
    inv_svc = InventoryService(db)
    
    try:
        p = prod_svc.create_product("MAG-70", "Maggi 70g", "Grocery", "packet", 12.0, 15.0, 14.0)
        inv_svc.receive_stock(p.id, 100, "init")
    except Exception:
        pass # Already exists
        
    db.commit()

    user = "real_gemini_prod_test"
    reset_user_conversation(user, db)
    
    print("\n--- Test 1: Combined Intent ---")
    msg1 = "make a bill for hari, add maggi 2 packets"
    print(f"User: {msg1}")
    resp1 = await process_agent_message(user, msg1, db)
    print(f"Agent: {resp1}")
    
    print("\n--- Test 2: Modify Bill ---")
    msg2 = "make maggi 3"
    print(f"User: {msg2}")
    resp2 = await process_agent_message(user, msg2, db)
    print(f"Agent: {resp2}")
    
    print("\n--- Test 3: Duplicate Call Loop Test ---")
    msg3 = "make maggi 3"
    print(f"User: {msg3}")
    resp3 = await process_agent_message(user, msg3, db)
    print(f"Agent: {resp3}")
    
    print("\n--- Test 4: Finalize ---")
    msg4 = "complete the bill"
    print(f"User: {msg4}")
    resp4 = await process_agent_message(user, msg4, db)
    print(f"Agent: {resp4}")

    db.close()

if __name__ == "__main__":
    asyncio.run(main())
