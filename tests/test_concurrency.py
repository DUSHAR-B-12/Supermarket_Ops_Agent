import asyncio
import pytest
from app.db.models import Product, Bill, BillItem, BillStatus
from app.db.session import SessionLocal, Base, engine
from app.services.billing_service import BillingService
from concurrent.futures import ThreadPoolExecutor

@pytest.fixture
def fresh_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Create test product with exactly 1 qty
    p = Product(sku="TEST-SKU", name="Test Item", selling_price=10.0, cost_price=5.0, quantity=1.0)
    db.add(p)
    db.commit()
    db.refresh(p)
    
    yield db
    
    db.close()
    Base.metadata.drop_all(bind=engine)

def checkout_worker(bill_id: int):
    # Need independent DB session per thread to simulate real concurrency
    local_db = SessionLocal()
    billing_service = BillingService(local_db)
    try:
        res = billing_service.finalize_bill(bill_id)
        local_db.close()
        return True, res
    except ValueError as e:
        local_db.close()
        return False, str(e)
    except Exception as e:
        local_db.close()
        return False, str(e)

@pytest.mark.asyncio
async def test_concurrent_oversell(fresh_db):
    product = fresh_db.query(Product).filter(Product.sku == "TEST-SKU").first()
    
    billing_service = BillingService(fresh_db)
    
    # Create two different bills that both want 1 item (only 1 exists)
    bill1 = billing_service.create_draft_bill()
    billing_service.add_bill_item(bill1.id, product.id, 1.0)
    
    bill2 = billing_service.create_draft_bill()
    billing_service.add_bill_item(bill2.id, product.id, 1.0)
    
    # Execute both finalize_bill requests concurrently using threads
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = loop.run_in_executor(pool, checkout_worker, bill1.id)
        f2 = loop.run_in_executor(pool, checkout_worker, bill2.id)
        
        results = await asyncio.gather(f1, f2)
    
    # Exactly one should succeed, one should fail
    successes = [r for r in results if r[0] is True]
    failures = [r for r in results if r[0] is False]
    print(f"Successes: {len(successes)}, Failures: {len(failures)}")
    fresh_db.expire_all()
    print(f"Final Quantity: {fresh_db.query(Product).filter(Product.sku == 'TEST-SKU').first().quantity}")
    
    assert len(successes) == 1
    assert len(failures) == 1
    
    assert "Concurrency Error" in failures[0][1]
    
    # Verify DB state
    fresh_db.expire_all()
    final_product = fresh_db.query(Product).filter(Product.sku == "TEST-SKU").first()
    assert float(final_product.quantity) == 0.0
    
    b1 = fresh_db.query(Bill).filter(Bill.id == bill1.id).first()
    b2 = fresh_db.query(Bill).filter(Bill.id == bill2.id).first()
    
    # One is finalized, one is draft
    statuses = {b1.status, b2.status}
    assert statuses == {BillStatus.FINALIZED, BillStatus.DRAFT}
