#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Напоминание оператору о PR, которые может слить только он (issue #92).
Оператор-PR: (а) автор не github-actions[bot] или (б) в заголовке «[ТРЕБУЕТ ОДОБРЕНИЯ ОПЕРАТОРА]».
Одно сообщение ACTION: по каждому PR — номер, заголовок, первые 3 строки блока «ДЛЯ ОПЕРАТОРА»,
дни ожидания, ссылка. Нет таких PR — ничего не шлём. Источник недоступен -> именованный отказ
(ALARM), не «PR нет». Повтор раз в сутки обеспечивает вызывающий (daily_report идемпотентен по дню).
CLI: python3 tools/operator_prs.py   # для отдельного утреннего слота (~05:07 UTC), см. mailbox/REPORT_*"""
import datetime as dt, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm_clients as L

MARK = "[ТРЕБУЕТ ОДОБРЕНИЯ ОПЕРАТОРА]"
BLOCK = "## ДЛЯ ОПЕРАТОРА"
BOT_LOGINS = {"github-actions[bot]", "app/github-actions", "github-actions"}
NO_BLOCK = "(в описании PR нет блока «ДЛЯ ОПЕРАТОРА» — требование CLAUDE.md не выполнено)"

def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def is_operator_pr(pr):
    """Автор неизвестен (нет поля) -> считаем оператор-PR: лишнее напоминание лучше пропуска."""
    login = ((pr.get("author") or {}).get("login") or "").strip().lower()
    return login not in BOT_LOGINS or MARK in (pr.get("title") or "")

def operator_block(body, n=3):
    """Первые n непустых строк после заголовка «## ДЛЯ ОПЕРАТОРА»; нет блока -> NO_BLOCK."""
    lines = (body or "").replace("\r\n", "\n").split("\n")
    for i, ln in enumerate(lines):
        if ln.strip().upper() == BLOCK:
            out = []
            for nxt in lines[i + 1:]:
                if nxt.lstrip().startswith("## "):
                    break
                if nxt.strip():
                    out.append(nxt.strip())
                if len(out) == n:
                    break
            return "\n".join(out) if out else NO_BLOCK
    return NO_BLOCK

def days_waiting(created_at, now):
    created = dt.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    return max(0, (now - created).days)

def message(prs, now):
    parts = [f"PR, которые может слить только оператор: {len(prs)}"]
    for pr in sorted(prs, key=lambda p: p["number"]):
        parts.append(f"\n#{pr['number']} {pr['title']}\n{operator_block(pr.get('body'))}\n"
                     f"ждёт {days_waiting(pr['createdAt'], now)} дн. — {pr['url']}")
    return "\n".join(parts)

def fetch():
    """-> (список открытых PR, None) либо (None, причина отказа)."""
    r = sh("gh", "pr", "list", "--state", "open", "--limit", "100", "--json",
           "number,title,author,body,createdAt,url")
    if r.returncode != 0:
        return None, f"gh pr list не выполнен: {r.stderr.strip()[:200]}"
    try:
        return json.loads(r.stdout), None
    except ValueError as e:
        return None, f"gh pr list вернул не JSON: {e}"

def remind(now=None):
    """-> (отправлено: bool, отказ: str|None). Нет оператор-PR -> (False, None) и тишина."""
    now = now or dt.datetime.now(dt.timezone.utc)
    prs, err = fetch()
    if prs is None:
        L.notify(f"Напоминание о PR оператора не собрано: {err}", L.ALARM)
        return False, err
    mine = [p for p in prs if is_operator_pr(p)]
    if not mine:
        print("operator_prs: PR, ждущих оператора, нет — сообщение не шлём")
        return False, None
    ok = L.notify(message(mine, now), L.ACTION)
    return ok, None if ok else "Telegram не принял напоминание"

def main():
    sent, err = remind()
    print("operator_prs:", "отправлено" if sent else (f"ОТКАЗ: {err}" if err else "нечего слать"))
    if err:
        sys.exit(1)

if __name__ == "__main__":
    main()
