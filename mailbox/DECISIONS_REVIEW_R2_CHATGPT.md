Проверил весь `DECISIONS_DRAFT_2026-08-08_FOR_REVIEW.md`. Главный вывод второго раунда: **направление стало заметно сильнее, но §2 в текущей редакции я бы не финализировал**. Reverse-expectations — правильный главный режим для такого продукта, однако формула `required EPS growth − actual EPS CAGR 5y` пока слишком груба, чтобы превращать её в единый рейтинг. Именно `actual_eps_cagr_5y` сейчас является самым слабым звеном конструкции. Проекты решений и предложенная последовательность работ зафиксированы в draft.

| Вопрос                                            | Вердикт                                            |
| ------------------------------------------------- | -------------------------------------------------- |
| 1.1 Nasdaq-100 при приоритете «компании первичны» | **Согласен с оговорками**                          |
| 2.1 Reverse-expectations как главный режим        | **Согласен с оговорками**                          |
| 2.2 EPS CAGR 5y как «достижимый рост»             | **Не согласен**                                    |
| 2.3 Единые 12% почти не меняют порядок            | **Не согласен с формулировкой**                    |
| 2.4 ROE median 5y cap 40%                         | **Не согласен как с достаточной защитой**          |
| 2.5 Growth gap или implied return                 | **Implied return — основной, gap — объяснение**    |
| 2.6 False-cheap cases                             | **Есть несколько опасных классов**                 |
| 3.1 Метрики                                       | **Согласен, сократить первый обязательный набор**  |
| 4.1 Пиры только как validation                    | **Арбитраж подтверждаю**                           |
| 5.1 Внеиндексные имена отдельно                   | **Согласен с одной оговоркой**                     |
| 6.1 Freeze researcher degrees of freedom          | **Почти, но дыра осталась**                        |
| 7.1 8–12 changesets / 2–3 недели                  | **Разложение недооценивает критический путь**      |
| 8.1 Порядок работ                                 | **Не согласен; margin model стоит слишком поздно** |

## §1. Nasdaq-100 при приоритете «компании первичны»

**Согласен с оговорками.**

Если реальная задача оператора — инвестировать прежде всего в крупные качественные компании Nasdaq, то метод действительно должен обслуживать этот инвестиционный universe, а не заставлять оператора покупать то, что удобно модели.

Но скрытая цена принципа «компании первичны» — **опасность методологической адаптации к желаемому результату**.

Например, одновременно в технологическом universe могут существовать NVIDIA и Micron. Для NVIDIA в 2024 году произошёл реальный структурный скачок: revenue +126%, gross margin выросла на 15.8 п.п., diluted EPS — +586%. ([SEC][1]) У Micron, напротив, earnings способны резко меняться вместе с циклом памяти: между FY2018 и FY2019 revenue снизилась на 23%, gross margin с 59% до 46%, net income с $14.1 млрд до $6.3 млрд. ([Micron Technology][2])

Обе компании могут находиться в одном «growth universe», но экономическая природа их роста различна. Поэтому:

> **Nasdaq-100 может определять, кого анализировать. Он не должен определять, какая экономическая модель считается правильной.**

Если после каждого сложного имени правила начинают меняться так, чтобы оно стало оценимым, universe начинает обучать модель прямо на production sample.

---

# §2. Главный режим: reverse expectations

## 2.1. Пригоден ли implied-growth ranking как главный режим?

**Согласен с оговорками. Сам reverse-DCF — да. Предложенный scalar ranking — пока нет.**

Переход от вопроса:

> «Сколько стоит компания?»

к вопросу:

> «Что должно произойти с бизнесом, чтобы сегодняшняя цена дала мне 12%?»

я считаю методологически правильным.

Для Nasdaq-100 это намного честнее попытки постоянно вычислять одну «справедливую цену».

Но у вас пока фактически решается **одномерное** уравнение: неизвестным объявляется growth, тогда как цена отражает одновременно:

* рост revenue;
* изменение margins;
* capital intensity;
* dilution;
* buybacks;
* terminal profitability;
* terminal multiple.

Это фундаментальный риск.

### NVIDIA — пример ошибки в другую сторону

До AI-инфлексии исторический CAGR прибыли не мог содержать информацию о скачке economics 2023–2024. В FY2024 operating income NVIDIA вырос на 681%, а gross margin резко перешла на другой уровень. ([SEC][1])

