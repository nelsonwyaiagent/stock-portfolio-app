"""
Stock Portfolio with Transaction Tracking v1.2
"""
import streamlit as st

st.set_page_config(page_title="股票組合", page_icon="📈", layout="wide")

import yfinance as yf
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

from portfolio_display import build_pnl_chart_frame, rsi_signal_labels
from portfolio_dividends import apply_ytd, hong_kong_today
from portfolio_ui import (
    collect_dividend_report,
    format_money,
    render_balance,
    render_compact_holdings,
    render_contributors,
    render_dividend_income,
    render_dividend_leaders,
    render_metric_tiles,
    security_profile,
    ytd_metric,
)

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

def get_name(ticker):
    """Display name. Local overrides and Yahoo; does not write portfolio data."""
    return security_profile(ticker)["name"]

def get_last_n_months(n=6):
    """Generate list of (month_end_date, month_label) for last n months"""
    months = []
    for i in range(n-1, -1, -1):
        # Calculate month end date
        if i == 0:
            # Current month - use TODAY (not end of month) since future has no data
            d = datetime.now()
            month_end = d.strftime("%Y-%m-%d")
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

@st.cache_data(ttl=3600)
def get_stock_metrics(ticker):
    """Fetch comprehensive stock metrics from Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Get metrics with fallbacks
        metrics = {
            'price': info.get('currentPrice'),
            'pe': info.get('trailingPE'),
            'forward_pe': info.get('forwardPE'),
            'pb_ratio': info.get('priceToBookRaw'),
            'beta': info.get('beta'),
            'dividend_yield': info.get('dividendYield'),  # Simple key that works
            'dividend_rate': info.get('dividendRate'),    # Annual rate
            'dividend_five_year': info.get('dividendFiveYearAverage'),
            'yield': info.get('yield'),
            'book_value': info.get('bookValue', 0),
            '52w_low': info.get('fiftyTwoWeekLow'),
            '52w_high': info.get('fiftyTwoWeekHigh'),
            'market_cap': info.get('marketCap'),
            'eps': info.get('trailingEPS'),
            'profit_margin': info.get('profitMargins'),
            'roe': info.get('returnOnEquity'),
        }
        
        # Calculate volatility
        if metrics['52w_low'] and metrics['52w_high'] and metrics['52w_low'] > 0:
            metrics['volatility'] = ((metrics['52w_high'] - metrics['52w_low']) / metrics['52w_low']) * 100
        else:
            metrics['volatility'] = None
            
        return metrics
    except Exception as e:
        return None

@st.cache_data(ttl=3600)
def get_90day_price(ticker):
    """Get 90-day price data"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d")
        if len(hist) > 0:
            current = hist['Close'].iloc[-1]
            highest = hist['Close'].max()
            drop_pct = ((highest - current) / highest) * 100 if highest > 0 else 0
            return {
                'current': current,
                'highest': highest,
                'drop_pct': drop_pct,
                'signal': '🟢 買入' if drop_pct >= 20 else ('🟡 留意' if drop_pct >= 10 else '🔴 持有')
            }
    except:
        pass
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
    """Existing RSI labels. Used by the research section, not the holdings table."""
    return rsi_signal_labels(rsi)

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
                    # Test connection first
                    r_test = supabase.table('portfolios').select('us_stocks').limit(1).execute()
                    
                    # Then get user data
                    r = supabase.table('portfolios').select('us_stocks','hk_stocks').eq('username', user).execute()
                    if r.data and len(r.data) > 0:
                        st.session_state.us_stocks = json.loads(r.data[0].get('us_stocks','{}'))
                        st.session_state.hk_stocks = json.loads(r.data[0].get('hk_stocks','{}'))
                    else:
                        # New user - initialize empty
                        st.session_state.us_stocks = {}
                        st.session_state.hk_stocks = {}
                    st.session_state.username = user
                    st.session_state.logged_in = True
                    st.rerun()
                except Exception as e:
                    st.error(f"連接錯誤，請重試 / Connection error, please try again")

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
    ledger = []
    
    if supabase:
        try:
            # Query HK transactions only
            r_hk = supabase.table('transactions').select('*').eq('username', st.session_state.username).execute()
            
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
                    
                    current_value = current_price * row['quantity'] if current_price else None
                    
                    tx_list.append({
                        'id': row['id'],
                        '股票代號': sym,
                        '公司': get_name(sym),
                        '類型': row['transaction_type'],
                        '數量': row['quantity'],
                        '成交價': price_hkd,
                        '成交總額': row['quantity'] * price_hkd,
                        '交易日期': row['transaction_date'],
                        '現價': current_price,
                        '現值': current_value,
                        '盈虧比率': pl_ratio,
                    })
                    
                    # Holdings
                    if sym not in holdings:
                        holdings[sym] = {'qty': 0, 'total_buy': 0, 'total_buy_qty': 0}
                    
                    if row['transaction_type'] == 'BUY':
                        holdings[sym]['total_buy'] += row['quantity'] * price_hkd
                        holdings[sym]['total_buy_qty'] += row['quantity']
                        holdings[sym]['qty'] += row['quantity']
                    else:
                        holdings[sym]['qty'] -= row['quantity']
                    ledger.append({
                        "symbol": sym,
                        "transaction_type": row["transaction_type"],
                        "quantity": row["quantity"],
                        "transaction_date": row["transaction_date"],
                    })
            
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
                '公司': row['公司'],
                '貨幣': curr,
                '類型': row['類型'],
                '數量': row['數量'],
                '成交價': f"{price_symbol}{row['成交價']:.2f}",
                '成交總額': f"{curr} {row['數量'] * row['成交價']:.2f}",
                '交易日期': row['交易日期'],
                '現價': f"{price_symbol}{row['現價']:.2f}" if row['現價'] else "-",
                '現值': f"{price_symbol}{(row['現價'] or 0) * row['數量']:.2f}" if row['現價'] else "-",
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
                profile = security_profile(ticker)
                company = profile["name"]
                price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
                if price:
                    # Convert to HKD. Position P&L uses the existing average-cost formula.
                    if currency == 'USD':
                        price_hkd = price * EXCHANGE_RATE
                    else:
                        price_hkd = price

                    val_hkd = qty * price_hkd
                    pnl = val_hkd - (qty * cost_hkd)
                    pct = (pnl/(qty*cost_hkd)*100) if cost_hkd else 0

                    row_data = {
                        "ticker": ticker,
                        "name": company,
                        "market": "US" if currency == "USD" else "HK",
                        "industry_code": profile["industry_code"],
                        "industry_label": profile["industry_label"],
                        "cost_total": qty * cost_hkd,
                        "market_value": val_hkd,
                        "pnl": pnl,
                        "pnl_pct": pct,
                        "股票代號": ticker,
                        "公司名稱": company,
                        "行業": profile["industry_label"],
                        "貨幣": currency,
                        "數量": qty,
                        "成本": cost_hkd,
                        "現值": val_hkd,
                        "盈虧": pnl,
                        "%": pct,
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

    dividend_names = {}
    dividend_currencies = {}
    for row in hk_rows + us_rows:
        dividend_names[row["ticker"]] = row["name"]
        dividend_currencies[row["ticker"]] = row.get("貨幣") or "HKD"
    for tx in ledger:
        sym = str(tx.get("symbol") or "").strip().upper()
        if sym and sym not in dividend_names:
            dividend_names[sym] = security_profile(sym)["name"]
    if ledger:
        with st.spinner("正在估算今年股息…"):
            dividend_report = collect_dividend_report(
                ledger,
                dividend_names,
                today=hong_kong_today(),
                default_currency="HKD",
                report_currency="HKD",
                spot_fx=EXCHANGE_RATE,
                currency_by_symbol=dividend_currencies,
            )
    else:
        dividend_report = collect_dividend_report(
            ledger,
            dividend_names,
            today=hong_kong_today(),
            default_currency="HKD",
            report_currency="HKD",
            spot_fx=EXCHANGE_RATE,
            currency_by_symbol=dividend_currencies,
        )
    apply_ytd(hk_rows, dividend_report)
    apply_ytd(us_rows, dividend_report)

    # Display summary. Open holdings and sold names that still paid this year.
    has_holdings = bool(us_rows or hk_rows)
    if has_holdings or dividend_report.get("rows"):
        # Combined totals in HKD
        combined_val = us_total_val + hk_total_val
        combined_cost = us_total_cost + hk_total_cost
        grand_total_pnl = combined_val - combined_cost
        grand_total_pnl_percent = (grand_total_pnl / combined_cost * 100) if combined_cost > 0 else 0

        pnl_tone = "neg" if grand_total_pnl < 0 else "pos" if grand_total_pnl > 0 else "neutral"
        render_metric_tiles([
            {
                "label": "總值 / Total Value",
                "value": format_money(combined_val, "HKD"),
                "sub": "港幣 / HKD",
            },
            {
                "label": "總成本 / Total Cost",
                "value": format_money(combined_cost, "HKD"),
                "sub": "港幣 / HKD",
            },
            {
                "label": "總盈虧 / Total P&L",
                "value": format_money(grand_total_pnl, "HKD", signed=True),
                "sub": f"{grand_total_pnl_percent:+.1f}%",
                "tone": pnl_tone,
            },
            ytd_metric(dividend_report.get("total_ytd"), "HKD"),
            {
                "label": "總持股 / Holdings",
                "value": str(len(hk_rows) + len(us_rows)),
                "sub": f"港股 {len(hk_rows)} · 美股 {len(us_rows)}",
            },
        ])

        all_rows = hk_rows + us_rows
        if has_holdings:
            render_contributors(all_rows, currency="HKD")
        render_dividend_leaders(dividend_report, all_rows, currency="HKD")
        if has_holdings:
            render_balance(all_rows, combined_val, currency="HKD")

        st.markdown("---")
        st.subheader("📊 持股明細 / Holdings Detail")
        st.markdown("### 🇭🇰 港股 / HK Stocks")
        render_compact_holdings(
            hk_rows,
            combined_val,
            currency="HKD",
            sort_key="hk_holdings_sort",
            empty_message="無港股數據 / No HK holdings",
        )
        st.markdown("### 🇺🇸 美股 / US Stocks")
        render_compact_holdings(
            us_rows,
            combined_val,
            currency="HKD",
            sort_key="main_us_holdings_sort",
            empty_message="無美股數據 / No US holdings",
        )

        render_dividend_income(dividend_report, currency="HKD")

        rows = all_rows
        df = pd.DataFrame(rows) if rows else pd.DataFrame()

        if len(df) > 0:
            combined_chart_data = []
            for item in rows:
                label = item["name"] if item["name"] != item["ticker"] else item["ticker"]
                combined_chart_data.append({
                    "股票代號": item["股票代號"],
                    "名稱": label,
                    "Value_HKD": item["現值"],
                    "PnL_HKD": item["盈虧"],
                })
            chart_df = pd.DataFrame(combined_chart_data)
            fig = px.pie(
                chart_df,
                values="Value_HKD",
                names="名稱",
                title="股票組合分配 / Portfolio Allocation",
                hole=0.4,
            )
            st.plotly_chart(fig, use_container_width=True)

            industry_df = df.groupby("行業")["現值"].sum().reset_index()
            if len(industry_df) > 0:
                fig2 = px.pie(
                    industry_df,
                    values="現值",
                    names="行業",
                    title="行業分布 / Industry Allocation",
                    hole=0.4,
                )
                st.plotly_chart(fig2, use_container_width=True)

        if rows:
            st.write("---")
            st.subheader("📊 各股票盈虧 / P&L by Stock")

        chart = build_pnl_chart_frame(rows, currency="HKD")
        if len(chart) > 0:
            chart["label"] = chart["盈虧"].apply(lambda x: f"HKD {x:,.0f}")
            fig_bar = px.bar(
                chart,
                x="標籤",
                y="盈虧",
                title="各股票盈虧 / P&L by Stock",
                color="盈虧",
                color_continuous_scale="RdYlGn",
            )
            fig_bar.update_traces(
                text=chart["label"],
                textposition="outside",
                customdata=chart["hover"],
                hovertemplate="%{customdata}<extra></extra>",
                marker=dict(color=["red" if x < 0 else "green" for x in chart["盈虧%"]]),
            )
            fig_bar.update_layout(xaxis_title="公司 / Company", xaxis=dict(automargin=True))
            fig_bar.add_hline(y=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig_bar, use_container_width=True)

            chart["label_pct"] = chart["盈虧%"].apply(lambda x: f"{x:.1f}%")
            fig_pct = px.bar(
                chart,
                x="標籤",
                y="盈虧%",
                title="各股票盈虧 / P&L by Stock (%)",
                color="盈虧%",
                color_continuous_scale="RdYlGn",
            )
            fig_pct.update_traces(
                text=chart["label_pct"],
                textposition="outside",
                customdata=chart["hover"],
                hovertemplate="%{customdata}<extra></extra>",
                marker=dict(color=["red" if x < 0 else "green" for x in chart["盈虧%"]]),
            )
            fig_pct.update_layout(xaxis_title="公司 / Company", xaxis=dict(automargin=True))
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
    # ===== STOCK ANALYSIS =====
    st.write("---")
    st.subheader("📈 股票分析 / Stock Analysis")
    st.caption(
        "RSI 與信號只在這個研究區顯示，並非持股表上的買賣指令。"
        "「預期年度股息」是 Yahoo dividendRate 的遠期年度估計（每股），不是今年已收現金。"
        " / RSI and signals stay in this research section and are not trade instructions. "
        "Expected annual dividend is Yahoo's forward dividendRate per share, not cash received this year."
    )

    # Fetch metrics for each holding - include all symbols even if qty is 0
    analysis_rows = []
    all_symbols = set(list(display_holdings.keys()) + list(holdings.keys()))
    
    for ticker in all_symbols:
        try:
            metrics = get_stock_metrics(ticker)
            price_90d = get_90day_price(ticker)
            
            if metrics:
                row_data = {
                    '股票代號': ticker,
                    '公司': get_name(ticker),
                    '股價': metrics.get('price'),
                    'P/E': metrics.get('pe'),
                    '預測P/E': metrics.get('forward_pe'),
                    '市帳率': metrics.get('pb_ratio'),
                    '52W低': metrics.get('52w_low'),
                    '52W高': metrics.get('52w_high'),
                    '波幅%': metrics.get('volatility'),
                    'Beta': metrics.get('beta'),
                    '股息%': metrics.get('dividend_yield'),
                    '預期年度股息': metrics.get('dividend_rate'),
                    '收益率': metrics.get('dividend_five_year'),
                    '帳面值': metrics.get('book_value'),
                }
                
                # Add 90-day data if available
                if price_90d:
                    row_data['90天最高'] = price_90d.get('highest')
                    row_data['現價'] = price_90d.get('current')
                    row_data['回調%'] = price_90d.get('drop_pct')
                    row_data['信號'] = price_90d.get('signal')

                try:
                    hist = get_stock_data_cached(ticker, "3mo")
                    if hist is not None and len(hist) > 0:
                        rsi_val = calculate_rsi(hist["Close"]).iloc[-1]
                        if pd.notna(rsi_val):
                            signal, _english = get_signal(float(rsi_val))
                            row_data["RSI"] = round(float(rsi_val), 1)
                            row_data["RSI信號"] = signal
                except Exception:
                    pass

                analysis_rows.append(row_data)
        except:
            pass
    
    if analysis_rows:
        df_analysis = pd.DataFrame(analysis_rows)
        st.dataframe(df_analysis, use_container_width=True)
    else:
        st.info("無法獲取股票分析數據 / Cannot fetch analysis data")
    
    # ===== MONTHLY VALUE =====
    st.header("📊 每月價值明細 / Monthly Value")
    months = get_last_n_months(6)
    
    # Function to calculate qty at month end from HK transaction history only
    def get_hk_qty_at_month(month_end_date, username):
        """Calculate HK stock qty at month end from transactions for specific user"""
        month_qty = {}
        
        if supabase:
            try:
                # Get HK transactions only (transactions table)
                hk_tx = supabase.table('transactions').select('symbol,quantity,transaction_type').eq('username', username).lte('transaction_date', month_end_date).execute()
                for row in hk_tx.data or []:
                    sym = row['symbol']
                    qty_change = row['quantity'] if row['transaction_type'] == 'BUY' else -row['quantity']
                    month_qty[sym] = month_qty.get(sym, 0) + qty_change
            except:
                pass
        
        # Return only positive qty
        return {k: v for k, v in month_qty.items() if v > 0}
    
    hist_rows = []
    total_by_month = {}
    
    # Get all months qty first - for current user only (HK only)
    all_month_qty = {}
    for month_end, label in months:
        all_month_qty[label] = get_hk_qty_at_month(month_end, st.session_state.username)
    
    # Build rows for each stock that appeared in any month
    allstocks = set()
    for mq in all_month_qty.values():
        allstocks.update(mq.keys())
    
    for ticker in allstocks:
        try:
            company = get_name(ticker)
            row = {"股票代號": ticker, "公司名稱": company}
            
            for month_end, label in months:
                mqty = all_month_qty.get(label, {}).get(ticker, 0)
                if mqty > 0:
                    try:
                        # For current month, get latest price; for past months, get month-end price
                        if label == months[-1][1]:  # Current month
                            stock = yf.Ticker(ticker)
                            current_price = stock.history(period="1d")['Close'].iloc[-1]
                            month_val = mqty * current_price
                        else:
                            hist = yf.Ticker(ticker).history(start="2025-01-01", end=month_end)
                            if not hist.empty:
                                month_price = hist['Close'].iloc[-1]
                                month_val = mqty * month_price
                            else:
                                month_val = 0
                        
                        row[f"{label} 數量"] = mqty
                        row[f"{label} 現值"] = round(month_val)
                    except:
                        row[f"{label} 數量"] = mqty
                        row[f"{label} 現值"] = 0
                else:
                    row[f"{label} 數量"] = 0
                    row[f"{label} 現值"] = 0
            
            hist_rows.append(row)
            
            # Accumulate totals
            for month_end, label in months:
                total_by_month[label] = total_by_month.get(label, 0) + row.get(f"{label} 現值", 0)
                
        except:
            pass
    
    if hist_rows:
        st.dataframe(pd.DataFrame(hist_rows), use_container_width=True)
        
        # Portfolio Trend Chart
        chart_df = pd.DataFrame(list(total_by_month.items()), columns=["月份", "總值"])
        fig_line = px.line(chart_df, x='月份', y='總值', title='組合價值趨勢 / Portfolio Trend', markers=True)
        st.plotly_chart(fig_line, use_container_width=True)