"""
Regression tests for the DETERMINISTIC HARNESS (microservice/app.py :: analyze()).

This is the money-critical core: it turns Stage2a's JSON judgment-spec into the RESULT that
every downstream node (Render Tables, gate, auditor, arbiter) treats as numeric truth. Every
test here encodes a bug that ACTUALLY happened on a live ticker run — the test exists so the
bug cannot come back silently.

Design note: analyze() is a pure function (data, spec) -> dict. It needs no network and no
yfinance, so these tests run in <1s and cost nothing. Run them after ANY change to app.py or
ivc_lib.py.
"""
import os
import re
import unittest

from _support import load_microservice_module

app = load_microservice_module("app")
analyze = app.analyze


# --- Fixtures -------------------------------------------------------------------------------
# A mature, profitable, well-covered name (MA-like): every anchor present, no nulls.
def mature_data():
    return {
        "price_data": {"current_price": {"adjClose": 480}},
        "eps0_reported": 12.0,
        "levered_fcf_per_share": 13.0,
        "dilution_cagr": -0.02,
        "pe_hist_median": 32,
        "pe_median_5y": 30.0,
        "pe_median_10y": 28.0,
        "peer_median_pe": 30,
        "div_yield": 0.006,
        "revenue": [{"end": "2020-12-31", "val": 100}, {"end": "2025-12-31", "val": 170}],
        "eps_cagr_5y": 0.21,
        "peg": 1.48,
        "debt_to_equity": 2.45,
        "sbc_to_revenue": 0.018,
        "erb_90d": 0.028,
        "rel_strength_6m": -0.16,
        "roe": 1.93,
        "op_margin_series": [0.27, 0.44, 0.49, 0.40, 0.41],
        "fcf_conversion": 0.95,
    }


def mature_spec():
    return {
        "assumptions": {"growth_rate": 0.11, "future_pe": 28, "hurdle": 0.12,
                        "dividend_yield": 0.006, "dividend_growth": 0.11},
        "scenarios": {
            "bear": {"weight": 0.30, "overrides": {"growth_rate": 0.07, "future_pe": 22}},
            "base": {"weight": 0.45, "overrides": {}},
            "bull": {"weight": 0.25, "overrides": {"growth_rate": 0.15, "future_pe": 34}},
        },
        "bull_bear_args": [
            {"side": "BULL", "label": "margin expansion", "probability": 0.3,
             "overrides": {"growth_rate": 0.15}},
            {"side": "BEAR", "label": "multiple compression", "probability": 0.4,
             "overrides": {"future_pe": 20}},
        ],
        "qualitative_scores": {
            "E_moat": {"points": 12, "evidence": "duopoly, 5y share stable"},
            "A_runway": {"points": 3, "evidence": "TAM headroom"},
            "F_forecast_trend": {"points": 4, "evidence": "ERB +2.8%"},
            "G_capalloc": {"points": 4, "evidence": "buyback 68% of FCF"},
            "H_sentiment": {"points": 1, "evidence": "short 1% float"},
        },
    }


class TestHarnessHappyPath(unittest.TestCase):
    """The normal case must keep producing a complete, self-consistent RESULT."""

    def setUp(self):
        self.r = analyze(mature_data(), mature_spec())

    def test_no_error_and_marked_as_harness(self):
        self.assertNotIn("error", self.r)
        self.assertTrue(self.r["_harness"])
        self.assertFalse(self.r["_FALLBACK"])

    def test_result_contract_keys_present(self):
        """Render Tables reads res.* directly — these keys are a hard contract with it."""
        for k in ["ivc_base", "scenarios", "pwfv", "weights", "bull_bear", "sensitivity",
                  "gps", "mos_ladder", "gates", "verdict_cap", "self_tests_all", "flags"]:
            self.assertIn(k, self.r, "RESULT contract key missing: %s" % k)

    def test_gps_has_exactly_ten_blocks_no_duplicates(self):
        """v2.4 regression: wiring emitted gps_quant twice ('блок A' AND 'quant_A_quant'),
        so visibleSum double-counted quant and inflated GPS. The harness builds the block
        list itself, so a duplicate is structurally impossible — assert that stays true."""
        blocks = self.r["gps"]["blocks"]
        self.assertEqual(len(blocks), 10)
        names = [b["name"] for b in blocks]
        self.assertEqual(len(names), len(set(names)), "duplicate GPS block: %s" % names)

    def test_gps_total_equals_sum_of_blocks(self):
        """v2.3 regression: GPS_TOTAL_MISMATCH sent healthy names (FOUR/PLTR/AMZN) to REWORK
        because the wiring's declared total disagreed with the visible blocks. The total is
        now BY CONSTRUCTION the sum — auditable, never mismatched."""
        blocks = self.r["gps"]["blocks"]
        self.assertAlmostEqual(self.r["gps"]["total"], round(sum(b["points"] for b in blocks), 1), places=1)

    def test_quant_blocks_come_from_gps_quant_not_the_llm(self):
        """The LLM must not be able to score the deterministic blocks. Changing only the
        qualitative_scores must leave the quant blocks byte-identical."""
        spec2 = mature_spec()
        spec2["qualitative_scores"]["E_moat"]["points"] = 0
        r2 = analyze(mature_data(), spec2)
        quant_names = ["A (growth)", "B (profitability)", "C (valuation)",
                       "D (balance sheet)", "F (momentum)"]
        for name in quant_names:
            a = next(b for b in self.r["gps"]["blocks"] if b["name"] == name)
            b = next(x for x in r2["gps"]["blocks"] if x["name"] == name)
            self.assertEqual(a["points"], b["points"],
                             "quant block %s moved when only a qualitative score changed" % name)

    def test_all_three_scenarios_computed(self):
        for k in ("bear", "base", "bull"):
            self.assertIn(k, self.r["scenarios"])
            self.assertIsNotNone(self.r["scenarios"][k]["result"].get("intrinsic_value"))

    def test_pwfv_is_probability_weighted_not_average(self):
        s = self.r["scenarios"]
        expected = sum(s[k]["weight"] * s[k]["result"]["intrinsic_value"] for k in s)
        self.assertAlmostEqual(self.r["pwfv"], round(expected, 2), places=1)


class TestHarnessNullSpec(unittest.TestCase):
    """v2.9 regression — THE crash that emptied PLTR's whole numeric layer.

    dict.get(k, default) does NOT substitute the default when the key EXISTS with value None.
    Stage2a legitimately emits nulls (PLTR pays no dividend -> "dividend_growth": null), those
    reached ivc_lib and raised 'unsupported operand type(s) for +: int and NoneType'.
    The harness must sanitize the spec at the boundary — it can never trust the LLM's shape.
    """

    def pltr_data(self):
        return {
            "price_data": {"current_price": {"adjClose": 170}},
            "eps0_reported": 0.65,
            "levered_fcf_per_share": 0.8,
            "dilution_cagr": None,          # explicit null from upstream
            "pe_hist_median": None,
            "peer_median_pe": None,
            "pe_sector_median": None,
            "revenue": [{"end": "2021-12-31", "val": 1541}, {"end": "2025-12-31", "val": 4200}],
            "roe": 0.11,
            "op_margin_series": [-0.3, 0.05, 0.31],
            "fcf_conversion": 1.1,
            "debt_to_equity": 0.05,
            "sbc_to_revenue": 0.19,
            "erb_90d": 0.1,
            "rel_strength_6m": 0.2,
            "eps_cagr_5y": None,
            "peg": None,
        }

    def pltr_spec(self):
        return {
            "assumptions": {
                "growth_rate": 0.30, "future_pe": 45, "hurdle": 0.12,
                "dividend_yield": None,     # non-dividend payer
                "dividend_growth": None,    # <-- the exact crash trigger
                "discount_rate": None, "terminal_growth": None, "years": None,
            },
            "scenarios": {
                "bear": {"weight": 0.35, "overrides": {"growth_rate": 0.18, "future_pe": None}},
                "base": {"weight": 0.40, "overrides": {}},
                "bull": {"weight": 0.25, "overrides": {"growth_rate": 0.40, "future_pe": 60}},
            },
            "bull_bear_args": [
                {"side": "BULL", "label": "AIP re-acceleration", "probability": None,
                 "overrides": {"growth_rate": 0.40}},
                {"side": "BEAR", "label": "multiple compression", "probability": 0.4,
                 "overrides": {"future_pe": None}},
            ],
            "qualitative_scores": {"E_moat": {"points": None, "evidence": "x"},
                                   "A_runway": {"points": 4}},
        }

    def test_explicit_nulls_do_not_crash(self):
        r = analyze(self.pltr_data(), self.pltr_spec())
        self.assertNotIn("error", r, "harness crashed on a null-bearing spec: %s" % r.get("error"))
        self.assertIsNotNone(r["ivc_base"].get("intrinsic_value"))

    def test_null_qualitative_points_score_zero_not_crash(self):
        r = analyze(self.pltr_data(), self.pltr_spec())
        moat = next(b for b in r["gps"]["blocks"] if b["name"] == "E_moat")
        self.assertEqual(moat["points"], 0)

    def test_null_override_falls_back_to_base_assumption(self):
        """_clean_ov drops null overrides so the BASE value survives, rather than poisoning
        the scenario with None."""
        r = analyze(self.pltr_data(), self.pltr_spec())
        self.assertIsNotNone(r["scenarios"]["bear"]["result"].get("intrinsic_value"))

    def test_null_probability_does_not_crash_bull_bear(self):
        r = analyze(self.pltr_data(), self.pltr_spec())
        self.assertEqual(len(r["bull_bear"]["rows"]), 2)


class TestHarnessPeCap(unittest.TestCase):
    """v2.6 regression: pe_cap_unjustified sent PLTR to REWORK because no PE anchor existed
    and the gate demanded named comps. The cap is now enforced deterministically here, so a
    no-anchor name gets a CONSERVATIVE VERDICT instead of a REWORK."""

    def no_anchor_data(self):
        d = mature_data()
        d["pe_hist_median"] = None
        d["peer_median_pe"] = None
        d["pe_sector_median"] = None
        return d

    def test_no_anchor_caps_future_pe_at_conservative_constant(self):
        spec = mature_spec()
        spec["assumptions"]["future_pe"] = 45
        r = analyze(self.no_anchor_data(), spec)
        self.assertFalse(r["pe_cap"]["anchors_available"])
        self.assertEqual(r["pe_cap"]["anchor_used"], 20.0)
        self.assertTrue(any("no PE anchor" in f for f in r["pe_cap"]["flags"]))

    def test_no_anchor_still_produces_a_verdict_not_a_failure(self):
        """The whole point: conservative answer beats no answer."""
        spec = mature_spec()
        spec["assumptions"]["future_pe"] = 45
        r = analyze(self.no_anchor_data(), spec)
        self.assertNotIn("error", r)
        self.assertIn(r["verdict_cap"], ("AVOID", "WATCH+"))

    def test_absurd_llm_future_pe_is_ignored_base_is_anchored(self):
        """v4.2.30 final: the base leg no longer routes the LLM future_pe through the 1.2x cap —
        it is ANCHORED to min(pe_median_5y, pe_median_10y, 25) and ignores the LLM entirely. An
        absurd LLM 99 must not reach the base; base uses the anchor (min(30,28,25)=25) and the
        divergence is flagged. (The 1.2x pe_cap now governs bull/bear scenario overrides only.)"""
        spec = mature_spec()
        spec["assumptions"]["future_pe"] = 99   # absurd LLM base -> must be ignored by the anchor
        r = analyze(mature_data(), spec)
        # v4.2.65: ceiling 25 -> 30 (architect mandate 03.08.2026). Expectations moved with
        # the formula in the same commit; the ratio itself is pinned in test_two_lens.
        # v4.2.65: this fixture's own medians are 28/32, so after the ceiling moved to 30 the
        # FIRM'S median binds instead of the absolute cap — min(28, 32, 30) = 28. That is the
        # personalisation working, and it makes the pin STRONGER: it now proves the anchor comes
        # from the company's history rather than from a constant that happens to match.
        self.assertEqual(r["pe_anchor"]["base_future_pe_used"], 28.0,
                         "base must be the window anchor, not the LLM's 99")
        self.assertTrue(any("pe_divergence" in f for f in r["pe_anchor"]["flags"]),
                        "the 99-vs-25 divergence must be flagged")

    def test_reasonable_pe_is_not_clamped(self):
        spec = mature_spec()
        spec["assumptions"]["future_pe"] = 28   # below the 38.4 cap
        r = analyze(mature_data(), spec)
        self.assertEqual(r["pe_cap"]["flags"], [])

    def test_cap_also_applies_to_scenario_overrides(self):
        """A bull scenario must not smuggle an uncapped multiple past the base-case cap."""
        spec = mature_spec()
        spec["scenarios"]["bull"]["overrides"]["future_pe"] = 99
        r = analyze(mature_data(), spec)
        self.assertTrue(any("capped" in f for f in r["pe_cap"]["flags"]))


