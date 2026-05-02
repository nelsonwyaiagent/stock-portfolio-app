"""
Stock Portfolio with Transaction Tracking v1.2
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

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

HK_NAMES = {
    "0700.HK": "騰訊控股", "9988.HK": "阿里巴巴", "1810.HK": "小米集團",
    "9618.HK": "京東集團", "1024.HK": "快手科技", "0880.HK": "中國平安",
    "3382.HK": "海爾智家", "6690.HK": "海爾智家", "0005.HK": "匯豐控股",
    "1299.HK": "友邦保險", "0941.HK": "中國移動", "2318.HK": "中國人壽",
}

# Industry classification - HK stocks
STOCK_INDUSTRY = {
    "00002.HK": "UTIL", "00003.HK": "UTIL", "00005.HK": "FIN",
    "00011.HK": "FIN", "00012.HK": "PROP", "00016.HK": "PROP",
    "00175.HK": "CONS", "00992.HK": "HW", "01801.HK": "HLTH",
    "01810.HK": "HW", "02020.HK": "CONS", "02250.HK": "HLTH",
    "02269.HK": "HLTH", "03690.HK": "TECH", "0386.HK": "ENGY",
    "03988.HK": "FIN", "06808.HK": "PROP", "0700.HK": "TECH",
    "0728.HK": "TLCO", "0857.HK": "ENGY", "0883.HK": "ENGY",
    "0941.HK": "TLCO", "09988.HK": "TECH", "1024.HK": "TECH",
    "1109.HK": "ENGY", "1113.HK": "PROP", "1177.HK": "HLTH",
    "1299.HK": "INSR", "1388.HK": "CONS", "1398.HK": "FIN",
    "2318.HK": "INSR", "2319.HK": "TECH", "2388.HK": "FIN",
    "2601.HK": "INSR", "2688.HK": "UTIL", "2888.HK": "FIN",
    "291.HK": "CONS", "3328.HK": "FIN", "3669.HK": "TECH",
    "9618.HK": "TECH", "0386.HK": "ENGY", "0883.HK": "ENGY",
}

def get_last_n_months(n=6):
    """Generate list of (month_end_date, month_label) for last n months"""
    months = []
    for i in range(n-1, -1, -1):
        # Calculate month end date
        if i == 0:
            # Current month - use today
            d = datetime.now()
        else:
            # Go back i months
            from datetime import datetime
            d = datetime.now() - timedelta(days=i*30)
        
        # Get last day of month
        if d.month == 12:
            next_month = datetime(d.year+1, 1, 1)
        else:
            next_month = datetime(d.year, d.month+1, 1)
        month_end = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
        month_label = d.strftime("%m月")
        
        months.append((month_end, month_label))
    return months

def get_name(t):
    return HK_NAMES.get(t, t)

def get_industry(ticker):
    # Normalize ticker format (remove .HK suffix, leading zeros)
    t = ticker.replace(".HK", "").lstrip("0")
    for key, val in STOCK_INDUSTRY.items():
        if key.replace(".HK", "").lstrip("0") == t:
            return val
    return "-"

@st.cache_data(ttl=3600)
def get_exchange_rate():
    """Fetch live USD to HKD exchange rate"""
    try:
        rate = yf.Ticker("USDHKD=X").history(period="1d")['Close'].iloc[-1]
        return rate
    except:
        return 7.82  # Fallback pegged rate

# Get exchange rate at app start
EXCHANGE_RATE = get_exchange_rate()

@st.cache_data(ttl=3600)
def get_stock_data_cached(ticker, period="1y"):
    """Fetch stock data from Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        return df
    except Exception as e:
        return None

