"""v4.2.59 — CENTRAL LENS, REVERSE DCF and the SELF-DOCUMENTATION block.

Operator decision 02.08.2026, ratified by the architect. Table 2 measured the thing these pins
protect: the PE ceiling and the fade carry 85% of the conservatism, no single layer flips MA, and
all of them together move IV from 458 to ~922. A reader shown only the conservative number cannot
see that spread — the operator's "cascade" complaint ran for two weeks with no figure to argue
over. The second lens prints the spread. It must never do anything else.
"""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "microservice"))
import app                      # noqa: E402

analyze = app.analyze


def _data(**over):
    """A SYNTHETIC MA-SHAPED fixture. Read the warning before using any number it produces.

    The revenue series below is INVENTED — plausible in shape, not Mastercard's filed series. It
    exists to exercise the two-lens code paths: a series long enough for both CAGR windows and for
    a median of increments, and PE windows above the 25 ceiling so the ceiling has something to
    bite on. eps0, dilution and price ARE the pair's real 2026-07-31 values, which is exactly what
    made the fixture dangerous: the numbers it emits look like MA numbers.

    They are not. On 2026-08-02 this fixture's output (verdict IV 432.22, central 604.03) was
    reported to the architect as if measured on the pair, and it cost a review cycle to unpick.
    The pair's real inputs give IV 457.97, and no figure from this file may be quoted against
    Table 2, the 5.2 pre-registration, or any run.
    """
    d = {
        "price_data": {"current_price": {"adjClose": 577.35}},
        "eps0_reported": 16.520971302428258,
        "dilution_cagr": -0.020721897557303248,
        "pe_median_5y": 33.92,
        "pe_median_10y": 33.44,
        "revenue": [{"val": v, "end": str(y)} for y, v in
                    [(2020, 15.30e9), (2021, 18.88e9), (2022, 22.24e9),
                     (2023, 25.10e9), (2024, 28.17e9), (2025, 32.0e9)]],
        "debt_to_equity": 3.185,
    }
    d.update(over)
    return d


SPEC = {"assumptions": {"growth_rate": 0.155, "future_pe": 24}}

#: The pair's REAL verdict-leg inputs (MA, 2026-07-31, RESULT.ivc_base.inputs). Pinned here so a
#: change to the verdict path is caught in THIS file — the one that adds a second lens — rather
#: than only in the files that predate it.
PAIR_31_07 = {"price": 577.35, "eps_normalized": 16.520971302428258,
              "growth_rate": 0.1382198495222513, "future_pe": 30, "hurdle": 0.12,
              "discount_rate": 0.12, "dividend_yield": 0.0,
              "share_dilution_cagr": -0.020721897557303248, "years": 10,
              "fade": True, "terminal_growth": 0.04}
PAIR_IV = 549.56          #: was 457.97 at ceiling 25; +20.00%, exactly 30/25
PAIR_IV_AT_OLD_CEILING = 457.97


