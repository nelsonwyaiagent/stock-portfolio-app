"""
Stock Portfolio Monitor App with Supabase
Author: Nova (AI Assistant)
For: Nelson
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os

# Page Config
st.set_page_config(
    page_title="Stock Portfolio Tracker",
    page_icon="📈",
    layout="wide"
)

# ============================================
# SUPABASE - Load from Streamlit Secrets
# ============================================

try:
    supabase_url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
    supabase_key = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))
except:
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")

supabase_client = None
if supabase_url and supabase_key:
    try:
        from supabase import create_client
        supabase_client = create_client(supabase_url, supabase_key)
    except:
        pass

# ============================================
# SESSION STATE
# ============================================

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if 'user_email' not in st.session_state:
    st.session_state.user_email = None

if 'user_id' not in st.session_state:
    st.session_state.user_id = None

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
        stock = yf.Ticker(ticker)
        return stock.history(period=period)
    except:
        return None

def calculate_rsi(prices, length=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices):
    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    return ema12 - ema26

def calculate_metrics(ticker, qty, avg_cost):
    df = get_stock_data(ticker)
    if df is None or df.empty:
        return None
    
    current_price = df['Close'].iloc[-1]
    cost_basis = qty * avg_cost
    current_value = qty * current_price
    pnl = current_value - cost_basis
    pnl_percent = (pnl / cost_basis) * 100 if cost_basis > 0 else 0
    
    week_ago = datetime.now() - timedelta(days=7)
    try:
        week_data = df[df.index <= week_ago]
        week_price = week_data['Close'].iloc[-1] if not week_data.empty else current_price
        weekly_change = ((current_price - week_price) / week_price) * 100
    except:
        weekly_change = 0
    
    rsi = calculate_rsi(df['Close']).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    macd_value = calculate_macd(df['Close']).iloc[-1]
    if pd.isna(macd_value):
        macd_value = 0
    
    return {
        "current_price": current_price,
        "cost_basis": cost_basis,
        "current_value": current_value,
        "pnl": pnl,
        "pnl_percent": pnl_percent,
        "weekly_change": weekly_change,
        "rsi": rsi,
        "macd": macd_value
    }

def get_signal(rsi, macd):
    if rsi < 30 and macd > 0:
        return "STRONG BUY", "🟢"
    elif rsi < 40 and macd > 0:
        return "BUY", "🟢"
    elif rsi > 70:
        return "SELL", "🔴"
    elif rsi > 60:
        return "WATCH", "🟡"
    return "HOLD", "🟡"

# ============================================
# SUPABASE FUNCTIONS
# ============================================

def save_portfolio(user_id, us_stocks, hk_stocks):
    if not supabase_client:
        return False
    try:
        # Check if exists
        response = supabase_client.table('portfolios').select('id').eq('id', user_id).execute()
        
        if response.data:
            supabase_client.table('portfolios').update({
                'us_stocks': json.dumps(us_stocks),
                'hk_stocks': json.dumps(hk_stocks)
            }).eq('id', user_id).execute()
        else:
            supabase_client.table('portfolios').insert({
                'id': user_id,
                'us_stocks': json.dumps(us_stocks),
                'hk_stocks': json.dumps(hk_stocks)
            }).execute()
        return True
    except:
        return False

def load_portfolio(user_id):
    if not supabase_client:
        return {}, {}
    try:
        response = supabase_client.table('portfolios').select('*').eq('id', user_id).execute()
        if response.data:
            data = response.data[0]
            return json.loads(data.get('us_stocks', '{}')), json.loads(data.get('hk_stocks', '{}'))
    except:
        pass
    return {}, {}

def login_user(email, password):
    if not supabase_client:
        st.error("Supabase not configured!")
        return False
    
    try:
        response = supabase_client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            st.session_state.logged_in = True
            st.session_state.user_email = response.user.email
            st.session_state.user_id = response.user.id
            
            # Load portfolio
            us, hk = load_portfolio(response.user.id)
            st.session_state.us_stocks = us if us else {}
            st.session_state.hk_stocks = hk if hk else {}
            return True
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
    return False

def signup_user(email, password, username):
    if not supabase_client:
        st.error("Supabase not configured!")
        return False
    
    try:
        response = supabase_client.auth.sign_up({
            "email": email,
            "password": password
        })
        
        if response.user:
            # Create portfolio entry
            supabase_client.table('portfolios').insert({
                'id': response.user.id,
                'username': username,
                'email': email,
                'us_stocks': '{}',
                'hk_stocks': '{}'
            }).execute()
            
            st.session_state.logged_in = True
            st.session_state.user_email = email
            st.session_state.user_id = response.user.id
            st.session_state.username = username
            return True
    except Exception as e:
        st.error(f"Signup failed: {str(e)}")
    return False

def logout_user():
    if st.session_state.logged_in:
        save_portfolio(st.session_state.user_id, st.session_state.us_stocks, st.session_state.hk_stocks)
    
    if supabase_client:
        try:
            supabase_client.auth.sign_out()
        except:
            pass
    
    st.session_state.logged_in = False
    st.session_state.user_email = None
    st.session_state.user_id = None
    st.session_state.username = ""
    st.session_state.us_stocks = {}
    st.session_state.hk_stocks = {}

# ============================================
# MAIN APP
# ============================================

st.title("📈 Stock Portfolio Tracker")
st.markdown("**By Nova (AI Assistant)**")

if not st.session_state.logged_in:
    st.markdown("---")
    
    tab_login, tab_signup = st.tabs(["🔐 Login", "📝 Sign Up"])
    
    with tab_login:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                login_user(email, password)
                st.rerun()
    
    with tab_signup:
        with st.form("signup"):
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            
            if st.form_submit_button("Sign Up"):
                if password != confirm_password:
                    st.error("Passwords don't match!")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters!")
                else:
                    signup_user(email, password, username)
                    st.success("Account created! Please login.")
                    st.rerun()

else:
    # Logged in
    st.markdown(f"**Logged in as: {st.session_state.user_email}**")
    
    col1, col2 = st.columns([6, 1])
    with col1:
        if st.button("💾 Save to Cloud"):
            if save_portfolio(st.session_state.user_id, st.session_state.us_stocks, st.session_state.hk_stocks):
                st.success("Saved to cloud!")
            else:
                st.warning("Save failed")
    with col2:
        if st.button("Logout"):
            logout_user()
            st.rerun()

    # Sidebar
    st.sidebar.header("⚙️ Manage Stocks")
    
    tab1, tab2, tab3 = st.sidebar.tabs(["🇺🇸 Add US", "🇭🇰 Add HK", "🗑️ Remove"])
    
    with tab1:
        with st.form("add_us"):
            ticker = st.text_input("Symbol (e.g. AAPL)", key="us_add").upper()
            qty = st.number_input("Qty", min_value=1, value=1, key="us_qty")
            cost = st.number_input("Avg Cost $", min_value=0.01, value=100.00, key="us_cost")
            if st.form_submit_button("➕ Add") and ticker:
                st.session_state.us_stocks[ticker] = {"qty": qty, "cost": cost}
                save_portfolio(st.session_state.user_id, st.session_state.us_stocks, st.session_state.hk_stocks)
                st.rerun()

    with tab2:
        with st.form("add_hk"):
            ticker = st.text_input("Symbol (e.g. 0700.HK)", key="hk_add").upper()
            qty = st.number_input("Qty", min_value=1, value=1, key="hk_qty")
            cost = st.number_input("Avg Cost $", min_value=0.01, value=100.00, key="hk_cost")
            if st.form_submit_button("➕ Add") and ticker:
                if not ticker.endswith('.HK'):
                    ticker = ticker + '.HK'
                st.session_state.hk_stocks[ticker] = {"qty": qty, "cost": cost}
                save_portfolio(st.session_state.user_id, st.session_state.us_stocks, st.session_state.hk_stocks)
                st.rerun()

    with tab3:
        all_stocks = {**st.session_state.us_stocks, **st.session_state.hk_stocks}
        if all_stocks:
            remove = st.selectbox("Remove", list(all_stocks.keys()))
            if st.button("🗑️ Remove"):
                if remove in st.session_state.us_stocks:
                    del st.session_state.us_stocks[remove]
                if remove in st.session_state.hk_stocks:
                    del st.session_state.hk_stocks[remove]
                save_portfolio(st.session_state.user_id, st.session_state.us_stocks, st.session_state.hk_stocks)
                st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Holdings")
    for t, d in st.session_state.us_stocks.items():
        st.sidebar.write(f"- {t}: {d['qty']} @ ${d['cost']}")
    for t, d in st.session_state.hk_stocks.items():
        st.sidebar.write(f"- {t}: {d['qty']} @ ${d['cost']}")
    if not st.session_state.us_stocks and not st.session_state.hk_stocks:
        st.sidebar.info("No stocks yet")

    # Portfolio
    st.markdown("---")
    st.header("💼 Portfolio Overview")
    
    total_value = 0
    total_cost = 0
    holdings = []
    
    for ticker, data in st.session_state.us_stocks.items():
        m = calculate_metrics(ticker, data['qty'], data['cost'])
        if m:
            total_value += m['current_value']
            total_cost += m['cost_basis']
            sig, emoji = get_signal(m['rsi'], m['macd'])
            holdings.append({"ticker": ticker, "qty": data['qty'], "price": m['current_price'], "value": m['current_value'], "pnl": m['pnl'], "pnl_pct": m['pnl_percent'], "rsi": m['rsi'], "signal": f"{emoji} {sig}"})

    for ticker, data in st.session_state.hk_stocks.items():
        m = calculate_metrics(ticker, data['qty'], data['cost'])
        if m:
            total_value += m['current_value']
            total_cost += m['cost_basis']
            sig, emoji = get_signal(m['rsi'], m['macd'])
            holdings.append({"ticker": ticker, "qty": data['qty'], "price": m['current_price'], "value": m['current_value'], "pnl": m['pnl'], "pnl_pct": m['pnl_percent'], "rsi": m['rsi'], "signal": f"{emoji} {sig}"})

    if holdings:
        col1, col2, col3, col4 = st.columns(4)
        pnl = total_value - total_cost
        pnl_pct = (pnl / total_cost) * 100 if total_cost > 0 else 0
        col1.metric("Value", f"${total_value:,.2f}")
        col2.metric("Cost", f"${total_cost:,.2f}")
        col3.metric("P&L", f"${pnl:,.2f}", f"{pnl_pct:.2f}%")
        col4.metric("Holdings", len(holdings))

        st.markdown("---")
        st.header("📊 Holdings Detail")
        df = pd.DataFrame(holdings)
        st.dataframe(df[["ticker", "qty", "price", "value", "pnl", "rsi", "signal"]].style.format({"price": "${:.2f}", "value": "${:.2f}", "pnl": "${:.2f}", "rsi": "{:.1f}"}), use_container_width=True)
        
        # Charts
        col1, col2 = st.columns(2)
        with col1:
            fig = go.Figure(go.Pie(labels=df['ticker'], values=df['value'], hole=0.4))
            fig.update_layout(title="Allocation")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = go.Figure(go.Bar(x=df['ticker'], y=df['pnl'], marker_color=['green' if x > 0 else 'red' for x in df['pnl']]))
            fig.update_layout(title="P/L")
            st.plotly_chart(fig, use_container_width=True)