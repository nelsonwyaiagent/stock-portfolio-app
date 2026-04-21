# US Stock Tables Plan

## Current Problem
1. Transaction input allows market selection but may have issues
2. US stock prices not showing correctly
3. Need separate tables for US stocks

## Solution

### 1. Create US Stock Transaction Table
```sql
CREATE TABLE IF NOT EXISTS us_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username TEXT NOT NULL,
  symbol TEXT NOT NULL,
  transaction_type TEXT CHECK (transaction_type IN ('BUY', 'SELL')),
  quantity INTEGER NOT NULL,
  price_usd DECIMAL(10,2) NOT NULL,
  transaction_date DATE NOT NULL,
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### 2. Create US Stock Portfolio Table (additional column in portfolios)
-- Already have us_stocks column, can use that

### 3. Modify App
- Add separate forms for US/HK stock input
- Query correct tables for each market
- Display with proper currency
