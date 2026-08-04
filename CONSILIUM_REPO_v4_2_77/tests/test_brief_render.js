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
  // v4.2.71: the fixture carries the blocks whose HUMAN names the pin checks — a two-block stub
  // would have let `A_runway` and `G_capalloc` keep leaking while the pin stayed green.
  gps: { total: 70, max: 100, blocks: [
    { name: 'A (growth)', points: 13, max: 16 },
    { name: 'A_runway', points: 3, max: 4 },
    { name: 'G_capalloc', points: 4, max: 5 },
    { name: 'H_sentiment', points: 4, max: 5 },
    { name: 'F_forecast_trend', points: 4, max: 5 },
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
  // v4.2.71: the fixture must carry scenarios, or the catalyst section is "absent" for a reason
  // that has nothing to do with the renderer — and the manifest pin would be testing the fixture.
  bull_bear: { rows: [
    { side: 'BULL', probability: 0.35, delta_iv_pct: 39.6, label: 'Реклама удерживает рост выше коридора' },
    { side: 'BULL', probability: 0.25, delta_iv_pct: 23.7, label: 'Квартальная выручка ускоряется' },
    { side: 'BEAR', probability: 0.30, delta_iv_pct: -20.3, label: 'Возврат к среднему росту' },
    { side: 'BEAR', probability: 0.25, delta_iv_pct: -28.0, label: 'Сжатие мультипликатора' },
  ] },
  year5_reference: 69.64,
  // v4.2.77 (g).2: the thesis is built from THESE fields. The fixture carries them because a
  // fixture that lacks them would let the section be "absent" for a reason that has nothing to do
  // with the renderer — the shape that made three earlier pins test themselves.
  market_context: { capex_deployed_2y: 3480.0, capex_intensity_pct: 8.4,
                    revision_vs_price: { erb_90d: 0.031, rel_strength_6m: -0.182,
                                         divergence: true } },
};

async function render(over) {
  const res = Object.assign({}, RESULT, over || {});
  const $ = (name) => ({ first: () => ({ json:
    name === 'Run Code' ? res
  : name === 'Parse DI' ? (res._di_payload || { required_mos_rung_pct: 20, rung_signals: [] })
  : name === 'Collect Usage' ? { council: (res._council === undefined
      ? { participated: ['Stage 2a Claude','Stage 2b Claude','Stage 4 Gemini','Stage 5 Auditor','Stage 6 Arbiter'],
          absent: [], count: 5, full_slate: true }
      : res._council) }
                        : { ticker: 'NFLX', chat_id: '12345',
                            _edgar: { cik: '0001065280', entity_name: 'NETFLIX INC' } } }) });
  const fn = new Function('$', `return (async () => { ${CODE} })();`);
  return (await fn($))[0];
}
async function renderMd(over) { return (await render(over)).json.brief_md; }

(async () => {
  const md = await renderMd();

  // v4.2.71 — THE SECTION MANIFEST. The approved NFLX v2 mockup is the specification of CONTENT,
  // and the renderer must produce all of its sections IN ITS ORDER. The live META brief carried
  // fewer than half: no "what this means" column, no catalysts, no watch-list, no year-5 point, no
  // score breakdown, no glossary, and the six-step appendix flattened to a bare table. Cause is
  // structural, not clerical — the renderer was written from MANDATES, so only what a mandate
  // named by hand arrived, and nobody diffed the output against the mockup. This list is that diff,
  // performed by machine on every run.
  const SPEC_SECTIONS = [
    '## Покупать?',
    '## Инвестиционный тезис',
    '## Сколько компания стоит?',
    '## По какой цене мы бы купили?',
    '## Настроение рынка и главные новости',
    '## Что у компании хорошо, а что плохо',
    '## Почему мы считаем именно так?',
    '## Что может изменить ответ?',
    '## За чем следить',
    '## Оговорки к этому выпуску',
    '# ПРИЛОЖЕНИЕ',
    '## Расчёт по шагам, числами',
    '### Что здесь произошло, по шагам',
    '## Из чего сложились баллы',
    '## Словарь',
    '## Источники',
  ];

  await check('v4.2.71: every section of the SPEC is present', async () => {
    const missing = SPEC_SECTIONS.filter(h => md.indexOf(h) === -1);
    assert(missing.length === 0, 'sections lost between spec and render: ' + missing.join(' | '));
  });

  await check('v4.2.71: the sections appear in the SPEC ORDER', async () => {
    // Order is part of the document, not decoration: the note answers "buy?" before it explains
    // how, and an appendix that drifts above the caveats stops being an appendix.
    let prev = -1;
    for (const h of SPEC_SECTIONS) {
      const at = md.indexOf(h);
      assert(at > prev, 'section out of order: ' + h);
      prev = at;
    }
  });

  await check('v4.2.71: the quality table carries HUMAN names and a meaning column', async () => {
    assert(!/A_runway|G_capalloc|H_sentiment|F_forecast_trend/.test(md),
      'internal block identifiers reached the human document');
    assert(/Запас роста/.test(md) && /Распределение капитала/.test(md), 'human names missing');
    assert(/что это значит/.test(md), 'the approved meaning column is absent');
  });

  // v4.2.72 (operator): a score with no number behind it is unusable — "рост 4 из 16" does not say
  // whether revenue grew 4% or 14%. The evidence exists in RESULT for every block; the brief was
  // printing the verdict and discarding the reason.
  await check('v4.2.72: every score is accompanied by the NUMBER behind it', async () => {
    const md2 = await renderMd({ gps: { total: 47, max: 94, blocks: [
      { name: 'A (growth)', points: 4, max: 16,
        evidence: { rev_cagr3: 0.1048, rev_cagr5: 0.107, eps_cagr5: 0.0521 } },
      { name: 'D (balance sheet)', points: 8, max: 10,
        evidence: { de: 1.42, dilution_cagr: -0.00725, sbc_rev: 0.0714 } } ] } });
    assert(/на чём основан балл/.test(md2), 'the evidence column is missing');
    assert(/выручка \+10\.5% в год за 3 года/.test(md2), 'growth numbers not rendered');
    assert(/прибыль \+5\.2% за 5 лет/.test(md2), 'earnings growth not rendered');
    assert(/долг к капиталу 1\.42/.test(md2), 'balance-sheet numbers not rendered');
  });

  await check('v4.2.72: an unmeasured block SAYS so instead of showing a bare score', async () => {
    const md2 = await renderMd({ gps: { total: 10, max: 20, blocks: [
      { name: 'E_moat', points: 10, max: 15 } ] } });
    assert(/показатель этого блока не измерен/.test(md2),
      'a score with no evidence must declare the absence, not imply the number exists');
  });

  await check('v4.2.72: raw magnitudes and English labels are made readable', async () => {
    const md2 = await renderMd({ gps: { total: 3, max: 4, blocks: [
      { name: 'A_runway', points: 3, max: 4,
        evidence: 'rpo 638000000000 vs FY26 revenue 67357000000 (9.4x coverage)' } ] } });
    assert(/638\.0 млрд/.test(md2), 'a twelve-digit magnitude was published unreadable');
    assert(/законтрактованная выручка/.test(md2), 'English scorer labels reached the reader');
    assert(!/\brpo\b/.test(md2), 'the raw label survived translation');
  });

  await check('v4.2.71: catalysts are priced in DOLLARS of this valuation', async () => {
    assert(/### В пользу покупки/.test(md) && /### Против/.test(md), 'catalyst sides missing');
    assert(/добавит к оценке/.test(md) && /отнимет от оценки/.test(md),
      'catalysts must be stated as money, not as scenario machinery');
    assert(!/PWFV|сценар/i.test(md), 'scenario machinery leaked into the human document');
  });

  await check('v4.2.71: the two-lens table names the BASE when the bases differ', async () => {
    assert(/отправная точка на акцию \|/.test(md),
      'the largest contributor to the META gap had no row in the comparison table');
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

  await check('v4.2.73: the two kinds of data are marked SEPARATELY', async () => {
    // One label covered both, and "76% не подтверждено" read as "do not trust this report" while
    // every number deciding the verdict was complete. Marking a complete thing with an incomplete
    // thing's label is the same error as marking an incomplete thing with a complete one's.
    assert(/Расчётные данные \(отчётность SEC\): полные и проверенные/.test(md),
      'the verified half is not stated as verified');
    assert(/Новостной контекст: собрано 0 разделов из 14/.test(md),
      'the news half must be counted in LIVE sections, not in dead ones');
    assert(/Оценка стоимости этим не затронута/.test(md),
      'the reader must be told which half the gap does NOT touch');
    assert(!/качество данных под вопросом/.test(md),
      'the acceptance-language wording survived into the human document');
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

  // v4.2.70 — the run declares how many opinions formed it, and a missing GPS ceiling is an
  // absence rather than a nominal 100. Both are the ступень-умолчание shape: a constant standing
  // where a measurement should be, indistinguishable from one in the printed document.
  await check('v4.2.70: an INCOMPLETE council is declared in the human document', async () => {
    const md2 = await renderMd({ _council: { participated: ['Stage 2a Claude','Stage 2b Claude',
      'Stage 4 Gemini','Stage 5 Auditor','Stage 6 Arbiter'],
      absent: [{ stage: 'Stage 3 Grok', reason: 'not wired into the graph' }],
      count: 5, full_slate: false } });
    assert(/на 5 мнениях из 6/.test(md2), 'the council size was not stated');
    assert(/Stage 3 Grok/.test(md2), 'the empty seat must be named');
    assert(/не сбой прогона/.test(md2),
      'an absent seat must not read as a failure — it is a narrower construction, not a broken one');
  });

  await check('v4.2.70 control: a FULL council says nothing', async () => {
    const md2 = await renderMd();
    assert(!/мнениях из/.test(md2), 'a complete council must not add noise to every report');
  });

  await check('v4.2.70: a missing GPS ceiling is an absence, not a literal 100', async () => {
    const md2 = await renderMd({ gps: { total: 47, max: null, blocks: [] } });
    assert(/максимум этого прогона не измерен/.test(md2), 'the nominal 100 was printed again');
    assert(!/47 из 100/.test(md2), 'a constant stood in for an unmeasured denominator');
  });
    await check('v4.2.77 (g).2: the thesis is BUILT from the numbers printed beside it', async () => {
    const t = md.slice(md.indexOf('## Инвестиционный тезис'), md.indexOf('## Сколько компания стоит?'));
    assert(/12\.6%|12\.57%|12,6/.test(t) || /15\.7%|16\.1%/.test(t) || /%/.test(t),
      'the thesis names no measured number at all');
    assert(/8\.4%/.test(t), 'the capex leg lost its intensity figure');
    assert(/3\.1%/.test(t) && /-18\.2%/.test(t), 'the revisions-vs-price pair lost its numbers');
  });

  await check('v4.2.77 (g).2: the DIRECTION follows the sign, not a stored adjective', async () => {
    // Rule 10: an explanation true on one name and printed on all is a lie with a plausible story.
    const demanding = await renderMd({ reverse_dcf: { g_implied_at_current_price: 0.30,
      actual_rev_cagr_5y: 0.05, future_pe_held: 30 } });
    const forgiving = await renderMd({ reverse_dcf: { g_implied_at_current_price: 0.04,
      actual_rev_cagr_5y: 0.19, future_pe_held: 30 } });
    assert(/ТРЕБУЕТ УСКОРЕНИЯ/.test(demanding), 'a price demanding 30% vs a 5% record reads neutral');
    assert(/ДОПУСКАЕТ ЗАМЕДЛЕНИЕ/.test(forgiving), 'the wording did not follow the flipped sign');
    assert(!/ТРЕБУЕТ УСКОРЕНИЯ/.test(forgiving), 'both directions printed the same words');
  });

  await check('v4.2.77 (g).2: an unmeasured run states the absence, never invents a thesis',
    async () => {
      const bare = await renderMd({ reverse_dcf: {}, market_context: {} });
      const t = bare.slice(bare.indexOf('## Инвестиционный тезис'),
                           bare.indexOf('## Сколько компания стоит?'));
      assert(/Тезис не построен/.test(t), 'a run with no measured factor still produced prose');
      assert(/отсутствие данных, а не вывод/.test(t),
        'the absence must not read as a finding about the company');
    });

console.log('\n' + (failed ? 'FAILED' : 'OK') + ' — ' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
