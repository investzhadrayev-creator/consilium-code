"""
BACKLOG #5: /reprice — a stored dossier verdict rescaled to a fresh price, gated by freshness.

Contract under test:
- REPRICE is a pure RESCALING: IV/FV10/ladder thresholds are price-independent; implied CAGR
  obeys icagr_new = (1+icagr_old)*(price_old/price_new)^(1/Y)-1. Repricing to the OLD price
  must reproduce the stored figures (identity), and repricing to a NEW price must MATCH a
  fresh ivc() run at that price (dy=0 case, where the identity is exact).
- Freshness gates never weaken: stale age -> refuse; newer 10-K/10-Q/8-K -> refuse with
  form/date/accession; EDGAR unreachable -> refuse (unknown is not fresh); no price -> refuse.
- The route itself is driven (consumer test rule, CLAUDE.md), never 500s, and refusals are
  first-class 200 answers.
"""
import json
import unittest
from unittest import mock

from _support import load_microservice_module

app_mod = load_microservice_module("app")
ivc_mod = load_microservice_module("ivc_lib")
edgar_mod = load_microservice_module("edgar_facts")


def _ivc_at(price, dy=0.0, dg=0.0):
    return ivc_mod.ivc({"price": price, "eps_normalized": 20.0, "growth_rate": 0.14,
                        "future_pe": 22, "hurdle": 0.12, "discount_rate": 0.12,
                        "dividend_yield": dy, "dividend_growth": dg,
                        "fade": True, "terminal_growth": 0.04, "years": 10})


def _stored_result(price=1100.0):
    base = _ivc_at(price)
    return {"ivc_base": base, "mos_ladder": base["mos_ladder"],
            "pwfv": 987.65, "verdict_cap": "AVOID",
            "scenarios": {"base": {"weight": 0.45, "overrides": {}, "result": _ivc_at(price)}}}


class TestRepriceMath(unittest.TestCase):

    def test_identity_at_old_price_reproduces_stored_figures(self):
        stored = _stored_result(1100.0)
        out = app_mod.reprice_result(stored, 1100.0, ticker="NFLX", spec_date="2026-07-18")
        self.assertTrue(out["repriced"])
        self.assertTrue(out["self_tests"]["identity_at_old_price_ok"])
        self.assertAlmostEqual(out["ivc_base"]["implied_cagr_pct"],
                               stored["ivc_base"]["implied_cagr_pct"], places=2)
        self.assertAlmostEqual(out["ivc_base"]["mos_pct"],
                               stored["ivc_base"]["mos_pct"], places=1)

    def test_rescale_matches_a_fresh_ivc_run_at_the_new_price(self):
        # dy=0: the identity is exact — the reprice must land on ivc()'s own number.
        stored = _stored_result(1100.0)
        out = app_mod.reprice_result(stored, 850.0, ticker="NFLX", spec_date="2026-07-18")
        fresh = _ivc_at(850.0)
        self.assertAlmostEqual(out["ivc_base"]["implied_cagr_pct"],
                               fresh["implied_cagr_pct"], delta=0.02)
        self.assertAlmostEqual(out["ivc_base"]["mos_pct"], fresh["mos_pct"], delta=0.05)
        for got, want in zip(out["ivc_base"]["mos_ladder"], fresh["mos_ladder"]):
            self.assertEqual(got["buy_threshold_price"], want["buy_threshold_price"],
                             "ladder thresholds are price-independent — must NOT move")
            self.assertEqual(got["reached"], want["reached"])

    def test_price_independent_figures_do_not_move(self):
        stored = _stored_result(1100.0)
        out = app_mod.reprice_result(stored, 700.0, ticker="NFLX", spec_date="2026-07-18")
        self.assertEqual(out["ivc_base"]["intrinsic_value"],
                         stored["ivc_base"]["intrinsic_value"])
        self.assertEqual(out["ivc_base"]["fv10_per_share"],
                         stored["ivc_base"]["fv10_per_share"])
        self.assertEqual(out["pwfv"], stored["pwfv"])

    def test_verdict_cap_rebanded_and_change_flagged(self):
        stored = _stored_result(1100.0)
        # deep enough cut that implied CAGR clears 16% -> BUY (at 250: ~17.4%)
        out = app_mod.reprice_result(stored, 250.0, ticker="NFLX", spec_date="2026-07-18")
        self.assertEqual(out["verdict_cap"], "BUY")
        self.assertEqual(out["stored_verdict_cap"], "AVOID")
        self.assertTrue(out["verdict_cap_changed"])

    def test_stored_dossier_is_never_mutated(self):
        stored = _stored_result(1100.0)
        before = json.dumps(stored, sort_keys=True)
        app_mod.reprice_result(stored, 500.0, ticker="NFLX", spec_date="2026-07-18")
        self.assertEqual(before, json.dumps(stored, sort_keys=True))

    def test_missing_price_new_is_refused_not_guessed(self):
        out = app_mod.reprice_result(_stored_result(), None, ticker="NFLX",
                                     spec_date="2026-07-18")
        self.assertFalse(out["repriced"])
        self.assertIn("price_new", out["_errors"])

    def test_empty_result_is_an_error_not_a_crash(self):
        out = app_mod.reprice_result({}, 500.0)
        self.assertFalse(out["repriced"])
        self.assertIn("result", out["_errors"])


