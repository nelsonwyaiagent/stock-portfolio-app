"""
Stock Portfolio with Transaction Tracking v1.1
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import plotly.express as px
from datetime import datetime, date

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

# HK stock Chinese names
HK_NAMES = {
    "0700.HK": "騰訊控股", "9988.HK": "阿里巴巴", "1810.HK": "小米集團",
    "9618.HK": "京東集團", "1024.HK": "快手科技", "0880.HK": "中國平安",
    "3382.HK": "海爾智家", "6690.HK": "海爾智家", "0005.HK": "匯豐控股",
    "1299.HK": "友邦保險", "0941.HK": "中國移動", "2318.HK": "中國人壽",
}

def get_name(t):
    return HK_NAMES.get(t, t)

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
                except: st.error("Error")

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

    # ===== TRANSACTION INPUT =====
    st.header("📝 新增交易")
    
    with st.form("add_transaction"):
        c1, c2 = st.columns(2)
        with c1:
            sym = st.text_input("股票代號").upper()
            ttype = st.selectbox("交易類型", ["BUY", "SELL"])
            qty = st.number_input("數量", min_value=1, value=1)
        with c2:
            price = st.number_input("成交價 (港幣)", min_value=0.01, value=100.0)
            tdate = st.date_input("交易日期", date.today())
            notes = st.text_input("備註 (可選)")
        
        if st.form_submit_button("➕ 新增交易") and sym and qty > 0:
            sym = sym if sym.endswith('.HK') or not sym.isalpha() else sym
            if supabase:
                try:
                    supabase.table('transactions').insert({
                        'username': st.session_state.username,
                        'symbol': sym,
                        'transaction_type': ttype,
                        'quantity': qty,
                        'price': price,
                        'transaction_date': str(tdate),
                        'notes': notes or None
                    }).execute()
                    st.success(f"已添加 {ttype} {sym}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # ===== TRANSACTION HISTORY =====
    st.header("📋 交易記錄 (按股票代號排序)")
    
    if supabase:
        try:
            r = supabase.table('transactions').select('*').eq('username', st.session_state.username).execute()
            if r.data and len(r.data) > 0:
                tx_data = []
                for row in r.data:
                    sym = row['symbol']
                    try:
                        current_price = yf.Ticker(sym).history(period="1d")['Close'].iloc[-1]
                    except:
                        current_price = None
                    
                    pl_ratio = None
                    if row['transaction_type'] == 'BUY' and current_price:
                        pl_ratio = ((current_price - row['price']) / row['price']) * 100
                    
                    tx_data.append({
                        '股票代號': sym,
                        '公司': get_name(sym),
                        '類型': row['transaction_type'],
                        '數量': row['quantity'],
                        '成交價': row['price'],
                        '交易日期': row['transaction_date'],
                        '現價': current_price,
                        '盈虧比率': pl_ratio,
                        '備註': row.get('notes', '')
                    })
                
                df_tx = pd.DataFrame(tx_data)
                # Sort by symbol, then by date descending
                df_tx = df_tx.sort_values(['股票代號', '交易日期'], ascending=[True, False])
                
                # Display
                st.dataframe(df_tx.style.format({
                    '成交價': '{:.2f}',
                    '現價': '{:.2f}' if df_tx['現價'].notna().any() else '{}',
                    '盈虧比率': '{:.1f}%' if df_tx['盈虧比率'].notna().any() else '{}'
                }).applymap(lambda x: 'color: green; font-weight: bold' if isinstance(x, (int, float)) and x > 0 else ('color: red' if isinstance(x, (int, float)) and x < 0 else ''), subset=['盈虧比率']), use_container_width=True)
                
                # Calculate holdings from transactions
                holdings = {}
                for _, row in df_tx.iterrows():
                    sym = row['股票代號']
                    if sym not in holdings:
                        holdings[sym] = {'qty': 0, 'total_cost': 0}
                    
                    if row['類型'] == 'BUY':
                        holdings[sym]['qty'] += row['數量']
                        holdings[sym]['total_cost'] += row['數量'] * row['成交價']
                    else:  # SELL
                        holdings[sym]['qty'] -= row['數量']
                
                # Convert to session state format
                us_h = {}
                hk_h = {}
                for sym, d in holdings.items():
                    if d['qty'] > 0:
                        avg_cost = d['total_cost'] / (d['qty'] + sum([h['qty'] for h in holdings.values() if h != d]))
                        # Calculate proper avg cost
                        buy_total = 0
                        buy_qty = 0
                        for _, r2 in df_tx[(df_tx['股票代號']==sym) & (df_tx['類型']=='BUY')].iterrows():
                            buy_total += r2['數量'] * r2['成交價']
                            buy_qty += r2['數量']
                        avg_cost = buy_total / buy_qty if buy_qty > 0 else 0
                        
                        if sym.endswith('.HK'):
                            hk_h[sym] = {'qty': d['qty'], 'cost': avg_cost}
                        else:
                            us_h[sym] = {'qty': d['qty'], 'cost': avg_cost}
                
                st.session_state.us_stocks = us_h
                st.session_state.hk_stocks = hk_h
        except Exception as e:
            st.error(f"Error loading: {e}")

    # ===== PORTFOLIO =====
    # Use holdings from transaction calculation
    st.header("💼 投資組合 (現在)")
    
    rows, total_val, total_cost = [], 0, 0
    
    all_holdings = {**st.session_state.us_stocks, **st.session_state.hk_stocks}
    
    for ticker, d in all_holdings.items():
        try:
            company = get_name(ticker)
            price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            if price:
                val = d['qty'] * price
                cost = d['qty'] * d['cost']
                pnl = val - cost
                pct = (pnl/cost*100) if cost else 0
                
                hist = yf.Ticker(ticker).history(period="3mo")['Close']
                delta = hist.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = (100 - (100 / (1 + gain/loss))).iloc[-1]
                if pd.isna(rsi): rsi = 50
                
                signal = "🟢 買入" if rsi < 30 else ("🔴 賣出" if rsi > 70 else "🟡 持有")
                
                rows.append({"股票代號": ticker, "公司名稱": company, "數量": d['qty'], 
                           "成本 (港幣)": d['cost'], "現價 (港幣)": price, "現值 (港幣)": val, 
                           "盈虧 (港幣)": pnl, "%": pct, "RSI": rsi, "信號": signal})
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