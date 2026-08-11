---
author: CHATGPT
date: 2026-08-11
status: external review — round 4
answers: mailbox/ROUND4_2026-08-11_TEST1_AND_METHOD_REVISION.md
---

# ROUND 4 REVIEW — Test #1, output redesign, multiples, universe, buy-vs-build

## Короткий вердикт

**Продолжать проект, но снова сузить его.** Не строить «оценщик справедливой стоимости» и не пытаться получить один правильный terminal multiple. Целевая форма, которую я сейчас рекомендую:

> **Auditable Expectations & TSR Map** — система, которая показывает (1) какие ожидания уже зашиты в цену и (2) из каких компонентов может сложиться доходность акционера при заранее объявленных сценариях бизнеса и мультипликатора.

**BUY/NO-BUY убрать из модели. 12% убрать из money-path как критерий.** Личная планка оператора может остаться UI-фильтром после расчёта, но не свойством актива.

**Сбор SEC перевести на `edgartools` как parsing/transport substrate, но НЕ отдавать библиотеке temporal semantics и money-path validation.** Собственный `edgar_facts.py` перестать расширять как универсальный XBRL-парсер.

**Старый EPS×terminal-multiple bridge перестать развивать как главный решатель.** Главный математический контракт — полный FCFF/reverse-DCF; простая внутренняя реализация остаётся для независимости, а pinned `implied-expectations` работает постоянным differential oracle на идентичных inputs.

**Test #1 не доказал ranking ability.** Он оказался полезным integration/instrumentation test, но 55/175 рассчитанных наблюдений и отсутствие forward Rank IC не позволяют делать вывод «ранжирующая способность присутствует».

И ещё: **диагноз «система структурно слепа к восстановлению мультипликатора» в текущей формулировке математически неверен.** Система может учитывать expansion, если terminal multiple выше текущего. Реальный дефект — multiple contribution скрыт внутри общей доходности, а правило `min(history, fundamental cap)` асимметрично ограничивает величину upside re-rating и выдаёт один terminal multiple там, где честнее диапазон.

---

# 1. ЧТО НА САМОМ ДЕЛЕ ПОКАЗАЛ TEST #1

## Позиция: **формально несостоявшийся; методологические выводы из ranking пока нельзя делать**

Факт из опубликованного результата:

- 175 пар обработано;
- 55 рассчитано;
- 120 отказов = 68.6%;
- критерий sensitivity по BUY провален на всех трёх донных датах;
- criteria по forward discrimination в этом прогоне вообще не вычислены;
- сама пре-регистрация объявляет тест несостоявшимся при отказе более трети универсума.

Следовательно корректное утверждение:

> **Test #1 доказал, что стенд способен обнаруживать ряд технических дефектов и что старая BUY-конструкция практически не срабатывает на доступной подвыборке. Он НЕ доказал predictive/ranking ability.**

Фраза из Round 4 «ранжирующая способность присутствует» слишком сильна.

То, что median implied CAGR меняется между датами и что MA/AVGO/NFLX/ADBE/NVDA выглядят постфактум правдоподобно, — это **face validity и time-series sensitivity**, не cross-sectional rank validation.

Настоящее утверждение о ranking ability требует минимум:

1. достаточно широкого point-in-time cross-section на каждой дате;
2. forward total return;
3. Spearman Rank IC;
4. top-minus-bottom spread / monotonicity;
5. заранее замороженного coverage contract.

Именно этого Test #1 из-за отказов не дал.

### Но тест всё равно был полезен

Шесть найденных дефектов — не пустая работа. Особенно AMZN со split gap и NVDA со stale FCF basis показывают, что ваш главный инженерный риск остаётся прежним: **правдивые на вид числа из несогласованных временных/акционных базисов**.

Однако это означает, что Test #1 фактически выполнял роль **integration/debug corpus**, а не чистого confirmatory validation sample.

Для Test #2 это надо исправить процессуально: сначала calibration/integration corpus, на нём ломаем plumbing; затем freeze exact build; только потом untouched validation universe.

---

# 2. А1 — УБРАТЬ BUY/NO-BUY?

## **СОГЛАСЕН. Убрать полностью из модельного выхода.**

