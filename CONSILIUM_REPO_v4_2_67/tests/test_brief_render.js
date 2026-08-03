// v4.2.65 — pins for `Assemble Brief`, the HUMAN document.
//
// Lesson lensrender-01, applied before the fact this time: every earlier pin on the two lenses
// checked RESULT FIELDS, and the lens lines still never reached the report for two paid runs.
// So these pins assert on the RENDERED MARKDOWN, block by block, in both data states.
const fs = require('fs'), path = require('path');
const WF_DIR = path.join(__dirname, '..', 'workflow');
const WF = fs.readdirSync(WF_DIR).filter(f => /^consilium_spine_v/.test(f)).sort().pop();
const NODES = JSON.parse(fs.readFileSync(path.join(WF_DIR, WF), 'utf8')).nodes;
const CODE = NODES.find(n => n.name === 'Assemble Brief').parameters.jsCode;

let passed = 0, failed = 0;
function assert(c, m) { if (!c) throw new Error(m || 'assertion failed'); }
async function check(name, fn) {
  try { await fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + e.message); }
}

const RESULT = {
  ivc_base: { intrinsic_value: 68.96, implied_cagr_pct: 11.56, fv10_per_share: 214.19,
    eps_terminal_dilution_adj: 7.14,
    inputs: { price: 71.71, base_per_share: 2.528, g: 0.12569, future_pe: 30,
              dilution_cagr: -0.00888, hurdle: 0.12, discount_rate: 0.12, terminal_g: 0.04 } },
  dual_basis: { verdict_leg: 'fcf_per_share',
    gaap_eps: { iv: 68.96, implied_cagr_pct: 11.56, base_per_share: 2.528 },
    fcf_per_share: { iv: 58.68, implied_cagr_pct: 9.78, base_per_share: 2.178 } },
  central_lens: { iv: 93.30, growth_used: 0.15650, future_pe_used: 33.53,
                  delta_iv_vs_verdict_pct: 59.0, computed_on: 'gaap_base',
                  delta_vs: 'verdict_leg(fcf_per_share)', advisory_only: true, flags: [] },
  reverse_dcf: { g_implied_at_current_price: 0.1614, at_hurdle_pct: 12, future_pe_held: 30,
                 actual_rev_cagr_3y: 0.1264, actual_rev_cagr_5y: 0.1257,
                 selftest_reverse_matches_forward: true },
  gps: { total: 70, max: 100, blocks: [ { name: 'A (growth)', points: 13, max: 16 },
                                        { name: 'F (momentum)', points: 2, max: 10 } ] },
  mos_ladder: [ { mos_target_pct: 10, buy_threshold_price: 53.35, discount_to_current_pct: -25.6,
                  implied_cagr_at_threshold_pct: 13.07 },
                { mos_target_pct: 20, buy_threshold_price: 48.90, discount_to_current_pct: -31.8,
                  implied_cagr_at_threshold_pct: 14.06 },
                { mos_target_pct: 30, buy_threshold_price: 45.14, discount_to_current_pct: -37.0,
                  implied_cagr_at_threshold_pct: 14.98 } ],
  required_mos_rung_pct: 20, rung_signals: [],
  _fp_vectors: { total: 14, unverified: 14, pct: 1.0, data_questionable: true, threshold: 0.30 },
  street_view: { consensus_target_mean: 94.33, analyst_count: 58 },
  year5_reference: 69.64,
};

async function render(over) {
  const res = Object.assign({}, RESULT, over || {});
  const $ = (name) => ({ first: () => ({ json:
    name === 'Run Code' ? res
                        : { ticker: 'NFLX', chat_id: '12345',
                            _edgar: { cik: '0001065280', entity_name: 'NETFLIX INC' } } }) });
  const fn = new Function('$', `return (async () => { ${CODE} })();`);
  return (await fn($))[0];
}
async function renderMd(over) { return (await render(over)).json.brief_md; }

