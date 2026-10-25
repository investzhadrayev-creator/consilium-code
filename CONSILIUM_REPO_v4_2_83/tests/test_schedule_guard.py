"""Consumer-tests for schedule reliability (issue #70): reserve slots + idempotency + missed-run watchdog.

Every test drives a CONSUMER (the script's main(), the CLI main(), watch_section()), never only a helper.
git / gh / Telegram / mail are replaced by one in-process fake world; nothing leaves the box.

The workflow YAML cannot be changed by the GitHub app, so the exact new files live in
mailbox/REPORT_2026-10-19_SCHEDULE_WORKFLOWS.md. The guard reads cron from workflow files, so these tests
materialise THAT report's blocks into a temp workflows dir and run the guard against them: the
deliverable the operator will paste is the thing under test, not a copy of it.
"""
import contextlib
import datetime as dt
import io
import json
import os
import re
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True   # the mutation probe edits tools/; no stale .pyc may outlive it
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "tools"))

import autocommit        # noqa: E402
import daily_audit as D  # noqa: E402
import daily_report as R  # noqa: E402
import llm_clients as L  # noqa: E402
import monthly_audit as M  # noqa: E402
import panel_axes as P   # noqa: E402
import schedule_guard as G  # noqa: E402
import weekly_digest as W  # noqa: E402

REPORT = os.path.join(REPO, "mailbox", "REPORT_2026-10-19_SCHEDULE_WORKFLOWS.md")
BRIDGE_REPORT = os.path.join(REPO, "mailbox", "REPORT_2026-10-25_BRIDGE_WORKFLOWS.md")
PEAK_MINUTES = {0, 15, 30, 45}
UTC = dt.timezone.utc


def at(y, m, d, hh, mm):
    return dt.datetime(y, m, d, hh, mm, tzinfo=UTC)


def report_blocks():
    with open(REPORT, encoding="utf-8") as f:
        text = f.read()
    return dict(re.findall(r"### `\.github/workflows/([^`]+)`[^\n]*\n\s*```yaml\n(.*?)```", text, re.S))


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


class World:
    """Fake git + gh. Unknown commands fail loudly (rc 1) and are recorded."""
    def __init__(self):
        self.files = set()
        self.panel_csv = "week_end,eri_value\n"
        self.k1 = False
        self.floor1 = []
        self.activity = True
        self.runs = {}            # workflow file -> [{"event","conclusion","createdAt"}]
        self.fetch_ok = True
        self.ls_ok = True
        self.gh_ok = True
        self.calls = []

    def add_panel_row(self, day):
        self.panel_csv += f"{day},NA\n"

    def sh(self, *cmd):
        self.calls.append(cmd)
        if cmd[:3] == ("git", "fetch", "--quiet"):
            return (0, "", "") if self.fetch_ok else (128, "", "fatal: unable to access")
        if cmd[:3] == ("git", "ls-tree", "--name-only"):
            if not self.ls_ok:
                return 128, "", "fatal: not a tree object"
            path = cmd[-1]
            if path == "Reports/floor1/":
                return 0, "".join(f"Reports/floor1/{n}\n" for n in self.floor1), ""
            if path == "tools/floor1_card.py":
                return 0, (path + "\n" if self.k1 else ""), ""
            return 0, (path + "\n" if path in self.files else ""), ""
        if cmd[:2] == ("git", "show"):
            return 0, self.panel_csv, ""
        if cmd[:2] == ("git", "log"):
            return 0, ("abc1234\n" if self.activity else ""), ""
        if cmd[:3] == ("gh", "run", "list"):
            if not self.gh_ok:
                return 1, "", "HTTP 403"
            return 0, json.dumps([dict(r, status="completed") for r in self.runs.get(cmd[4], [])]), ""
        return 1, "", f"unexpected command {cmd}"

    def pr_creates(self):
        return [c for c in self.calls if c[:3] == ("gh", "pr", "create")]


