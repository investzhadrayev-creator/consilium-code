"""Consumer-tests for issue #196: TASK-DIRECT in the architect journal, a RESULT line for every command,
the bridge-frequency guard, and the architect-direct section of the auditor packet / daily report.

Every test drives a CONSUMER (mail_bridge.main(), schedule_guard.watch_section(), audit_facts /
daily_audit.build_packet(), daily_report.day_events()/manual_runs_line()). git/gh/IMAP/Telegram are
in-process fakes; nothing leaves the box.
"""
import datetime as dt
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_automation_tools as T   # noqa: E402  (fakes: Patched, FakeIMAP; also sets default-deny stubs)
import test_schedule_guard as S     # noqa: E402

B, F, R, G, D, L = T.B, T.F, T.R, T.G, T.D, T.L
UTC = dt.timezone.utc


def _pristine_daily_report():
    """Other test modules replace daily_report.manual_runs_line with a stub (and the 'REAL' alias gets
    re-saved from the stub on a second import), so load an untouched copy of the module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("daily_report_pristine", os.path.join(T.TOOLS, "daily_report.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
NOW = dt.datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def issue(n, title="Задача", created="2026-11-02T10:00:00Z", author="investzhadrayev-creator",
          labels=("architect",), state="OPEN"):
    return {"number": n, "title": title, "createdAt": created, "state": state,
            "author": {"login": author}, "labels": [{"name": x} for x in labels]}


class BridgeBase(T.Patched):
    ISSUES = []
    ORIGIN = ""
    GH_FAILS = False

    def setUp(self):
        self.tmpcwd()
        os.makedirs("journal")
        with open(B.LOG, "w", encoding="utf-8") as f:
            f.write("# header\n")
        self.env(GMAIL_ADDRESS="op@example.com", GMAIL_APP_PASSWORD="x", MAIL_AUTH_TOKEN="TOK")
        T.FakeIMAP.mails, T.FakeIMAP.searches, T.FakeIMAP.stored, T.FakeIMAP.selected = {}, [], [], []
        T.FakeIMAP.refuse, T.FakeIMAP.listing = (), []
        self.patch(B.imaplib, "IMAP4_SSL", T.FakeIMAP)
        self.published = []
        self.patch(T.autocommit, "publish", lambda paths, msg, author="": self.published.append(msg) or True)
        self.sent = self.notified()
        self.issues = []
        self.origin = ""
        self.gh_fails = False
        self.gh_cmds = []

        def fake_sh(*cmd, inp=None, check=True):
            if cmd[:2] == ("gh", "issue"):
                self.gh_cmds.append(cmd)
                if self.gh_fails:
                    raise RuntimeError("gh: HTTP 502")
                return json.dumps(self.issues)
            if cmd[:2] == ("git", "show"):
                return self.origin
            return ""
        self.patch(B, "sh", fake_sh)

    def run_main(self):
        return T.TestBridgeMain.run_main(self)

    def journal(self):
        with open(B.LOG, encoding="utf-8") as f:
            return f.read().splitlines()

    def mail(self, subject, msgid="<t1@x>", body="Тело"):
        return T.TestBridgeMain.task_mail(self, msgid=msgid, subject=subject, body=body)


class TestTaskDirect(BridgeBase):
    def test_new_architect_issue_gets_exact_task_direct_line_via_autocommit(self):
        self.issues = [issue(201, "Журнал: проверка", "2026-11-02T10:00:00Z")]
        code, _ = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("2026-11-02T10:00:00Z | TASK-DIRECT | #201 Журнал: проверка | msgid=issue-201",
                      self.journal())
        self.assertIn("bridge: log architect command [TASK-DIRECT]", self.published)

    def test_query_asks_for_closed_issues_too_with_label_and_owner(self):
        self.run_main()
        (cmd,) = self.gh_cmds       # an architect task closed within minutes must still be journaled
        self.assertEqual(cmd[cmd.index("--state") + 1], "all")
        self.assertEqual(cmd[cmd.index("--label") + 1], "architect")
        self.assertEqual(cmd[cmd.index("--author") + 1], "investzhadrayev-creator")

    def test_dedup_by_issue_number_from_working_copy_and_from_origin(self):
        self.issues = [issue(201), issue(202)]
        self.origin = "2026-11-02T10:00:00Z | TASK-DIRECT | #201 Задача | msgid=issue-201\n"
        self.run_main()
        lines = [l for l in self.journal() if "TASK-DIRECT" in l]
        self.assertEqual(len(lines), 1, lines)          # 201 was only on origin/main, not in the checkout
        self.assertIn("#202", lines[0])
        self.run_main()                                  # second run: nothing new
        self.assertEqual(len([l for l in self.journal() if "TASK-DIRECT" in l]), 1)

    def test_only_owner_label_and_seven_day_window(self):
        self.patch(B.dt, "datetime", type("DT", (dt.datetime,), {
            "now": classmethod(lambda cls, tz=None: NOW)}))
        self.issues = [issue(1, author="someone-else"), issue(2, labels=("bug",)),
                       issue(3, created="2026-10-20T10:00:00Z"),        # older than 7 days
                       issue(4, created="not-a-date"),                  # unknown != fresh
                       issue(5)]
        self.run_main()
        got = [l for l in self.journal() if "TASK-DIRECT" in l]
        self.assertEqual(len(got), 1, got)
        self.assertIn("#5 ", got[0])

    def test_gh_failure_is_a_named_red_failure_not_no_tasks(self):
        self.gh_fails = True
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("TASK-DIRECT FAILED", out)
        self.assertTrue(any("TASK-DIRECT" in s for s in self.sent), self.sent)

    def test_multiline_title_stays_one_physical_line(self):
        self.issues = [issue(7, "a\nb\r\n  c")]
        self.run_main()
        self.assertIn("#7 a b c | msgid=issue-7", self.journal()[-1])

    def test_task_direct_ids_do_not_poison_mail_dedup(self):
        ids, legacy = B.parse_journal("2026-11-02T10:00:00Z | TASK-DIRECT | #201 X | msgid=issue-201\n")
        self.assertEqual((ids, legacy), (set(), set()))


class TestResultLines(BridgeBase):
    def results(self):
        return [l for l in self.journal() if " | RESULT | " in l]

    def test_success_is_ok_with_what_was_done(self):
        self.patch(B, "do_task", lambda t, b: "issue https://x/issues/9")
        self.add = T.TestBridgeMain.add
        T.FakeIMAP.mails[b"1"] = self.mail("[CONSILIUM-TASK] Сделай X")
        self.run_main()
        (r,) = self.results()
        self.assertRegex(r, r"^\S+ \| RESULT \| TASK \[CONSILIUM-TASK\] Сделай X \| ok \| "
                            r"issue https://x/issues/9 \| msgid=<t1@x>$")

    def test_refusal_is_refused_with_reason_and_job_is_red(self):
        def boom(s, b):
            raise B.CommandFailed("MERGE REFUSED pr#5: тесты не запускались")
        self.patch(B, "do_merge", boom)
        T.FakeIMAP.mails[b"1"] = self.mail("[CONSILIUM-MERGE] PR#5")
        code, _ = self.run_main()
        self.assertEqual(code, 1)
        (r,) = self.results()
        self.assertIn("| refused | MERGE REFUSED pr#5: тесты не запускались |", r)

    def test_executor_without_description_is_named_not_invented(self):
        self.patch(B, "do_task", lambda t, b: None)
        T.FakeIMAP.mails[b"1"] = self.mail("[CONSILIUM-TASK] X")
        self.run_main()
        (r,) = self.results()
        self.assertIn("| ok | исполнитель не вернул описание результата |", r)

    def test_real_executors_return_a_description(self):
        self.patch(B, "do_task", B.do_task)
        self.patch(B.subprocess, "run", lambda *a, **k: type("R", (), {
            "returncode": 0, "stdout": "https://github.com/o/r/issues/77\n", "stderr": ""})())
        self.assertEqual(B.do_task("t", "b"), "issue https://github.com/o/r/issues/77")
        self.patch(L, "notify", lambda *a, **k: True)
        self.assertIn("отправлено", B.do_notify("hi", ""))


class TestBridgeFrequency(S.Base):
    def runs(self, n, end="2026-10-19T15:20:00Z", conclusion="success", event="repository_dispatch"):
        t = dt.datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ")
        return S.runs_at(*[(t - dt.timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
                           for i in range(n)], event=event, conclusion=conclusion)

    def row(self, runs):
        S.TestWatchdog.healthy(self)
        self.w.runs["mail_bridge.yml"] = runs
        return {r["name"]: r for r in G.watch(self.now)}["mail-bridge"]

    def test_23_runs_is_degraded_with_the_named_line_and_alarm(self):
        r = self.row(self.runs(23))
        self.assertEqual(r["state"], G.DEGRADED)
        self.assertIn("мост: 23 запусков за сутки (норма ≥ 24 при внешнем будильнике каждые 15 мин)",
                      r["detail"])
        md, n = G.watch_section(self.now)
        self.assertIn("DEGRADED", md)
        self.assertGreaterEqual(n, 1)
        alarms = [s for s in self.sent if "мост: 23 запусков" in s]
        self.assertEqual(len(alarms), 1, self.sent)

    def test_24_runs_is_published_and_quiet(self):
        r = self.row(self.runs(24))
        self.assertEqual(r["state"], G.PUBLISHED)
        self.assertIsNone(r["alert"])

    def test_failed_runs_and_runs_older_than_24h_are_not_counted(self):
        old = self.runs(10, end="2026-10-18T14:00:00Z")                      # > 24 h before 15:40
        r = self.row(self.runs(23) + self.runs(5, conclusion="failure") + old)
        self.assertEqual(r["state"], G.DEGRADED)
        self.assertIn("мост: 23 запусков", r["detail"])

    def test_stale_bridge_stays_MISSING_not_degraded(self):
        r = self.row(self.runs(30, end="2026-10-19T03:00:00Z"))
        self.assertEqual(r["state"], G.MISSING)

    def test_alarm_goes_out_once_per_daily_report_run(self):
        self.row(self.runs(5))
        G.watch_section(self.now)
        self.assertEqual(len([s for s in self.sent if "запусков за сутки" in s]), 1, self.sent)


class TestAuditorPacketAndReport(T.Patched):
    def fake_gh(self, items=None, rc=0):
        self.cmds = []
        self.patch(F, "sh", lambda *cmd: self.cmds.append(cmd) or (rc, json.dumps(items or []), "boom" if rc else ""))

    def test_section_lists_number_title_created_state_within_26h(self):
        self.fake_gh([{"number": 5, "title": "Свежая", "createdAt": "2026-11-03T08:00:00Z", "state": "OPEN"},
                      {"number": 4, "title": "Старая", "createdAt": "2026-11-01T08:00:00Z", "state": "CLOSED"}])
        md = F.direct_tasks_section(NOW)
        (cmd,) = self.cmds                      # closed issues must be asked for, and only the owner's
        self.assertEqual(cmd[cmd.index("--state") + 1], "all")
        self.assertEqual(cmd[cmd.index("--label") + 1], "architect")
        self.assertEqual(cmd[cmd.index("--author") + 1], "investzhadrayev-creator")
        self.assertIn("## Задачи архитектора напрямую (метка architect) за 26 ч", md)
        self.assertIn("#5 | Свежая | 2026-11-03T08:00:00Z | OPEN", md)
        self.assertNotIn("Старая", md)
        self.assertIn("[показано 2 из 2, лимит 100]", md)

    def test_gh_failure_is_unavailable_not_none(self):
        self.fake_gh(rc=1)
        md = F.direct_tasks_section(NOW)
        self.assertIn("UNAVAILABLE", md)
        self.assertNotIn("(нет)", md)

    def test_packet_contains_the_section(self):
        self.patch(F, "direct_tasks_section", lambda *a, **k: "## Задачи архитектора напрямую MARK")
        self.patch(F, "missed_runs_section", lambda: "## missed")
        self.patch(F, "fact_sections", lambda d: "facts")
        pkt = D.build_packet("2026-11-03", {"cmds": "", "commits": "", "runs": "", "issues": "",
                                            "prev": "", "snapshot": False})
        self.assertIn("Задачи архитектора напрямую MARK", pkt)

    def test_day_events_phrase_for_direct_task_commit(self):
        out = ("+2026-11-02T10:00:00Z | TASK-DIRECT | #201 Журнал: проверка | msgid=issue-201\n"
               "+2026-11-02T11:00:00Z | TASK-DIRECT | #202 Вторая | msgid=issue-202\n")
        self.patch(R, "sh", lambda *a: out)
        ev = R.day_events("- bridge: log architect command [TASK-DIRECT] (abc123, consilium-bridge)")
        self.assertIn("- Архитектор поставил задачу боту (напрямую): Журнал: проверка", ev)
        self.assertIn("- Архитектор поставил задачу боту (напрямую): Вторая", ev)
        self.assertNotIn("#201", ev)

    def test_mail_task_commit_keeps_the_old_phrase(self):
        self.patch(R, "sh", lambda *a: "+2026-11-02T10:00:00Z | TASK | [CONSILIUM-TASK] Х | body_sha=a | msgid=<a>\n")
        ev = R.day_events("- bridge: log architect command [TASK] (abc, consilium-bridge)")
        self.assertIn("- Архитектор поставил задачу боту: Х", ev)
        self.assertNotIn("(напрямую)", ev)

    def test_manual_runs_counter_ignores_repository_dispatch(self):
        def run(event, actor):
            return {"event": event, "createdAt": "2026-11-02T10:00:00Z", "actor": actor}
        runs = [run("repository_dispatch", "investzhadrayev-creator")] * 5 + \
               [run("workflow_dispatch", "investzhadrayev-creator")]
        real = _pristine_daily_report()
        self.patch(F, "_runs_api", lambda limit: (runs, 6, ""))
        line = real.manual_runs_line(NOW)
        self.assertIn("за 7 дней: 1 (", line)


if __name__ == "__main__":
    unittest.main()
