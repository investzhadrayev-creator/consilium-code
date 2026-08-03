"""
Static validation of the n8n workflow JSON (workflow/consilium_spine_vX_Y.json).

These are the checks that were run by hand after EVERY build during development. They are
purely structural — no n8n instance, no API keys, no network, no cost — but they catch the
whole class of "imported the workflow and a node silently did nothing" failures:
dangling connections, a prompt blob that stopped parsing, a truncated LLM budget, a Russian
label leaking into the English report.

Cheap enough to run on every change; run them before importing any workflow into n8n.
"""
import json
import os
import re
import re
import unittest

from _support import latest_workflow_path

WORKFLOW_PATH = latest_workflow_path()

with open(WORKFLOW_PATH, encoding="utf-8") as fh:
    WF = json.load(fh)

NODES = {n["name"]: n for n in WF["nodes"]}
CONNECTIONS = WF.get("connections", {})

# Nodes whose text ends up in the report the user reads (and feeds to NotebookLM). These must
# be English. Prompts Growth is exempt: its Russian text is INSTRUCTIONS to a multilingual
# model, not output. Gather Data is exempt: its Russian strings are operator-facing Telegram
# errors shown to Askar directly ("Пустой ввод — укажите тикер"), which are correctly Russian.
REPORT_FACING_NODES = ["Render Tables", "Build Radar", "Assemble Report", "Assemble Core-V"]
# v4.2.65: the no-cyrillic rule's SCOPE is narrowed by mandate (architect, 03.08.2026) to the
# MACHINE report. `Assemble Brief` renders the human document, which is Russian by requirement.
# Listed as a NAMED, DATED exception rather than the rule being relaxed: an exemption someone must
# add deliberately keeps catching the accidental leak the rule exists for, which is how it caught
# Render Tables in v2.8 and Build Radar in v3.0.
CYRILLIC_EXEMPT = ["Prompts Growth", "Gather Data", "Assemble Brief", "Send Brief"]

# Anthropic's API REQUIRES max_tokens — a missing value there is a hard error, not a default.
ANTHROPIC_NODES = ["Stage 2a Claude", "Stage 2b Claude", "Stage 6 Arbiter", "Core-V Arbiter"]

# Minimum output budget WHERE ONE IS SET. Every number here is a scar: Stage 6, Stage 5,
# Core-V Narrative and Core-V Arbiter each shipped a run that truncated mid-answer and lost the
# machine-readable verdict block, producing an UNPARSED report.
#
# Deliberate non-rule: an UNSET budget is NOT a bug. Gemini/Perplexity/Grok then fall back to
# the model's own maximum, which is the most permissive setting and cannot truncate. Stage 4
# Gemini, Stage 1 Perplexity and Stage 3 Grok run unset and have never truncated. Writing a
# number into them "for consistency" would invent a ceiling that does not currently exist —
# i.e. introduce the exact failure this table guards against.
MIN_TOKEN_BUDGET = {
    "Stage 2a Claude": 16000,
    "Stage 2b Claude": 24000,
    "Stage 4 Gemini": 4000,
    "Stage 5 Auditor": 8000,
    "Stage 6 Arbiter": 32000,
    "Core-V Narrative": 8000,
    "Core-V Auditor": 8000,
    "Core-V Arbiter": 8000,
}


def budget_of(node):
    """Each provider names its output cap differently."""
    body = node["parameters"].get("jsonBody", "")
    for pattern in (r'max_tokens["\']?\s*:\s*(\d+)',
                    r'max_completion_tokens["\']?\s*:\s*(\d+)',
                    r'maxOutputTokens["\']?\s*:\s*(\d+)'):
        m = re.search(pattern, body)
        if m:
            return int(m.group(1))
    return None