class TestHarnessHonestFailure(unittest.TestCase):
    """When a required driver is missing, the harness must return an HONEST error rather than
    invent a default. A fabricated growth_rate is exactly the hallucination this whole
    architecture exists to prevent."""

    def test_missing_growth_rate_returns_error_not_a_guess(self):
        spec = mature_spec()
        spec["assumptions"]["growth_rate"] = None
        r = analyze(mature_data(), spec)
        self.assertIn("error", r)
        self.assertEqual(r["verdict_cap"], "AVOID", "an unusable run must fail CONSERVATIVE")

    def test_missing_future_pe_is_anchored_not_an_error(self):
        """v4.2.30 final mandate: base future_pe is anchored to min(pe_median_5y, pe_median_10y, PE_ABS_CAP=30).
        A missing LLM future_pe is never an error — the anchor (or the fixed default) supplies it.
        mature_data carries window medians -> a valid anchored run."""
        spec = mature_spec()
        spec["assumptions"]["future_pe"] = None
        d = mature_data()
        d["pe_median_5y"] = 30.0
        d["pe_median_10y"] = 28.0
        r = analyze(d, spec)
        self.assertNotIn("error", r, "a missing LLM future_pe must be filled by the window anchor")
        self.assertEqual(r["pe_anchor"]["base_future_pe_used"], 28.0)  # min(30,28,30)=28 — the
        # firm's OWN median now binds, which is the point of the personalisation.

    def test_missing_future_pe_AND_no_history_uses_default_18(self):
        """v4.2.30 final mandate CHANGED the no-history path: with neither window median present,
        base future_pe is the fixed long-run default 18 (with a loud flag) — NOT an honest error.
        The honest-error path no longer applies to future_pe (it was replaced by the default)."""
        spec = mature_spec()
        spec["assumptions"]["future_pe"] = None
        d = mature_data()
        d["pe_median_5y"] = None
        d["pe_median_10y"] = None
        r = analyze(d, spec)
        self.assertNotIn("error", r, "no history now yields the default, not an error")
        self.assertEqual(r["pe_anchor"]["base_future_pe_used"], 18.0)
        self.assertTrue(any("DEFAULT" in f and "insufficient history" in f
                            for f in r["pe_anchor"]["flags"]))


class TestHarnessVerdictCap(unittest.TestCase):
    """verdict_cap must be COMPUTED from the hurdle floor, never declared by an LLM.
    Root of the old gate_override REWORK.

    v3.3 regression: the harness collapsed the mandate's THREE bands into two, so BUY was
    structurally UNREACHABLE — no name could pass however good the numbers were. The bands
    mirror the stage4 gate rule (check #3) and must stay in sync with it.

    The fixture is the real ADBE run of 2026-07-15 (price $220.78, eps0 $16.69, de-rated to
    13.2x earnings / 8.9x FCF, buybacks shrinking the count 2.5%/yr). Its three scenarios
    reproduce the shipped report exactly — 8.76% / 15.20% / 22.32% — so these tests are pinned
    to real output, not to invented numbers.
    """

    def adbe_data(self):
        return {
            "price_data": {"current_price": {"adjClose": 220.78}},
            "eps0_reported": 16.69,
            "levered_fcf_per_share": 24.78,
            "dilution_cagr": -0.025,
            "pe_hist_median": 41.50,
            "peer_median_pe": None,
            "pe_sector_median": None,
            "div_yield": 0.0,
            "revenue": [{"end": "2020-11-27", "val": 100}, {"end": "2025-11-28", "val": 170}],
            "eps_cagr_5y": 0.09,
            "debt_to_equity": 0.24,
            "sbc_to_revenue": 0.082,
            "rel_strength_6m": -0.428,
            "roe": 0.613,
            "op_margin_series": [0.33, 0.37, 0.35, 0.34, 0.31, 0.37],
            "fcf_conversion": 1.382,
        }

    def run_case(self, growth, pe):
        spec = {"assumptions": {"growth_rate": growth, "future_pe": pe, "hurdle": 0.12},
                "qualitative_scores": {}}
        return analyze(self.adbe_data(), spec)

    def test_below_hurdle_floor_caps_at_avoid(self):
        """ADBE's real BEAR scenario: g=6%, PE=14 -> 8.76%."""
        r = self.run_case(0.06, 14)
        self.assertLess(r["ivc_base"]["implied_cagr_pct"], 12.0)
        self.assertEqual(r["verdict_cap"], "AVOID")

    def test_clears_floor_but_below_target_caps_at_watch_plus(self):
        """ADBE's real BASE scenario: g=11%, PE=18 -> 15.20%. Meets the 12% floor, sits below
        the 16% target, so WATCH+ is the design-correct cap — this one was NOT the bug."""
        r = self.run_case(0.11, 18)
        icagr = r["ivc_base"]["implied_cagr_pct"]
        self.assertTrue(12.0 <= icagr < 16.0, "fixture drifted out of the 12-16 band: %s" % icagr)
        self.assertEqual(r["verdict_cap"], "WATCH+")

    def test_in_target_zone_allows_buy(self):
        """ADBE's real BULL scenario: g=16%, PE=24 -> 22.32%. Before v3.3 this returned WATCH+
        no matter how high the implied CAGR went — this assertion is what catches that."""
        r = self.run_case(0.16, 24)
        self.assertGreaterEqual(r["ivc_base"]["implied_cagr_pct"], 16.0)
        self.assertEqual(r["verdict_cap"], "BUY")

    def test_buy_is_reachable_at_all(self):
        """Guard against any future change that silently makes the mandate unpassable."""
        caps = {self.run_case(g, pe)["verdict_cap"]
                for g, pe in [(0.06, 14), (0.11, 18), (0.16, 24)]}
        self.assertIn("BUY", caps, "no combination of inputs can produce BUY")

    def test_cap_bands_are_monotonic_in_implied_cagr(self):
        """A better implied CAGR must never produce a stricter cap."""
        rank = {"AVOID": 0, "WATCH+": 1, "BUY": 2}
        runs = []
        for g, pe in [(0.02, 10), (0.06, 14), (0.09, 16), (0.11, 18), (0.16, 24)]:
            r = self.run_case(g, pe)
            runs.append((r["ivc_base"]["implied_cagr_pct"], r["verdict_cap"]))
        runs.sort()
        ranks = [rank[cap] for _, cap in runs]
        self.assertEqual(ranks, sorted(ranks), "cap is not monotonic in implied CAGR: %s" % runs)

    def test_cap_is_a_ceiling_not_a_recommendation(self):
        """A BUY cap must never be produced by an unusable run — a missing driver still fails
        conservative regardless of how attractive the other inputs look."""
        spec = {"assumptions": {"growth_rate": None, "future_pe": 24, "hurdle": 0.12}}
        r = analyze(self.adbe_data(), spec)
        self.assertIn("error", r)
        self.assertEqual(r["verdict_cap"], "AVOID")


class TestDualBasis(unittest.TestCase):
    """v3.4: GAAP EPS double-counts SBC (charged in earnings AND diluting the share count).
    The harness prices BOTH legs and drives the verdict cap from the conservative one.

    Fixtures are the real NOW and ADBE runs of 2026-07-15."""

    def now_data(self):
        # SBC-heavy: GAAP $1.67/sh vs FCF $4.44/sh on the same $104.85 price (63x vs 24x).
        return {
            "price_data": {"current_price": {"adjClose": 104.85}},
            "eps0_reported": 1.67, "levered_fcf_per_share": 4.44, "levered_fcf": 4.58e9,
            "shares_current": 1.03e9, "dilution_cagr": 0.0067, "buyback_to_fcf": 0.402,
            "buyback_vs_sbc": 0.94, "pe_hist_median": 123.39, "peer_median_pe": 27.0,
            "revenue": [{"end": "2020-12-31", "val": 100}, {"end": "2025-12-31", "val": 280}],
            "sbc_to_revenue": 0.147, "debt_to_equity": 0.11, "roe": 0.135,
            "op_margin_series": [0.012, 0.044, 0.049, 0.085, 0.124, 0.137],
            "fcf_conversion": 2.618,
        }

    def adbe_data(self):
        # Low SBC, aggressive buybacks (buyback/SBC=5.8x), count SHRINKING 2.5%/yr.
        return {
            "price_data": {"current_price": {"adjClose": 220.78}},
            "eps0_reported": 16.69, "levered_fcf_per_share": 24.78, "levered_fcf": 9.85e9,
            "shares_current": 0.397e9, "dilution_cagr": -0.025, "buyback_to_fcf": 1.145,
            "buyback_vs_sbc": 5.81, "pe_hist_median": 41.50, "sbc_to_revenue": 0.082,
            "debt_to_equity": 0.24,
            "revenue": [{"end": "2020-11-27", "val": 100}, {"end": "2025-11-28", "val": 170}],
            "roe": 0.613, "op_margin_series": [0.33, 0.37, 0.35, 0.34, 0.31, 0.37],
            "fcf_conversion": 1.382,
        }

    def test_sbc_heavy_name_shows_a_large_gap(self):
        """NOW: the FCF leg values the business ~2x the GAAP leg. That gap IS the finding."""
        r = analyze(self.now_data(),
                    {"assumptions": {"growth_rate": 0.17, "future_pe": 27, "hurdle": 0.12},
                     "qualitative_scores": {}})
        db = r["dual_basis"]
        self.assertIsNotNone(db)
        self.assertGreater(db["gap_iv_pct"], 60, "SBC-heavy gap collapsed: %s" % db["gap_iv_pct"])
        self.assertGreater(db["fcf_per_share"]["iv"], db["gaap_eps"]["iv"])

    def test_low_sbc_name_shows_a_small_gap(self):
        """ADBE control: both legs must roughly agree when SBC is modest."""
        r = analyze(self.adbe_data(),
                    {"assumptions": {"growth_rate": 0.11, "future_pe": 18, "hurdle": 0.12},
                     "qualitative_scores": {}})
        db = r["dual_basis"]
        self.assertIsNotNone(db)
        self.assertLess(abs(db["gap_iv_pct"]), 25, "low-SBC gap blew out: %s" % db["gap_iv_pct"])

    def test_capital_return_buybacks_are_not_phantom_dilution(self):
        """THE bug caught during development: adding back ALL buybacks charged ADBE
        (buyback/FCF=114%, buyback/SBC=5.8x, share count SHRINKING) with +13pp phantom gross
        dilution, crushing its FCF leg to a third of the GAAP leg and flipping WATCH+ to AVOID.
        Only the SBC-offsetting portion of buybacks may be added back."""
        r = analyze(self.adbe_data(),
                    {"assumptions": {"growth_rate": 0.11, "future_pe": 18, "hurdle": 0.12},
                     "qualitative_scores": {}})
        gross = r["dual_basis"]["fcf_per_share"]["gross_dilution_used"]
        self.assertLess(gross, 0.02, "phantom dilution is back: gross=%s" % gross)
        self.assertEqual(r["verdict_cap"], "WATCH+",
                         "capital-return buybacks degraded the verdict again")

    def test_verdict_follows_the_conservative_leg(self):
        """NOW: even though the FCF leg is far richer, it still shows 10.7% < 12% hurdle —
        and the cap must come from min(legs), so AVOID."""
        r = analyze(self.now_data(),
                    {"assumptions": {"growth_rate": 0.17, "future_pe": 27, "hurdle": 0.12},
                     "qualitative_scores": {}})
        self.assertEqual(r["dual_basis"]["conservative_leg"], "gaap_eps")
        self.assertEqual(r["verdict_cap"], "AVOID")

    def test_no_fcf_data_degrades_gracefully(self):
        """A name without FCF/share must still produce a normal single-basis RESULT."""
        d = self.adbe_data()
        d["levered_fcf_per_share"] = None
        r = analyze(d, {"assumptions": {"growth_rate": 0.11, "future_pe": 18, "hurdle": 0.12},
                        "qualitative_scores": {}})
        self.assertNotIn("error", r)
        self.assertIsNone(r["dual_basis"])
        self.assertEqual(r["verdict_cap"], "WATCH+")

    def test_gross_dilution_never_below_net(self):
        """Gross dilution (before buybacks) is by definition >= net dilution."""
        r = analyze(self.now_data(),
                    {"assumptions": {"growth_rate": 0.17, "future_pe": 27, "hurdle": 0.12},
                     "qualitative_scores": {}})
        self.assertGreaterEqual(r["dual_basis"]["fcf_per_share"]["gross_dilution_used"], 0.0067)


