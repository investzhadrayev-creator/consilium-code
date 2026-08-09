"""
Regression tests for tools/historical_run.py — Счёт проверки №1 (issue #28,
mailbox/PREREG_2026-08-06_HISTORICAL_VALIDATION.md, executed under
mailbox/DECISION_2026-08-09_ARBITRATION.md В1/В4).

All tests are OFFLINE and use synthetic fixtures (no real archive exists yet -- the operator
uploads Reports/histrun_2026-08-08/histrun_raw_v3.zip separately; see tools/historical_run.py's
own module docstring for the exact command to run against it).

Two GOLDEN CASES are hand-computed and asserted byte-for-byte; both are ALSO reproduced in the
pull request description with the arithmetic shown step by step, per the mandate's acceptance
rule ("минимум два золотых кейса, посчитанных вручную").

  GOLDEN CASE 1 -- clean, no split, price above intrinsic value (no BUY):
    revenue 2014..2019 = 100 * 1.10^n (6 points)      -> rev_cagr_3y = rev_cagr_5y = 0.10 exactly
    growth_rate = min(0.10, 0.10) capped at 20%        = 0.10
    terminal_growth = min(0.04, 0.10)                  = 0.04
    net_income = 200/yr, equity = 1000/yr (2015..2019) -> roe_median_5y = 0.20 (no cap bites)
    payout = 1 - 0.04/0.20 = 0.8; k_exit=9%: formula_cap = 0.8/(0.09-0.04) = 16.0 (no pe_hist_median)
    eps_as_filed = net_income[2019]/shares[2019] = 200/100 = 2.00; no split -> eps_today = 2.00
    fcf_as_filed = (ocf-capex)/shares = (300-50)/100 = 2.50; fcf_today = 2.50
    ivc_lib.ivc(price=40, eps=2.00, g=0.10, future_pe=16.0, hurdle=12%, tg=0.04)
      -> intrinsic_value = 22.61, implied_cagr_pct = 5.79, hurdle_gate = FAIL
    ivc_lib.ivc(..., levered_fcf_per_share=2.50, ...) -> intrinsic_value = 28.27, ic% = 8.18
    conservative leg = gaap_eps (5.79 <= 8.18) -> published IV = 22.61, ic% = 5.79
    price 40.00 > threshold 22.61 -> variant A NOT reached; > 20.56 -> variant Б NOT reached.

  GOLDEN CASE 2 -- confirmed 4:1 split since the test date + ROE above the 40% cap (BUY):
    revenue 2014..2019 = 100 * 1.15^n (6 points)       -> rev_cagr_3y = rev_cagr_5y = 0.15 exactly
    growth_rate = 0.15 (cap 20% not binding); terminal_growth = min(0.04, 0.15) = 0.04
    net_income = 440/yr, equity = 800/yr               -> roe_median_5y = 440/800 = 0.55
    roe_terminal capped at 40% -> 0.40 (0.15 discarded, named)
    payout = 1 - 0.04/0.40 = 0.9; k_exit=9%: formula_cap = 0.9/(0.09-0.04) = 18.0
      (PREREG §8's own worked check: at g=4%, k_exit=9%, the formula cannot exceed 20.0x at any
       ROE -- 18.0 < 20.0, consistent)
    price_record: close=60.0, adjClose=15.0 (ratio 4.0); daily splitFactor product = 4.0 exactly
      -> split_factor_since = 4.0 (macro_prices.split_factor_since, reused verbatim, unmodified)
    eps_as_filed = net_income[2019]/shares[2019] = 440/50 = 8.80 -> eps_today = 8.80/4 = 2.20
    fcf_as_filed = (560-60)/50 = 10.00 -> fcf_today = 10.00/4 = 2.50
    ivc_lib.ivc(price=15, eps=2.20, g=0.15, future_pe=18.0, hurdle=12%, tg=0.04)
      -> intrinsic_value = 38.31, implied_cagr_pct = 23.01, hurdle_gate = PASS
    ivc_lib.ivc(..., levered_fcf_per_share=2.50, ...) -> intrinsic_value = 43.53, ic% = 24.59
    conservative leg = gaap_eps (23.01 <= 24.59) -> published IV = 38.31, ic% = 23.01
    price 15.00 <= threshold 38.31 -> variant A reached; <= 34.82 -> variant Б reached. BOTH BUY.
    Shadow DCF (decision В4, Gordon-growth perpetuity multiple (1.04)/(0.12-0.04) = 13.0 on the
    FCF leg): intrinsic_value = 31.44 -- DIFFERENT from the official 38.31, by construction (the
    two methods must not coincide, or a mutation swapping one for the other could hide in a run
    where they happen to agree).
"""
import time
import unittest