def prompts_dict():
    """Prompts Growth stores every prompt in one JS object literal. If it stops parsing, every
    downstream stage silently receives `undefined` instead of its instructions."""
    code = NODES["Prompts Growth"]["parameters"]["jsCode"]
    i = code.find("json:")
    j = code.find("{", i)
    depth, k = 0, j
    while k < len(code):
        if code[k] == "{":
            depth += 1
        elif code[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    return json.loads(code[j:k + 1])


class TestWiring(unittest.TestCase):

    def test_no_dangling_connections(self):
        names = set(NODES)
        dangling = []
        for src, conn in CONNECTIONS.items():
            if src not in names:
                dangling.append(src)
            for group in conn.get("main", []):
                for link in group:
                    if link["node"] not in names:
                        dangling.append(link["node"])
        self.assertEqual(dangling, [], "connections point at non-existent nodes: %s" % dangling)

    def test_gate_blocking_conditions_are_an_explicit_numbered_list(self):
        """v4.2.39 control (1). Once severity became load-bearing (MAJOR no longer blocks), the
        gate's TEETH must be DEFINED in one place, not scattered across items 2-10. Pin the
        exhaustive B1-B9 list and the anti-escalation clause."""
        code = json.dumps(NODES["Prompts Growth"]["parameters"], ensure_ascii=False)
        self.assertIn("ЗУБЫ ГЕЙТА", code, "the exhaustive BLOCKING list must exist in one place")
        for i in range(1, 10):
            self.assertIn("B%d." % i, code, "BLOCKING condition B%d missing from the list" % i)
        self.assertIn("Не поднимай пограничное", code,
                      "the anti-escalation clause must guard against drift to BLOCKING")
        self.assertIn("НЕ схлопывай MAJOR", code, "three severities -> three fields must hold")

    def test_gate_major_count_is_observational_only(self):
        """v4.2.39 control (3). The count travels to the report but must NEVER gate: a
        'N MAJOR -> block' rule would gate the same prose twice on two layers."""
        pv = NODES["Parse Verdict"]["parameters"]["jsCode"]
        self.assertIn("gate_major_count", pv, "the count must be exported")
        self.assertNotRegex(pv, r"gate_major_count\s*[><=]+\s*\d+",
                            "no threshold on gate_major_count may exist — that is double gating")
        ar = NODES["Assemble Report"]["parameters"]["jsCode"]
        self.assertIn("observational", ar, "the report must label the counts as observational")

    def test_rework_events_are_classified_for_the_rate_metric(self):
        """v4.2.39 control (4). rework_rate needs the events CLASSIFIED; the operator cannot
        compute an honest per-report cost from an unlabelled 'NEEDS REWORK' line."""
        txt = NODES["Send Rework"]["parameters"]["text"]
        self.assertIn("REWORK_CLASS", txt, "every rework event must carry its class")
        for cls in ("PARSER", "CONTRACT_DEFECT", "BLOCKING"):
            self.assertIn(cls, txt, "rework class %s must be distinguishable" % cls)
        self.assertIn("rework_rate", txt, "the message must state how the rate is computed")

    def test_prompts_carry_no_stale_valuation_terms(self):
        """v4.2.43 (mandate a). THE PROMPT IS A CONTRACT: the gate and the auditor judge the memo
        by the vocabulary written here, so a stale term is a stale SPEC against a live RESULT — it
        manufactures legitimate naming complaints that pollute the MAJOR statistics #18 is decided
        on. Same category as the pin that had to move in II.3."""
        code = json.dumps(NODES["Prompts Growth"]["parameters"], ensure_ascii=False)
        stale = {
            "IV_base": "renamed in v4.2.41 -> sensitivity.pwfv_minus_iv_verdict_leg (both terms on the verdict leg)",
            "pwfv_minus_ivbase": "field deleted in v4.2.41",
            "implied_cagr(base)": "verdict_cap is computed on the CONSERVATIVE leg, not the base leg",
        }
        for term, why in stale.items():
            self.assertNotIn(term, code, "stale term %r in the prompts — %s" % (term, why))
        # and the current vocabulary must actually be present
        self.assertIn("pwfv_minus_iv_verdict_leg", code,
                      "the prompts must name the CURRENT field")
        self.assertIn("КОНСЕРВАТИВНОЙ ноги", code,
                      "B4/verdict_cap must point the gate at the conservative leg")

    def test_workflow_nodes_may_not_read_ivc_base_without_a_whitelist_note(self):
        """v4.2.42 — the STRUCTURAL GUARD extended to the WORKFLOW. The ninth defect of the leg
        class lived here: Render Tables recomputed (res.pwfv - res.ivc_base.intrinsic_value),
        mixing the verdict-leg pwfv with the GAAP IV after pwfv changed legs in v4.2.40. The
        app.py grep pin could not see it — the renderers are a second publication surface. Every
        ivc_base read in a JS node must now carry a '# LEG-OK'-style note (// LEG-OK:)."""
        offenders = []
        for name, node in NODES.items():
            code = (node.get("parameters") or {}).get("jsCode") or ""
            lines = code.split("\n")
            for i, line in enumerate(lines):
                if "ivc_base" not in line or line.strip().startswith("//"):
                    continue
                prev = lines[i - 1] if i > 0 else ""
                if "LEG-OK" in line or "LEG-OK" in prev:
                    continue
                offenders.append("%s: %s" % (name, line.strip()[:90]))
        self.assertEqual(offenders, [],
                         "ivc_base read in a workflow node without a LEG-OK note:\n" +
                         "\n".join(offenders))

    def test_renderer_does_not_recompute_published_quantities(self):
        """v4.2.42: the renderer must READ RESULT.sensitivity.pwfv_minus_iv_verdict_leg, never
        recompute pwfv - ivc_base itself. Recomputation is how the legs got mixed in the report
        even though the microservice was already correct."""
        code = NODES["Render Tables"]["parameters"]["jsCode"].replace(" ", "")
        self.assertIn("pwfv_minus_iv_verdict_leg", code,
                      "the renderer must read the deterministic field from RESULT")
        self.assertNotIn("(res.pwfv||0)-ivBase", code,
                         "the renderer must NOT recompute pwfv - ivc_base (mixes legs)")

    def test_reprice_card_ladder_prefers_the_verdict_leg(self):
        """v4.2.40 (mandate II, SEVENTH defect). Render Reprice rendered the ladder from ivc_base
        (GAAP) while the verdict follows the conservative leg — the SAME fallback-order defect as
        II.5. Generalising II.5 across every fallback chain is what found it."""
        code = NODES["Render Reprice"]["parameters"]["jsCode"].replace(" ", "")
        self.assertIn("r.mos_ladder&&r.mos_ladder.length", code,
                      "the reprice ladder must PREFER RESULT.mos_ladder (verdict leg)")
        self.assertNotIn("constrows=(ivb.mos_ladder||[])", code,
                         "the old GAAP-first order must be gone")
        self.assertIn("mos_ladder_leg", NODES["Render Reprice"]["parameters"]["jsCode"],
                      "the reprice card must name the leg it used")

    def test_gather_data_lists_actual_debt_tags(self):
        """v4.2.33 mandate (1), second home. Gather Data assembles its own debt_components; it must
        expose the ACTUAL tags too, or the two homes drift again (the recurring defect of this
        project). §3 v1.5: a noncurrent+current sum is complete ONLY when both tags exist."""
        code = NODES["Gather Data"]["parameters"]["jsCode"]
        self.assertIn("debt_components_tags", code, "the tag map must exist")
        self.assertIn("'LongTermDebtNoncurrent'", code)
        self.assertIn("'LongTermDebtCurrent'", code)
        self.assertIn("'LongTermDebt'", code)
        self.assertRegex(code.replace(" ", ""), r"complete:\(dLtnc!=null&&dLtcur!=null\)",
                         "completeness must be computed from BOTH parts being present")
        self.assertIn("debt_components_tags,", code, "the tag map must be exported downstream")

    def test_both_legs_share_one_denominator_dei_tag_excluded(self):
        """v4.2.32 mandate (a). The EPS leg and the FCF leg must divide by the SAME share count,
        computed ONCE — a mismatch must be structurally impossible, not merely 'checked'. Before
        the fix FCF used shares_current (dei:EntityCommonStockSharesOutstanding, ONE class on a
        multi-class filer) while EPS used the split-normalized diluted series: MA 122,530,193 vs
        906,000,000 inflated FCF/share 7.39x and produced a 595.8% inter-leg gap."""
        code = NODES["Growth Enrich"]["parameters"]["jsCode"]
        # one variable, derived from the split-normalized diluted series used by EPS
        self.assertIn("shares_used=lastv(shares_for_eps)", code.replace(" ", ""),
                      "shares_used must be derived from the same series the EPS leg uses")
        self.assertIn("constshc=shares_used", code.replace(" ", ""),
                      "the FCF denominator must BE shares_used, not a separate source")
        # the dei tag must no longer feed the FCF denominator
        self.assertNotIn("shc=s.shares_current", code.replace(" ", ""),
                         "the dei EntityCommonStockSharesOutstanding tag must not be a denominator")
        # the denominator travels in the payload so a reader can audit it
        self.assertIn("shares_used,", code, "shares_used must be exported for audit")

    def test_pe_year_point_is_median_of_months_not_single_price(self):
        """v4.2.30 future_pe mandate (point 5). A year's P/E point must be the MEDIAN of that
        fiscal year's 12 month-end prices / FY EPS — a single month's price must not decide a
        year. Also pin the two separate windows (5y/10y) and the tightened PE<100 outlier bound."""
        code = NODES["Growth Enrich"]["parameters"]["jsCode"]
        # the year-point divides a MEDIAN of the year's month-end prices (pxMed) by EPS
        self.assertIn("pxMed", code, "the year-point must use a median of the year's prices")
        self.assertIn("yrPx", code, "the year's month-end prices must be collected before the median")
        self.assertRegex(code, r"date\.slice\(0,4\)===fy",
                         "prices must be grouped by the fiscal year")
        # two separate windows
        self.assertIn("pe_median_5y", code)
        self.assertIn("pe_median_10y", code)
        self.assertRegex(code, r"inWindow\(5\)")
        self.assertRegex(code, r"inWindow\(10\)")
        # tightened outlier bound (0,100), not the old 300
        self.assertIn("pe<100", code, "the outlier bound must be tightened to PE<100")
        self.assertNotIn("pe<300", code, "the old PE<300 bound must be gone")


        """v4.2.29 (contract §3 v1.5/v1.6, D3). The Dossier INSERT gained EXACTLY the seven typed
        judgement columns, added_at is supplied explicitly as the run timestamp (not NOW(), no DB
        default), and column/placeholder/value counts stay in lockstep. Legacy columns untouched."""
        node = NODES["Dossier → Postgres"]
        q = node["parameters"]["query"]
        qr = node["parameters"]["options"]["queryReplacement"]
        # the seven D3 columns are present
        for col in ["di_raw", "sustained_major", "sustained_minor", "sustained_blocking",
                    "llm_base_g", "growth_anchor", "growth_divergence"]:
            self.assertIn(col, q, "D3 column %s missing from INSERT" % col)
        # legacy columns still present (not clobbered)
        for legacy in ["ticker", "category", "spec_json", "result_json", "verdict",
                       "report_md", "memo_md", "report_level", "dossier_flags"]:
            self.assertIn(legacy, q, "legacy column %s was dropped" % legacy)
        # count integrity: columns == $N placeholders == value expressions
        n_cols = q[q.find("(") + 1:q.find(")")].count(",") + 1
        n_plh = len(re.findall(r"\$\d+", q))
        n_vals = qr.count("={{")
        self.assertEqual(n_cols, 22, "expected 22 columns, got %d" % n_cols)
        self.assertEqual(n_plh, 22, "expected 22 placeholders, got %d" % n_plh)
        self.assertEqual(n_vals, 22, "expected 22 value expressions, got %d" % n_vals)
        # added_at is the explicit run timestamp, NOT new Date() at insert time
        self.assertIn("$json.dossier.run_ts", qr,
                      "added_at must be the explicit run timestamp from the data")
        self.assertNotIn("new Date().toISOString() }}", qr,
                         "added_at must NOT be NOW()-at-insert (new Date at the insert node)")

    def test_dossier_flags_do_not_duplicate_typed_judgement_columns(self):
        """v1.6 rule: judgement metrics live in typed columns; duplicating di/growth into
        dossier_flags is forbidden. Inventory of what Assemble puts in dossier_flags must contain
        only service missing-flags, never di/growth values."""
        code = NODES["Assemble Report"]["parameters"]["jsCode"]
        # the only pushes into _dossier_flags are the *_missing service flags
        pushed = re.findall(r"_dossier_flags\.push\('([^']+)'\)", code)
        self.assertTrue(pushed, "expected the inventory of dossier_flags pushes")
        for f in pushed:
            self.assertTrue(f.endswith("_missing"),
                            "dossier_flags carries a non-service flag %r — possible metric dup" % f)
        for banned in ["di_raw", "growth_anchor", "growth_divergence", "sustained_"]:
            for f in pushed:
                self.assertNotIn(banned, f,
                                 "judgement metric %r leaked into dossier_flags (v1.6 forbids dup)" % banned)

    def test_gather_data_debt_priority_prefers_full_longtermdebt(self):
        """v4.2.26 (BACKLOG #5, second home). Gather Data carries its OWN debt-selection copy,
        parallel to edgar_facts.py. The v4.2.23 fix corrected edgar_facts but the report's
        total_debt is picked HERE — and the priority still put noncurrent_plus_current first, so
        NFLX 2026-07-19 printed $20.54B (D/E 0.77) while EDGAR had the full $21.86B (D/E 0.82).
        Pin that both homes now agree: full long_term_debt is the FIRST priority, the
        noncurrent+current reassembly is the fallback."""
        code = NODES["Gather Data"]["parameters"]["jsCode"]
        m = re.search(r"const _prio=\[([^\]]*)\]", code)
        self.assertIsNotNone(m, "debt priority list not found in Gather Data")
        prio = re.findall(r"'([^']+)'", m.group(1))
        self.assertEqual(prio[0], "long_term_debt",
                         "full LongTermDebt must be first priority (architect-approved definition), "
                         "got %r first" % (prio[0] if prio else None))
        self.assertIn("noncurrent_plus_current", prio,
                      "the noncurrent+current reassembly must remain as a fallback")
        self.assertLess(prio.index("long_term_debt"), prio.index("noncurrent_plus_current"),
                        "full figure must outrank the reassembly, matching edgar_facts.py")
        # short-term borrowings must NOT be in the priority (convention: long-term structure only)
        self.assertNotIn("short_term_borrowings", prio,
                         "short-term borrowings stay excluded by convention")

    def test_both_debt_homes_agree_full_beats_noncurrent(self):
        """The debt definition lives in TWO homes (Gather Data JS + edgar_facts.py). They drifted
        once (v4.2.23 fixed only one), and the pair caught it. Pin that both now prefer the full
        LongTermDebt over the noncurrent-only part, so a future edit to one cannot silently
        contradict the other. This is the 'one truth, two homes' guard applied to debt."""
        gd_code = NODES["Gather Data"]["parameters"]["jsCode"]
        gd_prio = re.findall(r"'([^']+)'", re.search(r"const _prio=\[([^\]]*)\]", gd_code).group(1))
        gd_full_first = gd_prio.index("long_term_debt") < gd_prio.index("noncurrent_plus_current")
        # edgar_facts.py: DEBT_FULL_LT (["LongTermDebt"]) is consulted before the noncurrent+current path
        ef_path = os.path.join(os.path.dirname(__file__), "..", "microservice", "edgar_facts.py")
        with open(ef_path, encoding="utf-8") as f:
            ef = f.read()
        # the full tag list must be defined, and the full branch must precede the reassembly branch
        self.assertIn('DEBT_FULL_LT = ["LongTermDebt"]', ef,
                      "edgar_facts must define the full-LongTermDebt tag group")
        full_pos = ef.find("full, full_tag = _latest_instant(facts, DEBT_FULL_LT)")
        reassemble_pos = ef.find("out[\"total_debt\"] = (nonc[\"val\"] if nonc else 0)")
        self.assertGreater(full_pos, 0, "edgar_facts full-debt read not found")
        self.assertGreater(reassemble_pos, full_pos,
                           "edgar_facts must try the full figure before reassembling from parts")
        self.assertTrue(gd_full_first,
                        "Gather Data must also prefer the full figure — both homes must agree")

    def test_gather_data_smoke_asserts_unsubstituted_placeholders(self):
        """v4.2.25 (BACKLOG #4). A JSON re-import reverts SVC and the EDGAR UA to their repo
        placeholders; on 2026-07-19 that silently sent every Tiingo/EDGAR call into the void and
        burned two full control runs before the config gap was found (it masqueraded as a data
        outage). Gather Data must now throw a clear config error BEFORE the first request when
        either placeholder is still in place. Pin the guard so it cannot be dropped, and confirm
        it covers BOTH placeholders and does not fire on a substituted URL/UA."""
        code = NODES["Gather Data"]["parameters"]["jsCode"]
        # the guard exists and is a real throw tied to the backlog item
        self.assertIn("CONFIG NOT SUBSTITUTED AFTER IMPORT", code,
                      "the placeholder smoke-assert is missing from Gather Data")
        # it checks the service URL placeholder AND that the value is a URL
        self.assertIn("YOUR_PYTHON_SERVICE_URL", code)
        self.assertRegex(code, r"\^https\?",
                         "the guard must also reject a non-URL SVC, not only the literal placeholder")
        # it checks the EDGAR UA placeholder AND that a real UA has an '@'
        self.assertRegex(code, r"YOUR_NAME|your@email",
                         "the guard must reject the UA placeholder")
        # the guard must run BEFORE the first http call (the companyfacts request that sends the UA header)
        guard_pos = code.index("CONFIG NOT SUBSTITUTED AFTER IMPORT")
        first_http = code.find("headers:{'User-Agent'")
        self.assertNotEqual(first_http, -1, "expected an EDGAR http call sending the UA header")
        self.assertLess(guard_pos, first_http,
                        "the smoke-assert must fire before the first EDGAR/http call, not after")

    def test_form4_runs_before_the_core_fork(self):
        """insider_form4 must reach GROUND_TRUTH for BOTH Core-P and Core-V. It does so only
        because Form4 Insider sits upstream of Eligibility (and therefore of the Route Gate
        fork). If someone moves it into one branch, the other fork silently loses insider data.
        """
        self.assertIn("Form4 Insider", NODES)
        targets = [l["node"] for g in CONNECTIONS["Form4 Insider"].get("main", []) for l in g]
        self.assertIn("Eligibility", targets)
        upstream = [l["node"] for g in CONNECTIONS["Growth Enrich"].get("main", []) for l in g]
        self.assertIn("Form4 Insider", upstream)

    def test_core_v_chain_is_intact(self):
        chain = [
            ("Run Scenario Tree (Core-V)", "Core-V Narrative"),
            ("Core-V Narrative", "Core-V Auditor"),
            ("Core-V Auditor", "Core-V Arbiter"),
            ("Core-V Arbiter", "Assemble Core-V"),
            ("Assemble Core-V", "Send Core-V"),
        ]
        for src, expected in chain:
            targets = [l["node"] for g in CONNECTIONS[src].get("main", []) for l in g]
            self.assertIn(expected, targets, "Core-V chain broken at %s -> %s" % (src, expected))

    def test_route_gate_forks_to_both_cores(self):
        outputs = CONNECTIONS["Route Gate"]["main"]
        self.assertEqual(len(outputs), 2, "Route Gate must have a TRUE and a FALSE branch")
        self.assertIn("Stage 2a Claude", [l["node"] for l in outputs[0]])
        self.assertIn("Run Scenario Tree (Core-V)", [l["node"] for l in outputs[1]])


class TestV4211Optimizations(unittest.TestCase):
    """v4.2.11 — the approved cost pass. Each pin encodes a dollar finding from the 2026-07-17
    audit: ~40% of the input bill was the same bytes resent; Stage 2b carried RESULT twice; the
    Stage 3 sentiment leg cost 12.7% of the bill for <=5/95 GPS points and zero gate influence."""

    LLM_DIET_NODES = ["Stage 2a Claude", "Stage 2b Claude", "Stage 4 Gemini",
                      "Stage 5 Auditor", "Stage 6 Arbiter"]

    def test_payload_diet_applied_to_every_llm_body(self):
        """The approved v4.3 diet: LLM payloads must NOT carry the raw Eligibility object with
        its ~750x2 OHLC rows. The slim wrapper's marker string is the pin."""
        for name in self.LLM_DIET_NODES:
            body = NODES[name]["parameters"]["jsonBody"]
            self.assertIn("stock/spy arrays stripped", body,
                          "%s sends the un-dieted GROUND_TRUTH" % name)
            self.assertNotIn("JSON.stringify($('Eligibility').first().json)", body,
                             "%s still stringifies the FULL Eligibility payload" % name)

    def test_run_code_still_receives_the_full_object(self):
        """The diet is for LLM eyes only — analyze() needs the price arrays (beta, rel
        strength). Slimming THIS body would null the market context deterministically."""
        body = NODES["Run Code"]["parameters"]["jsonBody"]
        self.assertIn("$('Eligibility').first().json", body)
        self.assertNotIn("_diet", body)

    def test_stage2b_carries_result_exactly_once(self):
        """Audit finding #2: 2b's payload held RESULT twice (Render Tables result_json + raw
        Run Code output — the same parsed object serialized twice, ~7k tokens) plus the same
        numbers a third time as TABLES. One door for RESULT: result_json."""
        body = NODES["Stage 2b Claude"]["parameters"]["jsonBody"]
        self.assertIn("result_json", body)
        self.assertNotIn("$('Run Code')", body,
                         "the duplicate raw RESULT is back in 2b's payload")

    def test_stage3_is_disconnected_with_an_honest_sentinel(self):
        """Stage 3 removed from the default run (operator decision 2026-07-18). The nodes STAY
        in the JSON for one-click rollback; only the edges go. The 2b payload must say WHY the
        sentiment block is absent — a silent missing section reads like a bug."""
        self.assertNotIn("Stage 3 Grok", CONNECTIONS, "Stage 3 still has outgoing edges")
        self.assertNotIn("Extract Grok", CONNECTIONS, "Extract Grok still has outgoing edges")
        rt_targets = [l["node"] for g in CONNECTIONS["Render Tables"]["main"] for l in g]
        self.assertIn("Stage 2b Claude", rt_targets, "Render Tables no longer feeds Stage 2b")
        body = NODES["Stage 2b Claude"]["parameters"]["jsonBody"]
        self.assertNotIn("$('Extract Grok')", body)
        self.assertIn("Stage 3 crowd sentiment DISABLED", body)
        self.assertIn("Re-enable", body, "the rollback path must travel with the decision")
        # rollback must stay one click: both nodes still present in the workflow
        self.assertIn("Stage 3 Grok", NODES)
        self.assertIn("Extract Grok", NODES)

    def test_stage3_search_cap_ready_for_reenable(self):
        """Lever 2 from OPTIMIZATION.md: 13 searches cost 64% of the Stage 3 bill; the cap
        rides along so a rollback re-enables a cheaper Stage 3, not the old one."""
        self.assertIn("max_tool_calls", NODES["Stage 3 Grok"]["parameters"]["jsonBody"])

    def test_stage2a_anchoring_corridor_present(self):
        """Variance control: PWFV moved $77.56 -> $64.75 -> $65.01 across three same-day runs
        purely from unanchored g/PE judgment. The corridor line is the fix; losing it silently
        reopens a 16% spread in the MoS-ladder entry prices the operator acts on."""
        code = NODES["Prompts Growth"]["parameters"]["jsCode"]
        self.assertIn("ANCHORING (v4.2.11", code)
        self.assertIn("rev_cagr_5y", code.split("ANCHORING (v4.2.11", 1)[1][:400])


class TestPrompts(unittest.TestCase):

    def test_prompts_blob_parses(self):
        p = prompts_dict()
        self.assertIsInstance(p, dict)
        # v4.2.2: 10, not 11 -- the `ivc_lib` key was a DEAD second copy of the scoring
        # library (nothing read it since Stage2a moved to emitting a JSON spec in v2.0).
        # A stale duplicate of money-critical code is worse than no copy: it reads as
        # authoritative and drifts silently. It lives in microservice/ivc_lib.py, only.
        self.assertGreaterEqual(len(p), 10)
        self.assertNotIn("ivc_lib", p,
                         "the scoring library must have exactly one home: microservice/ivc_lib.py")

    def test_every_expected_prompt_exists(self):
        p = prompts_dict()
        for key in ["stage1", "stage2a", "stage2b", "stage3", "stage4", "stage5_auditor",
                    "stage6_arbiter", "core_v_narrative", "core_v_auditor", "core_v_arbiter"]:
            self.assertIn(key, p)
            self.assertGreater(len(p[key]), 100, "prompt %s looks truncated" % key)

    def test_memo_data_discipline_v4227(self):
        """v4.2.27 memo-discipline experiment (architect). The memo prompt (stage2b) must carry
        THREE new hard rules — and ONLY the memo prompt may change (one-variable experiment):
          1. no unsupported superlatives (a value-word needs a number beside it),
          2. every affirmative claim carries a data reference,
          3. never contradict a RESULT flag (the divergence-vs-divergence=false precedent).
        Pin all three so the experiment's single variable cannot silently regress."""
        p = prompts_dict()
        s2b = p["stage2b"]
        # 1. superlative ban, with the concrete banned words named
        self.assertIn("ДИСЦИПЛИНА ДАННЫХ", s2b, "the discipline block is missing from stage2b")
        self.assertIn("compelling", s2b)
        self.assertRegex(s2b, r"СУПЕРЛАТИВ",
                         "the superlative ban must be explicit")
        # 2. every claim sourced
        self.assertRegex(s2b, r"СО ССЫЛКОЙ НА ДАННЫЕ|unsourced_claim",
                         "the per-claim data-reference rule must be present")
        # 3. never contradict a RESULT flag, naming the divergence precedent
        self.assertIn("НЕ ПРОТИВОРЕЧЬ ФЛАГАМ", s2b)
        self.assertIn("contradicts_result_flag", s2b)
        self.assertRegex(s2b, r"divergence=false",
                         "the divergence=false precedent (runs 4/5) must be cited as the example")

    def test_memo_discipline_did_not_touch_auditor_or_arbiter(self):
        """One-variable guarantee: the discipline experiment must NOT have leaked into the auditor
        or arbiter prompts (that would make the 4th point incomparable to the 3rd)."""
        p = prompts_dict()
        for other in ["stage5_auditor", "stage6_arbiter", "stage2a", "stage4"]:
            self.assertNotIn("ДИСЦИПЛИНА ДАННЫХ", p[other],
                             "discipline block leaked into %s — experiment no longer single-variable" % other)

    def test_radar_6_1_is_consistent_across_the_three_gates(self):
        """v4.2.24 (radar #12a). The 6.1 Radar table is built deterministically by Build Radar
        AFTER Stage 5 runs; it is absent from the memo text BY DESIGN. Three prompts must agree:
        stage2b tells the LLM to skip 6.1, stage4 tells the IC gate not to look for it, and
        stage5 (the adversarial auditor) must ALSO be told not to stamp it missing — otherwise it
        files a false MAJOR on a table that is in fact rendered (NFLX 2026-07-19 claim #12). This
        pins the three-way consistency so a future prompt edit cannot desync them again."""
        p = prompts_dict()
        # stage2b instructs the LLM to skip the 6.1 prose table
        self.assertRegex(p["stage2b"], r"6\.1",
                         "stage2b must reference the 6.1 handling")
        # stage4 already exempts 6.1 from its checks
        self.assertIn("Таблицы 6.1 в MEMO нет", p["stage4"],
                      "stage4 must tell the IC gate not to look for 6.1 in the memo")
        # stage5 (the fix): must be told NOT to stamp 6.1 / RADAR_ACTIONS missing
        s5 = p["stage5_auditor"]
        self.assertIn("ДЕТЕРМИНИРОВАННЫМ слоем", s5,
                      "stage5 must know 6.1 is built deterministically, not by the memo")
        self.assertRegex(s5, r"НЕ штампуй.*6\.1 missing|6\.1 missing",
                         "stage5 must be told not to stamp the (false) '6.1 missing' MAJOR")
        # but stage5 must STILL be able to flag a genuinely thresholdless row (claim #13 stays valid)
        self.assertIn("radar_no_threshold", s5,
                      "stage5 must keep flagging a row with no measurable KPI — that defect is real")

    def test_stage1_forces_first_source_and_bans_regional_aggregators(self):
        """The root fix for ASTS's fact-pack being ~92% [UNVERIFIED]: Perplexity was pulling
        Russian re-publishers for a US issuer instead of EDGAR."""
        s1 = prompts_dict()["stage1"]
        self.assertIn("SEC EDGAR", s1)
        self.assertIn("BANNED", s1)
        self.assertIn("Financemarker", s1)

    def test_stage3_is_x_only_and_bans_named_analyst_actions(self):
        """v4.2.9 — the rule collision that blocked NFLX 2026-07-17. Stage 3's node config has
        x_search ONLY (Grok itself said: 'I don't have access to web search or financial media'),
        yet the prompt demanded 'финансовые медиа' — so Grok substituted tweets ABOUT media and
        the memo cited a tweet's Oppenheimer/KeyBanc claim as a street fact. The prompt must
        promise only what the tools deliver, and bank names must be out of Stage 3's scope."""
        s3 = prompts_dict()["stage3"]
        self.assertNotIn("финансовые медиа", s3,
                         "the prompt promises a source the node's tools cannot reach")
        self.assertIn("ТОЛЬКО по X/Twitter", s3)
        self.assertIn("ЗАПРЕЩЕНО", s3)
        self.assertIn("Oppenheimer", s3, "the ban must carry its concrete counter-example")
        self.assertIn("ОБЕЗЛИЧЕННО", s3, "PT chatter must be reportable namelessly, not suppressed")

    def test_stage2b_names_have_one_door(self):
        """Fix 3: sentiment shapes narrative, FACT_PACK supplies names. Both halves must be
        stated — a ban without the permitted alternative teaches evasion, not compliance."""
        s2b = prompts_dict()["stage2b"]
        self.assertIn("names have one door", s2b)
        self.assertIn("may NEVER contribute a bank name", s2b)
        self.assertIn("unverified price-target-cut chatter", s2b,
                      "the nameless fallback phrasing must be given verbatim")

    def test_stage1_street_section_admits_sell_side_trackers(self):
        """Why Perplexity kept returning [UNVERIFIED]: the STREET section demanded tier-1 press or
        the bank's own note — but routine PT changes almost never reach Reuters/Bloomberg; they
        live on Benzinga/TipRanks/StreetInsider, which the hierarchy relegated below usability.
        The prompt demanded a source class where the data does not exist, got honest UNVERIFIEDs,
        and the memo then reached for a tweet. The section must admit the trackers, tagged."""
        s1 = prompts_dict()["stage1"]
        for tracker in ("Benzinga", "TipRanks", "StreetInsider"):
            self.assertIn(tracker, s1, tracker + " missing from the STREET sourcing list")
        self.assertIn("[AGGREGATOR]", s1)
        self.assertIn("X/Twitter and blogs are NOT sources for analyst actions", s1)
        self.assertIn("price target", s1)

    def test_stage2a_asks_for_a_spec_not_python(self):
        """The deterministic-harness contract: Stage2a supplies judgment, never executable code."""
        s2a = prompts_dict()["stage2a"]
        self.assertIn("Do NOT write code", s2a)
        self.assertIn("qualitative_scores", s2a)

    def test_insider_gates_present_in_both_cores(self):
        p = prompts_dict()
        self.assertIn("insider_unsourced", p["stage4"])
        self.assertIn("insider_data_available_but_omitted", p["stage4"])
        self.assertIn("insider_unsourced", p["core_v_auditor"])
        self.assertIn("INSIDER SIGNAL", p["core_v_narrative"])

    def test_core_v_hard_gates_present(self):
        cva = prompts_dict()["core_v_auditor"]
        self.assertIn("TAM SOURCES (MANDATORY HARD GATE)", cva)
        self.assertIn("DILUTION vs EDGAR (MANDATORY HARD GATE)", cva)

    def test_arbiter_machine_block_contract(self):
        p = prompts_dict()
        self.assertIn("COREV_VERDICT", p["core_v_arbiter"])
        self.assertIn("consensus|divergence|CONTESTED", p["stage6_arbiter"])


class TestModelBudgets(unittest.TestCase):

    def test_anthropic_nodes_always_declare_max_tokens(self):
        """The Anthropic API rejects a request without max_tokens — unset here is a hard break,
        not a permissive default."""
        for name in ANTHROPIC_NODES:
            self.assertIsNotNone(
                budget_of(NODES[name]),
                "%s calls the Anthropic API without max_tokens — the request will fail" % name)

    def test_set_budgets_meet_the_minimum_that_stopped_truncation(self):
        """Only checks nodes that DO set a budget. See the note on MIN_TOKEN_BUDGET: unset
        means 'model maximum', which is safe."""
        for name, minimum in MIN_TOKEN_BUDGET.items():
            budget = budget_of(NODES[name])
            if budget is None:
                continue   # unset -> model max -> cannot truncate
            self.assertGreaterEqual(
                budget, minimum,
                "%s budget %s < %s — this is how the verdict block got truncated before"
                % (name, budget, minimum))

    def test_core_v_arbiter_budget_matches_its_core_p_twin(self):
        """Specific regression: Core-V Arbiter (Opus) sat at 4000 while its Core-P twin needed
        64000. Same model, same job, same class of long output — it was one long run away from
        the same UNPARSED failure Stage 6 hit."""
        self.assertGreaterEqual(budget_of(NODES["Core-V Arbiter"]), 16000)

    def test_verdict_chains_stay_cross_family(self):
        """Decorrelation is the point: the memo, the audit and the verdict must come from
        three different model families, or the audit is just the author agreeing with itself.
        """
        def family(node):
            url = NODES[node]["parameters"].get("url", "")
            if "anthropic" in url:
                return "anthropic"
            if "openai" in url:
                return "openai"
            if "generativelanguage" in url:
                return "google"
            if "x.ai" in url:
                return "xai"
            return "other"

        core_v = [family(n) for n in ("Core-V Narrative", "Core-V Auditor", "Core-V Arbiter")]
        self.assertEqual(len(set(core_v)), 3, "Core-V chain is not cross-family: %s" % core_v)
        core_p = [family(n) for n in ("Stage 4 Gemini", "Stage 5 Auditor", "Stage 6 Arbiter")]
        self.assertEqual(len(set(core_p)), 3, "Core-P chain is not cross-family: %s" % core_p)


class TestHttpBodies(unittest.TestCase):

    def test_all_http_bodies_are_well_formed_expressions(self):
        for node in WF["nodes"]:
            if node.get("type") != "n8n-nodes-base.httpRequest":
                continue
            body = node["parameters"].get("jsonBody", "")
            if not body:
                continue
            self.assertTrue(body.startswith("={{"), "%s: body doesn't open with ={{" % node["name"])
            self.assertTrue(body.rstrip().endswith("}}"), "%s: body doesn't close with }}" % node["name"])

    def test_microservice_nodes_point_at_a_single_placeholder_or_host(self):
        """After consolidating equity-runner into growth-enrich there is exactly one service.
        Two different hosts here means a node is still calling the retired deployment."""
        hosts = set()
        for node in WF["nodes"]:
            for field in ("url",):
                url = node.get("parameters", {}).get(field, "")
                if "/analyze" in url or "/enrich_yf" in url or "/scenario_tree" in url \
                        or "/edgar_facts" in url or "/edgar_form4" in url:
                    hosts.add(url.split("/")[0] if "://" not in url else url.split("/")[2])
            code = node.get("parameters", {}).get("jsCode", "")
            for m in re.finditer(r"url:\s*'([^']*/(?:enrich_yf|edgar_facts|edgar_form4|analyze|scenario_tree))'", code):
                u = m.group(1)
                hosts.add(u.split("/")[0] if "://" not in u else u.split("/")[2])
        self.assertLessEqual(len(hosts), 1, "microservice calls are split across hosts: %s" % hosts)


class TestReportLanguage(unittest.TestCase):
    """The report is consumed in English (then translated by NotebookLM, which preserves the
    numbers). A Russian label leaking from a deterministic node is a real regression — it
    happened twice: Render Tables (v2.8) and then Build Radar (v3.0), which was missed because
    it is a SEPARATE code node."""

    def test_no_cyrillic_in_report_facing_nodes(self):
        for name in REPORT_FACING_NODES:
            blob = json.dumps(NODES[name]["parameters"], ensure_ascii=False)
            found = re.findall(r"[А-Яа-я]+", blob)
            self.assertEqual(found, [], "%s leaks Russian into the report: %s" % (name, found[:5]))

    def test_no_unexpected_node_leaks_cyrillic(self):
        """Catch-all: any NEW node that renders report text must be English. Exemptions are
        explicit and justified above."""
        offenders = {}
        for node in WF["nodes"]:
            if node["name"] in CYRILLIC_EXEMPT or node.get("type") == "n8n-nodes-base.stickyNote":
                continue
            blob = json.dumps(node.get("parameters", {}), ensure_ascii=False)
            hits = re.findall(r"[А-Яа-я]{3,}", blob)
            if hits:
                offenders[node["name"]] = hits[:3]
        self.assertEqual(offenders, {}, "unexpected Russian text: %s" % offenders)


class TestWorkflowIdentity(unittest.TestCase):
    """Operator-flagged 2026-07-18: the filename was bumped every iteration while the
    workflow's INTERNAL name — what n8n displays after import — sat at 'v4.2.9' through
    v4.2.12, so the UI lied about which version was running. Same defect class as the
    filename rule; same cure: the version in the name field must equal the version in the
    filename, mechanically."""

    def test_internal_name_matches_filename_version(self):
        import glob
        import os
        path = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "workflow",
                                             "consilium_spine_v*.json")))[-1]
        fname_ver = re.search(r"consilium_spine_v([\d_]+)\.json", path).group(1).replace("_", ".")
        self.assertEqual(WF.get("name"), "Consilium Spine v%s" % fname_ver,
                         "n8n will display '%s' for file v%s" % (WF.get("name"), fname_ver))


