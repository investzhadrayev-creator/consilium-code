"""
Regression tests for microservice/macro_prices.py's historical-validation-stand additions
(issue #14 pt.2/3): price_on_date and normalize_pe.

Philosophy under test (PREREG mailbox/PREREG_2026-08-06_HISTORICAL_VALIDATION.md §7, "the main
technical trap"): Tiingo's adjClose is expressed in TODAY's share-count basis; an EPS pulled from
a filing made on the as-of date is expressed in THAT DATE's basis. Multiplying them unreconciled
gives a P/E wrong by exactly the split multiple -- a confidently wrong "BUY" is the failure mode,
not a crash. normalize_pe's whole job is closing that gap, and its own docstring names which
basis it chose and why.

All tests are OFFLINE: price_on_date's network call is monkeypatched; normalize_pe is a pure
function tested directly against fixture rows. No SEC/Tiingo request is ever made.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "microservice"))
import macro_prices as mp  # noqa: E402


class TestPriceOnDate(unittest.TestCase):

    def setUp(self):
        self._old_token = os.environ.get("TIINGO_TOKEN")
        os.environ["TIINGO_TOKEN"] = "test-token"

    def tearDown(self):
        if self._old_token is None:
            os.environ.pop("TIINGO_TOKEN", None)
        else:
            os.environ["TIINGO_TOKEN"] = self._old_token

    def test_returns_the_full_raw_row_nothing_dropped(self):
        """Issue #14 pt.2: 'nothing discarded' -- the caller decides what it needs, this layer
        does not pre-guess it. In particular splitFactor and divCash must survive untouched."""
        raw = {"date": "2020-08-28T00:00:00.000Z", "close": 499.23, "adjClose": 124.8075,
              "high": 505.0, "low": 495.0, "open": 500.0, "volume": 100000,
              "splitFactor": 1.0, "divCash": 0.0}
        errors = {}
        with mock.patch.object(mp, "_get_json", return_value=[raw]) as m:
            r = mp.price_on_date("AAPL", "2020-08-28", errors)
        self.assertEqual(r, raw, "every field Tiingo returned must survive unfiltered")
        self.assertEqual(errors, {})
        called_url = m.call_args[0][0]
        self.assertIn("startDate=2020-08-28", called_url)
        self.assertIn("endDate=2020-08-28", called_url)

    def test_no_data_for_the_date_is_a_refusal_not_a_crash(self):
        errors = {}
        with mock.patch.object(mp, "_get_json", return_value=[]):
            r = mp.price_on_date("AAPL", "1776-07-04", errors)
        self.assertIsNone(r)
        self.assertIn("tiingo_price_on_date_AAPL", errors)

    def test_missing_token_is_a_refusal(self):
        os.environ.pop("TIINGO_TOKEN", None)
        errors = {}
        r = mp.price_on_date("AAPL", "2020-08-28", errors)
        self.assertIsNone(r)
        self.assertIn("tiingo_price_on_date", errors)

    def test_network_error_is_caught_not_raised(self):
        errors = {}
        with mock.patch.object(mp, "_get_json", side_effect=RuntimeError("timeout")):
            r = mp.price_on_date("AAPL", "2020-08-28", errors)
        self.assertIsNone(r)
        self.assertIn("tiingo_price_on_date_AAPL", errors)


class TestNormalizePe(unittest.TestCase):
    """The main pin (issue #14 pt.5, PREREG §4 criterion 4): a ticker with a split AFTER the
    as-of date must reproduce the manually-computed P/E within tolerance."""

    def test_matches_manual_calc_for_a_ticker_split_after_the_as_of_date(self):
        # AAPL-shaped: as-of date traded at $499.23 (pre-split basis); EPS filed for that period
        # was $2.20 (also pre-split basis) -- so the MANUAL, basis-consistent P/E is simply
        # close/eps_asof, no split arithmetic needed at all. A later 4:1 split (2020-08-31) means
        # today's adjClose for that same day is retroactively restated to ~$124.8075.
        close, adj_close, eps_asof = 499.23, 124.8075, 2.20
        row = {"close": close, "adjClose": adj_close}
        errors = {}
        out = mp.normalize_pe(row, eps_asof, errors)
        self.assertIsNotNone(out, errors)
        manual_pe = close / eps_asof
        self.assertAlmostEqual(out["pe"], manual_pe, delta=abs(manual_pe) * 0.01,
                               msg="normalized P/E must match the manually-computed P/E "
                                   "within 1%% (PREREG §4 criterion 4)")
        self.assertAlmostEqual(out["split_factor_since_as_of"], 4.0, places=4)
        self.assertEqual(errors, {})

    def test_no_split_since_as_of_is_the_identity_case(self):
        row = {"close": 100.0, "adjClose": 100.0}
        out = mp.normalize_pe(row, 5.0, {})
        self.assertAlmostEqual(out["pe"], 20.0, places=6)
        self.assertAlmostEqual(out["split_factor_since_as_of"], 1.0, places=6)

    def test_refuses_when_split_factor_is_not_determinable(self):
        """Issue #14 pt.5: absence of a usable close/adjClose must REFUSE, never silently default
        the factor to 1 -- a plausible-looking wrong P/E is worse than an honest null."""
        errors = {}
        out = mp.normalize_pe({"close": None, "adjClose": 124.8}, 2.20, errors)
        self.assertIsNone(out)
        self.assertIn("normalize_pe", errors)

    def test_refuses_on_zero_close(self):
        errors = {}
        out = mp.normalize_pe({"close": 0, "adjClose": 124.8}, 2.20, errors)
        self.assertIsNone(out)
        self.assertIn("normalize_pe", errors)

    def test_refuses_when_eps_missing(self):
        errors = {}
        out = mp.normalize_pe({"close": 100.0, "adjClose": 100.0}, None, errors)
        self.assertIsNone(out)
        self.assertIn("normalize_pe", errors)

    def test_refuses_on_missing_price_row(self):
        errors = {}
        out = mp.normalize_pe(None, 2.20, errors)
        self.assertIsNone(out)
        self.assertIn("normalize_pe", errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
