"""
Stock Portfolio with Historical Tracking
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import plotly.express as px
from datetime import datetime

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

for k in ['logged_in','username','us_stocks','hk_stocks']:
    if k not in st.session_state:
        st.session_state[k] = {} if k in ['us_stocks','hk_stocks'] else False

st.title("📈 Stock Portfolio")

# Login
if not st.session_state.logged_in:
    st.header("🔐 Login")
    with st.form("login"):
        user = st.text_input("Username")
        if st.form_submit_button("Login"):
            if user and supabase:
                try:
                    r = supabase.table('portfolios').select('us_stocks','hk_stocks').eq('username', user).execute()
                    if r.data and len(r.data) > 0:
                        st.session_state.us_stocks = json.loads(r.data[0].get('us_stocks','{}'))
                        st.session_state.hk_stocks = json.loads(r.data[0].get('hk_stocks','{}'))
                    st.session_state.username = user
                    st.session_state.logged_in = True
                    st.success("Loaded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

else:
    st.write(f"**👤 {st.session_state.username}**")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📥 Load"):
            if supabase:
                try:
                    r = supabase.table('portfolios').select('us_stocks','hk_stocks').eq('username', st.session_state.username).execute()
                    if r.data and len(r.data) > 0:
                        st.session_state.us_stocks = json.loads(r.data[0].get('us_stocks','{}'))
                        st.session_state.hk_stocks = json.loads(r.data[0].get('hk_stocks','{}'))
                        st.success("Loaded!")
                        st.rerun()
                except: pass
    with col2:
        if st.button("💾 Save"):
            if supabase:
                try:
                    supabase.table('portfolios').update({'us_stocks': json.dumps(st.session_state.us_stocks), 'hk_stocks': json.dumps(st.session_state.hk_stocks)}).eq('username', st.session_state.username).execute()
                    st.success("Saved!")
                except: pass
    with col3:
        if st.button("Logout"): st.session_state.logged_in = False; st.rerun()

    # Sidebar
    st.sidebar.header("⚙️ Add Stocks")
    with st.sidebar.form("add_us"):
        t = st.text_input("US").upper()
        q = st.number_input("Qty", 1, value=1)
        c = st.number_input("Cost", 0.01, value=100.0)
        if st.form_submit_button("Add") and t:
            st.session_state.us_stocks[t] = {"qty": q, "cost": c}
            st.rerun()
    with st.sidebar.form("add_hk"):
        t = st.text_input("HK").upper()
        q = st.number_input("Qty", 1, value=1)
        c = st.number_input("Cost", 0.01, value=100.0)
        if st.form_submit_button("Add") and t:
            t = t if t.endswith('.HK') else t + '.HK'
            st.session_state.hk_stocks[t] = {"qty": q, "cost": c}
            st.rerun()

    all_s = {**st.session_state.us_stocks, **st.session_state.hk_stocks}
    if all_s:
        st.sidebar.write("---")
        rem = st.sidebar.selectbox("Remove", list(all_s.keys()))
        if st.sidebar.button("Delete"):
            if rem in st.session_state.us_stocks: del st.session_state.us_stocks[rem]
            if rem in st.session_state.hk_stocks: del st.session_state.hk_stocks[rem]
            st.rerun()

    st.sidebar.write("**Holdings:**")
    for t, d in st.session_state.us_stocks.items(): st.sidebar.write(f"📈 {t}: {d['qty']}")
    for t, d in st.session_state.hk_stocks.items(): st.sidebar.write(f"📈 {t}: {d['qty']}")

    # Current Portfolio
    st.header("💼 Portfolio (Current)")
    rows, total_val, total_cost = [], 0, 0
    
    for ticker, d in {**st.session_state.us_stocks, **st.session_state.hk_stocks}.items():
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Try to get Chinese name
            if ticker.endswith('.HK'):
                company = info.get('longName', ticker)[:30]
            else:
                company = info.get('longName', info.get('shortName', ticker))[:30]
            
            price = stock.history(period="1d")['Close'].iloc[-1]
            if price:
                val = d['qty'] * price
                cost = d['qty'] * d['cost']
                pnl = val - cost
                pct = (pnl/cost*100) if cost else 0
                
                # RSI
                hist = stock.history(period="3mo")['Close']
                delta = hist.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi_val = (100 - (100 / (1 + rs))).iloc[-1]
                if pd.isna(rsi_val): rsi_val = 50
                
                if rsi_val < 30: signal = "🟢 BUY"
                elif rsi_val > 70: signal = "🔴 SELL"
                else: signal = "🟡 HOLD"
                
                rows.append({
                    "Symbol": ticker,
                    "Company": company,
                    "Qty": d['qty'],
                    "Cost (HKD)": d['cost'],
                    "Price (HKD)": price,
                    "Value (HKD)": val,
                    "P&L (HKD)": pnl,
                    "%": pct,
                    "RSI": rsi_val,
                    "Signal": signal
                })
                total_val += val
                total_cost += cost
        except: pass

    if rows:
        df = pd.DataFrame(rows)
        c1,c2,c3 = st.columns(3)
        c1.metric("Value", f"HKD {total_val:,.0f}")
        c2.metric("Cost", f"HKD {total_cost:,.0f}")
        c3.metric("P&L", f"HKD {total_val-total_cost:,.0f}")
        
        st.dataframe(df.style.format({
            "Cost (HKD)": "{:.2f}", 
            "Price (HKD)": "{:.2f}", 
            "Value (HKD)": "{:.2f}", 
            "P&L (HKD)": "{:.2f}", 
            "%": "{:.1f}%",
            "RSI": "{:.0f}"
        }), use_container_width=True)
        
        if len(df) > 0:
            fig = px.pie(df, values='Value (HKD)', names='Symbol', title='Allocation', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No stocks")

    # Historical Portfolio
    st.header("📊 Monthly Portfolio Value (2026)")
    
    # Months to check
    months = ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"]
    month_labels = ["Jan 2026", "Feb 2026", "Mar 2026", "Apr 2026"]
    
    hist_rows = []
    
    for i, (month_end, label) in enumerate(zip(months, month_labels)):
        month_val = 0
        month_data = {}
        
        for ticker, d in {**st.session_state.us_stocks, **st.session_state.hk_stocks}.items():
            try:
                stock = yf.Ticker(ticker)
                # Get price at month end
                hist = stock.history(start="2026-01-01", end=month_end)
                if not hist.empty:
                    # Get the last price of the month
                    month_price = hist['Close'].iloc[-1]
                    month_val += d['qty'] * month_price
                    month_data[ticker] = month_price
            except:
                pass
        
        hist_rows.append({"Month": label, "Total Value (HKD)": month_val})
    
    if hist_rows:
        hist_df = pd.DataFrame(hist_rows)
        st.dataframe(hist_df.style.format({"Total Value (HKD)": "HKD {:,.0f}"}), use_container_width=True)
        
        # Line chart
        fig_line = px.line(hist_df, x='Month', y='Total Value (HKD)', title='Portfolio Value Trend', markers=True)
        fig_line.update_traces(line_color='green', marker=dict(color='blue', size=10))
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No historical data")