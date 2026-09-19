"""Unified Plaid API wrapper for Kuber.

Handles link-token creation, token exchange, account fetching,
incremental transaction sync, and investment holdings.
"""
from __future__ import annotations

import plaid
from plaid.api import plaid_api
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.link_token_transactions import LinkTokenTransactions
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest


class PlaidClient:
    """Plaid SDK wrapper that accepts credentials as constructor params."""

    def __init__(self, client_id: str, secret: str, env: str = "production") -> None:
        if env != "production":
            raise ValueError(
                "Kuber only supports Plaid Production. "
                "Set PLAID_ENV=production in your .env file."
            )
        configuration = plaid.Configuration(
            host=plaid.Environment.Production,
            api_key={"clientId": client_id, "secret": secret},
        )
        api_client = plaid.ApiClient(configuration)
        self.client = plaid_api.PlaidApi(api_client)

    def create_link_token(self, user_id: str) -> str:
        """Create a Plaid Link token for the hosted link page."""
        request = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id=user_id),
            client_name="Kuber",
            # Only transactions is required; investments is optional so banks
            # without it (e.g. Bank of America) still show up in Link.
            products=[Products("transactions")],
            optional_products=[Products("investments")],
            country_codes=[CountryCode("US")],
            language="en",
            # Pull as much history as the institution allows (up to 2 years).
            transactions=LinkTokenTransactions(days_requested=730),
        )
        response = self.client.link_token_create(request)
        return response["link_token"]

    def exchange_public_token(self, public_token: str) -> tuple[str, str]:
        """Exchange a public token from Plaid Link for an access_token and item_id."""
        request = ItemPublicTokenExchangeRequest(public_token=public_token)
        response = self.client.item_public_token_exchange(request)
        return response["access_token"], response["item_id"]

    def get_accounts(self, access_token: str) -> list[dict]:
        """Fetch account details (metadata + balances) from Plaid."""
        request = AccountsGetRequest(access_token=access_token)
        response = self.client.accounts_get(request)
        accounts = []
        for acct in response["accounts"]:
            accounts.append({
                "account_id": acct["account_id"],
                "name": acct["name"],
                "official_name": acct.get("official_name"),
                "type": str(acct["type"]),
                "subtype": str(acct["subtype"]) if acct.get("subtype") else None,
                "mask": acct.get("mask"),
                "balance_current": (
                    str(acct["balances"]["current"])
                    if acct["balances"].get("current") is not None
                    else "0"
                ),
                "balance_available": (
                    str(acct["balances"]["available"])
                    if acct["balances"].get("available") is not None
                    else None
                ),
            })
        return accounts

    def sync_transactions(self, access_token: str, cursor: str | None = None) -> dict:
        """Incrementally fetch new/modified/removed transactions via transactions/sync.

        Pages through all available updates before returning.
        """
        added: list[dict] = []
        modified: list[dict] = []
        removed: list[dict] = []
        has_more = True
        next_cursor = cursor or ""

        while has_more:
            request = TransactionsSyncRequest(
                access_token=access_token,
                cursor=next_cursor,
            )
            response = self.client.transactions_sync(request)

            for txn in response["added"]:
                added.append(self._serialize_transaction(txn))
            for txn in response["modified"]:
                modified.append(self._serialize_transaction(txn))
            for txn in response["removed"]:
                removed.append({"transaction_id": txn["transaction_id"]})

            has_more = response["has_more"]
            next_cursor = response["next_cursor"]

        return {
            "added": added,
            "modified": modified,
            "removed": removed,
            "next_cursor": next_cursor,
        }

    def get_investment_holdings(self, access_token: str) -> dict:
        """Fetch investment holdings and securities from Plaid."""
        request = InvestmentsHoldingsGetRequest(access_token=access_token)
        try:
            response = self.client.investments_holdings_get(request)
        except plaid.ApiException:
            # Not all items support investments — return empty if unavailable.
            return {"holdings": [], "securities": []}

        securities_map = {}
        for sec in response.get("securities", []):
            securities_map[sec["security_id"]] = {
                "security_id": sec["security_id"],
                "name": sec.get("name"),
                "ticker_symbol": sec.get("ticker_symbol"),
                "type": sec.get("type"),
                "close_price": str(sec["close_price"]) if sec.get("close_price") is not None else None,
            }

        holdings = []
        for h in response.get("holdings", []):
            holdings.append({
                "account_id": h["account_id"],
                "security_id": h["security_id"],
                "quantity": str(h["quantity"]),
                "institution_value": str(h["institution_value"]) if h.get("institution_value") is not None else "0",
                "cost_basis": str(h.get("cost_basis")) if h.get("cost_basis") is not None else None,
                "security": securities_map.get(h["security_id"], {}),
            })

        return {"holdings": holdings, "securities": list(securities_map.values())}

    @staticmethod
    def _serialize_transaction(txn: dict) -> dict:
        """Convert a raw Plaid transaction object into a flat dict."""
        category_primary = None
        category_detailed = None
        pfc = txn.get("personal_finance_category")
        if pfc:
            category_primary = pfc.get("primary")
            category_detailed = pfc.get("detailed")

        return {
            "transaction_id": txn["transaction_id"],
            "account_id": txn["account_id"],
            "amount": txn["amount"],
            "name": txn.get("name"),
            "merchant_name": txn.get("merchant_name"),
            "date": str(txn["date"]),
            "pending": txn.get("pending", False),
            "category_primary": category_primary,
            "category_detailed": category_detailed,
        }
