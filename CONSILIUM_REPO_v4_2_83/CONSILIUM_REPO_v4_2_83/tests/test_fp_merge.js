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

// v4.2.77 — three themes. The fixture speaks the Tier-B contract: there is no `1. Revenue`
// section to merge any more, because the pipeline computes that series itself.
const HAPPY = {
  'Stage 1 FP legal':   call(['4. M&A'], ['5. News', '6. Moat']),
  'Stage 1 FP compete': call(['6. Moat', '11. Tone'], ['4. M&A']),
  'Stage 1 FP news':    call(['5. News', '12. Quarter'], ['4. M&A']),
};

check('the merged payload has the SHAPE of the single call it replaced', () => {
  const out = run(HAPPY);
  assert(out.choices && out.choices[0] && typeof out.choices[0].message.content === 'string',
    'downstream reads choices[0].message.content — the shape must be identical');
});

check('a section is indistinguishable by which call produced it', () => {
  const md = run(HAPPY).choices[0].message.content;
  for (const h of ['4. M&A', '6. Moat', '11. Tone', '5. News', '12. Quarter']) {
    assert(md.indexOf('## ' + h) !== -1, 'section lost in the merge: ' + h);
  }
  assert(!/FP legal|FP compete|FP news/.test(md),
    'the merged pack names its own plumbing — consumers must not be able to tell');
});

