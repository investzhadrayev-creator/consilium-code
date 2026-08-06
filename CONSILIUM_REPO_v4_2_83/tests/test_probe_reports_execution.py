"""v4.2.83 (mandate 10 §3) — pins for `tools/mutation_probe.py`.

The probe certifies every other pin in this repository and, until today, had none of its own. What
that cost is on the record: 56 of its 103 cases carried a `.js` selector; every selector was handed
to `python -m unittest`; unittest cannot import a `.js` file; the import error produced a non-zero
exit code; and this tool spelled non-zero as RED. Fifty-six cases announced "this pin can fail"
without ever reaching the pin.

Among them was `d9-01` — "one multiplier format in prose and tables" — whose whole job was to stop
`28` being printed where 27.53 was computed. The defect walked past its own guard because the guard
was never started, and the operator found it with a calculator on a paid document.

The architect's rule, now in the registry: a measurement made with an instrument that has not
itself been checked is a claim about the instrument, not about the world.

These tests therefore do not check that the probe is clever. They check that it can tell "I ran the
checks and they held" from "I never got as far as the checks" — and that it never reports the
second as the first, or as a defect caught.

NOTE ON FILE NAME. An earlier file pinning this same tool was removed by mandate 10 §1 because its
provenance could not be established. This one is written from scratch, and it is deliberately NOT
given that name: reusing it would make the two indistinguishable in any later reading of the
repository, which is the same defect the mailbox naming rule exists to prevent.
"""
import importlib.util
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(REPO, "tools", "mutation_probe.py")


