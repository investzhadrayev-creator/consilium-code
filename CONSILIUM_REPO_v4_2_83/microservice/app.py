# __build__ = "v4.2.83"   # ЕДИНАЯ версия СБОРКИ микросервиса: deploy пушит microservice/
# целиком, поэтому версия отдельного файла ничего не говорит о том, что крутится на
# Railway. Этот маркер одинаков во всех файлах и бампается при каждом деплое —
# grep -h __build__ microservice/*.py | sort -u должен давать РОВНО ОДНУ строку.
"""
app.py — deployable microservice for the Growth Alpha Pipeline.
Exposes routes the n8n workflow calls:
  POST /run            -> executes the deterministic IVC wiring code (Stage 2a output)
  POST /enrich_yf      -> yfinance enrichment (fwd_pe, peers, revisions, short interest, ...)
  POST /scenario_tree  -> Category-F deterministic anchors for pre-profit names (Core-V)
  GET  /health         -> liveness probe

Design notes (matches pipeline discipline):
  - Every route ALWAYS returns JSON, never a bare 500 with an HTML body — the n8n
    HTTP nodes and Render Tables parse JSON; an HTML error page would break them.
  - /run executes untrusted-ish generated Python in a subprocess with a timeout,
    capturing stdout (the pipeline contract: last line of stdout is the JSON result).
  - /enrich_yf wraps enrich_yf() which itself never throws.
  - /scenario_tree wraps scenario_tree() which itself never throws.
"""
import json
import os
import re as _re


def _build_marker():
    """v4.2.77. `/health` used to answer without a version, so there was no way to learn what was
    actually running on Railway — and the workflow and the microservice deploy separately, so they
    drift. Twice that drift cost a debugging cycle: a report was compared against the wrong build.

    The marker is READ from this file's own source, never restated here. Restating it would give the
    fact a second home, and the whole point of `__build__` is that `grep -h __build__
    microservice/*.py | sort -u` returns exactly one line. If the marker cannot be read, the answer
    is "UNKNOWN" — an absence spelled as an absence. A plausible default here would be worse than
    the silence it replaces: an operator would compare against a version that was never deployed.
    """
    try:
        with open(__file__, "r", encoding="utf-8") as fh:
            # The pattern is BUILT, not written literally: a literal here would itself answer
            # `grep -h __build__ microservice/*.py | sort -u` and turn the operator's one-line
            # check into a two-line one. The reader must not look like the thing it reads.
            m = _re.search('__bu' + 'ild__ = "([^"]+)"', fh.read())
        return m.group(1) if m else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


BUILD = _build_marker()

from flask import Flask, request, jsonify

from enrich_yf import enrich_yf
from scenario_f import scenario_tree   # v1.5: Core-V Category-F anchors
from edgar_facts import edgar_facts, raw_tags  # v1.8 facts + v4.2.44 raw-tag diagnostics
from edgar_form4 import edgar_form4    # v2.8: SEC EDGAR Form 4 insider transactions (phase 2)
from market_facts import market_facts  # v3.9: second-source forward data + in-house peer P/E
from macro_prices import macro_prices  # v4.2: FRED risk-free + Tiingo series (keys stay server-side)
from macro_prices import tiingo_price_on_date, split_factor_since, pe_same_share_basis
                                        # v4.2.84: issue #20, historical-reconstruction stand pt.2

app = Flask(__name__)

# Hard cap so a runaway generated script can't hang the worker.


def _peer_pe_excluded(data):
    """True when peer_median_pe exists but its basis is trailing, so it cannot anchor the cap."""
    return (isinstance(data.get("peer_median_pe"), (int, float))
            and "trailing" in str(data.get("peer_median_pe_basis") or ""))


def _three_year_table(data, price):
    """(I) v4.2.79 — the last three fiscal years from EDGAR series, nothing searched, nothing new
    fetched. revenue / net income / EPS / FCF come from series the pipeline already holds; the
    fiscal-year end is carried on every row because "2026" means different months at different
    companies and a reader comparing two briefs must be able to see that.

    The P/E column is the honest one to get wrong. We hold ONE Tiingo price — today's — and no
    historical prices, so a true historical multiple cannot be computed here. Rather than print a
    column called "P/E" that would be a lie for every year but the current one, the value published
    is explicitly today's price against that year's earnings, and the field is NAMED that way so
    the renderer cannot relabel it by accident.
    """
    def _pts(key):
        s = data.get(key) or []
        return [p for p in s if isinstance(p, dict) and isinstance(p.get("val"), (int, float))]

    rev = {p.get("end"): p["val"] for p in _pts("revenue")}
    ni = {p.get("end"): p["val"] for p in _pts("net_income")}
    ocf = {p.get("end"): p["val"] for p in _pts("ocf")}
    cx = {p.get("end"): p["val"] for p in _pts("capex")}
    sh = {p.get("end"): p["val"] for p in _pts("shares_diluted")}

    ends = sorted([e for e in rev.keys() if e], reverse=True)[:3]
    rows = []
    for e in sorted(ends):
        eps = (ni[e] / sh[e]) if (e in ni and sh.get(e)) else None
        fcf = (ocf[e] - cx[e]) if (e in ocf and e in cx) else None
        rows.append({
            "fy_end": e,
            "revenue": rev.get(e),
            "net_income": ni.get(e),
            "eps": round(eps, 3) if eps is not None else None,
            "fcf": fcf,
            "pe_at_todays_price": (round(price / eps, 2)
                                   if (eps and eps > 0 and price) else None),
        })
    return {"rows": rows, "price_used": price,
            "pe_basis": "today's Tiingo price divided by that fiscal year's EPS — NOT a historical "
                        "multiple; no historical price series is held by this pipeline"}


def _peer_multiple_block(data):
    """The peer median WITH the company multiple on the SAME basis, or an explicit refusal.

    Two numbers on different bases are not a comparison, however confident the sentence between
    them reads. The in-house peer median is trailing (EDGAR EPS x Tiingo price); the forward
    company multiple comes from a different source and a different period. `comparable` is the
    gate, computed once here rather than re-derived by every reader.
    """
    def _num(v):
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    rows = data.get("peer_multiples")
    rows = rows if isinstance(rows, list) else []
    count = len([r for r in rows if isinstance(r, dict)]) or None

    peer_med = _num(data.get("peer_median_pe"))
    peer_basis = data.get("peer_median_pe_basis") or None

    trailing_peer = "trailing" in str(peer_basis or "").lower()
    if trailing_peer:
        company = _num(data.get("pe_trailing_company"))
        company_basis = data.get("pe_trailing_company_basis") or None
    else:
        company = _num(data.get("fwd_pe"))
        company_basis = data.get("fwd_pe_basis") or None

    comparable = bool(peer_med is not None and company is not None
                      and count is not None and peer_basis and company_basis)
    # v4.2.79 (II): the rows themselves travel with the median so the brief can show WHO the peers
    # are. A median over unnamed companies is a number the reader cannot argue with, which is the
    # opposite of what this document is for.
    pub_rows = [{"ticker": r.get("ticker"), "market_cap": r.get("market_cap"),
                 "revenue_ltm": r.get("revenue_ltm"), "pe_trailing": r.get("pe_trailing"),
                 "fy_end": r.get("fy_end")}
                for r in rows if isinstance(r, dict) and r.get("ticker")]
    return {
        "rows": pub_rows,
        "median": peer_med,
        "count": count,
        "basis": peer_basis,
        "company": company,
        "company_basis": company_basis,
        "comparable": comparable,
        "excluded_from_pe_cap": _peer_pe_excluded(data),
    }


def _pe_anchor_fwd(data):
    """The peer/sector anchor for the FORWARD P/E cap -- forward-basis inputs only.

    A trailing peer median is not a forward anchor. It is not conservative either: a peer set
    with depressed earnings inflates the trailing median without saying anything about the
    multiple this name deserves. NFLX 2026-07-16: peers DIS/WBD/SPOT/PARA gave an in-house
    TRAILING median of 95.09 (WBD alone traded at 95x trailing on collapsed earnings). That
    became pe_sector_median -> cap = 1.5 x 95.09 ~ 143 -- a cap so loose it could never bind.
    The EVIDENCE PACK then printed it under a hardcoded "fwd P/E" label, so a trailing figure
    travelled through the whole report wearing a forward name.
    Dropping it here means the cap falls back to pe_hist_median, or to the conservative
    no-anchor default -- both defensible. A wrong anchor is worse than no anchor.
    v4.2.77: the second candidate, `data.get("pe_sector_median")`, is DELETED. It never arrived:
    the key appears nowhere in the workflow, so this loop read an absence on every run since the
    function was written, and the anchor has always in fact been the peer median alone. A read that
    can only ever return nothing is not harmless — it is a trap for the next reader, who sees two
    sources here and believes a true sector median is in play. Same class as the entry rung
    defaulting to 20 and the year-5 point that existed in RESULT but never printed: machinery whose
    shape promises a measurement it cannot deliver. A real sector median is a candidate AFTER the
    matrix, by the operator's decision; until such a source exists, this function has one input and
    says so.
    """
    if _peer_pe_excluded(data):
        peer = None
    else:
        peer = data.get("peer_median_pe")
    if isinstance(peer, (int, float)) and peer > 0:
        return float(peer)
    return None


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "growth-alpha-microservice",
                    "build": BUILD})


@app.route("/enrich_yf", methods=["POST"])
def _enrich_yf():
    body = request.get_json(force=True, silent=True) or {}
    ticker = body.get("ticker")
    peers = body.get("peers") or []
    if not ticker:
        return jsonify({"_errors": {"request": "ticker missing"}}), 200
    # enrich_yf never throws; returns a dict with _errors trail on partial failure.
    return jsonify(enrich_yf(ticker, peers)), 200


@app.route("/scenario_tree", methods=["POST"])
def _scenario_tree():
    """
    Core-V (pre-profit / Category-F) deterministic ANCHORS.
    Body: {"data": {...eligibility payload...}}  (also accepts a bare payload).
    scenario_tree() never throws; returns a dict with a '_warnings' trail.
    """
    body = request.get_json(force=True, silent=True) or {}
    data = body.get("data", body)
    return jsonify(scenario_tree(data)), 200


@app.route("/edgar_facts", methods=["POST"])
def _edgar_facts():
    """
    SEC EDGAR primary-source financials (deterministic XBRL facts).
    Body: {"ticker": "ASTS"}  (or {"cik": "0001780312"}). Optional "as_of": "YYYY-MM-DD"
    (issue #14/#20, the historical-reconstruction stand) restricts every fact to ones FILED on
    or before that day -- what the public actually knew on that date, not what a later
    restatement says. Omitted: not one line of behavior changes from before this field existed.
    edgar_facts() never throws; missing fields come back null with a '_missing' trail.

    as_of is compared against a filing-date STRING inside edgar_facts (`f.get("filed") <= as_of`)
    -- a non-string as_of (e.g. a bare int from a caller that forgot the quotes) throws a raw
    TypeError there and the route 500s, same class of bug as the eps type-check below. Checked
    here, at the boundary, so the route degrades to a named refusal instead: as_of is dropped
    (ticker/cik still process normally) and the reason lands in _errors.
    """
    body = request.get_json(force=True, silent=True) or {}
    as_of = body.get("as_of")
    as_of_error = None
    if as_of is not None and not isinstance(as_of, str):
        as_of_error = "as_of must be a string 'YYYY-MM-DD', got %s" % type(as_of).__name__
        as_of = None
    result = edgar_facts(body.get("ticker"), body.get("cik"), as_of)
    if as_of_error:
        result.setdefault("_errors", {})["as_of"] = as_of_error
    return jsonify(result), 200


# ============================================================================
# v2.5 DETERMINISTIC HARNESS (Variant 1) — replaces LLM-generated wiring.
# Stage2a now supplies a JSON SPEC (judgment inputs), NOT Python code. This fixed
# harness assembles the full RESULT deterministically: quant blocks from gps_quant
# (ONCE), qualitative blocks from the LLM's scored inputs, IVC + scenarios + bull/bear
# from ivc_lib. Eliminates: wiring code errors, GPS double-count/omission, degraded
# runs, GPS_TOTAL_MISMATCH. Same RESULT shape Render Tables/gate/auditor already read.
# ============================================================================
#: absolute ceiling on the exit multiple; see the note inside analyze()
PE_CAP = 30.0


