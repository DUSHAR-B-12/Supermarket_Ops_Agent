import logging
import sys
from app.config.settings import settings
from app.db.session import init_db
from app.telegram.bot import run_bot

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("run")


def main() -> None:
    logger.info("Initializing Supermarket Ops Agent Foundation...")
    
    # Initialize database tables
    try:
        init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    # Start Telegram Bot Polling
    try:
        run_bot()
    except Exception as e:
        logger.error(f"Telegram Bot failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