class TestVerdictPathUnmoved(unittest.TestCase):
    """The two-lens changeset had NO licence to move the verdict number, and the isolation pins are
    about direction of dependence — they would not have caught a change to the verdict formula
    itself. This pin closes that gap: the pair's inputs must still produce the pair's IV."""

    def test_the_ceiling_is_30_and_a_revert_to_25_is_caught(self):
        """Negative control on the mandated change itself. Table 2 measured this layer at +33.8%
        of IV — the largest single conservative choice in the model — so a silent revert would be
        the most expensive quiet change available. Pinned as the RATIO, not as two numbers: the
        relationship survives a future change of either constant, a memorised pair does not."""
        import app
        self.assertEqual(app.PE_CAP, 30.0, "the absolute ceiling moved away from the mandated 30")
        import ivc_lib
        old = ivc_lib.ivc(dict(PAIR_31_07, future_pe=25))
        self.assertEqual(old["intrinsic_value"], PAIR_IV_AT_OLD_CEILING)
        self.assertAlmostEqual(PAIR_IV / PAIR_IV_AT_OLD_CEILING, 30.0 / 25.0, places=4,
                               msg="the ceiling change is not the linear 30/25 it must be")

    def test_implied_cagr_is_annualised_over_the_FULL_horizon(self):
        """Found empty by mutation_probe on 2026-08-02: case icagr-01 (annualise over 5 instead of
        10) went GREEN — no pin in the suite could tell the two apart. The exponent turns a total
        multiple into a rate, and a rate is what the 12% hurdle is compared against: over 5 instead
        of 10 years, MA's 9.44% reads as 19.86% and AVOID becomes BUY.

        Pinned as an IDENTITY rather than a remembered number: (1+icagr)^Y must reproduce the total
        multiple FV10/price. A pin on the value alone would pass any exponent that happened to
        match on one fixture."""
        import ivc_lib
        r = ivc_lib.ivc(dict(PAIR_31_07))
        total = r["fv10_per_share"] / PAIR_31_07["price"]
        implied = (1 + r["implied_cagr_pct"] / 100.0) ** PAIR_31_07["years"]
        # Tolerance, not equality: implied_cagr_pct is published rounded to 2dp, and 9.44% vs the
        # exact rate compounds to a ~0.04% gap over ten years. The tolerance is far tighter than
        # any exponent error could hide — annualising over 5 instead of 10 doubles the rate.
        self.assertAlmostEqual(implied, total, delta=0.01,
                               msg="implied CAGR is not the %d-year annualisation of FV10/price"
                                   % PAIR_31_07["years"])
        self.assertEqual(r["implied_cagr_pct"], 11.45)

    def test_the_fade_actually_slows_growth_in_years_6_to_10(self):
        """Second empty pin found by the same probe sweep (fade-01, GREEN): removing the fade
        entirely — `gy = g` for all ten years — reddened nothing. The fade is worth roughly a third
        of the conservatism measured in Table 2 (L3: +30.7% of IV on MA when removed), so an
        unguarded fade is a third of the valuation resting on untested code.

        Pinned by CONSEQUENCE, not by reading the loop: the same inputs with fade off must produce
        a strictly larger terminal value, and the faded run must land on the number three MA runs
        and Table 2 agree on."""
        import ivc_lib
        faded = ivc_lib.ivc(dict(PAIR_31_07))
        unfaded = ivc_lib.ivc(dict(PAIR_31_07, fade=False))
        self.assertGreater(unfaded["fv10_per_share"], faded["fv10_per_share"],
                           "growth is not being slowed in years 6-10: the fade is inert")
        self.assertEqual(faded["intrinsic_value"], PAIR_IV)
        # Table 2, L3: removing the fade moves IV from 457.97 to 598.41 on these inputs.
        self.assertAlmostEqual(unfaded["intrinsic_value"], 718.09, places=2)   # 598.41 x 30/25

    def test_the_pair_inputs_still_produce_457_97(self):
        import ivc_lib
        r = ivc_lib.ivc(dict(PAIR_31_07))
        self.assertEqual(r["intrinsic_value"], PAIR_IV,
                         "the verdict path moved: 3 runs, Table 2 and the 5.2 pre-registration all "
                         "rest on IV=%s" % PAIR_IV)
        self.assertEqual(r["implied_cagr_pct"], 11.45)

    def test_adding_the_central_lens_cannot_shift_the_verdict_leg(self):
        """Same inputs through the full harness: the verdict leg is what ivc() alone computes."""
        r = analyze(_data(), SPEC)
        import ivc_lib
        direct = ivc_lib.ivc(dict(r["ivc_base"]["inputs"],
                                  eps_normalized=r["ivc_base"]["inputs"]["base_per_share"],
                                  growth_rate=r["ivc_base"]["inputs"]["g"],
                                  share_dilution_cagr=r["ivc_base"]["inputs"]["dilution_cagr"],
                                  terminal_growth=r["ivc_base"]["inputs"]["terminal_g"]))
        self.assertEqual(direct["intrinsic_value"], r["ivc_base"]["intrinsic_value"],
                         "the harness verdict leg diverged from ivc() on identical inputs")


