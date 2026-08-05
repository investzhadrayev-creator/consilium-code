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
  // v4.2.82: street_view as analyze() publishes it — the section is rendered from these fields.
  street_view: { consensus_target_mean: 248.15, analyst_count: 49, pwfv_vs_street_pct: -45.8,
                 upside_to_target_pct: 74.9,
                 recommendation_breakdown: { strongBuy: 15, buy: 25, hold: 8, sell: 1,
                                             strongSell: 0, total: 49 } },
  // v4.2.77 (g).2: the thesis is built from THESE fields. The fixture carries them because a
  // fixture that lacks them would let the section be "absent" for a reason that has nothing to do
  // with the renderer — the shape that made three earlier pins test themselves.
  market_context: { capex_deployed_2y: 3480.0, capex_intensity_pct: 8.4,
                    revision_vs_price: { erb_90d: 0.031, rel_strength_6m: -0.182,
                                         divergence: true } },
  // v4.2.77 (g).4: peer median and company multiple on ONE basis, with N. The fixture carries the
  // trailing pair because that is what the pipeline actually produces (edgar_tiingo_trailing_inhouse).
  peer_multiple: { median: 24.6, count: 5, basis: 'edgar_tiingo_trailing_inhouse',
                   company: 31.2, company_basis: 'alpha_vantage_trailing_reported',
                   comparable: true, excluded_from_pe_cap: true,
                   rows: [{ ticker: 'MSFT', market_cap: 3.1e12, revenue_ltm: 2.7e11,
                            pe_trailing: 34.2, fy_end: '2026-06-30' },
                          { ticker: 'SAP', market_cap: 3.2e11, revenue_ltm: 3.8e10,
                            pe_trailing: 23.84, fy_end: '2025-12-31' },
                          { ticker: 'CRM', market_cap: 2.4e11, revenue_ltm: 3.9e10,
                            pe_trailing: 21.1, fy_end: '2026-01-31' }] },
  // (I) v4.2.79 — three fiscal years as analyze() publishes them, fiscal-year END on every row.
  three_year_table: { price_used: 141.85, pe_basis: "today's price / that year's EPS",
    rows: [{ fy_end: '2024-05-31', revenue: 5.28e10, net_income: 1.05e10, eps: 3.77,
             fcf: 1.18e10, pe_at_todays_price: 37.63 },
           { fy_end: '2025-05-31', revenue: 5.72e10, net_income: 1.22e10, eps: 4.34,
             fcf: 9.9e9, pe_at_todays_price: 32.68 },
           { fy_end: '2026-05-31', revenue: 6.74e10, net_income: 1.24e10, eps: 4.31,
             fcf: null, pe_at_todays_price: 32.91 }] },
  // v4.2.77 (g).3: the pack as the merge actually shapes it — themed sections, some dated, some
  // refused. A fixture of clean dated bullets would have proved only that a regex matches a regex.
  _fact_pack: [
    '## 5. News catalysts',
    '* 2026-06-18 — announced a multi-year cloud contract with a named counterparty.',
    '* Management repeatedly described demand as strong.',
    '* [UNVERIFIED] — analyst day date not found in the search results.',
    '## 6. Moat evidence',
    '* 2026-05-02 — competitor launched a rival tier.',
    '## 12. Latest reported quarter',
    '* Q2 2026 — backlog reported at $638bn on the earnings call.',
    '* [TERMINAL-ONLY: professional-terminal data, not reachable by search]',
  ].join('\n'),
};

