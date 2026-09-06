import pytest
from app.services.product_service import ProductService
from app.db.models import Product
from app.db.seed import seed_database
from app.tools.inventory_tools import search_products, add_product, list_inventory

def test_medimix_pagination_issue(db_session):
    # 1. Create the initial products (seed_database adds 25 products)
    seed_database(db_session)
    initial_count = db_session.query(Product).count()
    print(f"Initial count: {initial_count}")
    
    # 2. Add some dummy products so we exceed the 50 limit
    for i in range(60):
        add_product(
            db=db_session,
            sku=f"DUMMY-{i}",
            name=f"Dummy Product {i}",
            category="Test",
            unit="piece",
            cost_price=10.0,
            mrp=15.0,
            selling_price=12.0,
            initial_quantity=5.0
        )
    
    # 3. Add Medimix Soap afterwards with quantity 20
    add_product(
        db=db_session,
        sku="MED-20",
        name="Medimix Soap",
        category="Personal Care",
        unit="piece",
        cost_price=15.0,
        mrp=22.0,
        selling_price=20.0,
        initial_quantity=20.0
    )
    
    total_count = db_session.query(Product).count()
    print(f"Total count after dummy & medimix: {total_count}")
    
    # 4. Call specific search for Medimix
    specific_results = search_products(db_session, "Medimix")
    print(f"Specific search found: {len(specific_results)} items. {specific_results[0]['name'] if specific_results else 'None'}")
    assert any(r["name"] == "Medimix Soap" for r in specific_results)
    
    # 5. Call the global inventory-list operation (using the new tool)
    global_results = list_inventory(db_session)
    print(f"Global search returned: {len(global_results)} items.")
    
    # Verify Medimix appears in global search
    found_in_global = any(r["name"] == "Medimix Soap" for r in global_results)
    print(f"Medimix found in global? {found_in_global}")
    
    assert found_in_global, "Medimix was excluded from global search! Pagination/limit bug detected."
