import logging
from typing import Any, Dict, List, Callable
from sqlalchemy.orm import Session

from app import tools

logger = logging.getLogger(__name__)

# Map tool names to python tool functions
TOOL_MAP: Dict[str, Callable[..., Any]] = {
    # Inventory
    "search_products": tools.search_products,
    "get_product": tools.get_product,
    "add_product": tools.add_product,
    "receive_stock": tools.receive_stock,
    "get_stock": tools.get_stock,
    "get_low_stock": tools.get_low_stock,
    # Billing
    "create_draft_bill": tools.create_draft_bill,
    "add_bill_item": tools.add_bill_item,
    "edit_bill_item": tools.edit_bill_item,
    "remove_bill_item": tools.remove_bill_item,
    "get_bill": tools.get_bill,
    "calculate_bill": tools.calculate_bill,
    "finalize_bill": tools.finalize_bill,
    # Khata
    "get_customer": tools.get_customer,
    "get_khata_balance": tools.get_khata_balance,
    "record_khata_credit": tools.record_khata_credit,
    "record_khata_repayment": tools.record_khata_repayment,
    # Preferences
    "get_preference": tools.get_preference,
    "set_preference": tools.set_preference,
    # Artifacts & Reports
    "generate_invoice_pdf": tools.generate_invoice_pdf,
    "get_daily_close": tools.get_daily_close,
    "generate_analysis_deck": tools.generate_analysis_deck,
}

