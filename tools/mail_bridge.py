#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Почтовый мост архитектора (раунд 7). Каждые 2 часа читает Gmail оператора и
исполняет письма-команды архитектора. Безопасность: From == GMAIL_ADDRESS,
в теле строка 'AUTH: <MAIL_AUTH_TOKEN>'. КАЖДАЯ команда сначала пишется в
несмываемый journal/architect_commands.log (коммит), ПОТОМ исполняется.

Отбор писем: ТОЛЬКО точные теги в начале темы (parse_command), окно 7 дней, без опоры
на флаг «непрочитано» (оператор мог прочитать письмо вручную раньше запуска). Письма, не
являющиеся командами, не трогаются и не помечаются. Уже исполненные пропускаются по
Message-ID (он пишется в строку журнала; для старых строк без него — по (вид, тема, body_sha)).
Любой отказ исполнения авторизованной команды -> уведомление в Telegram и красный job (exit 1).

Команды (Subject):
  [CONSILIUM-TASK] <название>        → тело письма становится GitHub Issue для claude[bot]
  [CONSILIUM-MERGE] PR#<N>           → merge PR N; ОТКАЗ при путях оператора и при невыполнении условий
                                        автопилота КОД (merge_refusal)
  [CONSILIUM-FILE] <путь>            → тело (внутри ``` ```) коммитится файлом;
                                        DECISION_/PREREG_/MANDATE_ → только ветка+PR (замок оператора)
  [CONSILIUM-NOTIFY] <заголовок>     → лог, затем тело уходит оператору в Telegram

