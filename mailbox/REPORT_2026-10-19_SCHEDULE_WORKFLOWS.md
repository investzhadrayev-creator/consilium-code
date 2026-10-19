---
date: 2026-10-19
issue: 70
author: claude[bot]
kind: REPORT
---

# REPORT 2026-10-19 — SCHEDULE WORKFLOWS (issue #70)

GitHub-приложению нельзя менять `.github/workflows/*` (как и в 0.6), поэтому точные новые версии
**целиком** лежат здесь; оператор применяет их вручную (копирует блоки в соответствующие файлы).
Код (`tools/`), тесты и мутации — в PR. Пока файлы не заменены, в репозитории работают старые cron.

Что меняется в workflow, помимо расписаний:

1. **Шаг идемпотентности** `python3 tools/schedule_guard.py check <workflow>` — до основной работы.
   Результат периода уже на `origin/main` → `ALREADY_PUBLISHED=1` в `$GITHUB_ENV`, остальные шаги
   пропускаются, job зелёный, без PR / Telegram. Сами скрипты (`daily_report.py`, `daily_audit.py`,
   `monthly_audit.py`, `weekly_digest.py`, `panel_axes.py --append`) проверяют то же самое повторно:
   защита не держится на одном YAML.
2. **`concurrency`** у каждого workflow с несколькими слотами — слоты не работают одновременно.
3. **`permissions: actions: read`** там, где скрипт зовёт `gh run list` (daily-report, daily-audit,
   monthly, weekly-digest, watchdog). При явном блоке `permissions` невыписанные права = `none`;
   проверить, давал ли `gh run list` в этих job'ах данные до сих пор, по логам я не могу
   (логи Actions мне недоступны) — право добавлено на всякий случай, оно read-only.
4. **Новый `schedule-watchdog.yml`** — отдельный самый поздний слот сторожа панели
   (воскресенье 07:37 UTC, после последнего слота панели 05:07 + запас).
5. **`notify-failures.yml`** — в список наблюдаемых добавлены `weekly-digest` и `schedule-watchdog`.

Расписание (UTC; все минуты вне 0/15/30/45):

| workflow | слоты | ключ «опубликовано» (на main) |
|---|---|---|
| mail-bridge | `17,47 * * * *` | дедуп по Message-ID внутри скрипта |
| daily-report | 15:37, 17:07 | `journal/digests/DAILY_<дата>.md` |
| daily-audit | 16:07, 17:37 | `journal/audits/DAILY_AUDIT_<дата>.md` |
| panel-weekly | сб 05:07, 08:07, 12:07, 16:07; вс 05:07 | строка `week_end` этой ISO-недели в `journal/PANEL_LOG.csv` (+ `Reports/floor1/FLOOR1_<дата>.md` этой недели, когда `tools/floor1_card.py` появится на main) |
| weekly-digest | сб 07:37, 13:37 | успешный прогон workflow на этой неделе (письмо файла не оставляет) |
| monthly-architect-audit | 1-е 06:07, 12:07; 2-е 06:07 | `journal/audits/MONTHLY_ARCHITECT_AUDIT_<YYYY-MM>.md` |
| calibrate-auditor | 16:53, 18:23 | сам скрипт: заявка без ответа (идемпотентен по файлу ответа) |
| schedule-watchdog | вс 07:37 | сторож панели: `schedule_guard.py watch --only panel-weekly --notify` |

Порядок «отчёт → аудит» сохранён в обоих слотах (15:37 < 16:07, 17:07 < 17:37).

### `.github/workflows/mail_bridge.yml`

```yaml
name: mail-bridge
on:
  schedule:
    - cron: '17,47 * * * *'
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
```

### `.github/workflows/daily_report.yml`

