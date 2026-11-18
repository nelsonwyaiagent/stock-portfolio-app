"""Year-to-date cash dividends from a buy/sell ledger and dividend events.

This module does not write to the database and does not change the
average-cost formula. It never inserts DIVIDEND rows into the ledger.

「已收」 is cash whose recognition date falls in the Hong Kong calendar
year (1 January through today). Yahoo chart events reliably provide the
ex-date and the cash amount per share, not a pay date. When ``pay_date``
is missing, the ex-date is the recognition date and dividends that have
gone ex but are not yet paid cannot be split out as 待派.

Shares entitled to an event are the net BUY minus SELL quantity whose
trade date is strictly before the ex-date. A sale after the ex-date still
counts. A purchase on or after the ex-date does not. Cash from a name
that was later sold is kept when those shares were held on the ex-date.

USD amounts are converted to HKD with the pay-date USDHKD rate when a
pay date and a rate are both available. Otherwise the app's spot rate is
used. The report records which source was used.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

HONG_KONG = ZoneInfo("Asia/Hong_Kong")

FREQUENCY_LABELS = {
    "monthly": "每月 monthly",
    "quarterly": "每季 quarterly",
    "semi-annual": "每半年 semi-annual",
    "annual": "每年 annual",
    "unknown": "未知 unknown",
}

# Closest of these canonical schedules. A tie prefers the more frequent one.
_FREQUENCY_TARGETS = (
    ("monthly", 12),
    ("quarterly", 4),
    ("semi-annual", 2),
    ("annual", 1),
)

_NON_CASH_TOKENS = ("scrip", "stock", "split", "specie", "bonus issue", "capital gain")

SOLD_NOTE = "已沽出，今年仍有已收股息"

ESTIMATE_NOTE = (
    "按除淨日持股估算的現金股息，並非券商入帳金額，亦非買賣建議。"
    " / Cash dividends estimated from shares held before each ex-date. "
    "Not a broker statement and not a trade suggestion."
)

EX_DATE_FALLBACK_NOTE = (
    "Yahoo 的股息歷史只可靠提供除淨日及每股現金金額，沒有派息日，"
    "因此「已收」以除淨日是否落在今年 1 月 1 日至今天判斷，"
    "已除淨但未派發的金額未能分開列作待派。"
    " / Yahoo dividend history provides the ex-date and cash per share, "
    "not a pay date. Received cash is the ex-date falling in this calendar "
    "year. Dividends that have gone ex but are not yet paid are not shown "
    "separately."
)

PAY_DATE_NOTE = (
    "「已收」指派息日落在今年 1 月 1 日至今天。已除淨而派息日未到的金額列作待派。"
    " / Received means the pay date falls between 1 January and today. "
    "Dividends that have gone ex and are not yet paid are listed as pending."
)

MIXED_DATE_NOTE = (
    "有派息日的股息按派息日計入今年已收；沒有派息日的仍按除淨日估算。"
    "只有能看到派息日、且已除淨未派發的金額會列作待派。"
    " / Events with a pay date count when that pay date is this year. "
    "Events without one still use the ex-date. Pending is shown only when a pay date is known."
)

NO_LEDGER_NOTE = (
    "沒有帶日期的買賣紀錄，未能估算今年股息。"
    " / No dated buy/sell ledger, so year-to-date dividends cannot be estimated."
)


def hong_kong_today() -> date:
    """Today's date in Hong Kong, which is the calendar this report uses."""
    return datetime.now(HONG_KONG).date()


