---
author: CHATGPT
date: 2026-08-12
status: external review — round 6
answers: mailbox/ROUND6_2026-08-12_MARKET_REGIME_AND_MONITORING.md
relates_to: mailbox/DECISION_2026-08-12_ROUND5_AND_EXPERIMENT.md, mailbox/ERRATUM_2026-08-12_02_AUDITORS.md
---

# ROUND 6 REVIEW — market regime + watchlist monitoring

## Короткий вердикт

Архитектуру, принятую после Round 5, **поддерживаю**: массовый Consilium-radar не строить; этаж 1 — дешёвый discovery, этаж 2 — глубокое досье одного имени, этаж 3 — журнал решений.

По режиму рынка моя рекомендация:

> **Режим не должен менять оценку бизнеса, terminal multiple, margin assumptions или требуемую доходность. Он должен менять только execution risk: размер первого транша и скорость набора позиции.**

Это компромисс между «режим только строка контекста» и «режим меняет discount rate».

Панель я бы сократил до **четырёх голосующих независимых осей**:

1. earnings revisions — Citi US Earnings Revision Index (ERI);
2. volatility — VIX относительно своей 50-дневной средней; term structure VIX/VIX3M как stress-подсказка;
3. breadth — доля S&P 500 выше 200-дневной средней (S5TH);
4. credit — ICE BofA US High Yield OAS.

**CNN Fear & Greed оставить пятым визуальным тайлом, но НЕ давать ему голос.** Он уже складывается из momentum, breadth, put/call, VIX, junk-bond demand и safe-haven demand. Если дать ему ещё один голос рядом с VIX/breadth/credit, мы дважды посчитаем одни и те же сигналы.

---

# Несогласие с постановкой / одно возражение к принятому решению Round 5

С общей постановкой Round 6 согласен. Есть одно важное возражение к пункту эксперимента в `DECISION_2026-08-12_ROUND5_AND_EXPERIMENT.md`: **«бэктест панели режима рынка на публичной истории» нельзя делать hard-gate в буквальной форме для всей панели.**

Причина — data availability/licensing:

- официальный VIX имеет бесплатную daily history с 1990 года;
- FRED с апреля 2026 ограничил публичную историю ICE BofA OAS тремя годами;
- S5TH бесплатно виден на TradingView/Investing.com как длинный график, но бесплатный clean CSV history я не нашёл;
- Citi ERI виден через MacroMicro, но полноценный data access/экспорт регулируется их планами; API стоит институционально дорого;
- CNN не публикует официальный downloadable historical dataset, а сама методика недавно меняла расчёт breadth-компонента.

Поэтому честная замена gate:

> **historical sanity-check на тех компонентах, где история воспроизводима + полностью замороженный prospective regime log с первого дня эксперимента.**

Не надо подменять отсутствие чистой истории community-scrape'ом и затем называть это бэктестом.

Поправку `ERRATUM_2026-08-12_02_AUDITORS.md` принимаю; новых возражений к ней нет.

---

# А1. Состав панели

## Позиция: **4 core-индикатора + 1 context-only; остальное убрать**

### Core 1 — Citi US Earnings Revision Index (ERI)

**Оставить. Это самый важный компонент, которого нет в обычных price/sentiment панелях.**

MacroMicro описывает Citi ERI как:

> доля компаний с повышением EPS-прогнозов минус доля компаний с понижением прогнозов по сравнению с прошлой неделей.

Естественная нулевая граница уже заложена в самом индикаторе:

- `ERI > 0` — upgrades преобладают;
- `ERI < 0` — downgrades преобладают.

Почему нужен: VIX/credit/breadth рассказывают, что **делает рынок**, а ERI — что происходит с **ожиданиями прибыли**, то есть добавляет независимую экономическую ось.

Источник и методика:
- MacroMicro / Citi ERI: https://en.macromicro.me/charts/55746/us-eu-jp-citi-earnings-revision-index
- ERI vs S&P 500 EPS: https://en.macromicro.me/charts/55748/us-citi-earnings-rervision-vs-sp500-eps