12% — это preference/operator hurdle, а не наблюдаемое свойство компании. Модель может вычислять доходность или price-implied expectations; решение «достаточно ли мне этого» принадлежит оператору.

Это не значит, что абсолютная дороговизна исчезает.

### Как писать «дорого по любым разумным предпосылкам» без нового BUY-порога

Не через доходность >/< X%, а через **feasibility envelope**.

Пример output:

```
EXPECTATIONS_OUTSIDE_REGISTERED_ENVELOPE

Чтобы оправдать цену, требуется хотя бы одно из:
- revenue growth > верхней границы зарегистрированного диапазона;
- operating margin > зарегистрированной нормализованной границы;
- duration роста > максимального горизонта;
- terminal multiple > зарегистрированного сценарного диапазона.
```

Это не рекомендация «не покупать». Это утверждение:

> **текущая цена не объясняется ни одной комбинацией предпосылок внутри заранее объявленного диапазона модели.**

Обратная формулировка:

`EXPECTATIONS_INSIDE_LOW_BURDEN_REGION` — цена объясняется даже нижней частью зарегистрированного диапазона.

Не использовать слова BUY/SELL/AVOID.

### Важное дополнение

**Ranking не должен заменять абсолютный контекст.** Первый номер в списке может быть просто «наименее дорогим из ста дорогих». Поэтому рядом с rank всегда нужен scenario envelope и benchmark context.

---

# 3. А2 — КАКАЯ СТАВКА НУЖНА?

## **Основной output: implied return / IRR; 12% не нужен как model input.**

Если вы задаёте нормализованный путь бизнеса и terminal scenario, можно решить обратную задачу:

> какая annualized return соответствует сегодняшней цене?

Тогда личный hurdle вообще не участвует в математике. После расчёта UI может показать:

```
model-implied shareholder return: 9.4–13.1%
operator reference: 12%
```

Но линия 12% не меняет ranking и не меняет inputs компании.

### Для price-implied expectations ставка всё же нужна

Reverse-DCF вопрос «какой рост требуется при данной цене?» математически требует discount rate. Я бы не выбирал одну «истинную» ставку.

Оставить вторичный expectations-view как сетку одинаковых reference rates, например:

```
required growth @ 8 / 10 / 12%
```

или market-consistent range, если вы заранее определите её методику.

**Не использовать company beta/WACC автоматически как новый источник псевдоточности до отдельной валидации.**

### Итоговая архитектура выхода

Два независимых представления:

1. **Expectations Map:** что цена требует от growth/margin/duration при стандартной rate-grid.
2. **TSR Map:** какую annualized shareholder return дают заранее объявленные operating + multiple scenarios; здесь личная ставка не нужна.

Я бы не объединял их в один score до Test #2. Пусть историческая проверка покажет, какой из двух rank реально несёт сигнал.

---

# 4. Б1 — «СЛЕПОТА К ВОЗВРАТУ МУЛЬТИПЛИКАТОРА»

## **НЕ СОГЛАСЕН С ДИАГНОЗОМ, СОГЛАСЕН С НЕОБХОДИМОСТЬЮ ЯВНО ПОКАЗЫВАТЬ MULTIPLE CONTRIBUTION.**

Текущая модель не структурно слепа к expansion.

Если:

```
P0 = E0 × M0
PT = ET × MT
```

то:

```
PT/P0 = (ET/E0) × (MT/M0)
```

Если кризисный `M0 = 8x`, а ваше terminal rule даёт `MT = 15x`, модель уже закладывает почти 1.9× вклад от восстановления множителя — даже при слабом росте earnings.

`min(historical_median, fundamental_cap)` **не сравнивается с current multiple**. Поэтому правило не запрещает движение 8→15.

### Что реально сломано

1. Multiple contribution скрыт внутри общего результата и не виден оператору.
2. Один terminal multiple создаёт ложную точность.
3. `min(history, fundamental cap)` асимметричен относительно historical normal: history может только снизить fundamental number, но не повысить его.
4. Если fundamental cap ниже нормального market multiple, модель систематически урезает re-rating upside.
5. На циклических/кризисных earnings raw P/E сам denominator может быть непригоден.