class TestMarketContext(unittest.TestCase):
    """v3.5: deterministic fear-discount diagnostics. The mandate's recurring setup —
    GOOGL-2024, LLY-Aug-2025, the 2026 hyperscaler capex scare: fundamentals compounding while
    the multiple is compressed by one named fear. These diagnostics INFORM the memo; they must
    never touch verdict_cap (hurdle discipline stays untouched)."""

    def fear_discount_data(self):
        """META-like: multiple 35% below own history, growth barely decelerating, analysts
        revising up into a falling price, capex demonstrably productive."""
        return {
            "price_data": {"current_price": {"adjClose": 580}},
            "eps0_reported": 27.0, "levered_fcf_per_share": 21.0, "levered_fcf": 54e9,
            "shares_current": 2.53e9, "dilution_cagr": -0.01,
            "buyback_to_fcf": 0.6, "buyback_vs_sbc": 2.5,
            "fwd_pe": 16.0, "pe_hist_median": 26.0,
            "eps_cagr_5y": 0.22, "eps_cagr_3y": 0.30,
            "eps_estimates": [{"period": "+1y", "growth": 0.20}],
            "erb_90d": 0.045, "rel_strength_6m": -0.22,
            "operating_income": [{"end": "2023-12-31", "val": 47e9},
                                 {"end": "2024-12-31", "val": 62e9},
                                 {"end": "2025-12-31", "val": 75e9}],
            "capex": [{"end": "2024-12-31", "val": 38e9}, {"end": "2025-12-31", "val": 52e9}],
            "revenue": [{"end": "2020-12-31", "val": 86e9}, {"end": "2025-12-31", "val": 190e9}],
            "sbc_to_revenue": 0.09, "debt_to_equity": 0.3, "roe": 0.35,
            "op_margin_series": [0.38, 0.34, 0.29, 0.35, 0.40, 0.42], "fcf_conversion": 1.1,
        }

    def value_trap_data(self):
        """The INTC-shaped counterexample: multiple compressed just as hard, but growth has
        actually collapsed (negative fwd growth). Must NOT flag as a fear-discount setup —
        distance from ATH without intact fundamentals is a value trap, not a signal."""
        d = self.fear_discount_data()
        d["eps_estimates"] = [{"period": "+1y", "growth": -0.10}]
        d["eps_cagr_3y"] = -0.05
        return d

    def spec(self):
        return {"assumptions": {"growth_rate": 0.14, "future_pe": 22, "hurdle": 0.12},
                "qualitative_scores": {}}

    def test_fear_discount_setup_is_flagged(self):
        r = analyze(self.fear_discount_data(), self.spec())
        mc = r["market_context"]["multiple_compression"]
        self.assertGreaterEqual(mc["multiple_discount_pct"], 25)
        self.assertGreaterEqual(mc["divergence_pp"], 20)
        self.assertTrue(mc["fear_discount_setup"])

    def test_value_trap_is_NOT_flagged(self):
        """Compressed multiple + collapsed growth must not produce the flag."""
        r = analyze(self.value_trap_data(), self.spec())
        mc = r["market_context"]["multiple_compression"]
        self.assertFalse(mc.get("fear_discount_setup"),
                         "value trap flagged as fear discount: %s" % mc)

    def test_revision_vs_price_divergence_detected(self):
        """The LLY-Aug-25 pattern: estimates up, price down."""
        r = analyze(self.fear_discount_data(), self.spec())
        self.assertTrue(r["market_context"]["revision_vs_price"]["divergence"])

    def test_no_divergence_when_price_follows_revisions(self):
        d = self.fear_discount_data()
        d["rel_strength_6m"] = 0.10
        r = analyze(d, self.spec())
        self.assertFalse(r["market_context"]["revision_vs_price"]["divergence"])

    def test_incremental_roic_computed_from_edgar_series(self):
        """(75-47)B new OI on (38+52)B deployed = 31.1%: capex is productive."""
        r = analyze(self.fear_discount_data(), self.spec())
        rq = r["market_context"]["reinvestment_quality"]
        self.assertAlmostEqual(rq["incremental_roic_pct"], 31.1, places=1)

    def test_missing_series_degrades_to_absent_not_crash(self):
        d = self.fear_discount_data()
        d["operating_income"] = None
        d["capex"] = None
        r = analyze(d, self.spec())
        self.assertNotIn("reinvestment_quality", r["market_context"] or {})
        self.assertNotIn("error", r)

    def test_diagnostics_do_not_touch_verdict_cap(self):
        """The flag informs the memo; hurdle discipline must stay untouched. Same valuation
        inputs with and without the fear-discount context must produce the same cap."""
        d1 = self.fear_discount_data()
        r1 = analyze(d1, self.spec())
        d2 = self.fear_discount_data()
        d2["fwd_pe"] = None; d2["pe_hist_median"] = None
        d2["erb_90d"] = None; d2["rel_strength_6m"] = None
        d2["operating_income"] = None; d2["capex"] = None
        r2 = analyze(d2, self.spec())
        self.assertEqual(r1["verdict_cap"], r2["verdict_cap"],
                         "market_context leaked into the verdict cap")


class TestStreetView(unittest.TestCase):
    """v3.6: deterministic sell-side consensus block. Named-bank targets are FACT_PACK
    territory (source+date required); this block carries only what yfinance reports."""

    def data_with_street(self):
        return {
            "price_data": {"current_price": {"adjClose": 580}},
            "eps0_reported": 27.0, "levered_fcf_per_share": 21.0, "levered_fcf": 54e9,
            "shares_current": 2.53e9, "dilution_cagr": -0.01,
            "buyback_to_fcf": 0.6, "buyback_vs_sbc": 2.5,
            "price_target": {"mean": 835.0, "high": 935.0, "low": 640.0},
            "analyst_count": 62, "recommendation_mean": 1.6, "recommendation_key": "buy",
            "analyst_actions_recent": [
                {"date": "2026-07-01", "firm": "BofA Securities", "action": "reit",
                 "to_grade": "Buy", "from_grade": "Buy"}],
            "revenue": [{"end": "2020-12-31", "val": 86e9}, {"end": "2025-12-31", "val": 190e9}],
            "sbc_to_revenue": 0.09, "debt_to_equity": 0.3, "roe": 0.35,
            "op_margin_series": [0.38, 0.40, 0.42], "fcf_conversion": 1.1,
        }

    def spec(self):
        return {"assumptions": {"growth_rate": 0.14, "future_pe": 22, "hurdle": 0.12},
                "qualitative_scores": {}}

    def test_consensus_and_upside_computed(self):
        r = analyze(self.data_with_street(), self.spec())
        sv = r["street_view"]
        self.assertEqual(sv["consensus_target_mean"], 835.0)
        self.assertAlmostEqual(sv["upside_to_target_pct"], 44.0, places=1)
        self.assertEqual(sv["analyst_count"], 62)

    def test_pwfv_vs_street_spread_present(self):
        """The spread the memo must explain when large: where OUR model disagrees with the
        street."""
        r = analyze(self.data_with_street(), self.spec())
        self.assertIsNotNone(r["street_view"]["pwfv_vs_street_pct"])

    def test_named_actions_carried_verbatim(self):
        r = analyze(self.data_with_street(), self.spec())
        acts = r["street_view"]["analyst_actions_recent"]
        self.assertEqual(acts[0]["firm"], "BofA Securities")

    def test_absent_targets_degrade_to_none_not_crash(self):
        d = self.data_with_street()
        d["price_target"] = None
        d["price_target_mean"] = None
        r = analyze(d, self.spec())
        self.assertIsNone(r["street_view"])
        self.assertNotIn("error", r)

    # ---- v4.2.10: analyst count must survive the yahoo field nulling (cloud IPs) ----------
    # NFLX 2026-07-17 shipped analyst_count=null while the SAME payload carried 58 analysts in
    # Finnhub rec_trends. The count existed; only the dead field was read. These tests drive the
    # CONSUMER (analyze output), per the rule that a contract asserted only in prose dies at the
    # caller.

    def _rec_trends(self):
        return {"months": [{"period": "2026-07-01", "strongBuy": 16, "buy": 29,
                            "hold": 13, "sell": 0, "strongSell": 0}],
                "buy_share_latest": 0.776, "_source": "finnhub /stock/recommendation"}

    def test_analyst_count_falls_back_to_rec_trends_sum(self):
        d = self.data_with_street()
        d["analyst_count"] = None            # yahoo nulls on cloud — the live-run shape
        d["rec_trends"] = self._rec_trends()
        r = analyze(d, self.spec())
        sv = r["street_view"]
        self.assertEqual(sv["analyst_count"], 58)
        self.assertIn("finnhub", sv["analyst_count_basis"])

    def test_yahoo_count_keeps_priority_when_present(self):
        d = self.data_with_street()          # analyst_count = 62 (yahoo)
        d["rec_trends"] = self._rec_trends()
        r = analyze(d, self.spec())
        sv = r["street_view"]
        self.assertEqual(sv["analyst_count"], 62)
        self.assertEqual(sv["analyst_count_basis"], "yahoo")

    def test_recommendation_breakdown_carried_with_total(self):
        d = self.data_with_street()
        d["rec_trends"] = self._rec_trends()
        r = analyze(d, self.spec())
        rb = r["street_view"]["recommendation_breakdown"]
        self.assertEqual(rb["total"], 58)
        self.assertEqual(rb["strongBuy"], 16)
        self.assertEqual(rb["period"], "2026-07-01")

    def test_no_rec_trends_leaves_breakdown_none_not_zero(self):
        """Unknown is not zero: absent rec_trends must yield None, never a zero-count."""
        d = self.data_with_street()
        d["analyst_count"] = None
        r = analyze(d, self.spec())
        sv = r["street_view"]
        self.assertIsNone(sv["analyst_count"])
        self.assertIsNone(sv["recommendation_breakdown"])

    def test_empty_bucket_months_do_not_invent_a_count(self):
        """All-null buckets sum to 0 -> total None, count stays None (zero is not unknown,
        and unknown is not zero — both directions)."""
        d = self.data_with_street()
        d["analyst_count"] = None
        d["rec_trends"] = {"months": [{"period": "2026-07-01", "strongBuy": None, "buy": None,
                                       "hold": None, "sell": None, "strongSell": None}]}
        r = analyze(d, self.spec())
        sv = r["street_view"]
        self.assertIsNone(sv["analyst_count"])
        self.assertIsNone(sv["recommendation_breakdown"]["total"])


class TestMarketContextValidity(unittest.TestCase):
    """v3.8: the diagnostics must stay SILENT rather than emit a confident artifact.

    Both bugs were found on the live ADBE run of 2026-07-15 — the run that produced the
    pipeline's first BUY, which is exactly when a spurious supporting signal is most dangerous.
    """

    def adbe_no_estimates(self):
        """Yahoo returned nothing for ADBE: no forward estimates, no fwd_pe. Asset-light capex."""
        return {
            "price_data": {"current_price": {"adjClose": 220.78}},
            "eps0_reported": 16.70, "levered_fcf_per_share": 24.78, "levered_fcf": 9.85e9,
            "shares_current": 0.397e9, "dilution_cagr": -0.025, "buyback_to_fcf": 1.145,
            "buyback_vs_sbc": 5.81, "pe_hist_median": 41.50,
            "fwd_pe": None, "eps_estimates": None,
            "eps_cagr_3y": 0.182, "eps_cagr_5y": 0.09,       # 3y window sits INSIDE the 5y window
            "sbc_to_revenue": 0.082, "debt_to_equity": 0.24,
            "revenue": [{"end": "2023-12-01", "val": 19.4e9}, {"end": "2024-11-29", "val": 21.5e9},
                        {"end": "2025-11-28", "val": 23.4e9}],
            "operating_income": [{"end": "2023-12-01", "val": 6.1e9},
                                 {"end": "2024-11-29", "val": 7.0e9},
                                 {"end": "2025-11-28", "val": 8.16e9}],
            "capex": [{"end": "2024-11-29", "val": 0.17e9}, {"end": "2025-11-28", "val": 0.19e9}],
            "roe": 0.613, "op_margin_series": [0.33, 0.37, 0.35, 0.34, 0.31, 0.37],
            "fcf_conversion": 1.382,
        }

    def spec(self):
        return {"assumptions": {"growth_rate": 0.11, "future_pe": 18, "hurdle": 0.12},
                "qualitative_scores": {}}

    def test_no_forward_estimate_makes_no_divergence_claim(self):
        """The exact ADBE artifact: trailing-3y vs trailing-5y produced decel -101.9% and a
        169.5pp 'divergence'. With no forward estimate the metric must not be computed at all."""
        r = analyze(self.adbe_no_estimates(), self.spec())
        mc = r["market_context"]["multiple_compression"]
        self.assertFalse(mc["divergence_available"])
        self.assertNotIn("divergence_pp", mc)
        self.assertIn("_why_no_divergence", mc)

    def test_no_forward_estimate_raises_no_fear_flag(self):
        r = analyze(self.adbe_no_estimates(), self.spec())
        self.assertFalse(r["market_context"]["multiple_compression"]["fear_discount_setup"],
                         "FEAR-DISCOUNT flag fired without a forward estimate")

    def test_multiple_discount_still_reported_with_its_basis(self):
        """Silence about divergence, not about everything: the discount is still an observation,
        but the reader must be told the P/E is trailing, not forward."""
        r = analyze(self.adbe_no_estimates(), self.spec())
        mc = r["market_context"]["multiple_compression"]
        self.assertGreater(mc["multiple_discount_pct"], 60)
        self.assertIn("trailing", mc["_pe_basis"])

    def test_asset_light_incremental_roic_is_not_meaningful(self):
        """ADBE reported 568% incremental ROIC off $0.36B of 2y capex (0.8% of revenue) —
        arithmetic noise dressed as a finding."""
        r = analyze(self.adbe_no_estimates(), self.spec())
        rq = r["market_context"]["reinvestment_quality"]
        self.assertTrue(rq["not_meaningful"])
        self.assertNotIn("incremental_roic_pct", rq)

    def test_capex_heavy_name_still_gets_incremental_roic(self):
        """MSFT control: capex 23% of revenue -> the metric IS meaningful and must survive."""
        d = self.adbe_no_estimates()
        d["capex"] = [{"end": "2024-06-30", "val": 44.5e9}, {"end": "2025-06-30", "val": 64.6e9}]
        d["operating_income"] = [{"end": "2023-06-30", "val": 88.5e9},
                                 {"end": "2024-06-30", "val": 109.4e9},
                                 {"end": "2025-06-30", "val": 128.5e9}]
        d["revenue"] = [{"end": "2023-06-30", "val": 211e9}, {"end": "2024-06-30", "val": 245e9},
                        {"end": "2025-06-30", "val": 281e9}]
        r = analyze(d, self.spec())
        rq = r["market_context"]["reinvestment_quality"]
        self.assertNotIn("not_meaningful", rq)
        self.assertAlmostEqual(rq["incremental_roic_pct"], 36.7, places=1)
        self.assertAlmostEqual(rq["capex_intensity_pct"], 23.0, places=1)

    def test_real_forward_estimate_still_produces_the_flag(self):
        """MSFT control: the fix must not silence the legitimate signal."""
        d = self.adbe_no_estimates()
        d["eps_estimates"] = [{"period": "+1y", "growth": 0.151}]
        d["eps_cagr_5y"] = 0.188
        d["fwd_pe"] = 20.4
        d["pe_hist_median"] = 34.4
        r = analyze(d, self.spec())
        mc = r["market_context"]["multiple_compression"]
        self.assertTrue(mc["divergence_available"])
        self.assertTrue(mc["fear_discount_setup"])
        self.assertNotIn("_pe_basis", mc)   # real forward P/E -> no basis warning


