import os
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.session_manager import SessionManager
from app.agent.registry import execute_tool
from app.agent.llm_client import LLMClient

logger = logging.getLogger(__name__)

_llm_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def format_tool_response(tool_results: List[Dict[str, Any]]) -> str:
    """
    Format tool execution results directly into a concise, shopkeeper-friendly
    natural language response, saving an extra LLM API call turn.
    """
    replies = []
    for tr in tool_results:
        tool_name = tr.get("name")
        status = tr.get("status")
        data = tr.get("data")
        error = tr.get("error")

        if status == "error":
            replies.append(f"⚠️ {error}")
            continue

        if not data:
            replies.append(f"✅ Executed {tool_name} successfully.")
            continue

        if tool_name == "receive_stock":
            replies.append(f"✅ Received stock for **{data.get('name')}**. New stock level: **{data.get('new_quantity')}**.")
        elif tool_name == "search_products":
            prods = data if isinstance(data, list) else []
            if not prods:
                replies.append("🔍 No matching products found in catalog.")
            else:
                lines = [f"🔍 Found {len(prods)} product(s):"]
                for p in prods:
                    lines.append(f"• **{p.get('name')}** (SKU: {p.get('sku')}): Price ₹{p.get('selling_price')}, Stock: {p.get('quantity')} {p.get('unit')}")
                replies.append("\n".join(lines))
        elif tool_name == "get_product":
            replies.append(f"📦 Product **{data.get('name')}** (SKU: {data.get('sku')}): Price ₹{data.get('selling_price')}, MRP ₹{data.get('mrp')}, Cost ₹{data.get('cost_price')}, Stock: {data.get('quantity')} {data.get('unit')}, GST: {data.get('gst_rate')}%.")
        elif tool_name == "get_stock":
            replies.append(f"📦 Product #{data.get('product_id')} available stock: **{data.get('quantity')}**.")
        elif tool_name == "get_low_stock":
            prods = data if isinstance(data, list) else []
            if not prods:
                replies.append("✅ Stock levels are healthy. No items below reorder levels.")
            else:
                lines = [f"⚠️ Found {len(prods)} low-stock item(s):"]
                for p in prods:
                    lines.append(f"• **{p.get('name')}**: {p.get('quantity')} {p.get('unit')} remaining (Reorder level: {p.get('reorder_level')})")
                replies.append("\n".join(lines))
        elif tool_name == "create_draft_bill":
            replies.append(f"🧾 Created draft bill #{data.get('bill_number')}.")
        elif tool_name in ["add_bill_item", "edit_bill_item", "remove_bill_item"]:
            replies.append(f"🧾 Draft bill item updated. Current Grand Total: **₹{data.get('grand_total'):.2f}** ({data.get('item_count')} items).")
        elif tool_name == "calculate_bill":
            replies.append(f"💰 Bill Calculation: Subtotal ₹{data.get('subtotal'):.2f}, CGST ₹{data.get('cgst'):.2f}, SGST ₹{data.get('sgst'):.2f}, Grand Total: **₹{data.get('grand_total'):.2f}**.")
        elif tool_name == "finalize_bill":
            replies.append(f"✅ Finalized Bill #{data.get('bill_number')} via **{data.get('payment_method')}**. Grand Total: **₹{data.get('grand_total'):.2f}**.")
        elif tool_name == "get_customer":
            replies.append(f"👤 Customer **{data.get('name')}**: Outstanding Khata balance ₹{data.get('credit_balance'):.2f}.")
        elif tool_name == "get_khata_balance":
            replies.append(f"📋 Khata credit balance for customer #{data.get('customer_id')}: **₹{data.get('credit_balance'):.2f}**.")
        elif tool_name == "record_khata_credit":
            replies.append(f"✅ Added credit for customer **{data.get('name')}**. New Khata balance: **₹{data.get('new_credit_balance'):.2f}**.")
        elif tool_name == "record_khata_repayment":
            replies.append(f"✅ Recorded repayment from **{data.get('name')}**. New Khata balance: **₹{data.get('new_credit_balance'):.2f}**.")
        elif tool_name == "get_preference":
            replies.append(f"⚙️ Preference `{data.get('key')}`: {data.get('value')}")
        elif tool_name == "set_preference":
            replies.append(f"⚙️ Saved preference: `{data.get('key')}` = **{data.get('value')}**.")
        elif tool_name == "generate_invoice_pdf":
            replies.append(f"📄 Generated PDF Tax Invoice for Bill #{data.get('bill_number')} (Total: ₹{data.get('grand_total'):.2f}).")
        elif tool_name == "get_daily_close":
            lines = [
                f"📊 **Daily Business Summary for {data.get('date')}**:",
                f"💰 Total Sales Revenue: ₹{data.get('total_sales'):.2f}",
                f"🧾 Finalized Bills Count: {data.get('bill_count')}",
                f"🏛️ Total Tax Collected: ₹{data.get('total_tax'):.2f} (CGST ₹{data.get('total_cgst'):.2f} + SGST ₹{data.get('total_sgst'):.2f})",
                f"💳 Khata Credit Outstanding: ₹{data.get('total_khata_outstanding'):.2f}",
            ]
            replies.append("\n".join(lines))
        elif tool_name == "generate_analysis_deck":
            replies.append(f"📊 Generated 6-slide PowerPoint sales analysis deck for {data.get('date')} (Total Sales: ₹{data.get('total_sales'):.2f}).")
        else:
            replies.append(f"✅ Executed {tool_name}: {json.dumps(data)}")

    return "\n\n".join(replies)


