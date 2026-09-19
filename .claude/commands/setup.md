First-time setup for Kuber. Configure Plaid credentials and seed the data directory.

Steps:
1. Check if `.env` already exists in the project root
2. If it exists, tell me it's already configured and ask if I want to reconfigure
3. If not, ask me for:
   - PLAID_CLIENT_ID (from https://dashboard.plaid.com/developers/keys)
   - PLAID_SECRET (Production secret)
4. Write `.env` to the project root with:
   ```
   PLAID_CLIENT_ID=<their value>
   PLAID_SECRET=<their value>
   PLAID_ENV=production
   ```
5. Create the `data/` directory if it doesn't exist
6. Seed `data/categories.csv` with the default 19 categories (read the seed data below)
7. Create `data/merchant_rules.csv` with just the header: `merchant_pattern,category_id`
8. Create `data/budgets.csv` with header: `id,category_id,monthly_limit,created_at`
9. Create `data/savings_goals.csv` with header: `id,name,icon,color,target_amount,current_amount,target_date,created_at`
10. Install Python dependencies: `pip install -r requirements.txt`
11. Confirm setup is complete and suggest `/add-account` to link a bank

Default categories to seed:
```csv
id,name,icon,color,is_income,plaid_categories
cat-housing,Housing,home,#AFA9EC,false,RENT_AND_UTILITIES|HOME_IMPROVEMENT
cat-food,Food & Dining,store,#F0997B,false,FOOD_AND_DRINK
cat-transport,Transport,car,#85B7EB,false,TRANSPORTATION
cat-leisure,Leisure,music,#5DCAA5,false,ENTERTAINMENT
cat-shopping,Shopping,cart,#EF9F27,false,GENERAL_MERCHANDISE
cat-health,Health,umbrella,#E24B4A,false,PERSONAL_CARE|MEDICAL
cat-education,Education,book,#378ADD,false,EDUCATION
cat-travel,Travel,plane,#85B7EB,false,TRAVEL
cat-loans,Loans & Debt,card,#AFA9EC,false,LOAN_PAYMENTS
cat-fees,Bank Fees,bank,#8C8C87,false,BANK_FEES
cat-services,Services,tag,#6E6E6A,false,GENERAL_SERVICES
cat-government,Government & Tax,briefcase,#8C8C87,false,GOVERNMENT_AND_NON_PROFIT
cat-utilities,Utilities,wifi,#8C8C87,false,
cat-salary,Salary,briefcase,#85B7EB,true,INCOME
cat-freelance,Freelance,code,#378ADD,true,
cat-dividends,Dividends,chart,#B5D4F4,true,
cat-income-other,Other Income,wallet,#5DCAA5,true,
cat-transfer,Transfer,exchange,#8C8C87,false,TRANSFER_IN|TRANSFER_OUT
cat-other,Other,dots,#8C8C87,false,OTHER
```