class TestBaseGrowthAnchoring(unittest.TestCase):
    """v4.2.28 (BACKLOG P). The base scenario's growth_rate is now anchored to a deterministic
    figure — min(rev_cagr_3y, rev_cagr_5y), capped 20% — instead of the LLM's number, which used
    to make IV/PWFV/implied_cagr/MoS float ~6% across runs on identical facts. Mandate pins:
      - min() takes the more conservative of the two revenue horizons,
      - a 20% absolute ceiling,
      - the LLM number is recorded (llm_base_g) and flagged (growth_divergence) but does NOT steer,
      - negative controls on BOTH sides: LLM above the anchor is not rewarded, LLM below is not
        obeyed either — the anchor wins regardless.
    """

    def _data(self, rev_points):
        return {
            "price_data": {"current_price": {"adjClose": 480}},
            "eps0_reported": 12.0, "levered_fcf_per_share": 13.0, "dilution_cagr": 0.0,
            "pe_hist_median": 32, "peer_median_pe": 30, "div_yield": 0.0,
            "revenue": rev_points, "eps_cagr_5y": 0.21, "peg": 1.48,
            "debt_to_equity": 1.0, "sbc_to_revenue": 0.018, "erb_90d": 0.028,
            "rel_strength_6m": -0.16, "roe": 1.0, "op_margin_series": [0.27, 0.44, 0.49, 0.40, 0.41],
            "fcf_conversion": 0.95,
        }

    def _spec(self, llm_g):
        return {"assumptions": {"growth_rate": llm_g, "future_pe": 28, "hurdle": 0.12,
                                "discount_rate": 0.12, "terminal_growth": 0.04},
                "scenarios": {"bear": {"weight": 0.30, "overrides": {"growth_rate": 0.07}},
                              "base": {"weight": 0.45, "overrides": {}},
                              "bull": {"weight": 0.25, "overrides": {"growth_rate": 0.20}}},
                "qualitative": {}}

    # 6 yearly points -> rev_cagr_5y and rev_cagr_3y are both well-defined and DIFFERENT.
    # vals: 100 ... last. 3y window vs 5y window give different CAGRs so min() is testable.
    REV_DECEL = [{"end": "2020-12-31", "val": 100}, {"end": "2021-12-31", "val": 118},
                 {"end": "2022-12-31", "val": 139}, {"end": "2023-12-31", "val": 164},
                 {"end": "2024-12-31", "val": 176}, {"end": "2025-12-31", "val": 188}]
    # 5y CAGR (100->188)=13.5%, 3y CAGR (139->188)=11.4% -> min = 3y = 11.4%

    def test_base_growth_is_the_anchor_not_the_llm_number(self):
        r = analyze(self._data(self.REV_DECEL), self._spec(llm_g=0.30))
        ga = r["growth_anchor"]
        # anchor must be min of the two horizons, NOT the LLM's 30%
        self.assertAlmostEqual(ga["base_growth_used"], min(ga["rev_cagr_3y"], ga["rev_cagr_5y"]), places=6)
        self.assertLess(ga["base_growth_used"], 0.30, "the LLM's 30% must not have steered the base")
        self.assertEqual(ga["llm_base_g"], 0.30, "the LLM number must still be recorded")

    def test_min_takes_the_conservative_horizon(self):
        r = analyze(self._data(self.REV_DECEL), self._spec(llm_g=0.12))
        ga = r["growth_anchor"]
        self.assertEqual(ga["base_growth_used"], min(ga["rev_cagr_3y"], ga["rev_cagr_5y"]))
        # this series decelerates, so 3y < 5y and min must pick 3y
        self.assertLessEqual(ga["base_growth_used"], ga["rev_cagr_5y"] + 1e-9)

    def test_twenty_percent_cap_is_enforced(self):
        # a hyper-growth series: 5y and 3y CAGR both well above 20%
        rev = [{"end": "2020-12-31", "val": 100}, {"end": "2021-12-31", "val": 160},
               {"end": "2022-12-31", "val": 260}, {"end": "2023-12-31", "val": 410},
               {"end": "2024-12-31", "val": 650}, {"end": "2025-12-31", "val": 1000}]
        r = analyze(self._data(rev), self._spec(llm_g=0.35))
        ga = r["growth_anchor"]
        self.assertEqual(ga["base_growth_used"], 0.20, "growth above 20% must be capped at 20%")
        self.assertTrue(any("capped" in f for f in ga["flags"]), "the cap must be flagged")

    def test_negative_control_llm_above_anchor_not_rewarded(self):
        """LLM says grow faster than the filed record — must be ignored; anchor wins."""
        r = analyze(self._data(self.REV_DECEL), self._spec(llm_g=0.25))
        ga = r["growth_anchor"]
        self.assertLess(ga["base_growth_used"], 0.25)
        self.assertGreater(ga["llm_base_g"] - ga["base_growth_used"], 0.03)
        self.assertTrue(any("growth_divergence" in f for f in r["flags"]),
                        "a >3pp divergence between LLM and anchor must be flagged")

    def test_negative_control_llm_below_anchor_not_obeyed(self):
        """LLM says grow slower than the filed record — anchor STILL wins (symmetric); the base
        leg follows the deterministic record, not a pessimistic LLM guess either."""
        r = analyze(self._data(self.REV_DECEL), self._spec(llm_g=0.02))
        ga = r["growth_anchor"]
        self.assertEqual(ga["base_growth_used"], min(ga["rev_cagr_3y"], ga["rev_cagr_5y"]))
        self.assertGreater(ga["base_growth_used"], 0.02, "the anchor must override a low LLM guess too")

    def test_small_divergence_not_flagged(self):
        """When the LLM lands within 3pp of the anchor, no divergence flag (avoid noise)."""
        r = analyze(self._data(self.REV_DECEL), self._spec(llm_g=0.114))
        self.assertFalse(any("growth_divergence" in f for f in r["flags"]),
                         "a <=3pp gap should not raise the divergence flag")

    def test_anchor_is_deterministic_across_llm_variation(self):
        """The whole point: identical facts + DIFFERENT llm growth -> identical base_growth_used
        and identical implied_cagr. This is the drift P diagnosed, now closed."""
        r1 = analyze(self._data(self.REV_DECEL), self._spec(llm_g=0.10))
        r2 = analyze(self._data(self.REV_DECEL), self._spec(llm_g=0.28))
        self.assertEqual(r1["growth_anchor"]["base_growth_used"],
                         r2["growth_anchor"]["base_growth_used"],
                         "base growth must not depend on the LLM number")
        self.assertEqual(r1["ivc_base"]["implied_cagr_pct"], r2["ivc_base"]["implied_cagr_pct"],
                         "implied_cagr must be byte-identical once base growth is anchored")


class TestBaseFuturePeAnchoring(unittest.TestCase):
    """v4.2.30 (BACKLOG P, future_pe leg — FINAL mandate). base future_pe = min(pe_median_5y,
    pe_median_10y, 25), NO floor; fixed default 18 with a loud flag when NEITHER window has >=3
    year-points. Mandate pins: min-of-windows logic; the 25 ceiling BITES; the 18 default fires
    with its flag on insufficient history; NO floor (a low median passes through); an LLM value
    above the anchor is not obeyed."""

    def _data(self, m5, m10):
        return {
            "price_data": {"current_price": {"adjClose": 480}},
            "eps0_reported": 12.0, "levered_fcf_per_share": 13.0, "dilution_cagr": 0.0,
            "pe_median_5y": m5, "pe_median_10y": m10, "peer_median_pe": None, "div_yield": 0.0,
            "revenue": [{"end": "2020-12-31", "val": 100}, {"end": "2025-12-31", "val": 180}],
            "eps_cagr_5y": 0.21, "peg": 1.48, "debt_to_equity": 1.0, "sbc_to_revenue": 0.018,
            "erb_90d": 0.028, "rel_strength_6m": -0.16, "roe": 1.0,
            "op_margin_series": [0.27, 0.44, 0.49, 0.40, 0.41], "fcf_conversion": 0.95,
        }

    def _spec(self, llm_pe):
        return {"assumptions": {"growth_rate": 0.12, "future_pe": llm_pe, "hurdle": 0.12,
                                "discount_rate": 0.12, "terminal_growth": 0.04},
                "scenarios": {"bear": {"weight": 0.30, "overrides": {}},
                              "base": {"weight": 0.45, "overrides": {}},
                              "bull": {"weight": 0.25, "overrides": {}}},
                "qualitative": {}}

    def test_ceiling_bites_high_median(self):
        # NFLX-like: both windows above 25 -> capped to 25
        r = analyze(self._data(42.0, 43.0), self._spec(llm_pe=30))
        pa = r["pe_anchor"]
        self.assertEqual(pa["base_future_pe_used"], 30.0, "the 30 ceiling must bite on high medians")
        self.assertTrue(any("capped" in f for f in pa["flags"]), "the cap must be flagged")

    def test_no_floor_low_median_passes_through(self):
        r = analyze(self._data(12.0, 14.0), self._spec(llm_pe=22))
        self.assertEqual(r["pe_anchor"]["base_future_pe_used"], 12.0,
                         "min(12,14) passes through — NO floor")

    def test_min_of_windows(self):
        # min(28, 19) = 19, below cap
        r = analyze(self._data(28.0, 19.0), self._spec(llm_pe=30))
        self.assertEqual(r["pe_anchor"]["base_future_pe_used"], 19.0,
                         "anchor must be the min of the two window medians")

    def test_one_window_missing_uses_the_other(self):
        r = analyze(self._data(22.0, None), self._spec(llm_pe=30))
        self.assertEqual(r["pe_anchor"]["base_future_pe_used"], 22.0,
                         "with only the 5y window present, it is used")

    def test_default_18_fires_with_flag_on_no_history(self):
        r = analyze(self._data(None, None), self._spec(llm_pe=30))
        pa = r["pe_anchor"]
        self.assertEqual(pa["base_future_pe_used"], 18.0,
                         "no window -> fixed default 18")
        self.assertTrue(any("DEFAULT" in f and "insufficient history" in f for f in pa["flags"]),
                        "the default must fire with a loud [PE ANCHOR: DEFAULT] flag")

    def test_llm_above_anchor_not_obeyed(self):
        r = analyze(self._data(42.0, 43.0), self._spec(llm_pe=38))
        pa = r["pe_anchor"]
        self.assertEqual(pa["base_future_pe_used"], 30.0)
        # v4.2.65: with the ceiling at 30 the gap to the LLM's 32 is 2 points, not 7, so the
        # >5-point divergence flag correctly does NOT fire. Raise the LLM number instead of
        # loosening the flag: the property under test is "a wide gap is announced", and the
        # fixture must keep providing a wide gap.
        self.assertEqual(pa["llm_base_pe"], 38, "the LLM number must still be recorded")
        self.assertTrue(any("pe_divergence" in f for f in r["flags"]),
                        "a >5-point gap must be flagged")

    def test_base_future_pe_deterministic_across_llm_variation(self):
        r1 = analyze(self._data(42.0, 43.0), self._spec(llm_pe=23))
        r2 = analyze(self._data(42.0, 43.0), self._spec(llm_pe=24))
        self.assertEqual(r1["pe_anchor"]["base_future_pe_used"], r2["pe_anchor"]["base_future_pe_used"],
                         "base future_pe must not depend on the LLM number (23 vs 24 -> same)")
        self.assertEqual(r1["ivc_base"]["implied_cagr_pct"], r2["ivc_base"]["implied_cagr_pct"],
                         "implied_cagr must be byte-identical once BOTH drivers are anchored")


