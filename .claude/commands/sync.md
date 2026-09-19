Manually refresh data from Plaid.

Steps:
1. Run: `python scripts/sync.py`
2. Read the JSON output
3. Report: "Synced N account(s) — M added, X modified, Y removed transactions"
4. If `needs_review` count is > 0, offer to classify the new transactions
