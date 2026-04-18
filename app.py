"""
Stock Portfolio - Using environment variables
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os

# Get from environment
URL = os.environ.get("SUPABASE_URL", "https://wnvpmiaxjsvlbqjbvjim.supabase.co")
KEY = os.environ.get("SUPABASE_KEY", "")

print(f"URL from env: {URL}")
print(f"KEY from env: {KEY[:20] if KEY else 'NOT SET'}...")

# Try to get from Streamlit secrets
try:
    URL = st.secrets.get("SUPABASE_URL", URL)
    KEY = st.secrets.get("SUPABASE_KEY", KEY)
except:
    pass

print(f"Final URL: {URL}")
print(f"Final KEY: {KEY[:20] if KEY else 'NOT SET'}...")

supabase = None
if KEY:
    try:
        from supabase import create_client
        supabase = create_client(URL, KEY)
        print("Supabase connected!")
    except Exception as e:
        print(f"Error: {e}")

# Test function
def test_db():
    if supabase:
        try:
            r = supabase.table('portfolios').select('*').execute()
            return r.data
        except Exception as e:
            return [{"error": str(e)}]
    return [{"error": "No supabase client"}]

# Session
for k in ['logged_in','username','us_stocks','hk_stocks']:
    if k not in st.session_state:
        st.session_state[k] = {} if k in ['us_stocks','hk_stocks'] else False

st.title("📈 Stock Portfolio")

st.write("Supabase URL:", URL)
st.write("Has Key:", "Yes" if KEY else "No")
st.write("Has Supabase:", "Yes" if supabase else "No")

# Test button
if st.button("🔍 Test DB"):
    data = test_db()
    st.write("DB result:", data)

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
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

if st.session_state.logged_in:
    st.write(f"**{st.session_state.username}**")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
    
    st.write("US:", st.session_state.us_stocks)
    st.write("HK:", st.session_state.hk_stocks)