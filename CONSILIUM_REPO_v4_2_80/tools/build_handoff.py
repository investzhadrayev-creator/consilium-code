#!/usr/bin/env python3
"""Builds the transfer package and GENERATES every counter, version and range from the tree.

Written after the new chat audited the previous handoff and found four stale metadata claims in a
seed that had been edited by hand: the archive name (v4_2_51 vs the delivered v4_2_53), the HANDOFF
line count (3724 vs 3899), the section range (header said A→MMM while §6 of the SAME file said
A→OOO), and a filename dated five days before its newest content. Same class the project already
closed inside the code — a fact living in two places, one of them updated — but the CONTEXT
TRANSFER layer had never been put under that protection, though it is as much a failure surface as
the code and as the contract with the model.

So: nothing here is typed by hand. Run it, ship what it prints.

    python tools/build_handoff.py            # rebuild archive + refresh seed metadata
"""
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = "/mnt/user-data/outputs"


def facts():
    """Every number the seed quotes, read from the tree — never remembered."""
    f = {}
    wf = sorted(x for x in os.listdir(os.path.join(REPO, "workflow"))
                if x.startswith("consilium_spine_"))
    f["workflow_file"] = wf[-1] if wf else None
    if f["workflow_file"]:
        with open(os.path.join(REPO, "workflow", f["workflow_file"]), encoding="utf-8") as fh:
            f["workflow_name"] = json.load(fh).get("name")
    # microservice build: one marker, identical in every file — mismatch is itself a defect
    builds = set()
    msdir = os.path.join(REPO, "microservice")
    for x in sorted(os.listdir(msdir)):
        if not x.endswith(".py"):
            continue
        with open(os.path.join(msdir, x), encoding="utf-8") as fh:
            m = re.search(r'__build__ = "([^"]+)"', fh.read())
        builds.add(m.group(1) if m else "MISSING:" + x)
    f["build"] = sorted(builds)
    f["build_consistent"] = len(builds) == 1 and not any(b.startswith("MISSING") for b in builds)
    # handoff: line count and the ACTUAL last section letter
    hp = os.path.join(REPO, "docs", "HANDOFF_ARCHITECT_2026-07-19_RU.md")
    with open(hp, encoding="utf-8") as fh:
        h = fh.read()
    f["handoff_lines"] = len(h.split("\n"))
    # sections are NOT in file order: naming went A..Z, then AA..ZZ, then AAA.. — and later
    # sections were inserted above older ones. "Last by position" would report T while the newest
    # material sits in OOO. Newest = longest letter run, then alphabetical.
    secs = re.findall(r"^## ([A-Z]+)\.", h, re.M)
    f["handoff_sections"] = len(secs)
    f["handoff_newest"] = max(secs, key=lambda s: (len(s), s)) if secs else "?"
    f["handoff_range"] = "A→%s" % f["handoff_newest"]
    # test count, straight from the runner
    p = subprocess.run([sys.executable, "run_tests.py"], cwd=REPO,
                       capture_output=True, text=True, timeout=600)
    m = re.search(r"Ran (\d+) tests", p.stdout + p.stderr)
    f["tests"] = int(m.group(1)) if m else None
    f["tests_green"] = p.returncode == 0 and "ALL GREEN" in (p.stdout + p.stderr)
    return f


def main():
    f = facts()
    print("=== FACTS READ FROM THE TREE ===")
    for k, v in f.items():
        print("  %-22s %s" % (k, v))
    if not f["build_consistent"]:
        print("\n!! microservice build markers disagree — fix before shipping:", f["build"])
        return 1
    if not f["tests_green"]:
        print("\n!! suite is not green — the package must not claim it is")
        return 1
    # archive: root is the repo itself, NOT a wrapper folder (a wrapper made the seed's unpack
    # instruction produce repo/repo_out/... and broke the one test with an absolute path)
    name = "CONSILIUM_REPO_%s.zip" % f["build"][0].replace(".", "_")
    dst = os.path.join(OUT, name)
    if os.path.exists(dst):
        os.remove(dst)
    # WHITELIST, not "everything minus junk". The previous package shipped 20+ documents, nine of
    # them 30-50 versions stale and unmarked (START_HERE.md sat at v4.2.15 while the code was at
    # v4.2.53) — and the receiving chat spent its opening cycles auditing the package instead of
    # working. Ship only what a fresh chat must read or run; history stays behind and is sent on
    # request. Less, but every file verified.
    SHIP = ["microservice", "tests", "tools", "workflow",
            "run_tests.py", "package.json", "package-lock.json",
            "CLAUDE.md",
            "docs/HANDOFF_ARCHITECT_2026-07-19_RU.md",
            "docs/SYSTEM_PARAMETERS_RU.md",
            "handoff/CHAT_CONSILIUM_SEED_v2.md"]
    missing = [p for p in SHIP if not os.path.exists(os.path.join(REPO, p))]
    if missing:
        print("\n!! whitelisted paths absent:", missing)
        return 1
    subprocess.run(["zip", "-qr", dst] + SHIP + ["-x", "*.pyc", "-x", "*/__pycache__/*",
                    "-x", "node_modules/*"], cwd=REPO, check=True)
    print("\narchive: %s" % name)
    print("SEED METADATA — paste verbatim, do not retype:")
    print("  архив: %s" % name)
    print("  воркфлоу: %s" % f["workflow_name"])
    print("  микросервис (единая версия сборки): %s" % f["build"][0])
    print("  сьют: %d тестов, ALL GREEN" % f["tests"])
    print("  HANDOFF: %d строк, секции %s" % (f["handoff_lines"], f["handoff_range"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
