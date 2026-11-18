"""
US Stock Portfolio Page - Full Featured
Similar to main app.py but for US stocks only (USD)
"""
import streamlit as st

st.set_page_config(page_title="美股組合", page_icon="📈", layout="wide")

import yfinance as yf
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from portfolio_display import build_pnl_chart_frame, rsi_signal_labels
from portfolio_dividends import apply_ytd, hong_kong_today
from portfolio_ui import (
    collect_dividend_report,
    format_money,
    render_balance,
    render_compact_holdings,
    render_contributors,
    render_dividend_income,
    render_dividend_leaders,
    render_metric_tiles,
    security_profile,
    ytd_metric,
)

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

EXCHANGE_RATE = 7.82  # Fallback

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        return yf.Ticker("USDHKD=X").history(period="1d")['Close'].iloc[-1]
    except:
        return 7.82

def get_us_name(ticker):
    return security_profile(ticker)["name"]

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
        st.switch_page("app.py")
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
                    '股票代號': sym,
                    '公司': get_us_name(sym),
                    '類型': row['transaction_type'],
                    '數量': row['quantity'],
                    '成交價': price_usd,
                    '成交總額': row['quantity'] * price_usd,
                    '交易日期': row['transaction_date'],
                    '現價': current_price,
                    '現值': current_value,
                    'Gain/Loss %': pl_ratio,
                })
            
            df_tx = pd.DataFrame(tx_list)
            st.dataframe(df_tx, use_container_width=True)
        else:
            st.info("暫無美股交易記錄!")
    except Exception as e:
        st.error(f"Error: {e}")

# Holdings calculation. The dated ledger is only used for dividend entitlement.
holdings = {}
us_total_val, us_total_cost = 0, 0
ledger = []

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
                ledger.append({
                    "symbol": sym,
                    "transaction_type": row["transaction_type"],
                    "quantity": qty,
                    "transaction_date": row["transaction_date"],
                })
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

ui_rows = []
for ticker, d in display_holdings.items():
    if "pnl" not in d or "current_value" not in d:
        continue
    profile = security_profile(ticker)
    ui_rows.append({
        "ticker": ticker,
        "name": profile["name"],
        "market": "US",
        "industry_code": profile["industry_code"],
        "industry_label": profile["industry_label"],
        "cost_total": d["qty"] * d["avg_cost"],
        "market_value": d["current_value"],
        "pnl": d["pnl"],
        "pnl_pct": d["pnl_pct"],
    })

dividend_names = {row["ticker"]: row["name"] for row in ui_rows}
for tx in ledger:
    sym = str(tx.get("symbol") or "").strip().upper()
    if sym and sym not in dividend_names:
        dividend_names[sym] = security_profile(sym)["name"]
if ledger:
    with st.spinner("正在估算今年股息…"):
        dividend_report = collect_dividend_report(
            ledger,
            dividend_names,
            today=hong_kong_today(),
            default_currency="USD",
            report_currency="USD",
            spot_fx=EXCHANGE_RATE,
        )
else:
    dividend_report = collect_dividend_report(
        ledger,
        dividend_names,
        today=hong_kong_today(),
        default_currency="USD",
        report_currency="USD",
        spot_fx=EXCHANGE_RATE,
    )
apply_ytd(ui_rows, dividend_report)

# Summary. Figures stay in USD; the cost basis above is unchanged.
st.subheader("📊 組合概要 / Portfolio Summary")
us_pnl = us_total_val - us_total_cost
us_pnl_pct = (us_pnl / us_total_cost * 100) if us_total_cost > 0 else 0
pnl_tone = "neg" if us_pnl < 0 else "pos" if us_pnl > 0 else "neutral"
render_metric_tiles([
    {"label": "總值 / Total Value", "value": format_money(us_total_val, "USD"), "sub": "美元 / USD"},
    {"label": "總成本 / Total Cost", "value": format_money(us_total_cost, "USD"), "sub": "美元 / USD"},
    {
        "label": "總盈虧 / Total P&L",
        "value": format_money(us_pnl, "USD", signed=True),
        "sub": f"{us_pnl_pct:+.1f}%",
        "tone": pnl_tone,
    },
    ytd_metric(dividend_report.get("total_ytd"), "USD"),
    {"label": "持股數 / Holdings", "value": str(len(ui_rows)), "sub": "美股 / US stocks"},
])
if ui_rows:
    render_contributors(ui_rows, currency="USD")
if ui_rows or dividend_report.get("rows"):
    render_dividend_leaders(dividend_report, ui_rows, currency="USD")
if ui_rows:
    render_balance(ui_rows, us_total_val, currency="USD")

st.subheader("📊 持股明細 / Holdings Detail")
render_compact_holdings(
    ui_rows,
    us_total_val,
    currency="USD",
    sort_key="us_page_holdings_sort",
    empty_message="無美股數據 / No US holdings",
)
if ui_rows or dividend_report.get("rows"):
    render_dividend_income(dividend_report, currency="USD")

