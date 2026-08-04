"""
Structural tests for workflow/consilium_lite_v1_0.json — Consilium Lite v1.0.

Lite is the DEFAULT instrument (operator decision 2026-07-18, option C from the cost audit).
Its safety story is different from the spine's: no gate, no auditor, no arbiter — so the pins
here guard the two things Lite cannot afford to lose: (1) the deterministic core is wired
EXACTLY like the spine's (same node code, same names, so the same suite covers it), and
(2) nothing judicial is silently half-wired — a gate that LOOKS present but never runs is
worse than an honestly absent one.
"""
import json
import os
import re
import unittest

import glob as _glob
_lite_files = sorted(_glob.glob(os.path.join(os.path.dirname(__file__), "..", "workflow",
                                             "consilium_lite_v*.json")))
LITE_PATH = _lite_files[-1]
with open(LITE_PATH, encoding="utf-8") as f:
    WF = json.load(f)
NODES = {n["name"]: n for n in WF["nodes"]}
CONNECTIONS = WF["connections"]


def targets_of(name):
    return [l["node"] for g in CONNECTIONS.get(name, {}).get("main", []) for l in g]


class TestLiteChain(unittest.TestCase):

    CHAIN = [
        ("Telegram Trigger", "Gather Data"), ("Gather Data", "Growth Enrich"),
        ("Growth Enrich", "Form4 Insider"), ("Form4 Insider", "Eligibility"),
        ("Eligibility", "Prompts Lite"), ("Prompts Lite", "Stage 1 Perplexity"),
        ("Stage 1 Perplexity", "Route Gate"), ("Route Gate", "Stage 2a Claude"),
        ("Stage 2a Claude", "Extract Python"), ("Extract Python", "Run Code"),
        ("Run Code", "Render Tables"), ("Render Tables", "Stage 2b Lite"),
        ("Stage 2b Lite", "Extract Memo"), ("Extract Memo", "Number Audit"),
        ("Number Audit", "Collect Usage"), ("Collect Usage", "Cost Ledger"),
        ("Cost Ledger", "Assemble Lite"), ("Assemble Lite", "Send Report"),
    ]

    def test_full_chain_wired(self):
        for src, dst in self.CHAIN:
            self.assertIn(dst, targets_of(src), "Lite chain broken at %s -> %s" % (src, dst))

    def test_no_dangling_connections(self):
        names = set(NODES)
        for src, conn in CONNECTIONS.items():
            self.assertIn(src, names, "connection source missing: %s" % src)
            for g in conn.get("main", []):
                for l in g:
                    self.assertIn(l["node"], names, "connection target missing: %s" % l["node"])

    def test_category_f_gets_an_honest_rejection_not_a_dead_end(self):
        outs = CONNECTIONS["Route Gate"]["main"]
        self.assertEqual(len(outs), 2, "Route Gate must keep both branches")
        self.assertIn("Send Not Eligible", [l["node"] for l in outs[1]])
        txt = json.dumps(NODES["Send Not Eligible"]["parameters"], ensure_ascii=False)
        self.assertIn("FULL Consilium Spine", txt,
                      "the rejection must point at the Core-V path, not just refuse")

    def test_postgres_append_wired_from_assemble(self):
        self.assertIn("Cost Ledger → Postgres", targets_of("Assemble Lite"),
                      "Lite runs must land in the same cumulative ledger table")


class TestLiteIsHonestlyLite(unittest.TestCase):
    """Absent means ABSENT: no judicial node may be present-but-unwired (a gate that looks
    installed but never fires is the most dangerous shape of missing)."""

    JUDICIAL = ["Stage 3 Grok", "Extract Grok", "Stage 4 Gemini", "Parse Verdict", "Gate",
                "Stage 5 Auditor", "Extract Audit", "Stage 6 Arbiter", "Extract Arbiter",
                "Parse DI", "Build Radar", "Send Rework"]

    def test_no_judicial_nodes_at_all(self):
        for name in self.JUDICIAL:
            self.assertNotIn(name, NODES, "%s must not exist in Lite, even disconnected" % name)

    def test_lite_mode_disclosed_in_the_report(self):
        code = NODES["Assemble Lite"]["parameters"]["jsCode"]
        self.assertIn("LITE MODE: no gate, no adversarial audit, no arbiter, no DI", code)

    def test_number_audit_banner_is_the_replacement_screen(self):
        code = NODES["Assemble Lite"]["parameters"]["jsCode"]
        self.assertIn("NUMBER AUDIT (deterministic)", code)
        self.assertIn("read BEFORE the memo", code)
        self.assertIn("escalate the ticker to a full consilium run", code)

    def test_glossary_present_in_lite_too(self):
        code = NODES["Assemble Lite"]["parameters"]["jsCode"]
        self.assertIn("## 9. Glossary", code)


