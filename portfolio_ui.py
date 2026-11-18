"""Streamlit rendering for the portfolio dashboard. No database writes."""

import yfinance as yf
import streamlit as st

from portfolio_display import (
    BALANCE_NOTE,
    CONTRIBUTOR_NOTE,
    HOLDINGS_NOTE,
    SORT_CHOICES,
    balance_snapshot,
    build_compact_frame,
    compact_styler,
    concentration_notice,
    contributor_lists,
    format_money,
    html_text,
    industry_color,
    resolve_security,
    total_return_ranking,
)
from portfolio_dividends import (
    build_dividend_report,
    build_income_frame,
    dividend_caption,
    rate_on_or_before,
    yahoo_cash_dividends,
    yahoo_usd_hkd_rates,
)

__all__ = [
    "collect_dividend_report",
    "format_money",
    "render_balance",
    "render_compact_holdings",
    "render_contributors",
    "render_dividend_income",
    "render_dividend_leaders",
    "render_metric_tiles",
    "security_profile",
    "ytd_metric",
]


def fetch_yahoo_profile(ticker: str) -> dict:
    """Yahoo name and sector. Empty dict fields when the lookup fails."""
    empty = {
        "short_name": "",
        "long_name": "",
        "sector": "",
        "industry": "",
        "quote_type": "",
    }
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return empty

    def text(key):
        value = info.get(key)
        return value.strip() if isinstance(value, str) else ""

    return {
        "short_name": text("shortName"),
        "long_name": text("longName"),
        "sector": text("sector"),
        "industry": text("industry"),
        "quote_type": text("quoteType"),
    }


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def security_profile(ticker: str) -> dict:
    return resolve_security(ticker, yahoo=fetch_yahoo_profile)


def _tone_color(tone: str) -> str:
    return {"pos": "#137333", "neg": "#c5221f"}.get(tone or "", "#1f2933")


def render_metric_tiles(metrics) -> None:
    """Full figures with a currency label. Values wrap instead of truncating."""
    cards = []
    for metric in metrics:
        color = _tone_color(metric.get("tone"))
        sub = metric.get("sub") or ""
        sub_html = (
            f'<div style="margin-top:2px;font-size:0.95rem;color:{color};white-space:normal;">{html_text(sub)}</div>'
            if sub
            else ""
        )
        cards.append(
            '<div style="border:1px solid #e6e8eb;border-radius:10px;padding:12px 14px;'
            'background:#fafbfc;min-width:0;">'
            f'<div style="font-size:0.82rem;color:#5c6770;line-height:1.35;">{html_text(metric.get("label"))}</div>'
            f'<div style="margin-top:4px;font-size:1.25rem;font-weight:650;line-height:1.3;color:{color};'
            'white-space:normal;overflow:visible;word-break:break-word;">'
            f'{html_text(metric.get("value"))}</div>'
            f"{sub_html}</div>"
        )
    st.html(
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));'
        'gap:10px;margin:4px 0 14px;">'
        + "".join(cards)
        + "</div>"
    )


def _contributor_card(title, rows, currency, empty) -> str:
    if not rows:
        body = f'<div style="color:#5c6770;">{html_text(empty)}</div>'
    else:
        lines = []
        for row in rows:
            pnl = float(row.get("pnl") or 0)
            pct = float(row.get("pnl_pct") or 0)
            color = "#137333" if pnl > 0 else "#c5221f"
            name = row.get("name") or row.get("ticker")
            lines.append(
                '<div style="display:flex;justify-content:space-between;gap:12px;'
                'padding:6px 0;border-top:1px solid #eef0f2;">'
                f'<div style="min-width:0;white-space:normal;word-break:break-word;">'
                f'<div style="font-weight:650;">{html_text(name)}</div>'
                f'<div style="color:#5c6770;font-size:0.85rem;">{html_text(row.get("ticker"))}</div>'
                "</div>"
                f'<div style="text-align:right;color:{color};font-weight:650;white-space:normal;">'
                f'<div>{html_text(format_money(pnl, currency, signed=True))}</div>'
                f'<div>{pct:+.1f}%</div>'
                "</div></div>"
            )
        body = "".join(lines)
    return (
        '<div style="border:1px solid #e6e8eb;border-radius:10px;padding:12px 14px;background:#fff;min-width:0;">'
        f'<div style="font-weight:700;margin-bottom:4px;">{html_text(title)}</div>'
        f"{body}</div>"
    )


def ytd_metric(total, currency="HKD") -> dict:
    """Top-tile figure for cash received this calendar year, not a forward estimate."""
    amount = float(total or 0)
    return {
        "label": "今年股息 / Div YTD",
        "value": format_money(amount, currency),
        "sub": "已收 / received",
        "tone": "pos" if amount > 0 else "neutral",
    }


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def cached_dividend_events(ticker: str):
    return yahoo_cash_dividends(ticker)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def cached_usd_hkd_rates() -> dict:
    return yahoo_usd_hkd_rates()


