// v4.2.74 — pins for `Merge FACT_PACK Calls`.
//
// The FACT_PACK request was split into four topical calls after the ORCL diagnosis: one search
// covering eleven unrelated topics returned snippets for two or three, and the model honestly
// tagged the rest [UNVERIFIED] ("not visible in this interface"). The contract did not change —
// four slightly different contracts would be worse than one starved search — so the merge must
// leave downstream unable to tell WHICH call a section came from. That indistinguishability is
// the property under test; without it the split has quietly become four pipelines.
const fs = require('fs'), path = require('path');
const WF_DIR = path.join(__dirname, '..', 'workflow');
const WF = fs.readdirSync(WF_DIR).filter(f => /^consilium_spine_v/.test(f)).sort().pop();
const WFJ = JSON.parse(fs.readFileSync(path.join(WF_DIR, WF), 'utf8'));
const CODE = WFJ.nodes.find(n => n.name === 'Merge FACT_PACK Calls').parameters.jsCode;

let passed = 0, failed = 0;
function assert(c, m) { if (!c) throw new Error(m || 'assertion failed'); }
function check(name, fn) {
  try { fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + e.message); }
}

const SKIP = '[NOT REQUESTED IN THIS CALL]';
function run(byCall) {
  const $ = (name) => ({ first: () => {
    if (!(name in byCall)) throw new Error('node not reached: ' + name);
    const t = byCall[name];
    if (t === null) throw new Error('call failed');
    return { json: { choices: [{ message: { content: t } }] } };
  } });
  return new Function('$', `return (() => { ${CODE} })();`)($)[0].json;
}
const call = (kept, skipped) => kept.map(h => '## ' + h + '\n\nfact\n').join('')
  + skipped.map(h => '## ' + h + '\n\n' + SKIP + '\n').join('');

const HAPPY = {
  'Stage 1 FP fin':     call(['1. Revenue'], ['4. M&A', '6. Moat']),
  'Stage 1 FP legal':   call(['4. M&A'], ['1. Revenue']),
  'Stage 1 FP compete': call(['6. Moat'], ['1. Revenue']),
  'Stage 1 FP news':    call(['5. News'], ['1. Revenue']),
};

check('the merged payload has the SHAPE of the single call it replaced', () => {
  const out = run(HAPPY);
  assert(out.choices && out.choices[0] && typeof out.choices[0].message.content === 'string',
    'downstream reads choices[0].message.content — the shape must be identical');
});

check('a section is indistinguishable by which call produced it', () => {
  const md = run(HAPPY).choices[0].message.content;
  for (const h of ['1. Revenue', '4. M&A', '6. Moat', '5. News']) {
    assert(md.indexOf('## ' + h) !== -1, 'section lost in the merge: ' + h);
  }
  assert(!/FP fin|FP legal|FP compete|FP news/.test(md),
    'the merged pack names its own plumbing — consumers must not be able to tell');
});

check('sections a call was told NOT to cover are dropped whole', () => {
  const md = run(HAPPY).choices[0].message.content;
  assert(md.indexOf(SKIP) === -1,
    'the "not requested" marker reached the pack: an unasked section would read as a missing one');
  assert((md.match(/## 1\. Revenue/g) || []).length === 1, 'a skipped section was kept as a duplicate');
});

check('a FAILED call marks its sections as a SOURCE failure, and the run lives', () => {
  // An unreachable source is an engineering event; an empty search is a fact about the world.
  // Publishing one as the other is the defect this whole session has been about.
  const out = run(Object.assign({}, HAPPY, { 'Stage 1 FP legal': null }));
  const md = out.choices[0].message.content;
  assert(/SOURCE_CALL_FAILED/.test(md), 'a dead call vanished silently');
  assert(/Stage 1 FP legal/.test(md), 'the failed theme must be named');
  assert(md.indexOf('## 1. Revenue') !== -1, 'one dead theme killed the surviving ones');
  assert(out._fp_merge.failed.length === 1, 'the failure is not counted: ' + out._fp_merge.failed);
});

check('a section answered by TWO calls is refused, never arbitrated', () => {
  // Picking a winner silently would publish an arbitrary choice as a fact.
  const out = run(Object.assign({}, HAPPY, {
    'Stage 1 FP compete': call(['6. Moat', '4. M&A'], []) }));
  const md = out.choices[0].message.content;
  assert(/MERGE_COLLISION/.test(md), 'a duplicate section was silently arbitrated');
  assert(out._fp_merge.collisions.length === 1, 'the collision is not counted');
  assert((md.match(/## 4\. M&A/g) || []).length === 1, 'both copies survived');
});

check('the merge DECIDES nothing — no scoring, no repair, no verdict', () => {
  for (const bad of ['verdict', 'intrinsic', 'score', 'iv_', 'UNVERIFIED] =']) {
    assert(CODE.indexOf(bad) === -1, 'the merge strayed beyond assembly: ' + bad);
  }
});

check('the four calls run in SERIES and end at the merge', () => {
  // v4.2.75: fan-in was the defect, not the shape of the pin. Four edges into one input of a Code
  // node do not make it wait — the first live run fired the merge on branch one and reported the
  // other three as unreachable sources when they simply had not run yet. The chain is what makes
  // "the merge sees all four" true; this pin now checks the property, not the old wiring.
  const c = WFJ.connections;
  const CHAIN = ['fin', 'legal', 'compete', 'news'];
  for (let i = 0; i < CHAIN.length; i++) {
    const tgt = [].concat.apply([], (c['Stage 1 FP ' + CHAIN[i]] || {}).main || []).map(x => x.node);
    const want = (i + 1 < CHAIN.length) ? ('Stage 1 FP ' + CHAIN[i + 1]) : 'Merge FACT_PACK Calls';
    assert(tgt.length === 1 && tgt[0] === want,
      'call ' + CHAIN[i] + ' should feed ' + want + ', feeds: ' + tgt);
  }
  const entry = [].concat.apply([], (c['Prompts Growth'] || {}).main || []).map(x => x.node);
  assert(entry.length === 1 && entry[0] === 'Stage 1 FP fin',
    'the chain must start from exactly one call, or the fan-in defect is back: ' + entry);
  const out = [].concat.apply([], (c['Merge FACT_PACK Calls'] || {}).main || []).map(x => x.node);
  assert(out.indexOf('Verify FACT_PACK Entity') !== -1,
    'the merge does not reach the entity gate — the pack would bypass verification');
});

check('each themed call keeps its own retry policy', () => {
  for (const t of ['fin', 'legal', 'compete', 'news']) {
    const n = WFJ.nodes.find(x => x.name === 'Stage 1 FP ' + t);
    assert(n.retryOnFail === true, 'retry lost on ' + t + ' — a transient flake would kill a theme');
    assert(n.maxTries >= 2, 'maxTries too low on ' + t);
  }
});

check('the news and legal themes carry a recency window; the others do not', () => {
  const body = (t) => WFJ.nodes.find(x => x.name === 'Stage 1 FP ' + t).parameters.jsonBody;
  assert(/search_recency_filter[^,]*month/.test(body('news')), 'news lost its month window');
  assert(/search_recency_filter[^,]*year/.test(body('legal')), 'legal lost its year window');
  assert(!/search_recency_filter/.test(body('fin')),
    'a recency window on the financial history would truncate the 5-year series');
});

console.log('\n' + (failed ? 'FAILED' : 'OK') + ' — ' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
