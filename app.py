"""
Stock Portfolio - Simple and Working
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import plotly.express as px

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
                    st.success(f"Loaded!")
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

    # Portfolio
    st.header("💼 Portfolio")
    rows, total_val, total_cost = [], 0, 0
    
    for ticker, d in {**st.session_state.us_stocks, **st.session_state.hk_stocks}.items():
        try:
            stock = yf.Ticker(ticker)
            price = stock.history(period="1d")['Close'].iloc[-1]
            if price:
                val = d['qty'] * price
                cost = d['qty'] * d['cost']
                pnl = val - cost
                pct = (pnl/cost*100) if cost else 0
                rows.append({"Symbol": ticker, "Qty": d['qty'], "Cost (HKD)": d['cost'], "Price (HKD)": price, "Value (HKD)": val, "P&L (HKD)": pnl, "%": pct})
                total_val += val
                total_cost += cost
        except: pass

    if rows:
        df = pd.DataFrame(rows)
        c1,c2,c3 = st.columns(3)
        c1.metric("Value", f"HKD {total_val:,.0f}")
        c2.metric("Cost", f"HKD {total_cost:,.0f}")
        c3.metric("P&L", f"HKD {total_val-total_cost:,.0f}")
        
        st.dataframe(df.style.format({"Cost (HKD)": "HKD {:.2f}", "Price (HKD)": "HKD {:.2f}", "Value (HKD)": "HKD {:.2f}", "P&L (HKD)": "HKD {:.2f}", "%": "{:.1f}%"}))
        
        # Pie chart
        if len(df) > 0:
            fig = px.pie(df, values='Value (HKD)', names='Symbol', title='Allocation', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No stocks")