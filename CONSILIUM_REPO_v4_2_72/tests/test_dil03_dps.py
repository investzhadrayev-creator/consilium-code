"""v4.2.60 — two IV-shifting defects closed together, because they shift it in OPPOSITE directions.

dil-03   pushed IV UP:   a missing net-dilution figure was read as `0.0`, i.e. "this company issues
                         no net shares" — the most flattering reading available, applied to the leg
                         that competes to become the verdict leg.
dps_series pushed IV DOWN: `dividend_growth` has been hard 0 since v4.2.31 because no DPS series was
                         ever emitted, which understates IV on every dividend payer, MA included.

Closing only one would have moved the anchor in one direction and made the NFLX re-run
uninterpretable. Both are runtime; both are pinned here.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "microservice"))
import app                      # noqa: E402
import edgar_facts              # noqa: E402

analyze = app.analyze


def _base(**over):
    d = {
        "price_data": {"current_price": {"adjClose": 100.0}},
        "eps0_reported": 5.0,
        "levered_fcf_per_share": 6.0,
        "dilution_cagr": -0.01,
        "pe_median_5y": 20.0,
        "pe_median_10y": 20.0,
        "revenue": [{"val": v, "end": str(y)} for y, v in
                    [(2020, 10e9), (2021, 11e9), (2022, 12.1e9),
                     (2023, 13.3e9), (2024, 14.6e9), (2025, 16.1e9)]],
    }
    d.update(over)
    return d


SPEC = {"assumptions": {"growth_rate": 0.10, "future_pe": 20}}


class TestDil03UnknownIsNotZero(unittest.TestCase):

    def test_known_dilution_still_produces_the_fcf_leg(self):
        r = analyze(_base(), SPEC)
        self.assertIsNotNone(r.get("dual_basis"), "control: a known dilution must still dual-basis")

    def test_UNKNOWN_dilution_refuses_the_fcf_leg_instead_of_assuming_zero(self):
        """The reachable path: the workflow nulls dilution_cagr whenever |CAGR| > 20% as a split
        artifact, and NFLX has already landed there. Assuming 0 there does not merely guess — it
        guesses in the direction that makes the leg cheaper, and a cheaper leg wins the verdict."""
        r = analyze(_base(dilution_cagr=None), SPEC)
        self.assertIsNone(r.get("dual_basis"),
                          "the FCF leg was computed on an INVENTED zero dilution")
        self.assertTrue(any("fcf_leg_skipped" in f for f in r.get("flags", [])),
                        "the refusal must be NAMED, not silent: %s" % r.get("flags"))

    def test_refusing_the_fcf_leg_does_not_by_itself_move_the_verdict_leg(self):
        """Isolate the REFUSAL from the missing input.

        The naive form — known-dilution run vs unknown-dilution run — fails, but NOT for the
        reason first written here. The original comment said the unknown value "legitimately moves
        the base IV (78.08 -> 70.61)". That was wrong, and the architect's grep caught it: the GAAP
        leg had no honest handling of unknown at all — it read `_f(..., 0.0)` and the IV moved
        because -0.01 was silently replaced by the constant 0.0. The movement was the DEFECT, and
        this docstring had rationalised it. See TestVerdictLegDilutionUnverified for the fix.
        The pin itself is still the right shape: hold the unknown fixed on both sides and vary only
        whether an FCF leg could have existed at all."""
        no_fcf = analyze(_base(dilution_cagr=None, levered_fcf_per_share=None), SPEC)
        refused = analyze(_base(dilution_cagr=None), SPEC)
        self.assertEqual(no_fcf["ivc_base"]["intrinsic_value"],
                         refused["ivc_base"]["intrinsic_value"],
                         "refusing the FCF leg disturbed the verdict leg")

    def test_unknown_SBC_makes_gross_a_labelled_FLOOR_not_a_silent_estimate(self):
        r = analyze(_base(sbc_to_revenue=None), SPEC)
        self.assertTrue(any("gross_dilution_is_a_FLOOR" in f for f in r.get("flags", [])),
                        "an unestimable add-back was passed off as measured: %s" % r.get("flags"))


class TestDpsSeriesWiring(unittest.TestCase):

    DPS = [{"val": v, "end": "%d-12-31" % y} for y, v in
           [(2020, 1.60), (2021, 1.76), (2022, 1.96), (2023, 2.28), (2024, 2.64), (2025, 3.04)]]

    def test_a_wired_dps_series_lifts_dividend_growth_off_zero(self):
        r = analyze(_base(dps_series=self.DPS, dividend_yield=0.005), SPEC)
        # Published under base_determinism — `inputs` is the ivc() argument summary, not the
        # full determinism record. Reading the wrong surface for a number is how this session
        # started; check the one the report actually prints.
        self.assertGreater(r["base_determinism"]["dividend_growth_used"], 0,
                           "dps_series wired but dividend_growth still 0")
        self.assertFalse(any("dps_series not yet wired" in f for f in r.get("flags", [])),
                         "the 'not yet wired' flag outlived the wiring")

    def test_dividend_growth_can_never_exceed_the_business_growth(self):
        """A dividend cannot be modelled compounding faster than what funds it."""
        wild = [{"val": v, "end": "%d-12-31" % y} for y, v in
                [(2020, 0.10), (2021, 0.30), (2022, 0.90), (2023, 2.70), (2024, 8.10), (2025, 24.3)]]
        r = analyze(_base(dps_series=wild, dividend_yield=0.005), SPEC)
        dg = r["base_determinism"]["dividend_growth_used"]
        g = r["ivc_base"]["inputs"]["g"]
        self.assertLessEqual(dg, g + 1e-9,
                             "dividend growth outran the business: %s vs %s" % (dg, g))

    def test_no_series_still_means_zero_AND_says_so(self):
        r = analyze(_base(), SPEC)
        self.assertEqual(r["base_determinism"]["dividend_growth_used"], 0.0)
        self.assertTrue(any("dividend_growth=0" in f for f in r.get("flags", [])),
                        "a zero that is really an absence must announce itself")


class TestDividendZeroSaysWHY(unittest.TestCase):
    """v4.2.64 — the zero must name its CAUSE.

    The single old message ("dps_series not yet wired in Growth Enrich") outlived its truth in
    v4.2.60 and was still printed on the NFLX pair of 2026-08-02, where the real reason is that
    Netflix pays no dividend. A reader cannot act on the two the same way: one is a fact about the
    company and a correct zero, the other is an engineering gap. The distinction already existed
    one layer down in edgar_facts; these pins are it reaching the flag a human reads.
    """

    def _flag(self, r):
        return next((f for f in r["flags"] if f.startswith("dividend_growth=0")), "")

    def test_a_non_payer_gets_a_CORRECT_zero_not_a_defect_report(self):
        r = analyze(_base(dps_series=None,
                          _edgar={"flags": {"dps_series_absent": "no per-share dividend facts"}}),
                    SPEC)
        f = self._flag(r)
        self.assertIn("CORRECT zero", f, f)
        self.assertNotIn("wired", f, "a non-payer must not be reported as an engineering gap")

    def test_a_refused_window_says_the_zero_is_a_PLACEHOLDER(self):
        r = analyze(_base(dps_series=None, _edgar={"flags": {
            "dps_series_refused_split_in_window": "confirmed split in 2022 inside the window"}}),
            SPEC)
        f = self._flag(r)
        self.assertIn("REFUSED", f, f)
        self.assertIn("placeholder", f, "a data defect must not read as a measurement")
        self.assertIn("2022", f, "the reason must travel with the flag, not be summarised away")

    def test_a_genuine_wiring_gap_is_STILL_reported_as_one(self):
        """The branch must not become unreachable: it is the only signal that the handoff broke."""
        r = analyze(_base(), SPEC)   # no _edgar block at all
        f = self._flag(r)
        self.assertIn("engineering gap", f, f)

    def test_the_stale_v4_2_31_wording_is_gone_everywhere(self):
        """Rule 12 completeness, by grep rather than by memory."""
        import glob
        root = os.path.join(os.path.dirname(__file__), "..")
        hits = []
        for pat in ("microservice/*.py", "workflow/*.json"):
            for path in glob.glob(os.path.join(root, pat)):
                with open(path, encoding="utf-8") as fh:
                    if "not yet wired" in fh.read():
                        hits.append(os.path.basename(path))
        self.assertEqual(hits, [], "the retired wording survives in: %s" % hits)


class TestDpsSplitRefusal(unittest.TestCase):
    """As-reported per-share amounts are incomparable across a split. There is no DPS
    split-normalisation in this codebase, so the window is REFUSED rather than published corrupted —
    the same defect class as the NVDA share-count artifact of v4.2.2."""

    def test_the_tag_map_prefers_DECLARED_over_cash_paid(self):
        """Cash-paid straddles periods on the payment calendar and injects timing as growth."""
        self.assertEqual(edgar_facts.DURATION_TAGS["dps"][0],
                         "CommonStockDividendsPerShareDeclared")

    def test_the_refusal_and_absence_paths_are_distinct_flags(self):
        """'Refused because untrustworthy' and 'the filer pays no dividend' must never share a
        message: one is a data defect, the other is a fact about the company."""
        src = open(os.path.join(os.path.dirname(__file__), "..",
                                "microservice", "edgar_facts.py"), encoding="utf-8").read()
        self.assertIn("dps_series_refused_split_in_window", src)
        self.assertIn("dps_series_absent", src)
        i_ref = src.index("dps_series_refused_split_in_window")
        self.assertIn("out[\"dps_series\"] = None", src[:i_ref],
                      "the refusal must NULL the series, not merely flag it")


class TestVerdictLegDilutionUnverified(unittest.TestCase):
    """v4.2.61 — the read dil-03 MISSED, caught by the architect's grep, not by these tests.

    The v4.2.60 changeset fixed the FCF leg and left `app.py:159` — the GAAP leg's own
    `_f(data.get("dilution_cagr"), 0.0)` — untouched. That is the leg that JUDGES, and it becomes
    the SOLE judge precisely when the FCF leg is refused for the same missing input. The report
    claimed "three reads became one"; the truth was two of three, and the surviving one was the
    one that mattered most.

    0.0 is neutral, not conservative: it understates IV for a buyback name (MA, -2.1%) and
    OVERSTATES it for a diluter. No honest substitute number exists, so the arithmetic stays
    neutral and the VERDICT is capped instead — an unverified share count may not produce a
    bullish call.
    """

    HIGH_GROWTH = {"assumptions": {"growth_rate": 0.30, "future_pe": 20}}

    def _fast(self, **over):
        d = _base(**over)
        d["revenue"] = [{"val": v, "end": str(y)} for y, v in
                        [(2020, 10e9), (2021, 13e9), (2022, 16.9e9),
                         (2023, 22e9), (2024, 28.6e9), (2025, 37.2e9)]]
        return d

    def test_unverified_dilution_is_NAMED_on_the_verdict_leg(self):
        r = analyze(self._fast(dilution_cagr=None), self.HIGH_GROWTH)
        self.assertTrue(any("dilution_UNVERIFIED" in f for f in r["flags"]),
                        "the GAAP leg computed on an assumed 0.0 said nothing about it: %s"
                        % r["flags"])

    def test_an_unverified_share_count_cannot_produce_a_bullish_cap(self):
        """The money case. Per-share value is a quotient: with the denominator's trajectory
        unknown, the numerator's quality says nothing about the answer."""
        r = analyze(self._fast(dilution_cagr=None), self.HIGH_GROWTH)
        self.assertEqual(r["verdict_cap"], "AVOID", "a bullish cap on an unverified share count")
        self.assertTrue(any("verdict_cap lowered" in f for f in r["flags"]),
                        "the cap moved silently: %s" % r["flags"])

    def test_control_the_SAME_name_with_a_KNOWN_dilution_still_reaches_BUY(self):
        """Without this control the pin above is satisfied by a cap that always says AVOID."""
        r = analyze(self._fast(dilution_cagr=-0.01), self.HIGH_GROWTH)
        self.assertEqual(r["verdict_cap"], "BUY",
                         "the guard is over-firing: a verified name lost its cap")
        self.assertFalse(any("dilution_UNVERIFIED" in f for f in r["flags"]))

    def test_the_cap_only_LOWERS_never_lifts(self):
        """A name already at AVOID must stay there, and no path may raise a cap on this account."""
        r = analyze(_base(dilution_cagr=None), SPEC)   # slow grower -> AVOID on its own merits
        self.assertEqual(r["verdict_cap"], "AVOID")
