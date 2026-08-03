/**
 * Execution test for the "Parse DI" code node — v4.2.12.
 *
 * WHY THIS FILE EXISTS: DI was the last freely-LLM-written number in the report, and it
 * wobbled in production. NFLX 2026-07-17 run #2 shipped an arbiter that (a) corrected its own
 * multiplication mid-sentence ("15×0.5 = 7.5 → wait...") and (b) improvised a 0.25 weight for
 * PARTIAL claims that formula F does not contain. Run #3's arbiter used a different PARTIAL
 * convention. Same formula, two arbiters, two answers. The formula now runs in THIS node from
 * the arbiter's raw counts; the arbiter's own di is kept as a canary and any divergence is
 * printed in the shipped report.
 *
 * Run:  node tests/test_parse_di.js
 */
const fs = require('fs');
const path = require('path');

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
  }).pop();
const WF = JSON.parse(fs.readFileSync(path.join(WORKFLOW_DIR, wfFile), 'utf8'));
const CODE = WF.nodes.find(n => n.name === 'Parse DI').parameters.jsCode;

let passed = 0, failed = 0;
function check(name, fn) {
  try { fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + e.message); }
}
function assert(c, m) { if (!c) throw new Error(m || 'assertion failed'); }

// v4.2.56a: the harness now supplies a Run Code payload too. The PUBLISHED GPS must come from the
// deterministic side — comparing the arbiter's recount against a number the arbiter also wrote
// would leave both sides of a money comparison in the model's hands.
async function run(arbiterText, gpsPublished) {
  const $ = (name) => ({ first: () => ({ json:
    name === 'Extract Arbiter' ? { memo_text: arbiterText }
  : name === 'Run Code' ? (gpsPublished === undefined ? {} : { gps: { total: gpsPublished } })
                               : { chat_id: '123', ticker: 'TEST' } }) });
  const fn = new Function('$', `return (async () => { ${CODE} })();`);
  return (await fn($))[0].json;
}

function block(obj) { return 'prose before\n```json\n' + JSON.stringify(obj) + '\n```\n'; }

