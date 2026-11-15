"""Display rules for the portfolio dashboard. No network and no database."""

import unittest

from portfolio_ui import _contributor_card
from portfolio_display import (
    COMPACT_COLUMNS,
    balance_snapshot,
    build_compact_frame,
    compact_styler,
    concentration_notice,
    contributor_lists,
    format_money,
    resolve_security,
)


OBSERVED = [
    ("3416.HK", 50000, 9.94, 382249.999),
    ("0700.HK", 400, 510, 154640.0024),
    ("1299.HK", 800, 75.4, 62200),
    ("3191.HK", 1250, 103.7332, 81575.0027),
    ("0016.HK", 500, 114.8, 55450.0008),
    ("2318.HK", 1000, 55.8, 51599.9985),
    ("3486.HK", 2000, 24.64, 28020.0025),
    ("3455.HK", 5, 5609, 26970),
    ("0941.HK", 500, 77, 40200.0008),
]


def observed_rows():
    rows = []
    for ticker, qty, cost, value in OBSERVED:
        profile = resolve_security(ticker)
        cost_total = qty * cost
        pnl = value - cost_total
        rows.append(
            {
                "ticker": ticker,
                "name": profile["name"],
                "market": "HK",
                "industry_code": profile["industry_code"],
                "industry_label": profile["industry_label"],
                "cost_total": cost_total,
                "market_value": value,
                "pnl": pnl,
                "pnl_pct": (pnl / cost_total * 100) if cost_total else 0,
            }
        )
    return rows


class NamingTests(unittest.TestCase):
    def test_known_bad_labels_are_corrected(self):
        ping_an = resolve_security("2318.HK")
        self.assertEqual(ping_an["name"], "中國平安")
        self.assertNotIn("人壽", ping_an["name"])
        self.assertEqual(ping_an["industry_code"], "INSR")
        self.assertEqual(resolve_security("2628.HK")["name"], "中國人壽")
        self.assertEqual(resolve_security("0880.HK")["name"], "澳博控股")

    def test_padding_variants_share_name_and_industry(self):
        for ticker in ("0016.HK", "00016.HK", "16.HK"):
            profile = resolve_security(ticker)
            self.assertEqual(profile["name"], "新鴻基地產")
            self.assertEqual(profile["industry_code"], "PROP")
        self.assertEqual(resolve_security("941.HK")["name"], "中國移動")
        self.assertEqual(resolve_security("00941.HK")["industry_code"], "TLCO")

    def test_observed_book_has_names_and_no_blank_industry(self):
        rows = observed_rows()
        names = {row["ticker"]: row["name"] for row in rows}
        self.assertEqual(names["3416.HK"], "國指備兌ETF")
        self.assertEqual(names["3191.HK"], "中國半導體ETF")
        self.assertEqual(names["3486.HK"], "亞洲半導體ETF")
        self.assertEqual(names["3455.HK"], "景順QQQ")
        for ticker, name in names.items():
            self.assertNotEqual(name, ticker)
        labels = {row["industry_label"] for row in rows}
        self.assertNotIn("-", labels)
        self.assertIn("指數ETF", labels)
        self.assertIn("科技 TECH", labels)
        self.assertIn("保險 INSR", labels)
        self.assertEqual(resolve_security("3416.HK")["industry_code"], "ETF")
        self.assertEqual(resolve_security("3191.HK")["industry_code"], "TECH")
        self.assertEqual(resolve_security("3486.HK")["industry_code"], "TECH")

    def test_local_override_beats_yahoo(self):
        def boom(_ticker):
            raise AssertionError("Yahoo should not be called when the local map is complete")

        profile = resolve_security("0700.HK", yahoo=boom)
        self.assertEqual(profile["name"], "騰訊控股")
        self.assertEqual(profile["industry_code"], "TECH")

    def test_yahoo_sector_and_etf_fallbacks(self):
        def yahoo(ticker):
            if ticker == "ZZZZ":
                return {
                    "short_name": "EX",
                    "long_name": "Example Corporation",
                    "sector": "Technology",
                    "industry": "Software",
                    "quote_type": "EQUITY",
                }
            if ticker == "LIFE":
                return {
                    "short_name": "ELI",
                    "long_name": "Example Life",
                    "sector": "Financial Services",
                    "industry": "Insurance - Life",
                    "quote_type": "EQUITY",
                }
            return {
                "short_name": "SAE",
                "long_name": "Some Active ETF",
                "sector": "",
                "industry": "",
                "quote_type": "ETF",
            }

        tech = resolve_security("ZZZZ", yahoo=yahoo)
        self.assertEqual(tech["name"], "Example Corporation")
        self.assertEqual(tech["industry_code"], "TECH")
        insured = resolve_security("LIFE", yahoo=yahoo)
        self.assertEqual(insured["industry_code"], "INSR")
        etf = resolve_security("9999.HK", yahoo=yahoo)
        self.assertEqual(etf["industry_label"], "指數ETF")
        self.assertNotEqual(etf["industry_label"], "-")

    def test_missing_profile_is_unclassified_not_dash(self):
        profile = resolve_security("NOPE")
        self.assertEqual(profile["name"], "NOPE")
        self.assertEqual(profile["industry_label"], "未分類")


