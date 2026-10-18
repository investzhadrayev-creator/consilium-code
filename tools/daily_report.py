#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ежедневный отчёт оператору «сделано / сложности / впереди» (в дни, когда шла работа).
Автосборка из фактов: коммиты, упавшие прогоны, открытые задачи, незакрытые пункты аудита.
Сохраняется в journal/digests/ и уходит письмом. Пустой день → выход без письма и коммита."""
import datetime as dt, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import llm_clients as L

def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout

def main():
    today = dt.date.today()
    commits = sh("git", "log", "--since=26 hours ago", "--format=- %s (%h, %an)").strip()
    if not commits:
        print("пустой день"); return
    failed = sh("gh", "run", "list", "--limit", "20", "--status", "failure",
                "--json", "name,createdAt",
                "--jq", '.[] | select(.createdAt > (now-93600|todate)) | "- \\(.name)"').strip()
    issues = sh("gh", "issue", "list", "--state", "open", "--limit", "15",
                "--json", "number,title", "--jq", '.[] | "- #\\(.number) \\(.title)"').strip()
    unresolved = ""
    if os.path.isdir("journal/audits"):
        for a in sorted(os.listdir("journal/audits"))[-3:]:
            with open(f"journal/audits/{a}", encoding="utf-8") as f:
                unresolved += "".join(l for l in f if l.startswith("UNRESOLVED"))
    md = (f"# Отчёт за {today}\n\n## Сделано\n{commits}\n\n"
          f"## Сложности\n{failed or '- без сбоев'}\n{unresolved}\n"
          f"## Впереди (открытые задачи)\n{issues or '- очередь пуста'}\n")
    path = f"journal/digests/DAILY_{today}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    import autocommit
    autocommit.publish([path], f"daily report {today}", author="consilium-report")
    L.send_mail(f"[CONSILIUM] Отчёт {today}", md)
    print("sent:", path)

if __name__ == "__main__":
    main()
