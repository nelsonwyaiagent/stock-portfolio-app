"""
Stock Portfolio Monitor App with Supabase
Author: Nova (AI Assistant)
For: Nelson
Simplified version - Username based login
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

# Page Config
st.set_page_config(page_title="Stock Portfolio Tracker", page_icon="📈", layout="wide")

# ============================================
# SIMPLE SUPABASE (No Auth, just database)
# ============================================

SUPABASE_URL = "https://wnvpmiaxjsvlbqjbvjim.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndudnBtaWF4anN2bGJRamJ2amltIiwicm9sZSI6ImFub24iLCJpbnN0YW5jZSI6IjEyMzQ1NiIsImlhdCI6MTY0MjAwMDAwMCwiZXhwIjoxOTU3NTc2MDAwfQ.HpH0M4F_x1m90e9vN8KxG1pJ8T6s2r5Q9y4W3X2zA"

try:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    supabase = None

# ============================================
# SESSION STATE
# ============================================

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if 'username' not in st.session_state:
    st.session_state.username = ""

if 'us_stocks' not in st.session_state:
    st.session_state.us_stocks = {}

if 'hk_stocks' not in st.session_state:
    st.session_state.hk_stocks = {}

# ============================================
# FUNCTIONS
# ============================================

@st.cache_data(ttl=3600)
def get_stock_data(ticker, period="1y"):
    try:
        return yf.Ticker(ticker).history(period=period)
    except:
        return None

def get_metrics(ticker, qty, cost):
    df = get_stock_data(ticker)
    if df is None or df.empty:
        return None
    price = df['Close'].iloc[-1]
    value = qty * price
    pnl = value - (qty * cost)
    pnl_pct = (pnl / (qty * cost)) * 100 if cost > 0 else 0
    
    # RSI
    rsi = 100 - (100 / (1 + (df['Close'].diff().where(df['Close'] > 0, 0).rolling(14).mean() / (-df['Close'].diff().where(df['Close'] < 0, 0).rolling(14).mean())).rolling(14).mean()))
    rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    return {"price": price, "value": value, "pnl": pnl, "pnl_pct": pnl_pct, "rsi": rsi}

def get_signal(rsi):
    if rsi < 30: return "BUY", "🟢"
    elif rsi > 70: return "SELL", "🔴"
    return "HOLD", "🟡"

# ============================================
# SUPABASE SAVE/LOAD
# ============================================

def save_portfolio(username, us, hk):
    if not supabase: return False
    try:
        # Try update first
        supabase.table('portfolios').update({
            'us_stocks': json.dumps(us),
            'hk_stocks': json.dumps(hk)
        }).eq('username', username).execute()
        return True
    except:
        try:
            # Try insert
            supabase.table('portfolios').insert({
                'username': username,
                'us_stocks': json.dumps(us),
                'hk_stocks': json.dumps(hk)
            }).execute()
            return True
        except:
            return False

def load_portfolio(username):
    if not supabase: return {}, {}
    try:
        r = supabase.table('portfolios').select('*').eq('username', username).execute()
        if r.data:
            return json.loads(r.data[0].get('us_stocks', '{}')), json.loads(r.data[0].get('hk_stocks', '{}'))
    except:
        pass
    return {}, {}

# ============================================
# MAIN APP
# ============================================

st.title("📈 Stock Portfolio Tracker")
st.markdown("**By Nova (AI Assistant)**")

# Login
if not st.session_state.logged_in:
    st.markdown("---")
    st.header("🔐 Login")
    
    with st.form("login"):
        username = st.text_input("Choose a Username")
        if st.form_submit_button("Start / Login"):
            if username:
                st.session_state.logged_in = True
                st.session_state.username = username
                # Load from cloud
                us, hk = load_portfolio(username)
                st.session_state.us_stocks = us or {}
                st.session_state.hk_stocks = hk or {}
                st.rerun()

else:
    # Logged in
    st.markdown(f"**👤 {st.session_state.username}** | [Logout](javascript:window.location.reload())")
    
    # Save button
    if st.button("💾 Save to Cloud"):
        if save_portfolio(st.session_state.username, st.session_state.us_stocks, st.session_state.hk_stocks):
            st.success("Saved!")
        else:
            st.warning("Save failed - will use local storage")

    # Sidebar
    st.sidebar.header("⚙️ Manage Stocks")
    
    tabs = st.sidebar.tabs(["🇺🇸 Add US", "🇭🇰 Add HK", "🗑️ Remove"])
    
    with tabs[0]:
        with st.form("add_us"):
            t = st.text_input("Symbol", key="us").upper()
            q = st.number_input("Qty", min_value=1, value=1)
            c = st.number_input("Cost $", min_value=0.01, value=100.00)
            if st.form_submit_button("Add") and t:
                st.session_state.us_stocks[t] = {"qty": q, "cost": c}
                st.rerun()
    
    with tabs[1]:
        with st.form("add_hk"):
            t = st.text_input("Symbol", key="hk").upper()
            q = st.number_input("Qty", min_value=1, value=1)
            c = st.number_input("Cost $", min_value=0.01, value=100.00)
            if st.form_submit_button("Add") and t:
                if not t.endswith('.HK'): t += '.HK'
                st.session_state.hk_stocks[t] = {"qty": q, "cost": c}
                st.rerun()
    
    with tabs[2]:
        all_s = {**st.session_state.us_stocks, **st.session_state.hk_stocks}
        if all_s:
            rem = st.selectbox("Remove", list(all_s.keys()))
            if st.button("Remove"):
                if rem in st.session_state.us_stocks: del st.session_state.us_stocks[rem]
                if rem in st.session_state.hk_stocks: del st.session_state.hk_stocks[rem]
                st.rerun()

    # Show holdings
    st.sidebar.write("📊 Holdings:")
    for t, d in st.session_state.us_stocks.items():
        st.sidebar.write(f"- {t}: {d['qty']} @ ${d['cost']}")
    for t, d in st.session_state.hk_stocks.items():
        st.sidebar.write(f"- {t}: {d['qty']} @ ${d['cost']}")

    # Portfolio
    st.markdown("---")
    st.header("💼 Portfolio")
    
    total_val = 0
    total_cost = 0
    holdings = []
    
    for t, d in st.session_state.us_stocks.items():
        m = get_metrics(t, d['qty'], d['cost'])
        if m:
            total_val += m['value']
            total_cost += d['qty'] * d['cost']
            sig, emoji = get_signal(m['rsi'])
            holdings.append({**d, "ticker": t, "price": m['price'], "value": m['value'], "pnl": m['pnl'], "rsi": m['rsi'], "signal": f"{emoji} {sig}"})

    for t, d in st.session_state.hk_stocks.items():
        m = get_metrics(t, d['qty'], d['cost'])
        if m:
            total_val += m['value']
            total_cost += d['qty'] * d['cost']
            sig, emoji = get_signal(m['rsi'])
            holdings.append({**d, "ticker": t, "price": m['price'], "value": m['value'], "pnl": m['pnl'], "rsi": m['rsi'], "signal": f"{emoji} {sig}"})

    if holdings:
        pnl = total_val - total_cost
        pct = (pnl / total_cost) * 100 if total_cost else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Value", f"${total_val:,.0f}")
        c2.metric("Cost", f"${total_cost:,.0f}")
        c3.metric("P&L", f"${pnl:,.0f}", f"{pct:.1f}%")
        c4.metric("Holdings", len(holdings))

        st.dataframe(pd.DataFrame(holdings)[["ticker", "qty", "price", "value", "pnl", "rsi", "signal"]].style.format({"price": "${:.2f}", "value": "${:.2f}", "pnl": "${:.2f}", "rsi": "{:.0f}"}), use_container_width=True)