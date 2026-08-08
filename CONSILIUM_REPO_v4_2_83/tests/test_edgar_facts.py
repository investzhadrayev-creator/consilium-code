"""
Regression tests for microservice/edgar_facts.py — the SEC first-source financial layer.

Philosophy under test: EDGAR is primary but NOT flawless. Real filings contain placeholder
zeros and stale period contexts, so this module is "first-source + deterministic sanity gates",
not blind trust. A silently-wrong number is more dangerous than an honest null — several tests
below assert exactly that.

All tests are OFFLINE: they inject a mock companyfacts payload into the module cache, so no
SEC request is made. Fast, free, deterministic.
"""
import time
import unittest

from _support import load_microservice_module

ef = load_microservice_module("edgar_facts")


def facts(us_gaap=None, dei=None):
    out = {"facts": {}}
    if us_gaap:
        out["facts"]["us-gaap"] = us_gaap
    if dei:
        out["facts"]["dei"] = dei
    return out


def usd(rows):
    return {"units": {"USD": rows}}


def shares(rows):
    return {"units": {"shares": rows}}


def row(start, end, val, form="10-K", accn="a1", filed="2025-02-01"):
    r = {"end": end, "val": val, "form": form, "accn": accn, "filed": filed}
    if start:
        r["start"] = start
    return r


class EdgarTestBase(unittest.TestCase):
    def setUp(self):
        # Never let one test's mock leak into another via the module-level caches.
        ef._FACTS_CACHE.clear()
        ef._CONCEPT_CACHE.clear()
        # Pre-cache the shares_current concept lookups as "absent" so nothing reaches the
        # network (which would otherwise cost ~4s of connection timeouts per run). Tests that
        # specifically exercise the companyconcept fallback overwrite these afterwards.
        for tax, tag in ef.SHARES_CURRENT:
            ef._CONCEPT_CACHE[("TEST", tax, tag)] = (time.time(), None)

    def run_with(self, mock, cik="TEST", as_of=None):
        ef._FACTS_CACHE[cik] = (time.time(), mock)
        return ef.edgar_facts(cik=cik, as_of=as_of)


class TestSeriesExtraction(EdgarTestBase):

    def test_quarterly_rows_excluded_from_annual_series(self):
        """A 10-Q row must never contaminate the annual series used for CAGR."""
        mock = facts({"Revenues": usd([
            row("2024-01-01", "2024-12-31", 150),
            row("2024-10-01", "2024-12-31", 40, form="10-Q", accn="q1"),  # quarterly
        ])})
        r = self.run_with(mock)
        self.assertEqual(r["revenue"], [{"end": "2024-12-31", "val": 150}])

    def test_restatement_dedupe_keeps_latest_filed(self):
        """Same fiscal year filed twice -> the LATER filing wins (restatement-safe)."""
        mock = facts({"Revenues": usd([
            row("2024-01-01", "2024-12-31", 148, accn="old", filed="2024-11-01"),
            row("2024-01-01", "2024-12-31", 150, accn="new", filed="2025-02-01"),
        ])})
        r = self.run_with(mock)
        self.assertEqual(r["revenue"], [{"end": "2024-12-31", "val": 150}])

    def test_series_is_oldest_first(self):
        """scenario_f/_cagr_series relies on [0] being the oldest point."""
        mock = facts({"Revenues": usd([
            row("2025-01-01", "2025-12-31", 200, accn="c"),
            row("2023-01-01", "2023-12-31", 100, accn="a"),
            row("2024-01-01", "2024-12-31", 150, accn="b"),
        ])})
        r = self.run_with(mock)
        self.assertEqual([p["end"] for p in r["revenue"]],
                         ["2023-12-31", "2024-12-31", "2025-12-31"])

    def test_audit_trail_carries_accession_and_filed_date(self):
        """Every number must be traceable to a filing — this is what makes it first-source."""
        mock = facts({"Revenues": usd([row("2024-01-01", "2024-12-31", 150, accn="0001-24-01")])})
        r = self.run_with(mock)
        self.assertEqual(r["revenue_audit"][0]["accn"], "0001-24-01")
        self.assertEqual(r["revenue_audit"][0]["filed"], "2025-02-01")


class TestGapFill(EdgarTestBase):
    """v2 regression (ASTS): v1 took the FIRST tag that had ANY data, so a year reported under
    a lower-priority alias was silently dropped — leaving a hole in the series that corrupted
    CAGR. Each year must now be filled by the highest-priority tag that reports it."""

    def test_year_only_under_secondary_tag_is_recovered(self):
        mock = facts({
            "RevenueFromContractWithCustomerExcludingAssessedTax": usd([
                row("2022-01-01", "2022-12-31", 100, accn="a"),
                row("2024-01-01", "2024-12-31", 150, accn="c"),
            ]),
            # 2023 exists ONLY here (ASTS's real pattern)
            "RevenueFromContractWithCustomerIncludingAssessedTax": usd([
                row("2023-01-01", "2023-12-31", 130, accn="b"),
            ]),
        })
        r = self.run_with(mock)
        self.assertEqual([p["end"] for p in r["revenue"]],
                         ["2022-12-31", "2023-12-31", "2024-12-31"],
                         "2023 was dropped — gap-fill regressed")

    def test_field_sources_lists_every_tag_used(self):
        mock = facts({
            "RevenueFromContractWithCustomerExcludingAssessedTax": usd([row("2022-01-01", "2022-12-31", 100)]),
            "RevenueFromContractWithCustomerIncludingAssessedTax": usd([row("2023-01-01", "2023-12-31", 130)]),
        })
        r = self.run_with(mock)
        self.assertEqual(len(r["_field_sources"]["revenue"]), 2)

    def test_higher_priority_tag_wins_when_both_report_a_year(self):
        mock = facts({
            "RevenueFromContractWithCustomerExcludingAssessedTax": usd([row("2024-01-01", "2024-12-31", 150)]),
            "Revenues": usd([row("2024-01-01", "2024-12-31", 999)]),   # lower priority
        })
        r = self.run_with(mock)
        self.assertEqual(r["revenue"][0]["val"], 150)


