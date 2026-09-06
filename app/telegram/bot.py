import os
import re
import json
import logging
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.agent.runner import process_agent_message, reset_user_conversation
from app.config.settings import settings

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command from Telegram user."""
    user = update.effective_user
    user_info = f"{user.id} (@{user.username})" if user and user.username else str(user.id if user else "unknown")
    logger.info(f"Received /start command from user {user_info}")

    reply = (
        " *Welcome to Supermarket Ops Agent!*\n\n"
        "I am your AI-powered Kirana store operations assistant.\n"
        "Send me natural language requests (e.g. stock updates, billing, credit queries, PDF invoices, sales decks).\n\n"
        "Type `/new` anytime to start a fresh conversation session."
    )
    if update.message:
        await update.message.reply_text(reply, parse_mode="Markdown")


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command to reset user conversation session."""
    user = update.effective_user
    user_id = user.id if user else 0
    logger.info(f"Received /new command from user {user_id}")

    reply = reset_user_conversation(user_id=user_id)
    if update.message:
        await update.message.reply_text(reply)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle normal incoming text messages from Telegram user."""
    import time
    telegram_receive_start = time.time()
    
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = user.id if user else 0
    username = f"@{user.username}" if user and user.username else "unknown"
    message_text = update.message.text.strip()

    telegram_receive_ms = int((time.time() - telegram_receive_start) * 1000)
    logger.info(f"Incoming Telegram message from user {user_id} ({username}): '{message_text}'")

    try:
        response_text = await process_agent_message(user_id=user_id, message_text=message_text)

        # Detect [FILE: /path/to/file] artifact tags
        file_matches = re.findall(r"\[FILE:\s*([^\]]+)\]", response_text)
        clean_text = re.sub(r"\[FILE:\s*([^\]]+)\]", "", response_text).strip()

        telegram_send_start = time.time()
        # Send text response
        if clean_text:
            # Telegram has a 4096-character message limit
            for i in range(0, len(clean_text), 4096):
                await update.message.reply_text(clean_text[i:i+4096])

        # Send document attachments for generated artifacts
        for file_path in file_matches:
            file_path = file_path.strip()
            if os.path.exists(file_path):
                logger.info(f"Sending document artifact to user {user_id}: {file_path}")
                with open(file_path, "rb") as doc_file:
                    filename = os.path.basename(file_path)
                    await update.message.reply_document(document=doc_file, filename=filename)
        telegram_send_ms = int((time.time() - telegram_send_start) * 1000)
        logger.info(f"TELEGRAM_STATS: {json.dumps({'receive_ms': telegram_receive_ms, 'send_ms': telegram_send_ms, 'total_ms': int((time.time() - telegram_receive_start) * 1000)})}")

    except Exception as e:
        logger.error(f"Error processing Telegram message from user {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "⚠️ An error occurred while processing your request. Please try again or type `/new` to reset."
            )
        except Exception:
            logger.error("Failed to send error message to user.", exc_info=True)


def create_telegram_app() -> Application:
    """Factory to build python-telegram-bot Application instance with appropriate timeouts."""
    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "placeholder_bot_token":
        logger.warning(
            "TELEGRAM_BOT_TOKEN is not set or using default placeholder. "
            "Bot polling will fail unless a valid token is provided in .env."
        )

    app = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


def run_bot() -> None:
    """Start the Telegram bot in long-polling mode."""
    logger.info("Starting Telegram Bot long-polling...")
    app = create_telegram_app()
    app.run_polling()
