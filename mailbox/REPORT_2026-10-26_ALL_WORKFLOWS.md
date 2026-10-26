---
date: 2026-10-26
issue: 105
author: claude[bot]
kind: REPORT
---

# REPORT 2026-10-26 — ВСЕ workflow-файлы, которые нужно загрузить (issue #105)

GitHub-приложению нельзя менять `.github/workflows/*`, поэтому точные версии файлов **целиком** лежат здесь.
Цель — одна загрузка вместо трёх. Блоки собраны сверкой с тем, что сейчас лежит в `.github/workflows/` на main
(после слияния #95, #96, #98): из всех блоков отчётов 10-19/10-25 отличаются от main ровно два.

| Файл | Нужно загрузить? | Что внутри |
|---|---|---|
| `mail_bridge.yml` | **да** | #95: триггер `workflow_run` (подстраховка к расписанию) |
| `panel_weekly.yml` | **да** | #98: `SEC_USER_AGENT` + установка edgartools; #105: публикация панели не зависит от карточки |
| `operator_prs.yml` | необязательно | #97/#92: утренний слот напоминания о PR оператора (дубль к daily-report, см. REPORT_2026-10-25_NOTIFY_WORKFLOWS.md) |
| остальные 7 из отчётов (`daily_report`, `daily_audit`, `weekly_digest`, `monthly_audit`, `calibrate-auditor`, `schedule_watchdog`, `notify-failures`) | нет | совпадают с main побайтно; #97 их не меняет |

**ДОПУЩЕНИЕ (не проверено):** имя секрета Actions — `SEC_USER_AGENT`. `gh secret list` прав не имеет
(`HTTP 403: Resource not accessible by integration`, см. REPORT_2026-10-25_K1_WORKFLOWS.md). Если назван иначе — поправить в шаге карточки.

## Исправление риска (пункт 3 issue #105)

Было: «Публикация через PR» с `if: env.ALREADY_PUBLISHED != '1'` без `always()` — упавший шаг карточки
(Tiingo 429, отказ SEC) пропускал публикацию, и терялась строка ПАНЕЛИ. Стало:

1. Шаги `deps` и `card`: `id` + `continue-on-error: true` — их падение не отменяет следующие шаги.
2. Публикация: `if: always() && env.ALREADY_PUBLISHED != '1'`.
3. Новый последний шаг: если `deps` или `card` упали (`outcome == 'failure'`) — `tools/notify_failure.py`
   (ALARM в Telegram, существующий код) и `exit 1`: job красный ПОСЛЕ публикации.
4. Ограничение: `always()` означает, что публикация идёт и при падении более раннего шага (напр. самой панели
   или проверки идемпотентности). Автоматика публикует только то, что реально записано в `journal/`, `Reports/`.
   Наблюдатель `notify-failures` увидит красный job сам, т.е. ALARM может прийти дважды (шаг + наблюдатель).

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
      - name: Зависимость адаптера К2 (edgartools — пин из requirements.txt новейшего дерева)
        id: deps
        if: env.FLOOR1_PUBLISHED != '1'
        continue-on-error: true   # падение карточки не должно отменять публикацию панели (см. шаг ALARM внизу)
        run: |
          req="$(ls -d CONSILIUM_REPO_v4_2_*/ | sort -V | tail -1)microservice/requirements.txt"
          python3 -m pip install --quiet "$(grep -i '^edgartools==' "$req")"
      - name: Карточка этажа 1 (tools/floor1_card.py, задача К1)
        id: card
        if: env.FLOOR1_PUBLISHED != '1'
        continue-on-error: true   # то же: красный job — отдельным шагом ПОСЛЕ публикации
        env:
          TIINGO_TOKEN: ${{ secrets.TIINGO_TOKEN }}
          SEC_USER_AGENT: ${{ secrets.SEC_USER_AGENT }}
        run: |
          if [ -f tools/floor1_card.py ]; then python3 tools/floor1_card.py; else echo "floor1_card.py ещё не создан (задача К1)"; fi
      - name: Публикация через PR (замок main не обходится)
        if: always() && env.ALREADY_PUBLISHED != '1'
        env:
          GH_TOKEN: ${{ github.token }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python3 tools/autocommit.py "weekly panel $(date -u +%F)" journal/ Reports/
      - name: Карточка упала — ALARM в Telegram и красный job (ПОСЛЕ публикации панели)
        if: always() && (steps.deps.outcome == 'failure' || steps.card.outcome == 'failure')
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          WF_NAME: panel-weekly — шаг карточки этажа 1 упал (строка ПАНЕЛИ опубликована отдельно)
          WF_BRANCH: ${{ github.ref_name }}
          WF_EVENT: ${{ github.event_name }}
          WF_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: |
          python3 tools/notify_failure.py || echo "ALARM не отправлен (см. вывод выше)"
          echo "::error::Карточка этажа 1 не построена; панель опубликована. Повтор — следующий слот расписания."
          exit 1
```

### `.github/workflows/operator_prs.yml` (необязательный)

```yaml
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
```
