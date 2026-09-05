import os
import logging
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.db.models import Bill, BillStatus
from app.config.settings import settings

logger = logging.getLogger(__name__)

# ── GreenBasket Supermart Brand Palette ──────────────────────────────
BRAND_DARK_GREEN = colors.HexColor("#1B5E20")   # Main header / brand text
BRAND_GREEN = colors.HexColor("#2E7D32")         # Section headers, accents
BRAND_LIGHT_GREEN = colors.HexColor("#43A047")   # Table header background
BRAND_PALE_GREEN = colors.HexColor("#C8E6C9")    # Grid lines, subtle accents
BRAND_WHITE = colors.white


def generate_pdf_invoice(bill: Bill, shop_name: Optional[str] = None, output_dir: Optional[str] = None) -> str:
    """
    Generate a clean, GST-compliant PDF invoice using ReportLab.
    Must be called on a FINALIZED bill.
    """
    if shop_name is None:
        shop_name = settings.SHOP_NAME

    if bill.status != BillStatus.FINALIZED:
        raise ValueError(f"Cannot generate invoice for bill #{bill.bill_number} because status is '{bill.status.value}'. Must be 'finalized'.")

    if not output_dir:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(base_dir, "invoices")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"Invoice_{bill.bill_number}.pdf"
    file_path = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        file_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=BRAND_DARK_GREEN,
        alignment=0,
    )
    meta_style = ParagraphStyle("InvoiceMeta", parent=styles["Normal"], fontSize=10, leading=14)
    header_cell_style = ParagraphStyle("HeaderCell", parent=styles["Normal"], fontSize=9, leading=11, fontName="Helvetica-Bold", textColor=BRAND_WHITE)
    cell_style = ParagraphStyle("BodyCell", parent=styles["Normal"], fontSize=9, leading=11)

    story = []

    # Header Title
    story.append(Paragraph(f"<b>{shop_name}</b>", title_style))
    story.append(Paragraph("GST Tax Invoice / Cash Memo", ParagraphStyle("Sub", parent=styles["Normal"], fontSize=11, textColor=colors.gray)))
    story.append(Spacer(1, 15))

    # Meta Info (Invoice #, Date, Customer, Payment Mode)
    finalized_date_str = bill.finalized_at.strftime("%Y-%m-%d %H:%M:%S") if bill.finalized_at else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    customer_name = bill.customer.name if bill.customer else "Walk-in Customer"
    payment_ref = f" (Ref: {bill.payment_reference})" if bill.payment_reference else ""

    meta_data = [
        [
            Paragraph(f"<b>Invoice No:</b> {bill.bill_number}", meta_style),
            Paragraph(f"<b>Date:</b> {finalized_date_str}", meta_style),
        ],
        [
            Paragraph(f"<b>Customer:</b> {customer_name}", meta_style),
            Paragraph(f"<b>Payment Method:</b> {bill.payment_method or 'Cash'}{payment_ref}", meta_style),
        ],
    ]

    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    # Items Table Header
    table_data = [[
        Paragraph("Product Description", header_cell_style),
        Paragraph("Qty", header_cell_style),
        Paragraph("Price (₹)", header_cell_style),
        Paragraph("GST %", header_cell_style),
        Paragraph("Taxable (₹)", header_cell_style),
        Paragraph("CGST (₹)", header_cell_style),
        Paragraph("SGST (₹)", header_cell_style),
        Paragraph("Total (₹)", header_cell_style),
    ]]

    # Items Table Rows
    for item in bill.items:
        product_name = item.product.name if item.product else f"Item #{item.product_id}"
        table_data.append([
            Paragraph(product_name, cell_style),
            Paragraph(f"{item.quantity:.2f}", cell_style),
            Paragraph(f"{item.unit_price:.2f}", cell_style),
            Paragraph(f"{item.gst_rate:.1f}%", cell_style),
            Paragraph(f"{item.taxable_amount:.2f}", cell_style),
            Paragraph(f"{item.cgst:.2f}", cell_style),
            Paragraph(f"{item.sgst:.2f}", cell_style),
            Paragraph(f"{item.total:.2f}", cell_style),
        ])

    items_table = Table(table_data, colWidths=[140, 45, 55, 45, 65, 60, 60, 70])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_LIGHT_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), BRAND_WHITE),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, BRAND_PALE_GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 15))

    # Summary Totals Table
    summary_data = [
        ["Subtotal (Excl. Tax):", f"₹ {bill.subtotal:.2f}"],
        ["Total CGST:", f"₹ {bill.cgst:.2f}"],
        ["Total SGST:", f"₹ {bill.sgst:.2f}"],
        ["Total GST Tax Collected:", f"₹ {bill.total_tax:.2f}"],
        ["Grand Total (Incl. Tax):", f"₹ {bill.grand_total:.2f}"],
    ]

    summary_table = Table(summary_data, colWidths=[400, 140])
    summary_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("LINEABOVE", (0, 0), (-1, 0), 1, BRAND_GREEN),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, BRAND_GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_table)

    story.append(Spacer(1, 25))
    story.append(Paragraph("Thank you for shopping at GreenBasket Supermart! Please visit again.", ParagraphStyle("Footer", parent=styles["Normal"], alignment=1, fontSize=10, textColor=BRAND_GREEN)))

    doc.build(story)
    logger.info(f"Generated PDF invoice at: {file_path}")
    return file_path