Secrets: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, MAIL_AUTH_TOKEN; опц. CONSILIUM_PAT
(PAT оператора: issues от его имени — упоминание @claude гарантированно будит бота).
"""
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
import base64, datetime as dt, email, email.header, hashlib, imaplib, os, re, subprocess, sys, time
import llm_clients as L

LOG = "journal/architect_commands.log"
WINDOW_DAYS = 7
COMMAND_RE = re.compile(r"^\s*\[CONSILIUM-(TASK|MERGE|FILE|NOTIFY)\](.*)$", re.S)

class CommandFailed(Exception):
    """Авторизованная команда не исполнена (отказ или ошибка) -> красный job + уведомление."""

def parse_command(subject):
    """Точная тема команды -> (KIND, остаток темы) либо None. Подстрока в середине темы
    (напр. «[investzhadrayev-creator/consilium-code] ...» от GitHub) командой НЕ является."""
    m = COMMAND_RE.match(subject or "")
    return (m.group(1), m.group(2).strip()) if m else None

PROTECTED = (".github/", "tools/", "CONSILIUM_REPO", "mailbox/DECISION_",
             "mailbox/PREREG_", "mailbox/MANDATE_", "CODEOWNERS", "CLAUDE.md")

def sh(*cmd, inp=None, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True, input=inp)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd}: {r.stderr[:400]}")
    return r.stdout

def gh_env():
    e = dict(os.environ)
    pat = os.environ.get("CONSILIUM_PAT")
    if pat:
        e["GH_TOKEN"] = pat
    return e

def body_sha(raw, token=""):
    """Хэш для журнала и дедупа legacy-строк — РОВНО как в старом мосте: декодированное
    text/plain (без нормализации CRLF и unflow) -> удалить 'AUTH: <token>' -> .strip() -> 16 hex.
    Хэш не зависит от секрета (журнал публичный, тело TASK тоже). Пустой token (только тесты) —
    тело хэшируется без удаления."""
    if token:
        raw = raw.replace(f"AUTH: {token}", "")
    return hashlib.sha256(raw.strip().encode()).hexdigest()[:16]

def log_command(kind, subject, raw, msgid="", token=""):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry = f"{ts} | {kind} | {subject} | body_sha={body_sha(raw, token)} | msgid={msgid or 'НЕТ'}"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    import autocommit
    if not autocommit.publish([LOG],
                              f"bridge: log architect command [{kind}]", author="consilium-bridge"):
        raise RuntimeError("лог команды не прошёл проверку — команда НЕ исполняется")
    print("logged:", entry)

def _decode_chunk(s, c):
    try:
        return s.decode(c or "utf-8", errors="replace")
    except LookupError:   # 'unknown-8bit' и т.п.: письмо с сырым 8-bit в заголовке не должно валить мост
        return s.decode("utf-8", errors="replace")

def decode_hdr(h):
    return "".join(_decode_chunk(s, c) if isinstance(s, bytes) else s
                   for s, c in email.header.decode_header(h or ""))

def executed_keys(path=LOG):
    """Что уже исполнено: Message-ID из журнала + (вид, тема, body_sha) для старых строк без него."""
    ids, legacy = set(), set()
    if not os.path.exists(path):
        return ids, legacy
    with open(path, encoding="utf-8") as f:
        for ln in f:
            parts = [p.strip() for p in ln.rstrip("\n").split(" | ")]
            if len(parts) < 4 or ln.startswith("#"):
                continue
            kv = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
            if kv.get("msgid") and kv["msgid"] != "НЕТ":
                ids.add(kv["msgid"])
            if kv.get("body_sha"):
                legacy.add((parts[1], parts[2], kv["body_sha"]))
    return ids, legacy

def body_parts(msg):
    """-> (сырой текст после снятия transfer-encoding (QP/base64) и charset, flowed, delsp)."""
    part = None
    if msg.is_multipart():
        for p in msg.walk():
            if p.get_content_type() == "text/plain" and not p.get_filename() \
                    and "attachment" not in str(p.get("Content-Disposition", "")).lower():
                part = p
                break
    else:
        part = msg
    if part is None:
        return "", False, False
    raw = part.get_payload(decode=True) or b""
    text = raw.decode(part.get_content_charset() or "utf-8", errors="replace")
    flowed = (part.get_param("format") or "").lower() == "flowed"
    delsp = (part.get_param("delsp") or "").lower() == "yes"
    return text, flowed, delsp

def body_text(msg):
    return body_parts(msg)[0]

def unflow(text, delsp=False):
    """RFC 3676: строка с хвостовым пробелом — мягкий перенос, склеить со следующей
    (delsp=yes: хвостовой пробел при склейке убрать). Space-stuffing снимается.
    Подпись «-- » не склеивается. Длинные строки не режутся и не теряются."""
    out, buf = [], ""
    for ln in text.split("\n"):
        if ln.startswith(" "):
            ln = ln[1:]
        if ln.endswith(" ") and ln.rstrip() != "--":
            buf += ln[:-1] if delsp else ln
            continue
        out.append(buf + ln)
        buf = ""
    if buf:
        out.append(buf)
    return "\n".join(out)

def normalize_body(text, flowed=False, delsp=False):
    """CRLF/CR -> LF, затем (если format=flowed) разворачивание мягких переносов."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unflow(text, delsp) if flowed else text

def extract_fenced(body):
    """Содержимое между ПЕРВОЙ открывающей ``` и ПОСЛЕДНЕЙ строкой-закрытием ```
    (внутри файла могут быть свои ```-блоки). None — блока нет."""
    lines = body.split("\n")
    start = next((i for i, l in enumerate(lines) if l.startswith("```")), None)
    if start is None:
        return None
    end = next((i for i in range(len(lines) - 1, start, -1) if lines[i].strip() == "```"), None)
    if end is None:
        return None
    return "\n".join(lines[start + 1:end]) + "\n"

def repo_url():
    slug = os.environ.get("GITHUB_REPOSITORY") or ""
    return f"https://github.com/{slug}" if slug else ""

def do_task(title, body):
    issue_body = body + "\n\n@claude Исполни задачу выше. Правила репозитория — в CLAUDE.md; append-only; именованные отказы; результат через PR."
    out = subprocess.run(["gh", "issue", "create", "--title", title,
                          "--body", issue_body], capture_output=True, text=True, env=gh_env())
    print("issue:", out.stdout or out.stderr)
    if out.returncode != 0:
        raise CommandFailed(f"TASK: issue не создан: {out.stderr.strip()[:300]}")

