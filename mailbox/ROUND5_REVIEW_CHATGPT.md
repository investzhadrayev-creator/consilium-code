---
author: CHATGPT
date: 2026-08-12
status: external review — round 5, fundamental revision
answers: mailbox/ROUND5_2026-08-11_FUNDAMENTAL_REVIEW_v2.md
includes: mailbox/ERRATUM_2026-08-11_01_AUDITORS.md
---

# ROUND 5 REVIEW — фундаментальная ревизия Consilium

## Короткий итог до ответов по пунктам

Мой обязательный выбор по 2.3: **(б) — задача решаема в урезанном виде.** Но я предлагаю урезать её сильнее, чем сформулировано в варианте (б).

Я **не рекомендую продолжать строить Consilium как собственный массовый valuation/ranking radar на ~100 имён**. За четыре раунда и два пилота проект накопил достаточно свидетельств, что именно эта часть создаёт непропорционально много инженерной и методологической сложности, а её инвестиционная добавленная стоимость пока не доказана.

Целевая форма, которую я рекомендую:

> **Discovery → Diligence → Decision Journal**, а не единый valuation engine.

1. **Discovery** — дешёвый внешний/готовый слой: fundamentals + earnings revisions + surprise/reaction + price momentum + простая valuation context. На первом этапе его вообще не надо программировать самостоятельно.
2. **Diligence (Consilium)** — собственный глубокий, воспроизводимый разбор 1 имени перед новой покупкой: нормализация экономики, cash conversion, цикличность, share count, долг, reverse-scenario surface, consensus-vs-requirement, provenance и отказ вместо догадки.
3. **Decision Journal** — неизменяемый снимок того, что было известно, почему имя прошло/не прошло, какие assumptions были приняты и что произошло после. Это недооценённая часть проекта: без неё нельзя понять, улучшает ли система реальные решения оператора.

В этой форме Consilium становится не «машиной, которая находит лучшие акции», а **системой защиты от плохого тезиса, плохой цены и ложной уверенности после того, как кандидат уже найден**.

Главный пересмотр моей позиции относительно ранних раундов: я больше **не считаю массовый reverse-DCF ranking разумным центром продукта для соло-оператора**. Reverse analysis оставляю, но как инструмент второго этажа для сценарного вопроса «что должно быть правдой при этой цене?», а не как scalar ranking всех имён.

---

# 1.1. Верна ли постановка задачи?

## Позиция: **НЕ ПОЛНОСТЬЮ. Формулировка делает многомерную задачу одномерной.**

Фраза «посчитать, какой рост бизнеса цена уже требует» звучит так, будто у цены есть единственный implied growth. У reverse valuation такого единственного ответа нет.

Цена одновременно зависит минимум от:

- исходной нормализованной прибыли/FCF;
- роста выручки;
- пути маржи;
- продолжительности высокого роста;
- реинвестирования и ROIIC/ROIC;
- share count / SBC / buybacks;
- чистого долга;
- terminal economics;
- terminal multiple или terminal return-on-capital assumptions;
- требуемой ставки доходности.

Поэтому математически Consilium сейчас не «извлекает требуемый рост из цены». Он делает другое:

> **фиксирует все неизвестные кроме одного и сообщает, какое значение оставшегося неизвестного согласует модель с ценой.**

Это полезно, но это **сечение многомерной поверхности**, а не свойство акции.

Особенно наглядно это уже проявилось на Micron: один и тот же price при FY2018 margin дал почти нулевой required growth, а при preregistered mid-cycle margin — около 6.8%. Цена не изменилась; изменился экономический режим базы.

### Как бы я переформулировал задачу

> **Для выбранной акции показать, какие комбинации нормализованного роста, маржи, длительности, реинвестирования и terminal/multiple assumptions совместимы с текущей ценой; сопоставить эти требования с текущей траекторией бизнеса, историческим диапазоном и внешними ожиданиями; выявить места, где тезис зависит от хрупкого допущения.**

Исторический growth тогда является **evidence/context**, а не «achievable growth» и не второй стороной универсального scalar gap.

### Что система де-факто умеет лучше всего уже сегодня

Не оценивать будущее, а **обнаруживать неправильную базу для рассуждения о будущем**:

- MU: peak earnings не являются нормальной базой;
- INTC: accounting EPS и cash economics расходятся;
- AMZN: share basis может сделать красивую «дешевизну» артефактом;
- NVDA: устаревшая cash leg может незаметно отнести расчёт на годы назад.

Это важная способность, но это скорее **investment due-diligence harness**, чем stock picker.

---

# 1.2. Является ли система «оценкой прошлого» и запаздывает ли она для growth-tech?

## Позиция: **reverse-DCF сам по себе НЕ запаздывает; запаздывает исторический якорь, если его превращать в прогноз. Для growth-tech это существенный дефект.**

Текущая цена — forward-looking объект. Reverse-DCF задаёт правильный forward-looking вопрос: «какая будущая экономика должна реализоваться, чтобы эта цена имела смысл?» В этом смысле он не является анализом прошлого.

Запаздывание появляется во второй половине старой конструкции:

> `price-implied requirement` сравнивается с trailing historical CAGR, как будто прошлый режим — лучшая оценка будущего.

Для зрелого стабильного бизнеса это иногда приемлемый baseline. Для технологического бизнеса в inflection regime — нет.

### Два симметричных типа ошибки

**NVDA-подобный inflection вверх.** История до AI-инфлексии не могла содержать новую economics. Historical anchor способен назвать будущую траекторию «героической» именно перед структурным ускорением.

**Zoom/Micron-подобный regime down.** Пятилетняя история ещё содержит boom/peak и способна объявить цену нетребовательной после того, как нормальная экономика уже сменилась.

Поэтому я бы перестал задавать системе вопрос:

