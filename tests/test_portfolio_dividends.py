"""Dividend entitlement, calendar year, FX, frequency, and total-return columns.

No network and no database. Yahoo responses are passed in as plain events.
"""

import copy
import unittest
from datetime import date

import pandas as pd

from portfolio_display import (
    build_compact_frame,
    contributor_lists,
    total_return_ranking,
)
from portfolio_dividends import (
    SOLD_NOTE,
    apply_ytd,
    build_dividend_report,
    build_income_frame,
    dividend_caption,
    events_from_series,
    infer_frequency,
    rate_on_or_before,
    shares_entitled,
    shares_held_before,
    trailing_payment_count,
)
from portfolio_ui import ytd_metric


TODAY = date(2026, 6, 15)


def buy(symbol, quantity, traded):
    return {
        "symbol": symbol,
        "transaction_type": "BUY",
        "quantity": quantity,
        "transaction_date": traded,
    }


def sell(symbol, quantity, traded):
    return {
        "symbol": symbol,
        "transaction_type": "SELL",
        "quantity": quantity,
        "transaction_date": traded,
    }


def cash(ex_date, amount, pay_date=None, kind="cash"):
    return {"ex_date": ex_date, "pay_date": pay_date, "amount": amount, "kind": kind}


class EntitlementTests(unittest.TestCase):
    def test_quantity_on_ex_date_nets_earlier_buys_and_sells(self):
        txs = [
            buy("3416.HK", 100, "2026-01-10"),
            buy("3416.HK", 40, "2026-02-01"),
            sell("3416.HK", 15, "2026-02-20"),
        ]
        self.assertEqual(shares_entitled(txs, "2026-03-01"), 125)

    def test_sale_on_or_after_ex_date_still_counts(self):
        txs = [
            buy("3416.HK", 100, "2026-01-10"),
            sell("3416.HK", 100, "2026-03-01"),
            sell("0700.HK", 5, "2026-03-02"),
        ]
        held = [buy("3416.HK", 100, "2026-01-10"), sell("3416.HK", 40, "2026-03-05")]
        self.assertEqual(shares_entitled(txs, "2026-03-01"), 100)
        self.assertEqual(shares_entitled(held, "2026-03-01"), 100)
        self.assertEqual(shares_held_before(held, "2026-03-06"), 60)

    def test_buy_on_or_after_ex_date_does_not_count(self):
        before = [buy("0700.HK", 10, "2026-05-14")]
        on_day = [buy("0700.HK", 10, "2026-05-15")]
        after = [buy("0700.HK", 10, "2026-05-16")]
        self.assertEqual(shares_entitled(before, "2026-05-15"), 10)
        self.assertEqual(shares_entitled(on_day, "2026-05-15"), 0)
        self.assertEqual(shares_entitled(after, "2026-05-15"), 0)

    def test_dividend_rows_do_not_change_quantity_and_ledger_is_not_modified(self):
        txs = [
            buy("0700.HK", 10, "2026-01-02"),
            {
                "symbol": "0700.HK",
                "transaction_type": "DIVIDEND",
                "quantity": 10,
                "transaction_date": "2026-05-01",
            },
        ]
        original = copy.deepcopy(txs)
        report = build_dividend_report(
            txs,
            {"0700.HK": [cash("2026-05-15", 1.0)]},
            today=TODAY,
        )
        self.assertEqual(txs, original)
        self.assertEqual(shares_entitled(txs, "2026-05-15"), 10)
        self.assertEqual(report["rows"][0]["ytd"], 10)
        self.assertEqual([tx["transaction_type"] for tx in txs], ["BUY", "DIVIDEND"])

    def test_oversold_before_ex_date_is_not_a_negative_dividend(self):
        txs = [buy("0700.HK", 5, "2026-01-02"), sell("0700.HK", 8, "2026-02-01")]
        self.assertEqual(shares_entitled(txs, "2026-05-15"), 0)

    def test_symbols_do_not_share_a_ledger(self):
        txs = [buy("0700.HK", 10, "2026-01-02"), buy("0941.HK", 3, "2026-01-02")]
        self.assertEqual(shares_entitled(txs[:1], "2026-05-15"), 10)
        report = build_dividend_report(
            txs,
            {
                "0700.HK": [cash("2026-05-15", 2)],
                "0941.HK": [cash("2026-03-01", 4)],
            },
            today=TODAY,
        )
        by_ticker = {row["ticker"]: row["ytd"] for row in report["rows"]}
        self.assertEqual(by_ticker["0700.HK"], 20)
        self.assertEqual(by_ticker["0941.HK"], 12)


