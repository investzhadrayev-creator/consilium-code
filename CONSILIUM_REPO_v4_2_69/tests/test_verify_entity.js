// v4.2.57 — pins for the ENTITY GATE (`Verify FACT_PACK Entity`).
//
// THE CASE OF RECORD: ticker "MA" is also the postal abbreviation of Massachusetts. Stage 1 was
// handed the bare ticker and returned a FACT_PACK about the US state — on 2026-07-24 and on BOTH
// 2026-07-31 runs. Every memo noticed and tagged the sections [UNVERIFIED]; every run continued.
// Detection is not refusal, and for eight days there was no point in the graph at which a
// FACT_PACK could be refused: nine consumers read Stage 1 directly, by name.
//
// These pins guard one property and no more: the FACT_PACK either describes the filer GROUND_TRUTH
// resolved, or the run stops before any model reasons about it. Identity is not a matter of degree.
const fs = require('fs'), path = require('path');
const WF_DIR = path.join(__dirname, '..', 'workflow');
const WF = fs.readdirSync(WF_DIR).filter(f => /^consilium_spine_v/.test(f)).sort().pop();
const NODES = JSON.parse(fs.readFileSync(path.join(WF_DIR, WF), 'utf8')).nodes;
const CODE = NODES.find(n => n.name === 'Verify FACT_PACK Entity').parameters.jsCode;

let passed = 0, failed = 0;
function assert(cond, msg) { if (!cond) throw new Error(msg || 'assertion failed'); }
async function check(name, fn) {
  try { await fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + e.message); }
}

// Returns { out } on pass, { err } on refusal — a thrown error IS the refusal here.
async function run(factpackText, edgar, ticker) {
  const payload = { choices: [{ message: { content: factpackText } }], id: 'resp-1' };
  const $ = (name) => ({ first: () => ({ json:
    name === 'Eligibility' ? { ticker: ticker || 'MA', _edgar: edgar } : payload }) });
  const $input = { first: () => ({ json: payload }) };
  const fn = new Function('$', '$input', `return (async () => { ${CODE} })();`);
  try { return { out: (await fn($, $input))[0].json, payload }; }
  catch (e) { return { err: e.message, payload }; }
}

const GT = { cik: '0001141391', entity_name: 'Mastercard Incorporated' };
const OK_ECHO = 'RESOLVED_ENTITY: Mastercard Incorporated (CIK 0001141391)\n\n## 1. Revenue\n...';