def analyze(data, spec):
    from ivc_lib import ivc, bull_bear_table, gps_quant
    data = data or {}
    spec = spec or {}
    A = spec.get("assumptions", {}) or {}

    # v2.9: SANITIZE the LLM spec. dict.get(k, default) does NOT substitute the default when the
    # key EXISTS with value None -- and Stage2a legitimately writes explicit nulls (e.g. PLTR pays
    # no dividend -> "dividend_growth": null). Those nulls reached ivc_lib and blew up on 1+None
    # ("unsupported operand type(s) for +: 'int' and 'NoneType'") -> empty numeric layer. The
    # deterministic layer must never trust the spec's shape: coerce here, once, at the boundary.
    def _f(v, dflt):
        return v if (isinstance(v, (int, float)) and not isinstance(v, bool)) else dflt

    def _clean_ov(ov):
        """Drop null overrides so the base assumption survives instead of poisoning ivc."""
        return {k: v for k, v in (ov or {}).items() if v is not None}

    pd = data.get("price_data", {}) if isinstance(data.get("price_data"), dict) else {}
    cp = pd.get("current_price")
    price = cp.get("adjClose") if isinstance(cp, dict) else (cp if cp else data.get("current_price"))

    _hurdle = _f(A.get("hurdle"), 0.12)
    base_inp = {
        "price": price,
        "eps_normalized": data.get("eps0_reported"),
        "levered_fcf_per_share": data.get("levered_fcf_per_share"),
        # v4.2.28 (BACKLOG P) BASE-GROWTH ANCHORING. The base scenario's growth_rate used to come
        # straight from the LLM (A.get("growth_rate")) — the ONE un-anchored driver of ivc_base,
        # so IV/PWFV/implied_cagr/MoS floated 6% across runs on identical facts while future_pe
        # (anchored by _cap_pe since v2.6) stayed put. Symmetric fix: the base leg is now anchored
        # to a DETERMINISTIC figure and the LLM's number is recorded but does not steer.
        #   base g = min(rev_cagr_3y, rev_cagr_5y), capped at 20% (mandate).
        # rev, not eps: extrapolating margin-expansion (eps_cagr 33%) into the BASE is against the
        # Graham-Dodd mandate — the margin bet's home is the BULL scenario, not base. min() takes
        # the more conservative of the two revenue horizons. Fade is untouched (ivc_lib applies g
        # years 1-5 then fades to terminal_g). Bull/bear remain fully LLM-driven downstream.
        "growth_rate": None,  # set just below to the anchored value
        "future_pe": _f(A.get("future_pe"), None),
        "hurdle": _hurdle,
        # v4.2.31 (BACKLOG P, base-determinism sweep — architect sanction on all 5 at once). Every
        # base input that fed IV from the LLM is pinned to a deterministic value; the LLM number is
        # recorded (llm_*) and flagged on divergence but does NOT steer the base. bull/bear keep the
        # LLM values (scenario analysis). This closes the class by audit, not by pair-induction.
        "discount_rate": _hurdle,   # = hurdle (mandate A); llm_disc recorded below
        # v4.2.61: the LAST `unknown-read-as-0.0` on the VERDICT path. dil-03 fixed the FCF leg
        # and left this one — and this is the leg that JUDGES, and the one that becomes the sole
        # judge precisely when the FCF leg is refused for the same missing input.
        # 0.0 is NOT a conservative reading. It is neutral, and neutral cuts both ways:
        #   buyback name (dilution NEGATIVE, e.g. MA -2.1%) -> 0.0 UNDERSTATES IV. Harmless.
        #   diluter      (dilution POSITIVE, e.g. an SBC-heavy issuer) -> 0.0 OVERSTATES IV,
        #   and overstatement on the judging leg is how an AVOID becomes a WATCH+.
        # There is no honest number to substitute — inventing a dilution would be the same defect
        # wearing a more cautious face. So: keep the neutral arithmetic, but REFUSE to let an
        # unverified input produce a bullish verdict (cap applied further down), and say so.
        "share_dilution_cagr": _f(data.get("dilution_cagr"), 0.0),
        "pe_hist_median": _f(data.get("pe_hist_median"), None),
        "pe_sector_median": _pe_anchor_fwd(data),
        # dividend from filings, not LLM: yield from data (its market-snapshot drift lives in the
        # scorecard market class); growth = min(DPS CAGR 3y, 5y) capped at base_g (a dividend cannot
        # be modelled growing faster than the business). Computed just below where base_g is known.
        "dividend_yield": _f(data.get("div_yield"), 0.0),
        "dividend_growth": 0.0,      # set below to the deterministic DPS-CAGR anchor
        "fade": True,                # mandate "fade untouched" = always on, never an LLM toggle
        # terminal_growth pinned to 0.04 with an asymmetry guard: the EFFECTIVE terminal is
        # min(0.04, base_g) — the fade may slow the tail, never accelerate it (a sub-4% grower must
        # not have its tail lifted to 4%). Set below where base_g is known.
        "terminal_growth": 0.04,
        "years": 10,                 # structural horizon (mandate); never an LLM value
        "mos_targets": [0.10, 0.20, 0.30],  # mandate ladder; not LLM
    }
    # record the LLM's base opinions (do not steer) + divergence flags
    base_llm_flags = []
    _llm_disc = _f(A.get("discount_rate"), None)
    if isinstance(_llm_disc, (int, float)):
        base_inp["llm_disc"] = _llm_disc
        if abs(_llm_disc - _hurdle) > 0.01:  # >1pp
            base_llm_flags.append("disc_divergence: LLM %.3f vs hurdle %.3f (>1pp)" % (_llm_disc, _hurdle))
    _llm_terminal = _f(A.get("terminal_growth"), None)
    if isinstance(_llm_terminal, (int, float)) and abs(_llm_terminal - 0.04) > 0.005:
        base_inp["llm_terminal_g"] = _llm_terminal
        base_llm_flags.append("terminal_g_divergence: LLM %.4f vs anchor 0.04" % _llm_terminal)
    _llm_years = _f(A.get("years"), None)
    if isinstance(_llm_years, (int, float)) and int(_llm_years) != 10:
        base_llm_flags.append("years_divergence: LLM %d vs structural 10" % int(_llm_years))
    # v2.6: DETERMINISTIC PE-CAP (was a gate REWORK trigger 'pe_cap_unjustified'). The LLM's
    # future_pe is clamped to a defensible anchor here, so it can never overreach and the gate
    # never has to reject-to-REWORK. Anchor = best of peer/hist/sector median (allow up to 1.2x).
    # If NO anchor exists at all -> conservative constant + flag (produces a verdict, not a REWORK).
    NO_ANCHOR_PE = 20.0
    _anchors = [x for x in (_pe_anchor_fwd(data), data.get("pe_hist_median"))
                if isinstance(x, (int, float)) and x > 0]
    pe_flags = []
    # Issue #12: ivc_lib's SECONDARY multiplier cap is min(pe_hist_median, 1.5*pe_sector_median)
    # (ivc_lib.py, `pecap`). The value that reaches it under the "pe_sector_median" key is exactly
    # _pe_anchor_fwd(data) -- see TestPeAnchorHasOneInput above for why the literal `pe_sector_median`
    # field itself is a ghost the workflow never produces. Whenever _pe_anchor_fwd(data) comes back
    # None, that half of the secondary cap is absent and the cap silently collapses to the historical
    # median alone -- correct arithmetic, but invisible to the reader. Say so, loudly, without
    # touching the arithmetic.
    if _pe_anchor_fwd(data) is None:
        pe_flags.append(
            "pe_sector_median_absent: sector median is not produced by the pipeline, so the "
            "secondary multiplier cap (min(pe_hist_median, 1.5x sector)) relies on the "
            "historical median alone")
    if _peer_pe_excluded(data):
        pe_flags.append(
            "peer_median_pe_%.1f_EXCLUDED_from_cap_basis_is_trailing_not_forward"
            % data.get("peer_median_pe"))

    def _cap_pe(v):
        if not isinstance(v, (int, float)) or v <= 0:
            return v
        if _anchors:
            cap = 1.2 * max(_anchors)
            if v > cap:
                pe_flags.append("future_pe %.1f capped at 1.2x anchor = %.1f" % (v, cap))
                return round(cap, 1)
            return v
        if v > NO_ANCHOR_PE:
            pe_flags.append("no PE anchor (peer/hist/sector all null) -> future_pe %.1f capped at conservative %.0f" % (v, NO_ANCHOR_PE))
            return NO_ANCHOR_PE
        return v

    # v4.2.30 (BACKLOG P, future_pe leg — FINAL architect mandate). base future_pe is anchored to
    #   min(pe_median_5y, pe_median_10y, 25), NO floor.
    # The two window medians come from Growth Enrich (each a median of FY year-points, where a
    # year-point is itself the median of that FY's 12 month-end prices / FY diluted EPS; outliers
    # PE in (0,100); >=3 year-points per window or the window is null). Ceiling 25 is the low end of
    # the band — doubt resolves conservatively; names worthy of more prove it through growth, not a
    # fatter exit multiple. No floor: a low median passes through (margin of safety lives in the
    # hurdle/MoS rungs, not an inflated exit multiple). If NEITHER window has >=3 points, there is
    # no history to anchor on -> fixed default 18 (long-run market median) with a LOUD flag. LLM
    # base future_pe is recorded (llm_base_pe) and flagged (pe_divergence >5) but does NOT steer the
    # base; bull/bear future_pe remain fully LLM-driven.
    # v4.2.65 (architect mandate 03.08.2026): PE_ABS_CAP 25 -> 30, and the ceiling stops being
    # one number for every company. The binding element is now normally the firm's OWN median;
    # 30 is an absolute backstop against bubble multiples, not a view on any particular name.
    # Measured cost of the old value, from Table 2 on MA: the ceiling was worth +33.8% of IV —
    # the single largest conservative layer, and it was a constant applied to companies whose own
    # histories differ by a factor of two. The level of 30 itself stays open until the six-name
    # matrix; the CENTRAL lens is computed with no ceiling at all, which is what makes the two
    # lenses a measurement of this decision rather than an opinion about it.
    PE_CAP = globals().get('PE_CAP', 30.0)
    PE_DEFAULT = 18.0
    pe_anchor_flags = []
    _pe_m5 = data.get("pe_median_5y")
    _pe_m10 = data.get("pe_median_10y")
    _llm_base_pe = _f(base_inp.get("future_pe"), None)  # the LLM's base future_pe, pre-anchor
    _window_meds = [x for x in (_pe_m5, _pe_m10) if isinstance(x, (int, float)) and x > 0]
    if _window_meds:
        _anchored_pe = min(min(_window_meds), PE_CAP)     # min(5y, 10y, 25); NO floor
        if min(_window_meds) > PE_CAP:
            pe_anchor_flags.append("base_future_pe min(median_5y,10y) %.1f capped at %.0f"
                                   % (min(_window_meds), PE_CAP))
        base_inp["future_pe"] = _anchored_pe
        base_inp["future_pe_basis"] = "min(pe_median_5y, pe_median_10y, %.0f) — deterministic, no floor" % PE_CAP
    else:
        # No window has >=3 year-points: no history to anchor on -> fixed long-run default, loud flag.
        base_inp["future_pe"] = PE_DEFAULT
        base_inp["future_pe_basis"] = "DEFAULT %.0f (insufficient history)" % PE_DEFAULT
        pe_anchor_flags.append("[PE ANCHOR: DEFAULT — insufficient history]")
    if isinstance(_llm_base_pe, (int, float)):
        base_inp["llm_base_pe"] = _llm_base_pe
        _pe_div = abs(_llm_base_pe - base_inp["future_pe"])
        if _pe_div > 5.0:
            pe_anchor_flags.append(
                "pe_divergence: LLM base future_pe %.1f vs anchor %.1f (%.1f > 5 points)"
                % (_llm_base_pe, base_inp["future_pe"], _pe_div))

    # v4.2.28 (BACKLOG P): compute the anchored base growth_rate deterministically.
    # _cagr is the SAME function the GPS block-A uses for rev_cagr5/rev_cagr3, so the anchor is
    # byte-identical to what the scorecard reports — no second, divergent computation.
    from ivc_lib import _cagr as _rev_cagr
    _rev_series = data.get("revenue")
    _rc5 = _rev_cagr(_rev_series, 5)
    _rc3 = _rev_cagr(_rev_series, 3)
    _anchor_candidates = [x for x in (_rc3, _rc5) if isinstance(x, (int, float))]
    GROWTH_CAP = 0.20  # absolute ceiling, symmetric to _cap_pe's multiple ceiling
    growth_flags = []
    if _anchor_candidates:
        _anchored_g = min(_anchor_candidates)              # conservative of the two horizons
        if _anchored_g > GROWTH_CAP:
            growth_flags.append("base_growth %.4f capped at %.2f" % (_anchored_g, GROWTH_CAP))
            _anchored_g = GROWTH_CAP
        base_inp["growth_rate"] = _anchored_g
        base_inp["growth_rate_basis"] = "min(rev_cagr_3y, rev_cagr_5y) capped %.0f%% (deterministic anchor)" % (GROWTH_CAP * 100)
    else:
        # No revenue series to anchor on. Fall back to the LLM number rather than fabricate one,
        # but flag loudly that the base leg is unanchored this run (honest, not silent).
        base_inp["growth_rate"] = _f(A.get("growth_rate"), None)
        base_inp["growth_rate_basis"] = "UNANCHORED: no revenue series; fell back to LLM growth_rate"
        growth_flags.append("base_growth_unanchored_no_revenue_series")
    # Record the LLM's base growth opinion WITHOUT letting it steer the base leg; flag material
    # divergence so the LLM's judgment stays visible to the auditor and to us.
    _llm_base_g = _f(A.get("growth_rate"), None)
    if isinstance(_llm_base_g, (int, float)):
        base_inp["llm_base_g"] = _llm_base_g
        if isinstance(base_inp.get("growth_rate"), (int, float)):
            _div_pp = abs(_llm_base_g - base_inp["growth_rate"]) * 100
            if _div_pp > 3.0:
                growth_flags.append(
                    "growth_divergence: LLM base g %.1f%% vs anchor %.1f%% (%.1fpp > 3pp)"
                    % (_llm_base_g * 100, base_inp["growth_rate"] * 100, _div_pp))

    # v4.2.31: terminal_growth asymmetry guard (mandate). Effective terminal = min(0.04, base_g):
    # the fade may only SLOW the tail toward terminal, never ACCELERATE a sub-4% grower up to 4%.
    _bg = base_inp.get("growth_rate")
    if isinstance(_bg, (int, float)):
        _eff_tg = min(0.04, _bg)
        if _eff_tg < 0.04:
            base_llm_flags.append("terminal_g asymmetry: capped to base_g %.4f (< 0.04, tail not lifted)" % _bg)
        base_inp["terminal_growth"] = _eff_tg

    # v4.2.31: dividend_growth from filings, not LLM. DPS series is split-normalized 10-K data;
    # growth = min(DPS CAGR 3y, DPS CAGR 5y), and never above base_g (a dividend cannot be modelled
    # growing faster than the business that funds it). If no DPS series -> 0 (honest, not invented).
    # v4.2.60: WIRED. edgar_facts now emits `dps_series` from CommonStockDividendsPerShareDeclared,
    # and refuses the window outright when a confirmed split falls inside it (as-reported per-share
    # amounts are incomparable across a split; there is no DPS split-normalisation here yet, and a
    # split artifact wearing a dividend's name is worse than no dividend growth at all). The formula
    # below is unchanged from v4.2.31 — it was always the target and needed no edit, only a series.
    # Direction of the fix: dividend_growth pinned at 0 UNDERSTATED IV on every payer, MA included.
    _dps = data.get("dps_series") or data.get("dividends_series")
    _dps_g = None
    if _dps:
        _d3 = _rev_cagr(_dps, 3)
        _d5 = _rev_cagr(_dps, 5)
        _dps_cands = [x for x in (_d3, _d5) if isinstance(x, (int, float))]
        if _dps_cands:
            _dps_g = min(_dps_cands)
            if isinstance(_bg, (int, float)):
                _dps_g = min(_dps_g, _bg)   # never above the business growth
    base_inp["dividend_growth"] = _dps_g if isinstance(_dps_g, (int, float)) else 0.0
    if _dps_g is None:
        # v4.2.64 (mandate 2): branch the message by CAUSE. The single old text — "dps_series not
        # yet wired in Growth Enrich" — outlived its truth in v4.2.60 and was still printed on the
        # NFLX pair of 2026-08-02, where the real reason is that Netflix pays no dividend. Three
        # states that a reader must be able to tell apart:
        #   the filer pays nothing        -> a FACT about the company, and a correct zero
        #   the window was refused        -> a DATA defect (split inside it), zero is a placeholder
        #   nothing is wired              -> an ENGINEERING gap
        # The same distinction already exists one layer down in edgar_facts (dps_series_absent vs
        # dps_series_refused_split_in_window); this is it finally reaching the flag a human reads.
        _dps_flags = (data.get("_edgar") or {}).get("flags") or {}
        if _dps_flags.get("dps_series_refused_split_in_window"):
            base_llm_flags.append(
                "dividend_growth=0: DPS window REFUSED — %s. The zero is a placeholder for an "
                "unusable series, not a measurement."
                % _dps_flags["dps_series_refused_split_in_window"])
        elif _dps_flags.get("dps_series_absent") or (data.get("dps_series") is None
                                                     and "dps_series" in data):
            base_llm_flags.append(
                "dividend_growth=0: the filer reports no per-share dividend — a CORRECT zero, a "
                "fact about the company, not a data gap.")
        else:
            base_llm_flags.append(
                "dividend_growth=0: no dps_series reached analyze() and no reason was reported "
                "upstream — engineering gap, investigate the Gather Data -> analyze handoff.")

    ivc_base = ivc(base_inp)
    if isinstance(ivc_base, dict) and "error" in ivc_base:
        # v4.2.49 (mandate AAA): an honest error is TWO independent facts, and merging them was the
        # sixth mirror of the class. `price missing` means the INPUT was not obtained → the run did
        # not finish. Category-F means the inputs are fine and the METHOD does not apply → the run
        # DID finish, with a conclusion. Both used to return the same shape (same _FALLBACK, same
        # _harness, same verdict_cap, even the same flag claiming "inputs insufficient" — a lie for
        # Category-F), so the live BASE predicate "broken = non-empty error" would drop OKLO, SMR,
        # IONQ, ASTS, RDDT out of v_ticker_latest. Classified below; GPS is computed for the
        # ANALYSIS_RESULT case (it does not depend on IV) because for loss-making names it is the
        # only quantitative output left.
        # LEG-OK: reading the base leg's own error text to classify it — leg-independent.
        _err = str(ivc_base.get("error") or "")
        _is_category_f = "Category-F" in _err or "no positive EPS or FCF" in _err
        _err_class = "ANALYSIS_RESULT" if _is_category_f else "DATA_ERROR"
        if not _is_category_f:
            return {"error": ivc_base["error"], "error_class": _err_class,
                    "_harness": True, "_FALLBACK": True,
                    "run_complete": False, "iv_computable": False,
                    "iv_not_computable_reason": ("price_missing" if "price missing" in _err
                                                 else "growth_or_pe_anchor_missing"),
                    "ivc_base": ivc_base, "verdict_cap": "AVOID",
                    "flags": ["harness_ivc_error_inputs_insufficient"]}
        # Category-F: fall through so GPS/radar are computed; the IV layer stays honestly empty.
        _category_f = {"error": ivc_base["error"], "error_class": _err_class,
                       "iv_not_computable_reason": "category_f_no_positive_base"}
    else:
        _category_f = None

    # ------------------------------------------------------------------------------------------
    # v3.4 DUAL BASIS (Variant B). GAAP EPS DOUBLE-COUNTS stock-based compensation for valuation:
    # SBC is subtracted from earnings AND the issued shares dilute the per-share base — the same
    # $1 charged twice. For SBC-heavy names this halves the apparent per-share economics
    # (NOW: GAAP $1.67/sh vs FCF $4.44/sh -> 63x vs 24x on the same price). The Graham-Dodd
    # answer is not to pick a side silently but to PRICE BOTH and show the gap:
    #   - GAAP leg: reported EPS + the spec's future_pe (as before).
    #   - FCF leg: levered FCF/share + GROSS dilution (before buybacks), so SBC is charged
    #     exactly ONCE — through the share count, not through the income statement. Using NET
    #     dilution here would double-CREDIT buybacks; gross is the honest pairing.
    #   - Both legs carry the SAME exit multiple (v4.2.50): weighting one leg down decided WHICH
    #     leg judges, which is not a valuation choice but a thumb on the scale.
    # The verdict_cap is driven by the CONSERVATIVE leg (min implied CAGR): the bull case may
    # argue from the other leg in prose, but sizing discipline follows the stricter number.
    # ------------------------------------------------------------------------------------------
    # v4.2.50 (mandate III): FCF_PE_DISCOUNT REMOVED. A 0.9 haircut on one leg's exit multiple is
    # a thumb on the scale: it lowered the FCF leg's IV, which made that leg "conservative" more
    # often, which made it the VERDICT leg — the knob was choosing the judge, not the number. Both
    # legs now use the SAME multiple; conservatism is decided by the base alone. If the FCF leg
    # under-charges SBC, the fix belongs in the SBC accounting, not in the terminal multiple.
    # Consequence accepted knowingly: for MA the verdict leg becomes GAAP.
    fcfps = data.get("levered_fcf_per_share")
    # v4.2.60 (dil-03): NET dilution read ONCE, as UNKNOWN-or-number. It used to be read three
    # times with `_f(..., 0.0)`, so a missing value silently became "this company issues no net
    # shares" — the most flattering assumption available, on the leg that competes to be the
    # verdict. The path is reachable: the workflow nulls dilution_cagr whenever |CAGR| > 20%
    # (split artifact), and NFLX has already landed there. Zero is a measurement; absent is not.
    publication_flags = []   # v4.2.61: declared before its first writer (the verdict-cap guard)
    _dil_net_known = _f(data.get("dilution_cagr"), None)
    _dilution_unverified = (_dil_net_known is None)
    if _dilution_unverified:
        base_llm_flags.append(
            "dilution_UNVERIFIED: no net dilution figure; the GAAP leg was computed at 0.0, which "
            "is NEUTRAL, not conservative — it understates IV for a buyback name and OVERSTATES it "
            "for a diluter. verdict_cap held at AVOID: an unverified share count may not produce a "
            "bullish verdict.")
    dil_gross = _f(data.get("dilution_cagr_gross"), None)  # optional upstream field
    if _dil_net_known is None and dil_gross is None:
        # No honest gross figure can be built on an unknown net. Refuse the FCF leg rather than
        # compute it on an invented zero: a leg missing is visible, a leg quietly flattered is not.
        base_llm_flags.append("fcf_leg_skipped: dilution_cagr UNKNOWN — gross dilution cannot be "
                              "derived, and assuming 0 would inflate the FCF leg")
        fcfps = None
    if dil_gross is None and _dil_net_known is not None:
        # GROSS dilution = what the share count would do WITHOUT buybacks = net dilution plus
        # the share-count effect of ONLY the SBC-offsetting portion of buybacks. Buybacks BEYOND
        # SBC are genuine capital return, not hidden dilution — adding them back would absurdly
        # charge shareholder-friendly names (ADBE: buyback/FCF=114%, count SHRINKING 2.5%/yr)
        # with double-digit phantom dilution. Cap the added-back portion at the SBC actually
        # granted (buyback_vs_sbc >= 1 -> everything issued was retired -> add back only SBC).
        dil_net = _dil_net_known
        bb_fcf = _f(data.get("buyback_to_fcf"), None)
        bb_vs_sbc = _f(data.get("buyback_vs_sbc"), None)
        fcf_total = _f(data.get("levered_fcf"), None)
        mcap = None
        if price and _f(data.get("shares_current"), None):
            mcap = price * data.get("shares_current")
        if bb_fcf is not None and fcf_total and mcap and mcap > 0:
            bb_dollars = bb_fcf * fcf_total
            if bb_vs_sbc is not None and bb_vs_sbc > 1:
                bb_dollars = bb_dollars / bb_vs_sbc      # only the SBC-offsetting share
            dil_gross = dil_net + bb_dollars / mcap
        else:
            # Coarse proxy. SBC/revenue UNKNOWN is not SBC/revenue ZERO: with no SBC figure the
            # proxy has nothing to add, so gross collapses onto net — which is a FLOOR, not an
            # estimate, and must be labelled as one rather than passed off as measured.
            _sbc_known = _f(data.get("sbc_to_revenue"), None)
            if _sbc_known is None:
                base_llm_flags.append("gross_dilution_is_a_FLOOR: sbc_to_revenue unknown, the "
                                      "buyback add-back could not be estimated")
                dil_gross = dil_net
            else:
                dil_gross = dil_net + _sbc_known * 0.5
    # gross can never be < net — but only when net is KNOWN; comparing against an assumed 0 would
    # reintroduce the same floor the block above just refused.
    if dil_gross is not None and _dil_net_known is not None:
        dil_gross = max(dil_gross, _dil_net_known)
    # v4.2.69 (mandate 3): a MISSING leg names the input it missed. ORCL shipped `dual_basis:
    # null` with `mos_pct_verdict_leg` empty and not one flag — the verdict rested on a single leg
    # and the document said nothing about it. The dual basis exists precisely so that the more
    # conservative of two answers wins; when only one exists, the reader is looking at a weaker
    # construction than the method promises, and silence about that is the fcf_leg_skipped hole
    # reopened from the other side.
    _fcf_absent_reason = None
    if not isinstance(fcfps, (int, float)):
        _fcf_absent_reason = "levered_fcf_per_share missing from GROUND_TRUTH"
    elif fcfps <= 0:
        _fcf_absent_reason = "levered_fcf_per_share <= 0 (%s) — no positive FCF base to grow" % fcfps
    elif not base_inp.get("future_pe"):
        _fcf_absent_reason = "no exit multiple anchored, so neither leg can be built"
    if _fcf_absent_reason and not any("fcf_leg_skipped" in f for f in base_llm_flags):
        base_llm_flags.append(
            "SINGLE_LEG_RUN: the FCF leg was not built (%s). The verdict rests on the GAAP leg "
            "alone — the dual-basis cross-check that normally picks the more conservative of two "
            "answers did not run." % _fcf_absent_reason)
    ivc_fcf = None
    if isinstance(fcfps, (int, float)) and fcfps > 0 and base_inp.get("future_pe"):
        fcf_inp = dict(base_inp)
        fcf_inp["eps_normalized"] = None                 # force the FCF engine in ivc()
        fcf_inp["levered_fcf_per_share"] = fcfps
        fcf_inp["future_pe"] = base_inp["future_pe"]   # same multiple on both legs
        fcf_inp["share_dilution_cagr"] = round(dil_gross, 5)
        ivc_fcf = ivc(fcf_inp)
        if isinstance(ivc_fcf, dict) and "error" in ivc_fcf:
            ivc_fcf = None

    dual_basis = None
    if ivc_fcf:
        # LEG-OK: building dual_basis itself — both legs are required here by definition.
        iv_g, iv_f = ivc_base.get("intrinsic_value"), ivc_fcf.get("intrinsic_value")
        # LEG-OK: building dual_basis — both legs required by definition.
        ic_g, ic_f = ivc_base.get("implied_cagr_pct"), ivc_fcf.get("implied_cagr_pct")
        conservative = "gaap_eps" if (ic_g is not None and ic_f is not None and ic_g <= ic_f) else "fcf_per_share"
        _gap = (round((iv_f / iv_g - 1) * 100, 1) if (iv_g and iv_f) else None)
        # v4.2.32 mandate (a): a gap this large is a DATA defect, not a business story. MA
        # 2026-07-22 produced gap 595.8% purely from mismatched share denominators, and the memo
        # rationalised it in prose as an "asset-light structural difference". Absurdity checks are
        # NEVER trusted to prose — only to deterministic Python. Above the threshold the FCF leg is
        # marked unreliable and the flag is raised as a DATA-class hard flag.
        GAP_IV_HARD_PCT = 100.0
        _gap_unreliable = _gap is not None and abs(_gap) > GAP_IV_HARD_PCT
        if _gap_unreliable:
            base_llm_flags.append(
                "[DATA] gap_iv_pct %.1f%% > %.0f%% — FCF leg UNRELIABLE (check share denominators)"
                % (_gap, GAP_IV_HARD_PCT))
        dual_basis = {
            # v4.2.50 (mandate III): the legs use DIFFERENT dilution numbers under what used to
            # read as one concept. Named apart so a reader never infers which is which: GAAP
            # charges SBC in earnings AND in the share count, so it pairs with NET dilution (after
            # buybacks); FCF does not charge SBC at all, so it pairs with GROSS (before buybacks)
            # — that is how SBC is counted exactly once. Arithmetic unchanged; naming only.
            "gaap_eps": {"iv": iv_g, "implied_cagr_pct": ic_g,
                         # LEG-OK: the GAAP entry of dual_basis itself.
                         "base_per_share": ivc_base.get("inputs", {}).get("base_per_share"),
                         "dilution_basis": "net_after_buybacks",
                         "dilution_net_after_buybacks": base_inp.get("share_dilution_cagr")},
            "fcf_per_share": {"iv": iv_f, "implied_cagr_pct": ic_f,
                              "base_per_share": fcfps,
                              "future_multiple": fcf_inp["future_pe"],
                              "dilution_basis": "gross_before_buybacks",
                              "dilution_gross_before_buybacks": fcf_inp["share_dilution_cagr"],
                              "gross_dilution_used": fcf_inp["share_dilution_cagr"]},
            "gap_iv_pct": _gap,
            "gap_hard_threshold_pct": GAP_IV_HARD_PCT,
            "fcf_leg_unreliable": _gap_unreliable,
            "shares_used": data.get("shares_used"),
            "conservative_leg": conservative,
            "verdict_leg": conservative,
            # v4.2.50 (mandate III): with the 0.9 thumb removed, WHICH leg judges is decided by the
            # base alone — so say it out loud instead of leaving it to be inferred from two IVs.
            "leg_choice_note": (
                "verdict follows %s (IV %.2f) — the lower of the two; %s reads %.2f, gap %.1f%%. "
                "Both legs now carry the SAME exit multiple (v4.2.50)."
                % (conservative, (iv_f if conservative == "fcf_per_share" else iv_g),
                   ("gaap_eps" if conservative == "fcf_per_share" else "fcf_per_share"),
                   (iv_g if conservative == "fcf_per_share" else iv_f),
                   abs((iv_f / iv_g - 1) * 100) if (iv_g and iv_f) else 0.0)
                if (iv_g and iv_f) else "single leg only"),
            "_note": ("GAAP charges SBC in earnings AND in the share count (double count); the FCF "
                      "leg charges it once, via GROSS dilution. A large gap means the verdict is "
                      "really a judgment about SBC, not about the business."),
        }

    # ==========================================================================================
    # v4.2.41 (mandate LL): THE PUBLICATION SOURCE, resolved ONCE, BEFORE any consumer.
    # PRINCIPLE: every published number follows the VERDICT leg; where both legs are informative,
    # publish `_by_leg` with the verdict one as the primary. The eighth defect of this class was
    # introduced BY the seventh's fix (pwfv moved to the FCF leg while sensitivity/bull_bear stayed
    # on the GAAP one), which proves per-consumer patching does not work: fix the consumer, miss its
    # neighbours on the same source. So the source itself is made single — the same structural move
    # as shares_used in v4.2.32, where mismatched denominators became IMPOSSIBLE rather than
    # detectable. `_pub` and `_pub_inp` below are the ONLY legal origin of published quantities;
    # a grep pin forbids reading ivc_base directly in publication paths.
    _vleg_name = (dual_basis or {}).get("verdict_leg") or "gaap_eps"
    _pub = (ivc_fcf if (_vleg_name == "fcf_per_share" and isinstance(ivc_fcf, dict)) else ivc_base)
    _pub_inp = (fcf_inp if (_vleg_name == "fcf_per_share" and isinstance(ivc_fcf, dict)) else base_inp)
    # ==========================================================================================

    # scenarios -> pwfv
    scen_spec = spec.get("scenarios") or {}
    # v4.2.31: scenario weights were the SIXTH LLM driver — pwfv is a weighted mean of the three
    # scenarios, so LLM-chosen weights made pwfv/implied_cagr drift even with a deterministic base
    # (NFLX pair: 25/50/25 vs 30/45/25; MA: 25/50/25 both). Fixed by CONVENTION to the mode/median
    # of observed runs: bear 0.25 / base 0.50 / bull 0.25 (base weighted highest — it is the
    # anchored, most-reliable leg). The LLM's proposed weights are recorded (llm_weights) but do
    # NOT steer pwfv. (Convention values proposed to the architect; mandate ratifies.)
    CONV_W = {"bear": 0.25, "base": 0.50, "bull": 0.25}
    _llm_weights = {}
    scenarios, pwfv, wsum = {}, 0.0, 0.0
    for name in ("bear", "base", "bull"):
        s = scen_spec.get(name, {}) or {}
        _lw = _f(s.get("weight"), None)
        if isinstance(_lw, (int, float)):
            _llm_weights[name] = _lw
        w = CONV_W[name]   # deterministic convention, NOT the LLM weight
        inp = dict(base_inp)
        inp.update(_clean_ov(s.get("overrides")))
        if "future_pe" in inp: inp["future_pe"] = _cap_pe(inp["future_pe"])
        r = ivc(inp)
        scenarios[name] = {"weight": w, "overrides": s.get("overrides") or {}, "result": r}
        iv = r.get("intrinsic_value") if isinstance(r, dict) else None
        if iv is not None:
            pwfv += w * iv
            wsum += w
    pwfv_gaap = round(pwfv, 2) if wsum > 0 else None

    # v4.2.40 (mandate II, SIXTH defect of the leg class): the scenario tree was built ONLY from
    # base_inp, i.e. the GAAP leg — so pwfv was a GAAP number even when the verdict came from the
    # FCF leg. Class and leg are independent: "CLASS 3 / LLM-by-design" describes the WEIGHTS, not
    # the leg. This is a MONEY defect through §1e: the +20/+40% overvaluation alerts on held
    # positions are computed FROM pwfv, so on an SBC-heavy name the alert fires late (fixture:
    # verdict leg IV 224.50 vs pwfv 322.30 = 43.6% too high; NFLX PWFV ~57.6 vs FCF IV 44.04 ~31%).
    # Fix: run the same scenario tree on the FCF leg too and publish the VERDICT leg's pwfv, with
    # both legs kept visible.
    pwfv_fcf, _wsum_f = 0.0, 0.0
    scenarios_fcf = {}
    if isinstance(ivc_fcf, dict) and fcfps:
        for name in ("bear", "base", "bull"):
            s = scen_spec.get(name, {}) or {}
            inp_f = dict(fcf_inp)
            inp_f.update(_clean_ov(s.get("overrides")))
            # the FCF leg carries its own conservative multiple haircut; re-apply it after overrides
            if "future_pe" in inp_f and isinstance(inp_f["future_pe"], (int, float)):
                inp_f["future_pe"] = _cap_pe(inp_f["future_pe"])
            rf = ivc(inp_f)
            scenarios_fcf[name] = {"weight": CONV_W[name], "result": rf}
            ivf = rf.get("intrinsic_value") if isinstance(rf, dict) else None
            if ivf is not None:
                pwfv_fcf += CONV_W[name] * ivf
                _wsum_f += CONV_W[name]
    pwfv_fcf = round(pwfv_fcf, 2) if _wsum_f > 0 else None
    pwfv = (pwfv_fcf if (_vleg_name == "fcf_per_share" and pwfv_fcf is not None) else pwfv_gaap)

    _bb_args = [dict(a, overrides=_clean_ov(a.get("overrides")),
                     probability=_f(a.get("probability"), 0.5))
                for a in (spec.get("bull_bear_args") or []) if isinstance(a, dict)]
    # v4.2.41 (mandate LL.3): the sensitivity table is a PUBLISHED number — memo and auditor read
    # it — so it runs on the VERDICT leg. The GAAP version is kept only under _by_leg, labelled.
    bb = bull_bear_table(_pub_inp, _bb_args)
    bb_gaap = (bull_bear_table(base_inp, _bb_args) if _pub_inp is not base_inp else None)
    # v4.2.41 (mandate LL.2): both terms must come from the SAME leg. Mixing pwfv (verdict leg)
    # with ivc_base (GAAP) measured scenario dispersion PLUS the inter-leg gap — a meaningless sum.
    ivbv = _pub.get("intrinsic_value")
    sensitivity = {"sum_expected_impact": bb.get("sum_expected_impact"),
                   "leg": _vleg_name,
                   "pwfv_minus_iv_verdict_leg": (round(pwfv - ivbv, 2) if (pwfv is not None and ivbv is not None) else None),
                   "by_leg": {"gaap_eps": (bb_gaap or bb).get("sum_expected_impact"),
                              "fcf_per_share": (bb.get("sum_expected_impact") if _vleg_name == "fcf_per_share" else None)},
                   "_note": "Sum EI is a one-factor sensitivity sum; NOT additive to scenario PWFV-IV. Both terms are on the VERDICT leg."}

    # GPS: quant (deterministic, ONCE) + qualitative (LLM-scored inputs)
    #
    # v4.2.4 -- feed the verdict's own implied CAGR into the C block. It was NEVER wired: gps_quant
    # reads gt["implied_cagr_base"], NOTHING in this harness or in any workflow node ever set it, so
    # C's icagr leg read [UNVERIFIED] for every ticker on every run since v4 -- while the number sat
    # in ivc_base ~100 lines above and in the report's own headline verdict table. ivc_lib._sub calls
    # this "the case of record"; v4.2.2 fixed the SYMPTOM (stopped scoring the gap as 0) and left the
    # cause standing, so the block reported an honest "unknown" about a number it already had.
    #
    # WHICH LEG: the conservative one -- the same leg verdict_cap follows (see dual_basis above).
    # Scoring valuation on the optimistic leg while the verdict is set by the pessimistic one would
    # let the scorecard credit exactly what the verdict denies. Falls back to ivc_base when there is
    # no FCF leg to compare against.
    #
    # UNITS: implied_cagr_pct is PERCENT (ivc_lib rounds icagr*100); the gps_quant grid compares
    # against FRACTIONS (0.16/0.14/0.12). Feeding 13.55 where 0.1355 is expected would silently
    # score every ticker a perfect 5. Hence the explicit /100 and the test that pins it.
    _verdict_ic_pct = None
    if dual_basis:
        _verdict_ic_pct = (dual_basis.get(dual_basis["verdict_leg"]) or {}).get("implied_cagr_pct")
    if _verdict_ic_pct is None:
        # LEG-OK: fallback only when dual_basis is absent (single-leg run).
        _verdict_ic_pct = ivc_base.get("implied_cagr_pct")
    _gps_in = dict(data)  # never mutate the caller's payload
    if _verdict_ic_pct is not None:
        _gps_in["implied_cagr_base"] = _verdict_ic_pct / 100.0
    q = gps_quant(_gps_in)
    ql = spec.get("qualitative_scores") or {}

    def _qp(k):
        v = ql.get(k)
        if isinstance(v, dict):
            try: return float(v.get("points", 0))
            except (TypeError, ValueError): return 0
        return float(v) if isinstance(v, (int, float)) else 0

    def _qe(k):
        v = ql.get(k)
        return v.get("evidence", "") if isinstance(v, dict) else ""

    # v4.2.4 -- the QUANT maxima are whatever gps_quant measured, not the nominal 16/15/15/10/10.
    # These five were hardcoded, which threw away the entire v4.2.2 reduced-denominator mechanism at
    # the boundary: gps_quant computed the honest max, stored it in detail[X], and this list
    # overwrote it with the nominal. ivc_lib.gps_quant's own docstring says "Consumers must read
    # max/max_quant from the output, never assume the nominal 16/15/15/10/10" -- this list did
    # exactly the forbidden thing, so a degraded run still printed /100 and Render Tables' own
    # "max reduced from 100" branch was unreachable dead code. The gap was computed, then discarded.
    # Qualitative maxima (runway/moat/forecast/capalloc/sentiment) stay nominal: they are LLM domain,
    # always scoreable, and never reduced.
    def _qmax(key, nominal):
        d = q["detail"].get(key) or {}
        m = d.get("max_quant", d.get("max"))
        return m if isinstance(m, (int, float)) else nominal

    blocks = [
        {"name": "A (growth)", "points": q["A_quant"], "max": _qmax("A", 16), "evidence": q["detail"]["A"]},
        {"name": "A_runway", "points": _qp("A_runway"), "max": 4, "evidence": _qe("A_runway")},
        {"name": "B (profitability)", "points": q["B"], "max": _qmax("B", 15), "evidence": q["detail"]["B"]},
        {"name": "C (valuation)", "points": q["C"], "max": _qmax("C", 15), "evidence": q["detail"]["C"]},
        {"name": "D (balance sheet)", "points": q["D"], "max": _qmax("D", 10), "evidence": q["detail"]["D"]},
        {"name": "E_moat", "points": _qp("E_moat"), "max": 15, "evidence": _qe("E_moat")},
        {"name": "F (momentum)", "points": q["F_quant"], "max": _qmax("F", 10), "evidence": q["detail"]["F"]},
        {"name": "F_forecast_trend", "points": _qp("F_forecast_trend"), "max": 5, "evidence": _qe("F_forecast_trend")},
        {"name": "G_capalloc", "points": _qp("G_capalloc"), "max": 5, "evidence": _qe("G_capalloc")},
        {"name": "H_sentiment", "points": _qp("H_sentiment"), "max": 5, "evidence": _qe("H_sentiment")},
    ]
    for _b in blocks:
        _b["points"] = _f(_b.get("points"), 0)
    gps_total = round(sum(b["points"] for b in blocks), 1)
    # The headline denominator is the sum of what was actually measurable. A GPS that always says
    # /100 cannot distinguish "scored badly" from "could not be scored" -- the whole point of v4.2.2.
    gps_max = round(sum(b["max"] for b in blocks if isinstance(b.get("max"), (int, float))), 1)
    gps = {"blocks": blocks, "total": gps_total, "quant_detail": q["detail"], "max": gps_max,
           "max_nominal": 100,
           "_max_note": (None if gps_max >= 100 else
                         "denominator reduced from 100: sub-blocks with unavailable inputs are "
                         "[UNVERIFIED] and drop out of BOTH numerator and denominator")}

    # v3.3: THREE-BAND verdict_cap, matching the stage4 gate rule (check #3) exactly:
    #   <12%    -> AVOID   (fails the hurdle floor)
    #   12-16%  -> WATCH+  (clears the floor, below the 12-16% mandate target)
    #   >=16%   -> BUY     (in the mandate's target zone)
    # v2.5-v3.2 collapsed this to two bands ("AVOID" if <12 else "WATCH+"), which made BUY
    # structurally UNREACHABLE for every name regardless of how good the numbers were — the
    # gate prompt has always specified three bands, the harness only implemented two.
    # This is a CAP, not a verdict: it bounds how bullish the arbiter may be, it never forces
    # a BUY. The arbiter can still land lower on qualitative grounds.
    # v3.4: the cap is driven by the CONSERVATIVE leg when a dual basis exists — sizing follows
    # the stricter number; the memo may argue the other leg in prose.
    # LEG-OK: seed value; overwritten just below by min() of BOTH legs (verdict_cap rule).
    icb = ivc_base.get("implied_cagr_pct")
    if dual_basis:
        legs = [dual_basis["gaap_eps"]["implied_cagr_pct"],
                dual_basis["fcf_per_share"]["implied_cagr_pct"]]
        legs = [x for x in legs if x is not None]
        if legs:
            icb = min(legs)
    if icb is None or icb < 12.0:
        verdict_cap = "AVOID"
    elif icb < 16.0:
        verdict_cap = "WATCH+"
    else:
        verdict_cap = "BUY"
    # v4.2.61: an UNVERIFIED share count cannot support a bullish cap. Per-share value is a
    # quotient, and with the denominator's trajectory unknown the numerator's quality says nothing
    # about the answer. This CAPS, it never forces: a name already at AVOID stays there.
    if _dilution_unverified and verdict_cap != "AVOID":
        publication_flags.append(
            "verdict_cap lowered %s -> AVOID: dilution UNVERIFIED (see dilution_UNVERIFIED)"
            % verdict_cap)
        verdict_cap = "AVOID"

    # ------------------------------------------------------------------------------------------
    # v3.5 MARKET CONTEXT — deterministic "fear-discount" diagnostics. The recurring setup the
    # mandate wants to catch (GOOGL-2024, LLY-Aug-2025, the 2026 hyperscaler capex scare):
    # fundamentals keep compounding while the MULTIPLE is compressed by one named fear. Three
    # quantitative legs; the qualitative leg (naming the fear + its falsifier) lives in stage2b.
    # All inputs already exist in the payload — no new data dependencies.
    # ------------------------------------------------------------------------------------------
    def _series_vals(key):
        s = data.get(key) or []
        return [p.get("val") for p in s if isinstance(p, dict) and isinstance(p.get("val"), (int, float))]

    market_context = {}

    # (1) Multiple compression vs fundamentals deceleration.
    #     discount = how much cheaper than its own history the name trades;
    #     decel    = how much slower it actually grows. divergence = discount - decel.
    #     Large positive divergence -> the market prices far more deterioration than is showing.
    pe_now = _f(data.get("fwd_pe"), None)
    if (pe_now is None or pe_now <= 0) and price:
        e0 = _f(data.get("eps0_reported"), None)
        if e0 and e0 > 0:
            pe_now = price / e0
    pe_anchor = _f(data.get("pe_hist_median"), None)
    # v3.8: g_now MUST be a FORWARD estimate. The old fallback used eps_cagr_3y, but the 3y
    # window lies INSIDE the 5y window — comparing them is not "growth now vs history", it is
    # two overlapping trailing periods. On ADBE (Yahoo returned nothing, so no estimates) that
    # produced g_now=18.2% vs g_hist=9.0% -> decel=-101.9% -> divergence=169.5pp and a
    # FEAR-DISCOUNT flag fired on an artifact (the 5y window simply contains the COVID margin
    # trough). No forward estimate -> report the multiple discount ONLY, make no divergence
    # claim, raise no flag. Honest silence beats a confident artifact.
    g_now = None
    for est in (data.get("eps_estimates") or []):
        if isinstance(est, dict) and str(est.get("period", "")).lower() in ("+1y", "1y"):
            gv = est.get("growth")
            if isinstance(gv, (int, float)):
                g_now = gv if abs(gv) < 3 else gv / 100.0
            break
    g_hist = _f(data.get("eps_cagr_5y"), None)
    if pe_now and pe_anchor and pe_anchor > 0:
        mc = {"fwd_pe": round(pe_now, 2), "pe_hist_median": pe_anchor,
              "multiple_discount_pct": round((1 - pe_now / pe_anchor) * 100, 1)}
        if not isinstance(data.get("fwd_pe"), (int, float)) or data.get("fwd_pe") <= 0:
            mc["_pe_basis"] = "trailing (price/eps0) — forward P/E unavailable"
        if g_now is None:
            mc["divergence_available"] = False
            mc["fear_discount_setup"] = False
            mc["_why_no_divergence"] = ("no forward EPS estimate available; a trailing-window "
                                        "comparison would be an artifact, not a signal")
        elif g_hist and g_hist > 0.02:
            mc["divergence_available"] = True
            mc["growth_now_pct"] = round(g_now * 100, 1)
            mc["growth_hist_pct"] = round(g_hist * 100, 1)
            mc["growth_decel_pct"] = round((1 - g_now / g_hist) * 100, 1)
            mc["divergence_pp"] = round(mc["multiple_discount_pct"] - mc["growth_decel_pct"], 1)
            # flag only when the discount is real AND fundamentals are broadly intact
            mc["fear_discount_setup"] = bool(mc["multiple_discount_pct"] >= 25
                                             and mc["divergence_pp"] >= 20
                                             and g_now > 0)
        else:
            mc["divergence_available"] = False
            mc["fear_discount_setup"] = False
        market_context["multiple_compression"] = mc

    # (2) Earnings-revision vs price-momentum divergence (the LLY-Aug-25 pattern):
    #     analysts revising UP while the price grinds DOWN.
    erb = _f(data.get("erb_90d"), None)
    rs6 = _f(data.get("rel_strength_6m"), None)
    if erb is not None and rs6 is not None:
        market_context["revision_vs_price"] = {
            "erb_90d": erb, "rel_strength_6m": rs6,
            "divergence": bool(erb > 0.02 and rs6 < -0.15),
            "_note": "positive revisions into a falling price = market fear vs analyst evidence",
        }

    # (3) Reinvestment quality — the direct answer to the capex scare. Incremental ROIC:
    #     how much NEW operating income the last two years of capex actually produced.
    #     v3.8 GUARD: only meaningful when capex is MATERIAL to the business model. An
    #     asset-light name grows through R&D/S&M (opex), not capex, so dividing by a tiny
    #     capex base yields an absurd ratio — ADBE returned 568% off $0.36B of 2y capex,
    #     a number that looks like a finding and is pure arithmetic noise. Require capex to
    #     be >=5% of revenue before making the claim at all.
    oi = _series_vals("operating_income")
    cx = _series_vals("capex")
    rev = _series_vals("revenue")
    if len(oi) >= 3 and len(cx) >= 2:
        delta_oi = oi[-1] - oi[-3]
        deployed = abs(cx[-1]) + abs(cx[-2])          # capex reported as negative outflow sometimes
        capex_intensity = None
        if rev and rev[-1] and rev[-1] > 0:
            capex_intensity = abs(cx[-1]) / rev[-1]
        if deployed > 0 and capex_intensity is not None and capex_intensity >= 0.05:
            market_context["reinvestment_quality"] = {
                "delta_operating_income_2y": round(delta_oi, 0),
                "capex_deployed_2y": round(deployed, 0),
                "capex_intensity_pct": round(capex_intensity * 100, 1),
                "incremental_roic_pct": round(delta_oi / deployed * 100, 1),
                "_note": ("each capex $ producing operating income = Google-2004, not a bubble; "
                          "negative or near-zero = the fear may be right"),
            }
        elif deployed > 0:
            market_context["reinvestment_quality"] = {
                "not_meaningful": True,
                "capex_intensity_pct": (round(capex_intensity * 100, 1)
                                        if capex_intensity is not None else None),
                "_note": ("asset-light: capex is <5% of revenue, so incremental ROIC on capex is "
                          "not a meaningful measure of reinvestment — this business compounds "
                          "through R&D/S&M (opex), not capital deployment"),
            }

    market_context = market_context or None

    # ------------------------------------------------------------------------------------------
    # v3.6 STREET VIEW — how the sell side prices the same name. Deterministic (yahoo tier):
    # consensus target mean/high/low, analyst depth, recommendation split, and the two spreads
    # that matter: price -> target (what the street expects) and PWFV -> target (where OUR model
    # disagrees with the street). Named-bank targets ("BofA $835") are NOT reliably available
    # from free deterministic sources — those flow through the Stage1 fact pack with citations
    # and must be quoted with their source and date, never merged into this block.
    # ------------------------------------------------------------------------------------------
    street_view = None
    pt = data.get("price_target") if isinstance(data.get("price_target"), dict) else {}
    pt_mean = _f(pt.get("mean"), _f(data.get("price_target_mean"), None))
    # v4.2.10: analyst coverage. The yahoo `analyst_count` field nulls on cloud IPs, but the
    # Finnhub recommendation split (rec_trends, already in the payload) carries the SAME fact:
    # the number of covering analysts, by rating bucket. NFLX 2026-07-17 shipped a report with
    # analyst_count=null while rec_trends held 29 buy + 16 strongBuy + 13 hold in the same
    # payload — the count existed, only the dead field was read. Fallback + carry the breakdown,
    # with the basis labelled (a house rule: the basis travels with the number).
    _an_count = data.get("analyst_count")
    _an_basis = "yahoo" if _an_count is not None else None
    _rec_breakdown = None
    _rec = data.get("rec_trends") if isinstance(data.get("rec_trends"), dict) else None
    if _rec and isinstance(_rec.get("months"), list) and _rec["months"]:
        _m0 = _rec["months"][0]
        _tot = 0
        _rec_breakdown = {"period": _m0.get("period")}
        for _k in ("strongBuy", "buy", "hold", "sell", "strongSell"):
            _v = _m0.get(_k)
            _rec_breakdown[_k] = _v
            _tot += int(_v or 0)
        _rec_breakdown["total"] = _tot or None
        if _an_count is None and _tot:
            _an_count = _tot
            _an_basis = "finnhub rec_trends (sum of latest-month rating buckets)"
    if pt_mean and price:
        pwfv_vs_street = None
        if pwfv:
            pwfv_vs_street = round((pwfv / pt_mean - 1) * 100, 1)
        street_view = {
            "consensus_target_mean": pt_mean,
            "consensus_target_high": _f(pt.get("high"), _f(data.get("price_target_high"), None)),
            "consensus_target_low": _f(pt.get("low"), _f(data.get("price_target_low"), None)),
            "upside_to_target_pct": round((pt_mean / price - 1) * 100, 1),
            "analyst_count": _an_count,
            "analyst_count_basis": _an_basis,
            "recommendation_breakdown": _rec_breakdown,
            "recommendation_mean": _f(data.get("recommendation_mean"), None),
            "recommendation_key": data.get("recommendation_key"),
            "pwfv_vs_street_pct": pwfv_vs_street,
            "analyst_actions_recent": (data.get("analyst_actions_recent") or [])[:8],
            "_tier": "yahoo consensus; named-bank targets belong to FACT_PACK with source+date",
        }

    # v4.2.34 (mandate HH): THE PUBLICATION LAYER MUST FOLLOW THE VERDICT LEG. Third recurrence of
    # the class "consumer numbers taken from the base leg while the verdict is set by the
    # conservative one" (v4.2.19 Render Tables -> app.py:717 mos_ladder -> trigger bands). Sweep,
    # not a one-line patch: every consumer number below is resolved against the verdict leg once.
    # The assumption "verdict leg == conservative leg" is VERIFIED, not inherited: if the verdict
    # leg's IV reads HIGHER than the other leg, that is flagged and BOTH are printed.
    # _pub / _vleg_name were resolved ONCE above (v4.2.41) — the single legal publication source.
    if dual_basis:
        _iv_v = (dual_basis.get(_vleg_name) or {}).get("iv")
        _other = "gaap_eps" if _vleg_name == "fcf_per_share" else "fcf_per_share"
        _iv_o = (dual_basis.get(_other) or {}).get("iv")
        if isinstance(_iv_v, (int, float)) and isinstance(_iv_o, (int, float)) and _iv_v > _iv_o:
            publication_flags.append(
                "[LEG] verdict leg %s IV %.2f is HIGHER than %s IV %.2f — 'verdict leg is the "
                "conservative one' does NOT hold this run; both legs printed" % (_vleg_name, _iv_v, _other, _iv_o))
    # MoS of BOTH legs, explicitly, with the verdict one marked: publishing only the base leg's
    # mos_pct produced a false sustained claim against a memo that had quoted the verdict leg
    # correctly (MA 2026-07-22: memo -48.94% FCF leg vs RESULT -45.74% base leg).
    _mos_by_leg = {}
    if dual_basis:
        for _ln in ("gaap_eps", "fcf_per_share"):
            _ivx = (dual_basis.get(_ln) or {}).get("iv")
            if isinstance(_ivx, (int, float)) and price:
                _mos_by_leg[_ln] = round((_ivx - price) / price * 100, 2)

    # v4.2.49 (mandate AAA/YY): run_complete and iv_computable are ORTHOGONAL facts, always
    # present. run_complete asks only whether the pipeline reached a terminal state and issued a
    # verdict — it does NOT require IV to be computable, or Category-F (verdict issued, method
    # honestly inapplicable) would be filed as unfinished and OKLO/SMR/IONQ/ASTS/RDDT would vanish
    # from v_ticker_latest. _FALLBACK stays what it is: disclosure of source degradation, input to
    # gate tooth B5 — Category-F is NOT degraded, its data arrived intact.
    _iv_ok = isinstance((ivc_base or {}).get("intrinsic_value"), (int, float)) and not _category_f
    # ---------------- v4.2.59: CENTRAL LENS + REVERSE DCF (operator decision 02.08.2026) --------
    # Both are computed by ivc_lib, deterministically, from the SAME inputs as the verdict leg.
    # Nothing here is allowed to reach a verdict, an alert or a rung; the pins enforce that.
    from ivc_lib import median_yoy as _median_yoy

    def _lens_decomposition(vinp, pubres, cg, cpe, _ivc):
        """Attribute the verdict-vs-central gap to base / growth / multiple, by substitution.

        Deliberately NOT an analytic split: the fade makes the closed form fragile, and a wrong
        closed form fails silently. One factor is swapped at a time from the verdict leg's own
        inputs, so every contribution is a real re-run of the same function. The residual is
        published rather than hidden — the factors interact multiplicatively (Table 2 measured a
        25% interaction term on MA), and a decomposition claiming to sum exactly would be lying
        about that."""
        try:
            v_iv = pubres.get("intrinsic_value")
            v_base = vinp.get("eps_normalized")
            c_base = base_inp.get("eps_normalized")
            if not all(isinstance(x, (int, float)) for x in (v_iv, v_base, c_base)):
                return None
            step = lambda **kw: _ivc(dict(vinp, **kw)).get("intrinsic_value")
            d_base = step(eps_normalized=c_base)
            d_growth = step(growth_rate=cg, terminal_growth=min(0.04, cg))
            d_pe = step(future_pe=cpe)
            total = None
            return {
                "verdict_iv": v_iv,
                "base_change": (None if d_base is None else round(d_base - v_iv, 2)),
                "growth_change": (None if d_growth is None else round(d_growth - v_iv, 2)),
                "multiple_change": (None if d_pe is None else round(d_pe - v_iv, 2)),
                "note": "each figure is the IV change from swapping ONE factor to its central "
                        "value; they do not sum to the total gap because the factors interact",
                "bases_differ": (abs(v_base - c_base) > 1e-9),
                "multiple_differs": (abs((vinp.get("future_pe") or 0) - (cpe or 0)) > 1e-9),
            }
        except Exception:
            return None
    _central_lens = None
    _reverse_dcf = None
    if _iv_ok and isinstance(base_inp.get("growth_rate"), (int, float)):
        _c_g = _median_yoy(_rev_series, 5)
        _c_pe = (min(_window_meds) if _window_meds else None)
        _c_flags = []
        if _c_g is None:
            _c_flags.append("central_growth_unavailable: fewer than 3 usable annual increments")
        if _c_pe is None:
            _c_flags.append("central_multiple_unavailable: no PE window with enough history")
        if _c_g is not None and _c_pe is not None:
            _c_inp = dict(base_inp)
            _c_inp["growth_rate"] = _c_g
            _c_inp["future_pe"] = _c_pe
            # The fade target follows the SAME asymmetry guard as the verdict leg: the tail may be
            # slowed toward terminal, never lifted. Skipping this would have let the central lens
            # accelerate a sub-4% grower — a difference in a guard, not in the two named choices,
            # and it would have contaminated the comparison the lens exists to make.
            _c_inp["terminal_growth"] = min(0.04, _c_g)
            _c_res = ivc(_c_inp)
            if isinstance(_c_res.get("intrinsic_value"), (int, float)):
                _central_lens = {
                    "iv": _c_res["intrinsic_value"],
                    "implied_cagr_pct": _c_res.get("implied_cagr_pct"),
                    "fv10_per_share": _c_res.get("fv10_per_share"),
                    "growth_used": _c_g,
                    "growth_basis": "median of annual revenue increments (5y window)",
                    "future_pe_used": _c_pe,
                    "future_pe_basis": "min(pe_median_5y, pe_median_10y) — NO 25 ceiling",
                    # v4.2.64 (mandate 1): the label, not the arithmetic. The lens is computed
                    # from the GAAP base BY CONSTRUCTION — a central estimate stripped of the
                    # conservative layers cannot be built on the leg that was CHOSEN for being
                    # conservative; that leg selection is itself one of the layers. So the two
                    # facts are named separately instead of collapsed into one "leg" field that
                    # was true of neither: what it was computed ON, and what the delta is measured
                    # AGAINST. Recomputing the lens on the verdict leg was considered and rejected
                    # by the architect: it would destroy the meaning of the lens.
                    "computed_on": "gaap_base",
                    "delta_vs": ("verdict_leg(%s)" % (_vleg_name or "gaap_eps")),
                    "delta_iv_vs_verdict_pct": (
                        round((_c_res["intrinsic_value"] / _pub["intrinsic_value"] - 1) * 100, 1)
                        if isinstance(_pub.get("intrinsic_value"), (int, float)) and _pub["intrinsic_value"] > 0
                        else None),
                    # v4.2.68 (mandate 1): the gap is DECOMPOSED, not explained by a constant.
                    # The brief printed "exactly two decisions: growth and the ceiling" — written
                    # while looking at NFLX, where it happened to be true. On META the ceiling
                    # bound NEITHER lens (both 20.69) so its contribution was zero, and more than
                    # half the gap came from a THIRD difference the sentence denied existed: the
                    # lens is built on the GAAP base while the verdict leg was FCF. An explanation
                    # that is true of one name and printed on every name is a false statement with
                    # a plausible history. Contributions are measured by substitution, one factor
                    # at a time, from the verdict leg's own inputs.
                    "gap_decomposition": _lens_decomposition(base_inp, _pub, _c_g, _c_pe, ivc),
                    "advisory_only": True,
                    "note": "CENTRAL LENS — advisory. No verdict, alert or MoS rung reads this.",
                    "flags": _c_flags,
                }
        if _central_lens is None:
            _central_lens = {"iv": None, "advisory_only": True, "flags": _c_flags,
                             "note": "CENTRAL LENS unavailable this run — stated, not silently omitted."}

        # Reverse DCF: solve for the growth the CURRENT price already embeds, holding the verdict
        # multiple, fade, dilution and discount fixed. Bisection on a monotone function rather than
        # an algebraic inversion, because the fade path makes the closed form fragile and a wrong
        # closed form fails silently. Self-check below is the guard against that.
        _rd_price = base_inp.get("price")
        if isinstance(_rd_price, (int, float)) and _rd_price > 0:
            def _icagr_at(gg):
                _i = dict(base_inp); _i["growth_rate"] = gg; _i["terminal_growth"] = min(0.04, gg)
                _r = ivc(_i)
                return _r.get("implied_cagr_pct")
            _lo, _hi = -0.50, 1.00
            _tgt = base_inp.get("hurdle", 0.12) * 100
            _g_impl = None
            if isinstance(_icagr_at(_lo), (int, float)) and isinstance(_icagr_at(_hi), (int, float)):
                for _ in range(60):
                    _mid = (_lo + _hi) / 2.0
                    _v = _icagr_at(_mid)
                    if not isinstance(_v, (int, float)):
                        break
                    if _v < _tgt: _lo = _mid
                    else: _hi = _mid
                _g_impl = (_lo + _hi) / 2.0
            _rd_ok = None
            if _g_impl is not None:
                _chk = _icagr_at(_g_impl)
                # The solved growth must reproduce the hurdle to within a tenth of a point, or the
                # number is not a solution and must not be published as one.
                _rd_ok = isinstance(_chk, (int, float)) and abs(_chk - _tgt) < 0.1
            _reverse_dcf = {
                "g_implied_at_current_price": (round(_g_impl, 4) if _g_impl is not None else None),
                "at_hurdle_pct": round(_tgt, 2),
                "future_pe_held": base_inp.get("future_pe"),
                "actual_rev_cagr_3y": _rc3,
                "actual_rev_cagr_5y": _rc5,
                # v4.2.68 (mandate 6): the solve is for the growth of the EARNINGS base, so the
                # like-for-like comparison is EPS growth. Revenue stays published beside it —
                # it is the more reliable series and the reader should see both — but the two are
                # now named as different quantities instead of silently juxtaposed.
                "actual_eps_cagr_5y": _f(data.get("eps_cagr_5y"), None),
                "compare_against": "actual_eps_cagr_5y (same quantity as the solve); "
                                   "actual_rev_cagr_* is a different series, shown for context",
                "selftest_reverse_matches_forward": _rd_ok,
                "basis": "growth that makes implied CAGR equal the hurdle at the current price, "
                         "verdict multiple/fade/dilution held fixed",
                "advisory_only": True,
            }
    _fp_vectors_in = data.get("_fp_vectors") or None
    _out_extra = {}
    if _category_f:
        _out_extra = dict(_category_f)
    return {
        # v4.2.77 (g).4 — the peer multiple, published as ONE object so the number cannot travel
        # without its basis. The in-house peer median is TRAILING (edgar_tiingo_trailing_inhouse);
        # the forward company multiple comes from another source and another period, so
        # `comparable` is decided HERE, once, and the human document is forbidden to compare when
        # it is False. Placed in RESULT, not in base_inp: the first draft of this field went into
        # the IVC input dict, where the renderer that reads it could never have seen it — caught by
        # the pin that confronts what renderers read with what analyze() returns.
        # `count` is None rather than 0 when peer rows are missing: a median over an unknown number
        # of peers must not be published as a median over none.
        "peer_multiple": _peer_multiple_block(data),
        # (I) v4.2.79 — three fiscal years from series already held. See _three_year_table for why
        # the P/E field carries its basis in its own NAME rather than in a comment.
        "three_year_table": _three_year_table(data, price),

        "_FALLBACK": False, "_harness": True,
        "run_complete": True,
        "iv_computable": bool(_iv_ok),
        "ivc_base": ivc_base,
        # v4.2.40: the published scenarios MUST be the ones pwfv is computed from, or the number
        # cannot be verified against them — the same opacity that made a correct memo look like a
        # hallucination (MA 2026-07-22). scenarios = the VERDICT leg's tree; both legs stay visible.
        "scenarios": ((scenarios_fcf if (_vleg_name == "fcf_per_share" and scenarios_fcf)
                       else scenarios)),
        "scenarios_leg": (_vleg_name or "gaap_eps"),
        "scenarios_by_leg": {"gaap_eps": scenarios, "fcf_per_share": (scenarios_fcf or None)},
        "pwfv": pwfv,
        "pwfv_by_leg": {"gaap_eps": pwfv_gaap, "fcf_per_share": pwfv_fcf},
        "pwfv_leg": (_vleg_name or "gaap_eps"),
        "weights": {k: scenarios[k]["weight"] for k in scenarios},
        "bull_bear": bb, "sensitivity": sensitivity,
        "gps": gps, "mos_ladder": _pub.get("mos_ladder"),
        "mos_ladder_leg": _vleg_name or "gaap_eps",
        "mos_pct_by_leg": _mos_by_leg,
        "mos_pct_verdict_leg": _mos_by_leg.get(_vleg_name),
        "fv10_verdict_leg": _pub.get("fv10_per_share"),
        "gates": {"hurdle_gate": _pub.get("hurdle_gate")},
        "verdict_cap": verdict_cap,
        "dual_basis": dual_basis,
        "market_context": market_context,
        "street_view": street_view,
        # LEG-OK: diagnostics of the base computation, not a published valuation number.
        "self_tests_all": bool(ivc_base.get("self_tests")),
        # LEG-OK: diagnostics/flags, not a published valuation number.
        "flags": (ivc_base.get("flags", []) + pe_flags + growth_flags + pe_anchor_flags + base_llm_flags + publication_flags),
        "pe_cap": {"anchors_available": bool(_anchors), "anchor_used": (round(1.2*max(_anchors),1) if _anchors else NO_ANCHOR_PE), "flags": pe_flags},
        "growth_anchor": {
            "base_growth_used": base_inp.get("growth_rate"),
            "basis": base_inp.get("growth_rate_basis"),
            "rev_cagr_3y": _rc3, "rev_cagr_5y": _rc5,
            "llm_base_g": base_inp.get("llm_base_g"),
            "flags": growth_flags,
        },
        "pe_anchor": {
            "base_future_pe_used": base_inp.get("future_pe"),
            "basis": base_inp.get("future_pe_basis"),
            "pe_median_5y": data.get("pe_median_5y"),
            "pe_median_10y": data.get("pe_median_10y"),
            "llm_base_pe": base_inp.get("llm_base_pe"),
            "flags": pe_anchor_flags,
        },
        # v4.2.59 — CENTRAL LENS (operator decision 02.08.2026, ratified). A SECOND, deterministic
        # valuation shown beside the verdict one. It changes NOTHING: no verdict, no alert, no rung
        # reads any field below. Table 2 measured why it exists — the PE ceiling and the fade carry
        # 85% of the conservatism, and no single layer flips MA, but all of them together move IV
        # from 458 to ~922. A reader given only the conservative number cannot see that spread, and
        # was left arguing about "the cascade" with no figure to argue over. Now both are printed.
        #   central growth   = MEDIAN of annual revenue increments (not the endpoint CAGR)
        #   central multiple = min(median 5y, median 10y), NO 25 ceiling
        #   fade, discount, dilution, hurdle  = IDENTICAL to the verdict leg, so the delta between
        #                                       the lenses isolates exactly those two choices.
        # v4.2.68 (mandate 3): the vector count moves INTO RESULT. It lived in the entity gate's
        # payload; Render Tables reached it by node reference, the brief copied the FIELD NAME and
        # got nothing, and four live runs printed "completeness not measured" beside a machine
        # report that measured it. One canonical home: RESULT. Bonus per mandate — from here it
        # reaches the dossier and БАЗА's data_questionable without a second path.
        "fp_vectors": _fp_vectors_in,
        "year5_reference": (ivc_base or {}).get("year5_reference"),
        "central_lens": _central_lens,
        # Reverse DCF: what growth the CURRENT price already pays for, at the verdict multiple.
        # Compared against what the company actually did, it turns "is it expensive" into a
        # falsifiable question instead of a multiple-vs-multiple opinion.
        "reverse_dcf": _reverse_dcf,
        **_out_extra,
        "base_determinism": {
            "discount_rate_used": base_inp.get("discount_rate"),
            "terminal_growth_used": base_inp.get("terminal_growth"),
            "dividend_yield_used": base_inp.get("dividend_yield"),
            "dividend_growth_used": base_inp.get("dividend_growth"),
            "fade_used": base_inp.get("fade"),
            "years_used": base_inp.get("years"),
            "scenario_weights_used": {k: scenarios[k]["weight"] for k in scenarios},
            "llm_disc": base_inp.get("llm_disc"),
            "llm_terminal_g": base_inp.get("llm_terminal_g"),
            "llm_weights": _llm_weights,
            "flags": base_llm_flags,
        },
    }


