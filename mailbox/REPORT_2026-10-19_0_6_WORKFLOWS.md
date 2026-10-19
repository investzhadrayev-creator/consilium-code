# REPORT 2026-10-19 — задача 0.6: новые версии .github/workflows/ (целиком)

Причина файла: пуш изменений в `.github/workflows/` отклонён платформой —
`refusing to allow a GitHub App to create or update workflow `.github/workflows/calibrate-auditor.yml` without `workflows` permission`.
Обход не применялся. Ниже ТОЧНЫЕ новые версии файлов; оператор кладёт их в `.github/workflows/` вручную
(PR с этим файлом + tools/ слить может только оператор — CODEOWNERS).

Что изменено (относительно main):
- `mail_bridge.yml`: cron `17 * * * *` (раз в час), env TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID (п. 1, 8).
- `daily_audit.yml`, `monthly_audit.yml`, `review_round.yml`, `panel_weekly.yml`: env TELEGRAM_* (п. 8).
- `daily_report.yml`: env TELEGRAM_*; последним шагом (`if: always()`) валидатор данных на main за 26 ч — замена PR-проверке, которая не стартует на auto/* PR (п. 6, предложение).
- НОВЫЙ `notify-failures.yml`: наблюдатель workflow_run -> Telegram о любом упавшем job автоматики (п. 8).
- НОВЫЙ `calibrate-auditor.yml`: cron раз в сутки + workflow_dispatch (п. 9).

Все файлы проверены `yaml.safe_load` без ошибок.

## `.github/workflows/mail_bridge.yml`

````yaml
name: mail-bridge
on:
  schedule:
    - cron: '17 * * * *'
  workflow_dispatch:
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
````

## `.github/workflows/daily_audit.yml`

````yaml
name: daily-audit
on:
  schedule:
    - cron: '0 16 * * *'   # 21:00 Астана, после отчёта
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
  issues: write
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Аудитор «сказано — сделано» (чёт→OpenAI, нечет→Gemini)
        env:
          GH_TOKEN: ${{ github.token }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          OPENAI_MODEL: ${{ vars.OPENAI_MODEL }}
          GEMINI_MODEL: ${{ vars.GEMINI_MODEL }}
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          OPERATOR_EMAIL: ${{ secrets.OPERATOR_EMAIL }}
        run: python3 tools/daily_audit.py
````

## `.github/workflows/monthly_audit.yml`

````yaml
name: monthly-architect-audit
on:
  schedule:
    - cron: '0 6 1 * *'
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
  issues: write
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - env:
          GH_TOKEN: ${{ github.token }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          OPENAI_MODEL: ${{ vars.OPENAI_MODEL }}
          GEMINI_MODEL: ${{ vars.GEMINI_MODEL }}
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          OPERATOR_EMAIL: ${{ secrets.OPERATOR_EMAIL }}
        run: python3 tools/monthly_audit.py
````

## `.github/workflows/daily_report.yml`

````yaml
name: daily-report
on:
  schedule:
    - cron: '30 15 * * *'   # 20:30 Астана
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
  issues: write
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - env:
          GH_TOKEN: ${{ github.token }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          OPERATOR_EMAIL: ${{ secrets.OPERATOR_EMAIL }}
        run: python3 tools/daily_report.py
      - name: Валидатор данных на main за 26 ч (замена PR-проверке, которая не стартует на auto/* PR)
        if: always()
        run: |
          BASE=$(git rev-list -1 --before="26 hours ago" origin/main || true)
          if [ -z "$BASE" ]; then echo "BASE не определён: история короче 26 ч — проверка не выполнена"; exit 1; fi
          BASE="$BASE" HEAD=origin/main python3 tools/validate_artifacts.py
````

## `.github/workflows/review_round.yml`

````yaml
name: review-round
on:
  workflow_dispatch:
    inputs:
      round_file:
        description: 'Путь к файлу раунда, например mailbox/ROUND8_....md'
        required: true
permissions:
  contents: write
  pull-requests: write
  issues: write
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - env:
          GH_TOKEN: ${{ github.token }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          OPENAI_MODEL: ${{ vars.OPENAI_MODEL }}
          GEMINI_MODEL: ${{ vars.GEMINI_MODEL }}
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          OPERATOR_EMAIL: ${{ secrets.OPERATOR_EMAIL }}
        run: python3 tools/review_round.py "${{ inputs.round_file }}"
````

## `.github/workflows/panel_weekly.yml`

````yaml
name: panel-weekly
on:
  schedule:
    - cron: '0 5 * * 6'   # суббота 05:00 UTC = 10:00 Астана
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
  issues: write
jobs:
  panel:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Панель режима (3 машинные оси; ERI/CNN = NA)
        env:
          TIINGO_TOKEN: ${{ secrets.TIINGO_TOKEN }}
          FRED_API_KEY: ${{ secrets.FRED_API_KEY }}
        run: |
          python3 tools/panel_axes.py --append || echo "PANEL_INSUFFICIENT=1" >> "$GITHUB_ENV"
      - name: Карточка этажа 1 (появится после задачи К1)
        env:
          TIINGO_TOKEN: ${{ secrets.TIINGO_TOKEN }}
        run: |
          if [ -f tools/floor1_card.py ]; then python3 tools/floor1_card.py; else echo "floor1_card.py ещё не создан (задача К1)"; fi
      - name: Публикация через PR (замок main не обходится)
        env:
          GH_TOKEN: ${{ github.token }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python3 tools/autocommit.py "weekly panel $(date -u +%F)" journal/ Reports/
````

## `.github/workflows/notify-failures.yml` (НОВЫЙ)

````yaml
name: notify-failures
# Наблюдатель: любой упавший job автоматики -> Telegram. Ловит и падения до старта шагов
# (startup_failure), которые step-level failure() увидеть не может.
on:
  workflow_run:
    workflows: [mail-bridge, daily-audit, monthly-architect-audit, daily-report, review-round, panel-weekly, calibrate-auditor]
    types: [completed]
permissions:
  contents: read
jobs:
  notify:
    if: github.event.workflow_run.conclusion == 'failure' || github.event.workflow_run.conclusion == 'startup_failure'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Telegram
        env:
          WF_NAME: ${{ github.event.workflow_run.name }}
          WF_URL: ${{ github.event.workflow_run.html_url }}
          WF_BRANCH: ${{ github.event.workflow_run.head_branch }}
          WF_EVENT: ${{ github.event.workflow_run.event }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python3 tools/notify_failure.py
````

## `.github/workflows/calibrate-auditor.yml` (НОВЫЙ)

````yaml
name: calibrate-auditor
# Калибровка аудитора (решение оператора 2026-10-19). Исполняется, только если есть
# mailbox/CALIBRATION_REQUEST_*.md без ответа (tools/calibrate_auditor.py сам это проверяет).
# Cron нужен потому, что слияния токеном Actions не запускают другие workflows.
on:
  schedule:
    - cron: '45 16 * * *'
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
  issues: write
jobs:
  calibrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Калибровка Gemini-кандидата против GEMINI_MODEL
        env:
          GH_TOKEN: ${{ github.token }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GEMINI_MODEL: ${{ vars.GEMINI_MODEL }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python3 tools/calibrate_auditor.py
````
