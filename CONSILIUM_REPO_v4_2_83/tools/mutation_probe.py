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
import re
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
    # v4.2.82 changeset. The pin this probes had NEVER executed: its fixture built no FCF leg, so
    # it self-skipped on every run since it was written, and the runner counted the skip as green.
    # The mutation is the defect in its most plausible form — the scorecard reading the leg that
    # flatters, while the verdict in the same report follows the leg that does not.
    ("leg-04", "microservice/app.py",
     '        _verdict_ic_pct = (dual_basis.get(dual_basis["verdict_leg"]) or {}).get("implied_cagr_pct")',
     '        _verdict_ic_pct = max([x for x in [(dual_basis.get("gaap_eps") or {}).get("implied_cagr_pct"), (dual_basis.get("fcf_per_share") or {}).get("implied_cagr_pct")] if x is not None] or [None])',
     "test_v422_regressions.TestGpsWiringV424.test_C_block_scores_the_VERDICT_leg_not_the_optimistic_one",
     "block C scores the VERDICT leg, never the optimistic one"),
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
     "    if _debt_uncertain:\n        d1, md1 = None, 0",
     "    if False:\n        d1, md1 = None, 0",
     "test_harness.TestDataIntegrityGates.test_debt_uncertain_forbids_full_marks_on_leverage",
     "a disputed debt is REFUSED, not merely docked (v4.2.82 replaced docking with refusal)"),
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
    # v4.2.83 (mandate 09 §1): this case mutated the flag TEXT in app.py while the pin that guards
    # it SUPPLIES that flag from its own fixture — mutation and pin were wired to different
    # artifacts, so the case could never turn red. The property belongs to the BRIEF.
    ("singleleg-01", "workflow/WORKFLOW.json",
     "M.push('- **\u041e\u0446\u0435\u043d\u043a\u0430 \u043f\u043e\u0441\u0442\u0440\u043e\u0435\u043d\u0430 \u043f\u043e \u043e\u0434\u043d\u043e\u043c\u0443 \u043e\u0441\u043d\u043e\u0432\u0430\u043d\u0438\u044e, \u0430 \u043d\u0435 \u043f\u043e \u0434\u0432\u0443\u043c.** ",
     "M.push('- **_** ",
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
    # ---- the four-call FACT_PACK split (v4.2.74) ----
    ("merge-01", "workflow/WORKFLOW.json",
     "      if (seen[key]) { collisions.push(h.trim()); continue; }",
     "      if (false) { collisions.push(h.trim()); continue; }",
     "test_fp_merge.js",
     "a section answered by two calls is refused, never silently arbitrated"),
    ("merge-02", "workflow/WORKFLOW.json",
     "    failed.push(name);",
     "    continue;",
     "test_fp_merge.js",
     "an unreachable source is marked as a SOURCE failure, not as absent facts"),
    ("merge-03", "workflow/WORKFLOW.json",
     ".filter(s => s.indexOf(SKIP) === -1)",
     "",
     "test_fp_merge.js",
     "an unasked section is dropped, never published as a missing one"),
    # ---- v4.2.77: the three-tier contract, the 4->3 cut, and the build marker ----
    ("tier-01", "workflow/WORKFLOW.json",
     "TIER A - PRODUCED",
     "TIER Z - PRODUCED",
     "test_fp_merge.js",
     "the contract declares the tier that is NOT to be searched"),
    ("tier-02", "workflow/WORKFLOW.json",
     "it must not be counted as run incompleteness",
     "it is counted as run incompleteness",
     "test_fp_merge.js",
     "terminal-only data is a property of the world, not a failure of this run"),
    ("tier-03", "workflow/WORKFLOW.json",
     "Cover ONLY section 4 and the STREET section of the contract above.",
     "Cover ONLY sections 4, 5 and the STREET section of the contract above.",
     "test_fp_merge.js",
     "a section claimed by two themes is caught in the CONTRACT, not only at the merge"),
    ("meter-02", "workflow/WORKFLOW.json",
     "['Stage 1 FP legal',   'perplexity', 'sonar-pro'],",
     "['Stage 1 FP fin',     'perplexity', 'sonar-pro'], "
     "['Stage 1 FP legal',   'perplexity', 'sonar-pro'],",
     "test_fp_merge.js",
     "a retired stage leaves no row in the meter map, wearing the look of a free zero"),
    ("health-01", "microservice/app.py",
     '"build": BUILD})',
     '"build": "v4.2.77"})',
     "test_harness.TestHealthDeclaresBuild.test_the_version_is_read_from_the_marker_not_restated",
     "the served version is READ from the marker, never restated"),
    ("ghost-01", "microservice/app.py",
     "    if isinstance(peer, (int, float)) and peer > 0:",
     "    peer = peer if isinstance(peer, (int, float)) else data.get('pe_sector_median')\n"
     "    if isinstance(peer, (int, float)) and peer > 0:",
     "test_harness.TestPeAnchorHasOneInput.test_a_sector_median_alone_anchors_nothing",
     "an input the pipeline never supplies cannot become load-bearing again"),
    ("thesis-01", "workflow/WORKFLOW.json",
     "const _verdictWord = (_gap > 0.02) ? 'ТРЕБУЕТ УСКОРЕНИЯ'",
     "const _verdictWord = (_gap > 99) ? 'ТРЕБУЕТ УСКОРЕНИЯ'",
     "test_brief_render.js",
     "the thesis direction is measured from the gap, not stored"),
    ("thesis-02", "workflow/WORKFLOW.json",
     "  if (_th.length) {",
     "  if (true) {",
     "test_brief_render.js",
     "an unmeasured run states the absence instead of inventing a thesis"),
    ("peer-01", "microservice/app.py",
     "    comparable = bool(peer_med is not None and company is not None",
     "    comparable = bool(True or peer_med is not None and company is not None",
     "test_harness.TestPeerMultipleBlockMatchesBases.test_no_company_multiple_on_that_basis_means_NOT_comparable",
     "two multiples on different bases are never declared comparable"),
    ("peer-02", "microservice/app.py",
     "    count = len([r for r in rows if isinstance(r, dict)]) or None",
     "    count = len([r for r in rows if isinstance(r, dict)])",
     "test_harness.TestPeerMultipleBlockMatchesBases.test_missing_peer_rows_give_count_None_not_zero",
     "an unknown peer count is an absence, never a zero"),
    ("peer-03", "workflow/WORKFLOW.json",
     "  if (_pm.comparable) {",
     "  if (true) {",
     "test_brief_render.js",
     "the brief refuses the comparison the RESULT refused"),
    ("cata-01", "workflow/WORKFLOW.json",
     "      if (line.length < 40) continue;",
     "      if (false) continue;",
     "test_brief_render.js",
     "a bare date line is not an event"),
    ("cata-02", "workflow/WORKFLOW.json",
     "    if (_sectionsSeen) {",
     "    if (false) {",
     "test_brief_render.js",
     "numbered sections scope the scan when the source supplies them"),
    ("cata-03", "workflow/WORKFLOW.json",
     "  } else if (_sourceFailed) {",
     "  } else if (false) {",
     "test_brief_render.js",
     "an unreachable source and an empty search print different sentences"),
    ("peer-04", "microservice/app.py",
     '        "peer_multiple": _peer_multiple_block(data),',
     '        "peer_multiple_INPUTS_ONLY": _peer_multiple_block(data),',
     "test_harness.TestPeerMultipleReachesRESULT.test_the_block_is_published_in_RESULT_not_in_the_ivc_inputs",
     "the block is published where the renderer reads it, not merely computed"),
    ("cata-04", "workflow/WORKFLOW.json",
     "НА ЯЗЫКЕ ИСТОЧНИКА",
     "как есть",
     "test_brief_render.js",
     "English events in a Russian brief are explained, not left looking like a defect"),
    # ---- v4.2.79: contract carve-out, section markers, extractor vs raw artifact, new sections ----
    ("carve-01", "workflow/WORKFLOW.json",
     "CARVE-OUT, and read it carefully",
     "Note in passing",
     "test_fp_merge.js",
     "a number said by management on a date is quotable, not a forbidden series"),
    ("marker-01", "workflow/WORKFLOW.json",
     "Emit it EVEN WHEN YOU FOUND NOTHING",
     "Emit it when you found something",
     "test_fp_merge.js",
     "a requested section announces itself even when empty"),
    ("street-01", "workflow/WORKFLOW.json",
     "Cover ONLY section 4 and the STREET section of the contract above.",
     "Cover ONLY section 4 of the contract above.",
     "test_fp_merge.js",
     "STREET belongs to exactly one theme and is not silently orphaned"),
    ("cata-05", "workflow/WORKFLOW.json",
     "      if (!dt || dt < _floor) continue;",
     "      if (!dt) continue;",
     "test_brief_render.js",
     "a 2021 announcement is not a current catalyst"),
    ("cata-06", "workflow/WORKFLOW.json",
     "  } else if (_linesScanned > 0) {",
     "  } else if (false) {",
     "test_brief_render.js",
     "an extraction miss is reported as ours, never as a fact about the company"),
    ("three-01", "microservice/app.py",
     "                                   if (eps and eps > 0 and price) else None),",
     "                                   if (eps and eps > 0 and price) else 0.0),",
     "test_harness.TestThreeYearTable.test_a_year_without_eps_publishes_None_not_zero",
     "a multiple is never computed from a missing EPS"),
    ("three-02", "workflow/WORKFLOW.json",
     "| фискальный год (конец) |",
     "| год |",
     "test_brief_render.js",
     "every row carries its fiscal-year end, because 2026 is not the same twelve months everywhere"),
    ("peers-01", "workflow/WORKFLOW.json",
     "    for (const r of _pr) {",
     "    for (const r of []) {",
     "test_brief_render.js",
     "the comparables are named, not summarised into an unarguable median"),
    # ---- v4.2.80: nine defects from the ORCL 2026-08-05 run ----
    ("d1-01", "workflow/WORKFLOW.json",
     ".replace(/(^|[^\\\\\\\\])\\\\$/g, '$1\\\\\\\\$')",
     "",
     "test_brief_render.js",
     "the dollar sign is escaped once, at the single exit"),
    ("d2-01", "workflow/WORKFLOW.json",
     "  if (a >= 1e9)  return sg + '$' + (a/1e9).toFixed(2)  + ' млрд';",
     "  if (a >= 1e99) return sg + '$' + (a/1e9).toFixed(2)  + ' млрд';",
     "test_brief_render.js",
     "filing values are printed on a human scale"),
    ("d2-02", "workflow/WORKFLOW.json",
     "a = Math.abs(x), sg = x < 0 ? MINUS",
     "a = x, sg = (0) ? MINUS",
     "test_brief_render.js",
     "the minus is never swallowed by the currency mark"),
    ("d3-01", "workflow/WORKFLOW.json",
     ".map(r=>Object.assign({}, r, {fwd_pe:null, eps_growth_pct:null, _basis:'trailing_inhouse'}));",
     ".map(r=>({ticker:r.ticker, pe_trailing:r.pe_trailing, _basis:'trailing_inhouse'}));",
     "test_brief_render.js",
     "the peer projection stops narrowing every field added upstream"),
    ("d4-01", "workflow/WORKFLOW.json",
     "      if (/^(Source tier|Source|Publication date[s]?|Tier",
     # v4.2.83: the first form replaced ONE alternative and left `|Source|` standing, which still
     # matched "Source tier: ...". A mutation must remove the property, not one of its spellings.
     "      if (/^(zzNEVER1|zzNEVER2|zzNEVER3|zzNEVER4",
     "test_brief_render.js",
     "a provenance note is not an event"),
    ("d5-01", "workflow/WORKFLOW.json",
     "      if (r.d < 0) _conflicted.push(_lab(r));",
     "      if (false) _conflicted.push(_lab(r));",
     "test_brief_render.js",
     "a scenario whose arithmetic contradicts its side is named"),
    ("d6-01", "workflow/WORKFLOW.json",
     "', причина: ' + _flagRu(_slf)",
     "', причина: ' + _slf",
     "test_brief_render.js",
     "the engine string never reaches the human document"),
    ("d6-02", "workflow/WORKFLOW.json",
     # v4.2.83: the return spans TWO lines and the first form cut only the first, so the phrase
     # the pin asserts survived on the continuation line and the case read GREEN. The anchor is
     # JSON-ESCAPED because the probe edits the raw workflow file, where jsCode is one string and
     # a newline is stored as two characters — the undocumented constraint that made every
     # workflow mutation here single-line, and that let this one cut half a statement.
     "  return 'причина записана техническим кодом «' + s.slice(0, 60)\\n    + '» — словарь этого выпуска её не покрывает, полная формулировка в машинном отчёте';",
     "  return 'причина: ' + s;",
     "test_brief_render.js",
     "an unrecognised flag is declared a gap, not shown raw"),
    ("d7-01", "workflow/WORKFLOW.json",
     "НА ЯЗЫКЕ МАШИННОГО АНАЛИЗА, как и события",
     "на основании данных, как и события",
     "test_brief_render.js",
     "the evidence column declares its language"),
    ("d8-01", "workflow/WORKFLOW.json",
     "  if (k1 >= 2 && k1 <= 4) return few;",
     "  if (false) return few;",
     "test_brief_render.js",
     "Russian counters agree with their numbers"),
    ("d9-01", "workflow/WORKFLOW.json",
     "bits.push('против сектора ' + mult(e.fwd_pe_vs_sector));",
     "bits.push('против сектора ' + Number(e.fwd_pe_vs_sector).toFixed(2) + 'x');",
     "test_brief_render.js",
     "one multiplier format in prose and tables"),
    # ---- v4.2.81: defects found in the second ORCL run ----
    ("d6-03", "workflow/WORKFLOW.json",
     "'вторая оценка строится только от положительной базы (точное значение — в машинном отчёте)'",
     "'вторая оценка строится от базы (' + (s.match(/-?[0-9]+[.]?[0-9]*/)||[])[0] + ')'",
     "test_brief_render.js",
     "no number is scraped out of prose and published as a measurement"),
    ("scale-01", "workflow/WORKFLOW.json",
     "  if (a >= 1e12) return sg + '$' + (a/1e12).toFixed(2) + ' трлн';",
     "",
     "test_brief_render.js",
     "trillions read as trillions, not as four-digit billions"),
    ("cata-07", "workflow/WORKFLOW.json",
     "  } else if (_datedSeen > 0) {",
     "  } else if (false) {",
     "test_brief_render.js",
     "a stale source and a failed extraction are different diagnoses"),
    ("street-02", "workflow/WORKFLOW.json",
     "## SECTION STREET: recent named analyst actions",
     "the STREET section",
     "test_brief_render.js",
     "an unnumbered section is still covered by the marker rule"),
    # ---- v4.2.82: the four operator points + the three-state metric ----
    ("debt-05", "microservice/ivc_lib.py",
     "        or _debt_diverges or _debt_zero_suspect)",
     "        or False)",
     "test_harness.TestDebtZeroIsUnknownORCLCase.test_the_ORCL_reading_is_refused_not_scored",
     "a 100% source divergence on debt is not read as a clean number"),
    ("debt-06", "microservice/ivc_lib.py",
     "    _debt_zero_suspect = (de == 0)",
     "    _debt_zero_suspect = False",
     "test_harness.TestDebtZeroIsUnknownORCLCase.test_an_exact_zero_alone_is_enough_to_refuse",
     "a leverage ratio of exactly zero is UNKNOWN, not a debt-free balance sheet"),
    ("debt-07", "microservice/ivc_lib.py",
     "        d1, md1 = None, 0        # REFUSED",
     "        d1, md1 = 0, 4           # REFUSED",
     "test_harness.TestDebtZeroIsUnknownORCLCase.test_a_refused_leverage_leaves_the_denominator",
     "a refused sub-block leaves the denominator, or it reads as a zero the company earned"),
    ("debt-08", "workflow/WORKFLOW.json",
     "    if (e.de_refused) {",
     "    if (false) {",
     "test_brief_render.js",
     "the refusal computed upstream is visible in the human document"),
    ("street-03", "workflow/WORKFLOW.json",
     "if (_sv.pwfv_vs_street_pct != null && Math.abs(_sv.pwfv_vs_street_pct) >= 25) {",
     "if (false) {",
     "test_brief_render.js",
     "a large gap to consensus is named, not left for the reader to compute"),
    ("label-01", "workflow/WORKFLOW.json",
     "                 label: r.label, label_ru: r.label_ru }))",
     "                 label: r.label }))",
     "test_brief_render.js",
     "label_ru survives the scenario projection"),
    # ---- v4.2.83 (мандат 07). Added AFTER the probe was taught to run .js selectors and to prove
    # execution: before that, any case added here with a .js selector would have printed RED
    # without running, like the 56 before it.
    ("xmult-01", "workflow/WORKFLOW.json",
     "M.push('| \u00d7 \u0432\u044b\u0445\u043e\u0434\u043d\u043e\u0439 \u043c\u043d\u043e\u0436\u0438\u0442\u0435\u043b\u044c ' + xmult(inp.future_pe) + ' | '",
     "M.push('| \u00d7 \u0432\u044b\u0445\u043e\u0434\u043d\u043e\u0439 \u043c\u043d\u043e\u0436\u0438\u0442\u0435\u043b\u044c ' + n2(inp.future_pe,0) + ' | '",
     "test_brief_render.js",
     "the exit multiple is ONE string everywhere it appears"),
    ("xmult-02", "workflow/WORKFLOW.json",
     "const xmult = (v)=> (v==null||!isFinite(v))?'\u2014':Number(v).toFixed(2);",
     "const xmult = (v)=> (v==null||!isFinite(v))?'\u2014':Number(v).toFixed(0);",
     "test_brief_render.js",
     "the printed arithmetic of the step table reconciles"),
    ("label-02", "workflow/WORKFLOW.json",
     ": (String(r.label || '\u2014') + ' _(\u043f\u043e-\u0440\u0443\u0441\u0441\u043a\u0438 \u043d\u0435 \u043f\u0440\u0438\u0448\u043b\u043e)_');",
     ": String(r.label || '\u2014');",
     "test_brief_render.js",
     "a missing label_ru is MARKED, never silently English"),
    # The first draft mutated one SPELLING of " с оговоркой" and came back GREEN: the phrase also
    # occurs in the sentence explaining what a caveated section is. A mutation must remove the
    # PROPERTY, not one of its spellings — so it now forces the legacy two-state branch.
    ("states-01", "workflow/WORKFLOW.json",
     "  if (_e != null && _c != null && _l != null) {",
     "  if (false) {",
     "test_brief_render.js",
     "the leaf metric prints THREE states, not two"),
    ("debt-09", "microservice/ivc_lib.py",
     "    if not _dd and isinstance(_dd_nested, dict):\n        _dd = _dd_nested",
     "    if False:\n        _dd = _dd_nested",
     "test_harness.TestDebtZeroIsUnknownORCLCase.test_the_divergence_is_read_where_the_producer_writes_it",
     "the debt divergence is read where the producer writes it"),
    # ---- Issue #12 restored onto v4.2.83 (Issue #15): pe_sector_median_absent flag ----
    ("secmed-01", "microservice/app.py",
     "    if _pe_anchor_fwd(data) is None:",
     "    if False:",
     "test_harness.TestPeSectorMedianAbsentFlag.test_flag_present_and_names_the_cause_when_sector_anchor_is_absent",
     "the sector-median-absent flag fires when the anchor cannot be built"),
    # ---- issue #21: the double-absence case (pe_hist_median ALSO missing) ----
    ("secmed-02", "microservice/app.py",
     '        if _f(data.get("pe_hist_median"), None) is not None:',
     "        if True:",
     "test_harness.TestPeSectorMedianAbsentFlag.test_flag_says_NOT_applied_when_both_anchors_are_absent",
     "a double-anchor absence says the cap is NOT applied, not a false historical-median fallback"),
    # ---- issue #14: the historical-reconstruction stand (as_of filter, ROE, same-basis P/E) ----
    ("asof-01", "microservice/edgar_facts.py",
     '    if as_of:\n        facts = _filter_facts_as_of(facts, as_of)\n        out["_as_of"] = as_of',
     "    if False:\n        facts = _filter_facts_as_of(facts, as_of)\n        out[\"_as_of\"] = as_of",
     "test_edgar_facts.TestAsOfFilter.test_as_of_excludes_facts_filed_after_the_cutoff",
     "as_of excludes every fact FILED after the cutoff, not just ones whose period ends after it"),
    ("asof-02", "microservice/edgar_facts.py",
     '    if as_of:\n        facts = _filter_facts_as_of(facts, as_of)\n        out["_as_of"] = as_of',
     "    if False:\n        facts = _filter_facts_as_of(facts, as_of)\n        out[\"_as_of\"] = as_of",
     "test_edgar_facts.TestAsOfFilter.test_as_of_excludes_equity_filed_after_the_cutoff",
     "the equity series obeys the SAME as_of cutoff as everything else"),
    ("roe-01", "microservice/edgar_facts.py",
     "    neg = [e for e in ends if eq[e] <= 0]\n    if neg:",
     "    neg = [e for e in ends if eq[e] <= 0]\n    if False:",
     "test_edgar_facts.TestEquityAndRoe.test_negative_equity_refuses_with_a_reason_not_a_number",
     "negative/zero equity refuses ROE with a named reason, never a computed number"),
    # THE mandate's own words: "снятие фильтра по дате обязано покраснеть" is asof-01/02 above;
    # "замена коэффициента сплита на единицу обязана покраснеть" is splitfactor-02 below, in the
    # literal form the mandate names -- the factor forced to 1 rather than the one it measured.
    # v4.2.83 (issue #24): refreshed for the product-vs-ratio rewrite. The old anchor (the
    # "matches no clean split multiple" message) was deleted along with the clean-multiple list
    # it belonged to; the mutation now targets the branch that replaced it -- a product/ratio
    # disagreement beyond tolerance -- forcing the SAME never-default-to-1 failure mode.
    # v4.2.83 (issue #26): refreshed for the divCash-driven residual rewrite -- the old fragment
    # (bare product vs ratio, fixed 5% tolerance) no longer exists verbatim after the constant was
    # replaced with an expected dividend contribution computed from `daily_rows`' own divCash.
    ("splitfactor-01", "microservice/macro_prices.py",
     '    if abs(ratio - expected) / expected > _SPLIT_RESIDUAL_TOLERANCE:\n'
     '        return None, ("split_factor_undeterminable: splitFactor product %.4f, expected dividend "\n'
     '                      "contribution %.4f (expected ratio %.4f), and close/adjClose ratio %.4f "\n'
     '                      "disagree by more than the %.1f%% residual tolerance"\n'
     '                      % (product, div_contribution, expected, ratio,\n'
     '                         _SPLIT_RESIDUAL_TOLERANCE * 100))\n'
     '    return product, None',
     "    return 1.0, None",
     "test_historical_stand.TestSameShareBasisPE.test_undeterminable_split_factor_refuses_never_defaults_to_one",
     "an undeterminable split factor is REFUSED, never silently defaulted to 1"),
    # issue #26: the mandate's own words -- "мутация 'ожидаемый вклад -> 1.0' обязана краснеть".
    # Forcing the dividend signal to 1.0 (i.e. ignoring divCash entirely, the pre-#26 behaviour)
    # must turn the MSFT pin red: with contribution pinned to 1.0, expected = product = 1.0
    # against the real observed ratio of 1.0737 -- a 7.37% gap the 1% residual cannot absorb, so
    # the run refuses a name that should pass clean.
    ("splitfactor-04", "microservice/macro_prices.py",
     "        contribution *= close / (close - div)\n    return contribution, None",
     "        contribution *= close / (close - div)\n    return 1.0, None",
     "test_historical_stand.TestSameShareBasisPE.test_msft_dividend_drift_with_no_split_does_not_refuse",
     "the expected dividend contribution is MEASURED from divCash, never forced to 1.0"),
    ("splitfactor-02", "microservice/macro_prices.py",
     "    eps_today_basis = eps_as_filed / factor",
     "    eps_today_basis = eps_as_filed / 1.0",
     "test_historical_stand.TestSameShareBasisPE.test_pe_matches_a_manual_calculation_across_a_confirmed_split",
     "price and EPS are reconciled onto the MEASURED split factor, not a hardcoded 1"),
    # ---- issue #20: wire the historical-reconstruction stand to HTTP (the #18 audit's finding
    # that as_of/roe_median_5y/pe_same_share_basis were computed but reached no caller) ----
    ("route-asof-01", "microservice/app.py",
     'result = edgar_facts(body.get("ticker"), body.get("cik"), as_of)',
     'result = edgar_facts(body.get("ticker"), body.get("cik"))',
     "test_historical_stand_routes.TestEdgarFactsRouteAsOf.test_as_of_in_the_request_body_reaches_edgar_facts_and_filters_the_result",
     "as_of in the /edgar_facts POST body actually reaches edgar_facts() and filters the result"),
    ("route-asof-type-01", "microservice/app.py",
     '    if as_of is not None and not isinstance(as_of, str):',
     '    if False:',
     "test_historical_stand_routes.TestEdgarFactsRouteAsOf.test_as_of_wrong_type_is_a_named_refusal_not_a_500",
     "a non-string as_of is refused by name instead of 500ing the /edgar_facts route"),
    ("route-price-01", "microservice/app.py",
     "    pe = pe_same_share_basis(price_record, eps, errors, symbol=ticker, daily_rows=daily_rows)",
     "    pe = None",
     "test_historical_stand_routes.TestPriceOnDateRoute.test_route_returns_price_split_factor_and_same_basis_pe_for_a_confirmed_split",
     "/price_on_date actually computes and publishes pe_same_share_basis, not a stub"),
    ("route-price-type-01", "microservice/app.py",
     '    if eps is not None and (not isinstance(eps, (int, float)) or isinstance(eps, bool)):',
     '    if False:',
     "test_historical_stand_routes.TestPriceOnDateRoute.test_eps_wrong_type_is_a_named_refusal_not_a_500",
     "a string eps is refused by name instead of 500ing the /price_on_date route"),
    ("roe-insufficient-01", "microservice/edgar_facts.py",
     '    if len(ends) < 3:\n        return None, {"roe_not_computable": "insufficient_history", "years_available": len(ends)}',
     '    if False:\n        return None, {"roe_not_computable": "insufficient_history", "years_available": len(ends)}',
     "test_edgar_facts.TestEquityAndRoe.test_fewer_than_three_years_refuses_insufficient_history",
     "fewer than 3 overlapping annual points refuses ROE by name, not a computed number"),
    ("equity-fallback-01", "microservice/edgar_facts.py",
     "    if not eq_series:\n        eq_series, eq_tag = _annual_instant_series(facts, EQUITY_TAGS_FALLBACK)\n        eq_combined = bool(eq_series)",
     "    if False:\n        eq_series, eq_tag = _annual_instant_series(facts, EQUITY_TAGS_FALLBACK)\n        eq_combined = bool(eq_series)",
     "test_edgar_facts.TestEquityAndRoe.test_stockholders_equity_falls_back_to_combined_tag_with_a_flag",
     "the combined-basis equity tag is used, and flagged, when the primary tag is absent"),
    ("asof-splits-companyconcept-01", "microservice/edgar_facts.py",
     "                if as_of:\n"
     "                    # companyconcept is a separate fetch, unfiltered by the caller's as_of --\n"
     "                    # apply the same cutoff here or a restatement filed after as_of leaks in.\n"
     "                    concept_units = _filter_units_as_of(concept_units, as_of)",
     "                if False:\n"
     "                    concept_units = _filter_units_as_of(concept_units, as_of)",
     "test_edgar_facts.TestAsOfCompanyconceptLeg.test_as_of_filters_the_companyconcept_leg_of_confirmed_splits",
     "as_of also filters the companyconcept leg of _detect_confirmed_splits, not just companyfacts"),
    ("asof-shares-companyconcept-01", "microservice/edgar_facts.py",
     "        if as_of:\n            units = _filter_units_as_of(units, as_of)",
     "        if False:\n            units = _filter_units_as_of(units, as_of)",
     "test_edgar_facts.TestAsOfCompanyconceptLeg.test_as_of_filters_the_companyconcept_leg_of_shares_current",
     "as_of also filters the companyconcept leg of _shares_current, not just companyfacts"),
    # ---- issue #24: composite splits + dividend admixture broke the single-day ratio ----
    ("splitfactor-03", "microservice/macro_prices.py",
     "    return product, None",
     "    return ratio, None",
     "test_historical_stand.TestSameShareBasisPE.test_compound_split_with_dividend_admixture_gives_the_exact_product_and_a_correct_pe",
     "the splitFactor PRODUCT wins over the dividend-contaminated close/adjClose ratio"),
    # ---- issue #28: Счёт проверки №1 (tools/historical_run.py) ----
    # Acceptance mandate: "подмена официального счёта теневым обязана краснеть" — the shadow
    # (EXPLORATORY, decision В4) DCF bridge must never be able to silently become the published
    # official number.
    ("histrun-shadow-swap-01", "tools/historical_run.py",
     '        intrinsic_value=verdict_leg["intrinsic_value"],   # OFFICIAL — never the shadow leg',
     '        intrinsic_value=shadow["intrinsic_value"],   # OFFICIAL — never the shadow leg',
     "test_historical_run.TestGoldenCase1CleanNoSplitNoBuy.test_full_pipeline_matches_hand_computed_arithmetic",
     "the official IV is never silently replaced by the shadow (EXPLORATORY) DCF leg"),
    # Acceptance mandate: "отключение отказа (подстановка вместо отказа) обязано краснеть" —
    # a pair with no trading-day record on the archived date must refuse, never guess a nearby
    # day or fall through to a bogus computation.
    ("histrun-standref-disabled-01", "tools/historical_run.py",
     "    if price_record is None:",
     "    if False:",
     "test_historical_run.TestNegativeControlsRefuseByName.test_no_trading_day_on_record_refuses_not_a_guess_at_the_nearest_day",
     "a missing trading-day record is refused by name, never silently passed through"),
    ("histrun-growth-refusal-disabled-01", "tools/historical_run.py",
     "    if rc3 is None or rc5 is None:",
     "    if False:",
     "test_historical_run.TestGrowthAnchor.test_refuses_by_name_when_history_too_short_for_either_window",
     "insufficient revenue history for the growth anchor is refused by name, not computed anyway"),
    ("histrun-roe-refusal-disabled-01", "tools/historical_run.py",
     "    if roe_capped <= g:",
     "    if False:",
     "test_historical_run.TestTerminalMultiple.test_refuses_by_name_when_capped_roe_at_or_below_terminal_growth",
     "a terminal ROE at/below terminal growth (undefined payout) is refused, not saturated to a negative multiple"),
    ("histrun-basis-bypass-01", "tools/historical_run.py",
     '    eps_today, eps_factor = basis_adjust(eps_af, split_factor, split_factor_reason, perrors, ticker + "_eps")',
     "    eps_today, eps_factor = eps_af, 1.0",
     "test_historical_run.TestGoldenCase2SplitAndRoeCapBuy.test_full_pipeline_matches_hand_computed_arithmetic",
     "PREREG §7's stand-health check: the EPS leg is never fed to ivc() on its as-filed share basis"),
    # ---- issue #28 audit round 2: two more mandate-required mutation cases ----
    ("histrun-basis-bypass-02", "tools/historical_run.py",
     '    fcf_today, fcf_factor = basis_adjust(fcf_af, split_factor, split_factor_reason, perrors, ticker + "_fcf")',
     "    fcf_today, fcf_factor = fcf_af, 1.0",
     "test_historical_run.TestFcfBasisAdjustAppliedToPublishedIv.test_published_iv_and_split_factor_use_the_adjusted_fcf",
     "PREREG §7's stand-health check applies to the FCF leg too: it is never fed to ivc() on its as-filed share basis"),
    ("histrun-histmedian-flip-01", "tools/historical_run.py",
     "    if pe_hist_median is not None and pe_hist_median < multiple:",
     "    if pe_hist_median is not None and pe_hist_median > multiple:",
     "test_historical_run.TestTerminalMultiple.test_historical_median_wins_when_below_the_formula_ceiling",
     "PREREG §8: the historical median only overrides the formula ceiling when it is BELOW it, never above"),
    # ---- issue #28 audit round 3 ----
    ("histrun-conservative-flip-01", "tools/historical_run.py",
     '        conservative = ("gaap_eps" if usable["gaap_eps"]["implied_cagr_pct"] <=\n'
     '                        usable["fcf_per_share"]["implied_cagr_pct"] else "fcf_per_share")',
     '        conservative = ("gaap_eps" if usable["gaap_eps"]["implied_cagr_pct"] >=\n'
     '                        usable["fcf_per_share"]["implied_cagr_pct"] else "fcf_per_share")',
     "test_historical_run.TestConservativeLegSelectionPicksTheLowerCagr.test_fcf_leg_wins_when_it_is_the_more_conservative_one",
     "the conservative leg is the one with the LOWER implied CAGR, never the higher one"),
    # ---- issue #30: first real run scored 0/175 on "edgar archive record has no usable 'cik'
    # field" -- the archive carries '_cik', not 'cik'. Both mutations below revert score_pair()
    # to the pre-fix reading and must turn the REAL-archive pin (not a synthetic fixture) red. ----
    ("histrun-real-cik-underscore-01", "tools/historical_run.py",
     '    cik = gt.get("_cik") or gt.get("cik")',
     '    cik = gt.get("cik")',
     "test_historical_run.TestRealArchiveFixtureNVDA.test_nvda_20200323_reaches_scored_with_numbers",
     "the REAL archive's own '_cik' field is read, not just the legacy bare 'cik'"),
    ("histrun-real-price-shape-01", "tools/historical_run.py",
     '    price_record = price_json.get("price_record")',
     "    price_record = price_json",
     "test_historical_run.TestRealArchiveFixtureNVDA.test_nvda_20200323_reaches_scored_with_numbers",
     "the archived price record is read from price_json['price_record'], never assumed to BE "
     "the OHLC record itself"),
    # ---- issue #32: filename date must be checked against the archive's OWN dates, not trusted
    # alone -- a desynced archive would otherwise score silently under the wrong date. ----
    ("histrun-asof-sync-disabled-01", "tools/historical_run.py",
     '    if gt_as_of != date_iso:',
     '    if False:',
     "test_historical_run.TestArchiveDateSyncedWithAsOfAndPriceDate.test_as_of_mismatch_refuses_with_both_dates_named",
     "the filename date is checked against the archive record's own _as_of, never trusted alone"),
    ("histrun-asof-null-disabled-01", "tools/historical_run.py",
     '    if gt_as_of is None:',
     '    if False:',
     "test_historical_run.TestArchiveDateSyncedWithAsOfAndPriceDate.test_as_of_null_gets_its_own_named_refusal_not_a_mismatch",
     "a null _as_of (e.g. VOO/ETF) gets its own named refusal instead of falling through to the "
     "mismatch check (which would print 'None' as if it were a date) or, worse, to a live score"),
    # v4.2.83 (issue #36's audit tail, issue #33): refreshed for the isinstance-guard split below
    # -- the single combined condition this used to target became TWO separate checks (a missing
    # 'date' field is now its own named refusal, see histrun-price-date-missing-disabled-01), so
    # the old anchor stopped matching and this case started reporting SKIP instead of RED.
    ("histrun-price-date-sync-disabled-01", "tools/historical_run.py",
     '    if price_date[:10] != date_iso:',
     "    if False:",
     "test_historical_run.TestArchiveDateSyncedWithAsOfAndPriceDate.test_price_date_mismatch_refuses_with_both_dates_named",
     "the filename date is checked against the archived price record's own date, never trusted alone"),
    # ---- issue #33 audit tail: a price record with NO 'date' field at all fell through the
    # isinstance guard silently (absence looked identical to "present and agrees") ----
    ("histrun-price-date-missing-disabled-01", "tools/historical_run.py",
     '    if not isinstance(price_date, str):',
     "    if False:",
     "test_historical_run.TestPriceRecordMissingDateFieldRefusesNamed.test_missing_date_field_refuses_by_name",
     "a price record with no 'date' field is a named refusal, never a silently skipped check"),
    # ---- issue #36: the archived split_factor covers [date_iso, today], never [basis_end, today]
    # -- basis_gap_reason() must run on EACH leg before basis_adjust() trusts the archived
    # multiplier, or a split effective between the leg's basis FY end and the observation date
    # (AMZN's real case) silently reproduces the pre-#36 mixed-basis defect on that leg alone. ----
    ("histrun-basisgap-eps-disabled-01", "tools/historical_run.py",
     '        gap = basis_gap_reason(gt, eps_end, date_iso, _value_at(gt.get("shares_diluted"), eps_end), "eps")',
     "        gap = None",
     "test_historical_run.TestBasisGapAmznRefusesNeverTheOldMixedBasisNumber.test_amzn_20221012_refuses_naming_both_dates",
     "the EPS leg's own basis gap (interval the archived split_factor cannot see) is checked, not assumed empty"),
    ("histrun-basisgap-fcf-disabled-01", "tools/historical_run.py",
     '        gap = basis_gap_reason(gt, fcf_end, date_iso, _value_at(gt.get("shares_diluted"), fcf_end), "fcf")',
     "        gap = None",
     "test_historical_run.TestBasisGapAmznRefusesNeverTheOldMixedBasisNumber.test_amzn_20221012_refuses_naming_both_dates",
     "the FCF leg's own basis gap (interval the archived split_factor cannot see) is checked, not assumed empty"),
    # ---- issue #36 audit tail (PR #38): shares_current can itself be a PROXY (edgar_facts.py
    # falls back to the latest annual shares_diluted when no filing's dei cover page is
    # available, flagging _flags.shares_current_proxied) -- that annual figure is exactly as
    # blind to a sub-annual split as the eps/fcf series it exists to check, so the gap check must
    # refuse on the flag alone rather than trust a ratio computed from a degraded witness. ----
    ("histrun-basisgap-proxied-witness-disabled-01", "tools/historical_run.py",
     '    proxied = (gt.get("_flags") or {}).get("shares_current_proxied")',
     "    proxied = None",
     "test_historical_run.TestBasisGapProxiedSharesCurrentRefusesAsDegradedWitness.test_amzn_proxied_refuses_naming_both_dates_and_the_degraded_witness",
     "a proxied (annual, cover-page-unavailable) shares_current is treated as a degraded witness "
     "and refuses by name, never trusted as if it were the real dei cover-page figure"),
    # ---- issue #39: edgar_facts.py's 1% is calibrated on a HOMOGENEOUS same-tag restatement
    # ratio; the shares_current/shares_diluted(basis_end) ratio here is HETEROGENEOUS (instant vs
    # weighted-average) and misses real splits at that tolerance -- the real AMZN_20221012 archive
    # pair (19.7817x vs clean 20x, 1.0917% away) is the case of record. Measured on all 175 real
    # archive pairs: the worst real split is 1.4000% away from its factor, the closest real
    # non-split is PLTR_20211231 at 1.6571% away -- both boundaries of that gap get their own
    # mutation, proving 1.5% is neither too narrow nor too wide, not merely "a number that passes
    # today's fixtures". ----
    ("histrun-tolerance-too-narrow-01", "tools/historical_run.py",
     "_SHARES_CURRENT_GAP_TOLERANCE = 0.015",
     "_SHARES_CURRENT_GAP_TOLERANCE = 0.01",
     "test_historical_run.TestRealArchiveFixtureAMZNRefusesUnderNewTolerance.test_real_amzn_20221012_refuses_naming_both_dates",
     "reverting to edgar_facts.py's homogeneous-pair 1% (the issue's own defect) must miss the "
     "real AMZN_20221012 split (1.0917% away) and let the false BUY back through"),
    # audit follow-up on PR #40: the archive's other two real splits (NVDA, ISRG) named in
    # _SHARES_CURRENT_GAP_TOLERANCE's own comment were unverifiable from the suite until the
    # NVDA_20211231/ISRG_20211231 fixtures landed -- these two cases prove those pins can go red
    # too, not just the AMZN one. NVDA's fcf leg (1.4000% away) is the single worst real split in
    # the whole archive, closer to the OLD 1% boundary than AMZN or ISRG are.
    ("histrun-tolerance-too-narrow-02", "tools/historical_run.py",
     "_SHARES_CURRENT_GAP_TOLERANCE = 0.015",
     "_SHARES_CURRENT_GAP_TOLERANCE = 0.01",
     "test_historical_run.TestBasisGapNvdaRealSplitFires.test_basis_gap_reason_fires_on_both_legs",
     "reverting to the old homogeneous-pair 1% must miss NVDA's fcf leg (1.4000% away, the "
     "archive's single worst real split) even though its eps leg (0.4777% away) still fires"),
    ("histrun-tolerance-too-narrow-03", "tools/historical_run.py",
     "_SHARES_CURRENT_GAP_TOLERANCE = 0.015",
     "_SHARES_CURRENT_GAP_TOLERANCE = 0.01",
     "test_historical_run.TestBasisGapIsrgRealSplitFires.test_basis_gap_reason_fires_on_both_legs",
     "reverting to the old homogeneous-pair 1% must miss the real ISRG_20211231 split (1.0150% "
     "away on both legs)"),
    ("histrun-tolerance-too-wide-01", "tools/historical_run.py",
     "_SHARES_CURRENT_GAP_TOLERANCE = 0.015",
     "_SHARES_CURRENT_GAP_TOLERANCE = 0.02",
     "test_historical_run.TestBasisGapPltrRealDilutionNeverReadsAsASplit.test_basis_gap_reason_does_not_fire_on_either_leg",
     "widening past the real archive's closest non-split (PLTR_20211231, 1.6571% away -- ordinary "
     "RSU dilution, no split) must start refusing ordinary pairs by name, the failure mode the "
     "NFLX_20221012 default (issue #36) and this tolerance's own upper bound both exist to avoid"),
    # ---- issue #39 audit round 3, item 2: basis_staleness_reason() must run BEFORE
    # basis_gap_reason() on each leg -- a basis year too old to trust (NVDA's fcf leg, stuck on
    # FY2012 by a capex tag change) is untrustworthy on its own, independent of whether
    # shares_current happens to show a clean split factor. Real case: NVDA_20200323's fcf leg
    # shows NO clean split signature at all (ratio 0.9929x vs the nearest factor -- NVDA had not
    # split as of that date) so basis_gap_reason() alone lets it straight through; only the
    # staleness gate catches it. ----
    ("histrun-stale-fcf-disabled-01", "tools/historical_run.py",
     '        stale = basis_staleness_reason(fcf_end, date_iso, "fcf")',
     "        stale = None",
     "test_historical_run.TestRealArchiveFixtureNVDA.test_nvda_20200323_reaches_scored_with_numbers",
     "disabling the fcf leg's staleness check lets NVDA_20200323's fcf leg (basis FY end "
     "2012-01-29, 2976 days / 8.1 years stale, no clean split signature at this date so "
     "basis_gap_reason() alone never catches it) reach basis_adjust() and flip the pair back to "
     "dual_basis_conservative on a decade-old FCF basis, the exact silent reuse this gate exists "
     "to refuse by name instead"),
    ("histrun-stale-threshold-too-wide-01", "tools/historical_run.py",
     "_STALE_BASIS_THRESHOLD_DAYS = 1095",
     "_STALE_BASIS_THRESHOLD_DAYS = 3000",
     "test_historical_run.TestRealArchiveFixtureNVDA.test_nvda_20200323_reaches_scored_with_numbers",
     "widening past NVDA_20200323's real 2976-day fcf-leg gap must miss that case and let the "
     "decade-stale FY2012 basis back into dual_basis_conservative, the same failure "
     "histrun-stale-fcf-disabled-01 proves for a full disable"),
    ("histrun-stale-threshold-too-narrow-01", "tools/historical_run.py",
     "_STALE_BASIS_THRESHOLD_DAYS = 1095",
     "_STALE_BASIS_THRESHOLD_DAYS = 100",
     "test_historical_run.TestRealArchiveFixtureMSFTStaysScoredUnderNewTolerance.test_real_msft_20211231_stays_scored_with_no_gap_named",
     "narrowing past an ordinary real gap (MSFT_20211231's basis FY end is 184 days before "
     "date_iso -- an unremarkable single-fiscal-year-behind case, not an anomaly) must start "
     "refusing ordinary pairs by name, the same false-positive failure mode "
     "_SHARES_CURRENT_GAP_TOLERANCE's own upper bound exists to avoid for the split-signature "
     "check"),
    # ---- K2 (issue #43): edgartools adapter + goldens MU / INTC / META / GOOG ----
    ('k2-01',
     'microservice/edgar_adapter.py',
     'and str(r["filing_date"]) <= as_of]',
     'and str(r["filing_date"]) < as_of]',
     'test_edgar_adapter.TestSelection.test_k2_01_a_filing_dated_on_the_as_of_day_is_inside_the_slice',
     "the adapter's filing selection includes a filing dated ON the as-of day (inclusive slice)"),
    ('k2-02',
     'microservice/edgar_facts.py',
     'if (f.get("filed") or "") and f.get("filed") <= as_of]',
     'if (f.get("filed") or "") and f.get("filed") < as_of]',
     'test_edgar_adapter.TestGoldens.test_k2_02_MU_2018_10_15_the_10K_filed_that_very_day_is_inside_the_slice',
     'golden MU 2018-10-15: the 10-K filed that day is inside the slice'),
    ('k2-03',
     'microservice/edgar_facts.py',
     'if (f.get("filed") or "") and f.get("filed") <= as_of]',
     'if (f.get("filed") or "")]',
     'test_edgar_adapter.TestGoldens.test_k2_03_INTC_2022_01_25_FY2021_filed_two_days_later_is_outside_the_slice',
     'golden INTC 2022-01-25: FY2021 filed 2022-01-27 is outside the as-of slice'),
    ('k2-04',
     'microservice/edgar_adapter.py',
     'ok = [r for r in listing if r.get("form") in forms and',
     'ok = [r for r in listing if str(r.get("form")).startswith(tuple(forms)) and',
     'test_edgar_adapter.TestSelection.test_k2_04_amendments_are_not_the_annual_filing',
     'a 10-K/A is not the annual filing (exact form match, GOOG 2019-02-06)'),
    ('k2-05',
     'microservice/edgar_adapter.py',
     '    for end, p in periods.items():\n        if p["total"] is None:\n',
     '    for end, p in periods.items():\n        if p["total"] is None and p["classes"]:\n            p["total"] = {"val": sum(c["val"] for c in p["classes"].values())}\n        if p["total"] is None:\n',
     'test_edgar_adapter.TestAggregation.test_k2_05_classes_without_a_consolidated_count_are_published_never_summed',
     'share classes are never summed into a total (diluted)'),
    ('k2-06',
     'microservice/edgar_adapter.py',
     '        if r["unit"] != "shares":\n            ignored["wrong_unit"] += 1\n            continue\n        if r["val"] is None:\n            ignored["null_value"] += 1\n            continue\n        p = periods.setdefault',
     '        if False:\n            ignored["wrong_unit"] += 1\n            continue\n        if r["val"] is None:\n            ignored["null_value"] += 1\n            continue\n        p = periods.setdefault',
     'test_edgar_adapter.TestAggregation.test_k2_06_a_non_share_unit_is_refused_and_counted',
     'a non-share unit is refused and counted, not read as shares'),
    ('k2-07',
     'microservice/edgar_adapter.py',
     '                out["shares_current"] = None\n                out["_refusals"]["shares_current"] = (',
     '                out["_refusals"]["shares_current"] = (',
     'test_edgar_adapter.TestGoldens.test_k2_07_META_reads_on_all_five_check1_dates_without_a_substitution',
     'golden META x5: the weighted-average proxy is replaced by a named refusal, not kept as shares_current'),
    ('k2-08',
     'microservice/requirements.txt',
     'edgartools==5.48.0',
     'edgartools>=5.39.1',
     'test_edgar_adapter.TestPinAndFixtures.test_k2_08_edgartools_is_pinned_exactly_and_matches_the_adapter',
     "edgartools is pinned with == to the adapter's version"),
    ('k2-09',
     'microservice/edgar_adapter.py',
     '    for end, p in periods.items():\n        if p["total"] is None:\n',
     '    for end, p in periods.items():\n        if p["total"] is None and p["classes"]:\n            p["total"] = {"val": sum(c["val"] for c in p["classes"].values())}\n        if p["total"] is None:\n',
     'test_edgar_adapter.TestGoldens.test_k2_09_GOOG_reads_on_all_five_check1_dates_with_classes_not_a_total',
     'golden GOOG x5: classes published, no class-sum total anywhere in the output'),
    ('k2-10',
     'microservice/edgar_adapter.py',
     'ANNUAL_DAYS = (350, 380)',
     'ANNUAL_DAYS = (0, 9999)',
     'test_edgar_adapter.TestAggregation.test_k2_10_only_annual_durations_are_read',
     'only annual durations feed the annual diluted series'),
    ('k2-11',
     'microservice/edgar_adapter.py',
     'violations = [x for x in filed if x > as_of]',
     'violations = []',
     'test_edgar_adapter.TestConsumer.test_k2_11_the_as_of_check_names_a_fact_filed_after_the_day',
     'the returned as-of check names any fact filed after the as-of day'),
    ('k2-12',
     'microservice/edgar_adapter.py',
     'if cf and f["filing"]["filing_date"] not in cf:',
     'if False:',
     'test_edgar_adapter.TestConsumer.test_k2_12_a_listing_date_that_disagrees_with_companyfacts_is_flagged_loudly',
     "a library filing date that disagrees with SEC's `filed` is flagged loudly"),
    # ---- task 0.6 (issue #55): root tools/ automation, bridge/notify/audit facts/calibration.
    # Paths are relative to this tree and reach the repo-root tools/ through '..'. ----
    ('auto-subject-01', '../tools/mail_bridge.py', 'COMMAND_RE = re.compile(r"^\\s*\\[CONSILIUM-', 'COMMAND_RE = re.compile(r".*\\[CONSILIUM-', 'test_automation_tools.TestBridgeMain.test_only_exact_command_subjects_are_taken_and_nothing_is_touched', 'a [CONSILIUM-x] tag in the MIDDLE of a subject (GitHub notification about the repo) is not a command'),
    ('auto-unseen-01', '../tools/mail_bridge.py', '(SINCE {since} SUBJECT', '(UNSEEN SINCE {since} SUBJECT', 'test_automation_tools.TestBridgeMain.test_only_exact_command_subjects_are_taken_and_nothing_is_touched', 'selection does not depend on the unread flag (a manually-read mail was lost on 2026-10-18)'),
    ('auto-peek-01', '../tools/mail_bridge.py', '"(BODY.PEEK[])"', '"(RFC822)"', 'test_automation_tools.TestBridgeMain.test_only_exact_command_subjects_are_taken_and_nothing_is_touched', 'reading a message never changes its flags'),
    ('auto-dedupe-01', '../tools/mail_bridge.py', 'if (msgid and msgid in ids) or (kind, subject, body_sha(raw, token)) in legacy:', 'if False:', 'test_automation_tools.TestBridgeMain.test_message_id_is_logged_and_second_run_skips', 'an executed command is skipped by Message-ID on the next hourly run'),
    ('auto-dedupe-02', '../tools/mail_bridge.py', 'legacy.add((parts[1], parts[2], kv["body_sha"]))', 'pass', 'test_automation_tools.TestBridgeMain.test_legacy_log_line_without_msgid_dedupes_by_kind_subject_hash', 'pre-0.6 log lines (no Message-ID) still dedupe, so the 7-day window cannot replay old commands'),
    ('auto-red-01', '../tools/mail_bridge.py', '    if failures:\n        L.notify(', '    if False:\n        L.notify(', 'test_automation_tools.TestBridgeMain.test_file_with_no_block_is_red_and_notified_not_silent_green', 'a refused command turns the bridge job RED and notifies'),
    ('auto-flowed-01', '../tools/mail_bridge.py', 'return unflow(text, delsp) if flowed else text', 'return text', 'test_automation_tools.TestFileCommandRealSample.test_crlf_qp_flowed_body_yields_the_exact_file', 'format=flowed soft breaks are reassembled'),
    ('auto-crlf-01', '../tools/mail_bridge.py', 'text = text.replace("\\r\\n", "\\n").replace("\\r", "\\n")', 'text = text', 'test_automation_tools.TestFileCommandRealSample.test_crlf_qp_flowed_body_yields_the_exact_file', 'CRLF is normalised before the fence is searched'),
    ('auto-fence-01', '../tools/mail_bridge.py', 'for i in range(len(lines) - 1, start, -1)', 'for i in range(start + 1, len(lines))', 'test_automation_tools.TestFileCommandRealSample.test_nested_fences_take_the_last_closing_fence', 'a file with its own ``` blocks is not cut at the first inner fence'),
    ('auto-sha-01', '../tools/mail_bridge.py', '        raw = raw.replace(f"AUTH: {token}", "")\n    return hashlib', '        pass\n    return hashlib', 'test_automation_tools.TestBodyShaMatchesOldBridge.test_hash_is_independent_of_the_secret', 'body_sha never depends on the AUTH secret (public journal; offline brute-force of the passphrase)'),
    ('auto-sha-02', '../tools/mail_bridge.py', 'return hashlib.sha256(raw.strip().encode()).hexdigest()[:16]', 'return hashlib.sha256(normalize_body(raw.strip()).encode()).hexdigest()[:16]', 'test_automation_tools.TestBodyShaMatchesOldBridge.test_real_test_b_mail_gives_the_hash_in_the_main_journal', 'body_sha is the OLD bridge hash (no CRLF normalisation): pre-0.6 journal lines still dedupe'),
    ('auto-sha-03', '../tools/mail_bridge.py', 'if (msgid and msgid in ids) or (kind, subject, body_sha(raw, token)) in legacy:', 'if (msgid and msgid in ids) or (kind, subject, body_sha(raw, "")) in legacy:', 'test_automation_tools.TestJournalReplayDoesNotReexecute.test_main_on_journal_copy_executes_nothing_and_creates_no_issue', 'legacy comparison uses the same token-stripped hash, so the 7-day replay executes nothing'),
    ('auto-hdr-01', '../tools/mail_bridge.py', 'except LookupError:', 'except ZeroDivisionError:', 'test_automation_tools.TestBridgeMain.test_only_exact_command_subjects_are_taken_and_nothing_is_touched', 'one mail with an unknown header charset cannot crash the whole bridge run'),
    ('auto-exit-01', '../tools/daily_audit.py', 'print("daily_audit: результат НЕ опубликован -> exit 1")\n        sys.exit(1)', 'print("daily_audit: результат НЕ опубликован -> exit 1")\n        pass', 'test_automation_tools.TestRedJobOnPublishFailure.test_daily_audit_exits_1', 'daily audit: publish()==False ends the process with 1'),
    ('auto-exit-02', '../tools/monthly_audit.py', 'print("monthly_audit: результат НЕ опубликован -> exit 1")\n        sys.exit(1)', 'print("monthly_audit: результат НЕ опубликован -> exit 1")\n        pass', 'test_automation_tools.TestRedJobOnPublishFailure.test_monthly_audit_exits_1', 'monthly audit: publish()==False ends the process with 1'),
    ('auto-exit-03', '../tools/daily_report.py', 'print("daily_report: результат НЕ опубликован -> exit 1")\n        sys.exit(1)', 'print("daily_report: результат НЕ опубликован -> exit 1")\n        pass', 'test_automation_tools.TestRedJobOnPublishFailure.test_daily_report_exits_1', 'daily report: publish()==False ends the process with 1'),
    ('auto-exit-04', '../tools/review_round.py', 'print("review_round: результат НЕ опубликован -> exit 1")\n            sys.exit(1)', 'print("review_round: результат НЕ опубликован -> exit 1")\n            pass', 'test_automation_tools.TestRedJobOnPublishFailure.test_review_round_exits_1', 'review round: publish()==False ends the process with 1'),
    ('auto-exit-05', '../tools/autocommit.py', 'print("autocommit: результат НЕ опубликован -> exit 1")\n        sys.exit(1)', 'print("autocommit: результат НЕ опубликован -> exit 1")\n        pass', 'test_automation_tools.TestRedJobOnPublishFailure.test_publish_or_exit_helper', 'the shared publish_or_exit helper exits 1'),
    ('auto-exit-06', '../tools/daily_audit.py', '    if red:\n        hard = rule_violations(md)\n        L.notify(', '    if False:\n        hard = rule_violations(md)\n        L.notify(', 'test_automation_tools.TestRedJobOnPublishFailure.test_daily_audit_red_still_notifies_before_exiting', 'a RED daily audit reaches Telegram even when publication fails'),
    ('auto-autonotify-01', '../tools/autocommit.py', 'llm_clients.notify(f"[RED] Автокоммит', 'llm_clients.notify(f"Автокоммит', 'test_automation_tools.TestRedJobOnPublishFailure.test_autocommit_validation_failure_notifies', 'a failed autocommit check notifies the operator'),
    ('auto-gemini-01', '../tools/llm_clients.py', 'if e.code == 400 and "temperature" in txt.lower() and "temperature" in body["generationConfig"]:', 'if False:', 'test_automation_tools.TestGeminiTemperature.test_retry_without_temperature_and_meta_says_not_applied', 'a 400 about temperature gets ONE retry without it'),
    ('auto-gemini-02', '../tools/llm_clients.py', 'temp = "not_applied"', 'temp = "0"', 'test_automation_tools.TestGeminiTemperature.test_retry_without_temperature_and_meta_says_not_applied', 'meta_block never claims temp=0 for a call that ran without temperature'),
    ('auto-notify-01', '../tools/llm_clients.py', 'print("WARN: telegram notify failed:", _scrub(repr(e), token))', 'print("WARN: telegram notify failed:", repr(e))', 'test_automation_tools.TestNotify.test_token_never_reaches_the_log_even_when_the_error_contains_it', 'the Telegram token never reaches the log'),
    ('auto-notify-02', '../tools/llm_clients.py', 'if not token or not chat:', 'if False:', 'test_automation_tools.TestNotify.test_no_secrets_warns_and_does_not_raise', 'notify without secrets does not try to send'),
    ('auto-notify-03', '../tools/llm_clients.py', 'if not j.get("ok"):', 'if False:', 'test_automation_tools.TestNotify.test_telegram_not_ok_is_false_not_true', 'a Telegram refusal is not reported as delivered'),
    ('auto-notify-04', '../tools/llm_clients.py', 'msg = text if text.startswith("[Консилиум] ") else "[Консилиум] " + text', 'msg = text', 'test_automation_tools.TestNotify.test_sends_prefixed_text_to_the_bot_endpoint', 'every message starts with the project prefix'),
    ('auto-facts-01', '../tools/audit_facts.py', 'if total is not None and shown < total:', 'if False:', 'test_automation_tools.TestAuditFacts.test_caption_names_truncation', "a truncated sample says so (limit 40 is not '40 failures')"),
    ('auto-facts-02', '../tools/daily_audit.py', '            f"{F.fact_sections(7)}")', '            "")', 'test_automation_tools.TestAuditFacts.test_both_auditor_packets_contain_the_fact_blocks', 'the daily packet carries ruleset/PR/DECISION facts'),
    ('auto-facts-03', '../tools/monthly_audit.py', 'f"{F.fact_sections(30)}\\n\\n"', '""', 'test_automation_tools.TestAuditFacts.test_both_auditor_packets_contain_the_fact_blocks', 'the monthly packet carries ruleset/PR/DECISION facts'),
    # ---- issue #88: known platform limit is not a problem; full DECISION text + missed runs in packets ----
    ('known-actor-01', '../tools/audit_facts.py', '    if run.get("actor") != PLATFORM_LIMIT_BOT:\n        return False', '    if False:\n        return False', 'test_automation_tools.TestKnownPlatformLimit.test_88_each_missing_condition_makes_it_a_problem', "the same failure on a PR not authored by github-actions[bot] (operator's, claude[bot], unknown) stays a problem"),
    ('known-jobs-01', '../tools/audit_facts.py', '    return n == 0', '    return n is None or n == 0', 'test_automation_tools.TestKnownPlatformLimit.test_88_each_missing_condition_makes_it_a_problem', "an unreadable jobs count is not 'jobs are empty': it stays a problem"),
    ('known-wf-01', '../tools/audit_facts.py', 'PLATFORM_LIMIT_WORKFLOWS = ("validate-artifacts", "claude-audit")', 'PLATFORM_LIMIT_WORKFLOWS = ("validate-artifacts", "claude-audit", "tests")', 'test_automation_tools.TestKnownPlatformLimit.test_88_each_missing_condition_makes_it_a_problem', 'only validate-artifacts and claude-audit are the known limit; any other workflow failing is a problem'),
    ('known-branch-01', '../tools/audit_facts.py', '.startswith("auto/")', '.startswith("")', 'test_automation_tools.TestKnownPlatformLimit.test_88_each_missing_condition_makes_it_a_problem', 'only auto/* branches are the known limit'),
    ('known-event-01', '../tools/audit_facts.py', 'if run.get("event") != "pull_request" or not str(', 'if not str(', 'test_automation_tools.TestKnownPlatformLimit.test_88_each_missing_condition_makes_it_a_problem', 'only the pull_request event is the known limit (a push failure is a problem)'),
    ('known-count-01', '../tools/daily_report.py', '    n_problems = len(recent) - len(known)', '    n_problems = len(recent)', 'test_automation_tools.TestKnownPlatformLimit.test_88_the_known_limit_is_in_its_own_section_and_not_counted', "the known limit is not in the 'N problems' count"),
    ('known-telegram-01', '../tools/daily_report.py', '        if F.is_platform_limit(r, jobs_count):', '        if False:', 'test_automation_tools.TestKnownPlatformLimit.test_88_the_telegram_line_is_green_when_only_the_known_limit_failed', 'a day with only the known limit reaches Telegram as green, not as problems'),
    ('known-jobs-02', '../tools/daily_report.py', '    return int(out) if out.isdigit() else None', '    return int(out) if out.isdigit() else 0', 'test_automation_tools.TestKnownPlatformLimit.test_88_each_missing_condition_makes_it_a_problem', "daily_report: a failed jobs query is not 'jobs are empty'"),
    ('known-actor-02', '../tools/audit_facts.py', '"actor": (r.get("actor") or {}).get("login")}', '"actor": "github-actions[bot]"}', 'test_automation_tools.TestKnownPlatformLimit.test_88_runs_api_carries_the_actor', "the run's actor is read from the API, not assumed to be the bot"),
    ('known-mark-01', '../tools/audit_facts.py', 'return " " + PLATFORM_LIMIT_MARK if is_platform_limit(run, count_jobs) else ""', 'return ""', 'test_automation_tools.TestKnownPlatformLimit.test_88_auditor_packets_mark_the_known_limit_and_warn_the_auditor', "the auditor packet marks a known-limit failure as 'not a problem, not a discrepancy'"),
    ('known-mark-02', '../tools/audit_facts.py', '"== ИЗВЕСТНОЕ ОГРАНИЧЕНИЕ ПЛАТФОРМЫ (читать до статусов автоматики) ==', '"== ПРОЧЕЕ (читать до статусов автоматики) ==', 'test_automation_tools.TestKnownPlatformLimit.test_88_auditor_packets_mark_the_known_limit_and_warn_the_auditor', 'the auditor is warned about the known limit before the run statuses'),
    ('pack-missed-01', '../tools/daily_audit.py', 'f"{F.missed_runs_section()}\\n\\n"', '""', 'test_automation_tools.TestKnownPlatformLimit.test_88_auditor_packets_mark_the_known_limit_and_warn_the_auditor', "the daily packet carries the schedule_guard 'missed runs' section"),
    ('pack-missed-02', '../tools/monthly_audit.py', 'f"{F.missed_runs_section()}\\n\\n"', '""', 'test_automation_tools.TestKnownPlatformLimit.test_88_auditor_packets_mark_the_known_limit_and_warn_the_auditor', "the monthly packet carries the schedule_guard 'missed runs' section"),
    ('decision-full-01', '../tools/audit_facts.py', 'f"{text[:shown]}")', 'f"{text.strip().splitlines()[0]}")', 'test_automation_tools.TestKnownPlatformLimit.test_88_decision_text_in_both_packets_is_the_real_file_not_the_front_matter_line', "the packet carries the DECISION text, not its first line ('---')"),
    ('decision-budget-01', '../tools/audit_facts.py', 'shown = min(len(text), max(left, 0))', 'shown = len(text)', 'test_automation_tools.TestKnownPlatformLimit.test_88_the_decision_budget_is_explicit_and_a_cut_is_signed', 'the DECISION budget is enforced'),
    ('decision-sign-01', '../tools/audit_facts.py', 'note = "" if shown == len(text) else " — ТЕКСТ УСЕЧЕН БЮДЖЕТОМ"', 'note = ""', 'test_automation_tools.TestKnownPlatformLimit.test_88_the_decision_budget_is_explicit_and_a_cut_is_signed', 'a DECISION text cut by the budget says so'),
    ('auto-report-01', '../tools/daily_report.py', '.splitlines()[-20:]', '.splitlines()[-5:]', 'test_automation_tools.TestDailyReportFailures.test_each_failed_run_carries_step_and_exactly_the_last_20_log_lines', 'a failed run carries the last 20 log lines'),
    ('auto-report-02', '../tools/daily_report.py', "jobs or 'НЕИЗВЕСТЕН: jobs пусты (startup_failure / ошибка файла workflow)'", "jobs or ''", 'test_automation_tools.TestDailyReportFailures.test_empty_jobs_say_unknown_step_not_blank', 'an unknown failed step is named unknown, not left blank'),
    ('auto-report-03', '../tools/daily_report.py', 'L.notify(f"{today}: всё зелёно" if n_problems == 0 else f"{today}: {n_problems} проблем — см. письмо", L.INFO)', 'L.notify(f"{today}: всё зелёно", L.INFO)', 'test_automation_tools.TestDailyReportFailures.test_telegram_line_reflects_the_report', "the daily Telegram line says 'all green' only when it is"),
    ('auto-credit-01', '../tools/panel_axes.py', 'source = f"fredgraph (attempt {attempt} of 3)"', 'source = "fredgraph"', 'test_automation_tools.TestCreditAxisSource.test_fredgraph_attempt_number_is_logged', 'the credit axis logs which path and which attempt gave the data'),
    ('auto-calib-01', '../tools/calibrate_auditor.py', 'missing = [m for m in (base_model, cand) if not os.path.exists(os.path.join(root, out_path(day, m)))]', 'missing = [base_model, cand]', 'test_automation_tools.TestCalibration.test_second_run_is_a_noop', 'an answered calibration request is not executed again'),
    ("auto-observer-01", "../tools/notify_failure.py", 'name = env.get("WF_NAME") or "НЕИЗВЕСТНЫЙ workflow"', 'name = env.get("WF_NAME") or ""',
     "test_automation_tools.TestFailureObserver.test_missing_name_is_named_unknown_not_blank",
     "a failure notice without a workflow name says the name is unknown, never blank"),
    ("auto-observer-02", "../tools/notify_failure.py", 'ok = L.notify(message(), L.ALARM)', 'ok = True',
     "test_automation_tools.TestFailureObserver.test_main_sends_through_notify",
     "the failure observer actually calls notify"),
    # ---- issue #70: schedule reliability (reserve slots, idempotency, missed-run watchdog)
    ('sched-skip-01', '../tools/daily_report.py', '    if G.skip_if_published("daily-report"):\n        return', '    if False:\n        return', 'test_schedule_guard.TestIdempotentScripts.test_daily_report_published_exits_zero_and_touches_nothing', 'daily-report: a published day => exit 0, no work, no PR, no Telegram'),
    ('sched-skip-02', '../tools/daily_audit.py', '    if G.skip_if_published("daily-audit"):\n        return', '    if False:\n        return', 'test_schedule_guard.TestIdempotentScripts.test_daily_audit_published_exits_zero_and_touches_nothing', 'daily-audit: a published day => exit 0, no LLM call, no PR'),
    ('sched-skip-03', '../tools/monthly_audit.py', '    if G.skip_if_published("monthly-architect-audit"):\n        return', '    if False:\n        return', 'test_schedule_guard.TestIdempotentScripts.test_monthly_audit_published_exits_zero_and_touches_nothing', 'monthly audit: a published month => exit 0, no LLM call, no PR'),
    ('sched-skip-04', '../tools/weekly_digest.py', '    if G.skip_if_published("weekly-digest"):\n        return', '    if False:\n        return', 'test_schedule_guard.TestIdempotentScripts.test_weekly_digest_second_slot_after_a_successful_run_sends_nothing', 'weekly digest: the reserve slot after a sent digest sends no second mail'),
    ('sched-skip-05', '../tools/panel_axes.py', '        if schedule_guard.panel_row_published():', '        if False:', 'test_schedule_guard.TestIdempotentScripts.test_panel_axes_append_skips_without_fetching_any_axis', 'panel_axes --append never reaches the validator with a duplicate week row'),
    ('sched-week-01', '../tools/schedule_guard.py', '        return d - dt.timedelta(days=d.weekday())', '        return d', 'test_schedule_guard.TestPanelWeekKey.test_sunday_reserve_slot_sees_the_saturday_row', 'a Saturday row and the Sunday last slot are the SAME week (ISO week key)'),
    ('sched-week-02', '../tools/schedule_guard.py', 'hit = [w for w in weeks if w and p <= w < end]', 'hit = [w for w in weeks if w and w < end]', 'test_schedule_guard.TestPanelWeekKey.test_previous_weeks_row_does_not_count', "last week's row does not publish this week"),
    ('sched-month-01', '../tools/schedule_guard.py', '    return d.replace(day=1)', '    return d', 'test_schedule_guard.TestWatchdog.test_everything_published_is_quiet_and_exit_zero', "the monthly period is the calendar month: the watchdog finds last month's closed period (else UNKNOWN)"),
    ('sched-fetch-01', '../tools/schedule_guard.py', '    return None if rc == 0 else f"UNAVAILABLE (git fetch origin main)', '    return None if True else f"UNAVAILABLE (git fetch origin main)', 'test_schedule_guard.TestIdempotentScripts.test_unverifiable_main_never_claims_published', 'a failed fetch of main is UNKNOWN, never silently trusted'),
    ('sched-ls-01', '../tools/schedule_guard.py', '    if rc != 0:\n        return None\n    return bool(out.strip())\n\n\ndef list_on_main', '    if rc != 0:\n        return False\n    return bool(out.strip())\n\n\ndef list_on_main', 'test_schedule_guard.TestWatchdog.test_git_error_on_lookup_is_unknown_not_missing', 'a git error is not "the file is absent" (no false MISSING alarm)'),
    ('sched-alert-01', '../tools/schedule_guard.py', '            if row["state"] == MISSING and now - deadline <= NOTIFY_WINDOW:', '            if False:', 'test_schedule_guard.TestWatchdog.test_missing_daily_audit_alerts_with_workflow_name_and_operator_hint', 'an unpublished period raises an alert'),
    ('sched-alert-02', '../tools/schedule_guard.py', 'now - deadline <= NOTIFY_WINDOW:', 'True:', 'test_schedule_guard.TestWatchdog.test_an_old_miss_is_listed_but_not_re_announced_every_day', 'an old miss is not re-announced every day'),
    ('sched-notify-01', '../tools/schedule_guard.py', '            if r["alert"]:\n                L.notify(alert_text(r), L.ALARM)', '            if False:\n                L.notify(alert_text(r), L.ALARM)', 'test_schedule_guard.TestWatchdog.test_missing_daily_audit_alerts_with_workflow_name_and_operator_hint', 'the alert actually reaches Telegram'),
    ('sched-hint-01', '../tools/schedule_guard.py', 'Оператору: Actions → {r[\'name\']} → "\n            f"Run workflow', 'Оператору: см. Actions"\n            f"', 'test_schedule_guard.TestWatchdog.test_sunday_watchdog_alerts_when_the_week_has_no_row', 'the alert tells the operator which workflow to run by hand'),
    ('sched-unk-01', '../tools/schedule_guard.py', 'act = "?" if r["actual"] is None else', 'act = r["actual"] or 0 if r["actual"] is None else', 'test_schedule_guard.TestWatchdog.test_gh_failure_is_unknown_not_green_and_not_a_false_missing', 'an unreadable run count prints "?", never 0'),
    ('sched-unk-02', '../tools/schedule_guard.py', '        unk = [r for r in rows if r["state"] == UNKNOWN]\n        if unk:', '        unk = [r for r in rows if r["state"] == UNKNOWN]\n        if False:', 'test_schedule_guard.TestWatchdog.test_gh_failure_is_unknown_not_green_and_not_a_false_missing', 'an unverifiable source is announced, not swallowed'),
    ('sched-empty-01', '../tools/schedule_guard.py', '        if not act:\n            return NOT_REQUIRED', '        if False:\n            return NOT_REQUIRED', 'test_schedule_guard.TestWatchdog.test_empty_day_is_not_an_alarm_but_is_named', 'an empty day (no report by design) is named, not alarmed'),
    ('sched-grace-01', '../tools/schedule_guard.py', 'if s and s[-1] + GRACE <= now:', 'if s and s[-1] <= now:', 'test_schedule_guard.TestWatchdog.test_watchdog_waits_for_the_last_slot_before_judging_the_week', 'the watchdog does not judge a period whose last slot may still be running'),
    ('sched-card-01', '../tools/schedule_guard.py', ' and p <= _day(FLOOR1_RE.match(n).group(1)) < end]', ']', 'test_schedule_guard.TestPanelWeekKey.test_card_of_another_week_does_not_count', "last week's floor1 card does not publish this week's"),
    ('sched-env-01', '../tools/schedule_guard.py', '        if r["row"]:\n            _set_env(PANEL_ROW_PUBLISHED="1")', '        if r["published"]:\n            _set_env(PANEL_ROW_PUBLISHED="1")', 'test_schedule_guard.TestPanelWeekKey.test_row_present_but_card_missing_runs_the_card_and_not_the_panel', 'a published row with a missing card does NOT re-run the panel (duplicate week)'),
    ('sched-dow-01', '../tools/schedule_guard.py', '    dow_ok = (d.weekday() + 1) % 7 in c["dow"]', '    dow_ok = d.weekday() in c["dow"]', 'test_schedule_guard.TestCronExpansion.test_dow_zero_and_seven_are_both_sunday', "cron weekday 0/7 = Sunday, 6 = Saturday (not python's Monday=0)"),
    ('sched-count-01', '../tools/schedule_guard.py', 'if r["event"] == "schedule"', 'if r["event"] != ""', 'test_schedule_guard.TestWatchdog.test_counts_expected_from_cron_and_actual_from_schedule_events_only', '"было" counts scheduled runs only, not manual dispatches'),
    ('sched-ok-01', '../tools/schedule_guard.py', 'r["conclusion"] == "success" and r["_t"] >= _dt(p)', 'r["conclusion"] != "" and r["_t"] >= _dt(p)', 'test_schedule_guard.TestIdempotentScripts.test_weekly_digest_failed_first_slot_does_not_count_as_sent', 'a FAILED digest run is not "already sent"'),
    ('sched-exit-01', '../tools/schedule_guard.py', '        return 1 if n else 0', '        return 0', 'test_schedule_guard.TestWatchdog.test_sunday_watchdog_alerts_when_the_week_has_no_row', 'the Sunday watchdog job turns red on a missed week'),
    ('bridge-age-01', '../tools/schedule_guard.py', '    if age <= BRIDGE_MAX_AGE:', '    if True:', 'test_schedule_guard.TestBridgeAgeWatchdog.test_older_than_six_hours_alarms_with_hours_action_and_link', 'a bridge older than 6 h raises the alarm'),
    ('bridge-age-02', '../tools/schedule_guard.py', '    if age <= BRIDGE_MAX_AGE:', '    if age < BRIDGE_MAX_AGE:', 'test_schedule_guard.TestBridgeAgeWatchdog.test_exactly_six_hours_is_still_fresh', 'the 6 h threshold is "older than", not "at"'),
    ('bridge-age-03', '../tools/schedule_guard.py', 'ok = [r["_t"] for r in runs if r["conclusion"] == "success"]', 'ok = [r["_t"] for r in runs]', 'test_schedule_guard.TestBridgeAgeWatchdog.test_a_recent_FAILED_run_does_not_make_the_bridge_fresh', 'a failed run is not a successful run: it does not freshen the bridge'),
    ('bridge-age-04', '../tools/schedule_guard.py', '                    if name == "mail-bridge":', '                    if False:', 'test_schedule_guard.TestBridgeAgeWatchdog.test_older_than_six_hours_alarms_with_hours_action_and_link', 'the watchdog applies the age rule to mail-bridge'),
    ('bridge-age-05', '../tools/schedule_guard.py', 'hours, bound = int(age.total_seconds() // 3600), "более "', 'hours, bound = int(age.total_seconds() // 3600), ""', 'test_schedule_guard.TestBridgeAgeWatchdog.test_no_successful_run_in_the_window_alarms_with_a_lower_bound_not_a_made_up_age', 'no success in the window: the age is a lower bound, never stated as exact'),
    ('bridge-age-06', '../tools/schedule_guard.py', '    if r["name"] == "mail-bridge":\n        return r["alert"]\n', '', 'test_schedule_guard.TestBridgeAgeWatchdog.test_older_than_six_hours_alarms_with_hours_action_and_link', 'the bridge alert carries its own text (hours + Actions path + link)'),
    ('bridge-age-07', '../tools/schedule_guard.py', 'BRIDGE_URL = "https://github.com/investzhadrayev-creator/consilium-code/actions/workflows/mail_bridge.yml"', 'BRIDGE_URL = ""', 'test_schedule_guard.TestBridgeAgeWatchdog.test_older_than_six_hours_alarms_with_hours_action_and_link', 'the alarm links to the bridge workflow page'),
    ('bridge-age-08', '../tools/daily_report.py', 'n_problems = n_failed + n_missed + (1 if unresolved else 0)', 'n_problems = n_failed + (1 if unresolved else 0)', 'test_schedule_guard.TestBridgeAgeWatchdog.test_daily_report_carries_the_bridge_alarm_in_its_section_and_counts_it', 'a bridge alarm makes the daily report say "problems", not "all green"'),
    ('bridge-wf-01', '../mailbox/REPORT_2026-10-25_BRIDGE_WORKFLOWS.md', '    types: [completed]', '    types: [requested]', 'test_schedule_guard.TestBridgeWorkflowRun.test_keeps_schedule_and_dispatch_and_adds_workflow_run_on_every_named_workflow', 'the bridge workflow fires on COMPLETION of the daily workflows'),
    ('bridge-wf-02', '../mailbox/REPORT_2026-10-25_BRIDGE_WORKFLOWS.md', 'weekly-digest, calibrate-auditor]', 'weekly-digest]', 'test_schedule_guard.TestBridgeWorkflowRun.test_keeps_schedule_and_dispatch_and_adds_workflow_run_on_every_named_workflow', 'all five named workflows trigger the bridge'),
    ('bridge-wf-03', '../mailbox/REPORT_2026-10-25_BRIDGE_WORKFLOWS.md', "    - cron: '17,47 * * * *'\n  workflow_dispatch:", '  workflow_dispatch:', 'test_schedule_guard.TestBridgeWorkflowRun.test_keeps_schedule_and_dispatch_and_adds_workflow_run_on_every_named_workflow', 'the schedule trigger is kept alongside workflow_run'),
    ('bridge-wf-04', '../mailbox/REPORT_2026-10-25_BRIDGE_WORKFLOWS.md', 'workflows: [daily-report, daily-audit,', 'workflows: [daily-reports, daily-audit,', 'test_schedule_guard.TestBridgeWorkflowRun.test_every_triggering_name_is_the_name_of_a_real_workflow_file', 'a trigger name that matches no real workflow never fires'),
    ('bridge-wf-05', '../mailbox/REPORT_2026-10-25_BRIDGE_WORKFLOWS.md', 'workflows: [daily-report, daily-audit,', 'workflows: [mail-bridge, daily-report, daily-audit,', 'test_schedule_guard.TestBridgeWorkflowRun.test_the_bridge_does_not_trigger_itself', 'the bridge is not its own trigger (no loop)'),
    ('sched-digest-01', '../tools/weekly_digest.py', 'panel = G.panel_parts(p)["row"]', 'panel = (G.PUBLISHED, "n/a")', 'test_schedule_guard.TestIdempotentScripts.test_weekly_digest_names_a_missing_panel_instead_of_showing_last_weeks_row', "the digest does not pass last week's panel row off as this week's"),
    ('sched-report-01', '../tools/daily_report.py', 'n_problems = n_failed + n_missed + (1 if unresolved else 0)', 'n_problems = n_failed + (1 if unresolved else 0)', 'test_schedule_guard.TestWatchdog.test_daily_report_carries_the_section_and_counts_missing_as_problems', 'a missed run turns the daily "all green" line into a problem count'),
    ('sched-report-02', '../tools/daily_report.py', '\\n\\n{missed}")', '")', 'test_schedule_guard.TestWatchdog.test_daily_report_carries_the_section_and_counts_missing_as_problems', 'the report carries the "Пропущенные запуски" section'),
    ('sched-cron-01', '../mailbox/REPORT_2026-10-19_SCHEDULE_WORKFLOWS.md', "- cron: '7 5 * * 6'     # суббота, основной слот", "- cron: '0 5 * * 6'     # суббота, основной слот", 'test_schedule_guard.TestDeliveredWorkflows.test_no_cron_on_a_peak_minute', 'no delivered cron sits on :00/:15/:30/:45'),
    ('sched-cron-02', '../mailbox/REPORT_2026-10-19_SCHEDULE_WORKFLOWS.md', "- cron: '17,47 * * * *'", "- cron: '17 * * * *'", 'test_schedule_guard.TestDeliveredWorkflows.test_slot_counts_match_the_issue', 'mail-bridge keeps its reserve slot every hour'),
    ('sched-cron-03', '../mailbox/REPORT_2026-10-19_SCHEDULE_WORKFLOWS.md', "- cron: '7 16 * * *'    # основной слот, 21:07 Астана, после отчёта (15:37)", "- cron: '7 15 * * *'    # основной слот, 21:07 Астана, после отчёта (15:37)", 'test_schedule_guard.TestDeliveredWorkflows.test_report_runs_before_audit_in_every_slot_pair', 'the audit never runs before the report in the same slot pair'),
    ('sched-cron-04', '../mailbox/REPORT_2026-10-19_SCHEDULE_WORKFLOWS.md', "    - cron: '7 5 * * 0'     # воскресенье", "    - cron: '7 5 * * 3'     # воскресенье", 'test_schedule_guard.TestDeliveredWorkflows.test_panel_slots_are_saturday_x4_and_sunday_x1', 'panel keeps 4 Saturday slots + the Sunday last slot'),
    ('sched-wf-01', '../mailbox/REPORT_2026-10-19_SCHEDULE_WORKFLOWS.md', "(чёт→OpenAI, нечет→Gemini)\n        if: env.ALREADY_PUBLISHED != '1'\n", '(чёт→OpenAI, нечет→Gemini)\n', 'test_schedule_guard.TestDeliveredWorkflows.test_every_guarded_workflow_calls_the_guard_before_the_work_and_gates_it', 'the delivered daily-audit workflow gates its work on the guard'),
    ('sched-wf-02', '../mailbox/REPORT_2026-10-19_SCHEDULE_WORKFLOWS.md', 'run: python3 tools/schedule_guard.py watch --only panel-weekly --notify', 'run: python3 tools/schedule_guard.py watch --only panel-weekly', 'test_schedule_guard.TestDeliveredWorkflows.test_watchdog_slot_is_after_last_panel_slot_plus_grace', 'the Sunday watchdog notifies Telegram'),
    ('sched-wf-03', '../mailbox/REPORT_2026-10-19_SCHEDULE_WORKFLOWS.md', 'workflows: [mail-bridge, daily-audit, monthly-architect-audit, daily-report, review-round, panel-weekly, calibrate-auditor, weekly-digest, schedule-watchdog]', 'workflows: [mail-bridge, daily-audit, monthly-architect-audit, daily-report, review-round, panel-weekly, calibrate-auditor]', 'test_schedule_guard.TestDeliveredWorkflows.test_failure_observer_watches_the_new_workflows', 'the failure observer watches the new digest + watchdog workflows'),
    # ---- issue #92: Telegram importance levels, operator-PR reminder, bridge NOTIFY prefixes
    ('lvl-01', '../tools/llm_clients.py', '"parse_mode": "HTML", "disable_notification": False}', '"parse_mode": "HTML", "disable_notification": True}', 'test_notify_levels.TestLevelsOnTheWire.test_action_is_loud_with_bold_first_line', 'an ACTION message makes a sound'),
    ('lvl-02', '../tools/llm_clients.py', '"text": msg[:TG_LIMIT], "disable_notification": True}', '"text": msg[:TG_LIMIT], "disable_notification": False}', 'test_notify_levels.TestLevelsOnTheWire.test_info_is_silent_and_is_the_default', 'an INFO message is silent'),
    ('lvl-03', '../tools/llm_clients.py', 'esc = html.escape(msg, quote=False)\n    if len(esc) <= budget:', 'esc = msg\n    if len(esc) <= budget:', 'test_notify_levels.TestLevelsOnTheWire.test_html_in_the_text_is_escaped_and_cannot_inject_markup', 'text in a loud message is HTML-escaped'),
    ('lvl-04', '../tools/llm_clients.py', 'LEVEL_HEADERS = {ACTION: "🔴 НУЖНО ВАШЕ РЕШЕНИЕ", ALARM: "🟠 ТРЕВОГА"}', 'LEVEL_HEADERS = {ACTION: "🔴 НУЖНО ВАШЕ РЕШЕНИЕ", ALARM: "🔴 НУЖНО ВАШЕ РЕШЕНИЕ"}', 'test_notify_levels.TestLevelsOnTheWire.test_alarm_is_loud_with_bold_first_line', 'ALARM and ACTION are told apart by their header'),
    ('lvl-05', '../tools/llm_clients.py', '    if level not in (ACTION, ALARM, INFO):\n        raise ValueError', '    if False:\n        raise ValueError', 'test_notify_levels.TestLevelsOnTheWire.test_unknown_level_is_refused_by_name_not_downgraded_to_info', 'an unknown level is refused, not silently downgraded'),
    ('lvl-06', '../tools/llm_clients.py', 'esc = html.escape(msg[:n], quote=False) + TRUNC_MARK', 'esc = html.escape(msg, quote=False)[:budget]', 'test_notify_levels.TestLevelsOnTheWire.test_overlong_loud_text_is_cut_before_escaping_never_inside_an_entity', 'an overlong loud message is cut before escaping, never inside an entity'),
    ('lvl-08', '../tools/daily_audit.py', 'L.ALARM if hard else L.INFO)', 'L.ALARM)', 'test_notify_levels.TestCallersPickTheLevel.test_red_audit_without_a_listed_violation_is_info_not_alarm', 'a RED audit with no listed rule violation is not an alarm'),
    ('lvl-09', '../tools/daily_audit.py', 'L.ALARM if hard else L.INFO)', 'L.INFO)', 'test_notify_levels.TestCallersPickTheLevel.test_red_audit_with_a_rule_violation_is_an_alarm', 'a confirmed rule violation is an alarm'),
    ('lvl-10', '../tools/daily_audit.py', 'if "ПОДТВЕРЖДАЮ НАРУШЕНИЕ" not in ln or "КЛАСС:" not in ln:', 'if "КЛАСС:" not in ln:', 'test_notify_levels.TestCallersPickTheLevel.test_red_audit_without_a_listed_violation_is_info_not_alarm', 'a retraction (ОТЗЫВАЮ) never counts as a confirmed violation'),
    ('lvl-11', '../tools/notify_failure.py', 'ok = L.notify(message(), L.ALARM)', 'ok = L.notify(message(), L.INFO)', 'test_notify_levels.TestCallersPickTheLevel.test_failed_job_observer_is_an_alarm', 'a failed automation job is an alarm'),
    ('lvl-12', '../tools/autocommit.py', '(ветка {branch})", llm_clients.ALARM)', '(ветка {branch})", llm_clients.INFO)', 'test_notify_levels.TestCallersPickTheLevel.test_failed_autocommit_check_is_an_alarm', 'a failed autocommit check is an alarm'),
    ('lvl-13', '../tools/daily_report.py', 'всё зелёно" if n_problems == 0 else f"{today}: {n_problems} проблем — см. письмо", L.INFO)', 'всё зелёно" if n_problems == 0 else f"{today}: {n_problems} проблем — см. письмо", L.ALARM)', 'test_notify_levels.TestCallersPickTheLevel.test_daily_report_line_is_info', 'the daily report line is silent INFO'),
    ('op-01', '../tools/operator_prs.py', 'return login not in BOT_LOGINS or MARK in (pr.get("title") or "")', 'return login not in BOT_LOGINS', 'test_notify_levels.TestOperatorReminder.test_sees_operator_prs_and_ignores_auto_prs', 'a bot PR titled [ТРЕБУЕТ ОДОБРЕНИЯ ОПЕРАТОРА] is still the operator\'s'),
    ('op-02', '../tools/operator_prs.py', 'return login not in BOT_LOGINS or MARK in (pr.get("title") or "")', 'return True', 'test_notify_levels.TestOperatorReminder.test_sees_operator_prs_and_ignores_auto_prs', 'auto-PRs are not reminded about'),
    ('op-03', '../tools/operator_prs.py', 'return login not in BOT_LOGINS or MARK in (pr.get("title") or "")', 'return MARK in (pr.get("title") or "")', 'test_notify_levels.TestOperatorReminder.test_sees_operator_prs_and_ignores_auto_prs', 'a human/claude PR is the operator\'s even without the title marker'),
    ('op-04', '../tools/operator_prs.py', '    if not mine:\n        print(', '    if False:\n        print(', 'test_notify_levels.TestOperatorReminder.test_nothing_waiting_sends_nothing', 'no operator PRs -> no message'),
    ('op-05', '../tools/operator_prs.py', 'if len(out) == n:', 'if len(out) == n + 1:', 'test_notify_levels.TestOperatorReminder.test_message_carries_title_three_block_lines_days_and_link', 'the reminder carries exactly the first 3 lines of the operator block'),
    ('op-06', '../tools/operator_prs.py', 'return max(0, (now - created).days)', 'return 0', 'test_notify_levels.TestOperatorReminder.test_repeats_every_day_while_the_pr_is_open_with_growing_wait', 'the reminder says how many days the PR has waited'),
    ('op-07', '../tools/operator_prs.py', '    if prs is None:\n        L.notify(', '    if False:\n        L.notify(', 'test_notify_levels.TestOperatorReminder.test_unreadable_pr_list_is_an_alarm_not_silence', 'an unreadable PR list is an alarm, not "no PRs"'),
    ('op-08', '../tools/operator_prs.py', 'ok = L.notify(message(mine, now), L.ACTION)', 'ok = L.notify(message(mine, now), L.INFO)', 'test_notify_levels.TestOperatorReminder.test_sees_operator_prs_and_ignores_auto_prs', 'the PR reminder is an ACTION'),
    ('op-09', '../tools/operator_prs.py', 'return NO_BLOCK\n\ndef days_waiting', 'return ""\n\ndef days_waiting', 'test_notify_levels.TestOperatorReminder.test_pr_without_the_block_says_so_instead_of_inventing_a_summary', 'a PR with no operator block says so'),
    ('op-10', '../tools/daily_report.py', '    _, remind_err = OP.remind()\n', '    remind_err = None\n', 'test_notify_levels.TestOperatorReminder.test_daily_report_sends_the_reminder_even_on_a_quiet_day', 'daily_report sends the operator-PR reminder'),
    ('op-11', '../tools/daily_report.py', '+ (1 if remind_err else 0)', '+ 0', 'test_notify_levels.TestOperatorReminder.test_unreadable_pr_list_counts_as_a_problem_in_the_daily_line', 'a failed reminder turns the daily "all green" into a problem count'),
    ('bridge-01', '../tools/mail_bridge.py', 'if first in ("!ACTION", "!ALARM"):', 'if first in ("!ACTION",):', 'test_notify_levels.TestBridgeLevels.test_notify_subject_prefix_selects_the_level', '!ALARM in a NOTIFY subject selects ALARM'),
    ('bridge-02', '../tools/mail_bridge.py', 'return first[1:], tail.strip()', 'return L.INFO, tail.strip()', 'test_notify_levels.TestBridgeLevels.test_notify_subject_prefix_selects_the_level', '!ACTION in a NOTIFY subject selects ACTION'),
    ('bridge-03', '../tools/mail_bridge.py', 'if not L.notify(text, level):', 'if not L.notify(text):', 'test_notify_levels.TestBridgeLevels.test_notify_command_through_main_reaches_telegram_loud', 'do_notify passes the level to Telegram'),
    ('bridge-04', '../tools/mail_bridge.py', 'f"{repo_url()}/pull/{n}", L.ACTION)', 'f"{repo_url()}/pull/{n}", L.INFO)', 'test_notify_levels.TestBridgeLevels.test_refused_merge_of_a_protected_pr_asks_the_operator', 'a bridge refusal to merge asks the operator loudly'),
    ('bridge-05', '../tools/mail_bridge.py', '"; ".join(f[:120] for f in failures[:3]), L.ALARM)', '"; ".join(f[:120] for f in failures[:3]), L.INFO)', 'test_notify_levels.TestBridgeLevels.test_bridge_failure_summary_is_an_alarm', 'unexecuted bridge commands are an alarm'),
    ('bridge-06', '../tools/mail_bridge.py', '"--body", operator_pr_body(content)],', '"--body", "Файл правил от архитектора. Merge — только оператор."],', 'test_notify_levels.TestBridgeLevels.test_protected_file_pr_created_by_the_bridge_carries_the_block_and_asks_the_operator', 'bridge PRs carry the operator block'),

    # ---- issue #105: the panel row is published even when the floor-1 card fails ----
    ('all-wf-01', '../mailbox/REPORT_2026-10-26_ALL_WORKFLOWS.md', "        if: always() && env.ALREADY_PUBLISHED != '1'\n        env:\n          GH_TOKEN", "        if: env.ALREADY_PUBLISHED != '1'\n        env:\n          GH_TOKEN", 'test_schedule_guard.TestPanelPublishesWithoutTheCard.test_publish_runs_even_when_an_earlier_step_failed', 'the panel row is published even when the card step failed'),
    ('all-wf-02', '../mailbox/REPORT_2026-10-26_ALL_WORKFLOWS.md', "        id: card\n        if: env.FLOOR1_PUBLISHED != '1'\n        continue-on-error: true", "        id: card\n        if: env.FLOOR1_PUBLISHED != '1'", 'test_schedule_guard.TestPanelPublishesWithoutTheCard.test_a_failing_card_or_dependency_step_does_not_stop_the_job', 'a failing card step does not abort the job before publication'),
    ('all-wf-03', '../mailbox/REPORT_2026-10-26_ALL_WORKFLOWS.md', "        if: always() && (steps.deps.outcome == 'failure' || steps.card.outcome == 'failure')", "        if: always() && (steps.deps.outcome == 'failure')", 'test_schedule_guard.TestPanelPublishesWithoutTheCard.test_card_failure_is_an_alarm_and_a_red_job_AFTER_publication', 'a card failure triggers the alarm/red-job step'),
    ('all-wf-04', '../mailbox/REPORT_2026-10-26_ALL_WORKFLOWS.md', '          exit 1', '          exit 0', 'test_schedule_guard.TestPanelPublishesWithoutTheCard.test_card_failure_is_an_alarm_and_a_red_job_AFTER_publication', 'the job goes red after a card failure (not a silent green)'),
    ('all-wf-05', '../mailbox/REPORT_2026-10-26_ALL_WORKFLOWS.md', '          WF_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}\n        run: |\n          python3 tools/notify_failure.py || echo', '          WF_URL: x\n        run: |\n          echo ${{ github.run_id }}; python3 tools/notify_failure.py || echo', 'test_schedule_guard.TestPanelPublishesWithoutTheCard.test_alarm_data_travels_through_env_not_shell_interpolation', 'alarm data is passed via env, not interpolated into the shell'),
    # ---- K1 (issues #44/#90): floor1 card ----
    ('f1-01',
     '../tools/floor1_card.py',
     '    if series[-1]["end"] != fy:',
     '    if False:',
     'test_floor1_card.TestProperties.test_f1_14_current_refuses_a_series_that_ends_before_the_card_year',
     'a series ending before the card fiscal year is refused (STALE_SERIES), not shown as latest'),
    ('f1-02',
     '../tools/floor1_card.py',
     '    fcf = fcf_series(ocf_c, capex_c)\n',
     '    fcf = fcf_series(ocf_c, capex_c) or [{"end": r["end"], "val": r["val"], "accn": [r.get("accn")]} for r in (ocf_c or [])]\n',
     'test_floor1_card.TestMissingIsNotZero.test_f1_11_ocf_without_capex_gives_no_fcf',
     'OCF is not substituted for FCF when capex is missing'),
    ('f1-03',
     '../tools/floor1_card.py',
     '        else:\n            continue\n        out.append',
     '        else:\n            debt, accn = nm[end]["val"], [nm[end].get("accn")]\n        out.append',
     'test_floor1_card.TestMissingIsNotZero.test_f1_10_a_noncurrent_debt_without_its_current_part_is_not_a_debt_point',
     'a missing current debt part is not read as zero'),
    ('f1-04',
     '../tools/floor1_card.py',
     '    if hit:\n        return refusal("SPLIT_IN_WINDOW"',
     '    if False:\n        return refusal("SPLIT_IN_WINDOW"',
     'test_floor1_card.TestProperties.test_f1_16_a_confirmed_split_inside_the_window_refuses_the_share_change',
     'share change across a confirmed split is refused'),
    ('f1-05',
     '../tools/floor1_card.py',
     '    if a["val"] <= 0 or b["val"] <= 0:',
     '    if False:',
     'test_floor1_card.TestProperties.test_f1_15_cagr_of_a_non_positive_boundary_is_undefined_not_a_number',
     'CAGR over a non-positive boundary is a named refusal'),
    ('f1-06',
     '../tools/floor1_card.py',
     '    elif "ifrs-full" in taxes and "us-gaap" not in taxes:',
     '    elif False:',
     'test_floor1_card.TestMissingIsNotZero.test_f1_12_foreign_filer_is_named_not_zero_filled',
     'a foreign (IFRS) filer is named, not generic'),
    ('f1-07',
     '../tools/floor1_card.py',
     'as_of=self.as_of, loader=self.loader)',
     'as_of="9999-12-31", loader=self.loader)',
     'test_floor1_card.TestOutputs.test_f1_29_the_run_date_is_the_sec_as_of_handed_to_the_adapter',
     'the run date is the as-of handed to the K2 adapter'),
    ('f1-08',
     '../tools/floor1_card.py',
     'F[name] = ok(t[0] - m[0], "ratio"',
     'F[name] = ok(m[0] - t[0], "ratio"',
     'test_floor1_card.TestProperties.test_f1_20_relative_strength_and_drawdown_on_a_synthetic_tape',
     'RS sign: ticker minus benchmark'),
    ('f1-09',
     '../tools/floor1_card.py',
     'if lo <= d <= as_of}',
     'if d <= as_of}',
     'test_floor1_card.TestProperties.test_f1_20_relative_strength_and_drawdown_on_a_synthetic_tape',
     '52-week drawdown ignores highs older than the window'),
    ('f1-10',
     '../tools/floor1_card.py',
     '    if (_d(as_of) - _d(d1)).days > PRICE_FRESH_DAYS:\n        return None, refusal("PRICE_STALE"',
     '    if False:\n        return None, refusal("PRICE_STALE"',
     'test_floor1_card.TestProperties.test_f1_21_a_stale_last_close_is_refused_not_used',
     'a stale last close is refused for RS'),
    ('f1-11',
     '../tools/floor1_card.py',
     '            if not isinstance(bpx, dict) or not bpx:',
     '            if False:',
     'test_floor1_card.TestProperties.test_f1_22_unavailable_benchmark_or_tiingo_is_named',
     'an unavailable benchmark is named'),
    ('f1-12',
     '../tools/floor1_card.py',
     '    if not token or not (os.environ.get("SEC_USER_AGENT") or "").strip():',
     '    if not token:',
     'test_floor1_card.TestOutputs.test_f1_28_without_credentials_no_card_is_written',
     'no SEC_USER_AGENT -> no card written, exit 2'),
    ('f1-13',
     '../tools/floor1_card.py',
     'if f["state"] != "UNDETERMINED")',
     'if True)',
     'test_floor1_card.TestOutputs.test_f1_26_coverage_counts_only_determined_fields',
     'UNDETERMINED flags do not count as coverage'),
    ('f1-14',
     '../tools/floor1_card.py',
     '        return _und("MISSING_INPUT", why)\n    ni, eps = raw.get("ni")',
     '        return {"state": "CLEAR", "evidence": why}\n    ni, eps = raw.get("ni")',
     'test_floor1_card.TestGoldens.test_f1_05_GOOG_share_classes_are_refused_by_name_not_summed',
     'a flag with a missing input is UNDETERMINED, never CLEAR'),
    ('f1-15',
     '../tools/floor1_card.py',
     'int(m.group(1)) > best[0])',
     'm.group(1) > str(best[0]))',
     'test_floor1_card.TestProperties.test_f1_24_the_newest_tree_is_chosen_by_number_not_by_string',
     'newest tree by number, not string'),
    ('f1-16',
     '../tools/floor1_card.py',
     'repr(f["value"]) if is_ok(f) else "",',
     'repr(f["value"]) if is_ok(f) else "0",',
     'test_floor1_card.TestMissingIsNotZero.test_f1_13_csv_cell_of_a_refused_field_is_empty_with_a_reason',
     'a refused CSV cell is empty, never 0'),
    ('f1-17',
     '../tools/floor1_card.py',
     '(out.get("_refusals") or {}).get("shares_diluted") or sh_ref',
     'sh_ref',
     'test_floor1_card.TestGoldens.test_f1_05_GOOG_share_classes_are_refused_by_name_not_summed',
     'the adapter refusal code (share classes) reaches the card'),
    ('f1-18',
     '../tools/floor1_card.py',
     'last >= max(p["val"] for p in pts) and last > med)',
     'last > med)',
     'test_floor1_card.TestProperties.test_f1_17_cycle_peak_needs_the_max_AND_above_median',
     'CYCLE_PEAK needs the 5-FY max, not just above median'),
    ('f1-19',
     '../tools/floor1_card.py',
     'ni[-1]["val"] > n1["val"] and fcf[-1]["val"] < f1["val"])',
     'ni[-1]["val"] > n1["val"] or fcf[-1]["val"] < f1["val"])',
     'test_floor1_card.TestProperties.test_f1_18_cash_conversion_divergence_is_NI_up_AND_FCF_down',
     'CASH_CONV_DIVERGENCE is NI up AND FCF down'),
    ('f1-20',
     '../tools/floor1_card.py',
     '"RAISED" if (sh < 0 and dn > 0)',
     '"RAISED" if (sh < 0 or dn > 0)',
     'test_floor1_card.TestProperties.test_f1_19_debt_for_buybacks_needs_shrinking_shares_AND_growing_net_debt',
     'DEBT_FOR_BUYBACKS needs both legs'),
    ('f1-21',
     '../tools/floor1_card.py',
     '"RAISED" if (sh < 0 and g_eps > g_ni)',
     '"RAISED" if (g_eps > 0)',
     'test_floor1_card.TestGoldens.test_f1_02_MU_values_and_CYCLE_PEAK_on_the_2018_memory_peak',
     'BUYBACK_EPS requires EPS growth above NI growth (MU shares grew: CLEAR)'),
    ('f1-23',
     '../mailbox/REPORT_2026-10-25_K1_WORKFLOWS.md',
     '          SEC_USER_AGENT: ${{ secrets.SEC_USER_AGENT }}\n',
     '',
     'test_floor1_card.TestWorkflowReport.test_f1_30_card_step_gets_both_secrets_the_script_requires',
     'the delivered workflow gives the card step SEC_USER_AGENT'),
    ('f1-24',
     '../mailbox/REPORT_2026-10-25_K1_WORKFLOWS.md',
     'python3 -m pip install --quiet "$(grep -i \'^edgartools==\' "$req")"',
     'python3 -m pip install --quiet edgartools',
     'test_floor1_card.TestWorkflowReport.test_f1_31_edgartools_is_installed_from_the_requirements_pin_before_the_card',
     'edgartools is installed from the requirements pin, not unpinned'),
    ('k11-01',
     '../tools/floor1_card.py',
     'DEBT_FULL_CHAIN = ["LongTermDebt", "DebtAndCapitalLeaseObligations"]',
     'DEBT_FULL_CHAIN = ["LongTermDebt"]',
     'test_floor1_card.TestTagChainsAndDerivedGrossProfit.test_f1_34_mu_net_debt_comes_from_the_alternative_tag_and_says_which',
     'alternative debt tag chain (tag drift) is read'),
    ('k11-02',
     '../tools/floor1_card.py',
     'len(set(sets)) > 1',
     'False',
     'test_floor1_card.TestTagChainsAndDerivedGrossProfit.test_f1_35_change_across_different_tag_sets_is_marked_mixed',
     'different tags in one change are marked mixed'),
    ('k11-03',
     '../tools/floor1_card.py',
     'c["accn"] == r.get("accn")',
     'True',
     'test_floor1_card.TestTagChainsAndDerivedGrossProfit.test_f1_37_missing_cost_or_report_mismatch_is_a_refusal_never_zero_or_revenue',
     'derived gross profit never joins two reports'),
    ('k11-04',
     '../tools/floor1_card.py',
     'F[k]["derived"] = True',
     'F[k]["derived"] = False',
     'test_floor1_card.TestTagChainsAndDerivedGrossProfit.test_f1_36_derived_gross_profit_carries_both_accessions_from_one_report',
     'derived gross margin is marked derived'),
    ('k11-05',
     '../tools/floor1_card.py',
     'if not is_ok(F["gm_latest"]):        # нет GrossProfit',
     'if True:        # нет GrossProfit',
     'test_floor1_card.TestTagChainsAndDerivedGrossProfit.test_f1_38_reported_gross_profit_wins_and_is_not_marked_derived',
     'reported GrossProfit is not overridden by derivation'),
    ('k11-06',
     '../tools/floor1_card.py',
     'c = cm.get(r["end"])\n        if c and c.get("accn")',
     'c = cm.get(r["end"]) or {"val": 0, "accn": r.get("accn"), "tag": "x"}\n        if c and c.get("accn")',
     'test_floor1_card.TestTagChainsAndDerivedGrossProfit.test_f1_37_missing_cost_or_report_mismatch_is_a_refusal_never_zero_or_revenue',
     'missing cost is a refusal, not zero cost'),
    ('k11-07',
     '../tools/floor1_card.py',
     'nd, nd_ref = current(nd, fy, "net debt (LongTermDebt - Cash)")',
     'nd_ref = None',
     'test_floor1_card.TestMissingIsNotZero.test_f1_08_a_stale_series_is_refused_not_shown_as_the_latest_value',
     'stale net-debt series is refused'),
    ('k11-08',
     '../.github/workflows/panel_weekly.yml',
     '          SEC_USER_AGENT: ${{ secrets.SEC_USER_AGENT }}\n        run: |\n          if [ -f tools/floor1_card.py ]',
     '        run: |\n          if [ -f tools/floor1_card.py ]',
     'test_floor1_card.TestWorkflowReport.test_f1_32_current_main_workflow_card_failure_does_not_cancel_publication',
     'main workflow: card step gets SEC_USER_AGENT'),
    ('k11-09',
     '../.github/workflows/panel_weekly.yml',
     "        if: always() && env.ALREADY_PUBLISHED != '1'",
     "        if: env.ALREADY_PUBLISHED != '1'",
     'test_floor1_card.TestWorkflowReport.test_f1_32_current_main_workflow_card_failure_does_not_cancel_publication',
     'main workflow: publish step has always()'),
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
        # v4.2.83 (mandate 09 §1) — TWO DEFECTS, ONE LINE.
        #
        # (1) Every selector went to `python -m unittest`, including the 56 cases whose selector is
        # a `.js` FILE. unittest cannot import `test_brief_render.js`, so it errored; the error made
        # the return code non-zero; and non-zero is how this function spelled RED. Those 56 printed
        # RED without the mutation being exercised at all. The catalogue said "103 cases, 103 RED"
        # while 47 pins had been probed and 56 had been asserted — and among the unprobed was
        # `d9-01`, the pin whose whole job was to stop `28` being printed for 27.53. The defect
        # walked past its own guard because the guard was never started.
        #
        # (2) The deeper error is reading an EXIT CODE as evidence that a check ran. An exit code is
        # a claim about the process; only a tally is a claim about the checks. So the number of
        # executed checks is now extracted from the selector's OWN output, and zero executed checks
        # is a third state — NOT_EXEC — which is neither a working pin nor an empty one, exactly as
        # SKIP is neither pass nor fail.
        #
        # Same disease, fourth instrument: `test_undef.js` exiting 0 without eslint; the python half
        # of the runner counting self-skips as success; the catalogue printing SKIP as an all-clear;
        # and now the catalogue counting an import error as a pin firing.
        if selector.endswith(".js"):
            p = subprocess.run(["node", os.path.join("tests", selector)], cwd=REPO,
                               capture_output=True, text=True, timeout=180)
            _pat = r"(\d+) passed"
        else:
            p = subprocess.run([sys.executable, "-m", "unittest", selector],
                               cwd=os.path.join(REPO, "tests"),
                               capture_output=True, text=True, timeout=180)
            _pat = r"Ran (\d+) tests?"
        _m = re.search(_pat, (p.stdout or "") + (p.stderr or ""))
        ran = int(_m.group(1)) if _m else 0
        # The negative control required by the mandate found a hole in the first draft of this fix:
        # a python selector that does not exist gives `Ran 1 test ... FAILED`, because unittest
        # SYNTHESISES a `_FailedTest` case to carry the loader error. The tally is therefore
        # non-zero and the loader's own complaint reads as a pin firing — the same lie in a new
        # costume, and the reason the control was demanded rather than assumed.
        if "unittest.loader._FailedTest" in ((p.stdout or "") + (p.stderr or "")):
            ran = 0
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
    if not ran:
        return cid, guards, "NOT_EXEC", "runner reached 0 checks — this pin was NOT probed"
    return cid, guards, ("RED" if red else "GREEN"), "%d checks ran" % ran


def main(argv):
    cases = [c for c in CASES if not argv or c[0] in argv]
    # v4.2.83 (mandate 10 §3). An argv naming no real case filtered the list to nothing, and the
    # function then walked an empty loop, found no GREEN, no SKIP, no NOT_EXEC, and printed
    # "all probed pins went RED" with exit 0. A run that probed NOTHING reported success — the same
    # disease this tool exists to catch, in the tool, one level above where it was just fixed.
    # Found by the pins written for this file under mandate 10, on their first execution.
    if not cases:
        print("NOT VERIFIED — no case matched %r, so nothing was probed." % (argv or "<all>"))
        print("An empty run is not a clean run.")
        return 1
    print("%-12s %-46s %-6s %s" % ("id", "what the pin guards", "result", "note"))
    empty, skipped, unrun = [], [], []
    for c in cases:
        cid, guards, res, note = run_case(c)
        print("%-12s %-44s %-9s %s" % (cid, guards[:44], res, note))
        if res == "GREEN":
            empty.append((cid, guards))
        elif res == "SKIP":
            skipped.append((cid, guards))
        elif res == "NOT_EXEC":
            unrun.append((cid, guards))
    print()
    # v4.2.83 (mandate 09 §1). NOT_EXEC is named FIRST and outranks everything below it. A case
    # whose checks never ran is not even a measurement of emptiness, so it cannot be summarised
    # away by any tally printed after it.
    if unrun:
        print("NOT EXECUTED — the runner reached no checks, so these pins were NOT probed:")
        for cid, g in unrun:
            print("  %s: %s" % (cid, g))
        print("An exit code is a claim about the process; a tally is a claim about the checks.")
        return 1
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
    print("catalogue: %d cases, %d RED, %d SKIP, %d GREEN, %d NOT_EXEC"
          % (len(cases), len(cases) - len(skipped) - len(empty) - len(unrun),
             len(skipped), len(empty), len(unrun)))
    # v4.2.77: a SKIP used to print the all-clear line anyway and exit 0. `SKIP` in this catalogue
    # means the mutation's anchor did not match — the case was never applied, so the pin it targets
    # was never probed. That is a REFUSAL OF THE CHECK, not a neutral outcome (rule 9), and it was
    # printing the same word as a pass. Exactly the disease this repo already cured in run_tests.py,
    # alive here in the tool that certifies the pins. Order matters: the unrun cases are named
    # BEFORE any all-clear, and they outrank it.
    if skipped:
        print("NOT VERIFIED — these cases never applied (anchor did not match), so the pins they "
              "target were not probed:")
        for cid, g in skipped:
            print("  %s: %s" % (cid, g))
        print("A mutation that did not run has proved nothing about its pin.")
        return 1
    print("all probed pins went RED — each can actually fail")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
