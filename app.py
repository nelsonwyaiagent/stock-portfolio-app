"""
Stock Portfolio - Simple Version
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import json
from datetime import datetime

# Simple page config
st.write("📈 **Stock Portfolio Tracker**")  # Skip complex config

# Supabase
URL = "https://wnvpmiaxjsvlbqjbvjim.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndudnBtaWF4anN2bGJRamJ2amltIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImluc3RhbmNlIjoiMTIzNDU2IiwiaWF0IjoxNjQyMDAwMDAwLCJleHAiOjE5NTc1NzYwMDAwfQ.pWhDRIGhSg0YdVTvXywz6J5JzX5J5J5J5J5J5J5J5J"

try:
    from supabase import create_client
    supabase = create_client(URL, KEY)
except:
    supabase = None

# Session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'us_stocks' not in st.session_state:
    st.session_state.us_stocks = {}
if 'hk_stocks' not in st.session_state:
    st.session_state.hk_stocks = {}

# Load/Save functions
def load_portfolio(username):
    if supabase:
        try:
            r = supabase.table('portfolios').select('us_stocks', 'hk_stocks').eq('username', username).execute()
            if r.data:
                us = r.data[0].get('us_stocks', '{}')
                hk = r.data[0].get('hk_stocks', '{}')
                return json.loads(us) if isinstance(us, str) else us, json.loads(hk) if isinstance(hk, str) else hk
        except:
            pass
    return {}, {}

def save_portfolio(username, us, hk):
    if supabase:
        try:
            r = supabase.table('portfolios').select('id').eq('username', username).execute()
            if r.data:
                supabase.table('portfolios').update({'us_stocks': json.dumps(us), 'hk_stocks': json.dumps(hk)}).eq('username', username).execute()
            else:
                supabase.table('portfolios').insert({'username': username, 'us_stocks': json.dumps(us), 'hk_stocks': json.dumps(hk)}).execute()
        except:
            pass

@st.cache_data(ttl=120)
def get_price(ticker):
    try:
        return yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
    except:
        return None

# Login section
st.header("🔐 Login")

if not st.session_state.logged_in:
    with st.form("login"):
        user = st.text_input("Username")
        if st.form_submit_button("Login / Sign Up"):
            if user:
                st.session_state.username = user
                st.session_state.logged_in = True
                us, hk = load_portfolio(user)
                st.session_state.us_stocks = us or {}
                st.session_state.hk_stocks = hk or {}
                st.success(f"Loaded! ({len(us)+len(hk)} stocks)")
                st.rerun()

else:
    # Logged in
    st.write(f"**Logged in as: {st.session_state.username}**")
    
    if st.button("💾 Save to Cloud"):
        save_portfolio(st.session_state.username, st.session_state.us_stocks, st.session_state.hk_stocks)
        st.success("Saved!")
    
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.us_stocks = {}
        st.session_state.hk_stocks = {}
        st.rerun()

    # Sidebar
    st.sidebar.header("⚙️ Add Stocks")
    
    with st.sidebar.form("add_us"):
        t = st.text_input("US Symbol (e.g. AAPL)").upper()
        q = st.number_input("Quantity", min_value=1, value=1)
        c = st.number_input("Avg Cost $", min_value=0.01, value=100.0)
        if st.form_submit_button("➕ Add US") and t:
            st.session_state.us_stocks[t] = {"qty": q, "cost": c}
            save_portfolio(st.session_state.username, st.session_state.us_stocks, st.session_state.hk_stocks)
            st.rerun()

    with st.sidebar.form("add_hk"):
        t = st.text_input("HK Symbol (e.g. 0700.HK)").upper()
        q = st.number_input("Quantity", min_value=1, value=1)
        c = st.number_input("Avg Cost $", min_value=0.01, value=100.0)
        if st.form_submit_button("➕ Add HK") and t:
            t = t if t.endswith('.HK') else t + '.HK'
            st.session_state.hk_stocks[t] = {"qty": q, "cost": c}
            save_portfolio(st.session_state.username, st.session_state.us_stocks, st.session_state.hk_stocks)
            st.rerun()

    # Remove
    all_s = {**st.session_state.us_stocks, **st.session_state.hk_stocks}
    if all_s:
        st.sidebar.markdown("---")
        rem = st.sidebar.selectbox("🗑️ Remove stock", list(all_s.keys()))
        if st.sidebar.button("Remove"):
            if rem in st.session_state.us_stocks: 
                del st.session_state.us_stocks[rem]
            if rem in st.session_state.hk_stocks: 
                del st.session_state.hk_stocks[rem]
            save_portfolio(st.session_state.username, st.session_state.us_stocks, st.session_state.hk_stocks)
            st.rerun()

    # Show holdings
    st.sidebar.markdown("---")
    st.sidebar.write("**Your Holdings:**")
    for t, d in st.session_state.us_stocks.items():
        st.sidebar.write(f"📈 {t}: {d['qty']} @ ${d['cost']}")
    for t, d in st.session_state.hk_stocks.items():
        st.sidebar.write(f"📈 {t}: {d['qty']} @ ${d['cost']}")
    if not all_s:
        st.sidebar.info("No stocks added")

    # Portfolio display
    st.header("💼 Portfolio")
    
    rows = []
    total_val = 0
    total_cost = 0
    
    for t, d in {**st.session_state.us_stocks, **st.session_state.hk_stocks}.items():
        price = get_price(t)
        if price:
            val = d['qty'] * price
            cost = d['qty'] * d['cost']
            pnl = val - cost
            rows.append({"Symbol": t, "Qty": d['qty'], "Cost": d['cost'], "Price": price, "Value": val, "P&L": pnl})
            total_val += val
            total_cost += cost

    if rows:
        df = pd.DataFrame(rows)
        c1, c2, c3 = st.columns(3)
        pnl = total_val - total_cost
        c1.metric("Total Value", f"${total_val:,.0f}")
        c2.metric("Total Cost", f"${total_cost:,.0f}")
        c3.metric("P&L", f"${pnl:,.0f}")
        
        st.dataframe(df.style.format({"Cost": "${:.2f}", "Price": "${:.2f}", "Value": "${:.2f}", "P&L": "${:.2f}"}))
    else:
        st.info("Add stocks to see your portfolio!")

    st.caption(f"Last updated: {datetime.now().strftime('%H:%M')}")