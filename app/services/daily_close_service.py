from datetime import datetime, date, time
from typing import Any, Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Bill, BillItem, BillStatus, Customer, Product

class DailyCloseService:
    def __init__(self, db: Session):
        self.db = db

    def get_daily_summary(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Compute deterministic daily closing business summary from database records.
        """
        if not target_date:
            target_date = date.today()

        date_str = target_date.strftime("%Y-%m-%d")
        start_of_day = datetime.combine(target_date, time.min)
        end_of_day = datetime.combine(target_date, time.max)

        # Query all finalized bills on target_date
        finalized_bills = (
            self.db.query(Bill)
            .filter(
                Bill.status == BillStatus.FINALIZED,
                Bill.finalized_at >= start_of_day,
                Bill.finalized_at <= end_of_day,
            )
            .all()
        )

        total_sales = sum(float(b.grand_total) for b in finalized_bills)
        bill_count = len(finalized_bills)

        # Payment Method Breakdown
        payment_breakdown = {"Cash": 0.0, "UPI": 0.0, "Card": 0.0, "Khata": 0.0}
        payment_counts = {"Cash": 0, "UPI": 0, "Card": 0, "Khata": 0}

        for b in finalized_bills:
            method = b.payment_method or "Cash"
            payment_breakdown[method] = payment_breakdown.get(method, 0.0) + float(b.grand_total)
            payment_counts[method] = payment_counts.get(method, 0) + 1

        # GST Totals
        total_subtotal = sum(float(b.subtotal) for b in finalized_bills)
        total_cgst = sum(float(b.cgst) for b in finalized_bills)
        total_sgst = sum(float(b.sgst) for b in finalized_bills)
        total_tax = total_cgst + total_sgst

        # Top-Selling Products by Quantity on target_date
        finalized_bill_ids = [b.id for b in finalized_bills]
        top_products = []
        if finalized_bill_ids:
            top_query = (
                self.db.query(
                    BillItem.product_id,
                    func.sum(BillItem.quantity).label("total_qty"),
                    func.sum(BillItem.total).label("total_revenue")
                )
                .filter(BillItem.bill_id.in_(finalized_bill_ids))
                .group_by(BillItem.product_id)
                .order_by(func.sum(BillItem.quantity).desc())
                .limit(5)
                .all()
            )
            for item in top_query:
                prod = self.db.query(Product).filter(Product.id == item.product_id).first()
                if prod:
                    top_products.append({
                        "product_id": prod.id,
                        "name": prod.name,
                        "unit": prod.unit,
                        "quantity_sold": float(item.total_qty),
                        "revenue": float(item.total_revenue),
                    })

        # Low Stock Inventory Items
        low_stock_items = (
            self.db.query(Product)
            .filter(Product.active == True, Product.quantity <= Product.reorder_level)
            .all()
        )
        low_stock_list = [
            {
                "product_id": p.id,
                "name": p.name,
                "quantity": float(p.quantity),
                "reorder_level": float(p.reorder_level),
                "unit": p.unit,
            }
            for p in low_stock_items
        ]

        # Total Khata Outstanding Balance across all customers
        total_khata_outstanding = (
            self.db.query(func.sum(Customer.credit_balance)).scalar() or 0.0
        )

        return {
            "date": date_str,
            "total_sales": round(total_sales, 2),
            "bill_count": bill_count,
            "subtotal": round(total_subtotal, 2),
            "total_cgst": round(total_cgst, 2),
            "total_sgst": round(total_sgst, 2),
            "total_tax": round(total_tax, 2),
            "payment_breakdown": {k: round(v, 2) for k, v in payment_breakdown.items()},
            "payment_counts": payment_counts,
            "top_selling_products": top_products,
            "low_stock_products": low_stock_list,
            "total_khata_outstanding": round(float(total_khata_outstanding), 2),
        }