def _load():
    spec = importlib.util.spec_from_file_location("mutation_probe_under_test", PROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# A mutation that changes nothing. Every case below drives the probe with it, so the only variable
# is the SELECTOR — which is exactly the axis that was broken. A no-op mutation must never produce
# RED: with the code untouched, a red pin would be reporting a defect that does not exist.
NOOP = ("pin", "microservice/ivc_lib.py", "    if _debt_uncertain:", "    if _debt_uncertain:")


class TestTheProbeProvesExecution(unittest.TestCase):

    def setUp(self):
        self.mp = _load()

    def _run(self, selector):
        return self.mp.run_case(NOOP + (selector, "probe self-check"))[2]

    # ---- property 1: a selector that cannot exist is NOT_EXEC, never RED -------------------
    def test_a_nonexistent_python_class_is_NOT_EXEC(self):
        """THE CASE OF RECORD, in its python form. Reporting this as RED is not a harmless
        mislabel: red-for-the-wrong-reason looks *safer* than green, so it survives review longer
        than a false pass would. That is why 56 cases lived for months."""
        self.assertEqual(self._run("test_harness.NoSuchClassAnywhere.test_nothing"), "NOT_EXEC")

    def test_a_nonexistent_python_module_is_NOT_EXEC(self):
        self.assertEqual(self._run("test_no_such_module_at_all.TestX.test_y"), "NOT_EXEC")

    def test_a_nonexistent_js_file_is_NOT_EXEC(self):
        """The exact shape of the original defect: `.js` selectors could not run at all, and every
        one of them was counted as a pin that fires."""
        self.assertEqual(self._run("test_no_such_file_at_all.js"), "NOT_EXEC")

    # ---- property 2: zero executed checks is NOT_EXEC, whatever the exit code says ----------
    def test_the_verdict_is_read_from_a_TALLY_not_from_an_exit_code(self):
        """An exit code is a claim about the process; a tally is a claim about the checks.

        The control that makes this pin mean something: unittest, handed a selector it cannot load,
        SYNTHESISES a `_FailedTest` case and prints `Ran 1 test ... FAILED`. So a naive tally reader
        sees a non-zero count AND a non-zero exit code, and both agree on the wrong answer. Anything
        that merely counts is not enough; the loader's own failure must be recognised as a failure
        to run rather than as a run that failed.
        """
        import subprocess
        import sys
        p = subprocess.run([sys.executable, "-m", "unittest",
                            "test_harness.NoSuchClassAnywhere.test_nothing"],
                           cwd=os.path.join(REPO, "tests"), capture_output=True, text=True)
        out = p.stdout + p.stderr
        self.assertIn("Ran 1 test", out,
                      "the control has stopped being a control: unittest no longer fabricates a "
                      "tally for an unloadable selector, and this pin now proves nothing")
        self.assertNotEqual(p.returncode, 0)
        # ...and the probe must still refuse to call that a probed pin.
        self.assertEqual(self._run("test_harness.NoSuchClassAnywhere.test_nothing"), "NOT_EXEC")

    # ---- property 3: a .js case is executed by the node runner -----------------------------
    def test_a_js_selector_actually_runs_and_reports_its_count(self):
        """Not "does not crash" — RUNS. The count comes back from the file's own tally line, so a
        non-zero count is evidence the checks were reached rather than evidence node started."""
        cid, guards, res, note = self.mp.run_case(NOOP + ("test_brief_render.js", "probe"))
        self.assertEqual(res, "GREEN",
                         "a no-op mutation reported %s: the probe is calling something a defect "
                         "that it has not proved" % res)
        self.assertRegex(note, r"^\d+ checks ran$")
        self.assertGreater(int(note.split()[0]), 1,
                           "one check is not a suite: the js runner did not reach its pins")

    def test_a_real_python_selector_runs_and_reports_its_count(self):
        cid, guards, res, note = self.mp.run_case(
            NOOP + ("test_harness.TestDebtZeroIsUnknownORCLCase", "probe"))
        self.assertEqual(res, "GREEN")
        self.assertRegex(note, r"^\d+ checks ran$")

    # ---- property 4: an anchor that does not match is SKIP, and SKIP is not RED -------------
    def test_an_unmatched_anchor_is_SKIP_and_says_how_many_times_it_matched(self):
        """`SKIP` here means the mutation never applied, so the pin was never put under stress.
        Rule 9: that is a refusal of the check, not a neutral outcome — and it must not be able to
        hide inside the RED count, which is the only number a reader looks at."""
        cid, guards, res, note = self.mp.run_case(
            ("pin", "microservice/ivc_lib.py", "zzz_this_fragment_cannot_exist_zzz", "x",
             "test_harness.TestDebtZeroIsUnknownORCLCase", "probe"))
        self.assertEqual(res, "SKIP")
        self.assertIn("0 times", note, "a SKIP must say WHY the anchor failed, not merely skip")

    def test_an_ambiguous_anchor_is_also_SKIP(self):
        """The other half: a fragment matching twice would mutate two places at once, so what the
        pin reacted to could not be attributed. Ambiguity is a refusal too."""
        cid, guards, res, note = self.mp.run_case(
            ("pin", "microservice/ivc_lib.py", "return", "return",
             "test_harness.TestDebtZeroIsUnknownORCLCase", "probe"))
        self.assertEqual(res, "SKIP")

    # ---- property 5: the summary line is produced by the tool and carries all five counters --
    def test_the_summary_line_is_printed_by_the_tool_with_all_five_counters(self):
        """Hand-counting this catalogue once produced 54 where the file held 41, which is why the
        tool prints its own size. The counters must ADD UP to the case count, or a state can go
        missing from the summary while still occurring — the way SKIP once printed the all-clear.
        """
        import io
        import re
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.mp.main(["debt-09"])
        line = [l for l in buf.getvalue().split("\n") if l.startswith("catalogue:")]
        self.assertTrue(line, "the tool printed no summary line at all")
        nums = [int(x) for x in re.findall(r"\d+", line[0])]
        self.assertEqual(len(nums), 5,
                         "the summary must carry cases, RED, SKIP, GREEN and NOT_EXEC: %r" % line[0])
        total, red, skip, green, notexec = nums
        self.assertEqual(total, red + skip + green + notexec,
                         "the counters do not add up to the case count — a state is unaccounted "
                         "for in the summary: %r" % line[0])

    def test_a_dirty_catalogue_cannot_exit_zero(self):
        """The contract the builder depends on. `build_handoff.py` refuses to package a tree whose
        catalogue is not clean, and it learns that from this exit code alone."""
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.mp.main(["no_such_case_id_exists"])
        self.assertNotEqual(rc, 0,
                            "a run that probed nothing at all returned success")


if __name__ == "__main__":
    unittest.main(verbosity=2)
