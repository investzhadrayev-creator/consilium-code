# Досье для человека — RDDT, срез 2026-11-02

## 1. Что за компания

Reddit, Inc., последний годовой отчёт — за ФГ, закончившийся 2025-12-31 (подан до 2026-11-02). Источник: SEC.

## 2. Три главных числа

1. Рост выручки, который уже заложен в цену (чтобы получить 12% в год 10 лет, если оценка компании к выручке не изменится): ОТКАЗ MISSING_INPUT: нет: чистый долг.
2. Сколько прибыли превращается в свободные деньги (FCF/NI за ФГ): **1.29**.
3. Что давал пассивный индекс за 5 лет до среза (в год): VOO **+11.9%**, QQQ **+12.8%**.

## 3. Сторожа: что горит и почему

- Сторож «деньги не догоняют прибыль» (CASH_DECAY): **не определён**. FCF/NI(ФГ0) = 1.29 >= 0.5, но медиана трёх предыдущих ФГ не вычислима (ФГ-1: NI <= 0; ФГ-2: NI <= 0; ФГ-3: NI <= 0): OK и AMBER неразличимы
  Улика: нет
- CYCLE_PEAK: UNDETERMINED. SHORT_HISTORY: om_med5 — короткая история: полю нужно 4 ФГ до 2025-12-31 (точка около 2021-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31
- CASH_CONV_DIVERGENCE: CLEAR. NI 2025-12-31: -484276000 -> 529721000; FCF: 215820000 -> 684169000
- BUYBACK_EPS: NOT_APPLICABLE. CAGR NI/EPS не определён: неположительная граница
- DEBT_FOR_BUYBACKS: UNDETERMINED. NOT_REPORTED: net_debt_chg_3y — не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)

## 4. Что должно быть правдой / что опровергнет

- ОТКАЗ MISSING_INPUT: нет: чистый долг
- Прибыль должна превращаться в деньги: FCF/NI за ФГ 2025-12-31 = 1.29 (порог CASH_DECAY 0.5).
- Опровергнет: Порог роста выручки: ОТКАЗ MISSING_INPUT: нет: чистый долг
- Опровергнет: FCF/NI < 0.5 (порог CASH_DECAY). Сейчас: 1.29.

## 5. Чего машина не знает

- Non-GAAP показатели компании: не проверено машиной (в XBRL us-gaap их нет).
- Будущее: сетка и обратный DCF — арифметика от допущений (множитель, горизонт, неизменные акции и долг), не прогноз.
- Поля этажа 1 без значения (названные отказы): rev_cagr_5y — SHORT_HISTORY: короткая история: полю нужно 5 ФГ до 2025-12-31 (точка около 2020-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31; gm_med5 — SHORT_HISTORY: короткая история: полю нужно 4 ФГ до 2025-12-31 (точка около 2021-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31; om_med5 — SHORT_HISTORY: короткая история: полю нужно 4 ФГ до 2025-12-31 (точка около 2021-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31; nm_med5 — SHORT_HISTORY: короткая история: полю нужно 4 ФГ до 2025-12-31 (точка около 2021-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31; net_debt_latest — NOT_REPORTED: не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих); net_debt_chg_3y — NOT_REPORTED: не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)

Решение о покупке или отказе — за оператором; досье вердикта не содержит. Подробности и accession — в `RDDT_2026-11-02_machine.md`.