class TestBaseDeterminismSweep(unittest.TestCase):
    """v4.2.31 (BACKLOG P, base-determinism sweep). All six LLM inputs that fed the base IV are
    pinned deterministically: discount_rate, terminal_growth, years, dividend_yield/growth, fade,
    and scenario weights. Mandate pins: determinism of all, the LLM is never obeyed for any, the
    base IV equals the band-12 (base-weighted) result, and the terminal-growth asymmetry guard."""

    def _spec(self, disc, tg, yrs, weights):
        s = mature_spec()
        s["assumptions"].update({"discount_rate": disc, "terminal_growth": tg, "years": yrs})
        s["scenarios"] = {"bear": {"weight": weights[0], "overrides": {}},
                          "base": {"weight": weights[1], "overrides": {}},
                          "bull": {"weight": weights[2], "overrides": {}}}
        return s

    def test_all_base_inputs_deterministic_across_llm_variation(self):
        r1 = analyze(mature_data(), self._spec(0.11, 0.05, 8, (0.35, 0.40, 0.25)))
        r2 = analyze(mature_data(), self._spec(0.13, 0.03, 12, (0.20, 0.55, 0.25)))
        self.assertEqual(r1["ivc_base"]["intrinsic_value"], r2["ivc_base"]["intrinsic_value"],
                         "base IV must be byte-identical despite different LLM base inputs")
        self.assertEqual(r1["pwfv"], r2["pwfv"],
                         "pwfv must be byte-identical (weights fixed by convention)")

    def test_discount_rate_is_hurdle_not_llm(self):
        r = analyze(mature_data(), self._spec(0.30, 0.04, 10, (0.25, 0.50, 0.25)))
        bd = r["base_determinism"]
        self.assertEqual(bd["discount_rate_used"], 0.12, "disc must be hurdle 12%, not the LLM 30%")
        self.assertEqual(bd["llm_disc"], 0.30, "the LLM disc must be recorded")
        self.assertTrue(any("disc_divergence" in f for f in r["flags"]),
                        ">1pp disc divergence must be flagged")

    def test_years_fixed_at_10(self):
        r = analyze(mature_data(), self._spec(0.12, 0.04, 7, (0.25, 0.50, 0.25)))
        self.assertEqual(r["base_determinism"]["years_used"], 10, "years must be the structural 10")

    def test_weights_fixed_by_convention_not_llm(self):
        r = analyze(mature_data(), self._spec(0.12, 0.04, 10, (0.10, 0.10, 0.80)))
        w = r["base_determinism"]["scenario_weights_used"]
        self.assertEqual(w, {"bear": 0.25, "base": 0.50, "bull": 0.25},
                         "weights must be the fixed convention, not the LLM's 10/10/80")
        self.assertEqual(r["base_determinism"]["llm_weights"],
                         {"bear": 0.10, "base": 0.10, "bull": 0.80}, "LLM weights must be recorded")

    def test_fade_always_on(self):
        s = mature_spec()
        s["assumptions"]["fade"] = False   # LLM tries to disable fade
        s["assumptions"]["discount_rate"] = 0.12
        r = analyze(mature_data(), s)
        self.assertTrue(r["base_determinism"]["fade_used"], "fade must be forced on regardless of LLM")

    def test_terminal_growth_asymmetry_low_grower_tail_not_lifted(self):
        """NEGATIVE CONTROL (mandate): a sub-4% grower must NOT have its terminal lifted to 4%.
        Effective terminal = min(0.04, base_g)."""
        d = mature_data()
        # force a low anchored base_g via a low-growth revenue series
        d["revenue"] = [{"end": "2020-12-31", "val": 100}, {"end": "2021-12-31", "val": 101},
                        {"end": "2022-12-31", "val": 102}, {"end": "2023-12-31", "val": 103},
                        {"end": "2024-12-31", "val": 104}, {"end": "2025-12-31", "val": 105}]
        s = mature_spec()
        s["assumptions"]["discount_rate"] = 0.12
        r = analyze(d, s)
        bg = r["growth_anchor"]["base_growth_used"]
        tg = r["base_determinism"]["terminal_growth_used"]
        self.assertLess(bg, 0.04, "this series must anchor below 4%")
        self.assertEqual(tg, bg, "effective terminal must be min(0.04, base_g)=base_g, NOT lifted to 0.04")

    def test_terminal_growth_normal_grower_uses_004(self):
        r = analyze(mature_data(), self._spec(0.12, 0.04, 10, (0.25, 0.50, 0.25)))
        # mature_data grows >4%, so terminal stays at the 0.04 cap
        self.assertEqual(r["base_determinism"]["terminal_growth_used"], 0.04)


class TestDataIntegrityGates(unittest.TestCase):
    """v4.2.32 mandates (a) and (b), the parts that live in the Python layer. Absurdity checks are
    NEVER trusted to prose — only to deterministic code. MA 2026-07-22 shipped a 595.8% inter-leg
    gap that the memo rationalised as an 'asset-light structural difference'."""

    def test_huge_inter_leg_gap_marks_fcf_leg_unreliable(self):
        d = mature_data()
        # force a wildly inflated FCF/share, as a wrong share denominator would
        d["levered_fcf_per_share"] = 140.0
        s = mature_spec()
        s["assumptions"]["discount_rate"] = 0.12
        r = analyze(d, s)
        db = r.get("dual_basis") or {}
        self.assertIsNotNone(db.get("gap_iv_pct"))
        self.assertGreater(abs(db["gap_iv_pct"]), 100.0, "this fixture must produce a >100% gap")
        self.assertTrue(db.get("fcf_leg_unreliable"),
                        "a >100% inter-leg gap must mark the FCF leg unreliable")
        self.assertTrue(any("[DATA]" in f and "gap_iv_pct" in f for f in r["flags"]),
                        "the gap must raise a DATA-class hard flag")

    def test_normal_gap_does_not_trip_the_flag(self):
        r = analyze(mature_data(), mature_spec())
        db = r.get("dual_basis") or {}
        if db.get("gap_iv_pct") is not None and abs(db["gap_iv_pct"]) <= 100.0:
            self.assertFalse(db.get("fcf_leg_unreliable"),
                             "a normal gap must not mark the leg unreliable")

    def test_debt_uncertain_forbids_full_marks_on_leverage(self):
        """mandate (b.3): a disputed debt reading must not buy the top leverage sub-score.
        MA scored de 4/4 'leverage negligible' off a $21M tag against a real ~$19B.

        v4.2.82 strengthens this: a disputed reading is no longer DOCKED, it is REFUSED. Docking
        says the number is usable but worse; it is not usable, and the block now reports out of a
        smaller denominator rather than pretending to know.
        """
        from ivc_lib import gps_quant
        clean = {"debt_to_equity": 0.003, "dilution_cagr": -0.02, "sbc_to_revenue": 0.018}
        disputed = dict(clean, total_debt_divergence=True)
        c, d = gps_quant(clean)["detail"]["D"], gps_quant(disputed)["detail"]["D"]
        self.assertEqual(c["pts"]["de"], 4, "control: a clean low-leverage reading still scores")
        self.assertIn(d["pts"].get("de"), (None, "[UNVERIFIED]"),
                      "a disputed debt reading was scored anyway: %r" % (d["pts"].get("de"),))
        self.assertTrue(d["debt_uncertain"])
        self.assertTrue(d["de_refused"])
        self.assertLess(d["max"], c["max"],
                        "a refused sub-block must leave the DENOMINATOR too, or the refusal reads "
                        "as a zero the company earned")