> «требует ли цена меньше роста, чем компания показывала раньше?»

и задавал два отдельных:

1. **Что цена требует?** — reverse scenario surface.
2. **Куда сейчас пересматривается ожидание бизнеса?** — revisions, guidance, margin trajectory, price reaction.

### Нужно ли пытаться предсказывать EPS Surprise?

Нет. Я не рекомендую превращать Consilium в модель угадывания квартального beat/miss.

Есть независимая академическая литература, показывающая исторический drift после earnings news и analyst revisions. Классическая работа Chan, Jegadeesh & Lakonishok (Journal of Finance, 1996) показывает, что past earnings surprise и past return независимо предсказывали последующий drift, а analysts реагировали на новости постепенно. Jung, Keeley & Ronen (2019) находят предсказуемость revisions и implementable abnormal returns, особенно при низком analyst coverage.

Но это **не означает**, что vendor claim вроде «Zacks Rank #1 = X% годовых» или конкретный ERB lead в 25 недель надо принять как закон. Транзакционные издержки уменьшают прибыльность PEAD-стратегий, а в самых ликвидных mega-cap рынках информационная реакция может быть быстрее, чем в старых выборках.

Источники внешней проверки:
- Chan, Jegadeesh, Lakonishok, *Momentum Strategies*, Journal of Finance (1996): https://doi.org/10.1111/j.1540-6261.1996.tb05222.x
- Jung, Keeley, Ronen, *The Predictability of Analyst Forecast Revisions* (2019): https://journals.sagepub.com/doi/10.1177/0148558X17722710
- Ng, Rusticus, Verdi, *Implications of Transaction Costs for PEAD*: https://research.polyu.edu.hk/en/publications/implications-of-transaction-costs-for-the-post-earnings-announcem/

### Вывод

**Price-implied expectations + current revisions/trajectory совместимы и нужны вместе.** История должна использоваться для нормализации и диапазонов, а не как автоматический прогноз будущего growth.

---

# 2.1. Четыре структурных минуса + пропущенные

## Минус 1 — данные грязнее задачи

### Вердикт: **ПОДТВЕРЖДАЮ. Тяжесть высокая операционно, но проблема лечится без строительства собственного XBRL-комбайна.**

Erratum ухудшил диагноз: 34 отказа — не «foreign/multiclass scope», а defect extraction/join layer; ещё 11 отказов, напротив, являются правильной работой новых basis/staleness guards.

Это говорит сразу две вещи:

1. fail-closed philosophy правильна;
2. собственная generic SEC plumbing съедает слишком много ресурсов.

**Лечение:** `edgartools`/filing-level XBRL как transport/parser substrate + собственный semantic adapter, а не дальнейшее расширение `edgar_facts.py` как универсального парсера.

Собственными должны остаться:

- `as_of` cutoff;
- accession/filed-at provenance;
- period/basis agreement;
- dimensional aggregation policy;
- share/split reconciliation;
- staleness;
- amendment/restatement policy;
- missing != zero/default;
- named refusal.

То есть проблема лечится **умеренно дёшево в архитектуре глубокого одного имени**, но дорого, если продолжать требовать 100×много исторических дат с универсальной автоматизацией.

---

## Минус 2 — «required growth» скрывает несколько неизвестных

### Вердикт: **ПОДТВЕРЖДАЮ. Это самый фундаментальный минус. Одним patch его не вылечить.**

И неизвестных не два, а больше: growth, margin path, duration, reinvestment efficiency, terminal economics/multiple, discount/return assumption.

Нельзя получить единственный «правильный required growth» без выбора остальных.

Измерение Round 4/erratum делает проблему конкретной: historical median multiple отсутствовал 55/55, поэтому terminal multiple полностью задавался фундаментальной формулой и в основном режиме физически упирался примерно в 18x. Значит scalar required growth частично ранжировал **совместимость компании с выбранным terminal model**, а не только требовательность текущей цены.

### Лечение

Не пытаться найти более умный один multiple.

Заменить scalar inverse solve на **scenario surface**, например:

| Normalized margin | Terminal multiple | Required revenue growth | Implied IRR при заданном growth |
|---|---:|---:|---:|
| Bear | unchanged | … | … |
| Base | market-normalized / fundamental ref | … | … |
| Bull | upper registered band | … | … |

Система должна показывать, **где находится хрупкость**:

> «12–14% return получается только если margin возвращается к 32% и multiple расширяется 18→25x».

Это полезнее, чем «required growth = 7.3%».

---

## Минус 3 — качество массового ranking трудно доказать малыми силами

### Вердикт: **ПОДТВЕРЖДАЮ. Для соло-проекта это один из главных аргументов отказаться от собственного массового ranking.**

Технически задача решаема: point-in-time constituents, delisted securities, prices, historical estimates существуют у коммерческих vendors. Но вопрос не «можно ли купить данные?», а «оправдан ли весь research infrastructure ради личного stock-selection workflow?».

Для честного claim «rank обладает alpha» понадобятся:

- PIT universe;
- dead/delisted names;
- PIT fundamentals;
- PIT consensus/revisions, если они входят в сигнал;
- forward total returns;
- corporate actions;
- enough cross-section;
- замороженная версия модели;
- защита от multiple testing/data snooping;
- достаточный временной период и независимые regimes.

Это превращает личный инструмент в маленькую quant research platform.

### Лечение

**Не делать статистический alpha claim.** Для Floor 1 начать prospective paper trail с сегодняшнего дня. Для Floor 2 валидировать не «доходность модели», а correctness/reproducibility и качество named failure modes на historical goldens.

---

## Минус 4 — система молчит почти всегда

### Вердикт: **СТАРАЯ ФОРМУЛИРОВКА БОЛЬШЕ НЕ ЯВЛЯЕТСЯ СТРУКТУРНЫМ МИНУСОМ.**

