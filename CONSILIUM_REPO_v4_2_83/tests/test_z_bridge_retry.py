"""Consumer-tests for issue #404: a bridge command counts as executed only when its RESULT line exists;
GitHub-side failures (5xx, "Merge already in progress", push Internal Server Error) are GITHUB_TRANSIENT
(INFO, no RESULT, retried next run, at most 3 retries); dangling auto/bridge-log-* PRs are closed.

Every test drives a CONSUMER (mail_bridge.main()). git/gh/IMAP/Telegram are in-process fakes.
"""
import datetime as dt
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_automation_tools as T   # noqa: E402
import test_z_direct_journal as D   # noqa: E402

B, L = T.B, T.L
UTC = dt.timezone.utc
MID = "<m1@x>"
SUBJ = "[CONSILIUM-MERGE] PR#400"
AFTER = "2026-11-04T13:30:00Z"      # after RETRY_SINCE (merge of #397)
BEFORE = "2026-11-04T10:31:00Z"     # the #400 incident: logged before RESULT-lines existed


def cmd_line(ts=AFTER, msgid=MID, kind="MERGE", subject=SUBJ):
    return f"{ts} | {kind} | {subject} | body_sha=abc123 | msgid={msgid}"


def res_line(status="ok", detail="PR #400 слит", msgid=MID, ts=AFTER):
    return f"{ts} | RESULT | MERGE {SUBJ} | {status} | {detail} | msgid={msgid}"


