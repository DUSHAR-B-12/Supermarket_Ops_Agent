import pytest
from app.db.models import Product, StockMovement, StockMovementType, BillStatus
from app.services.product_service import ProductService
from app.services.inventory_service import InventoryService
from app.services.tax_service import TaxService
from app.services.billing_service import BillingService
from app.services.khata_service import KhataService
from app.services.preference_service import PreferenceService

# 1. Product Creation Test
def test_product_creation(db_session):
    service = ProductService(db_session)
    product = service.create_product(
        sku="TEST-SKU-1",
        name="Test Biscuit",
        category="Snacks",
        unit="packet",
        cost_price=10.0,
        mrp=15.0,
        selling_price=12.0,
        gst_rate=18.0,
        initial_quantity=50.0,
    )
    assert product.id is not None
    assert product.sku == "TEST-SKU-1"
    assert product.selling_price == 12.0

# 2. Stock Receiving Test
def test_stock_receiving(db_session):
    product_service = ProductService(db_session)
    p = product_service.create_product(
        sku="TEST-SKU-2",
        name="Test Oil",
        category="Oil",
        unit="litre",
        cost_price=100.0,
        mrp=120.0,
        selling_price=110.0,
        initial_quantity=10.0,
    )
    inv_service = InventoryService(db_session)
    updated_p = inv_service.receive_stock(p.id, 25.0, reference="Vendor Delivery #101")
    assert updated_p.quantity == 35.0

# 3. Stock Movement Recording Test
def test_stock_movement_recording(db_session):
    product_service = ProductService(db_session)
    p = product_service.create_product(
        sku="TEST-SKU-3",
        name="Test Atta",
        category="Staples",
        unit="packet",
        cost_price=200.0,
        mrp=250.0,
        selling_price=230.0,
        initial_quantity=5.0,
    )
    inv_service = InventoryService(db_session)
    inv_service.receive_stock(p.id, 15.0, reference="GRN-555")

    movements = db_session.query(StockMovement).filter(StockMovement.product_id == p.id).all()
    assert len(movements) == 1
    assert movements[0].movement_type == StockMovementType.IN
    assert movements[0].quantity == 15.0
    assert movements[0].reference == "GRN-555"

# 4. Low-Stock Detection Test
def test_low_stock_detection(db_session):
    product_service = ProductService(db_session)
    p1 = product_service.create_product(
        sku="LOW-1", name="Item Low", category="Cat", unit="pc",
        cost_price=5.0, mrp=10.0, selling_price=8.0, initial_quantity=2.0, reorder_level=5.0
    )
    p2 = product_service.create_product(
        sku="HIGH-1", name="Item High", category="Cat", unit="pc",
        cost_price=5.0, mrp=10.0, selling_price=8.0, initial_quantity=20.0, reorder_level=5.0
    )
    inv_service = InventoryService(db_session)
    low_stock = inv_service.get_low_stock()
    low_skus = [p.sku for p in low_stock]
    assert "LOW-1" in low_skus
    assert "HIGH-1" not in low_skus

# 5. GST Calculation for Multiple Rates (0%, 5%, 12%, 18%)
def test_gst_calculation_rates():
    tax_service = TaxService()

    # 0% GST (Loose staples)
    t0 = tax_service.calculate_item_tax(unit_price=50.0, quantity=2.0, gst_rate=0.0)
    assert t0["taxable_amount"] == 100.0
    assert t0["cgst_amount"] == 0.0
    assert t0["sgst_amount"] == 0.0
    assert t0["total_amount"] == 100.0

    # 5% GST (Packaged staples)
    t5 = tax_service.calculate_item_tax(unit_price=200.0, quantity=1.0, gst_rate=5.0)
    assert t5["taxable_amount"] == 200.0
    assert t5["cgst_amount"] == 5.0  # 2.5%
    assert t5["sgst_amount"] == 5.0  # 2.5%
    assert t5["total_tax"] == 10.0
    assert t5["total_amount"] == 210.0

    # 12% GST (FMCG Butter/Maggi)
    t12 = tax_service.calculate_item_tax(unit_price=60.0, quantity=1.0, gst_rate=12.0)
    assert t12["taxable_amount"] == 60.0
    assert t12["cgst_amount"] == 3.6  # 6%
    assert t12["sgst_amount"] == 3.6  # 6%
    assert t12["total_tax"] == 7.2
    assert t12["total_amount"] == 67.2

    # 18% GST (Surf Excel / Parle-G)
    t18 = tax_service.calculate_item_tax(unit_price=100.0, quantity=1.0, gst_rate=18.0)
    assert t18["taxable_amount"] == 100.0
    assert t18["cgst_amount"] == 9.0  # 9%
    assert t18["sgst_amount"] == 9.0  # 9%
    assert t18["total_tax"] == 18.0
    assert t18["total_amount"] == 118.0

# 6. Bill Calculation Test
def test_bill_calculation(db_session):
    p_service = ProductService(db_session)
    p1 = p_service.create_product(sku="B1", name="Butter", category="D", unit="pc", cost_price=50.0, mrp=60.0, selling_price=60.0, gst_rate=12.0, initial_quantity=10.0)
    p2 = p_service.create_product(sku="B2", name="Atta", category="S", unit="pc", cost_price=200.0, mrp=240.0, selling_price=240.0, gst_rate=5.0, initial_quantity=10.0)

    b_service = BillingService(db_session)
    bill = b_service.create_draft_bill()
    b_service.add_bill_item(bill.id, p1.id, 1.0)  # 60 + 7.20 = 67.20
    b_service.add_bill_item(bill.id, p2.id, 1.0)  # 240 + 12.00 = 252.00

    calc_bill = b_service.calculate_bill(bill.id)
    assert float(calc_bill.subtotal) == 300.0
    assert float(calc_bill.total_tax) == 19.2
    assert float(calc_bill.grand_total) == 319.2