### Ковидный 2020 не является доказательством «слепоты»

В Test #1 на 23.03.2020 рассчитаны только 13/35 имён. Старый BUY threshold, старая модель и огромный отказной слой делают причинный вывод невозможным.

Можно сказать:

> «Ноль BUY на ковидном дне совместим с гипотезой, что модель недооценивала re-rating».

Нельзя сказать:

> «ноль BUY доказывает, что главным механизмом ошибки был неучтённый re-rating».

## Что выбираю из вариантов Б1

**(а) + (б), но как decomposition/sensitivity, а не как прогноз sentiment.**

Показывать:

```
Scenario             Annualized TSR
multiple unchanged        7.1%
multiple → P25            9.0%
multiple → median        12.4%
multiple → P75           15.0%
```

и рядом contribution:

```
Revenue growth       +x.x pp
Margin change        +x.x pp
Share-count change   +x.x pp
Multiple change      +x.x pp
Dividends            +x.x pp
Net-debt change      +x.x pp
```

Система не говорит, **какой multiple случится**. Она говорит, сколько доходности зависит от re-rating.

Это принципиально честнее.

Вариант (в) «ничего не менять, это консерватизм» отклоняю: скрытый и односторонний assumption — не консерватизм, а непрозрачная модельная ставка.

---

# 5. Б2 — ЧТО ТАКОЕ «НОРМАЛЬНЫЙ» MULTIPLE

## **Не искать одно число. Использовать диапазон двух разных якорей.**

Я бы прекратил попытку вычислить один «правильный terminal P/E».

### Якорь 1 — market-history band

Собственная point-in-time история компании:

- P25 / median / P75;
- 7–10 лет там, где доступно;
- **на нормализованном denominator**, а не сыром кризисном EPS.

Для циклической Micron raw P/E на peak/trough почти бессмысленен. Лучше использовать, например, EV / normalized operating profit (или NOPAT), где normalized margin считается зарегистрированным mid-cycle rule.

### Якорь 2 — fundamental steady-state multiple

Отдельно считать multiple, совместимый с terminal growth / reinvestment / return on capital / cost of capital.

Но **не делать `min(anchor1, anchor2)` единственной правдой**.

Показывать оба:

```
market-history band: 11x / 15x / 20x
fundamental steady-state reference: 16x
current normalized multiple: 9x
```

Затем scenario grid может включать 9x, 11x, 15x, 16x, 20x — с заранее фиксированным правилом выбора точек.

### Почему это лучше

На дне цикла вы отделяете два разных вопроса:

- **во что рынок раньше оценивал такую economics?**
- **какой multiple экономически совместим со steady-state economics?**

И не притворяетесь, что ответы обязаны совпасть.

---

# 6. Б3 — PRIOR ART ДЛЯ TSR DECOMPOSITION

## **Да. Я бы взял BCG TSR framework как основу OUTPUT TAXONOMY.**

BCG много лет раскладывает TSR для нефинансовых компаний на шесть investor-oriented drivers:

1. sales growth;
2. margin change;
3. multiple change;
4. dividend yield;
5. change in shares outstanding;
6. change in net debt / leverage.

Это почти буквально то, что сейчас нужно Consilium.

Источники:

- BCG, Value Creators methodology: https://www.bcg.com/publications/2023/industrial-distributors-thriving-across-markets
- BCG 2023 Value Creators: https://www.bcg.com/publications/2023/annual-value-creators-rankings
- BCG 2026 Value Creators: https://www.bcg.com/publications/2026/value-creators-rankings-strong-markets-hard-choices

### Expectations Investing — inverse side той же конструкции

Rappaport/Mauboussin рекомендуют начинать с ожиданий, embedded в price, и искать возможные revisions через sales, costs/margins и investment.

Источники:

- https://www.expectationsinvesting.com/
- https://www.expectationsinvesting.com/about-expectations-investing

Это естественная пара:

```
Expectations Investing → что уже ждёт рынок?
BCG-style TSR decomposition → откуда фактически/сценарно придёт shareholder return?
```

### Damodaran — для внутреннего growth decomposition