class RetryBase(D.BridgeBase):
    def setUp(self):
        super().setUp()
        self.runs = []                  # what the executor was asked to do
        self.merge_outcomes = []        # per call: exception to raise, or a string
        self.prs = []                   # open PRs for `gh pr list`
        self.closed = []
        base = B.sh

        def sh(*cmd, inp=None, check=True):
            if cmd[:3] == ("gh", "pr", "list"):
                if self.pr_list_fails:
                    raise RuntimeError("gh: HTTP 502")
                return json.dumps(self.prs)
            return base(*cmd, inp=inp, check=check)
        self.pr_list_fails = False
        self.patch(B, "sh", sh)

        def merge(subject, body):
            self.runs.append(subject)
            out = self.merge_outcomes.pop(0) if self.merge_outcomes else "PR #400 слит"
            if isinstance(out, Exception):
                raise out
            return out
        self.patch(B, "do_merge", merge)

        real_run = B.subprocess.run

        def run(cmd, *a, **k):
            if cmd[:3] == ["gh", "pr", "close"]:
                self.closed.append(cmd)
                return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            return real_run(cmd, *a, **k)
        self.patch(B.subprocess, "run", run)
        T.FakeIMAP.mails[b"1"] = self.mail(SUBJ, msgid=MID)

    def seed(self, *lines):
        with open(B.LOG, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def results(self):
        return [l for l in self.journal() if " | RESULT | " in l]

    def commands(self):
        return [l for l in self.journal() if " | MERGE | " in l]


class TestRetryWithoutResult(RetryBase):
    def test_command_line_without_result_is_retried_and_gets_a_result(self):
        self.seed(cmd_line())
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(self.runs, [SUBJ])
        self.assertIn("RETRY (нет RESULT)", out)
        self.assertEqual(len(self.commands()), 2)           # every attempt leaves its own COMMAND line
        (r,) = self.results()
        self.assertIn("| ok | PR #400 слит |", r)

    def test_ok_result_is_final(self):
        self.seed(cmd_line(), res_line("ok"))
        self.run_main()
        self.assertEqual(self.runs, [])

    def test_refused_result_is_final_never_retried(self):
        self.seed(cmd_line(), res_line("refused", "MERGE REFUSED pr#400: PR трогает защищённые пути"))
        code, _ = self.run_main()
        self.assertEqual((code, self.runs), (0, []))
        self.assertEqual(len(self.results()), 1)

    def test_command_logged_before_the_result_epoch_is_not_replayed(self):
        # the whole 7-day window of pre-#397 commands has no RESULT lines: replaying them would
        # create duplicate issues. Unknown epoch != "retry".
        self.seed(cmd_line(ts=BEFORE))
        code, out = self.run_main()
        self.assertEqual((code, self.runs), (0, []))
        self.assertIn("SKIP (уже исполнено)", out)

    def test_result_for_another_msgid_does_not_close_this_one(self):
        self.seed(cmd_line(), res_line("ok", msgid="<other@x>"))
        self.run_main()
        self.assertEqual(self.runs, [SUBJ])

    def test_retry_limit_three_then_refused_result_and_action_notice(self):
        self.seed(*[cmd_line(ts=f"2026-11-04T1{i}:30:00Z") for i in (3, 4, 5)])      # 1 try + 2 retries
        self.run_main()
        self.assertEqual(self.runs, [SUBJ], "third retry is still allowed")
        self.seed(cmd_line(ts="2026-11-04T16:30:00Z"))   # the 4th COMMAND line: 1 try + 3 retries, no RESULT yet
        self.runs.clear(); self.sent.clear(); self.levels.clear()
        # make the journal look exactly like: 4 attempts, no RESULT
        with open(B.LOG, encoding="utf-8") as f:
            kept = [l for l in f.read().splitlines() if " | RESULT | " not in l]
        with open(B.LOG, "w", encoding="utf-8") as f:
            f.write("\n".join(kept) + "\n")
        code, out = self.run_main()
        self.assertEqual(self.runs, [], "no 5th attempt")
        (r,) = self.results()
        self.assertIn("| refused | исчерпаны повторы", r)
        self.assertIn(L.ACTION, self.levels)
        self.assertTrue(any("исчерпаны повторы" in s for s in self.sent), self.sent)
        self.run_main()                                       # and it stays closed
        self.assertEqual((self.runs, len(self.results())), ([], 1))

    def test_same_lines_on_origin_and_in_the_checkout_are_counted_once(self):
        lines = [cmd_line(ts=f"2026-11-04T1{i}:30:00Z") for i in (3, 4, 5)]   # 3 attempts
        self.seed(*lines)
        self.origin = "\n".join(lines) + "\n"          # the very same lines also reached origin/main
        self.run_main()
        self.assertEqual(self.runs, [SUBJ], "3 attempts must not be read as 6 -> exhausted")
        self.assertEqual([r for r in self.results() if "исчерпаны" in r], [])

    def test_dedup_for_mail_without_message_id_is_unchanged(self):
        T.FakeIMAP.mails[b"1"] = self.mail(SUBJ, msgid="")
        code, _ = self.run_main()
        self.assertEqual(len(self.runs), 1)
        self.run_main()
        self.assertEqual(len(self.runs), 1, "legacy dedup (kind, subject, body_sha) must still hold")


class TestGithubTransient(RetryBase):
    def test_classifier_on_real_github_texts(self):
        for t in ("MERGE pr#400 не выполнен: GraphQL: Merge already in progress (mergePullRequest)",
                  "gh: HTTP 502 Bad Gateway", "remote: Internal Server Error", "HTTP 503",
                  "fatal: unable to access 'https://github.com/o/r/': The requested URL returned error: 504",
                  "error: RPC failed; HTTP 500 curl 22", "Gateway Timeout"):
            self.assertTrue(B.is_transient(t), t)
        for t in ("MERGE REFUSED pr#5: PR трогает защищённые пути", "тесты не прошли",
                  "конфликты слияния", "issue #5000 not found", "", None):
            self.assertFalse(B.is_transient(t), t)

    def test_transient_failure_is_info_green_and_has_no_result(self):
        self.merge_outcomes = [B.CommandFailed("MERGE pr#400 не выполнен: Merge already in progress")]
        code, out = self.run_main()
        self.assertEqual(code, 0, "a GitHub blip must not make the job red")
        self.assertIn("INFO GITHUB_TRANSIENT", out)
        self.assertEqual(self.results(), [])
        self.assertEqual(self.sent, [], "no alarm for a transient failure")

    def test_incident_2026_11_04_command_is_executed_on_the_next_run(self):
        self.merge_outcomes = [B.CommandFailed("gh: HTTP 502"), "PR #400 слит"]
        self.run_main()
        self.assertEqual(self.results(), [])
        code, _ = self.run_main()
        self.assertEqual((code, len(self.runs)), (0, 2))
        (r,) = self.results()
        self.assertIn("| ok | PR #400 слит |", r)
        self.run_main()
        self.assertEqual(len(self.runs), 2, "executed once it has a RESULT")

    def test_non_transient_failure_is_still_red_with_refused_result(self):
        self.merge_outcomes = [B.CommandFailed("MERGE REFUSED pr#400: тесты не прошли")]
        code, _ = self.run_main()
        self.assertEqual(code, 1)
        (r,) = self.results()
        self.assertIn("| refused | MERGE REFUSED pr#400: тесты не прошли |", r)
        self.run_main()
        self.assertEqual(len(self.runs), 1, "refusal is never retried")

    def test_log_push_server_error_skips_execution_quietly_and_retries(self):
        calls = []

        def publish(paths, msg, author=""):
            calls.append(msg)
            if len(calls) == 1:
                raise RuntimeError("('git', 'push', '-u', 'origin', 'auto/x'): remote: Internal Server Error")
            return True
        self.patch(T.autocommit, "publish", publish)
        code, out = self.run_main()
        self.assertEqual((code, self.runs), (0, []))
        self.assertIn("INFO GITHUB_TRANSIENT", out)
        self.assertEqual(self.sent, [])
        self.run_main()                          # next run: the command line is written again, command runs
        self.assertEqual(self.runs, [SUBJ])

    def test_log_validation_failure_is_still_red(self):
        def publish(paths, msg, author=""):
            raise RuntimeError("лог команды не прошёл проверку — команда НЕ исполняется")
        self.patch(T.autocommit, "publish", publish)
        code, _ = self.run_main()
        self.assertEqual((code, self.runs), (1, []))


class TestStaleLogPrs(RetryBase):
    def pr(self, n, branch, created, cross=False):
        return {"number": n, "headRefName": branch, "createdAt": created, "isCrossRepository": cross}

    def setUp(self):
        super().setUp()
        T.FakeIMAP.mails = {}
        self.now = dt.datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
        self.patch(B.dt, "datetime", type("DT", (dt.datetime,), {
            "now": classmethod(lambda cls, tz=None: self.now)}))

    def test_only_old_bridge_log_prs_of_this_repo_are_closed_with_branch_deleted(self):
        self.prs = [self.pr(401, "auto/bridge-log-architect-command-merge-1793787188", "2026-11-04T10:13:19Z"),
                    self.pr(402, "auto/bridge-log-architect-command-merge-1", "2026-11-04T11:45:00Z"),   # 15 min
                    self.pr(403, "claude/some-task", "2026-11-04T08:00:00Z"),
                    self.pr(404, "auto/daily-report-1", "2026-11-04T08:00:00Z"),
                    self.pr(405, "auto/bridge-log-x", "2026-11-04T08:00:00Z", cross=True),
                    self.pr(406, "auto/bridge-log-x", "не-дата")]
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual([c[3] for c in self.closed], ["401"])
        self.assertIn("--delete-branch", self.closed[0])
        self.assertIn("не разобран", out)

    def test_exactly_thirty_minutes_is_stale_twenty_nine_is_not(self):
        self.prs = [self.pr(1, "auto/bridge-log-a", "2026-11-04T11:30:00Z"),
                    self.pr(2, "auto/bridge-log-b", "2026-11-04T11:31:00Z")]
        self.run_main()
        self.assertEqual([c[3] for c in self.closed], ["1"])

    def test_gh_failure_in_cleanup_is_a_warning_not_a_red_job_and_mail_still_processed(self):
        self.pr_list_fails = True
        T.FakeIMAP.mails[b"1"] = self.mail(SUBJ, msgid=MID)
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("WARN: уборка висячих PR", out)
        self.assertEqual(self.runs, [SUBJ])

    def test_no_prs_no_closes(self):
        self.run_main()
        self.assertEqual(self.closed, [])


if __name__ == "__main__":
    unittest.main()