class TestSanityGates(EdgarTestBase):
    """EDGAR's own data quality problems — caught deterministically, surfaced visibly."""

    def test_placeholder_zero_revenue_is_dropped_not_used(self):
        """v3 regression (ASTS 2023): a literal 0 for revenue at an operating company is a
        filler tag, not a fact. Feeding it corrupts CAGR and burn_multiple."""
        mock = facts({"Revenues": usd([
            row("2022-01-01", "2022-12-31", 13825000, accn="a"),
            row("2023-01-01", "2023-12-31", 0, accn="z"),          # placeholder
            row("2025-01-01", "2025-12-31", 70918000, accn="d"),
        ])})
        r = self.run_with(mock)
        self.assertNotIn("2023-12-31", [p["end"] for p in r["revenue"]])
        self.assertEqual(r["_flags"]["dropped_zero"]["revenue"], ["2023-12-31"])

    def test_dropped_zero_is_visible_not_silent(self):
        """Dropping data silently would be its own failure mode."""
        mock = facts({"Revenues": usd([
            row("2023-01-01", "2023-12-31", 0),
            row("2024-01-01", "2024-12-31", 100),
        ])})
        r = self.run_with(mock)
        self.assertIn("dropped_zero", r["_flags"])

    def test_stale_context_is_flagged_when_year_duplicates_another(self):
        """v3 regression (ASTS): FY2024 was reported as 13.825M — identical to FY2022 and 5x
        below FY2025's 70.9M. A stale comparative context, i.e. a silently wrong number."""
        mock = facts({"Revenues": usd([
            row("2022-01-01", "2022-12-31", 13825000, accn="a", filed="2024-04-01"),
            row("2024-01-01", "2024-12-31", 13825000, accn="c", filed="2025-03-03"),  # stale
            row("2025-01-01", "2025-12-31", 70918000, accn="d", filed="2026-03-02"),
        ])})
        r = self.run_with(mock)
        self.assertEqual(r["_flags"]["suspect_stale_context"]["revenue"], ["2024-12-31"])

    def test_stale_value_is_flagged_but_NOT_dropped(self):
        """Deliberate: an exact duplicate could be legitimate. Flag for the auditor, don't
        silently delete — the analyst decides."""
        mock = facts({"Revenues": usd([
            row("2022-01-01", "2022-12-31", 13825000, filed="2024-04-01"),
            row("2024-01-01", "2024-12-31", 13825000, filed="2025-03-03"),
            row("2025-01-01", "2025-12-31", 70918000, filed="2026-03-02"),
        ])})
        r = self.run_with(mock)
        self.assertIn("2024-12-31", [p["end"] for p in r["revenue"]])

    def test_smooth_series_is_not_falsely_flagged_as_stale(self):
        """A flat/slow-growing series must not trip the stale detector."""
        mock = facts({"Revenues": usd([
            row("2023-01-01", "2023-12-31", 100),
            row("2024-01-01", "2024-12-31", 100),   # duplicate, but neighbours are close
            row("2025-01-01", "2025-12-31", 105),
        ])})
        r = self.run_with(mock)
        self.assertNotIn("suspect_stale_context", r["_flags"])

    def test_missing_field_is_null_with_a_missing_trail_never_invented(self):
        r = self.run_with(facts({"Revenues": usd([row("2024-01-01", "2024-12-31", 100)])}))
        self.assertIsNone(r["ocf"])
        self.assertIn("ocf", r["_missing"])


class TestDebtReconciliationGate(EdgarTestBase):
    """v4.2.32 mandate (b). The debt reconciliation gate, pinned on the two real cases that pull in
    OPPOSITE directions — so a future 'simplification' cannot satisfy one by breaking the other."""

    def test_MA_case_components_beat_a_broken_tag(self):
        """MA 2026-07-22: LongTermDebt returned $21M while the components said $19.0B (99.9%
        divergence). The components must win and the reading must be marked uncertain."""
        mock = facts({
            "LongTermDebt":            usd([row(None, "2026-03-31", 21000000, form="10-Q")]),
            "LongTermDebtNoncurrent":  usd([row(None, "2026-03-31", 17000000000, form="10-Q")]),
            "LongTermDebtCurrent":     usd([row(None, "2026-03-31", 2000000000, form="10-Q")]),
        })
        r = self.run_with(mock)
        self.assertEqual(r["total_debt"], 19000000000,
                         "components sum ($19.0B) must beat the broken $21M tag")
        self.assertTrue(r["_flags"].get("total_debt_divergence"),
                        "a 99.9% divergence must set total_debt_divergence TRUE (it read false before)")
        self.assertTrue(r["_flags"].get("debt_uncertain"),
                        "a disputed leverage reading must be marked uncertain")

    def test_NFLX_case_fuller_tag_survives_the_gate(self):
        """NFLX: LongTermDebt 21.86B (incl. current maturities) vs noncurrent-only 11.83B. The
        components sum reads LOWER because it is a PART — it must NOT displace the fuller figure.
        This is the v4.2.23 defect; the gate must not reintroduce it."""
        mock = facts({
            "LongTermDebt":            usd([row(None, "2026-03-31", 21857087000, form="10-Q")]),
            "LongTermDebtNoncurrent":  usd([row(None, "2026-03-31", 11825548000, form="10-Q")]),
        })
        r = self.run_with(mock)
        self.assertEqual(r["total_debt"], 21857087000,
                         "the fuller LongTermDebt must survive; components are only a part here")

    def test_gate_silent_when_sources_agree(self):
        mock = facts({
            "LongTermDebt":            usd([row(None, "2026-03-31", 19000000000, form="10-Q")]),
            "LongTermDebtNoncurrent":  usd([row(None, "2026-03-31", 17500000000, form="10-Q")]),
            "LongTermDebtCurrent":     usd([row(None, "2026-03-31", 1500000000, form="10-Q")]),
        })
        r = self.run_with(mock)
        self.assertEqual(r["total_debt"], 19000000000)
        self.assertFalse(r["_flags"].get("debt_uncertain"),
                         "agreeing sources must not raise the uncertainty flag")

    def test_actual_tags_are_listed_for_audit(self):
        """v4.2.33 mandate (1): the composition must be auditable by TAG, not by label. §3 v1.5
        semantics — total_debt is the FULL long-term debt including current maturities, so a
        components sum is only equivalent when BOTH parts exist; say so explicitly."""
        mock = facts({
            "LongTermDebt":            usd([row(None, "2026-03-31", 21857087000, form="10-Q")]),
            "LongTermDebtNoncurrent":  usd([row(None, "2026-03-31", 11825548000, form="10-Q")]),
        })
        r = self.run_with(mock)
        tags = r.get("debt_components_tags") or {}
        self.assertEqual(tags.get("full_long_term_debt"), "LongTermDebt")
        self.assertEqual(tags.get("noncurrent"), "LongTermDebtNoncurrent")
        self.assertIsNone(tags.get("current_maturities"), "NFLX has no current-maturities tag")
        self.assertFalse(tags.get("components_complete"),
                         "without the current-maturities tag the components sum is INCOMPLETE")
        self.assertIn("debt_components_incomplete", r["_flags"],
                      "incompleteness by construction must be stated, not implied")

    def test_double_count_guard_flags_suspect_composition(self):
        """v4.2.33 mandate (2): a components sum more than DOUBLE the chosen figure is more likely
        the same debt counted twice than a real under-report — flag the composition as suspect."""
        mock = facts({
            "LongTermDebt":            usd([row(None, "2026-03-31", 21000000, form="10-Q")]),
            "LongTermDebtNoncurrent":  usd([row(None, "2026-03-31", 17000000000, form="10-Q")]),
            "LongTermDebtCurrent":     usd([row(None, "2026-03-31", 2000000000, form="10-Q")]),
        })
        r = self.run_with(mock)
        self.assertIn("debt_components_suspect", r["_flags"],
                      "a >2x components/chosen ratio must flag the composition")
        # the gate still prefers the larger reading — the flag informs, it does not block
        self.assertEqual(r["total_debt"], 19000000000)

    def test_no_suspect_flag_on_normal_composition(self):
        mock = facts({
            "LongTermDebt":            usd([row(None, "2026-03-31", 19000000000, form="10-Q")]),
            "LongTermDebtNoncurrent":  usd([row(None, "2026-03-31", 17500000000, form="10-Q")]),
            "LongTermDebtCurrent":     usd([row(None, "2026-03-31", 1500000000, form="10-Q")]),
        })
        r = self.run_with(mock)
        self.assertNotIn("debt_components_suspect", r["_flags"])


