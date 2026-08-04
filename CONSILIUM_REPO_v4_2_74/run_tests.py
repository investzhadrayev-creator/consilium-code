#!/usr/bin/env python3
"""
Run the whole Consilium Spine regression suite.

    python3 run_tests.py

Everything here is offline, deterministic and free: no SEC calls, no LLM calls, no n8n
instance, no API keys. The whole suite finishes in well under a second, so there is no excuse
for skipping it before a deploy.

Exit code 0 = safe to deploy. Non-zero = do not deploy.
"""
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(REPO_ROOT, "tests")


def run_python_suite():
    sys.path.insert(0, TESTS_DIR)
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=TESTS_DIR, pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


def run_node_suite():
    """Render Tables / Build Radar are JavaScript inside n8n — Python cannot reach them, but
    Render Tables is the single source of every number in the report, so it must be executed.

    Exit-code contract for every JS check:
        0 = passed   |   1 = real failure   |   2 = COULD NOT RUN (missing tooling, no coverage)

    A 2 is not a pass, and this function no longer lets one masquerade as green. It used to:
    test_undef.js exited 0 when eslint was absent, so every fresh container — which is every
    chat session — certified "ALL GREEN, safe to deploy" having resolved zero identifiers. The
    node-missing branch had the same shape: a loud warning, then `return True`, and the final
    verdict line cheerfully contradicted the warning three lines later.

    An unrun gate is an unknown, and unknown is not zero. Skips are returned and they block the
    green verdict.

    Returns (ok, skipped) — skipped non-empty means this run cannot certify anything.
    """
    js_files = [os.path.join(TESTS_DIR, "test_syntax.js"),
                os.path.join(TESTS_DIR, "test_undef.js"),
                os.path.join(TESTS_DIR, "test_render_tables.js"),
                os.path.join(TESTS_DIR, "test_number_audit.js"),
                os.path.join(TESTS_DIR, "test_cost_section.js"),
                os.path.join(TESTS_DIR, "test_parse_di.js"),
                os.path.join(TESTS_DIR, "test_verify_entity.js"),
                os.path.join(TESTS_DIR, "test_brief_render.js"),
                os.path.join(TESTS_DIR, "test_fp_merge.js"),
                os.path.join(TESTS_DIR, "test_lite_assemble.js"),
                os.path.join(TESTS_DIR, "test_parse_verdict.js"),
                os.path.join(TESTS_DIR, "test_e2e_result_vs_tables.js")]
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("\n!! node not found — the JS gates did NOT run.")
        print("   They cover Render Tables, the single source of every number in the report.")
        print("   Install Node.js and re-run: this run cannot certify a deploy.")
        return False, [os.path.basename(f) for f in js_files]

    print("\n" + "=" * 70)
    failed, skipped = [], []
    for js in js_files:
        proc = subprocess.run(["node", js], cwd=REPO_ROOT)
        if proc.returncode == 2:
            skipped.append(os.path.basename(js))
        elif proc.returncode != 0:
            failed.append(os.path.basename(js))
    return (not failed and not skipped), skipped


if __name__ == "__main__":
    ok_py = run_python_suite()
    ok_js, skipped = run_node_suite()
    print("\n" + "=" * 70)
    # Order matters: a gate that did not run is reported BEFORE any green claim, and outranks
    # one. "Passed" and "was never asked" must never print the same word.
    if skipped:
        print("NOT VERIFIED — these gates could not run: " + ", ".join(skipped))
        print("A check that did not run has not passed. Do not deploy on this result.")
        sys.exit(1)
    if ok_py and ok_js:
        print("ALL GREEN — safe to deploy")
        sys.exit(0)
    print("FAILURES PRESENT — do not deploy")
    sys.exit(1)
