# Досье (machine) — RDDT, срез 2026-11-02

Reddit, Inc. (CIK 0001713445). Сгенерировано `tools/dossier.py` (К6 ч. A). Детерминированно, модели не вызывались. Вердикта нет: решение за оператором.

## (а) Провенанс и basis-check GAAP / non-GAAP

| Строка | Значение | Откуда |
|---|---|---|
| Выручка | 2,202,506,000 USD | SEC 0001713445-26-000022, ФГ 2025-12-31, тег RevenueFromContractWithCustomerExcludingAssessedTax, подан 2026-02-06 |
| Операционная прибыль | 441,984,000 USD | SEC 0001713445-26-000022, ФГ 2025-12-31, тег OperatingIncomeLoss, подан 2026-02-06 |
| Чистая прибыль (NI) | 529,721,000 USD | SEC 0001713445-26-000022, ФГ 2025-12-31, тег NetIncomeLoss, подан 2026-02-06 |
| Операционный денежный поток (OCF) | 690,875,000 USD | SEC 0001713445-26-000022, ФГ 2025-12-31, тег NetCashProvidedByUsedInOperatingActivities, подан 2026-02-06 |
| Капзатраты (capex) | 6,706,000 USD | SEC 0001713445-26-000022, ФГ 2025-12-31, тег PaymentsToAcquirePropertyPlantAndEquipment, подан 2026-02-06 |
| Акции, разводнённые средневзвешенные за ФГ | 202,107,978 | SEC 0001713445-26-000022, ФГ 2025-12-31, тег WeightedAverageNumberOfDilutedSharesOutstanding, подан 2026-02-06 |
| SBC (справочно) | 343,180,000 USD | SEC 0001713445-26-000022, ФГ 2025-12-31, тег ShareBasedCompensation, подан 2026-02-06 |

FCF = OCF − capex (вычислено здесь): 684,169,000 USD [accn 0001713445-26-000022 и 0001713445-26-000022]

**Расхождение NI / операционная прибыль / FCF** (отношения; знаменатель <= 0 -> отказ, не 0):
- NI / операционная прибыль: 1.199
- FCF / NI: 1.292
- FCF / операционная прибыль: 1.548
- Метки расхождения: нет (по правилам выше)

**Non-GAAP:** ОТКАЗ NON_GAAP_NOT_CHECKED: не проверено машиной: показатели, которые компания публикует вне GAAP (adjusted EBITDA, non-GAAP EPS), в XBRL us-gaap не лежат; публикует ли компания non-GAAP -- машина не знает

## (б) Факты этажа 1 (те же функции, что карточка, на as_of 2026-11-02)

