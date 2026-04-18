"""
Stock Portfolio Monitor App - Fixed Version
Author: Nova (AI Assistant)
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import json

st.set_page_config(title="Stock Portfolio", page_icon="📈")

# Supabase config
URL = "https://wnvpmiaxjsvlbqjbvjim.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndudnBtaWF4anN2bGJRamJ2amltIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImluc3RhbmNlIjoiMTIzNDU2IiwiaWF0IjoxNjQyMDAwMDAwLCJleHAiOjE5NTc1NzYwMDAwfQ.pWhDRIGhSg0YdVTvXywz6J5JzX5J5J5J5J5J5J5J5J"

try:
    from supabase import create_client
    supabase = create_client(URL, KEY)
except:
    supabase = None

# Session
if 'login' not in st.session_state:
    st.session_state.login = False
if 'user' not in st.session_state:
    st.session_state.user = ""
if 'us' not in st.session_state:
    st.session_state.us = {}
if 'hk' not in st.session_state:
    st.session_state.hk = {}

# Load from Supabase
def load_portfolio(username):
    if not supabase:
        return {}, {}
    try:
        r = supabase.table('portfolios').select('*').eq('username', username).execute()
        if r.data:
            data = r.data[0]
            us = data.get('us_stocks', '{}')
            hk = data.get('hk_stocks', '{}')
            return json.loads(us) if isinstance(us, str) else us, json.loads(hk) if isinstance(hk, str) else hk
    except Exception as e:
        st.error(f"Load error: {e}")
    return {}, {}

# Save to Supabase  
def save_portfolio(username, us, hk):
    if not supabase:
        return False
    try:
        # Check exists
        r = supabase.table('portfolios').select('id').eq('username', username).execute()
        if r.data:
            supabase.table('portfolios').update({'us_stocks': json.dumps(us), 'hk_stocks': json.dumps(hk)}).eq('username', username).execute()
        else:
            supabase.table('portfolios').insert({'username': username, 'us_stocks': json.dumps(us), 'hk_stocks': json.dumps(hk)}).execute()
        return True
    except Exception as e:
        st.error(f"Save error: {e}")
        return False

# Get stock price
@st.cache_data(ttl=300)
def get_price(ticker):
    try:
        return yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
    except:
        return None

# Main
st.title("📈 Stock Portfolio")

# Login
if not st.session_state.login:
    st.subheader("🔐 Login")
    with st.form("f"):
        user = st.text_input("Username")
        if st.form_submit_button("Login"):
            if user:
                st.session_state.user = user
                st.session_state.login = True
                # Load from cloud
                us, hk = load_portfolio(user)
                st.session_state.us = us or {}
                st.session_state.hk = hk or {}
                st.rerun()

else:
    st.subheader(f"👤 {st.session_state.user}")
    
    # Save button
    if st.button("💾 Save"):
        ok = save_portfolio(st.session_state.user, st.session_state.us, st.session_state.hk)
        if ok: st.success("Saved!")
    
    # Logout
    if st.button("Logout"):
        st.session_state.login = False
        st.session_state.user = ""
        st.session_state.us = {}
        st.session_state.hk = {}
        st.rerun()

    # Add stocks - Sidebar
    st.sidebar.header("Add Stocks")
    
    with st.sidebar.form("add_us"):
        t = st.text_input("US Symbol").upper()
        q = st.number_input("Qty", 1, value=1)
        c = st.number_input("Cost", 0.01, value=100.0)
        if st.form_submit_button("Add US") and t:
            st.session_state.us[t] = {"qty": q, "cost": c}
            save_portfolio(st.session_state.user, st.session_state.us, st.session_state.hk)
            st.rerun()
    
    with st.sidebar.form("add_hk"):
        t = st.text_input("HK Symbol").upper()
        q = st.number_input("Qty", 1, value=1)
        c = st.number_input("Cost", 0.01, value=100.0)
        if st.form_submit_button("Add HK") and t:
            t = t if t.endswith('.HK') else t + '.HK'
            st.session_state.hk[t] = {"qty": q, "cost": c}
            save_portfolio(st.session_state.user, st.session_state.us, st.session_state.hk)
            st.rerun()

    # Remove
    all_s = {**st.session_state.us, **st.session_state.hk}
    if all_s:
        st.sidebar.markdown("---")
        rem = st.sidebar.selectbox("Remove", list(all_s.keys()))
        if st.sidebar.button("Delete"):
            if rem in st.session_state.us: del st.session_state.us[rem]
            if rem in st.session_state.hk: del st.session_state.hk[rem]
            save_portfolio(st.session_state.user, st.session_state.us, st.session_state.hk)
            st.rerun()

    # Show holdings
    st.sidebar.markdown("---")
    st.sidebar.write("**Your Stocks:**")
    for t, d in st.session_state.us.items(): st.sidebar.write(f"{t}: {d['qty']} @ ${d['cost']}")
    for t, d in st.session_state.hk.items(): st.sidebar.write(f"{t}: {d['qty']} @ ${d['cost']}")

    # Portfolio table
    st.markdown("---")
    st.subheader("💼 Portfolio")
    
    rows = []
    total_val = 0
    total_cost = 0
    
    for t, d in {**st.session_state.us, **st.session_state.hk}.items():
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
        c1, c2, c3, c4 = st.columns(4)
        pnl = total_val - total_cost
        c1.metric("Value", f"${total_val:,.0f}")
        c2.metric("Cost", f"${total_cost:,.0f}")
        c3.metric("P&L", f"${pnl:,.0f}")
        c4.metric("Stocks", len(rows))
        
        st.dataframe(df.style.format({"Cost": "${:.2f}", "Price": "${:.2f}", "Value": "${:.2f}", "P&L": "${:.2f}"}), use_container_width=True)
    else:
        st.info("No stocks yet. Add some!")