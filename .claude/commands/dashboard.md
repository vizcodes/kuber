Show the overview dashboard widget.

Steps:
1. Read `data/accounts.csv` for all account balances
2. Read `data/transactions.csv` for all transactions
3. Read `data/categories.csv` for category names and colors
4. Compute:
   - Net worth: sum of all `current_balance` from accounts
   - Current month income: sum of `amount` where `transaction_type=income` and date is in current month
   - Current month spending: sum of `amount` where `transaction_type=expense` and date is in current month
   - Saved this month: income - spending
   - Monthly cash flow for past 12 months: group by month, sum income and expense separately
   - Top spending categories this month: group expenses by `category_id`, join category names and colors
   - Recent activity: last 10 transactions sorted by date descending
5. Read `widgets/overview.html` as a structural template
6. Inject the computed data and render via `show_widget` following `design/design-reference.md` rules