class TestCentralLens(unittest.TestCase):

    def setUp(self):
        self.r = analyze(_data(), SPEC)
        self.c = self.r.get("central_lens") or {}

    def test_central_lens_is_computed_and_uses_the_two_named_choices(self):
        """Median increments instead of endpoint CAGR; window median with NO 25 ceiling."""
        self.assertIsInstance(self.c.get("iv"), (int, float))
        self.assertAlmostEqual(self.c["future_pe_used"], 33.44, places=2,
                               msg="the central multiple must ignore the 25 ceiling")
        self.assertNotEqual(self.c["growth_used"], self.r["growth_anchor"]["base_growth_used"],
                            msg="median-of-increments must not collapse onto the endpoint CAGR")
        self.assertGreater(self.c["iv"], self.r["ivc_base"]["intrinsic_value"],
                           "on a name capped at 25, the central lens must read higher")

    def test_the_central_lens_touches_NOTHING_that_decides(self):
        """The whole point: if this fails, the second lens has become a second opinion.

        HOW THIS PIN WAS WRITTEN, and why the obvious version is worthless. The first draft ran
        analyze() twice on identical data and compared the verdict fields — which is a tautology:
        a leak is present in BOTH runs, so both sides move together and the pin stays green. It was
        caught by mutation MUT-S (leaking the uncapped window median into base_inp), which reddened
        nothing. What actually needs guarding is not equality between two identical runs but the
        DIRECTION OF DEPENDENCE: the decision path must be finished before the lens exists, and
        must never read it. That is a structural property, so it is checked structurally.
        """
        import inspect
        src = inspect.getsource(app.analyze)
        first_lens = src.index("_central_lens = None")
        decision_markers = ["verdict_cap =", "ivc_base = ", "mos_ladder"]
        for marker in decision_markers:
            idx = src.find(marker)
            self.assertTrue(0 <= idx < first_lens,
                            "%s is computed AFTER the central lens — the ordering that makes the "
                            "lens unable to influence a verdict no longer holds" % marker)
        before = src[:first_lens]
        for leaked in ("central_lens", "reverse_dcf", "_c_pe", "_c_g", "g_implied"):
            self.assertNotIn(leaked, before,
                             "the decision path reads '%s': the advisory lens has become an input"
                             % leaked)
        # And the lens says so about itself, in the payload, for any downstream reader.
        self.assertIs(self.c.get("advisory_only"), True)
        self.assertIn("advisory", (self.c.get("note") or "").lower())

    def test_no_OTHER_consumer_reads_the_advisory_fields_for_a_decision(self):
        """Structural, workflow-wide: only the renderer may touch these keys. A verdict-bearing
        node that starts reading central_lens would satisfy every numeric pin above."""
        import glob
        path = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "workflow",
                                             "consilium_spine_v*.json")))[-1]
        with open(path, encoding="utf-8") as fh:
            wf = json.load(fh)
        # v4.2.65: the brief renderer joins the render layer. Pre-registered surface list moves
        # from two to three, and the allowance is a NAMED list rather than a relaxed rule — a
        # fourth reader still fails this pin, which is the property worth keeping.
        allowed = {"Render Tables", "Assemble Brief"}
        offenders = []
        for node in wf["nodes"]:
            blob = json.dumps(node.get("parameters", {}), ensure_ascii=False)
            if ("central_lens" in blob or "reverse_dcf" in blob) and node["name"] not in allowed:
                offenders.append(node["name"])
        self.assertEqual(offenders, [],
                         "advisory fields read outside the render layer: %s" % offenders)

    def test_a_short_series_yields_a_STATED_absence_not_a_guess(self):
        """Fewer than 3 increments: a median over two points is the mean wearing another name."""
        r = analyze(_data(revenue=[{"val": 1.0e9, "end": "2024"}, {"val": 1.2e9, "end": "2025"}]),
                    SPEC)
        c = r.get("central_lens") or {}
        self.assertIsNone(c.get("iv"))
        self.assertTrue(any("central_growth_unavailable" in f for f in (c.get("flags") or [])),
                        "an unavailable lens must NAME why, never vanish: %s" % c)

    def test_the_label_matches_the_ACTUAL_base_the_lens_was_computed_on(self):
        """v4.2.64. The lens shipped labelled `leg: fcf_per_share` while being computed from the
        GAAP base — true of neither thing. The arithmetic was right: a central estimate stripped of
        the conservative layers cannot be built on the leg that was CHOSEN for conservatism, since
        that selection is itself one of the layers. Only the label was wrong, and a wrong label on
        a right number is the harder defect: nothing downstream disagrees with it.

        Two facts, named separately, and the pin proves the first one against the arithmetic rather
        than against a constant string."""
        import ivc_lib
        self.assertEqual(self.c["computed_on"], "gaap_base")
        self.assertIn("verdict_leg(", self.c["delta_vs"])
        inp = self.r["ivc_base"]["inputs"]
        recomputed = ivc_lib.ivc({
            "price": inp["price"], "eps_normalized": inp["base_per_share"],
            "growth_rate": self.c["growth_used"], "future_pe": self.c["future_pe_used"],
            "hurdle": inp["hurdle"], "discount_rate": inp["discount_rate"],
            "dividend_yield": inp["div_yield"], "share_dilution_cagr": inp["dilution_cagr"],
            "years": 10, "fade": inp["fade"], "terminal_growth": min(0.04, self.c["growth_used"]),
        })
        self.assertEqual(recomputed["intrinsic_value"], self.c["iv"],
                         "the lens does NOT reproduce from the base its label claims")

    def test_lens_delta_is_reported_so_the_spread_is_visible_without_arithmetic(self):
        self.assertIsInstance(self.c.get("delta_iv_vs_verdict_pct"), (int, float))
        expect = round((self.c["iv"] / self.r["ivc_base"]["intrinsic_value"] - 1) * 100, 1)
        self.assertAlmostEqual(self.c["delta_iv_vs_verdict_pct"], expect, places=1)


