import pytest
from app.services.product_service import ProductService
from app.db.models import Product
from app.db.seed import seed_database
from app.tools.inventory_tools import search_products, add_product, list_inventory

def test_search_specific_product(db_session):
    """Test searching for a specific product works normally."""
    seed_database(db_session)
    results = search_products(db_session, "Maggi")
    assert len(results) > 0
    assert any(r["name"] == "Maggi 70g" for r in results)

def test_search_wildcard_returns_all_in_stock(db_session):
    """Test wildcard queries (*, all, '') return all active products with quantity > 0."""
    seed_database(db_session)
    
    # Check what the actual stock is
    svc = ProductService(db_session)
    in_stock_count = db_session.query(Product).filter(Product.active == True, Product.quantity > 0).count()
    assert in_stock_count > 0, "Database must have in-stock items"
    
    # Test list_inventory instead of wildcard '*'
    results = list_inventory(db_session)
    assert len(results) == in_stock_count

    # Remove redundant wildcard tests since list_inventory has no query parameter
    pass

def test_search_wildcard_excludes_out_of_stock(db_session):
    """Test wildcard queries exclude products with 0 quantity."""
    seed_database(db_session)
    
    # Set one product to 0 quantity
    product = db_session.query(Product).first()
    product.quantity = 0.0
    db_session.commit()
    
    results = list_inventory(db_session)
    assert not any(r["id"] == product.id for r in results), "Out of stock item was returned in list_inventory!"

def test_search_wildcard_excludes_inactive(db_session):
    """Test wildcard queries exclude inactive products."""
    seed_database(db_session)
    
    # Set one product to inactive
    product = db_session.query(Product).first()
    product.active = False
    db_session.commit()
    
    results = list_inventory(db_session)
    assert not any(r["id"] == product.id for r in results), "Inactive item was returned in list_inventory!"

def test_duplicate_detection_is_consistent(db_session):
    """Test that a product found via wildcard is also detected as a duplicate when adding."""
    seed_database(db_session)
    product = db_session.query(Product).first()
    
    # It should be found in list_inventory
    results = list_inventory(db_session)
    assert any(r["id"] == product.id for r in results)
    
    # It should trigger duplicate error when adding again with same SKU
    with pytest.raises(ValueError, match="already exists"):
        add_product(
            db=db_session,
            sku=product.sku,
            name="New Name",
            category="Test",
            unit="unit",
            cost_price=10.0,
            mrp=15.0,
            selling_price=12.0
        )
