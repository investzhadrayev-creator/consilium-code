"""Regressions for the four defects the NFLX 2026-07-16 run exposed.

Every test here names a real failure. None of them is hypothetical.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "microservice"))
import app                      # noqa: E402
import ivc_lib                  # noqa: E402
import finra_short_interest     # noqa: E402


class TestUnknownIsNotZero(unittest.TestCase):
    """A missing input is UNKNOWN. Scoring it 0 turns a data gap into a business judgment."""

    def test_unconfirmed_split_withholds_eps_score_instead_of_scoring_zero(self):
        gt = {"revenue": [{"end": "%d-12-31" % y, "val": v} for y, v in
                          [(2020, 24996e6), (2021, 29698e6), (2022, 31616e6),
                           (2023, 33723e6), (2024, 39001e6), (2025, 45180e6)]],
              "eps_cagr_5y": -0.16096, "eps_series_unreliable": True}
        a = ivc_lib.gps_quant(gt)["detail"]["A"]
        self.assertEqual(a["pts"]["eps"], "[UNVERIFIED]")
        self.assertEqual(a["max_quant"], 10, "the 6 eps points must leave the DENOMINATOR too")
        self.assertIn("split", a["eps_unverified_reason"])

    def test_unreliable_series_is_not_silently_recomputed_from_the_poisoned_series(self):
        """gps_quant used to fall back to _cagr(eps_series_obj) when eps_cagr_5y was null --
        which is the exact corrupted series we just refused to trust."""
        series = [{"end": "2020-12-31", "val": 6.08}, {"end": "2025-12-31", "val": 2.53}]
        gt = {"eps_cagr_5y": None, "eps_series_obj": series, "eps_series_unreliable": True}
        self.assertIsNone(ivc_lib.gps_quant(gt)["detail"]["A"]["eps_cagr5"])

    def test_null_dilution_does_not_score_zero(self):
        """NFLX was SHRINKING its share count (buybacks at 96.5% of FCF) and scored 0/4 for
        dilution because the clamp nulled the field. Sign inverted by a data gap."""
        d = ivc_lib.gps_quant({"debt_to_equity": 0.5, "dilution_cagr": None,
                               "sbc_to_revenue": 0.008})["detail"]["D"]
        self.assertEqual(d["pts"]["shares"], "[UNVERIFIED]")
        self.assertEqual(d["max"], 6)

    def test_null_valuation_inputs_do_not_read_as_expensive(self):
        """Stage 2b diagnosed this in prose: 'structurally starved of forward-PE data, not a
        judgment that valuation is cheap.'"""
        c = ivc_lib.gps_quant({"peg": 1.45, "fwd_pe_vs_sector": None,
                               "implied_cagr_base": None})["detail"]["C"]
        self.assertEqual(c["pts"]["fwd_pe"], "[UNVERIFIED]")
        self.assertEqual(c["max"], 5, "only PEG was measurable")

    def test_present_inputs_still_score_exactly_as_before(self):
        """The rule changed only for MISSING inputs. Real scores must not move."""
        c = ivc_lib.gps_quant({"peg": 1.45, "fwd_pe_vs_sector": 1.0,
                               "implied_cagr_base": 0.15})["detail"]["C"]
        self.assertEqual(c["pts"], {"peg": 4, "fwd_pe": 3, "icagr": 4})
        self.assertEqual(c["max"], 15)


