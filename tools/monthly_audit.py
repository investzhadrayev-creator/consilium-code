#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ежемесячный аудит АРХИТЕКТОРА обоими рецензентами (механизм №6, раунд 7).
Пакет месяца → OpenAI и Gemini независимо → вердикты GREEN/RED коммитятся, минуя
архитектора. RED любого из двух → письмо оператору напрямую."""
import datetime as dt, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import llm_clients as L
import audit_facts as F

def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout

def main():
    ym = dt.date.today().strftime("%Y-%m")
    packet = (f"АУДИТ АРХИТЕКТОРА, месяц {ym}, репозиторий consilium-code\n\n"
              f"== ВСЕ КОММИТЫ (30 дней) ==\n"
              f"{F.clip(sh('git','log','--since=30 days ago','--format=%h | %ae | %s'), 6000)}\n\n"
              f"== КОМАНДЫ АРХИТЕКТОРА (лог) ==\n"
              f"{F.clip(sh('tail','-100','journal/architect_commands.log'), 4000)} (tail -100 строк)\n\n"
              f"== ИЗМЕНЕНИЯ ФАЙЛОВ ПРАВИЛ (30 дней) ==\n"
              f"{F.clip(sh('git','log','--since=30 days ago','--name-only','--format=%h %ae','--','.github/','tools/','mailbox/DECISION_','mailbox/PREREG_','CODEOWNERS'), 3000)}\n\n"
              f"== ПАДЕНИЯ АВТОМАТИКИ (подпись = размер выборки, НЕ число падений) ==\n"
              f"{F.failed_runs_text(40)}\n\n"
              f"{F.fact_sections(30)}\n\n"
              "ВОПРОСЫ: 1) Нарушал ли архитектор append-only? 2) Менялись ли правила "
              "(workflows/сторожа/DECISION) без PR с одобрением оператора? 3) Расходятся ли "
              "команды архитектора в логе с фактическими изменениями? 4) Есть ли признаки "
              "смягчения/сокрытия аудитов?\nФОРМАТ: первой строкой VERDICT: GREEN или "
              "VERDICT: RED, затем findings списком с фактами из пакета.")
    red = False
    out = [f"# MONTHLY ARCHITECT AUDIT {ym}", ""]
    for provider in ("openai", "gemini"):
        try:
            r = L.call(provider, packet, system=L.AUDITOR_PERSONA)
            out += [f"## {provider}", L.meta_block(r, packet), "", r["text"], ""]
            red = red or "VERDICT: RED" in r["text"]
        except L.Unavailable as e:
            out += [f"## {provider}", f"REVIEW_UNAVAILABLE: {e}", ""]
    path = f"journal/audits/MONTHLY_ARCHITECT_AUDIT_{ym}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    import autocommit
    ok = autocommit.publish([path], f"monthly architect audit {ym}" + (" [RED]" if red else ""),
                            author="consilium-audit")
    if red:
        L.notify(f"[RED] Месячный аудит архитектора {ym}. {path}")
        L.send_mail(f"[CONSILIUM RED] Месячный аудит архитектора {ym}",
                    f"Минимум один рецензент дал RED. Файл: {path}")
    print(("RED" if red else "clean"), "->", path)
    if not ok:
        print("monthly_audit: результат НЕ опубликован -> exit 1")
        sys.exit(1)

if __name__ == "__main__":
    main()
