from typing import List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.db.models import Product

class ProductService:
    def __init__(self, db: Session):
        self.db = db

    def create_product(
        self,
        sku: str,
        name: str,
        category: str,
        unit: str,
        cost_price: float,
        mrp: float,
        selling_price: float,
        gst_rate: float = 0.0,
        hsn_code: str = "0000",
        is_loose: bool = False,
        initial_quantity: float = 0.0,
        reorder_level: float = 5.0,
    ) -> Product:
        if selling_price < cost_price:
            raise ValueError(f"Selling price ({selling_price}) cannot be below cost price ({cost_price}).")

        existing = self.db.query(Product).filter(Product.sku == sku).first()
        if existing:
            raise ValueError(f"Product with SKU '{sku}' already exists.")

        product = Product(
            sku=sku,
            name=name,
            category=category,
            unit=unit,
            is_loose=is_loose,
            hsn_code=hsn_code,
            gst_rate=gst_rate,
            cost_price=cost_price,
            mrp=mrp,
            selling_price=selling_price,
            quantity=initial_quantity,
            reorder_level=reorder_level,
        )
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def get_by_id(self, product_id: int) -> Optional[Product]:
        return self.db.query(Product).filter(Product.id == product_id, Product.active == True).first()

    def get_by_sku(self, sku: str) -> Optional[Product]:
        return self.db.query(Product).filter(Product.sku == sku, Product.active == True).first()

    def search(self, query: str, limit: int = 50) -> List[Product]:
        q = query.strip().lower()
        search_pattern = f"%{q}%"
        return (
            self.db.query(Product)
            .filter(
                Product.active == True,
                or_(Product.name.ilike(search_pattern), Product.sku.ilike(search_pattern), Product.category.ilike(search_pattern)),
            )
            .limit(limit)
            .all()
        )

    def list_active_inventory(self, limit: int = 500) -> List[Product]:
        return (
            self.db.query(Product)
            .filter(Product.active == True, Product.quantity > 0)
            .limit(limit)
            .all()
        )
