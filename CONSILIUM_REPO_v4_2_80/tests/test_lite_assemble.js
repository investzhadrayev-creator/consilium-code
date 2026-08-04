/**
 * Execution test for Consilium Lite's "Assemble Lite" node.
 *
 * Lite has NO gate, NO auditor, NO arbiter — its entire defense is the deterministic
 * NUMBER_AUDIT banner printed before anything else. If that banner logic breaks, Lite becomes
 * an unguarded memo generator wearing the pipeline's credibility. These tests execute the real
 * node code against the three banner states (unmatched numbers / all matched / audit absent)
 * and pin the output contract that Send Report and the Postgres append consume.
 *
 * Run:  node tests/test_lite_assemble.js
 */
const fs = require('fs');
const path = require('path');

const liteFile = fs.readdirSync(path.join(__dirname, '..', 'workflow'))
  .filter(f => /^consilium_lite_v[\d_]+\.json$/.test(f)).sort().pop();
const LITE = JSON.parse(fs.readFileSync(
  path.join(__dirname, '..', 'workflow', liteFile), 'utf8'));
const CODE = LITE.nodes.find(n => n.name === 'Assemble Lite').parameters.jsCode;

let passed = 0, failed = 0;
function check(name, fn) {
  try { fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + e.message); }
}
function assert(c, m) { if (!c) throw new Error(m || 'assertion failed'); }

function makeRuntime(overrides) {
  const base = {
    'Eligibility': { ticker: 'TEST', chat_id: '123', company_title: 'Test Co',
                     _edgar: { flags: {} } },
    'Extract Memo': { memo_text: 'THESIS: dense prose citing $60.32 verbatim.' },
    'Render Tables': { tables_md: '### Verdict table here', result_json: { verdict_cap: 'AVOID' } },
    'Stage 1 Perplexity': { choices: [{ message: { content: 'compact fact pack' } }] },
    'Number Audit': { memo_numbers_total: 12, unmatched_count: 0, unmatched: [] },
    // Cost Ledger deliberately ABSENT by default — the throw is the degradation path
  };
  Object.assign(base, overrides || {});
  const $ = (name) => ({ first: () => {
    if (!(name in base)) throw new Error('node did not execute: ' + name);
    return { json: base[name] };
  }});
  return $;
}

async function run(overrides) {
  const fn = new Function('$', 'Buffer', `return (async () => { ${CODE} })();`);
  return (await fn(makeRuntime(overrides), Buffer))[0];
}
function mdOf(out) { return Buffer.from(out.binary.data.data, 'base64').toString('utf8'); }

(async () => {
  console.log('Assemble Lite');

  // ---- 1. clean audit ----
  let out = await run();
  let md = mdOf(out);
  check('assembles and reports the deterministic verdict in the header', () => {
    assert(md.includes('GROWTH LITE Report'), 'title missing');
    assert(md.includes('Verdict (deterministic verdict_cap): **AVOID**'), 'verdict line missing');
    assert(out.json.final_verdict === 'AVOID', 'json verdict: ' + out.json.final_verdict);
  });
  check('clean audit prints the all-matched line, not silence', () => {
    assert(md.includes('All 12 memo numbers matched'), 'clean-audit line missing');
  });
  check('LITE mode is declared honestly — no gate/audit/arbiter/DI', () => {
    assert(md.includes('LITE MODE: no gate, no adversarial audit, no arbiter, no DI'),
           'the missing-chain disclosure is gone');
  });
  check('glossary travels with every Lite report too', () => {
    assert(md.includes('## 9. Glossary'), 'glossary missing');
    assert(md.includes('PWFV'), 'glossary content truncated');
  });
  check('missing Cost Ledger degrades to a stated non-free run, not a crash', () => {
    assert(md.includes('Run cost'), 'cost section missing');
    assert(!/est_cost_usd[^\n]*0\.00/.test(md.split('Run cost')[1] || ''),
           'a missing ledger rendered as free');
  });
  check('output contract for Send Report / Postgres: LITE class, di null, contested false', () => {
    assert(out.json.di === null && out.json.di_class === 'LITE' && out.json.contested === false,
           JSON.stringify({di: out.json.di, cls: out.json.di_class, c: out.json.contested}));
    assert(typeof out.json.cost_summary === 'string' && out.json.cost_summary.length > 0,
           'cost_summary missing for the Telegram caption');
  });

  // ---- 2. unmatched numbers: the banner is the whole point ----
  out = await run({ 'Number Audit': { memo_numbers_total: 12, unmatched_count: 2,
    unmatched: [{ value: '47.5', context: 'implied growth of 47.5% justifies' },
                { value: '3.2B', context: 'buyback of 3.2B annually' }] } });
  md = mdOf(out);
  check('unmatched numbers: banner BEFORE the numeric layer, each number listed', () => {
    const iBanner = md.indexOf('NUMBER AUDIT (deterministic) — read BEFORE the memo');
    const iTables = md.indexOf('## 1. Numeric layer');
    assert(iBanner !== -1, 'banner missing with 2 unmatched numbers');
    assert(iBanner < iTables, 'banner rendered AFTER the tables — defeats its purpose');
    assert(md.includes('`47.5`') && md.includes('`3.2B`'), 'unmatched values not listed');
    assert(md.includes('escalate the ticker to a full consilium run'),
           'the escalation path must travel with the warning');
  });

  // ---- 3. audit node absent: unknown is not clean ----
  out = await run({ 'Number Audit': undefined });
  delete out; // value unused; rerun properly below
  const $abs = makeRuntime({}); // rebuild without Number Audit
  const runtimeAbs = (name) => name === 'Number Audit'
    ? { first: () => { throw new Error('node did not execute'); } } : $abs(name);
  const fnAbs = new Function('$', 'Buffer', `return (async () => { ${CODE} })();`);
  const outAbs = (await fnAbs(runtimeAbs, Buffer))[0];
  const mdAbs = mdOf(outAbs);
  check('audit node absent: every memo number declared unverified, never silently clean', () => {
    assert(mdAbs.includes('[audit node did not run'), 'absence not disclosed');
    assert(mdAbs.includes('treat every memo number as unverified'),
           'absence not translated into the reader instruction');
  });

  console.log('\n' + (failed ? 'FAILED' : 'OK') + ' — ' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