Цена/доступ: публичная страница существует; MacroMicro Prime сейчас указан как **$25/мес или $250/год**, Max — $30/мес или $280/год. Их API Essential — **$5,000/год**, поэтому API для Consilium сейчас экономически бессмысленен.

Pricing: https://en.macromicro.me/subscribe

**Практическое решение:** во время 4-недельного эксперимента платить только ради ERI не надо. Если график доступен в текущем публичном режиме — смотреть. Если конкретные live values закрыты — поле `ERI_UNAVAILABLE`, а не покупка подписки ради одного тайла.

---

### Core 2 — VIX trend; term structure как stress-check

**Оставить, но не превращать VIX в “страх = покупать / спокойствие = продавать”.**

Для голосования я использовал бы не произвольные уровни 20/30, а относительную конструкцию, близкую к той, которую использует CNN:

- VIX ниже своей 50-дневной средней → спокойствие/снижение волатильности;
- VIX выше 50-дневной → рост risk aversion.

Отдельной строкой показывать term structure:

- `VIX < VIX3M` — обычная восходящая структура;
- `VIX > VIX3M` — front-end volatility дороже, stress/backwardation-like condition.

Cboe прямо публикует текущую VIX term structure и позволяет выбрать историческую дату. Официальная история VIX доступна бесплатно с 1990 года.

Источники:
- Cboe VIX term structure: https://www.cboe.com/tradable-products/vix/term-structure
- Cboe VIX historical data: https://www.cboe.com/tradable_products/vix/vix_historical_data

**Почему term structure не отдельный голос:** это та же volatility-family. Давать VIX trend и VIX/VIX3M по одному голосу означало бы удвоить одну ось.

---

### Core 3 — breadth: S&P 500 Stocks Above 200-Day Average (S5TH)

**Оставить.**

Для tech-heavy watchlist особенно важно отличать «индекс растёт за счёт 5 мегакэпов» от широкого risk-on.

Естественная граница:

- `S5TH >= 50%` — большинство компонентов S&P 500 выше долгосрочного тренда;
- `< 50%` — большинство ниже.

Не нужно делать из 70% “перегрето” и 20% “обязательно покупать”. Эти уровни могут быть интересны как экстремумы, но для механического режима достаточно 50%.

Бесплатные источники:
- TradingView `S5TH`: https://www.tradingview.com/symbols/INDEX-S5TH/
- Investing.com S5TH: https://www.investing.com/indices/sp-500-stocks-above-200-day-average

TradingView показывает 1Y/5Y/10Y/all-time chart; Investing.com даёт текущий free live/delayed view.

---

### Core 4 — credit: ICE BofA US High Yield OAS

**Оставить.**

Это независимая от equity-options ось: готовность кредитного рынка финансировать риск.

Для простоты не вводил бы абсолютный “опасный spread” вроде 500 bps. Денежные условия меняются по эпохам. Для weekly regime достаточно направления за четыре недели:

- OAS сейчас ниже, чем 20 торговых дней назад → credit tightening / risk support;
- выше → spread widening / risk deterioration.

Источник:
- FRED, ICE BofA US High Yield Index Option-Adjusted Spread (`BAMLH0A0HYM2`): https://fred.stlouisfed.org/series/BAMLH0A0HYM2

Важное ограничение: **с апреля 2026 FRED оставляет для этой серии только три года публичных наблюдений.** Это уже указано самим FRED. Старую длинную историю теперь надо получать у source/vendor.

---

### Context-only — CNN Fear & Greed

**Оставить в панели визуально, исключить из механического score.**

Причина не в том, что индекс плох. Наоборот, он удобен человеку: одно число 0–100.

Но CNN сам говорит, что индекс равновесно объединяет семь компонентов:

1. market momentum;
2. 52-week highs/lows;
3. breadth;
4. put/call;
5. VIX;
6. safe-haven demand;
7. junk-bond demand.