class TestDebtAndShares(EdgarTestBase):

    def test_total_debt_is_sum_of_components_and_exposes_them(self):
        """Verified against ASTS's real filing: LT 2.963B + current 8.2M = 2.972B. The
        components are exposed so a suspicious total can be audited, not just trusted."""
        mock = facts({
            "LongTermDebtNoncurrent": usd([row(None, "2026-03-31", 2963296000, form="10-Q")]),
            "LongTermDebtCurrent": usd([row(None, "2026-03-31", 8236000, form="10-Q")]),
        })
        r = self.run_with(mock)
        self.assertEqual(r["total_debt"], 2971532000)
        self.assertEqual(r["long_term_debt"], 2963296000)
        self.assertEqual(r["current_portion_debt"], 8236000)

    def test_partial_debt_is_flagged_as_possibly_understated(self):
        mock = facts({"LongTermDebtNoncurrent": usd([row(None, "2025-12-31", 500)])})
        r = self.run_with(mock)
        self.assertIn("total_debt_partial", r["_flags"])

    def test_NFLX_full_longtermdebt_beats_noncurrent_only(self):
        """v4.2.23 (BACKLOG #5), pinned on NFLX's real facts. Both tags are present:
        LongTermDebt (full, incl. current maturities) = 21.857B, and LongTermDebtNoncurrent
        (a PART) = 11.826B. The pre-fix code took the noncurrent PART as total (D/E 0.44) while
        the full figure (D/E 0.82) sat unread. total_debt is DEFINED as the full long-term debt,
        so the full tag must win and the divergence must be recorded — not silently dropped."""
        mock = facts({
            "LongTermDebt":            usd([row(None, "2026-03-31", 21857087000, form="10-Q")]),
            "LongTermDebtNoncurrent":  usd([row(None, "2026-03-31", 11825548000, form="10-Q")]),
        })
        r = self.run_with(mock)
        self.assertEqual(r["total_debt"], 21857087000,
                         "the full LongTermDebt (incl. current portion) must be total_debt, "
                         "not the noncurrent-only part")
        self.assertEqual(r["_flags"]["total_debt_computed"], "LongTermDebt")
        self.assertIn("long_term_debt_full_vs_noncurrent", r["_flags"],
                      "the 21.86B-vs-11.83B divergence must be recorded, never silently resolved")
        self.assertNotIn("total_debt_partial", r["_flags"],
                         "a full figure is present — nothing is partial or understated here")

    def test_full_longtermdebt_preferred_even_without_a_current_tag(self):
        """Negative control for the fix: when ONLY the full LongTermDebt exists (no current tag
        at all), it must still be taken whole — the fix must not regress into demanding a current
        component that a full figure already contains."""
        mock = facts({"LongTermDebt": usd([row(None, "2026-03-31", 21857087000, form="10-Q")])})
        r = self.run_with(mock)
        self.assertEqual(r["total_debt"], 21857087000)
        self.assertNotIn("total_debt_partial", r["_flags"])

    def test_noncurrent_only_still_understates_honestly_when_no_full_tag(self):
        """The OTHER side of the negative control: if the full tag is genuinely absent and we
        have only the noncurrent part, we must fall to path-2 and FLAG partial — never invent a
        full figure. This is the case the old code handled; it must keep working."""
        mock = facts({"LongTermDebtNoncurrent": usd([row(None, "2026-03-31", 11825548000, form="10-Q")])})
        r = self.run_with(mock)
        self.assertEqual(r["total_debt"], 11825548000)
        self.assertIn("total_debt_partial", r["_flags"])

    def test_shares_current_falls_back_to_companyconcept_when_dei_absent(self):
        """v3 regression (ASTS): the dei block is entirely missing from companyfacts for some
        filers, so a separate companyconcept call is required."""
        mock = facts({"Revenues": usd([row("2024-01-01", "2024-12-31", 100)])})  # no dei
        ef._CONCEPT_CACHE[("TEST", "dei", "EntityCommonStockSharesOutstanding")] = (
            time.time(), {"shares": [row(None, "2026-04-30", 320000000, form="10-Q")]})
        r = self.run_with(mock)
        self.assertEqual(r["shares_current"], 320000000)

    def test_shares_current_proxies_to_diluted_when_unavailable_and_flags_it(self):
        """ASTS has no dei anywhere. Proxying to the latest weighted-avg diluted count is
        acceptable for this non-critical field — but must be labelled, never passed off as
        the real cover-page count."""
        mock = facts({"WeightedAverageNumberOfDilutedSharesOutstanding": shares([
            row("2025-01-01", "2025-12-31", 255982592)])})
        ef._CONCEPT_CACHE[("TEST", "dei", "EntityCommonStockSharesOutstanding")] = (time.time(), None)
        ef._CONCEPT_CACHE[("TEST", "us-gaap", "CommonStockSharesOutstanding")] = (time.time(), None)
        r = self.run_with(mock)
        self.assertEqual(r["shares_current"], 255982592)
        self.assertIn("shares_current_proxied", r["_flags"])
        self.assertNotIn("shares_current", r["_missing"])

    def test_cash_excludes_restricted_and_says_so(self):
        mock = facts({
            "CashAndCashEquivalentsAtCarryingValue": usd([row(None, "2025-12-31", 3030000000)]),
            "RestrictedCashAndCashEquivalents": usd([row(None, "2025-12-31", 428400000)]),
        })
        r = self.run_with(mock)
        self.assertEqual(r["cash"], 3030000000)
        self.assertEqual(r["restricted_cash"], 428400000)
        self.assertIn("cash_note", r["_flags"])


