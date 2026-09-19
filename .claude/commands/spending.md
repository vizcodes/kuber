Show spending by category.

Steps:
1. Default to 30 days. Options: 30d, 60d, 90d, Max
2. Read `data/transactions.csv` filtered to expense transactions in the period
3. Read `data/categories.csv` for category names and colors
4. Compute:
   - Net: income - expense for the period
   - Total income and total expense
   - Per-category spending: group by category_id, sum amounts, count transactions
   - Sort categories by amount descending
5. Read `widgets/spending.html` as template
6. Render via `show_widget` with period filter tabs, KPI cards, and horizontal bar chart