class TestPublicationLayerFollowsVerdictLeg(unittest.TestCase):
    """v4.2.34 (mandate HH). Third recurrence of the class 'consumer numbers from the base leg
    while the verdict is set by the conservative one'. Every published number must resolve against
    the VERDICT leg. MA 2026-07-22 is the case of record: verdict leg = fcf_per_share (IV 274.88)
    but the ladder was published from the GAAP IV 292.09 — entry prices 6.26% too high."""

    def _ma_like(self):
        """A dual-basis fixture where the FCF leg is the conservative (verdict) one."""
        d = mature_data()
        d["levered_fcf_per_share"] = 11.0     # below EPS 12.0 -> FCF leg lands lower
        s = mature_spec()
        s["assumptions"]["discount_rate"] = 0.12
        return analyze(d, s)

    def test_ladder_is_published_from_the_verdict_leg(self):
        r = self._ma_like()
        db = r["dual_basis"]
        vleg = db["verdict_leg"]
        self.assertEqual(r["mos_ladder_leg"], vleg,
                         "the published ladder must be labelled with the verdict leg")
        iv_v = db[vleg]["iv"]
        for rung in r["mos_ladder"]:
            t = rung["mos_target_pct"] / 100.0
            self.assertAlmostEqual(rung["buy_threshold_price"], round(iv_v / (1 + t), 2), places=1,
                                   msg="rung must equal IV_verdict_leg/(1+t), not the other leg's IV")

    def test_negative_control_ladder_is_not_the_other_leg(self):
        """MA-case negative control: with the legs materially apart, the published rungs must NOT
        match the non-verdict leg's IV."""
        r = self._ma_like()
        db = r["dual_basis"]
        vleg = db["verdict_leg"]
        other = "gaap_eps" if vleg == "fcf_per_share" else "fcf_per_share"
        iv_o = db[other]["iv"]
        if iv_o and abs(iv_o - db[vleg]["iv"]) / iv_o > 0.02:
            first = r["mos_ladder"][0]
            self.assertNotAlmostEqual(first["buy_threshold_price"], round(iv_o / 1.10, 2), places=1,
                                      msg="rungs must not be built from the non-verdict leg")

    def test_mos_pct_published_for_both_legs_with_verdict_marked(self):
        r = self._ma_like()
        self.assertIn("gaap_eps", r["mos_pct_by_leg"])
        self.assertIn("fcf_per_share", r["mos_pct_by_leg"])
        self.assertEqual(r["mos_pct_verdict_leg"],
                         r["mos_pct_by_leg"][r["dual_basis"]["verdict_leg"]],
                         "the verdict leg's MoS must be published explicitly")

    def test_fv10_of_verdict_leg_is_published_for_the_bands(self):
        r = self._ma_like()
        self.assertIsInstance(r.get("fv10_verdict_leg"), (int, float))
        out = app.trigger_prices(r, ticker="T")
        by = {t["trigger_type"]: t["price"] for t in out["triggers"]}
        self.assertAlmostEqual(by["band_avoid_to_watch"],
                               round(r["fv10_verdict_leg"] / (1.12 ** 10), 2), places=1,
                               msg="band12 must be built from the VERDICT leg's FV10")
        self.assertAlmostEqual(by["band_watch_to_buy"],
                               round(r["fv10_verdict_leg"] / (1.16 ** 10), 2), places=1)

    def test_pwfv_is_computed_on_the_verdict_leg(self):
        """v4.2.40 (mandate II, SIXTH defect). The scenario tree used to run ONLY on base_inp (the
        GAAP leg), so pwfv was a GAAP number even when the verdict came from the FCF leg. Class and
        leg are independent — 'LLM-by-design' describes the WEIGHTS, not the leg. Money defect via
        §1e: the +20/+40% overvaluation alerts on held positions are computed FROM pwfv."""
        r = self._ma_like()
        v = r["dual_basis"]["verdict_leg"]
        self.assertEqual(r["pwfv_leg"], v, "pwfv must be labelled with the verdict leg")
        self.assertEqual(r["pwfv"], r["pwfv_by_leg"][v],
                         "the published pwfv must BE the verdict leg's pwfv")
        other = "gaap_eps" if v == "fcf_per_share" else "fcf_per_share"
        if r["pwfv_by_leg"][other] is not None and r["pwfv_by_leg"][v] is not None:
            self.assertNotEqual(r["pwfv_by_leg"][v], r["pwfv_by_leg"][other],
                                "this fixture must keep the legs apart for the test to mean anything")
            self.assertLess(r["pwfv"], r["pwfv_by_leg"][other],
                            "on this fixture the conservative leg must publish the LOWER pwfv")

    def test_published_scenarios_reconcile_with_published_pwfv(self):
        """v4.2.40. The published pwfv MUST be verifiable against the published scenarios. When
        pwfv moved to the verdict leg while `scenarios` stayed GAAP, the number became unverifiable
        — the exact opacity that made a correct memo look like a hallucination (MA 2026-07-22).
        A reader recomputing the weighted mean from RESULT.scenarios must land on RESULT.pwfv."""
        r = self._ma_like()
        recomputed = round(sum(s["weight"] * s["result"]["intrinsic_value"]
                               for s in r["scenarios"].values()), 2)
        self.assertAlmostEqual(r["pwfv"], recomputed, places=1,
                               msg="pwfv must reconcile with the scenarios published alongside it")
        self.assertEqual(r["scenarios_leg"], r["pwfv_leg"],
                         "scenarios and pwfv must be labelled with the SAME leg")

    def test_publication_paths_may_not_read_ivc_base_without_a_whitelist_note(self):
        """v4.2.41 (mandate LL.4) — STRUCTURAL GUARD, the same move as shares_used in v4.2.32.
        The eighth defect of this class was introduced BY the seventh's fix: pwfv moved to the
        verdict leg while sensitivity/bull_bear stayed on GAAP. Patching consumers one by one does
        not converge — so `_pub`/`_pub_inp` are the single legal source of published quantities,
        and EVERY direct read of ivc_base/ivb must carry a `# LEG-OK:` note explaining why it is
        leg-independent (dual_basis construction, diagnostics, legacy fallback). A new unmarked
        read fails this test — the violation becomes structurally unreachable, not merely
        detectable by audit."""
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "microservice", "app.py")
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        pattern = re.compile(r'ivc_base\.get|ivb\.get|result\.get\(["\']ivc_base["\']\)')
        unmarked = []
        for i, line in enumerate(lines):
            if line.strip().startswith("#"):
                continue
            if not pattern.search(line):
                continue
            prev = lines[i - 1] if i > 0 else ""
            if "LEG-OK" in line or "LEG-OK" in prev:
                continue
            unmarked.append("app.py:%d: %s" % (i + 1, line.strip()[:90]))
        self.assertEqual(unmarked, [],
                         "direct ivc_base reads without a '# LEG-OK:' whitelist note — publication "
                         "must go through _pub. Offenders:\n" + "\n".join(unmarked))

    def test_single_publication_source_is_resolved_once(self):
        """_pub must be assigned exactly once: two homes for one truth is the recurring defect."""
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "microservice", "app.py")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        self.assertEqual(len(re.findall(r"^\s*_pub = ", src, re.M)), 1,
                         "_pub must have exactly ONE assignment (single publication source)")
        self.assertEqual(len(re.findall(r"^\s*_pub_inp = ", src, re.M)), 1,
                         "_pub_inp must have exactly ONE assignment")

    def test_sensitivity_and_bull_bear_run_on_the_verdict_leg(self):
        """mandate LL.2/LL.3: both terms of pwfv_minus_iv and the sensitivity table are published
        numbers — memo and auditor read them — so they must sit on the verdict leg."""
        r = self._ma_like()
        v = r["dual_basis"]["verdict_leg"]
        s = r["sensitivity"]
        self.assertEqual(s["leg"], v, "the sensitivity table must be labelled with the verdict leg")
        self.assertIn("pwfv_minus_iv_verdict_leg", s, "the mixed-leg field must be gone")
        self.assertNotIn("pwfv_minus_ivbase", s, "the old mixed-leg name must not survive")
        iv_v = r["dual_basis"][v]["iv"]
        self.assertAlmostEqual(s["pwfv_minus_iv_verdict_leg"], round(r["pwfv"] - iv_v, 2), places=1,
                               msg="both terms must come from the SAME (verdict) leg")

    def test_both_leg_pwfv_are_published(self):
        r = self._ma_like()
        self.assertIn("gaap_eps", r["pwfv_by_leg"])
        self.assertIn("fcf_per_share", r["pwfv_by_leg"])

    def test_inversion_is_flagged_not_inherited(self):
        """mandate HH: 'verdict leg == conservative leg' is VERIFIED, not assumed. If the verdict
        leg's IV reads HIGHER than the other leg's, raise a flag and print both."""
        d = mature_data()
        d["levered_fcf_per_share"] = 40.0   # FCF leg far ABOVE the EPS leg
        s = mature_spec()
        s["assumptions"]["discount_rate"] = 0.12
        r = analyze(d, s)
        db = r["dual_basis"]
        iv_v = db[db["verdict_leg"]]["iv"]
        other = "gaap_eps" if db["verdict_leg"] == "fcf_per_share" else "fcf_per_share"
        iv_o = db[other]["iv"]
        if iv_v > iv_o:
            self.assertTrue(any("[LEG]" in f for f in r["flags"]),
                            "an inverted verdict leg must raise the [LEG] flag")
        # both legs are published regardless
        self.assertEqual(len(r["mos_pct_by_leg"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestRunCompletenessAndErrorClass(unittest.TestCase):
    """v4.2.49 (mandate AAA). `error` carries a CLASS, and completeness is orthogonal to IV.

    Category-F and `price missing` used to be indistinguishable by SHAPE — same _FALLBACK, same
    _harness, same verdict_cap, even the same flag claiming "inputs insufficient" (a lie for
    Category-F). The live BASE predicate "broken = non-empty error" therefore classified
    Category-F as broken, which would drop OKLO, SMR, IONQ, ASTS, RDDT out of v_ticker_latest —
    the fourth marker to cut the same tail of the watchlist.
    """

    def _spec(self):
        s = mature_spec()
        s["assumptions"]["discount_rate"] = 0.12
        return s

    def test_category_f_is_an_analysis_result_and_the_run_is_complete(self):
        d = dict(mature_data(), eps0_reported=-2.0, levered_fcf_per_share=-5.0)
        r = analyze(d, self._spec())
        self.assertEqual(r["error_class"], "ANALYSIS_RESULT",
                         "intact data + inapplicable method is a CONCLUSION, not a failure")
        self.assertTrue(r["run_complete"], "a verdict was issued -> the run finished")
        self.assertFalse(r["iv_computable"])
        self.assertEqual(r["iv_not_computable_reason"], "category_f_no_positive_base")
        self.assertEqual(r["verdict_cap"], "AVOID")

    def test_category_f_is_NOT_a_fallback_and_keeps_its_gps(self):
        """_FALLBACK is disclosure of SOURCE DEGRADATION and feeds gate tooth B5. Category-F data
        arrived intact, so claiming degradation would force the memo to disclose a fiction. And
        GPS does not depend on IV — for loss-making names it is the only quantitative output."""
        d = dict(mature_data(), eps0_reported=-2.0, levered_fcf_per_share=-5.0)
        r = analyze(d, self._spec())
        self.assertFalse(r["_FALLBACK"], "no source degradation occurred")
        self.assertTrue(r.get("gps"), "GPS must be computed for Category-F")
        self.assertNotIn("harness_ivc_error_inputs_insufficient", r.get("flags", []),
                         "that flag asserts insufficient INPUTS — false here")

    def test_price_missing_is_a_data_error_and_the_run_is_incomplete(self):
        r = analyze({"price_data": {}}, self._spec())
        self.assertEqual(r["error_class"], "DATA_ERROR", "the input was never obtained")
        self.assertFalse(r["run_complete"])
        self.assertFalse(r["iv_computable"])
        self.assertEqual(r["iv_not_computable_reason"], "price_missing")
        self.assertTrue(r["_FALLBACK"])

    def test_the_two_states_are_distinguishable_by_SHAPE_not_by_error_text(self):
        """The whole point: a consumer must never have to parse the error string."""
        cf = analyze(dict(mature_data(), eps0_reported=-2.0, levered_fcf_per_share=-5.0), self._spec())
        pm = analyze({"price_data": {}}, self._spec())
        self.assertNotEqual(cf["run_complete"], pm["run_complete"])
        self.assertNotEqual(cf["error_class"], pm["error_class"])
        self.assertNotEqual(cf["_FALLBACK"], pm["_FALLBACK"])

    def test_a_normal_run_is_complete_with_computable_iv(self):
        r = analyze(mature_data(), self._spec())
        self.assertTrue(r["run_complete"])
        self.assertTrue(r["iv_computable"])
        self.assertIsNone(r.get("error_class"), "a healthy run carries no error class")

    def test_single_leg_run_is_complete(self):
        """A legitimate one-legged run (negative FCF) has no dual_basis but is fully finished."""
        r = analyze(dict(mature_data(), levered_fcf_per_share=-5.0), self._spec())
        self.assertTrue(r["run_complete"])
        self.assertTrue(r["iv_computable"], "the GAAP leg still computes")
        self.assertFalse(r["_FALLBACK"])


class TestLegSymmetryAndDilutionNaming(unittest.TestCase):
    """v4.2.50 (mandate III). Two changes shipped together, deliberately separable by measurement:

    (1) FCF_PE_DISCOUNT 0.90 REMOVED. A haircut on one leg's exit multiple lowered that leg's IV,
        which made it "conservative" more often, which made it the VERDICT leg — the knob was
        choosing the JUDGE, not the number. Both legs now share one multiple.
    (2) The two dilution figures are NAMED APART. Arithmetic was already correct (SBC charged once:
        GAAP pairs with NET, FCF with GROSS), so this part is numerically NEUTRAL — the whole
        numeric shift belongs to (1).
    """

    def _spec(self):
        s = mature_spec()
        s["assumptions"]["discount_rate"] = 0.12
        return s

    def test_both_legs_share_one_exit_multiple(self):
        r = analyze(dict(mature_data(), levered_fcf_per_share=11.0), self._spec())
        db = r["dual_basis"]
        self.assertEqual(db["fcf_per_share"]["future_multiple"], r["pe_anchor"]["base_future_pe_used"],
                         "the FCF leg must carry the SAME multiple as the base — no 0.9 haircut")

    def test_dilution_bases_are_named_apart(self):
        r = analyze(dict(mature_data(), levered_fcf_per_share=11.0), self._spec())
        db = r["dual_basis"]
        self.assertEqual(db["gaap_eps"]["dilution_basis"], "net_after_buybacks")
        self.assertEqual(db["fcf_per_share"]["dilution_basis"], "gross_before_buybacks")
        self.assertNotEqual(db["gaap_eps"]["dilution_net_after_buybacks"],
                            db["fcf_per_share"]["dilution_gross_before_buybacks"],
                            "this fixture must keep the two numbers apart, else the pin is empty")

    def test_leg_choice_is_stated_explicitly_with_the_gap(self):
        r = analyze(dict(mature_data(), levered_fcf_per_share=11.0), self._spec())
        note = r["dual_basis"]["leg_choice_note"]
        self.assertIn(r["dual_basis"]["verdict_leg"], note, "the note must name the chosen leg")
        self.assertIn("gap", note, "the note must state the inter-leg gap")

    def test_removing_the_haircut_can_flip_which_leg_judges(self):
        """The reason the knob mattered: on real MA inputs the verdict leg moves FCF -> GAAP once
        both legs share a multiple (IV FCF 274.57 -> 305.08 vs GAAP 292.09)."""
        from ivc_lib import ivc

        def leg(base, dil, pe):
            return ivc({"price": 531.98, "eps_normalized": base, "growth_rate": 0.06784855475078366,
                        "future_pe": pe, "hurdle": 0.12, "discount_rate": 0.12,
                        "share_dilution_cagr": dil, "dividend_yield": 0, "dividend_growth": 0,
                        "fade": True, "terminal_growth": 0.04, "years": 10,
                        "mos_targets": [0.20]})["intrinsic_value"]
        g = leg(16.520971302428258, -0.020721897557303248, 25.0)
        f_old = leg(18.939293598233995, -0.01156, 22.5)   # with the 0.9 haircut
        f_new = leg(18.939293598233995, -0.01156, 25.0)   # without it
        self.assertLess(f_old, g, "with the haircut the FCF leg judged")
        self.assertGreater(f_new, g, "without it the GAAP leg judges")


class TestVerdictCapFollowsConservativeLeg(unittest.TestCase):
    """v4.2.52 (sweep finding). The mutation probe caught this: flipping min(legs)->max(legs) in
    verdict_cap did NOT turn any verdict pin red — it was caught only incidentally, by a dilution
    test. The invariant "the verdict follows the CONSERVATIVE leg" — the rule that decides whether
    a name is buyable — had no direct pin of its own. Guarded by luck is not guarded."""

    def _spec(self):
        s = mature_spec()
        s["assumptions"]["discount_rate"] = 0.12
        return s

    def test_verdict_uses_the_lower_implied_cagr_of_the_two_legs(self):
        d = dict(mature_data(), levered_fcf_per_share=11.0)   # legs materially apart
        r = analyze(d, self._spec())
        db = r["dual_basis"]
        legs = [db["gaap_eps"]["implied_cagr_pct"], db["fcf_per_share"]["implied_cagr_pct"]]
        legs = [x for x in legs if x is not None]
        self.assertEqual(len(legs), 2, "this fixture must produce BOTH legs, else the pin is empty")
        self.assertNotAlmostEqual(legs[0], legs[1], places=2,
                                  msg="the legs must differ, else min and max coincide")
        lo, hi = min(legs), max(legs)
        expected = "AVOID" if lo < 12.0 else ("WATCH+" if lo < 16.0 else "BUY")
        self.assertEqual(r["verdict_cap"], expected,
                         "verdict_cap must follow the LOWER implied CAGR (conservative leg)")
        # and prove the pin can tell them apart: the optimistic reading would differ
        optimistic = "AVOID" if hi < 12.0 else ("WATCH+" if hi < 16.0 else "BUY")
        if optimistic != expected:
            self.assertNotEqual(r["verdict_cap"], optimistic,
                                "the optimistic leg must NOT drive the verdict")

    def test_a_leg_above_the_hurdle_cannot_lift_a_leg_below_it(self):
        """The case that matters for money: one leg would say BUY, the other AVOID."""
        d = dict(mature_data(), eps0_reported=30.0, levered_fcf_per_share=6.0)
        r = analyze(d, self._spec())
        db = r.get("dual_basis") or {}
        g = (db.get("gaap_eps") or {}).get("implied_cagr_pct")
        f = (db.get("fcf_per_share") or {}).get("implied_cagr_pct")
        # v4.2.82 changeset. This test carried TWO silent exits: a `skipTest` when a leg was
        # missing, and a bare `if max >= 12 > min:` around the only assertion — so a fixture that
        # drifted off the hurdle would have made the test pass having asserted nothing at all, and
        # without even the word "skipped" to show for it. The quieter of the two was the `if`.
        # Both preconditions are now assertions: this fixture is REQUIRED to straddle the hurdle,
        # because straddling it is the entire scenario the test is named after.
        self.assertIsNotNone(g, "fixture must produce a GAAP leg")
        self.assertIsNotNone(f, "fixture must produce an FCF leg")
        self.assertTrue(max(g, f) >= 12.0 > min(g, f),
                        "the fixture must STRADDLE the hurdle (legs %.2f / %.2f) — otherwise this "
                        "test cannot observe one leg lifting another" % (g, f))
        self.assertEqual(r["verdict_cap"], "AVOID",
                         "one leg below the hurdle must cap the verdict at AVOID")


class TestValuationCoreIdentities(unittest.TestCase):
    """v4.2.52 (sweep batch 2, architect's directive: start with invariants that LOOK obviously
    covered). Three of them turned out to be guarded by nothing or by accident:

      * DISCOUNTING — replacing (1+disc)**Y with (1+disc)**5 left the ENTIRE suite green. The
        single arithmetic step that turns a future value into today's fair price had no pin at all.
      * LADDER FORMULA — IV/(1+t) silently replaced by IV*(1-t) was caught only incidentally.
      * LEG CHOICE — hard-wiring `conservative = "gaap_eps"` was caught only incidentally.

    The pattern the architect named: the oldest, most central rules are the ones the suite grew
    AROUND, so coverage of them is assumed rather than written.
    """

    def _ivc(self, **over):
        from ivc_lib import ivc
        p = {"price": 100.0, "eps_normalized": 10.0, "growth_rate": 0.10, "future_pe": 20.0,
             "hurdle": 0.12, "discount_rate": 0.12, "share_dilution_cagr": 0.0,
             "dividend_yield": 0.0, "dividend_growth": 0.0, "fade": True,
             "terminal_growth": 0.04, "years": 10, "mos_targets": [0.10, 0.20, 0.30]}
        p.update(over)
        return ivc(p)

    def test_iv_is_fv10_discounted_over_the_FULL_horizon(self):
        """IV = FV10 / (1+disc)^years. Pinned as an identity, not as a magnitude."""
        r = self._ivc()
        fv10, iv = r["fv10_per_share"], r["intrinsic_value"]
        self.assertAlmostEqual(iv, fv10 / (1.12 ** 10), places=2,
                               msg="discounting must span the full 10-year horizon")
        # and prove the pin can tell horizons apart: 5 years would give a very different number
        self.assertNotAlmostEqual(iv, fv10 / (1.12 ** 5), places=2,
                                  msg="a 5-year discount must NOT satisfy this pin")

    def test_discount_rate_actually_moves_iv_in_the_right_direction(self):
        lo = self._ivc(discount_rate=0.10)["intrinsic_value"]
        hi = self._ivc(discount_rate=0.15)["intrinsic_value"]
        self.assertGreater(lo, hi, "a higher discount rate must lower today's fair value")

    def test_ladder_rung_is_iv_over_one_plus_target(self):
        """buy_threshold = IV/(1+t) — the price at which the MoS EQUALS the target. IV*(1-t) is a
        different (looser) number and must not satisfy this pin."""
        r = self._ivc()
        iv = r["intrinsic_value"]
        for rung in r["mos_ladder"]:
            t = rung["mos_target_pct"] / 100.0
            self.assertAlmostEqual(rung["buy_threshold_price"], round(iv / (1 + t), 2), places=1)
            self.assertNotAlmostEqual(rung["buy_threshold_price"], round(iv * (1 - t), 2), places=1,
                                      msg="IV*(1-t) is the wrong rung formula")

    def test_mos_at_the_threshold_equals_the_target(self):
        """The self-test the ladder exists for: standing at the rung, the margin IS the target."""
        r = self._ivc()
        iv = r["intrinsic_value"]
        for rung in r["mos_ladder"]:
            t = rung["mos_target_pct"] / 100.0
            thr = rung["buy_threshold_price"]
            self.assertAlmostEqual((iv - thr) / thr, t, places=2)

    def test_conservative_leg_is_chosen_by_comparison_not_hard_wired(self):
        """Flip which leg is cheaper and the verdict leg must follow. Hard-wiring either name
        passes a fixture where that name happens to be right — so both directions are pinned."""
        s = mature_spec()
        s["assumptions"]["discount_rate"] = 0.12
        fcf_low = analyze(dict(mature_data(), levered_fcf_per_share=6.0), s)
        fcf_high = analyze(dict(mature_data(), levered_fcf_per_share=40.0), s)
        self.assertEqual(fcf_low["dual_basis"]["verdict_leg"], "fcf_per_share",
                         "when the FCF leg is cheaper it must judge")
        self.assertEqual(fcf_high["dual_basis"]["verdict_leg"], "gaap_eps",
                         "when the GAAP leg is cheaper it must judge — the choice is COMPUTED")


class TestSbcDisciplineSubScore(unittest.TestCase):
    """sbc-01: the SBC sub-score of the D block had NO pin at all.

    Found 2026-07-30 by mutation, not by reading: replacing the whole ladder with
    `lambda v: 2` -- "any SBC intensity earns full marks" -- left all 411 tests green.
    The sub-score decides 2 of the D block's 10 points on every name, and the watchlist
    carries at least six names where it is the difference between 2/2 and 0/2
    (PLTR-class: SBC/revenue ~19%). A rule that no test can distinguish from a constant
    is not enforced by anything.

    Not to be confused with the phantom it was found next to: the `"sbc_rev":0` seen in the
    24.07 reports was a 140-char truncation in Render Tables clipping `0.0182` after its
    leading zero. The DATA was always fine (MA 1.82%, NFLX 0.8%, both scored 2/2). These pins
    guard the SCORING RULE, which is a different surface from the printing.
    """

    #: de and dilution are held constant so the D block moves ONLY through sbc.
    BASE = {"debt_to_equity": 0.5, "dilution_cagr": -0.02}

    def _sbc(self, v):
        from ivc_lib import gps_quant
        gt = dict(self.BASE, sbc_to_revenue=v)
        return gps_quant(gt)["detail"]["D"]

    def test_ladder_boundaries_are_exact_on_both_sides(self):
        """`2 if v < 0.03 else 1 if v <= 0.08 else 0` -- an off-by-one between `<` and `<=`
        moves a name a full point without changing anything a value-based test would see."""
        for v, expected in [(0.0299, 2), (0.03, 1), (0.05, 1), (0.08, 1), (0.0801, 0)]:
            self.assertEqual(self._sbc(v)["pts"]["sbc"], expected,
                             "SBC/revenue %.4f must score %d" % (v, expected))

    def test_heavier_sbc_scores_STRICTLY_worse_than_lighter_sbc(self):
        """The identity, not the values: the sub-score must DISCRIMINATE. A constant ladder
        is weakly monotonic and would survive an ordering-only assertion, so the comparison
        is strict and spans all three rungs."""
        light = self._sbc(0.018)["pts"]["sbc"]     # MA-like, real 2026 figure
        mid = self._sbc(0.05)["pts"]["sbc"]
        heavy = self._sbc(0.19)["pts"]["sbc"]      # PLTR-class
        self.assertGreater(light, mid, "1.8% SBC must beat 5% SBC")
        self.assertGreater(mid, heavy, "5% SBC must beat 19% SBC")

    def test_an_sbc_heavy_name_cannot_take_the_top_mark(self):
        """The money case. A name paying 19% of revenue in stock must not read as
        'SBC discipline: full marks' -- that is the GAAP-EPS double-count the dual-basis
        machinery exists to expose, arriving through the scorecard instead."""
        heavy = self._sbc(0.19)
        light = self._sbc(0.018)
        self.assertEqual(heavy["pts"]["sbc"], 0)
        self.assertEqual(light["pts"]["sbc"], 2)
        self.assertLess(heavy["pts"]["sbc"], light["pts"]["sbc"])
        self.assertEqual(heavy["max"], light["max"],
                         "both are MEASURED: the denominator must not move between them")

    def test_unmeasured_sbc_is_unknown_and_leaves_the_denominator(self):
        """Missing is not zero and not full marks: it drops out of BOTH sides, so the block
        renders points/reduced_max and the gap is visible (the v4.2.2 rule, applied here)."""
        d = self._sbc(None)
        self.assertEqual(d["pts"]["sbc"], "[UNVERIFIED]")
        self.assertEqual(d["max"], 8, "the 2 SBC points must leave the DENOMINATOR too")
        self.assertEqual(self._sbc(0.018)["max"], 10, "control: a measured name keeps its 10")


class TestHealthDeclaresBuild(unittest.TestCase):
    """v4.2.77. `/health` answered without a version, so there was no way to learn which build was
    actually live on Railway. The workflow and the microservice deploy separately and DO drift —
    that drift twice sent a debugging cycle after a report produced by a different build than the
    one being read. The one-liner closes it.

    The pin is deliberately about PROVENANCE, not about a value: the version must be READ from the
    single `__build__` marker, never restated in the route. A restated string is a second home for
    the fact and would go stale exactly when it matters — on the deploy someone forgot to finish.
    """

    def setUp(self):
        self.client = app.app.test_client()

    def test_health_reports_the_build(self):
        body = self.client.get("/health").get_json()
        self.assertEqual(body.get("status"), "ok")
        self.assertIn("build", body, "/health must name the build, or Railway stays unverifiable")
        self.assertNotEqual(body["build"], "UNKNOWN", "the marker could not be read")

    def test_the_version_is_read_from_the_marker_not_restated(self):
        src_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "microservice", "app.py")
        with open(src_path, encoding="utf-8") as fh:
            src = fh.read()
        marker = re.search(r'__bu' + r'ild__ = "([^"]+)"', src)
        self.assertIsNotNone(marker, "the build marker vanished from app.py")
        self.assertEqual(self.client.get("/health").get_json()["build"], marker.group(1),
                         "/health disagrees with the marker — two homes, one already stale")
        self.assertEqual(len(re.findall(r'"v4\.\d+\.\d+"', src)), 1,
                         "a version literal was restated in app.py; the marker is the only home")

    def test_an_unreadable_marker_is_UNKNOWN_never_a_plausible_default(self):
        """The v4.2.2 rule at the boundary: an absence spelled as an absence. A default here would
        have the operator compare a live report against a version that was never deployed."""
        real_file = app.__file__
        app.__file__ = "/nonexistent/app.py"
        try:
            self.assertEqual(app._build_marker(), "UNKNOWN")
        finally:
            app.__file__ = real_file
        self.assertNotEqual(app._build_marker(), "UNKNOWN", "control: the real source still reads")


class TestPeAnchorHasOneInput(unittest.TestCase):
    """v4.2.77. `_pe_anchor_fwd` used to try two candidates: the in-house peer median and
    `pe_sector_median`. The second never arrived — the key appears nowhere in the workflow — so the
    loop read an absence on every run since it was written, and the anchor has in fact always been
    the peer median alone.

    An always-empty read is not harmless. It is machinery whose SHAPE promises a measurement it
    cannot deliver, and the next reader believes a true sector median is in play. Same class as the
    entry rung defaulting to 20 and the year-5 point that lived in RESULT but never printed.
    """

    def test_the_ghost_input_is_not_read(self):
        src_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "microservice", "app.py")
        with open(src_path, encoding="utf-8") as fh:
            body = fh.read()
        start = body.index("def _pe_anchor_fwd(")
        end = body.index("\ndef ", start + 10)
        fn = body[start:end]
        code = "\n".join(l for l in fn.split("\n") if not l.strip().startswith("#"))
        code = code.split('"""')[0] + code.split('"""')[-1]
        self.assertNotIn('data.get("pe_sector_median")', code,
                         "the anchor reads a key the pipeline never supplies")

    def test_a_sector_median_alone_anchors_nothing(self):
        """Positive control: supplying ONLY the ghost key must NOT produce an anchor. If it does,
        the read is back and a value that never arrives is silently load-bearing again."""
        self.assertIsNone(app._pe_anchor_fwd({"pe_sector_median": 22.0}))
        self.assertEqual(app._pe_anchor_fwd({"peer_median_pe": 22.0}), 22.0,
                         "control: the peer median is still the anchor")

    def test_a_trailing_peer_median_is_still_excluded(self):
        """The NFLX-2026-07-16 guard survives the cut: a wrong anchor is worse than no anchor."""
        self.assertIsNone(app._pe_anchor_fwd({"peer_median_pe": 95.09,
                                              "peer_median_pe_basis": "trailing"}))


class TestPeerMultipleBlockMatchesBases(unittest.TestCase):
    """v4.2.77 (g).4. The peer median and the company multiple must be published on ONE basis or
    the comparison must be refused. The in-house peer median is TRAILING; the forward company
    multiple comes from a different source and period. A sentence placed between two such numbers
    does not make them comparable — it only makes the mismatch invisible."""

    def test_a_trailing_peer_median_pairs_with_the_trailing_company_multiple(self):
        b = app._peer_multiple_block({
            "peer_median_pe": 24.6, "peer_median_pe_basis": "edgar_tiingo_trailing_inhouse",
            "peer_multiples": [{"ticker": "A"}, {"ticker": "B"}, {"ticker": "C"}],
            "pe_trailing_company": 31.2, "pe_trailing_company_basis": "alpha_vantage_trailing_reported",
            "fwd_pe": 19.0, "fwd_pe_basis": "alpha_vantage"})
        self.assertTrue(b["comparable"])
        self.assertEqual(b["company"], 31.2, "the FORWARD multiple was paired with a trailing median")
        self.assertEqual(b["count"], 3)

    def test_no_company_multiple_on_that_basis_means_NOT_comparable(self):
        b = app._peer_multiple_block({
            "peer_median_pe": 24.6, "peer_median_pe_basis": "edgar_tiingo_trailing_inhouse",
            "peer_multiples": [{"ticker": "A"}], "fwd_pe": 19.0, "fwd_pe_basis": "alpha_vantage"})
        self.assertFalse(b["comparable"], "a trailing median was declared comparable to nothing")
        self.assertIsNone(b["company"])

    def test_missing_peer_rows_give_count_None_not_zero(self):
        """A median over an unknown number of peers must not be published as a median over none."""
        b = app._peer_multiple_block({"peer_median_pe": 24.6,
                                      "peer_median_pe_basis": "edgar_tiingo_trailing_inhouse",
                                      "pe_trailing_company": 31.2,
                                      "pe_trailing_company_basis": "av_trailing"})
        self.assertIsNone(b["count"])
        self.assertFalse(b["comparable"], "an unknown N still produced a comparison")


class TestPeerMultipleReachesRESULT(unittest.TestCase):
    """v4.2.77. The first draft of `peer_multiple` was written into `base_inp`, the IVC input dict,
    while the brief reads `res.peer_multiple` from RESULT. Both units were individually correct and
    every unit test of the block passed — the field simply never arrived. Same shape as the
    gps_quant case: a contract asserted only where it is PRODUCED, never where it is CONSUMED.
    So this pin drives analyze() and looks at what a renderer would actually see.
    """

    def test_the_block_is_published_in_RESULT_not_in_the_ivc_inputs(self):
        d = mature_data()
        d.update({"peer_median_pe": 24.6,
                  "peer_median_pe_basis": "edgar_tiingo_trailing_inhouse",
                  "peer_multiples": [{"ticker": "A"}, {"ticker": "B"}],
                  "pe_trailing_company": 31.2,
                  "pe_trailing_company_basis": "alpha_vantage_trailing_reported"})
        r = analyze(d, mature_spec())
        self.assertIn("peer_multiple", r, "the renderer's field never reaches RESULT")
        self.assertEqual(r["peer_multiple"]["count"], 2)
        self.assertTrue(r["peer_multiple"]["comparable"])
        self.assertEqual(r["peer_multiple"]["basis"], "edgar_tiingo_trailing_inhouse")

    def test_a_run_without_peers_still_publishes_the_block_as_a_refusal(self):
        """Absence must be STATED, not omitted: a missing key and a refused comparison look the
        same to a renderer that only checks truthiness, and one of them is a pipeline defect."""
        r = analyze(mature_data(), mature_spec())
        self.assertIn("peer_multiple", r)
        self.assertFalse(r["peer_multiple"]["comparable"])
        self.assertIsNone(r["peer_multiple"]["count"])


class TestThreeYearTable(unittest.TestCase):
    """(I) v4.2.79. Three fiscal years from series the pipeline already holds. The one place this
    could go wrong quietly is the multiple: we hold exactly one price — today's — and no historical
    price series, so a column called "P/E" would be false for every year but the last. The field
    NAMES its own basis so a renderer cannot relabel it by accident."""

    def test_rows_carry_the_fiscal_year_end_and_derived_values(self):
        d = mature_data()
        r = analyze(d, mature_spec())["three_year_table"]
        self.assertTrue(r["rows"], "no rows built from the EDGAR series")
        self.assertLessEqual(len(r["rows"]), 3, "more than three fiscal years published")
        for row in r["rows"]:
            self.assertIsNotNone(row["fy_end"], "a row without its fiscal-year end is ambiguous")
        self.assertIn("pe_at_todays_price", r["rows"][0],
                      "the multiple field must name its basis, not be called p/e")
        self.assertIn("NOT a historical", r["pe_basis"])

    def test_a_year_without_eps_publishes_None_not_zero(self):
        d = mature_data()
        d["shares_diluted"] = []
        r = analyze(d, mature_spec())["three_year_table"]
        for row in r["rows"]:
            self.assertIsNone(row["eps"])
            self.assertIsNone(row["pe_at_todays_price"],
                              "a multiple was computed from a missing EPS")

    def test_no_series_gives_an_empty_table_not_a_fabricated_one(self):
        d = mature_data()
        d["revenue"] = []
        r = analyze(d, mature_spec())["three_year_table"]
        self.assertEqual(r["rows"], [])


class TestDebtZeroIsUnknownORCLCase(unittest.TestCase):
    """v4.2.82, ORCL 2026-08-05 — the case of record.

    EDGAR returned total_debt = 0; `gather` reported $129.541B against equity of $42.508B
    (D/E ~ 3.05); the ground truth carried a 100% divergence between them. `debt_to_equity` came
    out a literal 0.00, took 4/4 under "v < 0.5", and the memo wrote "zero reported leverage ...
    support a high score" about a company carrying roughly $100B of debt. The run's own auditor
    sustained a MAJOR objection and the score did not move.

    This is the "zero instead of unknown" class landing on the balance sheet, and the whole point
    of the fix is that the honest answer is a REFUSAL — not a top mark, and not a zero the company
    could be said to have earned.
    """

    def _orcl(self):
        """v4.2.83: THE FIXTURE USED TO INVENT THE SHAPE. It put the divergence at the TOP level —
        `{"divergence": {...}}` — which is a payload the pipeline has never produced. `Gather Data`
        publishes `_edgar: {flags, divergence, sources, cik, entity_name}`, so the evidence really
        arrives at `_edgar.divergence.total_debt`. The pin was therefore green against a shape of
        its own making while the live run took the other branch entirely: on 2026-08-05 the refusal
        fired through `_debt_zero_suspect` and printed "debt_to_equity is exactly 0".

        Rule 5, exactly: a fixture consistent with itself proves nothing. It cost a full run to
        find, and the run only found it because the REASON STRING is published — had the refusal
        been a bare boolean, the wrong branch would have been invisible.
        """
        return {"debt_to_equity": 0, "dilution_cagr": -0.00725, "sbc_to_revenue": 0.0714,
                "_edgar": {"divergence": {"total_debt": {"edgar": 0,
                                                         "gather": 129541000000, "pct": 100}}}}

    def test_the_divergence_is_read_where_the_producer_writes_it(self):
        """The money case, and the one ORCL never exercised: divergence present, D/E NOT zero.

        With a non-zero ratio the zero-suspect branch cannot fire, so this test passes only if the
        divergence branch itself works. A 99.9% disagreement on debt with a plausible-looking 1.8
        ratio is the MA case shape (LongTermDebt tag $21M against components $19.0B) — it would
        have taken marks on merit right up until this changeset.
        """
        from ivc_lib import gps_quant
        d = gps_quant({"debt_to_equity": 1.8, "dilution_cagr": -0.02, "sbc_to_revenue": 0.018,
                       "_edgar": {"divergence": {"total_debt": {"edgar": 21000000,
                                                                "gather": 19000000000,
                                                                "pct": 99.9}}}})["detail"]["D"]
        self.assertTrue(d["de_refused"],
                        "a 99.9% divergence on a NON-zero ratio still bought a leverage score")
        self.assertIn("diverges", d["de_refusal_reason"] or "",
                      "the refusal fired, but through the wrong branch — the reason names it")

    def test_a_divergence_below_the_threshold_scores_normally(self):
        """Negative control. Without it the pin above is satisfied by refusing every balance sheet
        that carries any divergence block at all, which would make the guard useless in the other
        direction: sources rarely agree to the digit.
        """
        from ivc_lib import gps_quant
        d = gps_quant({"debt_to_equity": 0.3, "dilution_cagr": -0.02, "sbc_to_revenue": 0.018,
                       "_edgar": {"divergence": {"total_debt": {"edgar": 19000000000,
                                                                "gather": 19500000000,
                                                                "pct": 2.6}}}})["detail"]["D"]
        self.assertFalse(d["de_refused"], "a 2.6% disagreement is agreement, not uncertainty")
        self.assertEqual(d["pts"]["de"], 4, "a genuinely low ratio must still take the top mark")

    def test_the_ORCL_case_now_names_DIVERGENCE_as_the_reason(self):
        """The regression that would have caught 2026-08-05 before the run. Both branches are true
        for ORCL, and which one the code reports says which one it actually read.
        """
        from ivc_lib import gps_quant
        d = gps_quant(self._orcl())["detail"]["D"]
        self.assertIn("diverges", d["de_refusal_reason"] or "",
                      "reported the exact-zero branch again: the divergence read is still blind")
        self.assertIn("129541000000", (d["de_refusal_reason"] or "").replace(",", ""),
                      "the refusal must carry the numbers a reader can check")

    def test_the_ORCL_reading_is_refused_not_scored(self):
        from ivc_lib import gps_quant
        d = gps_quant(self._orcl())["detail"]["D"]
        self.assertTrue(d["debt_uncertain"], "a 100% source divergence read as a clean number")
        self.assertTrue(d["de_refused"])
        self.assertIn(d["pts"].get("de"), (None, "[UNVERIFIED]"),
                      "the zero still bought a leverage score")
        self.assertIn("diverges", d["de_refusal_reason"] or "",
                      "the refusal must say WHY, or the reader cannot judge it")

    def test_an_exact_zero_alone_is_enough_to_refuse(self):
        """Even with no divergence recorded, D/E of exactly 0.00 is not a business fact about an
        operating company — it is a fetch that came back empty."""
        from ivc_lib import gps_quant
        d = gps_quant({"debt_to_equity": 0, "dilution_cagr": -0.02,
                       "sbc_to_revenue": 0.018})["detail"]["D"]
        self.assertTrue(d["de_refused"])
        self.assertIn("UNKNOWN", d["de_refusal_reason"] or "")

    def test_a_refused_leverage_leaves_the_denominator(self):
        """A refusal that stays in the max is a zero wearing a refusal's name: the block would read
        8/10 instead of 8/8 and the reader would think two points were lost on merit."""
        from ivc_lib import gps_quant
        clean = gps_quant({"debt_to_equity": 0.3, "dilution_cagr": -0.02, "sbc_to_revenue": 0.018})
        refused = gps_quant(self._orcl())
        self.assertEqual(clean["detail"]["D"]["max"] - 4, refused["detail"]["D"]["max"])

    def test_a_real_low_leverage_reading_still_scores(self):
        """Control: the fix must not refuse every good balance sheet. 0.003 is low, not empty."""
        from ivc_lib import gps_quant
        d = gps_quant({"debt_to_equity": 0.003, "dilution_cagr": -0.02,
                       "sbc_to_revenue": 0.018})["detail"]["D"]
        self.assertEqual(d["pts"]["de"], 4)
        self.assertFalse(d["de_refused"])
