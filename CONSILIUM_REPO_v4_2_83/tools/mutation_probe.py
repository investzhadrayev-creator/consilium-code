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
    ("splitfactor-01", "microservice/macro_prices.py",
     '    return None, ("split_factor_undeterminable: close/adjClose ratio %.4f matches no clean "\n'
     '                  "split multiple and is not ~1.0" % ratio)',
     "    return 1.0, None",
     "test_historical_stand.TestSameShareBasisPE.test_undeterminable_split_factor_refuses_never_defaults_to_one",
     "an undeterminable split factor is REFUSED, never silently defaulted to 1"),
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
     "    pe = pe_same_share_basis(price_record, eps, errors, symbol=ticker)",
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