class TestConfirmedSplits(EdgarTestBase):
    """v4: the ONLY positive evidence of a real stock split is RETROACTIVE RESTATEMENT — a
    later 10-K re-reports an earlier year's share count at the post-split value. Organic
    dilution is never restated. A 'clean ratio' alone is NOT evidence: PLTR's ~2x jump in 2021
    was SBC/warrant dilution, and applying it as a split would have corrupted the whole
    historical per-share series."""

    def test_real_split_is_confirmed_via_restatement(self):
        """Apple's real pattern: FY2013 filed at 925M, later re-reported at ~6.5B (7:1).

        Note the fiscal-year dates: AAPL's FY2013 runs Sep-2012 -> Sep-2013. Duration matters —
        the annual filter drops periods under 300 days, so a mock with a calendar-year start
        would be silently skipped."""
        mock = facts({"WeightedAverageNumberOfDilutedSharesOutstanding": shares([
            row("2012-09-30", "2013-09-28", 925331000, accn="s1", filed="2013-10-30"),
            row("2012-09-30", "2013-09-28", 6521634000, accn="s3", filed="2015-10-28"),  # restated
        ])})
        r = self.run_with(mock)
        conf = r["_flags"]["confirmed_splits"]
        self.assertEqual(len(conf), 1)
        self.assertEqual(conf[0]["end"], "2013-09-28")
        self.assertEqual(conf[0]["factor"], 7)

    def test_split_confirmed_when_BOTH_basic_and_diluted_tags_report(self):
        """v4.2.3 regression — the live-NFLX shape the smoke test caught on 2026-07-17.

        Real filers report basic AND diluted weighted averages, which differ by the dilution
        wedge (~1-2%). Until v4.2.3 the detector pooled ALL tags into one bucket per end-date,
        so lo = basic pre-split and hi = diluted post-split, and a clean 10.00x split read as
        ~10.17x — outside the 1% tolerance, hence NOT CONFIRMED, deterministically, on every
        live run. Every fixture in this class used a single tag, so the suite stayed green:
        the same single-tag-mock disease as MOCK_RESULT in test_render_tables (see CLAUDE.md,
        'A green suite is not coverage'). Restatement is WITHIN-tag evidence; this test pins
        that the detector never compares values across tags."""
        mock = facts({
            "WeightedAverageNumberOfDilutedSharesOutstanding": shares([
                row("2024-01-01", "2024-12-31", 437000000, accn="d1", filed="2025-01-27"),
                row("2024-01-01", "2024-12-31", 4370000000, accn="d2", filed="2026-01-26"),  # restated x10
            ]),
            "WeightedAverageNumberOfSharesOutstandingBasic": shares([
                row("2024-01-01", "2024-12-31", 429500000, accn="b1", filed="2025-01-27"),
                row("2024-01-01", "2024-12-31", 4295000000, accn="b2", filed="2026-01-26"),  # restated x10
            ]),
        })
        r = self.run_with(mock)
        conf = r["_flags"].get("confirmed_splits")
        self.assertIsNotNone(conf, "split went unconfirmed because basic and diluted values "
                                   "were pooled into one ratio (the v4.2.3 bug)")
        self.assertEqual(len(conf), 1)
        self.assertEqual(conf[0]["end"], "2024-12-31")
        self.assertEqual(conf[0]["factor"], 10)
        # the confirming evidence must name its tag — the basis travels with the number
        self.assertIn(conf[0]["tag"], ("WeightedAverageNumberOfDilutedSharesOutstanding",
                                       "WeightedAverageNumberOfSharesOutstandingBasic"))

    def test_cross_tag_wedge_alone_is_never_a_split(self):
        """The inverse pin: basic-vs-diluted difference within one period (no restatement in
        EITHER tag) must never be read as evidence of anything. Two tags, one filing each,
        values differing by the dilution wedge — if pooling ever comes back, whichever clean
        ratio it happens to hit must not confirm."""
        mock = facts({
            "WeightedAverageNumberOfDilutedSharesOutstanding": shares([
                row("2024-01-01", "2024-12-31", 860000000, accn="d1", filed="2025-01-27"),
            ]),
            "WeightedAverageNumberOfSharesOutstandingBasic": shares([
                row("2024-01-01", "2024-12-31", 430000000, accn="b1", filed="2025-01-27"),  # exactly 2x
            ]),
        })
        r = self.run_with(mock)
        self.assertNotIn("confirmed_splits", r["_flags"],
                         "a basic/diluted wedge across tags was confirmed as a split")

    def test_organic_dilution_is_NOT_confirmed_as_a_split(self):
        """PLTR's real pattern: 979M -> 1923M across years, each reported ONCE, never
        restated. Clean ~2x ratio, but it is dilution."""
        mock = facts({"WeightedAverageNumberOfDilutedSharesOutstanding": shares([
            row("2019-01-01", "2019-12-31", 979330000, accn="d1", filed="2020-02-01"),
            row("2020-01-01", "2020-12-31", 1923617000, accn="d2", filed="2021-02-01"),
        ])})
        r = self.run_with(mock)
        self.assertNotIn("confirmed_splits", r["_flags"],
                         "organic dilution was wrongly confirmed as a split")

    def test_restatement_at_a_non_split_ratio_is_not_confirmed(self):
        """A small revision (e.g. 1.05x) is a restatement, not a split."""
        mock = facts({"WeightedAverageNumberOfDilutedSharesOutstanding": shares([
            row("2024-01-01", "2024-12-31", 1000000, accn="a", filed="2025-02-01"),
            row("2024-01-01", "2024-12-31", 1050000, accn="b", filed="2026-02-01"),
        ])})
        r = self.run_with(mock)
        self.assertNotIn("confirmed_splits", r["_flags"])

    def test_multiple_real_splits_are_all_found(self):
        """AAPL genuinely shows both the 2014 7:1 and the 2020 4:1 in its restatement history."""
        mock = facts({"WeightedAverageNumberOfDilutedSharesOutstanding": shares([
            row("2012-09-30", "2013-09-28", 925331000, accn="a", filed="2013-10-30"),
            row("2012-09-30", "2013-09-28", 6521634000, accn="b", filed="2015-10-28"),
            row("2017-10-01", "2018-09-29", 5000000000, accn="c", filed="2018-11-05"),
            row("2017-10-01", "2018-09-29", 20000000000, accn="d", filed="2020-10-30"),
        ])})
        r = self.run_with(mock)
        factors = sorted(c["factor"] for c in r["_flags"]["confirmed_splits"])
        self.assertEqual(factors, [4, 7])