class TestRepriceFreshnessGates(unittest.TestCase):

    def test_stale_spec_age_is_refused(self):
        fr = app_mod.reprice_freshness("NFLX", "2020-01-01")
        self.assertFalse(fr["fresh"])
        self.assertEqual(fr["refusal"]["reason"], "spec_stale_age")

    def test_unparseable_spec_date_is_refused_never_assumed_fresh(self):
        fr = app_mod.reprice_freshness("NFLX", "yesterday-ish")
        self.assertFalse(fr["fresh"])
        self.assertEqual(fr["refusal"]["reason"], "spec_date_unparseable")

    def _recent_spec_date(self):
        import time
        return time.strftime("%Y-%m-%d", time.gmtime(time.time() - 5 * 86400))

    def test_newer_filing_refuses_and_names_form_date_accession(self):
        spec = self._recent_spec_date()
        import time
        newer_day = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 1 * 86400))
        subs = {"filings": {"recent": {
            "form": ["4", "10-Q"], "filingDate": [newer_day, newer_day],
            "accessionNumber": ["0000000000-26-000001", "0000000000-26-000002"]}}}
        with mock.patch.object(edgar_mod, "_resolve_cik", return_value="0001065280"), \
             mock.patch.object(edgar_mod, "_get", return_value=subs):
            fr = app_mod.reprice_freshness("NFLX", spec)
        self.assertFalse(fr["fresh"])
        self.assertEqual(fr["refusal"]["reason"], "newer_filing_since_spec")
        f = fr["refusal"]["filings"][0]
        self.assertEqual(f["form"], "10-Q")          # Form 4 must NOT trigger the gate
        self.assertEqual(f["filingDate"], newer_day)
        self.assertTrue(f["accession"])

    def test_no_newer_filing_passes_the_gate(self):
        spec = self._recent_spec_date()
        subs = {"filings": {"recent": {
            "form": ["10-Q"], "filingDate": ["2026-01-05"],
            "accessionNumber": ["0000000000-26-000009"]}}}
        with mock.patch.object(edgar_mod, "_resolve_cik", return_value="0001065280"), \
             mock.patch.object(edgar_mod, "_get", return_value=subs):
            fr = app_mod.reprice_freshness("NFLX", spec)
        self.assertTrue(fr["fresh"])

    def test_edgar_unreachable_refuses_unknown_is_not_fresh(self):
        spec = self._recent_spec_date()
        with mock.patch.object(edgar_mod, "_resolve_cik",
                               side_effect=RuntimeError("net down")):
            fr = app_mod.reprice_freshness("NFLX", spec)
        self.assertFalse(fr["fresh"])
        self.assertEqual(fr["refusal"]["reason"], "edgar_unreachable")


class TestRepriceRoute(unittest.TestCase):

    def setUp(self):
        self.client = app_mod.app.test_client()

    def test_route_refuses_stale_spec_as_200(self):
        r = self.client.post("/reprice", json={"ticker": "NFLX", "spec_date": "2020-01-01",
                                               "result": _stored_result()})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertFalse(body["repriced"])
        self.assertEqual(body["refusal"]["reason"], "spec_stale_age")

    def test_route_never_500s_on_garbage(self):
        r = self.client.post("/reprice", data="not json at all",
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["repriced"])

    def test_route_full_happy_path_with_mocked_freshness_and_price(self):
        macro_mod = load_microservice_module("macro_prices")
        with mock.patch.object(app_mod, "reprice_freshness",
                               return_value={"fresh": True, "refusal": None,
                                             "spec_age_days": 2.0, "_errors": {}}), \
             mock.patch.object(macro_mod, "tiingo_series", return_value=[900.0, 912.5]):
            r = self.client.post("/reprice", json={"ticker": "NFLX",
                                                   "spec_date": "2026-07-16",
                                                   "result": _stored_result(1100.0)})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertTrue(body["repriced"])
        self.assertEqual(body["price_new"], 912.5)
        self.assertEqual(body["spec_age_days"], 2.0)
        self.assertTrue(body["triggers"]["complete"])

    def test_route_refuses_when_no_fresh_price(self):
        macro_mod = load_microservice_module("macro_prices")
        with mock.patch.object(app_mod, "reprice_freshness",
                               return_value={"fresh": True, "refusal": None,
                                             "spec_age_days": 2.0, "_errors": {}}), \
             mock.patch.object(macro_mod, "tiingo_series", return_value=[]):
            r = self.client.post("/reprice", json={"ticker": "NFLX",
                                                   "spec_date": "2026-07-16",
                                                   "result": _stored_result()})
        body = r.get_json()
        self.assertFalse(body["repriced"])
        self.assertEqual(body["refusal"]["reason"], "no_fresh_price")


if __name__ == "__main__":
    unittest.main()
