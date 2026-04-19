"""
Stock Portfolio with Transaction Tracking v1.1 - Fixed Average Cost
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

    # ===== SIDEBAR =====
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
            sym = sym if (sym.endswith('.HK') or not sym.isalpha()) else sym
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

    # ===== TRANSACTION HISTORY & HOLDINGS CALCULATION =====
    st.header("📋 交易記錄")
    
    # Calculate holdings from transactions
    holdings = {}
    
    if supabase:
        try:
            r = supabase.table('transactions').select('*').eq('username', st.session_state.username).execute()
            if r.data and len(r.data) > 0:
                tx_list = []
                for row in r.data:
                    sym = row['symbol']
                    try:
                        current_price = yf.Ticker(sym).history(period="1d")['Close'].iloc[-1]
                    except:
                        current_price = None
                    
                    pl_ratio = None
                    if row['transaction_type'] == 'BUY' and current_price:
                        pl_ratio = ((current_price - row['price']) / row['price']) * 100
                    
                    tx_list.append({
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
                    
                    # Calculate holdings
                    if sym not in holdings:
                        holdings[sym] = {'qty': 0, 'total_buy': 0, 'total_buy_qty': 0}
                    
                    if row['transaction_type'] == 'BUY':
                        holdings[sym]['total_buy'] += row['quantity'] * row['price']
                        holdings[sym]['total_buy_qty'] += row['quantity']
                        holdings[sym]['qty'] += row['quantity']
                    else:  # SELL
                        holdings[sym]['qty'] -= row['quantity']
                
                # Calculate average cost for remaining holdings
                for sym in holdings:
                    if holdings[sym]['total_buy_qty'] > 0:
                        holdings[sym]['avg_cost'] = holdings[sym]['total_buy'] / holdings[sym]['total_buy_qty']
                    else:
                        holdings[sym]['avg_cost'] = 0
                
                # Display transactions using st.dataframe for proper alignment
                st.markdown("**📋 交易記錄**")
                
                # Create dataframe first
                df_tx = pd.DataFrame(tx_list)
                df_tx = df_tx.sort_values(['股票代號', '交易日期'], ascending=[True, False])
                df_tx = df_tx.reset_index(drop=True)
                
                # Prepare display data with action column
                display_tx = []
                for i, row in df_tx.iterrows():
                    display_tx.append({
                        '股票代號': row['股票代號'],
                        '類型': row['類型'],
                        '數量': row['數量'],
                        '成交價': f"${row['成交價']:.2f}",
                        '交易日期': row['交易日期'],
                        '現價': f"${row['現價']:.2f}" if row['現價'] else "-",
                        '盈虧': f"{row['盈虧比率']:.1f}%" if row['盈虧比率'] else "-",
                        '操作': 'X'
                    })
                
                if display_tx:
                    st.dataframe(display_tx, use_container_width=True)
                
                # Delete buttons below
                st.write("**刪除記錄:**")
                for i, row in df_tx.iterrows():
                    c1, c2 = st.columns([4, 1])
                    with c1: st.write(f"刪除 {row['股票代號']} - {row['交易日期']}")
                    with c2:
                        if st.button("X", key=f"del_{i}"):
                            try:
                                if i < len(r.data):
                                    tx_id = r.data[i].get('id')
                                    if tx_id:
                                        supabase.table('transactions').delete().eq('id', tx_id).execute()
                                        st.success(f"Deleted {row['股票代號']}")
                                        st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
        except Exception as e:
            st.error(f"Error: {e}")

    # ===== PORTFOLIO =====
    st.header("💼 投資組合")
    
    rows, total_val, total_cost = [], 0, 0
    
    # Use holdings from transactions
    display_holdings = holdings.copy() if holdings else {**st.session_state.us_stocks, **st.session_state.hk_stocks}
    
    for ticker, d in display_holdings.items():
        try:
            qty = d.get('qty', 0)
            if qty and qty > 0:
                # Use avg_cost from transaction calculation, fallback to session cost
                cost = d.get('avg_cost', d.get('cost', 0))
                
                company = get_name(ticker)
                price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
                if price:
                    val = qty * price
                    total = qty * cost
                    pnl = val - total
                    pct = (pnl/total*100) if total else 0
                    
                    hist = yf.Ticker(ticker).history(period="3mo")['Close']
                    delta = hist.diff()
                    gain = delta.where(delta > 0, 0).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rsi = (100 - (100 / (1 + gain/loss))).iloc[-1]
                    if pd.isna(rsi): rsi = 50
                    
                    signal = "🟢 買入" if rsi < 30 else ("🔴 賣出" if rsi > 70 else "🟡 持有")
                    
                    rows.append({"股票代號": ticker, "公司名稱": company, "數量": qty, 
                               "成本 (港幣)": cost, "現價 (港幣)": price, "現值 (港幣)": val, 
                               "盈虧 (港幣)": pnl, "%": pct, "RSI": rsi, "信號": signal})
                    total_val += val
                    total_cost += total
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
        
        # P&L Bar
        st.write("---")
        st.subheader("📊 各股票盈虧")
        if len(df) > 0:
            fig_bar = px.bar(df, x='股票代號', y='%', title='股票盈虧 (%)', 
                           color='%', color_continuous_scale='RdYlGn')
            fig_bar.update_traces(marker=dict(color=[ 'red' if x < 0 else 'green' for x in df['%']]))
            fig_bar.add_hline(y=-10, line_dash="dash", line_color="orange", annotation_text="Loss 10%")
            fig_bar.add_hline(y=-15, line_dash="dot", line_color="red", annotation_text="Loss 15%")
            fig_bar.add_hline(y=-20, line_dash="dot", line_color="darkred", annotation_text="Loss 20%")
            fig_bar.add_hline(y=10, line_dash="dash", line_color="lightgreen", annotation_text="Gain 10%")
            fig_bar.add_hline(y=20, line_dash="dot", line_color="green", annotation_text="Gain 20%")
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("添加交易記錄來查看組合!")

    # ===== HISTORICAL =====
    st.header("📊 每月價值明細")
    months = [("2026-01-31", "1月"), ("2026-02-28", "2月"), ("2026-03-31", "3月"), ("2026-04-30", "4月")]
    
    hist_rows = []
    for ticker, d in display_holdings.items():
        if isinstance(d, dict) and d.get('qty', 0) > 0:
            try:
                company = get_name(ticker)
                current_price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
                current_val = d['qty'] * current_price
                cost = d.get('avg_cost', d.get('cost', 0))
                
                row = {"股票代號": ticker, "公司名稱": company, "數量": d['qty'], "現值 (港幣)": round(current_val)}
                
                for month_end, label in months:
                    try:
                        hist = yf.Ticker(ticker).history(start="2026-01-01", end=month_end)
                        if not hist.empty:
                            month_price = hist['Close'].iloc[-1]
                            month_val = d['qty'] * month_price
                            cost_val = d['qty'] * cost
                            pct_inc = ((month_val - cost_val) / cost_val * 100) if cost_val else 0
                            row[f"{label} value"] = round(month_val)
                            row[f"{label} %"] = pct_inc
                        else:
                            row[f"{label} value"] = 0
                            row[f"{label} %"] = 0
                    except:
                        row[f"{label} value"] = 0
                        row[f"{label} %"] = 0
                
                hist_rows.append(row)
            except: pass
    
    if hist_rows:
        hist_df = pd.DataFrame(hist_rows)
        fmt = {}
        for col in hist_df.columns:
            if "value" in col.lower(): fmt[col] = "港幣 {:,.0f}"
            elif "%" in col: fmt[col] = "{:.1f}%"
        st.dataframe(hist_df.style.format(fmt), use_container_width=True)
        
        total_by_month = {}
        for month_end, label in months:
            total = 0
            for ticker, d in display_holdings.items():
                if isinstance(d, dict) and d.get('qty', 0) > 0:
                    try:
                        stock = yf.Ticker(ticker)
                        hist = stock.history(start="2026-01-01", end=month_end)
                        if not hist.empty:
                            total += d['qty'] * hist['Close'].iloc[-1]
                    except: pass
            total_by_month[label] = total
        
        chart_df = pd.DataFrame(list(total_by_month.items()), columns=["月份", "總值 (港幣)"])
        fig_line = px.line(chart_df, x='月份', y='總值 (港幣)', title='組合價值趨勢', markers=True)
        st.plotly_chart(fig_line, use_container_width=True)