class TestErrorHandling(EdgarTestBase):
    """The module must never throw — a failure returns an error trail the pipeline can read."""

    def test_unknown_ticker_returns_error_not_exception(self):
        # Pre-populate the CIK map so _resolve_cik does NOT hit the network: the whole suite
        # must stay offline, fast and free.
        ef._CIK_CACHE.clear()
        ef._CIK_CACHE["AAPL"] = "0000320193"
        try:
            r = ef.edgar_facts(ticker="___NOSUCHTICKER___", cik=None)
            self.assertIsInstance(r, dict)
            self.assertIn("cik", r["_errors"])
        finally:
            ef._CIK_CACHE.clear()


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestRawTagsDiagnostic(EdgarTestBase):
    """v4.2.44: read-only diagnostic that exposes WHICH tag filled WHICH fiscal year. The assembled
    series cannot answer that — `_annual_merged` keeps only the SET of tags used, so MA's revenue
    series stitched from three tags with a ~1.6x step was detectable only through the margin
    series. This endpoint returns the un-merged truth."""

    def test_year_to_tag_map_exposes_tag_switching(self):
        mock = facts({
            "SalesRevenueNet": usd([row("2016-01-01", "2016-12-31", 100, form="10-K"),
                                    row("2017-01-01", "2017-12-31", 110, form="10-K")]),
            "Revenues":        usd([row("2018-01-01", "2018-12-31", 190, form="10-K")]),
            "RevenueFromContractWithCustomerExcludingAssessedTax":
                               usd([row("2022-01-01", "2022-12-31", 130, form="10-K")]),
        })
        ef._FACTS_CACHE["TEST"] = (time.time(), mock)
        r = ef.raw_tags(cik="TEST",
                        tags=["RevenueFromContractWithCustomerExcludingAssessedTax",
                              "Revenues", "SalesRevenueNet"])
        y2t = r["year_to_tags"]
        self.assertEqual(y2t.get("2016"), ["SalesRevenueNet"])
        self.assertEqual(y2t.get("2018"), ["Revenues"])
        self.assertEqual(y2t.get("2022"), ["RevenueFromContractWithCustomerExcludingAssessedTax"])
        self.assertNotEqual(y2t.get("2016"), y2t.get("2018"),
                            "the map must make a tag switch visible year by year")

    def test_values_carry_accession_and_filed(self):
        mock = facts({"Revenues": usd([row("2024-01-01", "2024-12-31", 200, form="10-K",
                                           accn="0000-24-1", filed="2025-02-01")])})
        ef._FACTS_CACHE["TEST"] = (time.time(), mock)
        r = ef.raw_tags(cik="TEST", tags=["Revenues"])
        pt = r["tags"]["Revenues"][0]
        self.assertEqual(pt["accession"], "0000-24-1")
        self.assertEqual(pt["filed"], "2025-02-01")
        self.assertEqual(pt["value"], 200)

    def test_no_network_degrades_honestly(self):
        r = ef.raw_tags(ticker="NOSUCHTICKER_XYZ")
        self.assertIn("_errors", r)
        self.assertEqual(r["tags"], {}, "no invented data when the source is unreachable")


