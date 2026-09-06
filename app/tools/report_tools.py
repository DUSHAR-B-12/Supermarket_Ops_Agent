from datetime import datetime, date
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.db.models import Bill, BillStatus
from app.artifacts.invoice import generate_pdf_invoice
from app.artifacts.analysis_deck import generate_analysis_deck_pptx
from app.services.daily_close_service import DailyCloseService
from app.services.preference_service import PreferenceService
from app.config.settings import settings


def generate_invoice_pdf(
    db: Session, bill_id: Optional[int] = None, bill_number: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Generate PDF invoice for a finalized bill.
    
    Resolution priority:
    1. bill_number (string like 'INV-20260906125214-B06D')
    2. bill_id (internal numeric ID)
    3. Most recently finalized bill (fallback)
    """
    import os

    bill = None

    # 1. Resolve by bill_number string
    if bill_number:
        bill = db.query(Bill).filter(Bill.bill_number == bill_number).first()
        if not bill:
            raise ValueError(f"No bill found with number '{bill_number}'. Please check and try again.")

    # 2. Resolve by internal numeric ID
    if not bill and bill_id:
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise ValueError(f"No bill found with ID {bill_id}.")

    # 3. Fallback: most recently finalized bill
    if not bill:
        bill = (
            db.query(Bill)
            .filter(Bill.status == BillStatus.FINALIZED)
            .order_by(Bill.finalized_at.desc())
            .first()
        )

    if not bill:
        raise ValueError("No finalized bill found to generate PDF invoice.")

    if bill.status != BillStatus.FINALIZED:
        raise ValueError(f"Bill #{bill.bill_number} is not finalized. Status is '{bill.status.value}'.")

    # Get shop name: user preference > settings > default
    shop_name = settings.SHOP_NAME
    if user_id:
        pref = PreferenceService(db).get_preference(str(user_id), "shop_name")
        if pref:
            shop_name = pref

    # Generate PDF into persistent data directory
    output_dir = os.path.join(settings.data_dir, "invoices")
    pdf_path = generate_pdf_invoice(bill, shop_name=shop_name, output_dir=output_dir)
    return {
        "bill_id": bill.id,
        "bill_number": bill.bill_number,
        "pdf_path": pdf_path,
        "grand_total": float(bill.grand_total),
    }


def get_daily_close(db: Session, date_str: Optional[str] = None) -> Dict[str, Any]:
    """Get deterministic daily closing summary for store operations."""
    target_date = None
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    service = DailyCloseService(db)
    summary = service.get_daily_summary(target_date)
    return summary


def generate_analysis_deck(db: Session, date_str: Optional[str] = None) -> Dict[str, Any]:
    """Generate PPTX sales analysis presentation deck."""
    import os
    summary = get_daily_close(db, date_str)
    output_dir = os.path.join(settings.data_dir, "decks")
    pptx_path = generate_analysis_deck_pptx(summary, output_dir=output_dir)
    return {
        "date": summary["date"],
        "total_sales": summary["total_sales"],
        "pptx_path": pptx_path,
    }
