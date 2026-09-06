# Supermarket Ops Agent — Demo Script

This script demonstrates the agent's full end-to-end capabilities as requested in the final evaluation criteria.

**Target Duration**: 4–5 minutes

## Prerequisites
Ensure the bot is running (`python run.py`) and the database is initialized.

---

### Step 1: Receive Stock
**Message:**
> `50 packets of Maggi came in, cost ₹12, MRP ₹14`

**Expected Response:**
The agent recognizes the stock receiving intent, updates Maggi inventory by +50, updates the cost/MRP, and confirms the new stock level.
**Feature Demonstrated:** Inventory management, context understanding.

---

### Step 2: Create Multi-item Bill
**Message:**
> `make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, UPI`

**Expected Response:**
The agent identifies all 4 products, maps quantities, checks stock, computes GST correctly for each (0%, 5%, 12%), splits CGST/SGST, assigns UPI payment, and creates a Draft Bill.
**Feature Demonstrated:** Multi-item parsing, GST calculation, DB grounding (real prices).

---

### Step 3: Edit the Bill
**Message:**
> `drop the butter, make it 6 Maggi`

**Expected Response:**
The agent retrieves the active draft bill, removes the Amul Butter item, updates the Maggi quantity to 6, and returns the recalculated Draft Bill.
**Feature Demonstrated:** Multi-turn state management, bill editing.

---

### Step 4: Oversell Guard
**Message:**
> `add 500 Maggi`

**Expected Response:**
The agent refuses to add it because the quantity exceeds the available stock in the inventory, returning a clear error indicating how much is actually available.
**Feature Demonstrated:** Business rules enforced at the tool/database layer, not prompted.

---

### Step 5: Khata Cycle (Finalize on Credit)
**Message:**
> `finalize the bill and put it on Ramesh's khata`

**Expected Response:**
The agent creates/fetches customer "Ramesh", finalizes the bill, atomically deducts the stock, and records the grand total as credit against Ramesh's Khata balance.
**Feature Demonstrated:** Khata ledger management, atomic stock deduction.

**Message 2:**
> `Ramesh paid ₹300`

**Expected Response:**
The agent records a ₹300 repayment for Ramesh and shows his remaining balance.
**Feature Demonstrated:** Khata repayment handling.

---

### Step 6: Generate PDF Invoice
**Message:**
> `send me that bill as a PDF`

**Expected Response:**
The agent calls the document generator and replies with a real `.pdf` file of the invoice showing the store name, GST split, HSN codes, and exact items.
**Feature Demonstrated:** Artifact generation, context memory (knows "that bill").

---

### Step 7: Generate Analysis Deck
**Message:**
> `make today's sales analysis deck`

**Expected Response:**
The agent gathers the day's total sales, Khata credit, top items, and low stock items, and replies with a real `.pptx` file containing native PowerPoint charts (Pie, Bar).
**Feature Demonstrated:** Complex data aggregation and PPTX artifact generation.

---

### Step 8: Set Preference
**Message:**
> `always assume UPI unless I say cash. default atta = Aashirvaad 5kg`

**Expected Response:**
The agent saves these rules to persistent memory.
**Feature Demonstrated:** Persistent owner preferences.

---

### Step 9: `/new`
**Message:**
> `/new`

**Expected Response:**
The agent clears the active conversation history and active draft bill.
**Feature Demonstrated:** Session reset.

---

### Step 10: Memory Surviving `/new`
**Message:**
> `make a bill for 1 atta`

**Expected Response:**
The agent uses the saved preference from Step 8 to automatically add "Aashirvaad Atta 5kg" and assumes the payment method will be "UPI" upon finalization, proving the memory survived the reset.
**Feature Demonstrated:** Durable preferences spanning across sessions.

---

### Step 11: Natural Language Robustness
**Message:**
> `what do we have in stock?` / `do we sell facewash?` / `actually change the maggi to 10`

**Expected Response:**
The agent understands these semantic variations instead of relying on exact rigid commands like "search products" or "edit bill item". It naturally retrieves inventory or updates the bill based on intent.
**Feature Demonstrated:** Advanced LLM semantic routing and tool-mapping without a rigid intent router.

