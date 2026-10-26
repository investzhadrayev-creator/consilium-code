"""Consumer-tests for Telegram importance levels and the operator-PR reminder (issue #92).

Operator approves from a phone and must see in 30 seconds what is needed of them: ACTION/ALARM are
loud (bold header, sound), INFO is silent. Every test drives the CONSUMER (notify() down to the Telegram
payload, daily_report.main(), mail_bridge.main()/do_notify()), not a helper named in a docstring.
Network, git, gh and IMAP are in-process fakes; nothing leaves the box.
"""
import contextlib
import datetime as dt
import io
import os
import re
import sys
import tempfile
import types
import unittest

sys.dont_write_bytecode = True   # the mutation probe edits tools/; no stale .pyc may outlive it
TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools")
sys.path.insert(0, TOOLS)

import autocommit        # noqa: E402
import daily_audit as D  # noqa: E402
import daily_report as R  # noqa: E402
import llm_clients as L  # noqa: E402
import mail_bridge as B  # noqa: E402
import notify_failure as NF  # noqa: E402
import operator_prs as OP  # noqa: E402
import schedule_guard as G  # noqa: E402

# Default-deny: nothing here may reach the real git/gh (same rule as test_automation_tools.py).
G.sh = lambda *cmd: (1, "", "test: git/gh unavailable by design")
OP.sh = lambda *cmd: types.SimpleNamespace(returncode=1, stdout="", stderr="test: gh unavailable by design")

NOW = dt.datetime(2026, 10, 25, 5, 7, tzinfo=dt.timezone.utc)


class Base(unittest.TestCase):
    def patch(self, obj, name, value):
        old = getattr(obj, name)
        setattr(obj, name, value)
        self.addCleanup(setattr, obj, name, old)

    def env(self, **kw):
        for k, v in kw.items():
            old = os.environ.get(k)
            os.environ[k] = v
            self.addCleanup(lambda k=k, old=old: os.environ.pop(k, None) if old is None
                            else os.environ.__setitem__(k, old))

    def tmpcwd(self):
        old = os.getcwd()
        os.chdir(tempfile.mkdtemp())
        self.addCleanup(os.chdir, old)

    def telegram(self):
        """Real notify(), fake wire. -> list of payloads that reached Telegram."""
        self.env(TELEGRAM_BOT_TOKEN="123456789:AAFakeTokenValueXYZ_-abc", TELEGRAM_CHAT_ID="42")
        wire = []
        self.patch(L, "_post", lambda url, headers, body, timeout=0: wire.append(body) or {"ok": True})
        return wire

    def recorder(self):
        """Fake notify() that records (level, text) — for tests of WHO picks which level."""
        got = []
        self.patch(L, "notify", lambda text, level=L.INFO: got.append((level, text)) or True)
        return got


