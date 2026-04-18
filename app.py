"""
Stock Portfolio Monitor App - Simple Version
Author: Nova (AI Assistant)
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

st.set_page_config(title="Stock Portfolio Tracker", page_icon="📈", layout="wide")

# Simple Supabase - using public anon key for read
SUPABASE_URL = "https://wnvpmiaxjsvlbqjbvjim.supabase.co"
# Use the service role key for write operations
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndudnBtaWF4anN2bGJRamJ2amltIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImluc3RhbmNlIjoiMTIzNDU2IiwiaWF0IjoxNjQyMDAwMDAwLCJleHAiOjE5NTc1NzYwMDAwfQ.pWhD RIGhSg0YdVTvXywz6J5J5J5J5J5J5J5J5J"

st.cache_data.clear()

try:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase connected!")
except Exception as e:
    print(f"Supabase error: {e}")
    supabase = None

# Session State
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'us_stocks' not in st.session_state:
    st.session_state.us_stocks = {}
if 'hk_stocks' not in st.session_state:
    st.session_state.hk_stocks = {}

@st.cache_data(ttl=60)
def get_stock(ticker):
    try:
        return yf.Ticker(ticker).history(period="1y")['Close'].iloc[-1]
    except:
        return None

def get_all_data(ticker, qty, cost):
    price = get_stock(ticker)
    if price is None:
        return None
    value = qty * price
    cost_basis = qty * cost
    pnl = value - cost_basis
    pnl_pct = (pnl / cost_basis) * 100 if cost_basis else 0
    # Simple RSI
    try:
        hist = yf.Ticker(ticker).history(period="3mo")['Close']
        delta = hist.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        if pd.isna(rsi): rsi = 50
    except:
        rsi = 50
    return {"price": price, "value": value, "pnl": pnl, "pnl_pct": pnl_pct, "rsi": rsi}

def save_data(username, us, hk):
    if not supabase:
        return False
    try:
        # Check if exists
        check = supabase.table('portfolios').select('username').eq('username', username).execute()
        if check.data:
            supabase.table('portfolios').update({'us_stocks': json.dumps(us), 'hk_stocks': json.dumps(hk)}).eq('username', username).execute()
        else:
            supabase.table('portfolios').insert({'username': username, 'us_stocks': json.dumps(us), 'hk_stocks': json.dumps(hk)}).execute()
        return True
    except Exception as e:
        print(f"Save error: {e}")
        return False

def load_data(username):
    if not supabase:
        return {}, {}
    try:
        r = supabase.table('portfolios').select('us_stocks', 'hk_stocks').eq('username', username).execute()
        if r.data and len(r.data) > 0:
            us = r.data[0].get('us_stocks', '{}')
            hk = r.data[0].get('hk_stocks', '{}')
            if isinstance(us, str):
                us = json.loads(us)
            if isinstance(hk, str):
                hk = json.loads(hk)
            return us, hk
    except Exception as e:
        print(f"Load error: {e}")
    return {}, {}

# Main App
st.title("📈 Stock Portfolio Tracker")
st.markdown("**By Nova (AI Assistant)**")

# Login
if not st.session_state.logged_in:
    st.markdown("---")
    st.header("🔐 Login")
    with st.form("login"):
        username = st.text_input("Username")
        if st.form_submit_button("Login / Sign Up"):
            if username:
                st.session_state.logged_in = True
                st.session_state.username = username
                # Load from Supabase
                us, hk = load_data(username)
                st.session_state.us_stocks = us if us else {}
                st.session_state.hk_stocks = hk if hk else {}
                st.success(f"Loaded {len(st.session_state.us_stocks) + len(st.session_state.hk_stocks)} stocks")
                st.rerun()

else:
    # Logged in
    st.markdown(f"**👤 {st.session_state.username}** | [Logout](javascript:window.location.reload())")
    
    # Save button
    if st.button("💾 Save to Cloud"):
        if save_data(st.session_state.username, st.session_state.us_stocks, st.session_state.hk_stocks):
            st.success("Saved!")
        else:
            st.warning("Save failed")
    
    # Sidebar - Add stocks
    st.sidebar.header("⚙️ Add Stocks")
    
    # Add US
    st.sidebar.subheader("🇺🇸 US Stocks")
    with st.sidebar.form("add_us"):
        us_t = st.text_input("Symbol (AAPL)", key="us_in").upper()
        us_q = st.number_input("Qty", min_value=1, value=1)
        us_c = st.number_input("Cost $", min_value=0.01, value=100.00)
        if st.form_submit_button("Add US") and us_t:
            st.session_state.us_stocks[us_t] = {"qty": us_q, "cost": us_c}
            st.rerun()
    
    # Add HK
    st.sidebar.subheader("🇭🇰 HK Stocks")
    with st.sidebar.form("add_hk"):
        hk_t = st.text_input("Symbol (0700.HK)", key="hk_in").upper()
        hk_q = st.number_input("Qty", min_value=1, value=1)
        hk_c = st.number_input("Cost $", min_value=0.01, value=100.00)
        if st.form_submit_button("Add HK") and hk_t:
            if not hk_t.endswith('.HK'):
                hk_t = hk_t + '.HK'
            st.session_state.hk_stocks[hk_t] = {"qty": hk_q, "cost": hk_c}
            st.rerun()
    
    # Remove
    st.sidebar.subheader("🗑️ Remove")
    all_stocks = {**st.session_state.us_stocks, **st.session_state.hk_stocks}
    if all_stocks:
        rem_t = st.sidebar.selectbox("Select to remove", list(all_stocks.keys()))
        if st.sidebar.button("Remove"):
            if rem_t in st.session_state.us_stocks:
                del st.session_state.us_stocks[rem_t]
            if rem_t in st.session_state.hk_stocks:
                del st.session_state.hk_stocks[rem_t]
            st.rerun()
    
    # Show current holdings
    st.sidebar.markdown("---")
    st.sidebar.write("**Your Holdings:**")
    for t, d in st.session_state.us_stocks.items():
        st.sidebar.write(f"📈 {t}: {d['qty']} @ ${d['cost']}")
    for t, d in st.session_state.hk_stocks.items():
        st.sidebar.write(f"📈 {t}: {d['qty']} @ ${d['cost']}")
    if not st.session_state.us_stocks and not st.session_state.hk_stocks:
        st.sidebar.info("No stocks added")

    # Portfolio summary
    st.markdown("---")
    st.header("💼 Portfolio")
    
    holdings = []
    total_val = 0
    total_cost = 0
    
    for t, d in {**st.session_state.us_stocks, **st.session_state.hk_stocks}.items():
        m = get_all_data(t, d['qty'], d['cost'])
        if m:
            total_val += m['value']
            total_cost += d['qty'] * d['cost']
            rsi_val = m['rsi']
            if rsi_val < 30: sig = "🟢 BUY"
            elif rsi_val > 70: sig = "🔴 SELL"
            else: sig = "🟡 HOLD"
            holdings.append({"Ticker": t, "Qty": d['qty'], "Cost": d['cost'], "Price": m['price'], "Value": m['value'], "P&L": m['pnl'], "P&L%": m['pnl_pct'], "RSI": rsi_val, "Signal": sig})

    if holdings:
        pnl = total_val - total_cost
        pnl_pct = (pnl / total_cost) * 100 if total_cost else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Value", f"${total_val:,.0f}")
        c2.metric("Cost", f"${total_cost:,.0f}")
        c3.metric("P&L", f"${pnl:,.0f}", f"{pnl_pct:.1f}%")
        c4.metric("Stocks", len(holdings))

        st.dataframe(pd.DataFrame(holdings).style.format({"Cost": "${:.2f}", "Price": "${:.2f}", "Value": "${:.2f}", "P&L": "${:.2f}", "P&L%": "{:.1f}%", "RSI": "{:.0f}"}), use_container_width=True)
    
    st.markdown(f"**Last updated:** {datetime.now().strftime('%H:%M')}")