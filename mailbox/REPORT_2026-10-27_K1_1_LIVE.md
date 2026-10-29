**(Б) = 641/735 = 87,2% — ЦЕЛЬ ≥95% НЕ ДОСТИГНУТА.** Числа с выхода `tools/floor1_card.py`, подгонки нет.

# REPORT 2026-10-27 — K1.1 часть 3: один живой прогон floor1_card (задача #115, PR #109)

Тип: отчёт. Не заменяет и не правит прежние файлы. Прогон: `python3 tools/floor1_card.py --out-dir /tmp/floor1_live` (as_of = 2026-10-27, 34 имени из config/watchlist.csv, SEC через адаптер с SEC_USER_AGENT, Tiingo с TIINGO_TOKEN). Прогон ОДИН, повторов не было; код завершился с rc=0. Карточка в репозиторий не коммитится (публикует суббота). Код на момент прогона = коммит п.1 этой же ветки (restricted cash).

## 1. Покрытие

| метрика | заполнено / знаменатель | % |
|---|---|---|
| (А) сырое: заполнено / все поля всех имён | 664/884 | 75,1% |
| (Б) применимое: заполнено / применимые поля имён в scope | 641/735 | 87,2% |

Разбор знаменателей (с выхода): пробелов (GAP) — 96 ячеек; NOT_APPLICABLE — 19 ячеек; OUT_OF_SCOPE_FORM — 5 имён, 130 ячеек. (Б) < 95% → цель не выполнена; остаток не закрыт именованным ограничением целиком — см. раздел 5.

## 2. Tiingo

429 не было и ошибок цен в выходе нет: бенчмарки VOO и QQQ прочитаны до 2026-10-26; отказов в полях rs_* ни у одного из 34 имён. Пробелы по цене — только dd_52w у CBRS и SPCX (`INSUFFICIENT_HISTORY`: ряд цен начинается 2026-05-14 и 2026-06-12, окно 52 недели с 2025-10-28; это короткая история котировок, не сбой источника).

## 3. OUT_OF_SCOPE_FORM — имена и форма из списка подач

Важно про «формы в списке»: список подач адаптера (`LiveLoader.listing`) заранее отфильтрован на 10-K и 10-Q (`COVER_FORMS`), поэтому «нет» означает «ни 10-K, ни 10-Q», а не «подач нет». Поэтому ниже вторая колонка — форма, прочитанная мной отдельно из SEC submissions (`data.sec.gov/submissions/CIK….json`, User-Agent из SEC_USER_AGENT, по одному запросу на имя; это не вывод floor1_card).

| имя | список подач адаптера (10-K/10-Q) | годовая форма по SEC submissions (recent) |
|---|---|---|
| CBRS | 10-Q | годовых форм нет (в recent: 10-Q ×2, 8-K, Form 4, DRS/A…) — ещё нет первого 10-K |
| DLO | нет | 20-F (последняя 2026-03-18), 6-K |
| NBIS | нет | 20-F (2026-04-30), 20-F/A (2026-05-22), 6-K ×248 |
| NVO | нет | 20-F (2026-02-04), 6-K |
| SPCX | 10-Q | годовых форм 10-K/20-F/40-F в recent нет (видны D, 8-K, S-8, 3, FWP…; 10-Q — по списку адаптера) — ещё нет первого 10-K |

Что осталось непроверенным: submissions читал только блок `recent`; более старые подачи не просматривал — для вывода о форме достаточно, для полной истории нет.

## 4. NBIS

Причина **установлена**: Nebius Group N.V. — иностранный эмитент, годовой отчёт подаёт формой 20-F (20-F 2026-04-30, 2025-04-30; 20-F/A 2026-05-22), текущие — 6-K. 10-K/10-Q у CIK 0001513845 в списке подач нет, поэтому правило `annual_scope` даёт OUT_OF_SCOPE_FORM (адаптер читает только 10-K). Цены у NBIS при этом получены (rs_voo_13w = -0.13240, dd_52w = -0.46538). Деньги/долг/выручка по NBIS в карточке пусты ПО ПРАВИЛУ scope, а не из-за сбоя чтения.

## 5. NOT_APPLICABLE — число по причинам (всего 19 ячеек)