(async () => {
  console.log('validating Parse DI in: ' + wfFile + '\n');

  // ---- 1. happy path: counts present, arbiter's own di agrees ----
  let r = await run(block({ di: 6.0, di_class: 'CONTESTED', final_verdict: 'AVOID', flip: false,
    counts: { sustained_blocking: 1, sustained_major: 10,
              gps_recount_delta_gt15: false, icagr_sign_disagreement: false } }));
  check('counts present + agreeing canary: python value, no divergence', () => {
    assert(r.di === 6, 'di=' + r.di);
    assert(r.di_source === 'python_from_counts', r.di_source);
    assert(r.di_divergence === false, 'false divergence flagged');
    assert(r.contested === true, 'DI 6 must be contested');
  });

  // ---- 2. THE run-2 wobble: arbiter says 8.0 (improvised PARTIAL weight), counts say 7.5 ----
  r = await run(block({ di: 8.0, di_class: 'CONTESTED', final_verdict: 'AVOID', flip: false,
    counts: { sustained_blocking: 0, sustained_major: 15,
              gps_recount_delta_gt15: false, icagr_sign_disagreement: false } }));
  check('run-2 scenario: formula over counts WINS, canary divergence printed', () => {
    assert(r.di === 7.5, 'expected 7.5 from 15 x 0.5, got ' + r.di);
    assert(r.di_llm === 8.0, 'canary lost: ' + r.di_llm);
    assert(r.di_divergence === true, 'divergence not flagged');
  });

  // ---- 3. MAJOR-volume driver note: contested with zero blocking and no flip ----
  check('driver note fires ONLY for pure-MAJOR contested, and does not weaken the gate', () => {
    assert(r.di_driver_note && r.di_driver_note.indexOf('MAJOR volume') !== -1,
           'driver note missing on 15-major/0-blocking');
    assert(r.contested === true, 'the note must not unblock trades');
    assert(r.di_driver_note.indexOf('operator decision') !== -1,
           'the note must state that a formula change is not automatic');
  });

  // ---- 4. blocking-driven contested must NOT carry the volume note ----
  r = await run(block({ di: 6, di_class: 'CONTESTED', final_verdict: 'AVOID', flip: true,
    counts: { sustained_blocking: 3, sustained_major: 0,
              gps_recount_delta_gt15: false, icagr_sign_disagreement: false } }));
  check('flip+blocking contested: no MAJOR-volume note, arithmetic right (3+3=6)', () => {
    assert(r.di === 6, 'di=' + r.di);
    assert(r.di_driver_note === null, 'note fired on a blocking-driven DI');
  });

  // ---- 5. old-format fallback: no counts -> LLM value kept, marked unverified ----
  r = await run(block({ di: 4.5, di_class: 'divergence', final_verdict: 'WATCH+', flip: false,
                        required_mos_rung_pct: 20, rung_reached: false }));
  check('old machine block (no counts): graceful fallback, honestly labelled', () => {
    assert(r.di === 4.5, 'di=' + r.di);
    // v4.2.56: the fallback is no longer merely "honestly labelled", it is a NAMED contract
    // defect. Silence was the whole problem: without `counts` the only check on the arbiter's
    // own arithmetic is disabled, and the old label read like a routine state.
    assert(r.di_source === 'llm_unverified_CONTRACT_DEFECT', r.di_source);
    assert(r.contract_defect === 'CONTRACT_DEFECT_arbiter_counts_missing', r.contract_defect);
    assert(/CONTRACT DEFECT/.test(r.di_driver_note || ''), 'the defect must be stated in prose too');
    assert(r.di_divergence === false, 'divergence cannot be asserted without counts');
    assert(r.required_mos_rung_pct === 20, 'no directional signal is knowable -> base rung');
  });

  // ---- 6. malformed counts (nulls) fall back rather than inventing zeros ----
  r = await run(block({ di: 3, di_class: 'divergence', final_verdict: 'NEUTRAL', flip: false,
    counts: { sustained_blocking: null, sustained_major: 'many' } }));
  check('unusable counts: unknown is not zero — fallback to llm_unverified', () => {
    assert(r.di === 3, 'di=' + r.di);
    assert(r.di_source === 'llm_unverified_CONTRACT_DEFECT', 'invented a computation from null counts');
    assert(r.contract_defect === 'CONTRACT_DEFECT_arbiter_counts_missing', r.contract_defect);
  });

  // ---- v4.2.56: the RUNG. DI has been computed since v4.2.12 and works; the rung was still prose.
  // THE CASE OF RECORD, MA 2026-07-24: the arbiter shipped di 6.0 / CONTESTED / rung 30 while its
  // OWN counts give 3.0. v4.2.12 caught the DI and printed the divergence; nobody recomputed the
  // rung, so a money number stayed consistent with the refuted DI and inconsistent with the real one.
  r = await run(block({ di: 6.0, di_class: 'CONTESTED', final_verdict: 'AVOID', flip: false,
    required_mos_rung_pct: 30, rung_reached: false,
    counts: { sustained_blocking: 0, sustained_major: 6,
              gps_recount_delta_gt15: false, icagr_sign_disagreement: false } }));
  check('v4.2.56 MA 24.07: counts 0/6/false/false -> DI 3.0, divergence, rung 20%', () => {
    assert(r.di === 3.0, 'di=' + r.di);
    assert(r.di_class === 'divergence', 'class=' + r.di_class);
    assert(r.di_source === 'python_from_counts', r.di_source);
    assert(r.di_divergence === true, 'the 6.0-vs-3.0 canary must fire');
    assert(r.required_mos_rung_pct === 20, 'rung=' + r.required_mos_rung_pct);
    assert(r.rung_llm === 30, 'the model number must be KEPT as a canary, got ' + r.rung_llm);
    assert(r.rung_mismatch === true, 'the rung canary must fire too');
    assert(r.rung_signals.length === 0, 'no directional signal existed: ' + r.rung_signals);
  });

  // The point of (b): DI CLASS must not move the rung. Volume of MAJOR is not direction.
  r = await run(block({ di: 6, di_class: 'CONTESTED', final_verdict: 'AVOID', flip: false,
    counts: { sustained_blocking: 0, sustained_major: 12,
              gps_recount_delta_gt15: false, icagr_sign_disagreement: false } }));
  check('v4.2.56 (b): CONTESTED on MAJOR volume alone leaves the rung at base 20%', () => {
    assert(r.di === 6, 'di=' + r.di);
    assert(r.di_class === 'CONTESTED', 'class=' + r.di_class);
    assert(r.required_mos_rung_pct === 20, 'DI class must NOT gate the rung: ' + r.required_mos_rung_pct);
    assert(r.contested === true, 'the quality flag itself must survive — it is still CONTESTED');
  });

  r = await run(block({ di: 1, di_class: 'consensus', final_verdict: 'WATCH+', flip: false,
    counts: { sustained_blocking: 2, sustained_major: 0,
              gps_recount_delta_gt15: false, icagr_sign_disagreement: false } }));
  check('v4.2.56 (b): a sustained BLOCKING is directional -> rung escalates to 30%', () => {
    assert(r.required_mos_rung_pct === 30, 'rung=' + r.required_mos_rung_pct);
    assert(/sustained_blocking=2/.test(r.rung_signals.join(',')), r.rung_signals);
  });

  r = await run(block({ di: 3, di_class: 'divergence', final_verdict: 'AVOID', flip: true,
    counts: { sustained_blocking: 0, sustained_major: 0,
              gps_recount_delta_gt15: false, icagr_sign_disagreement: true } }));
  check('v4.2.56 (b): a verdict flip and a sign disagreement each escalate', () => {
    assert(r.required_mos_rung_pct === 30, 'rung=' + r.required_mos_rung_pct);
    const sig = r.rung_signals.join(',');
    assert(/verdict_flip/.test(sig) && /icagr_sign_disagreement/.test(sig), sig);
    // v4.2.56a: this pin previously asserted that a GPS gap NEVER escalates — my judgment call,
    // overruled by the operator: the gap has a direction and a downward one is substantive.
    // The rule now lives in its own three pins below; this one keeps to what its name says.
    assert(!/gps/.test(sig), 'no GPS gap was raised in this fixture: ' + sig);
  });

  // ---- v4.2.56a: the GPS recount gap is DIRECTIONAL. Below the published score = "quality is
  // worse than the memo claims" and escalates; above = a dispute in the safe direction, flag only.
  r = await run(block({ di: 2, di_class: 'consensus', final_verdict: 'WATCH+', flip: false,
    counts: { sustained_blocking: 0, sustained_major: 0, gps_recount: 50,
              gps_recount_delta_gt15: true, icagr_sign_disagreement: false } }), 68);
  check('v4.2.56a: recount 50 vs published 68 (worse) -> rung escalates to 30%', () => {
    assert(r.required_mos_rung_pct === 30, 'rung=' + r.required_mos_rung_pct);
    assert(/gps_recount_below_published\(50 vs 68\)/.test(r.rung_signals.join(',')), r.rung_signals);
  });

  r = await run(block({ di: 2, di_class: 'consensus', final_verdict: 'WATCH+', flip: false,
    counts: { sustained_blocking: 0, sustained_major: 0, gps_recount: 85,
              gps_recount_delta_gt15: true, icagr_sign_disagreement: false } }), 68);
  check('v4.2.56a: recount 85 vs published 68 (safe direction) -> flag only, base rung', () => {
    assert(r.required_mos_rung_pct === 20, 'a gap in the SAFE direction must not tighten entry: '
      + r.required_mos_rung_pct);
    assert(r.rung_signals.length === 0, 'no directional signal: ' + r.rung_signals);
    assert(r.di === 2, 'formula F still counts the gap (2 x 1): di=' + r.di);
  });

  r = await run(block({ di: 2, di_class: 'consensus', final_verdict: 'WATCH+', flip: false,
    counts: { sustained_blocking: 0, sustained_major: 0,
              gps_recount_delta_gt15: true, icagr_sign_disagreement: false } }), 68);
  check('v4.2.56a: >15 flag raised with NO recount value -> escalate AND name the omission', () => {
    assert(r.required_mos_rung_pct === 30, 'omission must not buy a softer rung');
    assert(/DIRECTION_UNKNOWN/.test(r.rung_signals.join(',')), r.rung_signals);
    assert(r.contract_defect === 'CONTRACT_DEFECT_gps_recount_value_missing', r.contract_defect);
  });

  // ---- 7. no json block at all: regex rescue still works ----
  r = await run('adjudication prose... DI = 5.5 overall, class divergence.');
  check('regex fallback for a blockless arbiter output', () => {
    assert(r.di === 5.5, 'di=' + r.di);
    assert(r.contested === false, 'contested mis-set');
  });

  console.log('\n' + (failed ? 'FAILED' : 'OK') + ' — ' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
