import os
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.config.settings import settings
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.registry import TOOL_SCHEMAS

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
        self.llm_key = os.getenv("LLM_API_KEY") or getattr(settings, "LLM_API_KEY", "")
        self.model_name = (
            os.getenv("GEMINI_MODEL")
            or os.getenv("LLM_MODEL")
            or getattr(settings, "GEMINI_MODEL", None)
            or getattr(settings, "LLM_MODEL", "gemini-3.6-flash")
        )



        self.client_type = None

        if self.gemini_key and self.gemini_key != "placeholder_gemini_key":
            try:
                from google import genai
                self.client = genai.Client(api_key=self.gemini_key)
                self.client_type = "google_genai"
                logger.info("Initialized Google GenAI LLM client.")
            except Exception as e:
                logger.warning(f"Could not initialize google.genai: {e}")

        if not self.client_type and self.llm_key and self.llm_key != "placeholder_llm_key":
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.llm_key)
                self.client_type = "openai"
                logger.info("Initialized OpenAI LLM client.")
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI client: {e}")

        if not self.client_type:
            logger.info("No live LLM API key detected. Running in Mock/Deterministic mode.")
            self.client_type = "mock"

    def generate_completion(
        self,
        history: List[Dict[str, str]],
        user_message: str,
        tool_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Runs a completion turn.
        Returns:
            (final_text, tool_calls_list)
            If tool_calls_list is returned, the runner executes them and feeds results back.
            If final_text is returned, the turn is complete.
        """
        if self.client_type == "google_genai":
            return self._call_google_genai(history, user_message, tool_results)
        elif self.client_type == "openai":
            return self._call_openai(history, user_message, tool_results)
        else:
            return self._call_mock(history, user_message, tool_results)

    def _call_google_genai(
        self, history: List[Dict[str, str]], user_message: str, tool_results: Optional[List[Dict[str, Any]]]
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        try:
            from google.genai import types
            
            # Format messages
            contents = []
            for h in history:
                role = "user" if h["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h["content"])]))
            
            if tool_results:
                tool_res_parts = [types.Part.from_text(text=f"Tool Execution Results: {json.dumps(tool_results)}")]
                contents.append(types.Content(role="user", parts=tool_res_parts))
            else:
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[types.Tool(function_declarations=TOOL_SCHEMAS)],
                temperature=0.2,
            )

            model_to_use = (
                os.getenv("GEMINI_MODEL")
                or os.getenv("LLM_MODEL")
                or getattr(settings, "GEMINI_MODEL", "gemini-3.6-flash")
            )
            response = self.client.models.generate_content(
                model=model_to_use,
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
        except Exception as e:
            logger.error(f"Google GenAI API call error: {e}")
            return f"⚠️ Error calling AI model: {e}", None

    def _call_openai(
        self, history: List[Dict[str, str]], user_message: str, tool_results: Optional[List[Dict[str, Any]]]
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for h in history:
                messages.append({"role": h["role"], "content": h["content"]})

            if tool_results:
                messages.append({"role": "user", "content": f"Tool Execution Results: {json.dumps(tool_results)}"})
            else:
                messages.append({"role": "user", "content": user_message})

            openai_tools = [{"type": "function", "function": schema} for schema in TOOL_SCHEMAS]

            response = self.client.chat.completions.create(
                model=self.model_name if "gpt" in self.model_name else "gpt-4o-mini",
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
        except Exception as e:
            logger.error(f"OpenAI API call error: {e}")
            return f"⚠️ Error calling AI model: {e}", None

    def _call_mock(
        self, history: List[Dict[str, str]], user_message: str, tool_results: Optional[List[Dict[str, Any]]]
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """Mock fallback logic for deterministic unit testing without API keys."""
        if tool_results:
            # Format tool result response
            res_strs = []
            for tr in tool_results:
                if tr.get("status") == "error":
                    res_strs.append(f"❌ {tr.get('error')}")
                else:
                    res_strs.append(f"✅ Executed {tr.get('name')}: {json.dumps(tr.get('data'))}")
            return "\n".join(res_strs), None

        msg_lower = user_message.lower()

        # Intent heuristic for Mock Mode only when no API key is set
        if "how much" in msg_lower and "atta" in msg_lower:
            return None, [{"name": "search_products", "arguments": {"query": "Aashirvaad Atta 5kg"}}]
        elif "add" in msg_lower and "maggi" in msg_lower and "stock" in msg_lower:
            return None, [
                {"name": "search_products", "arguments": {"query": "Maggi 70g"}},
            ]
        elif "low stock" in msg_lower or "running out" in msg_lower:
            return None, [{"name": "get_low_stock", "arguments": {}}]
        elif "make a bill" in msg_lower or "bill for" in msg_lower:
            return None, [{"name": "create_draft_bill", "arguments": {}}]
        elif "finalize" in msg_lower:
            return None, [{"name": "finalize_bill", "arguments": {"bill_id": 1, "payment_method": "UPI"}}]
        elif "owes" in msg_lower or "khata" in msg_lower:
            return None, [{"name": "get_customer", "arguments": {"name": "Ravi"}}]

        return f"🤖 [Kirana Agent Response]: I understand you said '{user_message}'. How else can I assist with store operations?", None