- `FCF/NI не определено: NI <= 0` — 7: ASTS/fcf_to_ni, IONQ/fcf_to_ni, MP/fcf_to_ni, OKLO/fcf_to_ni, OSCR/fcf_to_ni, RKLB/fcf_to_ni, SMR/fcf_to_ni
- `CAGR NI/EPS не определён: неположительная граница` (BUYBACK_EPS) — 12: AMZN/BUYBACK_EPS, CELH/BUYBACK_EPS, IONQ/BUYBACK_EPS, MP/BUYBACK_EPS, OSCR/BUYBACK_EPS, PLTR/BUYBACK_EPS, RDDT/BUYBACK_EPS, RKLB/BUYBACK_EPS, SHOP/BUYBACK_EPS, SMR/BUYBACK_EPS, SOFI/BUYBACK_EPS, UBER/BUYBACK_EPS

## 6. Все оставшиеся пробелы (Б) по причине (96 ячеек; строки — как в карточке, имя / поля)

Ячейки флагов с `UNDETERMINED` — следствие отказа входного поля (указан в тексте); флаг, который остаётся неопределённым из-за поля-пробела, считается пробелом отдельно от самого поля.

### MISSING_INPUT — 29 ячеек

- IONQ / gm_latest, gm_med5: числитель gross margin: нет годового ряда в SEC-данных; gross profit: нет GrossProfit и нет себестоимости (нет CostOfRevenue/CostOfGoodsAndServicesSold) -- вывести не из чего, ноль не подставляется
- LLY / om_latest, om_med5: числитель operating margin: нет годового ряда в SEC-данных
- LLY / fcf_latest, fcf_to_ni: capex: нет годового ряда в SEC-данных
- MA / gm_latest, gm_med5: числитель gross margin: нет годового ряда в SEC-данных; gross profit: нет GrossProfit и нет себестоимости (нет CostOfRevenue/CostOfGoodsAndServicesSold) -- вывести не из чего, ноль не подставляется
- MP / gm_latest, gm_med5: числитель gross margin: нет годового ряда в SEC-данных; gross profit: нет GrossProfit и нет себестоимости (нет CostOfRevenue/CostOfGoodsAndServicesSold) -- вывести не из чего, ноль не подставляется
- OKLO / rev_cagr_3y, rev_cagr_5y, rev_accel: revenue: нет годового ряда в SEC-данных
- OKLO / gm_latest, gm_med5: числитель gross margin: нет годового ряда в SEC-данных; gross profit: нет GrossProfit и нет выручки (нет CostOfRevenue/CostOfGoodsAndServicesSold) -- вывести не из чего, ноль не подставляется
- OKLO / om_latest, om_med5: operating margin: нет совпадающих по датам рядов числителя и выручки
- OKLO / nm_latest, nm_med5: net margin: нет совпадающих по датам рядов числителя и выручки
- OSCR / gm_latest, gm_med5: числитель gross margin: нет годового ряда в SEC-данных; gross profit: нет GrossProfit и нет себестоимости (нет CostOfRevenue/CostOfGoodsAndServicesSold) -- вывести не из чего, ноль не подставляется
- OSCR / net_debt_latest, net_debt_chg_3y: нет ни одной даты, где есть и полный долг, и денежные средства
- PLTR / net_debt_latest, net_debt_chg_3y: нет ни одной даты, где есть и полный долг, и денежные средства
- SOFI / om_latest, om_med5: числитель operating margin: нет годового ряда в SEC-данных
- UBER / gm_latest, gm_med5: числитель gross margin: нет годового ряда в SEC-данных; gross profit: нет GrossProfit и нет себестоимости (нет CostOfRevenue/CostOfGoodsAndServicesSold) -- вывести не из чего, ноль не подставляется

### STALE_SERIES — 14 ячеек

- ASTS / gm_latest, gm_med5: числитель gross margin (выручка - себестоимость): последняя точка 2022-12-31, ФГ карточки 2025-12-31 (тег перестали заполнять или поменяли)
- ASTS / om_latest, om_med5: числитель operating margin: последняя точка 2020-12-31, ФГ карточки 2025-12-31 (тег перестали заполнять или поменяли)
- FOUR / gm_latest, gm_med5: числитель gross margin (выручка - себестоимость): последняя точка 2018-12-31, ФГ карточки 2025-12-31 (тег перестали заполнять или поменяли)
- NFLX / net_debt_latest, net_debt_chg_3y: net debt (LongTermDebt - Cash): последняя точка 2020-12-31, ФГ карточки 2025-12-31 (тег перестали заполнять или поменяли)
- ORCL / gm_latest, gm_med5: числитель gross margin: последняя точка 2018-05-31, ФГ карточки 2026-05-31 (тег перестали заполнять или поменяли)
- ORCL / net_debt_latest, net_debt_chg_3y: net debt (LongTermDebt - Cash): последняя точка 2022-05-31, ФГ карточки 2026-05-31 (тег перестали заполнять или поменяли)
- SOFI / net_debt_latest, net_debt_chg_3y: net debt (LongTermDebt - Cash): последняя точка 2022-12-31, ФГ карточки 2025-12-31 (тег перестали заполнять или поменяли)