class TestReverseDCF(unittest.TestCase):

    def setUp(self):
        self.r = analyze(_data(), SPEC)
        self.rd = self.r.get("reverse_dcf") or {}

    def test_the_solved_growth_REPRODUCES_the_hurdle(self):
        """The solver is a bisection, so it always returns SOMETHING. The self-check is what makes
        the answer a solution rather than a midpoint — without it a broken solver ships silently."""
        self.assertIs(self.rd.get("selftest_reverse_matches_forward"), True)
        self.assertIsInstance(self.rd.get("g_implied_at_current_price"), (int, float))

    def test_it_is_held_at_the_VERDICT_multiple_not_the_central_one(self):
        """Otherwise the reverse figure answers a question nobody asked: it must say what the price
        embeds under the lens that actually issues the verdict."""
        self.assertEqual(self.rd.get("future_pe_held"),
                         self.r["ivc_base"]["inputs"]["future_pe"])

    def test_the_actual_growth_is_printed_beside_it(self):
        """A required growth with no realised growth beside it is unfalsifiable — the comparison IS
        the deliverable."""
        self.assertIsInstance(self.rd.get("actual_rev_cagr_3y"), (int, float))
        self.assertIsInstance(self.rd.get("actual_rev_cagr_5y"), (int, float))
        self.assertEqual(self.rd["actual_rev_cagr_5y"], self.r["growth_anchor"]["rev_cagr_5y"],
                         "the reverse block must quote the SAME measured series, not recompute it")

    def test_reverse_dcf_decides_nothing_either(self):
        self.assertIs(self.rd.get("advisory_only"), True)


