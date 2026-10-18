Задача К2 (P0, первая): адаптер edgartools + goldens.

Контекст: mailbox/DECISION_2026-10-11_ROUND7_REBOOT.md, CLAUDE.md.

1. Запинить edgartools==5.48.0 (requirements; ≥5.39.1 обязательно — багфикс
   filing_date, денежный класс для as-of).
2. Архитектура: библиотека — транспорт/парсер; НАШИМИ остаются as_of-срез
   (filed ≤ дата), basis/период, агрегация размерностей (классы акций GOOG
   нельзя суммировать автоматически), сверка акций/сплитов, staleness,
   provenance, именованный отказ. Fast path companyfacts; при missing/
   размерном конфликте — filing-level XBRL.
3. Goldens (обязательны зелёными одним прогоном): MU as_of 2018-10-15;
   INTC as_of 2022-01-25; META и GOOG на датах проверки №1 — читаются БЕЗ
   ручной починки. Фикстуры = реальные данные, byte-for-byte.
4. DoD: goldens зелёные; версия запинена; consumer-tests; отчёт-файл
   mailbox/REPORT_<дата>_K2.md с измеренными числами с выхода инструментов.

@claude Исполни задачу. Результат — PR.