### INSUFFICIENT_HISTORY — 18 ячеек

- ASTS / rev_accel: revenue: нужны три подряд идущих ФГ до 2025-12-31
- ASTS / nm_med5: net margin: нет 5 ФГ подряд до 2025-12-31
- ASTS / shares_chg_3y: shares_diluted: нет точки за 3 ФГ до 2025-12-31
- CBRS / dd_52w: ряд цен начинается 2026-05-14, окно 52н с 2025-10-28
- CELH / net_debt_chg_3y: net debt: нет точки за 3 ФГ до 2025-12-31
- GOOG / gm_med5: gross margin (выручка - себестоимость): нет 5 ФГ подряд до 2025-12-31
- IONQ / rev_cagr_5y: revenue: нет точки за 5 ФГ до 2025-12-31
- MP / net_debt_chg_3y: net debt: нет точки за 3 ФГ до 2025-12-31
- OKLO / shares_chg_3y: shares_diluted: нет точки за 3 ФГ до 2025-12-31
- RDDT / rev_cagr_5y: revenue: нет точки за 5 ФГ до 2025-12-31
- RDDT / gm_med5: gross margin (выручка - себестоимость): нет 5 ФГ подряд до 2025-12-31
- RDDT / om_med5: operating margin: нет 5 ФГ подряд до 2025-12-31
- RDDT / nm_med5: net margin: нет 5 ФГ подряд до 2025-12-31
- SHOP / rev_cagr_5y: revenue: нет точки за 5 ФГ до 2025-12-31
- SHOP / gm_med5: gross margin: нет 5 ФГ подряд до 2025-12-31
- SHOP / om_med5: operating margin: нет 5 ФГ подряд до 2025-12-31
- SHOP / nm_med5: net margin: нет 5 ФГ подряд до 2025-12-31
- SPCX / dd_52w: ряд цен начинается 2026-06-12, окно 52н с 2025-10-28

### DEBT_TAG_ABSENT — 12 ячеек

- IONQ / net_debt_latest, net_debt_chg_3y: нет ни одного тега долга из цепочек LongTermDebt,DebtAndCapitalLeaseObligations / LongTermDebtNoncurrent,LongTermDebtAndCapitalLeaseObligations: «долга нет» и «тег не заполнен» неотличимы, ноль не подставляется
- ISRG / net_debt_latest, net_debt_chg_3y: нет ни одного тега долга из цепочек LongTermDebt,DebtAndCapitalLeaseObligations / LongTermDebtNoncurrent,LongTermDebtAndCapitalLeaseObligations: «долга нет» и «тег не заполнен» неотличимы, ноль не подставляется
- OKLO / net_debt_latest, net_debt_chg_3y: нет ни одного тега долга из цепочек LongTermDebt,DebtAndCapitalLeaseObligations / LongTermDebtNoncurrent,LongTermDebtAndCapitalLeaseObligations: «долга нет» и «тег не заполнен» неотличимы, ноль не подставляется
- RDDT / net_debt_latest, net_debt_chg_3y: нет ни одного тега долга из цепочек LongTermDebt,DebtAndCapitalLeaseObligations / LongTermDebtNoncurrent,LongTermDebtAndCapitalLeaseObligations: «долга нет» и «тег не заполнен» неотличимы, ноль не подставляется
- SHOP / net_debt_latest, net_debt_chg_3y: нет ни одного тега долга из цепочек LongTermDebt,DebtAndCapitalLeaseObligations / LongTermDebtNoncurrent,LongTermDebtAndCapitalLeaseObligations: «долга нет» и «тег не заполнен» неотличимы, ноль не подставляется
- SMR / net_debt_latest, net_debt_chg_3y: нет ни одного тега долга из цепочек LongTermDebt,DebtAndCapitalLeaseObligations / LongTermDebtNoncurrent,LongTermDebtAndCapitalLeaseObligations: «долга нет» и «тег не заполнен» неотличимы, ноль не подставляется

### UNDETERMINED/MISSING_INPUT — 17 ячеек