# Improved RSI calculation
def calculate_rsi(prices, length=14):
    """Calculate RSI manually"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# Better signal based on RSI
def get_signal(rsi):
    """Generate buy/sell signal based on RSI"""
    if rsi < 30:
        return "🟢 強買", "Strong Buy"
    elif rsi < 40:
        return "🟢 買", "Buy"
    elif rsi > 70:
        return "🔴 強賣", "Strong Sell"
    elif rsi > 60:
        return "🟡 留意", "Watch"
    else:
        return "🟡 持有", "Hold"

# Get weekly change
def get_weekly_change(ticker):
    """Calculate weekly price change"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1w")
        if len(hist) > 1:
            week_start = hist['Close'].iloc[0]
            week_end = hist['Close'].iloc[-1]
            return ((week_end - week_start) / week_start) * 100
    except:
        pass
    return 0

for k in ['logged_in','username','us_stocks','hk_stocks']:
    if k not in st.session_state:
        st.session_state[k] = {} if k in ['us_stocks','hk_stocks'] else False

st.title("📈 股票組合")

# Query param login
query_user = st.query_params.get("user", "")
if query_user:
    st.session_state.username = query_user
    st.session_state.logged_in = True

# Login
if not st.session_state.get('logged_in', False):
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
                    st.rerun()
                except:
                    st.error("Error")

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
                        st.rerun()
                except:
                    pass
    with col2:
        if st.button("💾 儲存"):
            if supabase:
                try:
                    supabase.table('portfolios').update({'us_stocks': json.dumps(st.session_state.us_stocks), 'hk_stocks': json.dumps(st.session_state.hk_stocks)}).eq('username', st.session_state.username).execute()
                    st.success("已儲存!")
                except:
                    pass
    with col3:
        if st.button("登出"):
            st.session_state.logged_in = False
            st.rerun()

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
            if rem in st.session_state.us_stocks:
                del st.session_state.us_stocks[rem]
            if rem in st.session_state.hk_stocks:
                del st.session_state.hk_stocks[rem]
            st.rerun()

    # View mode
    st.sidebar.write("---")
    st.sidebar.markdown("### 📂 頁面")
    # Display exchange rate
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**💱 匯率:** 1 USD = {EXCHANGE_RATE:.4f} HKD")
    
    view_mode = st.sidebar.radio("選擇視圖", ["📈 投資組合", "🗑️ 刪除交易記錄"], index=0)
    delete_mode = view_mode == "🗑️ 刪除交易記錄"

    # Add transaction form
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

    # Transaction records & holdings
    st.header("📋 交易記錄")
    holdings = {}
    tx_list = []
    
    if supabase:
        try:
            # Query HK transactions (existing table)
            r_hk = supabase.table('transactions').select('*').eq('username', st.session_state.username).execute()
            
            # Query US transactions (new table)
            try:
                r_us = supabase.table('us_transactions').select('*').eq('username', st.session_state.username).execute()
            except:
                r_us = type('obj', (object,), {'data': []})()
            
            # Process HK transactions
            if r_hk.data and len(r_hk.data) > 0:
                for row in r_hk.data:
                    sym = row['symbol']
                    try:
                        current_price = yf.Ticker(sym).history(period="1d")['Close'].iloc[-1]
                    except:
                        current_price = None
                    
                    pl_ratio = None
                    price_hkd = row['price']
                    if row['transaction_type'] == 'BUY' and current_price:
                        pl_ratio = ((current_price - price_hkd) / price_hkd) * 100
                    
                    currency = row.get('currency', 'HKD')
                    tx_list.append({
                        'id': row['id'],
                        '股票代號': sym,
                        '公司': get_name(sym),
                        '類型': row['transaction_type'],
                        'currency': currency,
                        '數量': row['quantity'],
                        '成交價': price_hkd,
                        '交易日期': row['transaction_date'],
                        '現價': current_price,
                        '盈虧比率': pl_ratio,
                    })
                    
                    # Holdings
                    price_in_hkd = price_hkd
                    if sym not in holdings:
                        holdings[sym] = {'qty': 0, 'total_buy': 0, 'total_buy_qty': 0, 'currency': currency}
                    
                    if row['transaction_type'] == 'BUY':
                        holdings[sym]['total_buy'] += row['quantity'] * price_in_hkd
                        holdings[sym]['total_buy_qty'] += row['quantity']
                        holdings[sym]['qty'] += row['quantity']
                    else:
                        holdings[sym]['qty'] -= row['quantity']
            
            # Process US transactions
            if r_us.data and len(r_us.data) > 0:
                for row in r_us.data:
                    sym = row['symbol']
                    try:
                        current_price = yf.Ticker(sym).history(period="1d")['Close'].iloc[-1]
                    except:
                        current_price = None
                    
                    pl_ratio = None
                    price_usd = row['price_usd']
                    price_hkd = price_usd * EXCHANGE_RATE
                    
                    if row['transaction_type'] == 'BUY' and current_price:
                        # Compare in HKD
                        current_hkd = current_price * EXCHANGE_RATE
                        pl_ratio = ((current_hkd - price_hkd) / price_hkd) * 100
                    
                    currency = 'USD'
                    tx_list.append({
                        'id': row['id'],
                        '股票代號': sym,
                        '公司': get_name(sym) if get_name(sym) != sym else sym,
                        '類型': row['transaction_type'],
                        'currency': currency,
                        '數量': row['quantity'],
                        '成交價': price_usd,
                        '成交價(HKD)': price_hkd,
                        '交易日期': row['transaction_date'],
                        '現價': current_price,
                        '現價(HKD)': current_price * EXCHANGE_RATE if current_price else None,
                        '盈虧比率': pl_ratio,
                    })
                    
                    # Holdings
                    if sym not in holdings:
                        holdings[sym] = {'qty': 0, 'total_buy': 0, 'total_buy_qty': 0, 'currency': currency}
                    
                    if row['transaction_type'] == 'BUY':
                        holdings[sym]['total_buy'] += row['quantity'] * price_hkd
                        holdings[sym]['total_buy_qty'] += row['quantity']
                        holdings[sym]['qty'] += row['quantity']
                    else:
                        holdings[sym]['qty'] -= row['quantity']
            
            # Avg cost in HKD
            for sym in holdings:
                if holdings[sym]['total_buy_qty'] > 0:
                    holdings[sym]['avg_cost'] = holdings[sym]['total_buy'] / holdings[sym]['total_buy_qty']
                else:
                    holdings[sym]['avg_cost'] = 0
        except Exception as e:
            st.error(f"Error: {e}")

    # Display transactions
    if tx_list:
        display_tx = []
        for row in tx_list:
            curr = row.get('currency', 'HKD')
            price_symbol = "$" if curr == 'USD' else "港幣"
            display_tx.append({
                '股票代號': row['股票代號'],
                '貨幣': curr,
                '類型': row['類型'],
                '數量': row['數量'],
                '成交價': f"{price_symbol}{row['成交價']:.2f}",
                '成交總額': f"{curr} {row['數量'] * row['成交價']:.2f}",
                '交易日期': row['交易日期'],
                '現價': f"{price_symbol}{row['現價']:.2f}" if row['現價'] else "-",
                '現值(HKD)': f"港幣{row['現價']*EXCHANGE_RATE:.2f}" if row['現價'] and curr == 'USD' else "-",
                '盈虧': f"{row['盈虧比率']:.1f}%" if row['盈虧比率'] else "-",
            })
        st.dataframe(display_tx, use_container_width=True)
    
    # Delete mode
    if delete_mode:
        st.header("🗑️ 刪除交易記錄")
        st.write(f"**共 {len(tx_list)} 筆記錄**")
        
        for row in tx_list:
            curr = row.get('currency', 'HKD')
            price_symbol = "$" if curr == 'USD' else "港幣"
            c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([2, 1, 0.8, 1.5, 1.5, 2, 2, 2, 1])
            with c1: st.write(f"**{row['股票代號']}**")
            with c2: st.write(row['類型'])
            with c3: st.write(f"[{curr}]")
            with c4: st.write(f"{price_symbol}{row['成交價']:.2f}")
            with c5: st.write(f"{curr} {row['數量'] * row['成交價']:.2f}")
            with c6: st.write(row['交易日期'])
            with c7: st.write(f"{price_symbol}{row['現價']:.2f}" if row['現價'] else "-")
            with c8: st.write(f"{row['盈虧比率']:.1f}%" if row.get('盈虧比率') else "-")
            with c9:
                if st.button("🗑️", key=f"del_{row['id']}"):
                    try:
                        if curr == 'USD':
                            supabase.table('us_transactions').delete().eq('id', row['id']).execute()
                        else:
                            supabase.table('transactions').delete().eq('id', row['id']).execute()
                        st.success(f"已刪除 {row['股票代號']}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        st.stop()
    else:
        st.markdown("如需刪除記錄，請選擇「🗑️ 刪除交易記錄」")

    # Portfolio display
    st.header("💼 投資組合")
    
    # Separate US and HK holdings
    us_rows, us_total_val, us_total_cost = [], 0, 0
    hk_rows, hk_total_val, hk_total_cost = [], 0, 0
    
    display_holdings = holdings.copy() if holdings else {**st.session_state.us_stocks, **st.session_state.hk_stocks}
    
    for ticker, d in display_holdings.items():
        try:
            qty = d.get('qty', 0)
            if qty and qty > 0:
                cost_hkd = d.get('avg_cost', d.get('cost', 0))
                currency = d.get('currency', 'HKD')
                company = get_name(ticker)
                price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
                if price:
                    # Convert to HKD
                    if currency == 'USD':
                        price_hkd = price * EXCHANGE_RATE
                    else:
                        price_hkd = price
                    
                    val_hkd = qty * price_hkd
                    pnl = val_hkd - (qty * cost_hkd)
                    pct = (pnl/(qty*cost_hkd)*100) if cost_hkd else 0
                    
                    # Calculate weekly change
                    weekly_change = 0
                    try:
                        stock = yf.Ticker(ticker)
                        hist = stock.history(period="1w")
                        if len(hist) > 1:
                            week_start = hist['Close'].iloc[0]
                            week_end = hist['Close'].iloc[-1]
                            weekly_change = ((week_end - week_start) / week_start) * 100
                    except:
                        pass
                    
                    # Calculate RSI
                    hist = yf.Ticker(ticker).history(period="3mo")['Close']
                    delta = hist.diff()
                    gain = delta.where(delta > 0, 0).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / loss
                    rsi = (100 - (100 / (1 + rs))).iloc[-1]
                    if pd.isna(rsi):
                        rsi = 50
                    
                    # Better signal based on RSI and weekly change
                    if rsi < 30:
                        signal = "🟢 強買"
                    elif rsi < 40:
                        signal = "🟢 買"
                    elif rsi > 70:
                        signal = "🔴 強賣"
                    elif rsi > 60:
                        signal = "🟡 留意"
                    else:
                        signal = "🟡 持有"
                    
                    row_data = {
                        "股票代號": ticker,
                        "公司名稱": company,
                        "行業": get_industry(ticker),
                        "貨幣": currency,
                        "數量": qty,
                        "成本": cost_hkd,
                        "現值": val_hkd,
                        "盈虧": pnl,
                        "%": pct,
                        "週變化 %": weekly_change,
                        "RSI": rsi,
                        "信號": signal
                    }
                    
                    # Append to separate list based on currency
                    if currency == 'USD':
                        us_rows.append(row_data)
                        us_total_val += val_hkd
                        us_total_cost += qty * cost_hkd
                    else:
                        hk_rows.append(row_data)
                        hk_total_val += val_hkd
                        hk_total_cost += qty * cost_hkd
        except:
            pass

    # Combined totals
    combined_val = us_total_val + hk_total_val
    combined_cost = us_total_cost + hk_total_cost

    # Display summary
    if us_rows or hk_rows:
        # Combined totals in HKD
        combined_val = us_total_val + hk_total_val
        combined_cost = us_total_cost + hk_total_cost
        grand_total_pnl = combined_val - combined_cost
        grand_total_pnl_percent = (grand_total_pnl / combined_cost * 100) if combined_cost > 0 else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("總值 / Total Value", f"{combined_val:,.0f}")
        c2.metric("總成本 / Total Cost", f"{combined_cost:,.0f}")
        c3.metric("總盈虧 / Total P&L", f"{grand_total_pnl:,.0f}", f"{grand_total_pnl_percent:.1f}%")
        c4.metric("總持股 / Holdings", len(us_rows) + len(hk_rows))
        
        # Display tables - HK first, then US (stacked)
        st.markdown("---")
        st.subheader("📊 Holdings Detail")
        
        # HK Stocks first
        st.markdown("### 🇭🇰 港股 / HK Stocks")
        if hk_rows:
            df_hk = pd.DataFrame(hk_rows)
            st.dataframe(df_hk.style.format({
                "成本": "{:.2f}",
                "現值": "{:.2f}",
                "盈虧": "{:.2f}",
                "%": "{:.1f}%",
                "週變化 %": "{:.1f}%",
                "RSI": "{:.0f}"
            }), use_container_width=True)
        else:
            st.info("無港股數據")
        
        # Then US Stocks
        st.markdown("### 🇺🇸 美股 / US Stocks")
        if us_rows:
            df_us = pd.DataFrame(us_rows)
            st.dataframe(df_us.style.format({
                "成本": "{:.2f}",
                "現值": "{:.2f}",
                "盈虧": "{:.2f}",
                "%": "{:.1f}%",
                "週變化 %": "{:.1f}%",
                "RSI": "{:.0f}"
            }), use_container_width=True)
        else:
            st.info("無美股數據")
        
        # Combine rows for charts
        rows = us_rows + hk_rows
        
        if rows:
            df = pd.DataFrame(rows)
        
        if len(df) > 0:
            # Combined chart data (all in HKD)
            combined_chart_data = []
            for item in rows:
                combined_chart_data.append({
                    "股票代號": item['股票代號'],
                    "Value_HKD": item['現值'],
                    "PnL_HKD": item['盈虧']
                })
            
            chart_df = pd.DataFrame(combined_chart_data)
            
            # Pie chart - Allocation (in HKD)
            fig = px.pie(chart_df, values='Value_HKD', names='股票代號', title='股票組合分配 / Portfolio Allocation', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
            
            # Industry distribution pie chart
            industry_df = df.groupby('行業')['現值'].sum().reset_index()
            if len(industry_df) > 0:
                fig2 = px.pie(industry_df, values='現值', names='行業', title='行業分布 / Industry Allocation', hole=0.4)
                st.plotly_chart(fig2, use_container_width=True)
        
        st.write("---")
        st.subheader("📊 各股票盈虧 / P&L by Stock")
        
        if len(df) > 0:
            fig_bar = px.bar(df, x='股票代號', y='盈虧', title='各股票盈虧 / P&L by Stock',
                           color='盈虧', color_continuous_scale='RdYlGn')
            fig_bar.update_traces(marker=dict(color=[ 'red' if x < 0 else 'green' for x in df['%']]))
            fig_bar.add_hline(y=-10, line_dash="dash", line_color="orange", annotation_text="Loss 10%")
            fig_bar.add_hline(y=-15, line_dash="dot", line_color="red", annotation_text="Loss 15%")
            fig_bar.add_hline(y=-20, line_dash="dot", line_color="darkred", annotation_text="Loss 20%")
            fig_bar.add_hline(y=10, line_dash="dash", line_color="lightgreen", annotation_text="Gain 10%")
            fig_bar.add_hline(y=20, line_dash="dot", line_color="green", annotation_text="Gain 20%")
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # P/L in percentage chart
        if len(df) > 0:
            fig_pct = px.bar(df, x='股票代號', y='%', title='各股票盈虧 / P&L by Stock (%)',
                           color='%', color_continuous_scale='RdYlGn')
            fig_pct.update_traces(marker=dict(color=[ 'red' if x < 0 else 'green' for x in df['%']]))
            fig_pct.add_hline(y=-10, line_dash="dash", line_color="orange", annotation_text="Loss 10%")
            fig_pct.add_hline(y=-15, line_dash="dot", line_color="red", annotation_text="Loss 15%")
            fig_pct.add_hline(y=-20, line_dash="dot", line_color="darkred", annotation_text="Loss 20%")
            fig_pct.add_hline(y=10, line_dash="dash", line_color="lightgreen", annotation_text="Gain 10%")
            fig_pct.add_hline(y=20, line_dash="dot", line_color="green", annotation_text="Gain 20%")
            st.plotly_chart(fig_pct, use_container_width=True)
    else:
        st.info("添加股票或交易記錄來查看組合!")

    # Monthly historical

# ===== TECHNICAL ANALYSIS =====
# Check if holdings exist - default to empty list if not defined
try:
    us_tickers = us_rows if 'us_rows' in globals() else []
except:
    us_tickers = []
try:
    hk_tickers = hk_rows if 'hk_rows' in globals() else []
except:
    hk_tickers = []
    
all_tickers = [h["股票代號"] for h in us_tickers] + [h["股票代號"] for h in hk_tickers]

if all_tickers:
    selected_stock = st.selectbox("Select Stock to Analyze", all_tickers)
    
    if selected_stock:
        df = get_stock_data_cached(selected_stock)
        if df is not None:
            # Calculate RSI
            df['RSI'] = calculate_rsi(df['Close'])
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Price chart
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df.index,
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    name='Price'
                ))
                fig.update_layout(title=f"{selected_stock} Price", height=300)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # RSI Chart
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='purple', width=2)))
                fig2.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought")
                fig2.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold")
                fig2.update_layout(title="RSI (14)", height=300, yaxis_range=[0, 100])
                st.plotly_chart(fig2, use_container_width=True)
    st.header("📊 每月價值明細 / Monthly Value")
    months = get_last_n_months(6)
    
    hist_rows = []
    for ticker, d in display_holdings.items():
        if isinstance(d, dict) and d.get('qty', 0) > 0:
            try:
                company = get_name(ticker)
                current_price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
                current_val = d['qty'] * current_price
                cost = d.get('avg_cost', d.get('cost', 0))
                
                row = {"股票代號": ticker, "公司名稱": company, "數量": d['qty'], "現值": round(current_val)}
                
                for month_end, label in months:
                    try:
                        hist = yf.Ticker(ticker).history(start="2025-07-01", end=month_end)
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
            except:
                pass
    
    if hist_rows:
        hist_df = pd.DataFrame(hist_rows)
        fmt = {}
        for col in hist_df.columns:
            if "value" in col.lower():
                fmt[col] = "{:,.0f}"
            elif "%" in col:
                fmt[col] = "{:.1f}%"
        st.dataframe(hist_df.style.format(fmt), use_container_width=True)
        
        total_by_month = {}
        for month_end, label in months:
            total = 0
            for ticker, d in display_holdings.items():
                if isinstance(d, dict) and d.get('qty', 0) > 0:
                    try:
                        stock = yf.Ticker(ticker)
                        hist = stock.history(start="2025-07-01", end=month_end)
                        if not hist.empty:
                            total += d['qty'] * hist['Close'].iloc[-1]
                    except:
                        pass
            total_by_month[label] = total
        
        chart_df = pd.DataFrame(list(total_by_month.items()), columns=["月份", "總值"])
        fig_line = px.line(chart_df, x='月份', y='總值', title='組合價值趨勢 / Portfolio Trend', markers=True)
        st.plotly_chart(fig_line, use_container_width=True)