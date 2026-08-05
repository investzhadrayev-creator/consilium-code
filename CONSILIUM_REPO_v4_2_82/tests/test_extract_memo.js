// v4.2.77 — pins for `Extract Memo`, specifically the (g).1 business-profile capture.
//
// The description itself is JUDGMENT and a model writes it. The CAPTURE is not judgment, and this
// file exists because the tempting version of it — "take the paragraph before THESIS" — works
// until the model reorders its own output, and then it ships the wrong paragraph silently, with a
// plausible story. Delimiters, or nothing.
const fs = require('fs'), path = require('path');
const WF_DIR = path.join(__dirname, '..', 'workflow');
const WF = fs.readdirSync(WF_DIR).filter(f => /^consilium_spine_v/.test(f)).sort().pop();
const NODES = JSON.parse(fs.readFileSync(path.join(WF_DIR, WF), 'utf8')).nodes;
const CODE = NODES.find(n => n.name === 'Extract Memo').parameters.jsCode;

let passed = 0, failed = 0;
function assert(c, m) { if (!c) throw new Error(m || 'assertion failed'); }
function check(name, fn) {
  try { fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + e.message); }
}

function run(text) {
  const $ = { first: () => ({ json: { content: [{ type: 'text', text: text }] } }) };
  const $input = $;
  return new Function('$input', `return (() => { ${CODE} })();`)($input)[0].json;
}

const PROFILE = 'Компания зарабатывает на подписке. Рост идёт из международных рынков. '
  + 'Главный вопрос — удержится ли цена подписки.';
const WRAPPED = '<<<BUSINESS_PROFILE>>>\n' + PROFILE + '\n<<<END_BUSINESS_PROFILE>>>\n\n'
  + '1. THESIS\nThe thesis prose lives here.';

check('the delimited profile is captured', () => {
  const out = run(WRAPPED);
  assert(out.business_profile === PROFILE,
    'the profile was not captured verbatim: ' + JSON.stringify(out.business_profile));
});

check('the delimiters do not survive into the machine report', () => {
  const out = run(WRAPPED);
  assert(out.memo_text.indexOf('BUSINESS_PROFILE') === -1, 'the markers leaked into the memo');
  assert(out.memo_text.indexOf('The thesis prose lives here.') !== -1,
    'stripping the profile ate the rest of the memo');
});

check('NO delimiters means NULL, never a stand-in paragraph', () => {
  // The failure this pin exists for: falling back to "the first paragraph" would publish the
  // thesis as a description, and the reader would never learn the description was missing.
  const out = run('1. THESIS\nThe thesis prose lives here.\n2. SCORECARD');
  assert(out.business_profile === null,
    'a memo without the block produced a profile anyway: ' + JSON.stringify(out.business_profile));
  assert(out.memo_text.indexOf('The thesis prose lives here.') !== -1, 'the memo was damaged');
});

check('an EMPTY block is an absence, not an empty description', () => {
  const out = run('<<<BUSINESS_PROFILE>>>\n   \n<<<END_BUSINESS_PROFILE>>>\n1. THESIS\nx');
  assert(out.business_profile === null, 'whitespace was published as a description');
});

check('a FAILED memo carries no profile at all', () => {
  // memo_ok=false means the runner error text is in memo_text. Scanning it for delimiters could
  // only ever produce garbage, and a description assembled from an error is worse than none.
  const $ = { first: () => ({ json: { type: 'error', error: { message: 'boom' } } }) };
  const out = new Function('$input', `return (() => { ${CODE} })();`)($)[0].json;
  assert(out.memo_ok === false, 'the error case stopped being an error');
  assert(out.business_profile === null, 'a profile was produced from a failed call');
});

console.log('\n' + (failed ? 'FAILED' : 'OK') + ' — ' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
