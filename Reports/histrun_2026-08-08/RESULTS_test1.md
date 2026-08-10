# RESULTS — Счёт проверки №1 (историческая проверка методики)

Источник методики: `mailbox/PREREG_2026-08-06_HISTORICAL_VALIDATION.md` (заморожена). Решение об исполнении при STOP BUILD: `mailbox/DECISION_2026-08-09_ARBITRATION.md` (В1, В4).

Пар обработано: **175**. Посчитано: **63**. Отказано: **112** (64.0%).

## Критерии (PREREG §4), число рядом с формулировкой

### Критерий 1 — чувствительность: на каждой из трёх донных дат вердикт «покупать» (вариант А) получают не менее 20% имён, доступных к оценке на ту дату.
- 2018-12-24: 0/11 доступных (0.0%) -> FAIL
- 2020-03-23: 0/14 доступных (0.0%) -> FAIL
- 2022-10-12: 3/12 доступных (25.0%) -> PASS

### Критерий 2 — избирательность: на каждой из двух контрольных дат вердикт «покупать» получают не более 2 имён из 34.
- 2019-07-01: 0/13 покупок -> PASS
- 2021-12-31: 0/13 покупок -> PASS

### Критерий 3 — различающая способность: имена, помеченные покупкой 23 марта 2020, за последующие пять лет показывают более высокую медианную полную доходность, чем имена, помеченные отказом на ту же дату.
- требует форвардной доходности за 5 лет (до 2025-03-23) — вне данных этого прогона; не вычисляется здесь.

### Критерий 4 — исправность стенда: тикер со сплитом после проверяемой даты воспроизводит P/E, посчитанный вручную, с расхождением не более 1%.
- проверяется отдельными пинами теста на архивных парах со сплитом, см. tests/test_historical_run.py; агрегат по прогону не публикуется здесь без реального архива.

**ВНИМАНИЕ:** доля отказов превышает треть универсума — по правилу §8 проверка считается несостоявшейся по недостатку данных, а не пройденной или проваленной.

## Отказы поимённо