from _support import load_microservice_module

ef = load_microservice_module("edgar_facts")
mp = load_microservice_module("macro_prices")

import os
import sys
_TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
import historical_run as hr


def facts(us_gaap=None, dei=None, cik=1234567):
    out = {"facts": {}, "cik": cik}
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


def _annual(tag_rows, filed_years):
    """tag_rows: [(year, val)]; filed_years: [(year, filed_date)] parallel list."""
    out = []
    for (y, v), (_, filed) in zip(tag_rows, filed_years):
        out.append(row("%d-01-01" % y, "%d-12-31" % y, v, filed=filed))
    return out


class HistoricalRunTestBase(unittest.TestCase):
    def setUp(self):
        ef._FACTS_CACHE.clear()
        ef._CONCEPT_CACHE.clear()


def _gold1_edgar():
    years = [2014, 2015, 2016, 2017, 2018, 2019]
    filed = ["2015-02-15", "2016-02-15", "2017-02-15", "2018-02-15", "2019-02-15", "2020-02-15"]
    revenue = [100.0, 110.0, 121.0, 133.1, 146.41, 161.051]
    rev_rows = [row("%d-01-01" % y, "%d-12-31" % y, v, filed=f)
                for y, v, f in zip(years, revenue, filed)]
    ni_years = years[1:]        # 2015..2019
    ni_filed = filed[1:]
    ni_rows = [row("%d-01-01" % y, "%d-12-31" % y, 200.0, filed=f)
              for y, f in zip(ni_years, ni_filed)]
    eq_rows = [row(None, "%d-12-31" % y, 1000.0, filed=f) for y, f in zip(ni_years, ni_filed)]
    sh_rows = [row("2019-01-01", "2019-12-31", 100.0, filed="2020-02-15")]
    ocf_rows = [row("2019-01-01", "2019-12-31", 300.0, filed="2020-02-15")]
    capex_rows = [row("2019-01-01", "2019-12-31", 50.0, filed="2020-02-15")]
    return facts({
        "Revenues": usd(rev_rows),
        "NetIncomeLoss": usd(ni_rows),
        "StockholdersEquity": usd(eq_rows),
        "WeightedAverageNumberOfDilutedSharesOutstanding": shares(sh_rows),
        "NetCashProvidedByUsedInOperatingActivities": usd(ocf_rows),
        "PaymentsToAcquirePropertyPlantAndEquipment": usd(capex_rows),
    }, cik=1111111)


def _gold1_price():
    return [{"date": "2020-03-23", "close": 40.0, "adjClose": 40.0, "splitFactor": 1.0,
            "divCash": 0.0}]


