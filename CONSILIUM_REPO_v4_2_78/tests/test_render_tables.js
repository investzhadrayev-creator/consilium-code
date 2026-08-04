/**
 * Execution test for the "Render Tables" and "Build Radar" code nodes.
 *
 * These two nodes are JavaScript running inside n8n, so the Python suite cannot reach them —
 * yet Render Tables is the single source of every number in the final report, and both nodes
 * have already shipped real bugs (GPS double-count in v2.4; Russian labels leaking into the
 * English report in v2.8/v3.0, where Build Radar was missed precisely because it is a SEPARATE
 * node from Render Tables' 26KB body).
 *
 * This harness mocks just enough of the n8n runtime ($, $input) to execute the real node code
 * against a realistic RESULT and assert on the rendered markdown. No n8n instance, no network.
 *
 * Run:  node tests/test_render_tables.js
 */
const fs = require('fs');
const path = require('path');

// ---------- locate the current workflow (highest version, same rule as _support.py) ----------
const WORKFLOW_DIR = path.join(__dirname, '..', 'workflow');
const wfFile = fs.readdirSync(WORKFLOW_DIR)
  .filter(f => /^consilium_spine_v[\d_]+\.json$/.test(f))
  .sort((a, b) => {
    const v = s => s.replace(/^consilium_spine_v|\.json$/g, '').split('_').map(Number);
    const [av, bv] = [v(a), v(b)];
    for (let i = 0; i < Math.max(av.length, bv.length); i++) {
      if ((av[i] || 0) !== (bv[i] || 0)) return (av[i] || 0) - (bv[i] || 0);
    }
    return 0;
  })
  .pop();
if (!wfFile) { console.error('FAIL: no workflow JSON found in ' + WORKFLOW_DIR); process.exit(1); }
const WF = JSON.parse(fs.readFileSync(path.join(WORKFLOW_DIR, wfFile), 'utf8'));
const nodeByName = Object.fromEntries(WF.nodes.map(n => [n.name, n]));

// ---------- tiny assertion helpers ----------
let passed = 0, failed = 0;
// v4.2.55: check() is AWAIT-AWARE. It used to be synchronous, so `check(name, async () => ...)`
// handed it an un-awaited promise: fn() returned before a single assertion ran, nothing could
// throw, and the check printed `ok` having examined NOTHING. 18 pins in this file and 6 in
// test_render_tables.js were inert that way — including every negative control on the gate parser.
// The hazard was even DOCUMENTED at test_render_tables.js:311 and worked around locally instead of
// being removed, after which six more async checks were written below the warning. Project rule,
// one level up again: a check reports what it examined, or it reports nothing — "skipped" and
// "passed" must never print the same word. Awaiting fn() makes the async form impossible to get
// wrong instead of merely documented as wrong.
async function check(name, fn) {
  try { await fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + e.message); }
}
function assert(cond, msg) { if (!cond) throw new Error(msg || 'assertion failed'); }

