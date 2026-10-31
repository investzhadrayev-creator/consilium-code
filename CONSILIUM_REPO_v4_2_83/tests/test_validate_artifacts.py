"""Consumer-tests for rule 4 of tools/validate_artifacts.py (issue #146).

A github-actions commit touching DECISION_/PREREG_/MANDATE_ is legal ONLY as the squash-merge of a PR whose
merged_by is the repository owner. Every test drives main() against a real temporary git repository; only
`gh api` is replaced by a fake world. Unanswered API == violation «не проверено», never silent permission.
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "tools"))
import validate_artifacts as V  # noqa: E402

OWNER = "investzhadrayev-creator"
SLUG = "investzhadrayev-creator/consilium-code"


def git(*a, **env):
    e = dict(os.environ, GIT_AUTHOR_NAME="x", GIT_AUTHOR_EMAIL="x@example.com",
             GIT_COMMITTER_NAME="x", GIT_COMMITTER_EMAIL="x@example.com", **env)
    return subprocess.run(("git",) + a, capture_output=True, text=True, check=True, env=e).stdout.strip()


class Api:
    """Fake `gh api`: {sha: (merge_commit_sha-of-PR, number)} and {number: merged_by login|None}."""
    def __init__(self):
        self.pulls = {}      # sha -> list of PR dicts for commits/{sha}/pulls
        self.full = {}       # number -> PR dict for pulls/{n}
        self.down = False
        self.calls = []

    def __call__(self, path):
        self.calls.append(path)
        if self.down:
            return None, "HTTP 502"
        parts = path.split("/")
        if parts[3] == "commits":
            return self.pulls.get(parts[4], []), None
        return self.full.get(int(parts[4])), None

    def merged(self, sha, number, by, merge_sha=None):
        self.pulls[sha] = [{"number": number, "merge_commit_sha": merge_sha or sha}]
        self.full[number] = {"number": number, "merged_at": "2026-10-28T10:00:00Z",
                             "merged_by": {"login": by} if by else None}


class TestOperatorMergeRule(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, self.old)
        git("init", "-q", "-b", "main")
        os.makedirs("mailbox")
        open("README", "w").write("x")
        git("add", "-A")
        git("commit", "-q", "-m", "root")
        self.base = git("rev-parse", "HEAD")
        self.api = Api()
        for name, val in (("gh_api", self.api), ("repo_slug", lambda: SLUG)):
            old = getattr(V, name)
            setattr(V, name, val)
            self.addCleanup(setattr, V, name, old)
        V.fails.clear()
        self.addCleanup(V.fails.clear)

    def bot_commit(self, path, body="решение\n"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").write(body)
        git("add", "-A")
        git("commit", "-q", "-m", "squash", "--author", "github-actions[bot] <actions@github.com>")
        return git("rev-parse", "HEAD")

    def run_validator(self):
        out = io.StringIO()
        old = os.environ.get("BASE")
        os.environ["BASE"] = self.base
        try:
            with contextlib.redirect_stdout(out):
                try:
                    V.main()
                    rc = 0
                except SystemExit as e:
                    rc = e.code
        finally:
            if old is None:
                os.environ.pop("BASE", None)
            else:
                os.environ["BASE"] = old
        return rc, out.getvalue()

    def test_decision_squash_merged_by_the_owner_is_clean(self):
        sha = self.bot_commit("mailbox/DECISION_2026-10-28_X.md")
        self.api.merged(sha, 7, OWNER)
        rc, out = self.run_validator()
        self.assertEqual((rc, V.fails), (0, []), out)

    def test_prereg_and_mandate_follow_the_same_rule(self):
        for n, name in enumerate(("PREREG_a.md", "MANDATE_b.md")):
            sha = self.bot_commit("mailbox/" + name)
            self.api.merged(sha, 10 + n, "someone-else")
        rc, out = self.run_validator()
        self.assertEqual(rc, 1)
        self.assertEqual(len(V.fails), 2, out)

    def test_merged_by_the_actions_token_is_a_violation(self):
        sha = self.bot_commit("mailbox/DECISION_2026-10-28_X.md")
        self.api.merged(sha, 7, "github-actions[bot]")
        rc, out = self.run_validator()
        self.assertEqual(rc, 1)
        self.assertIn("BOT PATH VIOLATION", out)
        self.assertIn("слит не владельцем", out)

    def test_merged_by_somebody_else_is_a_violation(self):
        sha = self.bot_commit("mailbox/DECISION_2026-10-28_X.md")
        self.api.merged(sha, 7, "claude[bot]")
        self.assertEqual(self.run_validator()[0], 1)

    def test_unknown_merger_is_a_violation_not_a_default(self):
        sha = self.bot_commit("mailbox/DECISION_2026-10-28_X.md")
        self.api.merged(sha, 7, None)
        self.assertEqual(self.run_validator()[0], 1)

    def test_api_down_is_a_named_violation_not_a_silent_pass(self):
        self.bot_commit("mailbox/DECISION_2026-10-28_X.md")
        self.api.down = True
        rc, out = self.run_validator()
        self.assertEqual(rc, 1)
        self.assertIn("не проверено: API недоступен", out)

    def test_unknown_repo_is_the_same_named_refusal(self):
        self.bot_commit("mailbox/DECISION_2026-10-28_X.md")
        V.repo_slug = lambda: ""
        rc, out = self.run_validator()
        self.assertEqual(rc, 1)
        self.assertIn("не проверено: API недоступен", out)

    def test_a_pr_that_merely_contained_the_commit_is_not_its_merge(self):
        sha = self.bot_commit("mailbox/DECISION_2026-10-28_X.md")
        self.api.merged(sha, 7, OWNER, merge_sha="f" * 40)      # owner merged a DIFFERENT commit of that PR
        rc, out = self.run_validator()
        self.assertEqual(rc, 1)
        self.assertIn("нет PR, слитого этим коммитом", out)

    def test_an_unmerged_pr_does_not_count(self):
        sha = self.bot_commit("mailbox/DECISION_2026-10-28_X.md")
        self.api.merged(sha, 7, OWNER)
        self.api.full[7]["merged_at"] = None
        self.assertEqual(self.run_validator()[0], 1)

    def test_forbidden_path_outside_allowed_dirs_is_never_excused_by_the_owner(self):
        sha = self.bot_commit("tools/evil.py")
        self.api.merged(sha, 7, OWNER)
        rc, out = self.run_validator()
        self.assertEqual(rc, 1)
        self.assertIn("tools/evil.py", out)

    def test_ordinary_bot_commit_needs_no_api_at_all(self):
        self.bot_commit("journal/digests/DAILY_2026-10-31.md")
        self.api.down = True
        rc, out = self.run_validator()
        self.assertEqual((rc, self.api.calls), (0, []), out)

    def test_human_commit_of_a_decision_is_not_this_rules_business(self):
        os.makedirs("mailbox", exist_ok=True)
        open("mailbox/DECISION_h.md", "w").write("x")
        git("add", "-A")
        git("commit", "-q", "-m", "human")
        self.api.down = True
        self.assertEqual(self.run_validator()[0], 0)


if __name__ == "__main__":
    unittest.main()
