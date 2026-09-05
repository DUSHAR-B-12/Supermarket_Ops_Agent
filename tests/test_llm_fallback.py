import pytest
from unittest.mock import MagicMock, patch
from app.agent.llm_client import LLMClient
from app.agent.registry import TOOL_SCHEMAS

# 1. Gemini Success -> No Groq Call & Exactly One Provider Request
def test_gemini_success_no_groq_call():
    client = LLMClient()
    client.gemini_model = "gemini-3.8-flash"
    client.gemini_fallback_models = ["gemini-3.7-flash"]
    client.gemini_client = MagicMock()
    client.groq_client = MagicMock()

    # Mock Gemini response
    mock_resp = MagicMock()
    mock_resp.function_calls = None
    mock_resp.text = "Gemini Response"
    client.gemini_client.models.generate_content.return_value = mock_resp

    text, calls = client.generate_completion(history=[], user_message="Hello")

    assert text == "Gemini Response"
    assert calls is None
    client.gemini_client.models.generate_content.assert_called_once()
    assert client.gemini_client.models.generate_content.call_args[1]["model"] == "gemini-3.8-flash"
    client.groq_client.chat.completions.create.assert_not_called()

# 2. Gemini 3.8 Failure -> 3.7 Fallback Success
def test_gemini_38_to_37_fallback():
    client = LLMClient()
    client.gemini_model = "gemini-3.8-flash"
    client.gemini_fallback_models = ["gemini-3.7-flash"]
    client.gemini_client = MagicMock()
    client.groq_client = MagicMock()

    # Fail on first call, succeed on second
    mock_resp = MagicMock()
    mock_resp.function_calls = None
    mock_resp.text = "Gemini 3.7 Response"
    
    client.gemini_client.models.generate_content.side_effect = [
        Exception("429 ResourceExhausted: Quota exceeded"),
        mock_resp
    ]

    text, calls = client.generate_completion(history=[], user_message="Check stock")

    assert text == "Gemini 3.7 Response"
    assert calls is None
    assert client.gemini_client.models.generate_content.call_count == 2
    # First call with 3.8
    assert client.gemini_client.models.generate_content.call_args_list[0][1]["model"] == "gemini-3.8-flash"
    # Second call with 3.7
    assert client.gemini_client.models.generate_content.call_args_list[1][1]["model"] == "gemini-3.7-flash"
    client.groq_client.chat.completions.create.assert_not_called()

# 3. All Gemini Models Fail -> Groq Fallback Success
def test_all_gemini_failure_groq_fallback():
    client = LLMClient()
    client.gemini_model = "gemini-3.8-flash"
    client.gemini_fallback_models = ["gemini-3.7-flash", "gemini-3.6-flash"]
    client.gemini_client = MagicMock()
    client.groq_client = MagicMock()

    # Fail all Gemini calls
    client.gemini_client.models.generate_content.side_effect = Exception("503 Service Unavailable")

    # Mock Groq response
    mock_choice = MagicMock()
    mock_choice.message.tool_calls = None
    mock_choice.message.content = "Groq Fallback Response"
    
    mock_groq_resp = MagicMock()
    mock_groq_resp.choices = [mock_choice]
    client.groq_client.chat.completions.create.return_value = mock_groq_resp

    text, calls = client.generate_completion(history=[], user_message="Check stock")

    assert text == "Groq Fallback Response"
    assert calls is None
    assert client.gemini_client.models.generate_content.call_count == 3
    client.groq_client.chat.completions.create.assert_called_once()

# 3. Both Providers Failing -> Clean Error Message
def test_both_providers_failing():
    client = LLMClient()
    client.gemini_client = MagicMock()
    client.groq_client = MagicMock()

    client.gemini_client.models.generate_content.side_effect = Exception("Gemini API Error")
    client.groq_client.chat.completions.create.side_effect = Exception("Groq API Error")

    text, calls = client.generate_completion(history=[], user_message="Hello")

    assert text is not None
    assert "All LLM providers failed" in text
    assert "Gemini API Error" in text
    assert "Groq API Error" in text

# 4. Tool Schemas Unchanged & Valid
def test_tool_schemas_integrity():
    assert isinstance(TOOL_SCHEMAS, list)
    assert len(TOOL_SCHEMAS) >= 20
    schema_names = [s["name"] for s in TOOL_SCHEMAS]
    assert "search_products" in schema_names
    assert "finalize_bill" in schema_names
    assert "generate_invoice_pdf" in schema_names
    assert "generate_analysis_deck" in schema_names
