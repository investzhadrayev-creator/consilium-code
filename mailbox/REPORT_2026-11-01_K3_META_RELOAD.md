# REPORT K3 META-RELOAD (issue #140)

**ВЫВОД: OUR_DEFECT (формулировка/интерпретация, не снапшот и не загрузчик).** Блок `dei` у META есть и в живом заборе, и в фикстуре — но в нём ОДИН тег (`EntityPublicFloat`); «473» — это число тегов во ВСЕХ таксономиях фикстуры, а не в dei. Не хватает тега обложки `dei:EntityCommonStockSharesOutstanding`, и сообщение кода называет это «dei absent». SEC_BACKFILL исключён: живой забор ≈ фикстура (+4 тега us-gaap). Оговорка: какой именно снапшот и какую строку «dei отсутствует в прогоне» видела проверка №1 — установить не удалось (см. «Не установлено»).

## 1. Свежий забор (`edgar_facts._companyfacts` — путь адаптера К2, UA из env SEC_USER_AGENT)
Забор: 2026-10-31T13:51:30Z (UTC), CIK 0001326801.
| Таксономия | тегов |
|---|---|
| dei | 1 (только `EntityPublicFloat`, 14 фактов, последний end 2025-06-30, filed 2026-01-29, accn 0001628280-26-003942) |
| us-gaap | 462 |
| srt / ecd / ffd | 1 / 7 / 6 |
| всего | 477 |

`dei:EntityCommonStockSharesOutstanding` в companyfacts: **нет**. companyconcept: `dei/EntityCommonStockSharesOutstanding` HTTP 404; `us-gaap/CommonStockSharesOutstanding` HTTP 404 (curl `-w %{http_code}`).

## 2. Источники
| Источник | dei | тегов dei / всего | дата |
|---|---|---|---|
| Живой забор | есть | 1 / 477 | 2026-10-31 |
| `CONSILIUM_REPO_v4_2_83/tests/fixtures/k2/companyfacts/CIK0001326801.json.gz` | есть | 1 / 473 (us-gaap 458) | captured 2026-10-18 (manifest) |
| companyconcept в фикстуре | — | `dei/EntityCommonStockSharesOutstanding` http_status 404 | 2026-10-18 |

Разница live−fixture: us-gaap 462 vs 458, dei идентичен (то же 14 фактов). Это дозаполнение новыми данными, не появление dei. sha256 companyfacts: фикстура 7518e76d…, live e340d888… (байты разные, как и ожидалось при +4 тега).
Старый снапшот/кэш, на который опиралась проверка №1: **не найден** в доступных мне каталогах (Reports/ и docs/HANDOFF* читать запрещено правилами задачи).

## 3. Механизм отказа
- `CONSILIUM_REPO_v4_2_83/microservice/edgar_facts.py:609-626` `_shares_current`: каскад по `SHARES_CURRENT` (стр. 90), `_latest_instant(... taxonomy=tax ...)` (стр. 616) → companyconcept. У META обложка публикуется по классам (A/B), companyfacts без размерностей её не содержит, companyconcept отдаёт 404 → `(None, None)`.
- Стр. 807-817: при `None` ставится флаг `shares_current_proxied` с текстом «**dei absent** in companyfacts+companyconcept» (стр. 815). Фраза говорит про блок dei, хотя отсутствует один ТЕГ. Это и порождает ложный вывод «dei отсутствует».
- Живой прогон адаптера (`read_as_of(META, as_of=2026-10-31)`): `shares_current=None`, отказ `MULTI_CLASS_NOT_SUMMED`, флаг `shares_current_proxy_rejected` (прокси 2574000000 отброшен), path=`filing_level`.
- Побочное наблюдение: `_companyconcept` (стр. 164-178) глотает ЛЮБУЮ ошибку (`except Exception → None`), то есть 404 и сбой сети неразличимы — нарушение «missing ≠ другое» в духе правила 3. По META 404 подтверждён curl-ом отдельно.

Одной фразой: **дефект наш — сообщения/интерпретация подменяют «нет тега обложки» на «нет dei»; данные и загрузчик целы.**

## 4. Влияние на карточку этажа 1
Нет (по META и по остальным): `grep -c shares_current tools/floor1_card.py` = 0; карточка берёт `shares_chg_*` из diluted. В `Reports/floor1/FLOOR1_2026-10-31.csv` META: `shares_chg_1y=-0.0153`, `shares_chg_3y=-0.0474`, причины пустые, покрытие 100.0%; во всех 35 строках нет подстрок dei/обложк/cover/proxied. Другие мульти-классовые имена напрямую на 404 не проверялись.

## 5. Предложение (НЕ реализовано)
1. Заменить текст флага (стр. 815) на «тег обложки dei:EntityCommonStockSharesOutstanding отсутствует (companyfacts и companyconcept: 404)»; различать 404 и сетевую ошибку в `_companyconcept`.
2. Для мульти-классовых эмитентов (META, GOOG) брать обложку из filing-level (instance, размерности) — уже частично есть (`MULTI_CLASS_NOT_SUMMED`).
3. Исправить формулировку в DECISION_ROUND6 §6 новым файлом с supersedes (файл не правился).

## Не установлено
- Какой снапшот и какую точную строку «dei отсутствует в источнике» видела проверка №1: точной строки в коде нет (`grep` по репозиторию вне Reports/HANDOFF — только «dei absent», edgar_facts.py:815).
- Происхождение «473»: совпадает с общим числом тегов в фикстуре (1+458+1+7+6), не с dei.