class FormatAndSortTests(unittest.TestCase):
    def test_money_shows_full_figures_and_currency(self):
        self.assertEqual(format_money(1120011, "HKD"), "HKD 1,120,011")
        self.assertEqual(format_money(-237106, "HKD", signed=True), "HKD -237,106")
        self.assertEqual(format_money(1880, "HKD", signed=True), "HKD +1,880")
        self.assertEqual(format_money(1234.5, "USD"), "USD 1,234.50")
        for text in (
            format_money(1120011, "HKD"),
            format_money(-237106, "HKD", signed=True),
        ):
            self.assertNotIn("…", text)
            self.assertNotIn("...", text)

    def test_observed_total_cost_is_not_truncated(self):
        rows = observed_rows()
        total_cost = sum(row["cost_total"] for row in rows)
        text = format_money(total_cost, "HKD")
        self.assertTrue(text.startswith("HKD 1,120,"), text)
        digits = text.replace("HKD ", "").replace(",", "")
        self.assertTrue(digits.isdigit())
        self.assertGreaterEqual(len(digits), 7)

    def test_default_sort_is_worst_dollar_pnl(self):
        rows = observed_rows()
        total = sum(row["market_value"] for row in rows)
        frame = build_compact_frame(rows, total)
        self.assertEqual(list(frame.columns), COMPACT_COLUMNS)
        self.assertNotIn("RSI", frame.columns)
        self.assertNotIn("信號", "".join(frame.columns))
        self.assertEqual(frame.iloc[0]["代號"], "3416.HK")
        self.assertLess(frame.iloc[0]["盈虧$"], frame.iloc[1]["盈虧$"])
        self.assertEqual(frame.iloc[0]["成本"], 50000 * 9.94)
        self.assertGreater(frame.iloc[0]["權重%"], 40)
        self.assertLess(frame.iloc[0]["權重%"], 50)

    def test_sort_by_percent_and_weight(self):
        rows = observed_rows()
        total = sum(row["market_value"] for row in rows)
        by_pct = build_compact_frame(rows, total, "pnl_pct")
        self.assertEqual(by_pct.iloc[0]["代號"], "3486.HK")
        self.assertEqual(by_pct.iloc[1]["代號"], "3191.HK")
        self.assertLess(by_pct.iloc[0]["盈虧%"], -40)
        by_weight = build_compact_frame(rows, total, "weight")
        self.assertEqual(by_weight.iloc[0]["代號"], "3416.HK")
        self.assertGreater(by_weight.iloc[0]["權重%"], by_weight.iloc[1]["權重%"])

    def test_styler_colors_gains_and_losses(self):
        rows = observed_rows()
        total = sum(row["market_value"] for row in rows)
        html = compact_styler(build_compact_frame(rows, total), "HKD").to_html()
        self.assertIn("-114,750", html)
        self.assertIn("+1,880", html)
        self.assertIn("c5221f", html)
        self.assertIn("137333", html)
        self.assertNotIn("RSI", html)
        self.assertNotIn("信號", html)


