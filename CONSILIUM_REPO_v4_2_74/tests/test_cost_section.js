// v4.2.5 — the billing path, driven end-to-end in JS.
//
// The python suite (test_pricing.py) owns the ARITHMETIC. This file owns the two things python
// cannot see: whether `Collect Usage` actually harvests, and whether `Assemble Report` tells the
// truth when the ledger is missing. Both are node code, and node code is where this project's
// bugs live — every defect found on 2026-07-17 was in a caller, not in a computation.
const fs = require('fs');
const path = require('path');

const wfDir = path.join(__dirname, '..', 'workflow');
const wfFile = fs.readdirSync(wfDir)
  .filter(f => /^consilium_spine_v\d+_\d+(_\d+)?\.json$/.test(f))
  .sort().pop();
const wf = JSON.parse(fs.readFileSync(path.join(wfDir, wfFile), 'utf8'));
const nodeByName = {};
for (const n of wf.nodes) nodeByName[n.name] = n;

let passed = 0, failed = 0;
function check(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.error('  FAIL ' + name + '\n       ' + e.message); failed++; }
}
function assert(c, m) { if (!c) throw new Error(m || 'assertion failed'); }

// Realistic provider responses: five schemas, exactly as they arrive.
const RESP = {
  'Stage 1 FP fin': { usage: { prompt_tokens: 4000, completion_tokens: 2000 } },
  'Stage 2a Claude': { model: 'claude-sonnet-5', usage: { input_tokens: 50000, output_tokens: 8000,
      cache_read_input_tokens: 30000, cache_creation_input_tokens: 20000 } },
  'Stage 2b Claude': { model: 'claude-sonnet-5', usage: { input_tokens: 40000, output_tokens: 6000 } },
  'Stage 4 Gemini': { usageMetadata: { promptTokenCount: 30000, candidatesTokenCount: 4000,
      thoughtsTokenCount: 5000 } },
  'Stage 5 Auditor': { model: 'gpt-5.6-sol', usage: { prompt_tokens: 25000, completion_tokens: 9000,
      completion_tokens_details: { reasoning_tokens: 7000 } } },
  'Stage 6 Arbiter': { model: 'claude-opus-4-8', usage: { input_tokens: 60000, output_tokens: 10000 } },
};
// v4.2.26 (BACKLOG #5 ran-map pin, final): ABSENT used to hardcode the not-on-path stage list —
// a THIRD copy of the topology (after the code's NOT_ON_PATH and the graph itself), exactly the
// silent-drift risk the architect flagged. Derive it FROM the Collect Usage source instead, so
// this test always exercises the REAL base map. TestMeterMapTopologyV4221 (python) separately
// pins that this same map matches the workflow graph — so graph -> map -> runtime behaviour is
// one closed chain with no hand-copied third home.
const ABSENT = (() => {
  const code = nodeByName['Collect Usage'].parameters.jsCode;
  const m = code.match(/const NOT_ON_PATH = new Set\(\[([^\]]*)\]\)/);
  if (!m) throw new Error('could not extract NOT_ON_PATH from Collect Usage — format changed?');
  const members = [...m[1].matchAll(/'([^']+)'/g)].map(x => x[1]);
  if (!members.length) throw new Error('NOT_ON_PATH parsed empty — refusing to run on a false-green map');
  return new Set(members);
})();

function runCollect(diClass) {
  const $ = (name) => {
    if (ABSENT.has(name)) throw new Error('node did not execute');   // n8n's real behaviour
    if (name === 'Eligibility') return { first: () => ({ json: { ticker: 'NFLX' } }) };
    return { first: () => ({ json: RESP[name] || null }) };
  };
  // v4.2.21: Collect Usage now reads di_payload.di_class from the main line ($input) to know
  // whether Stage 5/6 were meant to run (full) or were skipped by design (gated).
  const $input = { first: () => ({ json: { di_class: diClass || 'CONTESTED' } }) };
  const code = nodeByName['Collect Usage'].parameters.jsCode;
  return new Function('$', '$input', `return (() => { ${code} })();`)($, $input);
}

console.log('validating: ' + wfFile + '\n');
console.log('Collect Usage');

const collected = runCollect()[0].json;

check('harvests usage from every stage that ran', () => {
  const ok = collected.stages.filter(s => s.ran && s.response);
  assert(ok.length === 6, 'expected 6 executed stages (Grok disabled), got ' + ok.length);
});

