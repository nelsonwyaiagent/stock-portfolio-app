"""Pure display helpers for the portfolio dashboard.

Cost-basis math stays in the pages. This module only names securities,
formats numbers, and arranges the rows the dashboard shows.
"""

from html import escape

import pandas as pd

# Local names win over Yahoo. 2318.HK is Ping An (中國平安), not China Life.
# 0880.HK is SJM Holdings (澳博控股). China Life is 2628.HK.
HK_NAMES = {
    "0700.HK": "騰訊控股",
    "9988.HK": "阿里巴巴",
    "1810.HK": "小米集團",
    "9618.HK": "京東集團",
    "1024.HK": "快手科技",
    "0880.HK": "澳博控股",
    "3382.HK": "海爾智家",
    "6690.HK": "海爾智家",
    "0005.HK": "匯豐控股",
    "1299.HK": "友邦保險",
    "0941.HK": "中國移動",
    "2318.HK": "中國平安",
    "2628.HK": "中國人壽",
    "0016.HK": "新鴻基地產",
    "3416.HK": "國指備兌ETF",
    "3191.HK": "中國半導體ETF",
    "3486.HK": "亞洲半導體ETF",
    "3455.HK": "景順QQQ",
}

US_NAMES = {
    "AAPL": "蘋果",
    "MSFT": "微軟",
    "GOOGL": "谷歌",
    "AMZN": "亞馬遜",
    "TSLA": "特斯拉",
    "META": "Meta",
    "NVDA": "輝達",
    "JPM": "摩根大通",
    "V": "維薩",
    "JNJ": "嬌生",
    "WMT": "沃爾瑪",
    "PG": "寶潔",
    "MA": "萬事達",
    "UNH": "聯合健康",
    "HD": "家得寶",
    "DIS": "迪士尼",
    "NFLX": "Netflix",
    "AMD": "超微",
    "INTC": "英特爾",
    "COST": "好市多",
    "BA": "波音",
    "CAT": "卡特彼勒",
    "MMM": "3M",
    "GE": "GE",
    "XOM": "埃克森美孚",
    "CVX": "雪佛龍",
    "PFE": "輝瑞",
    "ABBV": "艾伯維",
    "KO": "可口可樂",
    "PEP": "百事",
    "MCD": "麥當勞",
    "NKE": "Nike",
}

# Short industry codes. Local entries win over the Yahoo sector fallback.
HK_INDUSTRY = {
    "00002.HK": "UTIL",
    "00003.HK": "UTIL",
    "00005.HK": "FIN",
    "00011.HK": "FIN",
    "00012.HK": "PROP",
    "00016.HK": "PROP",
    "0016.HK": "PROP",
    "00175.HK": "CONS",
    "00992.HK": "HW",
    "01801.HK": "HLTH",
    "01810.HK": "HW",
    "02020.HK": "CONS",
    "02250.HK": "HLTH",
    "02269.HK": "HLTH",
    "03690.HK": "TECH",
    "0386.HK": "ENGY",
    "03988.HK": "FIN",
    "06808.HK": "PROP",
    "0700.HK": "TECH",
    "0728.HK": "TLCO",
    "0857.HK": "ENGY",
    "0880.HK": "CONS",
    "0883.HK": "ENGY",
    "0941.HK": "TLCO",
    "09988.HK": "TECH",
    "1024.HK": "TECH",
    "1109.HK": "ENGY",
    "1113.HK": "PROP",
    "1177.HK": "HLTH",
    "1299.HK": "INSR",
    "1388.HK": "CONS",
    "1398.HK": "FIN",
    "2318.HK": "INSR",
    "2319.HK": "TECH",
    "2388.HK": "FIN",
    "2601.HK": "INSR",
    "2628.HK": "INSR",
    "2688.HK": "UTIL",
    "2888.HK": "FIN",
    "291.HK": "CONS",
    "3191.HK": "TECH",
    "3328.HK": "FIN",
    "3416.HK": "ETF",
    "3455.HK": "TECH",
    "3486.HK": "TECH",
    "3669.HK": "TECH",
    "9618.HK": "TECH",
}

