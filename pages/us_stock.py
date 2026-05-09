"""
US Stock Portfolio Page - Full Featured
Similar to main app.py but for US stocks only (USD)
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="美股組合", page_icon="📈")

# Supabase setup
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

# US stock names
US_NAMES = {
    "AAPL": "蘋果", "MSFT": "微軟", "GOOGL": "谷歌", "AMZN": "亞馬遜",
    "TSLA": "特斯拉", "META": "Meta", "NVDA": "輝達", "JPM": "摩根大通",
    "V": "維薩", "JNJ": "嬌生", "WMT": "沃爾瑪", "PG": "寶潔",
    "MA": "萬事達", "UNH": "聯合健康", "HD": "家得寶", "DIS": "迪士尼",
    "NFLX": "Netflix", "AMD": "超微", "INTC": "英特爾", "COST": "好市多",
    "BA": "波音", "CAT": "卡特彼勒", "MMM": "3M", "GE": "GE",
    "XOM": "埃克森美孚", "CVX": "雪佛龍", "PFE": "輝瑞", "ABBV": "艾伯維",
    "KO": "可口可樂", "PEP": "百事", "MCD": "麥當勞", "NKE": "Nike",
}

EXCHANGE_RATE = 7.82  # Fallback

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        return yf.Ticker("USDHKD=X").history(period="1d")['Close'].iloc[-1]
    except:
        return 7.82

def get_us_name(ticker):
    return US_NAMES.get(ticker, ticker)

def get_last_n_months(n=6):
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

def calculate_rsi(prices, length=14):
    """Calculate RSI manually"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(window=length).mean()
    avg_loss = loss.rolling(window=length).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

@st.cache_data(ttl=3600)
def get_stock_metrics(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            'price': info.get('currentPrice'),
            'pe': info.get('trailingPE'),
            'forward_pe': info.get('forwardPE'),
            'pb_ratio': info.get('priceToBookRaw'),
            'beta': info.get('beta'),
            'dividend_yield': info.get('dividendYield'),
            'dividend_rate': info.get('dividendRate'),
            '52w_low': info.get('fiftyTwoWeekLow'),
            '52w_high': info.get('fiftyTwoWeekHigh'),
            'book_value': info.get('bookValue', 0),
        }
    except:
        return None

# Check login
if 'logged_in' not in st.session_state or not st.session_state.get('logged_in'):
    st.warning("請先登入 / Please login first in main app")
    if st.button("← 返回"):
        st.switch_page("..")
    st.stop()

st.title("🇺🇸 美股組合 / US Stock Portfolio")

