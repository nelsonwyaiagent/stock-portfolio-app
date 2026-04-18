"""
Stock Portfolio - With manual Load button
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import json

# Supabase
URL = "https://wnvpmiaxjsvlbqjbvjim.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndudnBtaWF4anN2bGJRamJ2amltIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImluc3RhbmNlIjoiMTIzNDU2IiwiaWF0IjoxNjQyMDAwMDAwLCJleHAiOjE5NTc1NzYwMDAwfQ.pWhDRIGhSg0YdVTvXywz6J5JzX5J5J5J5J5J5J5J5J"

try:
    from supabase import create_client
    supabase = create_client(URL, KEY)
except:
    supabase = None

# Session
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
            if user:
                st.session_state.username = user
                st.session_state.logged_in = True
                # Auto load on login
                us, hk = load_data(user)
                st.session_state.us_stocks = us
                st.session_state.hk_stocks = hk
                st.success(f"Loaded {len(us)+len(hk)} stocks!")
                st.rerun()

else:
    st.write(f"**Logged in as: {st.session_state.username}**")
    
    # Load and Save buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📥 Load Data"):
            us, hk = load_data(st.session_state.username)
            st.session_state.us_stocks = us
            st.session_state.hk_stocks = hk
            st.success(f"Loaded {len(us)} US + {len(hk)} HK stocks!")
            st.rerun()
    with col2:
        if st.button("💾 Save"):
            save_data(st.session_state.username, st.session_state.us_stocks, st.session_state.hk_stocks)
            st.success("Saved!")
    with col3:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

    # Sidebar - Add
    st.sidebar.header("➕ Add Stocks")
    
    with st.sidebar.form("add_us"):
        t = st.text_input("US Symbol").upper()
        q = st.number_input("Qty", 1, value=1)
        c = st.number_input("Cost", 0.01, value=100.0)
        if st.form_submit_button("Add US"):
            st.session_state.us_stocks[t] = {"qty": q, "cost": c}
            save_data(st.session_state.username, st.session_state.us_stocks, st.session_state.hk_stocks)
            st.rerun()

    with st.sidebar.form("add_hk"):
        t = st.text_input("HK Symbol").upper()
        q = st.number_input("Qty", 1, value=1)
        c = st.number_input("Cost", 0.01, value=100.0)
        if st.form_submit_button("Add HK"):
            t = t if t.endswith('.HK') else t + '.HK'
            st.session_state.hk_stocks[t] = {"qty": q, "cost": c}
            save_data(st.session_state.username, st.session_state.us_stocks, st.session_state.hk_stocks)
            st.rerun()

    # Remove
    all_s = {**st.session_state.us_stocks, **st.session_state.hk_stocks}
    if all_s:
        st.sidebar.write("---")
        rem = st.sidebar.selectbox("🗑️ Remove", list(all_s.keys()))
        if st.sidebar.button("Delete"):
            if rem in st.session_state.us_stocks: del st.session_state.us_stocks[rem]
            if rem in st.session_state.hk_stocks: del st.session_state.hk_stocks[rem]
            save_data(st.session_state.username, st.session_state.us_stocks, st.session_state.hk_stocks)
            st.rerun()

    # Show holdings
    st.sidebar.write("---")
    st.sidebar.write("**Your Holdings:**")
    for t, d in st.session_state.us_stocks.items():
        st.sidebar.write(f"🇺🇸 {t}: {d['qty']} @ ${d['cost']}")
    for t, d in st.session_state.hk_stocks.items():
        st.sidebar.write(f"🇭🇰 {t}: {d['qty']} @ ${d['cost']}")
    if not all_s:
        st.sidebar.info("No stocks")

    # Portfolio
    st.header("💼 Portfolio")
    rows, total_val, total_cost = [], 0, 0
    
    for t, d in {**st.session_state.us_stocks, **st.session_state.hk_stocks}.items():
        try:
            price = yf.Ticker(t).history(period="1d")['Close'].iloc[-1]
            if price:
                val = d['qty'] * price
                cost = d['qty'] * d['cost']
                rows.append({"Symbol": t, "Qty": d['qty'], "Cost": d['cost'], "Price": price, "Value": val, "P&L": val-cost})
                total_val += val
                total_cost += cost
        except:
            pass

    if rows:
        c1,c2,c3 = st.columns(3)
        pnl = total_val - total_cost
        c1.metric("Value", f"${total_val:,.0f}")
        c2.metric("Cost", f"${total_cost:,.0f}")  
        c3.metric("P&L", f"${pnl:,.0f}")
        st.dataframe(pd.DataFrame(rows).style.format({"Cost":"${:.2f}","Price":"${:.2f}","Value":"${:.2f}","P&L":"${:.2f}"}))
    else:
        st.info("Add stocks to see portfolio!")

# Functions
def load_data(username):
    if not supabase:
        return {}, {}
    try:
        r = supabase.table('portfolios').select('us_stocks','hk_stocks').eq('username', username).execute()
        if r.data:
            us = r.data[0]['us_stocks']
            hk = r.data[0]['hk_stocks']
            return json.loads(us) if isinstance(us, str) else us, json.loads(hk) if isinstance(hk, str) else hk
    except Exception as e:
        st.error(f"Load error: {e}")
    return {}, {}

def save_data(username, us, hk):
    if supabase:
        try:
            supabase.table('portfolios').update({'us_stocks': json.dumps(us), 'hk_stocks': json.dumps(hk)}).eq('username', username).execute()
        except:
            pass