Damodaran отдельно подчёркивает, что revenue growth, operating-income growth, net-income growth и EPS growth различаются из-за operating leverage, debt и share issuance/buybacks.

Источник:
https://pages.stern.nyu.edu/~adamodar/New_Home_Page/littlebook/growthrates.htm

Поэтому я бы использовал:

- **BCG — форма пользовательского выхода**;
- **Expectations Investing — reverse model**;
- **Damodaran — sanity/framework для growth/reinvestment decomposition**.

---

# 7. В1 — КОНТРАКТ УНИВЕРСУМА TEST #2

## **Простого «торгуется ≥5 лет до самой ранней даты И подаёт 10-K» недостаточно.**

Главная ошибка этого правила: оно фиксирует eligibility относительно самой ранней даты и тем самым выкидывает компании, которые честно появились позже и были членами point-in-time universe на более поздних test dates.

### Правильная конструкция — два слоя

## U(t): внешний point-in-time universe на каждую дату

Например point-in-time S&P 500 ex-Financials, как вы уже планировали.

Состав определяется **только внешним историческим membership source**, а не сегодняшним списком.

## E(t): eligibility внутри U(t), определённая только фактами, известными на t

До запуска valuation для каждого имени автоматически проверить:

1. security реально торговалась на t;
2. issuer/security mapping однозначен;
3. нужное число полных FY history **уже было подано к t**;
4. form/taxonomy входит в поддержанную область;
5. модельный архетип разрешён;
6. есть минимальные raw inputs для money path;
7. share/basis contract можно проверить;
8. security не ETF/fund;
9. multi-class rule определён заранее.

### Обязательный PREFLIGHT

До открытия price/output модели публикуется:

```
U(t) count
E(t) count
exclusions by reason
coverage = E/U
```

И только затем freeze.

Я бы заранее установил minimum coverage gate, например 80–90% в поддерживаемой области. Точное число надо пре-регистрировать, не выбирать после результата.

### «Имя не существовало» должно исчезнуть как категория runtime failure

Если PIT universe корректен, несуществующее имя просто не входит в U(t).

### Young company — не tool failure

Если компания уже в индексе, но у неё нет 5 лет истории, это `MODEL_INELIGIBLE_SHORT_HISTORY`, известный **до valuation**. Она остаётся в coverage denominator и честно показывает границу метода.

---

# 8. В2 — ПОВТОРЯТЬ ЛИ TEST СЕЙЧАС?

## **НЕТ. Сначала изменить output/method contract, затем один новый confirmatory test.**

Повтор старого теста сейчас почти ничего не даст:

- BUY/NO-BUY вы собираетесь удалить;
- ставка 12% меняет статус;
- multiple output меняется;
- ranking metric меняется;
- data substrate, вероятно, меняется на edgartools;
- full DCF bridge должен стать главным/параллельным.

Валидировать старую конструкцию после решения её снять — пустая трата holdout history.

### Test #1 теперь считать

`INTEGRATION / PROTOCOL DISCOVERY RUN`.

Не «проваленной valuation validation» и не «доказавшей ranking».

### Test #2

Проводить только после freeze новой конструкции и exact build hash.

---

# 9. В3 — 20-F/40-F И GOOG MULTI-CLASS

## GOOG: **ПОДДЕРЖИВАТЬ ОБЯЗАТЕЛЬНО**

Alphabet — не экзотика, а core Nasdaq-100 issuer. Исключать его потому, что собственный parser не умеет dimensioned diluted shares, означает подстраивать universe под слабость инструмента.

Ваш `diag_edgar_gaps.md` уже установил конкретный механизм: до FY2022 Alphabet давал diluted-share denominators по классам через XBRL dimensions, а Company Facts API не давал пригодного aggregate. Это именно тот класс задачи, ради которого имеет смысл перейти к filing-level XBRL parser.

## 20-F / 40-F: **поддерживать поэтапно, не блокировать v1**

Для первой confirmatory validation допустима явно ограниченная область:

> domestic 10-K/10-Q issuers + multi-class domestic issuers.

Foreign private issuers временно получают `OUT_OF_SCOPE_FOREIGN_FILER`, не generic data failure.

