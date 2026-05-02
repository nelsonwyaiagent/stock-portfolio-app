# 📈 Stock Portfolio Manager (股票投資組合管理系統)

**版本**: v1.0 | **日期**: 2026年4月18日

一個基於網頁的股票投資組合管理系統，支援美國及香港股票追蹤。

## 🌟 功能特色

### 📊 投資組合管理
- 添加/移除美股和港股
- 即時股價更新 (Yahoo Finance)
- 總值、成本、盈虧統計

### 📈 技術分析
- RSI 技術指標
- 買入/賣出/持有信號
- 各股票盈虧百分比柱狀圖
- 組合分配圓餅圖

### 📉 歷史數據
- 每月價值明細 (2026年1月-4月)
- 組合價值趨勢線圖
- 月度回報率追蹤

### 💾 雲端儲存
- Supabase 雲端數據庫
- 自動載入和保存
- 多用戶支援

## 🖥️ 技術架構

| 組件 | 技術 |
|------|------|
| 前端 | Streamlit |
| 圖表 | Plotly |
| 數據 | Yahoo Finance |
| 數據庫 | Supabase |
| 部署 | Streamlit Cloud |

## 🚀 快速開始

1. 訪問: https://stock-portfolio-app.streamlit.app
2. 輸入用戶名登入
3. 添加你的股票
4. 按「💾 儲存」保存

## 📁 項目結構

```
stock-portfolio-app/
├── app.py              # 主應用程序
├── requirements.txt    # Python 依賴
└── README.md          # 說明文件
```

## 📋 依賴

```
streamlit
yfinance
pandas
plotly
supabase
```

## 📊 支援的股票

### 港股自動中文名稱
- 0700.HK - 騰訊控股
- 9988.HK - 阿里巴巴
- 1810.HK - 小米集團
- 9618.HK - 京東集團
- 1024.HK - 快手科技
- 0880.HK - 中國平安
- 0005.HK - 匯豐控股
- 1299.HK - 友邦保險
- 0941.HK - 中國移動

## 📄 許可證

MIT License

## 👤 開發者

由 Nova (AI Assistant) 開發

---

**產品規格**: 請參閱 `../product-specification-v1.md`Sat May  2 09:03:11 AM UTC 2026
