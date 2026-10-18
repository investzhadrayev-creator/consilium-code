Задача К1 (P0, после К2): генератор карточки этажа 1 — tools/floor1_card.py.

Контекст: mailbox/DECISION_2026-10-11_ROUND7_REBOOT.md (состав карточки),
CLAUDE.md. Вход: SEC (через адаптер К2) + Tiingo (TIINGO_TOKEN в env).
Выход: Reports/floor1/FLOOR1_<YYYY-MM-DD>.md + .csv по watchlist
(consilium-spine/07_ops/watchlist_seed.csv; при недоступности — список
в файле задачи уточнит архитектор отдельным Issue).

Поля на имя: рост выручки 3л/5л + ускорение; маржи против 5-летней медианы;
EPS рядом с NI и FCF; FCF/NI; изменение акций 1г/3г; чистый долг и тренд;
RS против VOO и QQQ 4/13 недель; просадка от 52w-max. Флаги с именованной
уликой: CYCLE_PEAK, CASH_CONV_DIVERGENCE, BUYBACK_EPS, DEBT_FOR_BUYBACKS.
Отсутствие данных — явное поле причины (missing ≠ zero). Minimal correct
важнее богатой визуализации (вердикт рецензентов).

DoD: один запуск на всём watchlist; покрытие ≥95% или named limitation
по имени; 0 подстановок; consumer-test на 3 имени с известными значениями;
вызывается из panel_weekly.yml (уже ждёт файл). Результат — PR.

@claude Исполни задачу. Результат — PR.