# Charts
if ui_rows:
    st.write("---")
    chart_data = [
        {
            "名稱": row["name"] if row["name"] != row["ticker"] else row["ticker"],
            "現值": row["market_value"],
        }
        for row in ui_rows
    ]
    fig_pie = px.pie(chart_data, values="現值", names="名稱", title="組合分配 / Portfolio Allocation", hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)

    chart = build_pnl_chart_frame(ui_rows, currency="USD")
    fig_bar = px.bar(
        chart,
        x="標籤",
        y="盈虧",
        title="損益 / P&L",
        color="盈虧",
        color_continuous_scale=["red", "gray", "green"],
    )
    fig_bar.update_traces(
        text=[f"USD {x:,.0f}" if pd.notna(x) else "USD 0" for x in chart["盈虧"]],
        textposition="outside",
        customdata=chart["hover"],
        hovertemplate="%{customdata}<extra></extra>",
    )
    fig_bar.update_layout(xaxis_title="公司 / Company", xaxis=dict(automargin=True))
    fig_bar.add_hline(y=0)
    st.plotly_chart(fig_bar, use_container_width=True)

    fig_pct = px.bar(
        chart,
        x="標籤",
        y="盈虧%",
        title="各股票盈虧 / P&L by Stock (%)",
        color="盈虧%",
        color_continuous_scale=["red", "gray", "green"],
    )
    fig_pct.update_traces(
        text=[f"{x:.1f}%" if pd.notna(x) else "0%" for x in chart["盈虧%"]],
        textposition="outside",
        customdata=chart["hover"],
        hovertemplate="%{customdata}<extra></extra>",
    )
    fig_pct.update_layout(xaxis_title="公司 / Company", xaxis=dict(automargin=True))
    fig_pct.add_hline(y=-10, line_dash="dash", line_color="orange", annotation_text="Loss 10%")
    fig_pct.add_hline(y=-15, line_dash="dot", line_color="red", annotation_text="Loss 15%")
    fig_pct.add_hline(y=10, line_dash="dash", line_color="lightgreen", annotation_text="Gain 10%")
    fig_pct.add_hline(y=20, line_dash="dot", line_color="green", annotation_text="Gain 20%")
    st.plotly_chart(fig_pct, use_container_width=True)

    st.write("---")
    industry_data = [{"行業": row["industry_label"], "現值": row["market_value"]} for row in ui_rows]
    industry_df = pd.DataFrame(industry_data)
    if len(industry_df) > 0:
        industry_agg = industry_df.groupby("行業")["現值"].sum().reset_index()
        fig_ind = px.pie(
            industry_agg,
            values="現值",
            names="行業",
            title="行業分布 / Industry Allocation",
            hole=0.4,
        )
        st.plotly_chart(fig_ind, use_container_width=True)

# Stock Detail / Trend Analysis
st.write("---")
st.subheader("📊 股票趨勢分析 / Stock Trend Analysis")

if list(display_holdings.keys()):
    analysis_stock = st.selectbox("選擇股票 / Select Stock", list(display_holdings.keys()))
    
    if analysis_stock:
        try:
            stock = yf.Ticker(analysis_stock)
            df = stock.history(period="1y")['Close']
            
            # Calculate RSI
            delta = df.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Price chart
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df.index,
                    open=stock.history(period="1y")['Open'],
                    high=stock.history(period="1y")['High'],
                    low=stock.history(period="1y")['Low'],
                    close=df,
                    name='Price'
                ))
                fig.update_layout(title=f"{analysis_stock} Price", height=300)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # RSI Chart
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df.index, y=rsi, name='RSI', line=dict(color='purple', width=2)))
                fig2.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought")
                fig2.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold")
                fig2.update_layout(title="RSI (14)", height=300, yaxis_range=[0, 100])
                st.plotly_chart(fig2, use_container_width=True)
        except Exception as e:
            st.error(f"Error: {e}")


@st.cache_data(ttl=3600)
def get_90day_price_us(ticker):
    """Get 90-day price data for US stocks"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d")
        if len(hist) > 0:
            current = hist['Close'].iloc[-1]
            highest = hist['Close'].max()
            drop_pct = ((highest - current) / highest) * 100 if highest > 0 else 0
            return {
                'current': current,
                'highest': highest,
                'drop_pct': drop_pct,
                'signal': '🟢 Buy' if drop_pct >= 20 else ('🟡 Watch' if drop_pct >= 10 else '🔴 Hold')
            }
    except:
        pass
    return None


# Stock Analysis
st.write("---")
st.subheader("📈 股票分析 / Stock Analysis")
st.caption(
    "RSI 與信號只在這個研究區顯示，並非持股表上的買賣指令。"
    "「預期年度股息」是 Yahoo dividendRate 的遠期年度估計（每股），不是今年已收現金。"
    " / RSI and signals stay in this research section and are not trade instructions. "
    "Expected annual dividend is Yahoo's forward dividendRate per share, not cash received this year."
)

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
            p90 = get_90day_price_us(ticker)
            
            if m:
                low = m.get("52w_low")
                high = m.get("52w_high")
                vol = ((high - low) / low) * 100 if low and high and low > 0 else None
                row = {
                    '股票代號': ticker,
                    '公司': get_us_name(ticker),
                    '股價': m.get('price'),
                    'P/E': m.get('pe'),
                    '預測P/E': m.get('forward_pe'),
                    '市帳率': m.get('pb_ratio'),
                    '52W低': low,
                    '52W高': high,
                    '波幅%': vol,
                    'Beta': m.get('beta'),
                    '股息%': m.get('dividend_yield'),
                    '預期年度股息': m.get('dividend_rate'),
                    '帳面值': m.get('book_value'),
                }

                if p90:
                    row['90天最高'] = p90.get('highest')
                    row['現價'] = p90.get('current')
                    row['回調%'] = p90.get('drop_pct')
                    row['信號'] = p90.get('signal')

                try:
                    hist = yf.Ticker(ticker).history(period="3mo")["Close"]
                    if hist is not None and len(hist) > 0:
                        rsi_val = calculate_rsi(hist).iloc[-1]
                        if pd.notna(rsi_val):
                            signal, _english = rsi_signal_labels(float(rsi_val))
                            row["RSI"] = round(float(rsi_val), 1)
                            row["RSI信號"] = signal
                except Exception:
                    pass

                analysis_rows.append(row)
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
    st.switch_page("app.py")