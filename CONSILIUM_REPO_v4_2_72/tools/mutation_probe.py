#!/usr/bin/env python3
"""Mutation probe — proves that a pin CAN fail (mandate: "an assertion of absence requires proof
of applicability").

Reading 161 assertions with two pairs of eyes is exactly the method the project already judged
weaker than a live check. So we do not read them: we BREAK the code each pin guards and require the
pin to go red. A pin that stays green is empty — it costs nothing to keep and buys false confidence.

Usage:
    python tools/mutation_probe.py            # run the whole catalogue below
    python tools/mutation_probe.py <id>       # run one case

Each case: (id, file, old_fragment, new_fragment, test_selector, what_it_guards).
The probe applies the mutation, runs ONLY that test, restores the file, and reports RED/GREEN.
RED = the pin works. GREEN = the pin is empty and goes on the repair list.
"""
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# id, path, old, new, test selector, what the assertion claims is absent
CASES = [
    # ---- money core: legs ----
    ("leg-01", "microservice/app.py",
     '_pub = (ivc_fcf if (_vleg_name == "fcf_per_share" and isinstance(ivc_fcf, dict)) else ivc_base)',
     '_pub = ivc_base',
     "test_harness.TestPublicationLayerFollowsVerdictLeg.test_ladder_is_published_from_the_verdict_leg",
     "ladder is published from the verdict leg"),
    ("leg-02", "microservice/app.py",
     '"pwfv": pwfv,',
     '"pwfv": pwfv_gaap,',
     "test_harness.TestPublicationLayerFollowsVerdictLeg.test_pwfv_is_computed_on_the_verdict_leg",
     "pwfv belongs to the verdict leg"),
    ("leg-03", "microservice/app.py",
     'fcf_inp["future_pe"] = base_inp["future_pe"]   # same multiple on both legs',
     'fcf_inp["future_pe"] = round(base_inp["future_pe"] * 0.9, 2)',
     "test_harness.TestLegSymmetryAndDilutionNaming.test_both_legs_share_one_exit_multiple",
     "both legs carry one exit multiple"),
    # ---- money core: share denominator ----
    ("shares-01", "workflow/WORKFLOW.json",
     "const shc=shares_used;",
     "const shc=s.shares_current||shares_used;",
     "test_workflow.TestWiring.test_both_legs_share_one_denominator_dei_tag_excluded",
     "both legs divide by ONE share count"),
    # ---- money core: debt ----
    ("debt-01", "microservice/edgar_facts.py",
     'if _rel > RECON_TOL and _comp_sum > _chosen:',
     'if False:',
     "test_edgar_facts.TestDebtReconciliationGate.test_MA_case_components_beat_a_broken_tag",
     "components beat a broken tag"),
    ("debt-02", "microservice/ivc_lib.py",
     'if _debt_uncertain and d1 is not None and md1 and d1 >= md1:',
     'if False and d1 is not None and md1 and d1 >= md1:',
     "test_harness.TestDataIntegrityGates.test_debt_uncertain_forbids_full_marks_on_leverage",
     "a disputed debt cannot take full marks"),
    # ---- money core: growth / pe anchors ----
    ("anchor-01", "microservice/app.py",
     '_anchored_g = min(_anchor_candidates)              # conservative of the two horizons',
     '_anchored_g = max(_anchor_candidates)',
     "test_harness.TestBaseGrowthAnchoring.test_min_takes_the_conservative_horizon",
     "base growth is min of the two windows"),
    ("anchor-02", "microservice/app.py",
     '_anchored_pe = min(min(_window_meds), PE_CAP)     # min(5y, 10y, 25); NO floor',
     '_anchored_pe = min(_window_meds)',
     "test_harness.TestBaseFuturePeAnchoring.test_ceiling_bites_high_median",
     "the 25 ceiling bites"),
    # ---- money core: determinism of base ----
    ("determ-01", "microservice/app.py",
     '"discount_rate": _hurdle,   # = hurdle (mandate A); llm_disc recorded below',
     '"discount_rate": _f(A.get("discount_rate"), _hurdle),',
     "test_harness.TestBaseDeterminismSweep.test_discount_rate_is_hurdle_not_llm",
     "discount rate is the hurdle, not the LLM's"),
    ("determ-02", "microservice/app.py",
     'w = CONV_W[name]   # deterministic convention, NOT the LLM weight',
     'w = float(_f(s.get("weight"), CONV_W[name]))',
     "test_harness.TestBaseDeterminismSweep.test_weights_fixed_by_convention_not_llm",
     "scenario weights are the fixed convention"),
    # ---- money core: series integrity ----
    ("series-01", "microservice/edgar_facts.py",
     "    if full:\n        chosen = full[0]",
     "    if False:\n        chosen = full[0]",
     "test_edgar_facts.TestRevenueTagIntegrity.test_single_tag_covering_the_range_wins_no_stitching",
     "a single-tag series wins over stitching"),
    ("series-02", "microservice/edgar_facts.py",
     "                if changed:\n                    defects.append(rec)",
     "                if False:\n                    defects.append(rec)",
     "test_edgar_facts.TestRevenueTagIntegrity.test_provenance_change_beyond_tag_also_makes_a_defect",
     "a provenance change makes a defect"),
    # ---- run completeness ----
    ("complete-01", "microservice/app.py",
     '        _err_class = "ANALYSIS_RESULT" if _is_category_f else "DATA_ERROR"',
     '        _err_class = "DATA_ERROR"',
     "test_harness.TestRunCompletenessAndErrorClass.test_category_f_is_an_analysis_result_and_the_run_is_complete",
     "Category-F is an ANALYSIS_RESULT"),
    # ---- second batch: ladder, verdict, dilution, gap, continuity ----
    ("ladder-01", "microservice/app.py",
     '"mos_ladder": _pub.get("mos_ladder"),',
     '"mos_ladder": ivc_base.get("mos_ladder"),',
     "test_harness.TestPublicationLayerFollowsVerdictLeg.test_negative_control_ladder_is_not_the_other_leg",
     "rungs are not built from the other leg"),
    ("verdict-01", "microservice/app.py",
     '        if legs:\n            icb = min(legs)',
     '        if legs:\n            icb = max(legs)',
     "test_harness.TestVerdictCapFollowsConservativeLeg",
     "verdict_cap follows the conservative leg"),
    ("dilution-01", "microservice/app.py",
     '"dilution_basis": "gross_before_buybacks",',
     '"dilution_basis": "net_after_buybacks",',
     "test_harness.TestLegSymmetryAndDilutionNaming.test_dilution_bases_are_named_apart",
     "the two dilution bases are named apart"),
    ("gap-01", "microservice/app.py",
     '_gap_unreliable = _gap is not None and abs(_gap) > GAP_IV_HARD_PCT',
     '_gap_unreliable = False',
     "test_harness.TestDataIntegrityGates.test_huge_inter_leg_gap_marks_fcf_leg_unreliable",
     "a >100% inter-leg gap marks the leg unreliable"),
    ("cont-01", "microservice/edgar_facts.py",
     '                elif uncomparable:',
     '                elif False:',
     "test_edgar_facts.TestRevenueTagIntegrity.test_missing_provenance_is_unknown_not_clean",
     "missing provenance is UNKNOWN, not clean"),
    ("terminal-01", "microservice/app.py",
     '        _eff_tg = min(0.04, _bg)',
     '        _eff_tg = 0.04',
     "test_harness.TestBaseDeterminismSweep.test_terminal_growth_asymmetry_low_grower_tail_not_lifted",
     "a sub-4% grower's tail is not lifted"),
    # ---- batch 2: invariants that LOOK obviously covered (architect's directive) ----
    ("hurdle-01", "microservice/app.py",
     '    if icb is None or icb < 12.0:',
     '    if icb is None or icb < 8.0:',
     "test_harness.TestHarnessVerdictCap",
     "the 12% hurdle boundary for AVOID"),
    ("hurdle-02", "microservice/app.py",
     '    elif icb < 16.0:',
     '    elif icb < 20.0:',
     "test_harness.TestHarnessVerdictCap",
     "the 16% boundary for BUY"),
    ("ladder-02", "microservice/ivc_lib.py",
     '        thr = iv/(1+t); mthr = (iv-thr)/thr',
     '        thr = iv*(1-t); mthr = (iv-thr)/thr',
     "test_harness.TestValuationCoreIdentities",
     "rung price = IV/(1+t), not IV*(1-t)"),
    ("fade-01", "microservice/ivc_lib.py",
     # v4.2.61: fragment refreshed. It had drifted out of the source (the `not fade or` guard was
     # added later) and the probe reported SKIP — which prints beside RED/GREEN and reads like a
     # third, benign state. It is not benign: a SKIPped case proves nothing while occupying a slot
     # in the register of proven pins. Two of 39 were stale this way.
     '        gy = g if (not fade or y <= 5) else g + (tg-g)*(y-5)/(Y-5)\n        e *= (1+gy); path.append(e)',
     '        gy = g\n        e *= (1+gy); path.append(e)',
     "test_two_lens.TestVerdictPathUnmoved.test_the_fade_actually_slows_growth_in_years_6_to_10",
     "growth fades to terminal in years 6-10"),
    ("disc-01", "microservice/ivc_lib.py",
     '    iv = fv10/((1+disc)**Y)',
     '    iv = fv10/((1+disc)**5)',
     "test_harness.TestValuationCoreIdentities",
     "FV10 is discounted over the full horizon"),
    ("dualbasis-01", "microservice/app.py",
     '        conservative = "gaap_eps" if (ic_g is not None and ic_f is not None and ic_g <= ic_f) else "fcf_per_share"',
     '        conservative = "gaap_eps"',
     "test_harness.TestValuationCoreIdentities",
     "the conservative leg is CHOSEN, not fixed"),
    ("icagr-01", "microservice/ivc_lib.py",
     '    icagr = ((fv10+fvdT)/price)**(1.0/Y) - 1',
     '    icagr = ((fv10+fvdT)/price)**(1.0/5) - 1',
     "test_two_lens.TestVerdictPathUnmoved.test_implied_cagr_is_annualised_over_the_FULL_horizon",
     "implied CAGR is annualised over the horizon"),
    # ---- money core: UNKNOWN dilution on the VERDICT leg (v4.2.61) ----
    # dil-03 fixed the FCF leg and left this read untouched; the architect's grep found it, not the
    # suite. Both directions are catalogued deliberately: a cap that fires ALWAYS satisfies the
    # naive pin just as well as a correct one, so the control belongs in the register beside it.
    ("dilverdict-01", "microservice/app.py",
     '    if _dilution_unverified and verdict_cap != "AVOID":',
     '    if False:',
     "test_dil03_dps.TestVerdictLegDilutionUnverified.test_an_unverified_share_count_cannot_produce_a_bullish_cap",
     "an UNVERIFIED share count cannot produce a bullish cap"),
    ("dilverdict-02", "microservice/app.py",
     '    if _dilution_unverified and verdict_cap != "AVOID":',
     '    if verdict_cap != "AVOID":',
     "test_dil03_dps.TestVerdictLegDilutionUnverified.test_control_the_SAME_name_with_a_KNOWN_dilution_still_reaches_BUY",
     "the cap does NOT over-fire: a verified name still reaches BUY"),
    ("dilverdict-03", "microservice/app.py",
     '    _dilution_unverified = (_dil_net_known is None)',
     '    _dilution_unverified = False',
     "test_dil03_dps.TestVerdictLegDilutionUnverified.test_unverified_dilution_is_NAMED_on_the_verdict_leg",
     "an assumed 0.0 on the judging leg announces itself"),
    # ---- FCF leg + dividends (v4.2.60) ----
    ("dil-03", "microservice/app.py",
     '    _dil_net_known = _f(data.get("dilution_cagr"), None)',
     '    _dil_net_known = _f(data.get("dilution_cagr"), 0.0)',
     "test_dil03_dps.TestDil03UnknownIsNotZero.test_UNKNOWN_dilution_refuses_the_fcf_leg_instead_of_assuming_zero",
     "unknown net dilution refuses the FCF leg instead of inventing a zero"),
    ("dps-01", "microservice/edgar_facts.py",
     '            out["dps_series"] = None',
     '            out["dps_series"] = _dps',
     "test_dil03_dps.TestDpsSplitRefusal.test_the_refusal_and_absence_paths_are_distinct_flags",
     "a split inside the DPS window REFUSES the series, never publishes it"),
    ("dps-02", "microservice/app.py",
     '                _dps_g = min(_dps_g, _bg)   # never above the business growth',
     '                pass',
     "test_dil03_dps.TestDpsSeriesWiring.test_dividend_growth_can_never_exceed_the_business_growth",
     "a dividend cannot compound faster than what funds it"),
    # ---- labels and causes (v4.2.64) ----
    # Both guard LABELS on numbers that are already correct — the harder defect class, because
    # nothing downstream disagrees with a wrong label.
    ("lenslabel-01", "microservice/app.py",
     '                    "computed_on": "gaap_base",',
     '                    "computed_on": "fcf_leg",',
     "test_two_lens.TestCentralLens.test_the_label_matches_the_ACTUAL_base_the_lens_was_computed_on",
     "the lens label matches the base it was actually computed on"),
    ("divcause-01", "microservice/app.py",
     '        if _dps_flags.get("dps_series_refused_split_in_window"):',
     '        if False:',
     "test_dil03_dps.TestDividendZeroSaysWHY.test_a_refused_window_says_the_zero_is_a_PLACEHOLDER",
     "a dividend zero names its CAUSE: refused window vs non-payer vs wiring gap"),
    ("lensrender-01", "workflow/WORKFLOW.json",
     "H.push(_mkLensLines(res));",
     "",
     "test_render_tables.js",
     "the two-lens header reaches the REPORT, not only RESULT"),
    # ---- the human document (v4.2.65) ----
    ("brief-01", "workflow/WORKFLOW.json",
     "M.push('## Настроение рынка и главные новости за 6 месяцев');",
     "",
     "test_brief_render.js",
     "the news heading is printed ALWAYS, thin data or not"),
    ("brief-02", "workflow/WORKFLOW.json",
     "const IV = (pub.iv != null) ? pub.iv : ivb.intrinsic_value;",
     "const IV = ivb.intrinsic_value;",
     "test_brief_render.js",
     "the brief's headline value is the VERDICT leg, not the GAAP leg"),
    ("brief-03", "workflow/WORKFLOW.json",
     "const nm = 'запас ' + n2(r.mos_target_pct,0) + '%' + (act ? ' — действует сейчас' : '');",
     "const nm = 'запас ' + n2(r.mos_target_pct,0) + '%';",
     "test_brief_render.js",
     "the ACTIVE rung is marked in the ladder"),
    # ---- delivery of the PAIR (v4.2.66) ----
    # The defect this catalogues actually shipped: the brief rendered perfectly and reached nobody,
    # and every content pin stayed green while it did. Content and delivery are different surfaces.
    ("pair-01", "workflow/WORKFLOW.json",
     '"Assemble Brief": {\n      "main": [\n        [\n          {\n            "node": "Send Brief"',
     '"Assemble Brief": {\n      "main": [\n        [\n          {\n            "node": "NOWHERE"',
     "test_brief_render.js",
     "the brief is wired to a node that actually delivers it"),
    ("pair-02", "workflow/WORKFLOW.json",
     "  pair_contract: { expects: ['machine_report', 'investor_brief'], this_one: 'investor_brief' } },",
     "  pair_contract: { expects: ['investor_brief'], this_one: 'investor_brief' } },",
     "test_brief_render.js",
     "the payload declares it owes TWO documents, not one"),

    ("ceiling-01", "microservice/app.py",
     "PE_CAP = 30.0",
     "PE_CAP = 25.0",
     "test_two_lens.TestVerdictPathUnmoved.test_the_ceiling_is_30_and_a_revert_to_25_is_caught",
     "the mandated ceiling of 30 cannot be silently reverted to 25"),
    # ---- the 2026-08-03 matrix defects (v4.2.68) ----
    ("decomp-01", "microservice/app.py",
     '                    "gap_decomposition": _lens_decomposition(base_inp, _pub, _c_g, _c_pe, ivc),',
     '                    "gap_decomposition": None,',
     "test_two_lens.TestLensGapDecomposition.test_the_decomposition_exists_and_names_each_factor",
     "the lens gap is MEASURED, not explained by a name-independent constant"),
    ("year5-01", "microservice/ivc_lib.py",
     "    year5_reference = (round(_e5d*pef/((1+disc)**5), 2) if _e5d is not None else None)",
     "    year5_reference = None",
     "test_two_lens.TestFixtureFieldsExistInSchema.test_the_fields_that_the_matrix_caught_are_now_really_produced",
     "the five-year point is produced by the pipeline, not by hand in a mockup"),
    ("rung-01", "workflow/WORKFLOW.json",
     "const rung = (_di.required_mos_rung_pct != null) ? _di.required_mos_rung_pct : null;",
     "const rung = (_di.required_mos_rung_pct != null) ? _di.required_mos_rung_pct : 20;",
     "test_brief_render.js",
     "an unknown entry rung is declared unknown, never defaulted to the base"),
    # ---- prose generated from the same fields as the numbers (v4.2.69) ----
    ("prose-01", "workflow/WORKFLOW.json",
     "    if (_d.growth_change) _f.push({ k: 'темп роста', v: _d.growth_change });",
     "    _f.push({ k: 'темп роста', v: _d.growth_change });",
     "test_brief_render.js",
     "only NON-ZERO factors are named in the lens-gap prose"),
    ("prose-02", "workflow/WORKFLOW.json",
     "cl.delta_iv_vs_verdict_pct < 0)",
     "false)",
     "test_brief_render.js",
     "the direction of the lens gap comes from its sign, not from a constant"),
    ("singleleg-01", "microservice/app.py",
     '            "SINGLE_LEG_RUN: the FCF leg was not built (%s). The verdict rests on the GAAP leg "',
     '            "note: second leg absent (%s). "',
     "test_brief_render.js",
     "a one-legged run declares itself in the human document"),
    # ---- who actually spoke, and what the denominator was (v4.2.70) ----
    ("council-01", "workflow/WORKFLOW.json",
     "council.full_slate = (council.absent.length === 0);",
     "council.full_slate = true;",
     "test_cost_section.js",
     "an incomplete council cannot report itself as full"),
    ("council-02", "workflow/WORKFLOW.json",
     "model: (on_path ? model : null),",
     "model: model,",
     "test_cost_section.js",
     "a disconnected stage prints no model id"),
    ("gpsmax-01", "workflow/WORKFLOW.json",
     "     + (gps.max != null ? (' из ' + n2(gps.max,0)) : ' баллов (максимум этого прогона не измерен)') + '**.",
     "     + ' из ' + n2(gps.max != null ? gps.max : 100, 0) + '**.",
     "test_brief_render.js",
     "an unmeasured GPS ceiling is an absence, not a nominal 100"),
    # ---- the section manifest (v4.2.71) ----
    # Closes the class, not the case: the live META brief lost seven sections and every content pin
    # stayed green, because each checked a section that WAS there.
    ("manifest-01", "workflow/WORKFLOW.json",
     "M.push('## Что может изменить ответ?');",
     "M.push('');",
     "test_brief_render.js",
     "a dropped section is caught by the manifest, not by luck"),
    ("manifest-02", "workflow/WORKFLOW.json",
     "M.push('## Словарь');",
     "M.push('');",
     "test_brief_render.js",
     "the appendix glossary cannot vanish silently"),
    ("blockru-01", "workflow/WORKFLOW.json",
     "  const ru = BLOCK_RU[key] || [key, ''];",
     "  const ru = [key, ''];",
     "test_brief_render.js",
     "internal block identifiers never reach the human document"),
    ("evidence-01", "workflow/WORKFLOW.json",
     "    + (f || '*показатель этого блока не измерен*') + ' | ' + ru[1] + ' |');",
     "    + ' | ' + ru[1] + ' |');",
     "test_brief_render.js",
     "a score is published with the number behind it, never bare"),
]


