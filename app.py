"""
Stock Portfolio Monitor App
Author: Nova (AI Assistant)
For: Nelson
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Page Config
st.set_page_config(
    page_title="Stock Portfolio Tracker",
    page_icon="📈",
    layout="wide"
)

# ============================================
# CONFIGURATION - Add your stocks here
# ============================================

# Example: US Stocks (Symbol, Quantity, Avg Cost)
US_STOCKS = {
    "AAPL": {"qty": 10, "cost": 150.00},
    "MSFT": {"qty": 5, "cost": 320.00},
    "GOOGL": {"qty": 2, "cost": 140.00},
}

# Example: HK Stocks (Symbol in HK format, Quantity, Avg Cost)
HK_STOCKS = {
    "0700.HK": {"qty": 100, "cost": 350.00},  # Tencent
    "9618.HK": {"qty": 50, "cost": 150.00},  # JD.com
    "0005.HK": {"qty": 30, "cost": 250.00},  # HSBC
}

# ============================================
# FUNCTIONS
# ============================================

@st.cache_data(ttl=3600)
def get_stock_data(ticker, period="1y"):
    """Fetch stock data from Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        return df
    except Exception as e:
        st.error(f"Error fetching {ticker}: {e}")
        return None

def calculate_rsi(prices, length=14):
    """Calculate RSI manually"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_ema(prices, length):
    """Calculate EMA"""
    return prices.ewm(span=length, adjust=False).mean()

def calculate_macd(prices):
    """Calculate MACD"""
    ema12 = calculate_ema(prices, 12)
    ema26 = calculate_ema(prices, 26)
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

def calculate_metrics(ticker, qty, avg_cost):
    """Calculate stock metrics"""
    df = get_stock_data(ticker)
    if df is None or df.empty:
        return None
    
    current_price = df['Close'].iloc[-1]
    cost_basis = qty * avg_cost
    current_value = qty * current_price
    pnl = current_value - cost_basis
    pnl_percent = (pnl / cost_basis) * 100 if cost_basis > 0 else 0
    
    # Calculate weekly change
    week_ago = datetime.now() - timedelta(days=7)
    try:
        week_data = df[df.index <= week_ago]
        if not week_data.empty:
            week_price = week_data['Close'].iloc[-1]
            weekly_change = ((current_price - week_price) / week_price) * 100
        else:
            weekly_change = 0
    except:
        weekly_change = 0
    
    # Calculate RSI
    df['RSI'] = calculate_rsi(df['Close'])
    rsi = df['RSI'].iloc[-1] if not pd.isna(df['RSI'].iloc[-1]) else 50
    
    # Calculate MACD
    macd, signal = calculate_macd(df['Close'])
    macd_value = macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else 0
    
    return {
        "current_price": current_price,
        "cost_basis": cost_basis,
        "current_value": current_value,
        "pnl": pnl,
        "pnl_percent": pnl_percent,
        "weekly_change": weekly_change,
        "rsi": rsi,
        "macd": macd_value,
        "52w_high": df['High'].max(),
        "52w_low": df['Low'].min()
    }

def get_signal(rsi, macd):
    """Generate buy/sell signal"""
    if rsi < 30 and macd > 0:
        return "STRONG BUY", "🟢"
    elif rsi < 40 and macd > 0:
        return "BUY", "🟢"
    elif rsi > 70:
        return "SELL", "🔴"
    elif rsi > 60:
        return "WATCH", "🟡"
    else:
        return "HOLD", "🟡"

# ============================================
# MAIN APP
# ============================================

st.title("📈 Stock Portfolio Tracker")
st.markdown("**By Nova (AI Assistant) | For Nelson**")

# Sidebar - Add Stocks
st.sidebar.header("⚙️ Configuration")
st.sidebar.markdown("---")
st.sidebar.subheader("📝 Your Stocks")

# Create tabs for US and HK stocks
tab1, tab2 = st.tabs(["🇺🇸 US Stocks", "🇭🇰 HK Stocks"])

with tab1:
    st.subheader("US Stocks")
    if US_STOCKS:
        for ticker, data in US_STOCKS.items():
            with st.expander(f"{ticker} - {data['qty']} shares @ ${data['cost']}"):
                st.write(f"Quantity: {data['qty']}")
                st.write(f"Avg Cost: ${data['cost']}")
    else:
        st.info("No US stocks added yet")

with tab2:
    st.subheader("HK Stocks")
    if HK_STOCKS:
        for ticker, data in HK_STOCKS.items():
            with st.expander(f"{ticker} - {data['qty']} shares @ ${data['cost']}"):
                st.write(f"Quantity: {data['qty']}")
                st.write(f"Avg Cost: ${data['cost']}")
    else:
        st.info("No HK stocks added yet")

# ============================================
# Portfolio Overview
# ============================================
st.markdown("---")
st.header("💼 Portfolio Overview")

total_value = 0
total_cost = 0
holdings_data = []

# Process US Stocks
for ticker, data in US_STOCKS.items():
    metrics = calculate_metrics(ticker, data['qty'], data['cost'])
    if metrics:
        total_value += metrics['current_value']
        total_cost += metrics['cost_basis']
        signal, emoji = get_signal(metrics['rsi'], metrics['macd'])
        holdings_data.append({
            "Ticker": ticker,
            "Type": "US",
            "Qty": data['qty'],
            "Avg Cost": data['cost'],
            "Current Price": metrics['current_price'],
            "Value": metrics['current_value'],
            "P&L": metrics['pnl'],
            "P&L %": metrics['pnl_percent'],
            "Weekly %": metrics['weekly_change'],
            "RSI": metrics['rsi'],
            "Signal": f"{emoji} {signal}"
        })

# Process HK Stocks
for ticker, data in HK_STOCKS.items():
    metrics = calculate_metrics(ticker, data['qty'], data['cost'])
    if metrics:
        total_value += metrics['current_value']
        total_cost += metrics['cost_basis']
        signal, emoji = get_signal(metrics['rsi'], metrics['macd'])
        holdings_data.append({
            "Ticker": ticker,
            "Type": "HK",
            "Qty": data['qty'],
            "Avg Cost": data['cost'],
            "Current Price": metrics['current_price'],
            "Value": metrics['current_value'],
            "P&L": metrics['pnl'],
            "P&L %": metrics['pnl_percent'],
            "Weekly %": metrics['weekly_change'],
            "RSI": metrics['rsi'],
            "Signal": f"{emoji} {signal}"
        })

# Summary Cards
col1, col2, col3, col4 = st.columns(4)

total_pnl = total_value - total_cost
total_pnl_percent = (total_pnl / total_cost) * 100 if total_cost > 0 else 0

with col1:
    st.metric("Total Value", f"${total_value:,.2f}")
with col2:
    st.metric("Total Cost", f"${total_cost:,.2f}")
with col3:
    st.metric("Total P&L", f"${total_pnl:,.2f}", f"{total_pnl_percent:.2f}%")
with col4:
    st.metric("Holdings", len(holdings_data))

# ============================================
# Holdings Table
# ============================================
st.markdown("---")
st.header("📊 Holdings Detail")

if holdings_data:
    df = pd.DataFrame(holdings_data)
    
    # Format columns
    st.dataframe(
        df.style.format({
            "Avg Cost": "${:.2f}",
            "Current Price": "${:.2f}",
            "Value": "${:.2f}",
            "P&L": "${:.2f}",
            "P&L %": "{:.2f}%",
            "Weekly %": "{:.2f}%",
            "RSI": "{:.2f}"
        }),
        use_container_width=True
    )
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie chart - Allocation
        fig = go.Figure(data=[go.Pie(
            labels=df['Ticker'],
            values=df['Value'],
            hole=0.4
        )])
        fig.update_layout(title="Portfolio Allocation")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Bar chart - P&L
        fig = go.Figure(data=[go.Bar(
            x=df['Ticker'],
            y=df['P&L'],
            marker_color=['green' if x > 0 else 'red' for x in df['P&L']]
        )])
        fig.update_layout(title="Profit/Loss by Stock")
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Add stocks to see your portfolio")

# ============================================
# Technical Analysis
# ============================================
st.markdown("---")
st.header("📈 Technical Analysis")

if holdings_data:
    selected_stock = st.selectbox("Select Stock to Analyze", 
                                  [h['Ticker'] for h in holdings_data])
    
    if selected_stock:
        df = get_stock_data(selected_stock)
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
                fig2.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='purple')))
                fig2.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought")
                fig2.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold")
                fig2.update_layout(title="RSI (14)", height=300, yaxis_range=[0, 100])
                st.plotly_chart(fig2, use_container_width=True)

# ============================================
# Footer
# ============================================
st.markdown("---")
st.markdown(f"""
---
**📅 Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}  
**🤖 Powered by:** Nova (AI Assistant)  
**📊 Data:** Yahoo Finance
""")