// ---------- realistic RESULT, shaped exactly like the harness emits ----------
const MOCK_RESULT = {
  _harness: true, _FALLBACK: false,
  // v4.2.63: the advisory lenses, present in every real RESULT since v4.2.59. Absent from this
  // fixture the render pins below would pass on the "unavailable this run" branch and prove
  // nothing about the case that matters.
  central_lens: { iv: 420.5, growth_used: 0.152, future_pe_used: 33.4,
                  delta_iv_vs_verdict_pct: 29.0, advisory_only: true, flags: [] },
  reverse_dcf: { g_implied_at_current_price: 0.176, at_hurdle_pct: 12, future_pe_held: 25,
                 actual_rev_cagr_3y: 0.129, actual_rev_cagr_5y: 0.159,
                 selftest_reverse_matches_forward: true, advisory_only: true },
  ivc_base: {
    engine: 'eps', years: 10, implied_cagr_pct: 7.75, intrinsic_value: 326.01, mos_pct: -12.3,
    fv10_per_share: 672, eps_terminal: 24, eps_terminal_dilution_adj: 24,
    buy_threshold_hurdle: 250.4, pe_cap_effective: 32, hurdle_gate: 'FAIL',
    flags: ['growth_gt_25pct_unfaded_FORCED_FADE'],
    self_tests: { iv_recompute_ok: true, hurdle_identity_ok: 'skipped_dividend_case', pe_cap_checked: true },
    inputs: { price: 480, base_per_share: 12, g: 0.11, fade: true, terminal_g: 0.04,
              future_pe: 28, hurdle: 0.12, discount_rate: 0.12, dilution_cagr: -0.02, div_yield: 0.006 },
  },
  pwfv: 332.8, verdict_cap: 'AVOID',
  weights: { bear: 0.3, base: 0.45, bull: 0.25 },
  // v4.2.5: gps.max is 95, NOT 100, on purpose. A mock carrying the nominal 100 cannot catch a
  // renderer that hardcodes '/100' -- it would agree by coincidence and report green. That is the
  // MOCK_RESULT disease this file already documents for render branches, applied to a constant.
  // C's max is 10 here (fwd_pe unmeasurable), so the blocks sum to 95 and any '/100' is a FAIL.
  gps: {
    total: 53, max: 95,
    blocks: [
      { name: 'A (growth)', points: 8, max: 16, evidence: { rev_cagr5: 0.11 } },
      { name: 'A_runway', points: 3, max: 4, evidence: 'TAM headroom' },
      { name: 'B (profitability)', points: 9, max: 15, evidence: { roe: 1.93 } },
      { name: 'C (valuation)', points: 4, max: 10, evidence: { peg: 1.48, pts: { fwd_pe: '[UNVERIFIED]', icagr: 0, peg: 4 } } },
      { name: 'D (balance sheet)', points: 6, max: 10, evidence: { de: 2.45 } },
      { name: 'E_moat', points: 12, max: 15, evidence: 'duopoly' },
      { name: 'F (momentum)', points: 2, max: 10, evidence: { erb_90d: 0.028 } },
      { name: 'F_forecast_trend', points: 4, max: 5, evidence: 'consensus +15.9%' },
      { name: 'G_capalloc', points: 4, max: 5, evidence: 'buyback 68% FCF' },
      { name: 'H_sentiment', points: 1, max: 5, evidence: 'short 1% float' },
    ],
    quant_detail: { A: { rev_cagr5: 0.11 }, B: { roe: 1.93 }, C: { peg: 1.48 }, D: { de: 2.45 }, F: { erb_90d: 0.028 } },
  },
  scenarios: {
    bear: { weight: 0.3, overrides: { growth_rate: 0.07, future_pe: 22 },
      result: { eps_terminal: 20, eps_terminal_dilution_adj: 20, fv10_per_share: 440,
                intrinsic_value: 280, implied_cagr_pct: 5.5, hurdle_gate: 'FAIL' } },
    base: { weight: 0.45, overrides: {},
      result: { eps_terminal: 24, eps_terminal_dilution_adj: 24, fv10_per_share: 672,
                intrinsic_value: 326.01, implied_cagr_pct: 7.75, hurdle_gate: 'FAIL' } },
    bull: { weight: 0.25, overrides: { growth_rate: 0.15, future_pe: 34 },
      result: { eps_terminal: 28, eps_terminal_dilution_adj: 28, fv10_per_share: 952,
                intrinsic_value: 410, implied_cagr_pct: 11.2, hurdle_gate: 'FAIL' } },
  },
  mos_ladder: [
    { mos_target_pct: 10, buy_threshold_price: 296.4, discount_to_current_pct: 38.2, implied_cagr_at_threshold_pct: 9.2, reached: false },
    { mos_target_pct: 20, buy_threshold_price: 271.7, discount_to_current_pct: 43.4, implied_cagr_at_threshold_pct: 10.2, reached: false },
    { mos_target_pct: 30, buy_threshold_price: 250.8, discount_to_current_pct: 47.8, implied_cagr_at_threshold_pct: 11.1, reached: false },
  ],
  sensitivity: { sum_expected_impact: -8.99, pwfv_minus_ivbase: 6.79 },
  bull_bear: {
    rows: [
      { side: 'BEAR', label: 'multiple compression risk', probability: 0.4, delta_iv: -30, delta_iv_pct: -9, delta_implied_cagr_pp: -0.8, expected_impact: -12 },
      { side: 'BULL', label: 'margin expansion', probability: 0.3, delta_iv: 20, delta_iv_pct: 6, delta_implied_cagr_pp: 0.5, expected_impact: 6 },
    ],
    sum_expected_impact: -6, bull_total: 6, bear_total: -12, net_skew: -6,
  },
  gates: { hurdle_gate: 'AVOID', pe_cap_gate: 'PASS', dilution_gate: 'PASS' },
  pe_cap: { anchors_available: true, anchor_used: 38.4, flags: [] },
  self_tests_all: true,
  flags: ['peer_pe_unavailable_fallback_hist_median'],
  // --- sections added in v3.4-v4.0. They were NOT in this mock until a `gt is not defined`
  // ReferenceError reached a live run: every one of these blocks sits behind an
  // `if (isObj(res.<section>))` guard, so an absent mock key silently skips the whole branch
  // and the suite reports green while testing a v3.3-shaped report. If you add a render
  // section, add it here in the same commit.
  dual_basis: {
    gaap_eps: { iv: 325.19, implied_cagr_pct: 16.22, base_per_share: 16.70 },
    fcf_per_share: { iv: 348.37, implied_cagr_pct: 17.03, base_per_share: 24.78,
                     future_multiple: 18.0, gross_dilution_used: -0.0036 },
    gap_iv_pct: 7.1, conservative_leg: 'gaap_eps', verdict_leg: 'gaap_eps',
  },
  market_context: {
    multiple_compression: { fwd_pe: 20.4, pe_hist_median: 34.4, multiple_discount_pct: 40.7,
      divergence_available: true, growth_now_pct: 15.1, growth_hist_pct: 18.8,
      growth_decel_pct: 19.7, divergence_pp: 21.0, fear_discount_setup: true },
    revision_vs_price: { erb_90d: 0.045, rel_strength_6m: -0.22, divergence: true },
    reinvestment_quality: { delta_operating_income_2y: 40e9, capex_deployed_2y: 109.1e9,
      capex_intensity_pct: 23.0, incremental_roic_pct: 36.7 },
  },
  street_view: {
    consensus_target_mean: 560.0, consensus_target_high: 650.0, consensus_target_low: 440.0,
    upside_to_target_pct: 41.5, analyst_count: 54, recommendation_mean: 1.5,
    recommendation_key: 'buy', pwfv_vs_street_pct: -39.0,
    // v4.2.10: count basis + rating split. The mock must carry them or the new render rows
    // never execute and the suite reports green without testing them (the MOCK_RESULT disease).
    analyst_count_basis: 'finnhub rec_trends (sum of latest-month rating buckets)',
    recommendation_breakdown: { period: '2026-07-01', strongBuy: 16, buy: 29, hold: 13,
                                sell: 0, strongSell: 0, total: 58 },
    analyst_actions_recent: [{ date: '2026-07-15', firm: 'BofA Securities', action: 'reit',
                               to_grade: 'Buy', from_grade: 'Buy' }],
  },
};