# Контрольная плоскость оператора (DECISION_2026-11-01_KOD_AUTOPILOT, п. 1а): РОВНО эти пути для MERGE.
# Запись на «/» или «_» — префикс (каталог / семейство файлов), остальное — точное имя файла.
MERGE_PROTECTED = (".github/", "CODEOWNERS", "CLAUDE.md",
                   "mailbox/DECISION_", "mailbox/PREREG_", "mailbox/MANDATE_",
                   "tools/validate_artifacts.py", "tools/autocommit.py", "tools/mail_bridge.py",
                   "tools/schedule_guard.py", "tools/llm_clients.py", "tools/daily_audit.py",
                   "tools/monthly_audit.py", "tools/audit_facts.py", "tools/calibrate_auditor.py")
# Заморозка перед субботней публикацией (п. 1в): пятница 00:00 UTC .. воскресенье 08:00 UTC.
FREEZE_PATHS = ("tools/floor1_card.py", "tools/panel_axes.py", "config/")
TESTS_CHECK = "suite"        # имя job в .github/workflows/tests.yml (workflow «suite» = тесты)
BOT_LOGINS = ("claude[bot]", "claude", "app/claude")
TYPE_CODE_RE = re.compile(r"^\s*[-*]?\s*Тип:\s*КОД\b", re.M)
TYPE_LAW_RE = re.compile(r"^\s*[-*]?\s*Тип:\s*ЗАКОН\b", re.M)

def _is_protected(path, protected):
    return any(path.startswith(p) if p.endswith(("/", "_")) else path == p for p in protected)

def in_freeze(now):
    """now — aware datetime. Пт 00:00 UTC (вкл.) .. вс 08:00 UTC (искл.)."""
    now = now.astimezone(dt.timezone.utc)
    wd = now.weekday()
    return wd in (4, 5) or (wd == 6 and now.hour < 8)

def _refuse_merge(n, reason):
    sh("gh", "pr", "comment", n, "--body", f"Мост отказал в merge: {reason}", check=False)
    L.notify(f"Мост отказал в merge PR #{n}: {reason[:200]}. "
             f"{repo_url()}/pull/{n}", L.ACTION)
    raise CommandFailed(f"MERGE REFUSED pr#{n}: {reason}")

def merge_refusal(pr, checks, now):
    """Чистая проверка условий (i)–(v) и путей. -> текст причины отказа либо None (можно сливать).
    Неизвестное (нет поля, нет check-runs, mergeable=UNKNOWN) — отказ, не «наверное можно»."""
    files = [f.get("path", "") for f in (pr.get("files") or [])]
    if not files:
        return "список файлов PR пуст или не получен"
    bad = [f for f in files if _is_protected(f, MERGE_PROTECTED)]
    if bad:
        return f"PR трогает защищённые пути ({', '.join(bad[:5])}). Требуется одобрение оператора в GitHub."
    au = pr.get("author") or {}
    if not (au.get("login") == "claude[bot]" or (au.get("login") in BOT_LOGINS and au.get("is_bot") is True)):
        return f"автор PR — {au.get('login')!r}, не claude[bot]"
    body = pr.get("body") or ""
    if TYPE_LAW_RE.search(body):
        return "в теле PR «Тип: ЗАКОН» — одобряет оператор"
    if not TYPE_CODE_RE.search(body):
        return "в теле PR нет строки «Тип: КОД»"
    runs = (checks or {}).get("check_runs") or []
    if not runs:
        return "тесты не запускались (у головного коммита нет check-runs)"
    if (checks or {}).get("total_count", len(runs)) > len(runs):
        return "список check-runs неполон — статус проверок неизвестен"
    if not any(r.get("name") == TESTS_CHECK for r in runs):
        return "тесты не запускались (среди check-runs нет workflow tests)"
    notok = [f"{r.get('name')}={r.get('status')}/{r.get('conclusion')}" for r in runs
             if not (r.get("status") == "completed" and r.get("conclusion") == "success")]
    if notok:
        return f"проверки не завершены или не успешны ({', '.join(notok[:5])})"
    if pr.get("mergeable") != "MERGEABLE":
        return f"PR не готов к слиянию без конфликтов (mergeable={pr.get('mergeable')})"
    if in_freeze(now):
        frozen = [f for f in files if _is_protected(f, FREEZE_PATHS)]
        if frozen:
            return (f"заморозка перед субботней публикацией (пт 00:00 — вс 08:00 UTC): "
                    f"{', '.join(frozen[:5])}")
    return None

