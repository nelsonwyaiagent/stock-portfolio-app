# 股票行業分類方案

## 目標
響投資組合表格加入「行業」欄位，自動分類股票

---

## 10 個行業分類 (短形式)

| # | 行業 (英文) | 中文 | 代碼 |
|---|-----------|------|------|
| 1 | Financials | 金融 | FIN |
| 2 | Properties | 地產 | PROP |
| 3 | Tech/Internet | 科技 | TECH |
| 4 | Telecom | 电訊 | TLCO |
| 5 | Insurance | 保險 | INSR |
| 6 | Energy | 能源 | ENGY |
| 7 | Utilities | 公用 | UTIL |
| 8 | Hardware | 硬件 | HW |
| 9 | Healthcare | 醫藥 | HLTH |
| 10 | Consumer | 消費 | CONS |

---

## 香港股票映射表

| 代號 | 類型 | 行業 |
|------|------|------|
| 00005.HK | 匯豐控股 | FIN |
| 03988.HK | 中銀香港 | FIN |
| 00011.HK | 恆生銀行 | FIN |
| 01113.HK | 長實集團 | PROP |
| 00016.HK | 新鴻基地產 | PROP |
| 00012.HK | 恆基地產 | PROP |
| 00700.HK | 騰訊控股 | TECH |
| 09988.HK | 阿里巴巴 | TECH |
| 03690.HK | 美團 | TECH |
| 00941.HK | 中國移動 | TLCO |
| 00728.HK | 中國電信 | TLCO |
| 01299.HK | 友邦保險 | INSR |
| 02318.HK | 中國平安 | INSR |
| 00883.HK | 中國海洋石油 | ENGY |
| 00386.HK | 中國石化 | ENGY |
| 00002.HK | 電能實業 | UTIL |
| 00003.HK | 煤氣公司 | UTIL |
| 00992.HK | 聯想集团 | HW |
| 01810.HK | 小米集团 | HW |
| 02269.HK | 藥明生物 | HLTH |
| 01801.HK | 信達生物 | HLTH |
| 00175.HK | 吉利汽車 | CONS |
| 02020.HK | 安踏体育 | CONS |

---

## 美股分類 (可選)

| 代號 | 類型 | 行業 |
|------|------|------|
| AAPL | Apple | HW |
| MSFT | Microsoft | TECH |
| GOOGL | Google | TECH |
| AMZN | Amazon | TECH |
| TSLA | Tesla | CONS |
| NVDA | Nvidia | HW |
| JPM | JPMorgan | FIN |
| V | Visa | FIN |
| JNJ | Johnson & Johnson | HLTH |
| XOM | Exxon | ENGY |

---

## 實施計劃

### 1. 新增映射字典
```python
STOCK_INDUSTRY = {
    "0700.HK": "TECH",
    "09988.HK": "TECH",
    # ... 其他股票
}
```

### 2. 修改投資組合顯示
- 加入「行業」欄位
- 用短代碼 (2-4 字元)

### 3. 修改圖表
圆饼圖可以按行业分类显示

---

## 顯示效果

| 股票代號 | 公司名稱 | 行業 | 數量 | ...
|----------|----------|------|------|---
| 0700.HK | 騰股控股 | TECH | 100 | ...

---