Источник/методика:
- CNN Fear & Greed: https://edition-prod-cf.sitemirror.cnn.com/markets/fear-and-greed

CNN также прямо отмечает недавнее изменение расчёта Stock Price Breadth. То есть это **vendor composite, который может менять методику**.

Поэтому использовать так:

`CNN F&G = human-readable sanity tile; weight = 0`.

Если CNN показывает Extreme Greed, а наши четыре core оси говорят Mixed — это не пятый голос, а повод увидеть расхождение.

---

## Что я вычёркиваю из core panel

### NAAIM Exposure Index — вычёркиваю из-за стоимости

С 1 августа 2026 NAAIM переводит индекс на subscription model. Для non-member доступ сейчас указан как **$600/год**, API partner — $1,500/год. Сам NAAIM подчёркивает, что индекс не является predictive tool, а отражает фактическую экспозицию active managers.

Источники:
- https://naaim.org/programs/naaim-exposure-index/
- subscription pricing: https://members.naaim.org/ap/Membership/Application/GrZAe6L1

Для бюджета проекта это не нужно.

### AAII sentiment — не нужен в core

Опрос мнений retail-инвесторов добавляет ещё один sentiment-градусник рядом с CNN/VIX, но мало добавляет к earnings/credit/breadth.

### Forward P/E S&P 500 — не regime, а valuation context

Полезно видеть отдельно в market dashboard, но не использовать для bull/bear vote.

### Put/call — не нужен отдельно

Уже входит в CNN и сильно перекрывается с volatility/sentiment. Не добавлять ещё один шумный краткосрочный голос.

---

# А2. Механическое чтение панели

## Позиция: **3 режима, 4 независимых голоса; CNN не голосует**

Каждый core-индикатор даёт `+1 / -1 / NA`:

| Ось | +1 | -1 | Источник |
|---|---|---|---|
| Earnings revisions | Citi ERI > 0 | Citi ERI < 0 | MacroMicro/Citi |
| Volatility | VIX < 50DMA | VIX > 50DMA | Cboe |
| Breadth | S5TH ≥ 50% | S5TH < 50% | TradingView/Investing |
| Credit | HY OAS ≤ уровень 20 торговых дней назад | HY OAS > уровень 20 торговых дней назад | FRED |

Если данных нет, голос = `NA`, не ноль и не “нейтрально”.

Считать:

```text
R = (sum valid votes) / N_valid
```

Минимум `N_valid = 3`. Если меньше:

`REGIME_INSUFFICIENT_DATA`.

### Режимы

| R | Режим | Чтение |
|---|---|---|
| `R >= +0.50` | **RISK_ON** | большинство независимых осей поддерживают риск |
| `-0.50 < R < +0.50` | **MIXED** | сигналы противоречат друг другу |
| `R <= -0.50` | **RISK_OFF** | большинство осей ухудшаются |

### Stress tag

Не новый режим, а дополнительная метка:

`VOL_STRESS = TRUE`, если текущий `VIX > VIX3M`.

Она не добавляет второй volatility vote.

### Что делать при противоречии

**Ничего не “арбитрировать глазами”.**

Два положительных + два отрицательных → `R=0` → `MIXED`.

Три против одного → `R=±0.5` → соответствующий risk-on/risk-off.

CNN Fear & Greed не ломает tie.

Это важно: оператор не получает ручку «ну CNN сейчас 72, поэтому я считаю рынок всё-таки бычьим».

---

# А3. Как режим влияет на действия

## Позиция: **выбираю (ii): режим меняет risk budget / размер первого транша, но НЕ оценку**

Это мой компромисс между двумя позициями Round 5.

### Инварианты

Режим **НЕ меняет**:

- revenue/margin assumptions;
- terminal multiple scenarios;
- DCF/reverse-DCF;
- 12–16% scenario surface;
- fair/required business economics;
- вывод Floor 2 о том, находится ли цена внутри допустимого диапазона.

В этом согласен с архитектором:

> `market mood != economics of the company`.

Но market mood **меняет риск исполнения**: correlation, liquidity, gap risk, вероятность того, что даже хороший stock временно упадёт вместе с рынком.

### Механическое правило

Сначала должен существовать заранее определённый **standard initial tranche** — базовый размер первой покупки по portfolio policy. Сам regime rule его не определяет.

Далее:

| Режим | Максимальный размер первого транша |
|---|---:|
| RISK_ON | `1.00 × standard starter` |
| MIXED | `0.75 × standard starter` |
| RISK_OFF | `0.50 × standard starter` |
| RISK_OFF + `VOL_STRESS` | `0.25 × standard starter` |

Это **максимум**, а не указание обязательно купить столько.

### Набор позиции

- новый транш разрешён только на очередном scheduled review;
- оба этажа по-прежнему должны давать разрешение;
- размер следующего транша определяется **текущим** regime multiplier;
- regime никогда не может превратить отрицательный Floor 2 в покупку;
- внутри 4-недельного эксперимента ручные overrides этого правила запрещены.

### Почему не менять требуемую доходность

Если при Risk Off увеличить required return с 12% до 15%, одна и та же NVDA внезапно “станет экономически другой” только потому, что VIX вырос. Это смешивает:

- качество/цену бизнеса;
- portfolio risk management.

Гораздо прозрачнее оставить valuation surface неизменной и управлять входом через размер.

### Почему не оставить regime чистым контекстом

Тогда Round 6 не меняет поведение вообще. Если оператор хочет не оценивать компанию в вакууме, режим должен иметь **один заранее ограниченный канал влияния**. Position staging — самый чистый канал.

---

# А4. Что реально можно проверить задним числом

## Позиция: **полный panel-backtest бесплатно и audit-grade сейчас недоступен**

| Индикатор | Публичная история | Пригодность для honest backtest |
|---|---|---|
| VIX | Cboe daily 1990–present | **Да, хорошая** |
| VIX term structure / VIX3M | текущая и point-in-time lookup у Cboe; bulk historical index data не столь свободна | **Частично** |
| HY OAS | FRED daily, но с апреля 2026 public window = 3 года | **Да для недавнего периода, нет для длинного цикла** |
| S5TH | TradingView показывает 1Y/5Y/10Y/all-time chart | **Хорошо для visual event study; clean free CSV не подтверждён** |
| Citi ERI | MacroMicro chart / paid tooling | **Проверяем на платформе, но не zero-cost reproducible data pipeline** |
| CNN Fear & Greed | official current/timeline; official downloadable history не публикуется | **Нет для audit-grade backtest** |

Источники:
- VIX history: https://www.cboe.com/tradable_products/vix/vix_historical_data
- Cboe term structure: https://www.cboe.com/tradable-products/vix/term-structure
- HY OAS: https://fred.stlouisfed.org/series/BAMLH0A0HYM2
- S5TH: https://www.tradingview.com/symbols/INDEX-S5TH/
- Citi ERI: https://en.macromicro.me/charts/55746/us-eu-jp-citi-earnings-revision-index
- CNN: https://edition-prod-cf.sitemirror.cnn.com/markets/fear-and-greed

### Что я предлагаю вместо псевдобэктеста

#### Test A — reproducible subset

На VIX + доступном HY OAS + собственных Tiingo SPY/QQQ returns проверить:

- regime-date;
- forward S&P/QQQ total return 13 недель;
- forward return 26 недель;
- max drawdown следующие 13 недель.

Не заявлять predictive power; цель — убедиться, что position-size rule не ведёт себя явно перверсивно.

#### Test B — event study по 4–6 известным режимам

Ручно сохранить screenshots/values S5TH/ERI для известных stress/recovery эпизодов, где платформа позволяет исторический просмотр. Это qualitative sanity check, не статистическая валидация.

#### Test C — prospective log

С первой недели эксперимента сохранять:

```text
week_end
ERI value/sign/source
VIX / VIX50 / VIX3M
S5TH
HY OAS / value_20d_ago
CNN F&G (context only)
R
regime
position_multiplier
```

Через год вы получите собственную честную PIT-историю без лицензированных ретроспективных реконструкций.

**Не использовать community historical CNN datasets как основу механического правила.** Такие архивы существуют, но даже их авторы отмечают, что официальный CNN dataset не публикуется и разные источники дают разные значения.

---

# Б1. Что отслеживать по каждому имени

## Позиция: **минимум, а не терминал Bloomberg своими руками**

### Еженедельные поля по всем ~34 именам

1. `next_earnings_date` + дней до отчёта;
2. `price_1w / 4w / 13w`;
3. `relative_strength_vs_QQQ_4w / 13w`;
4. `drawdown_from_52w_high`;
5. factual changes из собственной карточки:
   - revenue acceleration/deceleration;
   - margin vs median;
   - EPS vs NI/FCF divergence;
   - share-count trend;
   - net debt change;
   - cycle/buyback/cash-conversion flags;
6. `material_filing_or_event_since_last_review`;
7. состояние: `IGNORE / WATCH / CHECK_EXPECTATIONS / NOMINATE_FLOOR2`.

### Только для 3–5 имён после factual screen

8. текущий EPS consensus current FY / next FY;
9. revisions — up/down за 7/30/60 дней;
10. magnitude — current consensus vs 30/60/90 дней назад;
11. last EPS surprise;
12. **price reaction to last earnings** относительно QQQ;
13. confirmed/estimated next earnings date.

Zacks public Detailed Estimates уже показывает:

- current/next quarter and year consensus;
- Up/Down revisions за 7/30/60 дней;
- current consensus vs 7/30/60/90 days ago;
- last EPS surprise.

Пример публичной страницы:
- Amazon Detailed Estimates: https://www.zacks.com/stock/quote/AMZN/detailed-estimates
- META Detailed Estimates: https://www.zacks.com/stock/quote/META/detailed-estimates

### Что убрать

- analyst target price — убрать из weekly process; это слабый, легко якорящий человека output;
- поток всех новостей — убрать; нужен только material event;
- ежедневный RSI/MACD по 34 акциям — не нужен;
- standalone volume alert по каждому имени — слишком шумно; volume полезен только вместе с material price move/event.

### Что добавить

**Две вещи:**

1. `days_to_earnings` — чтобы не открыть новую позицию случайно за сутки до бинарного события без осознанного решения;
2. `reaction_to_last_earnings_vs_QQQ` — surprise без реакции рынка неполон. Это уже принято в Round 5 и я подтверждаю.

---

# Б2. Инструменты и алерты

## Позиция: **на старте достаточно IBKR + собственная карточка + Koyfin Free + Zacks + SEC RSS. Ничего покупать не нужно.**

| Поле/задача | Инструмент | Частота | Цена на 12.08.2026 | Комментарий |
|---|---|---|---:|---|
| price level / % move / volume | **IBKR TWS/Mobile alerts** | event-driven | $0 отдельной платы | использовать для decision-relevant уровней и shortlist/holdings |
| factual weekly card | **Consilium PostgreSQL + SEC + Tiingo** | weekly | уже есть | главный screen по всем 34 |
| watchlist / charts / basic estimates | **Koyfin Free** | weekly | $0 | 2 watchlists, 2Y financials, 1Y estimates, до 5 alerts |
| revisions / consensus detail | **Zacks Detailed Estimates** | только top 3–5 | $0 public page | руками; не scraping/API |
| earnings calendar | **Koyfin Earnings Calendar** | weekly | free/basic availability | фильтровать watchlist |
| S5TH / breadth | **TradingView** или Investing.com | weekly | $0 | market panel |
| Citi ERI | **MacroMicro** | weekly | free if visible; Prime $25/mo/$250yr | не покупать на старте |
| material SEC filings | **SEC company RSS** | event-driven для holdings/nominees | $0 | 8-K/10-Q/10-K primary source |
| company-specific IR | issuer IR email alerts | event-driven для holdings | $0 | earnings/guidance/major press releases |
| delayed visual news/screener fallback | **Finviz registered free** | optional weekly | $0 | до 50 portfolios × 50 tickers; no free alerts |
| broad push news/filing alerts if later needed | Finviz Elite | optional | $39.50/mo or $299.50/yr | не нужен пока IBKR/Koyfin/manual workflow укладываются во время |
| deeper company research + long estimates | Koyfin Plus | optional first paid upgrade | $39/mo | 10Y financials/10Y estimates, unlimited watchlists/screens, 50 alerts |

