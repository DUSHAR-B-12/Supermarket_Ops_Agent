"""
Regression tests for PDF invoice generation.
Covers bill resolution by ID, bill_number, latest finalized, error cases, and PDF validity.
"""
import os
import pytest
from app.db.models import Product, Bill, BillStatus
from app.db.seed import seed_database
from app.tools.billing_tools import create_draft_bill, add_bill_item, finalize_bill
from app.tools.report_tools import generate_invoice_pdf


def _setup_finalized_bill(db_session) -> dict:
    """Helper: seed products, create a draft, add an item, finalize, return bill data."""
    seed_database(db_session)
    product = db_session.query(Product).first()
    assert product is not None

    draft = create_draft_bill(db_session)
    bill_id = draft["bill_id"]
    add_bill_item(db_session, bill_id=bill_id, product_id=product.id, quantity=2)
    result = finalize_bill(db_session, bill_id=bill_id, payment_method="Cash")
    return result


def test_invoice_by_internal_id(db_session):
    """Test 1: Generate invoice by internal numeric bill_id."""
    bill_data = _setup_finalized_bill(db_session)
    result = generate_invoice_pdf(db_session, bill_id=bill_data["bill_id"])
    assert result["bill_id"] == bill_data["bill_id"]
    assert result["bill_number"] == bill_data["bill_number"]
    assert os.path.exists(result["pdf_path"])
    assert os.path.getsize(result["pdf_path"]) > 0


def test_invoice_by_bill_number(db_session):
    """Test 2: Generate invoice by bill_number string (e.g. INV-xxx)."""
    bill_data = _setup_finalized_bill(db_session)
    bill_number = bill_data["bill_number"]
    result = generate_invoice_pdf(db_session, bill_number=bill_number)
    assert result["bill_number"] == bill_number
    assert os.path.exists(result["pdf_path"])


def test_invoice_latest_finalized_no_args(db_session):
    """Test 3: 'give invoice of the bill' → resolves most recent finalized bill."""
    bill_data = _setup_finalized_bill(db_session)
    result = generate_invoice_pdf(db_session)  # No bill_id, no bill_number
    assert result["bill_id"] == bill_data["bill_id"]
    assert os.path.exists(result["pdf_path"])


def test_invoice_exact_bill_number_resolves_correct_bill(db_session):
    """Test 4: Exact bill number resolves the correct bill when multiple exist."""
    seed_database(db_session)
    product = db_session.query(Product).first()

    # Create and finalize two bills
    d1 = create_draft_bill(db_session)
    add_bill_item(db_session, bill_id=d1["bill_id"], product_id=product.id, quantity=1)
    b1 = finalize_bill(db_session, bill_id=d1["bill_id"])

    d2 = create_draft_bill(db_session)
    add_bill_item(db_session, bill_id=d2["bill_id"], product_id=product.id, quantity=3)
    b2 = finalize_bill(db_session, bill_id=d2["bill_id"])

    # Request invoice for the FIRST bill by its number
    result = generate_invoice_pdf(db_session, bill_number=b1["bill_number"])
    assert result["bill_id"] == b1["bill_id"]
    assert result["bill_number"] == b1["bill_number"]


def test_invoice_invalid_bill_number_error(db_session):
    """Test 5: Invalid bill number returns friendly error."""
    seed_database(db_session)
    with pytest.raises(ValueError, match="No bill found with number"):
        generate_invoice_pdf(db_session, bill_number="INV-NONEXISTENT-XXXX")


def test_invoice_draft_bill_rejected(db_session):
    """Test 6: Draft bill → invoice rejected until finalized."""
    seed_database(db_session)
    draft = create_draft_bill(db_session)
    with pytest.raises(ValueError, match="not finalized"):
        generate_invoice_pdf(db_session, bill_id=draft["bill_id"])


def test_invoice_pdf_is_valid(db_session):
    """Test 7 + 8: Generated PDF exists, is non-empty, and starts with PDF magic bytes."""
    bill_data = _setup_finalized_bill(db_session)
    result = generate_invoice_pdf(db_session, bill_id=bill_data["bill_id"])
    pdf_path = result["pdf_path"]

    assert os.path.exists(pdf_path), f"PDF not found at {pdf_path}"
    assert os.path.getsize(pdf_path) > 100, "PDF is suspiciously small"

    with open(pdf_path, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-", f"Not a valid PDF file. Header: {header}"


def test_invoice_telegram_artifact_tag(db_session):
    """Test 9: Verify the pdf_path in the result is suitable for [FILE: path] tag."""
    bill_data = _setup_finalized_bill(db_session)
    result = generate_invoice_pdf(db_session, bill_id=bill_data["bill_id"])
    pdf_path = result["pdf_path"]

    # The runner appends [FILE: pdf_path] which bot.py parses
    assert pdf_path.endswith(".pdf")
    assert os.path.isabs(pdf_path) or os.path.exists(pdf_path)


def test_invoice_survives_reinit(db_session):
    """Test 10 + 11: Finalized bill and invoice survive 'restart' (re-query)."""
    bill_data = _setup_finalized_bill(db_session)
    bill_number = bill_data["bill_number"]

    # Simulate restart by clearing session cache and re-querying
    db_session.expire_all()

    bill = db_session.query(Bill).filter(Bill.bill_number == bill_number).first()
    assert bill is not None, "Bill lost after session expire!"
    assert bill.status == BillStatus.FINALIZED

    # Should still be able to generate invoice
    result = generate_invoice_pdf(db_session, bill_number=bill_number)
    assert result["bill_number"] == bill_number
    assert os.path.exists(result["pdf_path"])