class TestCoreVDiet(unittest.TestCase):
    """v4.2.13: the diet missed the Core-V branch in v4.2.11 (found while preparing the
    Core-V test run). Narrative and Auditor carry GROUND_TRUTH -> slim; the Scenario Tree
    is the branch's Run Code and keeps the full object."""

    def test_core_v_llm_bodies_are_dieted(self):
        for name in ["Core-V Narrative", "Core-V Auditor"]:
            body = NODES[name]["parameters"]["jsonBody"]
            self.assertIn("stock/spy arrays stripped", body, "%s un-dieted" % name)
            self.assertNotIn("JSON.stringify($('Eligibility').first().json)", body,
                             "%s still sends the full payload" % name)

    def test_scenario_tree_keeps_the_full_object(self):
        p = NODES["Run Scenario Tree (Core-V)"]["parameters"]
        body = p.get("jsonBody", p.get("jsCode", ""))
        self.assertNotIn("_diet", body, "the deterministic scenario tree got starved")


class TestEvidenceFormatV4214(unittest.TestCase):
    """v4.2.14, after the second live NFLX burn (2026-07-18): the gate correctly blocked an
    E_moat justification written in words with zero digits. Both prompts already DEMANDED
    figures; what was missing was a prescribed SHAPE. These pins keep the shape from silently
    evaporating in a future prompt edit — losing it reopens an ~$0.85 stochastic burn per
    wordy memo."""

    def setUp(self):
        self.code = NODES["Prompts Growth"]["parameters"]["jsCode"]

    def test_2b_prescribes_the_justification_shape_and_moat_metric_menu(self):
        self.assertIn("ФОРМАТ ОБОСНОВАНИЯ Ж", self.code)
        self.assertIn("(v4.2.14)", self.code)
        self.assertIn("реализованная pricing power", self.code,
                      "the E_moat metric menu (op-margin trajectory) is gone")
        self.assertIn("score_unevidenced", self.code,
                      "the memo no longer knows the exact gate item it risks")

    def test_2a_evidence_field_requires_a_digit(self):
        self.assertIn("digit-bearing metric verbatim", self.code)
        self.assertIn("points 0 for that block", self.code)