class TestLevelsOnTheWire(Base):
    def test_action_is_loud_with_bold_first_line(self):
        wire = self.telegram()
        self.assertTrue(L.notify("слить PR #5", L.ACTION))
        p = wire[0]
        self.assertTrue(p["text"].startswith("<b>🔴 НУЖНО ВАШЕ РЕШЕНИЕ</b>\n"), p["text"])
        self.assertEqual(p["parse_mode"], "HTML")
        self.assertIs(p["disable_notification"], False)

    def test_alarm_is_loud_with_bold_first_line(self):
        wire = self.telegram()
        self.assertTrue(L.notify("панель не вышла", L.ALARM))
        p = wire[0]
        self.assertTrue(p["text"].startswith("<b>🟠 ТРЕВОГА</b>\n"), p["text"])
        self.assertEqual(p["parse_mode"], "HTML")
        self.assertIs(p["disable_notification"], False)

    def test_info_is_silent_and_is_the_default(self):
        wire = self.telegram()
        L.notify("2026-10-25: всё зелёно", L.INFO)
        L.notify("без уровня")
        for p in wire:
            self.assertIs(p["disable_notification"], True)
            self.assertNotIn("parse_mode", p)
            self.assertNotIn("<b>", p["text"])
        self.assertEqual(wire[0]["text"], "[Консилиум] 2026-10-25: всё зелёно")

    def test_html_in_the_text_is_escaped_and_cannot_inject_markup(self):
        wire = self.telegram()
        L.notify("PR <b>#5</b> & <a href='x'>link</a> <script>", L.ACTION)
        body = wire[0]["text"].split("\n", 1)[1]
        self.assertNotIn("<", body)
        self.assertIn("&lt;b&gt;#5&lt;/b&gt; &amp; &lt;a href", body)

    def test_overlong_loud_text_is_cut_before_escaping_never_inside_an_entity(self):
        wire = self.telegram()
        L.notify("&" * 6000, L.ACTION)
        t = wire[0]["text"]
        self.assertLessEqual(len(t), 4000)
        self.assertTrue(t.endswith("…(усечено)"), t[-30:])
        self.assertIsNone(re.search(r"&(?!amp;)", t), "a cut entity would make Telegram reject the message")

    def test_unknown_level_is_refused_by_name_not_downgraded_to_info(self):
        wire = self.telegram()
        with self.assertRaises(ValueError) as cm:
            L.notify("x", "URGENT")
        self.assertIn("URGENT", str(cm.exception))
        self.assertEqual(wire, [])


class TestCallersPickTheLevel(Base):
    def test_failed_autocommit_check_is_an_alarm(self):
        got = self.recorder()
        self.patch(autocommit, "sh", lambda *cmd, check=True, env=None: "x" if cmd[:3] == ("git", "diff", "--cached") else "")
        self.patch(autocommit.subprocess, "run",
                   lambda *a, **k: types.SimpleNamespace(returncode=1, stdout="BAD", stderr=""))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(autocommit.publish(["p"], "msg"))
        self.assertEqual([lv for lv, t in got if t.startswith("[RED]")], [L.ALARM])

    def test_failed_job_observer_is_an_alarm(self):
        got = self.recorder()
        self.patch(NF, "message", lambda env=None: "Упал job автоматики: x")
        with contextlib.redirect_stdout(io.StringIO()):
            NF.main()
        self.assertEqual(got, [(L.ALARM, "Упал job автоматики: x")])

    def _audit(self, text):
        self.tmpcwd()
        os.makedirs("journal/audits")
        self.patch(autocommit, "publish", lambda *a, **k: True)
        self.patch(L, "send_mail", lambda *a, **k: True)
        got = self.recorder()
        with contextlib.redirect_stdout(io.StringIO()):
            D.write_commit(dt.date(2026, 10, 25), text, red=True)
        return got

    V = "ПОДТВЕРЖДАЮ НАРУШЕНИЕ: правка правила без PR | ПРИЧИНА: прямой коммит | ПЛАН: откатить | КЛАСС: "

    def test_red_audit_with_a_rule_violation_is_an_alarm(self):
        for cls in ("ПРАВИЛО", "ЗАДНИМ_ЧИСЛОМ", "ПОДСТАНОВКА"):
            got = self._audit("## Проход 2\n" + self.V + cls + "\n")
            self.assertEqual([lv for lv, _ in got], [L.ALARM], cls)

    def test_red_audit_without_a_listed_violation_is_info_not_alarm(self):
        for text in ("## Проход 2\n" + self.V + "ИНОЕ\n",                      # class outside the list
                     "## Проход 2\nПОДТВЕРЖДАЮ НАРУШЕНИЕ: что-то | ПЛАН: x\n",   # auditor named no class
                     "## Проход 2\nОТЗЫВАЮ: первое впечатление ошибочно | КЛАСС: ПРАВИЛО\n"):  # not a confirmation
            got = self._audit(text)
            self.assertEqual([lv for lv, _ in got], [L.INFO], text)
            self.assertIn("не из списка", got[0][1])

    def test_daily_report_line_is_info(self):
        self.tmpcwd()
        os.makedirs("journal/digests")
        got = self.recorder()
        self.patch(OP, "sh", lambda *cmd: types.SimpleNamespace(returncode=0, stdout="[]", stderr=""))
        self.patch(L, "send_mail", lambda *a, **k: True)
        self.patch(autocommit, "publish", lambda *a, **k: True)
        self.patch(R, "sh", lambda *a: "- коммит\n")
        self.patch(R.F, "failed_runs", lambda limit=20: ([], 0, ""))
        self.patch(G, "watch_section", lambda *a, **k: ("stub\n", 0))
        with contextlib.redirect_stdout(io.StringIO()):
            R.main()
        self.assertEqual([lv for lv, t in got if "всё зелёно" in t], [L.INFO])


