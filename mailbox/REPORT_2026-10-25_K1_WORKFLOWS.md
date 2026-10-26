---
date: 2026-10-25
issue: 90
author: claude[bot]
kind: REPORT
---

# REPORT 2026-10-25 — K1 WORKFLOWS (issue #90)

GitHub-приложению нельзя менять `.github/workflows/*`, поэтому точная версия файла **целиком** лежит здесь;
оператор копирует блок в `.github/workflows/panel_weekly.yml`. Пока файл не заменён, карточка в Actions
запускается БЕЗ `SEC_USER_AGENT`: `tools/floor1_card.py` в этом случае завершится кодом 2 и карточку не запишет
(карточка из одних отказов — не карточка), job станет красным.

Что меняется относительно версии из `REPORT_2026-10-19_SCHEDULE_WORKFLOWS.md` (diff — только шаг карточки):

1. В шаг карточки добавлен `SEC_USER_AGENT: ${{ secrets.SEC_USER_AGENT }}`.
   **ДОПУЩЕНИЕ:** имя секрета Actions — `SEC_USER_AGENT`. Проверить не смог: `gh secret list` вернул
   `HTTP 403: Resource not accessible by integration`. Если секрет назван иначе — поправить имя в этой строке.
2. Перед карточкой добавлен шаг `pip install` пина `edgartools==…`, который берётся из `requirements.txt`
   новейшего дерева (один источник пина, как у теста K2-08). Без него `LiveLoader` адаптера не импортируется
   на чистом runner'е.
3. Порядок шагов, расписание, `concurrency`, идемпотентность и публикация через PR не тронуты.

Время выполнения: живой прогон на всех 34 именах (SEC + Tiingo) занял около 60 с на машине агента, т.е. далеко от
лимита job'а; с установкой edgartools — ещё порядка десятков секунд.

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
        if: env.FLOOR1_PUBLISHED != '1'
        run: |
          req="$(ls -d CONSILIUM_REPO_v4_2_*/ | sort -V | tail -1)microservice/requirements.txt"
          python3 -m pip install --quiet "$(grep -i '^edgartools==' "$req")"
      - name: Карточка этажа 1 (tools/floor1_card.py, задача К1)
        if: env.FLOOR1_PUBLISHED != '1'
        env:
          TIINGO_TOKEN: ${{ secrets.TIINGO_TOKEN }}
          SEC_USER_AGENT: ${{ secrets.SEC_USER_AGENT }}
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