class TestTablesCustodyV4215(unittest.TestCase):
    """v4.2.15: all three 2026-07-18 spine reports shipped section 1 as '[no data]' while the
    memo quoted the very same tables — Assemble's long-range $('Render Tables') failed at its
    position. The cure is a main-line custody chain using only hops proven working in those
    same runs. Losing any link silently re-opens the defect."""

    def test_number_audit_fetches_the_passthrough(self):
        code = NODES["Number Audit"]["parameters"]["jsCode"]
        self.assertIn("tables_md_passthrough", code)
        self.assertIn("$('Render Tables')", code)

    def test_build_radar_carries_it_down_the_main_line(self):
        code = NODES["Build Radar"]["parameters"]["jsCode"]
        self.assertIn("tables_md_passthrough", code)
        self.assertIn("$input.first().json.tables_md_passthrough", code)

    def test_assemble_reads_passthrough_first_and_fails_loudly(self):
        code = NODES["Assemble Report"]["parameters"]["jsCode"]
        self.assertIn("safe('Build Radar', j=>j.tables_md_passthrough)", code)
        self.assertIn("ASSEMBLY DEFECT", code,
                      "the loud failure banner is gone — a silent [no data] cost three reports")


class TestTerminalPeRuleV4215(unittest.TestCase):
    """v4.2.15: the v4.2.11 'anchor future_pe to pe_hist_median' line was obeyed literally
    (NFLX run3: future_pe=42.7) and moved PWFV from $63 to $101 on identical data, flipping
    the verdict band. The corrected rule must stay; its loss reopens a verdict coin-flip."""

    def test_pe_rule_present_and_hist_median_banned(self):
        code = NODES["Prompts Growth"]["parameters"]["jsCode"]
        self.assertIn("TERMINAL PE RULE (v4.2.15)", code)
        self.assertIn("NEVER anchor it to pe_hist_median", code)
        self.assertIn("18-28", code)

    def test_the_old_harmful_anchor_is_gone(self):
        code = NODES["Prompts Growth"]["parameters"]["jsCode"]
        self.assertNotIn("anchor base future_pe to min(pe_hist_median", code,
                         "the harmful v4.2.11 PE anchor is back")


