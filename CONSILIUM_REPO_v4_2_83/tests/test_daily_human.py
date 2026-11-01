"""Consumer-tests for the human-readable top of the daily report (issue #144).

Properties pinned (not shapes): the streak counts a week only when EVERY condition holds; an
undeterminable condition is a named refusal and never a count; a Saturday still inside its slots is
neither counted nor a miss; numbers in the day's events come from PANEL_LOG / the card, with named
refusals instead of defaults; the verdict/Telegram level follow real alarms and operator PRs; the
technical sections survive below the line. gh/git are in-process fakes; files live in a tmp dir.
"""
import contextlib
import datetime as dt
import io
import os
import sys
import tempfile
import types
import unittest

sys.dont_write_bytecode = True
TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools")
sys.path.insert(0, TOOLS)

import autocommit        # noqa: E402
import daily_report as R  # noqa: E402
import llm_clients as L  # noqa: E402
import schedule_guard as G  # noqa: E402

UTC = dt.timezone.utc
REAL_MANUAL = getattr(R, "REAL_manual_runs_line", R.manual_runs_line)  # other test modules stub the public name
SAT = dt.date(2026, 10, 31)
HDR = ("week_end,eri_value,eri_vote,expectations_source,vix,vix_50dma,vix_vote,vix3m,vol_stress,rsp_spy,"
       "rsp_spy_50dma,participation_vote,hy_oas,hy_oas_20d_ago,credit_vote,cnn_fg,greed_tag,n_valid,R,regime,"
       "size_multiplier,notes\n")


def row(d, regime="MIXED", size="0.75"):
    return f"{d},NA,NA,NA,19,16,-1,20,FALSE,0.28,0.28,1,3,3,-1,NA,,3,-0.33,{regime},{size},auto\n"


def card(b="95.4"):
    return f"**Покрытие (Б), применимое: 660/692 = {b}%** — заполнено\n"


class Fake:
    """Sources with every condition healthy unless a test breaks one: name -> (value, reason)."""
    def __init__(self, **over):
        self.o = over

    def _get(self, name, s):
        v = self.o.get(name, (True, ""))
        return v(s) if callable(v) else v
    panel_row = lambda self, s: self._get("panel_row", s)
    card_exists = lambda self, s: self._get("card_exists", s)
    card_b = lambda self, s: self._get("card_b", s)
    schedule_publish = lambda self, s: self._get("schedule_publish", s)
    validator = lambda self, s: self._get("validator", s)


def put(path, text, mode="w"):
    with open(path, mode, encoding="utf-8") as f:
        f.write(text)


def at(y, m, d, h=9):
    return dt.datetime(y, m, d, h, 0, tzinfo=UTC)


class Base(unittest.TestCase):
    def patch(self, obj, name, val):
        old = getattr(obj, name)
        setattr(obj, name, val)
        self.addCleanup(setattr, obj, name, old)

    def tmp(self):
        old = os.getcwd()
        d = tempfile.mkdtemp()
        os.chdir(d)
        self.addCleanup(os.chdir, old)
        return d


