# Kuber — Personal Finance Tracker

Kuber is a local-first personal finance tracker that runs entirely in Claude.
Data lives in CSV files under `data/`. Plaid syncs via Python scripts in
`scripts/`. Visualizations render inline in chat via `show_widget` using
templates from `widgets/`.

There is exactly one user. Never ask for or pass a user ID.

## Session start protocol

On every new session:

1. Check if `.env` exists at the project root. If not, greet the user and
   suggest they run `/setup`.
2. Check if `data/plaid_items.json` exists and has at least one entry. If
   not, suggest `/add-account`.
3. If Plaid items exist, check `last_synced_at` on the first item. If it
   was more than 1 hour ago, run `python scripts/sync.py` silently to
   refresh data.
4. Briefly report sync results only if something changed ("Synced 3
   accounts, 12 new transactions"). Don't mention the sync if nothing new.
5. If there are transactions with `needs_review=true` in
   `data/transactions.csv`, mention it: "N transactions need
   classification — want me to review them?"
6. Then respond to whatever the user actually asked.

## Data files

All under `data/` (gitignored — never committed):

| File | What it holds |
|---|---|
| `plaid_items.json` | Plaid access tokens, item IDs, cursors (sensitive) |
| `accounts.csv` | Linked bank accounts with balances |
| `transactions.csv` | All transactions with categories |
| `categories.csv` | Category definitions + Plaid mapping |
| `budgets.csv` | User-defined monthly budget limits |
| `savings_goals.csv` | Savings goals with targets |
| `merchant_rules.csv` | Learned merchant → category overrides |

## Answering questions

Read CSV files directly with the Read tool. Parse and aggregate in context.

| Question type | Read | Notes |
|---|---|---|
| Balances / accounts | `accounts.csv` | Sum `current_balance` for net worth |
| Spending breakdown | `transactions.csv` + `categories.csv` | Filter `transaction_type=expense`, group by `category_id` |
| Specific transactions | `transactions.csv` | Filter by date, merchant_name, category_id |
| Income sources | `transactions.csv` | Filter `transaction_type=income`, group by merchant_name |
| Money flow | `transactions.csv` + `categories.csv` | Income vs. expense aggregation for Sankey |
| Budgets | `budgets.csv` + `transactions.csv` | Compute current month spend per category vs. limit |
| Savings goals | `savings_goals.csv` | |
| Connect bank | — | Run `python scripts/plaid_link.py` |
| Sync data | — | Run `python scripts/sync.py` |

## Visualization rules

All visuals render via `show_widget` — **never** as published Artifacts or
sidebar content. Before building any widget:

1. Read `design/design-reference.md` for the full rule set
2. Reference `design/tokens.json` for colors/spacing/type
3. Read the matching widget template from `widgets/` as a structural starting
   point — inject computed data into the `const DATA = {}` placeholder

### Design essentials

- **Color encodes meaning, never decoration:** teal `#5DCAA5` = income/savings,
  coral `#F0997B` = expense, red `#E24B4A` = over budget only. Category colors
  from `tokens.json` `color.category`.
- **Two font weights only:** 400 and 500.
- **Currency formatting:** tabular figures, cents dimmed (lighter opacity), never
  dropped. Use the `−` (minus sign U+2212) before `$` for negative values.
- **Chart.js** from `https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.7/chart.umd.min.js`
  for bar/line charts. Custom SVG for Sankey.
- **Budget bars** cap at 100% and turn red — they never overflow.

## Transaction classification

When `sync.py` returns transactions with `needs_review=true`:

1. Read those transactions from `data/transactions.csv`
2. Group by `merchant_name` (so confirming one merchant applies to all its
   transactions)
3. Show batches of 5–10 merchants at a time with the suggested category
4. After user confirms or overrides, update `category_id` and set
   `needs_review=false` in `transactions.csv`
5. Append new merchant → category mappings to `data/merchant_rules.csv`
6. Tell the user how many merchant rules exist — "most of your transactions
   will auto-classify now"

Keep it minimal — the user should not feel fatigued classifying.

## Writing data

Claude can directly create or edit entries in:
- `data/budgets.csv` — when the user sets budget limits
- `data/savings_goals.csv` — when the user creates savings goals
- `data/transactions.csv` — category corrections, needs_review updates
- `data/merchant_rules.csv` — classification confirmations

For Plaid operations, always run the scripts in `scripts/`.

## Security

- **Never** display or log Plaid access tokens or API secrets
- **Never** commit `data/` or `.env` to git
- All Plaid API calls go through `scripts/` only — never call Plaid directly
