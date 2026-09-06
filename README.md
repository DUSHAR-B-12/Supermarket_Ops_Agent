# Supermarket Ops Agent

An autonomous, conversational AI agent that runs an entire Indian kirana store end-to-end via Telegram, powered by LLM tool orchestration.

## Live Bot
**@SuperMarket_All_in_one_Bot**  

## Architecture
The application runs as a lightweight, stateful backend bridging a Telegram interface to an LLM.

`Telegram → Agent (LLM) → Skills/Tools → Domain Services → SQLite → PDF/PPTX generation`

## Harness
This agent is built using a custom, native ReAct-style loop built directly on top of the **Gemini and Groq Python SDKs**, rather than using heavyweight frameworks like LangChain or LangGraph. 
**Why?** A custom loop provides absolute control over tool retry logic, idempotency checks, raw JSON schema alignment, and rate-limit fallbacks without the opaque abstraction overhead of node-based state machines.

## Control Loop
The core engine (`app/agent/runner.py`) uses a standard Agentic orchestration loop:
1. **Observe**: Receive the plain-language Telegram message and fetch the user's conversation history & persistent preferences.
2. **Reason**: The LLM analyzes the context and decides if it needs to execute a tool, ask for clarification, or finalize a response.
3. **Tool Call**: If tools are chosen, they are securely invoked in a sandboxed execution context (e.g., adding items to a draft bill).
4. **Tool Result**: The output of the Python functions (or SQL errors, stock guards) are fed back to the LLM.
5. **Continue**: The LLM repeats the cycle (chaining multiple tools if necessary) until all tasks are resolved.
6. **Natural-language Response**: The LLM synthesizes a final friendly response to the shopkeeper.

## Skills / Tools
The agent acts through thin tool wrappers over robust business services:
- **Inventory**: `search_products`, `receive_stock`, `get_stock`, `get_low_stock`
- **Billing**: `create_draft_bill`, `add_bill_item`, `edit_bill_item`, `remove_bill_item`, `finalize_bill`
- **Khata (Credit)**: `get_khata_balance`, `record_khata_repayment`
- **Preferences**: `set_preference`, `get_preference`
- **Analytics/Docs**: `get_daily_close`, `generate_invoice_pdf`, `generate_analysis_deck`

## Hard Parts
- **DB Grounding**: Prices and stock are never hallucinated; the LLM uses `search_products` to fetch exact details before billing.
- **Oversell Guard**: A strict `ValueError` is raised at the service layer if billed quantity > stock, which the LLM reads and relays to the user.
- **GST**: Calculations for CGST, SGST, and 0/5/12/18% slabs are handled mathematically by `TaxService`, not by the LLM.
- **Multi-turn Bills**: A `UserSession` table persists the `active_draft_bill_id`, allowing the user to add and edit items over several messages before finalizing.
- **Idempotency**: Telegram retries are caught using an `idempotency_key` mapped to the bill, preventing double billing.
- **Concurrency**: `finalize_bill` uses atomic SQL updates (`UPDATE ... WHERE quantity >= X`) to ensure two simultaneous checkout threads cannot oversell stock.
- **Guardrails**: Hardcoded logic prevents selling below cost price or over-repaying a Khata balance.
- **Persistence/Memory**: Preferences (e.g. "always assume UPI") are stored in SQLite and loaded into the System Prompt on every invocation.
- **Artifacts**: Real `reportlab` PDFs and `python-pptx` presentations (with native Pie/Bar charts) are generated dynamically based on real-time SQLite queries.

## Run Locally
1. Clone the repository and install dependencies:
```bash
pip install -r requirements.txt
```
2. Copy `.env.example` to `.env` and fill in your API keys (Telegram, Gemini).
3. Start the bot:
```bash
python run.py
```

## Tests
The suite contains 79 tests (including LLM mocking, concurrency, and Telegram handler tests).
```bash
python -m pytest -q
```
Result: `79 passed`

## Demo
A step-by-step 4-minute demonstration script of the bot's capabilities (Multi-item billing, Khata, PDF/PPTX generation, etc.) can be found in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).