class CalendarAndPendingTests(unittest.TestCase):
    def test_pay_date_filters_the_hong_kong_calendar_year(self):
        txs = [buy("0700.HK", 10, "2024-01-02")]
        events = [
            cash("2025-12-01", 1, pay_date="2025-12-20"),
            cash("2025-12-15", 1, pay_date="2026-01-10"),
            cash("2026-02-01", 1, pay_date="2026-02-20"),
            cash("2026-06-01", 1, pay_date="2026-07-01"),
            cash("2026-06-20", 1, pay_date="2026-07-05"),
        ]
        report = build_dividend_report(txs, {"0700.HK": events}, today=TODAY)
        row = report["rows"][0]
        self.assertEqual(report["recognition"], "pay_date")
        self.assertEqual(row["times_paid"], 2)
        self.assertEqual(row["ytd"], 20)
        self.assertEqual(report["total_ytd"], 20)
        self.assertEqual(report["pending_total"], 10)
        self.assertEqual(report["pending"][0]["pay_date"], "2026-07-01")
        self.assertNotIn("2026-06-20", [item["ex_date"] for item in report["pending"]])
        january = report["monthly"][0]
        self.assertEqual(january["label"], "1月")
        self.assertEqual(january["amount"], 10)
        self.assertEqual(report["monthly"][1]["amount"], 10)
        self.assertEqual(len(report["monthly"]), 6)
        self.assertIn("待派", dividend_caption(report))
        self.assertNotIn("沒有派息日", dividend_caption(report))

    def test_ex_date_fallback_when_yahoo_has_no_pay_date(self):
        txs = [buy("3416.HK", 100, "2025-06-01")]
        events = [
            cash("2025-12-31", 0.1),
            cash("2026-01-31", 0.2),
            cash("2026-06-15", 0.3),
            cash("2026-06-16", 0.4),
        ]
        report = build_dividend_report(txs, {"3416.HK": events}, today=TODAY)
        row = report["rows"][0]
        self.assertFalse(report["pay_date_seen"])
        self.assertEqual(report["recognition"], "ex_date")
        self.assertEqual(report["pending_total"], 0)
        self.assertEqual(report["pending"], [])
        self.assertEqual(row["times_paid"], 2)
        self.assertAlmostEqual(row["ytd"], 50)
        self.assertEqual([payment["recognition"] for payment in row["payments"]], ["ex_date", "ex_date"])
        caption = dividend_caption(report)
        self.assertIn("除淨日", caption)
        self.assertIn("待派", caption)
        self.assertIn("按除淨日持股估算", caption)

    def test_only_the_dividend_after_the_purchase_is_received(self):
        txs = [buy("3416.HK", 100, "2026-03-01")]
        events = [cash("2026-02-27", 0.5), cash("2026-04-30", 0.5)]
        report = build_dividend_report(txs, {"3416.HK": events}, today=TODAY)
        self.assertEqual(report["rows"][0]["times_paid"], 1)
        self.assertEqual(report["rows"][0]["ytd"], 50)


class FxTests(unittest.TestCase):
    def test_pay_date_fx_is_used_when_the_rate_exists(self):
        txs = [buy("AAPL", 10, "2026-01-02")]

        def fx_on_pay_date(day):
            self.assertEqual(day, date(2026, 3, 20))
            return 7.75

        report = build_dividend_report(
            txs,
            {"AAPL": [cash("2026-03-01", 1.0, pay_date="2026-03-20")]},
            today=TODAY,
            default_currency="USD",
            report_currency="HKD",
            spot_fx=7.8,
            fx_on_pay_date=fx_on_pay_date,
        )
        self.assertAlmostEqual(report["total_ytd"], 77.5)
        self.assertEqual(report["rows"][0]["payments"][0]["fx_source"], "pay_date")
        self.assertEqual(report["fx_sources"], ["pay_date"])
        self.assertIn("派息日", dividend_caption(report))

    def test_spot_fx_is_the_fallback_and_is_labeled(self):
        txs = [buy("AAPL", 10, "2026-01-02")]
        report = build_dividend_report(
            txs,
            {"AAPL": [cash("2026-03-01", 1.0)]},
            today=TODAY,
            default_currency="USD",
            report_currency="HKD",
            spot_fx=7.8,
            fx_on_pay_date=lambda _day: 9.99,
        )
        self.assertAlmostEqual(report["total_ytd"], 78)
        self.assertEqual(report["rows"][0]["payments"][0]["fx_source"], "spot")
        caption = dividend_caption(report, spot_fx=7.8)
        self.assertIn("現貨", caption)
        self.assertIn("7.8000", caption)

    def test_hkd_dividends_are_not_converted(self):
        txs = [buy("3416.HK", 50, "2026-01-02")]
        report = build_dividend_report(
            txs,
            {"3416.HK": [cash("2026-01-31", 0.14)]},
            today=TODAY,
            spot_fx=7.8,
        )
        self.assertAlmostEqual(report["total_ytd"], 7)
        self.assertEqual(report["fx_sources"], [])
        self.assertNotIn("現貨", dividend_caption(report))

    def test_usd_report_keeps_native_dollars(self):
        txs = [buy("AAPL", 4, "2026-01-02")]
        report = build_dividend_report(
            txs,
            {"AAPL": [cash("2026-02-09", 0.25)]},
            today=TODAY,
            default_currency="USD",
            report_currency="USD",
            spot_fx=7.8,
        )
        self.assertAlmostEqual(report["total_ytd"], 1)
        self.assertEqual(report["currency"], "USD")

    def test_weekend_pay_date_uses_the_previous_session(self):
        rates = {"2026-03-20": 7.75}
        sunday = date(2026, 3, 22)
        self.assertEqual(rate_on_or_before(rates, sunday), 7.75)
        self.assertIsNone(rate_on_or_before(rates, date(2026, 3, 28), lookback_days=6))


