Show budget progress and savings goals.

Steps:
1. Read `data/budgets.csv` for budget limits per category
2. Read `data/transactions.csv` for current month spending per category
3. Read `data/categories.csv` for category names and colors
4. Read `data/savings_goals.csv` for goals
5. Compute per budget:
   - Amount spent this month (sum expenses matching the budget's category_id)
   - Percent used: spent / monthly_limit
   - Over budget: percent_used > 1.0
6. Read `widgets/budgets.html` as template
7. Render via `show_widget`:
   - Progress bars capped at 100% visually, turn red (#E24B4A) when over budget
   - Show warning for over-budget categories
   - Savings goals section with teal progress bars (no over state)
