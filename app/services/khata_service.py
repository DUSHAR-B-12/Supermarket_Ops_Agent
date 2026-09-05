from typing import Optional, List
from sqlalchemy.orm import Session
from app.db.models import Customer, KhataTransaction, KhataTransactionType

class KhataService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_customer(
        self, name: str, phone: Optional[str] = None, telegram_user_id: Optional[int] = None
    ) -> Customer:
        customer = None
        if telegram_user_id:
            customer = self.db.query(Customer).filter(Customer.telegram_user_id == telegram_user_id).first()
        if not customer and name:
            customer = self.db.query(Customer).filter(Customer.name.ilike(name.strip())).first()

        if not customer:
            customer = Customer(
                name=name.strip(),
                phone=phone,
                telegram_user_id=telegram_user_id,
                credit_balance=0.0,
            )
            self.db.add(customer)
            self.db.commit()
            self.db.refresh(customer)
        return customer

    def get_customer_by_id(self, customer_id: int) -> Optional[Customer]:
        return self.db.query(Customer).filter(Customer.id == customer_id).first()

    def get_khata_balance(self, customer_id: int) -> float:
        customer = self.get_customer_by_id(customer_id)
        if not customer:
            raise ValueError(f"Customer with ID {customer_id} does not exist.")
        return float(customer.credit_balance)

    def record_credit(self, customer_id: int, amount: float, reference: Optional[str] = None) -> Customer:
        if amount <= 0:
            raise ValueError("Credit amount must be positive.")

        customer = self.get_customer_by_id(customer_id)
        if not customer:
            raise ValueError(f"Cannot add credit: Customer ID {customer_id} does not exist.")

        customer.credit_balance = float(customer.credit_balance) + float(amount)
        tx = KhataTransaction(
            customer_id=customer_id,
            transaction_type=KhataTransactionType.CREDIT,
            amount=amount,
            reference=reference or "Khata Credit Purchase",
        )
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def record_repayment(self, customer_id: int, amount: float, reference: Optional[str] = None) -> Customer:
        if amount <= 0:
            raise ValueError("Repayment amount must be positive.")

        customer = self.get_customer_by_id(customer_id)
        if not customer:
            raise ValueError(f"Cannot record repayment: Customer ID {customer_id} does not exist.")

        if float(customer.credit_balance) < float(amount):
            raise ValueError(f"Repayment of ₹{amount:.2f} exceeds outstanding Khata balance of ₹{float(customer.credit_balance):.2f}.")

        customer.credit_balance = float(customer.credit_balance) - float(amount)
        tx = KhataTransaction(
            customer_id=customer_id,
            transaction_type=KhataTransactionType.REPAYMENT,
            amount=amount,
            reference=reference or "Khata Repayment",
        )
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(customer)
        return customer
