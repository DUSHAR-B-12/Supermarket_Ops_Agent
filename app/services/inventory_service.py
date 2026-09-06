from typing import List, Optional
from sqlalchemy.orm import Session
from app.db.models import Product, StockMovement, StockMovementType

class InventoryService:
    def __init__(self, db: Session):
        self.db = db

    def receive_stock(self, product_id: int, quantity: float, reference: Optional[str] = None) -> Product:
        if quantity <= 0:
            raise ValueError("Stock receiving quantity must be positive.")

        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product with ID {product_id} not found.")

        self.db.query(Product).filter(Product.id == product_id).update(
            {"quantity": Product.quantity + float(quantity)}, synchronize_session=False
        )
        movement = StockMovement(
            product_id=product_id,
            movement_type=StockMovementType.IN,
            quantity=quantity,
            reference=reference or "Stock Receiving",
        )
        self.db.add(movement)
        self.db.commit()
        self.db.refresh(product)
        return product

    def get_stock(self, product_id: int) -> float:
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product with ID {product_id} not found.")
        return float(product.quantity)

    def get_low_stock(self) -> List[Product]:
        return (
            self.db.query(Product)
            .filter(Product.active == True, Product.quantity <= Product.reorder_level)
            .all()
        )

    def validate_stock_availability(self, product_id: int, requested_qty: float) -> Product:
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product with ID {product_id} not found.")
        if float(product.quantity) < float(requested_qty):
            raise ValueError(
                f"Oversell Guard: Cannot bill {requested_qty} {product.unit} of '{product.name}'. "
                f"Only {product.quantity} in stock."
            )
        return product
