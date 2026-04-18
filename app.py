"""
Stock Portfolio - Full UI with enhanced features
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os

# Get from environment
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
            if user and supabase:
                try:
                    r = supabase.table('portfolios').select('us_stocks','hk_stocks').eq('username', user).execute()
                    if r.data and len(r.data) > 0:
                        st.session_state.us_stocks = json.loads(r.data[0].get('us_stocks','{}'))
                        st.session_state.hk_stocks = json.loads(r.data[0].get('hk_stocks','{}'))
                    st.session_state.username = user
                    st.session_state.logged_in = True
                    st.success(f"Loaded {len(st.session_state.us_stocks)} US, {len(st.session_state.hk_stocks)} HK!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

else:
    st.write(f"**👤 {st.session_state.username}**")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📥 Load Data"):
            if supabase:
                try:
                    r = supabase.table('portfolios').select('us_stocks','hk_stocks').eq('username', st.session_state.username).execute()
                    if r.data and len(r.data) > 0:
                        st.session_state.us_stocks = json.loads(r.data[0].get('us_stocks','{}'))
                        st.session_state.hk_stocks = json.loads(r.data[0].get('hk_stocks','{}'))
                        st.success(f"Loaded {len(st.session_state.us_stocks)} US, {len(st.session_state.hk_stocks)} HK!")
                        st.rerun()
                except:
                    st.error("Load failed")
    with col2:
        if st.button("💾 Save"):
            if supabase:
                try:
                    supabase.table('portfolios').update({
                        'us_stocks': json.dumps(st.session_state.us_stocks),
                        'hk_stocks': json.dumps(st.session_state.hk_stocks)
                    }).eq('username', st.session_state.username).execute()
                    st.success("Saved!")
                except:
                    st.error("Save failed")
    with col3:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

    # Sidebar
    st.sidebar.header("⚙️ Add Stocks")
    
    with st.sidebar.form("add_us"):
        t = st.text_input("US Symbol").upper()
        q = st.number_input("Qty", 1, value=1)
        c = st.number_input("Cost (HKD)", 0.01, value=100.0)
        if st.form_submit_button("Add US") and t:
            st.session_state.us_stocks[t] = {"qty": q, "cost": c}
            st.rerun()

    with st.sidebar.form("add_hk"):
        t = st.text_input("HK Symbol").upper()
        q = st.number_input("Qty", 1, value=1)
        c = st.number_input("Cost (HKD)", 0.01, value=100.0)
        if st.form_submit_button("Add HK") and t:
            t = t if t.endswith('.HK') else t + '.HK'
            st.session_state.hk_stocks[t] = {"qty": q, "cost": c}
            st.rerun()

    all_s = {**st.session_state.us_stocks, **st.session_state.hk_stocks}
    if all_s:
        st.sidebar.write("---")
        rem = st.sidebar.selectbox("🗑️ Remove", list(all_s.keys()))
        if st.sidebar.button("Delete"):
            if rem in st.session_state.us_stocks: del st.session_state.us_stocks[rem]
            if rem in st.session_state.hk_stocks: del st.session_state.hk_stocks[rem]
            st.rerun()

    st.sidebar.write("---")
    st.sidebar.write("**Your Holdings:**")
    for t, d in st.session_state.us_stocks.items():
        st.sidebar.write(f"🇺🇸 {t}: {d['qty']} @ ${d['cost']}")
    for t, d in st.session_state.hk_stocks.items():
        st.sidebar.write(f"🇭🇰 {t}: {d['qty']} @ ${d['cost']}")
    if not all_s:
        st.sidebar.info("No stocks")

    # Portfolio with enhanced table
    st.header("💼 Portfolio")
    rows, total_val, total_cost = [], 0, 0
    
    for ticker, d in {**st.session_state.us_stocks, **st.session_state.hk_stocks}.items():
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get company name
            company_name = info.get('longName', info.get('shortName', ticker))
            
            price = stock.history(period="1d")['Close'].iloc[-1]
            if price:
                val = d['qty'] * price
                cost = d['qty'] * d['cost']
                pnl = val - cost
                pct_gain = (pnl / cost) * 100 if cost > 0 else 0
                
                # Calculate RSI for signal
                hist = stock.history(period="3mo")['Close']
                delta = hist.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = (100 - (100 / (1 + rs))).iloc[-1]
                if pd.isna(rsi): rsi = 50
                
                # Signal
                if rsi < 30: signal = "🟢 BUY"
                elif rsi > 70: signal = "🔴 SELL"
                else: signal = "🟡 HOLD"
                
                rows.append({
                    "Symbol": ticker,
                    "Company": company_name[:25] + "..." if len(company_name) > 25 else company_name,
                    "Qty": d['qty'],
                    f"Cost (HKD)": d['cost'],
                    f"Price (HKD)": price,
                    f"Value (HKD)": val,
                    f"P&L (HKD)": pnl,
                    "Gain/Loss %": pct_gain,
                    "RSI": rsi,
                    "Signal": signal
                })
                total_val += val
                total_cost += cost
        except:
            pass

    if rows:
        df = pd.DataFrame(rows)
        
        # Summary
        c1, c2, c3 = st.columns(3)
        pnl = total_val - total_cost
        c1.metric("Total Value", f"HKD {total_val:,.0f}")
        c2.metric("Total Cost", f"HKD {total_cost:,.0f}")
        c3.metric("Total P&L", f"HKD {pnl:,.0f}")
        
        # Enhanced table with color
        def color_gain_loss(val):
            if isinstance(val, (int, float)):
                if val < -15:
                    return 'color: red; font-weight: bold'
            return ''
        
        st.dataframe(
            df.style.format({
                "Cost (HKD)": "HKD {:.2f}",
                "Price (HKD)": "HKD {:.2f}",
                "Value (HKD)": "HKD {:.2f}",
                "P&L (HKD)": "HKD {:.2f}",
                "Gain/Loss %": "{:.1f}%",
                "RSI": "{:.0f}"
            }, subset=["Cost (HKD)", "Price (HKD)", "Value (HKD)", "P&L (HKD)", "Gain/Loss %"]),
            use_container_width=True
        )
        
        # Pie chart
        st.write("---")
        st.subheader("📊 Value Distribution")
        if len(df) > 0:
            fig = pd.DataFrame({
                'Symbol': df['Symbol'],
                'Value': df['Value (HKD)']
            })
            st.pyplot(fig.set_index('Symbol')['Value'].plot.pie(autopct='%1.1f%%', figsize=(8,8)).figure)
    else:
        st.info("Add stocks to see portfolio!")