Но для operational Nasdaq-100 постоянное исключение 20-F/40-F означает, что продукт не покрывает заявленный universe. Поэтому после domestic goldens нужен отдельный foreign-filer pack.

Минимум goldens:

- NVO — 20-F, IFRS;
- DLO — 20-F, IFRS;
- SHOP historical — 40-F;
- один 20-F US-GAAP filer;
- один issuer с form-transition.

---

# 10. `edgartools`: ПОРА ЛИ ЗАМЕНИТЬ СОБСТВЕННЫЙ СБОР?

## **ДА — заменить САНТЕХНИКУ. НЕТ — не отдавать библиотеке правила истины.**

Это сейчас моя самая прямая инженерная рекомендация.

`edgartools` уже предоставляет:

- structured 10-K/10-Q и другие SEC filings;
- filing metadata/accession/date;
- filing-level XBRL;
- dimensional XBRL data;
- standardized statements;
- multi-filing stitching;
- quarterly and annual periods;
- raw facts/DataFrame access;
- local caching/download.

Официальная документация:

- https://github.com/dgunning/edgartools
- https://edgartools.readthedocs.io/en/latest/xbrl/
- https://edgartools.readthedocs.io/en/latest/xbrl/guides/multi-period-analysis/

### Почему НЕ drop-in replacement

Ваши самые важные правила не являются parsing features:

1. `filed_at <= as_of`;
2. exact accession manifest;
3. restatement policy;
4. zero ≠ missing;
5. same-period rule across legs;
6. stale-fact refusal;
7. share-basis reconciliation between FY end and observation date;
8. split handling;
9. taxonomy/concept conflict policy;
10. provenance каждой трансформации.

Это и есть минимальный уникальный слой Consilium.

### Важное предупреждение

Даже зрелая библиотека не является oracle истины. В актуальной истории `edgartools` есть data-correctness fixes: например релиз v5.39.1 исправлял historical SGML parsing, из-за которого `FILED AS OF DATE` мог теряться и `filing_date` становился `None`.

Для обычного аналитика это bugfix. Для вашего `as-of` стенда — критический money-path class.

Следовательно:

> **pin version + own temporal adapter + replay goldens.**

Никаких auto-upgrade.

## Рекомендуемая схема

```
SEC raw filings
    ↓
edgartools (transport + parsing + XBRL dimensions)
    ↓
Consilium Temporal/Semantic Adapter
    - as_of
    - accession
    - period
    - unit/currency
    - dimensions
    - missing semantics
    - restatement policy
    - share basis
    - staleness
    ↓
Normalized immutable snapshot
    ↓
models
```

### Не использовать `Company.get_facts()` как единственный historical truth

Для confirmatory as-of строить snapshot из **конкретных filings, которые были filed к t**, и разбирать `filing.xbrl()` / stitched selected filings.

Company-level current facts удобны для trends, но могут содержать comparative facts, поданные позже observation date. Ваш temporal contract важнее convenience API.

### Миграционный gate

Не переписывать всё сразу.

Dual-run старый collector vs edgartools adapter на frozen difficult corpus:

- AMZN split-window case;
- GOOG FY2021 dimensions;
- NVDA stale/tag-switch case;
- ORCL debt facts;
- SHOP 40-F;
- NVO IFRS 20-F;
- amended filing;
- multi-class;
- one split;
- one zero-vs-missing case.

Каждый diff классифицируется:

`OLD_BUG / EDGARTOOLS_BUG / SEMANTIC_POLICY / UNRESOLVED`.

**UNRESOLVED > 0 → cutover запрещён.**

---

# 11. СОБСТВЕННЫЙ SOLVER И `implied-expectations`

## **Постоянный diff-test — ДА. Но старый EPS×multiple bridge не должен быть главным независимым solver.**

Micron уже показал structural difference +3.6 п.п. требуемого роста из-за промежуточных cash flows и net cash.

Это не маленькая погрешность арифметики. Это разные модели.

### Моя конструкция

**Primary:** маленькая чистая внутренняя FCFF/reverse-DCF функция без I/O и без LLM.

**Oracle:** pinned exact `implied-expectations`, только mathematical core, на идентичных inputs.

**Goldens:** несколько hand-worked/Damodaran spreadsheet cases.

