"""
Regression tests for database persistence across application restarts.
Ensures inventory, stock, and business data survive init_db() and seed_database().
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, init_db, SessionLocal, engine
from app.db.models import Product
from app.services.product_service import ProductService
from app.config.settings import settings


def test_database_uses_absolute_path():
    """Verify the resolved database URL uses an absolute path."""
    url = settings.resolved_database_url
    path = settings.resolved_database_path
    assert os.path.isabs(path), f"Database path should be absolute, got: {path}"
    assert "sqlite:///" in url
    # Verify both point to the same file
    assert path in url


def test_init_db_preserves_existing_products(tmp_path):
    """
    TEST A + D: Products survive re-initialization.
    Simulate: create products, then re-run init_db-equivalent flow.
    """
    db_path = str(tmp_path / "test_persist.db")
    db_url = f"sqlite:///{db_path}"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=test_engine)

    # Phase 1: Create tables, seed, and add a custom product
    Base.metadata.create_all(bind=test_engine)
    with TestSession() as session:
        from app.db.seed import seed_database
        seed_database(session)
        count_after_seed = session.query(Product).count()
        assert count_after_seed > 0, "Seed should have added products"

        # Add a custom user-created product
        svc = ProductService(session)
        svc.create_product(
            sku="CUSTOM-001",
            name="User Custom Product",
            category="Custom",
            unit="packet",
            cost_price=10.0,
            mrp=15.0,
            selling_price=12.0,
        )
        total_before = session.query(Product).count()
        assert total_before == count_after_seed + 1

    # Phase 2: Simulate restart — run create_all + seed again
    Base.metadata.create_all(bind=test_engine)
    with TestSession() as session:
        from app.db.seed import seed_database
        seed_database(session)  # Should detect existing products and skip
        total_after = session.query(Product).count()
        assert total_after == total_before, (
            f"Products lost after re-init! Before={total_before}, After={total_after}"
        )
        # Verify the custom product is still there
        custom = session.query(Product).filter(Product.sku == "CUSTOM-001").first()
        assert custom is not None, "Custom product lost after restart!"
        assert custom.name == "User Custom Product"


def test_stock_quantities_survive_reinit(tmp_path):
    """
    TEST B: Stock quantities survive application reinitialization.
    """
    db_path = str(tmp_path / "test_stock_persist.db")
    db_url = f"sqlite:///{db_path}"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=test_engine)

    # Phase 1: Create, seed, then modify stock
    Base.metadata.create_all(bind=test_engine)
    with TestSession() as session:
        from app.db.seed import seed_database
        seed_database(session)
        product = session.query(Product).first()
        product.quantity = 999.0
        session.commit()
        product_id = product.id

    # Phase 2: Simulate restart
    Base.metadata.create_all(bind=test_engine)
    with TestSession() as session:
        from app.db.seed import seed_database
        seed_database(session)  # Should skip because products exist
        product = session.query(Product).filter(Product.id == product_id).first()
        assert product is not None
        assert float(product.quantity) == 999.0, (
            f"Stock quantity was reset! Expected 999.0, got {product.quantity}"
        )


def test_all_tools_use_same_engine():
    """
    TEST C: Verify all services/tools reference the same SQLAlchemy engine.
    """
    from app.db.session import engine as session_engine
    # Create a session and verify it's bound to the same engine
    with SessionLocal() as session:
        assert session.bind is session_engine, "Session uses a different engine!"


def test_seed_database_is_idempotent(tmp_path):
    """
    TEST D: Verify seed_database does NOT insert duplicates or reset data.
    """
    db_path = str(tmp_path / "test_idempotent.db")
    db_url = f"sqlite:///{db_path}"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=test_engine)

    Base.metadata.create_all(bind=test_engine)
    with TestSession() as session:
        from app.db.seed import seed_database
        seed_database(session)
        count_first = session.query(Product).count()

        # Run seed again
        seed_database(session)
        count_second = session.query(Product).count()
        assert count_first == count_second, "Seed should be idempotent!"

        # Run a third time
        seed_database(session)
        count_third = session.query(Product).count()
        assert count_first == count_third, "Seed should still be idempotent!"