class TestStreak(Base):
    NOW = at(2026, 11, 1)          # Sunday 09:00 UTC: Saturday 10-31 is closed (slots end 08:00)

    def test_all_conditions_healthy_counts_the_week(self):
        r = R.weeks_streak(self.NOW, Fake())
        self.assertEqual((r["n"], r["last"]), (1, SAT))
        self.assertIn("Авто-недели подряд: 1 из 4 (последняя засчитанная — сб 31.10; следующая — сб 07.11)", R.weeks_line(r))

    def test_each_single_broken_condition_means_not_counted(self):
        for cond in ("panel_row", "card_exists", "card_b", "schedule_publish", "validator"):
            with self.subTest(cond=cond):
                r = R.weeks_streak(self.NOW, Fake(**{cond: (False, f"нет {cond}")}))
                self.assertEqual(r["n"], 0)
                self.assertIn(f"нет {cond}", R.weeks_line(r))

    def test_undeterminable_is_named_and_not_counted(self):
        r = R.weeks_streak(self.NOW, Fake(validator=(None, "gh не ответил")))
        self.assertEqual(r["n"], 0)
        self.assertIn("не определено: gh не ответил", R.weeks_line(r))

    def test_saturday_before_sunday_0800_is_pending_not_a_miss_and_not_counted(self):
        r = R.weeks_streak(at(2026, 10, 31, 18), Fake(panel_row=(False, "ещё нет строки")))
        self.assertEqual((r["n"], r["pending"], r["broken"], r["unknown"]), (0, SAT, None, None))
        self.assertIn("следующая — сб 31.10", R.weeks_line(r))

    def test_a_gap_resets_the_streak_going_backwards(self):
        # 11-14 and 11-07 fine, 10-31 missing a card: streak counts only back to the gap
        bad = {"card_exists": lambda s: (s != SAT, "нет карточки")}
        r = R.weeks_streak(at(2026, 11, 15), Fake(**bad))
        self.assertEqual((r["n"], r["last"]), (2, dt.date(2026, 11, 14)))

    def test_weeks_before_the_first_possible_saturday_do_not_exist(self):
        r = R.weeks_streak(at(2026, 10, 30), Fake())
        self.assertEqual(r["n"], 0)

    def test_sources_coverage_threshold_is_95_and_unparsable_card_is_unknown(self):
        d = self.tmp()
        os.makedirs("Reports/floor1")
        src = R.Sources(d)
        for b, want in (("95.0", True), ("94.9", False)):
            put("Reports/floor1/FLOOR1_2026-10-31.md", card(b), "w")
            self.assertEqual(src.card_b(SAT)[0], want, b)
        put("Reports/floor1/FLOOR1_2026-10-31.md", "пусто", "w")
        self.assertIsNone(src.card_b(SAT)[0])

    def test_sources_panel_row_needs_the_exact_week(self):
        d = self.tmp()
        os.makedirs("journal")
        put("journal/PANEL_LOG.csv", HDR + row("2026-10-24"), "w")
        src = R.Sources(d)
        self.assertFalse(src.panel_row(SAT)[0])
        put("journal/PANEL_LOG.csv", row("2026-10-31"), "a")
        self.assertTrue(R.Sources(d).panel_row(SAT)[0])

    def _runs(self, runs):
        s = R.Sources(".")
        s._runs["panel_weekly.yml"] = (runs, None)
        return s

    def test_workflow_dispatch_in_the_window_disqualifies_even_with_a_green_schedule_run(self):
        ok = {"event": "schedule", "conclusion": "success", "createdAt": "2026-10-31T10:51:32Z", "databaseId": 1}
        man = {"event": "workflow_dispatch", "conclusion": "success", "createdAt": "2026-10-31T09:00:00Z", "databaseId": 2}
        self.assertTrue(self._runs([ok]).schedule_publish(SAT)[0])
        self.assertFalse(self._runs([ok, man]).schedule_publish(SAT)[0])
        self.assertFalse(self._runs([dict(ok, event="workflow_dispatch")]).schedule_publish(SAT)[0])
        self.assertFalse(self._runs([dict(ok, conclusion="failure")]).schedule_publish(SAT)[0])

    def test_validator_step_red_wins_over_green_and_missing_is_unknown(self):
        s = R.Sources(".")
        s._runs["daily_report.yml"] = ([{"databaseId": 1, "event": "schedule", "createdAt": "2026-10-31T15:41:00Z"},
                                        {"databaseId": 2, "event": "schedule", "createdAt": "2026-10-31T17:11:00Z"}], None)

        def jobs(states):
            return {"jobs": [{"steps": [{"name": "Валидатор данных на main", "conclusion": c} for c in states]}]}
        for per_run, want in (((["success"], ["skipped"]), True), ((["success"], ["failure"]), False),
                              ((["skipped"], ["skipped"]), None)):
            it = iter(per_run)
            self.patch(R, "_gh_json", lambda *a, it=it: (jobs(next(it)), None))
            s._runs["daily_report.yml"] = s._runs["daily_report.yml"]
            self.assertEqual(s.validator(SAT)[0], want, per_run)