class TestRouteWiring(unittest.TestCase):
    """Every @app.route must reach the handler its name promises.

    Caught during v4.2.2: inserting two module-level helpers at the first `def _analyze(`
    landed them BETWEEN the /analyze decorator and its view function, so @app.route("/analyze")
    silently rebound to a 1-arg helper. Flask calls views with no args -> TypeError on every
    valuation request -> the whole Core-P fork dead. All 163 tests passed: the suite checked
    that functions behave, never that the ROUTES point at them. A decorator is action at a
    distance; only the url_map knows the truth.
    """

    EXPECTED = {
        "/health": "health",
        "/analyze": "_analyze",
        "/enrich_yf": "_enrich_yf",
        "/scenario_tree": "_scenario_tree",
        "/edgar_facts": "_edgar_facts",
        "/edgar_form4": "_edgar_form4",
        "/market_facts": "_market_facts",
        "/macro_prices": "_macro_prices",
    }

    def test_every_route_reaches_its_named_handler(self):
        rules = {r.rule: r.endpoint for r in app.app.url_map.iter_rules()}
        for route, handler in self.EXPECTED.items():
            self.assertIn(route, rules, "route %s vanished" % route)
            self.assertEqual(rules[route], handler,
                             "%s is wired to %r, expected %r" % (route, rules.get(route), handler))

    def test_no_view_function_takes_required_arguments(self):
        """A view Flask calls with no args must not require any -- the exact failure above."""
        import inspect
        for rule in app.app.url_map.iter_rules():
            fn = app.app.view_functions.get(rule.endpoint)
            if fn is None or rule.endpoint == "static":
                continue
            required = [p for p in inspect.signature(fn).parameters.values()
                        if p.default is inspect.Parameter.empty
                        and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
            self.assertEqual(required, [],
                             "view %s for %s requires args %s; Flask passes none"
                             % (rule.endpoint, rule.rule, [p.name for p in required]))


class TestPeerBasisNeverAnchorsForwardCap(unittest.TestCase):
    def test_trailing_peer_median_is_excluded(self):
        d = {"peer_median_pe": 95.09, "peer_median_pe_basis": "edgar_tiingo_trailing_inhouse"}
        self.assertIsNone(app._pe_anchor_fwd(d))
        self.assertTrue(app._peer_pe_excluded(d))

    def test_forward_peer_median_is_still_used(self):
        d = {"peer_median_pe": 30.0, "peer_median_pe_basis": "yahoo_forward"}
        self.assertEqual(app._pe_anchor_fwd(d), 30.0)
        self.assertFalse(app._peer_pe_excluded(d))

    def test_unlabelled_peer_median_is_trusted_as_forward(self):
        """Legacy yahoo path sets no basis; it IS forward. Do not silently discard it."""
        self.assertEqual(app._pe_anchor_fwd({"peer_median_pe": 28.0}), 28.0)


class TestFinraStaleness(unittest.TestCase):
    def test_query_is_bounded_by_a_settlement_date_window(self):
        """A client-side sort cannot repair a server-side truncation: the old body asked for
        60 rows with no date bound, so we sorted the wrong 60 and returned 2022-11-30."""
        src = open(os.path.join(os.path.dirname(__file__), "..", "microservice",
                                "finra_short_interest.py"), encoding="utf-8").read()
        self.assertIn("dateRangeFilters", src)
        self.assertIn("settlementDate", src.split("dateRangeFilters")[1][:200])

    def test_stale_settlement_is_refused_not_reported(self):
        calls = {}

        def fake_post(url, headers, body):
            calls["body"] = body
            return [{"settlementDate": "2022-11-30", "currentShortPositionQuantity": 10480000,
                     "previousShortPositionQuantity": 10890000, "daysToCoverQuantity": 1.39}]

        errs = {}
        orig_post, orig_tok = finra_short_interest._post_json, finra_short_interest._get_token
        finra_short_interest._post_json = fake_post
        finra_short_interest._get_token = lambda *a, **k: "tok"
        try:
            r = finra_short_interest.finra_short_interest("NFLX", "id", "secret", errs)
        finally:
            finra_short_interest._post_json, finra_short_interest._get_token = orig_post, orig_tok
        self.assertIsNone(r, "a 3.5-year-old settlement must never travel as a current fact")
        self.assertIn("2022-11-30", errs["finra_short"])

    def test_fresh_settlement_still_returns(self):
        import time
        fresh = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 10 * 86400))
        orig_post, orig_tok = finra_short_interest._post_json, finra_short_interest._get_token
        finra_short_interest._post_json = lambda u, h, b: [
            {"settlementDate": fresh, "currentShortPositionQuantity": 50000000,
             "previousShortPositionQuantity": 48000000, "daysToCoverQuantity": 2.1}]
        finra_short_interest._get_token = lambda *a, **k: "tok"
        try:
            r = finra_short_interest.finra_short_interest("NFLX", "id", "secret", {})
        finally:
            finra_short_interest._post_json, finra_short_interest._get_token = orig_post, orig_tok
        self.assertIsNotNone(r)
        self.assertEqual(r["settlement_date"], fresh)