```yaml
name: daily-report
on:
  schedule:
    - cron: '37 15 * * *'   # основной слот, 20:37 Астана
    - cron: '7 17 * * *'    # резерв: GitHub пропускает запуски под нагрузкой
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
  issues: write
  actions: read
concurrency: { group: daily-report, cancel-in-progress: false }
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Идемпотентность (результат дня уже на main?)
        env:
          GH_TOKEN: ${{ github.token }}
        run: python3 tools/schedule_guard.py check daily-report
      - if: env.ALREADY_PUBLISHED != '1'
        env:
          GH_TOKEN: ${{ github.token }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          OPERATOR_EMAIL: ${{ secrets.OPERATOR_EMAIL }}
        run: python3 tools/daily_report.py
      - name: Валидатор данных на main за 26 ч (замена PR-проверке, которая не стартует на auto/* PR)
        if: always() && env.ALREADY_PUBLISHED != '1'
        run: |
          BASE=$(git rev-list -1 --before="26 hours ago" origin/main || true)
          if [ -z "$BASE" ]; then echo "BASE не определён: история короче 26 ч — проверка не выполнена"; exit 1; fi
          BASE="$BASE" HEAD=origin/main python3 tools/validate_artifacts.py
```

### `.github/workflows/daily_audit.yml`

```yaml
name: daily-audit
on:
  schedule:
    - cron: '7 16 * * *'    # основной слот, 21:07 Астана, после отчёта (15:37)
    - cron: '37 17 * * *'   # резерв, после резерва отчёта (17:07)
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
  issues: write
  actions: read
concurrency: { group: daily-audit, cancel-in-progress: false }
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Идемпотентность (аудит дня уже на main?)
        env:
          GH_TOKEN: ${{ github.token }}
        run: python3 tools/schedule_guard.py check daily-audit
      - name: Аудитор «сказано — сделано» (чёт→OpenAI, нечет→Gemini)
        if: env.ALREADY_PUBLISHED != '1'
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
```

### `.github/workflows/panel_weekly.yml`

```yaml
name: panel-weekly
on:
  schedule:
    - cron: '7 5 * * 6'     # суббота, основной слот (10:07 Астана)
    - cron: '7 8 * * 6'     # резервы: один пропущенный запуск = сорванная неделя гейта
    - cron: '7 12 * * 6'
    - cron: '7 16 * * 6'
    - cron: '7 5 * * 0'     # воскресенье: последний слот (сторож — schedule-watchdog, 07:37)
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
  issues: write
concurrency: { group: panel-weekly, cancel-in-progress: false }
jobs:
  panel:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Идемпотентность (строка недели / карточка уже на main?)
        run: python3 tools/schedule_guard.py check panel-weekly
      - name: Панель режима (3 машинные оси; ERI/CNN = NA)
        if: env.PANEL_ROW_PUBLISHED != '1'
        env:
          TIINGO_TOKEN: ${{ secrets.TIINGO_TOKEN }}
          FRED_API_KEY: ${{ secrets.FRED_API_KEY }}
        run: |
          python3 tools/panel_axes.py --append || echo "PANEL_INSUFFICIENT=1" >> "$GITHUB_ENV"
      - name: Карточка этажа 1 (появится после задачи К1)
        if: env.FLOOR1_PUBLISHED != '1'
        env:
          TIINGO_TOKEN: ${{ secrets.TIINGO_TOKEN }}
        run: |
          if [ -f tools/floor1_card.py ]; then python3 tools/floor1_card.py; else echo "floor1_card.py ещё не создан (задача К1)"; fi
      - name: Публикация через PR (замок main не обходится)
        if: env.ALREADY_PUBLISHED != '1'
        env:
          GH_TOKEN: ${{ github.token }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python3 tools/autocommit.py "weekly panel $(date -u +%F)" journal/ Reports/
```

### `.github/workflows/weekly_digest.yml`

```yaml
name: weekly-digest
on:
  schedule:
    - cron: '37 7 * * 6'    # суббота, после основного слота панели (05:07)
    - cron: '37 13 * * 6'   # резерв, после слота панели 12:07
  workflow_dispatch:
permissions:
  contents: read
  actions: read
concurrency: { group: weekly-digest, cancel-in-progress: false }
jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - env:
          GH_TOKEN: ${{ github.token }}
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          OPERATOR_EMAIL: ${{ secrets.OPERATOR_EMAIL }}
        run: python3 tools/weekly_digest.py
```

