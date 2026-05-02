# Testing Guide for Stock Portfolio App

## Common Errors & Solutions

### 1. "Name or service not known" (DNS Resolution)
**Cause:** Cannot connect to Supabase - DNS/network issue
**Fix:** 
- Check SUPABASE_URL is correct in secrets
- Check internet connectivity on Streamlit Cloud

### 2. "logged_in not defined" 
**Cause:** Session state not initialized
**Fix:** Initialize session state at top of app

### 3. Import errors
**Fix:** Check all imports are available in Streamlit Cloud environment

## How to Test Locally (for debugging)

### Option 1: Run locally with test credentials
```bash
cd stock-portfolio-app
streamlit run app.py --server.headless true
```

### Option 2: Add debug logging
```python
import streamlit as st
st.write("DEBUG: supabase =", supabase)
st.write("DEBUG: URL =", URL[:20] + "...")
```

### Option 3: Test with mock data (no Supabase)
```python
# At top of app, add:
TEST_MODE = True
if TEST_MODE:
    # Use mock data instead of Supabase
    st.session_state.us_stocks = {'AAPL': {'qty': 10, 'cost': 150}}
    st.session_state.hk_stocks = {'0700.HK': {'qty': 100, 'cost': 350}}
```

## Testing Checklist

| Test | Expected Result |
|------|-----------------|
| Login with "Nelson" | No error, show main app |
| No portfolio | Show empty state message |
| Add US stock | Saved to us_transactions |
| Add HK stock | Saved to transactions |
| View portfolio | Shows both tables |
| Technical Analysis | Dropdown works |

## Quick Fix - Add Connection Test

Add this at top of login section:
```python
# Test connection
if not supabase:
    st.error("⚠️ Database not connected! Check SUPABASE_URL and KEY in secrets.")
    st.stop()
```