Модель, сравнивающая требуемый growth с прежним trailing CAGR, могла бы назвать компанию чрезмерно дорогой именно в момент структурного изменения.

Это не означает, что NVIDIA тогда была дешёвой. Это означает другое:

> Исторический CAGR не является пределом возможного будущего CAGR.

### Micron — противоположная ошибка

В циклическом пике историческая прибыль огромна, trailing P/E выглядит низким, исторический EPS growth великолепным, а рынок уже дисконтирует следующий спад.

Именно такой механизм хорошо виден в Micron: рекордные FY2018 earnings резко сократились уже в 2019 из-за падения pricing памяти. ([Micron Technology][2])

Reverse-growth может сказать:

> «Рынок почти ничего не требует, а компания исторически росла гораздо быстрее → дешёво».

На самом деле рынок может правильно требовать **снижения** прибыли.

Поэтому я поддерживаю reverse-expectations как главный интерфейс, но не формулу:

> `required growth – historical EPS CAGR`

как окончательную универсальную оценку.

---

# 2.2. `actual_eps_cagr_5y` как «достижимый рост»

**Не согласен. И я бы изменил терминологию до написания кода.**

`actual_eps_cagr_5y` — это:

> **наблюдавшийся исторический рост EPS**,

а не:

> **достижимый рост**.

Слово «достижимый» уже содержит прогноз.

Именно здесь модель незаметно пересекает границу между измерением и прогнозированием.

Я бы разложил EPS growth детерминированно:

```text
EPS growth
≈ business earnings growth
+ effect of shrinking share count
```

А business earnings growth:

```text
revenue growth
+ margin change
```

То есть минимум нужны четыре наблюдаемые величины:

```text
Revenue CAGR
Net-income / operating-profit CAGR
EPS CAGR
Share-count CAGR
```

И отдельно:

```text
margin_start → margin_end
```

Тогда система сможет говорить:

> EPS рос 12%;
> из них примерно 7 п.п. пришло от роста earnings,
> около 5 п.п. — от сокращения акций.

Это намного информативнее одного CAGR.

### O'Reilly — конкретный пример

В 2024 году net income O'Reilly вырос с примерно $2.35 млрд до $2.39 млрд — менее чем на 2%, тогда как diluted EPS вырос на 6%, а diluted shares снизились примерно с 61 млн до 59 млн. ([SEC][3])

EPS growth здесь явно включает вклад buybacks.

Если взять EPS CAGR как «достижимую производительность бизнеса», buyback превращается в operating growth.

Именно это делать нельзя.

### Что использовать до полноценной margin model

Я **не предлагаю ждать идеальной модели**.

До неё можно публиковать:

```text
required EPS growth
historical EPS CAGR
historical earnings CAGR
historical revenue CAGR
share-count contribution
margin trend
```

Но ranking должен получать `LOW_CONFIDENCE` или исключение из сравнения, если эти величины сильно расходятся.

Например:

```text
EPS CAGR       14%
Net income      8%
Revenue         6%
Shares         -5%
```

Такой CAGR нельзя автоматически объявлять `achievable = 14%`.

---

# 2.3. «12% константа — порядок почти не меняется»

**Не согласен с этим как с гарантией.**

В упрощённейшем случае вы почти правы.

Если нет дивидендов, terminal multiple фиксирован и используется один горизонт:

```text
P = EPS0 × (1+g)^T × PEterminal / (1+k)^T
```

то:

```text
1 + g_required
= (1+k) × (P / (EPS0 × PEterminal))^(1/T)
```

Для **самого `g_required`** изменение общей `k` действительно в основном масштабирует все значения одинаково и сохраняет порядок.

Но вы ранжируете не `g_required`.

Вы ранжируете:

```text
g_required − g_historical
```

А второе слагаемое у каждой компании своё.

Поэтому ranking способен поменяться.

Простой пример.

Представим две компании:

```text
A: structural factor = 1.15, historical growth = 15.0%
B: structural factor = 1.10, historical growth = 9.5%
```

При hurdle 9%:

```text
A required = 25.35%, gap = 10.35%
B required = 19.90%, gap = 10.40%
```

A чуть дешевле.

При hurdle 12%:

```text
A required = 28.80%, gap = 13.80%
B required = 23.20%, gap = 13.70%
```

Теперь B дешевле.

Порядок перевернулся.

В реальной модели эффект ещё сильнее из-за:

* разных terminal P/E;
* dividend streams;
* разных terminal ROE;
* dilution;
* fade.

