"""Plaid Link flow for Kuber.

Run as: python scripts/plaid_link.py

Starts a temporary local HTTP server, opens a Plaid Link page in the user's
browser, handles the callback, and saves the linked account data to local
CSV/JSON files. Exits when the flow completes or times out.
"""
from __future__ import annotations

import csv
import json
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

# Add scripts/ to path so sibling imports work when run as `python scripts/plaid_link.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATA_DIR, PLAID_CLIENT_ID, PLAID_ENV, PLAID_LINK_PORT, PLAID_SECRET
from plaid_client import PlaidClient

# ---------------------------------------------------------------------------
# Account type mapping (Plaid type → local type)
# ---------------------------------------------------------------------------
PLAID_ACCOUNT_TYPE_MAP: dict[str, str] = {
    "depository": "checking",
    "credit": "credit",
    "loan": "credit",
    "investment": "brokerage",
    "other": "checking",
}

# ---------------------------------------------------------------------------
# Shared state between the HTTP server and the main thread
# ---------------------------------------------------------------------------
_result: dict | None = None
_done = threading.Event()

# ---------------------------------------------------------------------------
# HTML template for the Plaid Link page
# ---------------------------------------------------------------------------
_PAGE_TEMPLATE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Connect your bank &mdash; Kuber</title>
  <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0A0A0B;
           color: #F5F4F1; display: flex; align-items: center; justify-content: center;
           height: 100vh; margin: 0; }}
    #status {{ text-align: center; font-size: 15px; }}
  </style>
</head>
<body>
  <div id="status">Opening Plaid Link&hellip;</div>
  <script>
    const handler = Plaid.create({{
      token: "{link_token}",
      onSuccess: (public_token) => {{
        document.getElementById('status').textContent = 'Connecting…';
        fetch('/callback', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ public_token }}),
        }})
          .then((r) => r.json())
          .then((r) => {{
            document.getElementById('status').textContent = r.status === 'ok'
              ? 'Connected — you can close this tab and go back to Claude.'
              : 'Something went wrong — go back to Claude and try again.';
          }})
          .catch(() => {{
            document.getElementById('status').textContent =
              'Something went wrong — go back to Claude and try again.';
          }});
      }},
      onExit: (err) => {{
        document.getElementById('status').textContent = err
          ? 'Link closed with an error — go back to Claude and try again.'
          : 'Link closed. You can close this tab.';
      }},
    }});
    handler.open();
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


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


def _append_accounts(accounts: list[dict]) -> None:
    path = DATA_DIR / "accounts.csv"
    file_exists = path.exists() and path.stat().st_size > 0
    fieldnames = [
        "id", "plaid_account_id", "institution_name", "name", "type",
        "subtype", "mask", "current_balance", "available_balance",
        "currency", "last_synced_at",
    ]
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for acct in accounts:
            writer.writerow(acct)


def _append_transactions(transactions: list[dict]) -> None:
    path = DATA_DIR / "transactions.csv"
    file_exists = path.exists() and path.stat().st_size > 0
    fieldnames = [
        "id", "plaid_transaction_id", "account_id", "date", "name",
        "merchant_name", "amount", "transaction_type", "category_id",
        "plaid_category", "needs_review",
    ]
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for txn in transactions:
            writer.writerow(txn)


def _load_category_map() -> dict[str, str]:
    """Build a plaid_primary_category -> category_id lookup from categories.csv."""
    path = DATA_DIR / "categories.csv"
    mapping: dict[str, str] = {}
    if not path.exists():
        return mapping
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            plaid_cats = row.get("plaid_categories", "")
            for pc in plaid_cats.split("|"):
                pc = pc.strip()
                if pc:
                    mapping[pc] = row["id"]
    return mapping


def _classify_transaction(
    txn: dict,
    category_map: dict[str, str],
) -> tuple[str, bool]:
    """Return (category_id, needs_review) for a Plaid transaction dict."""
    plaid_cat = txn.get("category_primary") or "OTHER"
    cat_id = category_map.get(plaid_cat, "cat-other")
    needs_review = cat_id == "cat-other" and plaid_cat not in ("OTHER", "")
    return cat_id, needs_review


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

_link_token: str = ""


async def _serve_link_page(request: Request) -> HTMLResponse:
    html = _PAGE_TEMPLATE.format(link_token=_link_token)
    return HTMLResponse(html)


