---
author: CHATGPT
date: 2026-08-09
status: final external review before operator decision
answers: mailbox/ROUND3_2026-08-08_FEASIBILITY_AND_EXISTENCE.md
---

# ROUND 3 REVIEW — feasibility, prior art, build/buy/stop

## Короткий вердикт

**М4: выбираю (б) ГИБРИД.**

Не строить ещё один полный valuation stack с нуля. Не останавливаться и на полностью ручном режиме, потому что тогда теряется то, что у проекта действительно потенциально ценно: воспроизводимый `as-of` слой, fail-closed семантика данных, режимные сторожа, point-in-time универсум, пре-регистрация и проверка ранжирования на истории.

**Строить только уникальный слой Consilium; коммодити использовать как библиотеку или независимые референсы.**

При этом рекомендация условная:

> **сначала один разрушительный ручной пилот максимум за 4–6 часов оператора. Если даже один кейс нельзя довести до воспроизводимого, объяснимого результата в этом бюджете — перейти к варианту (в), ручной режим, и прекратить строительство автоматической системы.**

Главный довод: reverse-DCF / expectations investing уже давно существует как метод и уже реализован в открытом и коммерческом софте. У Consilium нет рациональной причины заново строить этот слой. Возможный edge проекта — не формула, а **контроль того, какие данные и какой режим бизнеса допускаются к этой формуле, плюс честная историческая проверка ранга**.

---

# ЧАСТЬ 1. ВЕРНО ЛИ ВЫ МЕНЯ УСЛЫШАЛИ

## Позиция: **в основном да, с тремя поправками**

Изложение в части 1 корректно передаёт мою позицию прошлого раунда:

- Nasdaq-100 — operational universe, но не единственный validation universe;
- reverse expectations лучше подходит как главный интерфейс, чем «точная fair value»;
- `actual_eps_cagr_5y` нельзя называть достижимым ростом;
- нужны revenue / earnings / EPS / share-count / margin decomposition;
- циклические и режимные переходы должны быть явными отказами/флагами;
- 12% можно оставить личным hurdle, но устойчивость ранга к ставке надо измерять;
- peers — validation/flags, не подстановка отсутствующих inputs;
- внеиндексные speculative names — отдельно и без модельных выводов;
- Test #2 должен быть полностью пре-регистрирован до просмотра Test #1;
- margin/regime layer должен появиться **до** confirmatory Test #2.

### Поправка 1 — `ROIIC потом, после пилота` нельзя превращать в постоянную лазейку

Для самого пилота допустимо временно показать и accounting ROE, и альтернативный return measure рядом. Но до confirmatory Test #2 правило должно быть определено жёстко:

- отрицательный/нулевой equity → ROE **NOT_APPLICABLE**, не cap 40%;
- materially buyback-distorted equity → либо экономический return measure (предпочтительно ROIIC/return on incremental capital), либо отказ от terminal-return формулы для этого имени;
- cap 40% допустим лишь после того, как denominator признан экономически осмысленным.

То есть пилот должен помочь выбрать реализацию, но **не может легализовать заведомо бессмысленный ROE для O'Reilly/AAPL-класса**.

### Поправка 2 — `rank stability` в первый live-год не является доказательством качества

В live-режиме первый год можно измерять стабильность ранга, coverage, отказы и дрейф assumptions. Но четыре квартала не доказывают predictive value. Evidence о качестве ранга должен идти из point-in-time historical test; live-year — monitoring.

### Поправка 3 — `rho >= 0.98` по сетке hurdle — диагностический pin, не доказательство правильности 12%

Высокая rank correlation при 10–14% докажет только, что **порядок устойчив к выбранной ставке**. Она не докажет, что 12% является экономически правильной ставкой. Для личного investment hurdle это нормально: ставка задаётся оператором, а тест проверяет, не превращает ли она ranking в случайный порядок.

---

# ЧАСТЬ 2. СОБСТВЕННЫЙ ПОИСК PRIOR ART

Поиск проведён независимо от списка в документе. Мой вывод сильнее сформулированного в части 2:

> **reverse expectations — точно не уникальная часть проекта; EDGAR extraction — тоже не уникальная. Уникальная комбинация может возникнуть только на уровне point-in-time воспроизводимости + режимной нормализации + fail-closed правил + cross-sectional validation.**

## 2.1. Метод как таковой: Expectations Investing — established prior art

Rappaport/Mauboussin прямо предлагают начинать с текущей цены, извлекать встроенные в неё ожидания и затем анализировать вероятные revisions. Их framework ведёт от sales, costs и investment к value drivers — то есть сама идея «разложить ожидания по growth/margin/reinvestment, а не угадать fair value» уже сформулирована до Consilium.