def _gold2_edgar():
    years = [2014, 2015, 2016, 2017, 2018, 2019]
    filed = ["2015-02-15", "2016-02-15", "2017-02-15", "2018-02-15", "2019-02-15", "2020-02-15"]
    revenue = [100.0, 115.0, 132.25, 152.0875, 174.900625, 201.13571875]
    rev_rows = [row("%d-01-01" % y, "%d-12-31" % y, v, filed=f)
                for y, v, f in zip(years, revenue, filed)]
    ni_years = years[1:]
    ni_filed = filed[1:]
    ni_rows = [row("%d-01-01" % y, "%d-12-31" % y, 440.0, filed=f)
              for y, f in zip(ni_years, ni_filed)]
    eq_rows = [row(None, "%d-12-31" % y, 800.0, filed=f) for y, f in zip(ni_years, ni_filed)]
    sh_rows = [row("2019-01-01", "2019-12-31", 50.0, filed="2020-02-15")]
    ocf_rows = [row("2019-01-01", "2019-12-31", 560.0, filed="2020-02-15")]
    capex_rows = [row("2019-01-01", "2019-12-31", 60.0, filed="2020-02-15")]
    return facts({
        "Revenues": usd(rev_rows),
        "NetIncomeLoss": usd(ni_rows),
        "StockholdersEquity": usd(eq_rows),
        "WeightedAverageNumberOfDilutedSharesOutstanding": shares(sh_rows),
        "NetCashProvidedByUsedInOperatingActivities": usd(ocf_rows),
        "PaymentsToAcquirePropertyPlantAndEquipment": usd(capex_rows),
    }, cik=2222222)


def _gold2_price():
    return [{"date": "2020-03-23", "close": 60.0, "adjClose": 15.0, "splitFactor": 1.0,
            "divCash": 0.0},
           {"date": "2024-06-01", "close": 61.0, "adjClose": 15.25, "splitFactor": 4.0,
            "divCash": 0.0},
           {"date": "2026-08-08", "close": 62.0, "adjClose": 15.5, "splitFactor": 1.0,
            "divCash": 0.0}]


def _gold3_edgar():
    """Same growth/ROE/split shape as GOLD2, but NetIncomeLoss/StockholdersEquity STOP at FY2018
    -- FY2019 (the year shares_diluted/ocf/capex report) has no net_income point, so the EPS
    leg's own common-FY-end search (net_income & shares_diluted) finds none and refuses by name,
    while roe_median_5y (computed from the SEPARATE 2015-2018 net_income/equity overlap, still
    4 points >= the 3-point floor) is unaffected -- so the pair still SCORES, single-leg, on the
    FCF leg alone. Built for issue #28 audit round 2: item 2 (single_leg must name which leg and
    why) and mutation case histrun-basis-bypass-02 (the FCF leg's basis_adjust is the only thing
    standing between the published IV and a ~4x-inflated as-filed number)."""
    years = [2014, 2015, 2016, 2017, 2018, 2019]
    filed = ["2015-02-15", "2016-02-15", "2017-02-15", "2018-02-15", "2019-02-15", "2020-02-15"]
    revenue = [100.0, 115.0, 132.25, 152.0875, 174.900625, 201.13571875]
    rev_rows = [row("%d-01-01" % y, "%d-12-31" % y, v, filed=f)
                for y, v, f in zip(years, revenue, filed)]
    ni_years = [2015, 2016, 2017, 2018]      # NOTE: no 2019 point -- the EPS-leg trap
    ni_filed = filed[1:5]
    ni_rows = [row("%d-01-01" % y, "%d-12-31" % y, 440.0, filed=f)
              for y, f in zip(ni_years, ni_filed)]
    eq_rows = [row(None, "%d-12-31" % y, 800.0, filed=f) for y, f in zip(ni_years, ni_filed)]
    sh_rows = [row("2019-01-01", "2019-12-31", 50.0, filed="2020-02-15")]
    ocf_rows = [row("2019-01-01", "2019-12-31", 560.0, filed="2020-02-15")]
    capex_rows = [row("2019-01-01", "2019-12-31", 60.0, filed="2020-02-15")]
    return facts({
        "Revenues": usd(rev_rows),
        "NetIncomeLoss": usd(ni_rows),
        "StockholdersEquity": usd(eq_rows),
        "WeightedAverageNumberOfDilutedSharesOutstanding": shares(sh_rows),
        "NetCashProvidedByUsedInOperatingActivities": usd(ocf_rows),
        "PaymentsToAcquirePropertyPlantAndEquipment": usd(capex_rows),
    }, cik=3000003)


def _gold3_price():
    return _gold2_price()


