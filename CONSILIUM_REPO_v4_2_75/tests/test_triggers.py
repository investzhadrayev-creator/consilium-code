"""
BACKLOG #4: /triggers — 5 transition prices from RESULT (ARCHITECTURE §3 trigger_prices).

Contract under test:
- band AVOID->WATCH+ = FV10/1.12^10, WATCH+->BUY = FV10/1.16^10 (the §3 formulas, verbatim);
- ladder rows are READ from RESULT.mos_ladder (ivc_lib's pinned output), never recomputed;
- a missing driver removes the row AND lands in _errors — no zeros, no guesses;
- dividend payers: the §3 band formula vs ivc_lib's buy_threshold_hurdle divergence is SURFACED.

The consumer test rule applies (CLAUDE.md): the route itself is driven, not just the function —
the /analyze wiring defect (check #4 in the smoke test) shipped precisely because no test drove
the route.
"""
import unittest

from _support import load_microservice_module

app_mod = load_microservice_module("app")


def _result(fv10=193.24, iv=62.22, bth=None, ladder=True):
    r = {"ivc_base": {"fv10_per_share": fv10, "intrinsic_value": iv,
                      "buy_threshold_hurdle": bth if bth is not None else (fv10 / (1.12 ** 10))}}
    if ladder:
        r["mos_ladder"] = [
            {"mos_target_pct": 10.0, "buy_threshold_price": round(iv / 1.10, 2)},
            {"mos_target_pct": 20.0, "buy_threshold_price": round(iv / 1.20, 2)},
            {"mos_target_pct": 30.0, "buy_threshold_price": round(iv / 1.30, 2)},
        ]
    return r


class TestTriggerPrices(unittest.TestCase):

    def test_verdict_leg_fv10_wins_over_base_leg_fv10(self):
        """v4.2.34 (mandate HH). The bands must be built from the VERDICT leg's FV10. The older
        pins in this file feed fv10 only inside ivc_base and therefore exercise the FALLBACK path;
        this pin exercises the primary one, so the fix cannot silently regress to the base leg."""
        r = _result(fv10=193.24)          # base-leg FV10
        r["fv10_verdict_leg"] = 150.00    # verdict leg is lower (conservative)
        out = app_mod.trigger_prices(r)
        by = {t["trigger_type"]: t["price"] for t in out["triggers"]}
        self.assertAlmostEqual(by["band_avoid_to_watch"], round(150.00 / (1.12 ** 10), 2),
                               msg="band12 must use the verdict leg's FV10, not the base leg's")
        self.assertAlmostEqual(by["band_watch_to_buy"], round(150.00 / (1.16 ** 10), 2))
        self.assertNotAlmostEqual(by["band_avoid_to_watch"], round(193.24 / (1.12 ** 10), 2),
                                  msg="the base-leg FV10 must no longer drive the band")

    def test_five_rows_and_the_exact_band_formulas(self):
        out = app_mod.trigger_prices(_result(), ticker="NFLX", spec_date="2026-07-18",
                                     spec_version="v4.2.16")
        self.assertTrue(out["complete"])
        self.assertEqual(len(out["triggers"]), 5)
        by = {t["trigger_type"]: t["price"] for t in out["triggers"]}
        self.assertAlmostEqual(by["band_avoid_to_watch"], round(193.24 / (1.12 ** 10), 2))
        self.assertAlmostEqual(by["band_watch_to_buy"], round(193.24 / (1.16 ** 10), 2))
        # provenance travels with every row (a number's basis travels with it)
        for t in out["triggers"]:
            self.assertEqual(t["derived_from_spec_date"], "2026-07-18")
            self.assertEqual(t["spec_version"], "v4.2.16")

    def test_ladder_is_read_not_recomputed(self):
        """Poison the ladder deliberately: if the function recomputed IV/(1+t) it would
        'correct' these prices. It must carry them verbatim — ivc_lib is the one home."""
        r = _result()
        r["mos_ladder"][0]["buy_threshold_price"] = 55.55
        out = app_mod.trigger_prices(r)
        by = {t["trigger_type"]: t["price"] for t in out["triggers"]}
        self.assertEqual(by["ladder_10"], 55.55)

    def test_missing_fv10_withholds_bands_and_names_the_gap(self):
        r = _result()
        del r["ivc_base"]["fv10_per_share"]
        out = app_mod.trigger_prices(r)
        types = {t["trigger_type"] for t in out["triggers"]}
        self.assertNotIn("band_avoid_to_watch", types)
        self.assertNotIn("band_watch_to_buy", types)
        self.assertIn("fv10_per_share", out["_errors"])
        self.assertFalse(out["complete"])

    def test_missing_ladder_rung_is_withheld_and_named(self):
        r = _result()
        r["mos_ladder"] = r["mos_ladder"][:2]  # 30% rung gone
        out = app_mod.trigger_prices(r)
        types = {t["trigger_type"] for t in out["triggers"]}
        self.assertNotIn("ladder_30", types)
        self.assertIn("mos_ladder", out["_errors"])
        self.assertIn("[30]", out["_errors"]["mos_ladder"])
        self.assertFalse(out["complete"])

    def test_zero_fv10_is_treated_as_absent_not_as_a_price(self):
        """Unknown is not zero — and zero is not a valid FV10 either. A dropped-zero artifact
        arriving here must not mint a $0.00 trigger price."""
        out = app_mod.trigger_prices(_result(fv10=0))
        self.assertIn("fv10_per_share", out["_errors"])
        self.assertEqual([t for t in out["triggers"] if t["trigger_type"].startswith("band")], [])

    def test_dividend_divergence_is_surfaced_not_averaged(self):
        # ivc_lib threshold includes the dividend FV leg -> materially above the bare formula
        out = app_mod.trigger_prices(_result(bth=193.24 / (1.12 ** 10) * 1.05))
        self.assertIn("band12_vs_hurdle_threshold", out)
        d = out["band12_vs_hurdle_threshold"]
        self.assertNotEqual(d["band_formula"], d["ivc_lib_threshold"])

    def test_empty_result_is_an_error_not_a_crash_and_not_zeros(self):
        out = app_mod.trigger_prices({})
        self.assertEqual(out["triggers"], [])
        self.assertIn("result", out["_errors"])


class TestTriggersRoute(unittest.TestCase):
    """Drive the ROUTE — the /analyze wiring bug lived exactly in the gap between a correct
    function and an untested route."""

    def setUp(self):
        self.client = app_mod.app.test_client()

    def test_route_is_wired_to_trigger_prices(self):
        resp = self.client.post("/triggers", json={"result": _result(), "ticker": "NFLX"})
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["complete"])
        self.assertEqual(len(body["triggers"]), 5)

    def test_route_never_500s_on_garbage(self):
        resp = self.client.post("/triggers", data="not json at all",
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["triggers"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