check('a node that never executed is ran=false, NOT a zero-cost lie', () => {
  // Core-V branch + disabled Grok are genuinely not-on-path here. ran must be false for them.
  for (const name of ABSENT) {
    const s = collected.stages.find(x => x.stage === name);
    assert(s, 'stage missing from ledger entirely: ' + name);
    assert(s.ran === false, name + ' should be ran=false');
  }
});

check('D.2: an on-path stage whose reference throws is a LOST METER, not "not run"', () => {
  // The 2026-07-18 defect: Stage 1 and 2a EXECUTED (fact pack cited, scenarios built), yet a
  // custody throw on $('Stage 1') printed them "_not run_", understating the run by ~$0.25-0.35.
  // A stage on the Core-P main line always ran; a throw there is a meter we could not read, and
  // pricing.py must be fed ran=true so it labels it meter_lost (money spent, unmeasured).
  const $throwStage1 = (name) => {
    if (name === 'Stage 1 FP fin') throw new Error('custody: long-range reference died');
    if (ABSENT.has(name)) throw new Error('node did not execute');
    if (name === 'Eligibility') return { first: () => ({ json: { ticker: 'NFLX' } }) };
    return { first: () => ({ json: RESP[name] || null }) };
  };
  const $input = { first: () => ({ json: { di_class: 'CONTESTED' } }) };
  const code = nodeByName['Collect Usage'].parameters.jsCode;
  const out = new Function('$', '$input', `return (() => { ${code} })();`)($throwStage1, $input)[0].json;
  const s1 = out.stages.find(x => x.stage === 'Stage 1 FP fin');
  assert(s1.ran === true, 'an on-path stage that threw must stay ran=true (it DID run) — this is the whole fix');
  assert(s1.response == null, 'the meter is unreadable, so response is null');
  assert(s1.meter_unreachable === true, 'the custody failure must be surfaced explicitly');
});

check('D.2: on a GATED run, Stage 5/6 are truly not_run, not lost meters', () => {
  // gated trims the adversarial chain BY DESIGN — 5/6 did not run, so they are a real zero.
  // Only the mode signal (di_class) may make this call; a bare throw could not tell the two apart.
  const $gated = (name) => {
    if (name === 'Stage 5 Auditor' || name === 'Stage 6 Arbiter') throw new Error('gated: skipped');
    if (ABSENT.has(name)) throw new Error('node did not execute');
    if (name === 'Eligibility') return { first: () => ({ json: { ticker: 'NFLX' } }) };
    return { first: () => ({ json: RESP[name] || null }) };
  };
  const $input = { first: () => ({ json: { di_class: 'GATED' } }) };
  const code = nodeByName['Collect Usage'].parameters.jsCode;
  const out = new Function('$', '$input', `return (() => { ${code} })();`)($gated, $input)[0].json;
  for (const name of ['Stage 5 Auditor', 'Stage 6 Arbiter']) {
    const s = out.stages.find(x => x.stage === name);
    assert(s.ran === false, name + ' on a gated run must be ran=false (skipped by design)');
    assert(!s.meter_unreachable, name + ' gated is not a lost meter — it genuinely did not run');
  }
});

check('every stage in the pipeline appears in the ledger', () => {
  // A stage silently omitted from STAGES would be invisible spend — the worst failure mode here,
  // because it is the one that looks like everything is fine.
  const llmNodes = wf.nodes.filter(n => {
    const u = (n.parameters && n.parameters.url) || '';
    return /anthropic|openai|x\.ai|perplexity|generativelanguage/.test(u);
  }).map(n => n.name);
  const covered = new Set(collected.stages.map(s => s.stage));
  for (const n of llmNodes) assert(covered.has(n), 'LLM node not billed: ' + n);
});

check('the model in each node body matches the model Collect Usage bills', () => {
  // v4.2.6: the model id lives in TWO places -- the request body and the STAGES list here -- and
  // n8n gives a Code node no way to read a sibling's parameters. Change one and the run is priced
  // against the other. That is a live trap: Stage 3 moved 4.3 -> 4.5 and the two rates differ by
  // 2.4x on output. This test reads the real node bodies and refuses to let them diverge.
  const code = nodeByName['Collect Usage'].parameters.jsCode;
  for (const n of wf.nodes) {
    const body = (n.parameters && n.parameters.jsonBody) || '';
    const m = /model:\s*\\?"([a-z0-9.\-]+)\\?"/i.exec(body)
           || /\/models\/([a-z0-9.\-]+):generateContent/i.exec((n.parameters && n.parameters.url) || '');
    if (!m) continue;
    const inList = new RegExp("'" + n.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + "'\\s*,\\s*'[a-z]+'\\s*,\\s*'" + m[1].replace(/\./g, '\\.') + "'").test(code);
    const named = new RegExp("'" + n.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + "'").test(code);
    if (!named) continue;
    assert(inList, n.name + ' sends model ' + m[1] + ' but Collect Usage bills a different one');
  }
});

