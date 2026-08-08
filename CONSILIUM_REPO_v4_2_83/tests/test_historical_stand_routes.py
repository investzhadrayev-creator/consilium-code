"""
Regression tests for issue #20: the historical-reconstruction stand's HTTP surface.

PR #18 built as_of / roe_median_5y / pe_same_share_basis but wired NONE of it to an HTTP
route -- the #18 audit found every one of these functions reachable only from unit tests, not
from a single external caller. This file pins the two doors issue #20 asks to cut:
  1. /edgar_facts accepting an optional "as_of" body field and actually filtering on it.
  2. a new /price_on_date route publishing tiingo_price_on_date + pe_same_share_basis.

Offline: TIINGO_TOKEN is monkeypatched into the environment and macro_prices._get_json is
mocked (same pattern as test_historical_stand.py); edgar_facts facts are injected into the
module cache (same pattern as test_edgar_facts.py). No network, no SEC/Tiingo calls.
"""
import os
import time
import unittest
from unittest import mock

from _support import load_microservice_module

app_mod = load_microservice_module("app")
ef = load_microservice_module("edgar_facts")
mp = load_microservice_module("macro_prices")


def _row(start, end, val, form="10-K", accn="a1", filed="2025-02-01"):
    r = {"end": end, "val": val, "form": form, "accn": accn, "filed": filed}
    if start:
        r["start"] = start
    return r


class TestEdgarFactsRouteAsOf(unittest.TestCase):
    """Issue #20 pt.1: /edgar_facts must read the optional as_of field and pass it through --
    the #18 audit found the parameter existed only for unit tests; n8n could never request a
    historical reconstruction."""

    def setUp(self):
        self.client = app_mod.app.test_client()
        ef._FACTS_CACHE.clear()
        ef._CONCEPT_CACHE.clear()
        for tax, tag in ef.SHARES_CURRENT:
            ef._CONCEPT_CACHE[("RTEST", tax, tag)] = (time.time(), None)

    def _mock_facts(self):
        return {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            _row("2023-01-01", "2023-12-31", 100, accn="a", filed="2024-02-01"),
            _row("2024-01-01", "2024-12-31", 150, accn="b", filed="2025-02-01"),
        ]}}}}}

    def test_as_of_in_the_request_body_reaches_edgar_facts_and_filters_the_result(self):
        ef._FACTS_CACHE["RTEST"] = (time.time(), self._mock_facts())
        resp = self.client.post("/edgar_facts", json={"cik": "RTEST", "as_of": "2024-06-01"})
        body = resp.get_json()
        ends = [p["end"] for p in body["revenue"]]
        self.assertEqual(ends, ["2023-12-31"],
                         "as_of in the POST body never reached edgar_facts() -- the door issue "
                         "#20 asked to cut stayed shut")
        self.assertEqual(body.get("_as_of"), "2024-06-01")

    def test_omitting_as_of_leaves_the_route_byte_identical_to_before(self):
        ef._FACTS_CACHE["RTEST"] = (time.time(), self._mock_facts())
        resp = self.client.post("/edgar_facts", json={"cik": "RTEST"})
        body = resp.get_json()
        ends = [p["end"] for p in body["revenue"]]
        self.assertEqual(ends, ["2023-12-31", "2024-12-31"])
        self.assertNotIn("_as_of", body)


class TestPriceOnDateRoute(unittest.TestCase):
    """Issue #20 pt.2: publish tiingo_price_on_date + pe_same_share_basis to an HTTP caller.
    macro_prices.py's own docstring calls pe_same_share_basis 'the most important part of the
    task' (issue #14); before this route it had no caller outside tests/test_historical_stand.py."""

    def setUp(self):
        self.client = app_mod.app.test_client()

    def test_route_returns_price_split_factor_and_same_basis_pe_for_a_confirmed_split(self):
        """Mirrors test_historical_stand.TestSameShareBasisPE's main pin, at the HTTP layer:
        10:1 split, close=1000/adjClose=100 -> factor 10, eps_today_basis=5, pe=20."""
        raw_row = {"close": 1000.0, "adjClose": 100.0, "splitFactor": 1.0}
        with mock.patch.dict(os.environ, {"TIINGO_TOKEN": "t"}), \
             mock.patch.object(mp, "_get_json", return_value=[raw_row]):
            resp = self.client.post("/price_on_date",
                                    json={"ticker": "NFLX", "date": "2019-03-15", "eps": 50.0})
        body = resp.get_json()
        self.assertEqual(body["price_record"], raw_row)
        self.assertAlmostEqual(body["split_factor"], 10.0, places=6)
        self.assertAlmostEqual(body["pe_same_share_basis"], 20.0, places=6)
        self.assertEqual(body["_errors"], {})

    def test_route_without_eps_still_returns_price_but_refuses_pe_by_name(self):
        raw_row = {"close": 100.0, "adjClose": 100.0}
        with mock.patch.dict(os.environ, {"TIINGO_TOKEN": "t"}), \
             mock.patch.object(mp, "_get_json", return_value=[raw_row]):
            resp = self.client.post("/price_on_date", json={"ticker": "ADBE", "date": "2024-01-02"})
        body = resp.get_json()
        self.assertEqual(body["price_record"], raw_row)
        self.assertIsNone(body["pe_same_share_basis"])
        self.assertIn("pe_same_share_basis_ADBE", body["_errors"])

    def test_route_refuses_by_name_when_ticker_or_date_missing(self):
        resp = self.client.post("/price_on_date", json={"ticker": "ADBE"})
        body = resp.get_json()
        self.assertIsNone(body.get("price_record"))
        self.assertIn("request", body.get("_errors", {}))

    def test_route_never_defaults_an_undeterminable_split_factor_to_one(self):
        raw_row = {"close": 1000.0, "adjClose": 137.0}   # matches no clean multiple, not ~1
        with mock.patch.dict(os.environ, {"TIINGO_TOKEN": "t"}), \
             mock.patch.object(mp, "_get_json", return_value=[raw_row]):
            resp = self.client.post("/price_on_date",
                                    json={"ticker": "XYZ", "date": "2019-03-15", "eps": 50.0})
        body = resp.get_json()
        self.assertIsNone(body["split_factor"])
        self.assertIsNone(body["pe_same_share_basis"])
        self.assertIn("split_factor_undeterminable", body["_errors"].get("split_factor_XYZ", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