const MOCK_PAYLOAD = {
  ticker: 'TEST', chat_id: '123',
  op_margin_series: [0.27, 0.44, 0.49, 0.40, 0.41],
  rev_cagr_3y: 0.14, rev_cagr_5y: 0.07, eps_cagr_3y: 0.17, eps_cagr_5y: 0.21,
  roe: 1.93, fcf_conversion: 0.95, debt_to_equity: 2.45, sbc_to_revenue: 0.018,
  dilution_cagr: -0.02, levered_fcf_per_share: 13, levered_fcf: 2e9,
  buyback_latest: 3e9, buyback_to_fcf: 0.68, buyback_vs_sbc: 19.6,
  dividend_paid_latest: 1e9, dividend_growth_cagr: 0.11,
  rel_strength_6m: -0.16, rel_strength_12m: -0.23, erb_90d: 0.028,
  cash: 3e9, st_investments: 2.8e9, fwd_pe: 28, peg: 1.48, pe_hist_median: 32,
  peer_multiples: [{ ticker: 'AAA', fwd_pe: 25, eps_growth_pct: 12 }],
  peer_median_pe: 27, short_pct_float: 0.01, fwd_pe_vs_peer: 1.04,
  growth_diag: {}, rpo: 5e9, split_events: [],
  // v4.2.11: the LIVE payload shape — gross_profit/total_revenue are SERIES (arrays of
  // {end,val}); the latest scalar lives in series_latest. The v4.2.10 mock used scalars, went
  // green, and the first live run printed '$—B'. A mock that flatters the code is the
  // MOCK_RESULT disease; this one now mirrors Gather Data's actual return.
  latest_fy: '2025-12-31',
  series_latest: { gross_profit: 20.1e9, revenue: 45.2e9 },
  gross_profit: [ { end: '2024-12-31', val: 17.9e9 }, { end: '2025-12-31', val: 20.1e9 } ],
  total_revenue: [ { end: '2024-12-31', val: 39.0e9 }, { end: '2025-12-31', val: 45.2e9 } ],
  total_debt: 11.8e9, total_debt_source: 'LongTermDebtNoncurrent + 0',
  total_debt_divergence: true, alt_total_debt: 13.5e9, alt_total_debt_source: 'gather (yfinance)',
  implied_interest_rate: 0.043,
  fwd_pe_basis: 'price / (AV eps_ttm x (1 + yahoo +1y growth))',
  rec_trends: { months: [{ period: '2026-07-01', strongBuy: 16, buy: 29, hold: 13,
                           sell: 0, strongSell: 0 }],
                buy_share_latest: 0.776, buy_share_delta_3m: 0.013,
                _source: 'finnhub /stock/recommendation' },
  _edgar: { flags: { total_debt_partial: 'only one component present — may understate' },
            divergence: { gross_profit: { edgar: 20.1e9, gather: 21.3e9, pct: 5.6 } } },
  // v4.0: FINRA short interest lands in the Eligibility payload, which Render Tables reads
  // as `el` — the variable my patch got wrong (`gt`), crashing the node in production.
  short_interest: { settlement_date: '2026-07-15', short_shares: 10500000,
    short_pct_shares_outstanding: 2.64, days_to_cover: 3.0, change_pct_biweekly: 16.67,
    _pct_basis: 'FINRA short shares / EDGAR shares outstanding — SHARES OUTSTANDING, not float' },
  insider_form4: {
    discretionary_summary: { buy_shares: 0, sell_shares: 43003, net_shares: -43003,
      buy_value_usd: 0, sell_value_usd: 4100803.77, net_value_usd: -4100803.77,
      unique_insiders: 6, any_10b5_1_plan: true },
    non_discretionary_summary: { count: 92, codes_seen: ['A', 'F', 'M'] },
    discretionary_transactions: [],
  },
};

// ---------- mock n8n runtime ----------
function makeRuntime(resultJson) {
  const $ = (name) => ({
    first: () => ({
      json: name === 'Run Code' ? resultJson
          : name === 'Render Tables' ? { result_json: resultJson }
          : MOCK_PAYLOAD,
    }),
  });
  return { $, $input: { first: () => ({ json: MOCK_PAYLOAD }) } };
}

async function runNode(nodeName, resultJson) {
  const code = nodeByName[nodeName].parameters.jsCode;
  const { $, $input } = makeRuntime(resultJson === undefined ? MOCK_RESULT : resultJson);
  const fn = new Function('$', '$input', `return (async () => { ${code} })();`);
  return await fn($, $input);
}