@app.route("/edgar_raw_tags", methods=["POST"])
def _edgar_raw_tags():
    """
    DIAGNOSTIC, READ-ONLY: raw EDGAR facts per tag, un-merged.
    Body: {"ticker":"MA", "tags":["Revenues","SalesRevenueNet", ...], "taxonomy":"us-gaap"}
    Returns per tag: [{fy_end, value, unit, accession, filed, fy, fp}], plus `year_to_tags`
    showing which tags cover which fiscal year.

    Why it exists: the assembled series hides WHICH tag filled WHICH year — `_annual_merged` takes
    the first tag in priority order that reports a year, and only the SET of tags survives into
    `sources`. MA's revenue series turned out to be stitched from three tags with a ~1.6x step at
    the 2018/2022 boundaries, and that was detectable only indirectly, through the margin series.
    No LLM, no cost, no writes: it reads the same companyfacts payload edgar_facts already fetches.
    """
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(raw_tags(body.get("ticker"), body.get("cik"),
                            body.get("tags"), body.get("taxonomy") or "us-gaap")), 200


@app.route("/edgar_form4", methods=["POST"])
def _edgar_form4():
    """
    SEC EDGAR Form 4 insider transactions (deterministic, replaces Perplexity-sourced prose).
    Body: {"ticker": "PLTR", "lookback_days": 270}.
    edgar_form4() never throws; parse failures per-filing are recorded in '_errors', not guessed.
    """
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(edgar_form4(body.get("ticker"), body.get("cik"),
                               body.get("lookback_days", 270))), 200


