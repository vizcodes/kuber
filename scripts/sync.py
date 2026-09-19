"""Kuber incremental sync — pulls new transactions from Plaid into local CSVs.

Run as: python scripts/sync.py

Reads plaid_items.json for access tokens and cursors, calls Plaid's
transactions/sync endpoint, and updates transactions.csv + accounts.csv.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATA_DIR, PLAID_CLIENT_ID, PLAID_ENV, PLAID_SECRET
from plaid_client import PlaidClient


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _read_csv(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(filename: str, rows: list[dict], fieldnames: list[str]) -> None:
    path = DATA_DIR / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _read_plaid_items() -> list[dict]:
    path = DATA_DIR / "plaid_items.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_plaid_items(items: list[dict]) -> None:
    path = DATA_DIR / "plaid_items.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


def _load_category_map() -> dict[str, str]:
    """Build plaid_primary_category -> category_id from categories.csv."""
    rows = _read_csv("categories.csv")
    mapping: dict[str, str] = {}
    for row in rows:
        for pc in row.get("plaid_categories", "").split("|"):
            pc = pc.strip()
            if pc:
                mapping[pc] = row["id"]
    return mapping


def _load_merchant_rules() -> dict[str, str]:
    """Build lowercased merchant_pattern -> category_id from merchant_rules.csv."""
    rows = _read_csv("merchant_rules.csv")
    return {r["merchant_pattern"].lower(): r["category_id"] for r in rows if r.get("merchant_pattern")}


TRANSACTION_FIELDS = [
    "id", "plaid_transaction_id", "account_id", "date", "name",
    "merchant_name", "amount", "transaction_type", "category_id",
    "plaid_category", "needs_review",
]

ACCOUNT_FIELDS = [
    "id", "plaid_account_id", "institution_name", "name", "type",
    "subtype", "mask", "current_balance", "available_balance",
    "currency", "last_synced_at",
]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify(
    txn: dict,
    category_map: dict[str, str],
    merchant_rules: dict[str, str],
) -> tuple[str, bool]:
    """Return (category_id, needs_review). Merchant rules override Plaid mapping."""
    merchant = (txn.get("merchant_name") or txn.get("name") or "").lower()

    # Check merchant rules first (user-confirmed overrides)
    for pattern, cat_id in merchant_rules.items():
        if pattern in merchant:
            return cat_id, False

    # Fall back to Plaid category mapping
    plaid_cat = txn.get("category_primary") or "OTHER"
    cat_id = category_map.get(plaid_cat, "cat-other")
    needs_review = cat_id == "cat-other" and plaid_cat not in ("OTHER", "")
    return cat_id, needs_review


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------

def sync_item(
    plaid_client: PlaidClient,
    item: dict,
    existing_transactions: list[dict],
    accounts: list[dict],
    category_map: dict[str, str],
    merchant_rules: dict[str, str],
) -> dict:
    """Sync one Plaid item. Mutates existing_transactions and accounts in place.
    Returns a summary dict."""
    access_token = item["access_token"]
    cursor = item.get("transaction_cursor")

    # Build plaid_account_id -> local_id mapping
    plaid_to_local = {
        a["plaid_account_id"]: a["id"]
        for a in accounts
        if a.get("plaid_account_id")
    }

    # Build plaid_transaction_id -> index for fast lookup
    txn_index = {
        t["plaid_transaction_id"]: i
        for i, t in enumerate(existing_transactions)
        if t.get("plaid_transaction_id")
    }

    try:
        sync_result = plaid_client.sync_transactions(access_token, cursor)
    except Exception as e:
        return {"item_id": item.get("item_id", ""), "error": str(e), "added": 0, "modified": 0, "removed": 0}

    now = datetime.now(timezone.utc).isoformat()
    added_count = 0
    modified_count = 0
    removed_count = 0
    needs_review_count = 0

    # Process added transactions
    for txn in sync_result["added"]:
        if txn.get("pending"):
            continue
        local_account_id = plaid_to_local.get(txn["account_id"])
        if not local_account_id:
            continue

        raw_amount = float(txn["amount"])
        transaction_type = "income" if raw_amount < 0 else "expense"
        amount = str(abs(raw_amount))

        cat_id, needs_review = _classify(txn, category_map, merchant_rules)
        if needs_review:
            needs_review_count += 1

        new_row = {
            "id": uuid4().hex,
            "plaid_transaction_id": txn["transaction_id"],
            "account_id": local_account_id,
            "date": txn["date"],
            "name": txn.get("name") or "",
            "merchant_name": txn.get("merchant_name") or txn.get("name") or "",
            "amount": amount,
            "transaction_type": transaction_type,
            "category_id": cat_id,
            "plaid_category": txn.get("category_primary") or "",
            "needs_review": str(needs_review).lower(),
        }
        existing_transactions.append(new_row)
        added_count += 1

    # Process modified transactions
    for txn in sync_result["modified"]:
        if txn.get("pending"):
            continue
        idx = txn_index.get(txn["transaction_id"])
        if idx is None:
            continue

        raw_amount = float(txn["amount"])
        transaction_type = "income" if raw_amount < 0 else "expense"
        amount = str(abs(raw_amount))
        cat_id, needs_review = _classify(txn, category_map, merchant_rules)

        row = existing_transactions[idx]
        row["date"] = txn["date"]
        row["name"] = txn.get("name") or ""
        row["merchant_name"] = txn.get("merchant_name") or txn.get("name") or ""
        row["amount"] = amount
        row["transaction_type"] = transaction_type
        row["category_id"] = cat_id
        row["plaid_category"] = txn.get("category_primary") or ""
        row["needs_review"] = str(needs_review).lower()
        modified_count += 1

    # Process removed transactions
    removed_ids = {r["transaction_id"] for r in sync_result["removed"]}
    if removed_ids:
        before = len(existing_transactions)
        existing_transactions[:] = [
            t for t in existing_transactions
            if t.get("plaid_transaction_id") not in removed_ids
        ]
        removed_count = before - len(existing_transactions)

    # Update cursor
    item["transaction_cursor"] = sync_result["next_cursor"]
    item["last_synced_at"] = now

    # Update account balances
    try:
        plaid_accounts = plaid_client.get_accounts(access_token)
        for pa in plaid_accounts:
            local_id = plaid_to_local.get(pa["account_id"])
            if local_id:
                for acct in accounts:
                    if acct["id"] == local_id:
                        acct["current_balance"] = pa["balance_current"]
                        acct["available_balance"] = pa.get("balance_available") or ""
                        acct["last_synced_at"] = now
                        break
    except Exception:
        pass  # Balance fetch is best-effort

    return {
        "item_id": item.get("item_id", ""),
        "institution": item.get("institution_name", ""),
        "added": added_count,
        "modified": modified_count,
        "removed": removed_count,
        "needs_review": needs_review_count,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not PLAID_CLIENT_ID or not PLAID_SECRET:
        print(json.dumps({
            "status": "error",
            "error": "Missing PLAID_CLIENT_ID or PLAID_SECRET in .env.",
        }))
        sys.exit(1)

    items = _read_plaid_items()
    if not items:
        print(json.dumps({
            "status": "no_items",
            "message": "No linked accounts. Run /add-account first.",
        }))
        return

    plaid_client = PlaidClient(PLAID_CLIENT_ID, PLAID_SECRET, PLAID_ENV)
    existing_transactions = _read_csv("transactions.csv")
    accounts = _read_csv("accounts.csv")
    category_map = _load_category_map()
    merchant_rules = _load_merchant_rules()

    results = []
    for item in items:
        summary = sync_item(
            plaid_client, item, existing_transactions, accounts,
            category_map, merchant_rules,
        )
        results.append(summary)

    # Write back all changes
    _save_plaid_items(items)
    if existing_transactions:
        _write_csv("transactions.csv", existing_transactions, TRANSACTION_FIELDS)
    if accounts:
        _write_csv("accounts.csv", accounts, ACCOUNT_FIELDS)

    total_added = sum(r["added"] for r in results)
    total_modified = sum(r["modified"] for r in results)
    total_removed = sum(r["removed"] for r in results)
    total_review = sum(r.get("needs_review", 0) for r in results)

    print(json.dumps({
        "status": "ok",
        "accounts_synced": len(items),
        "added": total_added,
        "modified": total_modified,
        "removed": total_removed,
        "needs_review": total_review,
        "details": results,
    }))


if __name__ == "__main__":
    main()
