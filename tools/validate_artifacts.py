#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Независимый контролёр данных (раунд 7, В7.2; ChatGPT: «NOT_RUN никогда не PASS»).
Проверяет диапазон коммитов BASE..HEAD:
1) append-only: в журнальных файлах нет удалённых/изменённых строк;
2) существующие файлы mailbox/ не редактируются (новые — можно);
3) новые строки PANEL_LOG.csv: 22 поля, голоса в {1,-1,NA}, дата ISO, без дублей недели;
4) автокоммиты github-actions затрагивают только разрешённые пути; DECISION_/PREREG_/MANDATE_ — только
   если коммит = squash-слияние PR, слитого владельцем (gh api; нет ответа API -> нарушение «не проверено»).
Выход 0 = чисто; 1 = нарушение (список в stdout). Запуск: BASE=<sha> python3 tools/validate_artifacts.py
"""
import json, os, re, subprocess, sys

APPEND_ONLY = ("journal/PANEL_LOG.csv", "journal/architect_commands.log")
APPEND_ONLY_DIRS = ("journal/audits/", "journal/digests/", "mailbox/")
BOT_ALLOWED = ("journal/", "Reports/", "mailbox/")  # автокоммитам можно только сюда
BOT_FORBIDDEN = ("mailbox/DECISION_", "mailbox/PREREG_", "mailbox/MANDATE_")  # законы — только оператор
REPO_OWNER = "investzhadrayev-creator"  # единственный, чьё слияние делает DECISION/PREREG/MANDATE законом
VOTES = {"1", "-1", "NA"}
fails = []

def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout

def gh_api(path):
    """-> (json|None, причина|None). Отказ API называется, а не превращается в «пусто»."""
    try:
        r = subprocess.run(("gh", "api", path), capture_output=True, text=True)
    except OSError as e:
        return None, f"gh недоступен: {e}"
    if r.returncode != 0:
        return None, f"gh api {path}: rc={r.returncode} {r.stderr.strip()[:120]}"
    try:
        return json.loads(r.stdout), None
    except ValueError as e:
        return None, f"gh api {path}: ответ не JSON: {e!r}"

def repo_slug():
    slug = os.environ.get("GITHUB_REPOSITORY", "")
    if slug:
        return slug
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?\s*$",
                  sh("git", "remote", "get-url", "origin").strip())
    return m.group(1) if m else ""

def operator_merge(sha):
    """Коммит github-actions в BOT_FORBIDDEN допустим только как squash-слияние PR, слитого владельцем.
    -> (True, None) | (False, причина). Нет ответа API -> (False, «не проверено: API недоступен»)."""
    slug = repo_slug()
    if not slug:
        return False, "не проверено: API недоступен (репозиторий не определён)"
    prs, why = gh_api(f"repos/{slug}/commits/{sha}/pulls")
    if prs is None or not isinstance(prs, list):
        return False, f"не проверено: API недоступен ({why})"
    for pr in prs:
        if not isinstance(pr, dict) or pr.get("merge_commit_sha") != sha or not pr.get("number"):
            continue                         # PR, в который коммит лишь входил, — не его слияние
        full, why = gh_api(f"repos/{slug}/pulls/{pr['number']}")
        if not isinstance(full, dict):
            return False, f"не проверено: API недоступен ({why})"
        if not full.get("merged_at"):
            continue
        who = (full.get("merged_by") or {}).get("login")
        if who == REPO_OWNER:
            return True, None
        return False, f"PR #{pr['number']} слит не владельцем (merged_by={who})"
    return False, "нет PR, слитого этим коммитом (не squash-слияние PR)"

def main():
    base = os.environ.get("BASE", "")
    head = os.environ.get("HEAD", "HEAD")
    if not base or set(base) == {"0"}:
        base = sh("git", "rev-list", "--max-parents=0", "HEAD").split()[0]
    rng = f"{base}..{head}"

    # 1+2: построчный дифф по защищённым путям
    diff = sh("git", "diff", "--unified=0", rng, "--", "journal/", "mailbox/")
    current = None
    for ln in diff.splitlines():
        if ln.startswith("--- a/"):
            current = ln[6:]
        elif ln.startswith("+++ b/"):
            current = ln[6:] if current in (None, "/dev/null") else current
        elif ln.startswith("-") and not ln.startswith("---") and current:
            prot = current in APPEND_ONLY or any(
                current.startswith(d) for d in APPEND_ONLY_DIRS)
            if prot and ln[1:].strip():
                fails.append(f"APPEND-ONLY VIOLATION: удалена/изменена строка в {current}: {ln[:120]}")

    # mailbox: правка существующих файлов запрещена (status M/D)
    for ln in sh("git", "diff", "--name-status", rng, "--", "mailbox/").splitlines():
        st, _, path = ln.partition("\t")
        if st.strip().startswith(("M", "D", "R")):
            fails.append(f"MAILBOX IMMUTABLE: файл {path} изменён ({st}); исправления — новым файлом с supersedes")

    # 3: схема новых строк панели
    added = [l[1:] for l in sh("git", "diff", "--unified=0", rng, "--",
                               "journal/PANEL_LOG.csv").splitlines()
             if l.startswith("+") and not l.startswith("+++")]
    try:
        existing = sh("git", "show", f"{base}:journal/PANEL_LOG.csv").splitlines()
    except Exception:
        existing = []
    weeks = {l.split(",", 1)[0] for l in existing[1:] if l.strip()}
    for l in added:
        if l.startswith("week_end,") or not l.strip():
            continue
        f = l.split(",")
        if len(f) != 22:
            fails.append(f"PANEL SCHEMA: {len(f)} полей вместо 22: {l[:100]}")
            continue
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", f[0]):
            fails.append(f"PANEL SCHEMA: week_end не ISO-дата: {f[0]}")
        for i, name in ((2, "eri"), (6, "vix"), (11, "participation"), (14, "credit")):
            if f[i] not in VOTES:
                fails.append(f"PANEL SCHEMA: голос {name}='{f[i]}' вне {{1,-1,NA}}")
        if f[0] in weeks:
            fails.append(f"PANEL SCHEMA: дубль week_end {f[0]}")
        weeks.add(f[0])

    # 4: автокоммиты только в разрешённые пути
    for c in sh("git", "log", "--format=%H|%ae", rng).splitlines():
        sha, _, email = c.partition("|")
        if "github-actions" in email or "actions@github.com" in email:
            verdict = None                   # проверка слияния — один раз на коммит, и только если нужна
            for p in sh("git", "show", "--name-only", "--format=", sha).split():
                if not p:
                    continue
                if not any(p.startswith(a) for a in BOT_ALLOWED):
                    fails.append(f"BOT PATH VIOLATION: автокоммит {sha[:8]} трогает {p}")
                elif any(p.startswith(f) for f in BOT_FORBIDDEN):
                    verdict = verdict or operator_merge(sha)
                    if not verdict[0]:
                        fails.append(f"BOT PATH VIOLATION: автокоммит {sha[:8]} трогает {p} ({verdict[1]})")

    if fails:
        print("ВАЛИДАЦИЯ ПРОВАЛЕНА:")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("валидация чиста:", rng)

if __name__ == "__main__":
    main()