### Вывод

12% можно оставить основной личной hurdle rate.

Но нужно провести очень дешёвый sensitivity test:

```text
rank @ 10%
rank @ 11%
rank @ 12%
rank @ 13%
rank @ 14%
```

и измерить Spearman rank correlation.

Если `ρ > 0.98` — архитектор фактически прав.

Если ORLY прыгает с 12-го места на 38-е — ставка влияет не только на уровень.

Это надо **измерить**, а не предполагать.

---

# 2.4. Terminal ROE: median 5y, cap 40%

**Не согласен, что этого достаточно.**

40% cap — разумный sanity guard.

Он не лечит фундаментальную проблему denominator.

### O'Reilly — почти идеальный контрпример

O'Reilly на конец 2025 года имела **отрицательный shareholders' equity примерно −$763 млн**, одновременно продолжая огромные repurchases; только за 2025 год компания выкупила акции примерно на $2.1 млрд. ([O'Reilly Auto Parts][4])

Что означает ROE при отрицательном equity?

Экономически — почти ничего.

Не существует корректной операции:

> «ROE получился бессмысленным, поэтому поставим максимум 40%».

Вы превращаете невалидную величину в точную величину.

### Apple — более мягкий вариант того же класса

Apple продолжает крупные buybacks: только за шесть месяцев до 28 марта 2026 года компания выкупила акции примерно на $36 млрд. ([SEC][5])

Даже при положительном equity агрессивные repurchases уменьшают denominator book equity и механически повышают ROE.

Поэтому высокий accounting ROE может одновременно отражать:

* настоящий moat;
* asset-light economics;
* leverage;
* старые buybacks;
* низкий book capital.

### Что делать

Правило должно быть:

```text
if equity <= 0:
    accounting_ROE = NOT_APPLICABLE
```

Не cap.

Для таких компаний нужен другой terminal profitability input.

Лучший кандидат — **return on incremental invested capital / incremental earnings on reinvestment**.

Экономическая логика terminal value именно такая:

```text
terminal growth = reinvestment rate × incremental return on capital
```

Отсюда:

```text
reinvestment = g / ROIIC
payout-like distributable fraction = 1 − g / ROIIC
```

Это намного ближе к реальности, чем исторический ROE на баланс, уничтоженный buybacks.

До реализации ROIIC я бы сделал:

> `ROE_DISTORTED_BY_EQUITY_BASE → terminal_multiple_formula unavailable`

а не присваивал 40%.

Да, это приведёт к отказам. Это лучше ложной точности.

---

# 2.5. Growth gap или implied shareholder return?

**Основная метрика — implied return. Growth gap — обязательное объяснение рядом.**

Я изменяю акцент относительно первого раунда.

Growth gap прекрасен как диагностический язык:

> рынок требует 14%, история показывает 8% → нужны +6 п.п.

Это понятно человеку.

Но как **ranking metric** процентные пункты growth плохо сопоставимы между компаниями.

Разница в +4 п.п. growth:

* при terminal multiple 12;
* при terminal multiple 20;
* у дивидендной компании;
* у long-duration growth company

имеет разную денежную стоимость.

А вопрос инвестора в конечном счёте один:

> **Какую доходность даёт сегодняшняя цена, если принять выбранный operating scenario?**

Поэтому главный ranking я бы строил:

```text
implied shareholder IRR
under normalized operating assumptions
```

и сравнивал с 12%.

Например:

```text
NVDA          implied IRR 14.1%    growth gap -1.3pp
AAPL          implied IRR 11.8%    growth gap +0.4pp
ORCL          implied IRR 10.6%    growth gap +1.8pp
```

Это вымышленные числа только для показа интерфейса.

Пользователь сразу понимает порядок.

А `growth gap` объясняет, **почему** IRR получился таким.

Итого:

> **IRR — score.
> Required-growth gap — explanation.**

---

# 2.6. Три реальных false-cheap случая и сторожа

Это действительно самый важный вопрос документа.

## Случай A — Micron на пике memory cycle

### Что увидит ranking

На пике:

* EPS огромна;
* исторический EPS CAGR огромен;
* P/E часто выглядит низким;
* reverse model требует мало дополнительного роста.

Результат:

> `required 3% – historical 20% = −17 pp`

Очень «дёшево».

### Что происходит реально

Micron FY2018 получила net income около $14.1 млрд при gross margin 59%. Уже в FY2019 net income сократилась до $6.3 млрд, gross margin до 46%, revenue снизилась на 23%, главным образом из-за pricing decline. ([Micron Technology][2])

Рынок не требовал роста.

Он дисконтировал **mean reversion**.

### Сторож

Не просто флаг `CYCLICAL`.

Нужно измерение:

```text
margin volatility 5–10y
earnings volatility
peak-to-trough EPS
revenue cyclicality
```

И условие:

> Если earnings находятся значительно выше mid-cycle normalized earnings, historical EPS CAGR не используется как achievable anchor.

Для memory-semiconductors желательно считать normalized mid-cycle margin.

---

## Случай B — O'Reilly: EPS growth за счёт buybacks

### Что увидит ranking

Исторический EPS стабильно растёт.

Reverse required growth может оказаться умеренным.

Gap говорит:

> «рынок требует меньше, чем компания исторически способна давать».

### Что скрыто

В 2024 O'Reilly:

* net income вырос менее чем на 2%;
* diluted EPS вырос 6%;
* share count сократился примерно на 3%;
* repurchases составили около $2.08 млрд. ([SEC][3])

Следовательно часть EPS growth — финансовая инженерия капитала, а не operating growth.

Это не значит, что buybacks плохи.

Но их нельзя экстраполировать как бесплатный perpetual growth.

### Сторож

Обязательная decomposition:

```text
EPS CAGR
Net-income CAGR
Share-count CAGR
Buybacks / FCF
Buybacks / market cap
Net debt trend
```

И ограничение:

> share-count contribution нельзя автоматически продлевать на десять лет.

Если buybacks требуют роста leverage — sustainability flag.

---

## Случай C — Zoom после пандемии

Это отличный пример **regime contamination**.

FY2021–2022 создали фантастическую историческую траекторию. Но уже между FY2022 и FY2023:

* revenue вырос примерно с $4.10 млрд до $4.39 млрд;
* operating income рухнула с ~$1.06 млрд до ~$245 млн;
* net income — с ~$1.38 млрд до ~$104 млн. ([Zoom Communications, Inc.][6])

Представим ranking вскоре после сильного падения акции.

Price резко снизилась → required growth снизился.

Историческое окно всё ещё содержит pandemic boom → historical CAGR остаётся высоким.

Модель легко получает:

> «цена уже ничего не требует, а компания исторически растёт очень быстро».

False cheap.

### Сторож

Нужен не sector flag, а **regime-change detector**:

```text
revenue CAGR recent vs long
margin recent vs long
customer-growth / unit metric if available
EPS direction last 2y
```

Если:

```text
5y CAGR high
but last 2y earnings trend sharply negative
```

исторический CAGR нельзя считать forward anchor.

---

## Четвёртый случай — обратный false signal: NVIDIA

Он полезен потому, что показывает симметрию проблемы.

Перед структурным AI-сдвигом historical metrics могли выглядеть существенно слабее будущей экономики; затем FY2024 revenue вырос 126%, gross margin +15.8 п.п., EPS +586%. ([SEC][1])

Historical anchor мог назвать такое ожидание «героическим», хотя произошло изменение самого earnings regime.

То есть guards нужны в обе стороны:

```text
REGIME_PEAK → не верить высокому historical growth
REGIME_INFLECTION → не считать низкий historical growth потолком будущего
```

---

# §3. Метрики качества рейтинга

**Согласен с направлением, но для первой итерации сократил бы primary set.**

Историческая реконструкция честно может считать почти всё перечисленное, если используются point-in-time universe, данные, цены и неизменённый protocol.

Для первой настоящей validation я бы сделал три primary metrics:

| Метрика                               | Зачем                                     |
| ------------------------------------- | ----------------------------------------- |
| Spearman Rank IC, 12m forward         | Проверяет сам ranking                     |
| Top quintile − bottom quintile, 12m   | Проверяет экономическую величину различия |
| Top quintile vs equal-weight universe | Проверяет добавленную стоимость выбора    |

Почему **quintile**, а не decile сначала: на NDX decile — около 10 компаний. Очень шумно.

QQQ оставить вторичным practical benchmark:

> «Стоило ли вообще выбирать акции?»

12 месяцев сделать primary horizon.

24/36 — secondary.

Все горизонты можно посчитать исторически, но overlapping observations нельзя считать независимыми.

В первый live-год четыре квартальных snapshot не являются статистическим доказательством чего-либо.

---

# §4. Пиры — только validation и flags

**Арбитраж подтверждаю.**

Я бы не менял решение.

Но уточню: я не считаю peer information бесполезной для моделей вообще.

Есть допустимая конструкция:

```text
company estimate
+ explicit Bayesian shrinkage toward peer prior
```

если она:

* называется отдельной моделью;
* имеет измеренный shrinkage coefficient;
* валидирована out-of-sample.

Это совершенно другое, чем:

```text
company ROE missing
→ use semiconductor median ROE
```

Вторая операция возвращает `unknown → plausible`.

### Контрпример, где peers могли бы помочь

У O'Reilly accounting ROE невалиден из-за отрицательного equity. Peer profitability могла бы дать лучшее число, чем случайный cap 40%.

Но правильный вывод не:

> «подставим медианный peer ROE».

А:

> «ROE-model здесь неприменима; используем другой economic return measure».

То есть арбитраж §4 остаётся правильным.

---

# §5. Внеиндексные имена

**Согласен. Одно возражение.**

В отдельном файле должны быть действительно **факты**, а не качественная модель под другим названием.

Для RKLB условно допустимо:

```text
Revenue
Cash
Shares
Backlog
SEC filings
8-K events
```

Недопустимо:

```text
"execution risk moderate"
"moat strengthening"
"valuation becoming attractive"
```

Потому что это уже surrogate verdict.

Физическое разделение файла — правильное решение.

---

# §6. Заморозка researcher degrees of freedom

**Почти согласен. Но дыра осталась.**

Вы правильно останавливаете принятие §1–§5 до результатов Test #1. Это закрывает моё первоначальное возражение.

Однако **полный protocol Test #2 тоже нужно заморозить сейчас**, до Test #1.

Не только universe.

Сейчас следует заранее зафиксировать:

```text
point-in-time membership rule
eligibility
missing-data policy
negative EPS policy
rank definition
primary horizon
portfolio construction
rebalance lag
transaction costs
sector adjustment
benchmark
success criteria
failure criteria
```

Иначе после Test #1 остаётся пространство:

> «Раз прибор оказался слишком строгим, для Test #2 лучше возьмём quintiles вместо deciles / 24 месяца вместо 12 / исключим negative-EPS names...»

Это снова researcher degrees of freedom.

### Более серьёзная дыра

В вашем порядке **margin model идёт после Validation #2**.

Если после Validation #2 вы измените основную связь:

```text
revenue → earnings
```

то Validation #2 больше не валидирует финальную методологию.

Это логическое противоречие.

Есть только два честных варианта:

**A.** Margin model строится **до** Test #2.

или

**B.** Test #2 официально называется validation interim model, а после margin model требуется **Test #3 на untouched data**.

Я выбираю A.

---

# 7.1. Где врёт оценка 8–12 changesets / 2–3 недели

Разложение работ в draft хорошо как инженерный backlog, но **changeset — плохая единица оценки методологической работы**. Текущая таблица считает task complexity числом PR, хотя реальные риски находятся в определении contracts и data semantics.

Самые недооценённые пункты:

### №2 — «двойной якорь роста»: не 1–2 changesets по сути

Проблема не в добавлении `eps_cagr`.

Нужно решить:

* отрицательный EPS;
* EPS около нуля;
* acquisitions;
* discontinued operations;
* one-off taxes;
* share-count changes;
* buybacks;
* cyclicality;
* regime changes;
* 3/5/7-year windows.

И главное — определить, **что из этого может быть forward anchor**.

Это маленькая правка кода и большая методологическая работа.

### №3 — terminal multiple + ROE: тяжелее 2 changesets

O'Reilly уже показывает, что `ROE median capped 40%` ломается на отрицательном equity. ([O'Reilly Auto Parts][4])

