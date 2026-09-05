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
- `GEMINI_API_KEY` - Your primary Google Gemini API key
- `GEMINI_MODEL` - Primary model (e.g. `gemini-3.8-flash`)
- `GEMINI_FALLBACK_MODELS` - Comma-separated list of fallback models
- `GROQ_API_KEY` - Secondary fallback Groq API key
- `DATABASE_URL` - SQLite URL (default: `sqlite:///./data/supermarket.db`)

### Example Commands
Interact with the bot naturally in Telegram:
- "What do we have in stock?"
- "Add 100 packets of Aashirvaad Atta 5kg to stock"
- "Make a bill for Ravi"
- "Add 2 Tata Salt 1kg and 3 Maggi 70g"
- "Finalize the bill"
- "Generate invoice"
- "Ravi paid ₹500 towards his khata"
- "Generate daily close presentation"

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
