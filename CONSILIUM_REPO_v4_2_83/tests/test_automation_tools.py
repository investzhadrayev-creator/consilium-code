"""Consumer-tests for the root tools/ automation package (issue #55, task 0.6).

The tools live in ../tools (repo root), not in microservice/. Every test drives the CONSUMER
(main()/write_commit()/ax_credit()), not just the helper the docstring names -- the project's own
rule: a contract asserted only in prose is a contract nobody checks.

Network, git, gh, IMAP and Telegram are all replaced by in-process fakes; nothing leaves the box.
"""
import contextlib
import hashlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
import types
import unittest
import urllib.error

sys.dont_write_bytecode = True   # the mutation probe edits these files; no stale .pyc may outlive it
TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools")
sys.path.insert(0, TOOLS)

import autocommit        # noqa: E402
import audit_facts as F  # noqa: E402
import calibrate_auditor as C  # noqa: E402
import daily_audit as D  # noqa: E402
import daily_report as R  # noqa: E402
import llm_clients as L  # noqa: E402
import mail_bridge as B  # noqa: E402
import notify_failure as NF  # noqa: E402
import operator_prs as OP  # noqa: E402
import monthly_audit as M  # noqa: E402
import panel_axes as P   # noqa: E402
import schedule_guard as G  # noqa: E402

# Default-deny: the guard shells out to git/gh. No test in this module may reach the real ones
# (issue #70: the first run of this suite hit a real `git fetch` from a tmp cwd). Tests of the
# guard itself live in test_schedule_guard.py and install their own fakes.
G.sh = lambda *cmd: (1, "", "test: git/gh unavailable by design")
# daily_report now also asks gh for operator PRs (issue #92). Tests of OTHER things see "no open PRs";
# the reminder's own tests (TestOperatorReminder) install their own fakes.
OP.sh = lambda *cmd: types.SimpleNamespace(returncode=0, stdout="[]", stderr="")

SECRET = "123456789:AAFakeTelegramTokenValueXYZ_-abc"


class Patched(unittest.TestCase):
    """Small patch helper that always restores."""
    def patch(self, obj, name, value):
        old = getattr(obj, name)
        setattr(obj, name, value)
        self.addCleanup(setattr, obj, name, old)

    def env(self, **kw):
        for k, v in kw.items():
            old = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
            self.addCleanup(lambda k=k, old=old: os.environ.pop(k, None) if old is None
                            else os.environ.__setitem__(k, old))

    def tmpcwd(self):
        old = os.getcwd()
        d = tempfile.mkdtemp()
        os.chdir(d)
        self.addCleanup(os.chdir, old)
        return d

    def notified(self):
        sent = []
        self.levels = []
        self.patch(L, "notify", lambda text, level=L.INFO: (sent.append(text), self.levels.append(level)) and True)
        return sent


# ---------------------------------------------------------------------------------------------
# item 10: the real-shaped FILE email (CRLF + quoted-printable + format=flowed)
# ---------------------------------------------------------------------------------------------
INTENDED = (
    "# REPORT 2026-10-19 BRIDGE TEST B\n"
    "\n"
    "Длинная строка без переноса, которую почтовик обязан сложить: " + "слово " * 40 + "конец.\n"
    "  indented line (code-ish, begins with spaces)\n"
    "> not a quote, a literal marker\n"
    "```python\n"
    "print('inner fence must survive')\n"
    "```\n"
    "последняя строка — тире и кириллица\n"
)


def flowed_encode(text, width=60, delsp=True):
    """What a mail client does to a format=flowed body: wrap at spaces with a trailing soft space
    (delsp=yes needs ONE EXTRA space, since the decoder deletes one), space-stuff lines that
    begin with ' ', '>' or 'From '."""
    out = []
    for line in text.split("\n"):
        if line.startswith((" ", ">", "From ")):
            line = " " + line
        while len(line) > width and " " in line[:width]:
            cut = line.rfind(" ", 1, width)
            out.append(line[:cut] + ("  " if delsp else " "))
            line = line[cut + 1:]
        out.append(line)
    return "\n".join(out)


def make_email(subject, intended, sender="op@example.com", auth="TOK", msgid="<a1@mail.gmail.com>",
               flowed=True, extra_body_after=""):
    import quopri
    body = f"AUTH: {auth}\n\n```markdown\n{intended}```\n{extra_body_after}"
    body = flowed_encode(body) if flowed else body
    qp = quopri.encodestring(body.encode("utf-8")).replace(b"\n", b"\r\n")
    head = (f"From: {sender}\r\nTo: {sender}\r\nSubject: {subject}\r\nMessage-ID: {msgid}\r\n"
            "MIME-Version: 1.0\r\n"
            'Content-Type: text/plain; charset="UTF-8"; format=flowed; delsp=yes\r\n'
            "Content-Transfer-Encoding: quoted-printable\r\n\r\n").encode()
    return head + qp