### Sources

**IBKR alerts.** TWS supports price, percentage-change, volume and other alerts; mobile Trading Assistant can notify on daily percentage moves for selected instruments.
- https://www.ibkrguides.com/traderworkstation/alerts-and-notifications.htm
- https://www.ibkrguides.com/android/trading-assistant.htm

**Koyfin pricing.** Free: $0, 2 watchlists, 2Y financials & 1Y estimates; Plus $39/mo; Premium $79/mo.
- https://www.koyfin.com/pricing/
- plan comparison: https://www.koyfin.com/pricing/plans-comparison/

**Koyfin earnings calendar.** Supports earnings releases, estimates and watchlist filtering.
- https://www.koyfin.com/help/earnings-calendar-feature/

**Koyfin data licensing — важное ограничение.** Consensus estimates come from S&P Capital IQ; Koyfin explicitly says it does **not** offer an API because of vendor restrictions, and financials/estimates/valuation cannot be downloaded.
- data source: https://www.koyfin.com/help/faq/where-do-you-get-your-data/
- API restriction: https://www.koyfin.com/help/faq/can-i-get-the-data-via-api/
- download restriction: https://www.koyfin.com/help/faq/can-i-download-data/

То есть **Koyfin — экран для человека, не бесплатный backend Consilium**.

**Finviz pricing/features.** Registered free portfolios work for manual tracking; push/email alerts and API/export are Elite.
- https://elite.finviz.com/help/elite.ashx

**SEC RSS.** SEC allows company search results to be subscribed as RSS and filtered by filing type.
- https://www.sec.gov/about/rss-feeds

### Где проходит платная граница

Не покупать подписку, пока выполняются оба условия:

1. weekly ritual ≤45 минут;
2. глазами проверяется не больше 3–5 кандидатов.

**Первый платный апгрейд, если ручная работа станет узким местом — Koyfin Plus, не собственный scraper Zacks.**

Почему: $39/мес покупает более длинную financial/estimate history, unlimited watchlists/screens и больше alerts. Но даже после оплаты не пытаться выгружать consensus в Consilium в обход vendor restrictions.

Finviz Elite имеет смысл позже, если узким местом становятся именно broad news/filing/push alerts, а не estimates.

---

# Б3. Еженедельный регламент 30–45 минут

## Позиция: **один weekly loop + отдельная event branch; никаких “посмотрю рынок весь вечер”**

### Weekly loop

#### Шаг 1 — 5 минут: market regime

Заполнить 4 core tiles + CNN context:

```text
ERI
VIX / VIX50 / VIX3M
S5TH
HY_OAS / 20d_change
CNN_FG context
R
REGIME
```

Записать в журнал. Не интерпретировать текстом больше одного предложения.

#### Шаг 2 — 8–10 минут: factual watchlist card

Сортировать 34 имени не по “самым интересным”, а по **изменениям с прошлой недели**:

- новый flag;
- сильнейшее RS изменение;
- сильнейший drawdown/rebound;
- приближение earnings;
- material filing.

Отобрать максимум 5 имён в `CHECK_EXPECTATIONS`.

#### Шаг 3 — 10–12 минут: expectations только по top 3–5

На Zacks/Koyfin руками:

- current/next FY EPS estimate;
- Up/Down 30/60d;
- magnitude 30/60d;
- last surprise;
- next earnings date.