Одна BUY из пяти дат была следствием старого binary 12% gate, который уже решено убрать. Поэтому «молчание BUY» больше не аргумент против новой архитектуры.

Но остаётся другой серьёзный вопрос: **coverage/refusal rate.** Если глубокий dossier на META/GOOG не способен собрать базовые факты без ручной починки парсера, это проблема. Для one-name microscope отказ приемлем, но должен быть редким и объяснимым, а не нормальным режимом.

---

## Пропущенные структурные минусы

### 5. Смешение discovery и valuation/risk-control

«Найти акцию, которая может пойти лучше рынка» и «не переплатить за найденную акцию» — разные задачи.

Старая архитектура заставляла reverse valuation выполнять обе роли. Именно поэтому проект постоянно спорил, что считать ranking score.

### 6. Нестационарность бизнеса

Historical medians/CAGRs предполагают, что regime достаточно устойчив. Технологии, M&A, new products, regulation, capex cycles ломают это предположение.

### 7. Consensus — не независимая истина

Analyst revisions могут:

- следовать за price move;
- отражать company guidance;
- быть correlated между брокерами;
- иметь разную basis (GAAP/non-GAAP);
- плохо работать при малом coverage.

Их надо трактовать как **market expectations state**, а не ground truth будущей прибыли.

### 8. Sector metrics могут превратиться в новый zoo исключений

P/B×ROE для банков, AISC/P-NAV для miners и т.д. экономически разумны. Но если строить автоматический engine на каждый sector, проект снова разрастается в многоархетипную valuation platform.

На Floor 1 sector metric должен быть простым context/flag. Глубокая sector-specific economics — только в dossier по запросу.

### 9. Текстовые catalysts создают ручную/LLM-дискреционность

Catalysts полезны для человека, но их нельзя смешивать с quantitative score без отдельной проверяемой модели. Оставить как named text evidence с источником и датой, не как число.

### 10. Нет portfolio layer

Даже идеальная оценка одной акции не отвечает:

- сколько купить;
- с чем она коррелирует;
- какой concentration уже есть;
- каков opportunity cost против QQQ/другого кандидата;
- что делать при ухудшении thesis.

Это не значит «сейчас строить portfolio optimizer». Но продукт должен честно остановиться до границы: **Consilium помогает выбрать/отклонить entry thesis; position sizing — отдельное решение.**

### 11. Риск двойного счёта сигналов

Revisions, EPS surprise, price momentum и analyst upgrades часто отражают одну и ту же новость. Простое сложение баллов создаст иллюзию четырёх подтверждений, хотя это один information event.

### 12. Change-control нужен не только коду, но и vendor data

Если Koyfin/Zacks/Finnhub меняет definition/coverage, prospective journal должен хранить source, snapshot time и definition version настолько, насколько это возможно.

---

# 2.2. Что говорят MU-2018 и INTC-2021 против этих минусов?

## Позиция: **артефакты поддерживают Consilium как microscope, но не как radar.**

### MU-2018 — сильный положительный evidence

Сторож пика и preregistered normalization сделали именно то, что должен делать глубокий diligence:

- raw EPS 11.50 выглядел чрезвычайно дешёвой базой;
- правило mid-cycle без ручной подкрутки снизило базу примерно до 4.40;
- reality check показал, что peak EPS не был восстановлен много лет;
- решение стало существенно менее «кричащим».

Это реальная ценность. Но она доказывает не эффективность ranking, а способность **не экстраполировать плохую базу**.

### INTC-2021 — тоже полезный evidence, хотя пилот формально failed

Сам факт `P/E 9.8` против `P/FCF 17.3` уже показывал проблему до хитрого binary CASH_DECAY rule. Провал threshold `+15 pp` продемонстрировал слабость hand-designed Boolean guard.

Урок:

> **разложение и видимость противоречий важнее попытки заставить каждый риск стать одним бинарным флагом.**

Я бы оставил guards, но сделал их преимущественно:

- `OK / AMBER / RED / NOT_APPLICABLE`;
- с показанными сырыми компонентами;
- hard refusal только там, где data/basis/model domain действительно невалидны.

### Итог баланса

MU/INTC оправдывают продолжение **глубокого due-diligence layer**. Они не оправдывают дорогой массовый radar.

---

# 2.3. Обязательный выбор (а)/(б)/(в)

# **ВЫБОР: (б).**

Но моя версия (б):

> **глубокий разбор одного имени + внешний/готовый список кандидатов без собственных статистических alpha-претензий.**

Я не рекомендую даже сейчас строить внутренний «sorted list по reverse-DCF». Sorted/filtered discovery list лучше получать из более дешёвых данных Floor 1, а Consilium подключать только к 3–10 кандидатам.

Почему не (а): массовый radar требует data engineering + PIT validation, непропорциональных личному бюджету, и scalar reverse rank имеет identification problem.

Почему не (в): MU показал, что глубокий, preregistered, fail-closed analysis реально способен убрать опасную ложную простоту. Значит полезное ядро существует.

---

# В-3.1.1. Состав карточки Floor 1

## Позиция: **идея правильная, карточку надо упростить и добавить price/FCF dimensions. Не строить composite score на первом этапе.**

Я бы сделал Floor 1 не «маленькой valuation model», а **четырёхколоночной картой**:

1. **Business trajectory**
2. **Expectations momentum**
3. **Price / valuation context**
4. **Risk / regime**

### Обязательно оставить

#### Business trajectory

- Revenue growth 3y/5y и, важнее, LTM/last FY acceleration vs prior years.
- Operating margin: LTM, last FY, 3–5y median/range.
- EPS trajectory, но рядом operating income/FCF — чтобы buybacks не выдавались за business growth.
- FCF conversion (`FCF / NI` или sector-appropriate cash metric).
- Share-count change 1y/3y; SBC/buybacks context.
- Net debt / cash trend.

