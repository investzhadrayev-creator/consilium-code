"""Issue #392: счётчик досье дневного отчёта. Пинуется свойство: готово = пара machine+brief без _draft
(последняя версия), черновик и неполная пара не считаются, исторический as_of допустим."""
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools")
sys.path.insert(0, TOOLS)
import daily_report as R  # noqa: E402


def make(files):
    root = tempfile.mkdtemp()
    d = os.path.join(root, "Reports", "dossiers")
    os.makedirs(d)
    for f in files:
        open(os.path.join(d, f), "w").close()
    return root


class TestDossierCount(unittest.TestCase):
    def test_draft_does_not_count(self):
        r = make(["RDDT_2026-11-02_machine_draft.md", "RDDT_2026-11-02_brief_draft.md"])
        self.assertEqual(R.dossier_status("RDDT", r), "draft")
        line = R.dossier_line(r)
        self.assertIn("0 из 3", line)
        self.assertIn("черновик: RDDT", line)

    def test_v2_counts(self):
        r = make(["UBER_2026-11-02_machine.md", "UBER_2026-11-02_brief.md",
                  "UBER_2026-11-03_machine_v2.md", "UBER_2026-11-03_brief_v2.md"])
        self.assertEqual(R.dossier_status("UBER", r), "ready")
        self.assertIn("готовы: UBER", R.dossier_line(r))

    def test_nflx_historical_asof_counts(self):
        r = make(["NFLX_2020-02-15_machine.md", "NFLX_2020-02-15_brief.md"])
        line = R.dossier_line(r)
        self.assertIn("1 из 3", line)
        self.assertIn("готовы: NFLX-FY2019", line)
        self.assertIn("нет: UBER, RDDT", line)

    def test_half_pair_is_not_ready(self):
        r = make(["UBER_2026-11-02_machine.md"])
        self.assertNotEqual(R.dossier_status("UBER", r), "ready")

    def test_final_beats_draft_of_same_dossier(self):
        r = make(["RDDT_2026-11-02_machine.md", "RDDT_2026-11-02_brief.md",
                  "RDDT_2026-11-02_machine_draft.md", "RDDT_2026-11-02_brief_draft.md"])
        self.assertEqual(R.dossier_status("RDDT", r), "ready")


if __name__ == "__main__":
    unittest.main()
