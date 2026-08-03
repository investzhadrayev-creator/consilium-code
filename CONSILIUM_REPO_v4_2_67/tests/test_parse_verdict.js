/**
 * Execution test for the "Parse Verdict" code node — v4.2.13.
 *
 * WHY: the first live v4.2.12 NFLX run burned $0.85 on a parser event dressed as a gate
 * verdict. The old extractor was a greedy /\{[\s\S]*\}/ — first { to LAST } across the whole
 * text — so ANY prose containing braces around the JSON produced an unparseable span, and the
 * catch fell through to `{ verdict: "NEEDS REWORK", blocking_items: [] }`: a fail-closed
 * default indistinguishable from a real block. Fail-closed is correct for a gate and is KEPT;
 * these tests pin that the parser now (a) survives the realistic output shapes and (b) tells
 * the truth about which event happened when it cannot.
 *
 * Run:  node tests/test_parse_verdict.js
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
const CODE = WF.nodes.find(n => n.name === 'Parse Verdict').parameters.jsCode;

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
function assert(c, m) { if (!c) throw new Error(m || 'assertion failed'); }

async function run(geminiText) {
  const $ = (name) => ({ first: () => ({ json: { chat_id: '123', ticker: 'TEST' } }) });
  const $input = { first: () => ({ json:
    { candidates: [{ content: { parts: [{ text: geminiText }] } }] } }) };
  const fn = new Function('$', '$input', `return (async () => { ${CODE} })();`);
  return (await fn($, $input))[0].json;
}

const CLEAN = { verdict: 'IC-READY', blocking_items: [], notes: 'all checks passed' };
const BLOCKED = { verdict: 'NEEDS REWORK',
  blocking_items: [{ item: 'short_interest_unsourced', severity: 'BLOCKING',
                     detail: 'share count differs from GROUND_TRUTH' }] };

(async () => {
  console.log('validating Parse Verdict in: ' + wfFile + '\n');

  let r = await run(JSON.stringify(CLEAN));
  await check('bare clean JSON: IC-READY, parse_ok true', () => {
    assert(r.verdict === 'IC-READY' && r.parse_ok === true, JSON.stringify(r).slice(0, 120));
  });

  r = await run('Here is my assessment:\n```json\n' + JSON.stringify(BLOCKED) + '\n```\nDone.');
  await check('fenced JSON with prose around it: real block extracted intact', () => {
    assert(r.verdict === 'NEEDS REWORK' && r.parse_ok === true, 'lost the fenced object');
    assert(r.blocking_items[0].item === 'short_interest_unsourced', 'items lost in transit');
  });

  // THE live-failure class: braces in prose AFTER the JSON — the greedy first-{-to-last-}
  // span was unparseable and the old code silently defaulted to an empty NEEDS REWORK.
  r = await run('Assessment follows.\n' + JSON.stringify(CLEAN) +
    '\nNote: the payload shape { GROUND_TRUTH, RESULT } was consistent with the spec {v4.2}.');
  await check('LIVE CLASS: trailing prose with braces no longer poisons extraction', () => {
    assert(r.parse_ok === true, 'fell into fail-closed on the exact live-failure shape');
    assert(r.verdict === 'IC-READY', 'verdict corrupted: ' + r.verdict);
  });

  r = await run('Draft: ' + JSON.stringify({ verdict: 'NEEDS REWORK', blocking_items: [] }) +
    '\nFinal after re-check: ' + JSON.stringify(CLEAN));
  await check('two JSON objects: the LAST valid one wins (draft-then-final habit)', () => {
    assert(r.verdict === 'IC-READY', 'took the draft instead of the final');
  });

  r = await run(JSON.stringify(BLOCKED).slice(0, 60)); // truncated mid-object
  await check('truncated JSON: fail-closed, and HONEST about being a parser event', () => {
    assert(r.verdict === 'NEEDS REWORK', 'a gate must fail closed');
    assert(r.parse_ok === false, 'parser event not flagged');
    assert(r.blocking_items[0].item === 'gate_output_unparsed', 'unparsed not named');
    assert(/PARSER event/.test(r.blocking_items[0].detail), 'detail must say parser, not memo');
    assert(typeof r.raw_head === 'string' && r.raw_head.length > 0, 'raw_head missing');
  });

  r = await run('The memo looks fine to me overall, well structured.');
  await check('no JSON at all: fail-closed, never a silent empty-items verdict', () => {
    assert(r.verdict === 'NEEDS REWORK' && r.parse_ok === false, JSON.stringify(r).slice(0, 120));
    assert(r.blocking_items.length === 1 && r.blocking_items[0].item === 'gate_output_unparsed',
           'the empty-items masquerade is back');
  });

  r = await run(JSON.stringify({ status: 'ok', items: [] }));
  await check('JSON without a verdict key does not count as a gate verdict', () => {
    assert(r.parse_ok === false, 'accepted an object with no verdict key');
  });

  await check('v4.2.36: REWORK with EMPTY reasons is NAMED (not shipped silently)', async () => {
    const out = await run(JSON.stringify({ verdict: 'NEEDS REWORK', blocking_items: [] }));
    assert(out.parse_ok === true, 'not a parser event — the JSON parsed fine');
    assert(out.gate_incoherent === true, 'an empty-reason block must be marked incoherent');
    assert((out.blocking_items || []).length === 1, 'exactly one synthetic item');
    // v4.2.55: name updated to the v4.2.43 contract wording. The pin was inert (sync check() +
    // async callback), so the rename in v4.2.43 went unnoticed for 12 versions. The RUNTIME is
    // better than the pin expected — one synthetic item, gate_incoherent AND gate_contract_defect
    // both set, verdict not softened — so the test moves to the code, never the reverse.
    assert(out.blocking_items[0].item === 'CONTRACT_DEFECT_gate_rework_without_blocking_items',
      'named item, got: ' + out.blocking_items[0].item);
    assert(out.gate_contract_defect === true, 'the contract-defect marker must be set too');
    assert(String(out.verdict).toUpperCase().indexOf('REWORK') >= 0, 'fail-closed: verdict not softened');
  });

  await check('v4.2.36 negative control: a CLEAN verdict with no items is untouched', async () => {
    const out = await run(JSON.stringify(CLEAN));
    assert(!out.gate_incoherent, 'IC-READY must never be flagged incoherent');
    assert((out.blocking_items || []).length === 0, 'clean verdict must not gain synthetic items');
  });

  await check('v4.2.38: the REAL MA case — empty blocking, finding in major_items, LOUD contract defect', async () => {
    const out = await run(JSON.stringify({ verdict: 'NEEDS REWORK', blocking_items: [],
      major_items: ["catalysts_vague: 'Forward P/E compression' lacks a dated quarter"],
      minor_items: [] }));
    assert(out.gate_contract_defect === true, 'must be raised as a CONTRACT DEFECT, not normalised');
    assert(out.blocking_items[0].item.indexOf('CONTRACT_DEFECT') === 0,
      'the defect class must be loud in the item name');
    assert((out.gate_incoherent_major_items || []).length === 1, 'major_items must be captured');
    const d = out.blocking_items[0].detail;
    assert(d.indexOf('catalysts_vague') >= 0, 'the operator MUST see the real finding');
    assert(d.indexOf('MAJOR reported') >= 0, 'the detail must say the finding came from major_items');
  });

  await check('v4.2.38: MAJOR is NOT collapsed into minor_items — both lists are kept apart', async () => {
    const out = await run(JSON.stringify({ verdict: 'NEEDS REWORK', blocking_items: [],
      major_items: ['m1'], minor_items: ['n1', 'n2'] }));
    assert((out.gate_incoherent_major_items || []).length === 1, 'majors kept separately');
    assert((out.gate_incoherent_minor_items || []).length === 2, 'minors kept separately');
    const d = out.blocking_items[0].detail;
    assert(d.indexOf('MAJOR reported (1)') >= 0 && d.indexOf('MINOR reported (2)') >= 0,
      'counts must be reported per severity, not merged into one bag');
  });

  // ---- v4.2.43 (b): классификация НЕРАЗОБРАННОГО ответа гейта, с защитой от догадки ----

  await check('v4.2.51: REAL MA case — key with NO value is repaired, the IC-READY verdict survives', async () => {
    // live 2026-07-23: the gate emitted `"major_items": ,` and the whole run was discarded as a
    // PARSER event although the memo had PASSED. Syntax-only repair, never a verdict change.
    const raw = '{\n"verdict": "IC-READY",\n"blocking_items": [],\n"major_items": ,\n"minor_items": []\n}';
    const out = await run(raw);
    assert(out.parse_ok === true, 'the repaired object must parse');
    assert(String(out.verdict).toUpperCase() === 'IC-READY', 'the verdict must survive verbatim');
    assert(Array.isArray(out.major_items) && out.major_items.length === 0,
      'a missing value becomes an EMPTY list — the most restrictive reading');
    assert(out._json_repaired === 'empty_value_after_key', 'the repair must be disclosed, not silent');
    assert(!out.gate_contract_defect, 'a clean IC-READY is not a contract defect');
  });

  await check('v4.2.51 guard: repair NEVER rescues a genuinely broken payload', async () => {
    const out = await run('{"verdict": "IC-READY", "blocking_items": [oops');
    assert(out.parse_ok === false, 'a truly malformed body must still fail closed');
  });

  await check('v4.2.51 guard: repair does not alter a well-formed payload', async () => {
    const out = await run(JSON.stringify({ verdict: 'NEEDS REWORK',
      blocking_items: [{ item: 'x', severity: 'BLOCKING', detail: 'd' }] }));
    assert(out.parse_ok === true);
    assert(!out._json_repaired, 'nothing to repair -> no repair flag');
    assert(out.blocking_items.length === 1, 'content untouched');
  });

  await check('v4.2.43: real MA case — key WITH content while truncated => BLOCKING_UNPARSED', async () => {
    // gate caught a real B1 but the reply arrived unclosed: substantive block, broken transport
    const raw = '{\n"verdict": "NEEDS REWORK",\n"blocking_items": [\n"memo_number_hallucination: the memo states';
    const out = await run(raw);
    assert(out.parse_ok === false, 'unclosed JSON must not parse');
    assert(out.rework_class_raw === 'BLOCKING_UNPARSED',
      'content was PROVEN present -> must not be filed as a pure PARSER flake, got ' + out.rework_class_raw);
  });

  await check('v4.2.43 guard: key with PROVABLY EMPTY array => PARSER (no invented block)', async () => {
    const raw = '{"verdict": "NEEDS REWORK", "blocking_items": [], "minor_items": ["x"';
    const out = await run(raw);
    assert(out.parse_ok === false, 'this fixture must be unparsable');
    assert(out.rework_class_raw === 'PARSER',
      'an empty blocking_items is NOT a substantive block, got ' + out.rework_class_raw);
  });

  await check('v4.2.43 guard: key present but array UNRESOLVED => UNKNOWN, never a guess', async () => {
    // truncated right after the key: presence of the KEY is not evidence of CONTENT
    const raw = '{"verdict": "NEEDS REWORK", "blocking_items"';
    const out = await run(raw);
    assert(out.rework_class_raw === 'UNKNOWN',
      '"zero is not unknown" applies to the classifier itself, got ' + out.rework_class_raw);
  });

  await check('v4.2.43 guard: array opened but only whitespace so far => UNKNOWN', async () => {
    const raw = '{"verdict": "NEEDS REWORK", "blocking_items": [   ';
    const out = await run(raw);
    assert(out.rework_class_raw === 'UNKNOWN',
      'whitespace is not content and not proven emptiness, got ' + out.rework_class_raw);
  });

  await check('v4.2.43: no blocking_items key at all => PARSER', async () => {
    const out = await run('total garbage, no json here');
    assert(out.rework_class_raw === 'PARSER', 'gate named nothing -> transport-class event');
  });

  await check('v4.2.39 control (3): gate_major_count is exported and does NOT escalate', async () => {
    const out = await run(JSON.stringify({ verdict: 'IC-READY', blocking_items: [],
      major_items: ['m1', 'm2', 'm3'], minor_items: ['n1'] }));
    assert(out.gate_major_count === 3, 'the MAJOR count must be exported');
    assert(out.gate_minor_count === 1, 'the MINOR count must be exported');
    assert(String(out.verdict).toUpperCase().indexOf('REWORK') < 0,
      'THREE majors must NOT escalate to a block — "N MAJOR -> block" is forbidden (double gating)');
    assert(!out.gate_contract_defect, 'a clean IC-READY with majors is not a contract defect');
  });

  await check('v4.2.36 negative control: a REASONED block passes through verbatim', async () => {
    const out = await run(JSON.stringify(BLOCKED));
    assert(!out.gate_incoherent, 'a reasoned block is not incoherent');
    assert(out.blocking_items.length === 1, 'reasons preserved');
    assert(out.blocking_items[0].item === 'short_interest_unsourced', 'verbatim');
  });

  // ------------------------------------------------------------------------------------------
  // v4.2.55 (mandate RRR): the UNTERMINATED-TAIL family. Live Stage 4, 2026-07-30 — a complete
  // object missing ONE closing brace, finishReason STOP, 36 of 4096 tokens. Second occurrence in
  // a week. Repair is append-only/end-only and gated on the FULL contract; these pins exist to
  // prove it cannot become a fail-open. Every negative control below MUST stay fail-closed.
  // ------------------------------------------------------------------------------------------
  const LIVE_3007 = '{\n  "verdict": "IC-READY",\n  "blocking_items": [],\n' +
                    '  "major_items": [],\n  "minor_items": []';

  await check('v4.2.55 THE LIVE CASE: one missing brace is repaired and DECLARED', async () => {
    const out = await run(LIVE_3007);
    assert(out.parse_ok === true, 'the 2026-07-30 shape still dies as a PARSER event');
    assert(out.verdict === 'IC-READY', 'verdict lost: ' + out.verdict);
    assert(out._json_repaired_brackets === '}', 'repair must DECLARE itself, and say what it added');
    assert(out.gate_major_count === 0 && out.gate_minor_count === 0, 'counts must survive');
  });

  await check('v4.2.55 (b): exactly ONE closing brace, appended at the end, nothing else', async () => {
    const out = await run('{"verdict":"NEEDS REWORK","blocking_items":[{"item":"x","severity":"BLOCKING"}],'
                          + '"major_items":[],"minor_items":[]');
    assert(out.parse_ok === true, 'the recoverable shape (only the outer brace owed) was refused');
    assert(out._json_repaired_brackets === '}', 'exactly one "}" may ever be added, got: '
      + out._json_repaired_brackets);
    assert(out.verdict === 'NEEDS REWORK', 'a real BLOCK must survive the repair unchanged');
    assert(out.blocking_items.length === 1 && out.blocking_items[0].item === 'x',
      'content altered by a repair that is supposed to be append-only');
  });

  await check('v4.2.55 (b) mirror: MORE than the outer brace owed => refused, never guessed', async () => {
    // A cut inside a list leaves us unable to know what the model was about to name. Closing two
    // levels would invent a boundary. The only honest answer is a PARSER event.
    const out = await run('{"verdict":"IC-READY","blocking_items":[],"major_items":[{"item":"x"}'
                          + '],"minor_items":[{"item":"y"}');
    assert(out.parse_ok === false, 'FAIL-OPEN: closed more than the outer object');
    assert(out._json_repaired_brackets === undefined, 'nothing may be declared repaired here');
  });

  // --- negative controls: each MUST remain a PARSER event -------------------------------------
  const mustFailClosed = async (name, text) => check(name, async () => {
    const out = await run(text);
    assert(out.parse_ok === false, 'FAIL-OPEN: repair accepted a truncated contract');
    assert(out.verdict === 'NEEDS REWORK', 'a gate must fail closed');
    assert(out.blocking_items[0].item === 'gate_output_unparsed', 'parser event not named');
    assert(out._json_repaired_brackets === undefined, 'nothing may be declared repaired here');
  });

  // THE masquerade the contract check exists to stop: this balances to a VALID object with an
  // EMPTY blocking list. Accepting it would silently convert "the gate was about to name a
  // blocker" into "the gate named nothing" — the exact fail-open of the pre-v4.2.13 extractor.
  await mustFailClosed('v4.2.55 NC1: cut after "blocking_items": [ => still PARSER',
    '{"verdict":"NEEDS REWORK","blocking_items":[');
  await mustFailClosed('v4.2.55 NC2: cut after "major_items": [ => still PARSER',
    '{"verdict":"IC-READY","blocking_items":[],"major_items":[');
  await mustFailClosed('v4.2.55 NC3: cut after "minor_items": [ => still PARSER',
    '{"verdict":"IC-READY","blocking_items":[],"major_items":[],"minor_items":[');
  await mustFailClosed('v4.2.55 NC4: no verdict key => still PARSER',
    '{"blocking_items":[],"major_items":[],"minor_items":[]');
  await mustFailClosed('v4.2.55 NC5: a list that became a STRING => still PARSER',
    '{"verdict":"IC-READY","blocking_items":"none","major_items":[],"minor_items":[]');
  await mustFailClosed('v4.2.55 NC6: cut INSIDE a string literal => still PARSER (never close a quote)',
    '{"verdict":"NEEDS REWORK","blocking_items":[{"item":"short_i');

  await check('v4.2.55 NC8: a brace INSIDE a string must not be counted as structure', async () => {
    // Proves the string-awareness of the depth walk is load-bearing. Without it the `}` inside the
    // note pops the outer object, depth reaches 0, and a perfectly recoverable tail is refused.
    const out = await run('{"verdict":"IC-READY","blocking_items":[],"major_items":[],'
                          + '"minor_items":[],"note":"} not structure"');
    assert(out.parse_ok === true, 'a quoted brace was counted as structure');
    assert(out._json_repaired_brackets === '}', 'got ' + out._json_repaired_brackets);
  });

  await check('v4.2.55 NC7: duplicate key is NOT touched by the bracket repair', async () => {
    const out = await run('{"verdict":"NEEDS REWORK","verdict":"IC-READY","blocking_items":[],'
                          + '"major_items":[],"minor_items":[]}');
    assert(out.parse_ok === true, 'a COMPLETE object must parse on the normal path');
    assert(out._json_repaired_brackets === undefined,
      'a complete object must never reach the bracket path');
  });

  await check('v4.2.55 control: a WELL-FORMED object never declares a bracket repair', async () => {
    const out = await run(JSON.stringify({ verdict: 'IC-READY', blocking_items: [],
      major_items: [], minor_items: [] }));
    assert(out.parse_ok === true && out._json_repaired_brackets === undefined,
      'the repair must be invisible when nothing is broken');
  });

  // ------------------------------------------------------------------------------------------
  // v4.2.55 (mandate SSS #2): the rework CLASSIFIER, pinned at EVERY cut position. The class it
  // reports feeds rework_rate, which feeds the honest per-report cost, which feeds T/F. A wrong
  // class here is a wrong business number later, silently.
  // ------------------------------------------------------------------------------------------
  await check('v4.2.55 class: cut BEFORE the key => PARSER (the gate named no list)', async () => {
    const out = await run('{"verdict": "NEEDS REWORK"');
    assert(out.rework_class_raw === 'PARSER', 'got ' + out.rework_class_raw);
  });

  await check('v4.2.55 class: cut BETWEEN the key and its colon => UNKNOWN, never PARSER', async () => {
    // The defect of record: the key was invisible to a colon-anchored search, so a run whose gate
    // HAD named the list was filed as if it had named nothing.
    const out = await run('{"verdict": "NEEDS REWORK", "blocking_items"');
    assert(out.rework_class_raw === 'UNKNOWN',
      '"zero is not unknown" applies to the classifier itself, got ' + out.rework_class_raw);
  });

  await check('v4.2.55 class: key + colon, array never opened => UNKNOWN', async () => {
    const out = await run('{"verdict": "NEEDS REWORK", "blocking_items":');
    assert(out.rework_class_raw === 'UNKNOWN', 'got ' + out.rework_class_raw);
  });

  await check('v4.2.55 class: cut after [ with NOTHING in it => UNKNOWN (not "empty")', async () => {
    const out = await run('{"verdict": "NEEDS REWORK", "blocking_items": [   ');
    assert(out.rework_class_raw === 'UNKNOWN', 'got ' + out.rework_class_raw);
  });

  await check('v4.2.55 class: cut after [ WITH content => BLOCKING_UNPARSED', async () => {
    const out = await run('{"verdict": "NEEDS REWORK", "blocking_items": [{"item":"real_');
    assert(out.rework_class_raw === 'BLOCKING_UNPARSED', 'got ' + out.rework_class_raw);
  });

  await check('v4.2.55 class guard: the WORDS in prose are not a key => PARSER, not UNKNOWN', async () => {
    // The colon was the old form's only defence against prose. Removing it as an anchor must not
    // turn every memo that says "blocking items" into an UNKNOWN.
    const out = await run('I found no blocking items worth raising in this memo.');
    assert(out.rework_class_raw === 'PARSER', 'prose promoted to a named list: ' + out.rework_class_raw);
  });

  console.log('\n' + (failed ? 'FAILED' : 'OK') + ' — ' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