class BalanceTests(unittest.TestCase):
    def test_observed_book_is_concentrated_and_all_hk(self):
        rows = observed_rows()
        total = sum(row["market_value"] for row in rows)
        snap = balance_snapshot(rows, total)
        self.assertTrue(snap["concentrated"])
        self.assertEqual(snap["top1"]["ticker"], "3416.HK")
        self.assertGreater(snap["top1"]["weight"], 40)
        self.assertGreater(snap["top5_weight"], snap["top1"]["weight"])
        self.assertLessEqual(snap["top5_weight"], 100)
        self.assertAlmostEqual(snap["us_weight"], 0)
        self.assertAlmostEqual(snap["hk_weight"], 100)
        self.assertTrue(all(item["label"] != "-" for item in snap["industries"]))
        notice = concentration_notice(snap["warnings"][0], snap["warn_pct"])
        self.assertIn("15", notice["zh"])
        self.assertIn("並非買賣建議", notice["zh"])
        self.assertNotIn("買入", notice["zh"])
        self.assertNotIn("賣出", notice["zh"])
        self.assertNotIn("強買", notice["en"])
        self.assertNotIn("強賣", notice["en"])

    def test_warning_starts_above_fifteen_percent(self):
        def row(ticker, value):
            return {
                "ticker": ticker,
                "name": ticker,
                "market": "HK",
                "industry_label": "科技 TECH",
                "market_value": value,
                "pnl": -1,
                "pnl_pct": -1,
                "cost_total": value + 1,
            }

        under = balance_snapshot([row(f"N{i}", 1000) for i in range(10)], 10000)
        exact = balance_snapshot(
            [row("A", 1500)] + [row(f"N{i}", 850) for i in range(10)],
            10000,
        )
        over = balance_snapshot(
            [row("A", 1600)] + [row(f"N{i}", 840) for i in range(10)],
            10000,
        )
        self.assertFalse(under["concentrated"])
        self.assertFalse(exact["concentrated"])
        self.assertTrue(over["concentrated"])
        self.assertEqual(over["warnings"][0]["ticker"], "A")

    def test_contributors_are_dollar_ranked_not_signals(self):
        rows = observed_rows()
        winners, losers = contributor_lists(rows)
        self.assertEqual([row["ticker"] for row in losers], ["3416.HK", "0700.HK", "3191.HK"])
        self.assertEqual([row["ticker"] for row in winners], ["1299.HK", "0941.HK"])
        html = _contributor_card(
            "最大輸家 / Largest losses",
            [losers[0]],
            "HKD",
            "沒有未實現虧損 / No unrealized losses",
        )
        self.assertIn("HKD -114,750", html)
        self.assertIn("-23.1%", html)
        self.assertNotIn("-114,750.0%", html)
        self.assertNotIn("買入", html)
        self.assertNotIn("賣出", html)

    def test_market_split_counts_us_rows(self):
        rows = [
            {
                "ticker": "0700.HK",
                "name": "騰訊控股",
                "market": "HK",
                "industry_label": "科技 TECH",
                "market_value": 75,
                "pnl": 1,
                "pnl_pct": 1,
                "cost_total": 74,
            },
            {
                "ticker": "AAPL",
                "name": "蘋果",
                "market": "US",
                "industry_label": "科技 TECH",
                "market_value": 25,
                "pnl": -2,
                "pnl_pct": -2,
                "cost_total": 27,
            },
        ]
        snap = balance_snapshot(rows, 100)
        self.assertAlmostEqual(snap["hk_weight"], 75)
        self.assertAlmostEqual(snap["us_weight"], 25)
        self.assertEqual(resolve_security("AAPL")["name"], "蘋果")


if __name__ == "__main__":
    unittest.main()