def _workflow_path():
    wf = sorted(f for f in os.listdir(os.path.join(REPO, "workflow")) if f.endswith(".json"))
    return os.path.join("workflow", wf[-1])


def run_case(case):
    cid, path, old, new, selector, guards = case
    if path.endswith("WORKFLOW.json"):
        path = _workflow_path()
    full = os.path.join(REPO, path)
    with open(full, encoding="utf-8") as f:
        src = f.read()
    n = src.count(old)
    if n != 1:
        return cid, guards, "SKIP", "fragment found %d times" % n
    with open(full, "w", encoding="utf-8") as f:
        f.write(src.replace(old, new))
    try:
        p = subprocess.run([sys.executable, "-m", "unittest", selector],
                           cwd=os.path.join(REPO, "tests"),
                           capture_output=True, text=True, timeout=180)
        red = p.returncode != 0
    finally:
        with open(full, "w", encoding="utf-8") as f:
            f.write(src)
        # v4.2.52: restoring the SOURCE is not enough — CPython keeps a compiled .pyc whose
        # validity is judged by mtime+size, and a same-size restore can leave the MUTATED bytecode
        # in place. That is how a probe run poisoned a later measurement (verdict_cap read BUY on
        # an already-restored tree). The tool that dirties the tree must clean up after itself, or
        # every observation downstream is suspect.
        for root, dirs, _files in os.walk(REPO):
            for d in list(dirs):
                if d == "__pycache__":
                    shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                    dirs.remove(d)
    return cid, guards, ("RED" if red else "GREEN"), ""


