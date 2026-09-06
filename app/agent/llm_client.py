import os
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.config.settings import settings
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.registry import TOOL_SCHEMAS

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Multi-provider LLM Client supporting Primary (Google Gemini) and Secondary (Groq API)
    with automatic graceful fallback on rate limits / quota / provider errors.
    """

    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
        self.gemini_model = (
            os.getenv("GEMINI_MODEL")
            or getattr(settings, "GEMINI_MODEL", "gemini-3.1-flash-lite")
        )
        
        fallback_str = os.getenv("GEMINI_FALLBACK_MODELS") or getattr(settings, "GEMINI_FALLBACK_MODELS", "")
        self.gemini_fallback_models = [m.strip() for m in fallback_str.split(",") if m.strip()]

        self.groq_key = os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", "")
        self.groq_model = (
            os.getenv("GROQ_MODEL")
            or getattr(settings, "GROQ_MODEL", "qwen/qwen3.8-27b")
        )

        # Legacy OpenAI support if configured via LLM_API_KEY
        self.llm_key = os.getenv("LLM_API_KEY") or getattr(settings, "LLM_API_KEY", "")
        self.llm_model = os.getenv("LLM_MODEL") or getattr(settings, "LLM_MODEL", "gemini-3.6-flash")

        self.gemini_client = None
        self.groq_client = None
        self.openai_client = None

        if self.gemini_key and self.gemini_key != "placeholder_gemini_key":
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.gemini_key)
                logger.info("Initialized Google GenAI primary LLM client.")
            except Exception as e:
                logger.warning(f"Could not initialize google.genai: {e}")

        if self.groq_key and self.groq_key != "placeholder_groq_key":
            try:
                from openai import OpenAI
                self.groq_client = OpenAI(
                    api_key=self.groq_key,
                    base_url="https://api.groq.com/openai/v1"
                )
                logger.info("Initialized Groq secondary LLM client.")
            except Exception as e:
                logger.warning(f"Could not initialize Groq client: {e}")

        if self.llm_key and self.llm_key != "placeholder_llm_key":
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.llm_key)
                logger.info("Initialized generic OpenAI client.")
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI client: {e}")

    def generate_completion(
        self,
        history: List[Dict[str, str]],
        user_message: str,
        tool_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Runs a completion turn trying Primary (Gemini) first, with fallback to Secondary (Groq).
        Returns: (final_text, tool_calls_list)
        """
        # Primary Provider: Google Gemini with Fallback Chain
        if self.gemini_client:
            gemini_models_to_try = [self.gemini_model] + getattr(self, "gemini_fallback_models", [])
            last_gemini_err = None
            
            for model_name in gemini_models_to_try:
                try:
                    logger.info(f"Calling primary provider: Google Gemini ({model_name})")
                    return self._call_google_genai(history, user_message, tool_results, model_name=model_name)
                except Exception as gemini_err:
                    # We catch Exception here because the google.genai SDK exceptions (like APIError) inherit from Exception.
                    err_str = str(gemini_err).lower()
                    is_quota = any(term in err_str for term in ["429", "resource_exhausted", "quota", "rate limit"])
                    
                    if is_quota:
                        logger.warning(f"Gemini model {model_name} failed due to QUOTA/RATE LIMIT: {gemini_err}. Immediately trying next fallback.")
                    else:
                        logger.warning(f"Gemini model {model_name} failed with non-quota error: {gemini_err}; following existing fallback policy.")
                    
                    last_gemini_err = gemini_err
            
            # If all Gemini models failed, fallback to Groq if configured
            if self.groq_client:
                logger.info(f"Attempting fallback to secondary provider: Groq ({self.groq_model})")
                try:
                    return self._call_groq(history, user_message, tool_results)
                except Exception as groq_err:
                    logger.error(f"Secondary provider (Groq) also failed: {groq_err}")
                    return f"⚠️ All LLM providers failed. Primary (Gemini) error: {last_gemini_err}. Secondary (Groq) error: {groq_err}", None
            
            # Fallback to generic OpenAI if configured
            if self.openai_client:
                logger.info("Attempting fallback to generic OpenAI client.")
                try:
                    return self._call_openai(history, user_message, tool_results)
                except Exception as openai_err:
                    logger.error(f"Generic OpenAI client also failed: {openai_err}")

            return f"⚠️ Primary AI provider (Gemini) error: {last_gemini_err}", None

        # Secondary Provider direct: Groq
        if self.groq_client:
            try:
                logger.info(f"Calling Groq provider ({self.groq_model})")
                return self._call_groq(history, user_message, tool_results)
            except Exception as groq_err:
                logger.error(f"Groq provider error: {groq_err}")
                return f"⚠️ Groq API error: {groq_err}", None

        # Generic OpenAI direct
        if self.openai_client:
            try:
                logger.info("Calling generic OpenAI provider.")
                return self._call_openai(history, user_message, tool_results)
            except Exception as openai_err:
                return f"⚠️ OpenAI API error: {openai_err}", None

        # Mock Mode when no live API keys are provided
        logger.info("No live LLM API keys configured. Running in Mock/Deterministic mode.")
        return self._call_mock(history, user_message, tool_results)

    def _call_google_genai(
        self, history: List[Dict[str, str]], user_message: str, tool_results: Optional[List[Dict[str, Any]]], model_name: str = None
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        from google.genai import types

        model_name = model_name or self.gemini_model
        contents = []
        for h in history:
            role = "user" if h["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h["content"])]))

        if tool_results:
            combined_text = f"User Request: {user_message}\nTool Execution Results: {json.dumps(tool_results)}"
            tool_res_parts = [types.Part.from_text(text=combined_text)]
            contents.append(types.Content(role="user", parts=tool_res_parts))
        else:
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

        config_kwargs = {
            "system_instruction": SYSTEM_PROMPT,
            "tools": [types.Tool(function_declarations=TOOL_SCHEMAS)],
            "temperature": 0.2,
            "http_options": types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1)
            )
        }
        
        if "3.8-flash" in model_name:
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=1024)

        config = types.GenerateContentConfig(**config_kwargs)

        response = self.gemini_client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )

        tool_calls = []
        if response.function_calls:
            for fc in response.function_calls:
                tool_calls.append({"name": fc.name, "arguments": dict(fc.args)})
            return None, tool_calls

        text_resp = response.text or "I have processed your request."
        return text_resp, None

    def _call_groq(
        self, history: List[Dict[str, str]], user_message: str, tool_results: Optional[List[Dict[str, Any]]]
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})

        if tool_results:
            combined_text = f"User Request: {user_message}\nTool Execution Results: {json.dumps(tool_results)}"
            messages.append({"role": "user", "content": combined_text})
        else:
            messages.append({"role": "user", "content": user_message})

        groq_tools = [{"type": "function", "function": schema} for schema in TOOL_SCHEMAS]

        response = self.groq_client.chat.completions.create(
            model=self.groq_model,
            messages=messages,
            tools=groq_tools,
            tool_choice="auto",
        )

        choice = response.choices[0].message
        if choice.tool_calls:
            calls = []
            for tc in choice.tool_calls:
                calls.append({
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments or "{}"),
                })
            return None, calls

        return choice.content or "Done.", None

    def _call_openai(
        self, history: List[Dict[str, str]], user_message: str, tool_results: Optional[List[Dict[str, Any]]]
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})

        if tool_results:
            combined_text = f"User Request: {user_message}\nTool Execution Results: {json.dumps(tool_results)}"
            messages.append({"role": "user", "content": combined_text})
        else:
            messages.append({"role": "user", "content": user_message})

        openai_tools = [{"type": "function", "function": schema} for schema in TOOL_SCHEMAS]

        response = self.openai_client.chat.completions.create(
            model=self.llm_model if "gpt" in self.llm_model else "gpt-4o-mini",
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
        )

        choice = response.choices[0].message
        if choice.tool_calls:
            calls = []
            for tc in choice.tool_calls:
                calls.append({
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments or "{}"),
                })
            return None, calls

        return choice.content or "Done.", None

    def _call_mock(
        self, history: List[Dict[str, str]], user_message: str, tool_results: Optional[List[Dict[str, Any]]]
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """Mock fallback logic for deterministic unit testing without API keys."""
        if tool_results:
            # Multi-item adding behavior or corrections
            if any(tr.get("name") == "search_products" and tr.get("status") == "success" for tr in tool_results):
                msg_l = user_message.lower()
                import re as _re
                if _re.search(r'\b(change|make it|edit)\b', msg_l) and not any(tr.get("name") == "edit_bill_item" for tr in tool_results):
                    return None, [{"name": "edit_bill_item", "arguments": {"bill_id": 1, "product_id": 2, "new_quantity": 5.0}}]
                if _re.search(r'\b(remove|delete|cancel that item)\b', msg_l) and not any(tr.get("name") == "remove_bill_item" for tr in tool_results):
                    return None, [{"name": "remove_bill_item", "arguments": {"bill_id": 1, "product_id": 2}}]
                
                found_products = []
                for tr in tool_results:
                    if tr.get("name") == "search_products" and tr.get("status") == "success":
                        prods = tr.get("data", [])
                        if isinstance(prods, list):
                            found_products.extend(prods)
                        else:
                            found_products.append(prods)
                
                # Check which products have already been added in this session
                added_product_ids = set()
                for tr in tool_results:
                    if tr.get("name") == "add_bill_item" and tr.get("status") == "success":
                        added_product_ids.add(tr.get("data", {}).get("items", [-1])[-1].get("product_id"))
                
                qty_map = {
                    "atta": 2.0, "salt": 1.0, "maggi": 3.0,
                    "butter": 1.0, "oil": 1.0, "parle": 1.0,
                    "surf": 1.0, "sugar": 1.0, "rice": 1.0, "dal": 1.0,
                }
                
                import re
                msg_l = user_message.lower()
                
                # Find the FIRST found product that hasn't been added yet, and add it
                for prod in found_products:
                    if prod["id"] in added_product_ids:
                        continue
                        
                    pname = prod.get("name", "").lower()
                    matched_key = None
                    for key in qty_map:
                        if key in pname:
                            matched_key = key
                            break
                    if matched_key is None:
                        continue
                    
                    qty = qty_map.get(matched_key, 1.0)
                    pattern = rf'(\d+)[^\d]*?{re.escape(matched_key)}'
                    matches = list(re.finditer(pattern, msg_l))
                    if matches:
                        qty = float(matches[-1].group(1))
                        
                    return None, [{"name": "add_bill_item", "arguments": {"product_id": prod["id"], "quantity": qty}}]

            # No more products to add — generate a natural-language summary from tool results
            from app.agent.runner import format_tool_response
            return format_tool_response(tool_results), None

        msg_lower = user_message.lower()
        import re as _re

        # Conversational Chatter (MOCK ONLY)
        if _re.search(r'^(hi|hello|hey|good morning|thanks|ok|bye)\b', msg_lower):
            return "Hello! I am your Supermarket Ops Agent. How can I help?", None

        if _re.search(r'\b(what can you do|capabilities|store operations)\b', msg_lower):
            return "I am your Supermarket Ops Agent! I can manage inventory, create bills, track Khata balances, and generate daily closing reports or analysis decks.", None

        # Bill corrections triggers search
        if _re.search(r'\b(change|make it|edit)\b', msg_lower):
             return None, [{"name": "search_products", "arguments": {"query": "maggi"}}]
        if _re.search(r'\b(remove|delete|cancel that item)\b', msg_lower):
             return None, [{"name": "search_products", "arguments": {"query": "butter"}}]

        # Multi-product add-to-bill: search ALL mentioned products in one turn
        product_search_map = {
            "atta": "Aashirvaad Atta 5kg",
            "salt": "Tata Salt 1kg",
            "maggi": "Maggi 70g",
            "butter": "Amul Butter 100g",
            "oil": "Fortune Sunflower Oil 1L",
            "parle": "Parle-G",
            "surf": "Surf Excel",
        }
        if "add" in msg_lower and "stock" not in msg_lower:
            calls = []
            for key, query in product_search_map.items():
                if key in msg_lower:
                    calls.append({"name": "search_products", "arguments": {"query": query}})
            if calls:
                return None, calls

        # Generic stock query: "How much X do I have?"
        if "how much" in msg_lower:
            # Extract the product name from the query
            import re as _re
            match = _re.search(r'how much\s+(.+?)\s+do\s+i\s+have', msg_lower)
            if match:
                query = match.group(1).strip()
                return None, [{"name": "search_products", "arguments": {"query": query}}]
            return None, [{"name": "search_products", "arguments": {"query": user_message}}]

        # Stock receiving: "Add N X to stock"
        if "add" in msg_lower and "stock" in msg_lower:
            import re as _re
            match = _re.search(r'add\s+(\d+)\s+(.+?)\s+to\s+stock', msg_lower)
            if match:
                query = match.group(2).strip()
                return None, [{"name": "search_products", "arguments": {"query": query}}]

        # Search queries: "Show me everything containing X" / "Show me all products with X"
        if "show" in msg_lower and ("containing" in msg_lower or "product" in msg_lower):
            import re as _re
            match = _re.search(r'(?:containing|with|products?)\s+(.+?)[\.!?]?$', msg_lower)
            if match:
                query = match.group(1).strip()
                return None, [{"name": "search_products", "arguments": {"query": query}}]

        if "low stock" in msg_lower or "running out" in msg_lower or "reorder" in msg_lower:
            return None, [{"name": "get_low_stock", "arguments": {}}]
        elif "make a bill" in msg_lower or "bill for" in msg_lower or "create bill" in msg_lower:
            return None, [{"name": "create_draft_bill", "arguments": {}}]
        elif "finalize" in msg_lower or "complete the bill" in msg_lower:
            return None, [{"name": "finalize_bill", "arguments": {"payment_method": "UPI"}}]
        elif "owes" in msg_lower or "khata" in msg_lower:
            return None, [{"name": "get_customer", "arguments": {"name": "Ravi"}}]
        elif "prefer" in msg_lower or "remember" in msg_lower:
            if "upi" in msg_lower or "cash" in msg_lower or "card" in msg_lower or "set" in msg_lower:
                return None, [{"name": "set_preference", "arguments": {"key": "default_payment_method", "value": "UPI"}}]
            else:
                return None, [{"name": "get_preference", "arguments": {"key": "default_payment_method"}}]
        elif "today's close" in msg_lower or "daily close" in msg_lower:
            return None, [{"name": "get_daily_close", "arguments": {}}]
        elif "analysis deck" in msg_lower or "pptx" in msg_lower:
            return None, [{"name": "generate_analysis_deck", "arguments": {}}]
        elif "add new product" in msg_lower or "create product" in msg_lower or "add a product" in msg_lower:
            # For testing, return add_product with dummy arguments
            return None, [{"name": "add_product", "arguments": {
                "sku": "NEW-1", "name": "Facewash", "category": "Personal Care", 
                "unit": "piece", "cost_price": 50.0, "mrp": 100.0, "selling_price": 90.0
            }}]
        elif any(phrase in msg_lower for phrase in ["what's in stock", "show stock", "check inventory", "what do we have", "list products", "inventory", "stock", "items are available", "what products"]):
            return None, [{"name": "search_products", "arguments": {"query": "*"}}]
        elif _re.search(r'\b(find|search|do we sell|show|check)\s+(maggi|atta|salt|butter|oil|facewash)\b', msg_lower):
            match = _re.search(r'\b(find|search|do we sell|show|check)\s+(maggi|atta|salt|butter|oil|facewash)\b', msg_lower)
            return None, [{"name": "search_products", "arguments": {"query": match.group(2)}}]
        elif _re.search(r'\b(pdf|send invoice|generate receipt)\b', msg_lower):
            return None, [{"name": "generate_invoice_pdf", "arguments": {}}]
        elif _re.search(r'\b(total|calculate)\b', msg_lower):
            return None, [{"name": "calculate_bill", "arguments": {}}]
        elif _re.search(r'\b(paid|repayment|settle)\b', msg_lower):
             return None, [{"name": "record_khata_repayment", "arguments": {"customer_id": 1, "amount": 300.0}}]

        return f"🤖 [Kirana Agent Response]: I understand you said '{user_message}'. How else can I assist with store operations?", None