class FrequencyTests(unittest.TestCase):
    def test_canonical_counts_and_ties(self):
        self.assertEqual(infer_frequency(0), "unknown")
        self.assertEqual(infer_frequency(1), "annual")
        self.assertEqual(infer_frequency(2), "semi-annual")
        self.assertEqual(infer_frequency(4), "quarterly")
        self.assertEqual(infer_frequency(3), "quarterly")
        self.assertEqual(infer_frequency(5), "quarterly")
        self.assertEqual(infer_frequency(12), "monthly")
        self.assertEqual(infer_frequency(11), "monthly")
        self.assertEqual(infer_frequency(10), "monthly")
        self.assertEqual(infer_frequency(8), "monthly")

    def test_frequency_uses_trailing_twelve_months_not_one_ticker(self):
        # Quarterly payer: two payments fall in this calendar year, four in T12M.
        quarterly = [
            cash("2025-08-11", 0.26),
            cash("2025-11-10", 0.26),
            cash("2026-02-09", 0.26),
            cash("2026-05-11", 0.26),
        ]
        monthly = [cash(f"2026-{month:02d}-28", 0.15) for month in range(1, 7)]
        monthly += [cash(f"2025-{month:02d}-28", 0.15) for month in range(7, 13)]
        annual = [cash("2025-05-16", 4.5), cash("2026-05-15", 5.3)]
        self.assertEqual(trailing_payment_count(quarterly, TODAY), 4)
        # June's payment is still in the future on 15 June, so the trailing year has 11.
        self.assertEqual(trailing_payment_count(monthly, TODAY), 11)
        self.assertEqual(infer_frequency(11), "monthly")
        self.assertEqual(trailing_payment_count(annual, TODAY), 1)
        txs = [
            buy("AAPL", 1, "2025-01-02"),
            buy("3416.HK", 1, "2025-01-02"),
            buy("0700.HK", 1, "2025-01-02"),
        ]
        report = build_dividend_report(
            txs,
            {"AAPL": quarterly, "3416.HK": monthly, "0700.HK": annual},
            today=TODAY,
            currency_by_symbol={"AAPL": "USD"},
            report_currency="USD",
        )
        labels = {row["ticker"]: row["frequency"] for row in report["rows"]}
        self.assertEqual(labels["AAPL"], "quarterly")
        self.assertEqual(labels["3416.HK"], "monthly")
        self.assertEqual(labels["0700.HK"], "annual")
        aapl = next(row for row in report["rows"] if row["ticker"] == "AAPL")
        self.assertEqual(aapl["times_paid"], 2)


class CashOnlyTests(unittest.TestCase):
    def test_stock_and_scrip_are_not_cash(self):
        txs = [buy("0700.HK", 10, "2026-01-02")]
        events = [
            cash("2026-03-01", 5, kind="scrip"),
            cash("2026-04-01", 5, kind="stock dividend"),
            cash("2026-04-15", 2, kind="split"),
            cash("2026-05-01", 1, kind="cash"),
            {"ex_date": "2026-05-20", "amount": 0, "kind": "cash"},
        ]
        report = build_dividend_report(txs, {"0700.HK": events}, today=TODAY)
        self.assertEqual(report["rows"][0]["times_paid"], 1)
        self.assertEqual(report["rows"][0]["ytd"], 10)

    def test_yahoo_series_uses_the_exchange_date_and_has_no_pay_date(self):
        series = pd.Series(
            [0.14],
            index=[pd.Timestamp("2026-03-31 09:30:00", tz="Asia/Hong_Kong")],
        )
        events = events_from_series(series)
        self.assertEqual(events, [{"ex_date": "2026-03-31", "pay_date": None, "amount": 0.14, "kind": "cash"}])
        empty = events_from_series(pd.Series([0.0], index=[pd.Timestamp("2026-01-01")]))
        self.assertEqual(empty, [])