class TestGlossary(unittest.TestCase):
    """v4.2.10, operator request 2026-07-18: the report is LISTENED to (NotebookLM). The
    operator named GPS, IV, PWFV, DI and hurdle_gate as terms he could not decode — a metric
    the reader cannot decode produces no conviction, and conviction is the product. Every
    report must therefore end with a static glossary. This test pins (a) its presence, (b) its
    attachment to the assembled markdown, (c) coverage of every term the operator listed."""

    CODE = None

    @classmethod
    def setUpClass(cls):
        cls.CODE = NODES["Assemble Report"]["parameters"]["jsCode"]

    def test_glossary_section_exists(self):
        self.assertIn("## 9. Glossary", self.CODE,
                      "Assemble Report lost the glossary section")

    def test_glossary_is_appended_to_the_report(self):
        # the GLOSSARY constant must actually be joined into `md`, not merely defined —
        # a defined-but-unused block is exactly the silent-green failure this suite hunts
        self.assertRegex(self.CODE, r"costSection,\s*'',\s*\n?\s*GLOSSARY\s*\]",
                         "GLOSSARY is defined but not joined into the report markdown")

    def test_glossary_covers_operator_named_terms(self):
        for term in ["GPS", "IV (Intrinsic Value)", "PWFV", "DI (Disagreement Index)",
                     "Hurdle / hurdle_gate", "MoS (Margin of Safety)", "MoS ladder",
                     "verdict_cap", "Dual basis", "[UNVERIFIED]", "[AGGREGATOR]",
                     "Implied CAGR", "GPS denominator"]:
            self.assertIn(term, self.CODE, "glossary missing the term: %s" % term)


