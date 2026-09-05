from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.services.khata_service import KhataService

def get_customer(
    db: Session,
    customer_id: Optional[int] = None,
    name: Optional[str] = None,
    telegram_user_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    service = KhataService(db)
    customer = None
    if customer_id:
        customer = service.get_customer_by_id(customer_id)
    elif name or telegram_user_id:
        customer = service.get_or_create_customer(name=name or "", telegram_user_id=telegram_user_id)

    if not customer:
        return None

    return {
        "id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "telegram_user_id": customer.telegram_user_id,
        "credit_balance": float(customer.credit_balance),
    }

def get_khata_balance(db: Session, customer_id: int) -> Dict[str, Any]:
    service = KhataService(db)
    balance = service.get_khata_balance(customer_id)
    return {"customer_id": customer_id, "credit_balance": balance}

def record_khata_credit(
    db: Session, customer_id: int, amount: float, reference: Optional[str] = None
) -> Dict[str, Any]:
    service = KhataService(db)
    customer = service.record_credit(customer_id=customer_id, amount=amount, reference=reference)
    return {"customer_id": customer.id, "name": customer.name, "new_credit_balance": float(customer.credit_balance)}

def record_khata_repayment(
    db: Session, customer_id: int, amount: float, reference: Optional[str] = None
) -> Dict[str, Any]:
    service = KhataService(db)
    customer = service.record_repayment(customer_id=customer_id, amount=amount, reference=reference)
    return {"customer_id": customer.id, "name": customer.name, "new_credit_balance": float(customer.credit_balance)}
