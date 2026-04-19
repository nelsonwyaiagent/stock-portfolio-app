"""
Delete Transaction Records Page
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import os

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

st.title("🗑️ 刪除交易記錄")

# Check login - use URL param or session state
username = st.query_params.get("user", "")
if not username and ('logged_in' in st.session_state and st.session_state.get('logged_in')):
    username = st.session_state.get('username', "")

if not username:
    st.warning("請先响 主頁 登入!")
    st.markdown("[去主頁登入](./)")
    st.stop()

st.session_state.username = username
st.session_state.logged_in = True

st.write(f"**用戶:** {st.session_state.username}")

if not supabase:
    st.error("Supabase 未連接!")
    st.stop()

# Load transactions
try:
    r = supabase.table('transactions').select('*').eq('username', st.session_state.username).execute()
    
    if not r.data or len(r.data) == 0:
        st.info("暫無交易記錄!")
        st.stop()
    
    # Prepare data
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
            'id': row['id'],
            '股票代號': sym,
            '公司': get_name(sym),
            '類型': row['transaction_type'],
            '數量': row['quantity'],
            '成交價': row['price'],
            '交易日期': row['transaction_date'],
            '現價': current_price,
            '盈虧比率': pl_ratio,
        })
    
    df_tx = pd.DataFrame(tx_list)
    df_tx = df_tx.sort_values(['股票代號', '交易日期'], ascending=[True, False])
    
    st.write(f"**共 {len(df_tx)} 筆記錄**")
    
    # Display table with selectbox for deletion
    for i, row in df_tx.iterrows():
        col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 1, 1, 1.5, 2.5, 1.5, 1.5, 1])
        
        with col1: st.write(f"**{row['股票代號']}**")
        with col2: st.write(row['類型'])
        with col3: st.write(row['數量'])
        with col4: st.write(f"${row['成交價']:.2f}")
        with col5: st.write(row['交易日期'])
        with col6: st.write(f"${row['現價']:.2f}" if row['現價'] else "-")
        with col7: st.write(f"{row['盈虧比率']:.1f}%" if row['盈虧比率'] else "-")
        with col8:
            if st.button("🗑️ 刪除", key=f"del_{row['id']}"):
                try:
                    supabase.table('transactions').delete().eq('id', row['id']).execute()
                    st.success(f"已刪除 {row['股票代號']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

except Exception as e:
    st.error(f"Error: {e}")