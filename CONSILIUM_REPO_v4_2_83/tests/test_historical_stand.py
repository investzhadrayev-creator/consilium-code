"""
Regression tests for the issue #14 historical-reconstruction stand: price-on-date and
same-share-basis P/E in microservice/macro_prices.py.

Philosophy under test: adjClose is expressed in TODAY's share basis; EPS read from an old
filing is expressed in THAT FILING's basis. Mixing the two produces a P/E that is wrong by
exactly the split multiple -- a confident, plausible-looking number, not an obvious crash. Pin
#3 below ("the main pin") is the one the mandate calls the most important thing in the task.

All tests are OFFLINE: TIINGO_TOKEN is monkeypatched into the environment and _get_json is never
actually called except where a test constructs the record by hand.
"""
import os
import unittest
from unittest import mock

from _support import load_microservice_module

mp = load_microservice_module("macro_prices")


class TestPriceOnDate(unittest.TestCase):

    def test_returns_the_full_tiingo_record_unmodified(self):
        """Pt.2 of the mandate: nothing is dropped or hand-picked -- the exact field set Tiingo
        reports must survive, because pt.3 needs fields (splitFactor's siblings close/adjClose)
        that a narrower projection could easily have omitted."""
        raw_row = {"date": "2019-03-15T00:00:00.000Z", "close": 1000.0, "adjClose": 100.0,
                  "splitFactor": 1.0, "divCash": 0.0, "open": 995.0, "adjOpen": 99.5,
                  "high": 1010.0, "adjHigh": 101.0, "low": 990.0, "adjLow": 99.0,
                  "volume": 12345, "adjVolume": 123450}
        errors = {}
        with mock.patch.dict(os.environ, {"TIINGO_TOKEN": "t"}), \
             mock.patch.object(mp, "_get_json", return_value=[raw_row]) as g:
            r = mp.tiingo_price_on_date("NFLX", "2019-03-15", errors)
        self.assertEqual(r, raw_row)
        self.assertEqual(errors, {})
        url = g.call_args[0][0]
        self.assertIn("startDate=2019-03-15", url)
        self.assertIn("endDate=2019-03-15", url)

    def test_no_trading_day_is_a_refusal_not_a_guess(self):
        errors = {}
        with mock.patch.dict(os.environ, {"TIINGO_TOKEN": "t"}), \
             mock.patch.object(mp, "_get_json", return_value=[]):
            r = mp.tiingo_price_on_date("NFLX", "2019-03-16", errors)   # a Saturday
        self.assertIsNone(r)
        self.assertIn("tiingo_price_on_date_NFLX", errors)

    def test_missing_token_refuses_without_a_network_call(self):
        errors = {}
        with mock.patch.dict(os.environ, {}, clear=True):
            r = mp.tiingo_price_on_date("NFLX", "2019-03-15", errors)
        self.assertIsNone(r)
        self.assertIn("TIINGO_TOKEN", errors["tiingo_price_on_date_NFLX"])