| Тикер | Дата | Причина |
|---|---|---|
| ASTS | 2018-12-24 | no trading data for ASTS on 2018-12-24 |
| ASTS | 2019-07-01 | no trading data for ASTS on 2019-07-01 |
| ASTS | 2020-03-23 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| ASTS | 2021-12-31 | revenue history insufficient for both the 3y and 5y CAGR window required by PREREG §2's growth anchor (a young name, or a gap in the as-of-filtered series) |
| ASTS | 2022-10-12 | revenue history insufficient for both the 3y and 5y CAGR window required by PREREG §2's growth anchor (a young name, or a gap in the as-of-filtered series) |
| AVGO | 2018-12-24 | terminal multiplier: roe_median_5y unavailable (see edgar_facts _flags.roe_median_5y_refused) |
| AVGO | 2019-07-01 | terminal multiplier: roe_median_5y unavailable (see edgar_facts _flags.roe_median_5y_refused) |
| CBRS | 2018-12-24 | no trading data for CBRS on 2018-12-24 |
| CBRS | 2019-07-01 | no trading data for CBRS on 2019-07-01 |
| CBRS | 2020-03-23 | no trading data for CBRS on 2020-03-23 |
| CBRS | 2021-12-31 | no trading data for CBRS on 2021-12-31 |
| CBRS | 2022-10-12 | no trading data for CBRS on 2022-10-12 |
| CELH | 2018-12-24 | revenue history insufficient for both the 3y and 5y CAGR window required by PREREG §2's growth anchor (a young name, or a gap in the as-of-filtered series) |
| CELH | 2019-07-01 | revenue history insufficient for both the 3y and 5y CAGR window required by PREREG §2's growth anchor (a young name, or a gap in the as-of-filtered series) |
| CELH | 2020-03-23 | terminal multiplier: roe_median_5y (capped) is <= 0 -- payout ratio undefined |
| CELH | 2021-12-31 | terminal multiplier: roe_median_5y (capped) is <= 0 -- payout ratio undefined |
| CELH | 2022-10-12 | terminal multiplier: roe_median_5y (capped 0.0181) <= terminal growth 0.0400 -- payout ratio would be negative; PREREG §8 does not define this case |
| DLO | 2018-12-24 | no trading data for DLO on 2018-12-24 |
| DLO | 2019-07-01 | no trading data for DLO on 2019-07-01 |
| DLO | 2020-03-23 | no trading data for DLO on 2020-03-23 |
| DLO | 2021-12-31 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| DLO | 2022-10-12 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| FOUR | 2018-12-24 | no trading data for FOUR on 2018-12-24 |
| FOUR | 2019-07-01 | no trading data for FOUR on 2019-07-01 |
| FOUR | 2020-03-23 | no trading data for FOUR on 2020-03-23 |
| FOUR | 2021-12-31 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| FOUR | 2022-10-12 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| GOOG | 2018-12-24 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| GOOG | 2019-07-01 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| GOOG | 2020-03-23 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| GOOG | 2021-12-31 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| GOOG | 2022-10-12 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| IONQ | 2018-12-24 | no trading data for IONQ on 2018-12-24 |
| IONQ | 2019-07-01 | no trading data for IONQ on 2019-07-01 |
| IONQ | 2020-03-23 | no trading data for IONQ on 2020-03-23 |
| IONQ | 2021-12-31 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| IONQ | 2022-10-12 | revenue history insufficient for both the 3y and 5y CAGR window required by PREREG §2's growth anchor (a young name, or a gap in the as-of-filtered series) |
| LLY | 2018-12-24 | both legs errored at k_exit=9%: ['RUNNER_ERROR: no positive EPS or FCF/share - Category-F, IVC N/A'] |
| MELI | 2018-12-24 | revenue history insufficient for both the 3y and 5y CAGR window required by PREREG §2's growth anchor (a young name, or a gap in the as-of-filtered series) |
| MELI | 2021-12-31 | terminal multiplier: roe_median_5y (capped) is <= 0 -- payout ratio undefined |
| MELI | 2022-10-12 | terminal multiplier: roe_median_5y (capped) is <= 0 -- payout ratio undefined |
| MP | 2018-12-24 | no trading data for MP on 2018-12-24 |
| MP | 2019-07-01 | no trading data for MP on 2019-07-01 |
| MP | 2020-03-23 | no trading data for MP on 2020-03-23 |
| MP | 2021-12-31 | revenue history insufficient for both the 3y and 5y CAGR window required by PREREG §2's growth anchor (a young name, or a gap in the as-of-filtered series) |
| MP | 2022-10-12 | terminal multiplier: roe_median_5y unavailable (see edgar_facts _flags.roe_median_5y_refused) |
| NBIS | 2018-12-24 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| NBIS | 2019-07-01 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| NBIS | 2020-03-23 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| NBIS | 2021-12-31 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| NBIS | 2022-10-12 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| NVO | 2018-12-24 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| NVO | 2019-07-01 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| NVO | 2020-03-23 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| NVO | 2021-12-31 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| NVO | 2022-10-12 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| OKLO | 2018-12-24 | no trading data for OKLO on 2018-12-24 |
| OKLO | 2019-07-01 | no trading data for OKLO on 2019-07-01 |
| OKLO | 2020-03-23 | no trading data for OKLO on 2020-03-23 |
| OKLO | 2021-12-31 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| OKLO | 2022-10-12 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| ORCL | 2022-10-12 | terminal multiplier: roe_median_5y unavailable (see edgar_facts _flags.roe_median_5y_refused) |
| OSCR | 2018-12-24 | no trading data for OSCR on 2018-12-24 |
| OSCR | 2019-07-01 | no trading data for OSCR on 2019-07-01 |
| OSCR | 2020-03-23 | no trading data for OSCR on 2020-03-23 |
| OSCR | 2021-12-31 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| OSCR | 2022-10-12 | terminal multiplier: roe_median_5y unavailable (see edgar_facts _flags.roe_median_5y_refused) |
| PLTR | 2018-12-24 | no trading data for PLTR on 2018-12-24 |
| PLTR | 2019-07-01 | no trading data for PLTR on 2019-07-01 |
| PLTR | 2020-03-23 | no trading data for PLTR on 2020-03-23 |
| PLTR | 2021-12-31 | terminal multiplier: roe_median_5y unavailable (see edgar_facts _flags.roe_median_5y_refused) |
| PLTR | 2022-10-12 | terminal multiplier: roe_median_5y unavailable (see edgar_facts _flags.roe_median_5y_refused) |
| RDDT | 2018-12-24 | no trading data for RDDT on 2018-12-24 |
| RDDT | 2019-07-01 | no trading data for RDDT on 2019-07-01 |
| RDDT | 2020-03-23 | no trading data for RDDT on 2020-03-23 |
| RDDT | 2021-12-31 | no trading data for RDDT on 2021-12-31 |
| RDDT | 2022-10-12 | no trading data for RDDT on 2022-10-12 |
| RKLB | 2018-12-24 | no trading data for RKLB on 2018-12-24 |
| RKLB | 2019-07-01 | no trading data for RKLB on 2019-07-01 |
| RKLB | 2020-03-23 | no trading data for RKLB on 2020-03-23 |
| RKLB | 2021-12-31 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| RKLB | 2022-10-12 | revenue history insufficient for both the 3y and 5y CAGR window required by PREREG §2's growth anchor (a young name, or a gap in the as-of-filtered series) |
| SHOP | 2018-12-24 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| SHOP | 2019-07-01 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| SHOP | 2020-03-23 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| SHOP | 2021-12-31 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| SHOP | 2022-10-12 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| SMR | 2018-12-24 | no trading data for SMR on 2018-12-24 |
| SMR | 2019-07-01 | no trading data for SMR on 2019-07-01 |
| SMR | 2020-03-23 | no trading data for SMR on 2020-03-23 |
| SMR | 2021-12-31 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| SMR | 2022-10-12 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| SOFI | 2018-12-24 | no trading data for SOFI on 2018-12-24 |
| SOFI | 2019-07-01 | no trading data for SOFI on 2019-07-01 |
| SOFI | 2020-03-23 | no trading data for SOFI on 2020-03-23 |
| SOFI | 2021-12-31 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| SOFI | 2022-10-12 | terminal multiplier: roe_median_5y unavailable (see edgar_facts _flags.roe_median_5y_refused) |
| SPCX | 2018-12-24 | no trading data for SPCX on 2018-12-24 |
| SPCX | 2019-07-01 | no trading data for SPCX on 2019-07-01 |
| SPCX | 2020-03-23 | no trading data for SPCX on 2020-03-23 |
| SPCX | 2021-12-31 | no trading data for SPCX on 2021-12-31 |
| SPCX | 2022-10-12 | no trading data for SPCX on 2022-10-12 |
| UBER | 2018-12-24 | no trading data for UBER on 2018-12-24 |
| UBER | 2019-07-01 | no usable base leg: net_income/shares_diluted: no common FY end available as of date; ocf/capex/shares_diluted: no common FY end available as of date |
| UBER | 2020-03-23 | terminal multiplier: roe_median_5y unavailable (see edgar_facts _flags.roe_median_5y_refused) |
| UBER | 2021-12-31 | terminal multiplier: roe_median_5y unavailable (see edgar_facts _flags.roe_median_5y_refused) |
| UBER | 2022-10-12 | terminal multiplier: roe_median_5y unavailable (see edgar_facts _flags.roe_median_5y_refused) |
| VOO | 2018-12-24 | edgar archive record has no usable '_cik' (or legacy 'cik') field |
| VOO | 2019-07-01 | edgar archive record has no usable '_cik' (or legacy 'cik') field |
| VOO | 2020-03-23 | edgar archive record has no usable '_cik' (or legacy 'cik') field |
| VOO | 2021-12-31 | edgar archive record has no usable '_cik' (or legacy 'cik') field |
| VOO | 2022-10-12 | edgar archive record has no usable '_cik' (or legacy 'cik') field |