# 7. Selling Price From Database Behavior
def test_selling_price_from_db(db_session):
    p_service = ProductService(db_session)
    p = p_service.create_product(sku="DBPRICE-1", name="Sugar", category="S", unit="kg", cost_price=30.0, mrp=40.0, selling_price=35.0, initial_quantity=50.0)

    b_service = BillingService(db_session)
    bill = b_service.create_draft_bill()
    b_service.add_bill_item(bill.id, p.id, 2.0)

    item = bill.items[0]
    assert item.unit_price == 35.0

# 8. Below-Cost Sale Rejection
def test_below_cost_sale_rejection(db_session):
    p_service = ProductService(db_session)
    with pytest.raises(ValueError, match="cannot be below cost price"):
        p_service.create_product(sku="LOSS-1", name="Loss Item", category="C", unit="pc", cost_price=100.0, mrp=110.0, selling_price=90.0)

# 9. Draft Bill Does Not Reduce Stock
def test_draft_bill_does_not_reduce_stock(db_session):
    p_service = ProductService(db_session)
    p = p_service.create_product(sku="DRAFT-STOCK-1", name="Rice", category="S", unit="kg", cost_price=40.0, mrp=50.0, selling_price=45.0, initial_quantity=100.0)

    b_service = BillingService(db_session)
    bill = b_service.create_draft_bill()
    b_service.add_bill_item(bill.id, p.id, 10.0)

    db_session.refresh(p)
    assert p.quantity == 100.0

# 10. Finalized Bill Reduces Stock
def test_finalized_bill_reduces_stock(db_session):
    p_service = ProductService(db_session)
    p = p_service.create_product(sku="FINAL-STOCK-1", name="Dal", category="S", unit="kg", cost_price=80.0, mrp=100.0, selling_price=95.0, initial_quantity=50.0)

    b_service = BillingService(db_session)
    bill = b_service.create_draft_bill()
    b_service.add_bill_item(bill.id, p.id, 10.0)

    finalized = b_service.finalize_bill(bill.id, payment_method="Cash")
    assert finalized.status == BillStatus.FINALIZED

    db_session.refresh(p)
    assert p.quantity == 40.0

# 11. Oversell Rejection
def test_oversell_rejection(db_session):
    p_service = ProductService(db_session)
    p = p_service.create_product(sku="OVERSELL-1", name="Salt", category="S", unit="packet", cost_price=15.0, mrp=20.0, selling_price=18.0, initial_quantity=6.0)

    b_service = BillingService(db_session)
    bill = b_service.create_draft_bill()
    b_service.add_bill_item(bill.id, p.id, 10.0)

    with pytest.raises(ValueError, match="Oversell Guard"):
        b_service.finalize_bill(bill.id, payment_method="Cash")

# 12. Double-Finalization Protection
def test_double_finalization_protection(db_session):
    p_service = ProductService(db_session)
    p = p_service.create_product(sku="DOUBLE-FIN-1", name="Maggi", category="FMCG", unit="packet", cost_price=10.0, mrp=14.0, selling_price=14.0, initial_quantity=20.0)

    b_service = BillingService(db_session)
    bill = b_service.create_draft_bill()
    b_service.add_bill_item(bill.id, p.id, 5.0)

    b_service.finalize_bill(bill.id, payment_method="Cash")
    db_session.refresh(p)
    assert p.quantity == 15.0

    # Second finalization call should return existing finalized bill without reducing stock again
    b_service.finalize_bill(bill.id, payment_method="Cash")
    db_session.refresh(p)
    assert p.quantity == 15.0

# 13. Khata Credit Test
def test_khata_credit(db_session):
    khata_service = KhataService(db_session)
    customer = khata_service.get_or_create_customer(name="Ramesh", phone="9876543210")
    assert float(customer.credit_balance) == 0.0

    updated = khata_service.record_credit(customer.id, 500.0, reference="Credit sale")
    assert float(updated.credit_balance) == 500.0

# 14. Khata Repayment Test
def test_khata_repayment(db_session):
    khata_service = KhataService(db_session)
    customer = khata_service.get_or_create_customer(name="Suresh")
    khata_service.record_credit(customer.id, 500.0)

    updated = khata_service.record_repayment(customer.id, 300.0)
    assert float(updated.credit_balance) == 200.0


    # Non-existent customer repayment rejection
    with pytest.raises(ValueError, match="does not exist"):
        khata_service.record_repayment(customer_id=99999, amount=100.0)

# 15. Preference Persistence Test
def test_preference_persistence(db_session):
    pref_service = PreferenceService(db_session)
    pref_service.set_preference(user_id="12345", key="payment_method", value="UPI")
    pref_service.set_preference(user_id="12345", key="default_atta", value="Aashirvaad 5kg")

    val1 = pref_service.get_preference(user_id="12345", key="payment_method")
    val2 = pref_service.get_preference(user_id="12345", key="default_atta")

    assert val1 == "UPI"
    assert val2 == "Aashirvaad 5kg"