class TestGoldenCase1CleanNoSplitNoBuy(HistoricalRunTestBase):

    def test_full_pipeline_matches_hand_computed_arithmetic(self):
        row_out = hr.score_pair("GOLD1", "2020-03-23", _gold1_edgar(), _gold1_price())
        self.assertEqual(row_out["status"], "SCORED", row_out.get("reason"))
        self.assertAlmostEqual(row_out["rev_cagr_3y"], 0.10, places=6)
        self.assertAlmostEqual(row_out["rev_cagr_5y"], 0.10, places=6)
        self.assertAlmostEqual(row_out["growth_rate"], 0.10, places=6)
        self.assertAlmostEqual(row_out["terminal_growth"], 0.04, places=6)
        self.assertAlmostEqual(row_out["roe_median_5y"], 0.20, places=6)
        self.assertAlmostEqual(row_out["future_pe_k9"], 16.0, places=6)
        self.assertEqual(row_out["future_pe_source"], "formula_no_median_available")
        self.assertEqual(row_out["split_factor_eps"], 1.0)
        self.assertEqual(row_out["verdict_leg"], "gaap_eps")
        self.assertAlmostEqual(row_out["intrinsic_value"], 22.61, places=2)
        self.assertAlmostEqual(row_out["implied_cagr_pct"], 5.79, places=2)
        self.assertEqual(row_out["hurdle_gate"], "FAIL")
        self.assertFalse(row_out["buy_A_no_discount"])
        self.assertFalse(row_out["buy_B_10pct_discount"])
        self.assertAlmostEqual(row_out["shadow_dcf"]["intrinsic_value"], 22.97, places=2)
        self.assertIn("EXPLORATORY", row_out["shadow_dcf"]["label"])


class TestGoldenCase2SplitAndRoeCapBuy(HistoricalRunTestBase):

    def test_full_pipeline_matches_hand_computed_arithmetic(self):
        row_out = hr.score_pair("GOLD2", "2020-03-23", _gold2_edgar(), _gold2_price())
        self.assertEqual(row_out["status"], "SCORED", row_out.get("reason"))
        self.assertAlmostEqual(row_out["growth_rate"], 0.15, places=6)
        self.assertAlmostEqual(row_out["terminal_growth"], 0.04, places=6)
        self.assertAlmostEqual(row_out["roe_median_5y"], 0.55, places=6)
        self.assertAlmostEqual(row_out["future_pe_k9"], 18.0, places=4)
        self.assertLess(row_out["future_pe_k9"], 20.0,
                        "PREREG §8's own ORCL sanity check: at g=4%, k_exit=9%, the formula "
                        "ceiling must not exceed 20.0x at any ROE")
        self.assertEqual(row_out["split_factor_eps"], 4.0)
        self.assertEqual(row_out["split_factor_fcf"], 4.0)
        self.assertEqual(row_out["verdict_leg"], "gaap_eps")
        self.assertAlmostEqual(row_out["intrinsic_value"], 38.31, places=2)
        self.assertAlmostEqual(row_out["implied_cagr_pct"], 23.01, places=2)
        self.assertEqual(row_out["hurdle_gate"], "PASS")
        self.assertTrue(row_out["buy_A_no_discount"])
        self.assertTrue(row_out["buy_B_10pct_discount"])
        # Shadow DCF is EXPLORATORY and must differ from -- never overwrite -- the official IV.
        self.assertAlmostEqual(row_out["shadow_dcf"]["intrinsic_value"], 31.44, places=2)
        self.assertNotAlmostEqual(row_out["shadow_dcf"]["intrinsic_value"],
                                  row_out["intrinsic_value"], places=1)

    def test_naive_mixed_basis_would_have_overstated_iv_by_roughly_the_split_factor(self):
        """Documents the exact defect PREREG §7 exists to catch: feeding the AS-FILED eps
        (8.80, yesterday's basis) straight into ivc() against today's adjClose (15.00) instead
        of basis-adjusting it first would print a materially different -- and wrong -- IV."""
        naive = self._naive_iv()
        correct = hr.score_pair("GOLD2", "2020-03-23", _gold2_edgar(), _gold2_price())
        self.assertNotAlmostEqual(naive, correct["intrinsic_value"], places=0)

    @staticmethod
    def _naive_iv():
        import ivc_lib
        r = ivc_lib.ivc({"price": 15.0, "eps_normalized": 8.80, "growth_rate": 0.15,
                         "future_pe": 18.0, "hurdle": 0.12, "discount_rate": 0.12,
                         "terminal_growth": 0.04})
        return r["intrinsic_value"]


