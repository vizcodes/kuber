Show the transaction list.

Steps:
1. Ask for any filters: date range, category, search term, account — or show all recent
2. Read `data/transactions.csv`
3. Read `data/categories.csv` for category names and colors
4. Read `data/accounts.csv` for account names
5. Apply any filters the user requested
6. Read `widgets/transactions.html` as template
7. Render via `show_widget` with:
   - Interactive search box and category/date filter controls
   - Each row: date, merchant name, category (with color dot), amount (teal for income, coral for expense)
   - Dimmed cents, tabular figures