Значит сначала нужно решить:

> Что является terminal return measure, когда accounting ROE не определён?

Пока ответа нет, implementation spec не готова.

### №4 — ranking table: 1–2 changesets только как UI

Настоящий ranking engine должен знать:

* кто eligible;
* кто refused;
* какие данные stale;
* tie rules;
* unstable-margin exclusion;
* negative EPS;
* confidence;
* method version;
* PIT universe;
* benchmark weights.

Сам `sort()` действительно один changeset.

Ranking contract — нет.

### №7 — point-in-time universe

«2 changesets + source» скрывает самое тяжёлое за словами `+ source`.

Источник означает:

* licensing;
* historical constituent events;
* identifiers;
* ticker changes;
* mergers;
* delistings;
* class changes;
* effective dates.

Это data product.

### И главное: №6 вынесен за рамки «работоспособности»

Вот здесь я ломаю план сильнее всего.

> **Я не считаю ranking decision-grade до margin/regime layer.**

Можно сделать экспериментальный ranking без него.

Но нельзя после первого аудита, где центральной находкой было «revenue growth не равен earnings growth», объявить полноценной новую систему, в которой основной score опять сравнивается с историческим EPS без modelling profitability regimes.

То есть ваши 2–3 недели могут дать:

> **MVP / shadow ranking.**