- ASTS / BUYBACK_EPS, DEBT_FOR_BUYBACKS: MISSING_INPUT: shares_chg_3y отказано (INSUFFICIENT_HISTORY)
- CELH / DEBT_FOR_BUYBACKS: MISSING_INPUT: net_debt_chg_3y отказано (INSUFFICIENT_HISTORY)
- IONQ / DEBT_FOR_BUYBACKS: MISSING_INPUT: net_debt_chg_3y отказано (DEBT_TAG_ABSENT)
- ISRG / DEBT_FOR_BUYBACKS: MISSING_INPUT: net_debt_chg_3y отказано (DEBT_TAG_ABSENT)
- LLY / CASH_CONV_DIVERGENCE: MISSING_INPUT: нужны NI и FCF на одном последнем ФГ
- MP / DEBT_FOR_BUYBACKS: MISSING_INPUT: net_debt_chg_3y отказано (INSUFFICIENT_HISTORY)
- NFLX / DEBT_FOR_BUYBACKS: MISSING_INPUT: net_debt_chg_3y отказано (STALE_SERIES)
- OKLO / BUYBACK_EPS, DEBT_FOR_BUYBACKS: MISSING_INPUT: shares_chg_3y отказано (INSUFFICIENT_HISTORY)
- ORCL / DEBT_FOR_BUYBACKS: MISSING_INPUT: net_debt_chg_3y отказано (STALE_SERIES)
- OSCR / DEBT_FOR_BUYBACKS: MISSING_INPUT: net_debt_chg_3y отказано (MISSING_INPUT)
- PLTR / DEBT_FOR_BUYBACKS: MISSING_INPUT: net_debt_chg_3y отказано (MISSING_INPUT)
- RDDT / DEBT_FOR_BUYBACKS: MISSING_INPUT: net_debt_chg_3y отказано (DEBT_TAG_ABSENT)
- SHOP / DEBT_FOR_BUYBACKS: MISSING_INPUT: net_debt_chg_3y отказано (DEBT_TAG_ABSENT)
- SMR / DEBT_FOR_BUYBACKS: MISSING_INPUT: net_debt_chg_3y отказано (DEBT_TAG_ABSENT)
- SOFI / DEBT_FOR_BUYBACKS: MISSING_INPUT: net_debt_chg_3y отказано (STALE_SERIES)

### UNDETERMINED/INSUFFICIENT_HISTORY — 6 ячеек

- ASTS / CYCLE_PEAK: INSUFFICIENT_HISTORY: операционная маржа: нет 5 ФГ подряд
- LLY / CYCLE_PEAK: INSUFFICIENT_HISTORY: операционная маржа: нет 5 ФГ подряд
- OKLO / CYCLE_PEAK: INSUFFICIENT_HISTORY: операционная маржа: нет 5 ФГ подряд
- RDDT / CYCLE_PEAK: INSUFFICIENT_HISTORY: операционная маржа: нет 5 ФГ подряд
- SHOP / CYCLE_PEAK: INSUFFICIENT_HISTORY: операционная маржа: нет 5 ФГ подряд
- SOFI / CYCLE_PEAK: INSUFFICIENT_HISTORY: операционная маржа: нет 5 ФГ подряд

Итого 96 = числу GAP в карточке.

## 7. Деньги с ограничением (п.1)

В этом прогоне ни у одного имени чистый долг не взят через запасной тег `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` (в md-карточке: «† … нет таких имён»). То есть на живых данных эта ветка не сработала; её поведение доказано пином f1_48 на синтетике (мутации k11-22..24), а не живым случаем.

## 8. Что не закрыто

- (Б) = 87,2% < 95%: 96 пробелов остаются. Крупнейшие группы по числу ячеек: MISSING_INPUT (29), UNDETERMINED/MISSING_INPUT (17), INSUFFICIENT_HISTORY (18), STALE_SERIES (14), DEBT_TAG_ABSENT (12). Причины не классифицировал как «ограничение источника» или «наш дефект» — это требует чтения конкретных фактов по каждому имени, чего этот прогон не делал.
- Дрейф тегов (STALE_SERIES у NFLX, ORCL, SOFI, ASTS, FOUR) и отсутствие тегов (UBER/MA/MP gross profit, ISRG/SMR/SHOP/RDDT/IONQ/OKLO долг) — по тексту отказов выглядят как кандидаты на расширение цепочек тегов; не расширял, чтобы не подгонять число под цель.
