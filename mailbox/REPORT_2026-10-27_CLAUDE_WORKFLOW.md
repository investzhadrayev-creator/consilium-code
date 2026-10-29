# REPORT 2026-10-27 — новая версия .github/workflows/claude.yml (задача #115, п.3)

Файл предложен целиком, чтобы его можно было заменить одним копированием.
Изменено ровно три вещи относительно текущего файла:
1. `timeout-minutes: 30` -> `60`;
2. `--max-turns 120` -> `200`;
3. добавлен последний шаг `if: failure() || cancelled()` — комментарий в карточку через `gh issue comment` (GH_TOKEN).
Остальное не менялось. Сам `.github/workflows/claude.yml` в этом PR не тронут
(токен бота обычно не вправе менять workflow-файлы) — применить вручную.

Что не проверено: шаг не запускался; имя ветки берётся из `git branch --show-current`
рабочего дерева раннера, при отсутствии — пишется «ветка не определена».

```yaml
name: claude

# Агент-исполнитель. Просыпается, когда в карточке задачи или в комментарии
# упомянут @claude. Делает работу и открывает заявку на изменение (pull request).
#
# Аутентификация — токеном подписки (CLAUDE_CODE_OAUTH_TOKEN), не API-ключом:
# расход идёт из лимитов подписки оператора.
#
# ВАЖНО: агент НЕ пишет в основную ветку. Только ветка + заявка на изменение.
# Приёмка архитектором перед слиянием остаётся обязательной.

on:
  issues:
    types: [opened, assigned]
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  claude:
    # экономия лимита: запускаемся только на явное упоминание
    if: |
      github.event.sender.type != 'Bot' && (
      contains(github.event.issue.body, '@claude') ||
      contains(github.event.comment.body, '@claude'))
    runs-on: ubuntu-latest
    timeout-minutes: 60
    permissions:
      contents: write
      pull-requests: write
      issues: write
      id-token: write
    steps:
      - name: Забрать репозиторий
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Агент
        uses: anthropics/claude-code-action@v1
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          TIINGO_TOKEN: ${{ secrets.TIINGO_TOKEN }}
          SEC_USER_AGENT: ${{ secrets.SEC_USER_AGENT }}
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          claude_args: >-
            --allowed-tools "Bash,Read,Write,Edit,Grep,Glob" --max-turns 200 --permission-mode acceptEdits
          prompt: |
            Ты работаешь в проекте Consilium Spine — автоматизированный equity research
            под философией Грэма-Додда. Правила проекта обязательны к исполнению:
            прочитай CLAUDE.md в корне репозитория (главный) и CLAUDE.md в новейшем
            дереве CONSILIUM_REPO_v4_2_* и следуй обоим.

            Железные правила этого проекта:
            1. Никогда не пиши в основную ветку — только ветка и заявка на изменение.
            2. Каждое изменение сопровождается пином, который проверяет СВОЙСТВО, а не форму,
               и негативным контролем (мутацией), доказывающим, что пин может покраснеть.
            3. Отказ проверки не равен проходу: SKIP, NOT_EXEC, пропущенный тест — не зелёный.
            4. Перед отгрузкой прогони `npm install`, `python run_tests.py` и
               `python tools/mutation_probe.py` в дереве версии; сьют обязан быть зелёным,
               каталог — без SKIP, GREEN и NOT_EXEC.
            5. Числа о работе бери с выхода инструментов, не из памяти и не из документов.
            6. Ничего не выдумывай: если данных нет — так и напиши. Утверждение по допущению
               вместо чтения источника — самая дорогая ошибка этого проекта.
            7. В описании заявки перечисли: что изменено, какие пины добавлены, какие мутации
               краснеют, и что осталось незакрытым.

            КАК ОФОРМИТЬ РЕЗУЛЬТАТ — обязательная последовательность:
            1) git checkout -b claude/<короткое-имя-задачи>
            2) внести правки, прогнать проверки
            3) git add -A && git commit -m "<что сделано>"
            4) git push -u origin claude/<короткое-имя-задачи>
            5) gh pr create --title "<заголовок>" --body-file /tmp/pr.md
            6) в карточку задачи написать короткий отчёт:
               gh issue comment ${{ github.event.issue.number }} --body "<итог + ссылка на заявку>"

            ГРАНИЦЫ РАБОТЫ — соблюдать строго, они экономят лимит подписки оператора:
            - работай в новейшем каталоге CONSILIUM_REPO_v4_2_* И в корневых tools/, config/,
              Reports/floor1/, Reports/pilot_*/, а также создавай mailbox/REPORT_* — если
              этого требует задача;
            - НЕ запускай ничего вне перечисленных каталогов и не устанавливай системные пакеты
              без необходимости для задачи;
            - SEC-запросы — только с User-Agent из env SEC_USER_AGENT, никогда выдуманным;
            - НЕ читай старые каталоги версий, docs/HANDOFF* (7500 строк) и Reports/;
            - если задача сформулирована противоречиво или данных не хватает — не гадай:
              напиши об этом комментарием в карточку и остановись.

            Работа без опубликованной заявки считается НЕВЫПОЛНЕННОЙ. Если какая-то команда
            вернула отказ в правах — напечатай её текст и весь план работы в лог целиком.

      - name: Сохранить протокол сессии для разбора
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: claude-session-log
          path: /home/runner/work/_temp/claude-execution-output.json
          if-no-files-found: warn

      - name: Уведомить карточку, если бот не успел или упал
        if: failure() || cancelled()
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          BRANCH="$(git branch --show-current 2>/dev/null || true)"
          gh issue comment ${{ github.event.issue.number || github.event.pull_request.number }} \
            --body "бот не успел/упал, сделанное — в ветке ${BRANCH:-<ветка не определена>}, см. прогон ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
```
