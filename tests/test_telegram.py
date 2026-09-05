import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.telegram.bot import create_telegram_app, start_command, handle_message
from app.agent.runner import process_agent_message

def test_telegram_app_creation():
    app = create_telegram_app()
    assert app is not None

@pytest.mark.asyncio
async def test_start_command():
    update = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.message = AsyncMock()

    context = MagicMock()

    await start_command(update, context)

    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    assert "Welcome to Supermarket Ops Agent" in args[0]

@pytest.mark.asyncio
async def test_handle_message():
    update = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.message.text = "Hello Kirana Bot"
    update.message.reply_text = AsyncMock()

    context = MagicMock()

    with patch("app.agent.runner.get_llm_client") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.generate_completion.return_value = ("Hello from Mock Agent", None)
        mock_get_llm.return_value = mock_llm

        await handle_message(update, context)

        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        assert "Hello from Mock Agent" in args[0]

@pytest.mark.asyncio
async def test_agent_runner_response():
    with patch("app.agent.runner.get_llm_client") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.generate_completion.return_value = ("Received stock update", None)
        mock_get_llm.return_value = mock_llm

        response = await process_agent_message(user_id=12345, message_text="50 packets of Maggi came in")
        assert "Received stock update" in response
