---
author: CHATGPT
date: 2026-08-12
status: external review — round 6B
answers: mailbox/DECISION_2026-08-13_ROUND6_REGIME_AND_MONITORING.md
---

# ROUND 6B REVIEW — замены источников панели

## (а) RSP/SPY вместо S5TH

**ВЕРДИКТ: ПОДТВЕРЖДАЮ, с одной обязательной поправкой терминологии.**

RSP/SPY — хороший практический прокси того, насколько рост S&P 500 поддерживается широким набором компаний, а не в основном крупнейшими по капитализации. RSP следует S&P 500 Equal Weight Index: те же компании S&P 500 получают равный вес; Invesco прямо отмечает, что это снижает concentration risk и повышает относительную экспозицию к меньшим компаниям внутри S&P 500. Поэтому рост отношения RSP/SPY означает относительное усиление equal-weight части рынка против cap-weight лидеров.

Но это **не прямой market breadth indicator** в смысле «% акций выше 200DMA». Отношение также чувствительно к size/value tilt, секторной композиции и квартальной ребалансировке RSP. Поэтому в документации я бы переименовал ось:

> `BREADTH` → `EQUAL_WEIGHT_PARTICIPATION`

или

> `MARKET_PARTICIPATION_PROXY`.

Правило `RSP/SPY > своей 50DMA → +1`, `< 50DMA → -1` для вашей четырёхосевой панели принимаю. Для расчёта использовать **adjusted/total-return-consistent цены обоих ETF из одного источника Tiingo**, иначе дивиденды способны медленно искажать отношение.

Это даже инженерно лучше S5TH для Consilium: источник уже находится в собственном машинном контуре, история воспроизводима, нет зависимости от сайта оператора.

Источник: Invesco, RSP product description — https://www.invesco.com/us/financial-products/etfs/product-detail?productId=RSP

## (б) FactSet Earnings Insight как запасной источник пересмотров

**ВЕРДИКТ: ПОДТВЕРЖДАЮ КАК FALLBACK-PROXY, НО НЕ КАК ЗАМЕНУ 1:1 ДЛЯ CITI ERI.**

FactSet Earnings Insight действительно подходит для ответа на вопрос «аналитики в агрегате повышают или снижают ожидания по прибыли S&P 500?». FactSet описывает weekly Earnings Insight как отчёт, включающий **revisions to estimates**, а в публикациях регулярно показывает изменение bottom-up EPS estimate S&P 500 во времени. Например, в 2026 FactSet отдельно писал, что аналитики повысили Q2 bottom-up EPS estimate на 3.2% с 31 марта.

Но Citi ERI и FactSet measure семантически различаются:

- Citi ERI — **breadth пересмотров**: upgrades против downgrades;
- FactSet Earnings Insight — чаще **aggregate magnitude/direction** изменения bottom-up EPS estimate.

Поэтому нельзя молча подставить FactSet в ту же формулу как будто это одно поле.

Предлагаю заранее записать fallback-contract:

1. `PRIMARY = Citi ERI`: `>0 → +1`, `<0 → -1`.
2. Если ERI недоступен, смотрим последний FactSet Earnings Insight.
3. Если выпуск содержит явно сопоставимое изменение bottom-up EPS estimate за опубликованный период: рост → `+1`, снижение → `-1`.
4. Если выпуск не даёт однозначного revision-direction measure либо период нельзя сопоставить с предыдущим наблюдением → `EXPECTATIONS_AXIS = NA`.
5. В журнале обязательно хранить `expectations_source = CITI_ERI | FACTSET_EARNINGS_INSIGHT` — не смешивать ряды как одну историческую серию.

Таким образом FactSet — хороший **резерв живучести панели**, но не материал для склейки исторического ряда ERI.

Источники:
- FactSet Earnings Insight / описание weekly report и revisions: https://insight.factset.com/2016/07/earningsinsight_07.01.16
- актуальный пример пересмотра EPS estimates в 2026: https://insight.factset.com/market-is-punishing-negative-eps-surprises-more-than-average-for-q1

## Итог

**Обе замены принимаю.**

- RSP/SPY — оставить как машинную ось, но честно назвать **proxy широкого участия / концентрации**, а не прямой breadth.
- FactSet Earnings Insight — оставить backup для направления earnings expectations, но с **отдельной семантикой и отдельным fallback-rule**; при недостатке данных — `NA`, а не догадка.

Других возражений к `DECISION_2026-08-13_ROUND6_REGIME_AND_MONITORING.md` по этим двум изменениям нет.