### Почему не сделать external oracle единственным core

- проект свежий и single-maintainer;
- ранее в его ingestion уже найдены defaults, несовместимые с вашими правилами;
- независимость diff-test исчезнет, если ваша реализация станет просто fork того же кода.

### Почему не продолжать EPS bridge

Потому что он сознательно игнорирует intermediate cash flows и net cash. После MU это уже измеренная model limitation, а не гипотеза.

Оставить его можно как diagnostic:

`TERMINAL_ONLY_BRIDGE_DELTA`,

но не как money-path primary rank.

---

# 12. САМОЕ ВАЖНОЕ, О ЧЁМ ВЫ НЕ СПРОСИЛИ

## 12.1. Вы снова рискуете откалибровать прибор на validation sample

Шесть дефектов были найдены «по дороге» Test #1. Это хорошо для engineering, но означает, что sample выполнял роль development corpus.

В Test #2 нельзя снова:

> запустить holdout → найти plumbing pattern → починить → продолжить тот же holdout.

Даже без просмотра forward returns вы меняете coverage function на именах validation universe.

Нужны:

- отдельный calibration corpus;
- exact code freeze;
- untouched holdout run одним build.

## 12.2. Новые «калиброванные на данных» technical thresholds надо отделить от outcome calibration

Если split/staleness thresholds выбраны по distribution архивных technical signals и не используют future return, риск leakage ниже, но они всё равно меняют, какие observation проходят в sample.

Для Test #2 эти thresholds должны быть frozen заранее и проверены negative controls.

## 12.3. Один удачный MU не валидировал правило 5-летней median margin вообще

Он валидировал его **на одном memory-cycle case**.

На NVDA structural margin expansion или на META business-mix change механическая five-year median может быть так же неверна, как raw current margin.

Поэтому правило должно называться:

`CYCLICAL_MIDPOINT_ESTIMATOR`,

а не universal normalized margin.

Для non-cyclical/regime-change names нужен другой treatment / LOW_CONFIDENCE.

## 12.4. Не делайте один универсальный rank раньше Test #2

Сейчас у вас две потенциально разные идеи:

### Rank A — Expectations Burden

Насколько требовательны expectations в цене относительно нормализованной economics.

### Rank B — Scenario TSR

Какой shareholder return получается при registered scenarios growth/margin/multiple/distributions.

**Публиковать оба в Test #2.**

Не решать сейчас, что один «главнее». Test #2 должен показать:

- Rank IC каждого;
- top-bottom spread каждого;
- correlation между ними;
- cases, где они расходятся.

Например:

- Intel может иметь низкий expectation burden, но плохой cash trajectory;
- NVIDIA может иметь высокий expectation burden, но exceptional operating trajectory.

Один scalar может потерять это различие.

## 12.5. Multi-class — это не только parser issue, но и universe semantics

GOOG/GOOGL могут представлять одну economics через две securities.

До Test #2 решить заранее:

- ranking на уровне issuer или security?
- если security — допускаются ли обе share classes в portfolio deciles?
- если issuer — какая class используется для price/return?

Иначе Alphabet может получить двойной вес в rank statistics.

---

# 13. МОЯ ПРЕДЛАГАЕМАЯ M5-АРХИТЕКТУРА

## Слой 1 — DATA

`edgartools` + Consilium temporal/semantic adapter.

## Слой 2 — BUSINESS STATE

Только измеримые decomposition:

- revenue;
- margin;
- NOPAT/FCF;
- reinvestment;
- share count;
- dividends;
- net debt;
- cycle/regime flags.

## Слой 3 — EXPECTATIONS MAP

Full FCFF reverse DCF:

- implied growth;
- implied margin;
- implied duration;
- rate sensitivity.

## Слой 4 — TSR MAP

Сценарии:

- no multiple change;
- P25 normalized historical multiple;
- median normalized historical multiple;
- fundamental steady-state reference;
- optional P75 sensitivity.

Output decomposition по BCG-style components.

## Слой 5 — RANKING

До Test #2 два ranks:

- expectations burden;
- scenario TSR.

Никаких BUY/NO-BUY.

## Слой 6 — VALIDATION