#### Expectations momentum

- Consensus EPS **FY1 и FY2** change за 30/90 дней.
- Consensus revenue change за 30/90 дней.
- Analyst count + dispersion, если provider даёт.
- Последние 4–8 quarterly EPS/revenue surprises.
- **Реакция цены на последний earnings event** — это важное пропущенное поле. Beat, после которого акция падает и forecasts не поднимаются, информационно отличается от beat + raise + positive reaction.

#### Price / market confirmation

- Relative strength 3/6/12 месяцев против NDX и sector benchmark.

Это сознательное добавление. Классическая литература показывает, что price momentum и earnings news содержат частично независимую информацию. Если Floor 1 ищет «куда смотреть», игнорировать price response странно.

#### Valuation context

- Forward/normalized P/E или EV/EBIT/FCF where applicable;
- percentile/range собственной истории, если vendor уже предоставляет;
- sector-relative context.

### Что понизить в статусе

**PEG** — оставить как справочную строку, не signal. Он игнорирует margin, duration, capital intensity, rates и quality of growth.

**Raw P/E у cyclicals** — не signal cheapness. На Floor 1 нужен `CYCLICAL_EARNINGS_BASE` flag.

**Catalysts** — text-only, source/date required, никогда не numeric score.

### Что обязано пережить из полного Consilium

**Да: cycle/regime guard.** MU доказывает это лучше любого теоретического аргумента.

Но я добавлю ещё два дешёвых guard:

1. **Cash conversion divergence** — EPS/NI растёт, FCF заметно хуже.
2. **Share-count contribution** — EPS растёт существенно быстрее NI из-за shrinking denominator.

### Чего НЕ делать

Не создавать сейчас формулу:

`0.2×ERB + 0.2×surprise + 0.2×PEG + ...`

Без независимой истории веса будут эстетическими. Сначала показывать **профиль**, а shortlist строить простым последовательным фильтром.

---

# В-3.1.2. Данные consensus/revisions/surprises: доступность, цена, backtest

## Позиция: **Floor 1 можно сделать разумно дёшево для текущего использования, но честный historical backtest revisions почти наверняка не стоит покупать/строить на первом этапе. Forward-only validation принимаю и рекомендую.**

Это один из ключевых выводов раунда.

## Что реально доступно частному инвестору сейчас

### Koyfin — лучший кандидат для ручного/полуручного старта

Официальный Plus plan сейчас указан как **$39/month** и включает 10Y financials и 10Y estimates. Koyfin также добавил historical estimates/actuals/surprises.

Но есть критическое ограничение: Koyfin официально пишет, что **API нет из-за ограничений data providers**, а financials/estimates/valuation global equities **нельзя выгружать** из-за vendor restrictions. Consensus source — S&P Capital IQ.

То есть Koyfin — хороший **человеческий Floor 1**, но плохой фундамент для автоматического reproducible data pipeline.

Источники:
- https://www.koyfin.com/pricing/
- https://www.koyfin.com/help/faq/can-i-get-the-data-via-api/
- https://www.koyfin.com/help/faq/can-i-download-data/
- https://www.koyfin.com/help/faq/where-do-you-get-your-data/

### Zacks — дешёвый manual revisions lens

Zacks Premium публично стоит **$249/year**. Detailed estimates pages показывают именно нужные элементы: Agreement (up/down revisions) и Magnitude (consensus now vs 7/30/60/90 days), а также surprises/ESP.

Но их performance claims — **vendor claims**, не мои доказанные expected returns. Я не нашёл документированного retail API, на котором разумно строить Consilium. Использовать как UI/research source — да; строить scraper подписного сайта — нет.

Источники:
- https://www.zacks.com/products/index.php/research/screening/tracks/
- пример detailed estimates: https://www.zacks.com/stock/quote/AMZN/detailed-estimates

### Finnhub — наиболее интересный недорогой API-кандидат

Официальный Stock Estimates Estimate-1 plan сейчас указан как **$75/month/market**, personal use, и включает 10 лет EPS surprises/estimates и real-time upgrade/downgrade history according to plan description.

Это уже похоже на источник для автоматизации Floor 1.

Но важное ограничение: из публичной документации нельзя автоматически сделать вывод, что поле «historical EPS estimate» является **полным point-in-time vintage consensus на произвольную прошлую дату**. Исторический estimate series и historical *vintage snapshots* — разные продукты.

Поэтому перед любым backtest нужен trial-contract test: взять один fiscal period и проверить, можно ли получить consensus таким, каким он был, например, за 90/60/30 дней до earnings, а не только текущую/последнюю historical запись.

Источник:
- https://finnhub.io/pricing-stock-estimates

### LSEG I/B/E/S и FactSet — технически правильный ответ, экономически другой класс

LSEG I/B/E/S имеет детальные/consensus estimates, long history, API/FTP и прямо предлагает point-in-time estimates data. LSEG описывает PIT estimates coverage с историей на десятилетия. FactSet Consensus Estimates DataFeed также имеет current и historical snapshots, глобально с 1999.

Это именно те источники, с которыми можно делать институционально честный historical revisions backtest.

Но оба — sales/licensed institutional data products без простого retail sticker price на страницах продукта. Для соло-проекта я бы **сначала запросил quote, но не делал архитектуру зависимой от их покупки**.

Источники:
- https://www.lseg.com/en/data-analytics/financial-data/company-data/ibes-estimates
- https://www.lseg.com/en/data-analytics/asset-management-solutions/portfolio-management/backtest-your-portfolio-performance
- https://insight.factset.com/resources/factset-consensus-estimates-datafeed

### MacroMicro / Citi ERI