class TestRevenueTagIntegrity(EdgarTestBase):
    """v4.2.45 (mandate BBB). The MA defect: EDGAR carried BOTH `Revenues` (net) and
    `RevenueFromContract…` (gross) for 2018-2021, priority took gross, from 2022 only net remained
    → phantom -25.5% step at the seam → 5y CAGR 6.78% instead of 16.47%. Main rule: a single tag
    spanning the whole range wins outright — no stitching, no conflict resolution needed."""

    def _ma_like(self):
        return facts({
            "RevenueFromContractWithCustomerExcludingAssessedTax": usd([
                row("2018-01-01", "2018-12-31", 21831e6, form="10-K"),
                row("2019-01-01", "2019-12-31", 24980e6, form="10-K"),
                row("2020-01-01", "2020-12-31", 23616e6, form="10-K"),
                row("2021-01-01", "2021-12-31", 29845e6, form="10-K")]),
            "Revenues": usd([
                row("2018-01-01", "2018-12-31", 14950e6, form="10-K"),
                row("2019-01-01", "2019-12-31", 16883e6, form="10-K"),
                row("2020-01-01", "2020-12-31", 15301e6, form="10-K"),
                row("2021-01-01", "2021-12-31", 18884e6, form="10-K"),
                row("2022-01-01", "2022-12-31", 22237e6, form="10-K"),
                row("2023-01-01", "2023-12-31", 25098e6, form="10-K")]),
        })

    def test_single_tag_covering_the_range_wins_no_stitching(self):
        r = self.run_with(self._ma_like())
        vals = {p["end"][:4]: p["val"] for p in r["revenue"]}
        self.assertEqual(vals["2020"], 15301e6,
                         "the net tag spans the whole range -> it must be used ALONE (was 23616e6)")
        self.assertEqual(vals["2021"], 18884e6)
        self.assertEqual(r["_field_sources"]["revenue"], ["Revenues"],
                         "exactly ONE tag may appear in sources when it covers the range")
        self.assertNotIn("series_tag_mixed", r["_flags"],
                         "a single-tag series is not mixed")

    def test_window_coverage_not_whole_range_decides_fitness(self):
        """v4.2.53 (mandate NNN). THE REAL MA SHAPE: `Revenues` covers 18 of 19 years — 2015 is
        absent — and the previous "covers the whole range" rule therefore never fired, so a full
        paid re-run still carried the contaminated 6.78% anchor. Fitness is judged on the WINDOWS
        THE ANCHOR USES (last 3 and 5 years), not on the whole series: a hole outside every window
        cannot corrupt an anchor computed inside them."""
        def blk(years):
            return usd([row("%d-01-01" % y, "%d-12-31" % y, v * 1e9, form="10-K",
                            accn="a%d" % y, filed="%d-02-01" % (y + 1)) for y, v in years])
        mock = facts({
            "Revenues": blk([(2018, 14.95), (2019, 16.88), (2020, 15.30), (2021, 18.88),
                             (2022, 22.24), (2023, 25.10), (2024, 28.17), (2025, 32.79)]),
            "SalesRevenueNet": blk([(2015, 9.67), (2016, 10.78), (2017, 12.50)]),
            "RevenueFromContractWithCustomerExcludingAssessedTax":
                blk([(2018, 21.83), (2019, 24.98), (2020, 23.62), (2021, 29.85)]),
        })
        r = self.run_with(mock)
        vals = {p["end"][:4]: round(p["val"] / 1e9, 2) for p in r["revenue"]}
        self.assertEqual(r["_field_sources"]["revenue"], ["Revenues"],
                         "the tag covering BOTH anchor windows must win alone")
        self.assertEqual(vals["2020"], 15.30, "the net figure must survive (gross was 23.62)")
        self.assertEqual(vals["2021"], 18.88, "the net figure must survive (gross was 29.85)")
        self.assertNotIn("2015", vals,
                         "a year outside every window stays ABSENT — gaps are never filled")

    def test_a_gap_INSIDE_an_anchor_window_disqualifies_the_tag(self):
        """The mirror case: if the hole falls INSIDE a window the anchor uses, that tag is not fit
        and the code must not silently prefer it."""
        def blk(years):
            return usd([row("%d-01-01" % y, "%d-12-31" % y, v * 1e9, form="10-K",
                            accn="a%d" % y, filed="%d-02-01" % (y + 1)) for y, v in years])
        mock = facts({  # 2023 missing -> breaks both the 3y and 5y windows ending 2025
            "Revenues": blk([(2020, 15.30), (2021, 18.88), (2022, 22.24), (2024, 28.17), (2025, 32.79)]),
        })
        r = self.run_with(mock)
        vals = {p["end"][:4] for p in r["revenue"]}
        self.assertNotIn("2023", vals, "the gap is real and stays visible")
        # the tag is the only one present, so it is still used — but never via the window rule
        self.assertIn("series_tag_mixed", r["_flags"]) if len(r["_field_sources"]["revenue"]) > 1 \
            else self.assertEqual(r["_field_sources"]["revenue"], ["Revenues"])

    def test_tag_conflict_is_reported_even_when_resolved(self):
        r = self.run_with(self._ma_like())
        conf = r["_flags"].get("tag_conflict", {}).get("revenue")
        self.assertTrue(conf, "years reported by two tags with >5% spread must be surfaced")
        y2020 = [c for c in conf if c["end"].startswith("2020")]
        self.assertTrue(y2020, "2020 carried both a net and a gross figure")
        self.assertGreater(y2020[0]["spread_pct"], 30.0)

    def test_audit_points_carry_their_source_tag(self):
        r = self.run_with(self._ma_like())
        self.assertTrue(all("tag" in p for p in r["revenue_audit"]),
                        "every audit point must name the tag it came from (year->tag map)")

    def test_continuity_flags_a_tag_switch_as_a_DEFECT(self):
        """A margin jump that coincides with a TAG BOUNDARY is a data defect (real MA numbers)."""
        import edgar_facts as _ef
        op = [{"end": "%d-12-31" % y, "val": v * 1e9} for y, v in
              [(2020, 8.081), (2021, 10.082), (2022, 12.246), (2023, 14.006)]]
        stitched = [{"end": "%d-12-31" % y, "val": v * 1e9, "tag": t, "unit": "USD",
                     "form": "10-K", "accn": a} for y, v, t, a in
                    [(2020, 23.616, "RevenueFromContractWithCustomerExcludingAssessedTax", "a1"),
                     (2021, 29.845, "RevenueFromContractWithCustomerExcludingAssessedTax", "a1"),
                     (2022, 22.237, "Revenues", "a2"), (2023, 25.098, "Revenues", "a2")]]
        r = _ef._ratio_continuity(op, stitched)
        self.assertEqual(len(r["defects"]), 1, "the 2021->2022 seam must be a DEFECT")
        self.assertTrue(r["defects"][0]["end"].startswith("2022"))
        self.assertNotEqual(r["defects"][0]["tag"], r["defects"][0]["prev_tag"])
        self.assertEqual(r["business_events"], [], "nothing here is a business event")

    def test_provenance_change_beyond_tag_also_makes_a_defect(self):
        """v4.2.47 (mandate): the tag boundary is one member of a set. A unit change (thousands vs
        millions), a restatement under a new accession, or a skipped fiscal year produce the SAME
        step and must be defects too — otherwise a x1000 unit switch lands in business_events."""
        import edgar_facts as _ef
        op = [{"end": "%d-12-31" % y, "val": v * 1e9} for y, v in
              [(2020, 8.081), (2021, 10.082), (2022, 12.246), (2023, 14.006)]]
        unit_switch = [{"end": "%d-12-31" % y, "val": v * 1e9, "tag": "Revenues",
                        "unit": u, "form": "10-K", "accn": a} for y, v, u, a in
                       [(2020, 15.301, "USD", "a1"), (2021, 18.884, "USD", "a1"),
                        (2022, 22237.0, "USD-thousands", "a2"), (2023, 25098.0, "USD-thousands", "a2")]]
        r = _ef._ratio_continuity(op, unit_switch)
        self.assertEqual(len(r["defects"]), 1, "a unit switch must be a DEFECT, not a business event")
        self.assertIn("unit", r["defects"][0]["provenance_changed"])

    def test_year_gap_at_a_jump_is_a_defect(self):
        import edgar_facts as _ef
        rows = [(2019, 12.0, 8.0), (2020, 15.301, 8.081), (2023, 25.098, 3.0)]  # 2021-22 missing
        rev = [{"end": "%d-12-31" % y, "val": r * 1e9, "tag": "Revenues", "unit": "USD",
                "form": "10-K", "accn": "a1"} for y, r, _ in rows]
        op = [{"end": "%d-12-31" % y, "val": o * 1e9} for y, _, o in rows]
        r = _ef._ratio_continuity(op, rev)
        self.assertTrue(any("year_gap" in d["provenance_changed"] for d in r["defects"]),
                        "a jump straddling missing years must be a defect")

    def test_single_tag_jumps_are_business_events_NOT_defects(self):
        """v4.2.46, corrected after the live NFLX check: a threshold alone is NOT a criterion.
        MA's tag switch moved the margin 63%; NFLX moved it 88% (2012 expansion) and 277% (2013
        recovery) with ONE tag throughout — a real business can out-jump a data defect, so no
        threshold separates them. Only coincidence with a tag boundary makes a jump a defect."""
        import edgar_facts as _ef
        rev = {2011: 3204.577, 2012: 3609.282, 2013: 4374.562, 2014: 5504.656}
        opi = {2011: 376.068, 2012: 49.992, 2013: 228.347, 2014: 402.648}
        r = _ef._ratio_continuity(
            [{"end": "%d-12-31" % y, "val": opi[y] * 1e6} for y in sorted(opi)],
            [{"end": "%d-12-31" % y, "val": rev[y] * 1e6, "tag": "Revenues", "unit": "USD",
              "form": "10-K", "accn": "a%d" % y} for y in sorted(rev)])
        self.assertEqual(r["provenance_unknown"], [],
                         "the fixture must carry FULL provenance — otherwise 0 defects proves "
                         "nothing but missing data (v4.2.48)")
        self.assertEqual(r["defects"], [],
                         "a single-tag series must NEVER raise a defect, however large the jump")
        self.assertGreaterEqual(len(r["business_events"]), 2, "the real swings stay visible")
        self.assertGreater(max(e["jump_pct"] for e in r["business_events"]), 63.0,
                           "this fixture must contain a jump BIGGER than MA's defect (63%)")

    def test_accession_alone_is_a_cosignal_not_a_defect(self):
        """v4.2.48, measured on live data: accession changes on 76% of MA's year seams and 89% of
        NFLX's, because each year rides whichever 10-K covers it. Treating it as a primary signal
        would fire on ordinary report coverage — the 'gate that always fires' failure mode."""
        import edgar_facts as _ef
        op = [{"end": "%d-12-31" % y, "val": v * 1e9} for y, v in
              [(2020, 8.081), (2021, 10.082), (2022, 4.0), (2023, 14.006)]]
        rev = [{"end": "%d-12-31" % y, "val": v * 1e9, "tag": "Revenues", "unit": "USD",
                "form": "10-K", "accn": a} for y, v, a in
               [(2020, 15.301, "a1"), (2021, 18.884, "a2"), (2022, 22.237, "a3"), (2023, 25.098, "a4")]]
        r = _ef._ratio_continuity(op, rev)
        self.assertEqual(r["defects"], [],
                         "a changed accession ALONE must never make a defect")
        self.assertTrue(r["business_events"], "the jumps stay visible as business events")
        self.assertIn("accession", r["business_events"][0]["cosignal_changed"],
                      "the co-signal must still be recorded for the reader")

    def test_missing_provenance_is_unknown_not_clean(self):
        """v4.2.48 (mandate): absence of provenance is NOT sameness of provenance. Silently
        dropping uncomparable fields let a jump fall into business_events — 'zero is not unknown',
        sixth incarnation."""
        import edgar_facts as _ef
        op = [{"end": "%d-12-31" % y, "val": v * 1e9} for y, v in
              [(2021, 10.082), (2022, 4.0), (2023, 14.006)]]
        bare = [{"end": "%d-12-31" % y, "val": v * 1e9} for y, v in
                [(2021, 18.884), (2022, 22.237), (2023, 25.098)]]
        r = _ef._ratio_continuity(op, bare)
        self.assertEqual(r["defects"], [])
        self.assertEqual(r["business_events"], [],
                         "an uncomparable jump must NOT be filed as a clean business event")
        self.assertTrue(r["provenance_unknown"], "it must be filed as an honest 'don't know'")
        self.assertIn("tag", r["provenance_unknown"][0]["provenance_uncomparable"])


