#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Недельный дайджест оператору письмом (раньше жил inline в weekly_digest.yml; вынесен, чтобы
идемпотентность и пометка «панель этой недели» проверялись тестами). Два слота в субботу: если
успешный прогон этой недели уже был — выход 0 без письма. Панель: если строки этой недели на main
нет, дайджест так и пишет (иначе показал бы прошлую неделю под видом текущей)."""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm_clients as L
import schedule_guard as G

def sh(*c):
    return subprocess.run(c, capture_output=True, text=True).stdout

def main():
    if G.skip_if_published("weekly-digest"):
        return
    p = G.period_start("week", G.utcnow().date())
    panel = G.panel_parts(p)["row"]
    body = ("НЕДЕЛЬНЫЙ ДАЙДЖЕСТ CONSILIUM\n\n== Панель (последняя строка) ==\n"
            f"Строка этой недели на main: {panel[0]} — {panel[1]}\n"
            + sh('tail', '-1', 'journal/PANEL_LOG.csv')
            + "\n== Коммиты недели ==\n" + sh('git', 'log', '--since=7 days ago', '--format=- %ad %ae %s', '--date=format:%m-%d')
            + "\n== Падения ==\n" + sh('gh', 'run', 'list', '--limit', '30', '--status', 'failure', '--json', 'name', '--jq', '.[].name'))
    if not L.send_mail("[CONSILIUM] Недельный дайджест", body):
        print("weekly_digest: письмо НЕ отправлено -> exit 1")
        sys.exit(1)

if __name__ == "__main__":
    main()