class TestFileCommandRealSample(Patched):
    def parse(self, raw_bytes):
        import email
        msg = email.message_from_bytes(raw_bytes)
        raw, flowed, delsp = B.body_parts(msg)
        return raw, B.normalize_body(raw, flowed, delsp)

    def test_crlf_qp_flowed_body_yields_the_exact_file(self):
        raw, body = self.parse(make_email("[CONSILIUM-FILE] mailbox/REPORT_2026-10-19_BRIDGE_TEST_B.md", INTENDED))
        self.assertIn("\r\n", raw, "fixture lost its CRLF: the test no longer reproduces the 2026-10-18 failure")
        self.assertEqual(B.extract_fenced(body), INTENDED)

    def test_control_the_old_regex_cannot_see_this_message(self):
        """Negative control: the pre-0.6 extraction on the same raw text finds NO block (the bug)."""
        import re
        raw, _ = self.parse(make_email("[CONSILIUM-FILE] x", INTENDED))
        self.assertIsNone(re.search(r"```(?:\w+\n|\n)(.*?)```", raw, re.S))

    def test_long_lines_are_not_lost_or_cut(self):
        _, body = self.parse(make_email("[CONSILIUM-FILE] x", INTENDED))
        longest = max(INTENDED.split("\n"), key=len)
        self.assertIn(longest, body.split("\n"))

    def test_unflow_respects_delsp_both_ways(self):
        self.assertEqual(B.unflow("aaa  \nbbb", delsp=True), "aaa bbb")
        self.assertEqual(B.unflow("aaa \nbbb", delsp=False), "aaa bbb")
        self.assertEqual(B.unflow("-- \nsig", delsp=True), "-- \nsig")   # signature separator is not flowed

    def test_nested_fences_take_the_last_closing_fence(self):
        self.assertEqual(B.extract_fenced("x\n```\na\n```js\nb\n```\nc\n```\nsig"), "a\n```js\nb\n```\nc\n")
        self.assertIsNone(B.extract_fenced("no block here"))
        self.assertIsNone(B.extract_fenced("```\nunterminated"))


# ---------------------------------------------------------------------------------------------
# items 1, 8 (bridge half), 10 (red on refusal): main() against a fake mailbox
# ---------------------------------------------------------------------------------------------
class FakeIMAP:
    mails = {}           # id(bytes) -> raw
    searches = []
    stored = []
    selected = []

    def __init__(self, *a, **k):
        pass

    def login(self, *a):
        pass

    def select(self, box, readonly=False):
        FakeIMAP.selected.append((box, readonly))

    def search(self, charset, crit):
        FakeIMAP.searches.append(crit)
        return "OK", [b" ".join(FakeIMAP.mails)]   # permissive server: the client must filter

    def fetch(self, i, what):
        FakeIMAP.fetched = what
        return "OK", [(b"1", FakeIMAP.mails[i])]

    def store(self, *a):
        FakeIMAP.stored.append(a)
        raise AssertionError("bridge must not touch mail flags")

    def logout(self):
        pass


