# Nebula Supermarket Ops Agent

An agentic Telegram bot system designed to run an Indian supermarket / kirana store end-to-end via conversational interaction.

## Architecture & Design Principles
- **Telegram Interface Only**: No web frontend, forms, or admin panels. Chat is the product.
- **Agent-First**: The LLM reasons over messy human requests and orchestrates appropriate domain tools.
- **Strict Business Logic**: Oversell protection, GST computations, khata limits, and idempotency are enforced at the tool, service, and database transaction layer.

## Project Structure
```
nebula-supermarket-ops-agent/
├── app/
│   ├── agent/        # AI Agent runner, prompt engineering, and tool calling loop
│   ├── tools/        # Business tools registered for the LLM agent
│   ├── services/     # Core domain services (inventory, billing, khata, tax, report)
│   ├── db/           # SQLAlchemy models, sessions, and database initializations
│   ├── telegram/     # Telegram bot handlers and lifecycle management
│   ├── artifacts/    # Generated PDF invoices and PPTX decks
│   └── config/       # Environment settings and application configurations
├── tests/            # Automated test suite (pytest)
├── data/             # Persistent SQLite database storage
├── .env.example      # Example environment variables template
├── .gitignore        # Git ignore rules
├── requirements.txt  # Project dependencies
├── README.md         # Documentation
└── run.py            # Main entry point script
```

## Setup & Running

### 1. Environment Setup
Copy `.env.example` to `.env` and fill in the required credentials:
```bash
cp .env.example .env
```

Ensure the following variables are configured in `.env`:
- `TELEGRAM_BOT_TOKEN` - Obtain from [@BotFather](https://t.me/BotFather)
- `LLM_API_KEY` - API key for LLM provider (e.g. Gemini / OpenAI / Anthropic)
- `DATABASE_URL` - SQLite URL (default: `sqlite:///./data/supermarket.db`)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Bot
```bash
python run.py
```

### 4. Run Tests
```bash
pytest
```