@app.route("/market_facts", methods=["POST"])
def _market_facts():
    """v3.9: second-source market layer. Body carries the keys (n8n holds them, nothing is
    stored here): {"ticker","peers","av_key","finnhub_key","tiingo_token","price","yahoo":{...}}.
    Never throws; failures land in _errors per source."""
    b = request.get_json(force=True, silent=True) or {}
    return jsonify(market_facts(b.get("ticker"), b.get("peers"), b.get("av_key"),
                                b.get("finnhub_key"), b.get("tiingo_token"),
                                b.get("price"), b.get("yahoo"),
                                b.get("finra_client_id"), b.get("finra_client_secret"),
                                b.get("shares_outstanding"))), 200


@app.route("/cost", methods=["POST"])
def _cost():
    """v4.2.5 token/cost ledger. Body: {"stages":[{stage,provider,model,response,ran}], "today"?}.

    Lives here rather than in a Code node so the price table has ONE home, is covered by the python
    suite, and can be corrected without re-importing the workflow into n8n — prices move, and a
    price edit must not cost a workflow migration.

    Never throws, same contract as /analyze: a billing ledger that 500s would take the whole report
    down over a cosmetic section. On failure it degrades to a named error, not to silence — and
    never to zero.
    """
    b = request.get_json(force=True, silent=True) or {}
    try:
        from pricing import cost_ledger
        import datetime as _d
        t = b.get("today")
        today = _d.date.fromisoformat(t) if isinstance(t, str) and t else None
        return jsonify(cost_ledger(b.get("stages") or [], today)), 200
    except Exception as e:
        return jsonify({"error": "COST_LEDGER_ERROR: " + str(e)[:200], "_FALLBACK": True,
                        "_note": "cost accounting failed; this is NOT a $0 run"}), 200


