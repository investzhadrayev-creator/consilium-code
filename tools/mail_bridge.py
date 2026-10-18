#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Почтовый мост архитектора (раунд 7). Каждые 2 часа читает Gmail оператора и
исполняет письма-команды архитектора. Безопасность: From == GMAIL_ADDRESS,
в теле строка 'AUTH: <MAIL_AUTH_TOKEN>'. КАЖДАЯ команда сначала пишется в
несмываемый journal/architect_commands.log (коммит), ПОТОМ исполняется.

Команды (Subject):
  [CONSILIUM-TASK] <название>        → тело письма становится GitHub Issue для claude[bot]
  [CONSILIUM-MERGE] PR#<N>           → merge PR N; ОТКАЗ, если PR трогает защищённые пути
  [CONSILIUM-FILE] <путь>            → тело (внутри ``` ```) коммитится файлом;
                                        DECISION_/PREREG_/MANDATE_ → только ветка+PR (замок оператора)

Secrets: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, MAIL_AUTH_TOKEN; опц. CONSILIUM_PAT
(PAT оператора: issues от его имени — упоминание @claude гарантированно будит бота).
"""
import base64, email, email.header, imaplib, os, re, subprocess, sys, time

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

def log_command(kind, subject, body):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry = f"{ts} | {kind} | {subject} | body_sha={__import__('hashlib').sha256(body.encode()).hexdigest()[:16]}"
    with open("journal/architect_commands.log", "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    sh("git", "add", "journal/architect_commands.log")
    sh("git", "commit", "-m", f"bridge: log architect command [{kind}]")
    sh("git", "push")
    print("logged:", entry)

def decode_hdr(h):
    return "".join(s.decode(c or "utf-8", errors="replace") if isinstance(s, bytes) else s
                   for s, c in email.header.decode_header(h or ""))

def body_text(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace")
        return ""
    return msg.get_payload(decode=True).decode(
        msg.get_content_charset() or "utf-8", errors="replace")

def do_task(title, body):
    issue_body = body + "\n\n@claude Исполни задачу выше. Правила репозитория — в CLAUDE.md; append-only; именованные отказы; результат через PR."
    out = subprocess.run(["gh", "issue", "create", "--title", title,
                          "--body", issue_body], capture_output=True, text=True, env=gh_env())
    print("issue:", out.stdout or out.stderr)

def do_merge(subject, body):
    m = re.search(r"PR#?(\d+)", subject)
    if not m:
        print("MERGE: номер PR не найден в теме"); return
    n = m.group(1)
    files = sh("gh", "pr", "view", n, "--json", "files",
               "--jq", ".files[].path").split()
    bad = [f for f in files if any(f.startswith(p) or f == p for p in PROTECTED)]
    if bad:
        sh("gh", "pr", "comment", n, "--body",
           "Мост отказал в merge: PR трогает защищённые пути "
           f"({', '.join(bad[:5])}). Требуется одобрение оператора в GitHub.", check=False)
        print(f"MERGE REFUSED pr#{n}: protected paths {bad}")
        return
    print(sh("gh", "pr", "merge", n, "--squash", "--delete-branch", check=False))

def do_file(subject, body):
    path = subject.split("]", 1)[1].strip()
    m = re.search(r"```(?:\w+\n|\n)(.*?)```", body, re.S)
    if not m or not path or ".." in path:
        print("FILE: нет содержимого в ``` ``` или плохой путь"); return
    content = m.group(1)
    protected = any(path.startswith(p) for p in PROTECTED)
    if protected:
        br = f"architect/{int(time.time())}"
        sh("git", "checkout", "-b", br)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if os.path.exists(path) and path.startswith("mailbox/"):
        print(f"FILE REFUSED: {path} существует; mailbox неизменяем — новый файл с supersedes")
        sh("git", "checkout", "main", check=False); return
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    sh("git", "add", path)
    sh("git", "commit", "-m", f"architect via bridge: {path}")
    if protected:
        sh("git", "push", "-u", "origin", br)
        subprocess.run(["gh", "pr", "create", "--fill", "--title",
                        f"[ТРЕБУЕТ ОДОБРЕНИЯ ОПЕРАТОРА] {path}",
                        "--body", "Файл правил от архитектора. Merge — только оператор."],
                       capture_output=True, text=True, env=gh_env())
        sh("git", "checkout", "main")
        print(f"FILE -> PR (protected): {path}")
    else:
        sh("git", "push")
        print(f"FILE committed: {path}")

def main():
    addr = os.environ["GMAIL_ADDRESS"]; pwd = os.environ["GMAIL_APP_PASSWORD"]
    token = os.environ.get("MAIL_AUTH_TOKEN", "")
    sh("git", "config", "user.name", "consilium-bridge")
    sh("git", "config", "user.email", "actions@github.com")
    M = imaplib.IMAP4_SSL("imap.gmail.com")
    M.login(addr, pwd); M.select("INBOX")
    _, data = M.search(None, '(UNSEEN SUBJECT "[CONSILIUM-")')
    ids = data[0].split()
    print(f"bridge: {len(ids)} unseen command(s)")
    for i in ids:
        _, md = M.fetch(i, "(RFC822)")
        msg = email.message_from_bytes(md[0][1])
        subject = decode_hdr(msg["Subject"]); sender = decode_hdr(msg["From"])
        body = body_text(msg)
        M.store(i, "+FLAGS", "\\Seen")
        if addr.lower() not in sender.lower():
            print(f"REJECT (from={sender}): {subject}"); continue
        if token and f"AUTH: {token}" not in body:
            print(f"REJECT (no auth token): {subject}"); continue
        body = body.replace(f"AUTH: {token}", "").strip()
        kind = ("TASK" if "[CONSILIUM-TASK]" in subject else
                "MERGE" if "[CONSILIUM-MERGE]" in subject else
                "FILE" if "[CONSILIUM-FILE]" in subject else None)
        if not kind:
            continue
        sh("git", "pull", "--rebase", check=False)
        log_command(kind, subject, body)  # след ДО исполнения
        try:
            {"TASK": lambda: do_task(subject.split("]", 1)[1].strip() or "Задача архитектора", body),
             "MERGE": lambda: do_merge(subject, body),
             "FILE": lambda: do_file(subject, body)}[kind]()
        except Exception as e:
            print(f"EXEC ERROR [{kind}] {subject}: {e}")
    M.logout()

if __name__ == "__main__":
    main()
