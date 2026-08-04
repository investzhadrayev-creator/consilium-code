"""v4.2.5 cost ledger. Every test here pins a way this could quietly lie about money."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "microservice"))
import app        # noqa: E402
import pricing    # noqa: E402

TODAY = dt.date(2026, 7, 17)


def anthropic(inp, out, cr=0, cw=0):
    return {"usage": {"input_tokens": inp, "output_tokens": out,
                      "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw}}


class TestUnknownIsNotZero(unittest.TestCase):
    """The whole point. A run is never free; an unmeasured run is not a cheap one."""

    def test_unpriced_model_is_UNVERIFIED_not_zero(self):
        # A model with no rate. grok-4.3/4.5 are both priced now (v4.2.6), so this uses a name that
        # genuinely is not in the table — the behaviour under test is the POLICY, not the model.
        r = pricing.cost_ledger([{"stage": "Stage 3 Grok", "provider": "xai", "model": "grok-9.9",
                                  "response": {"usage": {"input_tokens": 5000, "output_tokens": 900}}}],
                                TODAY)
        row = r["rows"][0]
        self.assertEqual(row["input_tokens"], 5000, "tokens are facts and must survive")
        self.assertIsNone(row["est_cost_usd"])
        self.assertEqual(row["cost_status"], "[UNVERIFIED]")
        self.assertIn("Stage 3 Grok (grok-9.9)", r["totals"]["excluded_unpriced"])
        self.assertTrue(r["totals"]["est_cost_is_partial"])

    def test_missing_usage_block_is_METER_LOST_not_zero(self):
        """The stage ran and burned real money; we merely failed to read the meter. Reporting 0
        would understate the bill by exactly the amount we failed to measure."""
        r = pricing.cost_ledger([{"stage": "Stage 2a Claude", "provider": "anthropic",
                                  "model": "claude-sonnet-5", "response": {"content": "..."}}], TODAY)
        row = r["rows"][0]
        self.assertEqual(row["status"], "meter_lost")
        self.assertNotIn("est_cost_usd", row)
        self.assertIn("Stage 2a Claude", r["totals"]["excluded_meter_lost"])

    def test_not_run_is_DIFFERENT_from_meter_lost(self):
        """A Core-V branch that never executed genuinely cost nothing. Collapsing that with
        'we lost the meter' would make a real gap indistinguishable from a real zero."""
        r = pricing.cost_ledger([{"stage": "Core-V Arbiter", "provider": "anthropic",
                                  "model": "claude-opus-4-8", "response": None, "ran": False}], TODAY)
        self.assertEqual(r["rows"][0]["status"], "not_run")
        self.assertEqual(r["totals"]["excluded_meter_lost"], [])

    def test_total_declares_itself_partial_when_anything_is_missing(self):
        r = pricing.cost_ledger([
            {"stage": "ok", "provider": "anthropic", "model": "claude-opus-4-8",
             "response": anthropic(1000, 100)},
            {"stage": "bad", "provider": "xai", "model": "grok-9.9",
             "response": {"usage": {"input_tokens": 1, "output_tokens": 1}}},
        ], TODAY)
        self.assertTrue(r["totals"]["est_cost_is_partial"],
                        "a total that hides its own gaps is worse than no total")


class TestCacheEconomics(unittest.TestCase):
    """Stage 2a/2b/6 run cache_control ON. Getting this wrong is an order of magnitude."""

    def test_cache_read_is_not_billed_as_full_input(self):
        plain = pricing.cost_ledger([{"stage": "s", "provider": "anthropic", "model": "claude-opus-4-8",
                                      "response": anthropic(100000, 0)}], TODAY)["totals"]["est_cost_usd"]
        cached = pricing.cost_ledger([{"stage": "s", "provider": "anthropic", "model": "claude-opus-4-8",
                                       "response": anthropic(0, 0, cr=100000)}], TODAY)["totals"]["est_cost_usd"]
        self.assertAlmostEqual(cached, plain * 0.10, places=6,
                              msg="a cache READ must bill at 10%% of input, not 100%%")

    def test_cache_write_costs_MORE_than_plain_input(self):
        plain = pricing.cost_ledger([{"stage": "s", "provider": "anthropic", "model": "claude-opus-4-8",
                                      "response": anthropic(100000, 0)}], TODAY)["totals"]["est_cost_usd"]
        write = pricing.cost_ledger([{"stage": "s", "provider": "anthropic", "model": "claude-opus-4-8",
                                      "response": anthropic(0, 0, cw=100000)}], TODAY)["totals"]["est_cost_usd"]
        self.assertGreater(write, plain, "a cache WRITE bills at 125% of input, not less")

    def test_arithmetic_is_exactly_right_for_a_known_case(self):
        # opus 4.8 @ $5/$25 per MTok: 1M in + 1M out = 5 + 25 = 30
        r = pricing.cost_ledger([{"stage": "s", "provider": "anthropic", "model": "claude-opus-4-8",
                                  "response": anthropic(1_000_000, 1_000_000)}], TODAY)
        self.assertAlmostEqual(r["totals"]["est_cost_usd"], 30.0, places=4)


class TestCacheConventionsAreOpposite(unittest.TestCase):
    """v4.2.8. Anthropic and OpenAI/xAI count cached tokens in OPPOSITE ways, and applying one
    rule to both is not a rounding error — it produced a NEGATIVE cost, caught by a unit test
    mid-edit. Each normaliser must DECLARE its convention; the ledger must obey the declaration."""

    def test_anthropic_cached_tokens_are_a_SEPARATE_counter(self):
        # input_tokens EXCLUDES cache. Total input = input + cache_read + cache_creation.
        self.assertFalse(pricing._normalise_anthropic(anthropic(10, 10, cr=5))["cache_in_input"])

    def test_openai_and_xai_and_gemini_cached_tokens_are_a_SUBSET(self):
        for f, j in ((pricing._normalise_openai, {"usage": {"prompt_tokens": 10, "completion_tokens": 1}}),
                     (pricing._normalise_xai, {"usage": {"input_tokens": 10, "output_tokens": 1}}),
                     (pricing._normalise_gemini, {"usageMetadata": {"promptTokenCount": 10,
                                                                    "candidatesTokenCount": 1}})):
            self.assertTrue(f(j)["cache_in_input"], "%s must declare the subset convention" % f.__name__)

    def test_no_provider_can_ever_produce_a_negative_cost(self):
        """The failure mode that exposed this. A cost below zero is not a discount, it is a sign
        that two conventions got crossed."""
        cases = [("anthropic", "claude-opus-4-8", anthropic(0, 0, cr=100000)),
                 ("anthropic", "claude-opus-4-8", anthropic(10, 10, cr=100000, cw=100000)),
                 ("xai", "grok-4.5", {"usage": {"input_tokens": 100000, "output_tokens": 0,
                                                "input_tokens_details": {"cached_tokens": 100000}}}),
                 ("openai", "gpt-5.6-sol", {"usage": {"prompt_tokens": 100000, "completion_tokens": 0,
                                            "prompt_tokens_details": {"cached_tokens": 100000}}})]
        for prov, model, resp in cases:
            r = pricing.cost_ledger([{"stage": "s", "provider": prov, "model": model,
                                      "response": resp}], TODAY)
            self.assertGreaterEqual(r["totals"]["est_cost_usd"], 0,
                                    "%s/%s produced a NEGATIVE cost" % (prov, model))

    def test_a_legitimate_ZERO_is_not_reported_as_a_lost_meter(self):
        """The mirror of the house rule. `_n(x) or _n(y)` treats output_tokens=0 as absent (0 is
        falsy), falls through to a field the provider never sent, yields None, and the ledger then
        calls a fully measured stage "meter_lost" and drops it from the total. Unknown is not zero
        — and zero is not unknown. Caught by a unit test mid-edit, v4.2.8."""
        r = pricing.cost_ledger([{"stage": "s", "provider": "xai", "model": "grok-4.5",
            "response": {"usage": {"input_tokens": 1000, "output_tokens": 0}}}], TODAY)
        row = r["rows"][0]
        self.assertEqual(row["status"], "ok", "a real zero was misread as a lost meter")
        self.assertEqual(row["output_tokens"], 0)
        self.assertEqual(r["totals"]["excluded_meter_lost"], [])

    def test_a_fully_cached_subset_request_costs_the_cache_rate_not_zero_and_not_full(self):
        """xAI: 100k input of which 100k cached -> 100k x $0.50/M = $0.05. Not $0.20 (no discount
        applied), not $0.15 (double-counted), not negative."""
        r = pricing.cost_ledger([{"stage": "s", "provider": "xai", "model": "grok-4.5",
            "response": {"usage": {"input_tokens": 100000, "output_tokens": 0,
                                   "input_tokens_details": {"cached_tokens": 100000}}}}], TODAY)
        self.assertAlmostEqual(r["totals"]["est_cost_usd"], 0.05, places=6)


class TestNormalisers(unittest.TestCase):
    """Five providers, five schemas. Each is a chance to read the wrong field and never notice."""

    def test_openai_reasoning_tokens_are_not_double_counted(self):
        """reasoning_tokens live INSIDE completion_tokens. Adding them again would inflate the
        priciest leg of a reasoning model. gpt-5.6-sol runs reasoning_effort=medium."""
        r = pricing.cost_ledger([{"stage": "Stage 5 Auditor", "provider": "openai", "model": "gpt-5.6-sol",
            "response": {"usage": {"prompt_tokens": 1000, "completion_tokens": 5000,
                                   "completion_tokens_details": {"reasoning_tokens": 4000}}}}], TODAY)
        self.assertEqual(r["rows"][0]["output_tokens"], 5000, "reasoning tokens were double-counted")

    def test_gemini_thoughts_tokens_ARE_added(self):
        """Opposite of OpenAI: thoughtsTokenCount is billed as output and is NOT inside
        candidatesTokenCount. The two providers are mirror images and both must be handled."""
        r = pricing.cost_ledger([{"stage": "Stage 4 Gemini", "provider": "gemini",
            "model": "gemini-3.1-pro-preview",
            "response": {"usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 500,
                                           "thoughtsTokenCount": 2000}}}], TODAY)
        self.assertEqual(r["rows"][0]["output_tokens"], 2500, "gemini thinking tokens were dropped")

    def test_each_provider_shape_is_read_at_all(self):
        cases = [("anthropic", "claude-opus-4-8", anthropic(10, 20)),
                 ("openai", "gpt-5.6-sol", {"usage": {"prompt_tokens": 10, "completion_tokens": 20}}),
                 ("gemini", "gemini-3.1-pro-preview",
                  {"usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20}}),
                 ("xai", "grok-4.5", {"usage": {"input_tokens": 10, "output_tokens": 20}}),
                 ("perplexity", "sonar-pro", {"usage": {"prompt_tokens": 10, "completion_tokens": 20}})]
        for prov, model, resp in cases:
            r = pricing.cost_ledger([{"stage": prov, "provider": prov, "model": model,
                                      "response": resp}], TODAY)
            self.assertEqual(r["rows"][0].get("input_tokens"), 10, "%s normaliser is blind" % prov)

    def test_a_provider_changing_its_schema_degrades_to_meter_lost(self):
        r = pricing.cost_ledger([{"stage": "s", "provider": "anthropic", "model": "claude-opus-4-8",
                                  "response": {"usage": {"totally_new_field": 999}}}], TODAY)
        self.assertEqual(r["rows"][0]["status"], "meter_lost")


class TestPriceTableHonesty(unittest.TestCase):
    """A price table is a hardcoded number. This is what stops it lying quietly."""

    def test_intro_rate_expiry_is_machine_checked_not_a_comment(self):
        """claude-sonnet-5 is on an intro rate to 2026-08-31, then +50%. Stage 2a and 2b both
        use it. A comment would not have caught this; a date does."""
        before = pricing.effective_rates("claude-sonnet-5", dt.date(2026, 8, 30))
        after = pricing.effective_rates("claude-sonnet-5", dt.date(2026, 9, 1))
        self.assertEqual(before["input"], 2.00)
        self.assertEqual(after["input"], 3.00, "the intro rate did not lapse — costs understated 50%")

    def test_lapsed_rate_with_no_successor_refuses_to_price(self):
        """sonar-pro's post-2026-08-31 rate is not established. Guessing it would be inventing a
        number; carrying the intro rate forward would understate the bill."""
        self.assertIsNone(pricing.effective_rates("sonar-pro", dt.date(2026, 9, 1)))

    def test_table_warns_before_the_rate_lapses_not_after(self):
        st = pricing.table_status(dt.date(2026, 7, 17))
        models = [e["model"] for e in st["expiring"]]
        self.assertIn("claude-sonnet-5", models, "a 45-day warning that fires late is not a warning")
        self.assertIn("sonar-pro", models)

    def test_stale_table_says_so(self):
        self.assertFalse(pricing.table_status(dt.date(2026, 7, 17))["stale"])
        self.assertTrue(pricing.table_status(dt.date(2026, 12, 1))["stale"],
                        "90-day staleness rule (operator-set 2026-07-17) did not fire")

    def test_operator_verification_status_is_surfaced(self):
        """Every rate here came from a secondary aggregator. The report must say so until the
        operator checks them against vendor pages."""
        st = pricing.table_status(TODAY)
        self.assertIn("claude-opus-4-8", st["unverified_by_operator"])

    def test_perplexity_per_search_billing_is_flagged_as_incomplete(self):
        r = pricing.cost_ledger([{"stage": "Stage 1 Perplexity", "provider": "perplexity",
            "model": "sonar-pro",
            "response": {"usage": {"prompt_tokens": 1000, "completion_tokens": 500}}}], TODAY)
        self.assertIn("Stage 1 Perplexity", r["totals"]["understated_incomplete"])


class TestGrokV426(unittest.TestCase):
    """v4.2.6 — Stage 3 moved grok-4.3 -> grok-4.5 (4.5 launched 2026-07-08). Not a bug fix:
    4.3 is alive, cheaper and has 2x the context. The switch is a deliberate trade."""

    def test_both_grok_generations_are_priced(self):
        """4.3 stays priced so a rollback does not silently become [UNVERIFIED], and so the two
        can be compared on a real ledger rather than on vibes."""
        for m in ("grok-4.5", "grok-4.3"):
            self.assertIsNotNone(pricing.effective_rates(m, TODAY), m + " lost its rate")

    def test_45_really_is_more_expensive_than_43(self):
        def c(m):
            return pricing.cost_ledger([{"stage": "s", "provider": "xai", "model": m,
                "response": {"usage": {"input_tokens": 9000, "output_tokens": 3000}}}],
                TODAY)["totals"]["est_cost_usd"]
        self.assertGreater(c("grok-4.5"), c("grok-4.3"),
                           "the upgrade must show up in the ledger, not be assumed free")

    def test_context_surcharge_over_200k_is_declared_not_swallowed(self):
        """xAI bills an UNPUBLISHED higher rate above 200K input tokens. We cannot compute it, so
        the row must say the estimate is understated rather than quietly present a low number."""
        r = pricing.cost_ledger([{"stage": "s", "provider": "xai", "model": "grok-4.5",
            "response": {"usage": {"input_tokens": 250000, "output_tokens": 100}}}], TODAY)
        self.assertEqual(r["rows"][0]["cost_status"], "estimate_understated")
        self.assertTrue(r["totals"]["est_cost_is_partial"])

    def test_priority_tier_doubles_and_is_declared(self):
        # service_tier comes back INSIDE the response body, which is where _normalise_xai looks.
        # The first draft of this test put it on the stage dict and failed — correctly. Fixture
        # bug, not a code bug: a test that asserts against a shape the API never sends pins
        # nothing.
        r = pricing.cost_ledger([{"stage": "s", "provider": "xai", "model": "grok-4.5",
            "response": {"service_tier": "priority",
                         "usage": {"input_tokens": 100, "output_tokens": 100}}}], TODAY)
        self.assertEqual(r["rows"][0]["cost_status"], "estimate_understated")
        self.assertIn("2x", r["rows"][0]["note"])

    def test_vendor_cost_ticks_are_carried_RAW_never_converted(self):
        """xAI is the only provider that returns its own cost figure. It beats our estimate — but
        the 'ticks' unit is undocumented, and a guessed conversion wearing vendor authority is
        worse than an honest estimate. Carry it raw for the operator to reconcile once."""
        r = pricing.cost_ledger([{"stage": "s", "provider": "xai", "model": "grok-4.5",
            "response": {"usage": {"input_tokens": 9000, "output_tokens": 3000,
                                   "cost_in_usd_ticks": 361}}}], TODAY)
        row = r["rows"][0]
        self.assertEqual(row["vendor_cost_ticks"], 361, "the vendor's own number was dropped")
        self.assertNotEqual(row["est_cost_usd"], 361, "ticks were silently treated as dollars")
        self.assertLess(row["est_cost_usd"], 1.0, "ticks leaked into the dollar estimate")


class TestLiveGrokResponse(unittest.TestCase):
    """GOLDEN FIXTURE: the verbatim xAI response from the live NFLX run of 2026-07-17.

    Every synthetic fixture in this file was written by the same mind that wrote the code, so both
    share its blind spots. This one came off the wire. It immediately found two bugs the 19 tests
    above could not:
      1. cached_tokens is nested under input_tokens_details. The code read u["cached_tokens"] -- a
         field xAI never sends -- so 60,288 cached tokens billed at $2.00 instead of $0.50.
      2. 13 server-side x_search calls, $0.065, were invisible to a token-only meter: 64% of the
         stage's bill. Not an imprecision, a structural blindness.
    Net effect of the two, which partly cancelled: +15.3% -- the worst shape an error can take,
    because the total still looks plausible.
    """

    REAL = {"model": "grok-4.5", "service_tier": "default", "usage": {
        "input_tokens": 84348, "input_tokens_details": {"cached_tokens": 60288},
        "output_tokens": 3885, "output_tokens_details": {"reasoning_tokens": 2365},
        "total_tokens": 88233, "num_sources_used": 0, "num_server_side_tools_used": 13,
        "cost_in_usd_ticks": 1665740000,
        "server_side_tool_usage_details": {"web_search_calls": 0, "x_search_calls": 13,
                                           "code_interpreter_calls": 0}}}

    def _row(self):
        return pricing.cost_ledger([{"stage": "Stage 3 Grok", "provider": "xai",
                                     "model": "grok-4.5", "response": self.REAL}], TODAY)["rows"][0]

    def test_cached_tokens_are_read_from_where_xai_actually_puts_them(self):
        self.assertEqual(self._row()["cache_read_tokens"], 60288,
                         "cached tokens missed -> they bill at 4x the correct rate")

    def test_server_side_tool_calls_are_counted(self):
        r = self._row()
        self.assertEqual(r["tool_calls"], 13)
        self.assertEqual(r["tool_breakdown"], {"x_search_calls": 13})

    def test_our_formula_reconciles_to_the_vendor_EXACTLY(self):
        """The whole price table for grok-4.5, validated against a real invoice line:
             24,060 fresh @ $2.00/M + 60,288 cached @ $0.50/M + 3,885 out @ $6.00/M
             + 13 x_search @ $0.005 = $0.166574 = 1,665,740,000 ticks.
        If this ever fails, either a rate moved or xAI changed its billing."""
        self.assertAlmostEqual(self._row()["est_cost_own_formula_usd"], 0.166574, places=6)

    def test_the_tick_unit_is_1e_minus_10(self):
        """Derived, not guessed: an exact match across four independent terms."""
        self.assertEqual(pricing.TICK_USD, 1e-10)
        self.assertAlmostEqual(1665740000 * pricing.TICK_USD, 0.166574, places=6)

    def test_the_vendor_figure_wins_over_our_estimate(self):
        r = self._row()
        self.assertEqual(r["cost_status"], "vendor_reported")
        self.assertAlmostEqual(r["est_cost_usd"], r["vendor_cost_usd"], places=6)

    def test_a_stale_rate_is_caught_by_the_vendor_disagreeing(self):
        """The self-check. Corrupt the rate and the ledger must notice the vendor contradicting
        it -- so the price table is validated on every real run, not when someone remembers."""
        saved = pricing.PRICES["grok-4.5"]["output"]
        pricing.PRICES["grok-4.5"]["output"] = 99.0
        try:
            r = pricing.cost_ledger([{"stage": "Stage 3 Grok", "provider": "xai",
                                      "model": "grok-4.5", "response": self.REAL}], TODAY)
            self.assertEqual(r["rows"][0]["cost_status"], "vendor_reported_estimate_drifted")
            self.assertTrue(r["totals"]["rates_contradicted_by_vendor"])
            self.assertAlmostEqual(r["rows"][0]["est_cost_usd"], 0.166574, places=6,
                                   msg="the vendor number must still win")
        finally:
            pricing.PRICES["grok-4.5"]["output"] = saved

    def test_reasoning_tokens_are_inside_output_not_added(self):
        """Proven by the reconciliation: pricing 3,885 output (which CONTAINS 2,365 reasoning)
        matched the vendor to the tick. Adding them would have overshot."""
        self.assertEqual(self._row()["output_tokens"], 3885)


class TestRoute(unittest.TestCase):
    def test_cost_route_never_500s(self):
        c = app.app.test_client()
        for body in (None, {"stages": "garbage"}, {"stages": [{"provider": "nope"}]}, {}):
            r = c.post("/cost", json=body) if body is not None else c.post("/cost")
            self.assertEqual(r.status_code, 200, "a billing section must never take the report down")

    def test_cost_route_is_wired_to_the_ledger(self):
        c = app.app.test_client()
        r = c.post("/cost", json={"today": "2026-07-17", "stages": [
            {"stage": "Stage 6 Arbiter", "provider": "anthropic", "model": "claude-opus-4-8",
             "response": anthropic(1_000_000, 1_000_000)}]})
        self.assertAlmostEqual(r.get_json()["totals"]["est_cost_usd"], 30.0, places=4)


if __name__ == "__main__":
    unittest.main()