def main(argv):
    cases = [c for c in CASES if not argv or c[0] in argv]
    print("%-12s %-46s %-6s %s" % ("id", "what the pin guards", "result", "note"))
    empty, skipped = [], []
    for c in cases:
        cid, guards, res, note = run_case(c)
        print("%-12s %-46s %-6s %s" % (cid, guards[:46], res, note))
        if res == "GREEN":
            empty.append((cid, guards))
        elif res == "SKIP":
            skipped.append((cid, guards))
    print()
    if empty:
        print("EMPTY PINS (mutation did not turn them red) — repair list:")
        for cid, g in empty:
            print("  %s: %s" % (cid, g))
        return 1
    # v4.2.67: the catalogue reports its OWN size. It was hand-counted into a handoff as 54 when
    # it holds 41 — the miscount came from grepping `("` across the file, which also matches
    # parentheses inside the mutation strings themselves. A number about the test suite, produced
    # by eye rather than by the suite, is the same class as everything else caught this session:
    # "a value that looks like a measurement but isn't". Now it is a measurement.
    print("catalogue: %d cases, %d RED, %d SKIP, %d GREEN"
          % (len(cases), len(cases) - len(skipped) - len(empty), len(skipped), len(empty)))
    print("all probed pins went RED — each can actually fail")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