check('sections a call was told NOT to cover are dropped whole', () => {
  const md = run(HAPPY).choices[0].message.content;
  assert(md.indexOf(SKIP) === -1,
    'the "not requested" marker reached the pack: an unasked section would read as a missing one');
  assert((md.match(/## 4\. M&A/g) || []).length === 1, 'a skipped section was kept as a duplicate');
});

check('a FAILED call marks its sections as a SOURCE failure, and the run lives', () => {
  // An unreachable source is an engineering event; an empty search is a fact about the world.
  // Publishing one as the other is the defect this whole session has been about.
  const out = run(Object.assign({}, HAPPY, { 'Stage 1 FP legal': null }));
  const md = out.choices[0].message.content;
  assert(/SOURCE_CALL_FAILED/.test(md), 'a dead call vanished silently');
  assert(/Stage 1 FP legal/.test(md), 'the failed theme must be named');
  assert(md.indexOf('## 5. News') !== -1, 'one dead theme killed the surviving ones');
  assert(out._fp_merge.failed.length === 1, 'the failure is not counted: ' + out._fp_merge.failed);
});

check('a section answered by TWO calls is refused, never arbitrated', () => {
  // Picking a winner silently would publish an arbitrary choice as a fact.
  const out = run(Object.assign({}, HAPPY, {
    'Stage 1 FP compete': call(['6. Moat', '11. Tone', '5. News'], []) }));
  const md = out.choices[0].message.content;
  assert(/MERGE_COLLISION/.test(md), 'a duplicate section was silently arbitrated');
  assert(out._fp_merge.collisions.length === 1, 'the collision is not counted');
  assert((md.match(/## 5\. News/g) || []).length === 1, 'both copies survived');
});

check('the merge DECIDES nothing — no scoring, no repair, no verdict', () => {
  for (const bad of ['verdict', 'intrinsic', 'score', 'iv_', 'UNVERIFIED] =']) {
    assert(CODE.indexOf(bad) === -1, 'the merge strayed beyond assembly: ' + bad);
  }
});

check('the three calls run in SERIES and end at the merge', () => {
  // v4.2.75: fan-in was the defect, not the shape of the pin. Four edges into one input of a Code
  // node do not make it wait — the first live run fired the merge on branch one and reported the
  // other three as unreachable sources when they simply had not run yet. The chain is what makes
  // "the merge sees all four" true; this pin now checks the property, not the old wiring.
  const c = WFJ.connections;
  const CHAIN = ['legal', 'compete', 'news'];
  for (let i = 0; i < CHAIN.length; i++) {
    const tgt = [].concat.apply([], (c['Stage 1 FP ' + CHAIN[i]] || {}).main || []).map(x => x.node);
    const want = (i + 1 < CHAIN.length) ? ('Stage 1 FP ' + CHAIN[i + 1]) : 'Merge FACT_PACK Calls';
    assert(tgt.length === 1 && tgt[0] === want,
      'call ' + CHAIN[i] + ' should feed ' + want + ', feeds: ' + tgt);
  }
  const entry = [].concat.apply([], (c['Prompts Growth'] || {}).main || []).map(x => x.node);
  assert(entry.length === 1 && entry[0] === 'Stage 1 FP legal',
    'the chain must start from exactly one call, or the fan-in defect is back: ' + entry);
  const out = [].concat.apply([], (c['Merge FACT_PACK Calls'] || {}).main || []).map(x => x.node);
  assert(out.indexOf('Verify FACT_PACK Entity') !== -1,
    'the merge does not reach the entity gate — the pack would bypass verification');
});

check('each themed call keeps its own retry policy', () => {
  for (const t of ['legal', 'compete', 'news']) {
    const n = WFJ.nodes.find(x => x.name === 'Stage 1 FP ' + t);
    assert(n.retryOnFail === true, 'retry lost on ' + t + ' — a transient flake would kill a theme');
    assert(n.maxTries >= 2, 'maxTries too low on ' + t);
  }
});

check('the news and legal themes carry a recency window; the others do not', () => {
  const body = (t) => WFJ.nodes.find(x => x.name === 'Stage 1 FP ' + t).parameters.jsonBody;
  assert(/search_recency_filter[^,]*month/.test(body('news')), 'news lost its month window');
  assert(/search_recency_filter[^,]*year/.test(body('legal')), 'legal lost its year window');
  assert(!/search_recency_filter/.test(body('compete')),
    'a window on the qualitative moat theme would hide anything older than it');
});

check('the retired `fin` call leaves NO residue anywhere', () => {
  // A stage deleted from the graph but left in the meter map reads as not_run — a free zero for
  // money that was never spent, sitting next to money that was. Same changeset or not at all.
  const whole = JSON.stringify(WFJ);
  assert(whole.indexOf('Stage 1 FP fin') === -1,
    'the retired call still appears somewhere in the workflow (node, edge, or meter row)');
  const meter = WFJ.nodes.find(n => n.name === 'Collect Usage').parameters.jsCode;
  const rows = (meter.match(/\['Stage 1 FP \w+'/g) || []);
  assert(rows.length === 3, 'the meter map must carry exactly three FP rows, has: ' + rows.length);
});

check('the contract declares the three tiers, and Tier A is not requested', () => {
  // The diagnostic (EEEEE) found 13 dead leaves of 14, and the cause was not packaging: half the
  // contract asked search for numbers this pipeline computes itself. Search cannot find OUR figures
  // in articles, and its honest refusals were then recorded as OUR incompleteness.
  const pg = WFJ.nodes.find(n => n.name === 'Prompts Growth').parameters.jsCode;
  const c = pg.slice(pg.indexOf('"stage1"'), pg.indexOf('"stage1"') + 12000);
  for (const tier of ['TIER A', 'TIER B', 'TIER C']) {
    assert(c.indexOf(tier) !== -1, 'the contract no longer declares ' + tier);
  }
  // Tier-A content must not survive as a REQUESTED numbered section.
  for (const gone of ['1. Revenue and EPS by year', '2. Analyst forecast',
                      '3. Earnings revisions over 90 days', '7. Dividend history',
                      '8. Insider activity', '9. Short interest', '10. Sector median P/E',
                      '10b. PEER MULTIPLES']) {
    assert(c.indexOf(gone) === -1, 'Tier-A item is still requested from search: ' + gone);
  }
  assert(/TERMINAL-ONLY[\s\S]{0,400}not be counted as run incompleteness/.test(c),
    'the terminal tier must state that it is NOT counted as incompleteness — otherwise a known '
    + 'property of the source landscape is booked as a failure of this run');
});

check('every Tier-B section is asked for by exactly ONE theme', () => {
  // The merge REFUSES a section answered twice. That is the last line of defence; the contract is
  // the first, and a defence that only exists downstream turns a contract defect into a lost section.
  const secs = {};
  for (const t of ['legal', 'compete', 'news']) {
    const body = WFJ.nodes.find(x => x.name === 'Stage 1 FP ' + t).parameters.jsonBody;
    const m = body.match(/Cover ONLY sections? ([^.]+?) of the contract/);
    assert(m, 'theme ' + t + ' does not name its sections');
    for (const s of m[1].split(/,| and /).map(x => x.trim()).filter(Boolean)) {
      assert(!secs[s], 'section ' + s + ' is claimed by both ' + secs[s] + ' and ' + t);
      secs[s] = t;
    }
  }
  for (const s of ['4', '5', '6', '11', '12', 'the STREET section']) {
    assert(secs[s], 'Tier-B section ' + s + ' is asked for by no theme — it would be dead by design');
  }
  // v4.2.79: STREET moved news -> legal. `news` carried 5 + 12 + STREET and silently dropped 5 on
  // the ORCL run; `legal` carried one section. This is the balancing half of that fix.
  assert(secs['the STREET section'] === 'legal', 'STREET must sit with legal, not with news');
});

check('v4.2.79: a number said by management on a date is quotable, not a forbidden series', () => {
  // On the ORCL run the model wrote "Exact RPO figures ... not detailed here per instructions" and
  // "Any numerical guidance series ... are therefore not reproduced here". Tier A was meant to stop
  // it SEARCHING for series we compute; it stopped it QUOTING what management announced.
  const pg = WFJ.nodes.find(n => n.name === 'Prompts Growth').parameters.jsCode;
  const c = pg.slice(pg.indexOf('"stage1"'), pg.indexOf('"stage1"') + 14000);
  assert(/CARVE-OUT/.test(c), 'the Tier-A carve-out is gone');
  assert(/date of utterance/.test(c),
    'the carve-out must name the TEST that separates a series from a statement, not just assert one');
  assert(/TIER B EVENT and you MUST report it/.test(c), 'the carve-out does not compel reporting');
});

check('v4.2.79: every requested section must announce itself, present or empty', () => {
  // Section 5 vanished from the ORCL pack with no heading and no marker. A silently omitted section
  // is the one failure we can neither see nor count — it is indistinguishable from an empty world.
  const pg = WFJ.nodes.find(n => n.name === 'Prompts Growth').parameters.jsCode;
  const c = pg.slice(pg.indexOf('"stage1"'), pg.indexOf('"stage1"') + 14000);
  assert(/## SECTION <n>: <title>/.test(c), 'the mandatory heading form is not specified');
  assert(/NO FINDINGS: searched, nothing surfaced/.test(c),
    'an empty requested section has no honest marker to print');
  assert(/EVEN WHEN YOU FOUND NOTHING/i.test(c),
    'the marker is not mandatory on the empty case — which is the only case that matters');
});

console.log('\n' + (failed ? 'FAILED' : 'OK') + ' — ' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
