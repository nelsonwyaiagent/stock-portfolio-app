"""
Stock Portfolio - Chinese Company Names
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

st.title("📈 股票組合")

# Login
if not st.session_state.logged_in:
    st.header("🔐 登入")
    with st.form("login"):
        user = st.text_input("用戶名")
        if st.form_submit_button("登入"):
            if user and supabase:
                try:
                    r = supabase.table('portfolios').select('us_stocks','hk_stocks').eq('username', user).execute()
                    if r.data and len(r.data) > 0:
                        st.session_state.us_stocks = json.loads(r.data[0].get('us_stocks','{}'))
                        st.session_state.hk_stocks = json.loads(r.data[0].get('hk_stocks','{}'))
                    st.session_state.username = user
                    st.session_state.logged_in = True
                    st.success("已載入!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

else:
    st.write(f"**👤 {st.session_state.username}**")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📥 載入"):
            if supabase:
                try:
                    r = supabase.table('portfolios').select('us_stocks','hk_stocks').eq('username', st.session_state.username).execute()
                    if r.data and len(r.data) > 0:
                        st.session_state.us_stocks = json.loads(r.data[0].get('us_stocks','{}'))
                        st.session_state.hk_stocks = json.loads(r.data[0].get('hk_stocks','{}'))
                        st.success("已載入!")
                        st.rerun()
                except: pass
    with col2:
        if st.button("💾 儲存"):
            if supabase:
                try:
                    supabase.table('portfolios').update({'us_stocks': json.dumps(st.session_state.us_stocks), 'hk_stocks': json.dumps(st.session_state.hk_stocks)}).eq('username', st.session_state.username).execute()
                    st.success("已儲存!")
                except: pass
    with col3:
        if st.button("登出"): st.session_state.logged_in = False; st.rerun()

    # Sidebar
    st.sidebar.header("⚙️ 添加股票")
    with st.sidebar.form("add_us"):
        t = st.text_input("美股").upper()
        q = st.number_input("數量", 1, value=1)
        c = st.number_input("成本", 0.01, value=100.0)
        if st.form_submit_button("添加") and t:
            st.session_state.us_stocks[t] = {"qty": q, "cost": c}
            st.rerun()
    with st.sidebar.form("add_hk"):
        t = st.text_input("港股").upper()
        q = st.number_input("數量", 1, value=1)
        c = st.number_input("成本", 0.01, value=100.0)
        if st.form_submit_button("添加") and t:
            t = t if t.endswith('.HK') else t + '.HK'
            st.session_state.hk_stocks[t] = {"qty": q, "cost": c}
            st.rerun()

    all_s = {**st.session_state.us_stocks, **st.session_state.hk_stocks}
    if all_s:
        st.sidebar.write("---")
        rem = st.sidebar.selectbox("移除", list(all_s.keys()))
        if st.sidebar.button("刪除"):
            if rem in st.session_state.us_stocks: del st.session_state.us_stocks[rem]
            if rem in st.session_state.hk_stocks: del st.session_state.hk_stocks[rem]
            st.rerun()

    st.sidebar.write("**持股:**")
    for t, d in st.session_state.us_stocks.items(): st.sidebar.write(f"📈 {t}: {d['qty']}")
    for t, d in st.session_state.hk_stocks.items(): st.sidebar.write(f"📈 {t}: {d['qty']}")

    # Current Portfolio
    st.header("💼 投資組合 (現在)")
    rows, total_val, total_cost = [], 0, 0
    
    for ticker, d in {**st.session_state.us_stocks, **st.session_state.hk_stocks}.items():
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # For HK stocks, try to get Chinese name
            company = info.get('longName', info.get('shortName', ticker))[:25]
            
            price = stock.history(period="1d")['Close'].iloc[-1]
            if price:
                val = d['qty'] * price
                cost = d['qty'] * d['cost']
                pnl = val - cost
                pct = (pnl/cost*100) if cost else 0
                
                hist = stock.history(period="3mo")['Close']
                delta = hist.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi_val = (100 - (100 / (1 + rs))).iloc[-1]
                if pd.isna(rsi_val): rsi_val = 50
                
                signal = "🟢 買入" if rsi_val < 30 else ("🔴 賣出" if rsi_val > 70 else "🟡 持有")
                
                rows.append({"股票代號": ticker, "公司名稱": company, "數量": d['qty'], 
                           "成本 (港幣)": d['cost'], "現價 (港幣)": price, "現值 (港幣)": val, 
                           "盈虧 (港幣)": pnl, "%": pct, "RSI": rsi_val, "信號": signal})
                total_val += val
                total_cost += cost
        except: pass

    if rows:
        df = pd.DataFrame(rows)
        c1,c2,c3 = st.columns(3)
        c1.metric("總值", f"港幣 {total_val:,.0f}")
        c2.metric("總成本", f"港幣 {total_cost:,.0f}")
        c3.metric("總盈虧", f"港幣 {total_val-total_cost:,.0f}")
        
        st.dataframe(df.style.format({
            "成本 (港幣)": "{:.2f}", "現價 (港幣)": "{:.2f}", "現值 (港幣)": "{:.2f}", 
            "盈虧 (港幣)": "{:.2f}", "%": "{:.1f}%", "RSI": "{:.0f}"
        }), use_container_width=True)
        
        if len(df) > 0:
            fig = px.pie(df, values='現值 (港幣)', names='股票代號', title='組合分配', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

    # Historical Breakdown
    st.header("📊 每月價值明細 (2026)")
    
    months = [("2026-01-31", "1月"), ("2026-02-28", "2月"), ("2026-03-31", "3月"), ("2026-04-30", "4月")]
    
    hist_rows = []
    for ticker, d in {**st.session_state.us_stocks, **st.session_state.hk_stocks}.items():
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            company = info.get('longName', info.get('shortName', ticker))[:20]
            
            current_price = stock.history(period="1d")['Close'].iloc[-1]
            current_val = d['qty'] * current_price
            
            row = {"股票代號": ticker, "公司名稱": company, "數量": d['qty'], "現值 (港幣)": current_val}
            
            for month_end, label in months:
                try:
                    hist = stock.history(start="2026-01-01", end=month_end)
                    if not hist.empty:
                        month_price = hist['Close'].iloc[-1]
                        month_val = d['qty'] * month_price
                        cost_val = d['qty'] * d['cost']
                        pct_inc = ((month_val - cost_val) / cost_val * 100) if cost_val else 0
                        row[f"{label} value"] = month_val
                        row[f"{label} %"] = pct_inc
                    else:
                        row[f"{label} value"] = 0
                        row[f"{label} %"] = 0
                except:
                    row[f"{label} value"] = 0
                    row[f"{label} %"] = 0
            
            hist_rows.append(row)
        except:
            pass
    
    if hist_rows:
        hist_df = pd.DataFrame(hist_rows)
        fmt_dict = {}
        for col in hist_df.columns:
            if "value" in col.lower():
                fmt_dict[col] = "港幣 {:,.0f}"
            elif "%" in col:
                fmt_dict[col] = "{:.1f}%"
        
        st.dataframe(hist_df.style.format(fmt_dict), use_container_width=True)
        
        # Line chart
        total_by_month = {}
        for month_end, label in months:
            total = 0
            for ticker, d in {**st.session_state.us_stocks, **st.session_state.hk_stocks}.items():
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(start="2026-01-01", end=month_end)
                    if not hist.empty:
                        total += d['qty'] * hist['Close'].iloc[-1]
                except:
                    pass
            total_by_month[label] = total
        
        chart_df = pd.DataFrame(list(total_by_month.items()), columns=["月份", "總值 (港幣)"])
        fig_line = px.line(chart_df, x='月份', y='總值 (港幣)', title='組合價值趨勢', markers=True)
        st.plotly_chart(fig_line, use_container_width=True)