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
                  delta_vs: 'verdict_leg(fcf_per_share)', advisory_only: true, flags: [],
                  gap_decomposition: { verdict_iv: 58.68, base_change: 12.4,
                    growth_change: 21.7, multiple_change: 9.9,
                    bases_differ: true, multiple_differs: true,
                    note: 'they do not sum' } },
  // NOTE: the fixture must carry the FULL dual_basis, not just the leg name — the brief selects
  // the published leg object from it. A stub with only `verdict_leg` made the headline silently
  // fall back to ivc_base, which is exactly the defect pin brief-02 guards.
  dual_basis: { verdict_leg: 'fcf_per_share',
    gaap_eps: { iv: 68.96, implied_cagr_pct: 11.56, base_per_share: 2.528 },
    fcf_per_share: { iv: 58.68, implied_cagr_pct: 9.78, base_per_share: 2.178 } },
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
  : name === 'Parse DI' ? (res._di_payload || { required_mos_rung_pct: 20, rung_signals: [] })
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
    const raised = await renderMd({ _di_payload: { required_mos_rung_pct: 30,
      rung_signals: ['sustained_blocking=1'] } });
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

  // v4.2.68: the fifth defect of the 2026-08-03 matrix — the rung was read from RESULT, where it
  // has never lived, so `undefined` fell through to a literal 20 and every run printed "20%
  // действует сейчас" whether or not it did. A default wearing the clothes of a measurement, on
  // the single line that tells a reader what price to pay. Found by the fixture-vs-schema grep.
  await check('v4.2.68: an UNKNOWN rung is declared unknown, never defaulted to 20', async () => {
    const md2 = await renderMd({ _di_payload: {} });
    assert(/не определена этим прогоном/.test(md2),
      'an absent rung silently became the base rung');
    assert(!/действует сейчас/.test(md2), 'a row was marked active on no evidence');
    assert(/самую строгую ступень/.test(md2),
      'an unknown rung must send the reader to the safe end, not the convenient one');
  });

  // ------------------------------------------------------------------------------------------
  // v4.2.69 — prose about numbers is BUILT from the same field the numbers come from. The stored
  // sentence claimed "exactly two decisions" on every name: on META the ceiling contributed zero,
  // on ORCL the ceiling AND the base contributed zero and the whole gap was growth — while the
  // document asserted two factors and "nothing else differs". Third instance of the lensrender
  // class: the fix reached the computation and stopped before the prose.
  // ------------------------------------------------------------------------------------------
  await check('v4.2.69: only NON-ZERO factors are named in the gap prose', async () => {
    const md2 = await renderMd({ central_lens: Object.assign({}, RESULT.central_lens, {
      iv: 110.52, delta_iv_vs_verdict_pct: -12.6,
      gap_decomposition: { verdict_iv: 126.49, base_change: 0, growth_change: -15.97,
        multiple_change: 0, bases_differ: false, multiple_differs: false,
        note: 'they do not sum' } }) });
    assert(/темп роста/.test(md2), 'the one factor that acted was not named');
    assert(!/объясняется ровно двумя решениями/.test(md2), 'the stored constant survived');
    assert(/вклад нулевой/.test(md2), 'zero contributors must be stated as zero, not implied');
    assert(/НИЖЕ осторожной/.test(md2), 'the ORCL direction was not handled');
  });

  await check('v4.2.69: the ORCL direction is EXPLAINED, not just reported', async () => {
    // The verdict leg must move with it: the direction is a RELATION between the two numbers, and
    // a fixture that lowers only one of them tests nothing about the relation.
    const md2 = await renderMd({
      dual_basis: { verdict_leg: 'fcf_per_share',
        gaap_eps: { iv: 140.0, implied_cagr_pct: 12.5, base_per_share: 6.5 },
        fcf_per_share: { iv: 126.49, implied_cagr_pct: 11.70, base_per_share: 5.86 } },
      central_lens: Object.assign({}, RESULT.central_lens, {
      iv: 110.52, delta_iv_vs_verdict_pct: -12.6,
      gap_decomposition: { verdict_iv: 126.49, base_change: 0, growth_change: -15.97,
        multiple_change: 0, bases_differ: false, multiple_differs: false, note: 'x' } }) });
    assert(/скромнее оценки по крайним точкам/i.test(md2) || /медиана сгладила/i.test(md2),
      'a reader is told the direction flipped but not why');
    assert(!/Осторожная оценка ниже не потому/.test(md2),
      'the framing paragraph still asserts the opposite direction');
  });

  await check('v4.2.69 control: the usual direction still reads the usual way', async () => {
    const md2 = await renderMd();   // central 93.30 > verdict 58.68
    assert(/Осторожная оценка ниже не потому/.test(md2), 'the normal case lost its framing');
    assert(/выходной множитель/.test(md2) && /база расчёта/.test(md2),
      'all three acting factors must be named when all three act');
  });

  await check('v4.2.69: an unknown analyst count is stated, never printed as "?"', async () => {
    const md2 = await renderMd({ street_view: { consensus_target_mean: 94.33, analyst_count: null } });
    assert(/не раскрыто источником/.test(md2), 'absence was punctuated instead of stated');
    assert(!/\? аналитиков/.test(md2), 'a literal question mark reached the human document');
  });

  await check('v4.2.69: GPS is printed out of the ACHIEVABLE max, not a literal 100', async () => {
    const md2 = await renderMd({ gps: { total: 47, max: 94, blocks: [] } });
    assert(/47 из 94/.test(md2), 'the nominal 100 was printed over a reduced denominator');
  });

  await check('v4.2.69: a SINGLE-LEG run says so in the human document', async () => {
    const md2 = await renderMd({ dual_basis: null,
      flags: ['SINGLE_LEG_RUN: the FCF leg was not built (levered_fcf_per_share missing).'] });
    assert(/по одному основанию/.test(md2), 'a one-legged verdict was published silently');
    assert(/levered_fcf_per_share missing/.test(md2), 'the cause must travel with the caveat');
  });
  console.log('\n' + (failed ? 'FAILED' : 'OK') + ' — ' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