Не переносить все числа в базу. В журнал записывать только то, что повлияло на статус.

#### Шаг 4 — 8–10 минут: event/news check

Только для 3–5:

- earnings / guidance;
- 8-K / 10-Q / 10-K;
- acquisition/divestiture;
- material legal/regulatory event;
- capital allocation event;
- CEO/CFO change, если material.

Первоисточник — filing/IR, а не пересказ заголовка.

#### Шаг 5 — 5 минут: статусы

Каждому изменившемуся имени только один статус:

- `IGNORE`;
- `WATCH`;
- `NOMINATE_FLOOR2`.

Не больше 1–2 новых номинаций в неделю: этаж 2 ограничен временем.

#### Шаг 6 — 2–3 минуты: журнал

Записать:

```text
week
market_regime
names_escalated
why
what_changed_since_last_week
no_action_reason for tempting names
```

### Событийная ветка — когда пришёл alert

**Никогда не торговать непосредственно из alert.**

Мини-чеклист:

1. `WHAT_TRIGGERED?` — price level / 5% move / filing / earnings / news.
2. `SCHEDULED?` — это отчёт/макродень или неожиданный event?
3. `PRIMARY_SOURCE?` — открыть filing/IR, если event fundamental.
4. `RELATIVE_MOVE?` — акция против QQQ; рынок весь упал или это idiosyncratic?
5. `EXPECTATIONS_CHANGED?` — есть ли revisions/guidance change?
6. `THESIS_CHANGED?` — затронуты ли revenue/margin/cash/debt/share-count assumptions?
7. Если **нет** → log, без досье.
8. Если **да** и Floor 1 остаётся positive → `NOMINATE_FLOOR2`.
9. Только после Floor 2 → возможен operator decision.

---

# В1. Пример шапки досье этажа 2

## Позиция: **regime меняет чтение и execution, не числа valuation**

Ниже **схематический пример**, не текущие данные NVDA.

```text
NVDA — PRE-PURCHASE DOSSIER HEADER
Date: YYYY-MM-DD

MARKET REGIME
  Regime: MIXED
  Core vote: 2 positive / 2 negative, R = 0.00
  Citi ERI: + (upgrades dominate)
  VIX vs 50DMA: negative
  Breadth S5TH: positive (>50%)
  HY OAS 4w: widening
  VIX term structure: normal
  CNN F&G: Greed [context only, no vote]

NAME EXPECTATIONS
  FY EPS consensus 60d change: +3.2%       [illustrative]
  Revisions 60d: 5 up / 1 down             [illustrative]
  Last EPS surprise: +6%                    [illustrative]
  Earnings reaction vs QQQ: +4.1 pp         [illustrative]

PRICE / RELATIVE STRENGTH
  RS vs QQQ 13w: +6.5 pp                    [illustrative]
  Drawdown from 52w high: -7%               [illustrative]

FLOOR 1 STATUS
  POSITIVE → eligible for Floor 2

EXECUTION RULE IF FLOOR 2 PASSES
  MIXED regime → max first tranche = 0.75 × standard starter
```

### Как это меняет чтение досье

Без regime header оператор мог бы прочитать:

> revisions вверх + RS сильная → надо спешить.

С header:

> company-specific expectations сильные, но credit/volatility не подтверждают broad risk-on. Это не меняет допустимый multiple или margin surface, но означает меньший первый транш.

Если Floor 2 говорит `EXPECTATIONS_OUTSIDE_REGISTERED_ENVELOPE`, покупка всё равно не происходит.

Если Floor 2 проходит — market regime определяет только **staging**.

---

# В2. Анти-паттерны — запрещённые ходы

## 1. `Extreme Greed → продать всё` / `Extreme Fear → купить всё`

**Запретить.**

CNN — измеритель состояния, а не торговая команда. Extreme Greed может длиться долго в сильном bull market; Extreme Fear может появиться в начале, а не в конце падения.

## 2. Двойной подсчёт коррелированных сигналов