class TestAsOfFilter(EdgarTestBase):
    """Issue #14, the historical-reconstruction stand. `as_of` restricts every fact to ones
    FILED on or before that day -- what the public actually knew, not what a later restatement
    says. The property under test is the FILTER ITSELF, not any one field it happens to touch."""

    def test_as_of_excludes_facts_filed_after_the_cutoff(self):
        """Pin (issue #14 §5.1): at a given as_of, no fact FILED later must survive -- even one
        whose fiscal PERIOD ended well before the cutoff. Filtering on `end` instead of `filed`
        is exactly the bug this pin exists to catch."""
        mock = facts({"Revenues": usd([
            row("2023-01-01", "2023-12-31", 100, accn="a", filed="2024-02-01"),
            row("2024-01-01", "2024-12-31", 150, accn="b", filed="2025-02-01"),  # filed AFTER cutoff
        ])})
        r = self.run_with(mock, as_of="2024-06-01")
        ends = [p["end"] for p in r["revenue"]]
        self.assertEqual(ends, ["2023-12-31"])
        self.assertNotIn("2024-12-31", ends, "a fact filed after as_of leaked through")
        # property, not shape: walk every *_audit trail in the whole payload and check the SAME
        # invariant everywhere it could possibly appear, not just in the one field we picked.
        for key, val in r.items():
            if key.endswith("_audit") and isinstance(val, list):
                for point in val:
                    if isinstance(point, dict) and point.get("filed"):
                        self.assertLessEqual(point["filed"], "2024-06-01",
                                             "%s carries a fact filed after as_of" % key)

    def test_unset_as_of_matches_current_behavior_even_for_a_fact_filed_in_the_future(self):
        """Pin (issue #14 §5.2): omitting as_of must change NOTHING -- not even drop a fact filed
        implausibly far in the future. If the default path started filtering anything, this
        fixture makes it visible immediately instead of by accident on a live ticker."""
        mock = facts({"Revenues": usd([
            row("2024-01-01", "2024-12-31", 150, accn="a", filed="2099-01-01"),
        ])})
        r = self.run_with(mock)
        self.assertEqual(r["revenue"], [{"end": "2024-12-31", "val": 150}])
        self.assertNotIn("_as_of", r)

    def test_as_of_excludes_equity_filed_after_the_cutoff(self):
        """Pin (issue #14 §5.6): the equity series obeys the SAME as_of cutoff as everything
        else -- a company's book value disclosed after the cutoff must not leak into a
        historical-date roe_median_5y read."""
        mock = facts({"StockholdersEquity": usd([
            row(None, "2022-12-31", 900, accn="e1", filed="2023-02-01"),
            row(None, "2023-12-31", 950, accn="e2", filed="2024-02-01"),  # filed AFTER cutoff
        ])})
        r = self.run_with(mock, as_of="2023-06-01")
        ends = [p["end"] for p in r["stockholders_equity"]]
        self.assertEqual(ends, ["2022-12-31"])
        self.assertNotIn("2023-12-31", ends)


