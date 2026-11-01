#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ежедневный аудитор «сказано — сделано» (механизм №8, решение оператора 2026-10-11).
Два прохода: (1) сверка заявлений с фактами репозитория; (2) по каждому расхождению —
доследование с сырыми доказательствами: ПОДТВЕРЖДАЮ НАРУШЕНИЕ (+причина+план) или ОТЗЫВАЮ.
Аудитор дня: чётный день месяца → OpenAI, нечётный → Gemini. Вердикт коммитится, минуя
архитектора. ПОДТВЕРЖДЁННОЕ НАРУШЕНИЕ → письмо оператору. Пустой день → выход без коммита.
Протокол: mailbox/PROTOCOL_DAILY_AUDIT_v1.md (draft; открытые вопросы — оператору)."""
import datetime as dt, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import llm_clients as L
import audit_facts as F
import schedule_guard as G

def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout

PASS1_TASK = ("\n\nЗАДАЧА (проход 1 — сверка «сказано—сделано»): по КАЖДОЙ команде "
              "архитектора и каждому незакрытому пункту дай вердикт строкой:\n"
              "ПОДТВЕРЖДЕНО: <что> — <каким фактом> | РАСХОЖДЕНИЕ: <заявлено X, факт Y>\n"
              "Обязательно ищи: команды без следов исполнения; коммиты без команд, меняющие "
              "правила; упавшие прогоны, о которых никто не доложил. Только факты пакета.")

def gather(end=None):
    """Факты за 26ч до `end` (по умолчанию — сейчас). Для end в прошлом (калибровка) git-часть
    берётся за то же окно, а снимки состояния GitHub (прогоны, issues, PR, ruleset) — на момент
    вызова, и пакет это прямо пишет (нельзя вернуться во времени за состоянием API)."""
    win = ["--since=26 hours ago"] if end is None else [
        f"--since={(end - dt.timedelta(hours=26)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"--until={end.strftime('%Y-%m-%dT%H:%M:%SZ')}"]
    commits = sh("git", "log", *win, "--format=%h | %ae | %s").strip()
    log = sh("git", "log", *win, "-p", "--", "journal/architect_commands.log")
    cmds = "\n".join(l[1:] for l in log.splitlines()
                     if l.startswith("+") and "|" in l and not l.startswith("+++")).strip()
    runs = F.runs_overview(15)
    issues = sh("gh", "issue", "list", "--state", "open", "--limit", "20",
                "--json", "number,title", "--jq", '.[] | "#\\(.number) \\(.title)"')
    issues = F.caption(len([l for l in issues.splitlines() if l.strip()]), None, 20) + "\n" + issues
    prev = ""
    audits = sorted(os.listdir("journal/audits")) if os.path.isdir("journal/audits") else []
    prev_files = [a for a in audits if a.startswith("DAILY_AUDIT_")
                  and (end is None or a < f"DAILY_AUDIT_{end.date()}.md")]
    if prev_files:
        with open(f"journal/audits/{prev_files[-1]}", encoding="utf-8") as f:
            prev = "\n".join(l for l in f.read().splitlines()
                             if "UNRESOLVED" in l or "ПОДТВЕРЖДАЮ НАРУШЕНИЕ" in l)[:2000]
    return {"commits": commits, "cmds": cmds, "runs": runs.strip(),
            "issues": issues.strip(), "prev": prev.strip(), "snapshot": end is not None}

def build_packet(day, g):
    note = ("\n(ВНИМАНИЕ: ретроспективный пакет за прошлую дату — статусы прогонов, issues, "
            "PR, ruleset ниже — снимок на момент сборки, не на дату пакета)" if g["snapshot"] else "")
    return (f"ПАКЕТ ДНЯ {day} проекта Consilium (github.com/investzhadrayev-creator/consilium-code){note}\n\n"
            f"== КОМАНДЫ АРХИТЕКТОРА (несмываемый лог, за 26ч) ==\n{g['cmds'] or '(нет)'}\n\n"
            f"== ФАКТИЧЕСКИЕ КОММИТЫ (за 26ч) ==\n"
            f"{F.list_block(g['commits'], 'git log за 26ч, лимита нет') if g['commits'] else '(нет)'}\n\n"
            f"== СТАТУСЫ АВТОМАТИКИ (последние прогоны; подпись = размер выборки, "
            f"НЕ число падений) ==\n{g['runs'] or '(нет)'}\n\n"
            f"== ОТКРЫТЫЕ ЗАДАЧИ ==\n{g['issues'] or '(нет)'}\n\n"
            f"== НЕЗАКРЫТОЕ ИЗ ПРОШЛОГО АУДИТА ==\n{g['prev'] or '(нет)'}\n\n"
            f"{F.missed_runs_section()}\n\n"
            f"{F.fact_sections(7)}")

BILLING_MARKERS = ("402", "resource_exhausted", "credits", "quota", "billing")
AUTH_MARKERS = ("401", "403")
PROVIDER_TEXT = {"gemini": ("Gemini", "Google AI Studio (ai.studio → Billing)", "GEMINI_API_KEY"),
                 "openai": ("OpenAI", "OpenAI Platform (platform.openai.com → Billing)", "OPENAI_API_KEY")}

def _scrub_secrets(text):
    """Значения секретов и токены бота никогда не попадают в Telegram (в т.ч. из тела ошибки API)."""
    text = str(text)
    for name in ("GEMINI_API_KEY", "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN"):
        v = os.environ.get(name) or ""
        if v:
            text = text.replace(v, "***")
    text = re.sub(r"([?&]key=)[^&\s\"']+", r"\1***", text)
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._-]{8,}", r"\1***", text)
    return L._scrub(text, os.environ.get("TELEGRAM_BOT_TOKEN") or "")

def classify_unavailable(provider, err):
    """-> (level, текст оператору). Приоритет: 401/403 (ключ) не путаем с оплатой; прочее — ALARM
    с первой строкой ошибки (missing != default: причина называется, не подменяется общей фразой)."""
    name, where, secret = PROVIDER_TEXT.get(provider, (provider, provider, "API-ключ"))
    low = str(err).lower()
    if any(m in low for m in BILLING_MARKERS) and not low.startswith(("http 401", "http 403")):
        return L.ACTION, (f"🔴 Аудитор {name} не работает: закончились оплаченные кредиты. "
                          f"Что сделать: пополнить баланс в {where}. "
                          "Пока не пополнено — аудит в нечётные дни не проводится."
                          if provider == "gemini" else
                          f"🔴 Аудитор {name} не работает: закончились оплаченные кредиты. "
                          f"Что сделать: пополнить баланс в {where}. "
                          "Пока не пополнено — аудит в чётные дни не проводится.")
    if any(low.startswith(f"http {m}") or f"http {m}" in low for m in AUTH_MARKERS):
        return L.ACTION, (f"🔴 Аудитор {name} не работает: ключ API отклонён. "
                          f"Что сделать: проверить секрет {secret} (GEMINI_API_KEY/OPENAI_API_KEY).")
    first = (str(err).strip().splitlines() or ["(пустая ошибка)"])[0][:300]
    return L.ALARM, f"Аудитор {name} недоступен: {first}"

def notify_unavailable(provider, err, day, already=False):
    """Громко сообщает оператору, что рецензент недоступен. already=True (в этот день уже
    сообщали) -> молчим: не чаще раза в сутки. -> True если отправлено."""
    if already:
        return False
    level, text = classify_unavailable(provider, err)
    return L.notify(_scrub_secrets(f"{text} (аудит {day})"), level)

def _already_reported(path):
    """Файл аудита этого дня уже фиксирует недоступность -> второй слот не дублирует уведомление."""
    try:
        with open(path, encoding="utf-8") as f:
            return "REVIEW_UNAVAILABLE" in f.read()
    except OSError:
        return False

def main():
    if G.skip_if_published("daily-audit"):
        return
    today = dt.date.today()
    g = gather()
    commits, cmds = g["commits"], g["cmds"]
    if not commits and not cmds:
        print("пустой день — аудит не требуется"); return
    provider = "openai" if today.day % 2 == 0 else "gemini"

    packet = build_packet(today, g)
    prev = g["prev"]
    p1 = packet + PASS1_TASK
    try:
        r1 = L.call(provider, p1, system=L.AUDITOR_PERSONA)
    except L.Unavailable as e:
        md = (f"# DAILY AUDIT {today}\n\nREVIEW_UNAVAILABLE ({provider}): {e}\n")
        notify_unavailable(provider, e, today,
                           already=_already_reported(f"journal/audits/DAILY_AUDIT_{today}.md"))
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
              "ПЛАН: <что, в каком файле, кем исправить> | КЛАСС: <ПРАВИЛО|ЗАДНИМ_ЧИСЛОМ|ПОДСТАНОВКА|ИНОЕ>\n"
              "(КЛАСС: ПРАВИЛО — изменение правила без PR оператора; ЗАДНИМ_ЧИСЛОМ — правка задним числом; "
              "ПОДСТАНОВКА — подстановка числа вместо именованного отказа; прочее — ИНОЕ)\nлибо\nОТЗЫВАЮ: <почему первое впечатление ошибочно>")
        try:
            r2 = L.call(provider, p2, system=L.AUDITOR_PERSONA)
            out += ["", L.meta_block(r2, p2), "", "## Проход 2 — доследование", "", r2["text"]]
            red = "ПОДТВЕРЖДАЮ НАРУШЕНИЕ" in r2["text"]
            if red:
                out += ["", "UNRESOLVED: см. подтверждённые нарушения выше — закрыть и отчитаться в следующем аудите"]
        except L.Unavailable as e:
            out += ["", f"## Проход 2: REVIEW_UNAVAILABLE ({e})", "UNRESOLVED: доследование не выполнено"]
    write_commit(today, "\n".join(out) + "\n", red=red)

RULE_CLASSES = ("ПРАВИЛО", "ЗАДНИМ_ЧИСЛОМ", "ПОДСТАНОВКА")

def rule_violations(text):
    """Подтверждённые нарушения правил (список В-Б, issue #92): строка «ПОДТВЕРЖДАЮ НАРУШЕНИЕ» с
    «КЛАСС: <один из RULE_CLASSES>». Нет метки класса или класс ИНОЕ -> не из списка (INFO, не ALARM):
    ALARM только по явной метке аудитора, не по догадке парсера."""
    out = []
    for ln in text.splitlines():
        if "ПОДТВЕРЖДАЮ НАРУШЕНИЕ" not in ln or "КЛАСС:" not in ln:
            continue
        cls = ln.rsplit("КЛАСС:", 1)[1].strip().strip("<>*`. ").split()[0:1]
        if cls and cls[0].strip("|,;.").upper() in RULE_CLASSES:
            out.append(ln.strip())
    return out

def write_commit(today, md, red, unavailable=False):
    path = f"journal/audits/DAILY_AUDIT_{today}.md"
    os.makedirs("journal/audits", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    import autocommit
    ok = autocommit.publish([path], f"daily audit {today}" + (" [RED]" if red else ""),
                            author="consilium-audit")
    if red:
        hard = rule_violations(md)
        L.notify(f"[RED] Ежедневный аудит {today}: подтверждено нарушение"
                 + (f" правил ({len(hard)})" if hard else " (не из списка нарушений правил — к сведению)")
                 + f". journal/audits/DAILY_AUDIT_{today}.md", L.ALARM if hard else L.INFO)
        L.send_mail(f"[CONSILIUM RED] Ежедневный аудит {today}: подтверждено нарушение",
                    "Аудитор подтвердил расхождение «сказано—сделано».\n"
                    f"Файл: journal/audits/DAILY_AUDIT_{today}.md\n"
                    "https://github.com/investzhadrayev-creator/consilium-code/tree/main/journal/audits")
    print(("RED" if red else "clean"), "->", path)
    if not ok:
        print("daily_audit: результат НЕ опубликован -> exit 1")
        sys.exit(1)

if __name__ == "__main__":
    main()