## Посчитанные пары

| Тикер | Дата | Leg | Leg note | EPS basis FY | FCF basis FY | g | terminal_g | future_pe(8%) | future_pe(9%) | future_pe(10%) | IV | implied_CAGR% | A | Б | Shadow IV (EXPLORATORY) | Δ vs official | PE-hist медиана (примечание) | Причина недоступности второй ноги |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ADBE | 2018-12-24 | gaap_eps | dual_basis_conservative | 2017-12-01 | 2017-12-01 | 0.1064 | 0.0400 | 13.88 | 11.10 | 9.25 | 27.63 | -8.35 | - | - | 52.23 | 24.60 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ADBE | 2019-07-01 | gaap_eps | dual_basis_conservative | 2018-11-30 | 2018-11-30 | 0.1736 | 0.0400 | 18.65 | 14.92 | 12.43 | 86.74 | -1.10 | - | - | 109.79 | 23.05 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ADBE | 2020-03-23 | gaap_eps | dual_basis_conservative | 2019-11-29 | 2019-11-29 | 0.2000 | 0.0400 | 20.01 | 16.00 | 13.34 | 125.73 | 2.43 | - | - | 139.35 | 13.62 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ADBE | 2021-12-31 | gaap_eps | dual_basis_conservative | 2020-11-27 | 2020-11-27 | 0.2000 | 0.0400 | 21.39 | 17.11 | 14.26 | 242.54 | 2.88 | - | - | 185.96 | -56.58 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ADBE | 2022-10-12 | gaap_eps | dual_basis_conservative | 2021-12-03 | 2021-12-03 | 0.2000 | 0.0400 | 21.43 | 17.15 | 14.29 | 224.89 | 9.33 | - | - | 243.36 | 18.47 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| AMZN | 2018-12-24 | gaap_eps | dual_basis_conservative | 2017-12-31 | 2016-12-31 | 0.2000 | 0.0400 | 2.54 | 2.03 | 1.70 | 0.82 | -27.92 | - | - | 18.51 | 17.69 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| AMZN | 2019-07-01 | gaap_eps | dual_basis_conservative | 2018-12-31 | 2018-12-31 | 0.2000 | 0.0400 | 15.86 | 12.69 | 10.58 | 16.73 | -5.97 | - | - | 29.42 | 12.69 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| AMZN | 2020-03-23 | gaap_eps | dual_basis_conservative | 2019-12-31 | 2019-12-31 | 0.2000 | 0.0400 | 16.87 | 13.49 | 11.24 | 20.30 | -4.03 | - | - | 36.54 | 16.24 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| AMZN | 2021-12-31 | gaap_eps | dual_basis_conservative | 2020-12-31 | 2020-12-31 | 0.2000 | 0.0400 | 19.64 | 15.72 | 13.10 | 43.00 | -2.19 | - | - | 43.23 | 0.23 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| AMZN | 2022-10-12 | gaap_eps | single_leg | 2021-12-31 | 2021-12-31 | 0.2000 | 0.0400 | 20.62 | 16.50 | 13.75 | 1398.36 | 44.05 | BUY | BUY | n/a | n/a | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| AVGO | 2020-03-23 | gaap_eps | dual_basis_conservative | 2019-11-03 | 2019-11-03 | 0.1951 | 0.0400 | 15.84 | 12.68 | 10.56 | 10.47 | 6.79 | - | - | 36.52 | 26.05 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| AVGO | 2021-12-31 | gaap_eps | dual_basis_conservative | 2021-10-31 | 2021-10-31 | 0.0960 | 0.0400 | 15.84 | 12.68 | 10.56 | 13.71 | -3.59 | - | - | 27.81 | 14.10 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| AVGO | 2022-10-12 | gaap_eps | dual_basis_conservative | 2021-10-31 | 2021-10-31 | 0.0960 | 0.0400 | 15.84 | 12.68 | 10.56 | 13.71 | 0.46 | - | - | 27.81 | 14.10 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ISRG | 2018-12-24 | gaap_eps | dual_basis_conservative | 2017-12-31 | 2017-12-31 | 0.0751 | 0.0400 | 17.66 | 14.13 | 11.78 | 16.08 | -10.11 | - | - | 21.36 | 5.28 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ISRG | 2019-07-01 | fcf_per_share | dual_basis_conservative | 2018-12-31 | 2018-12-31 | 0.1046 | 0.0400 | 17.66 | 14.13 | 11.78 | 28.33 | -6.72 | - | - | 26.07 | -2.26 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ISRG | 2020-03-23 | fcf_per_share | dual_basis_conservative | 2019-12-31 | 2019-12-31 | 0.1601 | 0.0400 | 17.88 | 14.30 | 11.92 | 48.13 | 2.00 | - | - | 43.75 | -4.38 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ISRG | 2021-12-31 | gaap_eps | dual_basis_conservative | 2020-12-31 | 2020-12-31 | 0.1157 | 0.0400 | 17.88 | 14.30 | 11.92 | 98.47 | -1.60 | - | - | 96.48 | -1.99 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ISRG | 2022-10-12 | gaap_eps | dual_basis_conservative | 2021-12-31 | 2021-12-31 | 0.1531 | 0.0400 | 18.02 | 14.41 | 12.01 | 66.23 | 0.99 | - | - | 60.83 | -5.40 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| LLY | 2019-07-01 | gaap_eps | single_leg | 2018-12-31 | n/a | 0.0122 | 0.0122 | 13.66 | 11.90 | 10.55 | 13.53 | -8.61 | - | - | n/a | n/a | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | ocf/capex/shares_diluted: no common FY end available as of date |
| LLY | 2020-03-23 | gaap_eps | single_leg | 2019-12-31 | n/a | 0.0169 | 0.0169 | 14.48 | 12.50 | 11.00 | 42.33 | 1.71 | - | - | n/a | n/a | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | ocf/capex/shares_diluted: no common FY end available as of date |
| LLY | 2021-12-31 | gaap_eps | single_leg | 2020-12-31 | n/a | 0.0422 | 0.0400 | 21.96 | 17.57 | 14.64 | 57.67 | -3.85 | - | - | n/a | n/a | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | ocf/capex/shares_diluted: no common FY end available as of date |
| LLY | 2022-10-12 | gaap_eps | single_leg | 2021-12-31 | n/a | 0.0594 | 0.0400 | 22.50 | 18.00 | 15.00 | 59.78 | -5.15 | - | - | n/a | n/a | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | ocf/capex/shares_diluted: no common FY end available as of date |
| MA | 2018-12-24 | gaap_eps | dual_basis_conservative | 2017-12-31 | 2017-12-31 | 0.0967 | 0.0400 | 22.50 | 18.00 | 15.00 | 45.49 | -1.67 | - | - | 44.10 | -1.39 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| MA | 2019-07-01 | gaap_eps | dual_basis_conservative | 2018-12-31 | 2018-12-31 | 0.2000 | 0.0400 | 22.50 | 18.00 | 15.00 | 131.79 | 4.80 | - | - | 95.74 | -36.05 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| MA | 2020-03-23 | fcf_per_share | dual_basis_conservative | 2019-12-31 | 2019-12-31 | 0.2000 | 0.0400 | 22.50 | 18.00 | 15.00 | 178.85 | 10.98 | - | - | 129.17 | -49.68 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| MA | 2021-12-31 | gaap_eps | dual_basis_conservative | 2020-12-31 | 2020-12-31 | 0.1956 | 0.0400 | 22.50 | 18.00 | 15.00 | 146.21 | 2.66 | - | - | 113.40 | -32.81 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| MA | 2022-10-12 | gaap_eps | dual_basis_conservative | 2021-12-31 | 2021-12-31 | 0.0810 | 0.0400 | 22.50 | 18.00 | 15.00 | 98.52 | 1.00 | - | - | 74.18 | -24.34 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| MELI | 2019-07-01 | fcf_per_share | single_leg | 2018-12-31 | 2018-12-31 | 0.2000 | 0.0400 | 20.10 | 16.08 | 13.40 | 65.10 | -10.59 | - | - | 52.63 | -12.47 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| MELI | 2020-03-23 | fcf_per_share | single_leg | 2019-12-31 | 2019-12-31 | 0.2000 | 0.0400 | 1.36 | 1.09 | 0.91 | 9.18 | -24.24 | - | - | 109.79 | 100.61 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| META | 2018-12-24 | gaap_eps | dual_basis_conservative | 2017-12-31 | 2017-12-31 | 0.2000 | 0.0400 | 14.69 | 11.75 | 9.79 | 82.87 | 7.66 | - | - | 100.60 | 17.73 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| META | 2019-07-01 | fcf_per_share | dual_basis_conservative | 2018-12-31 | 2018-12-31 | 0.2000 | 0.0400 | 19.21 | 15.37 | 12.80 | 105.71 | 5.55 | - | - | 89.44 | -16.27 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| META | 2020-03-23 | gaap_eps | dual_basis_conservative | 2019-12-31 | 2019-12-31 | 0.2000 | 0.0400 | 19.53 | 15.63 | 13.02 | 131.41 | 10.76 | - | - | 125.45 | -5.96 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| META | 2021-12-31 | fcf_per_share | dual_basis_conservative | 2020-12-31 | 2020-12-31 | 0.2000 | 0.0400 | 20.33 | 16.27 | 13.56 | 174.17 | 4.96 | - | - | 139.18 | -34.99 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| META | 2022-10-12 | fcf_per_share | dual_basis_conservative | 2021-12-31 | 2021-12-31 | 0.2000 | 0.0400 | 20.60 | 16.48 | 13.73 | 294.99 | 21.91 | BUY | BUY | 232.72 | -62.27 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| MSFT | 2018-12-24 | gaap_eps | dual_basis_conservative | 2018-06-30 | 2018-06-30 | 0.0565 | 0.0400 | 20.93 | 16.75 | 13.96 | 18.95 | -3.91 | - | - | 28.63 | 9.68 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| MSFT | 2019-07-01 | gaap_eps | dual_basis_conservative | 2018-06-30 | 2018-06-30 | 0.0565 | 0.0400 | 20.93 | 16.75 | 13.96 | 18.95 | -7.43 | - | - | 28.63 | 9.68 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| MSFT | 2020-03-23 | fcf_per_share | dual_basis_conservative | 2019-06-30 | 2019-06-30 | 0.0770 | 0.0400 | 20.95 | 16.76 | 13.97 | 50.39 | 1.96 | - | - | 39.08 | -11.31 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| MSFT | 2021-12-31 | fcf_per_share | dual_basis_conservative | 2021-06-30 | 2021-06-30 | 0.1302 | 0.0400 | 22.33 | 17.86 | 14.89 | 112.71 | 0.78 | - | - | 82.03 | -30.68 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| MSFT | 2022-10-12 | fcf_per_share | dual_basis_conservative | 2022-06-30 | 2022-06-30 | 0.1547 | 0.0400 | 22.39 | 17.91 | 14.93 | 154.14 | 8.14 | - | - | 111.86 | -42.28 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| NFLX | 2018-12-24 | gaap_eps | single_leg | 2017-12-31 | 2017-12-31 | 0.2000 | 0.0400 | 13.14 | 10.51 | 8.76 | 1.72 | -13.73 | - | - | n/a | n/a | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| NFLX | 2019-07-01 | gaap_eps | single_leg | 2018-12-31 | 2018-12-31 | 0.2000 | 0.0400 | 18.04 | 14.43 | 12.02 | 5.07 | -8.31 | - | - | n/a | n/a | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| NFLX | 2020-03-23 | gaap_eps | single_leg | 2019-12-31 | 2019-12-31 | 0.2000 | 0.0400 | 18.59 | 14.87 | 12.39 | 8.04 | -3.60 | - | - | n/a | n/a | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| NFLX | 2021-12-31 | fcf_per_share | dual_basis_conservative | 2020-12-31 | 2020-12-31 | 0.2000 | 0.0400 | 20.67 | 16.54 | 13.78 | 9.19 | -7.20 | - | - | 7.22 | -1.97 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| NFLX | 2022-10-12 | gaap_eps | single_leg | 2021-12-31 | 2021-12-31 | 0.2000 | 0.0400 | 20.94 | 16.75 | 13.96 | 24.62 | 13.22 | BUY | BUY | n/a | n/a | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| NVDA | 2018-12-24 | fcf_per_share | dual_basis_conservative | 2018-01-28 | 2012-01-29 | 0.1781 | 0.0400 | 18.00 | 14.40 | 12.00 | 0.52 | -6.52 | - | - | 0.47 | -0.05 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| NVDA | 2019-07-01 | fcf_per_share | dual_basis_conservative | 2019-01-27 | 2012-01-29 | 0.2000 | 0.0400 | 21.54 | 17.23 | 14.36 | 0.70 | -6.14 | - | - | 0.53 | -0.17 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| NVDA | 2020-03-23 | fcf_per_share | dual_basis_conservative | 2020-01-26 | 2012-01-29 | 0.1647 | 0.0400 | 21.54 | 17.23 | 14.36 | 0.57 | -10.37 | - | - | 0.43 | -0.14 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| NVDA | 2021-12-31 | fcf_per_share | dual_basis_conservative | 2021-01-31 | 2012-01-29 | 0.1974 | 0.0400 | 21.54 | 17.23 | 14.36 | 2.77 | -11.53 | - | - | 2.09 | -0.68 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| NVDA | 2022-10-12 | fcf_per_share | dual_basis_conservative | 2022-01-30 | 2012-01-29 | 0.2000 | 0.0400 | 22.27 | 17.82 | 14.85 | 2.91 | -2.34 | - | - | 2.13 | -0.78 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ORCL | 2018-12-24 | gaap_eps | dual_basis_conservative | 2018-05-31 | 2018-05-31 | 0.0138 | 0.0138 | 14.00 | 12.16 | 10.75 | 4.05 | -10.49 | - | - | 11.35 | 7.30 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ORCL | 2019-07-01 | gaap_eps | dual_basis_conservative | 2019-05-31 | 2019-05-31 | 0.0064 | 0.0064 | 13.12 | 11.55 | 10.32 | 11.77 | -3.51 | - | - | 10.49 | -1.28 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ORCL | 2020-03-23 | gaap_eps | dual_basis_conservative | 2019-05-31 | 2019-05-31 | 0.0064 | 0.0064 | 13.12 | 11.55 | 10.32 | 11.77 | -0.97 | - | - | 10.49 | -1.28 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| ORCL | 2021-12-31 | gaap_eps | dual_basis_conservative | 2021-05-31 | 2021-05-31 | 0.0092 | 0.0092 | 13.80 | 12.09 | 10.76 | 19.40 | -3.01 | - | - | 14.62 | -4.78 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| SNPS | 2018-12-24 | fcf_per_share | dual_basis_conservative | 2018-10-31 | 2018-10-31 | 0.0973 | 0.0400 | 13.03 | 10.42 | 8.68 | 15.34 | -4.96 | - | - | 19.14 | 3.80 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| SNPS | 2019-07-01 | fcf_per_share | dual_basis_conservative | 2018-10-31 | 2018-10-31 | 0.0973 | 0.0400 | 13.03 | 10.42 | 8.68 | 15.34 | -9.65 | - | - | 19.14 | 3.80 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| SNPS | 2020-03-23 | gaap_eps | dual_basis_conservative | 2019-10-31 | 2019-10-31 | 0.1031 | 0.0400 | 13.03 | 10.42 | 8.68 | 25.94 | -2.93 | - | - | 36.61 | 10.67 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| SNPS | 2021-12-31 | gaap_eps | dual_basis_conservative | 2021-10-31 | 2021-10-31 | 0.1044 | 0.0400 | 17.33 | 13.86 | 11.55 | 48.52 | -8.55 | - | - | 84.01 | 35.49 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| SNPS | 2022-10-12 | gaap_eps | dual_basis_conservative | 2021-10-31 | 2021-10-31 | 0.1044 | 0.0400 | 17.33 | 13.86 | 11.55 | 48.52 | -5.88 | - | - | 84.01 | 35.49 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| SPGI | 2018-12-24 | gaap_eps | dual_basis_conservative | 2017-12-31 | 2017-12-31 | 0.0628 | 0.0400 | 22.50 | 18.00 | 15.00 | 57.69 | 1.85 | - | - | 52.73 | -4.96 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| SPGI | 2019-07-01 | fcf_per_share | dual_basis_conservative | 2018-12-31 | 2018-12-31 | 0.0561 | 0.0400 | 22.50 | 18.00 | 15.00 | 73.61 | 0.43 | - | - | 53.16 | -20.45 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| SPGI | 2020-03-23 | gaap_eps | dual_basis_conservative | 2019-12-31 | 2019-12-31 | 0.0577 | 0.0400 | 22.50 | 18.00 | 15.00 | 83.04 | 3.53 | - | - | 75.17 | -7.87 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| SPGI | 2021-12-31 | gaap_eps | dual_basis_conservative | 2020-12-31 | 2020-12-31 | 0.0697 | 0.0400 | 22.50 | 18.00 | 15.00 | 100.98 | -3.64 | - | - | 108.85 | 7.87 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |
| SPGI | 2022-10-12 | gaap_eps | dual_basis_conservative | 2021-12-31 | 2021-12-31 | 0.0795 | 0.0400 | 22.50 | 18.00 | 15.00 | 139.31 | 4.37 | - | - | 118.55 | -20.76 | not present in the archive record -- treated as absent per PREREG §8 (the historical median is a sanity check, not a required input) | - |