MacroMicro действительно публикует Citi Earnings Revision Index; определение соответствует `share upgrades - share downgrades` weekly. Это пригодно как **market-context series**, но не заменяет individual-stock revision feed.

Я НЕ смог независимо подтвердить как академический факт конкретные числа из документа Round 5 про «25 недель» и «8 месяцев». До получения первоисточника Morgan Stanley/Citi эти lead-lag значения надо считать **гипотезой/strategist claim**, а не контрактом системы.

Источник определения ERI:
- https://en.macromicro.me/charts/55746/us-eu-jp-citi-earnings-revision-index

## Надо ли принимать forward-only Floor 1?

### **ДА. И это честнее, чем псевдо-backtest на восстановленных сегодняшними средствами estimates.**

Я предлагаю prospective protocol:

### До первого snapshot

1. Freeze universe для первого исследования — например current NDX constituents на дату старта, **не менять cohort первые 13 недель**; новые index additions можно записывать отдельно, но не включать в primary cohort.
2. Freeze поля карточки и exact transforms.
3. Freeze shortlist rule. Никаких ручных «этот всё равно интересный» внутри primary sample.
4. Freeze source/provider и basis definitions.
5. Freeze evaluation horizons: **13 недель primary, 26 недель secondary**. Revisions — более короткий signal, чем 3–5-летний valuation thesis.

### Каждую неделю

- snapshot всех ~100, а не только понравившихся;
- immutable CSV/JSON;
- timestamp до того, как оператор смотрит результаты;
- source/version/coverage;
- missing fields остаются missing;
- calculated shortlist записывается автоматически или по заранее фиксированному чек-листу;
- после snapshot можно принимать человеческое решение, но оно записывается отдельно.

### Что измерять

- coverage rate;
- stability/reproducibility;
- Spearman rank IC, если есть rank;
- top vs bottom group total return;
- top group vs NDX and sector-adjusted benchmark;
- turnover;
- сколько кандидатов Floor 2 реально отверг.

### Важная граница честности

**За первый месяц нельзя доказать alpha Floor 1.** Четыре weekly observations — это не evidence.

За месяц можно доказать только:

> data workflow устойчив, coverage высокий, signal фиксируется до цены будущего периода, оператор не может post-hoc менять правила.

Первый 13-week outcome даст диагностический результат. Для сколько-нибудь серьёзного claims понадобится минимум год prospective history, и даже он останется exploratory из-за малого числа независимых market regimes.

### Мой конкретный совет по данным

**Не покупать I/B/E/S/FactSet сразу и не писать scraper.**

Сначала:

1. Koyfin/Zacks manual trial для оператора;
2. если Floor 1 реально используется еженедельно — протестировать Finnhub/FMP documented API;
3. начать собственные weekly consensus snapshots с сегодняшнего дня;
4. только если через 3–6 месяцев этот слой реально меняет решения — решать, нужна ли дорогая historical PIT license.

---

# В-3.1.3. Revisions philosophy vs price-of-requirements philosophy

## Позиция: **СОВМЕСТИМЫ, если это последовательные фильтры, а не два голосующих агента. При конфликте — НОВУЮ позицию не открывать.**

Это главный философский арбитраж.

Floor 1 и Floor 2 отвечают на разные вопросы:

### Floor 1

> **Где сейчас меняется информационное ожидание в благоприятную сторону?**

Это attention allocation / timing of research.

### Floor 2

> **Даже если ожидания улучшаются, сколько уже заложено в цену и насколько хрупким должен быть будущий сценарий?**

Это price/risk discipline.

Они не являются противоположными школами. Это две разные координаты.

## Evidence по revisions

Независимая академическая литература поддерживает существование earnings/forecast-revision momentum как феномена. Но это не лицензия принять vendor backtests как expected return Consilium.

- Chan/Jegadeesh/Lakonishok (1996): earnings surprise и price momentum имели independent future-return drift; analysts реагировали медленно.
- Jung/Keeley/Ronen (2019): revisions были предсказуемы, implementable abnormal return был сильнее при низком coverage.
- PEAD literature показывает долговременную аномалию, но transaction costs и market evolution уменьшают exploitable profits.

Для NDX mega-caps я бы ожидал **меньший**, а не больший informational edge от простого surprise chasing, потому что analyst coverage и liquidity огромны.

## Как записать conflict rule заранее

### Для НОВОЙ позиции

**Floor 1 negative** → `NOT_NOMINATED`; Floor 2 не обязан даже запускаться.

**Floor 1 positive/constructive** → кандидат допускается на Floor 2; это НЕ buy signal.

**Floor 2 показывает assumptions outside registered feasible envelope / severe regime risk / unresolved data conflict** → **NO INITIATION**, даже если revisions сильны.

**Floor 1 positive + Floor 2 acceptable** → `ELIGIBLE_FOR_OPERATOR_DECISION`, но не auto-buy.

### Если Floor 1 negative, а Floor 2 «очень дёшево»

По умолчанию **NO INITIATION / WATCH** в этой стратегии.

Почему? Иначе оператор каждый раз сможет сказать: «зато дешёво» и сломает логику discovery layer.

Если хочется ловить bottoms до revisions turn, это отдельная **Contrarian lane** с отдельным preregistered rule. Нельзя тихо смешивать её с revisions strategy.

### Цена такого правила

Да, система пропустит часть быстрых bottoms, когда valuation уже привлекательна, а analyst revisions ещё падают. Это осознанная цена. Она лучше, чем centaur, который всегда может объяснить любую сделку одним из двух этажей.

---

# В-3.1.4. Защита ERB/regime layer от «ручки»

## Позиция: **в первой версии ERB рынка НЕ должен менять действия вообще. Только context.**

Я не поддерживаю сейчас правило:

> «индекс растёт, ERB падает → заморозить новые покупки».

Это уже отдельная market-timing strategy. У неё нет validation в вашем проекте, а оператор получит очень мощную ручку для изменения exposure именно в эмоциональные периоды.

### V1

Показывать:

```text
MARKET_EXPECTATIONS_CONTEXT
ERI level / trend / 12w MA (если источник даёт)
index trend
breadth divergence: yes/no
```

Но **никакого hard gate**.

### Если позже ERB докажет полезность prospective data

Он может влиять только на **risk budget**, а не на economics компании.

Например:

- Normal: стандартный max new-position risk budget.
- Caution: максимум 50–75% стандартного initial position size / меньше новых initiation.
- Severe: новые initiation требуют дополнительного human review.

Но ERB никогда не должен:

- повышать допустимый multiple;
- снижать required evidence;
- менять normalization;
- превращать RED Floor 2 в green.

### Governance

- regime state пересчитывается в фиксированное время раз в неделю;
- изменение действует только с следующего trading session/week;
- operator override разрешён только как **отдельное documented override**, не как изменение правила;
- сами правила могут меняться только на scheduled quarterly governance date и вступать в силу с лагом, например 4 недели;
- никаких ретроактивных пересчётов старых snapshots новой логикой в primary record.

Ключевой принцип: **market regime может только ужесточать portfolio risk, но не улучшать оценку конкретной компании.**

---

# В-3.2.1. Перепрофилировать Consilium в глубокий разбор одного имени?

## Позиция: **ДА. Это моя основная рекомендация Round 5.**

Именно в этом режиме strengths проекта совпадают с task economics:

- 1–3 часа на сложное имя приемлемы;
- отказ допустим и информативен;
- filing-level fallback можно запускать только когда нужен;
- sector-specific nuance можно включать вручную/модульно;
- не нужен historical PIT universe для ежедневной работы;
- не нужен claim, что rank имеет alpha;
- MU/INTC становятся валидными regression/pilot cases, а не попыткой доказать stock picker.

Я бы сменил название продуктовой функции с «valuation/ranking» на:

> **Pre-Purchase Dossier / Thesis Stress Test.**

Он должен пытаться **сломать** покупку, а не дать ей target price.

---

# В-3.2.2. Что является ядром, а что балластом

## Ядро — оставить и усилить

### 1. Provenance / fail-closed data layer

- `edgartools`/filing-level parser substrate;
- собственный semantic validation adapter;
- accession + filed_at + period + unit + share basis;
- raw vs transformed value;
- named refusal.

### 2. 5–10y economic decomposition

- revenue;
- operating income/margin;
- NI/EPS;
- OCF/FCF;
- share count/SBC/buybacks;
- debt/cash;
- ROIC/ROIIC where defensible.

### 3. Narrow quarterly layer

Не вся отчётность. Минимум:

- revenue;
- operating income/margin;
- OCF/capex/FCF where meaningful;
- share count;
- event dates.

### 4. Regime analysis

- cycle peak/trough;
- margin break;
- cash conversion deterioration;
- buyback-driven EPS;
- balance-sheet deterioration;
- named corporate actions.

Не обязательно всё делать binary guard.

### 5. Reverse scenario surface

Полный FCFF bridge / independent oracle.

Не один required growth, а sensitivity across:

- margin;
- growth;
- duration;
- return/reinvestment;
- terminal/multiple scenario.

### 6. Consensus side-by-side

Только как observed external expectation, не автоматическая истина.

### 7. Decision journal

Обязательные поля:

- дата;
- цена;
- thesis;
- какие условия должны быть true;
- biggest disconfirming risks;
- source snapshots;
- почему оператор всё-таки купил/не купил;
- next review triggers.

Это даст проекту собственную evidence base намного быстрее, чем попытка доказать alpha универсального rank.

## Балласт — удалить из active path / заморозить

- BUY/NO-BUY engine;
- hard 12% gate;
- scalar `required growth - historical growth` rank;
- единственный terminal PE через `min(history, formula)`;
- массовый historical runner как production capability;
- point-in-time constituent infrastructure как ежедневный product requirement;
- PWFV/старые price alerts, если они зависят от старой valuation model;
- generic custom EDGAR parser вне Consilium-specific invariants;
- multi-agent valuation consensus;
- peer imputation;
- сложный publication layer для 100 имён;
- попытка выдавать model numbers для неподдержанных archetypes.

### Что НЕ удалять из репозитория

Historical test/pilots/old runners должны остаться как **append-only regression corpus и история ошибок**, но не как центр новой архитектуры.

---

# В-3.2.3. Consensus рядом с нашим требованием

## Позиция: **ДА, но consensus — отдельное наблюдение с provenance и basis, не input по умолчанию. Missing остаётся missing.**

Схема должна хранить минимум:

```text
source
snapshot_timestamp
fiscal_period
metric
basis: GAAP / adjusted / provider-defined
consensus_mean_or_median
high
low
analyst_count
dispersion
value_30d_ago
value_90d_ago
```

### Критическая проблема basis

Самая опасная ошибка здесь — сравнить:

> SEC GAAP EPS requirement

с

> vendor adjusted/non-GAAP consensus EPS

и назвать разницу «рынок ожидает X».

Если basis не reconciled:

`CONSENSUS_NOT_COMPARABLE_BASIS`

и оба числа показываются рядом без арифметического spread.

Для многих компаний проще и чище сравнивать сначала:

- revenue;
- operating margin/EBIT where definitions align;
- FCF if provider definition known;

а EPS — только после basis check.

### Missing rule

Да:

`CONSENSUS_UNAVAILABLE(reason)`

Никакого:

- LLM estimate;
- sector median;
- last known consensus beyond staleness limit;
- midpoint analyst high/low when consensus absent.