class TestSplitConfirmationReadsBothEndpoints(unittest.TestCase):
    def test_detector_merges_companyconcept(self):
        """companyfacts can keep one value per period; a split confirmation IS 'one period,
        two values'. A deduped source cannot confirm a split, by construction."""
        import edgar_facts
        facts = {"facts": {"us-gaap": {"WeightedAverageNumberOfDilutedSharesOutstanding": {
            "units": {"shares": [{"start": "2023-01-01", "end": "2023-12-31", "val": 449497000,
                                  "form": "10-K", "filed": "2024-01-25", "accn": "a1"}]}}}}}
        concept_only = {"shares": [
            {"start": "2023-01-01", "end": "2023-12-31", "val": 449497000,
             "form": "10-K", "filed": "2024-01-25", "accn": "a1"},
            {"start": "2023-01-01", "end": "2023-12-31", "val": 4494970000,
             "form": "10-K", "filed": "2026-01-27", "accn": "a2"}]}
        orig = edgar_facts._companyconcept
        edgar_facts._companyconcept = lambda cik, tax, tag: concept_only
        try:
            without = edgar_facts._detect_confirmed_splits(
                facts, ["WeightedAverageNumberOfDilutedSharesOutstanding"])
            with_cc = edgar_facts._detect_confirmed_splits(
                facts, ["WeightedAverageNumberOfDilutedSharesOutstanding"], cik="0001065280")
        finally:
            edgar_facts._companyconcept = orig
        self.assertEqual(without, [], "companyfacts alone cannot see the restatement")
        self.assertEqual(len(with_cc), 1)
        self.assertEqual(with_cc[0]["factor"], 10)
        self.assertEqual(with_cc[0]["end"], "2023-12-31")



