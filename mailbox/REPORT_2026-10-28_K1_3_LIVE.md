**(Б) = 660/692 = 95,4% (с новыми классами NOT_REPORTED и SHORT_HISTORY; цель ≥95% достигнута ТОЛЬКО благодаря им).** Числа с выхода `tools/floor1_card.py`, подгонки нет.

**(Б без новых классов) = 660/735 = 89,8%.** **(А) = 683/884 = 77,3%.** Числитель обоих (Б) и (А) не изменился относительно K1.2 (660 и 683): классы только выводят ячейки из знаменателя, новых заполненных ячеек нет.

# REPORT 2026-10-28 — K1.3: два класса по объективному правилу (задача #124)

Тип: отчёт. Прежние файлы не правятся (REPORT_2026-10-28_K1_2_LIVE.md остаётся как есть). Ветка от `claude/k1-2-coverage` (PR #122), PR «K1.3» зависит от #109 и #122; **классы вводятся только если оператор одобрит DECISION_2026-10-28_FLOOR1_CLASSES (PR #126); без этого PR не сливать.** Прогон ОДИН: `python3 tools/floor1_card.py --out-dir /tmp/floor1_live3`, as_of 2026-10-28 (в K1.2 было 2026-10-27), 34 имени, rc=0. Tiingo без ошибок.

## 1. Что реализовано (правила — в коде, не по именам тикеров)

- **NOT_REPORTED**: у поля есть группы входов (для маржи — выручка И числитель; для долга — все теги `DEBT_FULL/NONC/CUR_CHAIN` и все теги `ConvertibleDebt*`; для FCF — OCF и capex с запасным тегом; и т. д.). Если у ЛЮБОЙ группы ни один тег не имеет НИ ОДНОГО факта в companyfacts с `end` ≥ (ФГ карточки − 3 года − 21 дн.), поле — NOT_REPORTED с перечнем проверенных тегов и датой начала окна. Любой факт любой формы в окне (в том числе 10-Q) — класса нет, пробел. Применяется только к отказам «данных нет» (`MISSING_INPUT`, `STALE_SERIES`, `DEBT_TAG_ABSENT`); отказ по нашему решению (например `MULTI_CLASS_NOT_SUMMED` у GOOG: акции раскрыты по классам) классом не становится — иначе класс утверждал бы неправду.
- **SHORT_HISTORY**: заменяет только `INSUFFICIENT_HISTORY`. Окну поля нужно N ФГ до последнего (3/5/2/4/1/3 для rev_cagr_3y/rev_cagr_5y/rev_accel/med5/shares_1y/3y,net_debt_3y), точка = ФГ − N·365,25 дн.; если самый ранний годовой факт выручки (минимум по каждому тегу выручки) позже этой точки больше чем на 21 дн. (допуск `at_offset`) — класс, с датами в причине. Есть ранняя история, но точки нет (CELH) — пробел. Нет годовой выручки — доказать нечем, пробел. Цены: `dd_52w` — первая котировка Tiingo позже начала окна 52 недель → SHORT_HISTORY с датой первой котировки. RS-окна (4н/13н) в класс НЕ включены (в задаче названы только 52 недели).
- **Зависимые флаги** (CYCLE_PEAK ← om_latest/om_med5; CASH_CONV_DIVERGENCE ← fcf_latest/ni_latest; BUYBACK_EPS ← shares_chg_3y/eps_latest; DEBT_FOR_BUYBACKS ← shares_chg_3y/net_debt_chg_3y): если поле-зависимость в классе, флаг — `UNDETERMINED` с кодом класса, никогда CLEAR/RAISED, вне знаменателя (Б).
- Карточка: строки (Б) и «(Б) без новых классов» рядом; отдельные разделы NOT_REPORTED и SHORT_HISTORY; в CSV колонки `cells_not_reported`, `cells_short_history`, `coverage_B_without_new_classes`.

## 2. Покрытие

| метрика | значение |
|---|---|
| (А) сырое | 683/884 = 77,3% |
| (Б) с классами | 660/692 = 95,4% |
| (Б) без новых классов | 660/735 = 89,8% |
| NOT_REPORTED (в scope) | 32 ячейки: 24 поля + 8 флагов |
| SHORT_HISTORY (в scope) | 11 ячеек: 9 полей + 2 флага |
| пробелов (GAP) осталось | 32 |
| NOT_APPLICABLE / OUT_OF_SCOPE_FORM | 19 ячеек / 130 ячеек (5 имён) — без изменений |

Сверка: 692 + 32 + 11 = 735. В разделе SHORT_HISTORY карточки 13 ячеек, а не 11: ещё `dd_52w` у CBRS и SPCX, но эти имена вне scope (нет годового 10-K), их ячейки считаются в OUT_OF_SCOPE_FORM и в (Б) не входят.

## 3. Расхождения с ожиданием в задаче и в K1.2 (важно для решения оператора)

- **OKLO — не класс по буквальному правилу.** Ожидалось «выручка не отчитана → маржи NOT_REPORTED». Прочитано companyfacts OKLO: тег `Revenues` имеет факты из 10-Q: 0 на 2025-06-30 и 1 210 000 на 2026-06-30 (то же в `RevenueFromContractWithCustomerExcludingAssessedTax`); `LongTermDebtNoncurrent` = 0 на 2025-12-31 и 700 000 на 2026-06-30 (10-Q). Годовых (10-K) фактов выручки нет. По правилу «хоть один факт за 4 ФГ — пробел» это пробел (OKLO: 7 полей выручки/маржей и 2 поля долга остаются GAP; все ячейки OKLO — в списке пробелов в §4). Объявить «не представлено компанией» значило бы утверждать неправду: выручка в 10-Q представлена. Если архитектор имел в виду «нет ГОДОВОГО факта», это другое правило (годовые факты 10-K), в код не вносилось; его влияние на (Б) я не считал.
- **SHOP — тоже пробел, не класс**: в окне есть факты `ConvertibleDebtNoncurrent` (напр. 2022-12-31, 2023-12-31) и `ConvertibleDebtCurrent` (напр. 2023-12-31, 2024-12-31); теги `ConvertibleDebt*` входят в долговую цепочку по заданию.
- PLTR долг стал NOT_REPORTED (долговых фактов после 2021 нет), IONQ/ISRG/RDDT/SMR долг — NOT_REPORTED; MA/OSCR/ORCL/OKLO валовая прибыль и ASTS/LLY/SOFI операционная прибыль — NOT_REPORTED.
- NOT_REPORTED: 24 поля против 39 полей в информационной оценке K1.2 (§3.1); разница объясняется OKLO и SHOP (см. выше), прочие расхождения по именам я не раскладывал. SHORT_HISTORY: 9 полей против 18 ячеек в K1.2 (§3.2); для ASTS самый ранний годовой факт выручки — ФГ 2020-12-31 (прочитано из companyfacts), поэтому окна 2–4 ФГ не короче истории и ячейки ASTS остаются пробелами; по MP, GOOG, OKLO причину различия я отдельно не проверял.
- Класс вводится после известных цифр (оговорка DECISION). Защита: правило объективное, окно и допуски фиксированы константами, «(Б) без новых классов» публикуется рядом.

## 4. Полный список ячеек классов (дословно из карточки) и остаток пробелов по причинам

## Named limitations (32)

- ASTS / rev_accel — `INSUFFICIENT_HISTORY`: revenue: нужны три подряд идущих ФГ до 2025-12-31
- ASTS / gm_latest, gm_med5 — `STALE_SERIES`: числитель gross margin (выручка - себестоимость): последняя точка 2022-12-31, ФГ карточки 2025-12-31 (тег перестали заполнять или поменяли)
- ASTS / nm_med5 — `INSUFFICIENT_HISTORY`: net margin: нет 5 ФГ подряд до 2025-12-31
- ASTS / shares_chg_3y — `INSUFFICIENT_HISTORY`: shares_diluted: нет точки за 3 ФГ до 2025-12-31
- ASTS / BUYBACK_EPS, DEBT_FOR_BUYBACKS — `UNDETERMINED`: MISSING_INPUT: shares_chg_3y отказано (INSUFFICIENT_HISTORY)
- CELH / net_debt_chg_3y — `INSUFFICIENT_HISTORY`: net debt: нет точки за 3 ФГ до 2025-12-31
- CELH / DEBT_FOR_BUYBACKS — `UNDETERMINED`: MISSING_INPUT: net_debt_chg_3y отказано (INSUFFICIENT_HISTORY)
- GOOG / gm_med5 — `INSUFFICIENT_HISTORY`: gross margin (выручка - себестоимость): нет 5 ФГ подряд до 2025-12-31
- MP / gm_med5 — `INSUFFICIENT_HISTORY`: gross margin (выручка - себестоимость): нет 5 ФГ подряд до 2025-12-31
- MP / net_debt_chg_3y — `INSUFFICIENT_HISTORY`: net debt: нет точки за 3 ФГ до 2025-12-31
- MP / DEBT_FOR_BUYBACKS — `UNDETERMINED`: MISSING_INPUT: net_debt_chg_3y отказано (INSUFFICIENT_HISTORY)
- OKLO / rev_cagr_3y, rev_cagr_5y, rev_accel — `MISSING_INPUT`: revenue: нет годового ряда в SEC-данных
- OKLO / om_latest, om_med5 — `MISSING_INPUT`: operating margin: нет совпадающих по датам рядов числителя и выручки
- OKLO / nm_latest, nm_med5 — `MISSING_INPUT`: net margin: нет совпадающих по датам рядов числителя и выручки
- OKLO / shares_chg_3y — `INSUFFICIENT_HISTORY`: shares_diluted: нет точки за 3 ФГ до 2025-12-31
- OKLO / net_debt_latest, net_debt_chg_3y — `DEBT_TAG_ABSENT`: нет ни одного тега долга из цепочек LongTermDebt,DebtAndCapitalLeaseObligations,DebtLongtermAndShorttermCombinedAmount / LongTermDebtNoncurrent,LongTermDebtAndCapitalLeaseObligations,LongTermNotesPayable: «долга нет» и «тег не заполнен» неотличимы, ноль не подставляется
- OKLO / CYCLE_PEAK — `UNDETERMINED`: INSUFFICIENT_HISTORY: операционная маржа: нет 5 ФГ подряд
- OKLO / BUYBACK_EPS, DEBT_FOR_BUYBACKS — `UNDETERMINED`: MISSING_INPUT: shares_chg_3y отказано (INSUFFICIENT_HISTORY)
- OSCR / net_debt_latest, net_debt_chg_3y — `MISSING_INPUT`: долг не раскрыт полностью: нетекущая часть есть (2023-12-31,2024-12-31,2025-12-31), текущей части в данных нет на этих датах -- «нет текущей части» != ноль, ноль не подставляется
- OSCR / DEBT_FOR_BUYBACKS — `UNDETERMINED`: MISSING_INPUT: net_debt_chg_3y отказано (MISSING_INPUT)
- SHOP / net_debt_latest, net_debt_chg_3y — `DEBT_TAG_ABSENT`: нет ни одного тега долга из цепочек LongTermDebt,DebtAndCapitalLeaseObligations,DebtLongtermAndShorttermCombinedAmount / LongTermDebtNoncurrent,LongTermDebtAndCapitalLeaseObligations,LongTermNotesPayable: «долга нет» и «тег не заполнен» неотличимы, ноль не подставляется
- SHOP / DEBT_FOR_BUYBACKS — `UNDETERMINED`: MISSING_INPUT: net_debt_chg_3y отказано (DEBT_TAG_ABSENT)

## NOT_REPORTED — не представлено компанией (ни одного факта по тегам цепочки за последний ФГ и 3 предшествующих; вне знаменателя Б) (32)

- ASTS / om_latest, om_med5: не представлено компанией: операционная прибыль, проверены теги OperatingIncomeLoss; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- ASTS / CYCLE_PEAK: NOT_REPORTED: om_latest — не представлено компанией: операционная прибыль, проверены теги OperatingIncomeLoss; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих); om_med5 — не представлено компанией: операционная прибыль, проверены теги OperatingIncomeLoss; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- IONQ / net_debt_latest, net_debt_chg_3y: не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- IONQ / DEBT_FOR_BUYBACKS: NOT_REPORTED: net_debt_chg_3y — не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- ISRG / net_debt_latest, net_debt_chg_3y: не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- ISRG / DEBT_FOR_BUYBACKS: NOT_REPORTED: net_debt_chg_3y — не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- LLY / om_latest, om_med5: не представлено компанией: операционная прибыль, проверены теги OperatingIncomeLoss; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- LLY / CYCLE_PEAK: NOT_REPORTED: om_latest — не представлено компанией: операционная прибыль, проверены теги OperatingIncomeLoss; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих); om_med5 — не представлено компанией: операционная прибыль, проверены теги OperatingIncomeLoss; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- MA / gm_latest, gm_med5: не представлено компанией: валовая прибыль/себестоимость, проверены теги GrossProfit, CostOfRevenue, CostOfGoodsAndServicesSold, CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- OKLO / gm_latest, gm_med5: не представлено компанией: валовая прибыль/себестоимость, проверены теги GrossProfit, CostOfRevenue, CostOfGoodsAndServicesSold, CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- ORCL / gm_latest, gm_med5: не представлено компанией: валовая прибыль/себестоимость, проверены теги GrossProfit, CostOfRevenue, CostOfGoodsAndServicesSold, CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization; в companyfacts нет ни одного факта с end >= 2023-05-10 (последний ФГ карточки 2026-05-31 и 3 предшествующих)
- OSCR / gm_latest, gm_med5: не представлено компанией: валовая прибыль/себестоимость, проверены теги GrossProfit, CostOfRevenue, CostOfGoodsAndServicesSold, CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- PLTR / net_debt_latest, net_debt_chg_3y: не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- PLTR / DEBT_FOR_BUYBACKS: NOT_REPORTED: net_debt_chg_3y — не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- RDDT / net_debt_latest, net_debt_chg_3y: не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- RDDT / DEBT_FOR_BUYBACKS: NOT_REPORTED: net_debt_chg_3y — не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- SMR / net_debt_latest, net_debt_chg_3y: не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- SMR / DEBT_FOR_BUYBACKS: NOT_REPORTED: net_debt_chg_3y — не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- SOFI / om_latest, om_med5: не представлено компанией: операционная прибыль, проверены теги OperatingIncomeLoss; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)
- SOFI / CYCLE_PEAK: NOT_REPORTED: om_latest — не представлено компанией: операционная прибыль, проверены теги OperatingIncomeLoss; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих); om_med5 — не представлено компанией: операционная прибыль, проверены теги OperatingIncomeLoss; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)

