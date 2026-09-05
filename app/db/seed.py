import logging
from decimal import Decimal
from sqlalchemy.orm import Session
from app.db.models import Product

logger = logging.getLogger(__name__)

SEED_PRODUCTS = [
    {
        "sku": "SKU-ATTA-5KG",
        "name": "Aashirvaad Atta 5kg",
        "category": "Staples",
        "unit": "packet",
        "is_loose": False,
        "hsn_code": "1101",
        "gst_rate": 5.0,
        "cost_price": 210.0,
        "mrp": 250.0,
        "selling_price": 240.0,
        "quantity": 30.0,
        "reorder_level": 5.0,
    },
    {
        "sku": "SKU-SALT-1KG",
        "name": "Tata Salt 1kg",
        "category": "Staples",
        "unit": "packet",
        "is_loose": False,
        "hsn_code": "2501",
        "gst_rate": 5.0,
        "cost_price": 22.0,
        "mrp": 28.0,
        "selling_price": 26.0,
        "quantity": 50.0,
        "reorder_level": 10.0,
    },
    {
        "sku": "SKU-BUTTER-100G",
        "name": "Amul Butter 100g",
        "category": "Dairy",
        "unit": "packet",
        "is_loose": False,
        "hsn_code": "0405",
        "gst_rate": 12.0,
        "cost_price": 52.0,
        "mrp": 62.0,
        "selling_price": 60.0,
        "quantity": 25.0,
        "reorder_level": 5.0,
    },
    {
        "sku": "SKU-OIL-1L",
        "name": "Fortune Sunflower Oil 1L",
        "category": "Oil & Ghee",
        "unit": "litre",
        "is_loose": False,
        "hsn_code": "1512",
        "gst_rate": 5.0,
        "cost_price": 125.0,
        "mrp": 150.0,
        "selling_price": 145.0,
        "quantity": 20.0,
        "reorder_level": 5.0,
    },
    {
        "sku": "SKU-MAGGI-70G",
        "name": "Maggi 70g",
        "category": "FMCG",
        "unit": "packet",
        "is_loose": False,
        "hsn_code": "1902",
        "gst_rate": 12.0,
        "cost_price": 11.5,
        "mrp": 14.0,
        "selling_price": 14.0,
        "quantity": 100.0,
        "reorder_level": 20.0,
    },
    {
        "sku": "SKU-PARLE-G",
        "name": "Parle-G",
        "category": "Snacks",
        "unit": "packet",
        "is_loose": False,
        "hsn_code": "1905",
        "gst_rate": 18.0,
        "cost_price": 8.0,
        "mrp": 10.0,
        "selling_price": 10.0,
        "quantity": 80.0,
        "reorder_level": 15.0,
    },
    {
        "sku": "SKU-SURF-EXCEL",
        "name": "Surf Excel",
        "category": "Household",
        "unit": "packet",
        "is_loose": False,
        "hsn_code": "3402",
        "gst_rate": 18.0,
        "cost_price": 110.0,
        "mrp": 140.0,
        "selling_price": 135.0,
        "quantity": 15.0,
        "reorder_level": 4.0,
    },
    {
        "sku": "SKU-SUGAR-LOOSE",
        "name": "loose sugar",
        "category": "Staples",
        "unit": "kg",
        "is_loose": True,
        "hsn_code": "1701",
        "gst_rate": 0.0,
        "cost_price": 38.0,
        "mrp": 46.0,
        "selling_price": 44.0,
        "quantity": 100.0,
        "reorder_level": 15.0,
    },
    {
        "sku": "SKU-RICE-LOOSE",
        "name": "loose rice",
        "category": "Staples",
        "unit": "kg",
        "is_loose": True,
        "hsn_code": "1006",
        "gst_rate": 0.0,
        "cost_price": 45.0,
        "mrp": 60.0,
        "selling_price": 55.0,
        "quantity": 150.0,
        "reorder_level": 25.0,
    },
    {
        "sku": "SKU-DAL-LOOSE",
        "name": "loose dal",
        "category": "Staples",
        "unit": "kg",
        "is_loose": True,
        "hsn_code": "0713",
        "gst_rate": 0.0,
        "cost_price": 95.0,
        "mrp": 120.0,
        "selling_price": 115.0,
        "quantity": 80.0,
        "reorder_level": 10.0,
    },
]


def seed_database(db: Session) -> None:
    """Populate initial Kirana store seed data if database is empty."""
    existing_count = db.query(Product).count()
    if existing_count > 0:
        logger.info(f"Database already seeded with {existing_count} products.")
        return

    logger.info("Seeding database with realistic Kirana products...")
    for item in SEED_PRODUCTS:
        product = Product(**item)
        db.add(product)
    db.commit()
    logger.info("Seed data successfully inserted.")