class TestGrowthAnchor(unittest.TestCase):

    def test_caps_at_20pct(self):
        gt = {"revenue": [{"end": "%d-12-31" % y, "val": v} for y, v in
                          zip(range(2014, 2020), [100 * 1.30 ** n for n in range(6)])]}
        g, rc3, rc5, reason = hr.compute_growth_anchor(gt)
        self.assertIsNone(reason)
        self.assertAlmostEqual(g, 0.20, places=6)

    def test_refuses_by_name_when_history_too_short_for_either_window(self):
        gt = {"revenue": [{"end": "2018-12-31", "val": 100}, {"end": "2019-12-31", "val": 110}]}
        g, rc3, rc5, reason = hr.compute_growth_anchor(gt)
        self.assertIsNone(g)
        self.assertIsNone(rc3)
        self.assertIsNone(rc5)
        self.assertIsNotNone(reason)
        self.assertNotEqual(reason, "")


class TestTerminalMultiple(unittest.TestCase):

    def test_golden_case_1_formula_16(self):
        multiple, meta = hr.official_future_pe(0.20, 0.04, 0.09, None)
        self.assertAlmostEqual(multiple, 16.0, places=6)
        self.assertEqual(meta["source"], "formula_no_median_available")

    def test_golden_case_2_roe_capped_at_40pct_discards_named_excess(self):
        multiple, meta = hr.official_future_pe(0.55, 0.04, 0.09, None)
        self.assertAlmostEqual(multiple, 18.0, places=4)
        self.assertAlmostEqual(meta["roe_terminal_capped"], 0.40, places=6)
        self.assertAlmostEqual(meta["roe_excess_discarded_pp"], 0.15, places=6)

    def test_historical_median_wins_when_below_the_formula_ceiling(self):
        multiple, meta = hr.official_future_pe(0.55, 0.04, 0.09, 12.0)
        self.assertAlmostEqual(multiple, 12.0, places=6)
        self.assertEqual(meta["source"], "historical_median")
        self.assertAlmostEqual(meta["formula_excess_discarded"], 6.0, places=6)

    def test_historical_median_above_ceiling_is_discarded(self):
        multiple, meta = hr.official_future_pe(0.55, 0.04, 0.09, 25.0)
        self.assertAlmostEqual(multiple, 18.0, places=4)
        self.assertEqual(meta["source"], "formula")

    def test_refuses_by_name_when_roe_missing(self):
        multiple, meta = hr.official_future_pe(None, 0.04, 0.09, None)
        self.assertIsNone(multiple)
        self.assertIn("roe_median_5y unavailable", meta["reason"])

    def test_refuses_by_name_when_capped_roe_at_or_below_terminal_growth(self):
        """PREREG §8 does not define the formula outside a positive payout ratio -- a named
        refusal, not a saturated/negative payout, per PROTOCOL_GAPS."""
        multiple, meta = hr.official_future_pe(0.03, 0.04, 0.09, None)
        self.assertIsNone(multiple)
        self.assertIn("PREREG §8 does not define this case", meta["reason"])


class TestDiscoverPairs(unittest.TestCase):

    def test_pairs_both_files_together(self):
        names = ["AAA_20200323_edgar.json", "AAA_20200323_price.json",
                "BBB_20200323_edgar.json"]   # BBB missing its price file
        pairs, incomplete = hr.discover_pairs(names)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0][0], "AAA")
        self.assertEqual(len(incomplete), 1)
        self.assertEqual(incomplete[0]["ticker"], "BBB")
        self.assertIn("incomplete_pair_missing_price_file", incomplete[0]["reason"])

    def test_unrelated_filenames_are_ignored(self):
        pairs, incomplete = hr.discover_pairs(["README.txt", "manifest.json"])
        self.assertEqual(pairs, [])
        self.assertEqual(incomplete, [])