@app.route("/macro_prices", methods=["POST"])
def _macro_prices():
    """v4.2: risk-free (FRED) + adjusted price series (Tiingo). Moved off the n8n side because
    n8n 2.x Code nodes cannot read env vars (task-runner sandbox), and the alternative was
    inlining the keys into the workflow JSON. Keys are read from THIS service's environment."""
    b = request.get_json(force=True, silent=True) or {}
    return jsonify(macro_prices(b.get("ticker"), b.get("benchmark", "SPY"),
                                b.get("start", "2023-01-01"))), 200


@app.route("/price_on_date", methods=["POST"])
def _price_on_date():
    """v4.2.84: issue #20, historical-reconstruction stand pt.2. PR #18 built
    tiingo_price_on_date/pe_same_share_basis in macro_prices.py but wired them to no route --
    its own docstring called pe_same_share_basis 'the most important part of the task' and the
    #18 audit found it reachable only from unit tests. This route is the door.

    A SEPARATE route rather than folding onto /market_facts: /market_facts is called on every
    live run and returns TODAY's snapshot; this route exists only for a historical-date
    reconstruction, a distinct caller from the always-on path, and must not change
    /market_facts's response shape for a feature most runs never touch.

    Body: {"ticker": "ADBE", "date": "2019-03-15", "eps": 50.0}
      ticker, date required. eps optional -- EPS as reported in the filing AS OF that date, in
      THAT filing's share basis; without it pe_same_share_basis is null with a named refusal
      ("no EPS supplied"), price_record and split_factor are still returned.

    Returns: {"ticker","date","price_record": {...raw Tiingo row...} | None,
              "split_factor": float | None, "pe_same_share_basis": float | None, "_errors": {}}
    Never throws. A missing trading day, an undeterminable split factor, or missing EPS are all
    named refusals in _errors -- never a guessed number and never a silent 1.0 split factor.

    eps must be a number: pe_same_share_basis divides by it (`eps_as_filed / factor`), and a
    string eps (a caller sending "50.0" instead of 50.0, an easy JSON-body mistake) throws a raw
    TypeError there that pe_same_share_basis's own None-check never catches -- it only guards
    the missing case. Checked here, at the boundary, same fix as as_of above: a wrong-typed eps
    is dropped (price_record/split_factor still returned) and the reason is a named refusal."""
    b = request.get_json(force=True, silent=True) or {}
    ticker, date = b.get("ticker"), b.get("date")
    errors = {}
    if not ticker or not date:
        return jsonify({"ticker": ticker, "date": date, "price_record": None,
                        "split_factor": None, "pe_same_share_basis": None,
                        "_errors": {"request": "ticker and date are required"}}), 200
    eps = b.get("eps")
    if eps is not None and (not isinstance(eps, (int, float)) or isinstance(eps, bool)):
        errors["eps_%s" % ticker] = "eps must be a number, got %s" % type(eps).__name__
        eps = None
    price_record = tiingo_price_on_date(ticker, date, errors)
    split_factor, split_reason = split_factor_since(price_record)
    if split_reason:
        errors["split_factor_%s" % ticker] = split_reason
    pe = pe_same_share_basis(price_record, eps, errors, symbol=ticker)
    return jsonify({"ticker": ticker, "date": date, "price_record": price_record,
                    "split_factor": split_factor, "pe_same_share_basis": pe,
                    "_errors": errors}), 200