class Base(unittest.TestCase):
    NOW = at(2026, 10, 19, 15, 40)

    def patch(self, obj, name, value):
        old = getattr(obj, name)
        setattr(obj, name, value)
        self.addCleanup(setattr, obj, name, old)

    def setUp(self):
        self.old_cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, self.old_cwd)
        wf = os.path.join(self.tmp, "wf")
        os.makedirs(wf)
        for name, text in report_blocks().items():
            with open(os.path.join(wf, name), "w", encoding="utf-8") as f:
                f.write(text)
        self.patch(G, "WF_DIR", wf)
        self.w = World()
        self.patch(G, "sh", self.w.sh)
        self.now = self.NOW
        self.patch(G, "utcnow", lambda: self.now)
        self.sent = []
        self.mails = []
        self.llm = []
        self.patch(L, "notify", lambda text: self.sent.append(text) or True)
        self.patch(L, "send_mail", lambda *a, **k: self.mails.append(a) or True)
        self.patch(L, "call", lambda *a, **k: self.llm.append(a) or {"text": "VERDICT: GREEN", "provider": "x", "model": "m", "usage": {}})
        self.published = []

        def no_publish(paths, message, author="x"):
            self.published.append((paths, message))
            return True
        self.patch(autocommit, "publish", no_publish)

    # world helpers (now = Monday 2026-10-19 15:40Z unless a test moves it)
    def publish_day(self, day):
        self.w.files |= {f"journal/digests/DAILY_{day}.md", f"journal/audits/DAILY_AUDIT_{day}.md"}


# ---------------------------------------------------------------------------------------------
# the deliverable: the new workflow files themselves
# ---------------------------------------------------------------------------------------------
EXPECTED_FILES = {"mail_bridge.yml", "daily_report.yml", "daily_audit.yml", "panel_weekly.yml",
                  "weekly_digest.yml", "monthly_audit.yml", "calibrate-auditor.yml",
                  "schedule_watchdog.yml", "notify-failures.yml"}


class TestDeliveredWorkflows(Base):
    def test_report_carries_every_workflow_file(self):
        self.assertEqual(set(report_blocks()), EXPECTED_FILES)

    def test_no_cron_on_a_peak_minute(self):
        found = 0
        for name, text in report_blocks().items():
            for expr in re.findall(r"^\s*-\s*cron:\s*['\"]([^'\"]+)['\"]", text, re.M):
                found += 1
                minutes = G._field(expr.split()[0], 0, 59)
                self.assertFalse(minutes & PEAK_MINUTES, f"{name}: {expr} lands on a peak minute")
        self.assertGreaterEqual(found, 16, "cron lines found: the regex stopped matching the report")

    def test_slot_counts_match_the_issue(self):
        day = at(2026, 10, 20, 0, 0)       # Tuesday
        week = at(2026, 10, 19, 0, 0)      # Mon..Sun, 24 = Saturday
        month = at(2026, 11, 1, 0, 0)
        nd = lambda a, b, n: len(G.slots(n, a, b))
        self.assertEqual(nd(day, day + dt.timedelta(days=1), "mail-bridge"), 48)
        self.assertEqual(nd(day, day + dt.timedelta(days=1), "daily-report"), 2)
        self.assertEqual(nd(day, day + dt.timedelta(days=1), "daily-audit"), 2)
        self.assertEqual(nd(week, week + dt.timedelta(days=7), "panel-weekly"), 5)
        self.assertEqual(nd(week, week + dt.timedelta(days=7), "weekly-digest"), 2)
        self.assertEqual(nd(month, at(2026, 12, 1, 0, 0), "monthly-architect-audit"), 3)
        self.assertEqual(nd(day, day + dt.timedelta(days=1), "calibrate-auditor"), 2)

    def test_panel_slots_are_saturday_x4_and_sunday_x1(self):
        s = G.slots("panel-weekly", at(2026, 10, 19, 0, 0), at(2026, 10, 26, 0, 0))
        self.assertEqual([t.strftime("%a") for t in s], ["Sat"] * 4 + ["Sun"])

    def test_report_runs_before_audit_in_every_slot_pair(self):
        d0, d1 = at(2026, 10, 20, 0, 0), at(2026, 10, 21, 0, 0)
        rep, aud = G.slots("daily-report", d0, d1), G.slots("daily-audit", d0, d1)
        self.assertTrue(all(r < a for r, a in zip(rep, aud)), (rep, aud))

    def test_digest_slots_come_after_a_panel_slot(self):
        w0, w1 = at(2026, 10, 19, 0, 0), at(2026, 10, 26, 0, 0)
        panel, digest = G.slots("panel-weekly", w0, w1), G.slots("weekly-digest", w0, w1)
        for t in digest:
            self.assertTrue(any(p < t for p in panel), t)

    def test_watchdog_slot_is_after_last_panel_slot_plus_grace(self):
        wd = G.expand_cron(re.search(r"cron:\s*'([^']+)'", report_blocks()["schedule_watchdog.yml"]).group(1),
                           at(2026, 10, 19, 0, 0), at(2026, 10, 26, 0, 0))
        self.assertEqual(len(wd), 1)
        last_panel = G.slots("panel-weekly", at(2026, 10, 19, 0, 0), at(2026, 10, 26, 0, 0))[-1]
        self.assertGreaterEqual(wd[0], last_panel + G.GRACE)
        self.assertIn("--only panel-weekly --notify", report_blocks()["schedule_watchdog.yml"])

    def test_every_guarded_workflow_calls_the_guard_before_the_work_and_gates_it(self):
        blocks = report_blocks()
        for wf, name, work in (("daily_report.yml", "daily-report", "tools/daily_report.py"),
                               ("daily_audit.yml", "daily-audit", "tools/daily_audit.py"),
                               ("monthly_audit.yml", "monthly-architect-audit", "tools/monthly_audit.py"),
                               ("panel_weekly.yml", "panel-weekly", "tools/autocommit.py")):
            text = blocks[wf]
            self.assertIn(name, G.SPECS)
            self.assertEqual(G.SPECS[name]["file"], wf)
            self.assertIn(f"tools/schedule_guard.py check {name}", text, wf)
            self.assertLess(text.index("schedule_guard.py check"), text.index(work), wf)
            self.assertIn("ALREADY_PUBLISHED != '1'", text, wf)
        self.assertIn("PANEL_ROW_PUBLISHED != '1'", blocks["panel_weekly.yml"])
        self.assertIn("FLOOR1_PUBLISHED != '1'", blocks["panel_weekly.yml"])
        self.assertIn("tools/weekly_digest.py", blocks["weekly_digest.yml"])

    def test_gh_run_list_users_can_read_actions(self):
        blocks = report_blocks()
        for wf in ("daily_report.yml", "daily_audit.yml", "monthly_audit.yml", "weekly_digest.yml",
                   "schedule_watchdog.yml"):
            self.assertIn("actions: read", blocks[wf], wf)

    def test_failure_observer_watches_the_new_workflows(self):
        text = report_blocks()["notify-failures.yml"]
        for n in ("weekly-digest", "schedule-watchdog", "panel-weekly", "daily-report"):
            self.assertIn(n, text)

    def test_every_workflow_name_in_the_blocks_matches_the_guard_spec(self):
        blocks = report_blocks()
        for name, spec in G.SPECS.items():
            m = re.search(r"^name:\s*(\S+)", blocks[spec["file"]], re.M)
            self.assertEqual(m.group(1), name)