class TestSameShareBasisPE(unittest.TestCase):
    """Issue #14 §5.3 (the MAIN pin) and §5.4. Issue #24 replaced the single-day close/adjClose
    ratio (which refused every composite split and every dividend payer) with the PRODUCT of
    `splitFactor` across daily rows since the requested date, cross-checked against the ratio."""

    def test_pe_matches_a_manual_calculation_across_a_confirmed_split(self):
        """The main pin. A 10:1 split, no dividend admixture: today's adjClose is 1/10 of that
        day's raw close, and the splitFactor product across the range agrees exactly.
        Manual calc: split_factor = product([...,10.0,...]) = 10;
                     eps_today_basis = eps_as_filed / 10 = 50/10 = 5;
                     pe = adjClose / eps_today_basis = 100/5 = 20."""
        price_record = {"close": 1000.0, "adjClose": 100.0, "splitFactor": 1.0}
        daily_rows = [{"splitFactor": 1.0}, {"splitFactor": 10.0}, {"splitFactor": 1.0}]
        pe = mp.pe_same_share_basis(price_record, eps_as_filed=50.0, errors={},
                                    daily_rows=daily_rows)
        self.assertAlmostEqual(pe, 20.0, places=6)

    def test_compound_split_with_dividend_admixture_gives_the_exact_product_and_a_correct_pe(self):
        """Issue #24's own example in miniature: NVDA 2020-03-23's close/adjClose ratio was
        40.2006 -- two real splits (4:1, 10:1) compounding to EXACTLY 40, plus ~0.5% of
        accumulated-dividend admixture that never lands on a 'clean' multiple. The splitFactor
        PRODUCT is the exact, dividend-free signal and must win over the contaminated ratio.
        Manual calc: factor = 4*10 = 40; eps_today_basis = 200/40 = 5; pe = 100/5 = 20."""
        price_record = {"close": 4020.06, "adjClose": 100.0}   # ratio = 40.2006
        daily_rows = [{"splitFactor": 1.0}, {"splitFactor": 4.0}, {"splitFactor": 1.0},
                     {"splitFactor": 10.0}, {"splitFactor": 1.0}]   # product = 40.0 exactly
        factor, reason = mp.split_factor_since(price_record, daily_rows)
        self.assertIsNone(reason)
        self.assertAlmostEqual(factor, 40.0, places=6,
                               msg="the PRODUCT must win -- 40.2006 (the raw ratio) is wrong")
        pe = mp.pe_same_share_basis(price_record, eps_as_filed=200.0, errors={},
                                    daily_rows=daily_rows)
        self.assertAlmostEqual(pe, 20.0, places=6)

    def test_product_and_ratio_diverging_beyond_tolerance_is_a_named_refusal(self):
        """A splitFactor product of 10 (one clean 10:1 split) against a close/adjClose ratio of
        12 is a 20% gap -- far beyond plausible dividend drag, so this is refused with BOTH
        numbers named, never a guess at which signal to trust."""
        price_record = {"close": 1200.0, "adjClose": 100.0}    # ratio = 12.0
        daily_rows = [{"splitFactor": 10.0}]                    # product = 10.0
        factor, reason = mp.split_factor_since(price_record, daily_rows)
        self.assertIsNone(factor)
        self.assertIn("split_factor_undeterminable", reason)
        self.assertIn("10", reason)
        self.assertIn("12", reason)

    def test_naive_mixed_basis_pe_is_wrong_by_exactly_the_split_factor(self):
        """Documents the exact defect the mandate describes: dividing TODAY's adjClose by the
        EPS AS FILED (yesterday's basis) understates P/E tenfold for a 10:1 split -- 'the system
        confidently announces a buy'."""
        price_record = {"close": 1000.0, "adjClose": 100.0}
        daily_rows = [{"splitFactor": 10.0}]
        naive_pe = price_record["adjClose"] / 50.0             # the bug: bases mixed
        correct_pe = mp.pe_same_share_basis(price_record, 50.0, {}, daily_rows=daily_rows)
        self.assertAlmostEqual(correct_pe / naive_pe, 10.0, places=6,
                               msg="a 10:1 split must understate the naive P/E by exactly 10x")

    def test_undeterminable_split_factor_refuses_never_defaults_to_one(self):
        """Pin (issue #14 §5.4, updated by #24): close/adjClose = 1000/137 disagrees wildly with
        a splitFactor product of 1 (no split on record) -- the mandate's rule ('отсутствие
        данных для приведения — отказ, а не подстановка коэффициента 1') requires a refusal
        here, not a best-effort number."""
        price_record = {"close": 1000.0, "adjClose": 137.0}
        daily_rows = [{"splitFactor": 1.0}]
        errors = {}
        pe = mp.pe_same_share_basis(price_record, 50.0, errors, symbol="XYZ",
                                    daily_rows=daily_rows)
        self.assertIsNone(pe)
        self.assertIn("pe_same_share_basis_XYZ", errors)
        self.assertIn("split_factor_undeterminable", errors["pe_same_share_basis_XYZ"])

    def test_missing_daily_rows_refuses_never_defaults_to_one(self):
        """No daily rows at all (a failed range fetch) must refuse -- never fall back to the
        ratio alone, and never to 1.0."""
        price_record = {"close": 1000.0, "adjClose": 100.0}
        pe = mp.pe_same_share_basis(price_record, 50.0, {}, symbol="ABC", daily_rows=[])
        self.assertIsNone(pe)

    def test_no_split_since_the_date_leaves_eps_unchanged(self):
        price_record = {"close": 100.0, "adjClose": 100.0}
        daily_rows = [{"splitFactor": 1.0}]
        pe = mp.pe_same_share_basis(price_record, 5.0, {}, daily_rows=daily_rows)
        self.assertAlmostEqual(pe, 20.0, places=6)

    def test_missing_eps_refuses(self):
        price_record = {"close": 100.0, "adjClose": 100.0}
        errors = {}
        pe = mp.pe_same_share_basis(price_record, None, errors, symbol="ABC")
        self.assertIsNone(pe)
        self.assertIn("pe_same_share_basis_ABC", errors)

    def test_split_factor_since_computes_the_product_across_daily_rows(self):
        for factor in (2.0, 3.0, 4.0, 5.0, 10.0, 12.0, 40.0):
            price_record = {"close": 100.0 * factor, "adjClose": 100.0}
            daily_rows = [{"splitFactor": 1.0}, {"splitFactor": factor}, {"splitFactor": 1.0}]
            got, reason = mp.split_factor_since(price_record, daily_rows)
            self.assertEqual(got, factor, "factor %s: %s" % (factor, reason))
            self.assertIsNone(reason)

    def test_msft_dividend_drift_with_no_split_does_not_refuse(self):
        """Issue #26, THE pin. MSFT 2018-12-24: no split since (splitFactor product = 1.0), but
        the LIVE close/adjClose ratio was 1.0737 -- seven years of dividends alone, which blew
        through the old fixed 5% tolerance and refused 7 of 29 live historical checks (MSFT x3,
        ORCL x4). Real Tiingo rows for a 7-year window are ~1,800 individual days; this collapses
        them to their net effect for a compact, exact-arithmetic pin (same 'own example in
        miniature' shape as the NVDA compound-split pin above), using the REAL ratio reported
        live for MSFT (1.0737, issue #26's own numbers) and a single dividend row engineered to
        reproduce it exactly: close 107.37, divCash 7.37 -> contribution = 107.37/100 = 1.0737.
        Manual calc: product = 1.0 (no split); dividend contribution = 1.0737; expected =
        1.0 * 1.0737 = 1.0737 = the observed ratio exactly -- no refusal, and the returned
        factor is the SPLIT product (1.0), not the dividend-inflated ratio."""
        price_record = {"close": 107.37, "adjClose": 100.0}   # ratio = 1.0737
        daily_rows = [{"splitFactor": 1.0, "divCash": 0.0},
                     {"splitFactor": 1.0, "divCash": 7.37, "close": 107.37},
                     {"splitFactor": 1.0, "divCash": 0.0}]
        factor, reason = mp.split_factor_since(price_record, daily_rows)
        self.assertIsNone(reason)
        self.assertAlmostEqual(factor, 1.0, places=6)

    def test_nvda_v3_case_stays_green_at_exactly_40(self):
        """Issue #26's own regression guard: the issue #24 NVDA pin (two real splits, 4:1 and
        10:1, compounding to exactly 40, plus ~0.5% of dividend admixture the old code tolerated
        blindly) must still pass green under the new divCash-driven check. These daily_rows carry
        no divCash field at all (Tiingo reports none for the split days themselves), so the
        expected dividend contribution is 1.0 and the entire 0.5015% gap between the ratio
        (40.2006) and the product (40.0) falls inside the new, far smaller residual tolerance."""
        price_record = {"close": 4020.06, "adjClose": 100.0}   # ratio = 40.2006
        daily_rows = [{"splitFactor": 1.0}, {"splitFactor": 4.0}, {"splitFactor": 1.0},
                     {"splitFactor": 10.0}, {"splitFactor": 1.0}]   # product = 40.0 exactly
        factor, reason = mp.split_factor_since(price_record, daily_rows)
        self.assertIsNone(reason)
        self.assertEqual(factor, 40.0)

    def test_real_discrepancy_beyond_the_dividend_contribution_is_still_a_refusal_with_three_numbers(self):
        """A genuine data problem (a missed split, a bad row) must still refuse even after the
        measured dividend contribution explains part of the drift -- 'a real discrepancy' per the
        mandate. Same dividend admixture as the MSFT pin above (contribution = 1.0737), but the
        observed ratio is 1.3 -- 21% beyond what the dividends explain, far past the 1% residual.
        The refusal must name all three numbers: the splitFactor product, the expected dividend
        contribution, and the raw ratio -- never a guess at which to trust."""
        price_record = {"close": 130.0, "adjClose": 100.0}   # ratio = 1.3
        daily_rows = [{"splitFactor": 1.0, "divCash": 0.0},
                     {"splitFactor": 1.0, "divCash": 7.37, "close": 107.37},
                     {"splitFactor": 1.0, "divCash": 0.0}]
        factor, reason = mp.split_factor_since(price_record, daily_rows)
        self.assertIsNone(factor)
        self.assertIn("split_factor_undeterminable", reason)
        self.assertIn("1.0000", reason)    # splitFactor product
        self.assertIn("1.0737", reason)    # expected dividend contribution
        self.assertIn("1.3000", reason)    # raw close/adjClose ratio

    def test_dividend_row_whose_close_cannot_support_its_own_divCash_is_undeterminable(self):
        """A row claiming divCash >= its own close is bad data, not a payer to skip silently --
        the mandate's refusal rule applies to the dividend signal too, not only the split one."""
        price_record = {"close": 107.0, "adjClose": 100.0}
        daily_rows = [{"splitFactor": 1.0, "divCash": 50.0, "close": 40.0}]
        factor, reason = mp.split_factor_since(price_record, daily_rows)
        self.assertIsNone(factor)
        self.assertIn("split_factor_undeterminable", reason)