class TestNegativeControlsRefuseByName(HistoricalRunTestBase):
    """PREREG §5.1: a refusal IS a result, not a defect to paper over. Each of the three
    'непригодна' classes named in issue #28 gets its own named-refusal pin here."""

    def test_young_name_insufficient_revenue_history_refuses(self):
        edgar = facts({"Revenues": usd([
            row("2018-01-01", "2018-12-31", 100.0, filed="2019-02-15"),
            row("2019-01-01", "2019-12-31", 110.0, filed="2020-02-15"),
        ])}, cik=3333333)
        out = hr.score_pair("YOUNGCO", "2020-03-23", edgar, [{"date": "2020-03-23",
                            "close": 10.0, "adjClose": 10.0, "splitFactor": 1.0}])
        self.assertEqual(out["status"], "REFUSED")
        self.assertIsNotNone(out["reason"])

    def test_no_trading_day_on_record_refuses_not_a_guess_at_the_nearest_day(self):
        out = hr.score_pair("GOLD1", "2020-03-23", _gold1_edgar(), [])
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("no trading record", out["reason"])

    def test_split_factor_undeterminable_refuses(self):
        """Mirrors test_historical_stand.TestSameShareBasisPE's own undeterminable-factor pin:
        product 10 vs ratio 12 disagree beyond tolerance."""
        price_rows = [{"date": "2020-03-23", "close": 1200.0, "adjClose": 100.0}]
        # note: split_factor_since needs daily_rows AND the single-day record; historical_run
        # passes the WHOLE price_rows list as daily_rows, so the single matching row also
        # supplies (a wrong) splitFactor product signal here on purpose.
        price_rows[0]["splitFactor"] = 10.0
        out = hr.score_pair("GOLD1", "2020-03-23", _gold1_edgar(), price_rows)
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("split_factor_undeterminable", out["reason"])


class TestShadowDcfNeverFeedsTheOfficialVerdict(unittest.TestCase):

    def test_shadow_dcf_absent_when_fcf_leg_unavailable_official_still_scores(self):
        edgar = _gold1_edgar()
        # strip the FCF leg's inputs (ocf/capex) -- only the EPS leg remains usable.
        del edgar["facts"]["us-gaap"]["NetCashProvidedByUsedInOperatingActivities"]
        del edgar["facts"]["us-gaap"]["PaymentsToAcquirePropertyPlantAndEquipment"]
        out = hr.score_pair("GOLD1", "2020-03-23", edgar, _gold1_price())
        self.assertEqual(out["status"], "SCORED")
        self.assertEqual(out["verdict_leg_note"], "single_leg")
        self.assertIsNone(out["shadow_dcf"]["intrinsic_value"])
        self.assertIn("EXPLORATORY", out["shadow_dcf"]["label"])
        # official verdict is UNCHANGED by the shadow leg being unavailable
        self.assertAlmostEqual(out["intrinsic_value"], 22.61, places=2)


