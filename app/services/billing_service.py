from datetime import datetime
from typing import List, Optional
import uuid

from sqlalchemy.orm import Session

from app.db.models import Bill, BillItem, BillStatus, Product, StockMovement, StockMovementType
from app.services.inventory_service import InventoryService
from app.services.khata_service import KhataService
from app.services.tax_service import TaxService


class BillingService:
    def __init__(self, db: Session):
        self.db = db
        self.tax_service = TaxService()
        self.inventory_service = InventoryService(db)
        self.khata_service = KhataService(db)

    def generate_bill_number(self) -> str:
        now_str = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_suffix = uuid.uuid4().hex[:4].upper()
        return f"INV-{now_str}-{unique_suffix}"

    def create_draft_bill(
        self, customer_id: Optional[int] = None, idempotency_key: Optional[str] = None
    ) -> Bill:
        if idempotency_key:
            existing = self.db.query(Bill).filter(Bill.idempotency_key == idempotency_key).first()
            if existing:
                return existing

        bill = Bill(
            bill_number=self.generate_bill_number(),
            customer_id=customer_id,
            status=BillStatus.DRAFT,
            subtotal=0.0,
            cgst=0.0,
            sgst=0.0,
            total_tax=0.0,
            grand_total=0.0,
            idempotency_key=idempotency_key,
        )
        self.db.add(bill)
        self.db.commit()
        self.db.refresh(bill)
        return bill

    def add_bill_item(self, bill_id: int, product_id: int, quantity: float) -> Bill:
        bill = self.db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise ValueError(f"Bill ID {bill_id} not found.")

        if bill.status != BillStatus.DRAFT:
            raise ValueError(f"Cannot modify bill {bill_id} because it is already {bill.status.value}.")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product or not product.active:
            raise ValueError(f"Product ID {product_id} is invalid or inactive.")

        if product.selling_price < product.cost_price:
            raise ValueError(
                f"Cannot add product '{product.name}': Selling price ({product.selling_price}) "
                f"is below cost price ({product.cost_price})."
            )

        # Check if item already in draft bill
        existing_item = (
            self.db.query(BillItem)
            .filter(BillItem.bill_id == bill_id, BillItem.product_id == product_id)
            .first()
        )

        if existing_item:
            new_qty = float(existing_item.quantity) + float(quantity)
            tax_breakup = self.tax_service.calculate_item_tax(
                unit_price=float(product.selling_price),
                quantity=new_qty,
                gst_rate=float(product.gst_rate),
            )
            existing_item.quantity = new_qty
            existing_item.taxable_amount = tax_breakup["taxable_amount"]
            existing_item.cgst = tax_breakup["cgst_amount"]
            existing_item.sgst = tax_breakup["sgst_amount"]
            existing_item.total = tax_breakup["total_amount"]
        else:
            tax_breakup = self.tax_service.calculate_item_tax(
                unit_price=float(product.selling_price),
                quantity=quantity,
                gst_rate=float(product.gst_rate),
            )
            item = BillItem(
                bill_id=bill_id,
                product_id=product_id,
                quantity=quantity,
                unit_price=float(product.selling_price),
                cost_price=float(product.cost_price),
                gst_rate=float(product.gst_rate),
                taxable_amount=tax_breakup["taxable_amount"],
                cgst=tax_breakup["cgst_amount"],
                sgst=tax_breakup["sgst_amount"],
                total=tax_breakup["total_amount"],
            )
            self.db.add(item)

        self.db.commit()
        return self.calculate_bill(bill_id)

    def edit_bill_item(self, bill_id: int, product_id: int, new_quantity: float) -> Bill:
        bill = self.db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise ValueError(f"Bill ID {bill_id} not found.")

        if bill.status != BillStatus.DRAFT:
            raise ValueError(f"Cannot edit bill {bill_id} because it is already {bill.status.value}.")

        if new_quantity <= 0:
            return self.remove_bill_item(bill_id, product_id)

        item = (
            self.db.query(BillItem)
            .filter(BillItem.bill_id == bill_id, BillItem.product_id == product_id)
            .first()
        )
        if not item:
            raise ValueError(f"Product ID {product_id} is not present in bill {bill_id}.")

        tax_breakup = self.tax_service.calculate_item_tax(
            unit_price=float(item.unit_price),
            quantity=new_quantity,
            gst_rate=float(item.gst_rate),
        )
        item.quantity = new_quantity
        item.taxable_amount = tax_breakup["taxable_amount"]
        item.cgst = tax_breakup["cgst_amount"]
        item.sgst = tax_breakup["sgst_amount"]
        item.total = tax_breakup["total_amount"]

        self.db.commit()
        return self.calculate_bill(bill_id)

    def remove_bill_item(self, bill_id: int, product_id: int) -> Bill:
        bill = self.db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise ValueError(f"Bill ID {bill_id} not found.")

        if bill.status != BillStatus.DRAFT:
            raise ValueError(f"Cannot modify bill {bill_id} because it is already {bill.status.value}.")

        item = (
            self.db.query(BillItem)
            .filter(BillItem.bill_id == bill_id, BillItem.product_id == product_id)
            .first()
        )
        if item:
            self.db.delete(item)
            self.db.commit()

        return self.calculate_bill(bill_id)

    def get_bill(self, bill_id: int) -> Optional[Bill]:
        return self.db.query(Bill).filter(Bill.id == bill_id).first()

    def calculate_bill(self, bill_id: int) -> Bill:
        bill = self.db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise ValueError(f"Bill ID {bill_id} not found.")

        subtotal = 0.0
        total_cgst = 0.0
        total_sgst = 0.0

        for item in bill.items:
            subtotal += float(item.taxable_amount)
            total_cgst += float(item.cgst)
            total_sgst += float(item.sgst)

        total_tax = total_cgst + total_sgst
        grand_total = subtotal + total_tax

        bill.subtotal = round(subtotal, 2)
        bill.cgst = round(total_cgst, 2)
        bill.sgst = round(total_sgst, 2)
        bill.total_tax = round(total_tax, 2)
        bill.grand_total = round(grand_total, 2)

        self.db.commit()
        self.db.refresh(bill)
        return bill

    def finalize_bill(
        self,
        bill_id: int,
        payment_method: str = "Cash",
        payment_reference: Optional[str] = None,
        customer_id: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Bill:
        bill = self.db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise ValueError(f"Bill ID {bill_id} not found.")

        # Double finalization protection
        if bill.status == BillStatus.FINALIZED:
            return bill

        if bill.status == BillStatus.CANCELLED:
            raise ValueError(f"Cannot finalize bill {bill_id} because it was cancelled.")

        if not bill.items:
            raise ValueError("Cannot finalize an empty bill with no items.")

        # Assign customer if provided
        if customer_id:
            bill.customer_id = customer_id

        valid_methods = ["Cash", "UPI", "Card", "Khata"]
        if payment_method not in valid_methods:
            raise ValueError(f"Invalid payment method '{payment_method}'. Must be one of {valid_methods}.")

        if payment_method == "Khata":
            if not bill.customer_id:
                raise ValueError("Khata payment requires a valid customer.")

        # Pre-validate stock and pricing for all items
        for item in bill.items:
            product = self.db.query(Product).filter(Product.id == item.product_id).first()
            if not product:
                raise ValueError(f"Product ID {item.product_id} no longer exists.")
            if product.selling_price < product.cost_price:
                raise ValueError(
                    f"Refusing finalization: '{product.name}' selling price ({product.selling_price}) "
                    f"is below cost price ({product.cost_price})."
                )
            self.inventory_service.validate_stock_availability(
                product_id=product.id, requested_qty=float(item.quantity)
            )

        # Recalculate bill values
        self.calculate_bill(bill_id)

        # Atomic transaction execution: deduct stock & update status
        for item in bill.items:
            product = self.db.query(Product).filter(Product.id == item.product_id).first()
            product.quantity = float(product.quantity) - float(item.quantity)
            movement = StockMovement(
                product_id=product.id,
                movement_type=StockMovementType.OUT,
                quantity=item.quantity,
                reference=f"Bill Finalization #{bill.bill_number}",
            )
            self.db.add(movement)

        # Record Khata transaction if payment is Khata
        if payment_method == "Khata" and bill.customer_id:
            self.khata_service.record_credit(
                customer_id=bill.customer_id,
                amount=float(bill.grand_total),
                reference=f"Khata Purchase Bill #{bill.bill_number}",
            )

        bill.status = BillStatus.FINALIZED
        bill.payment_method = payment_method
        bill.payment_reference = payment_reference
        bill.finalized_at = datetime.utcnow()
        if idempotency_key:
            bill.idempotency_key = idempotency_key

        self.db.commit()
        self.db.refresh(bill)
        return bill