async function render(over) {
  const res = Object.assign({}, RESULT, over || {});
  const $ = (name) => ({ first: () => ({ json:
    name === 'Run Code' ? res
  : name === 'Parse DI' ? (res._di_payload || { required_mos_rung_pct: 20, rung_signals: [] })
  : name === 'Extract Memo' ? { memo_text: 'memo', memo_ok: true,
      business_profile: (res._business_profile === undefined
        ? 'Компания зарабатывает на подписке. Рост идёт из международных рынков. '
          + 'Главный вопрос — удержится ли цена подписки.'
        : res._business_profile) }
  : name === 'Verify FACT_PACK Entity' ? (res._fact_pack === undefined
      ? (() => { throw new Error('no pack on this run'); })()
      : { choices: [{ message: { content: res._fact_pack } }] })
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
    '## Что это за бизнес',
    '## Покупать?',
    '## Инвестиционный тезис',
    '## Компания в цифрах, 3 года',
    '## Сопоставимые компании',
    '## Сколько компания стоит?',
    '## По какой цене мы бы купили?',
    '## Настроение рынка и главные новости',
    '## Катализаторы с датами',
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
    // v4.2.80 (D6): the cause still travels — in RUSSIAN. The ORCL brief pasted the engine string
    // "the FCF leg was not built (levered_fcf_per_share <= 0 (-8.128345916266301) ...)" into a
    // Russian sentence. The raw text is not lost: it stays in the machine report, where raw
    // belongs. Here the reader gets words, and the pin refuses the paste coming back.
    assert(/не определён|отрицателен/.test(md2), 'the cause must travel with the caveat, in Russian');
    assert(!/levered_fcf_per_share/.test(md2),
      'the engine string was pasted into the human document again');
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
    assert(!/\$3480|\$3,480/.test(t),
      'an absolute capex figure was stamped with a dollar sign whose unit is unverified');
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

  await check('v4.2.77 (g).4: the peer line prints N, both numbers and the shared basis',
    async () => {
      assert(/Медиана мультипликатора 5 сопоставимых компаний/.test(md),
        'N is missing — a median over five names would read as a median over the market');
      assert(/24\.60/.test(md) && /31\.20/.test(md), 'one of the two multiples is absent');
      assert(/edgar_tiingo_trailing_inhouse/.test(md), 'the shared basis is not stated');
      assert(!/сектор/i.test(md.slice(md.indexOf('Медиана мультипликатора'),
                                      md.indexOf('## Сколько компания стоит?'))),
        'the word "sector" came back — the number would borrow a breadth it does not have');
      assert(/дороже сопоставимых/.test(md), 'the direction does not follow 31.2 > 24.6');
    });

  await check('v4.2.77 (g).4: mismatched bases REFUSE the comparison', async () => {
    // A trailing median against a forward multiple is the defect that produced a 143x cap.
    const bad = await renderMd({ peer_multiple: { median: 24.6, count: 5,
      basis: 'edgar_tiingo_trailing_inhouse', company: 31.2, company_basis: 'alpha_vantage',
      comparable: false, excluded_from_pe_cap: true } });
    assert(/не сведены к одному базису/.test(bad), 'two bases were compared anyway');
    assert(!/против 31\.20/.test(bad), 'the refused comparison still printed its numbers');
    assert(/отказ от сравнения, а не утверждение/.test(bad),
      'the refusal must not read as a finding about valuation');
  });

  await check('v4.2.77 (g).4: an unknown N cannot be printed as a comparison', async () => {
    const noN = await renderMd({ peer_multiple: { median: 24.6, count: null,
      basis: 'edgar_tiingo_trailing_inhouse', company: 31.2,
      company_basis: 'alpha_vantage_trailing_reported', comparable: false,
      excluded_from_pe_cap: true } });
    assert(/число компаний в ней неизвестно/.test(noN), 'a median over an unknown N was compared');
  });

  await check('v4.2.79 (g).3: numbered sections scope the scan; the date test does the rest',
    async () => {
      const t = md.slice(md.indexOf('## Катализаторы с датами'),
                         md.indexOf('## Что у компании хорошо'));
      assert(/2026-06-18/.test(t), 'a dated news event was dropped');
      assert(/Q2 2026/.test(t), 'section 12 (the reported quarter) never reached the section');
      assert(!/described demand as strong/.test(t),
        'an UNDATED claim was published as a catalyst — the reader cannot calendar it');
      assert(!/\[UNVERIFIED\]|TERMINAL-ONLY/.test(t), 'a refusal marker was printed as an event');
      assert(!/rival tier/.test(t),
        'section 6 leaked in although the pack numbered its sections');
      assert(/НА ЯЗЫКЕ ИСТОЧНИКА/.test(t),
        'the source-language disclosure is missing: English lines in a Russian brief read as a bug');
    });

  await check('v4.2.79 (g).3: OLD dated events are not catalysts', async () => {
    // The Cerner announcement (December 20, 2021) and the OFCCP settlement (July 19, 2021) carry
    // dates and are not catalysts. The six-month window is the contract's own and drops them
    // without anyone having to name them.
    const stale = await renderMd({ _fact_pack: [
      '## SECTION 5: News catalysts',
      '* Oracle announced a definitive agreement to acquire Cerner on December 20, 2021 for $95.00.',
      '* 2026-07-02 — a multi-year cloud agreement was signed with a named counterparty.',
    ].join('\n') });
    const t = stale.slice(stale.indexOf('## Катализаторы'), stale.indexOf('## Что у компании'));
    assert(/2026-07-02/.test(t), 'a recent event was dropped by the window');
    assert(!/Cerner/.test(t), 'a 2021 announcement was published as a current catalyst');
  });

  await check('v4.2.79 (g).3: the REAL ORCL pack yields the events the run reported as absent',
    async () => {
      // The pin that would have caught the defect. The first extractor keyed on numbered headings;
      // the model wrote `### Fiscal Q4 2026 — Results & Guidance`, and the brief announced that the
      // news layer had returned no dated events while two sat in the pack. The fixture is the raw
      // artifact of the 2026-08-04 ORCL run, not a fixture written to match the parser.
      const raw = fs.readFileSync(
        path.join(__dirname, 'fixtures', 'fact_pack_ORCL_20260804.md'), 'utf8');
      const out = await renderMd({ _fact_pack: raw });
      const t = out.slice(out.indexOf('## Катализаторы'), out.indexOf('## Что у компании'));
      assert(!/ни одна строка не прошла|не вернул/.test(t),
        'the real pack still reads as empty — the extractor learned nothing from the ORCL run');
      const bullets = (t.match(/^\* /gm) || []).length;
      assert(bullets >= 3, 'only ' + bullets + ' events extracted from the real pack');
      assert(/June 11, 2026|March 10, 2026|2026/.test(t), 'the dated quarter events are missing');
      assert(!/\*\*/.test(t), 'markdown bold markers leaked into the event text as content');
    });

  await check('v4.2.79 (g).3: FOUR absences, four different sentences', async () => {
    // The fourth was added after the ORCL run: a pack that arrived, had text, and yielded nothing
    // is a statement about OUR EXTRACTION. The old third state called that "the search found
    // nothing" — a claim about the company, and a false one.
    const noPack = await renderMd({ _fact_pack: undefined });
    const failedCall = await renderMd({ _fact_pack: '## SOURCE_CALL_FAILED: Stage 1 FP news\n\ndead' });
    const nothingPassed = await renderMd({ _fact_pack:
      '## SECTION 5: News catalysts\n\nOracle continued to invest in cloud infrastructure capacity.' });
    const emptySection = await renderMd({ _fact_pack:
      '## SECTION 5: News catalysts\n[NO FINDINGS: searched, nothing surfaced]' });
    assert(/до этой секции не доехал/.test(noPack), 'a missing pack does not name itself');
    assert(/источник был недоступен/.test(failedCall), 'a failed news call reads as an empty world');
    assert(/утверждение о НАШЕМ извлечении/.test(nothingPassed),
      'an extraction miss is still being reported as a fact about the company');
    assert(/вернул пустой раздел/.test(emptySection),
      'an honestly empty section must not read as an extraction failure');
    assert(!/источник был недоступен/.test(nothingPassed),
      'two different absences printed the same sentence');
  });

  await check('v4.2.77 (g).1: the business description comes FIRST and is labelled as judgment',
    async () => {
      assert(md.indexOf('## Что это за бизнес') < md.indexOf('## Покупать?'),
        'the description must precede the verdict — the reader meets the company first');
      assert(/зарабатывает на подписке/.test(md), 'the captured profile never reached the brief');
      assert(/Описание — суждение модели/.test(md),
        'the label is missing: a model description would stand beside arithmetic unmarked');
    });

  await check('v4.2.77 (g).1: a missing profile is a pipeline gap, not a fact about the company',
    async () => {
      const bare = await renderMd({ _business_profile: null });
      const t = bare.slice(bare.indexOf('## Что это за бизнес'), bare.indexOf('## Покупать?'));
      assert(/пропуск конвейера/.test(t), 'the absence reads as a statement about the company');
      assert(!/зарабатывает на подписке/.test(t), 'a stale profile survived the empty case');
    });

  await check('v4.2.79 (I): three fiscal years, each row carrying its fiscal-year END', async () => {
    const t = md.slice(md.indexOf('## Компания в цифрах'), md.indexOf('## Сопоставимые компании'));
    for (const e of ['2024-05-31', '2025-05-31', '2026-05-31']) {
      assert(t.indexOf(e) !== -1, 'fiscal year ' + e + ' is missing — "2026" alone is ambiguous');
    }
    assert(/НЕ исторический мультипликатор/.test(t),
      'the P/E column is unlabelled: today\'s price against a 2024 EPS is not a 2024 multiple');
    assert(/—/.test(t), 'a missing FCF printed as something other than a dash');
    assert(!/\| 0\.00 \|/.test(t), 'an absent value was printed as zero');
  });

  await check('v4.2.79 (II): the comparables are NAMED, with size beside the multiple', async () => {
    const t = md.slice(md.indexOf('## Сопоставимые компании'), md.indexOf('## Сколько компания стоит?'));
    for (const p of ['MSFT', 'SAP', 'CRM']) {
      assert(t.indexOf(p) !== -1, 'peer ' + p + ' is not named — the median cannot be argued with');
    }
    assert(/34\.20/.test(t) && /23\.84/.test(t), 'the per-peer multiples are missing');
    assert(/задан заранее, не подобран под результат/.test(t),
      'the peer set must state that it was not chosen to fit the answer');
  });

  await check('v4.2.79: both new sections state absence rather than vanishing', async () => {
    const bare = await renderMd({ three_year_table: { rows: [] },
                                  peer_multiple: { median: null, count: null, comparable: false } });
    assert(/Ряды отчётности за три года до этой секции не доехали/.test(bare),
      'the three-year table disappeared silently instead of naming the gap');
    assert(/Состав сопоставимых компаний до этой секции не доехал/.test(bare),
      'the peer table disappeared silently instead of naming the gap');
    assert(/пропуск конвейера, а не отсутствие отчётности/.test(bare),
      'the absence reads as a statement about the company');
  });

  // ---- v4.2.80: nine defects, every pin anchored to the REAL 2026-08-05 artifacts -------------
  const ZAP = fs.readFileSync(
    path.join(__dirname, 'fixtures', 'ORCL_20260805_zapiska.md'), 'utf8');
  const RES805 = JSON.parse(fs.readFileSync(
    path.join(__dirname, 'fixtures', 'ORCL_20260805_RESULT.json'), 'utf8'))[0];

  await check('D1: the dollar sign is escaped, so a money pair cannot become a formula', async () => {
    assert(/\$[0-9]/.test(ZAP), 'control: the shipped brief did carry bare dollar signs');
    const bare = md.split('\n').filter(l => /(^|[^\\])\$/.test(l));
    assert(bare.length === 0, 'unescaped $ survived on ' + bare.length + ' line(s), e.g. '
      + JSON.stringify((bare[0] || '').slice(0, 70)));
    assert(/\\\$/.test(md), 'nothing was escaped at all — the filter did not run');
  });

  await check('D2: filing values are printed on a human scale, sign outside the currency',
    async () => {
      assert(/\$52961000000\.00/.test(ZAP), 'control: the shipped brief printed raw filing values');
      // Scoped to MONEY: a CIK is nine digits and is not a filing value.
      const raw9 = md.replace(/\\/g, '').match(/\$-?\d{9,}/g) || [];
      assert(raw9.length === 0, 'a raw filing value is still printed: ' + JSON.stringify(raw9[0]));
      const t = md.slice(md.indexOf('## Компания в цифрах'), md.indexOf('## Сопоставимые'));
      assert(/млрд/.test(t), 'the three-year table is not on a human scale');
      assert(!/\$-/.test(t), 'a minus sign was swallowed by the currency mark');
    });

  await check('D3: peer rows reach RESULT with size, not only a multiple', async () => {
    const shipped = RES805.peer_multiple.rows;
    assert(shipped.every(r => r.market_cap === null),
      'control: the shipped run had market_cap null on every peer');
    // The projection in Growth Enrich named its fields one by one and dropped everything else.
    const ge = NODES.find(n => n.name === 'Growth Enrich').parameters.jsCode;
    const proj = ge.slice(ge.indexOf('peer_pe_inhouse.rows.filter'), ge.indexOf('peer_pe_inhouse.rows.filter') + 400);
    assert(/Object\.assign\(\{\}, r,/.test(proj),
      'the peer projection still enumerates fields, so the next field added upstream dies here too');
  });

  await check('D4: provenance notes are not events', async () => {
    assert(/Source tier: Tier 3/.test(ZAP), 'control: the shipped brief published provenance lines');
    const out = await renderMd({ _fact_pack: [
      '## SECTION 5: News catalysts',
      '- Source tier: Tier 3 [AGGREGATOR]/commentary (Tikr blog), publication date: June 17, 2026.',
      '- This is a backlog figure attributed to management, dated June 17, 2026.',
      '- 2026-07-02 — Oracle signed a multi-year cloud agreement with a named counterparty.',
    ].join('\n') });
    const t = out.slice(out.indexOf('## Катализаторы'), out.indexOf('## Что у компании'));
    assert(!/Source tier/.test(t), 'a provenance note was published as an event');
    assert(!/This is a backlog figure/.test(t), 'commentary about an event was published as one');
    assert(/multi-year cloud agreement/.test(t), 'the real event was dropped with the metadata');
  });

  await check('D5: one sign per number, and a side/sign conflict is named', async () => {
    assert(/\+\$-7\.03/.test(ZAP), 'control: the shipped brief printed two signs');
    const out = await renderMd({ bull_bear: { rows: [
      { side: 'BULL', label: 'Cloud acceleration', probability: 0.55, delta_iv_pct: -5.0 },
      { side: 'BULL', label: 'Backlog explosion', probability: 0.6, delta_iv_pct: 90.0 },
      { side: 'BEAR', label: 'Capex collapse', probability: 0.6, delta_iv_pct: -13.0 }] } });
    assert(!/\+\\?\$-|\+\u2212/.test(out), 'a value still carries two signs');
    // The D1 escape runs before this, so the rendered form is MINUS + \$ — the pin must read the
    // document as it actually ships, not as it looked before the filter existed.
    assert(/\u2212\\?\$\d/.test(out), 'the negative bull contribution lost its own sign');
    assert(/записан как благоприятный, но/.test(out), 'the side/sign conflict was not named');
    assert(/Cloud acceleration/.test(out.slice(out.indexOf('Внимание'))),
      'the conflicting scenario is not identified by name');
  });

  await check('D6: the flag reason is Russian; the engine string stays in the machine report',
    async () => {
      assert(/the FCF leg was not built/.test(ZAP), 'control: the shipped brief pasted English');
      const out = await renderMd({ dual_basis: null, flags: [
        'SINGLE_LEG_RUN: the FCF leg was not built (levered_fcf_per_share <= 0 '
        + '(-8.128345916266301) — no positive FCF base to grow).'] });
      assert(/денежный поток на акцию отрицателен/.test(out), 'the reason was not translated');
      assert(!/levered_fcf_per_share|no positive FCF base/.test(out),
        'the engine string was pasted into the human document');
    });

  await check('D6 control: an unknown flag is NAMED as unknown, never pasted', async () => {
    const out = await renderMd({ dual_basis: null,
      flags: ['SINGLE_LEG_RUN: some_future_reason_code triggered.'] });
    assert(/словарь этого выпуска её не покрывает/.test(out),
      'an unrecognised flag must be declared a gap in the dictionary, not shown raw');
  });

  await check('D7: the evidence column declares its language', async () => {
    assert(/НА ЯЗЫКЕ МАШИННОГО АНАЛИЗА/.test(md),
      'English evidence in a Russian table reads as a defect unless the refusal is stated');
    assert(md.indexOf('НА ЯЗЫКЕ МАШИННОГО АНАЛИЗА') < md.indexOf('| сторона бизнеса |'),
      'the notice must stand ABOVE the table it explains');
  });

  await check('D8: Russian counters agree with their numbers', async () => {
    assert(/собрано 1 разделов/.test(ZAP), 'control: the shipped brief printed "1 разделов"');
    const one = await renderMd({ fp_vectors: { total: 5, unverified: 4, data_questionable: true } });
    const two = await renderMd({ fp_vectors: { total: 5, unverified: 3, data_questionable: true } });
    const five = await renderMd({ fp_vectors: { total: 5, unverified: 0, data_questionable: false } });
    // NB: JS \b is ASCII-only, so it never matches after a Cyrillic letter — the boundary is
    // written explicitly instead. The first draft of this pin failed on correct output.
    assert(/собран 1 раздел[ ,.]/.test(one), 'singular is wrong: '
      + (one.match(/собран\S* \d+ \S+/) || [])[0]);
    assert(/собрано 2 раздела[ ,.]/.test(two), 'the 2-4 form is wrong');
    assert(/собрано 5 разделов[ ,.]/.test(five), 'the plural form is wrong');
  });

  await check('D9: one multiplier format, from one helper', async () => {
    const forms = (md.match(/\d+\.\d+[x\u00d7]|\d+\.\d+ ?раза?/g) || []);
    const bad = forms.filter(f => !/\u00d7$/.test(f));
    assert(bad.length === 0, 'more than one multiplier format in one document: '
      + JSON.stringify(bad.slice(0, 4)));
  });

  // ---- v4.2.81: defects found in the SECOND ORCL run (2026-08-05, _v2 artifacts) --------------
  const ZAP2 = fs.readFileSync(
    path.join(__dirname, 'fixtures', 'ORCL_20260805_v2.md'), 'utf8');

  await check('v4.2.81: the flag reason publishes NO scraped number', async () => {
    assert(/отрицателен \(0\.00\)/.test(ZAP2),
      'control: the shipped brief said "negative (0.00)" — zero is not negative');
    const out = await renderMd({ dual_basis: null, flags: [
      'SINGLE_LEG_RUN: the FCF leg was not built (levered_fcf_per_share <= 0 '
      + '(-8.128345916266301) — no positive FCF base to grow).'] });
    const sent = out.slice(out.indexOf('по одному основанию'), out.indexOf('по одному основанию') + 500);
    assert(/отрицателен/.test(sent), 'the reason lost its meaning');
    assert(!/\d+\.\d\d\)/.test(sent),
      'a number scraped out of prose is being published again: ' + JSON.stringify(sent.slice(0, 200)));
    assert(/машинном отчёте/.test(sent), 'the reader is not told where the exact figure lives');
  });

  await check('v4.2.81: trillions read as trillions', async () => {
    assert(/\$3634\.46 млрд/.test(ZAP2), 'control: the shipped brief printed 3634 млрд');
    const out = await renderMd({ peer_multiple: { median: 24.6, count: 1, comparable: true,
      basis: 'b', company: 30, company_basis: 'c',
      rows: [{ ticker: 'MSFT', market_cap: 3.63446e12, revenue_ltm: 3.3e11, pe_trailing: 27.17 }] } });
    assert(/трлн/.test(out), 'a four-digit "млрд" defeats the point of a human scale');
    assert(!/\d{4}\.\d\d млрд/.test(out), 'four digits before the decimal are back');
  });

  await check('v4.2.81: stale dates are a diagnosis of the SOURCE, not of our extraction',
    async () => {
      assert(/утверждение о НАШЕМ извлечении/.test(ZAP2),
        'control: the shipped brief blamed our extraction for a stale source');
      const stale = await renderMd({ _fact_pack: [
        '## SECTION 5: News catalysts',
        '- June 10, 2025 – Fiscal 2025 results and AI infrastructure demand for the cloud unit.',
        '- June 10, 2025 – Acceleration in cloud and AI services across the OCI customer base.',
      ].join('\n') });
      const t = stale.slice(stale.indexOf('## Катализаторы'), stale.indexOf('## Что у компании'));
      assert(/ВСЕ они старше шести месяцев/.test(t), 'the stale-source state did not fire');
      assert(/2 строки/.test(t), 'the count of stale lines is wrong or ungrammatical');
      assert(!/утверждение о НАШЕМ извлечении/.test(t),
        'a working extraction is still being blamed for what the search returned');
    });

  await check('v4.2.81: the STREET section is covered by the marker rule', async () => {
    const pg = NODES.find(n => n.name === 'Prompts Growth').parameters.jsCode;
    assert(/## SECTION STREET/.test(pg),
      'STREET has no number, so the numbered-marker rule never reached it — and it vanished');
  });

  // ---- v4.2.82 -------------------------------------------------------------------------------
  await check('v4.2.82: the balance-sheet refusal is VISIBLE in the human document', async () => {
    // ORCL 2026-08-05: "долг к капиталу 0.00" beside 4/4 told the reader a ~$100B-debt company
    // has none. The refusal is computed upstream; if the brief does not show it, the block just
    // reports out of a smaller denominator and looks fine.
    const out = await renderMd({ gps: { blocks: [ { name: 'D (balance sheet)', points: 4, max: 6,
      evidence: { de: 0, de_refused: true, dilution_cagr: -0.00725, sbc_rev: 0.0714,
        de_refusal_reason: 'total_debt diverges 100% between sources (edgar 0 vs gather 129541000000)' } } ] } });
    assert(/балл по ней НЕ выставлен/.test(out), 'the refusal is invisible to the reader');
    assert(!/долг к капиталу 0\.00/.test(out), 'the zero is still printed as a leverage reading');
    assert(/источники расходятся/.test(out), 'the reason for the refusal is not given');
  });

  await check('v4.2.82: the street section reports the distance to consensus', async () => {
    assert(/## Что думает улица/.test(md), 'the street section is missing');
    const t = md.slice(md.indexOf('## Что думает улица'), md.indexOf('## Компания в цифрах'));
    assert(/аналитик/.test(t), 'the analyst count is missing');
    assert(/наша оценка против цели улицы/.test(t), 'the distance to consensus is not stated');
  });

  await check('v4.2.82: a big gap to the street is named, not left for the reader to compute',
    async () => {
      const out = await renderMd({ street_view: { consensus_target_mean: 248.15, analyst_count: 49,
        pwfv_vs_street_pct: -45.8,
        recommendation_breakdown: { strongBuy: 15, buy: 25, hold: 8, sell: 1, strongSell: 0, total: 49 } } });
      assert(/расходимся с улицей сильно/.test(out), 'a 45.8% gap passed without comment');
      assert(/49 аналитиков/.test(out), 'the analyst count is wrong or ungrammatical');
      assert(/82% за покупку/.test(out), 'the buy share is wrong: ' + (out.match(/\d+% за покупку/) || [])[0]);
    });

  await check('v4.2.82: scenario names are Russian, with a VISIBLE fallback', async () => {
    const out = await renderMd({ bull_bear: { rows: [
      { side: 'BULL', label: 'OCI hypergrowth extends corridor', label_ru: 'Ускорение облачного бизнеса',
        probability: 0.3, delta_iv_pct: 20 },
      { side: 'BEAR', label: 'Capex financing pressure', probability: 0.4, delta_iv_pct: -13 }] } });
    assert(/Ускорение облачного бизнеса/.test(out), 'the Russian scenario name was ignored');
    assert(/Capex financing pressure/.test(out),
      'a missing label_ru must fall back to the English string, not to silence');
  });

console.log('\n' + (failed ? 'FAILED' : 'OK') + ' — ' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