US_INDUSTRY = {
    "AAPL": "TECH",
    "MSFT": "TECH",
    "GOOGL": "TECH",
    "AMZN": "CONS",
    "TSLA": "AUTO",
    "META": "TECH",
    "NVDA": "TECH",
    "JPM": "FIN",
    "V": "FIN",
    "JNJ": "HLTH",
    "WMT": "CONS",
    "PG": "CONS",
    "MA": "FIN",
    "UNH": "HLTH",
    "HD": "CONS",
    "DIS": "MEDIA",
    "NFLX": "MEDIA",
    "AMD": "TECH",
    "INTC": "TECH",
    "COST": "CONS",
    "BA": "INDU",
    "CAT": "INDU",
    "MMM": "INDU",
    "GE": "INDU",
    "XOM": "ENGY",
    "CVX": "ENGY",
    "PFE": "HLTH",
    "ABBV": "HLTH",
    "KO": "CONS",
    "PEP": "CONS",
    "MCD": "CONS",
    "NKE": "CONS",
}

INDUSTRY_LABELS = {
    "TECH": "科技 TECH",
    "FIN": "金融 FIN",
    "PROP": "地產 PROP",
    "TLCO": "電訊 TLCO",
    "INSR": "保險 INSR",
    "ENGY": "能源 ENGY",
    "UTIL": "公用 UTIL",
    "HW": "硬件 HW",
    "HLTH": "醫藥 HLTH",
    "CONS": "消費 CONS",
    "INDU": "工業 INDU",
    "MAT": "原材料 MAT",
    "MEDIA": "媒體 MEDIA",
    "AUTO": "汽車 AUTO",
    "ETF": "指數ETF",
    "UNK": "未分類",
}

YAHOO_SECTOR_TO_CODE = {
    "Technology": "TECH",
    "Financial Services": "FIN",
    "Financial": "FIN",
    "Real Estate": "PROP",
    "Communication Services": "TLCO",
    "Healthcare": "HLTH",
    "Energy": "ENGY",
    "Utilities": "UTIL",
    "Consumer Cyclical": "CONS",
    "Consumer Defensive": "CONS",
    "Industrials": "INDU",
    "Basic Materials": "MAT",
}

INDUSTRY_COLORS = {
    "科技 TECH": "#4C78A8",
    "金融 FIN": "#F58518",
    "地產 PROP": "#54A24B",
    "電訊 TLCO": "#72B7B2",
    "保險 INSR": "#E45756",
    "能源 ENGY": "#B279A2",
    "公用 UTIL": "#FF9DA6",
    "硬件 HW": "#9D755D",
    "醫藥 HLTH": "#BAB0AC",
    "消費 CONS": "#EECA3B",
    "工業 INDU": "#4C78A8",
    "原材料 MAT": "#9D755D",
    "媒體 MEDIA": "#B279A2",
    "汽車 AUTO": "#F58518",
    "指數ETF": "#6B5B95",
    "未分類": "#9AA0A6",
}

FALLBACK_COLORS = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#B279A2", "#EECA3B"]

SINGLE_NAME_WARN_PCT = 15.0
COMPACT_COLUMNS = ["代號", "公司", "權重%", "成本", "市值", "盈虧$", "盈虧%", "今年股息", "含息盈虧", "含息%"]

