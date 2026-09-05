from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.services.inventory_service import InventoryService
from app.services.product_service import ProductService

def search_products(db: Session, query: str) -> List[Dict[str, Any]]:
    service = ProductService(db)
    products = service.search(query)
    return [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "unit": p.unit,
            "selling_price": float(p.selling_price),
            "cost_price": float(p.cost_price),
            "gst_rate": float(p.gst_rate),
            "quantity": float(p.quantity),
            "reorder_level": float(p.reorder_level),
        }
        for p in products
    ]

def get_product(db: Session, identifier: str) -> Optional[Dict[str, Any]]:
    service = ProductService(db)
    p = None
    if identifier.isdigit():
        p = service.get_by_id(int(identifier))
    if not p:
        p = service.get_by_sku(identifier)
    if not p:
        matches = service.search(identifier, limit=1)
        p = matches[0] if matches else None

    if not p:
        return None

    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "unit": p.unit,
        "selling_price": float(p.selling_price),
        "cost_price": float(p.cost_price),
        "mrp": float(p.mrp),
        "gst_rate": float(p.gst_rate),
        "quantity": float(p.quantity),
        "reorder_level": float(p.reorder_level),
    }

def add_product(
    db: Session,
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
) -> Dict[str, Any]:
    service = ProductService(db)
    p = service.create_product(
        sku=sku,
        name=name,
        category=category,
        unit=unit,
        cost_price=cost_price,
        mrp=mrp,
        selling_price=selling_price,
        gst_rate=gst_rate,
        hsn_code=hsn_code,
        is_loose=is_loose,
        initial_quantity=initial_quantity,
        reorder_level=reorder_level,
    )
    return {"id": p.id, "sku": p.sku, "name": p.name, "quantity": float(p.quantity)}

def receive_stock(db: Session, product_id: int, quantity: float, reference: Optional[str] = None) -> Dict[str, Any]:
    service = InventoryService(db)
    p = service.receive_stock(product_id=product_id, quantity=quantity, reference=reference)
    return {"id": p.id, "name": p.name, "new_quantity": float(p.quantity)}

def get_stock(db: Session, product_id: int) -> Dict[str, Any]:
    service = InventoryService(db)
    qty = service.get_stock(product_id)
    return {"product_id": product_id, "quantity": qty}

def get_low_stock(db: Session) -> List[Dict[str, Any]]:
    service = InventoryService(db)
    products = service.get_low_stock()
    return [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "quantity": float(p.quantity),
            "reorder_level": float(p.reorder_level),
            "unit": p.unit,
        }
        for p in products
    ]