# Sidebar - Add Transaction
with st.sidebar:
    st.header("➕ 添加交易 / Add Transaction")
    
    transaction_type = st.selectbox("類型", ["BUY", "SELL"])
    symbol = st.text_input("股票代號 (e.g., AAPL)", "").upper()
    
    current_price = 100.0
    if symbol:
        try:
            stock = yf.Ticker(symbol)
            current_price = stock.history(period="1d")['Close'].iloc[-1]
            st.write(f"現價: ${current_price:.2f}")
            st.write(f"公司: {get_us_name(symbol)}")
        except:
            st.warning("無法獲取價格")
    
    quantity = st.number_input("數量", min_value=1, value=10)
    price_usd = st.number_input("成交價 (USD)", min_value=0.01, value=float(current_price))
    trans_date = st.date_input("交易日期", datetime.now())
    
    if st.button("確認添加"):
        if symbol and quantity and price_usd > 0:
            try:
                supabase.table('us_transactions').insert({
                    'username': st.session_state.username,
                    'symbol': symbol,
                    'transaction_type': transaction_type,
                    'quantity': int(quantity),
                    'price_usd': float(price_usd),
                    'transaction_date': str(trans_date),
                }).execute()
                st.success("添加成功!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# Transaction History - US Stocks
st.header("📋 美股交易記錄")

if supabase:
    try:
        r_us = supabase.table('us_transactions').select('*').eq('username', st.session_state.username).execute()
        
        if r_us.data and len(r_us.data) > 0:
            tx_list = []
            for row in r_us.data:
                sym = row['symbol']
                try:
                    current_price = yf.Ticker(sym).history(period="1d")['Close'].iloc[-1]
                except:
                    current_price = None
                
                pl_ratio = None
                price_usd = row['price_usd']
                if row['transaction_type'] == 'BUY' and current_price:
                    pl_ratio = ((current_price - price_usd) / price_usd) * 100
                
                current_value = current_price * row['quantity'] if current_price else None
                
                tx_list.append({
                    'id': row['id'],
                    '股票代號': sym,
                    '公司': get_us_name(sym),
                    '類型': row['transaction_type'],
                    '數量': row['quantity'],
                    '成交價': price_usd,
                    '成交總額': row['quantity'] * price_usd,
                    '交易日期': row['transaction_date'],
                    '現價': current_price,
                    '現值': current_value,
                    '盈虧比率': pl_ratio,
                })
            
            df_tx = pd.DataFrame(tx_list)
            st.dataframe(df_tx, use_container_width=True)
        else:
            st.info("暫無美股交易記錄!")
    except Exception as e:
        st.error(f"Error: {e}")

# Holdings calculation
holdings = {}
us_total_val, us_total_cost = 0, 0

if supabase:
    try:
        r_us = supabase.table('us_transactions').select('*').eq('username', st.session_state.username).execute()
        
        if r_us.data:
            for row in r_us.data:
                sym = row['symbol']
                qty = row['quantity']
                price_usd = row['price_usd']
                
                if sym not in holdings:
                    holdings[sym] = {'qty': 0, 'total_buy': 0, 'total_buy_qty': 0}
                
                if row['transaction_type'] == 'BUY':
                    holdings[sym]['total_buy'] += qty * price_usd
                    holdings[sym]['total_buy_qty'] += qty
                    holdings[sym]['qty'] += qty
                else:
                    holdings[sym]['qty'] -= qty
    except Exception as e:
        st.error(f"Error: {e}")

# Calculate values
display_holdings = {k: v for k, v in holdings.items() if v['qty'] > 0}

for sym, d in display_holdings.items():
    try:
        current_price = yf.Ticker(sym).history(period="1d")['Close'].iloc[-1]
        d['current_price'] = current_price
        d['current_value'] = d['qty'] * current_price
        d['avg_cost'] = d['total_buy'] / d['total_buy_qty'] if d['total_buy_qty'] > 0 else 0
        d['pnl'] = d['current_value'] - (d['qty'] * d['avg_cost'])
        d['pnl_pct'] = (d['pnl'] / (d['qty'] * d['avg_cost']) * 100) if d['avg_cost'] > 0 else 0
        us_total_val += d['current_value']
        us_total_cost += d['qty'] * d['avg_cost']
    except:
        pass

# Summary Cards
st.subheader("📊 組合概要 / Portfolio Summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("總值", f"${us_total_val:,.0f}")
c2.metric("總成本", f"${us_total_cost:,.0f}")
c3.metric("總盈虧", f"${us_total_val - us_total_cost:,.0f}", f"{((us_total_val - us_total_cost) / us_total_cost * 100) if us_total_cost > 0 else 0:.1f}%")
c4.metric("持股數", len(display_holdings))

# Holdings Table
st.subheader("📊 Holdings Detail")
if display_holdings:
    rows = []
    for ticker, d in display_holdings.items():
        try:
            # RSI
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")['Close']
            rsi = calculate_rsi(hist).iloc[-1]
            
            if rsi < 30:
                signal = "🟢 買"
            elif rsi > 70:
                signal = "🔴 強賣"
            elif rsi > 60:
                signal = "🟡 留意"
            else:
                signal = "🟡 持有"
            
            # Dividend
            expected_div = 0
            div_yield = None
            try:
                m = get_stock_metrics(ticker)
                if m:
                    fd = m.get("dividend_rate", 0)
                    if fd:
                        expected_div = d['qty'] * fd
                    div_yield = m.get("dividend_yield")
            except:
                pass
            
            rows.append({
                "股票代號": ticker,
                "公司": get_us_name(ticker),
                "數量": d['qty'],
                "成本": f"${d['avg_cost']:.2f}",
                "現值": f"${d['current_value']:.2f}",
                "盈虧": f"${d['pnl']:.2f}",
                "%": f"{d['pnl_pct']:.1f}%",
                "股息率": f"{div_yield:.2f}%" if div_yield else "-",
                "預期股息": f"${expected_div:.2f}" if expected_div else "-",
                "RSI": f"{rsi:.0f}",
                "信號": signal,
            })
        except:
            pass
    
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
else:
    st.info("無美股數據")

# Charts
if display_holdings:
    st.write("---")
    
    # Pie Chart
    chart_data = [{"股票代號": k, "現值": v['current_value']} for k, v in display_holdings.items()]
    fig_pie = px.pie(chart_data, values='現值', names='股票代號', title='組合分配 / Portfolio Allocation', hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)
    
    # P&L Bar Chart
    pnl_data = [{"股票代號": k, "盈虧": v['pnl'], "%": v['pnl_pct']} for k, v in display_holdings.items()]
    fig_bar = px.bar(pnl_data, x='股票代號', y='盈虧', title='損益 / P&L', color='盈虧',
                   color_continuous_scale=['red', 'gray', 'green'])
    fig_bar.add_hline(y=0)
    st.plotly_chart(fig_bar, use_container_width=True)
    
    # P&L % Chart
    fig_pct = px.bar(pnl_data, x='股票代號', y='%', title='各股票盈虧 / P&L by Stock (%)',
                     color='%', color_continuous_scale=['red', 'gray', 'green'])
    fig_pct.add_hline(y=-10, line_dash="dash", line_color="orange", annotation_text="Loss 10%")
    fig_pct.add_hline(y=-15, line_dash="dot", line_color="red", annotation_text="Loss 15%")
    fig_pct.add_hline(y=10, line_dash="dash", line_color="lightgreen", annotation_text="Gain 10%")
    fig_pct.add_hline(y=20, line_dash="dot", line_color="green", annotation_text="Gain 20%")
    st.plotly_chart(fig_pct, use_container_width=True)

# US Stock Industry mapping
US_INDUSTRY = {
    "AAPL": "TECH", "MSFT": "TECH", "GOOGL": "TECH", "AMZN": "CONS",
    "TSLA": "AUTO", "META": "TECH", "NVDA": "TECH", "JPM": "FIN",
    "V": "FIN", "JNJ": "HLTH", "WMT": "CONS", "PG": "CONS",
    "MA": "FIN", "UNH": "HLTH", "HD": "CONS", "DIS": "MEDIA",
    "NFLX": "MEDIA", "AMD": "TECH", "INTC": "TECH", "COST": "CONS",
    "BA": "INDU", "CAT": "INDU", "MMM": "INDU", "GE": "INDU",
    "XOM": "ENERGY", "CVX": "ENERGY", "PFE": "HLTH", "ABBV": "HLTH",
    "KO": "CONS", "PEP": "CONS", "MCD": "CONS", "NKE": "CONS",
}

def get_us_industry(ticker):
    return US_INDUSTRY.get(ticker, "OTHER")

# Industry Allocation Chart
if display_holdings:
    st.write("---")
    industry_data = []
    for ticker, d in display_holdings.items():
        ind = get_us_industry(ticker)
        industry_data.append({"行業": ind, "現值": d['current_value']})
    
    industry_df = pd.DataFrame(industry_data)
    if len(industry_df) > 0:
        industry_agg = industry_df.groupby('行業')['現值'].sum().reset_index()
        fig_ind = px.pie(industry_agg, values='現值', names='行業', title='行業分布 / Industry Allocation', hole=0.4)
        st.plotly_chart(fig_ind, use_container_width=True)

# Stock Analysis
st.write("---")
st.subheader("📈 股票分析 / Stock Analysis")

# Get ALL US stock symbols from transactions (not just current holdings)
all_us_symbols = set()
if supabase:
    try:
        r_us = supabase.table('us_transactions').select('symbol').eq('username', st.session_state.username).execute()
        for row in r_us.data or []:
            all_us_symbols.add(row['symbol'])
    except:
        pass

if all_us_symbols:
    analysis_rows = []
    for ticker in all_us_symbols:
        try:
            m = get_stock_metrics(ticker)
            if m:
                vol = 0
                if m.get('52w_low') and m.get('52w_high') and m['52w_low'] > 0:
                    vol = ((m['52w_high'] - m['52w_low']) / m['52w_low']) * 100
                
                analysis_rows.append({
                    '股票代號': ticker,
                    '公司': get_us_name(ticker),
                    '股價': m.get('price'),
                    'P/E': m.get('pe'),
                    '預測P/E': m.get('forward_pe'),
                    '市帳率': m.get('pb_ratio'),
                    '52W低': m.get('52w_low'),
                    '52W高': m.get('52w_high'),
                    '波幅%': vol,
                    'Beta': m.get('beta'),
                    '股息%': m.get('dividend_yield'),
                    '遠期股息': m.get('dividend_rate'),
                    '帳面值': m.get('book_value'),
                })
        except:
            pass
    
    if analysis_rows:
        st.dataframe(pd.DataFrame(analysis_rows), use_container_width=True)
else:
    st.info("無美股數據")

# Monthly Value
st.write("---")
st.subheader("📊 每月價值明細 / Monthly Value")

months = get_last_n_months(6)

def get_us_qty_at_month(month_end_date, username):
    month_qty = {}
    if supabase:
        try:
            us_tx = supabase.table('us_transactions').select('symbol,quantity,transaction_type').eq('username', username).lte('transaction_date', month_end_date).execute()
            for row in us_tx.data or []:
                sym = row['symbol']
                qty_change = row['quantity'] if row['transaction_type'] == 'BUY' else -row['quantity']
                month_qty[sym] = month_qty.get(sym, 0) + qty_change
        except:
            pass
    return {k: v for k, v in month_qty.items() if v > 0}

all_month_qty = {}
for month_end, label in months:
    all_month_qty[label] = get_us_qty_at_month(month_end, st.session_state.username)

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
                    if label == months[-1][1]:
                        current_price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
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
        
        for month_end, label in months:
            total_by_month[label] = total_by_month.get(label, 0) + row.get(f"{label} 現值", 0)
    except:
        pass

if hist_rows:
    st.dataframe(pd.DataFrame(hist_rows), use_container_width=True)
    
    chart_df = pd.DataFrame(list(total_by_month.items()), columns=["月份", "總值 (USD)"])
    fig_line = px.line(chart_df, x='月份', y='總值 (USD)', title='組合價值趨勢 / Portfolio Trend', markers=True)
    fig_line.update_layout(yaxis={"tickprefix": "$"})
    st.plotly_chart(fig_line, use_container_width=True)

# Back button
st.markdown("---")
if st.button("← 返回投資組合"):
    st.switch_page("..")