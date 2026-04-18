"""
Stock Portfolio - Debug version with print statements
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os

# Debug - print environment info
print("Starting app...")

# Supabase
URL = "https://wnvpmiaxjsvlbqjbvjim.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndudnBtaWF4anN2bGJRamJ2amltIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImluc3RhbmNlIjoiMTIzNDU2IiwiaWF0IjoxNjQyMDAwMDAwLCJleHAiOjE5NTc1NzYwMDAwfQ.pWhDRIGhSg0YdVTvXywz6J5JzX5J5J5J5J5J5J5J5J"

supabase = None
try:
    from supabase import create_client
    supabase = create_client(URL, KEY)
    print("Supabase connected!")
except Exception as e:
    print(f"Supabase error: {e}")

# Test function
def test_supabase():
    if supabase:
        try:
            r = supabase.table('portfolios').select('username','us_stocks','hk_stocks').execute()
            print(f"Query result: {r.data}")
            return r.data
        except Exception as e:
            print(f"Query error: {e}")
            return []
    return []

# Session state
for k in ['logged_in','username','us_stocks','hk_stocks']:
    if k not in st.session_state:
        st.session_state[k] = {} if k in ['us_stocks','hk_stocks'] else False

st.title("📈 Stock Portfolio")

# Test button - show what's in DB
if st.button("🔍 Test DB"):
    data = test_supabase()
    st.write("DB Contents:")
    for row in data:
        st.write(f"- {row.get('username')}: US={row.get('us_stocks')}, HK={row.get('hk_stocks')}")

# Login
if not st.session_state.logged_in:
    st.header("🔐 Login")
    with st.form("login"):
        user = st.text_input("Username")
        if st.form_submit_button("Login"):
            if user:
                # Manual query
                if supabase:
                    try:
                        r = supabase.table('portfolios').select('us_stocks','hk_stocks').eq('username', user).execute()
                        st.write(f"Query for {user}: {r.data}")
                        if r.data and len(r.data) > 0:
                            us_str = r.data[0].get('us_stocks', '{}')
                            hk_str = r.data[0].get('hk_stocks', '{}')
                            st.session_state.us_stocks = json.loads(us_str) if us_str else {}
                            st.session_state.hk_stocks = json.loads(hk_str) if hk_str else {}
                            st.session_state.username = user
                            st.session_state.logged_in = True
                            st.success(f"Loaded {len(st.session_state.us_stocks) + len(st.session_state.hk_stocks)} stocks!")
                            st.rerun()
                        else:
                            st.warning("No data found, starting fresh")
                            st.session_state.username = user
                            st.session_state.logged_in = True
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("Supabase not connected")

else:
    st.write(f"**Logged in: {st.session_state.username}**")
    st.write(f"US stocks: {st.session_state.us_stocks}")
    st.write(f"HK stocks: {st.session_state.hk_stocks}")
    
    # Manual load
    if st.button("📥 Manual Load"):
        if supabase:
            try:
                r = supabase.table('portfolios').select('us_stocks','hk_stocks').eq('username', st.session_state.username).execute()
                if r.data and len(r.data) > 0:
                    us_str = r.data[0].get('us_stocks', '{}')
                    hk_str = r.data[0].get('hk_stocks', '{}')
                    st.session_state.us_stocks = json.loads(us_str) if us_str else {}
                    st.session_state.hk_stocks = json.loads(hk_str) if hk_str else {}
                    st.success(f"Loaded! {len(st.session_state.us_stocks)} US, {len(st.session_state.hk_stocks)} HK")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # Portfolio display
    st.header("💼 Your Stocks")
    
    if not st.session_state.us_stocks and not st.session_state.hk_stocks:
        st.info("No stocks. Add some!")
    else:
        rows = []
        for t, d in {**st.session_state.us_stocks, **st.session_state.hk_stocks}.items():
            try:
                price = yf.Ticker(t).history(period="1d")['Close'].iloc[-1]
                val = d['qty'] * price
                cost = d['qty'] * d['cost']
                rows.append({"Symbol": t, "Qty": d['qty'], "Cost": d['cost'], "Price": price, "Value": val, "P&L": val-cost})
            except:
                pass
        
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df.style.format({"Cost":"${:.2f}","Price":"${:.2f}","Value":"${:.2f}","P&L":"${:.2f}"}))