## SHORT_HISTORY — короткая история (окно поля длиннее истории; вне знаменателя Б) (13)

- CBRS / dd_52w: короткая история: ряд цен Tiingo начинается 2026-05-14, окну 52 недель нужен close с 2025-10-29
- IONQ / rev_cagr_5y: короткая история: полю нужно 5 ФГ до 2025-12-31 (точка около 2020-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2021-12-31
- RDDT / rev_cagr_5y: короткая история: полю нужно 5 ФГ до 2025-12-31 (точка около 2020-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31
- RDDT / gm_med5, om_med5, nm_med5: короткая история: полю нужно 4 ФГ до 2025-12-31 (точка около 2021-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31
- RDDT / CYCLE_PEAK: SHORT_HISTORY: om_med5 — короткая история: полю нужно 4 ФГ до 2025-12-31 (точка около 2021-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31
- SHOP / rev_cagr_5y: короткая история: полю нужно 5 ФГ до 2025-12-31 (точка около 2020-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31
- SHOP / gm_med5, om_med5, nm_med5: короткая история: полю нужно 4 ФГ до 2025-12-31 (точка около 2021-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31
- SHOP / CYCLE_PEAK: SHORT_HISTORY: om_med5 — короткая история: полю нужно 4 ФГ до 2025-12-31 (точка около 2021-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31
- SPCX / dd_52w: короткая история: ряд цен Tiingo начинается 2026-06-12, окну 52 недель нужен close с 2025-10-29

## 5. Тесты и мутации

- `python3 run_tests.py` (CONSILIUM_REPO_v4_2_83): **ALL GREEN, rc=0**; Python-сьют 859 тестов (было 847), OK. В окружении раннера поставлены `edgartools==5.48.0` и `flask==3.0.3`; `npm install` выполнен.
- `python3 tools/mutation_probe.py`: каталог 362 случая, **362 RED**, 0 SKIP, 0 GREEN, 0 NOT_EXEC (было 349).
- Новые пины f1_54..f1_65 (классы `TestK13NotReported`, `TestK13ShortHistory`, `TestK13CoverageFlagsAndCard`), мутации k13-01..k13-13, все RED. Первая версия k13-07 была GREEN (пустой пин) — переделана; k13-13 была GREEN из-за тавтологии теста (брал зависимости из самого `FLAG_DEPS`) — тест привязан к явной таблице. Пять старых пинов (f1_08, f1_13, f1_37, f1_51, f1_53) пришлось обновить: их синтетические данные без тегов в окне теперь по правилу NOT_REPORTED; исходный смысл («отказ, не ноль») сохранён, класс проверяется явно.

## 6. Что не закрыто

- Остаток пробелов (см. §4): OKLO (см. §3), OSCR долг (нет текущей части), SHOP долг, ASTS/CELH/MP/GOOG/OKLO история, ASTS валовая прибыль (STALE_SERIES).
- Рабочее допущение: любой факт любой формы в окне блокирует NOT_REPORTED. Решение «только годовые факты» не принято мной, это решение архитектора.
- RS-окна и CELH-подобные случаи в SHORT_HISTORY не включены.
