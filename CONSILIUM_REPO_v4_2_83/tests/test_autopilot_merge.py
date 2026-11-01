"""Consumer-tests for the КОД autopilot (DECISION_2026-11-01_KOD_AUTOPILOT): the bridge merges ordinary
code PRs without the operator ONLY when every condition holds; control-plane paths stay refused.

Drives the consumer do_merge() (gh/notify are in-process fakes; nothing leaves the box) and the
daily report's day_events(). Unknown (no check-runs, mergeable=UNKNOWN, no field) is a named refusal.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import types
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import daily_report as R  # noqa: E402
import llm_clients as L   # noqa: E402
import mail_bridge as B   # noqa: E402

WED = dt.datetime(2026, 11, 4, 12, 0, tzinfo=dt.timezone.utc)   # Wednesday
GOOD_BODY = "## ДЛЯ ОПЕРАТОРА\n- Что меняется: x\n- Тип: КОД\n- Риск: y\n"
OK_CHECKS = {"total_count": 2, "check_runs": [
    {"name": "suite", "status": "completed", "conclusion": "success"},
    {"name": "validate", "status": "completed", "conclusion": "success"}]}


def pr(**kw):
    d = {"files": [{"path": "tools/notify_failure.py"}], "author": {"login": "claude[bot]", "is_bot": True},
         "body": GOOD_BODY, "title": "Fix thing", "mergeable": True, "headRefOid": "abc123"}
    d.update(kw)
    return d


class Harness(unittest.TestCase):
    def run_merge(self, prdata, checks=OK_CHECKS, now=WED, rest=None):
        """Real do_merge(); fakes for gh. -> (merged_cmd or None, notifications, refused_exc or None)."""
        notes, calls, sleeps = [], [], []
        # REST mergeable answers, one per request to pulls/N; default = the PR dict's own value, every time.
        seq = list(rest) if rest is not None else None
        self.rest_requests = 0
        def fake_sh(*a, **k):
            calls.append(a)
            if a[:3] == ("gh", "pr", "view"):
                self.assertNotIn("mergeable", a[-1], "GraphQL mergeable must not be requested")
                return json.dumps({k: v for k, v in prdata.items() if k != "mergeable"})
            if a[:2] == ("gh", "api") and re.search(r"/pulls/\d+$", a[2]):
                self.rest_requests += 1
                val = (seq.pop(0) if len(seq) > 1 else seq[0]) if seq is not None else prdata.get("mergeable")
                return json.dumps({"mergeable": val, "mergeable_state": "x"})
            if a[:2] == ("gh", "api"):
                return json.dumps(checks)
            return ""
        merged = []
        def fake_run(cmd, **k):
            if cmd[:3] == ["gh", "pr", "merge"]:
                merged.append(cmd)
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        saved = (B.sh, B.subprocess.run, L.notify, B.repo_url, B.time.sleep)
        B.sh, B.subprocess.run = fake_sh, fake_run
        B.time.sleep = lambda s: sleeps.append(s)
        L.notify = lambda text, level=L.INFO: notes.append((level, text)) or True
        B.repo_url = lambda: "https://github.com/o/r"
        exc = None
        try:
            B.do_merge("PR#7", "", now=now)
        except B.CommandFailed as e:
            exc = e
        finally:
            B.sh, B.subprocess.run, L.notify, B.repo_url, B.time.sleep = saved
        self.last_calls, self.sleeps = calls, sleeps
        return (merged[0] if merged else None), notes, exc

    def assertRefused(self, prdata, needle, **kw):
        merged, notes, exc = self.run_merge(prdata, **kw)
        self.assertIsNone(merged, "merge must not run")
        self.assertIsNotNone(exc)
        self.assertIn(needle, str(exc))
        self.assertEqual([lv for lv, _ in notes], [L.ACTION])
        self.assertTrue(any(c[:3] == ("gh", "pr", "comment") for c in self.last_calls), "refusal is commented on the PR")


class TestMergeConditions(Harness):
    def test_all_conditions_met_merges_with_marker_subject_pinned_head_and_info(self):
        merged, notes, exc = self.run_merge(pr())
        self.assertIsNone(exc)
        self.assertIn("--match-head-commit", merged)
        self.assertEqual(merged[merged.index("--match-head-commit") + 1], "abc123")
        self.assertEqual(merged[merged.index("--subject") + 1], "[CONSILIUM-MERGE] Fix thing (#7)")
        self.assertEqual(notes, [(L.INFO, "слит PR #7: Fix thing")])

    def test_i_author_must_be_the_bot(self):
        self.assertRefused(pr(author={"login": "someone", "is_bot": False}), "автор PR")
        self.assertRefused(pr(author={"login": "claude", "is_bot": False}), "автор PR")   # human lookalike
        merged, _, exc = self.run_merge(pr(author={"login": "app/claude", "is_bot": True}))
        self.assertIsNone(exc)

    def test_ii_type_line_code_required_law_refused(self):
        self.assertRefused(pr(body="## ДЛЯ ОПЕРАТОРА\n- Тип: ЗАКОН\n"), "ЗАКОН")
        self.assertRefused(pr(body="просто текст"), "Тип: КОД")
        self.assertRefused(pr(body=""), "Тип: КОД")
        self.assertRefused(pr(body="- Тип: ЗАКОН (решения) или КОД (код)\n"), "ЗАКОН")
        self.assertRefused(pr(body="- Тип: КОД\n- Тип: ЗАКОН\n"), "ЗАКОН")

    def test_iii_checks_must_be_complete_green_and_include_tests(self):
        self.assertRefused(pr(), "нет check-runs", checks={"total_count": 0, "check_runs": []})
        self.assertRefused(pr(), "нет workflow tests", checks={"total_count": 1, "check_runs": [
            {"name": "validate", "status": "completed", "conclusion": "success"}]})
        for st, concl in (("in_progress", None), ("completed", "failure"), ("completed", "skipped"),
                          ("completed", "neutral"), ("queued", None)):
            ch = {"total_count": 2, "check_runs": [
                {"name": "suite", "status": "completed", "conclusion": "success"},
                {"name": "other", "status": st, "conclusion": concl}]}
            self.assertRefused(pr(), "не завершены или не успешны", checks=ch)
        self.assertRefused(pr(), "неполон", checks={"total_count": 150, "check_runs": OK_CHECKS["check_runs"]})
        # tests themselves red
        self.assertRefused(pr(), "suite=completed/failure", checks={"total_count": 1, "check_runs": [
            {"name": "suite", "status": "completed", "conclusion": "failure"}]})

    def test_iv_conflicts_refused(self):
        self.assertRefused(pr(mergeable=False), "конфликты")
        self.assertEqual(self.rest_requests, 1)      # a definite false is not retried

    def test_iv_null_then_true_merges_after_pause(self):
        merged, _, exc = self.run_merge(pr(), rest=[None, True])
        self.assertIsNone(exc)
        self.assertIsNotNone(merged)
        self.assertEqual(self.rest_requests, 2)
        self.assertEqual(self.sleeps, [5])

    def test_iv_null_forever_is_named_refusal_after_four_retries(self):
        self.assertRefused(pr(mergeable=None), "mergeable не вычислен GitHub")
        self.assertEqual(self.rest_requests, 5)      # first request + 4 retries
        self.assertEqual(self.sleeps, [5, 5, 5, 5])

    def test_iv_null_then_false_refused_as_conflicts(self):
        self.assertRefused(pr(), "конфликты", rest=[None, False])

    def test_iv_garbage_mergeable_is_not_a_pass(self):
        self.assertRefused(pr(), "mergeable не вычислен GitHub", rest=["true"])

    def test_iv_graphql_mergeable_not_used(self):
        with open(B.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertNotRegex(src, r'"files,author,body,title,[^"]*mergeable')

    def test_v_freeze_window_boundaries_for_freeze_files(self):
        U = dt.timezone.utc
        for path in ("tools/floor1_card.py", "tools/panel_axes.py", "config/x.json"):
            p = pr(files=[{"path": path}])
            self.assertRefused(p, "заморозка", now=dt.datetime(2026, 11, 6, 0, 0, tzinfo=U))    # Fri 00:00 in
            self.assertRefused(p, "заморозка", now=dt.datetime(2026, 11, 7, 12, 0, tzinfo=U))   # Sat
            self.assertRefused(p, "заморозка", now=dt.datetime(2026, 11, 8, 7, 59, tzinfo=U))   # Sun 07:59 in
            for out in (dt.datetime(2026, 11, 5, 23, 59, tzinfo=U), dt.datetime(2026, 11, 8, 8, 0, tzinfo=U),
                        dt.datetime(2026, 11, 9, 0, 0, tzinfo=U)):                              # Thu 23:59, Sun 08:00, Mon
                _, _, exc = self.run_merge(p, now=out)
                self.assertIsNone(exc, (path, out))

    def test_freeze_is_in_utc_not_local_time(self):
        plus3 = dt.timezone(dt.timedelta(hours=3))
        thu_2330_utc_as_fri_0230 = dt.datetime(2026, 11, 6, 2, 30, tzinfo=plus3)   # = Thu 23:30 UTC
        self.assertFalse(B.in_freeze(thu_2330_utc_as_fri_0230))
        self.assertTrue(B.in_freeze(dt.datetime(2026, 11, 5, 23, 30, tzinfo=dt.timezone(dt.timedelta(hours=-1)))))  # = Fri 00:30 UTC

    def test_freeze_does_not_block_ordinary_code(self):
        _, _, exc = self.run_merge(pr(), now=dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.timezone.utc))
        self.assertIsNone(exc)


class TestControlPlaneStillRefused(Harness):
    PATHS = [".github/workflows/x.yml", ".github/CODEOWNERS", "CODEOWNERS", "CLAUDE.md",
             "mailbox/DECISION_2026-11-02_X.md", "mailbox/PREREG_x.md", "mailbox/MANDATE_x.md",
             "tools/validate_artifacts.py", "tools/autocommit.py", "tools/mail_bridge.py", "tools/schedule_guard.py",
             "tools/llm_clients.py", "tools/daily_audit.py", "tools/monthly_audit.py", "tools/audit_facts.py",
             "tools/calibrate_auditor.py"]

    def test_every_operator_path_is_refused_even_with_everything_else_green(self):
        for path in self.PATHS:
            self.assertRefused(pr(files=[{"path": "tools/notify_failure.py"}, {"path": path}]), "защищённые пути")

    def test_ordinary_tools_and_version_tree_are_no_longer_protected(self):
        for path in ("tools/notify_failure.py", "tools/operator_prs.py", "tools/daily_report.py",
                     "CONSILIUM_REPO_v4_2_83/microservice/app.py", "CONSILIUM_REPO_v4_2_83/tests/test_x.py",
                     "mailbox/REPORT_2026-11-02_X.md", "tools/daily_audit_helper.py"):
            _, _, exc = self.run_merge(pr(files=[{"path": path}]))
            self.assertIsNone(exc, path)

    def test_no_files_is_a_named_refusal_not_a_merge(self):
        self.assertRefused(pr(files=[]), "список файлов")


class TestWiring(unittest.TestCase):
    def test_tests_check_name_is_the_job_of_tests_yml(self):
        with open(os.path.join(ROOT, ".github/workflows/tests.yml"), encoding="utf-8") as f:
            text = f.read()
        self.assertRegex(text, r"(?m)^jobs:\n  " + re.escape(B.TESTS_CHECK) + r":\n")

    def test_codeowners_lists_exactly_the_control_plane_files_and_no_tools_wildcard(self):
        with open(os.path.join(ROOT, ".github/CODEOWNERS"), encoding="utf-8") as f:
            lines = [l.split() for l in f if l.strip() and not l.startswith("#")]
        pats = {l[0].lstrip("/") for l in lines}
        self.assertNotIn("tools/", pats)
        tools = {p for p in pats if p.startswith("tools/")}
        self.assertEqual(tools, {p for p in B.MERGE_PROTECTED if p.startswith("tools/")})
        for p in B.MERGE_PROTECTED:
            if not p.startswith("tools/"):
                self.assertTrue(p in pats or p + "*" in pats, p)

    def test_file_command_protection_is_unchanged(self):
        self.assertIn("tools/", B.PROTECTED)
        self.assertIn("CONSILIUM_REPO", B.PROTECTED)


class TestDailyReport(unittest.TestCase):
    def test_bridge_merges_are_reported_by_title_and_other_bot_work_is_unchanged(self):
        ev = R.day_events("- [CONSILIUM-MERGE] Fix thing (#7) (abc1234, claude[bot])\n"
                          "- Other (#8) (def5678, claude[bot])").splitlines()
        self.assertEqual(ev[0], "- Слит мостом без оператора: Fix thing")
        self.assertEqual(ev[1], "- Слита работа бота: Other")


if __name__ == "__main__":
    unittest.main()
