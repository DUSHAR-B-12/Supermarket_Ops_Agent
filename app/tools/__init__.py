"""
Agent tool definitions package.
"""
from app.tools.inventory_tools import (
    search_products,
    list_inventory,
    get_product,
    add_product,
    receive_stock,
    get_stock,
    get_low_stock,
)
from app.tools.billing_tools import (
    create_draft_bill,
    add_bill_item,
    edit_bill_item,
    remove_bill_item,
    get_bill,
    calculate_bill,
    finalize_bill,
)
from app.tools.khata_tools import (
    get_customer,
    get_khata_balance,
    record_khata_credit,
    record_khata_repayment,
)
from app.tools.preference_tools import (
    get_preference,
    set_preference,
)
from app.tools.report_tools import (
    generate_invoice_pdf,
    get_daily_close,
    generate_analysis_deck,
)

__all__ = [
    # Inventory
    "search_products",
    "list_inventory",
    "get_product",
    "add_product",
    "receive_stock",
    "get_stock",
    "get_low_stock",
    # Billing
    "create_draft_bill",
    "add_bill_item",
    "edit_bill_item",
    "remove_bill_item",
    "get_bill",
    "calculate_bill",
    "finalize_bill",
    # Khata
    "get_customer",
    "get_khata_balance",
    "record_khata_credit",
    "record_khata_repayment",
    # Preferences
    "get_preference",
    "set_preference",
    # Reports & Artifacts
    "generate_invoice_pdf",
    "get_daily_close",
    "generate_analysis_deck",
]