def collect_dividend_report(
    ledger,
    names=None,
    *,
    today=None,
    default_currency="HKD",
    report_currency="HKD",
    spot_fx=7.82,
    currency_by_symbol=None,
):
    """Fetch Yahoo cash dividends for the dated ledger and estimate this year's cash.

    Pay-date USDHKD history is loaded only when an event actually carries a
    pay date and the report currency is HKD. Yahoo's usual payload has no
    pay date, so USD cash then uses the spot rate already shown in the app.
    """
    symbols = []
    seen = set()
    for tx in ledger or []:
        symbol = str((tx or {}).get("symbol") or "").strip().upper()
        if symbol and symbol not in seen:
            seen.add(symbol)
            symbols.append(symbol)
    events = {symbol: cached_dividend_events(symbol) for symbol in symbols}
    fx_on_pay_date = None
    needs_pay_fx = report_currency == "HKD" and any(
        event.get("pay_date") for event_list in events.values() for event in event_list or []
    )
    if needs_pay_fx:
        rates = cached_usd_hkd_rates()

        def fx_on_pay_date(day, rates=rates):
            return rate_on_or_before(rates, day)

    return build_dividend_report(
        ledger,
        events,
        today=today,
        currency_by_symbol=currency_by_symbol,
        default_currency=default_currency,
        report_currency=report_currency,
        spot_fx=spot_fx,
        fx_on_pay_date=fx_on_pay_date,
        names=names,
    )


def _dividend_card(title, rows, currency, empty) -> str:
    if not rows:
        body = f'<div style="color:#5c6770;">{html_text(empty)}</div>'
    else:
        lines = []
        for row in rows:
            amount = float(row.get("ytd") or 0)
            name = row.get("name") or row.get("ticker")
            times = int(row.get("times_paid") or 0)
            note = row.get("note") or ""
            note_html = (
                f'<div style="color:#8a5a00;font-size:0.8rem;">{html_text(note)}</div>' if note else ""
            )
            lines.append(
                '<div style="display:flex;justify-content:space-between;gap:12px;'
                'padding:6px 0;border-top:1px solid #eef0f2;">'
                f'<div style="min-width:0;white-space:normal;word-break:break-word;">'
                f'<div style="font-weight:650;">{html_text(name)}</div>'
                f'<div style="color:#5c6770;font-size:0.85rem;">{html_text(row.get("ticker"))}'
                f' · {times} 次</div>{note_html}</div>'
                f'<div style="text-align:right;color:#137333;font-weight:650;white-space:normal;">'
                f'{html_text(format_money(amount, currency))}</div></div>'
            )
        body = "".join(lines)
    return (
        '<div style="border:1px solid #d7eadb;border-radius:10px;padding:12px 14px;background:#f7fbf8;min-width:0;">'
        f'<div style="font-weight:700;margin-bottom:4px;">{html_text(title)}</div>'
        f"{body}</div>"
    )


def _total_return_card(title, rows, currency, empty) -> str:
    if not rows:
        body = f'<div style="color:#5c6770;">{html_text(empty)}</div>'
    else:
        lines = []
        for row in rows:
            total = float(row.get("total_return") or 0)
            pct = float(row.get("total_return_pct") or 0)
            color = "#137333" if total > 0 else "#c5221f" if total < 0 else "#3c4043"
            name = row.get("name") or row.get("ticker")
            lines.append(
                '<div style="display:flex;justify-content:space-between;gap:12px;'
                'padding:6px 0;border-top:1px solid #eef0f2;">'
                f'<div style="min-width:0;white-space:normal;word-break:break-word;">'
                f'<div style="font-weight:650;">{html_text(name)}</div>'
                f'<div style="color:#5c6770;font-size:0.85rem;">{html_text(row.get("ticker"))}</div>'
                "</div>"
                f'<div style="text-align:right;color:{color};font-weight:650;white-space:normal;">'
                f'<div>{html_text(format_money(total, currency, signed=True))}</div>'
                f"<div>{pct:+.1f}%</div></div></div>"
            )
        body = "".join(lines)
    return (
        '<div style="border:1px solid #e6e8eb;border-radius:10px;padding:12px 14px;background:#fff;min-width:0;">'
        f'<div style="font-weight:700;margin-bottom:4px;">{html_text(title)}</div>'
        f"{body}</div>"
    )


