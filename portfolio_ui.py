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
)

__all__ = [
    "format_money",
    "render_balance",
    "render_compact_holdings",
    "render_contributors",
    "render_metric_tiles",
    "security_profile",
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
        },
    )
