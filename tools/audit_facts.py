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

def decisions(days=60):
    """mailbox/DECISION_* за N дней: действующие решения оператора, аудитор обязан их учитывать."""
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
             "лимита выборки нет]"]
    for path, d in sorted(items.items(), key=lambda kv: kv[1] or ""):
        title = ""
        try:
            with open(path, encoding="utf-8") as f:
                title = next((l.strip() for l in f if l.strip()), "")[:100]
        except OSError:
            title = "(файл недоступен)"
        lines.append(f"{d} {path} | {title}")
    return "\n".join(lines)

def failed_runs(limit=20):
    rc, out, err = sh("gh", "run", "list", "--limit", str(limit), "--status", "failure",
                      "--json", "databaseId,name,createdAt,event,headBranch")
    if rc != 0:
        return None, None, _unavailable("failed runs", rc, err)
    runs = json.loads(out)
    rc2, tot, _ = sh("gh", "api", "-X", "GET", "repos/{owner}/{repo}/actions/runs",
                     "-f", "status=failure", "-f", "per_page=1", "--jq", ".total_count")
    total = int(tot) if rc2 == 0 and tot.strip().isdigit() else None
    return runs, total, ""

def runs_overview(limit=15):
    rc, out, err = sh("gh", "run", "list", "--limit", str(limit), "--json",
                      "name,status,conclusion,createdAt")
    if rc != 0:
        return _unavailable("run list", rc, err)
    runs = json.loads(out)
    rc2, tot, _ = sh("gh", "api", "-X", "GET", "repos/{owner}/{repo}/actions/runs",
                     "-f", "per_page=1", "--jq", ".total_count")
    total = int(tot) if rc2 == 0 and tot.strip().isdigit() else None
    return caption(len(runs), total, limit) + "\n" + "\n".join(
        f"{r['createdAt']} {r['name']}: {r['status']}/{r['conclusion']}" for r in runs)

def fact_sections(days):
    """Блоки пакета аудитора по п.3 а/б/в."""
    return (f"== СОСТОЯНИЕ ЗАМКА main (ruleset protect-main) И CODEOWNERS ==\n{ruleset_state()}\n\n"
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
        f"{r['createdAt']} {r['name']} ({r['event']}, {r['headBranch']})" for r in runs)
