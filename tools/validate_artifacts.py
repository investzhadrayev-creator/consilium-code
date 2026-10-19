#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Независимый контролёр данных (раунд 7, В7.2; ChatGPT: «NOT_RUN никогда не PASS»).
Проверяет диапазон коммитов BASE..HEAD:
1) append-only: в журнальных файлах нет удалённых/изменённых строк;
2) существующие файлы mailbox/ не редактируются (новые — можно);
3) новые строки PANEL_LOG.csv: 22 поля, голоса в {1,-1,NA}, дата ISO, без дублей недели;
4) автокоммиты github-actions затрагивают только разрешённые пути.
Выход 0 = чисто; 1 = нарушение (список в stdout). Запуск: BASE=<sha> python3 tools/validate_artifacts.py
"""
import os, re, subprocess, sys

APPEND_ONLY = ("journal/PANEL_LOG.csv", "journal/architect_commands.log")
APPEND_ONLY_DIRS = ("journal/audits/", "journal/digests/", "mailbox/")
BOT_ALLOWED = ("journal/", "Reports/", "mailbox/")  # автокоммитам можно только сюда
BOT_FORBIDDEN = ("mailbox/DECISION_", "mailbox/PREREG_", "mailbox/MANDATE_")  # законы — только оператор
VOTES = {"1", "-1", "NA"}
fails = []

def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout

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
            for p in sh("git", "show", "--name-only", "--format=", sha).split():
                if p and (not any(p.startswith(a) for a in BOT_ALLOWED)
                          or any(p.startswith(f) for f in BOT_FORBIDDEN)):
                    fails.append(f"BOT PATH VIOLATION: автокоммит {sha[:8]} трогает {p}")

    if fails:
        print("ВАЛИДАЦИЯ ПРОВАЛЕНА:")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("валидация чиста:", rng)

if __name__ == "__main__":
    main()