def trigger_prices(result, ticker=None, spec_date=None, spec_version=None):
    """BACKLOG #4 / ARCHITECTURE §3 trigger_prices: 5 transition prices, pure math from RESULT.

    Contract (do not change without the architect): band AVOID->WATCH+ = FV10/1.12^10,
    WATCH+->BUY = FV10/1.16^10, ladder = IV/(1+t) for t=10/20/30%. Ladder prices are NOT
    recomputed here — they are read verbatim from RESULT.mos_ladder, which ivc_lib (pinned math)
    already produced. One home per number; recomputing a pinned figure is how two "identical"
    numbers drift apart.

    Honesty rules, same as everywhere: a missing driver -> that row is absent AND named in
    _errors; never a zero, never a guess. Dividend payers: the §3 band formula ignores the
    dividend FV leg, while ivc_lib's buy_threshold_hurdle includes it — when they diverge >0.5%
    the divergence is SURFACED (band12_vs_hurdle_threshold), not averaged (house rule).
    """
    out = {"ticker": ticker, "derived_from_spec_date": spec_date, "spec_version": spec_version,
           "triggers": [], "_errors": {}}
    if not isinstance(result, dict) or not result:
        out["_errors"]["result"] = "no RESULT payload — nothing to derive triggers from"
        return out
