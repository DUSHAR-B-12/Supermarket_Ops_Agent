from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.services.billing_service import BillingService

def create_draft_bill(
    db: Session, customer_id: Optional[int] = None, idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    service = BillingService(db)
    bill = service.create_draft_bill(customer_id=customer_id, idempotency_key=idempotency_key)
    return {"bill_id": bill.id, "bill_number": bill.bill_number, "status": bill.status.value}

def add_bill_item(db: Session, bill_id: int, product_id: int, quantity: float) -> Dict[str, Any]:
    service = BillingService(db)
    bill = service.add_bill_item(bill_id=bill_id, product_id=product_id, quantity=quantity)
    return get_bill(db, bill.id)

def edit_bill_item(db: Session, bill_id: int, product_id: int, new_quantity: float) -> Dict[str, Any]:
    service = BillingService(db)
    bill = service.edit_bill_item(bill_id=bill_id, product_id=product_id, new_quantity=new_quantity)
    return get_bill(db, bill.id)

def remove_bill_item(db: Session, bill_id: int, product_id: int) -> Dict[str, Any]:
    service = BillingService(db)
    bill = service.remove_bill_item(bill_id=bill_id, product_id=product_id)
    return get_bill(db, bill.id)

def get_bill(db: Session, bill_id: int) -> Optional[Dict[str, Any]]:
    service = BillingService(db)
    bill = service.get_bill(bill_id)
    if not bill:
        return None
    return {
        "id": bill.id,
        "bill_id": bill.id,
        "bill_number": bill.bill_number,
        "customer_id": bill.customer_id,
        "status": bill.status.value,
        "subtotal": float(bill.subtotal),
        "cgst": float(bill.cgst),
        "sgst": float(bill.sgst),
        "total_tax": float(bill.total_tax),
        "grand_total": float(bill.grand_total),
        "item_count": len(bill.items),
        "payment_method": bill.payment_method,
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product.name if item.product else "",
                "quantity": float(item.quantity),
                "unit_price": float(item.unit_price),
                "gst_rate": float(item.gst_rate),
                "cgst": float(item.cgst),
                "sgst": float(item.sgst),
                "total": float(item.total),
            }
            for item in bill.items
        ],
    }

def calculate_bill(db: Session, bill_id: int) -> Dict[str, Any]:
    service = BillingService(db)
    bill = service.calculate_bill(bill_id)
    return {
        "bill_id": bill.id,
        "subtotal": float(bill.subtotal),
        "cgst": float(bill.cgst),
        "sgst": float(bill.sgst),
        "total_tax": float(bill.total_tax),
        "grand_total": float(bill.grand_total),
    }

def finalize_bill(
    db: Session,
    bill_id: int,
    payment_method: str = "Cash",
    payment_reference: Optional[str] = None,
    customer_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    service = BillingService(db)
    bill = service.finalize_bill(
        bill_id=bill_id,
        payment_method=payment_method,
        payment_reference=payment_reference,
        customer_id=customer_id,
        idempotency_key=idempotency_key,
    )
    return {
        "bill_id": bill.id,
        "bill_number": bill.bill_number,
        "status": bill.status.value,
        "grand_total": float(bill.grand_total),
        "payment_method": bill.payment_method,
        "finalized_at": bill.finalized_at.isoformat() if bill.finalized_at else None,
    }