class TestTiingoDailyRowsSince(unittest.TestCase):
    """Issue #24: the range fetch that feeds split_factor_since's product signal."""

    def test_returns_the_raw_rows_from_the_same_endpoint_startdate_only(self):
        rows = [{"date": "2020-03-23", "close": 100.0, "adjClose": 100.0, "splitFactor": 1.0},
               {"date": "2026-08-07", "close": 200.0, "adjClose": 200.0, "splitFactor": 1.0}]
        errors = {}
        with mock.patch.dict(os.environ, {"TIINGO_TOKEN": "t"}), \
             mock.patch.object(mp, "_get_json", return_value=rows) as g:
            r = mp.tiingo_daily_rows_since("NVDA", "2020-03-23", errors)
        self.assertEqual(r, rows)
        self.assertEqual(errors, {})
        url = g.call_args[0][0]
        self.assertIn("startDate=2020-03-23", url)
        self.assertNotIn("endDate=", url)

    def test_missing_token_refuses_without_a_network_call(self):
        errors = {}
        with mock.patch.dict(os.environ, {}, clear=True):
            r = mp.tiingo_daily_rows_since("NVDA", "2020-03-23", errors)
        self.assertEqual(r, [])
        self.assertIn("TIINGO_TOKEN", errors["tiingo_daily_rows_NVDA"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
