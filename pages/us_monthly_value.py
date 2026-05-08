"""
US Stock Monthly Value Page
Displays monthly value trend for US stocks (USD)
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import os
from datetime import datetime, timedelta

# Initialize Supabase
URL = os.environ.get("SUPABASE_URL", "")
KEY = os.environ.get("SUPABASE_KEY", "")

try:
    URL = st.secrets.get("SUPABASE_URL", URL)
    KEY = st.secrets.get("SUPABASE_KEY", KEY)
except:
    pass

supabase = None
if KEY:
    try:
        from supabase import create_client
        supabase = create_client(URL, KEY)
    except:
        pass

st.set_page_config(page_title="美股每月價值", page_icon="📈")

# Check login
if 'logged_in' not in st.session_state or not st.session_state.get('logged_in'):
    st.warning("請先登入 / Please login first")
    st.switch_page("..")

st.title("📊 美股每月價值明細 / US Monthly Value")

# US stock names (common ones)
US_NAMES = {
    "AAPL": "蘋果公司", "MSFT": "微軟", "GOOGL": "谷歌", "AMZN": "亞馬遜",
    "TSLA": "特斯拉", "META": "Meta", "NVDA": "輝達", "JPM": "摩根大通",
    "V": "維薩", "JNJ": "嬌生", "WMT": "沃爾瑪", "PG": "寶潔",
    "MA": "萬事達", "UNH": "聯合健康", "HD": "家得寶", "DIS": "迪士尼",
}

def get_us_name(ticker):
    return US_NAMES.get(ticker, ticker)

def get_last_n_months(n=6):
    """Generate list of (month_end_date, month_label) for last n months"""
    months = []
    for i in range(n-1, -1, -1):
        if i == 0:
            d = datetime.now()
            month_end = d.strftime("%Y-%m-%d")
        else:
            d = datetime.now() - timedelta(days=i*30)
            if d.month == 12:
                next_month = datetime(d.year+1, 1, 1)
            else:
                next_month = datetime(d.year, d.month+1, 1)
            month_end = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
        
        month_label = d.strftime("%m月")
        months.append((month_end, month_label))
    return months

# Function to calculate US stock qty at month end
def get_us_qty_at_month(month_end_date, username):
    """Calculate US stock qty at month end from us_transactions for specific user"""
    month_qty = {}
    
    if supabase:
        try:
            # Get US transactions only (us_transactions table)
            us_tx = supabase.table('us_transactions').select('symbol,quantity,transaction_type').eq('username', username).lte('transaction_date', month_end_date).execute()
            for row in us_tx.data or []:
                sym = row['symbol']
                qty_change = row['quantity'] if row['transaction_type'] == 'BUY' else -row['quantity']
                month_qty[sym] = month_qty.get(sym, 0) + qty_change
        except:
            pass
    
    return {k: v for k, v in month_qty.items() if v > 0}

# Get months
months = get_last_n_months(6)

# Get all months qty - US only
all_month_qty = {}
for month_end, label in months:
    all_month_qty[label] = get_us_qty_at_month(month_end, st.session_state.username)

# Build rows for each US stock
allstocks = set()
for mq in all_month_qty.values():
    allstocks.update(mq.keys())

hist_rows = []
total_by_month = {}

for ticker in allstocks:
    try:
        company = get_us_name(ticker)
        row = {"股票代號": ticker, "公司名稱": company}
        
        for month_end, label in months:
            mqty = all_month_qty.get(label, {}).get(ticker, 0)
            if mqty > 0:
                try:
                    if label == months[-1][1]:  # Current month
                        stock = yf.Ticker(ticker)
                        current_price = stock.history(period="1d")['Close'].iloc[-1]
                        month_val = mqty * current_price
                    else:
                        hist = yf.Ticker(ticker).history(start="2025-01-01", end=month_end)
                        if not hist.empty:
                            month_price = hist['Close'].iloc[-1]
                            month_val = mqty * month_price
                        else:
                            month_val = 0
                    
                    row[f"{label} 數量"] = mqty
                    row[f"{label} 現值"] = round(month_val)
                except:
                    row[f"{label} 數量"] = mqty
                    row[f"{label} 現值"] = 0
            else:
                row[f"{label} 數量"] = 0
                row[f"{label} 現值"] = 0
        
        hist_rows.append(row)
        
        # Accumulate totals
        for month_end, label in months:
            total_by_month[label] = total_by_month.get(label, 0) + row.get(f"{label} 現值", 0)
            
    except:
        pass

# Display table
if hist_rows:
    st.dataframe(pd.DataFrame(hist_rows), use_container_width=True)
    
    # Portfolio Trend Chart (USD)
    chart_df = pd.DataFrame(list(total_by_month.items()), columns=["月份", "總值 (USD)"])
    fig_line = px.line(chart_df, x='月份', y='總值 (USD)', title='美股組合價值趨勢 / US Portfolio Trend', markers=True)
    
    # Convert to USD currency format
    fig_line.update_layout(yaxis={"tickprefix": "$", "tickformat": ",.0f"})
    
    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("無美股數據 / No US stock data")

# Back button
st.markdown("---")
if st.button("← 返回投資組合"):
    st.switch_page("..")