# Declarative JSON Schemas for OpenAI / Gemini function calling
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "search_products",
        "description": "Search product catalog by name, SKU, or category.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term e.g. 'Atta', 'Maggi', 'Sugar'"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_product",
        "description": "Get detailed product record by ID, SKU, or exact name match.",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Product ID, SKU, or exact name"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "add_product",
        "description": "Add a new product to the supermarket catalog.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "name": {"type": "string"},
                "category": {"type": "string"},
                "unit": {"type": "string", "description": "kg, g, litre, ml, packet, piece, dozen"},
                "cost_price": {"type": "number"},
                "mrp": {"type": "number"},
                "selling_price": {"type": "number"},
                "gst_rate": {"type": "number", "description": "0, 5, 12, or 18"},
                "hsn_code": {"type": "string"},
                "is_loose": {"type": "boolean"},
                "initial_quantity": {"type": "number"},
                "reorder_level": {"type": "number"},
            },
            "required": ["sku", "name", "category", "unit", "cost_price", "mrp", "selling_price"],
        },
    },
    {
        "name": "receive_stock",
        "description": "Record received stock arrival for a product. Increases inventory quantity.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer"},
                "quantity": {"type": "number", "description": "Quantity received"},
                "reference": {"type": "string", "description": "Optional invoice or GRN reference"},
            },
            "required": ["product_id", "quantity"],
        },
    },
    {
        "name": "get_stock",
        "description": "Get current available stock quantity for a product ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer"}
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "get_low_stock",
        "description": "List all products running low on stock (quantity <= reorder_level).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "create_draft_bill",
        "description": "Create a new draft bill for a customer. Does NOT reduce inventory.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer", "description": "Optional customer ID"},
                "idempotency_key": {"type": "string"}
            },
        },
    },
    {
        "name": "add_bill_item",
        "description": "Add a product item to a draft bill.",
        "parameters": {
            "type": "object",
            "properties": {
                "bill_id": {"type": "integer"},
                "product_id": {"type": "integer"},
                "quantity": {"type": "number"},
            },
            "required": ["bill_id", "product_id", "quantity"],
        },
    },
    {
        "name": "edit_bill_item",
        "description": "Modify the quantity of a product in an existing draft bill.",
        "parameters": {
            "type": "object",
            "properties": {
                "bill_id": {"type": "integer"},
                "product_id": {"type": "integer"},
                "new_quantity": {"type": "number"},
            },
            "required": ["bill_id", "product_id", "new_quantity"],
        },
    },
    {
        "name": "remove_bill_item",
        "description": "Remove a product from a draft bill.",
        "parameters": {
            "type": "object",
            "properties": {
                "bill_id": {"type": "integer"},
                "product_id": {"type": "integer"},
            },
            "required": ["bill_id", "product_id"],
        },
    },
    {
        "name": "get_bill",
        "description": "Get detailed bill information including items, tax breakup, status, and total.",
        "parameters": {
            "type": "object",
            "properties": {
                "bill_id": {"type": "integer"}
            },
            "required": ["bill_id"],
        },
    },
    {
        "name": "calculate_bill",
        "description": "Calculate subtotal, CGST, SGST, total tax, and grand total for a bill.",
        "parameters": {
            "type": "object",
            "properties": {
                "bill_id": {"type": "integer"}
            },
            "required": ["bill_id"],
        },
    },
    {
        "name": "finalize_bill",
        "description": "Finalize a draft bill: transitions status from 'draft' to 'finalized', validates stock, deducts inventory atomically, and records the payment method. Call this tool when the user says 'finalize the bill', 'complete the bill', 'confirm the sale', 'finish this bill', or any equivalent request to close a draft bill. Accepts payment_method: Cash, UPI, Card, or Khata (defaults to Cash).",
        "parameters": {
            "type": "object",
            "properties": {
                "bill_id": {"type": "integer"},
                "payment_method": {"type": "string", "enum": ["Cash", "UPI", "Card", "Khata"]},
                "payment_reference": {"type": "string"},
                "customer_id": {"type": "integer"},
                "idempotency_key": {"type": "string"},
            },
            "required": ["bill_id"],
        },
    },
    {
        "name": "get_customer",
        "description": "Fetch or create a Khata customer record by name, ID, or Telegram user ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "name": {"type": "string"},
                "telegram_user_id": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_khata_balance",
        "description": "Get outstanding credit balance for a customer ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"}
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "record_khata_credit",
        "description": "Record a credit purchase for a customer (increases credit balance).",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "amount": {"type": "number"},
                "reference": {"type": "string"},
            },
            "required": ["customer_id", "amount"],
        },
    },
    {
        "name": "record_khata_repayment",
        "description": "Record a cash/UPI repayment from a customer (decreases credit balance).",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "amount": {"type": "number"},
                "reference": {"type": "string"},
            },
            "required": ["customer_id", "amount"],
        },
    },
    {
        "name": "get_preference",
        "description": "Get owner standing preference value by key. (user_id is automatically injected, do NOT ask the user for it).",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Automatically injected, leave blank."},
                "key": {"type": "string"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "set_preference",
        "description": "Save owner standing preference (e.g., default payment method, shop name). (user_id is automatically injected, do NOT ask the user for it).",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Automatically injected, leave blank."},
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "generate_invoice_pdf",
        "description": "Generate a GST-compliant PDF invoice document for a finalized bill.",
        "parameters": {
            "type": "object",
            "properties": {
                "bill_id": {"type": "integer", "description": "Bill ID to generate PDF for (optional)"},
                "user_id": {"type": "string"},
            },
        },
    },
    {
        "name": "get_daily_close",
        "description": "Calculate daily close business summary (sales, bill count, payment breakdown, GST, top items, low stock, Khata).",
        "parameters": {
            "type": "object",
            "properties": {
                "date_str": {
                    "type": "string",
                    "description": "Optional date string in YYYY-MM-DD format (e.g. '2026-09-05'). Do NOT pass null. For today, pass today's date string or omit date_str entirely."
                }
            },
        },
    },
    {
        "name": "generate_analysis_deck",
        "description": "Generate a 6-slide PowerPoint (.pptx) sales analysis deck with charts and store metrics.",
        "parameters": {
            "type": "object",
            "properties": {
                "date_str": {
                    "type": "string",
                    "description": "Optional date string in YYYY-MM-DD format (e.g. '2026-09-05'). Do NOT pass null. For today, pass today's date string or omit date_str entirely."
                }
            },
        },
    },
]


def execute_tool(db: Session, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a registered domain tool function with error catching."""
    tool_func = TOOL_MAP.get(tool_name)
    if not tool_func:
        logger.error(f"Unknown tool requested: '{tool_name}'")
        return {"error": f"Tool '{tool_name}' is not registered."}

    # Normalize/strip None values passed for optional arguments
    sanitized_args = {k: v for k, v in arguments.items() if v is not None}

    logger.info(f"Executing tool '{tool_name}' with args: {sanitized_args}")
    try:
        result = tool_func(db=db, **sanitized_args)
        logger.info(f"Tool '{tool_name}' returned success: {result}")
        return {"status": "success", "data": result}
    except Exception as e:
        logger.warning(f"Tool '{tool_name}' failed with exception: {e}")
        return {"status": "error", "error": str(e)}
