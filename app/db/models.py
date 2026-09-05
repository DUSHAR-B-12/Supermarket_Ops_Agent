from datetime import datetime
import enum
from typing import List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class BillStatus(str, enum.Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    CANCELLED = "cancelled"


class StockMovementType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"
    ADJUSTMENT = "ADJUSTMENT"


class KhataTransactionType(str, enum.Enum):
    CREDIT = "CREDIT"
    REPAYMENT = "REPAYMENT"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="General")
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="packet")
    is_loose: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hsn_code: Mapped[str] = mapped_column(String(32), nullable=False, default="0000")
    gst_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    cost_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    mrp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    selling_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=0.0)
    reorder_level: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=5.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    bill_items: Mapped[List["BillItem"]] = relationship("BillItem", back_populates="product")
    stock_movements: Mapped[List["StockMovement"]] = relationship("StockMovement", back_populates="product")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    telegram_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    credit_balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    bills: Mapped[List["Bill"]] = relationship("Bill", back_populates="customer")
    khata_transactions: Mapped[List["KhataTransaction"]] = relationship("KhataTransaction", back_populates="customer")


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bill_number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id"), nullable=True)
    status: Mapped[BillStatus] = mapped_column(SQLEnum(BillStatus), default=BillStatus.DRAFT, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    cgst: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    sgst: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    total_tax: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    grand_total: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # Cash, UPI, Card, Khata
    payment_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="bills")
    items: Mapped[List["BillItem"]] = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")


class BillItem(Base):
    __tablename__ = "bill_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bill_id: Mapped[int] = mapped_column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    cost_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    gst_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    taxable_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    cgst: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    sgst: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)

    bill: Mapped["Bill"] = relationship("Bill", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="bill_items")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    movement_type: Mapped[StockMovementType] = mapped_column(SQLEnum(StockMovementType), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="stock_movements")


class KhataTransaction(Base):
    __tablename__ = "khata_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    transaction_type: Mapped[KhataTransactionType] = mapped_column(SQLEnum(KhataTransactionType), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="khata_transactions")


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    active_draft_bill_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("bills.id"), nullable=True)
    conversation_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
