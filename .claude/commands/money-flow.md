Show the money flow Sankey diagram.

Steps:
1. Default to current month. Ask which period if relevant: Month, Quarter, Year
2. Read `data/transactions.csv` filtered to the selected period
3. Read `data/categories.csv` for names and colors
4. Read `data/accounts.csv` for total cash in bank
5. Compute:
   - Income sources: group income transactions by merchant_name, sum amounts
   - Total income for the period
   - Expense categories: group expense transactions by category_id, sum amounts
   - Savings: income - total expenses
   - Unallocated: any remainder
   - Summary KPIs: liquid runway (balance / monthly expense avg), kept from income %, largest outflow category
6. Read `widgets/money_flow.html` as template
7. Render via `show_widget` — follow the Sankey rules in `design/design-reference.md`:
   - Income ribbons in blue shades on the left
   - One white centre bar
   - Expense/savings ribbons on the right in semantic colors
   - Proportional ribbon heights
