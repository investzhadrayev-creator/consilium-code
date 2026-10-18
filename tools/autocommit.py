#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Публикация данных автоматикой БЕЗ обхода замка main (DECISION 2026-10-18).
Каждый автокоммит идёт так: своя ветка auto/* → PR → встроенная проверка
validate_artifacts.py (BASE=main) → squash-merge стандартным токеном Actions.
Main защищён ruleset без исключений для автоматики; данные (journal/, Reports/,
mailbox/ данные) не принадлежат CODEOWNERS, поэтому merge не требует оператора.
Провал проверки → PR остаётся открытым, issue [RED], выход 1 — ничего не сливается.
CLI: python3 tools/autocommit.py "<сообщение>" <путь> [<путь> ...]"""
import os, re, subprocess, sys, time

def sh(*cmd, check=True, env=None):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {r.stderr.strip()[:500]}")
    return r.stdout.strip()

def publish(paths, message, author="consilium-auto"):
    sh("git", "config", "user.name", author)
    sh("git", "config", "user.email", "actions@github.com")
    sh("git", "add", "--", *paths)
    if not sh("git", "diff", "--cached", "--name-only"):
        print("autocommit: изменений нет —", message)
        return True
    slug = re.sub(r"[^a-z0-9]+", "-", message.lower())[:40].strip("-") or "data"
    branch = f"auto/{slug}-{int(time.time())}"
    sh("git", "checkout", "-b", branch)
    sh("git", "commit", "-m", message)
    sh("git", "push", "-u", "origin", branch)
    sh("git", "fetch", "origin", "main")
    base = sh("git", "merge-base", "origin/main", "HEAD")
    env = dict(os.environ, BASE=base, HEAD="HEAD")
    v = subprocess.run([sys.executable, "tools/validate_artifacts.py"],
                       capture_output=True, text=True, env=env)
    print(v.stdout)
    sh("gh", "pr", "create", "--base", "main", "--head", branch,
       "--title", f"[auto] {message}",
       "--body", "Автокоммит данных. Встроенная проверка:\n```\n"
                 + (v.stdout[-3000:] or "(пусто)") + "\n```")
    if v.returncode != 0:
        sh("gh", "issue", "create", "--title", f"[RED] Автокоммит не прошёл проверку: {message}",
           "--body", f"Ветка {branch} не слита. Вывод валидатора:\n```\n{v.stdout[-3000:]}\n```",
           check=False)
        sh("git", "checkout", "main", check=False)
        print("autocommit: ПРОВЕРКА ПРОВАЛЕНА — PR оставлен открытым")
        return False
    for attempt in range(3):
        r = subprocess.run(["gh", "pr", "merge", branch, "--squash", "--delete-branch"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            break
        print(f"autocommit: merge попытка {attempt + 1}: {r.stderr.strip()[:300]}")
        time.sleep(15)
    else:
        sh("git", "checkout", "main", check=False)
        raise RuntimeError(f"autocommit: не удалось слить {branch}")
    sh("git", "checkout", "main")
    sh("git", "pull", "--ff-only", "origin", "main", check=False)
    print("autocommit: слито —", message)
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: autocommit.py <message> <path> [<path>...]")
    sys.exit(0 if publish(sys.argv[2:], sys.argv[1]) else 1)
