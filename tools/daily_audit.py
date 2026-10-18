#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ежедневный аудитор «сказано — сделано» (механизм №8, решение оператора 2026-10-11).
Два прохода: (1) сверка заявлений с фактами репозитория; (2) по каждому расхождению —
доследование с сырыми доказательствами: ПОДТВЕРЖДАЮ НАРУШЕНИЕ (+причина+план) или ОТЗЫВАЮ.
Аудитор дня: чётный день месяца → OpenAI, нечётный → Gemini. Вердикт коммитится, минуя
архитектора. ПОДТВЕРЖДЁННОЕ НАРУШЕНИЕ → письмо оператору. Пустой день → выход без коммита.
Протокол: mailbox/PROTOCOL_DAILY_AUDIT_v1.md (draft; открытые вопросы — оператору)."""
import datetime as dt, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import llm_clients as L

def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout

def gather():
    commits = sh("git", "log", "--since=26 hours ago",
                 "--format=%h | %ae | %s")
    cmds = ""
    log = sh("git", "log", "--since=26 hours ago", "-p", "--",
             "journal/architect_commands.log")
    cmds = "\n".join(l[1:] for l in log.splitlines()
                     if l.startswith("+") and "|" in l and not l.startswith("+++"))
    runs = sh("gh", "run", "list", "--limit", "15",
              "--json", "name,status,conclusion,createdAt",
              "--jq", '.[] | "\\(.createdAt) \\(.name): \\(.status)/\\(.conclusion)"')
    issues = sh("gh", "issue", "list", "--state", "open", "--limit", "20",
                "--json", "number,title", "--jq", '.[] | "#\\(.number) \\(.title)"')
    prev = ""
    audits = sorted(os.listdir("journal/audits")) if os.path.isdir("journal/audits") else []
    prev_files = [a for a in audits if a.startswith("DAILY_AUDIT_")]
    if prev_files:
        with open(f"journal/audits/{prev_files[-1]}", encoding="utf-8") as f:
            prev = "\n".join(l for l in f.read().splitlines()
                             if "UNRESOLVED" in l or "ПОДТВЕРЖДАЮ НАРУШЕНИЕ" in l)[:2000]
    return commits.strip(), cmds.strip(), runs.strip(), issues.strip(), prev.strip()

def main():
    today = dt.date.today()
    commits, cmds, runs, issues, prev = gather()
    if not commits and not cmds:
        print("пустой день — аудит не требуется"); return
    provider = "openai" if today.day % 2 == 0 else "gemini"

    packet = (f"ПАКЕТ ДНЯ {today} проекта Consilium (github.com/investzhadrayev-creator/consilium-code)\n\n"
              f"== КОМАНДЫ АРХИТЕКТОРА (несмываемый лог, за 26ч) ==\n{cmds or '(нет)'}\n\n"
              f"== ФАКТИЧЕСКИЕ КОММИТЫ (за 26ч) ==\n{commits or '(нет)'}\n\n"
              f"== СТАТУСЫ АВТОМАТИКИ ==\n{runs or '(нет)'}\n\n"
              f"== ОТКРЫТЫЕ ЗАДАЧИ ==\n{issues or '(нет)'}\n\n"
              f"== НЕЗАКРЫТОЕ ИЗ ПРОШЛОГО АУДИТА ==\n{prev or '(нет)'}")
    p1 = (packet + "\n\nЗАДАЧА (проход 1 — сверка «сказано—сделано»): по КАЖДОЙ команде "
          "архитектора и каждому незакрытому пункту дай вердикт строкой:\n"
          "ПОДТВЕРЖДЕНО: <что> — <каким фактом> | РАСХОЖДЕНИЕ: <заявлено X, факт Y>\n"
          "Обязательно ищи: команды без следов исполнения; коммиты без команд, меняющие "
          "правила; упавшие прогоны, о которых никто не доложил. Только факты пакета.")
    try:
        r1 = L.call(provider, p1, system=L.AUDITOR_PERSONA)
    except L.Unavailable as e:
        md = (f"# DAILY AUDIT {today}\n\nREVIEW_UNAVAILABLE ({provider}): {e}\n")
        write_commit(today, md, red=False, unavailable=True)
        return

    out = [f"# DAILY AUDIT {today} — аудитор: {provider}", "",
           L.meta_block(r1, p1), "", "## Проход 1 — сверка", "", r1["text"]]
    red = False
    if "РАСХОЖДЕНИЕ" in r1["text"]:
        ev = (f"ДОКАЗАТЕЛЬСТВА:\n== полный лог команд (хвост) ==\n"
              f"{sh('tail', '-30', 'journal/architect_commands.log')}\n"
              f"== диффы дня ==\n{sh('git', 'log', '--since=26 hours ago', '--stat')[:4000]}")
        p2 = ("Твои РАСХОЖДЕНИЯ из прохода 1:\n"
              + "\n".join(l for l in r1["text"].splitlines() if "РАСХОЖДЕНИЕ" in l)
              + "\n\n" + ev +
              "\n\nЗАДАЧА (проход 2 — доследование): по КАЖДОМУ расхождению закончи одним из двух, "
              "отмолчаться нельзя:\nПОДТВЕРЖДАЮ НАРУШЕНИЕ: <суть> | ПРИЧИНА: <почему произошло> | "
              "ПЛАН: <что, в каком файле, кем исправить>\nлибо\nОТЗЫВАЮ: <почему первое впечатление ошибочно>")
        try:
            r2 = L.call(provider, p2, system=L.AUDITOR_PERSONA)
            out += ["", L.meta_block(r2, p2), "", "## Проход 2 — доследование", "", r2["text"]]
            red = "ПОДТВЕРЖДАЮ НАРУШЕНИЕ" in r2["text"]
            if red:
                out += ["", "UNRESOLVED: см. подтверждённые нарушения выше — закрыть и отчитаться в следующем аудите"]
        except L.Unavailable as e:
            out += ["", f"## Проход 2: REVIEW_UNAVAILABLE ({e})", "UNRESOLVED: доследование не выполнено"]
    write_commit(today, "\n".join(out) + "\n", red=red)

def write_commit(today, md, red, unavailable=False):
    path = f"journal/audits/DAILY_AUDIT_{today}.md"
    os.makedirs("journal/audits", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    import autocommit
    autocommit.publish([path], f"daily audit {today}" + (" [RED]" if red else ""),
                       author="consilium-audit")
    if red:
        L.send_mail(f"[CONSILIUM RED] Ежедневный аудит {today}: подтверждено нарушение",
                    "Аудитор подтвердил расхождение «сказано—сделано».\n"
                    f"Файл: journal/audits/DAILY_AUDIT_{today}.md\n"
                    "https://github.com/investzhadrayev-creator/consilium-code/tree/main/journal/audits")
    print(("RED" if red else "clean"), "->", path)

if __name__ == "__main__":
    main()