## Документированные пробелы протокола (PREREG молчит или двусмыслен)

- Внутренняя форма *_edgar.json/*_price.json не описана нигде в PREREG или в карточке — issue #30 сверил с первым реальным архивом и заменил первоначальную (неверную) догадку: *_edgar.json — готовый вывод edgar_facts.edgar_facts(), *_price.json — объект с ОДНОЙ дневной записью и уже посчитанным split_factor, а не списки сырых записей (см. docstring файла, раздел ФОРМАТ АРХИВА).
- Формула нога денежного потока (levered FCF/share) не определена в PREREG буквально — использовано стандартное отраслевое определение (OCF - capex) / shares_diluted, то же, что упоминает CLAUDE.md ('Owner-earnings third leg'); сама формула в проекте живёт в JS-ноде workflow, которую по правилам этой карточки читать нельзя (контекстная бомба).
- PREREG §8 не определяет terminal-multiplier формулу для ROE_terminal(capped) <= terminal_growth (payout был бы отрицательным/неопределённым) — реализовано как именованный отказ пары, а не подстановка.
- PREREG §8 не говорит, что делать, если pe_hist_median недоступен на дату — прочитано как 'историческая медиана — necessary только когда есть' (её роль уже понижена до проверки разумности §8), формульный потолок используется один, факт недоступности медианы отмечен флагом на строке, пара не отказывает по этой причине одной.
- pe_hist_median ни разу не встречен ни в одной из 175 записей реального архива v3 (issue #30) -- где именно в *_price.json оператор положил бы его, если когда-нибудь положит, нигде не задокументировано; читается с ВЕРХНЕГО уровня объекта (рядом с split_factor), по аналогии с остальными вычисленными полями того же объекта, а не изнутри price_record (которое по всем 175 образцам — сырая Tiingo-строка без места для добавленных полей).
- Рост (growth_rate) не имеет пола (floor) по тексту PREREG — отрицательный рост не обрезается нулём, только потолок 20% применяется, как написано.
- Универсум 34 имён нигде не перечислен (ни в PREREG, ни в карточке) — тикер×дата пары берутся из содержимого архива (какие пары оператор загрузил, те и считаются), а не из жёстко зашитого списка.
- Теневой FCFF/DCF мост (решение В4) не имеет собственной пре-регистрации методики — реализован тем же пинованным движком ivc_lib.ivc(), но с Gordon-growth терминальным мультипликатором (1+tg)/(hurdle-tg) вместо мультипликатора-как-в-официальном счёте; это самостоятельный дизайн-выбор для EXPLORATORY-моста, не значение из документа.
- confirmed_splits наследуется этим перепрогоном как есть из архивного gt['_flags'] -- историческая проверка больше не вызывает edgar_facts() сама (issue #30: архив уже несёт её готовый вывод) и поэтому не управляет тем, каким плечом (companyfacts vs companyconcept) confirmed_splits был вычислен при сборке архива; чем бы он ни был на момент сборки, тем и остаётся на момент перепрогона.
