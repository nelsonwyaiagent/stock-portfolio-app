"""
Stock Portfolio - Debug version
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import json

# CORRECT Supabase credentials from earlier test
URL = "https://wnvpmiaxjsvlbqjbvjim.supabase.co"
# Using the key that WORKED in curl
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndudnBtaWF4anN2bGJRamJ2amltIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImluc3RhbmNlIjoiMTIzNDU2IiwiaWF0IjoxNjQyMDAwMDAwLCJleHAiOjE5NTc1NzYwMDAwfQ.pWhDRIGhSg0YdVTvXywz6J5JzX5J5J5J5J5J5J5J5J"

print(f"Testing with URL: {URL}")

supabase = None
try:
    from supabase import create_client
    supabase = create_client(URL, KEY)
    print("Supabase connected successfully!")
except Exception as e:
    print(f"Connection error: {e}")

# Test query function
def test_db():
    if supabase:
        try:
            r = supabase.table('portfolios').select('*').execute()
            return r.data
        except Exception as e:
            return [{"error": str(e)}]
    return [{"error": "No supabase"}]

# Session
for k in ['logged_in','username','us_stocks','hk_stocks']:
    if k not in st.session_state:
        st.session_state[k] = {} if k in ['us_stocks','hk_stocks'] else False

st.title("📈 Stock Portfolio")

# Debug button
if st.button("🔍 Test DB"):
    data = test_db()
    st.write("Database says:", data)

# Login
if not st.session_state.logged_in:
    st.header("🔐 Login")
    with st.form("login"):
        user = st.text_input("Username")
        if st.form_submit_button("Login"):
            if user:
                st.session_state.username = user
                st.session_state.logged_in = True
                # Try to load
                if supabase:
                    try:
                        r = supabase.table('portfolios').select('us_stocks','hk_stocks').eq('username', user).execute()
                        st.write("Query result:", r.data)
                        if r.data and len(r.data) > 0:
                            us = r.data[0].get('us_stocks', '{}')
                            hk = r.data[0].get('hk_stocks', '{}')
                            st.session_state.us_stocks = json.loads(us) if us else {}
                            st.session_state.hk_stocks = json.loads(hk) if hk else {}
                            st.success(f"Loaded {len(st.session_state.us_stocks)} US, {len(st.session_state.hk_stocks)} HK!")
                    except Exception as e:
                        st.error(f"Error: {e}")
                st.rerun()

else:
    st.write(f"**Logged in: {st.session_state.username}**")
    
    # Manual load
    if st.button("📥 Load"):
        if supabase:
            try:
                r = supabase.table('portfolios').select('us_stocks','hk_stocks').eq('username', st.session_state.username).execute()
                if r.data and len(r.data) > 0:
                    us = r.data[0].get('us_stocks', '{}')
                    hk = r.data[0].get('hk_stocks', '{}')
                    st.session_state.us_stocks = json.loads(us) if us else {}
                    st.session_state.hk_stocks = json.loads(hk) if hk else {}
                    st.success("Loaded!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # Show stocks
    st.header("💼 Stocks")
    all_stocks = {**st.session_state.us_stocks, **st.session_state.hk_stocks}
    if all_stocks:
        for t, d in all_stocks.items():
            st.write(f"- {t}: {d['qty']} @ ${d['cost']}")
    else:
        st.info("No stocks yet!")