(async () => {
  let r;

  r = await run(OK_ECHO, GT);
  await check('match: the APPROVED CONTENT passes through byte-identical', () => {
    assert(!r.err, 'refused a matching entity: ' + r.err);
    // v4.2.57a: the gate now ATTACHES a measurement (_fp_vectors), so it is no longer the same
    // object — but every byte it approved must be the same byte. The property that matters is
    // "nothing I approved was altered", not "I returned the identical reference"; pinning the
    // reference would have blocked adding a measurement that changes nothing about the content.
    assert(r.out.choices === r.payload.choices, 'the approved content was copied or edited');
    assert(r.out.choices[0].message.content === OK_ECHO, 'content was altered in transit');
    assert(r.out._fp_vectors, 'the measurement must ride with the approved payload');
  });

  // SEC writes 0001141391; models and humans write 1141391. Comparing as strings would refuse
  // every correct FACT_PACK, which is the failure mode that turns a gate off within a week.
  r = await run('RESOLVED_ENTITY: Mastercard Incorporated (CIK 1141391)\n...', GT);
  await check('match: leading zeros are not a mismatch', () => {
    assert(!r.err, 'refused on zero-padding alone: ' + r.err);
  });

  // The live 2026-07-24 shape: a real FACT_PACK, about the wrong legal person.
  r = await run('RESOLVED_ENTITY: Commonwealth of Massachusetts (CIK 0000317540)\n...', GT);
  await check('THE MA CASE: a different CIK is refused as FACTPACK_ENTITY_MISMATCH', () => {
    assert(r.err, 'FAIL-OPEN: a FACT_PACK about another entity was allowed through');
    assert(/^FACTPACK_ENTITY_MISMATCH/.test(r.err), r.err);
    assert(/1141391/.test(r.err) && /317540/.test(r.err), 'both CIKs must be named: ' + r.err);
  });

  r = await run('## 1. Revenue and EPS by year\nMastercard is a payments network...', GT);
  await check('no echo at all: FACTPACK_ENTITY_UNVERIFIED, never assumed-correct', () => {
    assert(r.err, 'FAIL-OPEN: an unidentified FACT_PACK was allowed through');
    assert(/^FACTPACK_ENTITY_UNVERIFIED/.test(r.err), r.err);
  });

  // Unknown is not a pass. If GROUND_TRUTH could not resolve a CIK there is nothing to verify
  // against, and "nothing to verify against" must never read as "verified".
  r = await run(OK_ECHO, { cik: null, entity_name: null });
  await check('no CIK in GROUND_TRUTH: refuse, do not wave through', () => {
    assert(r.err, 'FAIL-OPEN: verified against nothing');
    assert(/^FACTPACK_ENTITY_UNVERIFIED/.test(r.err), r.err);
  });

  r = await run('RESOLVED_ENTITY: Mastercard Incorporated (CIK 0001141391)', GT);
  await check('the echo alone, with no body, still passes — the gate judges IDENTITY only', () => {
    assert(!r.err, 'the gate strayed beyond identity: ' + r.err);
  });

  // ---- v4.2.57a: the FACT_PACK VECTOR COUNT lives here, not in a renderer. -------------------
  // It first shipped inside Assemble Report — one of TWO terminal assemblers — so the CBRS and SMR
  // runs of 2026-08-02, both routed to Core-V, carried NO vector line while carrying 32 and 46
  // [UNVERIFIED] tags. The names that most needed the count were structurally unable to receive it.
  const FP = (n) => 'RESOLVED_ENTITY: Mastercard Incorporated (CIK 0001141391)\n' + n;
  const SEC = (title, dead) => '\n## ' + title + '\n' + (dead ? 'no usable data [UNVERIFIED]' : 'revenue 28.2B');

  r = await run(FP(SEC('1. Revenue', 0) + SEC('2. Margins', 0) + SEC('3. Street', 1) +
                   SEC('4. Regulation', 1)), GT);
  await check('counter: 2 of 4 dead = 50% -> data_questionable above the 30% threshold', () => {
    const v = r.out._fp_vectors;
    assert(v, 'the count must ride WITH the verified payload');
    assert(v.total === 4 && v.unverified === 2, JSON.stringify(v));
    assert(v.pct === 0.5, 'pct=' + v.pct);
    assert(v.data_questionable === true, 'half the vectors are gone and nothing said so');
  });

  r = await run(FP(SEC('1. Revenue', 0) + SEC('2. Margins', 0) + SEC('3. Street', 0) +
                   SEC('4. Regulation', 0) + SEC('5. Moat', 1)), GT);
  await check('counter: 1 of 5 dead = 20% -> thin but NOT flagged', () => {
    const v = r.out._fp_vectors;
    assert(v.total === 5 && v.unverified === 1, JSON.stringify(v));
    assert(v.data_questionable === false, 'a normal run must not raise the flag');
  });

  await check('counter: the PROVISIONAL origin label travels with the number', () => {
    const v = r.out._fp_vectors;
    assert(v.threshold === 0.30, 'threshold=' + v.threshold);
    assert(/PROVISIONAL/.test(v.threshold_origin) && /n=4/.test(v.threshold_origin),
      'a threshold calibrated on thin data must SAY so wherever it is read: ' + v.threshold_origin);
  });

  await check('counter: the verified content is still byte-identical beside the count', () => {
    assert(r.out.choices === r.payload.choices,
      'the gate may ADD a measurement, never touch what it approved');
  });

  // Neither assembler may recompute the count: a renderer deriving what it publishes is a second
  // source of truth for one fact, and the two drift apart the first time either is edited.
  await check('both assemblers READ the count and neither computes it', () => {
    // v4.2.65: THREE assemblers now (Report, Core-V, Brief). The number is pinned deliberately —
    // when it changes, the surface pre-registration must be redone, and this pin is what forces
    // that. It was raised from 2 to 3 in the same changeset that added the third, never before.
    const asm = NODES.filter(n => /^Assemble /.test(n.name));
    assert(asm.length === 3, 'assembler list changed — re-run the surface pre-registration: '
      + asm.map(n => n.name));
    for (const a of asm) {
      const code = a.parameters.jsCode || '';
      assert(/_fp_vectors/.test(code), a.name + ' does not read the count — coverage gap');
      assert(/fpLine/.test(code), a.name + ' reads the count but never prints it');
      assert(!/indexOf\('\[UNVERIFIED\]'\)/.test(code),
        a.name + ' RECOMPUTES the count: one fact, one home');
    }
  });

  console.log('\n' + (failed ? 'FAILED' : 'OK') + ' — ' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