Они не дают:

> **validated ranking suitable for capital allocation.**

Я бы вообще убрал календарную оценку из decision document и заменил её acceptance gates.

---

# 8.1. Порядок работ

Текущий:

> финализация → Test1 → changesets 1–5 → NDX → Test2 → margin model.

**Не согласен.**

Ключевая ошибка — validation происходит **до** крупного изменения самой модели.

Я переставил бы так:

| Порядок | Что                                                                         |
| ------- | --------------------------------------------------------------------------- |
| 1       | Финализировать §1–§6 + полностью пре-регистрировать Test #2                 |
| 2       | Завершить Test #1 **без изменений**                                         |
| 3       | Починить reverse calculation на правильной ноге                             |
| 4       | Построить growth decomposition: revenue / earnings / EPS / shares / margins |
| 5       | Ввести applicability + cyclical/regime/buyback guards                       |
| 6       | Решить terminal profitability: ROE vs ROIIC и отрицательный equity          |
| 7       | Реализовать terminal multiple M2                                            |
| 8       | **Реализовать margin/regime model**                                         |
| 9       | Реализовать ranking + IRR + growth-gap как shadow output                    |
| 10      | Построить PIT S&P500 ex-financials validation universe                      |
| 11      | Test #2                                                                     |
| 12      | Только после успешного Test #2 — operational NDX dashboard/alerts           |
| 13      | Peer percentiles и косметические улучшения                                  |