class TestEquityAndRoe(EdgarTestBase):
    """Issue #14 §5: stockholders_equity + roe_median_5y did not exist before this change."""

    def test_median_of_last_five_years_computed_correctly(self):
        ends = ["2019-12-31", "2020-12-31", "2021-12-31", "2022-12-31", "2023-12-31"]
        ni_vals = [80, 120, 90, 200, 150]     # / equity 1000 -> .08 .12 .09 .20 .15
        ni_rows = [row(e[:4] + "-01-01", e, v, accn="ni" + e[:4],
                      filed=str(int(e[:4]) + 1) + "-02-01") for e, v in zip(ends, ni_vals)]
        eq_rows = [row(None, e, 1000, accn="eq" + e[:4],
                      filed=str(int(e[:4]) + 1) + "-02-01") for e in ends]
        mock = facts({"NetIncomeLoss": usd(ni_rows), "StockholdersEquity": usd(eq_rows)})
        r = self.run_with(mock)
        # sorted ROE: .08 .09 .12 .15 .20 -> median .12
        self.assertAlmostEqual(r["roe_median_5y"], 0.12, places=6)
        self.assertNotIn("roe_median_5y_refused", r["_flags"])

    def test_negative_equity_refuses_with_a_reason_not_a_number(self):
        """Pin (issue #14 §5.5): negative/zero equity is a REFUSAL by name
        (roe_not_computable: negative_equity), never a number and never a silent skip."""
        ends = ["2021-12-31", "2022-12-31", "2023-12-31"]
        ni_rows = [row(e[:4] + "-01-01", e, 10, accn="ni" + e[:4],
                      filed=str(int(e[:4]) + 1) + "-02-01") for e in ends]
        eq_vals = [100, -50, 120]
        eq_rows = [row(None, e, v, accn="eq" + e[:4],
                      filed=str(int(e[:4]) + 1) + "-02-01") for e, v in zip(ends, eq_vals)]
        mock = facts({"NetIncomeLoss": usd(ni_rows), "StockholdersEquity": usd(eq_rows)})
        r = self.run_with(mock)
        self.assertIsNone(r["roe_median_5y"])
        self.assertEqual(r["_flags"]["roe_median_5y_refused"]["roe_not_computable"], "negative_equity")

    def test_fewer_than_three_years_refuses_insufficient_history(self):
        ends = ["2022-12-31", "2023-12-31"]
        ni_rows = [row(e[:4] + "-01-01", e, 10, accn="ni" + e[:4],
                      filed=str(int(e[:4]) + 1) + "-02-01") for e in ends]
        eq_rows = [row(None, e, 100, accn="eq" + e[:4],
                      filed=str(int(e[:4]) + 1) + "-02-01") for e in ends]
        mock = facts({"NetIncomeLoss": usd(ni_rows), "StockholdersEquity": usd(eq_rows)})
        r = self.run_with(mock)
        self.assertIsNone(r["roe_median_5y"])
        self.assertEqual(r["_flags"]["roe_median_5y_refused"]["roe_not_computable"], "insufficient_history")

    def test_stockholders_equity_falls_back_to_combined_tag_with_a_flag(self):
        mock = facts({"StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": usd([
            row(None, "2023-12-31", 500, accn="c1", filed="2024-02-01"),
        ])})
        r = self.run_with(mock)
        self.assertEqual(r["stockholders_equity"], [{"end": "2023-12-31", "val": 500}])
        self.assertIn("stockholders_equity_combined_basis", r["_flags"])

    def test_primary_equity_tag_wins_when_both_present(self):
        mock = facts({
            "StockholdersEquity": usd([row(None, "2023-12-31", 400, accn="p1", filed="2024-02-01")]),
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": usd([
                row(None, "2023-12-31", 999, accn="c1", filed="2024-02-01")]),
        })
        r = self.run_with(mock)
        self.assertEqual(r["stockholders_equity"], [{"end": "2023-12-31", "val": 400}])
        self.assertNotIn("stockholders_equity_combined_basis", r["_flags"])

    def test_roe_basis_travels_next_to_the_number(self):
        """Pin (issue #20 pt.4): the #18 audit found roe_median_5y had no basis label next to
        it -- a consumer would compare it to a peer's average-capital ROE as the same measure.
        roe_basis names the actual denominator (year-end equity, per _roe_median_5y's docstring),
        and must be present even when the median itself is refused -- the label describes what
        the FIELD means, not a fact about this one company's history."""
        mock = facts({"Revenues": usd([row("2024-01-01", "2024-12-31", 100)])})  # no equity at all
        r = self.run_with(mock)
        self.assertIsNone(r["roe_median_5y"])
        self.assertEqual(r["roe_basis"], "net_income / year_end_equity")


class TestAsOfCompanyconceptLeg(EdgarTestBase):
    """Issue #20 pt.3, the two branches the #18 audit named as unpinned: `_detect_confirmed_
    splits` and `_shares_current` both make a SEPARATE companyconcept fetch that bypasses the
    caller's as_of filtering on `facts`, so each applies the same cutoff again internally
    (edgar_facts.py:536-539, 620-621). Before this pin, deleting those two lines failed no test
    in the tree -- a historical-date read could see a share count or a split restatement first
    disclosed AFTER the requested as_of date."""

    def test_as_of_filters_the_companyconcept_leg_of_shares_current(self):
        # companyfacts carries nothing for shares_current -- forces the companyconcept fallback.
        mock = facts({"Revenues": usd([row("2024-01-01", "2024-12-31", 100)])})
        rows = [
            row(None, "2023-06-30", 100000000, form="10-Q", accn="q1", filed="2023-07-20"),
            row(None, "2024-06-30", 200000000, form="10-Q", accn="q2", filed="2024-07-20"),
        ]
        ef._CONCEPT_CACHE[("TEST", "dei", "EntityCommonStockSharesOutstanding")] = (
            time.time(), {"shares": rows})
        # Positive control: without as_of, the later (larger) filing wins -- proves the branch
        # is reachable and the mock actually exercises it.
        r_all = self.run_with(mock)
        self.assertEqual(r_all["shares_current"], 200000000)
        # With as_of set BEFORE the second filing's filed date, that filing must not be seen.
        r_cut = self.run_with(mock, as_of="2023-12-31")
        self.assertEqual(r_cut["shares_current"], 100000000,
                         "a share count filed after as_of leaked through the companyconcept leg "
                         "of _shares_current")

    def test_as_of_filters_the_companyconcept_leg_of_confirmed_splits(self):
        # companyfacts carries nothing for shares_diluted -- forces reliance on companyconcept.
        mock = facts({"Revenues": usd([row("2024-01-01", "2024-12-31", 100)])})
        pre_split = row("2012-09-30", "2013-09-28", 925331000, accn="s1", filed="2013-10-30")
        restated = row("2012-09-30", "2013-09-28", 6521634000, accn="s3", filed="2015-10-28")
        ef._CONCEPT_CACHE[("TEST", "us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding")] = (
            time.time(), {"shares": [pre_split, restated]})
        # Positive control: without as_of, the restatement is visible and the split confirms.
        r_all = self.run_with(mock)
        self.assertEqual(r_all["_flags"]["confirmed_splits"][0]["factor"], 7)
        # With as_of BEFORE the restatement's filed date, only the pre-split value is visible --
        # one distinct value can never confirm a split (needs two).
        r_cut = self.run_with(mock, as_of="2014-01-01")
        self.assertNotIn("confirmed_splits", r_cut["_flags"],
                         "a restatement filed after as_of leaked through the companyconcept leg "
                         "of _detect_confirmed_splits, confirming a split before it was public")
        self.assertIn("confirmed_splits_none", r_cut["_flags"])