class FakeGh:
    """gh pr list --json ... -> the given PR dicts."""
    def __init__(self, prs, rc=0, stderr=""):
        import json
        self.out, self.rc, self.err = json.dumps(prs), rc, stderr

    def __call__(self, *cmd):
        return types.SimpleNamespace(returncode=self.rc, stdout=self.out if self.rc == 0 else "", stderr=self.err)


def pr(n, title, login, body="", created="2026-10-19T05:00:00Z"):
    return {"number": n, "title": title, "author": {"login": login}, "body": body, "createdAt": created,
            "url": f"https://github.com/o/r/pull/{n}"}


BLOCK = ("## ДЛЯ ОПЕРАТОРА\n- Меняем напоминания в Telegram.\n- Тип: КОД\n- Риск: лишний шум.\n"
         "- ЧЕТВЁРТАЯ-СТРОКА-НЕ-ДОЛЖНА-ПОПАСТЬ\n\n## Что изменено\nдетали\n")


class TestOperatorReminder(Base):
    def test_sees_operator_prs_and_ignores_auto_prs(self):
        got = self.recorder()
        self.patch(OP, "sh", FakeGh([
            pr(42, "diag: shares gap", "app/claude", BLOCK),
            pr(77, "[auto] daily report", "app/github-actions"),
            pr(86, "[ТРЕБУЕТ ОДОБРЕНИЯ ОПЕРАТОРА] mailbox/DECISION_x.md", "app/github-actions", BLOCK),
        ]))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(OP.remind(NOW), (True, None))
        self.assertEqual(len(got), 1, "ONE message for all PRs")
        level, text = got[0]
        self.assertEqual(level, L.ACTION)
        self.assertIn("#42", text)
        self.assertIn("#86", text)
        self.assertNotIn("#77", text)
        self.assertNotIn("[auto]", text)

    def test_message_carries_title_three_block_lines_days_and_link(self):
        got = self.recorder()
        self.patch(OP, "sh", FakeGh([pr(42, "diag: shares gap", "app/claude", BLOCK)]))
        with contextlib.redirect_stdout(io.StringIO()):
            OP.remind(NOW)
        text = got[0][1]
        self.assertIn("#42 diag: shares gap", text)
        self.assertIn("Меняем напоминания в Telegram.", text)
        self.assertIn("Тип: КОД", text)
        self.assertIn("Риск: лишний шум.", text)
        self.assertNotIn("ЧЕТВЁРТАЯ", text, "only the first 3 lines of the block")
        self.assertNotIn("Что изменено", text, "the block ends at the next heading")
        self.assertIn("ждёт 6 дн.", text)               # 2026-10-19 05:00 -> 2026-10-25 05:07
        self.assertIn("https://github.com/o/r/pull/42", text)

    def test_pr_without_the_block_says_so_instead_of_inventing_a_summary(self):
        got = self.recorder()
        self.patch(OP, "sh", FakeGh([pr(5, "x", "app/claude", "просто описание")]))
        with contextlib.redirect_stdout(io.StringIO()):
            OP.remind(NOW)
        self.assertIn("нет блока «ДЛЯ ОПЕРАТОРА»", got[0][1])

    def test_nothing_waiting_sends_nothing(self):
        got = self.recorder()
        self.patch(OP, "sh", FakeGh([pr(77, "[auto] x", "app/github-actions")]))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(OP.remind(NOW), (False, None))
        self.assertEqual(got, [])

    def test_unreadable_pr_list_is_an_alarm_not_silence(self):
        got = self.recorder()
        self.patch(OP, "sh", FakeGh(None, rc=1, stderr="HTTP 502"))
        with contextlib.redirect_stdout(io.StringIO()):
            sent, err = OP.remind(NOW)
        self.assertFalse(sent)
        self.assertIn("502", err)
        self.assertEqual([lv for lv, _ in got], [L.ALARM])

    def test_pr_title_html_reaches_telegram_escaped(self):
        wire = self.telegram()
        self.patch(OP, "sh", FakeGh([pr(9, "<b>x</b> & y", "app/claude", BLOCK)]))
        with contextlib.redirect_stdout(io.StringIO()):
            OP.remind(NOW)
        body = wire[0]["text"].split("\n", 1)[1]
        self.assertNotIn("<", body)
        self.assertIn("&lt;b&gt;x&lt;/b&gt; &amp; y", body)

    def test_repeats_every_day_while_the_pr_is_open_with_growing_wait(self):
        got = self.recorder()
        self.patch(OP, "sh", FakeGh([pr(42, "t", "app/claude", BLOCK)]))
        with contextlib.redirect_stdout(io.StringIO()):
            OP.remind(NOW)
            OP.remind(NOW + dt.timedelta(days=1))
        self.assertEqual(len(got), 2)
        self.assertIn("ждёт 6 дн.", got[0][1])
        self.assertIn("ждёт 7 дн.", got[1][1])

    def test_daily_report_sends_the_reminder_even_on_a_quiet_day(self):
        self.tmpcwd()
        got = self.recorder()
        self.patch(OP, "sh", FakeGh([pr(42, "t", "app/claude", BLOCK)]))
        self.patch(R, "sh", lambda *a: "")                       # no commits in 26h -> "empty day" path
        self.patch(G, "watch_section", lambda *a, **k: ("stub\n", 0))
        with contextlib.redirect_stdout(io.StringIO()):
            R.main()
        self.assertEqual([lv for lv, _ in got if "#42" in _], [L.ACTION])
        self.assertIn(L.INFO, [lv for lv, t in got if "коммитов за 26ч нет" in t])

    def test_daily_report_does_not_send_it_when_the_day_is_already_published(self):
        got = self.recorder()
        self.patch(OP, "sh", FakeGh([pr(42, "t", "app/claude", BLOCK)]))
        self.patch(G, "skip_if_published", lambda name, now=None: True)
        with contextlib.redirect_stdout(io.StringIO()):
            R.main()
        self.assertEqual(got, [], "the second cron slot must not repeat the day's reminder")

    def test_unreadable_pr_list_counts_as_a_problem_in_the_daily_line(self):
        self.tmpcwd()
        os.makedirs("journal/digests")
        got = self.recorder()
        self.patch(OP, "sh", FakeGh(None, rc=1, stderr="boom"))
        self.patch(L, "send_mail", lambda *a, **k: True)
        self.patch(autocommit, "publish", lambda *a, **k: True)
        self.patch(R, "sh", lambda *a: "- коммит\n")
        self.patch(R.F, "failed_runs", lambda limit=20: ([], 0, ""))
        self.patch(G, "watch_section", lambda *a, **k: ("stub\n", 0))
        with contextlib.redirect_stdout(io.StringIO()):
            R.main()
        self.assertFalse(any("всё зелёно" in t for _, t in got), got)


