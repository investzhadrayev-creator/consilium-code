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
    """Issue #14 §5.3 (the MAIN pin) and §5.4."""

    def test_pe_matches_a_manual_calculation_across_a_confirmed_split(self):
        """The main pin. A 10:1 split: today's adjClose is 1/10 of that day's raw close.
        Manual calc: split_factor = close/adjClose = 1000/100 = 10;
                     eps_today_basis = eps_as_filed / 10 = 50/10 = 5;
                     pe = adjClose / eps_today_basis = 100/5 = 20."""
        price_record = {"close": 1000.0, "adjClose": 100.0, "splitFactor": 1.0}
        pe = mp.pe_same_share_basis(price_record, eps_as_filed=50.0, errors={})
        self.assertAlmostEqual(pe, 20.0, places=6)

    def test_naive_mixed_basis_pe_is_wrong_by_exactly_the_split_factor(self):
        """Documents the exact defect the mandate describes: dividing TODAY's adjClose by the
        EPS AS FILED (yesterday's basis) understates P/E tenfold for a 10:1 split -- 'the system
        confidently announces a buy'."""
        price_record = {"close": 1000.0, "adjClose": 100.0}
        naive_pe = price_record["adjClose"] / 50.0             # the bug: bases mixed
        correct_pe = mp.pe_same_share_basis(price_record, 50.0, {})
        self.assertAlmostEqual(correct_pe / naive_pe, 10.0, places=6,
                               msg="a 10:1 split must understate the naive P/E by exactly 10x")

    def test_undeterminable_split_factor_refuses_never_defaults_to_one(self):
        """Pin (issue #14 §5.4): close/adjClose = 1000/137 matches no clean split multiple and
        is not ~1 -- the mandate's rule ('отсутствие данных для приведения — отказ, а не
        подстановка коэффициента 1') requires a refusal here, not a best-effort number."""
        price_record = {"close": 1000.0, "adjClose": 137.0}
        errors = {}
        pe = mp.pe_same_share_basis(price_record, 50.0, errors, symbol="XYZ")
        self.assertIsNone(pe)
        self.assertIn("pe_same_share_basis_XYZ", errors)
        self.assertIn("split_factor_undeterminable", errors["pe_same_share_basis_XYZ"])

    def test_no_split_since_the_date_leaves_eps_unchanged(self):
        price_record = {"close": 100.0, "adjClose": 100.0}
        pe = mp.pe_same_share_basis(price_record, 5.0, {})
        self.assertAlmostEqual(pe, 20.0, places=6)

    def test_missing_eps_refuses(self):
        price_record = {"close": 100.0, "adjClose": 100.0}
        errors = {}
        pe = mp.pe_same_share_basis(price_record, None, errors, symbol="ABC")
        self.assertIsNone(pe)
        self.assertIn("pe_same_share_basis_ABC", errors)

    def test_split_factor_since_recognises_every_clean_multiple(self):
        for factor in mp._CLEAN_SPLIT_FACTORS:
            price_record = {"close": 100.0 * factor, "adjClose": 100.0}
            got, reason = mp.split_factor_since(price_record)
            self.assertEqual(got, float(factor), "factor %s: %s" % (factor, reason))
            self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