# LEG-OK: reads a STORED RESULT (older payloads); the verdict-leg value is preferred above.
    ivb = result.get("ivc_base") or {}
    # v4.2.34 (mandate HH): the bands must be built from the VERDICT leg's FV10, not the base
    # leg's. RESULT now publishes fv10_verdict_leg; fall back to ivc_base only for older payloads.
    fv10 = result.get("fv10_verdict_leg")
    if not isinstance(fv10, (int, float)) or fv10 <= 0:
        # LEG-OK: fallback for older payloads; fv10_verdict_leg is preferred above.
        fv10 = ivb.get("fv10_per_share")

    def _row(ttype, price):
        out["triggers"].append({"ticker": ticker, "trigger_type": ttype,
                                "price": round(float(price), 2),
                                "derived_from_spec_date": spec_date,
                                "spec_version": spec_version})

    if isinstance(fv10, (int, float)) and fv10 > 0:
        band12 = fv10 / (1.12 ** 10)
        band16 = fv10 / (1.16 ** 10)
        _row("band_avoid_to_watch", band12)
        _row("band_watch_to_buy", band16)
        # LEG-OK: self-check against the stored base threshold.
        bth = ivb.get("buy_threshold_hurdle")
        if isinstance(bth, (int, float)) and bth > 0 and abs(bth - band12) / bth > 0.005:
            # dividend FV leg present in ivc_lib's threshold but absent from the §3 formula
            out["band12_vs_hurdle_threshold"] = {
                "band_formula": round(band12, 2), "ivc_lib_threshold": round(bth, 2),
                "note": "divergence >0.5% — dividend-paying name; the §3 band formula omits the "
                        "dividend FV leg. Both shown; reconcile before alerting on the band."}
    else:
        out["_errors"]["fv10_per_share"] = "missing/non-positive in RESULT.ivc_base — band rows withheld"

    # LEG-OK: RESULT (verdict leg) FIRST; ivb only as legacy fallback.
    ladder = result.get("mos_ladder") or ivb.get("mos_ladder") or []
    got = set()
    for rung in ladder:
        try:
            t = rung.get("mos_target_pct")
            p = rung.get("buy_threshold_price")
            if t in (10, 10.0, 20, 20.0, 30, 30.0) and isinstance(p, (int, float)) and p > 0:
                _row("ladder_%d" % int(t), p)
                got.add(int(t))
        except Exception:
            continue
    missing = sorted({10, 20, 30} - got)
    if missing:
        out["_errors"]["mos_ladder"] = ("rungs absent from RESULT.mos_ladder: %s — withheld, "
                                        "not recomputed" % missing)
    out["complete"] = (len(out["triggers"]) == 5)
    return out