LLM может **объяснить** найденное расхождение, но не создавать missing number.

---

# В-3.3. Порядок строительства, один месяц, один тест, альтернатива

## Позиция: **не строить Floor 1 с нуля первым. Сначала доказать workflow готовыми средствами, затем перепрофилировать Floor 2.**

Действующий STOP BUILD я не снимаю — это решение оператора. Ниже порядок **если оператор отдельным решением разрешит следующий experiment**.

## Шаг 0 — не писать production code

Зафиксировать новый scope:

> Floor 1 = external/manual discovery experiment;
> Floor 2 = Consilium pre-purchase dossier;
> никаких alpha claims и auto-BUY.

## Неделя 1 — Floor 1 без собственной разработки

Использовать Koyfin Plus / Zacks trial или аналог и сделать карточку вручную для current NDX.

Цель: понять, **помогает ли сама информация оператору**, прежде чем автоматизировать её.

Одновременно создать immutable weekly snapshot format. Если vendor запрещает export estimates, ключевые поля можно заносить в небольшой research ledger вручную для shortlisted names; для всего universe лучше trial documented API (Finnhub/FMP) только после проверки лицензии/семантики.

## Недели 1–4 — prospective paper trail

Четыре frozen weekly snapshots, одинаковые правила, весь cohort.

Не менять формулу после того, как увидели week 1.

## Неделя 2 — перепрофилировать Floor 2 минимально

Не «переписать Consilium».

Сделать один dossier template и `edgartools` adapter/fallback на существующих goldens:

- MU;
- INTC;
- META;
- GOOG.

Acceptance: zero invented values, clear provenance, ручной dossier ≤2 часов для обычного имени.

## Недели 3–4 — 3–4 живых dossiers

Каждую неделю брать одно имя, nominated Floor 1, и проходить Floor 2 **до решения оператора**.

Записывать, что Floor 2 изменил:

- ничего;
- снизил уверенность;
- нашёл data gap;
- нашёл regime/price problem;
- фактически остановил покупку.

## Что можно доказать за один месяц

Не alpha.

**Единственный честный one-month test:**

> **Prospective Funnel Viability Test.** Может ли оператор четыре недели подряд получать reproducible shortlist без ручного ремонта data pipeline и доводить 3–4 кандидата до полного dossier ≤2 часов/имя, при этом все inputs имеют provenance, а правила не меняются post-hoc?

### PASS criteria, которые я бы зафиксировал

- ≥95% Floor-1 required-field coverage по cohort или named provider limitation;
- weekly refresh ≤30 минут operator time после настройки;
- 0 fabricated/substituted missing values;
- минимум 3 complete Floor-2 dossiers;
- median dossier time ≤2 часа;
- META/GOOG больше не требуют patch production parser внутри analysis session;
- каждый dossier заканчивается explicit `what must be true / what would falsify thesis`;
- ни одной post-hoc правки signal rule внутри месяца.

Если этот тест не проходит — **не автоматизировать дальше.** Использовать готовые research tools + manual checklist.

### Когда появится первый predictive test

Primary forward horizon Floor 1 я бы поставил 13 недель. Первый cohort outcome тогда появится через квартал. Более серьёзное суждение — после 12 месяцев prospective records.

## Альтернатива всей двухэтажной конструкции №1 — Event-Driven Research Queue

Я считаю её даже сильнее weekly 100-name radar для соло-оператора.

Не сканировать сто компаний одинаково каждую неделю. Пусть готовый provider отправляет событие:

- крупный positive/negative estimate revision;
- earnings beat/miss + guidance change;
- значимое price drawdown/new high;
- material filing/corporate event.

Событие создаёт **research ticket**. Только 5–10 наиболее сильных tickets проходят короткую карточку, 1–3 — deep Consilium dossier.

Плюсы:

- меньше data plumbing;
- анализ синхронизирован с появлением новой информации;
- меньше false precision от ranking всех 100;
- существенно дешевле operator time;
- естественный prospective journal.

## Альтернатива №2 — Portfolio-first active sleeve

Если конечная цель — не доказать фактор, а улучшить личный результат относительно QQQ, можно сделать QQQ/core portfolio базой, а Consilium использовать только для ограниченного active sleeve. Тогда правильный вопрос проекта:

> «Добавили ли 5–10 активных решений value относительно того, чтобы ничего не делать?»

Это гораздо легче измерить через decision journal, чем доказать universal alpha rank.

---

# ПЕРЕСМОТР МОЕГО ROUND 4 ПОСЛЕ ROUND 5

Round 5 заставляет меня изменить несколько собственных рекомендаций.

## 1. Отзываю рекомендацию строить два массовых внутренних ranking output

В Round 4 я предлагал держать по universe два представления:

- Expectations Map;
- TSR Map;

и дать Test #2 решить, какой rank лучше.

**Теперь я это не рекомендую.** Оба maps полезны **внутри one-name dossier**, но не оправдывают строительство mass ranking/validation infrastructure.

Причина: identification problem reverse valuation + data burden + отсутствие дешёвого честного PIT revisions history делают experiment слишком дорогим для личной задачи.

## 2. Historical multiple PIT series — больше не critical-path product

В Round 4 я рекомендовал создать отдельный market-history band P25/median/P75.

Концептуально совет остаётся правильным. Но при выборе 2.3(б) **не надо строить универсальную 100-name historical multiple database сейчас**.

Для deep-dive name:

- брать licensed/vendor valuation history или вручную собранную небольшую history;
- сохранять provenance;
- normalizing denominator where needed;
- если history нет — `MARKET_HISTORY_BAND_UNAVAILABLE`.

Fundamental steady-state multiple не должен masquerade как historical normal.

## 3. Test #2 mass historical ranking — отменить/отложить

Я больше не считаю его следующим рациональным experiment.

