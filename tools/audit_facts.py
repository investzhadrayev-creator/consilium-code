#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Факты для пакетов аудиторов (daily_audit.py, monthly_audit.py) и отчёта дня.
Правило: у каждой выборки явная подпись «показано N из M, лимит L» — лимит нельзя
принять за число событий (ошибка 18.10: лимит 40 принят за «40 падений»).
Недоступный источник — именованный отказ с причиной (UNAVAILABLE), не пустая строка."""
import datetime as dt, json, os, re, subprocess

RULESET_ID = 25354082

def sh(*cmd):
    """-> (returncode, stdout, stderr); без исключений, отказ виден вызывающему."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr

def repo_slug():
    slug = os.environ.get("GITHUB_REPOSITORY") or ""
    if not slug:
        rc, out, _ = sh("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
        slug = out.strip() if rc == 0 else ""
    return slug

def caption(shown, total, limit):
    """Подпись выборки. total=None -> общее число неизвестно (названо, не подставлено)."""
    t = "?" if total is None else str(total)
    note = ""
    if total is not None and shown < total:
        note = " — ВЫБОРКА УСЕЧЕНА лимитом, остальное не показано"
    elif total is None:
        note = " — общее число M неизвестно"
    return f"[показано {shown} из {t}, лимит {limit}{note}]"

def _unavailable(what, rc, err):
    return f"UNAVAILABLE ({what}): rc={rc} {err.strip()[:200]}"

def ruleset_state():
    rc, out, err = sh("gh", "api", f"repos/{{owner}}/{{repo}}/rulesets/{RULESET_ID}")
    if rc != 0:
        rs = _unavailable(f"ruleset {RULESET_ID}", rc, err)
    else:
        try:
            j = json.loads(out)
            rs = (f"ruleset {j.get('name')} id={RULESET_ID}: enforcement={j.get('enforcement')}\n"
                  f"bypass_actors={json.dumps(j.get('bypass_actors', 'НЕ ПОКАЗАНО API'), ensure_ascii=False)}\n"
                  f"rules={json.dumps(j.get('rules'), ensure_ascii=False)}")
        except Exception as e:
            rs = f"UNAVAILABLE (ruleset parse): {e!r}"
    try:
        with open(".github/CODEOWNERS", encoding="utf-8") as f:
            co = f.read().strip()
    except OSError as e:
        co = f"UNAVAILABLE (CODEOWNERS): {e!r}"
    return f"{rs}\n--- .github/CODEOWNERS ---\n{co}"

def merged_prs(days, limit=50):
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    rc, out, err = sh("gh", "pr", "list", "--state", "merged", "--search", f"merged:>={since}",
                      "--limit", str(limit), "--json",
                      "number,title,author,mergedBy,reviewDecision,reviews,files,mergedAt")
    if rc != 0:
        return _unavailable("merged PRs", rc, err)
    try:
        prs = json.loads(out)
    except Exception as e:
        return f"UNAVAILABLE (merged PRs parse): {e!r}"
    rc2, tot, _ = sh("gh", "api", "-X", "GET", "search/issues", "-f",
                     f"q=repo:{repo_slug()} is:pr is:merged merged:>={since}", "--jq", ".total_count")
    total = int(tot) if rc2 == 0 and tot.strip().isdigit() else None
    lines = [caption(len(prs), total, limit) + f" слиты с {since}"]
    for p in prs:
        approvals = sum(1 for r in p.get("reviews") or [] if r.get("state") == "APPROVED")
        paths = [f["path"] for f in p.get("files") or []]
        lines.append(
            f"#{p['number']} author={(p.get('author') or {}).get('login')} "
            f"merged_by={(p.get('mergedBy') or {}).get('login') or 'НЕИЗВЕСТНО'} "
            f"reviewDecision={p.get('reviewDecision') or 'нет'} approvals={approvals} "
            f"paths={','.join(paths[:8])}{'…(+%d)' % (len(paths) - 8) if len(paths) > 8 else ''} "
            f"| {p['title'][:70]}")
    return "\n".join(lines)

DECISION_BUDGET = 40000   # символов на весь блок решений; явный лимит, усечение подписывается

def decisions(days=60, budget=None):
    """mailbox/DECISION_* за N дней: действующие решения оператора, аудитор обязан их учитывать.
    Передаётся ПОЛНЫЙ текст (раньше — первая непустая строка = «---» front matter, т.е. аудитор
    не видел решений вовсе). Бюджет явный; усечение подписано «показано N символов из M»;
    файл, не поместившийся в бюджет целиком, назван — не пропущен молча."""
    budget = DECISION_BUDGET if budget is None else budget
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    rc, out, err = sh("git", "log", f"--since={since}", "--diff-filter=A", "--name-only",
                      "--format=%cs", "--", "mailbox/DECISION_*")
    if rc != 0:
        return _unavailable("DECISION list", rc, err)
    items, date = {}, None
    for ln in out.splitlines():
        if re.fullmatch(r"\d{4}-\d\d-\d\d", ln):
            date = ln
        elif ln.strip():
            items[ln.strip()] = date
    lines = [f"[mailbox/DECISION_* добавлены за {days} дн. (с {since}): {len(items)} файл(ов); "
             f"бюджет текста {budget} симв. на все файлы, новейшие первыми]"]
    left = budget
    for path, d in sorted(items.items(), key=lambda kv: kv[1] or "", reverse=True):
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            lines.append(f"=== {d} {path} === UNAVAILABLE (файл недоступен: {e!r})")
            continue
        shown = min(len(text), max(left, 0))
        left -= shown
        note = "" if shown == len(text) else " — ТЕКСТ УСЕЧЕН БЮДЖЕТОМ"
        lines.append(f"=== {d} {path} === [показано {shown} символов из {len(text)}{note}]\n"
                     f"{text[:shown]}")
    return "\n".join(lines)

# --- известное ограничение платформы (DECISION_2026-10-25 п. 6, PR #56 п. 6) -----------------
PLATFORM_LIMIT_WORKFLOWS = ("validate-artifacts", "claude-audit")
PLATFORM_LIMIT_BOT = "github-actions[bot]"
PLATFORM_LIMIT_REF = "mailbox/DECISION_2026-10-25_OPERATOR_ROUND8.md п. 6 (PR #56 п. 6)"
PLATFORM_LIMIT_MARK = f"[ИЗВЕСТНОЕ ОГРАНИЧЕНИЕ ПЛАТФОРМЫ, не проблема и не расхождение: {PLATFORM_LIMIT_REF}]"
PLATFORM_LIMIT_NOTE = (
    "Падения validate-artifacts и claude-audit на авто-PR (event=pull_request, ветка auto/*, автор "
    "github-actions[bot]) с пустыми jobs / startup_failure — установленное ограничение платформы. "
    "Данные проверяются validate_artifacts.py внутри autocommit до слияния и страховочным шагом "
    f"daily_report. Источник: {PLATFORM_LIMIT_REF}. Такое падение НЕ является расхождением "
    "«сказано—сделано»; любое другое падение (в т.ч. тех же проверок на PR бота/оператора или с "
    "непустыми jobs) — по-прежнему расхождение.")

def jobs_count(run_id):
    """Число jobs прогона или None, если узнать не удалось (отказ ≠ «пусто»)."""
    rc, out, _ = sh("gh", "run", "view", str(run_id), "--json", "jobs", "--jq", ".jobs|length")
    return int(out.strip()) if rc == 0 and out.strip().isdigit() else None

def is_platform_limit(run, count_jobs=None):
    """Все три условия ОДНОВРЕМЕННО: (а) workflow из списка, (б) pull_request из auto/* от
    github-actions[bot], (в) jobs пусты. Неизвестное (нет актора, не удалось посчитать jobs) —
    не ограничение: это проблема."""
    if run.get("name") not in PLATFORM_LIMIT_WORKFLOWS:
        return False
    if run.get("event") != "pull_request" or not str(run.get("headBranch") or "").startswith("auto/"):
        return False
    if run.get("actor") != PLATFORM_LIMIT_BOT:
        return False
    n = (count_jobs or jobs_count)(run["databaseId"])
    return n == 0

def mark(run, count_jobs=None):
    return " " + PLATFORM_LIMIT_MARK if is_platform_limit(run, count_jobs) else ""

def missed_runs_section():
    """Раздел «Пропущенные запуски» сторожа расписаний — в пакет аудитора. Без Telegram
    (алерты шлёт сам сторож/daily_report). Недоступный сторож — именованный отказ."""
    try:
        import schedule_guard
        md, _ = schedule_guard.watch_section(notify=False)
        return md
    except Exception as e:
        return f"## Пропущенные запуски\n\nUNAVAILABLE (schedule_guard): {e!r}\n"

def _runs_api(limit, status=None):
    """Прогоны через REST (там есть автор запуска; `gh run list --json` его не отдаёт).
    -> (runs, total, err); runs в форме databaseId/name/createdAt/event/headBranch/actor/..."""
    args = ["gh", "api", "-X", "GET", "repos/{owner}/{repo}/actions/runs", "-f", f"per_page={limit}"]
    if status:
        args += ["-f", f"status={status}"]
    rc, out, err = sh(*args)
    if rc != 0:
        return None, None, _unavailable("failed runs" if status else "run list", rc, err)
    try:
        j = json.loads(out)
        runs = [{"databaseId": r["id"], "name": r.get("name"), "createdAt": r.get("created_at"),
                 "event": r.get("event"), "headBranch": r.get("head_branch"),
                 "status": r.get("status"), "conclusion": r.get("conclusion"),
                 "actor": (r.get("actor") or {}).get("login")} for r in j["workflow_runs"]]
        total = j.get("total_count")
    except Exception as e:
        return None, None, _unavailable("runs parse", 0, repr(e))
    return runs, total if isinstance(total, int) else None, ""

def failed_runs(limit=20):
    return _runs_api(limit, "failure")

def runs_overview(limit=15):
    runs, total, err = _runs_api(limit)
    if runs is None:
        return err
    def row(r):
        m = mark(r) if r["conclusion"] in ("failure", "startup_failure") else ""
        return f"{r['createdAt']} {r['name']}: {r['status']}/{r['conclusion']}{m}"
    return caption(len(runs), total, limit) + "\n" + "\n".join(row(r) for r in runs)

def fact_sections(days):
    """Блоки пакета аудитора по п.3 а/б/в."""
    return (f"== ИЗВЕСТНОЕ ОГРАНИЧЕНИЕ ПЛАТФОРМЫ (читать до статусов автоматики) ==\n{PLATFORM_LIMIT_NOTE}\n\n"
            f"== СОСТОЯНИЕ ЗАМКА main (ruleset protect-main) И CODEOWNERS ==\n{ruleset_state()}\n\n"
            f"== СЛИТЫЕ PR ЗА {days} ДН. ==\n{merged_prs(days)}\n\n"
            f"== ДЕЙСТВУЮЩИЕ РЕШЕНИЯ ОПЕРАТОРА mailbox/DECISION_* (60 дн.) — "
            f"аудитор ОБЯЗАН их учитывать ==\n{decisions(60)}")

def clip(text, limit):
    """Усечение по символам с явной подписью (молчаливый срез [:N] запрещён)."""
    if len(text) <= limit:
        return f"[показано {len(text)} из {len(text)} симв., лимит {limit}]\n{text}"
    return f"[показано {limit} из {len(text)} симв., лимит {limit} — ВЫБОРКА УСЕЧЕНА]\n{text[:limit]}"

def list_block(text, limit_note="лимита нет"):
    n = len([l for l in text.splitlines() if l.strip()])
    return f"[строк: {n}, {limit_note}]\n{text}"

def failed_runs_text(limit):
    runs, total, err = failed_runs(limit)
    if runs is None:
        return err
    return caption(len(runs), total, limit) + "\n" + "\n".join(
        f"{r['createdAt']} {r['name']} ({r['event']}, {r['headBranch']}, actor={r['actor']})"
        f"{mark(r)}" for r in runs)
