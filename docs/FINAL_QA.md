# Supermarket Ops Agent — Final QA Checklist

This document ensures the bot is ready for production and complies with every requirement from the Nebula KnowLab PDF.

## 1. Automated Testing
Run the comprehensive test suite to verify core logic:
```bash
python -m pytest -q
```
- Expect > 70 passing tests.
- This includes integration tests, concurrency tests, and logic boundary tests.

## 2. Production Smoke Test
Before calling it production-ready, manually verify:
- [ ] **Startup**: `python run.py` initializes without crashing and connects to Telegram.
- [ ] **Message Received**: The bot responds to a simple `hello` message.
- [ ] **State Persists**: After restarting `run.py`, the active draft bill and khata balances remain intact.

## 3. Artifact Validation
Ensure the generated documents open successfully without corruption.
- [ ] **PDF Invoice**: `send me the bill as PDF` -> Open the resulting `.pdf`. Check for GST accuracy (CGST/SGST split).
- [ ] **PPTX Analysis**: `make analysis deck` -> Open the resulting `.pptx`. Verify native Pie/Bar charts render correctly.

## 4. Telegram Reliability Test
- [ ] Ensure the bot recovers gracefully if Telegram servers time out.
- [ ] Ensure idempotency: rapid double-sends of "finalize" do not decrement stock twice.

## 5. Persistence Test
- [ ] Delete `data/supermarket.db` (if local test).
- [ ] Run `python run.py` to auto-seed a fresh database.
- [ ] Verify products exist by asking `search products`.

## 6. Concurrency Test
- Run `python -m pytest tests/test_concurrency.py`.
- This ensures that if two users/devices attempt to finalize a bill that sells the last item in stock at the exact same millisecond, only ONE transaction succeeds and the other rolls back gracefully.

## 7. Submission PDF Requirements Checklist

| Requirement | Verified? |
|-------------|-----------|
| Telegram-only interface | [x] |
| Agent-first architecture (LLM tools) | [x] |
| Durable SQLite persistence | [x] |
| GST calculations & HSN codes | [x] |
| Multi-turn draft bills & edits | [x] |
| Idempotency & Oversell Guard | [x] |
| Concurrency Safety (Atomic deduction) | [x] |
| Khata Management (Credit/Repay) | [x] |
| Persistent owner preferences | [x] |
| Valid PDF & real PPTX charts | [x] |