Вместо него:

- Floor 1 prospective paper trail;
- Floor 2 historical regression goldens + live dossiers;
- decision journal.

Возвращаться к PIT rank validation можно только если через несколько месяцев prospective evidence показывает, что собственный ranking действительно нужен.

## 4. Моя рекомендация по `edgartools` усилилась

Round 5/erratum показали, что custom generic XBRL plumbing — главный measured sink времени. `edgartools` как parser + own semantic/provenance layer теперь является не «хорошей идеей», а **предпочтительной архитектурой**.

## 5. Full FCFF/reverse scenario и TSR decomposition остаются

Но они переходят из mass score в one-name explanation.

---

# ОТВЕТЫ НА ERRATUM 2026-08-11

## Erratum: Б2-bis — нужен ли отдельный контракт истории multiples?

### Позиция: **ДА, если historical band используется. Но после выбора 2.3(б) НЕ строить mass product сейчас.**

Исправление подтверждает: `pe_hist_median` отсутствовал 55/55 и `min()` историческим аргументом вообще не связывал. Значит market-history band в Round 4 был предложением новой data capability, а не использованием уже существующего ряда.

Если он нужен для конкретного dossier, контракт обязан хранить:

- observation date;
- price/EV date;
- denominator period;
- filing cutoff;
- normalized vs raw denominator;
- share basis;
- net debt basis;
- source;
- refusal.

Нельзя строить historical P/E series сегодняшним EPS по старым ценам.

До появления ряда:

`MARKET_HISTORY_BAND_UNAVAILABLE`

а fundamental multiple показывать отдельно как model reference.

### MELI 1.09x

Этот кейс усиливает мой вывод: не надо добавлять произвольный floor типа `PE >= 8`. Формула должна отказывать/помечать terminal economics unstable, если малая вариация ROE/g даёт экономически бессмысленный multiple. Это domain problem inputs, а не cosmetic PE-bound.

---

## Erratum: META — filing-level XBRL или более дешёвое решение?

### Позиция: **filing-level XBRL нужен как targeted fallback; `edgartools` — разумный способ не писать parser самим.**

META — сильный пример того, что данные существуют в filing, но агрегированный Company Facts path не предоставляет нужный current-share witness в той форме, которая требуется вашему basis guard.

Рекомендованная схема:

```text
fast path: standardized/company-level facts
          ↓ semantic validation
если missing / dimensional / conflict
          ↓
filing-level XBRL via edgartools
          ↓
own semantic aggregation + provenance
```

Собственными остаются decisions, **как** агрегировать факты. GOOG уже показал, что class-level diluted denominators нельзя автоматически суммировать: доступ к dimension — не то же самое, что экономическая семантика.

META и GOOG должны стать обязательными regression goldens нового adapter.

---

## Erratum: В3 — foreign/multiclass после исправленных чисел

### Позиция: **не исключать domestic multiclass из universe из-за слабости parser. 20-F/40-F — отдельный capability tier, а не экономическая неприменимость.**

GOOG/META — обязательные для поддерживаемого US mega-cap workflow. Если parser их не читает, это defect/capability gap.

Foreign filers можно временно маркировать:

`UNSUPPORTED_FILING_REGIME_20F/40F`

пока слой не реализован. Но claim scope должен быть честным: если validation сделана только на 10-K domestic issuers, нельзя писать «validated on Nasdaq-100».

### Дополнительная поправка к самому erratum

Фраза erratum «настоящий иностранный эмитент здесь только NVO» конфликтует с вашим же `Reports/diag_edgar_gaps.md`: на релевантных исторических датах SHOP подавал 40-F, DLO и NBIS — 20-F; GOOG — 10-K.

Корректная формулировка:

> **в class-34 есть foreign issuers, но foreign status НЕ является причиной этого класса отказа.**

Это важно поправить, иначе следующий документ снова создаст ложную causal label.

---

## Мой собственный пропуск в Round 4

Я не заметил расхождение исходной сводной таблицы причин отказов с сырым `RESULTS_test1.csv`. Я правильно оспорил claim «ranking ability присутствует» и независимо не согласился исключать GOOG из-за parser weakness, но **не пересчитал 120 refusals по машинному артефакту**, хотя проект просил проверять такие утверждения.

Это была недоделанная проверка с моей стороны. Мера проекта «генерировать refusal summary тем же скриптом, а не писать прозой» — правильная.

---

# ФИНАЛЬНАЯ РЕКОМЕНДАЦИЯ ROUND 5

## **STOP BUILD массового Consilium radar. CONTINUE EXPERIMENT с существенно более узким продуктом.**

Если оператор снимает текущий STOP BUILD отдельным решением, я рекомендую разрешить **не строительство новой системы**, а месячный experiment:

> **готовый revisions/fundamentals discovery → 3–4 Consilium dossiers → immutable decision journal.**

После месяца спросить не «сколько PR мы закрыли?», а:

1. Сократилось ли время от идеи до понятного тезиса?
2. Нашёл ли Floor 2 хотя бы один material fact/assumption, который изменил бы реальное решение?
3. Можно ли повторить dossier без ручной починки data parser?
4. Есть ли operator behavior, которое journal делает более дисциплинированным?

Если ответ в основном «нет» — **остановить собственную разработку и оставить checklist + готовые инструменты**.

Если «да» — автоматизировать только те шаги, которые реально повторялись в этих dossiers.

Это reverses прежнюю логику проекта:

> **не строить capabilities, а потом искать им применение; сначала повторить полезный workflow вручную, затем автоматизировать только доказанный bottleneck.**

Для текущего масштаба оператора это, на мой взгляд, лучший шанс получить инструмент, который реально улучшает инвестиционные решения, а не ещё одну исследовательскую платформу, требующую собственной команды данных.
