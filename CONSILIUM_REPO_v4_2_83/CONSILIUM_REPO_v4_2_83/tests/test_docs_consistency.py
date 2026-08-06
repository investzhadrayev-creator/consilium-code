"""
v1.4.1 (2026-07-18): the architect chat caught two drift defects ON ARRIVAL of the handoff
package — the exact docs<->reality class from the original audit (defect #3), reproduced by
the author of that audit: (1) starter kits pinned 'v1.2' while the TZ was v1.4; (2) chat
numbering contradicted between ARCHITECTURE/BACKLOG and the kit filenames. Cure, per house
pattern: pin the class with a test. Canon: chats are NAMES (АРХИТЕКТОР/БАЗА/КОНСИЛИУМ/
WATCHLIST), never numbers; kits never hardcode a TZ version.
"""
import glob
import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _docs():
    return glob.glob(os.path.join(ROOT, "docs", "*.md")) + \
           glob.glob(os.path.join(ROOT, "handoff", "*.md"))


class TestDocsConsistency(unittest.TestCase):

    def test_no_numbered_chat_references(self):
        offenders = {}
        for p in _docs():
            hits = re.findall(r"[Чч][Аа][Тт]\s*[0-9]", open(p, encoding="utf-8").read())
            if hits:
                offenders[os.path.basename(p)] = hits[:3]
        self.assertEqual(offenders, {},
                         "numbered chat references are back (canon is NAMES): %s" % offenders)

    def test_kits_do_not_pin_a_tz_version(self):
        offenders = []
        for p in glob.glob(os.path.join(ROOT, "handoff", "*.md")):
            if re.search(r"ARCHITECTURE_BASE_RU\.md\s+v1\.\d", open(p, encoding="utf-8").read()):
                offenders.append(os.path.basename(p))
        self.assertEqual(offenders, [],
                         "starter kits hardcode a TZ version again (they must point to the "
                         "doc header): %s" % offenders)

    def test_handoff_kit_is_the_CURRENT_seed_not_the_old_starters(self):
        """v4.2.54. The starter kits (CHAT_*_START.md) froze at v4.2.15 and, when shipped beside a
        current seed, told the receiving chat to burn an NFLX pair on a question already closed —
        a document named START outranked the one that was true. They are no longer part of a
        transfer package; what must be present is the CURRENT seed."""
        names = set(os.listdir(os.path.join(ROOT, "handoff")))
        self.assertIn("CHAT_CONSILIUM_SEED_v2.md", names,
                      "the current seed must be present in handoff/")
        stale = [n for n in names if n.endswith("_START.md")]
        for s in stale:
            head = open(os.path.join(ROOT, "handoff", s), encoding="utf-8").read(200)
            self.assertIn("SUPERSEDED", head,
                          "a starter kit ships unmarked beside the seed: %s" % s)
        numbered = [n for n in names if re.match(r"CHAT_[0-9]", n)]
        self.assertEqual(numbered, [], "numbered kit filenames are back: %s" % numbered)


if __name__ == "__main__":
    unittest.main()