**Запретить:**

> CNN Fear & Greed bearish + VIX bearish + junk bonds bearish = “три независимых подтверждения”.

Нет: VIX и junk-bond demand уже входят в CNN. Именно поэтому CNN у меня имеет weight 0.

## 3. Изменять valuation assumptions из-за настроения рынка

**Запретить:**

> “рынок страшный — я поставлю terminal P/E 12 вместо 18”

или

> “рынок бычий — подниму multiple до 25”.

Это скрытый ручной рычаг. Market regime меняет execution risk, не economics.

## 4. Переписать режим после того, как не понравился результат

**Запретить:**

> “ERI отрицательный, но AI сейчас особый цикл, поэтому этот голос не считаем”.

Данные могут быть `NA`, только если источник реально недоступен. Нельзя выключать индикатор, потому что он мешает покупке.

## 5. Ждать RISK_ON, чтобы купить после капитуляции

**Запретить обратную крайность.**

Risk-off не означает “никаких покупок”. Иначе regime rule заставит покупать дороже после восстановления рынка.

Поэтому даже `RISK_OFF + VOL_STRESS` не даёт автоматический ban: если оба этажа согласны, разрешён маленький стартовый транш (`0.25×`). Это сохраняет возможность покупать хорошую компанию в панике, но ограничивает timing risk.

---

# Возражения к решениям Round 5

## 1. Основную трёхэтажную архитектуру — принимаю

Не вижу причин возвращаться к mass reverse-DCF radar.

## 2. Правило конфликта этажей — принимаю, с одним уточнением

**Market regime не должен становиться третьим veto-этажом.**

То есть:

- Floor 1 positive;
- Floor 2 positive;
- market RISK_OFF

→ имя остаётся `ELIGIBLE_FOR_OPERATOR_DECISION`, но starter уменьшается по А3.

Если сделать Risk Off абсолютным запретом, вы незаметно вернёте market-timing model, которого не хотели строить.

## 3. Пункт «бэктест панели на публичной истории» — предлагаю переписать

Как указано в А4:

> `historical reproducible subset test + prospective full-panel log`.

Полный audit-grade historical backtest CNN + ERI + breadth + credit без платных/неофициальных данных сейчас не соответствует принципу проекта.

## 4. Остальные арбитражи Round 5 — без возражений

В частности поддерживаю:

- edgartools как parser substrate, semantic layer остаётся Consilium;
- META/GOOG как regression goldens;
- 20-F/40-F как отдельный capability tier;
- отсутствие косметического floor terminal multiple;
- journal как обязательный продукт;
- NFLX-FY2019 как экзамен денежного сторожа.

---

# Финальная рекомендация Round 6

## Что реально внедрять в эксперимент

### Market panel

**Core:**

1. Citi ERI;
2. VIX vs 50DMA;
3. S5TH;
4. HY OAS 4-week direction.

**Context only:** CNN Fear & Greed + VIX/VIX3M.

Пять минут в неделю.

### Rule

`RISK_ON / MIXED / RISK_OFF` по нормализованному голосованию.

Режим меняет **только starter-size**:

`1.00 / 0.75 / 0.50`, с `0.25` при `RISK_OFF + VOL_STRESS`.

### Watchlist

Не строить ещё один мониторинг-сервис.

- собственная карточка — facts;
- IBKR — event alerts;
- Koyfin Free — watchlist/market/earnings;
- Zacks — ручные revisions по 3–5 именам;
- SEC RSS/IR — primary material events;
- платный Koyfin Plus только если weekly process перестаёт укладываться в 45 минут.

### Проверка

Не пытаться доказать alpha панели.

Проверять два более скромных утверждения:

1. **оператор соблюдает заранее заданный risk-budget rule без ручных исключений;**
2. **панель уменьшает размер входа в broad risk deterioration, не блокируя хорошие Floor1+Floor2 opportunities полностью.**

Это соответствует новой природе Consilium: не предсказатель рынка, а система дисциплины решения.