### `.github/workflows/monthly_audit.yml`

```yaml
name: monthly-architect-audit
on:
  schedule:
    - cron: '7 6 1 * *'     # 1-е число, основной слот
    - cron: '7 12 1 * *'    # 1-е число, резерв
    - cron: '7 6 2 * *'     # 2-е число, резерв на случай потери обоих
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
  issues: write
  actions: read
concurrency: { group: monthly-audit, cancel-in-progress: false }
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Идемпотентность (аудит месяца уже на main?)
        env:
          GH_TOKEN: ${{ github.token }}
        run: python3 tools/schedule_guard.py check monthly-architect-audit
      - if: env.ALREADY_PUBLISHED != '1'
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
        run: python3 tools/monthly_audit.py
```

### `.github/workflows/calibrate-auditor.yml`

```yaml
name: calibrate-auditor
# Калибровка аудитора (решение оператора 2026-10-19). Исполняется, только если есть
# mailbox/CALIBRATION_REQUEST_*.md без ответа (tools/calibrate_auditor.py сам это проверяет,
# повторный слот при готовом ответе ничего не делает). Cron нужен потому, что слияния токеном
# Actions не запускают другие workflows.
on:
  schedule:
    - cron: '53 16 * * *'
    - cron: '23 18 * * *'   # резерв
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
  issues: write
concurrency: { group: calibrate-auditor, cancel-in-progress: false }
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
```

### `.github/workflows/schedule_watchdog.yml` (новый файл)

```yaml
name: schedule-watchdog
# Самый поздний слот сторожа панели: после последнего слота panel-weekly (вс 05:07 UTC) строки
# этой недели нет на main -> Telegram немедленно + красный job. Общий сторож по всем
# расписаниям живёт в daily-report (раздел «Пропущенные запуски»).
on:
  schedule:
    - cron: '37 7 * * 0'
  workflow_dispatch:
permissions:
  contents: read
  actions: read
jobs:
  watch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Сторож панели
        env:
          GH_TOKEN: ${{ github.token }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python3 tools/schedule_guard.py watch --only panel-weekly --notify
```

### `.github/workflows/notify-failures.yml`

```yaml
name: notify-failures
# Наблюдатель: любой упавший job автоматики -> Telegram. Ловит и падения до старта шагов
# (startup_failure), которые step-level failure() увидеть не может.
on:
  workflow_run:
    workflows: [mail-bridge, daily-audit, monthly-architect-audit, daily-report, review-round, panel-weekly, calibrate-auditor, weekly-digest, schedule-watchdog]
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
```

## Что НЕ проверено (named limitations)

- Сами YAML не исполнялись: у меня нет Actions. Что проверено: (а) все 9 блоков разобраны как YAML
  парсером js-yaml (разовая проверка из зависимостей eslint, в тесты не входит — pyyaml в среде нет;
  результат: 9 из 9 разобраны, ключи верхнего уровня и job'ы на месте); (б) тесты
  `test_schedule_guard.TestDeliveredWorkflows` разбирают блоки регулярками: cron вне пиковых минут,
  число и порядок слотов, шаг идемпотентности до основной работы и условия `if`; `schedule_guard.py`
  в тестах читает cron именно из этих блоков. Синтаксис шагов (`if:` на env из `$GITHUB_ENV`) движком
  Actions не проверялся.
- Поведение `gh run list --created ">=ДАТА"` и права `actions: read` проверены только по
  документации `gh`, не живым вызовом. Сторож различает отказ источника (`UNKNOWN` + причина) и
  пропуск (`MISSING`), поэтому ошибка здесь проявится как громкий `UNKNOWN`, а не как зелёное.
- GitHub может задерживать запуск не на минуты, а на часы (в карточке: 2 запуска из ~10 за 17 ч).
  Резервы снижают риск, но не доказывают его отсутствие: поэтому сторож.
