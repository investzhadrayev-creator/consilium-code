#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telegram о упавшем job автоматики. Вызывается workflow-наблюдателем notify-failures.yml
(событие workflow_run) — он ловит и падения до старта шагов, которые step-level failure() не видит.
Данные приходят ТОЛЬКО через env (WF_NAME, WF_URL, WF_BRANCH, WF_EVENT), не через shell-интерполяцию."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm_clients as L

def message(env=os.environ):
    name = env.get("WF_NAME") or "НЕИЗВЕСТНЫЙ workflow"
    return (f"Упал job автоматики: {name} (ветка {env.get('WF_BRANCH') or '?'}, "
            f"событие {env.get('WF_EVENT') or '?'}) {env.get('WF_URL') or ''}").strip()

def main():
    ok = L.notify(message())
    print("notify_failure:", "отправлено" if ok else "НЕ отправлено (см. WARN выше)")

if __name__ == "__main__":
    main()
