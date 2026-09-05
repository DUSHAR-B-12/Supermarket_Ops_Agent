from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, TypedDict

class TaxBreakup(TypedDict):
    taxable_amount: float
    gst_rate: float
    cgst_rate: float
    sgst_rate: float
    cgst_amount: float
    sgst_amount: float
    total_tax: float
    total_amount: float

class TaxService:
    """
    Deterministic GST calculation service.
    Enforces per-item tax slabs, CGST/SGST split for intra-state billing,
    and standard monetary rounding (ROUND_HALF_UP).
    """

    @staticmethod
    def _round(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_item_tax(cls, unit_price: float, quantity: float, gst_rate: float) -> TaxBreakup:
        """
        Calculate taxable amount, CGST, SGST, total tax, and total amount for a single item line.
        """
        price_dec = Decimal(str(unit_price))
        qty_dec = Decimal(str(quantity))
        rate_dec = Decimal(str(gst_rate))

        taxable_dec = cls._round(price_dec * qty_dec)
        
        # Intra-state GST split: CGST % = SGST % = gst_rate / 2
        half_rate_dec = rate_dec / Decimal("2.0")
        
        cgst_dec = cls._round(taxable_dec * (half_rate_dec / Decimal("100.0")))
        sgst_dec = cls._round(taxable_dec * (half_rate_dec / Decimal("100.0")))
        total_tax_dec = cgst_dec + sgst_dec
        total_amount_dec = taxable_dec + total_tax_dec

        return {
            "taxable_amount": float(taxable_dec),
            "gst_rate": float(rate_dec),
            "cgst_rate": float(half_rate_dec),
            "sgst_rate": float(half_rate_dec),
            "cgst_amount": float(cgst_dec),
            "sgst_amount": float(sgst_dec),
            "total_tax": float(total_tax_dec),
            "total_amount": float(total_amount_dec),
        }