async def process_agent_message(user_id: int, message_text: str, db: Optional[Session] = None) -> str:
    """
    Main Agent Orchestration Loop with API Quota Optimization:
    Observe -> Reason -> Act (via LLM function calls) -> Directly format tool results (1-turn completion).
    """
    user_str = str(user_id)
    logger.info(f"Agent runner processing message for user_id={user_str}: '{message_text}'")

    close_session = False
    if db is None:
        init_db()
        db = SessionLocal()
        close_session = True

    try:
        session_mgr = SessionManager(db)
        history = session_mgr.get_history(user_str)
        active_bill_id = session_mgr.get_active_draft_bill(user_str)

        llm = get_llm_client()
        tool_results = None
        turn_count = 0
        max_turns = 5
        final_reply = ""
        generated_artifacts = []

        context_msg = message_text
        if active_bill_id:
            context_msg = f"[Context: Active Draft Bill ID is #{active_bill_id}] {message_text}"

        while turn_count < max_turns:
            turn_count += 1
            logger.info(f"Execution turn {turn_count}/{max_turns} for user_id={user_str}")

            text_resp, tool_calls = llm.generate_completion(
                history=history,
                user_message=context_msg if turn_count == 1 else message_text,
                tool_results=tool_results,
            )

            if tool_calls:
                tool_results = []
                for call in tool_calls:
                    tool_name = call["name"]
                    arguments = call.get("arguments", {})

                    if active_bill_id and "bill_id" in arguments and not arguments.get("bill_id"):
                        arguments["bill_id"] = active_bill_id

                    if tool_name in ["generate_invoice_pdf", "get_preference", "set_preference"]:
                        if "user_id" in arguments and not arguments.get("user_id"):
                            arguments["user_id"] = user_str

                    res = execute_tool(db, tool_name, arguments)
                    
                    if tool_name == "create_draft_bill" and res.get("status") == "success":
                        new_bill_id = res["data"].get("bill_id")
                        if new_bill_id:
                            session_mgr.set_active_draft_bill(user_str, new_bill_id)
                            active_bill_id = new_bill_id
                    elif tool_name == "finalize_bill" and res.get("status") == "success":
                        session_mgr.set_active_draft_bill(user_str, None)
                        active_bill_id = None

                    if res.get("status") == "success" and isinstance(res.get("data"), dict):
                        data_dict = res["data"]
                        for file_key in ["pdf_path", "pptx_path"]:
                            if file_key in data_dict and os.path.exists(data_dict[file_key]):
                                generated_artifacts.append(data_dict[file_key])

                    tool_results.append({
                        "name": tool_name,
                        "status": res.get("status"),
                        "data": res.get("data"),
                        "error": res.get("error"),
                    })

                # API QUOTA OPTIMIZATION:
                # Format response directly from tool results and complete turn in 1 LLM request.
                final_reply = format_tool_response(tool_results)
                break

            if text_resp:
                final_reply = text_resp
                break

        if not final_reply:
            final_reply = "I have processed your request."

        # Append artifact tags if files were generated
        for artifact_path in generated_artifacts:
            if f"[FILE: {artifact_path}]" not in final_reply:
                final_reply += f"\n[FILE: {artifact_path}]"

        session_mgr.add_message(user_str, "user", message_text)
        session_mgr.add_message(user_str, "assistant", final_reply)

        logger.info(f"Agent finished processing for user_id={user_str}. Reply length={len(final_reply)}")
        return final_reply
    finally:
        if close_session:
            db.close()


def reset_user_conversation(user_id: int, db: Optional[Session] = None) -> str:
    """Helper for Telegram /new command."""
    user_str = str(user_id)
    close_session = False
    if db is None:
        init_db()
        db = SessionLocal()
        close_session = True

    try:
        session_mgr = SessionManager(db)
        session_mgr.reset_session(user_str)
        return "🔄 Started a fresh conversation session. Historical inventory, bills, Khata, and preferences remain intact."
    finally:
        if close_session:
            db.close()