def do_merge(subject, body, now=None):
    m = re.search(r"PR#?(\d+)", subject)
    if not m:
        raise CommandFailed("MERGE: номер PR не найден в теме")
    n = m.group(1)
    import json
    pr = json.loads(sh("gh", "pr", "view", n, "--json",
                       "files,author,body,title,mergeable,headRefOid") or "{}")
    sha = pr.get("headRefOid") or ""
    checks = {}
    if sha:
        checks = json.loads(sh("gh", "api", f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs?per_page=100") or "{}")
    why = merge_refusal(pr, checks, now or dt.datetime.now(dt.timezone.utc))
    if why:
        _refuse_merge(n, why)
    title = pr.get("title") or f"PR #{n}"
    r = subprocess.run(["gh", "pr", "merge", n, "--squash", "--delete-branch",
                        "--match-head-commit", sha,
                        "--subject", f"[CONSILIUM-MERGE] {title} (#{n})",
                        "--body", "Слит мостом без оператора (DECISION_2026-11-01_KOD_AUTOPILOT)."],
                       capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        raise CommandFailed(f"MERGE pr#{n} не выполнен: {r.stderr.strip()[:300]}")
    L.notify(f"слит PR #{n}: {title}", L.INFO)

def operator_pr_body(content):
    """Тело PR моста начинается с блока «## ДЛЯ ОПЕРАТОРА» (CLAUDE.md, issue #92): блок берётся из
    первых строк файла архитектора. Нет блока в файле -> блок-отказ с причиной, не выдуманное резюме."""
    lines = content.replace("\r\n", "\n").split("\n")
    for i, ln in enumerate(lines[:40]):
        if ln.strip().upper() == "## ДЛЯ ОПЕРАТОРА":
            blk = [ln]
            for nxt in lines[i + 1:i + 12]:
                if nxt.lstrip().startswith("## "):
                    break
                blk.append(nxt)
            return "\n".join(blk).rstrip() + "\n\nФайл правил от архитектора. Merge — только оператор."
    return ("## ДЛЯ ОПЕРАТОРА\n- Что меняется: НЕ УКАЗАНО — в первых 40 строках файла архитектора нет блока "
            "«## ДЛЯ ОПЕРАТОРА».\n- Тип: НЕ УКАЗАН\n- Риск: НЕ УКАЗАН\n\n"
            "Файл правил от архитектора. Merge — только оператор.")

def do_file(subject, body):
    path = parse_command(subject)[1]
    content = extract_fenced(body)
    if content is None or not path or ".." in path:
        raise CommandFailed(f"FILE: нет содержимого в ``` ``` или плохой путь (path={path!r})")
    protected = any(path.startswith(p) for p in PROTECTED)
    if os.path.exists(path) and path.startswith("mailbox/"):
        raise CommandFailed(f"FILE REFUSED: {path} существует; mailbox неизменяем — новый файл с supersedes")
    if protected:
        br = f"architect/{int(time.time())}"
        sh("git", "checkout", "-b", br)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    if not protected:
        import autocommit
        if not autocommit.publish([path], f"architect via bridge: {path}", author="consilium-bridge"):
            raise CommandFailed(f"FILE {path}: публикация не прошла проверку")
        print(f"FILE published: {path}")
        return
    sh("git", "add", path)
    sh("git", "commit", "-m", f"architect via bridge: {path}")
    sh("git", "push", "-u", "origin", br)
    r = subprocess.run(["gh", "pr", "create", "--fill", "--title",
                        f"[ТРЕБУЕТ ОДОБРЕНИЯ ОПЕРАТОРА] {path}",
                        "--body", operator_pr_body(content)],
                       capture_output=True, text=True, env=dict(os.environ))
    sh("git", "checkout", "main")
    if r.returncode != 0:
        raise CommandFailed(f"FILE {path}: PR не создан: {r.stderr.strip()[:300]}")
    url = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    L.notify(f"PR «ТРЕБУЕТ ОДОБРЕНИЯ ОПЕРАТОРА»: {path} {url}", L.ACTION)
    print(f"FILE -> PR (protected): {path} {url}")

def notify_level(title):
    """Тема [CONSILIUM-NOTIFY]: «!ACTION ...» / «!ALARM ...» -> уровень, иначе INFO.
    -> (уровень, тема без метки). Метка — отдельное слово: «!ACTIONS» меткой не является."""
    first, _, tail = title.strip().partition(" ")
    if first in ("!ACTION", "!ALARM"):
        return first[1:], tail.strip()
    return L.INFO, title

def do_notify(title, body):
    level, title = notify_level(title)
    text = (title + ("\n" + body if body else "")).strip() or "(пустое уведомление)"
    if not L.notify(text, level):
        raise CommandFailed("NOTIFY: Telegram не принял сообщение (нет секретов или ошибка отправки)")

def recent_commands(M, days=WINDOW_DAYS):
    """Письма за N дней с тегом в теме. Флаг UNSEEN не используется; PEEK — флаги не меняются.
    IMAP SUBJECT — подстрока, поэтому точный отбор делается на клиенте (parse_command)."""
    since = (dt.date.today() - dt.timedelta(days=days)).strftime("%d-%b-%Y")
    _, data = M.search(None, f'(SINCE {since} SUBJECT "[CONSILIUM-")')
    found = []
    for i in data[0].split():
        _, md = M.fetch(i, "(BODY.PEEK[])")
        msg = email.message_from_bytes(md[0][1])
        subject = decode_hdr(msg["Subject"])
        if parse_command(subject):
            found.append((msg, subject))
    return found

def main():
    addr = os.environ["GMAIL_ADDRESS"]; pwd = os.environ["GMAIL_APP_PASSWORD"]
    token = os.environ.get("MAIL_AUTH_TOKEN", "")
    sh("git", "config", "user.name", "consilium-bridge")
    sh("git", "config", "user.email", "actions@github.com")
    M = imaplib.IMAP4_SSL("imap.gmail.com")
    M.login(addr, pwd); M.select("INBOX", readonly=True)
    cands = recent_commands(M)
    M.logout()
    print(f"bridge: {len(cands)} command-subject message(s) in last {WINDOW_DAYS}d")
    failures = []
    for msg, subject in cands:
        kind, rest = parse_command(subject)
        sender = decode_hdr(msg["From"])
        msgid = (msg["Message-ID"] or "").strip()
        raw, flowed, delsp = body_parts(msg)
        ids, legacy = executed_keys()
        if (msgid and msgid in ids) or (kind, subject, body_sha(raw, token)) in legacy:
            print(f"SKIP (уже исполнено) {kind} {msgid or '(без Message-ID)'}")
            continue
        if addr.lower() not in sender.lower():
            print(f"REJECT (from={sender}): {subject}"); continue
        body = normalize_body(raw, flowed, delsp)
        if token and f"AUTH: {token}" not in body:
            print(f"REJECT (no auth token): {subject}"); continue
        body = body.replace(f"AUTH: {token}", "").strip() if token else body.strip()
        sh("git", "checkout", "main", check=False)
        sh("git", "pull", "--rebase", check=False)
        try:
            log_command(kind, subject, raw, msgid, token)  # след ДО исполнения
        except Exception as e:
            print(f"LOG FAILED, command skipped [{kind}] {subject}: {e}")
            failures.append(f"{kind} {subject}: лог не записан ({e})")
            continue
        try:
            {"TASK": lambda: do_task(rest or "Задача архитектора", body),
             "MERGE": lambda: do_merge(subject, body),
             "FILE": lambda: do_file(subject, body),
             "NOTIFY": lambda: do_notify(rest, body)}[kind]()
        except Exception as e:
            print(f"EXEC ERROR [{kind}] {subject}: {e}")
            failures.append(f"{kind} {subject}: {e}")
            sh("git", "checkout", "main", check=False)
    if failures:
        L.notify(f"Мост: не исполнено {len(failures)} команд(ы): " + "; ".join(f[:120] for f in failures[:3]), L.ALARM)
        sys.exit(1)

if __name__ == "__main__":
    main()