class TestResilience(unittest.TestCase):
    """Every external call must survive a transient provider failure.

    v4.0.2: Anthropic returned HTTP 529 (overloaded_error) mid-run. Investigating it surfaced
    that all four Core-V nodes had NO retry and NO timeout while every Core-P node had both —
    a 529 on the Core-V Arbiter would have killed an ASTS/RKLB run outright. Nothing tested
    node-level settings before, so the asymmetry sat there silently.

    Note what this CANNOT fix: n8n's retry is a FIXED delay capped at 5s, not exponential
    backoff. A sustained provider overload still fails the run; the answer there is to re-run
    the ticker, not to weaken anything.
    """

    LLM_NODES = ["Stage 1 Perplexity Raw", "Stage 2a Claude", "Stage 2b Claude", "Stage 3 Grok",
                 "Stage 4 Gemini", "Stage 5 Auditor", "Stage 6 Arbiter",
                 "Core-V Narrative", "Core-V Auditor", "Core-V Arbiter"]
    SERVICE_NODES = ["Run Code", "Run Scenario Tree (Core-V)", "Run Reprice"]

    def test_every_external_call_retries(self):
        for name in self.LLM_NODES + self.SERVICE_NODES:
            self.assertTrue(NODES[name].get("retryOnFail"),
                            "%s has no retry — one transient 429/500/529 kills a $0.5-2 run" % name)

    def test_llm_nodes_use_the_full_retry_budget(self):
        """n8n caps maxTries at 5 and waitBetweenTries at 5000ms. Provider overloads are the
        common failure, so take the whole allowance."""
        for name in self.LLM_NODES:
            self.assertGreaterEqual(NODES[name].get("maxTries", 0), 5, "%s: maxTries" % name)
            self.assertGreaterEqual(NODES[name].get("waitBetweenTries", 0), 5000,
                                    "%s: waitBetweenTries" % name)

    def test_core_v_has_retry_parity_with_core_p(self):
        """The two forks are equally load-bearing; Core-V must not be the weaker path."""
        for p_node, v_node in [("Stage 2b Claude", "Core-V Narrative"),
                               ("Stage 5 Auditor", "Core-V Auditor"),
                               ("Stage 6 Arbiter", "Core-V Arbiter"),
                               ("Run Code", "Run Scenario Tree (Core-V)")]:
            p, v = NODES[p_node], NODES[v_node]
            self.assertEqual(v.get("retryOnFail"), p.get("retryOnFail"),
                             "%s vs %s: retry mismatch" % (v_node, p_node))
            self.assertGreaterEqual(v.get("maxTries", 0), p.get("maxTries", 0),
                                    "%s retries less than %s" % (v_node, p_node))

    def test_every_external_call_has_a_timeout(self):
        """No timeout = a hung provider connection stalls the execution indefinitely."""
        for name in self.LLM_NODES + self.SERVICE_NODES:
            t = NODES[name]["parameters"].get("options", {}).get("timeout")
            self.assertTrue(t and t > 0, "%s has no timeout" % name)


class TestNoSecretsInWorkflow(unittest.TestCase):
    """v4.1: the workflow JSON must contain NO keys and NO placeholders.

    Two things this protects. Practically: re-importing used to mean retyping ~10 placeholders
    at 3-4 min each, and a missed one is a silent defect. Structurally: the export is meant to
    be safe to share and store — one careless edit that inlines a key destroys that property
    quietly, and nothing else would notice.
    """

    SECRET_ENV = ["TIINGO_TOKEN", "FRED_KEY", "FINNHUB_KEY", "ALPHAVANTAGE_KEY",
                  "FINRA_CLIENT_ID", "FINRA_CLIENT_SECRET"]

    def workflow_blob(self):
        """Everything except sticky notes — changelog prose legitimately names placeholders."""
        return json.dumps([n for n in WF["nodes"]
                           if n.get("type") != "n8n-nodes-base.stickyNote"])

    def test_no_live_key_shaped_strings(self):
        """Catch a real key pasted in during debugging and forgotten."""
        blob = self.workflow_blob()
        for pattern, provider in [(r"sk-ant-[A-Za-z0-9_-]{20,}", "Anthropic"),
                                  (r"sk-proj-[A-Za-z0-9_-]{20,}", "OpenAI"),
                                  (r"sk-[A-Za-z0-9]{32,}", "OpenAI-style"),
                                  (r"xai-[A-Za-z0-9]{20,}", "xAI"),
                                  (r"pplx-[A-Za-z0-9]{20,}", "Perplexity"),
                                  (r"AIza[A-Za-z0-9_-]{30,}", "Google")]:
            self.assertIsNone(re.search(pattern, blob),
                              "a live %s key is embedded in the workflow" % provider)

    def test_llm_nodes_use_credentials_not_inline_headers(self):
        for name in ["Stage 1 Perplexity Raw", "Stage 2a Claude", "Stage 2b Claude", "Stage 3 Grok",
                     "Stage 5 Auditor", "Stage 6 Arbiter", "Stage 4 Gemini",
                     "Core-V Narrative", "Core-V Auditor", "Core-V Arbiter"]:
            n = NODES[name]
            self.assertEqual(n["parameters"].get("authentication"), "genericCredentialType",
                             "%s does not use an n8n credential" % name)
            self.assertTrue(n.get("credentials"), "%s has no credential bound" % name)

    def test_no_auth_headers_inline(self):
        """The credential supplies the auth header; a leftover inline one would shadow it."""
        for n in WF["nodes"]:
            for h in n.get("parameters", {}).get("headerParameters", {}).get("parameters", []):
                self.assertNotIn(h.get("name", "").lower(), ("x-api-key", "authorization"),
                                 "%s still sets an auth header inline" % n["name"])

    def test_no_data_source_keys_anywhere_in_n8n(self):
        """v4.2: data-source keys live on the Railway service that uses them, never in n8n.

        v4.1 tried to keep them in n8n via $env — a dead end: n8n 2.x runs Code nodes in a
        task-runner sandbox with no access to the container environment ('access to env vars
        denied'), and the only alternative was inlining them into the exported JSON.
        """
        blob = self.workflow_blob()
        for name in self.SECRET_ENV:
            self.assertNotIn(name, blob,
                             "%s is referenced in n8n; it belongs to growth-enrich" % name)

    def test_no_env_access_in_code_nodes(self):
        """$env raises in n8n 2.x task runners. A reintroduced $env is a runtime crash, and
        crashes at Gather Data mean no report and no obvious cause."""
        for n in WF["nodes"]:
            code = n.get("parameters", {}).get("jsCode", "")
            self.assertNotIn("$env.", code,
                             "%s reads $env — task runners deny that at runtime" % n["name"])

    def test_only_non_secret_placeholders_remain(self):
        """Two are tolerated because neither is a credential: the service URL, and the SEC
        User-Agent contact (SEC fair-access WANTS to know who is calling)."""
        found = set(re.findall(r"YOUR_[A-Z_]+", self.workflow_blob()))
        self.assertEqual(found, {"YOUR_PYTHON_SERVICE_URL", "YOUR_NAME"},
                         "unexpected placeholder set: %s" % found)

    def test_microservice_url_is_one_constant_per_node(self):
        """Every caller resolves the host from a single `SVC` const, so an import edits one
        line per node rather than hunting inline URLs."""
        for name in ["Gather Data", "Growth Enrich", "Form4 Insider"]:
            code = NODES[name]["parameters"]["jsCode"]
            self.assertIn("const SVC='YOUR_PYTHON_SERVICE_URL'", code,
                          "%s has no single SVC constant" % name)

    def test_macro_prices_is_called_not_fred_or_tiingo_directly(self):
        """Gather Data must not call FRED/Tiingo itself — that is what forced keys into n8n."""
        code = NODES["Gather Data"]["parameters"]["jsCode"]
        self.assertIn("/macro_prices", code)
        self.assertNotIn("stlouisfed", code, "Gather Data still calls FRED directly")
        self.assertNotIn("api.tiingo.com", code, "Gather Data still calls Tiingo directly")


