---
date: 2026-10-25
issue: 94
author: claude[bot]
kind: REPORT
---

# REPORT 2026-10-25 — BRIDGE WORKFLOWS (issue #94)

GitHub-приложению нельзя менять `.github/workflows/*`, поэтому точная новая версия файла **целиком**
лежит здесь; оператор применяет её вручную (копирует блок в файл). Код (`tools/schedule_guard.py`),
тесты и мутации — в PR.

## Факт из задачи (не проверялся мной)

2026-10-25 письма-команды отправлены в 06:34–06:52 UTC; `mail_bridge.yml` с cron `17,47 * * * *` на main с
06:41 UTC; к 08:57 UTC в `journal/architect_commands.log` новых строк нет. Логи Actions мне недоступны —
вывод «частое расписание GitHub исполняет ненадёжно» взят из задачи, мной не подтверждён.

## Что меняется в workflow

`mail_bridge.yml`: `schedule` и `workflow_dispatch` сохранены без изменений; **добавлен** триггер
`workflow_run` на завершение `daily-report`, `daily-audit`, `panel-weekly`, `weekly-digest`,
`calibrate-auditor` (`types: [completed]`). Имена — это `name:` из соответствующих файлов в
`.github/workflows/` (проверяется тестом). Сам `mail-bridge` в списке нет (иначе петля). Дедуп по
Message-ID и `concurrency: bridge` уже были и не тронуты. `workflow_run` срабатывает по любому
завершению (в т.ч. упавшему) — мосту это безразлично, ему нужен лишь повод запуститься.

Ограничение GitHub: `workflow_run` берётся из файла на ветке по умолчанию, поэтому до замены файла
на main новый триггер не действует.

### `.github/workflows/mail_bridge.yml`

```yaml
name: mail-bridge
on:
  schedule:
    - cron: '17,47 * * * *'
  workflow_dispatch:
  workflow_run:
    workflows: [daily-report, daily-audit, panel-weekly, weekly-digest, calibrate-auditor]
    types: [completed]
permissions:
  contents: write
  issues: write
  pull-requests: write
concurrency: { group: bridge, cancel-in-progress: false }
jobs:
  bridge:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Исполнение писем-команд архитектора
        env:
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          MAIL_AUTH_TOKEN: ${{ secrets.MAIL_AUTH_TOKEN }}
          CONSILIUM_PAT: ${{ secrets.CONSILIUM_PAT }}
          GH_TOKEN: ${{ github.token }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python3 tools/mail_bridge.py
```

## Сторож моста (код, не workflow)

`schedule_guard.watch` для `mail-bridge` теперь меряет возраст последнего УСПЕШНОГО прогона
(`gh run list --workflow mail_bridge.yml`, любой event). Старше 6 ч → алярм
«Мост не запускался N ч — Actions → mail-bridge → Run workflow <ссылка>». Нет успешного прогона в
окне → «более N ч» (нижняя граница). `gh` недоступен → `UNKNOWN` с причиной. Сторож живёт в разделе
«Пропущенные запуски» daily-report; прав в `daily_report.yml` менять не нужно (`actions: read` есть).
Прежнее правило «0 запусков по расписанию за 24 ч» заменено: с `workflow_run` мост законно работает без
schedule-событий.
