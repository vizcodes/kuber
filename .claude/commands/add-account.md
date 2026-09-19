Link a new bank account via Plaid.

Steps:
1. Verify `.env` exists — if not, tell me to run `/setup` first
2. Run: `python scripts/plaid_link.py`
3. Read the first JSON line from stdout — it will have a `url` field
4. Tell me to open that URL in my browser to connect my bank account
5. Wait for the script to complete (it prints a second JSON line when done)
6. Read the result: report which institution was connected, how many accounts were linked, and how many transactions were synced
7. If `needs_review` count is > 0, offer to start the transaction classification flow (read CLAUDE.md "Transaction classification" section)