class TestCronExpansion(Base):
    def test_dow_zero_and_seven_are_both_sunday(self):
        for expr in ("7 5 * * 0", "7 5 * * 7"):
            t = G.expand_cron(expr, at(2026, 10, 19, 0, 0), at(2026, 10, 26, 0, 0))
            self.assertEqual([x.day for x in t], [25], expr)

    def test_step_and_list_fields(self):
        t = G.expand_cron("17,47 * * * *", at(2026, 10, 20, 0, 0), at(2026, 10, 20, 2, 0))
        self.assertEqual([x.strftime("%H:%M") for x in t], ["00:17", "00:47", "01:17", "01:47"])

    def test_garbage_cron_is_a_named_refusal(self):
        with self.assertRaises(G.ScheduleError):
            G.parse_cron("61 * * * *")
        with self.assertRaises(G.ScheduleError):
            G.parse_cron("* * * *")


# ---------------------------------------------------------------------------------------------
# idempotency: each script, published result -> exit 0, writes nothing, no PR, no Telegram
# ---------------------------------------------------------------------------------------------
class TestIdempotentScripts(Base):
    def assert_silent(self):
        self.assertEqual(self.w.pr_creates(), [])
        self.assertEqual(self.published, [])
        self.assertEqual(self.sent, [], "a skipped slot must not ping Telegram")
        self.assertEqual(self.mails, [])
        self.assertEqual(self.llm, [])
        self.assertEqual(os.listdir(self.tmp), ["wf"], "a skipped slot wrote files")

    def test_daily_report_published_exits_zero_and_touches_nothing(self):
        self.publish_day("2026-10-19")
        self.patch(R, "sh", lambda *a: self.fail("daily_report did work although the day is published"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            R.main()      # returns normally == exit code 0
        self.assertIn("уже опубликовано", out.getvalue())
        self.assert_silent()

    def test_daily_report_not_published_does_the_work(self):
        self.patch(R, "sh", lambda *a: "- коммит (abc, bot)\n")
        self.patch(R.F, "failed_runs", lambda limit=20: ([], 0, ""))
        os.makedirs("journal/digests")
        with quiet():
            R.main()
        self.assertEqual(len(self.published), 1)
        self.assertEqual(len(self.mails), 1)

    def test_daily_audit_published_exits_zero_and_touches_nothing(self):
        self.publish_day("2026-10-19")
        self.patch(D, "gather", lambda end=None: self.fail("daily_audit gathered although the day is published"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            D.main()
        self.assertIn("уже опубликовано", out.getvalue())
        self.assert_silent()

    def test_daily_audit_not_published_proceeds(self):
        called = []
        self.patch(D, "gather", lambda end=None: called.append(1) or {"commits": "", "cmds": ""})
        with quiet():
            D.main()
        self.assertEqual(called, [1])

    def test_monthly_audit_published_exits_zero_and_touches_nothing(self):
        self.now = at(2026, 11, 2, 6, 10)       # the 2nd-of-month reserve slot
        self.w.files.add("journal/audits/MONTHLY_ARCHITECT_AUDIT_2026-11.md")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            M.main()
        self.assertIn("уже опубликовано", out.getvalue())
        self.assert_silent()

    def test_monthly_audit_other_month_file_does_not_count(self):
        self.now = at(2026, 11, 1, 6, 10)
        self.w.files.add("journal/audits/MONTHLY_ARCHITECT_AUDIT_2026-10.md")
        self.patch(M.F, "failed_runs_text", lambda n: "")
        self.patch(M.F, "fact_sections", lambda n: "")
        self.patch(M, "sh", lambda *a: "")
        os.makedirs("journal/audits")
        with quiet():
            M.main()
        self.assertEqual(len(self.published), 1)
        self.assertEqual(len(self.llm), 2)

    def test_weekly_digest_second_slot_after_a_successful_run_sends_nothing(self):
        self.now = at(2026, 10, 24, 13, 40)      # Saturday reserve slot
        self.w.runs["weekly_digest.yml"] = [
            {"event": "schedule", "conclusion": "success", "createdAt": "2026-10-24T07:44:10Z"}]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            W.main()
        self.assertIn("уже опубликовано", out.getvalue())
        self.assert_silent()

    def test_weekly_digest_failed_first_slot_does_not_count_as_sent(self):
        self.now = at(2026, 10, 24, 13, 40)
        self.w.runs["weekly_digest.yml"] = [
            {"event": "schedule", "conclusion": "failure", "createdAt": "2026-10-24T07:44:10Z"},
            {"event": "schedule", "conclusion": "success", "createdAt": "2026-10-17T07:44:10Z"}]  # last week
        self.patch(W, "sh", lambda *a: "x\n")
        with quiet():
            W.main()
        self.assertEqual(len(self.mails), 1)

    def test_weekly_digest_names_a_missing_panel_instead_of_showing_last_weeks_row(self):
        self.now = at(2026, 10, 24, 7, 40)
        self.w.add_panel_row("2026-10-18")           # previous ISO week
        self.patch(W, "sh", lambda *a: "2026-10-18,NA\n")
        with quiet():
            W.main()
        body = self.mails[0][1]
        self.assertIn("Строка этой недели на main: MISSING", body)

    def test_panel_axes_append_skips_without_fetching_any_axis(self):
        self.now = at(2026, 10, 24, 8, 10)           # Saturday backup slot
        self.w.add_panel_row("2026-10-24")
        for ax in ("ax_vix", "ax_participation", "ax_credit"):
            self.patch(P, ax, lambda *a, _n=ax: self.fail(f"{_n} called although the week is published"))
        self.patch(sys, "argv", ["panel_axes.py", "--append"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            P.main()
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("уже опубликована", out.getvalue())
        self.assertFalse(os.path.exists("journal/PANEL_LOG.csv"))

    def test_panel_axes_without_published_row_runs_and_appends(self):
        self.now = at(2026, 10, 24, 8, 10)
        self.patch(P, "ax_vix", lambda: ("19.0", "15.0", "-1", "20.0", "FALSE"))
        self.patch(P, "ax_participation", lambda: ("0.28", "0.28", "-1"))
        self.patch(P, "ax_credit", lambda: ("NA", "NA", "NA"))
        os.makedirs("journal")
        self.patch(sys, "argv", ["panel_axes.py", "--append"])
        with quiet(), self.assertRaises(SystemExit):
            P.main()
        with open("journal/PANEL_LOG.csv", encoding="utf-8") as f:
            self.assertEqual(len(f.read().splitlines()), 1)

    def test_unverifiable_main_never_claims_published(self):
        self.w.fetch_ok = False
        self.publish_day("2026-10-19")
        r = G.already_published("daily-report", self.now)
        self.assertFalse(r["published"])
        self.assertEqual(r["state"], G.UNKNOWN)
        self.assertIn("git fetch origin main", r["detail"])

    def test_mail_bridge_and_calibration_have_no_period_result(self):
        for n in ("mail-bridge", "calibrate-auditor"):
            self.assertFalse(G.already_published(n, self.now)["published"])


class TestPanelWeekKey(Base):
    def check(self, now):
        self.now = now
        env = os.path.join(self.tmp, "ghenv")
        open(env, "w").close()
        old = os.environ.get("GITHUB_ENV")
        os.environ["GITHUB_ENV"] = env
        self.addCleanup(lambda: os.environ.__setitem__("GITHUB_ENV", old) if old else os.environ.pop("GITHUB_ENV", None))
        with quiet():
            rc = G.main(["schedule_guard.py", "check", "panel-weekly"])
        self.assertEqual(rc, 0)
        with open(env, encoding="utf-8") as f:
            return set(f.read().split())

    def test_saturday_slot_sees_a_sunday_row_of_the_same_iso_week(self):
        self.w.add_panel_row("2026-10-25")          # Sunday of the week that began Mon 2026-10-19
        flags = self.check(at(2026, 10, 24, 8, 10))
        self.assertIn("PANEL_ROW_PUBLISHED=1", flags)
        self.assertIn("ALREADY_PUBLISHED=1", flags)    # K1 absent -> the card is not required

    def test_sunday_reserve_slot_sees_the_saturday_row(self):
        # the realistic order: Saturday published, the Sunday last slot must find it and stay silent
        self.w.add_panel_row("2026-10-24")
        flags = self.check(at(2026, 10, 25, 5, 10))
        self.assertEqual(flags, {"PANEL_ROW_PUBLISHED=1", "ALREADY_PUBLISHED=1"})

    def test_previous_weeks_row_does_not_count(self):
        self.w.add_panel_row("2026-10-18")
        self.assertEqual(self.check(at(2026, 10, 24, 8, 10)), set())

    def test_row_present_but_card_missing_runs_the_card_and_not_the_panel(self):
        self.w.k1 = True
        self.w.add_panel_row("2026-10-24")
        flags = self.check(at(2026, 10, 24, 12, 10))
        self.assertEqual(flags, {"PANEL_ROW_PUBLISHED=1"})   # a second row would be a duplicate week

    def test_row_and_card_published_skips_everything(self):
        self.w.k1 = True
        self.w.add_panel_row("2026-10-24")
        self.w.floor1 = ["FLOOR1_2026-10-24.md", "FLOOR1_2026-10-24.csv"]
        flags = self.check(at(2026, 10, 25, 5, 10))
        self.assertEqual(flags, {"PANEL_ROW_PUBLISHED=1", "FLOOR1_PUBLISHED=1", "ALREADY_PUBLISHED=1"})

    def test_card_of_another_week_does_not_count(self):
        self.w.k1 = True
        self.w.add_panel_row("2026-10-24")
        self.w.floor1 = ["FLOOR1_2026-10-17.md"]
        self.assertNotIn("FLOOR1_PUBLISHED=1", self.check(at(2026, 10, 24, 12, 10)))


# ---------------------------------------------------------------------------------------------
# watchdog
# ---------------------------------------------------------------------------------------------
def runs_at(*stamps, event="schedule", conclusion="success"):
    return [{"event": event, "conclusion": conclusion, "createdAt": s} for s in stamps]


class TestWatchdog(Base):
    def healthy(self):
        """Monday 2026-10-19 15:40Z with everything of the closed periods published."""
        self.publish_day("2026-10-18")
        self.w.files.add("journal/audits/MONTHLY_ARCHITECT_AUDIT_2026-10.md")
        self.w.add_panel_row("2026-10-18")
        self.w.runs["weekly_digest.yml"] = runs_at("2026-10-17T07:44:10Z")
        self.w.runs["mail_bridge.yml"] = runs_at("2026-10-19T15:20:00Z")
        self.w.runs["calibrate-auditor.yml"] = runs_at("2026-10-18T16:55:00Z")
        self.w.runs["daily_report.yml"] = runs_at("2026-10-19T15:41:00Z")

    def rows(self):
        return {r["name"]: r for r in G.watch(self.now)}

    def test_everything_published_is_quiet_and_exit_zero(self):
        self.now = at(2026, 10, 19, 18, 0)
        self.healthy()
        self.publish_day("2026-10-19")
        self.w.runs["calibrate-auditor.yml"] = runs_at("2026-10-19T16:55:00Z")    # the 24 h window moved
        md, n = G.watch_section(self.now)
        self.assertEqual(n, 0, md)
        self.assertEqual(self.sent, [])
        self.assertIn("## Пропущенные запуски", md)
        with quiet():
            self.assertEqual(G.main(["x", "watch", "--only", "daily-audit"]), 0)

    def test_counts_expected_from_cron_and_actual_from_schedule_events_only(self):
        self.healthy()
        self.w.runs["mail_bridge.yml"] = (runs_at("2026-10-19T15:20:00Z", "2026-10-19T03:20:00Z")
                                          + runs_at("2026-10-19T10:00:00Z", event="workflow_dispatch")
                                          + runs_at("2026-10-17T10:00:00Z"))    # older than 24 h
        r = self.rows()["mail-bridge"]
        self.assertEqual(r["expected"], 48)             # '17,47 * * * *' over any 24 h window
        self.assertEqual(r["actual"], 2)
        self.assertIn("| mail-bridge | 48 | 2 |", G.render(list(self.rows().values()), self.now))

    def test_missing_daily_audit_alerts_with_workflow_name_and_operator_hint(self):
        self.healthy()
        self.w.files.discard("journal/audits/DAILY_AUDIT_2026-10-18.md")
        md, n = G.watch_section(self.now)
        self.assertGreaterEqual(n, 1)
        msg = [s for s in self.sent if "daily-audit" in s]
        self.assertEqual(len(msg), 1, self.sent)
        self.assertIn("Actions → daily-audit → Run workflow", msg[0])
        self.assertIn("MISSING", md)

    def test_empty_day_is_not_an_alarm_but_is_named(self):
        self.healthy()
        self.w.files.discard("journal/audits/DAILY_AUDIT_2026-10-18.md")
        self.w.activity = False
        r = self.rows()["daily-audit"]
        self.assertEqual(r["state"], G.NOT_REQUIRED)
        self.assertIn("пустой день", r["detail"])
        self.assertIsNone(r["alert"])

    def test_nothing_missing_means_no_telegram(self):
        self.healthy()
        md, n = G.watch_section(self.now)
        self.assertEqual([s for s in self.sent if "Пропущен" in s], [])

    def test_gh_failure_is_unknown_not_green_and_not_a_false_missing(self):
        self.healthy()
        self.w.gh_ok = False
        rows = self.rows()
        self.assertEqual(rows["weekly-digest"]["state"], G.UNKNOWN)
        self.assertIn("UNAVAILABLE (gh run list", rows["weekly-digest"]["detail"])
        self.assertIsNone(rows["weekly-digest"]["actual"])
        md, n = G.watch_section(self.now)
        self.assertGreaterEqual(n, 1)
        self.assertTrue(any("не смог проверить" in s for s in self.sent), self.sent)
        self.assertIn("| ? |", md)       # unknown counts print as '?', never as 0

    def test_fetch_failure_makes_main_based_states_unknown_not_missing(self):
        self.healthy()
        self.w.fetch_ok = False
        r = self.rows()["daily-report"]
        self.assertEqual(r["state"], G.UNKNOWN)
        self.assertIsNone(r["alert"])

    def test_git_error_on_lookup_is_unknown_not_missing(self):
        self.healthy()
        self.w.ls_ok = False
        r = self.rows()["daily-report"]
        self.assertEqual(r["state"], G.UNKNOWN)
        self.assertIsNone(r["alert"])

    def test_mail_bridge_without_a_single_scheduled_run_alerts(self):
        self.healthy()
        self.w.runs["mail_bridge.yml"] = []
        md, n = G.watch_section(self.now)
        self.assertTrue(any("mail-bridge" in s and "Run workflow" in s for s in self.sent), self.sent)

    def test_sunday_watchdog_alerts_when_the_week_has_no_row(self):
        self.now = at(2026, 10, 25, 7, 40)          # after the last slot (Sun 05:07) + grace
        self.w.add_panel_row("2026-10-18")          # last week's row only
        self.w.runs["panel_weekly.yml"] = runs_at("2026-10-24T05:30:00Z")
        with quiet():
            rc = G.main(["x", "watch", "--only", "panel-weekly", "--notify"])
        self.assertEqual(rc, 1)
        self.assertEqual(len(self.sent), 1)
        self.assertIn("panel-weekly", self.sent[0])
        self.assertIn("2026-10-19", self.sent[0])           # the missed week is named
        self.assertIn("Actions → panel-weekly → Run workflow", self.sent[0])

    def test_sunday_watchdog_is_silent_when_the_week_is_published(self):
        self.now = at(2026, 10, 25, 7, 40)
        self.w.add_panel_row("2026-10-24")
        with quiet():
            rc = G.main(["x", "watch", "--only", "panel-weekly", "--notify"])
        self.assertEqual((rc, self.sent), (0, []))

    def test_watchdog_waits_for_the_last_slot_before_judging_the_week(self):
        self.now = at(2026, 10, 25, 5, 30)          # the Sunday slot may still be running (grace)
        self.w.add_panel_row("2026-10-18")
        p, _ = G.latest_closed_period("panel-weekly", self.now)
        self.assertEqual(p, dt.date(2026, 10, 12))   # judges the previous week, not this one
        self.now = at(2026, 10, 25, 6, 10)
        p, _ = G.latest_closed_period("panel-weekly", self.now)
        self.assertEqual(p, dt.date(2026, 10, 19))

    def test_card_missing_after_k1_counts_as_a_missed_week(self):
        self.now = at(2026, 10, 25, 7, 40)
        self.w.k1 = True
        self.w.add_panel_row("2026-10-24")
        r = self.rows()["panel-weekly"]
        self.assertEqual(r["state"], G.MISSING)
        self.assertIn("FLOOR1_", r["detail"])
        self.assertTrue(r["alert"])

    def test_an_old_miss_is_listed_but_not_re_announced_every_day(self):
        self.now = at(2026, 10, 28, 15, 40)         # three days after the deadline
        self.w.add_panel_row("2026-10-18")
        r = self.rows()["panel-weekly"]
        self.assertEqual(r["state"], G.MISSING)
        self.assertIsNone(r["alert"])

    def test_unknown_workflow_name_is_a_usage_error(self):
        with quiet():
            self.assertEqual(G.main(["x", "watch", "--only", "nonsense"]), 2)

    def test_daily_report_carries_the_section_and_counts_missing_as_problems(self):
        self.healthy()
        self.w.files.discard("journal/audits/DAILY_AUDIT_2026-10-18.md")
        self.patch(R, "sh", lambda *a: "- коммит (abc, bot)\n")
        self.patch(R.F, "failed_runs", lambda limit=20: ([], 0, ""))
        os.makedirs("journal/digests")
        with quiet():
            R.main()
        (name,) = os.listdir("journal/digests")      # the script names the file by the runner's date
        with open(os.path.join("journal/digests", name), encoding="utf-8") as f:
            md = f.read()
        self.assertIn("## Пропущенные запуски", md)
        self.assertIn("daily-audit", md)
        self.assertRegex(self.sent[-1], r"проблем — см\. письмо")
        self.assertNotIn("всё зелёно", self.sent[-1])


# ---------------------------------------------------------------------------------------------
# issue #94: the bridge is not trusted to run on schedule alone -> workflow_run + bridge-age watchdog
# ---------------------------------------------------------------------------------------------
BRIDGE_URL = "https://github.com/investzhadrayev-creator/consilium-code/actions/workflows/mail_bridge.yml"
TRIGGER_WORKFLOWS = ["daily-report", "daily-audit", "panel-weekly", "weekly-digest", "calibrate-auditor"]


def bridge_report_yaml():
    with open(BRIDGE_REPORT, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"### `\.github/workflows/mail_bridge\.yml`\s*\n\s*```yaml\n(.*?)```", text, re.S)
    assert m, "mail_bridge.yml block not found in the bridge report"
    return m.group(1)


class TestBridgeWorkflowRun(unittest.TestCase):
    """The deliverable file itself: the property is 'the bridge fires after the workflows that DO run'."""
    def test_keeps_schedule_and_dispatch_and_adds_workflow_run_on_every_named_workflow(self):
        y = bridge_report_yaml()
        self.assertRegex(y, r"(?m)^  schedule:\n    - cron: '17,47 \* \* \* \*'")
        self.assertRegex(y, r"(?m)^  workflow_dispatch:")
        m = re.search(r"(?m)^  workflow_run:\n    workflows: \[([^\]]*)\]\n    types: \[completed\]", y)
        self.assertIsNotNone(m, "no workflow_run trigger with types: [completed]")
        self.assertEqual([x.strip() for x in m.group(1).split(",")], TRIGGER_WORKFLOWS)
        self.assertIn("concurrency: { group: bridge, cancel-in-progress: false }", y)
        self.assertIn("python3 tools/mail_bridge.py", y)

    def test_every_triggering_name_is_the_name_of_a_real_workflow_file(self):
        """workflow_run matches on `name:`; a name that matches no file never fires (silent no-op)."""
        wf_dir = os.path.join(REPO, ".github", "workflows")
        names = set()
        for fn in os.listdir(wf_dir):
            with open(os.path.join(wf_dir, fn), encoding="utf-8") as f:
                m = re.search(r"^name:\s*(\S+)", f.read(), re.M)
            if m:
                names.add(m.group(1))
        listed = [x.strip() for x in re.search(r"workflows: \[([^\]]*)\]", bridge_report_yaml()).group(1).split(",")]
        self.assertEqual(len(listed), len(TRIGGER_WORKFLOWS))
        for n in listed:
            self.assertIn(n, names)

    def test_the_bridge_does_not_trigger_itself(self):
        y = bridge_report_yaml()
        wr = re.search(r"workflows: \[([^\]]*)\]", y).group(1)
        self.assertNotIn("mail-bridge", wr)


class TestBridgeAgeWatchdog(Base):
    healthy = TestWatchdog.healthy
    rows = TestWatchdog.rows

    def bridge(self, *runs):
        self.w.runs["mail_bridge.yml"] = list(runs)

    def msgs(self):
        return [s for s in self.sent if "Мост" in s]

    def test_older_than_six_hours_alarms_with_hours_action_and_link(self):
        self.healthy()
        self.bridge(*runs_at("2026-10-19T09:30:00Z"))         # 6 h 10 min before 15:40
        md, n = G.watch_section(self.now)
        self.assertGreaterEqual(n, 1)
        (m,) = self.msgs()
        self.assertIn("Мост не запускался 6 ч", m)
        self.assertIn("Actions → mail-bridge → Run workflow", m)
        self.assertIn(BRIDGE_URL, m)
        self.assertEqual(m.count("Run workflow"), 1, m)          # the operator hint once, not wrapped twice

    def test_fresh_run_is_silent(self):
        self.healthy()
        self.bridge(*runs_at("2026-10-19T09:41:00Z"))         # 5 h 59 min
        md, n = G.watch_section(self.now)
        self.assertEqual(self.msgs(), [])
        self.assertEqual(n, 0, md)
        self.assertIsNone(self.rows()["mail-bridge"]["alert"])

    def test_exactly_six_hours_is_still_fresh(self):
        self.healthy()
        self.bridge(*runs_at("2026-10-19T09:40:00Z"))
        self.assertIsNone(self.rows()["mail-bridge"]["alert"])

    def test_a_recent_FAILED_run_does_not_make_the_bridge_fresh(self):
        self.healthy()
        self.bridge(*runs_at("2026-10-19T15:30:00Z", conclusion="failure"),
                    *runs_at("2026-10-19T07:00:00Z"))
        G.watch_section(self.now)
        self.assertEqual(len(self.msgs()), 1, self.sent)
        self.assertIn("8 ч", self.msgs()[0])

    def test_a_workflow_run_or_dispatch_success_counts_not_only_schedule(self):
        self.healthy()
        self.bridge(*runs_at("2026-10-19T14:50:00Z", event="workflow_run"))
        G.watch_section(self.now)
        self.assertEqual(self.msgs(), [])

    def test_no_successful_run_in_the_window_alarms_with_a_lower_bound_not_a_made_up_age(self):
        self.healthy()
        self.bridge(*runs_at("2026-10-19T15:30:00Z", conclusion="failure"))
        G.watch_section(self.now)
        (m,) = self.msgs()
        self.assertIn("более", m)
        self.assertRegex(m, r"Мост не запускался более \d+ ч")

    def test_gh_failure_is_unknown_and_not_a_bridge_alarm(self):
        self.healthy()
        self.w.gh_ok = False
        r = self.rows()["mail-bridge"]
        self.assertEqual(r["state"], G.UNKNOWN)
        self.assertIn("UNAVAILABLE (gh run list", r["detail"])
        self.assertIsNone(r["alert"])
        G.watch_section(self.now)
        self.assertEqual(self.msgs(), [])
        self.assertTrue(any("не смог проверить" in s and "mail-bridge" in s for s in self.sent), self.sent)

    def test_daily_report_carries_the_bridge_alarm_in_its_section_and_counts_it(self):
        self.healthy()
        self.bridge(*runs_at("2026-10-18T03:00:00Z"))
        self.patch(R, "sh", lambda *a: "- коммит (abc, bot)\n")
        self.patch(R.F, "failed_runs", lambda limit=20: ([], 0, ""))
        os.makedirs("journal/digests")
        with quiet():
            R.main()
        (name,) = os.listdir("journal/digests")
        with open(os.path.join("journal/digests", name), encoding="utf-8") as f:
            md = f.read()
        self.assertIn("mail-bridge", md)
        self.assertIn("MISSING", md)
        self.assertEqual(len(self.msgs()), 1, self.sent)
        self.assertRegex(self.sent[-1], r"проблем — см\. письмо")


if __name__ == "__main__":
    unittest.main()