def render_dividend_leaders(report, holdings_rows=None, currency="HKD") -> None:
    """Dividend ranking beside price winners and losers. Price ranking is unchanged."""
    st.markdown("#### 今年股息 / Dividends this year")
    st.caption(
        "與上方股價盈虧分開排列。價格虧損仍在最大輸家；這裡只看今年已收現金。"
        " / Listed separately from price P&L. A price loss stays in the losers list."
    )
    leaders = list((report or {}).get("rows") or [])[:5]
    income = _dividend_card(
        "今年股息最多 / Largest dividend income",
        leaders,
        currency,
        "今年尚未有按除淨日估算的已收股息 / No received dividends estimated for this year",
    )
    cards = [income]
    any_dividend = any(float(row.get("div_ytd") or 0) != 0 for row in holdings_rows or [])
    if any_dividend:
        ranked = total_return_ranking(holdings_rows)
        cards.append(
            _total_return_card(
                "含息總回報最高 / Highest total return",
                ranked,
                currency,
                "沒有持股 / No holdings",
            )
        )
    st.html(
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));'
        'gap:12px;margin:0 0 8px;">'
        + "".join(cards)
        + "</div>"
    )
    if any_dividend:
        st.caption("含息總回報 = 未實現股價盈虧 + 今年股息，不取代上方的股價贏家／輸家。")


def render_dividend_income(report, currency="HKD") -> None:
    """Per-name cash received this year and a monthly chart of that cash."""
    st.markdown("#### 今年股息收入 / Dividend income this year")
    st.caption(dividend_caption(report))
    pending = (report or {}).get("pending") or []
    if (report or {}).get("pay_date_seen") and pending:
        pending_total = float((report or {}).get("pending_total") or 0)
        lines = "".join(
            "<div>"
            f"{html_text(item.get('name'))}（{html_text(item.get('ticker'))}）"
            f" 除淨 {html_text(item.get('ex_date'))}，派息 {html_text(item.get('pay_date'))}："
            f" {html_text(format_money(item.get('amount'), currency))}"
            "</div>"
            for item in pending
        )
        st.html(
            '<div style="background:#f4f7fb;border:1px solid #d5deea;border-radius:8px;'
            'padding:10px 12px;margin:6px 0;">'
            f'<div style="font-weight:650;">待派 / Ex-dividend, not yet paid: '
            f"{html_text(format_money(pending_total, currency))}</div>"
            f'<div style="color:#5c6770;margin-top:4px;">{lines}</div></div>'
        )
    frame = build_income_frame(report)
    if frame.empty:
        st.info("今年尚未有按除淨日估算的已收股息 / No received dividends estimated for this year")
    else:
        decimals = 0 if currency == "HKD" else 2
        styler = frame.style.format(
            {
                "次數": "{:.0f}",
                "今年股息": f"{{:,.{decimals}f}}",
            }
        ).hide(axis="index")
        st.dataframe(
            styler,
            use_container_width=True,
            hide_index=True,
            column_config={
                "代號": st.column_config.TextColumn("代號 / Ticker", width=110),
                "公司": st.column_config.TextColumn("公司 / Company", width=160),
                "次數": st.column_config.TextColumn("次數 / Times paid", width=110),
                "今年股息": st.column_config.TextColumn(f"今年股息 {currency}", width=140),
                "頻率": st.column_config.TextColumn("頻率 / Frequency", width=170),
                "備註": st.column_config.TextColumn("備註 / Note", width=240),
            },
        )
    monthly = (report or {}).get("monthly") or []
    if monthly:
        import plotly.express as px

        chart = px.bar(
            monthly,
            x="label",
            y="amount",
            title="今年股息現金 / Dividend cash by month",
        )
        chart.update_traces(
            marker_color="#4C78A8",
            hovertemplate="%{x}<br>" + currency + " %{y:,.2f}<extra></extra>",
        )
        chart.update_layout(
            xaxis_title="月份 / Month",
            yaxis_title=currency,
            showlegend=False,
            margin=dict(l=8, r=8, t=48, b=8),
        )
        st.plotly_chart(chart, use_container_width=True)


def render_contributors(rows, currency="HKD") -> None:
    winners, losers = contributor_lists(rows)
    st.markdown("#### 最大贏家 / 最大輸家")
    st.caption(CONTRIBUTOR_NOTE)
    left = _contributor_card(
        "最大輸家 / Largest losses",
        losers,
        currency,
        "沒有未實現虧損 / No unrealized losses",
    )
    right = _contributor_card(
        "最大贏家 / Largest gains",
        winners,
        currency,
        "沒有未實現盈利 / No unrealized gains",
    )
    st.html(
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));'
        'gap:12px;margin:0 0 8px;">'
        + left
        + right
        + "</div>"
    )


def _stat_card(label, value, sub="", border="#e6e8eb") -> str:
    sub_html = (
        f'<div style="margin-top:2px;color:#5c6770;font-size:0.85rem;white-space:normal;word-break:break-word;">{html_text(sub)}</div>'
        if sub
        else ""
    )
    return (
        f'<div style="border:1px solid {border};border-radius:10px;padding:10px 12px;background:#fff;min-width:0;">'
        f'<div style="color:#5c6770;font-size:0.8rem;">{html_text(label)}</div>'
        f'<div style="margin-top:4px;font-size:1.15rem;font-weight:650;color:#1f2933;'
        'white-space:normal;overflow:visible;word-break:break-word;">'
        f"{html_text(value)}</div>{sub_html}</div>"
    )


