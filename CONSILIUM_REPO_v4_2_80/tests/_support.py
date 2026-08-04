"""
Shared test support: import modules from ../microservice without needing packaging/installation.

Kept deliberately tiny — the test suite must have ZERO third-party dependencies so it can run
anywhere (laptop, CI, a Claude Code session) in under a second and at no cost. Only `flask` is
needed, and only because app.py imports it at module level; yfinance/curl_cffi are imported
lazily inside enrich_yf's functions, so they are never touched by these tests.
"""
import importlib
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MICROSERVICE_DIR = os.path.join(REPO_ROOT, "microservice")
WORKFLOW_DIR = os.path.join(REPO_ROOT, "workflow")


def load_microservice_module(name):
    """Import a module from microservice/ by name (e.g. 'app', 'edgar_facts')."""
    if MICROSERVICE_DIR not in sys.path:
        sys.path.insert(0, MICROSERVICE_DIR)
    return importlib.import_module(name)


def latest_workflow_path():
    """Return the highest-versioned consilium_spine_vX_Y.json in workflow/.

    Tests should always validate the CURRENT workflow, not a pinned filename, so that bumping
    the version doesn't silently leave the suite validating a stale file.
    """
    files = [f for f in os.listdir(WORKFLOW_DIR)
             if f.startswith("consilium_spine_v") and f.endswith(".json")]
    if not files:
        raise FileNotFoundError("no consilium_spine_v*.json in %s" % WORKFLOW_DIR)

    def version_key(fname):
        stem = fname[len("consilium_spine_v"):-len(".json")]
        try:
            return tuple(int(p) for p in stem.split("_"))
        except ValueError:
            return (0,)

    return os.path.join(WORKFLOW_DIR, max(files, key=version_key))