(async () => {
  const md = await renderMd();

  await check('every mandated block of the note is present', async () => {
    for (const h of ['## Покупать?', '## Сколько компания стоит?', '## По какой цене мы бы купили?',
                     '## Настроение рынка и главные новости', '## Что у компании хорошо',
                     '## Почему мы считаем именно так?', '## Оговорки', '# ПРИЛОЖЕНИЕ',
                     '## Расчёт по шагам', '## Источники']) {
      assert(md.indexOf(h) !== -1, 'missing block: ' + h);
    }
  });

  await check('the headline value is the VERDICT leg, not ivc_base', async () => {
    // ivc_base carries the GAAP leg (68.96); the verdict leg here is FCF (58.68). Printing the
    // wrong one would disagree with the machine report while looking entirely plausible.
    assert(/\$58\.68/.test(md), 'the verdict-leg IV is missing from the note');
    assert(!/Осторожная оценка\*\* \| \*\*\$68\.96/.test(md), 'the note printed the GAAP leg as the verdict');
  });

  await check('the ACTIVE rung is named and marked in the ladder', async () => {
    assert(/запас 20% — действует сейчас/.test(md), 'the active rung is not named');
    assert(/направленных сигналов тревоги в этом прогоне не было/i.test(md),
      'a base rung must say WHY it is base, or the reader cannot tell it from a raised one');
  });

  await check('a RAISED rung names its signal instead of the base wording', async () => {
    const raised = await renderMd({ required_mos_rung_pct: 30,
      rung_signals: ['sustained_blocking=1'] });
    assert(/Ступень поднята до 30%/.test(raised), 'a raised rung was not announced');
    assert(/sustained_blocking=1/.test(raised), 'the signal that raised it must be named');
  });

  // The heading exists ALWAYS. A section that vanishes on thin data teaches the reader the format
  // never had it; a heading with an honest line teaches the opposite — and it matters most on the
  // runs where the data failed, which is exactly when it used to disappear.
  await check('news section: HONEST ABSENCE when no news vectors survived', async () => {
    assert(/## Настроение рынка и главные новости за 6 месяцев/.test(md), 'heading missing');
    assert(/Новостные данные этого прогона неполны/.test(md), 'silent absence instead of an honest line');
    assert(/мнение модели, не расчёт/.test(md), 'the opinion disclaimer must ride with the section');
  });

  await check('news section: LIVE state prints the items and the direction', async () => {
    const live = await renderMd({
      news_highlights: [ { headline: 'Отчёт за 2 квартал: выручка +14%', iv_impact: '+$3' },
                         { headline: 'Регулятор ЕС открыл проверку' } ],
      sentiment_direction: 'улучшается' });
    assert(/выручка \+14%/.test(live) && /Регулятор ЕС/.test(live), 'news items did not render');
    assert(/Настроение рынка: улучшается/.test(live), 'the direction line is missing');
    assert(/мнение модели, не расчёт/.test(live), 'the disclaimer must survive the live state too');
  });

  await check('the data-quality caveat is inherited, with numbers', async () => {
    assert(/14 из 14/.test(md), 'the vector count must be stated, not summarised away');
    assert(/Числа из отчётности SEC этим не затронуты/.test(md),
      'the reader must be told the SEC figures are unaffected');
  });

  await check('no internal jargon reaches the human document', async () => {
    for (const bad of ['UNVERIFIED', 'PWFV', 'GPS', 'implied_cagr', 'verdict_cap', 'mos_ladder',
                       'FACT_PACK', 'DI=', 'gaap_eps', 'fcf_per_share']) {
      assert(md.indexOf(bad) === -1, 'internal token leaked into the brief: ' + bad);
    }
  });

  await check('the brief COMPUTES nothing — every number traces to RESULT', async () => {
    assert(!/\bMath\.(pow|exp|log)\b/.test(CODE), 'the brief is doing valuation arithmetic');
    assert(!/\*\*\s*10\b/.test(CODE), 'the brief is discounting on its own');
  });


  // ------------------------------------------------------------------------------------------
  // v4.2.66 — DELIVERY. The v4.2.65 brief rendered correctly and reached nobody: the node had no
  // outgoing connection, so the document was assembled and dropped. Every pin above passed while
  // it happened, because every pin above asserts on the rendered STRING — and the string was
  // perfect. `lensrender-01` one step further downstream: the render reached the markdown, the
  // markdown reached no one. Caught by the architect's grep on connections, not by this suite.
  // ------------------------------------------------------------------------------------------
  await check('v4.2.66: the brief emits a BINARY document, not just a string', async () => {
    const out = await render();
    assert(out.binary && out.binary.data, 'no binary payload — Send cannot attach a file');
    assert(/text\/markdown/.test(out.binary.data.mimeType), out.binary.data.mimeType);
    assert(/ЗАПИСКА/.test(out.binary.data.fileName), 'the filename must distinguish the two documents: '
      + out.binary.data.fileName);
    assert(out.json.chat_id !== undefined, 'chat_id must ride along or delivery has no address');
  });

  await check('v4.2.66: the payload DECLARES the pair contract', async () => {
    const out = await render();
    const pc = out.json.pair_contract || {};
    assert(Array.isArray(pc.expects) && pc.expects.length === 2, 'the run must declare it owes TWO documents');
    assert(pc.this_one === 'investor_brief', 'the document must name which half of the pair it is');
  });

  await check('v4.2.66: the brief is actually WIRED to a delivery node', async () => {
    const wf = JSON.parse(fs.readFileSync(path.join(WF_DIR, WF), 'utf8'));
    const out = (wf.connections['Assemble Brief'] || {}).main || [];
    const targets = [].concat.apply([], out).map(x => x.node);
    assert(targets.length > 0, 'FAIL-SILENT: the brief is assembled and thrown away');
    const senders = targets.filter(t => /^Send /.test(t));
    assert(senders.length > 0, 'the brief goes nowhere that delivers it: ' + targets);
    // And the machine report must still be delivered — a pair means BOTH, and "fixed" must not
    // mean one document replaced the other.
    const rep = [].concat.apply([], (wf.connections['Assemble Report'] || {}).main || [])
                  .map(x => x.node).filter(t => /^Send /.test(t));
    assert(rep.length > 0, 'the machine report lost its delivery: a pair means BOTH');
  });
  console.log('\n' + (failed ? 'FAILED' : 'OK') + ' — ' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