class TestGpsWiringV424(unittest.TestCase):
    """v4.2.4 — two defects the live NFLX 2026-07-17 report exposed. Both are the SAME disease as
    v4.2.2: the deterministic layer computed an honest number and the boundary threw it away.
    Neither was catchable by any gps_quant unit test, because gps_quant was correct in both cases.
    Only analyze() -- the thing that CALLS it -- was wrong. So these tests drive analyze()."""

    @staticmethod
    def _run(spec_over=None, data_over=None):
        # THE FCF LEG NEEDS TWO INPUTS, NOT ONE. This comment used to claim that
        # `levered_fcf_per_share` alone "ACTIVATES the FCF leg -> dual_basis exists -> the
        # verdict-leg test actually runs". It was false from the moment v4.2.60 (dil-03) landed:
        # analyze() now REFUSES the FCF leg when net dilution is unknown, because gross dilution
        # cannot be derived from an unknown net and assuming zero would flatter the leg that
        # competes to be the verdict. So `fcfps = None`, `dual_basis` stayed null, and the pin below
        # went on skipping itself — under a comment asserting that it did not.
        #
        # The comment is the finding: it stated an OUTCOME nobody measured. Same class as
        # rule 5 (a fixture agreeing with itself proves nothing), one layer out — prose agreeing
        # with an intention rather than with the code. `dilution_cagr` is what was missing.
        data = {"ticker": "TEST", "eps0_reported": 2.5, "peg": 1.45,
                "levered_fcf_per_share": 2.25,
                "dilution_cagr": 0.01,
                "price_data": {"current_price": 50}, "macro_data": {"risk_free": 0.04}}
        data.update(data_over or {})
        spec = {"assumptions": {"growth_rate": 0.10, "future_pe": 20, "hurdle": 0.12},
                "scenarios": {"base": {"weight": 1.0, "overrides": {}}}}
        spec.update(spec_over or {})
        return app.analyze(data, spec)

    def test_implied_cagr_reaches_the_C_block_at_all(self):
        """THE defect: gps_quant asks for gt['implied_cagr_base']; nothing ever set it. C's icagr
        leg was [UNVERIFIED] for every ticker on every run since v4, while the number sat in
        ivc_base and in the report's own headline table."""
        r = self._run()
        c = r["gps"]["quant_detail"]["C"]
        self.assertIsNotNone(c["implied_cagr"],
                             "implied_cagr never reached gps_quant — the v4.2.4 wiring defect")
        self.assertNotEqual(c["pts"]["icagr"], "[UNVERIFIED]",
                            "the icagr leg is permanently unverified for every ticker")

    def test_implied_cagr_is_passed_as_a_FRACTION_not_percent(self):
        """The landmine in the fix. implied_cagr_pct is PERCENT (ivc_lib rounds icagr*100); the
        gps_quant grid compares against 0.16/0.14/0.12. Feed 13.55 where 0.1355 belongs and every
        ticker silently scores a perfect 5 on valuation — a wiring bug that INFLATES scores is far
        worse than one that withholds them."""
        r = self._run()
        ic = r["gps"]["quant_detail"]["C"]["implied_cagr"]
        self.assertLess(abs(ic), 1.5, "implied_cagr looks like a percent, not a fraction (%r)" % ic)
        legs = r["dual_basis"] or {}
        leg = legs.get(legs.get("verdict_leg")) if legs else None
        if leg and leg.get("implied_cagr_pct") is not None:
            self.assertAlmostEqual(ic, leg["implied_cagr_pct"] / 100.0, places=6)

    def test_C_block_scores_the_VERDICT_leg_not_the_optimistic_one(self):
        """verdict_cap follows the conservative leg. If C scored the optimistic leg, the scorecard
        would credit valuation that the verdict denies, in the same report.

        v4.2.82 changeset: the `if not db: self.skipTest(...)` that used to open this test is gone.
        A missing FCF leg is now a FAILURE of this test, not an excuse from it — the absent leg was
        the reason the invariant went unchecked from the day it was written. The two guards below
        are what make the assertion mean something: both legs must exist, and they must DIFFER,
        because when the legs coincide the pin is satisfied by either one and cannot tell the
        verdict leg from the optimistic one.
        """
        r = self._run()
        db = r.get("dual_basis")
        self.assertTrue(db, "the fixture must build BOTH legs — without dual_basis this invariant "
                            "is not tested, and a skip here reads as a pass")
        ic_g = db["gaap_eps"]["implied_cagr_pct"]
        ic_f = db["fcf_per_share"]["implied_cagr_pct"]
        self.assertIsNotNone(ic_g)
        self.assertIsNotNone(ic_f)
        self.assertNotAlmostEqual(ic_g, ic_f, places=2,
                                  msg="the legs must differ, else scoring the optimistic leg "
                                      "would satisfy this pin too")
        verdict_leg = db["verdict_leg"]
        self.assertEqual(verdict_leg, "gaap_eps" if ic_g <= ic_f else "fcf_per_share",
                         "the verdict leg must be the CONSERVATIVE one")
        leg = db[verdict_leg]
        self.assertAlmostEqual(r["gps"]["quant_detail"]["C"]["implied_cagr"],
                               leg["implied_cagr_pct"] / 100.0, places=6,
                               msg="block C scored a leg the verdict does not follow")

    def test_reduced_max_survives_the_block_assembly(self):
        """gps_quant reduces a block's max when an input is unmeasurable; analyze() hardcoded
        16/15/15/10/10 and overwrote it. ivc_lib's docstring forbids exactly that."""
        r = self._run()
        c_block = next(b for b in r["gps"]["blocks"] if b["name"].startswith("C "))
        self.assertEqual(c_block["max"], r["gps"]["quant_detail"]["C"]["max"],
                         "the C row's max was hardcoded, not read from gps_quant")

    def test_gps_denominator_is_not_a_nominal_100_when_inputs_are_missing(self):
        """fwd_pe_vs_sector is absent here, so C loses 5 points of DENOMINATOR. A GPS that always
        says /100 cannot distinguish 'scored badly' from 'could not be scored'."""
        r = self._run()
        self.assertLess(r["gps"]["max"], 100,
                        "denominator stayed nominal despite an unmeasurable sub-block")
        self.assertEqual(r["gps"]["max"], sum(b["max"] for b in r["gps"]["blocks"]),
                         "headline max must equal the sum of the rendered rows — always auditable")
        self.assertIsNotNone(r["gps"]["_max_note"], "a reduced denominator must say why")

    def test_full_inputs_restore_the_full_denominator(self):
        """The inverse pin: nothing missing -> /100. The reduction must be evidence-driven, not a
        permanent haircut."""
        r = self._run(data_over={"fwd_pe_vs_sector": 0.9})
        c_block = next(b for b in r["gps"]["blocks"] if b["name"].startswith("C "))
        self.assertEqual(c_block["max"], 15, "all three C inputs present -> full 15")


# v4.2.82 micro-changeset (architect's decision, 2026-08-05). This guard used to sit ~150 lines
# further up — between TestSplitConfirmationReadsBothEndpoints and TestGpsWiringV424 —
# so `python3 tests/test_v422_regressions.py` executed unittest.main() at that point and ran only
# the classes defined ABOVE it, printing a green summary over a SUBSET without the word "skipped"
# appearing anywhere. Under `unittest discover` the file was fine, which is exactly why it
# survived: the harmless path was the one everybody used.
#
# Third mechanism of one class in a single day: (1) a self-skip counted as a pass, (2) a bare `if`
# around the only assertion, (3) a main-guard truncating a direct run. The rule they share is the
# one from 2026-07-17 — a check reports what it examined, or it reports nothing — and each time it
# was defeated by a DIFFERENT mechanism, never by a repeat. Auditing for the known shape is not
# enough; the shape is not the invariant.
if __name__ == "__main__":
    unittest.main(verbosity=2)
