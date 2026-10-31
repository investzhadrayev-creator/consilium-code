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

def main():
    if G.skip_if_published("daily-report"):
        return
    today = dt.date.today()
    # Напоминание оператору — раньше «пустого дня»: тихий день не повод молчать о ждущих PR.
    # Повтор раз в сутки: skip_if_published выше отсекает второй слот расписания.
    _, remind_err = OP.remind()
    missed, n_missed = G.watch_section(wait=G.REPORT_WAIT, self_name="daily-report")
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
    n_problems = n_failed + n_missed + (1 if unresolved else 0) + (1 if remind_err else 0)
    md = (f"# Отчёт за {today}\n\n## Сделано\n{commits}\n\n"
          f"## Сложности\n{failed}\n{unresolved}\n"
          f"## Впереди (открытые задачи)\n{issues or '- очередь пуста'}\n\n{missed}")
    path = f"journal/digests/DAILY_{today}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    import autocommit
    ok = autocommit.publish([path], f"daily report {today}", author="consilium-report")
    L.send_mail(f"[CONSILIUM] Отчёт {today}", md)
    L.notify(f"{today}: всё зелёно" if n_problems == 0 else f"{today}: {n_problems} проблем — см. письмо", L.INFO)
    print("sent:", path)
    if not ok:
        print("daily_report: результат НЕ опубликован -> exit 1")
        sys.exit(1)

if __name__ == "__main__":
    main()