check('model drift against the provider echo is detected, not trusted', () => {
  // The model ids are duplicated in this node. If a node body changes model and this list does
  // not, the run is priced against the wrong rate. The provider echo is the check.
  const saved = RESP['Stage 6 Arbiter'];
  RESP['Stage 6 Arbiter'] = { model: 'claude-fable-5', usage: { input_tokens: 1, output_tokens: 1 } };
  const c = runCollect()[0].json;
  RESP['Stage 6 Arbiter'] = saved;
  assert(c.model_drift.length === 1, 'drift not detected: ' + JSON.stringify(c.model_drift));
  assert(/claude-fable-5/.test(c.model_drift[0]), 'drift message must name what was actually served');
});

check('computes no prices itself — arithmetic belongs to pricing.py', () => {
  const code = nodeByName['Collect Usage'].parameters.jsCode;
  // Strip comments and ALL n8n runtime references ($input, $json, $(...)) before the heuristic —
  // otherwise the bare '$' in '$input' (added in v4.2.18/v4.2.21 for the di_payload/di_class read)
  // trips the price detector, which is meant to catch ARITHMETIC ($5, usd, rate), not references.
  const scrubbed = code.replace(/\/\/.*$/gm, '').replace(/\$input/g, '').replace(/\$json/g, '')
                       .replace(/\$\(/g, '');
  assert(!/\$|usd|price|rate|\*\s*5\b/i.test(scrubbed),
    'Collect Usage looks like it is pricing things; that is pricing.py\'s job, one home only');
});

console.log('\nAssemble Report — cost section');

function runAssemble(ledger) {
  const $ = (name) => {
    if (name === 'Cost Ledger') {
      if (ledger === 'ABSENT') throw new Error('node did not execute');
      return { first: () => ({ json: ledger }) };
    }
    if (name === 'Collect Usage') return { first: () => ({ json: { model_drift: [] } }) };
    if (name === 'Eligibility') return { first: () => ({ json: { ticker: 'NFLX', chat_id: '1' } }) };
    return { first: () => ({ json: {} }) };
  };
  const code = nodeByName['Assemble Report'].parameters.jsCode;
  try { return new Function('$', `return (() => { ${code} })();`)($); }
  catch (e) { return { _threw: e }; }
}

const GOOD = {
  rows: [{ stage: 'Stage 6 Arbiter', model: 'claude-opus-4-8', status: 'ok', input_tokens: 60000,
           output_tokens: 10000, cache_read_tokens: 0, cache_write_tokens: 0, est_cost_usd: 0.55 },
         { stage: 'Stage 3 Grok', model: 'grok-4.3', status: 'ok', input_tokens: 9000,
           output_tokens: 3000, est_cost_usd: null, cost_status: '[UNVERIFIED]' }],
  totals: { input_tokens: 69000, output_tokens: 13000, est_cost_usd: 0.55,
            est_cost_is_partial: true, excluded_unpriced: ['Stage 3 Grok (grok-4.3)'],
            excluded_meter_lost: [], understated_incomplete: ['Stage 1 FP fin'] },
  price_table: { as_of: '2026-07-17', age_days: 0, stale: false, stale_after_days: 90,
                 expiring: [{ model: 'claude-sonnet-5', status: 'EXPIRING', on: '2026-08-31',
                              detail: 'intro rate lapses in 45 days' }],
                 unverified_by_operator: ['claude-opus-4-8'] },
  _basis: 'tokens: exact. dollars: ESTIMATE.',
};

check('a partial total SAYS it is partial and names what it dropped', () => {
  const r = runAssemble(GOOD);
  assert(!r._threw, 'Assemble threw: ' + (r._threw && r._threw.message));
  const md = Buffer.from(r[0].binary.data.data, 'base64').toString('utf8');
  assert(/PARTIAL/.test(md), 'a partial total that does not say so understates the bill silently');
  assert(/the real bill is HIGHER/.test(md), 'the direction of the error must be stated');
  assert(/Stage 3 Grok \(grok-4\.3\)/.test(md), 'unpriced stage not named');
});

check('an unpriced stage renders [UNVERIFIED], never $0.00', () => {
  const md = Buffer.from(runAssemble(GOOD)[0].binary.data.data, 'base64').toString('utf8');
  const grokRow = md.split('\n').find(l => l.indexOf('grok-4.3') >= 0);
  assert(/\[UNVERIFIED\]/.test(grokRow), 'unpriced row: ' + grokRow);
  assert(!/\$0\.0000/.test(grokRow), 'an unpriced model was rendered as free: ' + grokRow);
});

check('an expiring intro rate is surfaced before it lapses', () => {
  const md = Buffer.from(runAssemble(GOOD)[0].binary.data.data, 'base64').toString('utf8');
  assert(/EXPIRING.*2026-08-31/.test(md), 'the sonnet-5 intro expiry was not surfaced');
});

check('the price-table date travels with the number', () => {
  const md = Buffer.from(runAssemble(GOOD)[0].binary.data.data, 'base64').toString('utf8');
  assert(/Price table as of 2026-07-17/.test(md), 'a dollar figure without its rate date is a claim with no basis');
});

check('a MISSING ledger is not a free run', () => {
  const md = Buffer.from(runAssemble('ABSENT')[0].binary.data.data, 'base64').toString('utf8');
  assert(/NOT a \$0 run/.test(md), 'ledger absent and the report implied the run was free');
});

check('a FALLBACK ledger is not a free run either', () => {
  const md = Buffer.from(runAssemble({ _FALLBACK: true, error: 'boom' })[0].binary.data.data,
    'base64').toString('utf8');
  assert(/NOT a \$0 run/.test(md), '/cost errored and the report implied the run was free');
});

check('a missing ledger does NOT take the report down', () => {
  // The whole reason Cost Ledger runs onError=continueRegularOutput. A cosmetic section must
  // never cost the analysis.
  const r = runAssemble('ABSENT');
  assert(!r._threw, 'Assemble threw when the ledger was absent: ' + (r._threw && r._threw.message));
  const md = Buffer.from(r[0].binary.data.data, 'base64').toString('utf8');
  assert(/Arbiter Verdict/.test(md), 'the report lost its analytical content over a billing section');
});

check('Telegram gets a cost summary, and it degrades honestly too', () => {
  assert(/\[UNVERIFIED — ledger unavailable\]/.test(runAssemble('ABSENT')[0].json.cost_summary),
    'telegram summary claimed a number it did not have');
  assert(/\$0\.55/.test(runAssemble(GOOD)[0].json.cost_summary), 'telegram summary missing the estimate');
});

check('the full ledger is exposed for the Postgres append', () => {
  assert(runAssemble(GOOD)[0].json.cost_ledger, 'cost_ledger not passed through — nothing to store');
});

  // v4.2.70 — a DISCONNECTED stage is not a participant with an idle meter.
  // `| Stage 3 Grok | grok-4.5 | — | — | —/— | _not run_ |` shipped in twelve reports. The stage
  // has had no edge in or out since before v4.2.44, disconnected by a deliberate and well-argued
  // operator decision — but the row printed a model id, and a model id beside a stage name reads
  // as "this model was consulted". Two readers took it that way. The price-map constant is kept
  // for the drift watchdog and no longer printed.
  check('v4.2.70: a disconnected stage prints no model id', () => {
    const grok = collected.stages.find(x => x.stage === 'Stage 3 Grok');
    assert(grok, 'the stage vanished from the ledger entirely — it must still be accounted for');
    assert(grok.model === null, 'a price-map constant was published as if it had served: ' + grok.model);
    assert(grok.model_configured === 'grok-4.5',
      'the configured id must survive for the drift watchdog, just not for the reader');
    assert(grok.on_path_participant === false, 'a disconnected stage counted as a participant');
  });

  check('v4.2.70: the council composition is DECLARED, with the empty seat named', () => {
    assert(collected.council, 'no council declaration — the reader cannot tell 3 opinions from 4');
    assert(collected.council.full_slate === false, 'an incomplete council reported itself as full');
    const seats = collected.council.absent.map(a => a.stage);
    assert(seats.indexOf('Stage 3 Grok') !== -1, 'the empty seat is not named: ' + seats);
  });

  check('v4.2.70 control: a stage that IS on path keeps its model id', () => {
    const s2a = collected.stages.find(x => x.stage === 'Stage 2a Claude');
    assert(s2a.model, 'suppression leaked onto a participating stage');
    assert(s2a.on_path_participant === true, 's2a stopped counting as a participant');
  });

console.log('');
if (failed) { console.error('FAILED — ' + passed + ' passed, ' + failed + ' failed'); process.exit(1); }
console.log('OK — ' + passed + ' passed, 0 failed');