async def _handle_callback(request: Request) -> JSONResponse:
    global _result
    body = await request.json()
    public_token = body.get("public_token")
    if not public_token:
        return JSONResponse({"status": "error", "error": "missing public_token"})

    try:
        plaid = PlaidClient(PLAID_CLIENT_ID, PLAID_SECRET, PLAID_ENV)
        access_token, item_id = plaid.exchange_public_token(public_token)
        now = datetime.now(timezone.utc).isoformat()

        # Save the new Plaid item
        items = _read_plaid_items()
        new_item = {
            "id": uuid.uuid4().hex,
            "item_id": item_id,
            "access_token": access_token,
            "institution_name": "",
            "transaction_cursor": None,
            "linked_at": now,
            "last_synced_at": now,
        }
        items.append(new_item)
        _save_plaid_items(items)

        # Fetch and save accounts
        plaid_accounts = plaid.get_accounts(access_token)
        plaid_account_id_to_local: dict[str, str] = {}
        local_accounts: list[dict] = []

        for pa in plaid_accounts:
            local_id = uuid.uuid4().hex
            account_type = PLAID_ACCOUNT_TYPE_MAP.get(pa["type"], "checking")
            if pa.get("subtype") == "savings":
                account_type = "savings"

            institution = pa.get("official_name") or pa["name"]
            # Update the item's institution name from the first account
            if not new_item["institution_name"]:
                new_item["institution_name"] = institution
                _save_plaid_items(items)

            local_accounts.append({
                "id": local_id,
                "plaid_account_id": pa["account_id"],
                "institution_name": institution,
                "name": pa["name"],
                "type": account_type,
                "subtype": pa.get("subtype") or "",
                "mask": pa.get("mask") or "",
                "current_balance": pa["balance_current"],
                "available_balance": pa.get("balance_available") or "",
                "currency": "USD",
                "last_synced_at": now,
            })
            plaid_account_id_to_local[pa["account_id"]] = local_id

        _append_accounts(local_accounts)

        # Initial transaction sync
        sync_result = plaid.sync_transactions(access_token)
        category_map = _load_category_map()
        local_transactions: list[dict] = []
        needs_review_count = 0

        for txn in sync_result["added"]:
            if txn.get("pending"):
                continue
            local_account_id = plaid_account_id_to_local.get(txn["account_id"])
            if not local_account_id:
                continue

            raw_amount = float(txn["amount"])
            if raw_amount < 0:
                transaction_type = "income"
                amount = str(abs(raw_amount))
            else:
                transaction_type = "expense"
                amount = str(raw_amount)

            cat_id, needs_review = _classify_transaction(txn, category_map)
            if needs_review:
                needs_review_count += 1

            local_transactions.append({
                "id": uuid.uuid4().hex,
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
            })

        _append_transactions(local_transactions)

        # Save cursor for future incremental syncs
        new_item["transaction_cursor"] = sync_result["next_cursor"]
        new_item["last_synced_at"] = now
        _save_plaid_items(items)

        _result = {
            "status": "ok",
            "institution": new_item["institution_name"],
            "accounts_linked": len(plaid_accounts),
            "transactions_synced": len(local_transactions),
            "needs_review": needs_review_count,
        }
        _done.set()
        return JSONResponse({"status": "ok", "accounts_linked": len(plaid_accounts)})

    except Exception as e:
        _result = {"status": "error", "error": str(e)}
        _done.set()
        return JSONResponse({"status": "error", "error": str(e)})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global _link_token

    if not PLAID_CLIENT_ID or not PLAID_SECRET:
        print(json.dumps({
            "status": "error",
            "error": "Missing PLAID_CLIENT_ID or PLAID_SECRET in .env. Run /setup first.",
        }))
        sys.exit(1)

    _ensure_data_dir()

    # Create link token
    plaid = PlaidClient(PLAID_CLIENT_ID, PLAID_SECRET, PLAID_ENV)
    _link_token = plaid.create_link_token("kuber-user")

    # Build and start temp server
    app = Starlette(
        routes=[
            Route("/", _serve_link_page),
            Route("/callback", _handle_callback, methods=["POST"]),
        ],
    )

    port = PLAID_LINK_PORT
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    url = f"http://localhost:{port}"
    print(json.dumps({
        "status": "waiting",
        "url": url,
        "message": f"Open {url} in your browser to connect your bank account.",
    }), flush=True)

    # Wait for callback (10 minute timeout)
    _done.wait(timeout=600)

    if _result:
        print(json.dumps(_result), flush=True)
    else:
        print(json.dumps({
            "status": "timeout",
            "error": "Timed out waiting for Plaid Link to complete.",
        }), flush=True)

    server.should_exit = True


if __name__ == "__main__":
    main()