class TestSelfDocumentation(unittest.TestCase):
    """The 'Why these parameters' block: printed by the ASSEMBLER from constants.

    A parameter that explains itself in prose a model composed is a parameter whose rationale drifts
    run to run — and the operator's conservatism complaint ran for two weeks precisely because the
    reasoning behind each layer lived in chat history rather than in the report.
    """

    WF = None

    @classmethod
    def setUpClass(cls):
        import glob
        path = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "workflow",
                                             "consilium_spine_v*.json")))[-1]
        with open(path, encoding="utf-8") as fh:
            wf = json.load(fh)
        cls.NODES = {n["name"]: n for n in wf["nodes"]}
        cls.CODE = cls.NODES["Assemble Report"]["parameters"]["jsCode"]

    def test_the_block_exists_and_is_published(self):
        self.assertIn("WHY_PARAMS", self.CODE)
        self.assertIn("whyBlock", self.CODE)
        self.assertIn("whyBlock, ''", self.CODE, "the block is built but never printed")

    def test_all_five_mandated_decisions_are_present(self):
        for token in ("Entry rung 20%", "P/E ceiling 25", "Fade to 4%",
                      "min(3y, 5y)", "conservative lens"):
            self.assertIn(token, self.CODE, "missing mandated line: %s" % token)

    def test_every_line_carries_a_DATE(self):
        """Without a date a reader cannot tell a ratified decision from an accumulated habit."""
        block = self.CODE[self.CODE.index("WHY_PARAMS = ["):self.CODE.index("const whyBlock")]
        entries = re.findall(r"\['([^']+)',\s*\n?\s*'([^']*)'", block)
        self.assertGreaterEqual(len(entries), 5, "parsed %d entries" % len(entries))
        undated = [name for name, text in entries
                   if not re.search(r"\d{2}\.\d{2}\.\d{4}|Graham-Dodd|architect mandate|asymmetric|endpoints",
                                    text)]
        self.assertEqual(undated, [], "lines without a date or a named authority: %s" % undated)

    def test_the_rationale_is_NOT_written_by_a_model(self):
        """It must be a constant in the assembler, not a field lifted from any LLM node."""
        block = self.CODE[self.CODE.index("WHY_PARAMS = ["):self.CODE.index("const whyBlock")]
        for forbidden in ("safe(", "$(", "memo", "arb"):
            self.assertNotIn(forbidden, block,
                             "the rationale block reads from a model surface: %s" % forbidden)


class TestLensGapDecomposition(unittest.TestCase):
    """v4.2.68 (mandate 1) — the gap is MEASURED, never explained by a constant.

    The brief printed "exactly two decisions: growth and the ceiling" on every name. It was written
    while looking at NFLX, where it was true. On META the ceiling bound NEITHER lens (both 20.69),
    so its contribution was zero, and more than half the gap came from a third difference the
    sentence denied existed: the lens is built on the GAAP base while the verdict leg was FCF.
    An explanation true of one name and printed on all names is a false statement with a plausible
    history — the same shape as the 54-vs-41 catalogue count, one level up.
    """

    def _dec(self, **over):
        d = _data(**over)
        return analyze(d, SPEC).get("central_lens", {}).get("gap_decomposition")

    def test_the_decomposition_exists_and_names_each_factor(self):
        dec = self._dec()
        self.assertIsNotNone(dec, "the gap is published without an attribution")
        for k in ("base_change", "growth_change", "multiple_change", "verdict_iv"):
            self.assertIn(k, dec)

    def test_a_zero_multiple_contribution_is_REPORTED_as_zero(self):
        """The META case. Both lenses on the same multiple must attribute nothing to the ceiling —
        this is the exact claim the old constant sentence got wrong."""
        # medians below the cap => the ceiling binds neither lens
        dec = self._dec(pe_median_5y=20.69, pe_median_10y=23.575)
        self.assertAlmostEqual(dec["multiple_change"], 0.0, places=2,
                               msg="a ceiling that bound nothing was credited with a contribution")
        self.assertFalse(dec["multiple_differs"])

    def test_a_real_multiple_gap_is_reported_as_nonzero(self):
        """Control: without this the pin above is satisfied by always reporting zero."""
        dec = self._dec(pe_median_5y=33.92, pe_median_10y=33.44)   # cap 30 binds the verdict lens
        self.assertGreater(dec["multiple_change"], 0.0)
        self.assertTrue(dec["multiple_differs"])

    def test_the_decomposition_does_NOT_claim_to_sum(self):
        """Table 2 measured a 25% interaction term on MA. A decomposition that claimed the parts
        add up would be lying about the multiplicativity the same table established."""
        dec = self._dec()
        self.assertIn("do not sum", dec["note"])