Два заметных изменения.

**Peer flags я убрал с critical path.** Они полезны, но не определяют, работает ли метод.

**Historical NDX тоже не является prerequisite Test #2**, если Test #2 проводится на S&P500 ex-Financials. Для production достаточно current NDX membership; исторический NDX нужен для отдельного NDX-specific research.

---

# Финальная оценка шести проектов решений

§1 **принимать**: Nasdaq-100 как operational universe.

§2 **не принимать в текущей формуле**. Принимать reverse-expectations как главный режим, но заменить концепцию `achievable = EPS CAGR5` на growth decomposition / normalized scenario. Основной ranking — implied return, growth gap рядом.

§3 **принимать с упрощённым primary protocol**: Rank IC + top-bottom + equal-weight benchmark, 12m primary.

§4 **принимать**: peers только validation/flags.

§5 **принимать**, если «facts only» действительно запрещает скрытые qualitative verdicts.

§6 **принимать после усиления**: полный Test #2 protocol заморозить сейчас и **перенести margin model до Test #2**.

Именно последнее я считаю самым важным изменением второго раунда. Сейчас ваш порядок предлагает сначала доказать, что метод работает, а затем изменить одну из главных причин его ошибок. **Такую validation пришлось бы проводить заново.**

[1]: https://www.sec.gov/Archives/edgar/data/1045810/000104581024000104/nvda-20240514.htm?utm_source=chatgpt.com "nvda-20240514"
[2]: https://investors.micron.com/static-files/bc79bf75-0f1e-434b-a428-afedf5b874ca?utm_source=chatgpt.com "UNITED STATES"
[3]: https://www.sec.gov/Archives/edgar/data/898173/000089817325000008/orly-20241231x10k.htm?utm_source=chatgpt.com "O Reilly Automotive Inc_December 31, 2024"
[4]: https://corporate.oreillyauto.com/2026/02/04/oreilly-automotive-inc-reports-fourth-quarter-and-full-year-2025-results/?utm_source=chatgpt.com "O'Reilly Automotive, Inc. Reports Fourth Quarter and Full-Year 2025 Results - O'Reilly Auto Parts"
[5]: https://www.sec.gov/Archives/edgar/data/320193/000032019326000013/aapl-20260328.htm?utm_source=chatgpt.com "aapl-20260328"
[6]: https://investors.zoom.us/static-files/50e0c380-f4bd-4a16-80e3-da56b64017ce?utm_source=chatgpt.com "Annual Report"