class TestBridgeMain(Patched):
    def setUp(self):
        self.tmpcwd()
        os.makedirs("journal")
        with open(B.LOG, "w", encoding="utf-8") as f:
            f.write("# header\n")
        self.env(GMAIL_ADDRESS="op@example.com", GMAIL_APP_PASSWORD="x", MAIL_AUTH_TOKEN="TOK")
        FakeIMAP.mails, FakeIMAP.searches, FakeIMAP.stored, FakeIMAP.selected = {}, [], [], []
        self.patch(B.imaplib, "IMAP4_SSL", FakeIMAP)
        self.patch(B, "sh", lambda *a, **k: "")
        self.patch(autocommit, "publish", lambda *a, **k: True)
        self.calls = []
        self.patch(B, "do_task", lambda t, b: self.calls.append(("TASK", t, b)))
        self.sent = self.notified()

    def add(self, key, raw):
        FakeIMAP.mails[key] = raw

    def run_main(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            try:
                B.main()
                code = 0
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()

    def task_mail(self, msgid="<t1@x>", subject="[CONSILIUM-TASK] Сделай X", body="Тело задачи"):
        return (f"From: op@example.com\r\nSubject: {subject}\r\nMessage-ID: {msgid}\r\n"
                f"Content-Type: text/plain; charset=utf-8\r\n\r\nAUTH: TOK\r\n{body}\r\n").encode()

    def test_only_exact_command_subjects_are_taken_and_nothing_is_touched(self):
        # worst case: even with the operator's address and a valid token the tag mid-subject is NOT a command
        gh = ("From: op@example.com\r\nSubject: [investzhadrayev-creator/consilium-code] "
              "Re: [CONSILIUM-TASK] PR run failed\r\nMessage-ID: <gh@x>\r\n\r\nAUTH: TOK\r\nbody\r\n").encode()
        self.add(b"1", gh)
        self.add(b"2", self.task_mail())
        code, _ = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual([c[0] for c in self.calls], ["TASK"], "GitHub notification was executed as a command")
        self.assertEqual(FakeIMAP.stored, [], "bridge changed mail flags")
        self.assertTrue(all(ro for _, ro in FakeIMAP.selected), "mailbox must be opened read-only")
        self.assertNotIn("UNSEEN", FakeIMAP.searches[0], "must not depend on the unread flag")
        self.assertIn("SINCE", FakeIMAP.searches[0])
        self.assertIn("PEEK", FakeIMAP.fetched)

    def test_already_read_message_is_still_executed(self):
        # a manually-read mail is indistinguishable server-side for our purposes: we never ask for \Unseen
        self.add(b"1", self.task_mail())
        self.run_main()
        self.assertEqual(len(self.calls), 1)

    def test_message_id_is_logged_and_second_run_skips(self):
        self.add(b"1", self.task_mail(msgid="<dup@x>"))
        self.run_main()
        with open(B.LOG, encoding="utf-8") as f:
            self.assertIn("msgid=<dup@x>", f.read())
        self.run_main()
        self.assertEqual(len(self.calls), 1, "same Message-ID executed twice")

    def test_parse_command_accepts_exactly_the_four_tags_at_the_start(self):
        for k in ("TASK", "MERGE", "FILE", "NOTIFY"):
            self.assertEqual(B.parse_command(f"[CONSILIUM-{k}] x")[0], k)
        for bad in ("[investzhadrayev-creator/consilium-code] Re: [CONSILIUM-TASK] x", "Re: [CONSILIUM-TASK] x",
                    "[CONSILIUM-OTHER] x", "CONSILIUM-TASK x", ""):
            self.assertIsNone(B.parse_command(bad), bad)

    def test_legacy_log_line_without_msgid_dedupes_by_kind_subject_hash(self):
        # old bridge: sha of the body AFTER removing "AUTH: <token>" and .strip()
        old_sha = hashlib.sha256("Тело".encode()).hexdigest()[:16]
        with open(B.LOG, "a", encoding="utf-8") as f:
            f.write(f"2026-10-18T00:00:00Z | TASK | [CONSILIUM-TASK] Старая | body_sha={old_sha}\n")
        self.add(b"1", self.task_mail(subject="[CONSILIUM-TASK] Старая", body="Тело"))
        self.run_main()
        self.assertEqual(self.calls, [])

    def test_command_from_a_stranger_is_rejected_not_executed(self):
        self.add(b"1", self.task_mail().replace(b"op@example.com", b"evil@example.com"))
        code, out = self.run_main()
        self.assertEqual(self.calls, [])
        self.assertIn("REJECT", out)

    def test_notify_logs_first_then_sends(self):
        order = []
        self.patch(B, "log_command", lambda *a, **k: order.append("log"))
        self.patch(B.L, "notify", lambda t, level=L.INFO: order.append("notify:" + t) or True)
        self.add(b"1", self.task_mail(subject="[CONSILIUM-NOTIFY] Заголовок", body="строка тела"))
        code, _ = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(order[0], "log")
        self.assertIn("Заголовок", order[1])
        self.assertIn("строка тела", order[1])

    def test_notify_that_cannot_be_delivered_turns_the_job_red(self):
        self.patch(B.L, "notify", lambda t, level=L.INFO: False)
        self.add(b"1", self.task_mail(subject="[CONSILIUM-NOTIFY] X"))
        code, _ = self.run_main()
        self.assertEqual(code, 1)

    def test_file_with_no_block_is_red_and_notified_not_silent_green(self):
        self.patch(B, "do_task", B.do_task)
        self.add(b"1", self.task_mail(subject="[CONSILIUM-FILE] mailbox/REPORT_x.md", body="нет блока"))
        code, out = self.run_main()
        self.assertEqual(code, 1, "a refused command must not leave a green job")
        self.assertTrue(any("не исполнено" in s for s in self.sent), self.sent)

    def test_file_real_sample_end_to_end_writes_exact_content(self):
        pub = []
        self.patch(autocommit, "publish", lambda paths, msg, author="": pub.append(paths) or True)
        self.add(b"1", make_email("[CONSILIUM-FILE] mailbox/REPORT_2026-10-19_BRIDGE_TEST_B.md", INTENDED))
        code, _ = self.run_main()
        self.assertEqual(code, 0)
        with open("mailbox/REPORT_2026-10-19_BRIDGE_TEST_B.md", encoding="utf-8") as f:
            self.assertEqual(f.read(), INTENDED)


# ---------------------------------------------------------------------------------------------
# issue #58: body_sha must equal the OLD bridge's hash and must not depend on the secret
# ---------------------------------------------------------------------------------------------
# Real values from journal/architect_commands.log on main (mail TEST_B, 2026-10-18T20:48:33Z).
TEST_B_SAMPLE = json.loads(
    '"```\\r\\n# Тест почтового моста — вариант B\\r\\n\\r\\nДата: 2026-10-19. Автор: архитектор.\\r\\n'
    'Назначение: проверка кодовой фразы моста (вариант B — без обратной кавычки).\\r\\n'
    'Если этот файл появился в main, мост принял фразу варианта B.\\r\\n'
    'Файл-данные, правил не меняет.\\r\\n```"')
TEST_B_SHA = "2495d21235e62f73"
TEST_B_SUBJECT = "[CONSILIUM-FILE] mailbox/REPORT_2026-10-19_BRIDGE_TEST_B.md"
TEST_B_LOG_LINE = f"2026-10-18T20:48:33Z | FILE | {TEST_B_SUBJECT} | body_sha={TEST_B_SHA}\n"


def test_b_mail(token="TOK", subject=TEST_B_SUBJECT, msgid="<tb@x>"):
    import quopri
    body = f"AUTH: {token}\r\n\r\n" + TEST_B_SAMPLE + "\r\n"
    qp = quopri.encodestring(body.encode("utf-8"))
    head = (f"From: op@example.com\r\nSubject: {subject}\r\nMessage-ID: {msgid}\r\n"
            "MIME-Version: 1.0\r\n"
            "Content-Type: text/plain; charset=UTF-8; format=flowed\r\n"
            "Content-Transfer-Encoding: quoted-printable\r\n\r\n").encode()
    return head + qp


class TestBodyShaMatchesOldBridge(Patched):
    def raw_of(self, token):
        import email
        return B.body_parts(email.message_from_bytes(test_b_mail(token)))[0]

    def test_real_test_b_mail_gives_the_hash_in_the_main_journal(self):
        raw = self.raw_of("TOK")
        self.assertIn("\r\n", raw, "fixture lost CRLF: not the real shape")
        self.assertEqual(B.body_sha(raw, "TOK"), TEST_B_SHA)
        self.assertEqual(hashlib.sha256(TEST_B_SAMPLE.encode()).hexdigest()[:16], TEST_B_SHA,
                         "the sample no longer matches the journal value")

    def test_hash_is_independent_of_the_secret(self):
        self.assertEqual(B.body_sha(self.raw_of("TOK-ONE"), "TOK-ONE"),
                         B.body_sha(self.raw_of("another secret 2"), "another secret 2"))

    def test_hash_does_not_normalise_crlf(self):
        """Negative control: the normalised text hashes differently (the 2026-10-19 defect, f9201065...)."""
        raw = self.raw_of("TOK")
        norm = B.normalize_body(raw, True, False)
        self.assertNotEqual(B.body_sha(norm, "TOK"), TEST_B_SHA)

    def test_empty_token_hashes_body_unchanged_but_stripped(self):
        self.assertEqual(B.body_sha("  x\r\n", ""), hashlib.sha256(b"x").hexdigest()[:16])


class TestJournalReplayDoesNotReexecute(Patched):
    def setUp(self):
        self.tmpcwd()
        os.makedirs("journal")
        # the TASK line is built by the OLD bridge's algorithm on a synthetic body (the real TASK
        # mail body is not recoverable from the journal, only its hash)
        task_body = "Тело задачи 0.6\r\nвторая строка"
        self.task_sha = hashlib.sha256(task_body.encode()).hexdigest()[:16]
        self.task_subject = "[CONSILIUM-TASK] 0.6: автоматика"
        with open(B.LOG, "w", encoding="utf-8") as f:
            f.write("# header\n" + TEST_B_LOG_LINE +
                    f"2026-10-19T00:13:27Z | TASK | {self.task_subject} | body_sha={self.task_sha}\n")
        self.env(GMAIL_ADDRESS="op@example.com", GMAIL_APP_PASSWORD="x", MAIL_AUTH_TOKEN="TOK")
        FakeIMAP.mails, FakeIMAP.searches, FakeIMAP.stored, FakeIMAP.selected = {}, [], [], []
        self.patch(B.imaplib, "IMAP4_SSL", FakeIMAP)
        self.patch(B, "sh", lambda *a, **k: "")
        self.published = []
        self.patch(autocommit, "publish", lambda *a, **k: self.published.append(a) or True)
        self.calls = []
        self.patch(B, "do_task", lambda t, b: self.calls.append(("TASK", t, b)))
        self.patch(B, "do_file", lambda s, b: self.calls.append(("FILE", s, b)))
        self.patch(B, "do_merge", lambda s, b: self.calls.append(("MERGE", s, b)))
        self.sent = self.notified()

    def test_legacy_line_skips_test_b(self):
        ids, legacy = B.executed_keys()
        self.assertIn(("FILE", TEST_B_SUBJECT, TEST_B_SHA), legacy)
        FakeIMAP.mails[b"1"] = test_b_mail("TOK")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            B.main()
        self.assertIn("SKIP (уже исполнено) FILE", out.getvalue())
        self.assertEqual(self.calls, [])

    def test_main_on_journal_copy_executes_nothing_and_creates_no_issue(self):
        gh_calls = []
        self.patch(B, "sh", lambda *a, **k: gh_calls.append(a) or "")
        task_mail = (f"From: op@example.com\r\nSubject: {self.task_subject}\r\nMessage-ID: <t0@x>\r\n"
                     "Content-Type: text/plain; charset=utf-8\r\n\r\n"
                     "AUTH: TOK\r\n\r\nТело задачи 0.6\r\nвторая строка\r\n").encode()
        FakeIMAP.mails[b"1"] = test_b_mail("TOK")
        FakeIMAP.mails[b"2"] = task_mail
        before = open(B.LOG, encoding="utf-8").read()
        with contextlib.redirect_stdout(io.StringIO()):
            B.main()
        self.assertEqual(self.calls, [], "old journal commands were re-executed")
        self.assertFalse([c for c in gh_calls if "issue" in c and "create" in c], gh_calls)
        self.assertEqual(self.published, [], "a replayed command was logged again")
        self.assertEqual(open(B.LOG, encoding="utf-8").read(), before)

    def test_new_line_is_logged_without_secret_dependence(self):
        FakeIMAP.mails[b"1"] = test_b_mail("TOK", subject="[CONSILIUM-FILE] mailbox/REPORT_new.md", msgid="<n@x>")
        with contextlib.redirect_stdout(io.StringIO()):
            B.main()
        line = open(B.LOG, encoding="utf-8").read().splitlines()[-1]
        self.assertIn(f"body_sha={TEST_B_SHA}", line)


# ---------------------------------------------------------------------------------------------
# item 2: publish() == False must end the process with 1
# ---------------------------------------------------------------------------------------------
class TestRedJobOnPublishFailure(Patched):
    def setUp(self):
        self.tmpcwd()
        os.makedirs("journal/audits")
        os.makedirs("journal/digests")
        self.real_publish = autocommit.publish
        self.patch(autocommit, "publish", lambda *a, **k: False)
        self.patch(L, "send_mail", lambda *a, **k: True)
        self.sent = self.notified()
        self.patch(F, "sh", lambda *a: (1, "", "stub"))

    def test_daily_audit_exits_1(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as cm:
            D.write_commit(dt.date(2026, 10, 19), "# x\n", red=False)
        self.assertEqual(cm.exception.code, 1)

    def test_daily_audit_red_still_notifies_before_exiting(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            D.write_commit(dt.date(2026, 10, 19), "# x\n", red=True)
        self.assertTrue(any("[RED]" in s and "DAILY_AUDIT_2026-10-19" in s for s in self.sent), self.sent)

    def test_daily_audit_published_does_not_exit(self):
        self.patch(autocommit, "publish", lambda *a, **k: True)
        with contextlib.redirect_stdout(io.StringIO()):
            D.write_commit(dt.date(2026, 10, 19), "# x\n", red=False)

    def test_monthly_audit_exits_1(self):
        self.patch(L, "call", lambda *a, **k: {"text": "VERDICT: GREEN", "provider": "x", "model": "m", "usage": {}})
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as cm:
            M.main()
        self.assertEqual(cm.exception.code, 1)

    def test_daily_report_exits_1(self):
        self.patch(R, "sh", lambda *a: "- коммит (abc, bot)\n")
        self.patch(F, "failed_runs", lambda limit=20: ([], 0, ""))
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as cm:
            R.main()
        self.assertEqual(cm.exception.code, 1)

    def test_review_round_exits_1(self):
        import review_round as RR
        self.patch(RR.L, "call", lambda *a, **k: {"text": "ACCEPT", "provider": "x", "model": "m", "usage": {}})
        self.patch(sys, "argv", ["review_round.py", "ROUNDX_test.md"])
        os.makedirs("mailbox")
        with open("ROUNDX_test.md", "w", encoding="utf-8") as f:
            f.write("round")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as cm:
            RR.main()
        self.assertEqual(cm.exception.code, 1)

    def test_publish_or_exit_helper(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            autocommit.publish_or_exit(["x"], "m")

    def test_autocommit_validation_failure_notifies(self):
        # the [RED] path inside the REAL publish(): fake git/gh and a failing validator
        def fake_sh(*cmd, check=True, env=None):
            return "x" if cmd[:3] == ("git", "diff", "--cached") else ""
        self.patch(autocommit, "sh", fake_sh)
        self.patch(autocommit.subprocess, "run",
                   lambda *a, **k: types.SimpleNamespace(returncode=1, stdout="BAD", stderr=""))
        with contextlib.redirect_stdout(io.StringIO()):
            ok = self.real_publish(["p"], "msg")
        self.assertFalse(ok)
        self.assertTrue(any(s.startswith("[RED]") and "msg" in s for s in self.sent), self.sent)


# ---------------------------------------------------------------------------------------------
# item 7: Gemini 400-on-temperature -> retry without it, honestly labelled
# ---------------------------------------------------------------------------------------------
class TestGeminiTemperature(Patched):
    def setUp(self):
        self.env(GEMINI_API_KEY="k", GEMINI_MODEL="gemini-x")
        self.bodies = []
        self.patch(L.time, "sleep", lambda s: None)

    def fake_post(self, reject_temperature):
        def post(url, headers, body, timeout=120):
            self.bodies.append(json.loads(json.dumps(body)))
            if reject_temperature and "temperature" in body["generationConfig"]:
                raise urllib.error.HTTPError(url, 400, "Bad Request", {}, io.BytesIO(
                    b'{"error":{"message":"Unsupported value: temperature does not support 0"}}'))
            return {"candidates": [{"content": {"parts": [{"text": "ответ"}]}}], "usageMetadata": {}}
        return post

    def test_retry_without_temperature_and_meta_says_not_applied(self):
        self.patch(L, "_post", self.fake_post(True))
        r = L.call_gemini("p")
        self.assertEqual(r["text"], "ответ")
        self.assertEqual(len(self.bodies), 2)
        self.assertIn("temperature", self.bodies[0]["generationConfig"])
        self.assertNotIn("temperature", self.bodies[1]["generationConfig"])
        meta = L.meta_block(r, "p")
        self.assertIn("temp=not_applied", meta)
        self.assertNotIn("temp=0 ", meta, "meta_block claims temperature 0 for a call that ran without it")

    def test_control_accepted_temperature_stays_temp_0(self):
        self.patch(L, "_post", self.fake_post(False))
        r = L.call_gemini("p")
        self.assertEqual(len(self.bodies), 1)
        self.assertIn("temp=0 ", L.meta_block(r, "p"))

    def test_other_400_is_not_retried_silently(self):
        def post(url, headers, body, timeout=120):
            self.bodies.append(body)
            raise urllib.error.HTTPError(url, 400, "Bad", {}, io.BytesIO(b'{"error":"API key not valid"}'))
        self.patch(L, "_post", post)
        with self.assertRaises(L.Unavailable):
            L.call_gemini("p")
        self.assertEqual(len(self.bodies), 1)


# ---------------------------------------------------------------------------------------------
# item 8: notify
# ---------------------------------------------------------------------------------------------
class TestNotify(Patched):
    def test_no_secrets_warns_and_does_not_raise(self):
        self.env(TELEGRAM_BOT_TOKEN=None, TELEGRAM_CHAT_ID=None)
        called = []
        self.patch(L, "_post", lambda *a, **k: called.append(1))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertFalse(L.notify("x"))
        self.assertIn("WARN", out.getvalue())
        self.assertEqual(called, [], "must not try to send without secrets")

    def test_token_never_reaches_the_log_even_when_the_error_contains_it(self):
        self.env(TELEGRAM_BOT_TOKEN=SECRET, TELEGRAM_CHAT_ID="42")

        def boom(url, headers, body, timeout=0):
            raise urllib.error.URLError(f"cannot reach {url}")
        self.patch(L, "_post", boom)
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertFalse(L.notify("x"))
        for stream in (out.getvalue(), err.getvalue()):
            self.assertNotIn(SECRET, stream)
            self.assertNotIn(SECRET.split(":")[1], stream)
        self.assertIn("WARN", out.getvalue())

    def test_sends_prefixed_text_to_the_bot_endpoint(self):
        self.env(TELEGRAM_BOT_TOKEN=SECRET, TELEGRAM_CHAT_ID="42")
        seen = {}

        def post(url, headers, body, timeout=0):
            seen.update(url=url, body=body)
            return {"ok": True}
        self.patch(L, "_post", post)
        self.assertTrue(L.notify("привет"))
        self.assertTrue(seen["url"].startswith("https://api.telegram.org/bot") and seen["url"].endswith("/sendMessage"))
        self.assertEqual(seen["body"]["text"], "[Консилиум] привет")
        self.assertEqual(seen["body"]["chat_id"], "42")

    def test_telegram_not_ok_is_false_not_true(self):
        self.env(TELEGRAM_BOT_TOKEN=SECRET, TELEGRAM_CHAT_ID="42")
        self.patch(L, "_post", lambda *a, **k: {"ok": False, "description": "chat not found"})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(L.notify("x"))


# ---------------------------------------------------------------------------------------------
# item 3: auditor packets carry the facts and label every sample
# ---------------------------------------------------------------------------------------------
class TestAuditFacts(Patched):
    def test_caption_names_truncation(self):
        self.assertIn("показано 40 из 61, лимит 40", F.caption(40, 61, 40))
        self.assertIn("УСЕЧЕНА", F.caption(40, 61, 40))
        self.assertNotIn("УСЕЧЕНА", F.caption(5, 5, 40))
        self.assertIn("неизвестно", F.caption(5, None, 40))   # unknown M is named, not invented

    def fake_gh(self):
        prs = [{"number": 7, "title": "t", "author": {"login": "bot"}, "mergedBy": {"login": "op"},
                "reviewDecision": "APPROVED", "reviews": [{"state": "APPROVED"}],
                "files": [{"path": "tools/a.py"}], "mergedAt": "x"}]
        rs = {"name": "protect-main", "enforcement": "active",
              "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole"}],
              "rules": [{"type": "pull_request"}]}

        def sh(*cmd):
            j = " ".join(cmd)
            if "rulesets" in j:
                return 0, json.dumps(rs), ""
            if cmd[:3] == ("gh", "pr", "list"):
                return 0, json.dumps(prs), ""
            if "search/issues" in j:
                return 0, "9", ""
            if cmd[0] == "git":
                return 0, "2026-10-11\nmailbox/DECISION_2026-10-11_ROUND7_REBOOT.md\n", ""
            return 1, "", "stub"
        self.patch(F, "sh", sh)

    def test_ruleset_and_codeowners_state(self):
        self.fake_gh()
        s = F.ruleset_state()
        self.assertIn("enforcement=active", s)
        self.assertIn("RepositoryRole", s)
        self.assertIn("pull_request", s)
        self.assertIn("CODEOWNERS", s)

    def test_merged_prs_carry_author_merger_decision_paths_and_sample_label(self):
        self.fake_gh()
        s = F.merged_prs(7, limit=1)
        for needle in ("#7", "author=bot", "merged_by=op", "reviewDecision=APPROVED", "tools/a.py",
                       "показано 1 из 9, лимит 1", "УСЕЧЕНА"):
            self.assertIn(needle, s)

    def test_unavailable_source_is_named_not_empty(self):
        self.patch(F, "sh", lambda *a: (1, "", "HTTP 403"))
        self.assertIn("UNAVAILABLE", F.merged_prs(7))
        self.assertIn("UNAVAILABLE", F.ruleset_state().split("\n")[0])

    def test_decisions_listed(self):
        self.fake_gh()
        self.assertIn("mailbox/DECISION_2026-10-11_ROUND7_REBOOT.md", F.decisions(60))

    def test_both_auditor_packets_contain_the_fact_blocks(self):
        self.fake_gh()
        g = {"commits": "c", "cmds": "k", "runs": "r", "issues": "i", "prev": "", "snapshot": False}
        pk = D.build_packet(dt.date(2026, 10, 19), g)
        seen = {}
        self.patch(L, "call", lambda prov, prompt, **k: seen.setdefault(prov, prompt) and
                   {"text": "VERDICT: GREEN", "provider": prov, "model": "m", "usage": {}})
        self.patch(autocommit, "publish", lambda *a, **k: True)
        self.tmpcwd()
        os.makedirs("journal/audits")
        with contextlib.redirect_stdout(io.StringIO()):
            M.main()
        for packet in (pk, seen["openai"]):
            self.assertIn("protect-main", packet)
            self.assertIn("mailbox/DECISION_2026-10-11", packet)
            self.assertIn("СЛИТЫЕ PR", packet)
            self.assertIn("показано", packet)


# ---------------------------------------------------------------------------------------------
# item 4: failed run -> workflow, failed step, last 20 log lines
# ---------------------------------------------------------------------------------------------
class TestDailyReportFailures(Patched):
    def test_each_failed_run_carries_step_and_exactly_the_last_20_log_lines(self):
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.patch(F, "failed_runs", lambda limit=20: (
            [{"databaseId": 11, "name": "panel-weekly", "createdAt": now, "event": "schedule",
              "headBranch": "main"}], 3, ""))
        log = "\n".join(f"logline-{i:02d}" for i in range(1, 31))

        def sh(*cmd):
            return "panel / Публикация через PR" if "--json" in cmd else log
        self.patch(R, "sh", sh)
        md, n = R.failed_details()
        self.assertEqual(n, 1)
        self.assertIn("panel-weekly", md)
        self.assertIn("Публикация через PR", md)
        self.assertIn("logline-30", md)
        self.assertIn("logline-11", md)
        self.assertNotIn("logline-10\n", md + "\n", "more than 20 lines were included")
        self.assertIn("показано 1 из 3, лимит 20", md)

    def test_empty_jobs_say_unknown_step_not_blank(self):
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.patch(F, "failed_runs", lambda limit=20: (
            [{"databaseId": 1, "name": "claude-audit", "createdAt": now, "event": "pull_request",
              "headBranch": "auto/x"}], 1, ""))
        self.patch(R, "sh", lambda *a: "")
        md, n = R.failed_details()
        self.assertIn("НЕИЗВЕСТЕН", md)
        self.assertEqual(n, 1)

    def test_unavailable_run_list_is_a_problem_not_all_green(self):
        self.patch(F, "failed_runs", lambda limit=20: (None, None, "UNAVAILABLE (failed runs): rc=1"))
        md, n = R.failed_details()
        self.assertGreaterEqual(n, 1)

    def test_telegram_line_reflects_the_report(self):
        self.tmpcwd()
        os.makedirs("journal/digests")
        sent = self.notified()
        self.patch(L, "send_mail", lambda *a, **k: True)
        self.patch(autocommit, "publish", lambda *a, **k: True)
        self.patch(R, "sh", lambda *a: "- коммит\n")
        self.patch(F, "failed_runs", lambda limit=20: ([], 0, ""))
        self.patch(G, "watch_section", lambda *a, **k: ("## Пропущенные запуски\nstub\n", 0))
        with contextlib.redirect_stdout(io.StringIO()):
            R.main()
        self.assertTrue(sent[-1].endswith("всё зелёно"), sent)
        self.patch(F, "failed_runs", lambda limit=20: (None, None, "UNAVAILABLE"))
        with contextlib.redirect_stdout(io.StringIO()):
            R.main()
        self.assertIn("проблем — см. письмо", sent[-1])


# ---------------------------------------------------------------------------------------------
# item 5: credit axis names its data path in the log; the PANEL_LOG row is unchanged
# ---------------------------------------------------------------------------------------------
class TestCreditAxisSource(Patched):
    def run_axis(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            res = P.ax_credit()
        return res, err.getvalue()

    def test_fredgraph_attempt_number_is_logged(self):
        self.env(FRED_API_KEY=None)
        self.patch(P, "_credit_fredgraph", lambda: ([float(i) for i in range(1, 31)], ["a1 failed"], 2))
        res, err = self.run_axis()
        self.assertIn("fredgraph (attempt 2 of 3)", err)
        self.assertEqual(len(res), 3, "PANEL_LOG schema is frozen: ax_credit still returns 3 fields")

    def test_api_path_is_logged_and_key_is_not(self):
        self.env(FRED_API_KEY="SECRETKEY")
        self.patch(P, "_credit_fred_api", lambda key: [float(i) for i in range(1, 31)])
        res, err = self.run_axis()
        self.assertIn("FRED API", err)
        self.assertNotIn("SECRETKEY", err)

    def test_no_data_is_NA_and_names_no_source(self):
        self.env(FRED_API_KEY=None)
        self.patch(P, "_credit_fredgraph", lambda: (None, ["e1", "e2", "e3"], None))
        res, err = self.run_axis()
        self.assertEqual(res, (P.NA, P.NA, P.NA))
        self.assertNotIn("data from", err)


# ---------------------------------------------------------------------------------------------
# item 9: calibration is idempotent and refuses by name
# ---------------------------------------------------------------------------------------------
class TestCalibration(Patched):
    def setUp(self):
        self.tmpcwd()
        os.makedirs("mailbox")
        self.env(GEMINI_MODEL="gemini-3.1")
        self.sent = self.notified()
        self.calls = []

        def call_gemini(prompt, system=None, max_tokens=6000, model=None):
            self.calls.append((model, prompt))
            return {"text": f"ответ {model}", "model": model, "temp": "0", "usage": {}, "provider": "gemini"}
        self.patch(L, "call_gemini", call_gemini)
        self.patch(D, "gather", lambda end=None: {"commits": "c", "cmds": "k", "runs": "r", "issues": "i",
                                                  "prev": "", "snapshot": end is not None})
        self.patch(F, "fact_sections", lambda d: "FACTS")
        self.published = []
        self.patch(autocommit, "publish", lambda paths, msg, author="": self.published.append(list(paths)) or True)

    def request(self, text=None):
        with open("mailbox/CALIBRATION_REQUEST_2026-10-19.md", "w", encoding="utf-8") as f:
            f.write(text or "---\ndate: 2026-10-18\ncandidate_model: gemini-4-argon   # кандидат\n---\nтело\n")

    def test_same_packet_to_both_models_and_files_written(self):
        self.request()
        with contextlib.redirect_stdout(io.StringIO()):
            C.main()
        models = [m for m, _ in self.calls]
        self.assertEqual(sorted(models), ["gemini-3.1", "gemini-4-argon"])
        self.assertEqual(self.calls[0][1], self.calls[1][1], "the two models must get one identical packet")
        self.assertTrue(os.path.exists("journal/calibration/2026-10-18_gemini-3.1.md"))
        with open("journal/calibration/2026-10-18_gemini-4-argon.md", encoding="utf-8") as f:
            txt = f.read()
        self.assertIn("ответ gemini-4-argon", txt)
        self.assertIn("provider=gemini model=gemini-4-argon", txt)   # meta_block

    def test_second_run_is_a_noop(self):
        self.request()
        with contextlib.redirect_stdout(io.StringIO()):
            C.main()
            n = len(self.calls)
            C.main()
        self.assertEqual(len(self.calls), n, "answered request was executed again")
        self.assertEqual(len(self.published), 1)

    def test_no_request_means_no_model_call(self):
        with contextlib.redirect_stdout(io.StringIO()):
            C.main()
        self.assertEqual(self.calls, [])

    def test_bad_request_is_a_named_refusal(self):
        self.request("без front matter")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as cm:
            C.main()
        self.assertEqual(cm.exception.code, 1)
        self.assertTrue(any("Калибровка" in s for s in self.sent))
        self.assertEqual(self.calls, [])

    def test_unavailable_candidate_writes_no_placeholder_file(self):
        self.request()

        def call_gemini(prompt, system=None, max_tokens=6000, model=None):
            if model == "gemini-4-argon":
                raise L.Unavailable("HTTP 404")
            return {"text": "ok", "model": model, "temp": "0", "usage": {}, "provider": "gemini"}
        self.patch(L, "call_gemini", call_gemini)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as cm:
            C.main()
        self.assertEqual(cm.exception.code, 1)
        self.assertFalse(os.path.exists("journal/calibration/2026-10-18_gemini-4-argon.md"),
                         "a stub file would mark the request answered forever")


class TestFailureObserver(Patched):
    def test_message_names_workflow_branch_and_link(self):
        m = NF.message({"WF_NAME": "daily-audit", "WF_URL": "https://x/run/1", "WF_BRANCH": "main",
                        "WF_EVENT": "schedule"})
        for needle in ("daily-audit", "https://x/run/1", "main", "schedule"):
            self.assertIn(needle, m)

    def test_missing_name_is_named_unknown_not_blank(self):
        self.assertIn("НЕИЗВЕСТНЫЙ", NF.message({}))

    def test_main_sends_through_notify(self):
        sent = self.notified()
        self.env(WF_NAME="mail-bridge", WF_URL="u", WF_BRANCH="main", WF_EVENT="schedule")
        with contextlib.redirect_stdout(io.StringIO()):
            NF.main()
        self.assertEqual(len(sent), 1)
        self.assertIn("mail-bridge", sent[0])


if __name__ == "__main__":
    unittest.main()