CONTRIBUTOR_NOTE = (
    "按未實現盈虧金額排列，反映目前持倉對組合盈虧的貢獻，並非買賣建議。"
    " / Ranked by unrealized P&L contribution. Not a buy or sell signal."
)
BALANCE_NOTE = (
    "持倉分布一覽，用來觀察集中度與市場、行業比重，並非操作建議。"
    " / Mix and concentration only. Not a trade instruction."
)
HOLDINGS_NOTE = (
    "金額見欄位單位。成本為持倉成本（數量 × 平均成本），市值 − 成本 = 盈虧。"
    "權重以組合總市值為分母。綠色為盈利，紅色為虧損。"
    "盈虧$ 與盈虧% 只計股價，不含股息。今年股息是按除淨日持股估算的已收現金；"
    "含息盈虧 = 盈虧$ + 今年股息。"
    " / Cost is position cost (quantity × average cost). "
    "Weight uses total portfolio value. Green is a gain, red is a loss. "
    "Price P&L excludes dividends. Div YTD is estimated cash from shares held before each ex-date; "
    "total return adds that cash to price P&L."
)

SORT_CHOICES = (
    ("pnl", "盈虧$ / P&L $"),
    ("pnl_pct", "盈虧% / P&L %"),
    ("weight", "權重% / Weight"),
)


def ticker_keys(ticker: str) -> list:
    """Equivalent symbols, including HK zero-padding variants."""
    raw = (ticker or "").strip().upper()
    if not raw:
        return []
    keys = [raw]
    if raw.endswith(".HK"):
        digits = "".join(ch for ch in raw[:-3] if ch.isdigit())
        if digits:
            stripped = digits.lstrip("0") or "0"
            # 16, 0016 and 00016 are the same HK listing. zfill the unpadded code
            # so a 5-digit key still finds a 4-digit override.
            for variant in (
                f"{stripped}.HK",
                f"{stripped.zfill(4)}.HK",
                f"{stripped.zfill(5)}.HK",
                f"{digits}.HK",
            ):
                if variant not in keys:
                    keys.append(variant)
    else:
        if "." in raw:
            dashed = raw.replace(".", "-")
            if dashed not in keys:
                keys.append(dashed)
        if "-" in raw:
            dotted = raw.replace("-", ".")
            if dotted not in keys:
                keys.append(dotted)
    return keys


def _lookup(mapping: dict, ticker: str):
    for key in ticker_keys(ticker):
        if key in mapping:
            return mapping[key]
    return None


def _clean(text) -> str:
    if not isinstance(text, str):
        return ""
    return " ".join(text.replace("\n", " ").split())


def _is_useless_name(name: str, ticker: str) -> bool:
    if not name:
        return True
    folded = name.upper().replace(" ", "")
    if folded in {key.upper().replace(" ", "") for key in ticker_keys(ticker)}:
        return True
    return folded in {"-", "—", "N/A", "NA", "NONE", "NULL"}


def _truncate(text: str, limit: int = 40) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def yahoo_display_name(profile: dict, ticker: str) -> str:
    short = _clean((profile or {}).get("short_name"))
    long = _clean((profile or {}).get("long_name"))
    if long and not _is_useless_name(long, ticker):
        return _truncate(long)
    if short and not _is_useless_name(short, ticker):
        return _truncate(short)
    return ""


def industry_label(code: str) -> str:
    if not code:
        return INDUSTRY_LABELS["UNK"]
    return INDUSTRY_LABELS.get(code, INDUSTRY_LABELS["UNK"])


def _industry_from_yahoo(profile: dict) -> str:
    profile = profile or {}
    industry = _clean(profile.get("industry"))
    if industry and "insurance" in industry.lower():
        return "INSR"
    sector = _clean(profile.get("sector"))
    if sector in YAHOO_SECTOR_TO_CODE:
        return YAHOO_SECTOR_TO_CODE[sector]
    quote_type = _clean(profile.get("quote_type")).upper()
    blob = f"{profile.get('short_name', '')} {profile.get('long_name', '')}".upper()
    if quote_type == "ETF" or " ETF" in f" {blob}" or blob.endswith("ETF"):
        return "ETF"
    return ""