// ---------- tests ----------
(async () => {
  console.log('validating: ' + wfFile + '\n');
  console.log('Render Tables');

  const out = await runNode('Render Tables');
  const md = out[0].json.tables_md;

  await check('executes without throwing and reports render_ok', () => {
    assert(out[0].json.render_ok === true, 'render_ok was ' + out[0].json.render_ok);
  });

  // v4.2.63: the two-lens header must reach the REPORT, not merely RESULT. Both NFLX runs of
  // 2026-08-02 carried central_lens and reverse_dcf in RESULT and printed neither, because the
  // push landed in the FALLBACK branch's H — the first `const H = []` in the file. Every pin at
  // the time asserted on RESULT fields, so the whole suite agreed the feature worked.
  await check('v4.2.63: the CENTRAL LENS line reaches the rendered report', () => {
    assert(/CENTRAL LENS/.test(md), 'the central lens never reached the markdown');
    assert(/ADVISORY: no verdict, alert or entry rung reads this/.test(md),
      'the advisory disclaimer must travel with the number, not live only in RESULT');
  });

  await check('v4.2.63: the REVERSE DCF line reaches the rendered report', () => {
    assert(/REVERSE DCF/.test(md), 'the reverse DCF never reached the markdown');
    assert(/Actual: 3y/.test(md),
      'the required growth must be printed BESIDE the realised growth or it is unfalsifiable');
  });

  await check('produces substantial markdown', () => {
    assert(md && md.length > 1500, 'tables_md too short: ' + (md ? md.length : 0));
  });

  await check('renders every report section', () => {
    for (const section of ['Verdict', 'Scorecard', 'IVC — scenarios', 'MoS ladder',
                           'BULL / BEAR', 'Gates', 'Self-tests', 'EVIDENCE PACK',
                           'Fundamentals snapshot']) {
      assert(md.includes(section), 'missing section: ' + section);
    }
  });

  // ---------- v4.2.10 Fundamentals snapshot ----------
  await check('fundamentals: gross profit rendered with margin from the SERIES shape', () => {
    assert(md.includes('Gross profit (latest FY2025)'), 'gross profit row missing or FY label lost');
    assert(md.includes('gross margin 44.47%'), 'margin not computed from series_latest (20.1/45.2)');
  });

  await check('fundamentals: gross-profit divergence warned in words, not JSON', () => {
    assert(md.includes('Gross profit divergence'), 'divergence warning missing');
    assert(md.includes('sources disagree'), 'divergence explanation missing');
  });
  await check('fundamentals: total debt with source, partial flag and implied rate', () => {
    assert(md.includes('Total debt | $11.80B'), 'total debt row missing');
    assert(md.includes('only one component present'), 'partial-coverage flag not surfaced');
    assert(md.includes('Implied interest rate | 4.30%'), 'implied rate row missing');
    assert(md.includes('Debt divergence'), 'alt-debt divergence row missing');
  });
  await check('fundamentals: forward P/E carries its basis', () => {
    assert(md.includes('Forward P/E | 28'), 'fwd P/E row missing');
    assert(md.includes('AV eps_ttm'), 'fwd P/E basis not carried with the number');
  });
  await check('fundamentals: analyst coverage derived from rec_trends with rating split', () => {
    assert(md.includes('58 analysts'), 'analyst total not derived from rec_trends');
    assert(md.includes('16 strong buy, 29 buy, 13 hold'), 'rating breakdown missing');
  });
  await check('fundamentals: consensus-anonymity note present (no fake firm promises)', () => {
    assert(md.includes('anonymized aggregates'), 'anonymity note missing');
    assert(md.includes('STREET section'), 'pointer to named actions missing');
  });
  await check('street view: analyst count basis + rating split rendered', () => {
    assert(md.includes('count basis: finnhub rec_trends'), 'analyst_count_basis not rendered');
    assert(md.includes('Rating split | 16 strong buy / 29 buy / 13 hold / 0 sell'),
           'recommendation_breakdown row missing');
  });
  // ---------- series-shape fallback: series_latest absent, arrays only ----------
  // live regression pinned: v4.2.10 read the top-level field, got the ARRAY, printed '$—B'
  const _savedSL = MOCK_PAYLOAD.series_latest;
  delete MOCK_PAYLOAD.series_latest;
  const outSeriesOnly = await runNode('Render Tables');
  MOCK_PAYLOAD.series_latest = _savedSL;
  await check('fundamentals: array-only payload still yields the latest value, never $—B', () => {
    const md3 = outSeriesOnly[0].json.tables_md;
    assert(md3.includes('Gross profit (latest FY2025) | $20.10B'),
           'array-tail fallback failed: ' + (md3.match(/\| Gross profit[^\n]*/) || ['row missing'])[0]);
    assert(!md3.includes('$—B'), 'the v4.2.10 live bug is back: rendered a dash-B');
  });

  // ---------- dropped-zero gross profit: the Lite 2026-07-18 live artifact ----------
  const _savedSL2 = MOCK_PAYLOAD.series_latest;
  MOCK_PAYLOAD.series_latest = { gross_profit: 0, revenue: 45.2e9 };
  const outZeroGp = await runNode('Render Tables');
  MOCK_PAYLOAD.series_latest = _savedSL2;
  await check('zero gross profit against real revenue renders UNVERIFIED, never $0.00B', () => {
    const mdz = outZeroGp[0].json.tables_md;
    assert(!mdz.includes('$0.00B'), 'the dropped-zero artifact is printed as fact again');
    assert(!mdz.includes('gross margin 0.00%'), 'a 0.00% margin printed as fact');
    assert(mdz.includes('dropped-zero artifact'), 'the artifact must be NAMED, not dashed');
  });

  // ---------- v4.2.22 (#10): STALE (not exactly zero) gross profit — the NFLX 2026-07-19 case ----
  // NFLX's GrossProfit tag is barely reported; series_latest.gross_profit came back as a value that
  // rounds to $0.00B while NOT being ===0, so the v4.2.15 guard missed it and $0.00B printed as fact
  // against $45B revenue. The widened guard (<=0 OR margin <0.5%) must now catch that rounding band,
  // WITHOUT suppressing a genuine thin margin above it.
  const _savedSL3 = MOCK_PAYLOAD.series_latest;
  MOCK_PAYLOAD.series_latest = { gross_profit: 1.16e9, revenue: 45.2e9 };  // 2.57% — real, above band
  const outStaleGp = await runNode('Render Tables');
  MOCK_PAYLOAD.series_latest = _savedSL3;
  await check('a 2.57% margin is above the 0.5% artifact band and must PRINT, not be suppressed', () => {
    const md = outStaleGp[0].json.tables_md;
    assert(/Gross profit[^\n]*\$1\.16B/.test(md),
      'a real (if thin) margin was wrongly suppressed: '
      + (md.match(/\| Gross profit[^\n]*/) || ['row missing'])[0]);
  });

  const _savedSL4 = MOCK_PAYLOAD.series_latest;
  MOCK_PAYLOAD.series_latest = { gross_profit: 0.1e9, revenue: 45.2e9 };  // 0.22% — rounds to $0.00B band
  const outTinyGp = await runNode('Render Tables');
  MOCK_PAYLOAD.series_latest = _savedSL4;
  await check('gross profit inside the $0.00B rounding band (<0.5%) renders UNVERIFIED, never a fake fact', () => {
    const md = outTinyGp[0].json.tables_md;
    assert(md.includes('[UNVERIFIED]') && md.includes('artifact'),
      'the near-zero gp artifact must be marked UNVERIFIED and named: '
      + (md.match(/\| Gross profit[^\n]*/) || ['row missing'])[0]);
  });

  // ---------- null-fwd_pe branch: second execution with fwd_pe removed ----------
  // check() is SYNCHRONOUS — an async callback hands it an unawaited promise and every failure
  // inside would report green. Run the node here in the outer async scope; assert sync.
  const _savedFwd = MOCK_PAYLOAD.fwd_pe, _savedBasis = MOCK_PAYLOAD.fwd_pe_basis,
        _savedDiag = MOCK_PAYLOAD.growth_diag;
  MOCK_PAYLOAD.fwd_pe = null; MOCK_PAYLOAD.fwd_pe_basis = null;
  MOCK_PAYLOAD.growth_diag = { market_facts_errors: { alpha_vantage:
    "rate-limited or empty: We have detected your API key as A263Z7Y0ZBAIK3OC and our limit" } };
  const outNullFwd = await runNode('Render Tables');
  MOCK_PAYLOAD.fwd_pe = _savedFwd; MOCK_PAYLOAD.fwd_pe_basis = _savedBasis;
  MOCK_PAYLOAD.growth_diag = _savedDiag;
  await check('fundamentals: null fwd_pe states the REASON, never a silent dash', () => {
    const md2 = outNullFwd[0].json.tables_md;
    assert(md2.includes('Forward P/E | [UNVERIFIED]'), 'null fwd_pe not marked UNVERIFIED');
    assert(md2.includes('Alpha Vantage: rate-limited or empty'),
           'the recorded reason for absence was not surfaced');
  });
  await check('SECURITY: the reason row redacts key-shaped tokens (live leak 2026-07-17)', () => {
    // the shipped NFLX report carried the operator's real AV key inside this exact row
    const md2 = outNullFwd[0].json.tables_md;
    assert(!md2.includes('A263Z7Y0ZBAIK3OC'), 'API key leaked into the report AGAIN');
    assert(md2.includes('[REDACTED]'), 'redaction marker absent from the reason row');
  });

  await check('LEG-MIXING FIX (v4.2.19): the Verdict line prints the verdict_cap leg, not GAAP always', async () => {
    // The 2026-07-18 control runs: the Verdict row printed GAAP MoS (-9.77%) next to an
    // FCF-driven verdict (-27.95%). The memo-LLM read the contradiction and filed a claim the
    // arbiter stamped MAJOR -- BOTH runs -- so the renderer itself manufactured contested claims
    // and inflated DI. The row's implied_cagr and MoS MUST be the same leg that drives verdict_cap.
    const legRes = JSON.parse(JSON.stringify(MOCK_RESULT));
    legRes.ivc_base.inputs.price = 1274.17;
    legRes.ivc_base.implied_cagr_pct = 8.34;   // GAAP leg (must NOT appear in the verdict row)
    legRes.ivc_base.mos_pct = -9.77;            // GAAP MoS  (must NOT appear in the verdict row)
    legRes.verdict_cap = 'AVOID';
    legRes.dual_basis = {
      gaap_eps: { iv: 1149.68, implied_cagr_pct: 8.34, base_per_share: 16.70 },
      fcf_per_share: { iv: 918.05, implied_cagr_pct: 1.23, base_per_share: 24.78,
                       future_multiple: 18.0, gross_dilution_used: -0.0036 },
      gap_iv_pct: -20.1, conservative_leg: 'fcf_per_share', verdict_leg: 'fcf_per_share',
    };
    const mdLeg = (await runNode('Render Tables', legRes))[0].json.tables_md;
    // header names the leg explicitly -- no more ambiguous 'MoS base'
    assert(mdLeg.includes('implied_cagr (FCF/sh)'), 'verdict header does not name the FCF leg');
    assert(mdLeg.includes('MoS (FCF/sh)'), 'MoS column not labelled with the verdict leg');
    // the verdict ROW carries the FCF numbers, and NOT the GAAP ones
    const vrow = mdLeg.match(/^\| TEST \|[^\n]*\|/m);
    assert(vrow, 'verdict row not found');
    assert(vrow[0].includes('1.23%'), 'verdict row lost the FCF implied_cagr: ' + vrow[0]);
    assert(vrow[0].includes('-27.95%'), 'verdict row lost the FCF MoS: ' + vrow[0]);
    assert(!vrow[0].includes('8.34%'), 'GAAP implied_cagr leaked into the FCF-verdict row');
    assert(!vrow[0].includes('-9.77%'), 'GAAP MoS leaked into the FCF-verdict row (leg-mixing)');
  });

  await check('LEG-MIXING FIX: with no dual_basis, the verdict row falls back to ivc_base honestly', async () => {
    const noDb = JSON.parse(JSON.stringify(MOCK_RESULT));
    delete noDb.dual_basis;
    noDb.ivc_base.implied_cagr_pct = 7.75; noDb.ivc_base.mos_pct = -12.3;
    const mdNo = (await runNode('Render Tables', noDb))[0].json.tables_md;
    assert(mdNo.includes('implied_cagr (GAAP)'), 'single-leg name should read GAAP');
    const vrow = mdNo.match(/^\| TEST \|[^\n]*\|/m);
    assert(vrow && vrow[0].includes('7.75%') && vrow[0].includes('-12.3'),
      'no-dual-basis fallback must still print ivc_base figures');
  });

  await check('GPS total printed equals the sum of the visible blocks', () => {
    // v2.3/v2.4 regression: the whole GPS_TOTAL_MISMATCH -> REWORK loop.
    const m = md.match(/\*\*TOTAL GPS\*\*\s*\|\s*\*\*([\d.]+)\*\*/);
    assert(m, 'TOTAL GPS row not found');
    const printed = parseFloat(m[1]);
    const expected = MOCK_RESULT.gps.blocks.reduce((s, b) => s + b.points, 0);
    assert(printed === expected, 'printed ' + printed + ' != sum ' + expected);
  });

  await check('EVERY GPS denominator in the report agrees — no renderer keeps a private /100', () => {
    // v4.2.5 regression, found in the live 2026-07-17 v4.2.4 run: the Verdict row printed
    // "59/100" while the Scorecard row thirty rows down printed "59/95". v4.2.4 fixed gps.max in
    // analyze() and the Scorecard renderer, and missed the Verdict renderer — the fix went where
    // the bug was reported, not everywhere the constant lived. This test refuses to name a site:
    // it scrapes EVERY "<total>/<max>" GPS rendering and demands they agree with RESULT.gps.max.
    const expected = MOCK_RESULT.gps.max;
    assert(typeof expected === 'number', 'MOCK_RESULT.gps.max must be set for this test to mean anything');
    const verdict = md.match(/^\| TEST \| ([\d.]+)\/(\d+|\?) \|/m);
    assert(verdict, 'verdict row GPS cell not found');
    assert(verdict[2] === String(expected),
      'verdict row says /' + verdict[2] + ' but RESULT.gps.max=' + expected);
    const total = md.match(/\*\*TOTAL GPS\*\*\s*\|\s*\*\*([\d.]+)\*\*\s*\|\s*\*\*(\d+)\*\*/);
    assert(total, 'TOTAL GPS row not found');
    assert(total[2] === String(expected),
      'scorecard says /' + total[2] + ' but RESULT.gps.max=' + expected);
    assert(verdict[2] === total[2],
      'the SAME report printed two different GPS denominators: /' + verdict[2] + ' and /' + total[2]);
  });

  await check('EVIDENCE PACK short interest carries its BASIS, and never mislabels one as the other', () => {
    // v4.2.4 regression, found in the live NFLX 2026-07-17 report: the FINRA block printed
    // "2.47% of shares outstanding (NOT float)" and the EVIDENCE PACK, ~100 lines below in the
    // same document, printed "2.5% of float". Two bases, one report -- and EVIDENCE PACK is the
    // section the memo/auditor/arbiter are told to cite VERBATIM, so the wrong label propagates.
    const line = md.split('\n').find(l => l.startsWith('- Short interest:'));
    assert(line, 'EVIDENCE PACK short-interest line missing');
    assert(/of shares OUTSTANDING/.test(line),
      'the FINRA primary figure and its basis are absent: ' + line);
    assert(!/^- Short interest: [^|]*of float/.test(line),
      'the outstanding-basis number is still labelled "of float": ' + line);
  });

  await check('EVIDENCE PACK short interest carries EVERYTHING the Stage 4 gate demands', () => {
    // v4.2.7 regression — NFLX 2026-07-17 was BLOCKED at the IC gate with MAJOR
    // short_interest_unsourced, a full LLM spend burned. Cause: the gate requires shares+date and
    // Stage 2b is told to cite days-to-cover, but the exact count existed ONLY in the raw
    // GROUND_TRUTH JSON — section 1 rounds it to '104.12M' and the EVIDENCE PACK (the section the
    // memo is told to cite VERBATIM) had neither the count nor days-to-cover. This test asserts
    // the citation source can actually satisfy its reader.
    const line = md.split('\n').find(l => l.startsWith('- Short interest:'));
    assert(/10,500,000 shares/.test(line), 'exact share count absent — the gate demands it: ' + line);
    assert(/2026-07-15/.test(line), 'settlement date absent: ' + line);
    assert(/days-to-cover 3\.00/.test(line), 'days-to-cover absent — Stage 2b is told to cite it: ' + line);
    assert(!/10500000 shares/.test(line), 'share count must be human-grouped to be citable verbatim');
  });

  await check('EVIDENCE PACK short interest gets the UNITS right for BOTH fields', () => {
    // The landmine: short_pct_float is a FRACTION (0.01), short_pct_shares_outstanding is already
    // PERCENT (2.64). Mixing them renders 264% or 0.0001%. Both must print as human percents.
    const line = md.split('\n').find(l => l.startsWith('- Short interest:'));
    assert(line.includes('2.64% of shares OUTSTANDING'),
      'outstanding figure wrong (expected 2.64%, unscaled): ' + line);
    assert(line.includes('1.00% of FLOAT'),
      'float figure wrong (expected 0.01 -> 1.00%): ' + line);
    assert(!/26400|264\.00|0\.03% of shares/.test(line), 'a unit conversion went wrong: ' + line);
  });

  await check('EVIDENCE PACK names the FINRA settlement date alongside the figure', () => {
    // A short-interest number without its settlement date is undated -- the v4.2.2 staleness
    // lesson. The primary section carries it; the EVIDENCE PACK must too, since it is what
    // gets cited.
    const line = md.split('\n').find(l => l.startsWith('- Short interest:'));
    assert(line.includes('2026-07-15'), 'settlement date missing from the cited line: ' + line);
  });

  await check('dual basis section renders both legs', () => {
    assert(md.includes('Valuation basis'), 'dual basis section missing');
    assert(md.includes('16.22') && md.includes('17.03'), 'both legs must print their implied CAGR');
    assert(md.includes('gaap_eps'), 'conservative leg not named');
  });

  await check('market context renders the fear-discount banner', () => {
    assert(md.includes('Market context'), 'market context section missing');
    assert(md.includes('FEAR-DISCOUNT SETUP'), 'flag set in RESULT but no banner rendered');
    assert(md.includes('36.7'), 'incremental ROIC not printed');
  });

  await check('street view renders consensus and the model-vs-street gap', () => {
    assert(md.includes('Street view'), 'street view section missing');
    assert(md.includes('560'), 'consensus target not printed');
    assert(md.includes('BofA Securities'), 'named analyst action not printed');
  });

  await check('FINRA short interest renders with its basis label', () => {
    // Regression: this block referenced an undefined `gt` and threw ReferenceError on a live
    // run. It never executed here because MOCK_RESULT had no market_context to enter.
    assert(md.includes('Short interest'), 'short interest not rendered');
    assert(md.includes('2026-07-15'), 'settlement date missing');
    assert(md.includes('outstanding'), 'basis label (shares outstanding, not float) missing');
  });

  await check('no duplicate scorecard rows (no gps_quant double-count)', () => {
    // v2.4 regression: the wiring emitted gps_quant twice ('блок A' AND 'quant_A_quant') and
    // visibleSum counted both, inflating GPS. Scope this to the Scorecard section only —
    // other tables legitimately repeat identifiers (BR1/BL1 appear in both Bull/Bear and the
    // radar skeleton), so a document-wide scan would false-positive.
    const start = md.indexOf('Scorecard');
    const end = md.indexOf('###', start + 1);
    const section = md.slice(start, end === -1 ? undefined : end);
    const names = section.split('\n')
      .filter(l => l.trim().startsWith('|'))
      .map(l => l.split('|')[1].trim())
      .filter(n => n && !/^-+$/.test(n) && !/^\*\*?(Block|TOTAL)/i.test(n))
      .map(n => n.toLowerCase().replace(/^block\s+/, '').replace(/^quant[_ ]/, '').replace(/_quant$/, ''));
    assert(names.length >= 10, 'scorecard rows not found (parsed ' + names.length + ')');
    assert(new Set(names).size === names.length, 'duplicate scorecard rows: ' + names);
  });

  await check('report text contains no Cyrillic', () => {
    const hits = md.match(/[А-Яа-я]+/g);
    assert(!hits, 'Russian leaked into the report: ' + (hits || []).slice(0, 5));
  });

  // v4.2.24 (radar #12b): the RADAR skeleton threshold generator (suggestThreshold).
  // The NFLX 2026-07-19 BL1 driver "Ad-tier and password-sharing crackdown monetization" matched
  // no pattern and fell to the default '<0 (deterioration vs base)' — a non-falsifiable tripwire
  // the auditor correctly stamped MAJOR. Two fixes: (a) ad-tier/monetization now maps to a real
  // filed metric+operator; (b) the default no longer fakes a threshold — it declares an honest gap.
  const _radarThr = async (label, side) => {
    const r = JSON.parse(JSON.stringify(MOCK_RESULT));
    r.bull_bear = { rows: [{ side: side, label: label, probability: 0.4, delta_iv: 10,
      delta_iv_pct: 3, delta_implied_cagr_pp: 0.5, expected_impact: 5 }],
      sum_expected_impact: 5, bull_total: 5, bear_total: 0, net_skew: 5 };
    const o = (await runNode('Render Tables', r))[0].json;
    // v4.2.55: select the row from INSIDE the radar table, anchored on its header. The old form
    // took the FIRST `| BL1` line in the whole document — and the bull/bear scenario table emits
    // `| BL1 |` rows too, ABOVE the radar. So this helper had been reading the scenario row and
    // asserting radar properties against it. Both pins were inert (sync check() + async callback),
    // so nothing reported the mismatch. THE RUNTIME WAS CORRECT THROUGHOUT: the radar row carries
    // `Streaming revenue YoY (ad-tier/monetization proxy) | <12%` exactly as v4.2.24 intended.
    // Anchor on the header text, never on "first match" or an index — same rule as node source.
    const HDR = '| ID | Argument (driver) | Metric | Threshold | Where to look | Action [you] |';
    const at = o.tables_md.indexOf(HDR);
    assert(at >= 0, 'radar table header not found — the anchor drifted, fix the anchor not the pin');
    const radar = o.tables_md.slice(at);
    return (radar.match(/\| (BL1|BR1)[^\n]*/) || ['no radar row'])[0];
  };

  await check('ad-tier/monetization driver gets a REAL filed metric+operator, not "<0 vs base"', async () => {
    const rowmd = await _radarThr('Ad-tier and password-sharing crackdown monetization', 'BULL');
    assert(!/deterioration vs base/.test(rowmd),
      'the non-falsifiable default is back for an ad-tier driver: ' + rowmd);
    assert(/Streaming revenue YoY/.test(rowmd) && /<12%/.test(rowmd),
      'ad-tier driver did not map to the falsifiable streaming-revenue metric: ' + rowmd);
  });

  await check('an unmatched driver declares an HONEST no-KPI gap, never a fake soft threshold', async () => {
    const rowmd = await _radarThr('some entirely novel qualitative thesis point', 'BULL');
    assert(!/deterioration vs base/.test(rowmd),
      'the fake soft threshold is back: ' + rowmd);
    assert(/needs sourced KPI/.test(rowmd) && /no filed numeric KPI/.test(rowmd),
      'unmatched driver must declare an explicit no-KPI gap, not invent an operator: ' + rowmd);
    // the operator-guarantee must NOT have faked a leading "<" onto the honest gap
    assert(!/\| no filed numeric KPI/.test(rowmd) || !/< *no filed/.test(rowmd),
      'the operator-guarantee faked an operator onto the honest gap: ' + rowmd);
  });

  await check('renders the deterministic verdict_cap', () => {
    assert(md.includes('AVOID'), 'verdict_cap not rendered');
  });

  console.log('\nRender Tables — RUNNER_ERROR path');

  const errOut = await runNode('Render Tables', { error: 'RUNNER_ERROR: harness exception: test' });
  await check('degrades honestly instead of inventing tables', () => {
    const emd = errOut[0].json.tables_md || '';
    assert(errOut[0].json.render_ok === false, 'render_ok should be false on error');
    assert(emd.includes('RUNNER_ERROR'), 'error not surfaced to the reader');
  });

  console.log('\nBuild Radar');

  const radarOut = await runNode('Build Radar');
  await check('executes without throwing', () => {
    assert(radarOut && radarOut[0] && radarOut[0].json, 'no output');
  });

  await check('no Cyrillic (v3.0 regression — this node was missed in the v2.8 translation)', () => {
    const blob = JSON.stringify(radarOut[0].json);
    const hits = blob.match(/[А-Яа-я]+/g);
    assert(!hits, 'Russian leaked from Build Radar: ' + (hits || []).slice(0, 5));
  });

  // v4.2.20 RADAR-OMISSION FIX. MOCK_PAYLOAD carries no memo_text, so $('Extract Memo') yields
  // no <<RADAR_ACTIONS>> block — this IS the "LLM dropped the action" case that stamped MAJOR
  // twice on 2026-07-18. With a skeleton present, every row must still be executable, and the
  // omission must still be recorded (delivery repair, not gate softener).
  const _radarWithSkel = async () => {
    const r = JSON.parse(JSON.stringify(MOCK_RESULT));
    r.radar_skeleton = [
      { id: 'BR1', driver: 'ad-market cyclicality (EI $-30)', metric: 'Revenue YoY',
        thr: '<15%', where: '10-Q, segment revenue' },
      { id: 'BL1', driver: 'margin expansion (EI $20)', metric: 'Operating margin',
        thr: '>42%', where: 'Income Statement (10-Q)' },
    ];
    return (await runNode('Build Radar', r))[0].json;
  };

  await check('omitted memo action -> row is still executable, synthesised from the skeleton', async () => {
    const out = await _radarWithSkel();
    const md = out.radar_md;
    assert(!md.includes('[action not provided]'),
      'the empty-cell placeholder that the auditor stamped MAJOR is back');
    // the auto action must be built from the SAME deterministic fields (metric+threshold+where)
    assert(md.includes('If Revenue YoY <15% (check 10-Q, segment revenue), revisit the thesis'),
      'BR1 auto-action not synthesised from skeleton fields: ' + md);
    assert(md.includes('_[auto'), 'the auto action must be LABELLED as auto-derived, not passed off as the memo\'s');
  });

  await check('the omission is still RECORDED — a delivery repair, not a hidden gate softener', async () => {
    const out = await _radarWithSkel();
    assert(out.radar_actions_ok === false,
      'radar_actions_ok must stay false when the memo omitted actions — the LLM miss stays visible');
    assert(Array.isArray(out.radar_missing_actions) && out.radar_missing_actions.includes('BR1')
           && out.radar_missing_actions.includes('BL1'),
      'radar_missing_actions must still name every omitted id (metrics depend on it)');
  });

  await check('a genuinely empty skeleton yields NO row — the gate is untouched', async () => {
    const r = JSON.parse(JSON.stringify(MOCK_RESULT));
    r.radar_skeleton = [];
    const out = (await runNode('Build Radar', r))[0].json;
    assert(out.radar_md.includes('[radar skeleton unavailable this run]'),
      'no skeleton must mean no fabricated rows — auto-action only fills an EXISTING row');
  });

  console.log('\n' + (failed === 0 ? 'OK' : 'FAILED') + ' — ' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed === 0 ? 0 : 1);
})().catch(e => { console.error('harness error: ' + (e.stack || e.message)); process.exit(1); });

// v4.2.35 (mandate HH/II): the rendered ladder must come from RESULT.mos_ladder (verdict leg),
// with ivc_base.mos_ladder only as a fallback. The old order rendered the GAAP rungs always, so
// the memo quoted them and the gate flagged them against RESULT (MA 2026-07-22).
{
  const rtNode = WF.nodes.find(n => n.name === 'Render Tables');
  const src = rtNode.parameters.jsCode.replace(/\s+/g, '');
  assert(src.includes('res.mos_ladder||(res.ivc_base&&res.ivc_base.mos_ladder)'),
    'ladder must prefer RESULT.mos_ladder (verdict leg) over ivc_base (GAAP leg)');
  assert(!src.includes('(res.ivc_base&&res.ivc_base.mos_ladder)||res.mos_ladder'),
    'the old GAAP-first order must be gone');
  assert(src.includes('res.mos_ladder_leg'), 'the rendered table must name the leg it used');
  console.log('render: ladder prefers the verdict leg — ok');
}
