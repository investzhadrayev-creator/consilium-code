# REPORT 2026-10-25 — issue #92: workflow для напоминания о PR оператора (по желанию)

Причина файла: изменения в `.github/workflows/` бот-приложение пушить не может (нет права `workflows`,
см. `REPORT_2026-10-19_0_6_WORKFLOWS.md`). Обход не применялся. Ниже — ТОЧНАЯ версия нового файла;
оператор кладёт его в `.github/workflows/` вручную (PR с этим файлом слить может только оператор).

## Что нужно, а что нет

- Напоминание **в daily_report** (`tools/daily_report.py`) работает БЕЗ изменений workflow: `daily_report.yml`
  уже даёт `GH_TOKEN` и `TELEGRAM_*`, а права `pull-requests: write` покрывают чтение PR. Один раз в сутки:
  второй (резервный) слот отсекается `schedule_guard.skip_if_published`.
- Утренний слот ~05:07 UTC (отдельный файл ниже) — **необязателен**. Если включить его вместе с daily_report,
  оператор получит напоминание ДВАЖДЫ в сутки (утром и в ~20:37 по Астане): общего хранилища «уже слали
  сегодня» нет. Решение оператора: оставить только daily_report (ничего не класть) либо добавить утренний слот.
- Команда моста `[CONSILIUM-NOTIFY]` с `!ACTION`/`!ALARM` — без изменений workflow (`mail_bridge.yml`).
- Новый workflow не зарегистрирован в `schedule_guard.SPECS`: сторож расписаний его пропуск не заметит.

## `.github/workflows/operator_prs.yml` (необязательный)

````yaml
name: operator-prs
on:
  schedule:
    - cron: '7 5 * * *'     # ~10:07 Астана; GitHub может задержать запуск под нагрузкой
  workflow_dispatch:
permissions:
  contents: read
  pull-requests: read
concurrency: { group: operator-prs, cancel-in-progress: false }
jobs:
  remind:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - env:
          GH_TOKEN: ${{ github.token }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python3 tools/operator_prs.py
````

Проверка файла: `yaml.safe_load` — см. описание PR.