if __name__ == "__main__":
    print("validating: %s" % WORKFLOW_PATH)
    unittest.main(verbosity=2)


class TestDossierV4216(unittest.TestCase):
    """BACKLOG #3: the dossier row (ARCHITECTURE §3 contract) is written by the spine itself.

    Custody first: the 2026-07-18 control runs lost section 6 and the Stage 1/2a meters to
    long-range $() references, so every dossier field must travel the main line
    (Render Tables -> Number Audit -> Build Radar -> Assemble) and the Postgres node must read
    ONLY $json — never a distant node."""

    SCHEMA_COLUMNS = ["ticker", "category", "added_at", "spec_json", "result_json", "verdict",
                      "verdict_date", "report_md", "memo_md", "factpack_md",
                      "last_filing_accession", "spec_stale", "spec_stale_reason",
                      "report_level", "dossier_flags"]

    def test_dossier_node_exists_and_cannot_kill_the_report(self):
        n = NODES.get("Dossier → Postgres")
        self.assertIsNotNone(n, "Dossier → Postgres node is missing")
        self.assertEqual(n["type"], "n8n-nodes-base.postgres")
        self.assertEqual(n.get("onError"), "continueRegularOutput",
                         "a dossier write failure must never take down Send Report")

    def test_insert_carries_every_schema_column(self):
        q = NODES["Dossier → Postgres"]["parameters"]["query"]
        self.assertIn("INSERT INTO ticker_dossier", q)
        for col in self.SCHEMA_COLUMNS:
            self.assertIn(col, q, "§3 column %s absent from the INSERT" % col)

    def test_dossier_node_is_fed_by_assemble_and_reads_only_json(self):
        targets = [t["node"] for t in CONNECTIONS["Assemble Report"]["main"][0]]
        self.assertIn("Dossier → Postgres", targets)
        qr = NODES["Dossier → Postgres"]["parameters"]["options"]["queryReplacement"]
        self.assertNotIn("$(", qr, "the Postgres node must not do long-range lookups")
        self.assertIn("$json.dossier.", qr)

    def test_custody_chain_carries_the_dossier_payload(self):
        self.assertIn("spec_json_passthrough", NODES["Render Tables"]["parameters"]["jsCode"])
        self.assertIn("factpack_passthrough", NODES["Render Tables"]["parameters"]["jsCode"])
        self.assertIn("dossier_passthrough", NODES["Number Audit"]["parameters"]["jsCode"])
        self.assertIn("dossier_passthrough", NODES["Build Radar"]["parameters"]["jsCode"])
        asm = NODES["Assemble Report"]["parameters"]["jsCode"]
        self.assertIn("dossier_passthrough", asm)
        self.assertIn("dossier_flags", asm)

    def test_section6_prefers_the_passthrough(self):
        """The factpack must be read from the main line FIRST; the long-range reference is a
        fallback, and a double miss is a loud ASSEMBLY DEFECT — never a silent [no data]."""
        asm = NODES["Assemble Report"]["parameters"]["jsCode"]
        self.assertIn("factpack_md", asm)
        i_pass = asm.find("dossier_passthrough||{}).factpack_md")
        i_direct = asm.find("safe('Verify FACT_PACK Entity'")
        self.assertTrue(0 < i_pass < i_direct,
                        "passthrough must be tried before the direct reference")
        self.assertIn("ASSEMBLY DEFECT: the memo cites FACT_PACK", asm)

    def test_missing_fields_are_null_and_named_never_invented(self):
        asm = NODES["Assemble Report"]["parameters"]["jsCode"]
        for flag in ("spec_json_missing", "result_json_missing", "factpack_md_missing"):
            self.assertIn(flag, asm, "a silently absent dossier field: %s" % flag)

class TestRepriceV4217(unittest.TestCase):
    """BACKLOG #5: `reprice TICKER` — the stored dossier verdict rescaled to a fresh price.

    The branch is deliberately SHORT (Gather Data -> IF -> Fetch Dossier -> Prep -> HTTP ->
    Render -> Send, every $() reference <= 2 hops) because the 2026-07-18 control runs proved
    long-range custody dies. The freshness gates live in the MICROSERVICE (/reprice), where
    they are unit-tested — the workflow must not re-implement or weaken them."""

    def test_gather_data_parses_reprice_and_exports_run_mode(self):
        code = NODES["Gather Data"]["parameters"]["jsCode"]
        self.assertIn("reprice\\s+", code, "`reprice TICKER` command is not parsed")
        self.assertIn("run_mode", code)
        self.assertRegex(code, r"return \[\{ json: \{\n  ticker, company_title, run_mode",
                         "run_mode must be exported in the return payload")

    def test_reprice_route_if_splits_on_run_mode(self):
        n = NODES.get("Reprice Route")
        self.assertIsNotNone(n, "Reprice Route IF node is missing")
        cond = n["parameters"]["conditions"]["conditions"][0]
        self.assertIn("run_mode", cond["leftValue"])
        self.assertEqual(cond["rightValue"], "reprice")
        outs = WF["connections"]["Reprice Route"]["main"]
        self.assertEqual(outs[0][0]["node"], "Fetch Dossier", "true branch -> Fetch Dossier")
        self.assertEqual(outs[1][0]["node"], "Growth Enrich",
                         "false branch must continue the normal analysis line")

    def test_gather_data_feeds_the_router_not_growth_enrich_directly(self):
        self.assertEqual(WF["connections"]["Gather Data"]["main"][0][0]["node"],
                         "Reprice Route")

    def test_fetch_dossier_reads_latest_row_and_survives_empty(self):
        n = NODES.get("Fetch Dossier")
        self.assertIsNotNone(n)
        q = n["parameters"]["query"]
        self.assertIn("FROM ticker_dossier", q)
        self.assertIn("ORDER BY added_at DESC LIMIT 1", q)
        self.assertEqual(n.get("onError"), "continueRegularOutput")
        self.assertTrue(n.get("alwaysOutputData"),
                        "an empty SELECT would silently kill the branch — the user must "
                        "get the honest 'no dossier' answer instead")

    def test_reprice_chain_is_wired_end_to_end(self):
        chain = ["Fetch Dossier", "Reprice Prep", "Run Reprice", "Render Reprice",
                 "Send Reprice"]
        for a, b in zip(chain, chain[1:]):
            self.assertEqual(WF["connections"][a]["main"][0][0]["node"], b,
                             "%s must feed %s" % (a, b))

    def test_run_reprice_calls_the_reprice_route_with_the_prep_body(self):
        n = NODES["Run Reprice"]
        self.assertEqual(n["parameters"]["url"], "YOUR_PYTHON_SERVICE_URL/reprice")
        body = n["parameters"]["jsonBody"]
        for field in ("ticker", "spec_date", "result"):
            self.assertIn(field, body)
        self.assertNotIn("$('", body, "the HTTP body must read $json only — short custody")

    def test_render_reprice_handles_all_three_outcomes(self):
        code = NODES["Render Reprice"]["parameters"]["jsCode"]
        self.assertIn("no dossier on record", code)          # missing dossier
        self.assertIn("REFUSED", code)                        # freshness refusal
        self.assertIn("newer_filing_since_spec", code)        # names form/date/accession
        self.assertIn("Not a fresh analysis", code)           # honest scope label
        self.assertIn("SELF-TEST FAILED", code)               # surfaced, not swallowed

    def test_reprice_references_stay_short_range(self):
        """Max 2 hops: Prep reads Gather Data (2 back), Render reads Prep (2 back)."""
        prep = NODES["Reprice Prep"]["parameters"]["jsCode"]
        rend = NODES["Render Reprice"]["parameters"]["jsCode"]
        import re as _re
        self.assertEqual(sorted(set(_re.findall(r"\$\('([^']+)'\)", prep))), ["Gather Data"])
        self.assertEqual(sorted(set(_re.findall(r"\$\('([^']+)'\)", rend))), ["Reprice Prep"])

    def test_send_reprice_uses_the_send_rework_pattern(self):
        n = NODES["Send Reprice"]
        self.assertEqual(n["type"], "n8n-nodes-base.telegram")
        self.assertEqual(n["parameters"]["chatId"], "={{ $json.chat_id }}")
        self.assertIn("telegramApi", n.get("credentials", {}))