class TestEventsAndVerdict(Base):
    def test_panel_event_numbers_come_from_panel_log_and_card(self):
        d = self.tmp()
        os.makedirs("journal"); os.makedirs("Reports/floor1")
        put("journal/PANEL_LOG.csv", HDR + row("2026-10-31", "MIXED", "0.75"), "w")
        put("Reports/floor1/FLOOR1_2026-10-31.md", card("95.4"), "w")
        t = R.panel_event("2026-10-31")
        self.assertIn("Рынок: смешанный, размер позиций 75% от обычного", t)
        self.assertIn("Покрытие данных (Б) 95.4%", t)
        put("journal/PANEL_LOG.csv", HDR + row("2026-10-31", "RISK_OFF", "0.5"), "w")
        self.assertIn("риск-офф, размер позиций 50%", R.panel_event("2026-10-31"))

    def test_panel_event_unknown_regime_and_missing_files_are_named_refusals(self):
        self.tmp()
        os.makedirs("journal")
        put("journal/PANEL_LOG.csv", HDR + row("2026-10-31", "REGIME_INSUFFICIENT_DATA", "NA"), "w")
        t = R.panel_event("2026-10-31")
        self.assertIn("режим не определён (REGIME_INSUFFICIENT_DATA)", t)
        self.assertNotIn("смешанный", t)
        self.assertIn("Покрытие данных (Б) не определено", t)
        self.assertIn("режим не определён: нет строки", R.panel_event("2030-01-01"))

    def test_audit_event_takes_verdict_from_the_commit_subject_and_line_from_the_file(self):
        self.tmp()
        os.makedirs("journal/audits")
        put("journal/audits/DAILY_AUDIT_2026-10-30.md", "# x\n\n**Итог:** нарушений нет.\n", "w")
        self.assertEqual(R.audit_event("2026-10-30", False), 'Аудит "сказано—сделано": GREEN — нарушений нет.')
        self.assertIn("RED — нарушений нет.", R.audit_event("2026-10-30", True))
        self.assertIn("вердикта не найдена", R.audit_event("2099-01-01", False))

    def test_bridge_title_is_read_from_the_commit_diff_and_pr_work_is_rephrased(self):
        self.tmp()
        self.patch(R, "sh", lambda *c: "+2026-10-31T19:51:36Z | TASK | [CONSILIUM-TASK] Дневной отчёт | body_sha=1\n" if c[1] == "show" else "")
        ev = R.day_events("- bridge: log architect command [TASK] (#143) (64e20f1, claude[bot])\n"
                          "- Fix thing (#150) (abc1234, claude[bot])\n"
                          "- Human edit (#151) (def5678, operator)\n"
                          "- странный коммит")
        lines = ev.splitlines()
        self.assertEqual(lines[0], "- Архитектор поставил задачу боту: Дневной отчёт")
        self.assertEqual(lines[1], "- Слита работа бота: Fix thing")
        self.assertEqual(lines[2], "- Human edit (#151)")
        self.assertEqual(lines[3], "- странный коммит")

    def test_bridge_without_a_log_line_is_a_named_refusal(self):
        self.patch(R, "sh", lambda *a: "")
        self.assertIn("заголовок не определён", R.day_events("- bridge: log architect command [TASK] (#1) (abc, x)"))

    def test_verdict_and_level(self):
        item = ["1. x — КОД, ждёт 0 дн. — u"]
        self.assertEqual(R.day_verdict([], [])[1], L.INFO)
        self.assertEqual(R.day_verdict([], [])[0], "По плану, от тебя ничего не нужно")
        v, lv = R.day_verdict(item, [])
        self.assertEqual((lv, v.startswith("🔴 Нужно твоё действие")), (L.ACTION, True))
        v, lv = R.day_verdict(item, [("Упало 2", "t", "d")])
        self.assertEqual((lv, v.startswith("🟠 Тревога")), (L.ALARM, True))
        self.assertIn("ждут твоего решения PR: 1", v)

    def test_only_real_alarms_and_each_carries_what_threat_action(self):
        self.assertEqual(R.alarms(0, 0, False, None), [])      # known platform limit is subtracted upstream
        a = R.alarms(1, 2, True, "gh отказал")
        self.assertEqual(len(a), 4)
        self.assertTrue(all(len(x) == 3 and all(x) for x in a))

    def test_operator_items_use_block_type_days_and_link(self):
        now = at(2026, 11, 1)
        prs = [{"number": 7, "title": "bot work", "author": {"login": "github-actions[bot]"}, "body": "", "createdAt": "2026-10-30T09:00:00Z", "url": "u7"},
               {"number": 8, "title": "t8", "author": {"login": "claude"}, "createdAt": "2026-10-29T09:00:00Z", "url": "u8",
                "body": "## ДЛЯ ОПЕРАТОРА\n- Меняет письмо.\n- Тип: ЗАКОН (прочитать)\n- Риск"},
               {"number": 9, "title": "t9", "author": {"login": "claude"}, "createdAt": "2026-11-01T01:00:00Z", "url": "u9", "body": "нет блока"}]
        it = R.operator_items(prs, now)
        self.assertEqual(len(it), 2)                         # the github-actions PR is not the operator's
        self.assertEqual(it[0], "1. Меняет письмо. — ЗАКОН, ждёт 3 дн. — u8")
        self.assertIn("2. t9 — тип не указан, ждёт 0 дн. — u9", it[1])

    def test_manual_runs_count_only_non_bot_dispatches_within_7_days(self):
        runs = [{"event": "workflow_dispatch", "createdAt": "2026-10-30T00:00:00Z", "actor": "investzhadrayev-creator"},
                {"event": "workflow_dispatch", "createdAt": "2026-10-30T00:00:00Z", "actor": "github-actions[bot]"},
                {"event": "workflow_dispatch", "createdAt": "2026-10-01T00:00:00Z", "actor": "investzhadrayev-creator"},
                {"event": "schedule", "createdAt": "2026-10-30T00:00:00Z", "actor": "investzhadrayev-creator"}]
        self.patch(R.F, "_runs_api", lambda n: (runs, 4, ""))
        self.assertIn("за 7 дней: 1 (цель 0", REAL_MANUAL(at(2026, 11, 1)))
        self.patch(R.F, "_runs_api", lambda n: (None, None, "UNAVAILABLE"))
        self.assertIn("не определено (UNAVAILABLE)", REAL_MANUAL(at(2026, 11, 1)))