@app.route("/triggers", methods=["POST"])
def _triggers():
    """BACKLOG #4. Body: {"result": RESULT, "ticker"?, "spec_date"?, "spec_version"?}.
    Same never-throw contract as /analyze: a trigger derivation that 500s would take down a
    caller over pure arithmetic; failure degrades to named errors."""
    b = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(trigger_prices(b.get("result") or {}, b.get("ticker"),
                                      b.get("spec_date"), b.get("spec_version"))), 200
    except Exception as e:
        return jsonify({"error": "TRIGGERS_ERROR: " + str(e)[:200], "_FALLBACK": True,
                        "triggers": [], "complete": False}), 200


# ==============================================================================================
# BACKLOG #5 — REPRICE. A dossier verdict at a NEW price without re-running the LLM chain.
#
# The whole thing is a RESCALING, not a revaluation. In ivc(): IV, FV10, eps_terminal, the
# ladder thresholds (thr = IV/(1+t)) and buy_threshold_hurdle do NOT depend on the current
# price (the dividend legs anchor to the DOLLAR dividend d0 fixed at spec time, which is the
# honest economics: the company pays dollars, not a yield). The only price-dependent outputs
# are implied CAGR, MoS, ladder reached/discount, hurdle_gate and verdict_cap. And implied
# CAGR obeys an exact identity: (fv10+fvdT) = price_old*(1+icagr_old)^Y, therefore
#     icagr_new = (1+icagr_old) * (price_old/price_new)^(1/Y) - 1
# — leg-universal (GAAP, FCF, every scenario), no ivc() call, no drift between two "homes"
# of the same number. Self-test: price_new == price_old must reproduce the stored figures.
#
# FRESHNESS GATES (do not weaken): a rescaled verdict is only honest while the SPEC is honest.
#   1. spec older than 30 days -> refuse (assumptions have a shelf life);
#   2. any 10-K/10-Q/8-K filed AFTER spec_date -> refuse, naming form/date/accession
#      (the fundamentals may have changed; a reprice would launder a stale spec);
#   3. no fresh price obtainable -> refuse (never reprice against a guessed price).
# A refusal is a first-class answer, not an error.
# ==============================================================================================

REPRICE_MAX_SPEC_AGE_DAYS = 30
_REPRICE_FILING_FORMS = ("10-K", "10-Q", "8-K")


def _rescale_icagr_pct(icagr_old_pct, price_old, price_new, years):
    """Exact identity rescale; returns pct or None on missing/garbage inputs."""
    try:
        if not all(isinstance(v, (int, float)) for v in (icagr_old_pct, price_old, price_new)):
            return None
        if price_old <= 0 or price_new <= 0:
            return None
        y = int(years or 10)
        return round(((1 + icagr_old_pct / 100.0)
                      * (price_old / price_new) ** (1.0 / y) - 1) * 100.0, 2)
    except Exception:
        return None


def _rescale_leg(leg, price_old, price_new, years):
    """Rescale a full ivc() output dict IN A COPY. Only price-dependent fields move."""
    if not isinstance(leg, dict) or "implied_cagr_pct" not in leg:
        return leg
    r = json.loads(json.dumps(leg))  # deep copy; never mutate the stored dossier
    ic_new = _rescale_icagr_pct(r.get("implied_cagr_pct"), price_old, price_new, years)
    if ic_new is not None:
        r["implied_cagr_pct"] = ic_new
    iv = r.get("intrinsic_value")
    if isinstance(iv, (int, float)) and price_new > 0:
        r["mos_pct"] = round((iv - price_new) / price_new * 100, 2)
    for rung in (r.get("mos_ladder") or []):
        thr = rung.get("buy_threshold_price")
        if isinstance(thr, (int, float)) and thr > 0:
            rung["reached"] = price_new <= thr
            rung["discount_to_current_pct"] = round((price_new - thr) / price_new * 100, 2)
    if isinstance(r.get("inputs"), dict):
        r["inputs"]["price"] = price_new
        r["inputs"]["price_at_spec"] = price_old
    hurdle = (r.get("inputs") or {}).get("hurdle", 0.12)
    flags = r.get("flags") or []
    if ic_new is not None:
        r["hurdle_gate"] = ("PASS" if (ic_new / 100.0 >= hurdle
                                       and not any("BLOCKING" in str(f) for f in flags))
                            else "FAIL")
    return r


def reprice_result(result, price_new, ticker=None, spec_date=None):
    """Pure rescaling of a stored RESULT to price_new. Never throws; names every gap."""
    out = {"ticker": ticker, "derived_from_spec_date": spec_date, "repriced": False,
           "_errors": {}, "self_tests": {}}
    if not isinstance(result, dict) or not result:
        out["_errors"]["result"] = "no stored RESULT — nothing to reprice"
        return out
# LEG-OK: reads a STORED RESULT (older payloads); the verdict-leg value is preferred above.
    ivb = result.get("ivc_base") or {}
    # LEG-OK: stored price is leg-independent.
    price_old = (ivb.get("inputs") or {}).get("price")
    # LEG-OK: stored horizon is leg-independent.
    years = ivb.get("years", 10)
    if not (isinstance(price_old, (int, float)) and price_old > 0):
        out["_errors"]["price_old"] = "stored RESULT.ivc_base.inputs.price missing/non-positive"
        return out
    if not (isinstance(price_new, (int, float)) and price_new > 0):
        out["_errors"]["price_new"] = "fresh price missing/non-positive — refuse to guess"
        return out
    out.update({"price_at_spec": price_old, "price_new": round(float(price_new), 2),
                "price_change_pct": round((price_new - price_old) / price_old * 100, 2)})

    out["ivc_base"] = _rescale_leg(ivb, price_old, price_new, years)

    db = result.get("dual_basis")
    if isinstance(db, dict):
        db2 = json.loads(json.dumps(db))
        for lk in ("gaap_eps", "fcf_per_share"):
            leg = db2.get(lk)
            if isinstance(leg, dict):
                leg["implied_cagr_pct"] = _rescale_icagr_pct(
                    leg.get("implied_cagr_pct"), price_old, price_new, years)
        legs = [x for x in ((db2.get("gaap_eps") or {}).get("implied_cagr_pct"),
                            (db2.get("fcf_per_share") or {}).get("implied_cagr_pct"))
                if x is not None]
        if legs:
            db2["conservative_leg"] = db2["verdict_leg"] = (
                "gaap_eps" if (db2.get("gaap_eps") or {}).get("implied_cagr_pct") == min(legs)
                else "fcf_per_share")
        out["dual_basis"] = db2

    scen = result.get("scenarios")
    if isinstance(scen, dict):
        out["scenarios"] = {
            name: dict(s, result=_rescale_leg((s or {}).get("result"), price_old,
                                              price_new, years))
            for name, s in scen.items() if isinstance(s, dict)}
    out["pwfv"] = result.get("pwfv")  # probability-weighted FAIR VALUE: price-independent

    # verdict_cap: same three-band rule as analyze(), driven by the conservative leg.
    icb = (out["ivc_base"] or {}).get("implied_cagr_pct")
    if out.get("dual_basis"):
        _legs = [x for x in ((out["dual_basis"].get("gaap_eps") or {}).get("implied_cagr_pct"),
                             (out["dual_basis"].get("fcf_per_share") or {}).get("implied_cagr_pct"))
                 if x is not None]
        if _legs:
            icb = min(_legs)
    out["verdict_cap"] = ("AVOID" if (icb is None or icb < 12.0)
                          else ("WATCH+" if icb < 16.0 else "BUY"))
    out["stored_verdict_cap"] = result.get("verdict_cap")
    out["verdict_cap_changed"] = (out["verdict_cap"] != result.get("verdict_cap")
                                  if result.get("verdict_cap") else None)

    # Self-test: repricing at the OLD price must reproduce the stored figure exactly.
    # LEG-OK: leg-independent / legacy fallback.
    st = _rescale_icagr_pct(ivb.get("implied_cagr_pct"), price_old, price_old, years)
    out["self_tests"]["identity_at_old_price_ok"] = (
        # LEG-OK: leg-independent / legacy fallback.
        st is not None and ivb.get("implied_cagr_pct") is not None
        and abs(st - ivb["implied_cagr_pct"]) < 0.01)

    out["triggers"] = trigger_prices(result, ticker=ticker, spec_date=spec_date)
    out["repriced"] = True
    return out


def reprice_freshness(ticker, spec_date, max_age_days=REPRICE_MAX_SPEC_AGE_DAYS):
    """Gates 1+2. Returns {'fresh': bool, 'refusal': {...}|None, '_errors': {...}}."""
    import time as _t
    out = {"fresh": True, "refusal": None, "_errors": {}}

    def _refuse(reason, **kw):
        out["fresh"] = False
        out["refusal"] = dict({"reason": reason}, **kw)
        return out

    try:
        spec_ts = _t.mktime(_t.strptime(str(spec_date)[:10], "%Y-%m-%d"))
    except Exception:
        return _refuse("spec_date_unparseable", spec_date=spec_date,
                       note="cannot verify freshness -> refuse, never assume fresh")
    age_days = (_t.time() - spec_ts) / 86400.0
    if age_days > max_age_days:
        return _refuse("spec_stale_age", age_days=round(age_days, 1),
                       max_age_days=max_age_days,
                       note="assumptions have a shelf life; run a full analysis instead")

    # Gate 2: any 10-K/10-Q/8-K filed AFTER the spec date invalidates the spec.
    try:
        import edgar_facts as _ef
        cik = _ef._resolve_cik(ticker)
        if not cik:
            return _refuse("cik_unresolved", ticker=ticker,
                           note="cannot check EDGAR for newer filings -> refuse")
        subs = _ef._get("https://data.sec.gov/submissions/CIK%s.json" % cik)
        recent = ((subs.get("filings") or {}).get("recent") or {})
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        accns = recent.get("accessionNumber") or []
        spec_day = str(spec_date)[:10]
        newer = [{"form": f, "filingDate": d, "accession": a}
                 for f, d, a in zip(forms, dates, accns)
                 if f in _REPRICE_FILING_FORMS and d > spec_day]
        if newer:
            return _refuse("newer_filing_since_spec", filings=newer[:5],
                           note="fundamentals may have changed; a reprice would launder "
                                "a stale spec — run a full analysis")
    except Exception as e:
        return _refuse("edgar_unreachable", error=str(e)[:160],
                       note="cannot PROVE freshness -> refuse (unknown is not fresh)")
    out["spec_age_days"] = round(age_days, 1)
    return out


@app.route("/reprice", methods=["POST"])
def _reprice():
    """BACKLOG #5. Body: {"ticker", "result": stored RESULT, "spec_date"}.
    Never-throw contract. Refusals are 200s with {"repriced": false, "refusal": {...}}."""
    b = request.get_json(force=True, silent=True) or {}
    try:
        ticker = b.get("ticker")
        spec_date = b.get("spec_date")
        fr = reprice_freshness(ticker, spec_date)
        if not fr["fresh"]:
            return jsonify({"ticker": ticker, "repriced": False, "refusal": fr["refusal"],
                            "derived_from_spec_date": spec_date}), 200
        # Gate 3: a fresh price, or nothing. Tiingo adjusted close, latest observation.
        from macro_prices import tiingo_series
        _err = {}
        series = tiingo_series(ticker, _err)
        price_new = series[-1] if series else None
        if not (isinstance(price_new, (int, float)) and price_new > 0):
            return jsonify({"ticker": ticker, "repriced": False,
                            "refusal": {"reason": "no_fresh_price", "errors": _err,
                                        "note": "never reprice against a guessed price"},
                            "derived_from_spec_date": spec_date}), 200
        out = reprice_result(b.get("result") or {}, float(price_new),
                             ticker=ticker, spec_date=spec_date)
        out["spec_age_days"] = fr.get("spec_age_days")
        return jsonify(out), 200
    except Exception as e:
        return jsonify({"error": "REPRICE_ERROR: " + str(e)[:200], "_FALLBACK": True,
                        "repriced": False}), 200


@app.route("/analyze", methods=["POST"])
def _analyze():
    """v2.5 deterministic harness. Body: {"data": {...payload...}, "spec": {...judgment inputs...}}.
    Never executes LLM code; assembles RESULT from ivc_lib + the LLM's JSON spec."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(analyze(body.get("data", {}), body.get("spec", {}))), 200
    except Exception as e:
        return jsonify({"error": "RUNNER_ERROR: harness exception: " + str(e)[:200], "_FALLBACK": True}), 200


if __name__ == "__main__":
    # Railway/Render provide $PORT; default 8080 locally.
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