PIT external universe + preflight + exact frozen build + forward rank metrics.

---

# 14. СТОИТ ЛИ ВООБЩЕ ПРОДОЛЖАТЬ СТРОИТЬ?

## **ДА, но только эту уменьшенную M5. Автономный valuation engine — STOP.**

Почему не STOP всего проекта сейчас:

- MU pilot показал, что reproducible as-of workflow можно выполнить быстро;
- Test #1 реально поймал опасные basis/staleness defects;
- у проекта теперь есть понятная уникальная функция: auditability + temporal correctness + regime/refusal + validation;
- reverse DCF/XBRL plumbing можно перестать изобретать.

Почему нельзя продолжать как раньше:

- неделя ушла прежде всего на plumbing, а не на investment insight;
- 69% отказов — неприемлемая база для claimed universe rank;
- Test #1 не дал predictive evidence;
- один terminal multiple и один scalar rank пока слишком хрупкие;
- n8n/custom XBRL expansion увеличивают surface area быстрее, чем инвестиционную ценность.

### Новый STOP gate

До Test #2 заранее записать:

1. minimum preflight coverage;
2. expected allowed refusal reasons;
3. primary rank metrics;
4. success/failure rule для Rank IC / top-bottom / monotonicity;
5. maximum unresolved data diffs после edgartools cutover.

Если новая конструкция снова не может провести confirmatory test из-за coverage/instrument defects — **остановить автоматический universe ranking и оставить manual/semi-automatic company workflow.**

Если test технически проходит, но оба rank не показывают устойчивой forward discrimination — **тоже остановить claim, что система ищет относительную дешевизну**, и оставить её как research/decomposition tool.

---

# 15. ЯВНЫЕ ОТВЕТЫ НА ВОПРОСЫ ROUND 4

| Вопрос | Позиция |
|---|---|
| А1 — убрать BUY/NO-BUY | **СОГЛАСЕН полностью** |
| А2 — ставка | **Primary implied IRR без 12% как входа; 12% только user reference. Reverse-expectations — rate grid.** |
| Б1 — учесть recovery multiple | **Диагноз “слепота” отвергаю; multiple expansion уже математически возможен. Добавить явную decomposition + scenarios.** |
| Б2 — normal multiple | **Не одно число: normalized historical band + separate fundamental reference. Не `min()` как единственная правда.** |
| Б3 — литература | **BCG TSR decomposition + Expectations Investing + Damodaran growth/reinvestment decomposition.** |
| В1 — universe contract | **Простого 5y+10-K недостаточно. PIT U(t) + as-of eligibility E(t) + preflight coverage gate.** |
| В2 — повторять test сейчас | **НЕТ. Сначала M5/final output, затем один новый frozen Test #2.** |
| В3 — 20-F/40-F/GOOG | **GOOG поддерживать сейчас; foreign forms staged, но permanent exclusion несовместим с заявкой на полный NDX.** |
| edgartools | **ДА как substrate; НЕТ как semantic truth.** |
| oracle diff-test | **ДА постоянно, на идентичных inputs; full DCF primary, EPS bridge diagnostic only.** |
| весь проект | **CONTINUE NARROW HYBRID; STOP autonomous fair-value engine.** |

---

# ФИНАЛЬНАЯ РЕКОМЕНДАЦИЯ ОПЕРАТОРУ

Не пытайтесь ещё раз «починить текущий valuation engine».

Сделайте более радикальный и одновременно более простой переход:

> **из машины оценки цены → в машину разложения ожиданий и потенциальной TSR.**

Рынок может дать доходность через:

- рост бизнеса;
- изменение маржи;
- сокращение/размытие акций;
- возврат/сжатие multiple;
- дивиденды;
- изменение net debt.

Consilium должен не угадывать одно будущее, а показывать **какая часть результата требует какой предпосылки и насколько ranking устойчив к смене этой предпосылки**.

Это лучше соответствует реальной задаче оператора — выбрать из Nasdaq-100 компании с наиболее интересным соотношением текущих ожиданий, качества economics и потенциальной доходности — и требует меньше собственной инфраструктуры, чем очередная версия универсального intrinsic-value engine.