class TestSingleLegSurfacesMissingLegReason(HistoricalRunTestBase):
    """Issue #28 audit round 2, item 2: a single_leg row must publish WHY the other leg is
    missing (eps_reason/fcf_reason), on the row, in the CSV, and in the report table -- not
    just the fact that it's single_leg. GOLD3 (see its fixture docstring) refuses the EPS leg
    by name (no common FY end -- FY2019 has no net_income point) while the FCF leg scores
    normally through the split adjustment; numbers below are from the tool's own output
    (`hr.score_pair`), not hand-derived, since the arithmetic is identical to GOLD2's already
    hand-verified FCF leg (fcf_today = (560-60)/50 / 4.0 = 2.50)."""

    def test_row_names_the_missing_leg_reason(self):
        out = hr.score_pair("GOLD3", "2020-03-23", _gold3_edgar(), _gold3_price())
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        self.assertEqual(out["verdict_leg_note"], "single_leg")
        self.assertEqual(out["verdict_leg"], "fcf_per_share")
        self.assertIsNone(out["fcf_reason"])
        self.assertIsNotNone(out["eps_reason"])
        self.assertIn("no common FY end", out["eps_reason"])
        self.assertAlmostEqual(out["intrinsic_value"], 43.53, places=2)
        self.assertAlmostEqual(out["implied_cagr_pct"], 24.59, places=2)

    def test_csv_and_report_carry_the_missing_leg_reason(self):
        import csv
        import tempfile
        out = hr.score_pair("GOLD3", "2020-03-23", _gold3_edgar(), _gold3_price())
        with tempfile.TemporaryDirectory() as d:
            csv_path = os.path.join(d, "out.csv")
            md_path = os.path.join(d, "out.md")
            hr.write_csv([out], csv_path)
            hr.write_report([out], md_path)

            with open(csv_path, encoding="utf-8") as f:
                csv_row = next(csv.DictReader(f))
            self.assertIn("eps_reason", csv_row)
            self.assertIn("fcf_reason", csv_row)
            self.assertIn("no common FY end", csv_row["eps_reason"])
            self.assertEqual(csv_row["fcf_reason"], "")

            with open(md_path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("Причина недоступности второй ноги", text)
            self.assertIn("no common FY end", text)


class TestPeHistMedianNoteIsPublished(HistoricalRunTestBase):
    """Issue #28 audit round 2, item 1: pe_hist_median_note (already computed in score_pair)
    must reach the CSV column and the report's notes column, and the cell is never empty when
    the median is ABSENT from the archive (the mandate's own wording)."""

    def test_absent_median_note_is_non_empty_on_both_surfaces(self):
        import csv
        import tempfile
        out = hr.score_pair("GOLD1", "2020-03-23", _gold1_edgar(), _gold1_price())
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        self.assertIsNone(out["pe_hist_median"])
        self.assertTrue(out["pe_hist_median_note"])   # non-empty string, not None/""

        with tempfile.TemporaryDirectory() as d:
            csv_path = os.path.join(d, "out.csv")
            md_path = os.path.join(d, "out.md")
            hr.write_csv([out], csv_path)
            hr.write_report([out], md_path)

            with open(csv_path, encoding="utf-8") as f:
                csv_row = next(csv.DictReader(f))
            self.assertIn("pe_hist_median_note", csv_row)
            self.assertTrue(csv_row["pe_hist_median_note"])

            with open(md_path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("PE-hist медиана (примечание)", text)
            self.assertIn(out["pe_hist_median_note"], text)

    def test_present_median_gives_no_reason_but_report_cell_still_not_blank(self):
        price = _gold1_price()
        price[0] = dict(price[0], pe_hist_median=14.0)
        out = hr.score_pair("GOLD1", "2020-03-23", _gold1_edgar(), price)
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        self.assertEqual(out["pe_hist_median"], 14.0)
        self.assertIsNone(out["pe_hist_median_note"])   # nothing to explain -- median was found

        import tempfile
        with tempfile.TemporaryDirectory() as d:
            md_path = os.path.join(d, "out.md")
            hr.write_report([out], md_path)
            with open(md_path, encoding="utf-8") as f:
                lines = f.read().splitlines()
            data_row = next(l for l in lines if l.startswith("| GOLD1 |"))
            cells = [c.strip() for c in data_row.strip("|").split("|")]
            # last two columns are PE-hist note and missing-leg reason (see write_report header)
            self.assertEqual(cells[-2], "-")
            self.assertNotEqual(cells[-2], "")


class TestFcfBasisAdjustAppliedToPublishedIv(HistoricalRunTestBase):
    """Guards mutation case histrun-basis-bypass-02: on a single_leg-FCF row, the published IV
    and split_factor_fcf must come from the split-ADJUSTED fcf/share (2.50), never the as-filed
    one (10.00) -- see GOLD3's fixture docstring for why the EPS leg is unavailable here, which
    makes the FCF leg's own basis_adjust the ONLY thing standing between the officially
    published number and a ~4x-inflated one."""

    def test_published_iv_and_split_factor_use_the_adjusted_fcf(self):
        out = hr.score_pair("GOLD3", "2020-03-23", _gold3_edgar(), _gold3_price())
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        self.assertEqual(out["verdict_leg"], "fcf_per_share")
        self.assertEqual(out["split_factor_fcf"], 4.0)
        self.assertAlmostEqual(out["intrinsic_value"], 43.53, places=2)


class TestRunArchiveMissingFileStops(unittest.TestCase):

    def test_missing_archive_refuses_without_fabricating_a_run(self):
        rows, err = hr.run_archive("/nonexistent/histrun_raw_v3.zip")
        self.assertIsNone(rows)
        self.assertIsNotNone(err)
        self.assertIn("archive not found", err)


class TestSensitivityBoundsArePublished(HistoricalRunTestBase):
    """score_pair() already computes the full k_exit grid (0.08/0.09/0.10) into row['sensitivity']
    (see PREREG §8); this pins that the 8% and 10% bounds actually reach the CSV and the report
    table, not just the in-memory row -- a field computed but never written is not a result."""

    def test_csv_and_report_carry_both_sensitivity_bounds(self):
        import csv
        import tempfile
        row_out = hr.score_pair("GOLD1", "2020-03-23", _gold1_edgar(), _gold1_price())
        self.assertEqual(row_out["status"], "SCORED", row_out.get("reason"))
        # hand-computed: payout = 1 - 0.04/0.20 = 0.8
        #   k_exit=8%: 0.8/(0.08-0.04) = 20.0    k_exit=10%: 0.8/(0.10-0.04) = 13.333...
        self.assertAlmostEqual(row_out["sensitivity"]["0.08"], 20.0, places=6)
        self.assertAlmostEqual(row_out["sensitivity"]["0.1"], 13.333333, places=5)

        with tempfile.TemporaryDirectory() as d:
            csv_path = os.path.join(d, "out.csv")
            md_path = os.path.join(d, "out.md")
            hr.write_csv([row_out], csv_path)
            hr.write_report([row_out], md_path)

            with open(csv_path, encoding="utf-8") as f:
                csv_row = next(csv.DictReader(f))
            self.assertIn("sensitivity_pe_k8", csv_row)
            self.assertIn("sensitivity_pe_k10", csv_row)
            self.assertAlmostEqual(float(csv_row["sensitivity_pe_k8"]), 20.0, places=6)
            self.assertAlmostEqual(float(csv_row["sensitivity_pe_k10"]), 13.333333, places=5)

            with open(md_path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("future_pe(8%)", text)
            self.assertIn("future_pe(10%)", text)
            self.assertIn("20.00", text)
            self.assertIn("13.33", text)


class TestReportAndCsvSmoke(unittest.TestCase):
    """Not a golden-arithmetic pin -- just proves write_csv/write_report execute cleanly over a
    mixed SCORED/REFUSED row set, so a real archive run cannot crash at the reporting step."""

    def test_write_csv_and_report_do_not_raise(self):
        import tempfile
        rows = [hr.score_pair("GOLD1", "2020-03-23", _gold1_edgar(), _gold1_price()),
               hr.score_pair("GOLD2", "2020-03-23", _gold2_edgar(), _gold2_price()),
               {"ticker": "NOPE", "date": "2020-03-23", "status": "REFUSED",
                "reason": "synthetic refusal for the smoke test"}]
        with tempfile.TemporaryDirectory() as d:
            hr.write_csv(rows, os.path.join(d, "out.csv"))
            hr.write_report(rows, os.path.join(d, "out.md"))
            self.assertTrue(os.path.exists(os.path.join(d, "out.csv")))
            self.assertTrue(os.path.exists(os.path.join(d, "out.md")))
            with open(os.path.join(d, "out.md"), encoding="utf-8") as f:
                text = f.read()
            for i in (1, 2, 3, 4):
                self.assertIn(hr.CRITERIA_TEXT[i][:20], text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
