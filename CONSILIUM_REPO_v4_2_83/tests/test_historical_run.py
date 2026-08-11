"""
Regression tests for tools/historical_run.py — Счёт проверки №1 (issue #28,
mailbox/PREREG_2026-08-06_HISTORICAL_VALIDATION.md, executed under
mailbox/DECISION_2026-08-09_ARBITRATION.md В1/В4).

issue #30: the first real run against Reports/histrun_2026-08-08/histrun_raw_v3.zip scored
0/175 — the tool's documented assumption about the archive's internal JSON shape (RAW SEC
companyfacts / a raw list of Tiingo daily rows) was wrong. The real archive's *_edgar.json IS
edgar_facts.edgar_facts()'s own OUTPUT (already as-of filtered, series as [{end,val}],
roe_median_5y a plain float, service fields underscored: _cik/_as_of/_errors/...), and
*_price.json is a DICT carrying one price_record plus an already-computed split_factor, not a
list. Every synthetic fixture below is now built in that real shape (see the `gt()`/`price_pkg()`
helpers) and one PAIR OF REAL ARCHIVE FILES is embedded as tests/fixtures/NVDA_20200323_*.json
(TestRealArchiveFixtureNVDA) so "fixture shaped like a guess, not like real data" cannot recur
undetected — see tools/historical_run.py's own module docstring, ФОРМАТ АРХИВА, for the full
field-by-field account.

Two GOLDEN CASES are hand-computed and asserted byte-for-byte; both are ALSO reproduced in the
pull request description with the arithmetic shown step by step, per the mandate's acceptance
rule ("минимум два золотых кейса, посчитанных вручную"). The arithmetic is UNCHANGED by issue
#30 — only how the same inputs are encoded into a fixture changed (roe_median_5y is now supplied
directly, exactly as edgar_facts() itself would compute and the archive would carry it, instead
of being re-derived from a synthetic equity/net_income series).

  GOLDEN CASE 1 -- clean, no split, price above intrinsic value (no BUY):
    revenue 2014..2019 = 100 * 1.10^n (6 points)      -> rev_cagr_3y = rev_cagr_5y = 0.10 exactly
    growth_rate = min(0.10, 0.10) capped at 20%        = 0.10
    terminal_growth = min(0.04, 0.10)                  = 0.04
    roe_median_5y = 0.20 (supplied directly, as edgar_facts() would compute it -- no cap bites)
    payout = 1 - 0.04/0.20 = 0.8; k_exit=9%: formula_cap = 0.8/(0.09-0.04) = 16.0 (no pe_hist_median)
    eps_as_filed = net_income[2019]/shares[2019] = 200/100 = 2.00; split_factor=1.0 -> eps_today = 2.00
    fcf_as_filed = (ocf-capex)/shares = (300-50)/100 = 2.50; fcf_today = 2.50
    ivc_lib.ivc(price=40, eps=2.00, g=0.10, future_pe=16.0, hurdle=12%, tg=0.04)
      -> intrinsic_value = 22.61, implied_cagr_pct = 5.79, hurdle_gate = FAIL
    ivc_lib.ivc(..., levered_fcf_per_share=2.50, ...) -> intrinsic_value = 28.27, ic% = 8.18
    conservative leg = gaap_eps (5.79 <= 8.18) -> published IV = 22.61, ic% = 5.79
    price 40.00 > threshold 22.61 -> variant A NOT reached; > 20.56 -> variant Б NOT reached.

  GOLDEN CASE 2 -- archive-supplied 4:1 split_factor since the test date + ROE above the 40% cap
  (BUY):
    revenue 2014..2019 = 100 * 1.15^n (6 points)       -> rev_cagr_3y = rev_cagr_5y = 0.15 exactly
    growth_rate = 0.15 (cap 20% not binding); terminal_growth = min(0.04, 0.15) = 0.04
    roe_median_5y = 0.55 (supplied directly)
    roe_terminal capped at 40% -> 0.40 (0.15 discarded, named)
    payout = 1 - 0.04/0.40 = 0.9; k_exit=9%: formula_cap = 0.9/(0.09-0.04) = 18.0
      (PREREG §8's own worked check: at g=4%, k_exit=9%, the formula cannot exceed 20.0x at any
       ROE -- 18.0 < 20.0, consistent)
    price_record: close=60.0, adjClose=15.0 (ratio 4.0); archive's own split_factor = 4.0 (the
      PRECOMPUTED output of macro_prices.split_factor_since() at archive-build time -- see
      tools/historical_run.py's ФОРМАТ АРХИВА; this test supplies that same number directly)
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
import csv
import os
import sys
import tempfile
import unittest

_TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
import historical_run as hr

_FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def series(pairs):
    """pairs: [(end_date_iso, val), ...] -> [{"end":..., "val":...}, ...] -- the exact shape
    edgar_facts.edgar_facts() (and therefore the real archive) puts revenue/net_income/ocf/
    capex/shares_diluted in."""
    return [{"end": end, "val": val} for end, val in pairs]


def gt(ticker="GOLD", cik=1234567, cik_field="_cik", revenue=None, net_income=None,
      shares_diluted=None, ocf=None, capex=None, roe_median_5y=None, errors=None,
      shares_current=None, as_of="2020-03-23", flags=None):
    """Build a synthetic *_edgar.json record in the REAL archive shape (issue #30): this IS
    edgar_facts.edgar_facts()'s own output shape, not raw SEC companyfacts -- see
    tools/historical_run.py's ФОРМАТ АРХИВА. `cik_field` defaults to the real archive's own
    "_cik"; pass "cik" to exercise the legacy-fixture fallback historical_run.py also accepts.
    `shares_current` (issue #36): edgar_facts._shares_current's own bare-number field, absent
    (None) by default so every pre-existing fixture is unaffected by basis_gap_reason().
    `flags` (issue #36 audit tail on PR #38): merged into `_flags`, e.g.
    {"shares_current_proxied": "..."} to reproduce edgar_facts.py's degraded-witness mode."""
    out = {"_source": "sec_edgar", "_ticker": ticker, "_entity_name": ticker, "_as_of": as_of,
          "_missing": [], "_flags": dict(flags or {}), "_errors": errors or {},
          "revenue": revenue or [], "net_income": net_income or [],
          "shares_diluted": shares_diluted or [], "ocf": ocf or [], "capex": capex or [],
          "roe_median_5y": roe_median_5y, "shares_current": shares_current}
    out[cik_field] = cik
    return out


def price_pkg(ticker, date_iso, adj_close=None, close=None, split_factor=1.0,
             pe_hist_median=None, no_record=False, errors=None):
    """Build a synthetic *_price.json record in the REAL archive shape (issue #30): a DICT
    carrying one price_record plus an already-computed split_factor, never a list of raw Tiingo
    daily rows -- see tools/historical_run.py's ФОРМАТ АРХИВА."""
    if no_record:
        return {"ticker": ticker, "date": date_iso, "price_record": None,
               "split_factor": None, "pe_same_share_basis": None, "_errors": errors or {}}
    pr = {"date": date_iso, "close": close if close is not None else adj_close,
         "adjClose": adj_close, "splitFactor": split_factor if split_factor is not None else 1.0,
         "divCash": 0.0}
    out = {"ticker": ticker, "date": date_iso, "price_record": pr,
          "split_factor": split_factor, "pe_same_share_basis": None, "_errors": errors or {}}
    if pe_hist_median is not None:
        out["pe_hist_median"] = pe_hist_median
    return out


def _gold1_gt():
    years = [2014, 2015, 2016, 2017, 2018, 2019]
    revenue = [100.0, 110.0, 121.0, 133.1, 146.41, 161.051]
    return gt("GOLD1", cik=1111111,
             revenue=series([("%d-12-31" % y, v) for y, v in zip(years, revenue)]),
             net_income=series([("2019-12-31", 200.0)]),
             shares_diluted=series([("2019-12-31", 100.0)]),
             ocf=series([("2019-12-31", 300.0)]),
             capex=series([("2019-12-31", 50.0)]),
             roe_median_5y=0.20)


def _gold1_price():
    return price_pkg("GOLD1", "2020-03-23", adj_close=40.0, split_factor=1.0)


def _gold2_gt():
    years = [2014, 2015, 2016, 2017, 2018, 2019]
    revenue = [100.0, 115.0, 132.25, 152.0875, 174.900625, 201.13571875]
    return gt("GOLD2", cik=2222222,
             revenue=series([("%d-12-31" % y, v) for y, v in zip(years, revenue)]),
             net_income=series([("2019-12-31", 440.0)]),
             shares_diluted=series([("2019-12-31", 50.0)]),
             ocf=series([("2019-12-31", 560.0)]),
             capex=series([("2019-12-31", 60.0)]),
             roe_median_5y=0.55)


def _gold2_price():
    return price_pkg("GOLD2", "2020-03-23", adj_close=15.0, close=60.0, split_factor=4.0)


def _gold3_gt():
    """Same growth/ROE/split shape as GOLD2, but net_income carries ONLY a 2018 point while
    shares_diluted carries ONLY 2019 -- the two series share no common 'end', so the EPS leg's
    own common-FY-end search refuses by name, while roe_median_5y (a directly-supplied field in
    the real archive shape, independent of the net_income series entirely) is unaffected -- so
    the pair still SCORES, single-leg, on the FCF leg alone. Built for issue #28 audit round 2:
    item 2 (single_leg must name which leg and why) and mutation case histrun-basis-bypass-02
    (the FCF leg's basis_adjust is the only thing standing between the published IV and a
    ~4x-inflated as-filed number)."""
    years = [2014, 2015, 2016, 2017, 2018, 2019]
    revenue = [100.0, 115.0, 132.25, 152.0875, 174.900625, 201.13571875]
    return gt("GOLD3", cik=3000003,
             revenue=series([("%d-12-31" % y, v) for y, v in zip(years, revenue)]),
             net_income=series([("2018-12-31", 440.0)]),      # NOTE: no 2019 point -- the trap
             shares_diluted=series([("2019-12-31", 50.0)]),
             ocf=series([("2019-12-31", 560.0)]),
             capex=series([("2019-12-31", 60.0)]),
             roe_median_5y=0.55)


def _gold3_price():
    return price_pkg("GOLD3", "2020-03-23", adj_close=15.0, close=60.0, split_factor=4.0)


def _gold4_gt():
    """Built for issue #28 audit round 3, item 4 (mutation histrun-conservative-flip-01). Same
    shape as GOLD1 (10% growth, ROE 20%, no split) EXCEPT ocf/capex are set so the FCF leg's
    as-filed value (170/100 = 1.70) is BELOW the EPS leg's (200/100 = 2.00) -- the reverse of
    GOLD1/GOLD2, where the FCF leg is always the higher one. Because ivc()'s intrinsic_value/
    implied_cagr scale with the per-share base at fixed price/growth/multiple, the LOWER base
    (fcf) yields the LOWER implied_cagr_pct here, so the conservative pick MUST be fcf_per_share
    -- a comparison operator flipped from <= to >= would silently pick gaap_eps (the optimistic
    leg) instead, and this fixture is what makes that flip observable (GOLD1/GOLD2 cannot: both
    happen to pick gaap_eps regardless of which way the comparison points)."""
    years = [2014, 2015, 2016, 2017, 2018, 2019]
    revenue = [100.0, 110.0, 121.0, 133.1, 146.41, 161.051]
    return gt("GOLD4", cik=4444444,
             revenue=series([("%d-12-31" % y, v) for y, v in zip(years, revenue)]),
             net_income=series([("2019-12-31", 200.0)]),
             shares_diluted=series([("2019-12-31", 100.0)]),
             # ocf - capex = 220 - 50 = 170 -> fcf_af = 1.70, BELOW eps_af = 2.00
             ocf=series([("2019-12-31", 220.0)]),
             capex=series([("2019-12-31", 50.0)]),
             roe_median_5y=0.20)


def _gold4_price():
    return price_pkg("GOLD4", "2020-03-23", adj_close=40.0, split_factor=1.0)


# ---- issue #36 fixtures: AMZN_20221012 / NFLX_20221012 -----------------------------------------
# Reports/ is out of bounds for this changeset (task boundary) so these are NOT the literal
# archive bytes (contrast TestRealArchiveFixtureNVDA, built for issue #30 from the real zip) --
# they are synthetic, in the real archive SHAPE, engineered to reproduce the STRUCTURAL defect
# the issue names on realistic-scale numbers (real AMZN FY2021: ~$33.36B net income over ~515M
# pre-split diluted shares -> EPS ~$64.8 pre-split, ~10.3B shares post the June-2022 20:1 split;
# real observation date 2022-10-12, real archived split_factor_eps=1.0, real eps_basis_end
# 2021-12-31 -- all three exactly as issue #36 quotes them). The GOLD1 growth/ROE shape (10%
# growth, ROE 0.20) is reused for both so the arithmetic is traceable to already-hand-verified
# numbers (see TestGoldenCase1's own docstring) rather than re-derived from scratch.
_Y36 = [2016, 2017, 2018, 2019, 2020, 2021]
_REV36 = series([("%d-12-31" % y, 100.0 * 1.10 ** n) for n, y in enumerate(_Y36)])


def _amzn_gap_gt():
    """AMZN_20221012 (issue #36's own real case): FY2021 EPS/FCF basis (net_income 200/shares
    100 -> eps_af=2.00, same magnitude relationship as GOLD1) filed BEFORE the June-2022 20:1
    split; shares_current=2000 is a stand-in for a post-split dei cover-page figure disclosed on
    a 10-Q filed between 2021-12-31 and the observation date -- a clean 20x jump against
    shares_diluted(2021-12-31)=100, the exact signature basis_gap_reason() looks for."""
    return gt("AMZN", cik=1018724, as_of="2022-10-12",
             revenue=_REV36,
             net_income=series([("2021-12-31", 200.0)]),
             shares_diluted=series([("2021-12-31", 100.0)]),
             ocf=series([("2021-12-31", 300.0)]),
             capex=series([("2021-12-31", 50.0)]),
             roe_median_5y=0.20, shares_current=2000.0)


def _amzn_gap_price():
    """Archived split_factor_eps=1.0 -- issue #36's own quoted real number: no split from the
    OBSERVATION date onward, which is exactly what makes the pre-observation-date split
    invisible to it."""
    return price_pkg("AMZN", "2022-10-12", adj_close=40.0, close=40.0, split_factor=1.0)


def _nflx_safe_gt():
    """NFLX_20221012: same growth/ROE shape as GOLD1, but net_income/ocf/capex scaled 10x so
    that dividing by the archived split_factor=10.0 (the split effective AFTER 2022-10-12, per
    the issue) reproduces GOLD1's exact eps_today/fcf_today (2.00/2.50) and therefore its exact
    hand-verified numbers -- see TestIssue36SplitAfterObservationStaysScored. shares_current
    equals shares_diluted(2021-12-31) exactly (no split has happened as of the observation date
    yet) so basis_gap_reason() must NOT fire here -- the mutation this protects against is
    reverting the fix's own gap check to over-refuse a genuinely safe pair."""
    return gt("NFLX", cik=1065280, as_of="2022-10-12",
             revenue=_REV36,
             net_income=series([("2021-12-31", 2000.0)]),
             shares_diluted=series([("2021-12-31", 100.0)]),
             ocf=series([("2021-12-31", 3000.0)]),
             capex=series([("2021-12-31", 500.0)]),
             roe_median_5y=0.20, shares_current=100.0)


def _nflx_safe_price():
    """Archived split_factor=10.0 -- issue #36's own quoted real number for NFLX: close=400.0
    (as-traded that day, pre-split basis) vs adjClose=40.0 (rebased to post-split "today")."""
    return price_pkg("NFLX", "2022-10-12", adj_close=40.0, close=400.0, split_factor=10.0)


def _amzn_proxied_gt():
    """AMZN_20221012, issue #36 audit tail on PR #38: shares_current is a PROXY (edgar_facts.py
    falls back to the latest annual shares_diluted when no filing's dei cover page is available,
    flagging gt['_flags']['shares_current_proxied']) -- an annual figure exactly as blind to a
    sub-annual split as the eps/fcf series it is meant to check. shares_current is deliberately
    set EQUAL to shares_diluted(2021-12-31) (ratio 1.0x, no clean-factor jump) so this fixture
    proves the refusal comes from the degraded-witness flag itself, not from the ratio check --
    before the audit-tail fix, this exact input silently scored (ratio 1.0 looks like 'no split',
    which is precisely the false negative the flag exists to catch)."""
    return gt("AMZN", cik=1018724, as_of="2022-10-12",
             revenue=_REV36,
             net_income=series([("2021-12-31", 200.0)]),
             shares_diluted=series([("2021-12-31", 100.0)]),
             ocf=series([("2021-12-31", 300.0)]),
             capex=series([("2021-12-31", 50.0)]),
             roe_median_5y=0.20, shares_current=100.0,
             flags={"shares_current_proxied": "cover-page count unavailable; proxied to latest "
                    "weighted-avg diluted shares (2021-12-31)"})


def _amzn_proxied_price():
    return price_pkg("AMZN", "2022-10-12", adj_close=40.0, close=40.0, split_factor=1.0)


class TestGoldenCase1CleanNoSplitNoBuy(unittest.TestCase):

    def test_full_pipeline_matches_hand_computed_arithmetic(self):
        row_out = hr.score_pair("GOLD1", "2020-03-23", _gold1_gt(), _gold1_price())
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


class TestGoldenCase2SplitAndRoeCapBuy(unittest.TestCase):

    def test_full_pipeline_matches_hand_computed_arithmetic(self):
        row_out = hr.score_pair("GOLD2", "2020-03-23", _gold2_gt(), _gold2_price())
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
        correct = hr.score_pair("GOLD2", "2020-03-23", _gold2_gt(), _gold2_price())
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
        gt_row = {"revenue": [{"end": "%d-12-31" % y, "val": v} for y, v in
                              zip(range(2014, 2020), [100 * 1.30 ** n for n in range(6)])]}
        g, rc3, rc5, reason = hr.compute_growth_anchor(gt_row)
        self.assertIsNone(reason)
        self.assertAlmostEqual(g, 0.20, places=6)

    def test_refuses_by_name_when_history_too_short_for_either_window(self):
        gt_row = {"revenue": [{"end": "2018-12-31", "val": 100}, {"end": "2019-12-31", "val": 110}]}
        g, rc3, rc5, reason = hr.compute_growth_anchor(gt_row)
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


class TestNegativeControlsRefuseByName(unittest.TestCase):
    """PREREG §5.1: a refusal IS a result, not a defect to paper over. Each of the three
    'непригодна' classes named in issue #28 gets its own named-refusal pin here."""

    def test_young_name_insufficient_revenue_history_refuses(self):
        edgar = gt("YOUNGCO", cik=3333333,
                  revenue=series([("2018-12-31", 100.0), ("2019-12-31", 110.0)]))
        out = hr.score_pair("YOUNGCO", "2020-03-23", edgar,
                            price_pkg("YOUNGCO", "2020-03-23", adj_close=10.0, split_factor=1.0))
        self.assertEqual(out["status"], "REFUSED")
        self.assertIsNotNone(out["reason"])

    def test_no_trading_day_on_record_refuses_not_a_guess_at_the_nearest_day(self):
        out = hr.score_pair("GOLD1", "2020-03-23", _gold1_gt(),
                            price_pkg("GOLD1", "2020-03-23", no_record=True))
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("no trading record", out["reason"])

    def test_split_factor_undeterminable_refuses(self):
        """issue #30: the archive ships split_factor already computed (or, on refusal, None plus
        a named reason in _errors) -- this mirrors the case where macro_prices.
        split_factor_since() itself refused at archive-build time (product/ratio disagreement,
        see test_historical_stand.TestSameShareBasisPE)."""
        price = price_pkg("GOLD1", "2020-03-23", adj_close=100.0, close=1200.0, split_factor=None,
                          errors={"split_factor_GOLD1":
                                  "split_factor_undeterminable: splitFactor product 10.0000 "
                                  "disagrees with close/adjClose ratio 12.0000 beyond tolerance"})
        out = hr.score_pair("GOLD1", "2020-03-23", _gold1_gt(), price)
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("split_factor_undeterminable", out["reason"])


class TestCikFieldNaming(unittest.TestCase):
    """issue #30: the real archive's *_edgar.json carries the CIK as '_cik' (edgar_facts()'s own
    field name), not the bare 'cik' the tool originally assumed -- the first real run scored
    0/175 on exactly this. '_cik' is read as primary, bare 'cik' kept as a fallback ONLY for
    fixtures/tools that predate this fix; absence of both is the same named refusal as before."""

    def test_underscore_cik_is_read(self):
        edgar = _gold1_gt()
        self.assertIn("_cik", edgar)
        self.assertNotIn("cik", edgar)
        out = hr.score_pair("GOLD1", "2020-03-23", edgar, _gold1_price())
        self.assertEqual(out["status"], "SCORED", out.get("reason"))

    def test_bare_cik_fallback_still_works(self):
        edgar = _gold1_gt()
        edgar["cik"] = edgar.pop("_cik")
        self.assertIn("cik", edgar)
        self.assertNotIn("_cik", edgar)
        out = hr.score_pair("GOLD1", "2020-03-23", edgar, _gold1_price())
        self.assertEqual(out["status"], "SCORED", out.get("reason"))

    def test_neither_cik_field_refuses_by_name(self):
        edgar = _gold1_gt()
        del edgar["_cik"]
        out = hr.score_pair("GOLD1", "2020-03-23", edgar, _gold1_price())
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("cik", out["reason"])


class TestArchiveDateSyncedWithAsOfAndPriceDate(unittest.TestCase):
    """issue #32: score_pair() took date_iso only from the ARCHIVE FILENAME and never checked it
    against the two dates the archive's own records carry (gt['_as_of'], price_json['date']) -- a
    desynced archive (e.g. a file paired under the wrong name) would silently score under a date
    that isn't the one its own numbers were computed for, instead of refusing. Both real-world
    shapes get their OWN named refusal so a reader can tell "wrong date" from "no date at all"
    (the second is the real VOO/ETF case: edgar_facts() found no fiscal-period anchor to stamp,
    which is not the same defect as a mismatch and must not print 'None' as if it were a date)."""

    def test_matching_as_of_and_price_date_scores_normally(self):
        # sanity: the two dates agreeing (the common case, and every other fixture in this file)
        # must not be newly refused by this change.
        out = hr.score_pair("GOLD1", "2020-03-23", _gold1_gt(), _gold1_price())
        self.assertEqual(out["status"], "SCORED", out.get("reason"))

    def test_as_of_mismatch_refuses_with_both_dates_named(self):
        edgar = _gold1_gt()
        edgar["_as_of"] = "2020-03-20"
        out = hr.score_pair("GOLD1", "2020-03-23", edgar, _gold1_price())
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("2020-03-23", out["reason"])
        self.assertIn("2020-03-20", out["reason"])

    def test_as_of_null_gets_its_own_named_refusal_not_a_mismatch(self):
        # the real ETF (VOO) case: a valid filename, but _as_of is null in the archived record.
        edgar = _gold1_gt()
        edgar["_as_of"] = None
        out = hr.score_pair("VOO", "2020-03-23", edgar, price_pkg("VOO", "2020-03-23", adj_close=40.0))
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("no _as_of", out["reason"])
        self.assertNotIn("None", out["reason"])

    def test_price_date_mismatch_refuses_with_both_dates_named(self):
        price = _gold1_price()
        price["date"] = "2020-03-20"
        out = hr.score_pair("GOLD1", "2020-03-23", _gold1_gt(), price)
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("2020-03-23", out["reason"])
        self.assertIn("2020-03-20", out["reason"])


class TestShadowDcfNeverFeedsTheOfficialVerdict(unittest.TestCase):

    def test_shadow_dcf_absent_when_fcf_leg_unavailable_official_still_scores(self):
        edgar = _gold1_gt()
        edgar["ocf"] = []       # strip the FCF leg's inputs -- only the EPS leg remains usable
        edgar["capex"] = []
        out = hr.score_pair("GOLD1", "2020-03-23", edgar, _gold1_price())
        self.assertEqual(out["status"], "SCORED")
        self.assertEqual(out["verdict_leg_note"], "single_leg")
        self.assertIsNone(out["shadow_dcf"]["intrinsic_value"])
        self.assertIn("EXPLORATORY", out["shadow_dcf"]["label"])
        # official verdict is UNCHANGED by the shadow leg being unavailable
        self.assertAlmostEqual(out["intrinsic_value"], 22.61, places=2)


class TestSingleLegSurfacesMissingLegReason(unittest.TestCase):
    """Issue #28 audit round 2, item 2: a single_leg row must publish WHY the other leg is
    missing (eps_reason/fcf_reason), on the row, in the CSV, and in the report table -- not
    just the fact that it's single_leg. GOLD3 (see its fixture docstring) refuses the EPS leg
    by name (no common FY end -- net_income/shares_diluted share no end) while the FCF leg
    scores normally through the split adjustment; numbers below are from the tool's own output
    (`hr.score_pair`), not hand-derived, since the arithmetic is identical to GOLD2's already
    hand-verified FCF leg (fcf_today = (560-60)/50 / 4.0 = 2.50)."""

    def test_row_names_the_missing_leg_reason(self):
        out = hr.score_pair("GOLD3", "2020-03-23", _gold3_gt(), _gold3_price())
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        self.assertEqual(out["verdict_leg_note"], "single_leg")
        self.assertEqual(out["verdict_leg"], "fcf_per_share")
        self.assertIsNone(out["fcf_reason"])
        self.assertIsNotNone(out["eps_reason"])
        self.assertIn("no common FY end", out["eps_reason"])
        self.assertAlmostEqual(out["intrinsic_value"], 43.53, places=2)
        self.assertAlmostEqual(out["implied_cagr_pct"], 24.59, places=2)

    def test_csv_and_report_carry_the_missing_leg_reason(self):
        out = hr.score_pair("GOLD3", "2020-03-23", _gold3_gt(), _gold3_price())
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


class TestPeHistMedianNoteIsPublished(unittest.TestCase):
    """Issue #28 audit round 2, item 1: pe_hist_median_note (already computed in score_pair)
    must reach the CSV column and the report's notes column, and the cell is never empty when
    the median is ABSENT from the archive (the mandate's own wording)."""

    def test_absent_median_note_is_non_empty_on_both_surfaces(self):
        out = hr.score_pair("GOLD1", "2020-03-23", _gold1_gt(), _gold1_price())
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
        # issue #30: pe_hist_median now lives at the TOP level of *_price.json, alongside
        # split_factor -- see ФОРМАТ АРХИВА / PROTOCOL_GAPS in tools/historical_run.py.
        price = price_pkg("GOLD1", "2020-03-23", adj_close=40.0, split_factor=1.0,
                          pe_hist_median=14.0)
        out = hr.score_pair("GOLD1", "2020-03-23", _gold1_gt(), price)
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        self.assertEqual(out["pe_hist_median"], 14.0)
        self.assertIsNone(out["pe_hist_median_note"])   # nothing to explain -- median was found

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


class TestFcfBasisAdjustAppliedToPublishedIv(unittest.TestCase):
    """Guards mutation case histrun-basis-bypass-02: on a single_leg-FCF row, the published IV
    and split_factor_fcf must come from the split-ADJUSTED fcf/share (2.50), never the as-filed
    one (10.00) -- see GOLD3's fixture docstring for why the EPS leg is unavailable here, which
    makes the FCF leg's own basis_adjust the ONLY thing standing between the officially
    published number and a ~4x-inflated one."""

    def test_published_iv_and_split_factor_use_the_adjusted_fcf(self):
        out = hr.score_pair("GOLD3", "2020-03-23", _gold3_gt(), _gold3_price())
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


class TestSensitivityBoundsArePublished(unittest.TestCase):
    """score_pair() already computes the full k_exit grid (0.08/0.09/0.10) into row['sensitivity']
    (see PREREG §8); this pins that the 8% and 10% bounds actually reach the CSV and the report
    table, not just the in-memory row -- a field computed but never written is not a result."""

    def test_csv_and_report_carry_both_sensitivity_bounds(self):
        row_out = hr.score_pair("GOLD1", "2020-03-23", _gold1_gt(), _gold1_price())
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
        rows = [hr.score_pair("GOLD1", "2020-03-23", _gold1_gt(), _gold1_price()),
               hr.score_pair("GOLD2", "2020-03-23", _gold2_gt(), _gold2_price()),
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


class TestScorePairIsFullyOffline(unittest.TestCase):
    """issue #30: score_pair() now reads the archive's OWN already-computed edgar_facts() output
    and already-computed split_factor directly -- there is no live edgar_facts()/macro_prices()
    call left to make, so the network-hole class audit round 3 found (an un-preseeded
    companyconcept fetch inside a live edgar_facts() re-invocation) cannot recur structurally:
    historical_run.py no longer imports either module at all. Proven at the module level, not by
    patching a network entry point that no longer exists in this file."""

    def test_no_edgar_facts_or_macro_prices_module_bound_in_historical_run(self):
        self.assertFalse(hasattr(hr, "ef"))
        self.assertFalse(hasattr(hr, "edgar_facts"))
        self.assertFalse(hasattr(hr, "mp"))
        self.assertFalse(hasattr(hr, "macro_prices"))

    def test_score_pair_runs_without_sec_user_agent_or_tiingo_token_env(self):
        env_keys = ("SEC_USER_AGENT", "TIINGO_TOKEN")
        saved = {k: os.environ.pop(k, None) for k in env_keys}
        try:
            out = hr.score_pair("GOLD2", "2020-03-23", _gold2_gt(), _gold2_price())
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
        self.assertEqual(out["status"], "SCORED", out.get("reason"))


class TestBasisEndAndLegNotePublished(unittest.TestCase):
    """Issue #28 audit round 3, item 2: eps_basis_end/fcf_basis_end/verdict_leg_note (already
    computed in score_pair()) must reach both the CSV and the report table, not just the
    in-memory row -- the same class of gap audit round 2 found for pe_hist_median_note and
    eps_reason/fcf_reason."""

    def test_csv_and_report_carry_basis_ends_and_leg_note(self):
        out = hr.score_pair("GOLD2", "2020-03-23", _gold2_gt(), _gold2_price())
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        self.assertEqual(out["eps_basis_end"], "2019-12-31")
        self.assertEqual(out["fcf_basis_end"], "2019-12-31")
        self.assertEqual(out["verdict_leg_note"], "dual_basis_conservative")

        with tempfile.TemporaryDirectory() as d:
            csv_path = os.path.join(d, "out.csv")
            md_path = os.path.join(d, "out.md")
            hr.write_csv([out], csv_path)
            hr.write_report([out], md_path)

            with open(csv_path, encoding="utf-8") as f:
                csv_row = next(csv.DictReader(f))
            self.assertIn("eps_basis_end", csv_row)
            self.assertIn("fcf_basis_end", csv_row)
            self.assertIn("verdict_leg_note", csv_row)
            self.assertEqual(csv_row["eps_basis_end"], "2019-12-31")
            self.assertEqual(csv_row["fcf_basis_end"], "2019-12-31")
            self.assertEqual(csv_row["verdict_leg_note"], "dual_basis_conservative")

            with open(md_path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("Leg note", text)
            self.assertIn("EPS basis FY", text)
            self.assertIn("FCF basis FY", text)
            self.assertIn("2019-12-31", text)
            self.assertIn("dual_basis_conservative", text)


class TestEveryRowKeyIsPublished(unittest.TestCase):
    """Issue #28 audit round 3, item 3: every non-underscore key score_pair() puts on a SCORED
    row must reach an output surface -- either verbatim in CSV_FIELDS, or as a documented
    compound field in CSV_COMPOUND_FIELDS (flattened by write_csv). Internal-only fields carry a
    leading underscore (_grid, _gt_flags) and are exempt by construction. Audit rounds 1 and 2
    each found ONE unpublished field by inspection (pe_hist_median_note, then eps_reason/
    fcf_reason) -- this pin is the class fix, so the next one is caught by a test, not a re-read."""

    def test_scored_row_keys_all_reach_csv_or_are_documented_compound_fields(self):
        for out in (hr.score_pair("GOLD1", "2020-03-23", _gold1_gt(), _gold1_price()),
                   hr.score_pair("GOLD2", "2020-03-23", _gold2_gt(), _gold2_price()),
                   hr.score_pair("GOLD3", "2020-03-23", _gold3_gt(), _gold3_price())):
            self.assertEqual(out["status"], "SCORED", out.get("reason"))
            unpublished = [k for k in out
                          if not k.startswith("_")
                          and k not in hr.CSV_FIELDS
                          and k not in hr.CSV_COMPOUND_FIELDS]
            self.assertEqual(unpublished, [],
                             "score_pair() produced field(s) that reach no output surface: %r"
                             % unpublished)


class TestConservativeLegSelectionPicksTheLowerCagr(unittest.TestCase):
    """Issue #28 audit round 3, item 4: guards mutation histrun-conservative-flip-01 (the <=
    comparison choosing the conservative leg in score_pair()'s dual_basis branch flipped to
    >=). GOLD1/GOLD2 both happen to pick gaap_eps, so neither can distinguish a flipped
    comparison from a correct one that always prefers the same leg by coincidence -- GOLD4 is
    built so the FCF leg has the LOWER implied_cagr_pct, so a flip to >= would silently pick
    gaap_eps (the optimistic leg) instead."""

    def test_fcf_leg_wins_when_it_is_the_more_conservative_one(self):
        out = hr.score_pair("GOLD4", "2020-03-23", _gold4_gt(), _gold4_price())
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        self.assertEqual(out["verdict_leg_note"], "dual_basis_conservative")
        self.assertEqual(out["verdict_leg"], "fcf_per_share")


class TestBasisGapAmznRefusesNeverTheOldMixedBasisNumber(unittest.TestCase):
    """Issue #36: the archived split_factor covers [date_iso, today], never [eps_basis_end/
    fcf_basis_end, today] -- see basis_gap_reason()'s own docstring and PROTOCOL_GAPS. AMZN's
    real case (split_factor_eps=1.0, eps_basis_end=2021-12-31, observed 2022-10-12, a 20:1 split
    in between): before this fix, basis_adjust() would have divided by 1.0 (a no-op) and fed the
    PRE-split eps_af straight to ivc() against the POST-split price -- exactly GOLD1's own
    arithmetic (IV=22.61, see the module docstring's GOLDEN CASE 1 and the naive-IV check below),
    a plausible-LOOKING but wrong number, the same danger class as the real run's IV=1398.36.
    This pair must now refuse by name, citing both the basis FY end and the observation date."""

    def test_amzn_20221012_refuses_naming_both_dates(self):
        out = hr.score_pair("AMZN", "2022-10-12", _amzn_gap_gt(), _amzn_gap_price())
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("2021-12-31", out["reason"])
        self.assertIn("2022-10-12", out["reason"])
        self.assertIn("split", out["reason"])

    def test_amzn_20221012_never_reports_a_number_let_alone_the_old_mixed_basis_one(self):
        out = hr.score_pair("AMZN", "2022-10-12", _amzn_gap_gt(), _amzn_gap_price())
        self.assertEqual(out["status"], "REFUSED")
        self.assertNotIn("intrinsic_value", out)

    def test_pre_fix_mixed_basis_would_have_looked_plausible_not_absurd(self):
        """Documents WHY a refusal is the right call rather than a number that would fail some
        other sanity gate: fed straight to ivc() (the pre-#36 path), AMZN's own as-filed eps/fcf
        reproduce GOLD1's already-hand-verified, entirely unremarkable-looking numbers -- a wrong
        answer that does not announce itself as wrong."""
        import ivc_lib
        r = ivc_lib.ivc({"price": 40.0, "eps_normalized": 2.00, "growth_rate": 0.10,
                         "future_pe": 16.0, "hurdle": 0.12, "discount_rate": 0.12,
                         "terminal_growth": 0.04})
        self.assertAlmostEqual(r["intrinsic_value"], 22.61, places=2)


class TestSplitAfterObservationDateNflxStaysScoredUnchanged(unittest.TestCase):
    """Issue #36's negative control ("защита от перепочинки"): NFLX_20221012's split is effective
    AFTER the observation date, so it sits entirely inside [date_iso, today] -- the window the
    archived split_factor=10.0 already, correctly, covers. basis_gap_reason() must NOT fire here
    (shares_current == shares_diluted(basis_end), no clean-factor jump), and the pair must stay
    SCORED with numbers identical to GOLD1's hand-verified arithmetic (the fixture is scaled by
    exactly 10x on eps/fcf so dividing by split_factor=10.0 reproduces GOLD1's inputs exactly)."""

    def test_nflx_20221012_stays_scored_with_gold1s_hand_verified_numbers(self):
        out = hr.score_pair("NFLX", "2022-10-12", _nflx_safe_gt(), _nflx_safe_price())
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        self.assertEqual(out["split_factor_eps"], 10.0)
        self.assertEqual(out["split_factor_fcf"], 10.0)
        self.assertEqual(out["eps_basis_end"], "2021-12-31")
        self.assertAlmostEqual(out["future_pe_k9"], 16.0, places=6)
        self.assertEqual(out["verdict_leg"], "gaap_eps")
        self.assertAlmostEqual(out["intrinsic_value"], 22.61, places=2)
        self.assertAlmostEqual(out["implied_cagr_pct"], 5.79, places=2)
        self.assertEqual(out["hurdle_gate"], "FAIL")
        self.assertFalse(out["buy_A_no_discount"])
        self.assertFalse(out["buy_B_10pct_discount"])


class TestBasisGapProxiedSharesCurrentRefusesAsDegradedWitness(unittest.TestCase):
    """Issue #36 audit tail on PR #38: basis_gap_reason() used to trust shares_current
    unconditionally, but edgar_facts.py proxies it to the latest ANNUAL shares_diluted (flagging
    gt['_flags']['shares_current_proxied']) when no filing's dei cover page is available -- in
    that mode the witness is exactly as blind to a sub-annual split as the annual eps/fcf series
    it exists to check, so 'ratio == 1.0, no clean jump' means 'cannot tell', not 'no split'. The
    fixture sets shares_current == shares_diluted(basis_end) (ratio 1.0x) specifically so this
    pin cannot pass by accident via the ordinary ratio path -- only the flag check can refuse it."""

    def test_amzn_proxied_refuses_naming_both_dates_and_the_degraded_witness(self):
        out = hr.score_pair("AMZN", "2022-10-12", _amzn_proxied_gt(), _amzn_proxied_price())
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("2021-12-31", out["reason"])
        self.assertIn("2022-10-12", out["reason"])
        self.assertIn("proxied", out["reason"])

    def test_amzn_proxied_never_reports_a_number(self):
        out = hr.score_pair("AMZN", "2022-10-12", _amzn_proxied_gt(), _amzn_proxied_price())
        self.assertEqual(out["status"], "REFUSED")
        self.assertNotIn("intrinsic_value", out)


class TestPriceRecordMissingDateFieldRefusesNamed(unittest.TestCase):
    """Issue #33 audit tail: a price archive record with no 'date' field at all (as opposed to a
    'date' present but disagreeing with the filename) fell through the old `isinstance(price_date,
    str)` guard silently and was never checked -- a missing field looked exactly like "field
    present and agrees". Must now be its own named refusal, the same class of fix as gt_as_of
    being None above (TestArchiveDateSyncedWithAsOfAndPriceDate)."""

    def test_missing_date_field_refuses_by_name(self):
        price = _gold1_price()
        del price["date"]
        out = hr.score_pair("GOLD1", "2020-03-23", _gold1_gt(), price)
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("no usable 'date' field", out["reason"])
        self.assertIn("2020-03-23", out["reason"])

    def test_non_string_date_field_refuses_by_name(self):
        price = _gold1_price()
        price["date"] = 20200323   # a plausible operator mistake: an int, not an ISO string
        out = hr.score_pair("GOLD1", "2020-03-23", _gold1_gt(), price)
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("no usable 'date' field", out["reason"])


class TestRealArchiveFixtureNVDA(unittest.TestCase):
    """issue #30's own acceptance mandate: a test on a REAL archive record, driven all the way to
    status=SCORED with concrete numbers -- not a synthetic fixture that merely LOOKS like the
    real format. tests/fixtures/NVDA_20200323_edgar.json / _price.json are the two files from
    Reports/histrun_2026-08-08/histrun_raw_v3.zip's NVDA_20200323 pair, copied byte-for-byte
    (re-serialized, same content) -- the exact pair that used to REFUSE with "edgar archive
    record has no usable 'cik' field" before this fix. Numbers below are read from the tool's
    own output against these files, not hand-derived (NVDA's real EDGAR history -- confirmed
    4:1 and 10:1 splits since 2020-03-23, compounding to split_factor=40.0 -- is not arithmetic
    anyone should hand-check; the point of this pin is that the REAL archive reaches SCORED at
    all, matching PREREG's own machinery, not that these specific digits are independently
    re-derived)."""

    @classmethod
    def setUpClass(cls):
        import json
        with open(os.path.join(_FIXTURES_DIR, "NVDA_20200323_edgar.json"), encoding="utf-8") as f:
            cls.edgar = json.load(f)
        with open(os.path.join(_FIXTURES_DIR, "NVDA_20200323_price.json"), encoding="utf-8") as f:
            cls.price = json.load(f)

    def test_fixture_is_the_real_archive_shape_not_a_guess(self):
        # the exact discrepancy issue #30 reported: real records carry '_cik', not 'cik'.
        self.assertIn("_cik", self.edgar)
        self.assertNotIn("cik", self.edgar)
        self.assertIsInstance(self.price, dict)
        self.assertIn("price_record", self.price)
        self.assertIn("split_factor", self.price)

    def test_nvda_20200323_reaches_scored_with_numbers(self):
        out = hr.score_pair("NVDA", "2020-03-23", self.edgar, self.price)
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        self.assertEqual(out["cik"], "0001045810")
        self.assertEqual(out["verdict_leg"], "fcf_per_share")
        self.assertEqual(out["verdict_leg_note"], "dual_basis_conservative")
        self.assertAlmostEqual(out["growth_rate"], 0.16472039648286363, places=6)
        self.assertAlmostEqual(out["terminal_growth"], 0.04, places=6)
        self.assertAlmostEqual(out["roe_median_5y"], 0.28913571676501215, places=6)
        self.assertAlmostEqual(out["future_pe_k9"], 17.23313325330132, places=4)
        self.assertEqual(out["future_pe_source"], "formula_no_median_available")
        self.assertEqual(out["split_factor_eps"], 40.0)
        self.assertEqual(out["split_factor_fcf"], 40.0)
        self.assertAlmostEqual(out["intrinsic_value"], 0.57, places=2)
        self.assertAlmostEqual(out["implied_cagr_pct"], -10.37, places=2)
        self.assertEqual(out["hurdle_gate"], "FAIL")
        self.assertFalse(out["buy_A_no_discount"])
        self.assertFalse(out["buy_B_10pct_discount"])
        self.assertIsNone(out["pe_hist_median"])   # not present in this record -- see PROTOCOL_GAPS

    def test_nvda_reaches_csv_and_report_without_raising(self):
        out = hr.score_pair("NVDA", "2020-03-23", self.edgar, self.price)
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        with tempfile.TemporaryDirectory() as d:
            csv_path = os.path.join(d, "out.csv")
            md_path = os.path.join(d, "out.md")
            hr.write_csv([out], csv_path)
            hr.write_report([out], md_path)
            with open(csv_path, encoding="utf-8") as f:
                csv_row = next(csv.DictReader(f))
            self.assertEqual(csv_row["ticker"], "NVDA")
            self.assertEqual(csv_row["status"], "SCORED")


class TestRealArchiveFixtureAMZNRefusesUnderNewTolerance(unittest.TestCase):
    """issue #39's own acceptance mandate, item 3: a pin on the REAL archive AMZN_20221012 pair
    (not the synthetic near-clone in _amzn_gap_gt() above), copied byte-for-byte from
    Reports/histrun_2026-08-08/histrun_raw_v3.zip -- the exact real pair the issue reports:
    shares_current=10187554818, shares_diluted(2021-12-31)=515000000, ratio 19.7817x against a
    clean 20x split signature, 1.0917% away. The OLD 1% tolerance (edgar_facts.py's own, reused
    verbatim here before this fix) missed this by 0.0917pp and let the pair through as SCORED
    with intrinsic_value=1398.36, implied_cagr_pct=44.05 -- the issue's own '19.78x' / '44% CAGR'
    false BUY. _SHARES_CURRENT_GAP_TOLERANCE (1.5%, see its own comment in historical_run.py for
    the archive-wide justification) must catch it."""

    @classmethod
    def setUpClass(cls):
        import json
        with open(os.path.join(_FIXTURES_DIR, "AMZN_20221012_edgar.json"), encoding="utf-8") as f:
            cls.edgar = json.load(f)
        with open(os.path.join(_FIXTURES_DIR, "AMZN_20221012_price.json"), encoding="utf-8") as f:
            cls.price = json.load(f)

    def test_fixture_reproduces_the_issues_own_numbers(self):
        sh_basis = hr._value_at(self.edgar["shares_diluted"], "2021-12-31")
        self.assertEqual(self.edgar.get("shares_current"), 10187554818)
        self.assertEqual(sh_basis, 515000000)
        ratio = self.edgar["shares_current"] / sh_basis
        self.assertAlmostEqual(ratio, 19.781659840776697, places=6)
        # the exact gap the old 1% tolerance missed and the new 1.5% one catches:
        self.assertGreater(abs(ratio - 20) / 20, 0.01)
        self.assertLessEqual(abs(ratio - 20) / 20, hr._SHARES_CURRENT_GAP_TOLERANCE)

    def test_real_amzn_20221012_refuses_naming_both_dates(self):
        out = hr.score_pair("AMZN", "2022-10-12", self.edgar, self.price)
        self.assertEqual(out["status"], "REFUSED", out.get("reason"))
        self.assertIn("2021-12-31", out["reason"])
        self.assertIn("2022-10-12", out["reason"])
        self.assertIn("split", out["reason"])

    def test_real_amzn_20221012_never_reports_the_false_buy_number(self):
        out = hr.score_pair("AMZN", "2022-10-12", self.edgar, self.price)
        self.assertEqual(out["status"], "REFUSED")
        self.assertNotIn("intrinsic_value", out)

    def test_pre_fix_1pct_tolerance_would_have_silently_scored_this_pair(self):
        """Documents the defect this pin exists to catch: at the OLD tolerance (0.01, reverted
        here on a local copy of the function's own math, not by mutating the module) the ratio
        check would not have fired at all, and the pair would have reached SCORED with the
        issue's own false-BUY numbers -- see TestRealArchiveFixtureAMZNRefusesUnderNewTolerance
        below for the actual reproduction on the live module state."""
        ratio = self.edgar["shares_current"] / hr._value_at(self.edgar["shares_diluted"], "2021-12-31")
        factor = next((c for c in hr._CLEAN_SPLIT_FACTORS if abs(ratio - c) / c <= 0.01), None)
        self.assertIsNone(factor, "old 1%% tolerance already misses this ratio (%.4f%% away)" %
                          (abs(ratio - 20) / 20 * 100))


class TestRealArchiveFixtureMSFTStaysScoredUnderNewTolerance(unittest.TestCase):
    """issue #39 mandate, item 4: a negative-control pin on a REAL archive pair with no split in
    the gap -- MSFT_20211231, one of the two examples the issue names explicitly ('например
    NVDA_20200323 или MSFT_20211231'), copied byte-for-byte from the real archive. Its ratio
    (shares_current/shares_diluted(2021-06-30)) is nowhere near any clean split factor (0.9869x --
    ordinary buybacks, not a split); this guards against the widened tolerance starting to refuse
    ordinary pairs wholesale."""

    @classmethod
    def setUpClass(cls):
        import json
        with open(os.path.join(_FIXTURES_DIR, "MSFT_20211231_edgar.json"), encoding="utf-8") as f:
            cls.edgar = json.load(f)
        with open(os.path.join(_FIXTURES_DIR, "MSFT_20211231_price.json"), encoding="utf-8") as f:
            cls.price = json.load(f)

    def test_real_msft_20211231_stays_scored_with_no_gap_named(self):
        out = hr.score_pair("MSFT", "2021-12-31", self.edgar, self.price)
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        self.assertIsNone(out["eps_reason"])
        self.assertIsNone(out["fcf_reason"])

    def test_real_msft_20211231_numbers_match_the_tools_own_output(self):
        out = hr.score_pair("MSFT", "2021-12-31", self.edgar, self.price)
        self.assertEqual(out["status"], "SCORED", out.get("reason"))
        self.assertEqual(out["eps_basis_end"], "2021-06-30")
        self.assertEqual(out["split_factor_eps"], 1.0)
        self.assertAlmostEqual(out["intrinsic_value"], 112.71, places=2)
        self.assertAlmostEqual(out["implied_cagr_pct"], 0.78, places=2)


class TestBasisGapPltrRealDilutionNeverReadsAsASplit(unittest.TestCase):
    """issue #39: PLTR_20211231 is the CLOSEST any non-split pair comes to a clean split factor
    anywhere in the real 175-pair archive -- ratio 2.0331x vs a clean 2x, 1.6571% away (heavy
    RSU-driven dilution in PLTR's first full year after its September-2020 direct listing, not a
    split; see gt['_flags'] in the fixture -- no confirmed_splits, no restatement). This is the
    tightest real boundary case _SHARES_CURRENT_GAP_TOLERANCE (1.5%) has to clear on the safe
    side: basis_gap_reason() must NOT read this ratio as a split signature.

    PLTR's overall row still REFUSES in this archive -- for the unrelated, pre-existing reason
    that roe_median_5y is unavailable (gt['_flags']['roe_median_5y_refused']: negative equity in
    2018/2019) -- so this pin exercises basis_gap_reason() and eps_reason/fcf_reason directly on
    the real numbers, rather than asserting an overall SCORED status the real data does not
    support. Asserting 'SCORED' here would be exactly the kind of invented number rule 6 forbids."""

    @classmethod
    def setUpClass(cls):
        import json
        with open(os.path.join(_FIXTURES_DIR, "PLTR_20211231_edgar.json"), encoding="utf-8") as f:
            cls.edgar = json.load(f)
        with open(os.path.join(_FIXTURES_DIR, "PLTR_20211231_price.json"), encoding="utf-8") as f:
            cls.price = json.load(f)

    def test_ratio_is_the_closest_real_non_split_to_a_clean_factor(self):
        sh_basis = hr._value_at(self.edgar["shares_diluted"], "2020-12-31")
        self.assertEqual(self.edgar.get("shares_current"), 1991118000)
        self.assertEqual(sh_basis, 979330067)
        ratio = self.edgar["shares_current"] / sh_basis
        self.assertAlmostEqual(ratio, 2.0331429281033193, places=6)
        dev = abs(ratio - 2) / 2
        self.assertAlmostEqual(dev, 0.016571464051659657, places=6)
        self.assertGreater(dev, hr._SHARES_CURRENT_GAP_TOLERANCE)   # outside the window -> no gap

    def test_basis_gap_reason_does_not_fire_on_either_leg(self):
        eps_af, eps_end, _ = hr.compute_eps_leg(self.edgar)
        fcf_af, fcf_end, _ = hr.compute_fcf_leg(self.edgar)
        self.assertIsNotNone(eps_af)
        self.assertIsNotNone(fcf_af)
        sh_eps = hr._value_at(self.edgar["shares_diluted"], eps_end)
        sh_fcf = hr._value_at(self.edgar["shares_diluted"], fcf_end)
        self.assertIsNone(hr.basis_gap_reason(self.edgar, eps_end, "2021-12-31", sh_eps, "eps"))
        self.assertIsNone(hr.basis_gap_reason(self.edgar, fcf_end, "2021-12-31", sh_fcf, "fcf"))

    def test_real_pltr_20211231_refuses_for_roe_not_for_a_basis_gap(self):
        out = hr.score_pair("PLTR", "2021-12-31", self.edgar, self.price)
        self.assertEqual(out["status"], "REFUSED")
        self.assertIn("roe_median_5y", out["reason"])
        self.assertNotIn("split", out["reason"])
        self.assertNotIn("basis gap", out["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