def _industry_bar(industries) -> str:
    if not industries:
        return '<div style="color:#5c6770;">未有行業資料 / No industry mix</div>'
    parts = []
    legend = []
    for index, item in enumerate(industries):
        color = industry_color(item["label"], index)
        weight = float(item["weight"])
        if weight <= 0:
            continue
        parts.append(
            f'<div title="{html_text(item["label"])} {weight:.1f}%" '
            f'style="width:{weight:.4f}%;background:{color};height:100%;"></div>'
        )
        legend.append(
            '<span style="display:inline-flex;align-items:center;gap:6px;margin:6px 14px 0 0;">'
            f'<span style="width:10px;height:10px;border-radius:2px;background:{color};display:inline-block;"></span>'
            f'{html_text(item["label"])} {weight:.1f}%</span>'
        )
    return (
        '<div style="display:flex;width:100%;height:16px;border-radius:8px;overflow:hidden;background:#eee;">'
        + "".join(parts)
        + '</div><div style="font-size:0.92rem;line-height:1.5;">'
        + "".join(legend)
        + "</div>"
    )


def render_balance(rows, total_value, currency="HKD") -> None:
    if not rows:
        return
    snap = balance_snapshot(rows, total_value)
    st.markdown("#### 風險快覽 / Balance")
    st.caption(BALANCE_NOTE)
    top = snap["top1"] or {"name": "—", "ticker": "", "weight": 0.0}
    cells = [
        _stat_card(
            "最大持股 / Top holding",
            f"{top['weight']:.1f}%",
            f"{top['name']} · {top['ticker']}".strip(" ·"),
            border="#e0a100" if snap["concentrated"] else "#e6e8eb",
        ),
        _stat_card(
            "前五大 / Top 5",
            f"{snap['top5_weight']:.1f}%",
            "佔組合市值 / Share of portfolio value",
        ),
        _stat_card(
            "港股 / HK",
            format_money(snap["hk_value"], currency),
            f"{snap['hk_weight']:.1f}%",
        ),
        _stat_card(
            "美股 / US",
            format_money(snap["us_value"], currency),
            f"{snap['us_weight']:.1f}%",
        ),
    ]
    st.html(
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;">'
        + "".join(cells)
        + "</div>"
    )
    st.markdown("**行業比重 / Industry mix**")
    st.html(_industry_bar(snap["industries"]))
    notices = []
    for item in snap["warnings"]:
        notice = concentration_notice(item, snap["warn_pct"])
        notices.append(
            '<div style="background:#fff6e5;border:1px solid #f0d3a0;border-radius:8px;'
            'padding:10px 12px;margin-top:8px;">'
            f'<div style="font-weight:650;white-space:normal;">{html_text(notice["zh"])}</div>'
            f'<div style="color:#5c6770;margin-top:2px;white-space:normal;">{html_text(notice["en"])}</div>'
            "</div>"
        )
    if notices:
        st.html("".join(notices))


def render_compact_holdings(
    rows,
    total_value,
    currency="HKD",
    sort_key="holdings_sort",
    empty_message="無持股數據 / No holdings",
) -> None:
    """Default holdings table: no RSI and no buy/sell signal column."""
    if not rows:
        st.info(empty_message)
        return
    labels = dict(SORT_CHOICES)
    choice = st.radio(
        "排序 / Sort",
        list(labels.keys()),
        format_func=lambda key: labels[key],
        horizontal=True,
        key=sort_key,
    )
    frame = build_compact_frame(rows, total_value, choice)
    st.caption(HOLDINGS_NOTE)
    st.dataframe(
        compact_styler(frame, currency),
        use_container_width=True,
        hide_index=True,
        column_config={
            "代號": st.column_config.TextColumn("代號 / Ticker", width=120),
            "公司": st.column_config.TextColumn("公司 / Company", width=160),
            "權重%": st.column_config.TextColumn("權重%", width=90),
            "成本": st.column_config.TextColumn(f"成本 {currency}", width=120),
            "市值": st.column_config.TextColumn(f"市值 {currency}", width=130),
            "盈虧$": st.column_config.TextColumn(f"盈虧$ {currency}", width=130),
            "盈虧%": st.column_config.TextColumn("盈虧%", width=90),
            "今年股息": st.column_config.TextColumn(f"今年股息 {currency}", width=130),
            "含息盈虧": st.column_config.TextColumn(f"含息盈虧 {currency}", width=140),
            "含息%": st.column_config.TextColumn("含息%", width=90),
        },
    )