def parse_date(value):
    """Calendar date from a date, datetime, or ISO-like string."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _symbol(value) -> str:
    return str(value or "").strip().upper()


def _kind(value) -> str:
    text = str(value or "cash").strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def is_cash_dividend(event) -> bool:
    """True for a positive cash dividend. Stock, scrip, and splits are not cash."""
    if not isinstance(event, dict):
        return False
    kind = _kind(event.get("kind"))
    if any(token in kind for token in _NON_CASH_TOKENS):
        return False
    try:
        amount = float(event.get("amount"))
    except (TypeError, ValueError):
        return False
    if amount != amount or amount <= 0:  # NaN or non-positive
        return False
    return parse_date(event.get("ex_date")) is not None


def shares_held_before(transactions, day) -> float:
    """Net BUY minus SELL quantity with a trade date strictly before ``day``.

    Other transaction types, including DIVIDEND, are ignored so cash
    dividends never change the share count. The result is not clamped.
    """
    cutoff = parse_date(day)
    if cutoff is None:
        return 0.0
    total = 0.0
    for tx in transactions or []:
        if not isinstance(tx, dict):
            continue
        traded = parse_date(tx.get("transaction_date"))
        if traded is None or traded >= cutoff:
            continue
        try:
            quantity = float(tx.get("quantity") or 0)
        except (TypeError, ValueError):
            continue
        action = str(tx.get("transaction_type") or "").strip().upper()
        if action == "BUY":
            total += quantity
        elif action == "SELL":
            total -= quantity
    return total


def shares_entitled(transactions, ex_date) -> float:
    """Shares that receive the dividend: held strictly before the ex-date."""
    return max(shares_held_before(transactions, ex_date), 0.0)


def infer_frequency(payment_count: int) -> str:
    """Map a trailing-12-month cash payment count to a schedule.

    The count is matched to the nearest of 12 (monthly), 4 (quarterly),
    2 (semi-annual), and 1 (annual). An equal distance prefers the more
    frequent schedule. The count is a property of the security's ex-dates,
    not of one ticker and not of how many payments this portfolio received.
    """
    try:
        count = int(payment_count)
    except (TypeError, ValueError):
        return "unknown"
    if count <= 0:
        return "unknown"
    name, _target = min(_FREQUENCY_TARGETS, key=lambda item: (abs(item[1] - count), -item[1]))
    return name


def trailing_start(today) -> date:
    """First day of the trailing 12 months ending on ``today`` (inclusive)."""
    today = parse_date(today)
    try:
        return today.replace(year=today.year - 1)
    except ValueError:
        return today.replace(year=today.year - 1, day=28)


def trailing_payment_count(events, today) -> int:
    """Cash ex-dates in the trailing 12 months, whether or not we held shares."""
    today = parse_date(today)
    if today is None:
        return 0
    start = trailing_start(today)
    count = 0
    for event in events or []:
        if not is_cash_dividend(event):
            continue
        ex_date = parse_date(event.get("ex_date"))
        if ex_date is not None and start <= ex_date <= today:
            count += 1
    return count


def rate_on_or_before(rates, day, lookback_days=7):
    """Positive FX rate on ``day`` or the nearest earlier date within the lookback.

    ``rates`` maps ISO dates (or date keys) to USDHKD closes. Weekends and
    holidays fall back to the previous session. Returns None when no rate
    is close enough to treat as the pay-date rate.
    """
    day = parse_date(day)
    if day is None or not rates:
        return None
    normalized = {}
    for key, value in rates.items():
        parsed = parse_date(key)
        if parsed is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number == number and number > 0:
            normalized[parsed] = number
    for offset in range(int(lookback_days) + 1):
        found = normalized.get(day - timedelta(days=offset))
        if found:
            return found
    return None


def events_from_series(series) -> list:
    """Cash events from a Yahoo-style dividend series indexed by ex-date.

    The series has no pay date. Splits and capital gains are not part of
    this series. Non-positive amounts are dropped.
    """
    if series is None:
        return []
    try:
        pairs = list(series.items())
    except Exception:
        return []
    events = []
    for stamp, amount in pairs:
        try:
            value = float(amount)
        except (TypeError, ValueError):
            continue
        if value != value or value <= 0:
            continue
        try:
            ex_date = pd.Timestamp(stamp).date()
        except Exception:
            continue
        events.append(
            {
                "ex_date": ex_date.isoformat(),
                "pay_date": None,
                "amount": value,
                "kind": "cash",
            }
        )
    return events


def yahoo_cash_dividends(ticker: str) -> list:
    """Cash dividends for one ticker from Yahoo. Empty list when the lookup fails.

    Yahoo's chart dividend event is ``{amount, date}`` where ``date`` is the
    ex-date. Pay date is left unset so the report uses the ex-date fallback.
    """
    try:
        import yfinance as yf

        series = yf.Ticker(ticker).dividends
    except Exception:
        return []
    return events_from_series(series)


def yahoo_usd_hkd_rates() -> dict:
    """ISO date to USDHKD close for pay-date conversion. Empty when unavailable."""
    try:
        import yfinance as yf

        history = yf.Ticker("USDHKD=X").history(period="5y")
        closes = history["Close"]
    except Exception:
        return {}
    rates = {}
    try:
        pairs = closes.items()
    except Exception:
        return {}
    for stamp, close in pairs:
        try:
            value = float(close)
            day = pd.Timestamp(stamp).date().isoformat()
        except (TypeError, ValueError):
            continue
        if value == value and value > 0:
            rates[day] = value
    return rates


def _money(value) -> float:
    return round(float(value), 6)


def _to_display(native, currency, report_currency, basis, recognition, spot_fx, fx_on_pay_date):
    """Return (amount in the report currency, fx source label)."""
    currency = (currency or report_currency or "HKD").upper()
    report_currency = (report_currency or "HKD").upper()
    native = float(native)
    if currency == report_currency:
        if currency == "USD":
            return native, "usd"
        if currency == "HKD":
            return native, "hkd"
        return native, "native"
    if currency == "USD" and report_currency == "HKD":
        if basis == "pay_date" and fx_on_pay_date is not None:
            try:
                rate = fx_on_pay_date(recognition)
            except Exception:
                rate = None
            try:
                rate = float(rate)
            except (TypeError, ValueError):
                rate = None
            if rate and rate > 0:
                return native * rate, "pay_date"
        try:
            spot = float(spot_fx)
        except (TypeError, ValueError):
            spot = 0.0
        if spot > 0:
            return native * spot, "spot"
        return native, "unconverted"
    if currency == "HKD" and report_currency == "USD":
        try:
            spot = float(spot_fx)
        except (TypeError, ValueError):
            spot = 0.0
        if spot > 0:
            return native / spot, "spot"
        return native, "unconverted"
    return native, "unconverted"


def _recognition(event):
    """(date, basis) using the pay date when Yahoo supplied one, else the ex-date."""
    pay_date = parse_date(event.get("pay_date"))
    ex_date = parse_date(event.get("ex_date"))
    if pay_date is not None:
        return pay_date, "pay_date"
    return ex_date, "ex_date"


def empty_dividend_report(today=None, report_currency="HKD", spot_fx=None, ledger_empty=True) -> dict:
    today = parse_date(today) or hong_kong_today()
    return {
        "as_of": today.isoformat(),
        "year": today.year,
        "currency": report_currency,
        "total_ytd": 0.0,
        "pending_total": 0.0,
        "pay_date_seen": False,
        "recognition": "ex_date",
        "fx_sources": [],
        "spot_fx": spot_fx,
        "ledger_empty": ledger_empty,
        "rows": [],
        "monthly": _monthly_buckets(today, {}),
        "pending": [],
    }


def _monthly_buckets(today, totals) -> list:
    rows = []
    for month in range(1, today.month + 1):
        rows.append(
            {
                "month": month,
                "label": f"{month}月",
                "amount": _money(totals.get(month, 0.0)),
            }
        )
    return rows


def _group_transactions(transactions) -> dict:
    grouped = {}
    for tx in transactions or []:
        if not isinstance(tx, dict):
            continue
        symbol = _symbol(tx.get("symbol"))
        if not symbol:
            continue
        grouped.setdefault(symbol, []).append(tx)
    return grouped


def build_dividend_report(
    transactions,
    events_by_symbol,
    *,
    today=None,
    currency_by_symbol=None,
    default_currency="HKD",
    report_currency="HKD",
    spot_fx=7.82,
    fx_on_pay_date=None,
    names=None,
) -> dict:
    """Estimate this calendar year's cash dividends for a buy/sell ledger.

    ``transactions`` is not modified. ``events_by_symbol`` maps a ticker to
    a list of ``{ex_date, pay_date, amount, kind}`` events.
    """
    today = parse_date(today) or hong_kong_today()
    year_start = date(today.year, 1, 1)
    report_currency = (report_currency or "HKD").upper()
    default_currency = (default_currency or report_currency).upper()
    currency_by_symbol = {_symbol(key): value for key, value in (currency_by_symbol or {}).items()}
    names = {_symbol(key): value for key, value in (names or {}).items()}
    grouped = _group_transactions(transactions)
    events_by_symbol = {_symbol(key): value for key, value in (events_by_symbol or {}).items()}

    if not grouped:
        report = empty_dividend_report(today, report_currency, spot_fx, ledger_empty=True)
        return report

    pay_date_seen = False
    cash_events_seen = 0
    fx_sources = set()
    month_totals = {}
    rows = []
    pending_rows = []

    symbols = sorted(set(grouped) | {_symbol(key) for key in events_by_symbol})
    for symbol in symbols:
        txs = grouped.get(symbol, [])
        if not txs:
            continue
        events = events_by_symbol.get(symbol, [])
        currency = str(currency_by_symbol.get(symbol, default_currency) or default_currency).upper()
        frequency = infer_frequency(trailing_payment_count(events, today))
        current_qty = shares_held_before(txs, today + timedelta(days=1))
        payments = []
        pending_amount = 0.0
        ytd_display = 0.0
        ytd_native = 0.0
        times_paid = 0

        for event in events or []:
            if not is_cash_dividend(event):
                continue
            cash_events_seen += 1
            if parse_date(event.get("pay_date")) is not None:
                pay_date_seen = True
            ex_date = parse_date(event.get("ex_date"))
            recognition, basis = _recognition(event)
            if recognition is None or ex_date is None:
                continue
            shares = shares_entitled(txs, ex_date)
            if shares <= 0:
                continue
            per_share = float(event["amount"])
            native = shares * per_share
            display, fx_source = _to_display(
                native,
                currency,
                report_currency,
                basis,
                recognition,
                spot_fx,
                fx_on_pay_date,
            )
            if fx_source in {"pay_date", "spot"}:
                fx_sources.add(fx_source)
            record = {
                "ex_date": ex_date.isoformat(),
                "pay_date": parse_date(event.get("pay_date")).isoformat()
                if parse_date(event.get("pay_date"))
                else None,
                "recognition": basis,
                "shares": shares,
                "amount_per_share": per_share,
                "native": _money(native),
                "display": _money(display),
                "fx_source": fx_source,
                "month": recognition.month,
            }
            gone_ex = ex_date <= today
            received = year_start <= recognition <= today
            pending = basis == "pay_date" and gone_ex and recognition > today
            if received:
                ytd_display += display
                ytd_native += native
                times_paid += 1
                month_totals[recognition.month] = month_totals.get(recognition.month, 0.0) + display
                payments.append(record)
            elif pending:
                pending_amount += display
                pending_rows.append(
                    {
                        "ticker": symbol,
                        "name": names.get(symbol) or symbol,
                        "ex_date": ex_date.isoformat(),
                        "pay_date": record["pay_date"],
                        "amount": _money(display),
                        "shares": shares,
                    }
                )

        if ytd_display <= 0 and pending_amount <= 0:
            continue
        sold = current_qty <= 0 and ytd_display > 0
        notes = []
        if sold:
            notes.append(SOLD_NOTE)
        if pending_amount > 0:
            notes.append("另有待派")
        rows.append(
            {
                "ticker": symbol,
                "name": names.get(symbol) or symbol,
                "currency": currency,
                "ytd": _money(ytd_display),
                "ytd_native": _money(ytd_native),
                "times_paid": times_paid,
                "frequency": frequency,
                "frequency_label": FREQUENCY_LABELS.get(frequency, FREQUENCY_LABELS["unknown"]),
                "current_qty": current_qty,
                "sold": sold,
                "note": "；".join(notes),
                "pending": _money(pending_amount),
                "payments": payments,
            }
        )

    rows.sort(key=lambda row: (-row["ytd"], row["ticker"]))
    if not pay_date_seen:
        recognition = "ex_date"
    elif cash_events_seen and pay_date_seen:
        # Mixed when any considered cash event had no pay date. Events are
        # re-scanned cheaply from the caller's lists.
        missing_pay = False
        for event_list in events_by_symbol.values():
            for event in event_list or []:
                if is_cash_dividend(event) and parse_date(event.get("pay_date")) is None:
                    missing_pay = True
                    break
            if missing_pay:
                break
        recognition = "mixed" if missing_pay else "pay_date"
    else:
        recognition = "pay_date"

    return {
        "as_of": today.isoformat(),
        "year": today.year,
        "currency": report_currency,
        "total_ytd": _money(sum(row["ytd"] for row in rows)),
        "pending_total": _money(sum(row["pending"] for row in rows)),
        "pay_date_seen": pay_date_seen,
        "recognition": recognition,
        "fx_sources": sorted(fx_sources),
        "spot_fx": spot_fx,
        "ledger_empty": False,
        "rows": rows,
        "monthly": _monthly_buckets(today, month_totals),
        "pending": pending_rows,
    }


def apply_ytd(rows, report) -> list:
    """Copy display-currency YTD cash onto holding rows. Price P&L is untouched."""
    amounts = {_symbol(row.get("ticker")): row["ytd"] for row in (report or {}).get("rows", [])}
    for row in rows or []:
        ticker = _symbol(row.get("ticker") or row.get("股票代號"))
        row["div_ytd"] = amounts.get(ticker, 0.0)
    return rows


def dividend_caption(report, spot_fx=None) -> str:
    """User-facing explanation of the estimate, the date rule, and any FX label."""
    report = report or {}
    if report.get("ledger_empty"):
        return NO_LEDGER_NOTE
    parts = [ESTIMATE_NOTE]
    recognition = report.get("recognition") or "ex_date"
    if recognition == "pay_date":
        parts.append(PAY_DATE_NOTE)
    elif recognition == "mixed":
        parts.append(MIXED_DATE_NOTE)
    else:
        parts.append(EX_DATE_FALLBACK_NOTE)
    sources = set(report.get("fx_sources") or [])
    rate = spot_fx if spot_fx is not None else report.get("spot_fx")
    if sources == {"pay_date"}:
        parts.append("美元股息按派息日美元兌港元匯率折算。 / USD dividends use the pay-date USDHKD rate.")
    elif sources == {"spot"}:
        rate_text = f"{float(rate):.4f}" if rate else "現貨"
        parts.append(
            f"美元股息按現貨匯率折算（1 USD = {rate_text} HKD，與頁面匯率相同），"
            "因為沒有可用的派息日匯率。"
            " / USD dividends use the app spot rate because a pay-date rate was not available."
        )
    elif sources:
        parts.append(
            "美元股息：有派息日匯率的用派息日，其餘用現貨匯率。"
            " / USD dividends use the pay-date rate when it exists and the spot rate otherwise."
        )
    return " ".join(parts)


INCOME_COLUMNS = ["代號", "公司", "次數", "今年股息", "頻率", "備註"]


def build_income_frame(report) -> pd.DataFrame:
    """One row per name with received or pending cash this year, largest first."""
    records = []
    for row in (report or {}).get("rows", []):
        records.append(
            {
                "代號": row.get("ticker") or "",
                "公司": row.get("name") or row.get("ticker") or "",
                "次數": int(row.get("times_paid") or 0),
                "今年股息": float(row.get("ytd") or 0),
                "頻率": row.get("frequency_label") or FREQUENCY_LABELS["unknown"],
                "備註": row.get("note") or "",
            }
        )
    frame = pd.DataFrame(records, columns=INCOME_COLUMNS)
    if frame.empty:
        return frame
    return frame.sort_values(["今年股息", "代號"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