class TestFixtureFieldsExistInSchema(unittest.TestCase):
    """v4.2.68 (mandate 5) — a pin may not invent the field it checks.

    TWO defects in the 2026-08-03 matrix had this shape: `news_highlights` and `year5_reference`
    were written into fixtures, the pins went green, and neither field existed anywhere in the
    system. The pin proved the RENDERER handles a field; nothing proved the field arrives. A third,
    `required_mos_rung_pct`, was found by this very check — it lives in Parse DI, never in RESULT,
    so the brief silently defaulted the entry rung to 20 on every run.

    This test reads what the renderers ask of `res` and confronts it with what analyze() actually
    returns. Known non-RESULT sources are listed explicitly, with the reason, so the list itself
    documents where each exception comes from — an unnamed exception would defeat the point.
    """

    #: fields legitimately absent from analyze()'s return, each with its real origin
    NOT_FROM_ANALYZE = {
        "_": "regex artifact",
        "_raw": "raw upstream passthrough on the error path",
        "_parse_error": "error path", "error": "error path",
        "fallback_reason": "error path",
        "radar_skeleton": "built by Build Radar, not by analyze",
        "_fp_vectors": "legacy alias; canonical home is RESULT.fp_vectors since v4.2.68",
        "news_highlights": "NOT PRODUCED — honest-absence by mandate 5 until the news source is decided",
        "sentiment_direction": "NOT PRODUCED — same",
        "required_mos_rung_pct": "computed by Parse DI; the brief now reads it from that node",
        "rung_signals": "computed by Parse DI; same",
    }

    def test_every_field_a_renderer_reads_either_exists_or_is_named(self):
        import glob
        import json as _json
        import re as _re
        root = os.path.join(os.path.dirname(__file__), "..")
        path = sorted(glob.glob(os.path.join(root, "workflow", "consilium_spine_v*.json")))[-1]
        with open(path, encoding="utf-8") as fh:
            wf = _json.load(fh)
        reads = set()
        for name in ("Assemble Brief", "Render Tables"):
            code = next(n for n in wf["nodes"] if n["name"] == name)["parameters"]["jsCode"]
            reads |= set(_re.findall(r"res\.([a-z_][a-z0-9_]*)", code))
        with open(os.path.join(root, "microservice", "app.py"), encoding="utf-8") as fh:
            src = fh.read()
        tail = src[src.rfind("    return {"):]
        produced = set(_re.findall(r'"([a-z_][a-z0-9_]*)":', tail[:8000]))
        unexplained = sorted(f for f in reads
                             if f not in produced and f not in self.NOT_FROM_ANALYZE)
        self.assertEqual(unexplained, [],
                         "renderers read fields that nothing produces and nobody declared: %s"
                         % unexplained)

    def test_the_fields_that_the_matrix_caught_are_now_really_produced(self):
        r = analyze(_data(), SPEC)
        self.assertIsInstance(r.get("year5_reference"), (int, float),
                              "year5_reference is still hand-arithmetic, not a pipeline field")
        self.assertIn("fp_vectors", r, "the vector count has no canonical home in RESULT")