def resolve_security(ticker: str, yahoo=None) -> dict:
    """Name and industry. Local overrides win; Yahoo fills the gaps."""
    raw = (ticker or "").strip().upper()
    name_override = _lookup(HK_NAMES, raw) or _lookup(US_NAMES, raw)
    industry_override = _lookup(HK_INDUSTRY, raw) or _lookup(US_INDUSTRY, raw)
    profile = {}
    if yahoo and (not name_override or not industry_override):
        try:
            profile = yahoo(raw) or {}
        except Exception:
            profile = {}
    name = name_override or yahoo_display_name(profile, raw) or raw
    code = industry_override or _industry_from_yahoo(profile) or "UNK"
    label = industry_label(code)
    if not label or label.strip() in {"-", "—"}:
        label = INDUSTRY_LABELS["UNK"]
        code = "UNK"
    return {
        "ticker": raw,
        "name": name,
        "industry_code": code,
        "industry_label": label,
    }


def format_money(amount, currency="HKD", signed=False, decimals=None) -> str:
    """Full amount with a currency label and thousands separators. Never ellipsized."""
    value = float(amount or 0)
    if decimals is None:
        decimals = 0 if currency == "HKD" else 2
    number = f"{abs(value):,.{decimals}f}"
    if signed:
        if value > 0:
            sign = "+"
        elif value < 0:
            sign = "-"
        else:
            sign = ""
        return f"{currency} {sign}{number}"
    if value < 0:
        return f"{currency} -{number}"
    return f"{currency} {number}"


CHART_AXIS_LINE = 8
CHART_AXIS_LINES = 2


def _chart_source_name(name, ticker: str) -> str:
    ticker = (ticker or "").strip()
    cleaned = _clean(name) if isinstance(name, str) else ""
    if not cleaned or cleaned == ticker:
        return ticker
    return cleaned


def _wrap_axis_label(text: str, line_length=CHART_AXIS_LINE, max_lines=CHART_AXIS_LINES) -> str:
    """Keep category labels short. Plotly draws <br> as a line break."""
    if len(text) <= line_length:
        return text
    max_chars = line_length * max_lines
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return "<br>".join(text[i:i + line_length] for i in range(0, len(text), line_length))


def build_pnl_chart_frame(rows, currency="HKD") -> pd.DataFrame:
    """Bar-chart categories use company names. Hover still includes the ticker."""
    sources = []
    for row in rows or []:
        ticker = str(row.get("ticker") or row.get("股票代號") or "").strip()
        name = row.get("name") if row.get("name") is not None else row.get("公司名稱")
        sources.append(
            (
                ticker,
                name,
                _as_float(row.get("pnl", row.get("盈虧"))),
                _as_float(row.get("pnl_pct", row.get("%"))),
            )
        )
    bases = [_chart_source_name(name, ticker) for ticker, name, _, _ in sources]
    counts = {}
    for base in bases:
        counts[base] = counts.get(base, 0) + 1
    records = []
    for (ticker, name, pnl, pct), base in zip(sources, bases):
        text = _wrap_axis_label(base)
        if counts[base] > 1 and ticker and ticker not in text:
            text = f"{text}<br>{ticker}"
        full = _chart_source_name(name, ticker)
        hover_name = full if not ticker or full == ticker else f"{full} ({ticker})"
        hover = f"{hover_name}<br>{format_money(pnl, currency, signed=True)} ({pct:+.1f}%)"
        records.append(
            {
                "標籤": text,
                "hover": hover,
                "盈虧": pnl,
                "盈虧%": pct,
            }
        )
    return pd.DataFrame(records, columns=["標籤", "hover", "盈虧", "盈虧%"])