class TestMainEndToEnd(Base):
    def run_main(self, prs, failed=([], 0, "")):
        self.tmp()
        os.makedirs("journal/digests")
        mails, notes = [], []
        self.patch(L, "send_mail", lambda subj, body, *a, **k: mails.append((subj, body)) or True)
        self.patch(L, "notify", lambda text, level=L.INFO: notes.append((text, level)) or True)
        self.patch(autocommit, "publish", lambda *a, **k: True)
        self.patch(R, "sh", lambda *a: "- коммит (abc, bot)\n")
        self.patch(R.F, "failed_runs", lambda limit=20: failed)
        self.patch(G, "watch_section", lambda *a, **k: ("## Пропущенные запуски\nstub\n", 0))
        self.patch(R.OP, "fetch", lambda: (prs, None))
        self.patch(R.OP, "remind", lambda: (False, None))
        self.patch(R, "Sources", lambda: Fake(panel_row=(False, "нет строки")))
        with contextlib.redirect_stdout(io.StringIO()):
            R.main()
        (name,) = os.listdir("journal/digests")
        with open(os.path.join("journal/digests", name), encoding="utf-8") as f:
            return mails, notes, f.read()

    def test_quiet_day_layout_subject_level_and_technical_part_below_the_line(self):
        mails, notes, md = self.run_main([])
        self.assertTrue(md.startswith("# Консилиум — "))
        head, line, tech = md.partition("\n---\n")
        self.assertEqual(line, "\n---\n")
        for sec in ("## Итог дня: По плану, от тебя ничего не нужно", "## Где мы относительно финиша",
                    "## Что нужно от тебя\nНичего.", "## Что произошло за сутки", "## Тревоги\nНет"):
            self.assertIn(sec, head)
        self.assertNotIn("abc", head)                       # no SHA above the line
        self.assertIn("## Технические подробности", tech)
        self.assertIn("## Сделано", tech)
        self.assertIn("## Впереди", tech)
        self.assertTrue(mails[0][0].startswith("Консилиум "))
        self.assertNotIn("[CONSILIUM]", mails[0][0])
        self.assertTrue(mails[0][0].endswith("По плану, от тебя ничего не нужно"))
        (text, level), = notes
        self.assertEqual(level, L.INFO)
        self.assertIn("Авто-недели подряд", text)
        self.assertNotIn("проблем", text)

    def test_operator_pr_makes_the_day_ACTION_and_alarm_makes_it_ALARM(self):
        pr = [{"number": 8, "title": "t8", "author": {"login": "claude"}, "createdAt": "2026-10-29T09:00:00Z",
               "url": "u8", "body": "## ДЛЯ ОПЕРАТОРА\n- Меняет письмо.\n- Тип: КОД"}]
        mails, notes, md = self.run_main(pr)
        self.assertEqual(notes[-1][1], L.ACTION)
        self.assertIn("1. Меняет письмо. — КОД", md)
        self.assertIn("🔴 Нужно твоё действие", mails[0][0])
        mails, notes, md = self.run_main(pr, failed=(None, None, "UNAVAILABLE"))
        self.assertEqual(notes[-1][1], L.ALARM)
        self.assertIn("🟠 Тревога", mails[0][0])

    def test_unavailable_pr_list_is_not_nothing_needed(self):
        mails, notes, md = self.run_main(None)
        self.assertNotIn("Ничего.", md)
        self.assertNotIn("По плану", mails[0][0])
        self.assertEqual(notes[-1][1], L.ALARM)


if __name__ == "__main__":
    unittest.main()