| Поле | Значение | Единица | Основание (basis) | Провенанс |
|---|---|---|---|---|
| rev_cagr_3y | 0.489345066754274 | ratio | CAGR 3л ФГ 2022-12-31..2025-12-31 | 0001713445-25-000018; 0001713445-26-000022 |
| rev_cagr_5y | — | — | ОТКАЗ SHORT_HISTORY: короткая история: полю нужно 5 ФГ до 2025-12-31 (точка около 2020-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31 | — |
| rev_accel | 0.07685618951070627 | ratio | YoY(2025-12-31) - YoY(2024-12-31) = 0.6940 - 0.6171 | 0001713445-26-000022 |
| gm_latest | 0.9118204445300035 | ratio | gross margin (выручка - себестоимость) ФГ 2025-12-31 | 0001713445-26-000022 |
| gm_med5 | — | — | ОТКАЗ SHORT_HISTORY: короткая история: полю нужно 4 ФГ до 2025-12-31 (точка около 2021-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31 | — |
| om_latest | 0.20067323312626617 | ratio | operating margin ФГ 2025-12-31 | 0001713445-26-000022 |
| om_med5 | — | — | ОТКАЗ SHORT_HISTORY: короткая история: полю нужно 4 ФГ до 2025-12-31 (точка около 2021-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31 | — |
| nm_latest | 0.2405083118956316 | ratio | net margin ФГ 2025-12-31 | 0001713445-26-000022 |
| nm_med5 | — | — | ОТКАЗ SHORT_HISTORY: короткая история: полю нужно 4 ФГ до 2025-12-31 (точка около 2021-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31 | — |
| ni_latest | 529721000 | USD | NetIncomeLoss ФГ 2025-12-31 | 0001713445-26-000022 |
| eps_latest | 2.620980157448312 | USD/sh | вычислено: NI / средневзв. разводнённые акции, ФГ 2025-12-31 (НЕ отчётный EPS) | 0001713445-26-000022 |
| fcf_latest | 684169000 | USD | OCF - capex(PP&E) ФГ 2025-12-31 | 0001713445-26-000022 |
| fcf_to_ni | 1.2915648048689783 | ratio | FCF/NI ФГ 2025-12-31 | 0001713445-26-000022 |
| shares_chg_1y | 0.38932191455245846 | ratio | средневзв. разводнённые акции 2025-12-31 vs 2024-12-31 | 0001713445-26-000022 |
| shares_chg_3y | 2.5302017889189647 | ratio | средневзв. разводнённые акции 2025-12-31 vs 2022-12-31 | 0001713445-25-000018; 0001713445-26-000022 |
| net_debt_latest | — | — | ОТКАЗ NOT_REPORTED: не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих) | — |
| net_debt_chg_3y | — | — | ОТКАЗ NOT_REPORTED: не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих) | — |
| rs_voo_4w | -0.36559253026834815 | ratio | доходность тикера -0.3902 минус VOO -0.0246, adjClose 2026-10-05..2026-10-30 | Tiingo adjClose 2026-10-30 |
| rs_voo_13w | -0.407385492730589 | ratio | доходность тикера -0.4071 минус VOO 0.0003, adjClose 2026-08-03..2026-10-30 | Tiingo adjClose 2026-10-30 |
| rs_qqq_4w | -0.3032791776431615 | ratio | доходность тикера -0.3902 минус QQQ -0.0869, adjClose 2026-10-05..2026-10-30 | Tiingo adjClose 2026-10-30 |
| rs_qqq_13w | -0.3943994408526058 | ratio | доходность тикера -0.4071 минус QQQ -0.0127, adjClose 2026-08-03..2026-10-30 | Tiingo adjClose 2026-10-30 |
| dd_52w | -0.6457343683621055 | ratio | close 2026-10-30 91.73 к max adjClose 258.93 (2026-01-13) | Tiingo adjClose 2026-10-30 |

**Чистый долг — сырые факты** (поле net_debt_latest)

- ОТКАЗ NOT_REPORTED: не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)

## (в) Сторожа с уликами

**CASH_DECAY** (правила PREREG_2026-11-01_K4_NFLX_CASH_DECAY §4): **НЕ_ОПРЕДЕЛЁН**
- Причина: FCF/NI(ФГ0) = 1.29 >= 0.5, но медиана трёх предыдущих ФГ не вычислима (ФГ-1: NI <= 0; ФГ-2: NI <= 0; ФГ-3: NI <= 0): OK и AMBER неразличимы
- Улика: нет (вердикт без улики: не RED/AMBER)

Диагностика FCF/NI по ФГ (из сторожа, как есть):
- {"capex_to_ocf": 0.009706531572281527, "end": "2025-12-31", "fcf_to_ni": 1.2915648048689783, "ocf_to_ni": 1.3042242992065634, "why": {}}
- {"capex_to_ocf": 0.028135526055082228, "end": "2024-12-31", "fcf_to_ni": null, "ocf_to_ni": null, "why": {"fcf_to_ni": "NI <= 0", "ocf_to_ni": "NI <= 0"}}
- {"capex_to_ocf": null, "end": "2023-12-31", "fcf_to_ni": null, "ocf_to_ni": null, "why": {"capex_to_ocf": "OCF <= 0", "fcf_to_ni": "NI <= 0", "ocf_to_ni": "NI <= 0"}}
- {"capex_to_ocf": null, "end": "2022-12-31", "fcf_to_ni": null, "ocf_to_ni": null, "why": {"capex_to_ocf": "OCF <= 0", "fcf_to_ni": "NI <= 0", "ocf_to_ni": "NI <= 0"}}
- {"capex_to_ocf": null, "end": null, "fcf_to_ni": null, "ocf_to_ni": null, "why": {"all": "нет фактов за этот ФГ"}}

**Флаги карточки этажа 1:**
- CYCLE_PEAK: **UNDETERMINED** [SHORT_HISTORY] — SHORT_HISTORY: om_med5 — короткая история: полю нужно 4 ФГ до 2025-12-31 (точка около 2021-12-31), а самый ранний годовой факт выручки в companyfacts — ФГ 2022-12-31
- CASH_CONV_DIVERGENCE: **CLEAR** — NI 2025-12-31: -484276000 -> 529721000; FCF: 215820000 -> 684169000
- BUYBACK_EPS: **NOT_APPLICABLE** [NOT_APPLICABLE] — CAGR NI/EPS не определён: неположительная граница
- DEBT_FOR_BUYBACKS: **UNDETERMINED** [NOT_REPORTED] — NOT_REPORTED: net_debt_chg_3y — не представлено компанией: долг, проверены теги LongTermDebt, DebtAndCapitalLeaseObligations, DebtLongtermAndShorttermCombinedAmount, LongTermDebtNoncurrent, LongTermDebtAndCapitalLeaseObligations, LongTermNotesPayable, LongTermDebtCurrent, DebtCurrent, LongTermDebtAndCapitalLeaseObligationsCurrent, NotesPayableCurrent, ShortTermBorrowings, ConvertibleDebt*; в companyfacts нет ни одного факта с end >= 2022-12-10 (последний ФГ карточки 2025-12-31 и 3 предшествующих)

## (г) Сценарная поверхность

Допущения (basis): цена — Tiingo close «как торговалась» 91.73 на 2026-10-30; акции — разводнённые средневзвешенные за ФГ 2025-12-31 из SEC (не на дату, не float); чистый долг — поле net_debt_latest этажа 1; горизонт 10 лет; число акций, чистый долг и дивиденды (нет) не меняются; множитель — параметр сетки, не прогноз.
Текущая капитализация: 18,539,364,822 USD; EV: ОТКАЗ (нет чистый долг); EV/S: ОТКАЗ.

**Таблица 1. Подразумеваемая годовая доходность за 10 лет: рост выручки в год × выходной EV/S** (EV_T = EV/S × Выручка₀ × (1+g)^10; цена_T = (EV_T − чистый долг) / акции)

| рост \ EV/S | 10 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|
| 0% | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT |
| 5% | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT |
| 10% | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT |
| 15% | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT |
| 20% | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT |
| 25% | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT | ОТКАЗ:MISSING_INPUT |

**Таблица 2. То же: рост чистой прибыли в год × выходной P/E** (маржа неизменна; NI₀ = 529,721,000 USD)

| рост \ P/E | 10 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|
| 0% | -11.8% | -8.1% | -5.4% | -3.3% | -1.5% |
| 5% | -7.4% | -3.5% | -0.7% | +1.5% | +3.4% |
| 10% | -3.0% | +1.1% | +4.0% | +6.4% | +8.3% |
| 15% | +1.5% | +5.7% | +8.7% | +11.2% | +13.2% |
| 20% | +5.9% | +10.3% | +13.5% | +16.0% | +18.2% |
| 25% | +10.3% | +14.8% | +18.2% | +20.9% | +23.1% |

**Ориентир «что даёт пассив»** — доходность за N лет до 2026-11-02 по Tiingo adjClose (с учётом дивидендов и сплитов):

| | 1 год | 3 года (в год) | 5 лет (в год) |
|---|---|---|---|
| VOO | +12.1% за период; +12.1% в год [adjClose 2025-10-31..2026-10-30] | +80.7% за период; +21.8% в год [adjClose 2023-11-03..2026-10-30] | +75.5% за период; +11.9% в год [adjClose 2021-11-02..2026-10-30] |
| QQQ | +10.3% за период; +10.3% в год [adjClose 2025-10-31..2026-10-30] | +91.0% за период; +24.1% в год [adjClose 2023-11-03..2026-10-30] | +82.8% за период; +12.8% в год [adjClose 2021-11-02..2026-10-30] |

**Обратный DCF** (функция ivc старого конвейера, бисекция; порог 12%, 10 лет, fade на годах 6–10 к min(4%, g), разводнение 0, дивиденды 0): какой рост базы на акцию уже заложен в цену при выходном P/E:

| База \ выходной P/E | 10 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|
| GAAP EPS (2.6210 USD) | 37.6% | 30.1% | 25.0% | 21.1% | 18.1% |
| FCF/акцию (3.3852 USD) | 32.8% | 25.5% | 20.6% | 16.9% | 13.9% |

## (д) ЧТО ДОЛЖНО БЫТЬ ПРАВДОЙ / ЧТО ОПРОВЕРГНЕТ

Генерируется формулами из чисел раздела (г); суждений нет. Порог 12% и горизонт 10 лет — параметры мандата.

**Что должно быть правдой:**
- ОТКАЗ MISSING_INPUT: нет: чистый долг
- Прибыль должна превращаться в деньги: FCF/NI за ФГ 2025-12-31 = 1.29 (порог CASH_DECAY 0.5).

**Что опровергнет:**
- Порог роста выручки: ОТКАЗ MISSING_INPUT: нет: чистый долг
- FCF/NI < 0.5 (порог CASH_DECAY). Сейчас: 1.29.

## (е) Время машины и хэш входа

- Время машины (от чтения SEC до готового отчёта): 6.4 с (предел гейта: 7200 с)
- Хэш входа (sha256 фактов SEC, цен бенчмарков и точки цены): `06b92a4fbea0f1f6c61e343bde33f1091b28a5f4e3f4ebf257daf7872b70d5ff`
- Источники: SEC EDGAR через адаптер К2 (edgartools==5.48.0), Tiingo; as_of 2026-11-02; цены строго <= as_of.
