import pytest
from unittest.mock import MagicMock
from app.agent.llm_client import LLMClient
from app.agent.registry import TOOL_SCHEMAS

# 1. Primary Gemini quota error -> second Gemini model
def test_primary_quota_error_fallback_to_second():
    client = LLMClient()
    client.gemini_model = "gemini-3.8-flash"
    client.gemini_fallback_models = ["gemini-3.7-flash", "gemini-3.6-flash"]
    client.gemini_client = MagicMock()
    client.groq_client = MagicMock()

    mock_resp = MagicMock()
    mock_resp.function_calls = None
    mock_resp.text = "Gemini 3.7 Response"
    
    # 3.8 gets 429 quota exhausted, 3.7 succeeds
    client.gemini_client.models.generate_content.side_effect = [
        Exception("429 ResourceExhausted: Quota exceeded"),
        mock_resp
    ]

    text, calls = client.generate_completion(history=[], user_message="Hello")

    assert text == "Gemini 3.7 Response"
    assert client.gemini_client.models.generate_content.call_count == 2
    assert client.gemini_client.models.generate_content.call_args_list[0][1]["model"] == "gemini-3.8-flash"
    assert client.gemini_client.models.generate_content.call_args_list[1][1]["model"] == "gemini-3.7-flash"
    client.groq_client.chat.completions.create.assert_not_called()

# 2. First two Gemini models quota error -> third Gemini model
def test_two_models_quota_error_fallback_to_third():
    client = LLMClient()
    client.gemini_model = "gemini-3.8-flash"
    client.gemini_fallback_models = ["gemini-3.7-flash", "gemini-3.6-flash"]
    client.gemini_client = MagicMock()
    client.groq_client = MagicMock()

    mock_resp = MagicMock()
    mock_resp.function_calls = None
    mock_resp.text = "Gemini 3.6 Response"
    
    # 3.8 and 3.7 get quota errors, 3.6 succeeds
    client.gemini_client.models.generate_content.side_effect = [
        Exception("HTTP 429 quota limit"),
        Exception("rate limit exceeded"),
        mock_resp
    ]

    text, calls = client.generate_completion(history=[], user_message="Hello")

    assert text == "Gemini 3.6 Response"
    assert client.gemini_client.models.generate_content.call_count == 3
    assert client.gemini_client.models.generate_content.call_args_list[2][1]["model"] == "gemini-3.6-flash"

# 3. All Gemini models fail -> Groq
def test_all_gemini_failure_groq_fallback():
    client = LLMClient()
    client.gemini_model = "gemini-3.8-flash"
    client.gemini_fallback_models = ["gemini-3.7-flash"]
    client.gemini_client = MagicMock()
    client.groq_client = MagicMock()

    client.gemini_client.models.generate_content.side_effect = Exception("429 Quota Exceeded")

    mock_choice = MagicMock()
    mock_choice.message.tool_calls = None
    mock_choice.message.content = "Groq Fallback Response"
    
    mock_groq_resp = MagicMock()
    mock_groq_resp.choices = [mock_choice]
    client.groq_client.chat.completions.create.return_value = mock_groq_resp

    text, calls = client.generate_completion(history=[], user_message="Hello")

    assert text == "Groq Fallback Response"
    assert client.gemini_client.models.generate_content.call_count == 2
    client.groq_client.chat.completions.create.assert_called_once()

# 4. Non-quota errors behave according to the existing error policy
def test_non_quota_error_still_falls_back():
    client = LLMClient()
    client.gemini_model = "gemini-3.8-flash"
    client.gemini_fallback_models = ["gemini-3.7-flash"]
    client.gemini_client = MagicMock()
    client.groq_client = MagicMock()

    mock_resp = MagicMock()
    mock_resp.function_calls = None
    mock_resp.text = "Gemini 3.7 Response after 500 error"
    
    # Non-quota error (e.g. 500 Server Error)
    client.gemini_client.models.generate_content.side_effect = [
        Exception("500 Internal Server Error"),
        mock_resp
    ]

    text, calls = client.generate_completion(history=[], user_message="Hello")

    # Should still fallback correctly
    assert text == "Gemini 3.7 Response after 500 error"
    assert client.gemini_client.models.generate_content.call_count == 2
    
# 5. Successful fallback still supports tool calls
def test_fallback_supports_tool_calls():
    client = LLMClient()
    client.gemini_model = "gemini-3.8-flash"
    client.gemini_fallback_models = ["gemini-3.7-flash"]
    client.gemini_client = MagicMock()
    
    # First fails
    # Second returns a tool call
    mock_fc = MagicMock()
    mock_fc.name = "get_stock"
    mock_fc.args = {"product_id": 101}
    
    mock_resp = MagicMock()
    mock_resp.function_calls = [mock_fc]
    mock_resp.text = ""
    
    client.gemini_client.models.generate_content.side_effect = [
        Exception("429 ResourceExhausted"),
        mock_resp
    ]

    text, calls = client.generate_completion(history=[], user_message="Check stock")

    assert calls is not None
    assert len(calls) == 1
    assert calls[0]["name"] == "get_stock"
    assert calls[0]["arguments"] == {"product_id": 101}