def _as_float(value, default=0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _weight(value, total) -> float:
    total = _as_float(total)
    if total == 0:
        return 0.0
    return _as_float(value) / total * 100


def build_compact_frame(rows, total_value, sort_by="pnl") -> pd.DataFrame:
    """Compact holdings view. Default order is worst unrealized P&L $ first."""
    records = []
    for row in rows or []:
        ticker = str(row.get("ticker") or row.get("股票代號") or "")
        if not ticker:
            continue
        market_value = _as_float(row.get("market_value", row.get("現值")))
        price_pnl = _as_float(row.get("pnl", row.get("盈虧")))
        price_pct = _as_float(row.get("pnl_pct", row.get("%")))
        dividend_ytd = _as_float(row.get("div_ytd"))
        cost_total = _as_float(row.get("cost_total"))
        total_return = price_pnl + dividend_ytd
        total_pct = (total_return / cost_total * 100) if cost_total else 0.0
        records.append(
            {
                "代號": ticker,
                "公司": row.get("name") or row.get("公司名稱") or ticker,
                "權重%": _weight(market_value, total_value),
                "成本": cost_total,
                "市值": market_value,
                "盈虧$": price_pnl,
                "盈虧%": price_pct,
                "今年股息": dividend_ytd,
                "含息盈虧": total_return,
                "含息%": total_pct,
            }
        )
    frame = pd.DataFrame(records, columns=COMPACT_COLUMNS)
    if frame.empty:
        return frame
    if sort_by == "weight":
        frame = frame.sort_values(["權重%", "代號"], ascending=[False, True], kind="mergesort")
    elif sort_by == "pnl_pct":
        frame = frame.sort_values(["盈虧%", "代號"], ascending=[True, True], kind="mergesort")
    else:
        frame = frame.sort_values(["盈虧$", "代號"], ascending=[True, True], kind="mergesort")
    return frame.reset_index(drop=True)


def _pnl_number(value):
    if isinstance(value, str):
        cleaned = value.replace("%", "").replace(",", "").replace("+", "").strip()
        return _as_float(cleaned, default=None)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _pnl_css(value) -> str:
    number = _pnl_number(value)
    if number is None:
        return ""
    if number > 0:
        return "color: #137333; font-weight: 600"
    if number < 0:
        return "color: #c5221f; font-weight: 600"
    return "color: #3c4043"


def compact_styler(frame: pd.DataFrame, currency="HKD"):
    decimals = 0 if currency == "HKD" else 2
    number = f"{{:,.{decimals}f}}"
    signed = f"{{:+,.{decimals}f}}"
    styler = frame.style.map(_pnl_css, subset=["盈虧$", "盈虧%", "今年股息", "含息盈虧", "含息%"])
    styler = styler.format(
        {
            "權重%": "{:.1f}%",
            "成本": number,
            "市值": number,
            "盈虧$": signed,
            "盈虧%": "{:+.1f}%",
            "今年股息": signed,
            "含息盈虧": signed,
            "含息%": "{:+.1f}%",
        }
    )
    return styler.hide(axis="index")


def contributor_lists(rows, limit=3):
    """Best and worst unrealized P&L contributors, ranked by dollars."""
    usable = []
    for row in rows or []:
        ticker = row.get("ticker") or row.get("股票代號")
        if not ticker:
            continue
        usable.append(row)
    losers = sorted(
        (row for row in usable if _as_float(row.get("pnl")) < 0),
        key=lambda row: (_as_float(row.get("pnl")), str(row.get("ticker"))),
    )[:limit]
    winners = sorted(
        (row for row in usable if _as_float(row.get("pnl")) > 0),
        key=lambda row: (-_as_float(row.get("pnl")), str(row.get("ticker"))),
    )[:limit]
    return winners, losers


def total_return_ranking(rows, limit=3):
    """Highest price P&L plus year-to-date dividends. Does not replace price ranking."""
    ranked = []
    for row in rows or []:
        ticker = row.get("ticker") or row.get("股票代號")
        if not ticker:
            continue
        price_pnl = _as_float(row.get("pnl", row.get("盈虧")))
        dividend_ytd = _as_float(row.get("div_ytd"))
        cost = _as_float(row.get("cost_total"))
        total = price_pnl + dividend_ytd
        ranked.append(
            {
                "ticker": ticker,
                "name": row.get("name") or row.get("公司名稱") or ticker,
                "pnl": price_pnl,
                "div_ytd": dividend_ytd,
                "total_return": total,
                "total_return_pct": (total / cost * 100) if cost else 0.0,
            }
        )
    ranked.sort(key=lambda item: (-item["total_return"], str(item["ticker"])))
    return ranked[:limit]


def balance_snapshot(rows, total_value, warn_pct=SINGLE_NAME_WARN_PCT) -> dict:
    usable = []
    for row in rows or []:
        ticker = row.get("ticker") or row.get("股票代號")
        if not ticker:
            continue
        usable.append(row)
    total = _as_float(total_value)
    ranked = sorted(usable, key=lambda row: _as_float(row.get("market_value")), reverse=True)
    hk_value = sum(_as_float(row.get("market_value")) for row in usable if row.get("market") != "US")
    us_value = sum(_as_float(row.get("market_value")) for row in usable if row.get("market") == "US")
    industries = {}
    for row in usable:
        label = row.get("industry_label") or INDUSTRY_LABELS["UNK"]
        if not label or str(label).strip() in {"-", "—"}:
            label = INDUSTRY_LABELS["UNK"]
        industries[label] = industries.get(label, 0.0) + _as_float(row.get("market_value"))
    mix = [
        {"label": label, "value": value, "weight": _weight(value, total)}
        for label, value in industries.items()
        if value > 0
    ]
    mix.sort(key=lambda item: (-item["value"], item["label"]))
    warnings = []
    for row in ranked:
        weight = _weight(row.get("market_value"), total)
        if weight > warn_pct:
            warnings.append(
                {
                    "ticker": row.get("ticker"),
                    "name": row.get("name") or row.get("ticker"),
                    "weight": weight,
                    "market_value": _as_float(row.get("market_value")),
                }
            )
    top1 = None
    if ranked:
        top = ranked[0]
        top1 = {
            "ticker": top.get("ticker"),
            "name": top.get("name") or top.get("ticker"),
            "weight": _weight(top.get("market_value"), total),
            "market_value": _as_float(top.get("market_value")),
        }
    return {
        "top1": top1,
        "top5_weight": _weight(sum(_as_float(row.get("market_value")) for row in ranked[:5]), total),
        "hk_value": hk_value,
        "us_value": us_value,
        "hk_weight": _weight(hk_value, total),
        "us_weight": _weight(us_value, total),
        "industries": mix,
        "warnings": warnings,
        "concentrated": bool(warnings),
        "warn_pct": warn_pct,
        "total_value": total,
    }


def concentration_notice(item: dict, warn_pct: float) -> dict:
    weight = _as_float(item.get("weight"))
    name = item.get("name") or item.get("ticker")
    ticker = item.get("ticker") or ""
    return {
        "zh": (
            f"單一持股 {name}（{ticker}）佔組合 {weight:.1f}%，"
            f"高於 {warn_pct:.0f}% 參考線。此為集中度提示，並非買賣建議。"
        ),
        "en": (
            f"Single holding {ticker} is {weight:.1f}% of portfolio value, "
            f"above the {warn_pct:.0f}% reference line. "
            "This is a concentration notice, not a trade suggestion."
        ),
    }


def industry_color(label: str, index: int = 0) -> str:
    return INDUSTRY_COLORS.get(label) or FALLBACK_COLORS[index % len(FALLBACK_COLORS)]


def rsi_signal_labels(rsi) -> tuple:
    """Existing RSI wording. Shown only in the research section."""
    if rsi < 30:
        return "🟢 強買", "Strong Buy"
    if rsi < 40:
        return "🟢 買", "Buy"
    if rsi > 70:
        return "🔴 強賣", "Strong Sell"
    if rsi > 60:
        return "🟡 留意", "Watch"
    return "🟡 持有", "Hold"


def html_text(value) -> str:
    return escape("" if value is None else str(value), quote=True)