class TestBridgeLevels(Base):
    def test_notify_subject_prefix_selects_the_level(self):
        for subject, level, shown in (
                ("!ACTION Слить PR 5", L.ACTION, "Слить PR 5"),
                ("!ALARM Панель не вышла", L.ALARM, "Панель не вышла"),
                ("Обычная тема", L.INFO, "Обычная тема"),
                ("!ACTIONS не метка", L.INFO, "!ACTIONS не метка"),
                ("!action нижний регистр", L.INFO, "!action нижний регистр")):
            got = self.recorder()
            B.do_notify(subject, "тело")
            self.assertEqual(got[-1][0], level, subject)
            self.assertTrue(got[-1][1].startswith(shown), (subject, got[-1][1]))
            self.assertNotIn("!ACTION ", got[-1][1])
            self.assertNotIn("!ALARM ", got[-1][1])

    def test_notify_command_through_main_reaches_telegram_loud(self):
        wire = self.telegram()
        B.do_notify("!ACTION Слить PR 5", "")
        self.assertTrue(wire[0]["text"].startswith("<b>🔴 НУЖНО ВАШЕ РЕШЕНИЕ</b>\n"))
        self.assertIs(wire[0]["disable_notification"], False)

    def test_refused_merge_of_a_protected_pr_asks_the_operator(self):
        got = self.recorder()
        self.patch(B, "sh", lambda *a, **k: "CLAUDE.md\n" if "--jq" in a else "")
        self.patch(B, "repo_url", lambda: "https://github.com/o/r")
        with self.assertRaises(B.CommandFailed):
            B.do_merge("PR#5", "")
        self.assertEqual([lv for lv, _ in got], [L.ACTION])

    def test_bridge_failure_summary_is_an_alarm(self):
        got = self.recorder()
        self.tmpcwd()
        os.makedirs("journal")
        open(B.LOG, "w").close()
        self.env(GMAIL_ADDRESS="op@example.com", GMAIL_APP_PASSWORD="x", MAIL_AUTH_TOKEN="")
        self.patch(B, "sh", lambda *a, **k: "")
        self.patch(B, "recent_commands", lambda M, days=7: [(
            __import__("email").message_from_bytes(
                b"From: op@example.com\r\nSubject: [CONSILIUM-FILE] x.md\r\nMessage-ID: <z@x>\r\n\r\nno block\r\n"),
            "[CONSILIUM-FILE] x.md")])
        self.patch(B.imaplib, "IMAP4_SSL", lambda host: types.SimpleNamespace(
            login=lambda *a: None, select=lambda *a, **k: None, logout=lambda: None))
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            B.main()
        self.assertIn(L.ALARM, [lv for lv, _ in got])

    def test_pr_body_of_a_bridge_pr_starts_with_the_operator_block_from_the_file(self):
        body = B.operator_pr_body("# DECISION\n\n" + BLOCK + "\nдалее текст\n")
        self.assertTrue(body.startswith("## ДЛЯ ОПЕРАТОРА\n"), body[:60])
        self.assertIn("Меняем напоминания в Telegram.", body)
        self.assertNotIn("Что изменено", body)
        self.assertEqual(OP.operator_block(body).splitlines()[0], "- Меняем напоминания в Telegram.")

    def test_protected_file_pr_created_by_the_bridge_carries_the_block_and_asks_the_operator(self):
        self.tmpcwd()
        got = self.recorder()
        created = []
        self.patch(B, "sh", lambda *a, **k: "")
        self.patch(B.subprocess, "run", lambda cmd, **k: created.append(cmd) or types.SimpleNamespace(
            returncode=0, stdout="https://github.com/o/r/pull/9\n", stderr=""))
        with contextlib.redirect_stdout(io.StringIO()):
            B.do_file("[CONSILIUM-FILE] mailbox/DECISION_x.md",
                      "```markdown\n# DECISION\n\n" + BLOCK + "```\n")
        body = created[0][created[0].index("--body") + 1]
        self.assertTrue(body.startswith("## ДЛЯ ОПЕРАТОРА\n- Меняем напоминания"), body[:80])
        self.assertEqual([lv for lv, _ in got], [L.ACTION])

    def test_pr_body_without_a_block_names_the_gap_and_the_reminder_shows_it(self):
        body = B.operator_pr_body("# DECISION\nбез блока\n")
        self.assertTrue(body.startswith("## ДЛЯ ОПЕРАТОРА\n"))
        self.assertIn("НЕ УКАЗАНО", body)
        self.assertNotIn("нет блока «ДЛЯ ОПЕРАТОРА»", OP.operator_block(body))   # the block exists, its fields are refusals


if __name__ == "__main__":
    unittest.main()