Источники:

- [Expectations Investing — official site](https://www.expectationsinvesting.com/)
- [Expectations Investing, revised 2021 — Columbia University Press](https://cup.columbia.edu/book/expectations-investing/9780231554848/)
- [Ten Rules / framework](https://www.expectationsinvesting.com/about-expectations-investing)

Важная для Consilium деталь: original framework не ограничивается одним `implied growth`. Он прямо связывает revisions с volume/pricing/sales mix, margins и investment. Это подтверждает моё возражение против единственного score `required EPS growth - trailing EPS CAGR`.

## 2.2. `Keenan-ux/implied-expectations`: полезный референс, но не production core

Проверил не только README, но и код.

Сильные стороны:

- MIT, PyPI 0.1.0 от 2 июля 2026;
- стандартный two-stage FCFF, не P/E shortcut;
- growth связан с reinvestment через `g / ROIC`;
- EV → debt/cash → equity;
- три инверсии: growth / duration / margin;
- terminal RONIC по умолчанию = discount rate, поэтому terminal growth value-neutral;
- closed-form/golden/round-trip тесты заявлены и структура кода действительно небольшая и прозрачная;
- loss-makers и банки явно не поддерживаются на уровне основной модели.

Но есть важное расхождение между философией README и ingestion-кодом.

В `edgar.py`:

- tax при непригодном факте → **21% default**;
- ROIC при невозможности измерить → **20% default**;
- измеренный ROIC clamp → **10–100%**;
- не найденный debt → **0**;
- не найденный cash → **0**.

Это ровно класс ошибок, который Consilium уже дорого выкорчёвывал: `unknown → plausible/zero`.

Кроме того, current extractor сочетает latest annual flows с latest instant balance-sheet facts. Для текущего quick read это допустимая конвенция; для воспроизводимой исторической `as-of` проверки — нет без отдельного temporal contract.

Источники:

- [Repository](https://github.com/Keenan-ux/implied-expectations)
- [PyPI](https://pypi.org/project/implied-expectations/)
- `src/implied_expectations/edgar.py`
- `src/implied_expectations/model.py`

### Вывод

**Не брать ingestion и defaults как production truth.**

Использовать solver как independent reference на **явно переданных Consilium inputs**. Это хороший differential oracle именно потому, что реализация независима и проще вашей.

## 2.3. BoothCheck: ближе всего к вашей целевой постановке, но это comparator, не фундамент

Публичные отчёты BoothCheck показывают несколько вещей, которые целевая M4 только собирается строить:

- company-specific cost of capital;
- mid-cycle operating margin;
- различие trailing vs normalized margin;
- reverse growth/duration;
- в некоторых отчётах сегментный/маршрутный анализ;
- явное предупреждение о циклическом peak/trough.

Например, публичный отчёт ICLR показывает trailing margin 6.6%, mid-cycle 13.3%, отдельно решает required margin и implied growth. Это гораздо ближе к нужной диагностике, чем плоский current margin.

Источник: [BoothCheck ICLR report](https://boothcheck.com/report/ICLR)

Но:

- код/полная методология не проверены;
- сервис может менять правила;
- это не point-in-time historical engine Consilium;
- внешний результат не должен становиться ground truth для вашей validation.

**Использование: second opinion / discrepancy generator.** Если BoothCheck и Consilium резко расходятся — это повод открыть assumptions, а не усреднить цифры.

## 2.4. New Constructs: коммерческий reverse-DCF уже делает ровно «что должна сделать компания, чтобы оправдать цену»

Публичные материалы New Constructs много лет выражают current price через необходимые NOPAT margin и revenue growth. Например, в материалах по Regeneron они сопоставляют implied NOPAT/growth с историческими уровнями и нормализуют margin относительно TTM/многолетних значений.

Источники:

- [Regeneron example / reverse DCF](https://www.newconstructs.com/using-roic-to-find-the-best-worst-stocks-in-the-sp-500/)
- [Krispy Kreme reverse DCF example](https://www.newconstructs.com/dork-rally-crashes/)

Это ещё одно подтверждение: **сам reverse solver — commodity.**

## 2.5. Damodaran: terminal return/reinvestment и нормализация тоже не надо изобретать заново

У Damodaran есть готовые spreadsheets/diagnostics для:

- implied ROC/ROE в terminal value;
- WACC;
- capitalization R&D;
- operating leases;
- stable-growth reinvestment;
- reconciliation FCFF/FCFE;
- разные модели для разных типов firms.

Источники:

- [Valuation spreadsheets](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/eqspread.htm)
- [Investment Valuation resources / implied ROC](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/Inv3ed.htm)

Особенно полезная мысль для M4: terminal growth должен проверяться через implied return on capital и reinvestment. Это хороший независимый sanity reference для вашей terminal-return логики.

## 2.6. EDGAR/XBRL: `edgartools` закрывает большую часть generic plumbing

`dgunning/edgartools` — зрелый MIT-проект с удобным доступом к 10-K/10-Q, XBRL, statements, filings by date/accession и segment data там, где XBRL позволяет.

Источники:

- [GitHub](https://github.com/dgunning/edgartools)
- [XBRL docs](https://edgartools.readthedocs.io/en/stable/xbrl/)

Я **не предлагаю удалить ваш `edgar_facts.py` и довериться библиотеке**. Ваши incident-driven rules по split/restatement/basis/conflicts — часть уникальной защиты. Но generic download/parsing/filing navigation разумно сравнить с edgartools и перестать поддерживать то, что библиотека уже делает лучше.

## 2.7. Point-in-time universes: есть готовые источники от бесплатных до профессиональных

### Open-source bootstrap

`jmccarrell/n100tickers` предоставляет date-centric Nasdaq-100 membership, заявляя coverage с 1 Jan 2015 до Aug 2026.

- [n100tickers](https://github.com/jmccarrell/n100tickers)

`unliftedq/index-constitution` содержит S&P 500 / Nasdaq-100 и API `constituents_at()`, но для US history источники во многом основаны на Wikipedia/публичных списках.

- [index-constitution](https://github.com/unliftedq/index-constitution)

Оба полезны для **bootstrap/pilot**, но я не считаю их достаточным единственным источником confirmatory validation.

### Более серьёзные источники

**Norgate Data** предоставляет historical index membership с delisted securities; для Nasdaq-100 заявляет историю с Oct 1993. Доступ платный (Platinum/Diamond), membership доступен point-in-time через plugins/API.

- [Norgate historical index constituents](https://norgatedata.com/data-content-tables.php)

**QuantConnect US ETF Constituents** хранит historical constituents/weights ETF, daily с 2015 и monthly до этого, и привязан к security master с splits/dividends/symbol changes. Это особенно интересно для practical benchmark `QQQ constituents`, хотя QQQ holdings и официальный NDX membership — не абсолютно одно понятие.

- [QuantConnect ETF Constituents](https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/us-etf-constituents)

### Вывод

Не строить historical membership с нуля до проверки этих источников. Для пилота open-source + official announcement spot-check достаточно. Для confirmatory Test #2 нужен frozen dataset + source-quality field; если open history не проходит выборочную сверку, **заплатить за Norgate/аналог дешевле, чем строить свой security master**.

## 2.8. Point-in-time fundamentals: Calcbench — важный пропущенный кандидат

Calcbench прямо предлагает point-in-time standardized fundamentals с filing timestamps и revisions, предназначенные для backtests без look-ahead. API платный/отдельно лицензируется.

- [Calcbench point-in-time fundamentals](https://www.calcbench.com/blog/post/153949139113/point-in-time-fundamental-data)
- [Calcbench API](https://www.calcbench.com/api)

Это не означает «купить и выбросить as-of stand». Но перед дальнейшим расширением своего исторического data layer стоит запросить цену. Если стоимость разумна, это может снять значительную часть инженерного риска Test #2.

## 2.9. Что я НЕ нашёл

Я не нашёл зрелого open-source продукта, который одновременно даёт:

1. reproducible point-in-time SEC snapshot;
2. normalized margin/regime logic;
3. reverse expectations;
4. fail-closed accounting semantics;
5. point-in-time universe;
6. cross-sectional ranking;
7. preregistered historical validation;
8. audit trail каждого refusal.

Именно эта **система контроля эксперимента**, а не valuation formula, остаётся разумным предметом собственного строительства.

---

# ЧАСТЬ 3. М1 — ПОСТАТЕЙНАЯ СВЕРКА С PRIOR ART

## Позиция: **с оговорками; `implied-expectations` закрывает solver, но не decision layer**

| Целевая функция M4 | implied-expectations | BoothCheck | Что оставлять Consilium |
|---|---|---|---|
| Reverse FCFF growth solve | **полностью** | да | не изобретать заново; дифф-тест |
| Solve duration | **полностью** | да | reference |
| Solve margin | **полностью** | есть аналоги | reference |
| Growth↔reinvestment via ROIC | **есть** | есть ROIC/WACC logic | собственная fail-closed семантика |
| Net debt → equity | **есть** | есть | собственный verified debt/cash |
| Sensitivity rates/horizons | **есть** | есть | стандартизировать вывод |
| XBRL provenance | частично, concept-level | непрозрачно снаружи | accession/context/unit/basis manifest |
| Unknown ≠ zero/default | **нет** | неизвестно | **обязательно своё** |
| Historical `as-of` | нет | не подтверждено | **своё/купленное PIT** |
| Restatements / temporal reconstruction | нет как исследовательский стенд | не подтверждено | **своё/Calcbench** |
| Quarterly regime detector | нет | частично отражён в нормализации | **свой простой guard** |
| Mid-cycle normalization | нет | **да, публично видно** | своё правило + BoothCheck comparator |
| Buyback/share decomposition | нет как динамический driver | частично | **своё** |
| Point-in-time universe | нет | нет | **Norgate/QC/open dataset + своё freeze** |
| Ranking / Rank IC / validation | нет | не это назначение | **своё** |
| Prereg / refusal discipline | нет | неизвестно | **своё** |

### Насколько flat margin фатальна для NDX ranking?

**Как референс — не фатальна. Как production ranking без сторожей — фатальна.**

Причина: cross-sectional order начнёт измерять не только дешевизну, но и **где компания случайно находится в цикле маржи**.

- Micron у peak memory pricing получит невероятно привлекательную стартовую economics.
- Meta 2025 имеет consolidated margin 41%, но FoA 52% и Reality Labs loss $19.2B; одна flat margin смешивает mature cash machine и long-duration option.
- Netflix 2023→2025 подняла operating margin с 20.6% до 29.5%; результат reverse solve сильно зависит от того, считать ли 29.5% нормой или стадией расширения.
- Adobe 2024 содержит $1B Figma termination fee в cash-flow/expense history; naive trend путает one-off с economics.

Flat margin допустима только если output называется **“what current economics must sustain”**, а не “relative cheapness”. Для ранжирования надо хотя бы знать, является ли current margin нормальной, peak/trough или regime-changing.

---

# М2. ВЗЯТЬ ЯДРО ИЛИ РЕФЕРЕНС?

## Позиция: **референс, не production core**

Я бы сделал так:

1. Pin exact PyPI wheel/version **и hash** `implied-expectations==0.1.0` в validation environment.
2. Не использовать его EDGAR extractor в money path.
3. Передавать solver-у уже проверенные Consilium inputs: revenue, margin, tax, debt, cash, shares, ROIC, discount, terminal assumptions.
4. Для diff-test выровнять assumptions **точно**. Сравнение разных моделей без выравнивания inputs бесполезно.
5. Хранить upstream result + upstream version/hash в run manifest.
6. При расхождении выше заранее объявленного tolerance → `DIFF_REVIEW_REQUIRED`, а не averaging.

### Почему не делать fork основным ядром

Если вы начнёте переписывать его defaults, data layer, terminal rule и regime logic, через месяц получите второй Consilium под чужим именем и потеряете независимость проверки.

### Нужно ли vendoring?

Для воспроизводимости достаточно:

- pinned version + cryptographic hash;
- локально кешированный wheel/source archive;
- upstream commit SHA;
- license notice.

Можно vendor exact **неизменённый** release artifact как страховку supply-chain, но не вести собственную функциональную ветку.

### Чем страховать single-author risk

Не доверять библиотеке как истине. Должно быть три уровня:

- Consilium implementation;
- независимый `implied-expectations` reference;
- несколько hand-worked / spreadsheet goldens (можно на логике Damodaran/Expectations Investing).

BoothCheck — четвёртый внешний comparator, но не тест oracle, потому что его код не открыт.

---

# М3. РУЧНОЙ РЕЖИМ

## Позиция: **обязателен как pilot и fallback; не как конечный способ покрывать 100 имён**

## Чек-лист одной компании

1. **Identity/as-of:** CIK, filing cutoff, current/historical price timestamp.
2. **Reconcile inputs:** revenue, operating income, tax, cash, debt/leases, diluted shares.
3. **Growth decomposition:** revenue CAGR, operating-income/NOPAT CAGR, EPS CAGR, share-count CAGR.
4. **Margin path:** минимум 5 FY; желательно L4Q и последние 4–8 quarters.
5. **Normalize explicit one-offs:** только named adjustment с filing evidence; raw value всегда хранить рядом.
6. **Capital intensity:** capex, working capital where material, SBC/share count, acquisitions.
7. **Regime guards:** cycle peak/trough, recent margin break, acquisition/divestiture, restructuring.
8. **Reverse solve:** growth / duration / margin under 10/12/14% (или заранее замороженная сетка).
9. **Independent solve:** `implied-expectations` на тех же inputs.
10. **BoothCheck comparator:** если есть покрытие — записать assumptions и divergence.
11. **Failure handling:** необъяснимое расхождение → никакого score.
12. **Output:** implied assumptions + normalized scenario + implied return/range + confidence; не “BUY” из одного solve.

## Минимальные скрипты

Не нужен новый n8n.

- `snapshot.py` — ваш as-of/SEC adapter или edgartools + Consilium validation;
- `decompose.py` — revenue/OP/EPS/shares/margin;
- `regime.py` — quarterly/annual guards;
- `reverse.py` — wrapper Consilium solver + pinned `implied-expectations`;
- `diff.py` — assumption-normalized comparison;
- `pilot_report.py` — один markdown/json artifact.

## Время

После настройки:

- обычный mature name: **~60–90 минут оператора**;
- компания с one-off / segment issue / corporate action: **2–3 часа**;
- cyclical/regime case: **до 4 часов**.

Если типичный NDX name требует >2 часов ручной работы ежеквартально, ручной режим не масштабируется на 100 имён. Если **разрушительный пилот** не помещается в 4–6 часов, автоматизация тоже пока не имеет спецификации — это stop signal.

## Что ручной прогон показал бы сегодня для META / NFLX / ADBE

Это **не полный solve** — я не подменяю запрошенный пилот несколькими веб-фактами. Ниже именно диагностические выводы, которые должны появиться ДО цифры ranking.

### META — `NORMALIZATION_REQUIRED`

2025:

- revenue ~$201B;
- consolidated operating margin 41%;
- FoA margin 52%;
- Reality Labs operating loss ~$19.2B;
- effective tax 30%, но компания прямо указывает, что без valuation-allowance effect он был бы примерно 13%, а 2026 guidance — 13–16%;
- capex including finance-lease principal ~$72.2B; guidance на 2026 резко выше.

Следовательно naive reverse DCF с 41% flat margin и 30% tax одновременно **смешивает segment economics и one-off tax regime**. Честный ручной output сначала должен разложить FoA/RL, normal tax и AI capital intensity.

Источники: Meta 2025 10-K, SEC.

### NFLX — `CURRENT BUSINESS STRONG, EVENT RECENCY REQUIRED`

2025:

- revenue ~$45.2B, +16%;
- operating margin 29.5% против 26.7% в 2024 и 20.6% в 2023;
- net income ~$11.0B.

Это хороший пример, где flat current margin может оказаться **не peak, а ещё продолжающейся margin expansion**.

Ещё важнее: January 2026 10-K содержит pending WBD transaction, но 26 February 2026 Netflix официально отказалась повышать предложение после superior Paramount bid. То есть **один annual snapshot сегодня уже stale по важному corporate event**. Ручной режим обязан сначала обработать event layer и оценивать standalone Netflix, а не автоматически тащить January acquisition assumption.

Источники: Netflix 2025 10-K; Netflix “Declines to Raise Offer for Warner Bros.”, 26 Feb 2026.

### ADBE — **из трёх выглядит наиболее интересным кандидатом на полный reverse-expectations разбор**, но не объявляю его дешёвым без solve

2025:

- revenue ~$23.77B, +11%;
- subscription = 96% revenue;
- diluted EPS $16.70;
- operating cash flow ~$10.03B;
- 2024 cash flow был ухудшен $1B Figma termination fee.

На закрытии 7 Aug 2026 ~$265.21 это около **15.9x FY2025 diluted EPS** — стартовая цена уже требует заметно меньше героических assumptions, чем типичный high-growth multiple. Но year-over-year earnings/cash-flow comparisons надо очистить от Figma termination fee.

Моя предварительная очередь для ручного solve из этих трёх: **ADBE first, NFLX second, META third** — не потому что это ranking результата, а потому что ADBE сейчас имеет наиболее диагностичное сочетание умеренного multiple + recurring revenue + явного one-off, который можно честно нормализовать.

---

# М4. ПРЯМАЯ РЕКОМЕНДАЦИЯ

## **(б) ГИБРИД — строить уникальный слой поверх готовых коммодити**

### СВОЁ

1. immutable `as-of` snapshot/manifest;
2. fail-closed semantic adapter (`unknown != 0/default`);
3. annual + minimal quarterly growth/margin/share decomposition;
4. regime/cycle/corporate-action guards;
5. point-in-time universe + eligibility/refusal contract;
6. ranking + Rank IC/top-bottom/benchmark evaluation;
7. preregistration and method versioning;
8. audit trail каждого input/refusal;
9. operator-facing report.

### ВЗЯТЬ / ИСПОЛЬЗОВАТЬ

- **edgartools**: generic filing/XBRL plumbing там, где не нужен специальный incident rule;
- **implied-expectations**: pinned independent solver/reference;
- **BoothCheck**: external comparator для margin/cycle divergences;
- **Damodaran spreadsheets**: sanity goldens по reinvestment/terminal ROC;
- **Norgate / QuantConnect / vetted open datasets**: point-in-time membership вместо своего security-master проекта;
- **Calcbench**: запросить цену на PIT fundamentals до расширения собственного historical data layer.

### ПРЕКРАТИТЬ СТРОИТЬ

- ещё один generic reverse-DCF solver “потому что свой”;
- собственный generic EDGAR client, если поведение не относится к Consilium-specific invariant;
- multi-agent valuation consensus;
- generic news/qualitative score;
- свободные LLM monetary assumptions.

### Stop gate

Гибрид имеет смысл **только если pilot P1/P2 ниже проходит**.

Если нет — вариант (в): ручной workflow на готовых инструментах. Не превращать неясную методику в большую автоматизацию.

---

# М5. ЧТО ЕЩЁ ПРОПУЩЕНО В PRIOR ART

1. **Expectations Investing official framework** — важнее любого GitHub repo; это методологический reference.
2. **Damodaran valuation spreadsheets** — terminal ROC/reinvestment/leasing/R&D sanity references.
3. **New Constructs reverse DCF** — доказательство commercial prior art и примеры margin+growth expectations.
4. **Norgate Data** — профессиональный PIT constituent source с delisted coverage.
5. **QuantConnect ETF Constituents** — готовая daily historical ETF membership/weights инфраструктура.
6. **Calcbench PIT fundamentals** — потенциально самое сильное “buy instead of build” для Test #2 data layer.
7. **edgartools quarterly/segment XBRL** — прежде чем строить квартальную трубу вручную.

Из этого списка первым я бы **проверил цену Calcbench и Norgate**, потому что именно data reconstruction, а не формула, с наибольшей вероятностью съест месяцы и породит тихие ошибки.

---

# ЧАСТЬ 4. Ф1 — ТРИ НАИБОЛЕЕ ВЕРОЯТНЫЕ ТОЧКИ ОТКАЗА

## 1. Data semantics / temporal consistency — **самая вероятная**

Не HTTP, не SEC rate limit, а ситуация, когда каждое число “настоящее”, но относится к разному периоду/basis.

Типовой будущий дефект:

> annual revenue из одного filing + latest debt из более позднего quarter + share basis после split + historical price до split → красивый reverse result.

LLM-аудитор склонен принять provenance labels как доказательство корректности, как уже происходило с внутренними документами проекта.

**Acceptance:** каждый money-path number несёт accession/filed_at/period/unit/share_basis/transformation.

## 2. Regime normalization превратится в набор исключений, подогнанных под известные примеры

После Micron появится rule A, после Zoom rule B, после NVDA rule C, после Intel rule D. Через десять имён получится hidden discretionary model.

**Acceptance:** сторожа должны опираться на небольшое число общих измеримых признаков и быть preregistered до массового test:

- recent-vs-midcycle margin delta;
- margin volatility;
- revenue/earnings divergence;
- share-count contribution;
- named corporate action/one-off.

Не `if ticker == MU`.

## 3. Validation/PIT universe silently gets look-ahead

Самый опасный класс — неправильный состав индекса, ticker successor, delisted price или filing, который был известен позже test date.

**Acceptance:** membership source/version frozen; data availability based on filed timestamp, not fiscal period; delisted names retained; exclusions counted and reported.

---

# Ф2. МИНИМАЛЬНАЯ DECISION-GRADE MARGIN MODEL

## Позиция: **существенно меньше “полной модели”, но больше одного CAGR**

Обязательно:

1. Revenue 3y/5y trend.
2. Operating margin минимум по 5 FY.
3. **Последние 4 quarters / LTM operating margin** — без этого regime detector запаздывает.
4. Recent margin vs 5y median + previous FY.
5. Отдельное хранение raw и normalized margin.
6. Named one-off adjustments только с filing evidence.
7. Revenue growth → NOPAT/operating profit через margin, а не revenue growth → EPS напрямую.
8. Growth funding: reinvestment + ROIC/ROIIC sanity.
9. Share-count/SBC/buybacks отдельно от operating growth.
10. Cycle/regime status, который способен **запретить comparable ranking**.

Можно отложить:

- полную segment valuation;
- S-curves;
- product-level unit economics;
- stochastic state-transition model;
- peer-based input calibration;
- квартальный forecast на 10 лет;
- ML.

### Меняет ли BoothCheck границу?

**Нет.** Оно уменьшает стоимость проверки вашей нормализации, но не снимает необходимость иметь свою объяснимую rule, если ranking зависит от неё.

BoothCheck — comparator. Если ваша “decision-grade” модель просто вызывает BoothCheck и принимает его mid-cycle margin, у вас появляется скрытый внешний model dependency без reproducibility.

---

# Ф3. КАКИЕ ДАННЫЕ, ВЕРОЯТНО, НЕ БУДУТ БЕСПЛАТНЫМИ/ДЁШЕВЫМИ

## Point-in-time index membership

**Качественный источник — вероятно платный**, хотя бесплатные bootstrap datasets есть.

Honest degraded mode:

- open-source PIT list;
- freeze commit/version;
- spot-check все membership changes около test dates по official Nasdaq announcements;
- `source_quality=RESEARCH`, не `GOLD`.

Для confirmatory test лучше Norgate/аналог, если цена разумна.

## Point-in-time standardized fundamentals / revisions

SEC сырьё бесплатное, но **нормализация стоит инженерного времени**. Calcbench продаёт ровно это как продукт.

Honest degraded mode: собственный as-of stand, но ограничить universe/forms и сохранять raw filing manifest.

## Quarterly margins

Сами данные для US issuers в основном **бесплатны в 10-Q/XBRL**. Проблема не цена, а semantics: YTD vs quarter, tag changes, amended filings, fiscal calendars.

Honest degraded mode: поддержать только revenue + operating income квартально; всё остальное оставить annual.

## Segment margins

Часто доступны в filings, но custom tags и изменения segment definitions делают cross-company automation дорогой.

Honest degraded mode: whole-company model + `SEGMENT_DIVERGENCE` flag; segment data показывать человеку, но не делать обязательным ranking input.

## Historical prices/delisted securities

На масштабе и для delisted names бесплатность быстро становится хрупкой.

Honest degraded mode: платный price vendor для validation; не смешивать несколько бесплатных feeds без reconciliation.

---

# Ф4. ГОДОВОЙ PIPELINE ПРОТИВ КВАРТАЛЬНЫХ REGIME GUARDS

## Позиция: **annual-only недостаточен для decision-grade ranking**

Он запаздывает до года именно в моментах, где сторож нужнее всего.

- NVDA AI inflection произошла внутри года и быстро изменила margin/revenue regime.
- Zoom после pandemic peak также ломала траекторию быстрее, чем пятилетний CAGR успевал очиститься.
- commodity/memory cycle способен развернуться за несколько кварталов.

### Honest annual approximation

Если квартальная труба ещё не готова:

- last FY margin vs 3/5y median;
- last FY vs prior FY delta;
- revenue CAGR vs earnings CAGR;
- share-count contribution;
- long-run margin min/median/max.

Но output должен иметь:

`REGIME_GUARD_WEAK_ANNUAL_ONLY`

и cyclical/high-volatility names не должны получать high-confidence comparable rank.

### Что я рекомендую вместо полной quarterly architecture

Сделать **очень узкий quarterly slice**:

- revenue;
- operating income;
- period start/end;
- filing timestamp;
- derived quarter from YTD where necessary;
- last 4 quarters.

Это маленький слой, особенно если проверить edgartools, и он даёт большую часть ценности regime detector.

---

# ЧАСТЬ 5. П1 — САМЫЙ ДИАГНОСТИЧНЫЙ ПИЛОТ

## **Micron Technology, сразу после публикации FY2018 10-K**

10-K был подан **15 октября 2018**. Пилотную price date я предлагаю зафиксировать как **первый торговый день после filing** (точную торговую дату/close стенд должен получить до расчёта и записать в prereg artifact).

Почему Micron лучше остальных кандидатов для первого разрушительного теста:

FY2018 — почти идеальный trap для naive implied-expectations model:

- revenue $30.39B против $20.32B годом ранее;
- gross margin **58.9%** против 41.5%;
- operating margin **49.3%** против 28.9%;
- net income ~$14.14B против ~$5.09B.

То есть trailing economics выглядят фантастически. Уже следующий цикл показал, насколько опасно принимать peak margin за норму.

Этот один кейс одновременно нагружает:

1. as-of filing discipline;
2. margin normalization;
3. cycle detector;
4. revenue/earnings decomposition;
5. reverse-growth solve;
6. ROIC/reinvestment;
7. sensitivity to normalized margin;
8. reference diff с `implied-expectations`;
9. способность системы **не назвать cyclical peak дешёвым только потому, что trailing earnings велики**.

O'Reilly я бы сделал **вторым** пилотом: он лучше тестирует buybacks/negative equity/ROE. Но Micron лучше проверяет центральную гипотезу M4 — может ли regime layer защитить reverse ranking.

Источники:

- Micron FY2018 10-K filing date: 15 Oct 2018;
- Micron FY2018 results / SEC filing: revenue $30.391B, gross margin 58.9%, operating income $14.994B, net income $14.135B.

---

# П2. ПРОТОКОЛ ПИЛОТА

## Позиция: **да, помещается в 4–6 часов, если не писать production code во время пилота**

## Зафиксировать ДО начала

1. Company: MU.
2. Filing cutoff: FY2018 10-K filed 2018-10-15.
3. Price date rule: first trading day after filing; one source.
4. Raw filings/accessions allowed.
5. Model horizon.
6. Discount grid (например 10/12/14%; primary 12%).
7. Terminal growth / terminal RONIC rule.
8. Definition raw margin.
9. **Normalization rule written before seeing reverse result**.
10. Cycle-guard thresholds.
11. Debt/cash/share basis.
12. External reference versions.
13. Failure thresholds below.

## Последовательность

### A. 45–60 мин — historical gold facts

Ручная таблица 5–10 FY:

`revenue | gross margin | op margin | op income | EPS | shares | debt | cash`

### B. 30 мин — regime diagnosis

Записать:

- current vs 5y median margin;
- max/min range;
- recent acceleration;
- классификацию peak/normal/trough по prereg rule.

### C. 45 мин — два solves

1. naive flat FY2018 margin;
2. prereg normalized/mid-cycle margin.

Никакой ручной “подкрутки” после результата.

### D. 30 мин — independent references

- `implied-expectations` с теми же explicit inputs;
- BoothCheck historical comparator — только если сервис позволяет корректный as-of; если нет, **не использовать current report как historical truth**.

### E. 30–45 мин — reality check

Посмотреть последующие FY2019/FY2020 **только после того, как historical conclusion сохранён**.

### F. 30 мин — postmortem

Что сработало/не сработало; сколько ручных решений потребовалось.

Итого: ~3–4 часа чистой работы + запас до 6.

## Провал КОНСТРУКЦИИ

Любой из пунктов ниже — не “MU оказалась сложной”, а failure:

1. **As-of violation:** использован факт, filed после cutoff.
2. **Basis failure:** price/shares/split/revenue periods не удаётся однозначно согласовать.
3. **Peak blindness:** prereg cycle guard не срабатывает на FY2018 MU.
4. **Normalization discretion:** mid-cycle margin нельзя получить по заранее записанному правилу без ручного “ну здесь возьмём вот это”.
5. **Solver instability:** небольшое разумное изменение normalized margin меняет вывод из clearly undemanding в heroic и система не показывает эту чувствительность.
6. **Reference divergence:** при одинаковых inputs Consilium и independent solver расходятся больше заранее установленного tolerance и причина не найдена.
7. **Time failure:** оператор не может завершить reproducible artifact за 6 часов.

### Какой tolerance для solver diff

До пилота задать, например:

- forward value round-trip: <1% EV difference;
- recovered implied growth: <0.25 п.п. при **идентичных математических assumptions**.

Если модели концептуально различаются, diff не оценивается этим threshold — сначала выравниваются модели.

## Что НЕ является критерием успеха

Не требовать, чтобы модель “предсказала падение акции”.

Success pilot = она увидела, что FY2018 economics были peak regime, не экстраполировала их молча и показала, насколько price-implied expectations меняются после defensible normalization.

---

# ФИНАЛЬНОЕ РЕШЕНИЕ, КОТОРОЕ Я РЕКОМЕНДУЮ ОПЕРАТОРУ

## **GO, но только в HYBRID и только после pilot gate**

Не строить Consilium как собственный valuation universe engine.

Строить его как:

> **auditable expectations-ranking and validation harness**

где valuation solver заменяем, тестируем и сравниваем как коммодити, а core project — это:

- временная корректность данных;
- normalization/regime semantics;
- отказ вместо догадки;
- reproducibility;
- point-in-time population;
- out-of-sample validation;
- measurement of rank quality.

### Последовательность после этого раунда

1. **Не писать новые production features.**
2. Провести MU-2018 pilot.
3. Если pilot >6 часов или normalization остаётся discretionary → **STOP BUILD**, перейти на manual workflow.
4. Если pilot проходит → зафиксировать минимальный M4 spec по результату **без подгонки economics под будущую доходность**.
5. Подключить pinned `implied-expectations` как oracle, не core.
6. Сделать narrow quarterly revenue/op-income layer.
7. Решить PIT data buy-vs-build (получить цены Norgate/Calcbench).
8. Только затем автоматизировать NDX ranking.
9. Confirmatory Test #2 — только на untouched prereg protocol.

Главная смена приоритета относительно предыдущего плана:

> **следующий артефакт должен быть не ещё один changeset, а один вручную доказанный end-to-end case.**

Если MU-2018 нельзя объяснимо пройти вручную, автоматизация лишь умножит скорость получения неправильных чисел.
