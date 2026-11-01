"""Consumer-tests: auditor unavailable => the operator hears about it (issue #151).

Gemini 402 ("prepayment credits are depleted") silently produced REVIEW_UNAVAILABLE files for a week.
Every test drives the CONSUMER (daily_audit.main() / monthly_audit.main()) down to the notify() call;
the LLM, git and Telegram are in-process fakes.
"""
import contextlib
import io
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools")
sys.path.insert(0, TOOLS)

import autocommit        # noqa: E402
import daily_audit as D  # noqa: E402
import llm_clients as L  # noqa: E402
import monthly_audit as M  # noqa: E402
import schedule_guard as G  # noqa: E402

G.sh = lambda *cmd: (1, "", "test: git/gh unavailable by design")

E402 = ('HTTP 402: {\n  "error": {\n    "code": 402,\n    "message": "Your prepayment credits are depleted. '
        'Please go to AI Studio at https://ai.studio/projects to manage your project and billing."\n  }\n}')


class Base(unittest.TestCase):
    def patch(self, obj, name, value):
        old = getattr(obj, name)
        setattr(obj, name, value)
        self.addCleanup(setattr, obj, name, old)

    def setUp(self):
        old = os.getcwd()
        os.chdir(tempfile.mkdtemp())
        self.addCleanup(os.chdir, old)
        os.makedirs("journal/audits")
        self.sent = []
        self.patch(L, "notify", lambda text, level=L.INFO: self.sent.append((level, text)) or True)
        self.patch(L, "send_mail", lambda *a, **k: True)
        self.patch(autocommit, "publish", lambda *a, **k: True)
        self.patch(G, "skip_if_published", lambda name: False)
        self.patch(D, "gather", lambda end=None: {"commits": "c1", "cmds": "x", "prev": ""})
        self.patch(D, "build_packet", lambda day, g: "packet")
        self.patch(M.F, "sh", lambda *a: (1, "", "stub"))

    def unavailable(self, msg):
        def boom(*a, **k):
            raise L.Unavailable(msg)
        self.patch(L, "call", boom)

    def run_daily(self, provider="gemini"):
        class _D:  # day parity picks the provider
            day = 31 if provider == "gemini" else 30
        import datetime as dt
        real = dt.date
        day = dt.date(2026, 10, _D.day)
        class FakeDate(real):
            @classmethod
            def today(cls):
                return day
        self.patch(D.dt, "date", FakeDate)
        with contextlib.redirect_stdout(io.StringIO()):
            D.main()


class TestDailyAuditUnavailable(Base):
    def test_402_is_action_with_top_up_instructions(self):
        self.unavailable(E402)
        self.run_daily("gemini")
        self.assertEqual(len(self.sent), 1, self.sent)
        level, text = self.sent[0]
        self.assertEqual(level, L.ACTION)
        self.assertIn("закончились оплаченные кредиты", text)
        self.assertIn("пополнить баланс", text)
        self.assertIn("Google AI Studio", text)

    def test_401_is_action_about_the_key(self):
        self.unavailable('HTTP 401: {"error": "API key not valid"}')
        self.run_daily("gemini")
        level, text = self.sent[0]
        self.assertEqual(level, L.ACTION)
        self.assertIn("ключ API отклонён", text)
        self.assertIn("GEMINI_API_KEY", text)
        self.assertNotIn("кредит", text)

    def test_timeout_is_alarm_with_first_error_line(self):
        self.unavailable("TimeoutError('timed out')\nsecond line")
        self.run_daily("gemini")
        level, text = self.sent[0]
        self.assertEqual(level, L.ALARM)
        self.assertIn("TimeoutError('timed out')", text)
        self.assertNotIn("second line", text)

    def test_secret_in_error_body_never_reaches_the_message(self):
        os.environ["GEMINI_API_KEY"] = "SECRETKEY123456"
        self.addCleanup(os.environ.pop, "GEMINI_API_KEY", None)
        self.unavailable("HTTP 500: https://x/v1?key=SECRETKEY123456&alt=sse boom")
        self.run_daily("gemini")
        for _, text in self.sent:
            self.assertNotIn("SECRETKEY123456", text)

    def test_key_in_url_is_scrubbed_even_when_not_in_env(self):
        self.unavailable("HTTP 500: https://x/v1?key=AIzaUNKNOWNKEY999&alt=sse boom")
        self.run_daily("gemini")
        for _, text in self.sent:
            self.assertNotIn("AIzaUNKNOWNKEY999", text)

    def test_second_slot_of_the_same_day_does_not_duplicate(self):
        self.unavailable(E402)
        self.run_daily("gemini")
        self.assertEqual(len(self.sent), 1)
        self.run_daily("gemini")   # file of the day already records REVIEW_UNAVAILABLE
        self.assertEqual(len(self.sent), 1, self.sent)


class TestMonthlyAuditUnavailable(Base):
    def test_each_unavailable_provider_is_reported(self):
        def call(provider, *a, **k):
            if provider == "openai":
                raise L.Unavailable("HTTP 401: bad key")
            raise L.Unavailable(E402)
        self.patch(L, "call", call)
        with contextlib.redirect_stdout(io.StringIO()):
            M.main()
        self.assertEqual(len(self.sent), 2, self.sent)
        by_text = " | ".join(t for _, t in self.sent)
        self.assertIn("OpenAI", by_text)
        self.assertIn("Gemini", by_text)
        self.assertEqual({lv for lv, _ in self.sent}, {L.ACTION})


if __name__ == "__main__":
    unittest.main()
