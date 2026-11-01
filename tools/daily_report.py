#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ежедневный отчёт оператору «сделано / сложности / впереди» (в дни, когда шла работа).
Автосборка из фактов: коммиты, упавшие прогоны, открытые задачи, незакрытые пункты аудита.
Сохраняется в journal/digests/ и уходит письмом. Пустой день → выход без письма и коммита."""
import datetime as dt, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import llm_clients as L
import audit_facts as F
import schedule_guard as G
import operator_prs as OP

def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout

def jobs_count(rid):
    """Число jobs прогона; None, если gh не ответил (отказ ≠ «jobs пусты»)."""
    out = sh("gh", "run", "view", str(rid), "--json", "jobs", "--jq", ".jobs|length").strip()
    return int(out) if out.isdigit() else None

def failed_details(since_hours=26, limit=20):
    """Для каждого упавшего прогона: workflow, упавший шаг, последние 20 строк лога.
    -> (markdown, N проблем). Источник недоступен -> именованный отказ, N=1 (не «зелёно»)."""
    runs, total, err = F.failed_runs(limit)
    if runs is None:
        return f"- {err}\n", 1
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=since_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [r for r in runs if r["createdAt"] > cutoff]
    if not recent:
        return F.caption(len(runs), total, limit) + f" упавших прогонов за {since_hours}ч нет\n", 0
    out = [F.caption(len(runs), total, limit) + f" из них за {since_hours}ч: {len(recent)}"]
    known = []
    for r in recent:
        rid = r["databaseId"]
        if F.is_platform_limit(r, jobs_count):
            known.append(f"- **{r['name']}** (run {rid}, {r['event']}, {r['headBranch']}, "
                         f"actor={r.get('actor')}): jobs пусты / startup_failure")
            continue
        jobs = sh("gh", "run", "view", str(rid), "--json", "jobs", "--jq",
                  '[.jobs[]|select(.conclusion=="failure")|.name+" / "+([.steps[]|select(.conclusion=="failure")|.name]|join(", "))]|join("; ")').strip()
        tail = "\n".join(sh("gh", "run", "view", str(rid), "--log-failed").splitlines()[-20:])
        out.append(f"- **{r['name']}** (run {rid}, {r['event']}, {r['headBranch']})\n"
                   f"  упавший шаг: {jobs or 'НЕИЗВЕСТЕН: jobs пусты (startup_failure / ошибка файла workflow)'}\n"
                   f"```\n{tail or '(лог упавших шагов пуст)'}\n```")
    n_problems = len(recent) - len(known)
    if known:
        out.append("### Известное ограничение платформы (не проблема)\n"
                   f"{F.PLATFORM_LIMIT_NOTE}\nВ счёт «N проблем» и в Telegram не входят:\n"
                   + "\n".join(known))
    return "\n".join(out) + "\n", n_problems

# ───────────── «Человеческая» верхняя часть (issue #144) ─────────────
# Правила подсчёта авто-недель: DECISION_2026-10-25 п.7 и DECISION_2026-10-28_FLOOR1_COVERAGE.
import csv, json, re
FIRST_WEEK = dt.date(2026, 10, 31)          # первая возможная авто-неделя (сб)
WEEKS_GOAL = 4
B_MIN = 95.0                                # порог покрытия (Б), %
CLOSE = dt.timedelta(days=1, hours=8)       # неделя S закрыта после вс 08:00 UTC (последний слот)
REGIMES = {"MIXED": "смешанный", "RISK_ON": "риск-он", "RISK_OFF": "риск-офф"}
DOSSIERS = ("NFLX-FY2019", "UBER", "RDDT")
B_RE = re.compile(r"Покрытие \(Б\), применимое: \d+/\d+ = ([0-9]+(?:\.[0-9]+)?)%")
BOT_NAMES = ("claude",)

def _ru_date(d):
    return f"{d:%d.%m}"

def _last_saturday(day):
    return day - dt.timedelta(days=(day.weekday() - 5) % 7)

def _gh_json(*cmd):
    """-> (данные, None) | (None, причина). Отказ gh/не-JSON — именованная причина, не «пусто»."""
    out = sh(*cmd)
    try:
        return json.loads(out), None
    except ValueError:
        return None, f"{' '.join(cmd[:3])} не вернул JSON"

class Sources:
    """Источники фактов о неделе S. Каждый метод -> (True|False|None, причина). None = не определено."""
    def __init__(self, root="."):
        self.root = root
        self._runs = {}

    def _read(self, rel):
        try:
            with open(os.path.join(self.root, rel), encoding="utf-8") as f:
                return f.read(), None
        except OSError as e:
            return None, f"нет файла {rel} ({e.__class__.__name__})"

    def panel_row(self, s):
        text, err = self._read("journal/PANEL_LOG.csv")
        if text is None:
            return None, err
        found = any(r.get("week_end") == str(s) for r in csv.DictReader(text.splitlines()))
        return found, f"нет строки week_end={s} в PANEL_LOG.csv"

    def card_exists(self, s):
        ok = os.path.isfile(os.path.join(self.root, f"Reports/floor1/FLOOR1_{s}.md"))
        return ok, f"нет Reports/floor1/FLOOR1_{s}.md"

    def card_b(self, s):
        text, err = self._read(f"Reports/floor1/FLOOR1_{s}.md")
        if text is None:
            return False, err               # карточки нет — условие не выполнено, а не «не определено»
        m = B_RE.search(text)
        if not m:
            return None, "в карточке нет строки «Покрытие (Б), применимое»"
        v = float(m.group(1))
        return v >= B_MIN, f"покрытие (Б) {v}% < {B_MIN}%"

    def _gh_runs(self, wf, fields):
        if wf not in self._runs:
            self._runs[wf] = _gh_json("gh", "run", "list", "--workflow", wf, "--limit", "100", "--json", fields)
        return self._runs[wf]

    def schedule_publish(self, s):
        runs, err = self._gh_runs("panel_weekly.yml", "databaseId,event,conclusion,createdAt")
        if runs is None:
            return None, err
        lo = dt.datetime.combine(s, dt.time(0, 0), dt.timezone.utc)
        hi = lo + CLOSE
        win = [r for r in runs if lo <= dt.datetime.strptime(r["createdAt"], "%Y-%m-%dT%H:%M:%SZ")
               .replace(tzinfo=dt.timezone.utc) < hi]
        if any(r["event"] == "workflow_dispatch" for r in win):
            return False, "в окне недели был ручной запуск panel-weekly (workflow_dispatch)"
        ok = any(r["event"] == "schedule" and r["conclusion"] == "success" for r in win)
        return ok, "нет успешного прогона panel-weekly с event=schedule"

    def validator(self, s):
        runs, err = self._gh_runs("daily_report.yml", "databaseId,event,createdAt")
        if runs is None:
            return None, err
        day = [r for r in runs if r["event"] == "schedule" and r["createdAt"].startswith(str(s))]
        if not day:
            return None, f"нет прогона daily-report за {s}"
        states = []
        for r in day:
            jobs, jerr = _gh_json("gh", "run", "view", str(r["databaseId"]), "--json", "jobs")
            if jobs is None:
                return None, jerr
            for j in jobs.get("jobs", []):
                states += [st.get("conclusion") for st in j.get("steps", []) if "Валидатор" in st.get("name", "")]
        if "failure" in states:
            return False, f"шаг валидатора в отчёте {s} красный"
        if "success" in states:
            return True, ""
        return None, f"шаг валидатора в отчёте {s} не выполнен/не найден"

def week_status(s, now, src):
    """-> (OK|NO|PENDING|UNKNOWN, причина). Суббота до вс 08:00 UTC — PENDING (не пропуск)."""
    if now < dt.datetime.combine(s, dt.time(0, 0), dt.timezone.utc) + CLOSE:
        return "PENDING", "ещё идёт"
    for check in (src.panel_row, src.card_exists, src.card_b, src.schedule_publish, src.validator):
        ok, why = check(s)
        if ok is None:
            return "UNKNOWN", why
        if not ok:
            return "NO", why
    return "OK", ""

def weeks_streak(now, src):
    """Считаем подряд от последней субботы назад; пропуск обнуляет; PENDING пропускаем без счёта;
    UNKNOWN — неделя НЕ засчитана и счёт останавливается. -> dict."""
    s = _last_saturday(now.date())
    res = {"n": 0, "last": None, "pending": None, "unknown": None, "broken": None}
    while s >= FIRST_WEEK:
        st, why = week_status(s, now, src)
        if st == "PENDING":
            res["pending"] = s
        elif st == "OK":
            res["n"] += 1
            res["last"] = res["last"] or s
        else:
            res["unknown" if st == "UNKNOWN" else "broken"] = (s, why)
            break
        s -= dt.timedelta(days=7)
    res["next"] = res["pending"] or (_last_saturday(now.date()) + dt.timedelta(days=7))
    return res

def weeks_line(r):
    last = f"последняя засчитанная — сб {_ru_date(r['last'])}" if r["last"] else "засчитанных ещё нет"
    parts = [f"{last}; следующая — сб {_ru_date(r['next'])}"]
    if r["unknown"]:
        parts.append(f"не определено: {r['unknown'][1]} (сб {_ru_date(r['unknown'][0])} не засчитана)")
    if r["broken"]:
        parts.append(f"сб {_ru_date(r['broken'][0])} не засчитана: {r['broken'][1]}")
    return f"- Авто-недели подряд: {r['n']} из {WEEKS_GOAL} ({'; '.join(parts)})"

def exam_line(root="."):
    def hits(pat):
        import glob
        return sorted(glob.glob(os.path.join(root, pat)))
    for f in hits("Reports/exam/NFLX_FY2019*.md"):
        with open(f, encoding="utf-8") as fh:
            m = re.search(r"ВЕРДИКТ:\s*(RED|AMBER|GREEN)", fh.read())
        if not m:
            return "проведён, но строки «ВЕРДИКТ: RED|AMBER|GREEN» в файле нет"
        return "проведён: RED" if m.group(1) == "RED" else f"проведён: не RED ({m.group(1)})"
    f = hits("mailbox/PREREG_*NFLX*.md")
    return (f"правило зафиксировано ({os.path.basename(f[0])}), экзамен не проведён" if f
            else "правило сторожа ещё не зафиксировано")

def dossier_line(root="."):
    import glob
    ready = [t for t in DOSSIERS if glob.glob(os.path.join(root, f"Reports/dossiers/{t}_*.md"))]
    return f"- Досье: {len(ready)} из {len(DOSSIERS)} (" + (", ".join(ready) + " готовы" if ready else "ни одно не готово") + ")"

def tests_line():
    """Последний прогон tests.yml на main. Эталоны MU/INTC/META/GOOG — часть сьюта (TestGoldens),
    отдельным статусом gh их не отдаёт: показываем статус сьюта целиком и говорим об этом."""
    runs, err = _gh_json("gh", "run", "list", "--workflow", "tests.yml", "--branch", "main", "--limit", "1",
                         "--json", "conclusion,createdAt")
    if not runs:
        return f"- Эталонные тесты MU/INTC/META/GOOG: не определено ({err or 'нет прогонов на main'})"
    c, d = runs[0].get("conclusion"), runs[0]["createdAt"][:10]
    word = {"success": "зелёные", "failure": "красные"}.get(c, f"не определено (прогон завершился: {c or 'ещё идёт'})")
    return f"- Эталонные тесты MU/INTC/META/GOOG: {word} (последний прогон сьюта на main, {d}; отдельно от сьюта эти 4 не выделяются)"

def manual_runs_line(now):
    """Ручные запуски (workflow_dispatch) не ботом за 7 дней. Автор есть только в REST (audit_facts)."""
    runs, _, err = F._runs_api(100)
    if runs is None:
        return f"- Ручных запусков автоматики оператором за 7 дней: не определено ({err}) (цель 0)"
    cut = (now - dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    m = [r for r in runs if r["event"] == "workflow_dispatch" and (r["createdAt"] or "") > cut
         and (r.get("actor") or "").lower() not in OP.BOT_LOGINS]
    return (f"- Ручных запусков автоматики оператором за 7 дней: {len(m)} (цель 0; "
            f"по последним {len(runs)} прогонам)")

def operator_items(prs, now):
    """Нумерованный список PR, ждущих оператора (логика operator_prs). -> list[str]."""
    out = []
    for i, pr in enumerate(sorted((p for p in prs if OP.is_operator_pr(p)), key=lambda p: p["number"]), 1):
        body = pr.get("body") or ""
        what = OP.operator_block(body, 1)
        what = pr["title"] if what == OP.NO_BLOCK else what.lstrip("- ").strip()
        m = re.search(r"^\W*Тип:\s*(ЗАКОН|КОД)", body, re.M | re.I)
        kind = m.group(1).upper() if m else "тип не указан"
        out.append(f"{i}. {what} — {kind}, ждёт {OP.days_waiting(pr['createdAt'], now)} дн. — {pr['url']}")
    return out

SUBJ_PANEL = re.compile(r"^weekly panel (\d{4}-\d{2}-\d{2})\b")
SUBJ_AUDIT = re.compile(r"^daily audit (\d{4}-\d{2}-\d{2})( \[RED\])?")
SUBJ_BRIDGE = re.compile(r"^bridge: log architect command")
COMMIT_RE = re.compile(r"^- (.*) \(([0-9a-f]+), (.*)\)$")
PR_SUFFIX = re.compile(r"\s*\(#\d+\)$")

def panel_event(d, root="."):
    try:
        with open(os.path.join(root, "journal/PANEL_LOG.csv"), encoding="utf-8") as f:
            row = next((r for r in csv.DictReader(f) if r.get("week_end") == d), None)
    except OSError as e:
        return f"Вышла недельная панель и карточка 34 компаний. Данные недели не прочитаны: {e.__class__.__name__}."
    if row is None:
        regime = "режим не определён: нет строки недели в PANEL_LOG"
    elif row.get("regime") in REGIMES:
        try:
            regime = f"Рынок: {REGIMES[row['regime']]}, размер позиций {round(float(row['size_multiplier']) * 100)}% от обычного"
        except (ValueError, TypeError, KeyError):
            regime = f"Рынок: {REGIMES[row['regime']]}, размер позиций не определён"
    else:
        regime = f"Рынок: режим не определён ({row.get('regime')})"
    try:
        with open(os.path.join(root, f"Reports/floor1/FLOOR1_{d}.md"), encoding="utf-8") as f:
            m = B_RE.search(f.read())
        cover = f"{m.group(1)}%" if m else "не определено (строки нет в карточке)"
    except OSError:
        cover = "не определено (карточки нет)"
    names = "карточка 34 компаний"
    return f"Вышла недельная панель и {names}. {regime}. Покрытие данных (Б) {cover}."

def audit_event(d, red, root="."):
    try:
        with open(os.path.join(root, f"journal/audits/DAILY_AUDIT_{d}.md"), encoding="utf-8") as f:
            line = next((l.strip() for l in f if l.startswith("**Итог:**")), None)
    except OSError:
        line = None
    verdict = "RED" if red else "GREEN"
    return f'Аудит "сказано—сделано": {verdict} — ' + (line.replace("**Итог:**", "").strip() if line else "первая строка вердикта не найдена")

def bridge_title(sha):
    out = sh("git", "show", "--format=", "-U0", sha, "--", "journal/architect_commands.log")
    for l in out.splitlines():
        if l.startswith("+") and not l.startswith("+++"):
            parts = l[1:].split(" | ")
            if len(parts) >= 3:
                return re.sub(r"^\[CONSILIUM-[A-Z]+\]\s*", "", parts[2].strip())
    return "заголовок не определён (строки в журнале нет)"

def day_events(commits):
    ev = []
    for line in commits.splitlines():
        m = COMMIT_RE.match(line.strip())
        if not m:
            ev.append(f"- {line.lstrip('- ').strip()}")
            continue
        subj, sha, author = m.groups()
        if (p := SUBJ_PANEL.match(subj)):
            ev.append(f"- {panel_event(p.group(1))}")
        elif (a := SUBJ_AUDIT.match(subj)):
            ev.append(f"- {audit_event(a.group(1), bool(a.group(2)))}")
        elif SUBJ_BRIDGE.match(subj):
            ev.append(f"- Архитектор поставил задачу боту: {bridge_title(sha)}")
        elif PR_SUFFIX.search(subj) and any(b in author.lower() for b in BOT_NAMES):
            ev.append(f"- Слита работа бота: {PR_SUFFIX.sub('', subj)}")
        else:
            ev.append(f"- {subj}")
    return "\n".join(ev) or "- Ничего."

def alarms(n_failed, n_missed, unresolved, remind_err):
    """Только настоящие (известное ограничение платформы уже вычтено в n_failed).
    -> list[(что случилось, чем грозит финишу, что делаем)]."""
    out = []
    if n_failed:
        out.append((f"Упало прогонов автоматики: {n_failed}", "неделя может не засчитаться, а счёт до финиша — обнулиться",
                    "архитектор разбирает причину (подробности ниже черты)"))
    if n_missed:
        out.append((f"Пропущены плановые запуски: {n_missed}", "пропуск недели обнуляет счёт авто-недель",
                    "сторож расписаний уже сообщил; архитектор проверяет"))
    if unresolved:
        out.append(("Аудит оставил неразрешённые пункты", "нарушение правил может остаться неисправленным",
                    "архитектор разберёт на ближайшем аудите"))
    if remind_err:
        out.append(("Не собралось напоминание о PR, ждущих тебя", "PR могут лежать незамеченными",
                    "проверь список PR вручную; архитектор чинит напоминание"))
    return out

def day_verdict(items, alarm_list):
    if alarm_list:
        tail = f"; и ждут твоего решения PR: {len(items)}" if items else ""
        return f"🟠 Тревога: {alarm_list[0][0].lower()}" + (f" (всего {len(alarm_list)})" if len(alarm_list) > 1 else "") + tail, L.ALARM
    if items:
        return f"🔴 Нужно твоё действие: PR, ждущих тебя — {len(items)}", L.ACTION
    return "По плану, от тебя ничего не нужно", L.INFO

def human_top(today, now, commits, prs, n_failed, n_missed, unresolved, remind_err, src=None):
    """-> (markdown верхней части, итог дня, уровень Telegram, строка авто-недель)."""
    src = src or Sources()
    items = operator_items(prs, now) if prs is not None else []
    al = alarms(n_failed, n_missed, unresolved, remind_err)
    verdict, level = day_verdict(items, al)
    wl = weeks_line(weeks_streak(now, src))
    need = "\n".join(items) if items else ("Ничего." if prs is not None else "Не определено: список PR недоступен (см. тревоги).")
    if prs is None and not remind_err:
        al.append(("Не удалось получить список PR", "можно не заметить PR, ждущий тебя", "архитектор проверяет"))
        verdict, level = day_verdict(items, al)
    alarm_txt = "\n".join(f"- {w} / {t} / {d}" for w, t, d in al) if al else "Нет"
    md = (f"# Консилиум — {today}\n## Итог дня: {verdict}\n## Где мы относительно финиша\n{wl}\n"
          f"- Экзамен NFLX-FY2019: {exam_line()}\n{dossier_line()}\n{tests_line()}\n{manual_runs_line(now)}\n"
          f"## Что нужно от тебя\n{need}\n## Что произошло за сутки\n{day_events(commits)}\n"
          f"## Тревоги\n{alarm_txt}\n---\n")
    return md, verdict, level, wl

def main():
    if G.skip_if_published("daily-report"):
        return
    today = dt.date.today()
    # Напоминание оператору — раньше «пустого дня»: тихий день не повод молчать о ждущих PR.
    # Повтор раз в сутки: skip_if_published выше отсекает второй слот расписания.
    _, remind_err = OP.remind()
    missed, n_missed = G.watch_section()
    commits = sh("git", "log", "--since=26 hours ago", "--format=- %s (%h, %an)").strip()
    if not commits:
        print("пустой день")
        L.notify(f"{today}: коммитов за 26ч нет, отчёт не формировался", L.INFO)
        return
    failed, n_failed = failed_details()
    issues = sh("gh", "issue", "list", "--state", "open", "--limit", "15",
                "--json", "number,title", "--jq", '.[] | "- #\\(.number) \\(.title)"').strip()
    unresolved = ""
    if os.path.isdir("journal/audits"):
        for a in sorted(os.listdir("journal/audits"))[-3:]:
            with open(f"journal/audits/{a}", encoding="utf-8") as f:
                unresolved += "".join(l for l in f if l.startswith("UNRESOLVED"))
    prs, _ = OP.fetch()
    now = dt.datetime.now(dt.timezone.utc)
    unresolved_flag = bool(unresolved)
    top, verdict, level, weeks = human_top(today, now, commits, prs, n_failed, n_missed,
                                           unresolved_flag, remind_err)
    tech = (f"## Технические подробности (для архитектора и аудиторов)\n\n## Сделано\n{commits}\n\n"
            f"## Сложности\n{failed}\n{unresolved}\n"
            f"## Впереди (открытые задачи)\n{issues or '- очередь пуста'}\n\n{missed}")
    md = top + tech
    path = f"journal/digests/DAILY_{today}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    import autocommit
    ok = autocommit.publish([path], f"daily report {today}", author="consilium-report")
    L.send_mail(f"Консилиум {today}: {verdict}", md)
    L.notify(f"{today}: {verdict}\n{weeks}", level)
    print("sent:", path)
    if not ok:
        print("daily_report: результат НЕ опубликован -> exit 1")
        sys.exit(1)

if __name__ == "__main__":
    main()