class TestGatedV4218(unittest.TestCase):
    """BACKLOG #6: the DEFAULT run is GATED — deterministic layer + memo + Stage-4 gate
    (~$0.43); `TICKER full` runs the adversarial Stage 5/6 chain. The gate itself is never
    weakened: a gated run is SHORTER, not softer. Honesty rules pinned here: di is NULL (not
    0 — zero is not unknown), final_verdict is the deterministic verdict_cap (never an
    invented arbiter verdict), and Assemble labels the skipped sections instead of printing
    '[no data]'."""

    def test_gather_data_parses_full_suffix_and_defaults_to_gated(self):
        code = NODES["Gather Data"]["parameters"]["jsCode"]
        self.assertIn("_mFull", code)
        self.assertIn("s+full$", code.replace("\\", ""))
        self.assertIn("'reprice' : (_mFull ? 'full' : 'gated')", code,
                      "default must be gated; `full` and `reprice` are explicit opt-ins")

    def test_parse_verdict_exports_run_mode(self):
        code = NODES["Parse Verdict"]["parameters"]["jsCode"]
        self.assertIn("run_mode", code)

    def test_mode_gate_sits_between_gate_and_stage5(self):
        self.assertEqual(WF["connections"]["Gate"]["main"][0][0]["node"], "Mode Gate",
                         "Gate(true) must feed Mode Gate, not Stage 5 directly")
        outs = WF["connections"]["Mode Gate"]["main"]
        self.assertEqual(outs[0][0]["node"], "Stage 5 Auditor", "full -> adversarial chain")
        self.assertEqual(outs[1][0]["node"], "Gated Verdict", "gated -> deterministic verdict")
        cond = NODES["Mode Gate"]["parameters"]["conditions"]["conditions"][0]
        self.assertIn("run_mode", cond["leftValue"])
        self.assertEqual(cond["rightValue"], "full")

    def test_gated_verdict_emits_the_parse_di_shape_honestly(self):
        code = NODES["Gated Verdict"]["parameters"]["jsCode"]
        self.assertIn("di: null", code, "di must be NULL — the chain did not run; 0 would lie")
        self.assertIn("di_class: 'GATED'", code)
        self.assertIn("contested: false", code)
        self.assertIn("verdict_cap", code, "final_verdict = deterministic verdict_cap")
        self.assertIn("TICKER full", code, "the answer must tell the operator how to escalate")
        import re as _re
        refs = sorted(set(_re.findall(r"\$\('([^']+)'\)", code)))
        self.assertEqual(refs, ["Build Radar"],
                         "custody: only the <=5-hop Build Radar reference is allowed")
        self.assertEqual(WF["connections"]["Gated Verdict"]["main"][0][0]["node"],
                         "Collect Usage")

    def test_collect_usage_carries_the_di_payload_down_the_main_line(self):
        code = NODES["Collect Usage"]["parameters"]["jsCode"]
        self.assertIn("di_payload", code)
        self.assertIn("$input.first().json", code)

    def test_assemble_reads_di_from_the_main_line_with_guarded_fallback(self):
        code = NODES["Assemble Report"]["parameters"]["jsCode"]
        i_main = code.find("di_payload")
        i_direct = code.find("$('Parse DI')")
        self.assertTrue(0 < i_main < i_direct,
                        "main-line di_payload must be tried before the direct reference")
        self.assertIn("try { di = $('Parse DI').first().json; } catch", code,
                      "the direct read must be guarded — it THROWS on gated runs")
        self.assertIn("di_payload_missing_ASSEMBLY_DEFECT", code,
                      "a double miss must be loud, never a silent default")

    def test_assemble_labels_gated_sections_instead_of_no_data(self):
        code = NODES["Assemble Report"]["parameters"]["jsCode"]
        self.assertEqual(code.count("gated run — Stage 5/6 skipped by design"), 2,
                         "sections 3 AND 4 must both carry the explicit gated label")

    def test_gated_runs_never_touch_stage_5_or_6_wiring(self):
        """The chain Stage 5 -> Extract Audit -> Stage 6 -> ... stays intact for full runs."""
        self.assertEqual(WF["connections"]["Stage 5 Auditor"]["main"][0][0]["node"],
                         "Extract Audit")
        self.assertEqual(WF["connections"]["Parse DI"]["main"][0][0]["node"], "Collect Usage")

class TestMeterMapTopologyV4221(unittest.TestCase):
    """C3 watch-item (architect): Collect Usage hardcodes the path topology as a SECOND copy
    (the NOT_ON_PATH map) of a truth that already lives in the workflow connections. Two homes
    for one fact drift silently: re-enable Grok, add a stage, or re-wire Core-V, and the map goes
    stale while the meters quietly lie again — the exact class this whole fix exists to kill.
    This pins the map to the ACTUAL graph, derived here from connections, never from a third copy.

    Discipline (also in CLAUDE.md): change the topology -> bump the map, or this test fails."""

    def _adj(self):
        adj = {}
        for src, d in WF["connections"].items():
            adj[src] = [[c["node"] for c in (grp or [])] for grp in d.get("main", [])]
        return adj

    def _reach(self, start):
        adj = self._adj()
        seen, stack = set(), [start]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            for grp in adj.get(n, []):
                stack.extend(grp)
        return seen

    def _incoming(self):
        inc = {}
        for src, d in WF["connections"].items():
            for grp in d.get("main", []):
                for c in (grp or []):
                    inc.setdefault(c["node"], []).append(src)
        return inc

    def _map_from_code(self):
        """The base NOT_ON_PATH set as written in Collect Usage (mode-independent members)."""
        code = NODES["Collect Usage"]["parameters"]["jsCode"]
        m = re.search(r"const NOT_ON_PATH = new Set\(\[([^\]]*)\]\)", code)
        self.assertIsNotNone(m, "NOT_ON_PATH map not found in Collect Usage")
        return set(re.findall(r"'([^']+)'", m.group(1)))

    def test_grok_membership_matches_whether_it_is_wired(self):
        code_map = self._map_from_code()
        incoming = self._incoming()
        grok_wired = len(incoming.get("Stage 3 Grok", [])) > 0
        self.assertEqual("Stage 3 Grok" in code_map, not grok_wired,
                         "Grok is in NOT_ON_PATH iff it has NO incoming edge (disabled). "
                         "If someone re-wired Grok, drop it from the map; if they cut it, add it.")

    def test_core_v_nodes_are_off_the_core_p_branch(self):
        """Every Core-V node must be on Route Gate's Core-V output, NOT the Core-P output —
        that is exactly what justifies their place in NOT_ON_PATH for a Core-P run."""
        rg = WF["connections"]["Route Gate"]["main"]
        core_p = self._reach(rg[0][0]["node"])
        core_v = self._reach(rg[1][0]["node"])
        code_map = self._map_from_code()
        for cv in ("Core-V Narrative", "Core-V Auditor", "Core-V Arbiter"):
            self.assertIn(cv, code_map, "%s must be in NOT_ON_PATH" % cv)
            self.assertIn(cv, core_v, "%s must be on the Core-V branch" % cv)
            self.assertNotIn(cv, core_p, "%s must NOT be on the Core-P branch" % cv)

    def test_core_p_llm_stages_are_NOT_in_the_map(self):
        """The stages that always run on a Core-P execution must never be marked not-on-path;
        a throw on them is a lost meter, not a free zero. Stage 5/6 are added to the map only
        under gated mode, at runtime — they must NOT appear in the static base set."""
        code_map = self._map_from_code()
        for on_path in ("Stage 1 Perplexity Raw", "Stage 2a Claude", "Stage 2b Claude",
                        "Stage 4 Gemini", "Stage 5 Auditor", "Stage 6 Arbiter"):
            self.assertNotIn(on_path, code_map,
                             "%s is on the Core-P main line; a throw there is meter_lost, "
                             "not not_run — it must not be in the static NOT_ON_PATH" % on_path)

    def test_stage_5_6_are_gated_at_runtime_by_di_class(self):
        """The mode-dependent members are added inside an `if (_gated)` guard keyed on
        di_class==='GATED' — the only signal that can tell a design-skip from a lost meter."""
        code = NODES["Collect Usage"]["parameters"]["jsCode"]
        self.assertRegex(code, r"if \(_gated\)[^\n]*NOT_ON_PATH\.add\('Stage 5 Auditor'\)")
        self.assertIn("NOT_ON_PATH.add('Stage 6 Arbiter')", code)
        self.assertIn("di_class", code)

    def test_every_map_member_is_a_known_stage(self):
        """A typo'd stage name in the map would silently never match — the member would do
        nothing and a real on-path stage would keep mis-reporting. Pin the names to STAGES."""
        code = NODES["Collect Usage"]["parameters"]["jsCode"]
        stage_names = set(re.findall(r"\['([^']+)',\s*'[^']+',\s*'[^']+'\]", code))
        for member in self._map_from_code():
            self.assertIn(member, stage_names,
                          "NOT_ON_PATH member %r is not a declared STAGE — typo?" % member)

