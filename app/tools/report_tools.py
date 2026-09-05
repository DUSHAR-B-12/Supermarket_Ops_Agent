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
    db: Session, bill_id: Optional[int] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Generate PDF invoice for a finalized bill."""
    bill = None
    if bill_id:
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
    else:
        # Get latest finalized bill
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

    pdf_path = generate_pdf_invoice(bill, shop_name=shop_name)
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
    summary = get_daily_close(db, date_str)
    pptx_path = generate_analysis_deck_pptx(summary)
    return {
        "date": summary["date"],
        "total_sales": summary["total_sales"],
        "pptx_path": pptx_path,
    }