class TestLitePayloadDiscipline(unittest.TestCase):

    def test_diet_on_both_llm_ground_truth_bodies(self):
        for name in ["Stage 2a Claude", "Stage 2b Lite"]:
            body = NODES[name]["parameters"]["jsonBody"]
            self.assertIn("stock/spy arrays stripped", body,
                          "%s sends un-dieted GROUND_TRUTH" % name)

    def test_run_code_receives_the_full_object(self):
        body = NODES["Run Code"]["parameters"]["jsonBody"]
        self.assertIn("$('Eligibility').first().json", body)
        self.assertNotIn("_diet", body)

    def test_2b_lite_carries_result_once_and_no_sentiment(self):
        body = NODES["Stage 2b Lite"]["parameters"]["jsonBody"]
        self.assertIn("result_json", body)
        self.assertNotIn("$('Run Code')", body)
        self.assertNotIn("SENTIMENT", body)
        self.assertNotIn("Extract Grok", body)

    def test_prompt_keys_resolve_against_prompts_lite(self):
        code = NODES["Prompts Lite"]["parameters"]["jsCode"]
        m = re.match(r"\s*return \[\{ json: (\{.*\})\s*\}\];\s*$", code, re.S)
        self.assertIsNotNone(m, "Prompts Lite must be a single JSON literal, like the spine")
        keys = set(json.loads(m.group(1)).keys())
        self.assertEqual(keys, {"stage1_lite", "stage2a", "stage2b_lite"})
        for node, key in [("Stage 1 Perplexity", "stage1_lite"),
                          ("Stage 2a Claude", "stage2a"),
                          ("Stage 2b Lite", "stage2b_lite")]:
            self.assertIn("$('Prompts Lite').first().json.%s" % key,
                          NODES[node]["parameters"]["jsonBody"],
                          "%s does not read Prompts Lite.%s" % (node, key))

    def test_stage1_lite_cuts_the_dual_source_items(self):
        p = json.loads(re.match(r"\s*return \[\{ json: (\{.*\})\s*\}\];\s*$",
                                NODES["Prompts Lite"]["parameters"]["jsCode"], re.S).group(1))
        s1 = p["stage1_lite"]
        self.assertIn("DELIBERATELY EXCLUDED", s1)
        for cut in ["insider Form 4", "short interest", "dividends/buyback"]:
            self.assertIn(cut, s1, "the exclusion list lost: %s" % cut)
        self.assertIn("CATALYSTS", s1.upper())

    def test_stage2a_prompt_is_the_spine_one_with_anchoring(self):
        p = json.loads(re.match(r"\s*return \[\{ json: (\{.*\})\s*\}\];\s*$",
                                NODES["Prompts Lite"]["parameters"]["jsCode"], re.S).group(1))
        self.assertIn("ANCHORING (v4.2.11", p["stage2a"],
                      "Lite must not fork the judgment-core prompt; one canonical stage2a")

    def test_2b_lite_demands_catalysts_and_growth_lines(self):
        p = json.loads(re.match(r"\s*return \[\{ json: (\{.*\})\s*\}\];\s*$",
                                NODES["Prompts Lite"]["parameters"]["jsCode"], re.S).group(1))
        s2b = p["stage2b_lite"]
        self.assertIn("THREE GROWTH LINES", s2b)
        self.assertIn("CATALYSTS (next 4 quarters)", s2b)
        self.assertIn("NUMBER_AUDIT", s2b, "the memo must know it is screened deterministically")


class TestLiteMetering(unittest.TestCase):

    def test_collect_usage_lists_exactly_the_llm_nodes_present(self):
        code = NODES["Collect Usage"]["parameters"]["jsCode"]
        for name in ["Stage 1 Perplexity", "Stage 2a Claude", "Stage 2b Lite"]:
            self.assertIn("'%s'" % name, code, "ledger blind to %s" % name)
        for absent in ["Stage 3 Grok", "Stage 4 Gemini", "Stage 5 Auditor", "Stage 6 Arbiter",
                       "Core-V Narrative"]:
            self.assertNotIn("'%s'" % absent, code,
                             "ledger lists a node Lite does not have: %s" % absent)

    def test_send_caption_has_no_di_artifact(self):
        cap = NODES["Send Report"]["parameters"]["additionalFields"]["caption"]
        self.assertNotIn("DI=", cap, "caption would print DI=null in Lite")
        self.assertIn("NUMBER AUDIT", cap, "caption must point the reader at the banner")


class TestLiteLanguage(unittest.TestCase):
    """Report-facing nodes: zero Cyrillic (the spine rule, same reason — NotebookLM pipeline).
    Prompts Lite and Gather Data are the same deliberate exemptions as in the spine."""

    EXEMPT = {"Prompts Lite", "Gather Data", "LITE README", "Send Not Eligible"}

    def test_no_cyrillic_outside_exemptions(self):
        offenders = {}
        for node in WF["nodes"]:
            if node["name"] in self.EXEMPT or node.get("type") == "n8n-nodes-base.stickyNote":
                continue
            blob = json.dumps(node.get("parameters", {}), ensure_ascii=False)
            hits = re.findall(r"[А-Яа-я]{3,}", blob)
            if hits:
                offenders[node["name"]] = hits[:3]
        self.assertEqual(offenders, {}, "Russian leaking into the Lite report: %s" % offenders)


if __name__ == "__main__":
    unittest.main()


class TestLiteIdentity(unittest.TestCase):
    def test_internal_name_matches_file_version(self):
        import re as _re, os as _os
        _ver = _re.search(r"consilium_lite_v([\d_]+)\.json", _os.path.basename(LITE_PATH)).group(1).replace("_", ".")
        self.assertEqual(WF.get("name"), "Consilium Lite v%s" % _ver,
                         "n8n would display a wrong Lite version: %s" % WF.get("name"))