class SoldNameTests(unittest.TestCase):
    def test_sold_after_ex_date_stays_in_the_income_list(self):
        txs = [buy("3416.HK", 100, "2026-01-02"), sell("3416.HK", 100, "2026-04-02")]
        report = build_dividend_report(
            txs,
            {"3416.HK": [cash("2026-03-31", 0.14), cash("2026-04-30", 0.14)]},
            today=TODAY,
            names={"3416.HK": "國指備兌ETF"},
        )
        row = report["rows"][0]
        self.assertEqual(row["ytd"], 14)
        self.assertEqual(row["times_paid"], 1)
        self.assertTrue(row["sold"])
        self.assertEqual(row["current_qty"], 0)
        self.assertIn(SOLD_NOTE, row["note"])
        frame = build_income_frame(report)
        self.assertEqual(frame.iloc[0]["代號"], "3416.HK")
        self.assertIn("已沽出", frame.iloc[0]["備註"])


class TotalReturnTests(unittest.TestCase):
    def test_price_pnl_is_unchanged_and_total_return_adds_ytd_cash(self):
        rows = [
            {
                "ticker": "3416.HK",
                "name": "國指備兌ETF",
                "pnl": -100,
                "pnl_pct": -25,
                "div_ytd": 30,
                "cost_total": 400,
                "market_value": 300,
            },
            {
                "ticker": "1299.HK",
                "name": "友邦保險",
                "pnl": 10,
                "pnl_pct": 5,
                "div_ytd": 0,
                "cost_total": 200,
                "market_value": 210,
            },
        ]
        frame = build_compact_frame(rows, 510)
        loser = frame.set_index("代號").loc["3416.HK"]
        self.assertEqual(loser["盈虧$"], -100)
        self.assertEqual(loser["盈虧%"], -25)
        self.assertEqual(loser["今年股息"], 30)
        self.assertEqual(loser["含息盈虧"], -70)
        self.assertEqual(loser["含息%"], -17.5)

    def test_price_ranking_stays_put_when_dividends_change_total_return(self):
        rows = [
            {"ticker": "3416.HK", "name": "國指備兌ETF", "pnl": -100, "pnl_pct": -25, "div_ytd": 250, "cost_total": 400},
            {"ticker": "1299.HK", "name": "友邦保險", "pnl": 10, "pnl_pct": 5, "div_ytd": 1, "cost_total": 200},
        ]
        _winners, losers = contributor_lists(rows)
        self.assertEqual(losers[0]["ticker"], "3416.HK")
        ranking = total_return_ranking(rows)
        self.assertEqual(ranking[0]["ticker"], "3416.HK")
        self.assertEqual(ranking[0]["total_return"], 150)
        self.assertEqual(ranking[1]["ticker"], "1299.HK")

    def test_apply_ytd_does_not_touch_price_pnl(self):
        rows = [{"ticker": "0700.hk", "pnl": -49, "pnl_pct": -24}]
        report = build_dividend_report(
            [buy("0700.HK", 10, "2026-01-02")],
            {"0700.hk": [cash("2026-05-15", 5.3)]},
            today=TODAY,
        )
        apply_ytd(rows, report)
        self.assertEqual(rows[0]["pnl"], -49)
        self.assertEqual(rows[0]["pnl_pct"], -24)
        self.assertAlmostEqual(rows[0]["div_ytd"], 53)

    def test_ytd_tile_is_received_cash_not_the_forward_estimate(self):
        metric = ytd_metric(11509, "HKD")
        self.assertEqual(metric["label"], "今年股息 / Div YTD")
        self.assertEqual(metric["sub"], "已收 / received")
        self.assertNotIn("預期", metric["label"])
        self.assertNotIn("預期", metric["sub"])
        self.assertNotIn("expected", metric["sub"])
        self.assertEqual(metric["value"], "HKD 11,509")


class EmptyLedgerTests(unittest.TestCase):
    def test_no_dated_ledger_explains_why_ytd_is_zero(self):
        report = build_dividend_report([], {"0700.HK": [cash("2026-05-15", 5)]}, today=TODAY)
        self.assertEqual(report["total_ytd"], 0)
        self.assertTrue(report["ledger_empty"])
        self.assertIn("買賣紀錄", dividend_caption(report))


if __name__ == "__main__":
    unittest.main()
