# ORCL — ORACLE CORP — GROWTH ALPHA Report (2026-08-04)
> Mandate: 12–16% CAGR / 10y, hurdle 12% (floor). DI=6.5 [CONTESTED] | final: AVOID | rung 20% (base — no directional signal) | 🔴 CONTESTED (quality flag — review the verification list; NOT a trade block)
> ⚠️ DI reached CONTESTED purely on MAJOR volume (13 x 0.5); zero BLOCKING, no flip - review whether the manual-verification list is material before treating trades as blocked. Changing the formula itself (cap / sustained-share) is an operator decision, not an automatic one: CONTESTED is a gate.
> 🟠 FACT_PACK vectors: 4/5 [UNVERIFIED] (80%) | 🟠 data_questionable — most of the qualitative side is absent, not merely thin | threshold 30% (PROVISIONAL calibration, n=4 (1 clean); recalibrate at 6 clean runs)

## Why these parameters

*Printed by the assembler from constants — not written by a model. Each line carries its date and author.*

- **Entry rung 20%** — operator decision 23.07 / 02.08.2026: insurance against calculation error. Its price is measured — -16.7% on the entry price ($458 -> $382 on MA). Raised only by directional signals, never by DI class.
- **P/E ceiling 25** — architect mandate, CONSERVATIVE lens: insurance against multiple compression. The CENTRAL lens is computed WITHOUT it; the question stays open until the validation matrix (Table 2: this layer is worth +33.8% of IV on MA).
- **Fade to 4% terminal** — Graham-Dodd standard: no company outgrows the economy forever. The tail may only be slowed toward terminal, never lifted.
- **Growth base min(3y, 5y)** — protection against paying up front for one good stretch: endpoints cannot be flattered by a strong middle. The CENTRAL lens uses the median of annual increments instead.
- **Verdict from the conservative lens** — the cost of being wrong is asymmetric in money: overpaying costs capital, a missed idea costs return.

## 0. EDGAR provenance & cross-check (SEC first-source + sanity gates)
```json
{
  "flags": {
    "confirmed_splits_none": "no retroactive share-count restatement found in companyfacts+companyconcept 10-K history; a clean ratio jump downstream is UNCONFIRMED, not proven dilution",
    "debt_components_incomplete": "components sum built from current only — INCOMPLETE by construction, not comparable to a full LongTermDebt figure",
    "dropped_zero": {
      "revenue": [
        "2008-05-31",
        "2009-05-31"
      ]
    },
    "margin_step_business_event": [
      {
        "cosignal_changed": [
          "accession"
        ],
        "end": "2022-05-31",
        "in_cagr_window_3y": false,
        "in_cagr_window_5y": true,
        "jump_pct": 31.5,
        "prev_end": "2021-05-31",
        "prev_ratio": 0.3758,
        "prev_tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "provenance_changed": [],
        "provenance_uncomparable": [],
        "ratio": 0.2574,
        "tag": "RevenueFromContractWithCustomerExcludingAssessedTax"
      }
    ],
    "tag_conflict": {
      "dps": [
        {
          "absent_years": [
            "2008",
            "2009"
          ],
          "chosen_tag": "CommonStockDividendsPerShareCashPaid",
          "note": "single-tag series chosen on window coverage; years outside the anchor windows are absent by construction"
        }
      ],
      "ocf": [
        {
          "absent_years": [
            "2014",
            "2015"
          ],
          "chosen_tag": "NetCashProvidedByUsedInOperatingActivities",
          "note": "single-tag series chosen on window coverage; years outside the anchor windows are absent by construction"
        }
      ],
      "revenue": [
        {
          "end": "2010-05-31",
          "spread_pct": 91.5,
          "values": {
            "Revenues": 26820000000,
            "SalesRevenueNet": 2290000000
          }
        },
        {
          "end": "2011-05-31",
          "spread_pct": 80.5,
          "values": {
            "Revenues": 35622000000,
            "SalesRevenueNet": 6944000000
          }
        },
        {
          "absent_years": [
            "2008",
            "2009",
            "2010",
            "2011",
            "2012",
            "2013",
            "2014",
            "2015",
            "2016"
          ],
          "chosen_tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
          "note": "single-tag series chosen on window coverage; years outside the anchor windows are absent by construction"
        }
      ]
    },
    "total_debt_computed": "LongTermDebt"
  },
  "divergence": {
    "short_term_investments": {
      "edgar": 605000000,
      "gather": 45641000000,
      "pct": 98.7
    },
    "total_debt": {
      "edgar": 0,
      "gather": 129541000000,
      "pct": 100
    }
  },
  "sources": {
    "capex": [
      "PaymentsToAcquirePropertyPlantAndEquipment"
    ],
    "cash": "CashAndCashEquivalentsAtCarryingValue",
    "dividends_paid": [
      "PaymentsOfDividendsCommonStock"
    ],
    "dps": [
      "CommonStockDividendsPerShareCashPaid"
    ],
    "gross_profit": [
      "GrossProfit"
    ],
    "net_income": [
      "NetIncomeLoss"
    ],
    "ocf": [
      "NetCashProvidedByUsedInOperatingActivities"
    ],
    "operating_income": [
      "OperatingIncomeLoss"
    ],
    "revenue": [
      "RevenueFromContractWithCustomerExcludingAssessedTax"
    ],
    "rpo": "RevenueRemainingPerformanceObligation",
    "sbc": [
      "ShareBasedCompensation"
    ],
    "shares_current": "dei:EntityCommonStockSharesOutstanding (companyfacts)",
    "shares_diluted": [
      "WeightedAverageNumberOfDilutedSharesOutstanding"
    ],
    "short_term_investments": "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    "total_debt": "LongTermDebt"
  },
  "cik": "0001341439",
  "entity_name": "Oracle Corporation"
}
```

## 1. Numeric layer (deterministic, Python)
**CENTRAL LENS:** IV 110.52 (growth 8.4% = median of annual increments; P/E 27.5 = window median, NO 25 ceiling) | computed on gaap_base, delta vs verdict_leg(gaap_eps) = -12.6% | ADVISORY: no verdict, alert or entry rung reads this.

**REVERSE DCF:** the current price already pays for 12.3% growth (multiple 27.5 held, hurdle 12.0%). Actual: 3y 10.5%, 5y 10.7%.

### Verdict (deterministic layer)
| TICKER | GPS | implied_cagr (GAAP) | PWFV | MoS (GAAP) | verdict_cap |
| --- | --- | --- | --- | --- | --- |
| ORCL | 51/100 | 10.72% | $143.53 | -10.83% | AVOID |

### Fundamentals snapshot
| Metric | Value |
| --- | --- |
| Gross profit | [UNVERIFIED] — source returned 0.00B against revenue $67.36B (stale/implausible <2% margin artifact; see section 0 flags) |
| Total debt | $0.00B _(source: combined_short_long)_ |
| Implied interest rate | 3.55% (interest expense / total debt) |
| Forward P/E | 16.08 _(basis: AV ForwardPE reported (computation unavailable; official second source))_ |
| PEG | 0.73 _(fwd P/E / fwd EPS growth %, house convention)_ |
| Analyst coverage | 49 analysts (15 strong buy, 25 buy, 8 hold, 1 sell) as of 2026-08-01 — Finnhub recommendation split |
_Consensus panels are anonymized aggregates — no free feed publishes which firms sit in the average. Named analyst actions (firm, date, target) appear in the Fact Pack STREET section only._

### Market context — is this a fear discount?
| Metric | Value |
| --- | --- |
| P/E vs own history | 16.08 vs 27.53 (discount 41.60%) |
| Divergence | **not computed** — no forward EPS estimate available; a trailing-window comparison would be an artifact, not a signal |

⚑ **Revision/price divergence:** analyst estimates revising UP (ERB 2.80%) into a FALLING price (rel 6m -23.27%).

**Short interest (FINRA, primary source):** 50.07M shares as of 2026-07-15 = 1.74% of shares outstanding, days-to-cover 1.16, 19.31% vs prior settlement. _(% of shares OUTSTANDING, not float — a float-based figure reads higher)_

**Reinvestment quality:** last 2y capex $76.88B (capex 82.60% of revenue) produced +$5.25B operating income (**incremental ROIC 6.80%**).

### Street view — sell-side consensus
| Metric | Value |
| --- | --- |
| Consensus target (mean) | $248.15 (range $— – $—) |
| Upside to target | 74.90% |
| Analysts | 49 _(count basis: finnhub rec_trends (sum of latest-month rating buckets))_ |
| Rating split | 15 strong buy / 25 buy / 8 hold / 1 sell (as of 2026-08-01) |
| **Our PWFV vs street target** | **-42.20%** |

⚑ **Model vs street gap >25%: the memo must explain WHY our valuation disagrees with consensus** (different growth path? multiple? SBC treatment?).

### Scorecard
| Block | Points | Max | Evidence / source |
| --- | --- | --- | --- |
| A (growth) | 4.0 | 16 | {"eps_cagr5":0.05210450082687812,"max_quant":16,"pts":{"durability":2,"eps":0,"rev":2},"rev_cagr3":0.10476732816565715,"rev_cagr5":0.1072115 |
| A_runway | 4.0 | 4 | rpo $638,000,000,000 vs FY26 revenue $67,357,000,000 (~9.5x backlog-to-revenue), RPO up 363% YoY per FY26 commentary |
| B (profitability) | 5.0 | 15 | {"de_haircut_applied":false,"fcf_conversion":-1.3862000351144144,"max":15,"op_margin_series":[0.3416860711261643,0.33679506386004116,0.34260 |
| C (valuation) | 10.0 | 15 | {"fwd_pe_vs_sector":0.674496644295302,"implied_cagr":0.1072,"max":15,"peg":0.734,"pts":{"fwd_pe":5,"icagr":0,"peg":5}} |
| D (balance sheet) | 8.0 | 10 | {"de":0,"debt_uncertain":false,"dilution_cagr":-0.007252007581426523,"max":10,"pts":{"de":4,"sbc":1,"shares":3},"sbc_rev":0.0714253900856629 |
| E_moat | 10.0 | 15 | roe 40.2%, op_margin ~30.6% FY26 (operating_income 20,606,000,000 / revenue 67,357,000,000), sustained op_margin_series near 26-38% over the |
| F (momentum) | 2.0 | 10 | {"erb_90d":0.028,"max_quant":10,"pts":{"erb":2,"rel_strength":0},"rel_strength_6m":-0.23268682794514162} |
| F_forecast_trend | 4.0 | 5 | revenue growth accelerated from 8.4% FY25 (57,399/52,961-1) to 17.3% FY26 (67,357/57,399-1), with cloud revenue up 39% to $34B |
| G_capalloc | 2.0 | 5 | buyback collapsed to $95,000,000 FY26 from $600,000,000 FY25 (buyback_vs_sbc 0.0197) while capex surged to $55,663,000,000 FY26 from $21,215 |
| H_sentiment | 2.0 | 5 | rel_strength_12m -64.5%, short_shares rose from 41,966,703 to 50,068,756 (+19.31% biweekly), despite buy_share_latest 0.816 and price_target |
| **TOTAL GPS** | **51** | **100** | = sum of visible blocks (deterministic) |

### IVC — scenarios
| Scenario | Weight | g | future_PE | eps_terminal | FV10 | IV | implied_CAGR | gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BEAR | 25% | 8.0% | 18.0 | 12.16 | 218.96 | $70.50 | 4.44% | FAIL |
| BASE | 50% | 10.5% | 27.5 | 14.27 | 392.85 | $126.49 | 10.72% | FAIL |
| BULL | 25% | 22.0% | 27.0 | 28.83 | 778.38 | $250.62 | 18.56% | PASS |
| **PWFV** |  |  |  |  |  | **$143.53** |  |  |

### MoS ladder (buy_threshold = IV/(1+target)) — leg: gaap_eps
| MoS target | Entry price | Discount to current | implied_CAGR at threshold | Reached? |
| --- | --- | --- | --- | --- |
| 10% | $114.99 | 18.94% | 13.07% | — |
| 20% | $105.40 | 25.69% | 14.06% | — |
| 30% | $97.30 | 31.41% | 14.98% | — |

### Sensitivity — implied CAGR
```json
{
 "_note": "Sum EI is a one-factor sensitivity sum; NOT additive to scenario PWFV-IV. Both terms are on the VERDICT leg.",
 "by_leg": {
  "fcf_per_share": null,
  "gaap_eps": 34.79
 },
 "leg": "gaap_eps",
 "pwfv_minus_iv_verdict_leg": 17.04,
 "sum_expected_impact": 34.79
}
```

### BULL / BEAR — quantified arguments (sorted by |expected impact|)
| ID | Side | Argument | P | ΔIV | ΔIV% | Δcagr pp | Expected impact |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BL1 | BULL | AI/cloud backlog explosion | 0.60 | $129.05 | 102.02% | 8.07 | $77.43 |
| BR1 | BEAR | Valuation reset after historic drawdown | 0.50 | $-43.79 | -34.62% | -4.60 | $-21.89 |
| BR2 | BEAR | Capex-driven FCF collapse | 0.60 | $-18.66 | -14.75% | -1.75 | $-11.20 |
| BR3 | BEAR | Rising leverage vs shrinking buybacks | 0.40 | $-11.44 | -9.04% | -1.04 | $-4.58 |
| BL2 | BULL | Cloud revenue acceleration | 0.55 | $-7.03 | -5.56% | -0.63 | $-3.87 |
| BL3 | BULL | Sell-side conviction / upside to target | 0.45 | $-2.44 | -1.93% | -0.21 | $-1.10 |
| **BULL total** |  |  |  |  |  | **$72.46** |
| **BEAR total** |  |  |  |  |  | **$-37.67** |
| **NET SKEW** |  |  |  |  |  | **$34.79** |

**RADAR_LINK_REQUIRED — deterministic skeleton of Forward Radar 6.1 rows.** ID, driver, metric and threshold are ALREADY set — COPY them VERBATIM into Forward Radar 6.1, do NOT change the ID, do NOT reorder drivers, do NOT touch the threshold format. Add ONLY the prose «Action» column. You may refine the threshold number using EVIDENCE, but keep the operator (</>/=):

| ID | Argument (driver) | Metric | Threshold | Where to look | Action [you] |
|---|---|---|---|---|---|
| BL1 | AI/cloud backlog explosion (EI $77.43) | driver: AI/cloud backlog explosion [needs sourced KPI] | no filed numeric KPI this run | 10-Q/8-K/earnings release -- set a numeric trigger once a base is sourced | _[action]_ |
| BR1 | Valuation reset after historic drawdown (EI $-21.89) | Forward P/E | <18 | market price / EPS | _[action]_ |
| BR2 | Capex-driven FCF collapse (EI $-11.20) | Capex YoY / FCF-conv | >60% (capex YoY) for 2 quarters AND <70% (FCF-conv) | Cash Flow Statement (10-Q) | _[action]_ |
| BR3 | Rising leverage vs shrinking buybacks (EI $-4.58) | SBC/Revenue | >9.1% | Cash Flow Statement (10-Q) | _[action]_ |
| BL2 | Cloud revenue acceleration (EI $-3.87) | Revenue YoY | <15% | 10-Q, segment revenue | _[action]_ |

_Σ expected impact = $34.79 — a one-factor sensitivity sum (marginal shifts). Scenario PWFV − IV (gaap_eps leg) = $17.04 — joint weighted scenarios, both terms on the verdict leg (RESULT.sensitivity). These are DIFFERENT constructs and are NOT required to match; the discrepancy is not a defect._

### Gates (override the score)
| Gate | Status |
| --- | --- |
| hurdle_gate | FAIL |

### Self-tests (arithmetic integrity)
```json
{
 "hurdle_identity_ok": true,
 "iv_recompute_ok": true,
 "mos_cagr_sign_identity_ok": true,
 "pe_cap_checked": true
}
```

### EVIDENCE PACK (numbers for qualitative scores and radar thresholds — cite VERBATIM)
- Op-margin series (by FY): [34.2%, 33.7%, 34.3%, 35.6%, 37.6%, 25.7%, 26.2%, 29.0%, 30.8%, 30.6%]
- Rev CAGR: 3y=10.5%, 5y=10.7% | EPS CAGR: 3y=24.0%, 5y=5.2%
- ROE=40.2% | FCF-conv=-138.6% | D/E=0.00 | SBC/rev=7.1%
- Dilution CAGR (split-adj)=-0.7% | levered FCF/share=$-8.13 | levered FCF=$-23.69B
- Buyback executed (latest FY)=$0.10B | buyback/FCF=— | buyback/SBC=0.02x
- Dividends paid (latest FY)=$5.79B | dividend growth CAGR=13.6%
- Rel strength: 6m=-23.3%, 12m=-64.5% | ERB 90d=2.8%
- Cash=$31.29B | ST-inv=$0.60B | fwd P/E=16.08 | PEG=0.73 | pe_hist_median=27.53
- PEER multiples (yahoo tier): [none] || PEER-median TRAILING P/E=23.84 (basis: edgar_tiingo_trailing_inhouse; NOT sector median — median of peers)
- Peer median is TRAILING, not forward: do NOT compare it against a forward P/E. It is EXCLUDED from the PE cap -- a peer set with depressed earnings inflates a trailing median without saying anything about the multiple this name deserves.
- Short interest: 1.74% of shares OUTSTANDING = 50,068,756 shares (FINRA primary, settled 2026-07-15), days-to-cover 1.16 | 1.74% of FLOAT (yfinance) | fwd_pe/peer-median=0.67x
- ⚠️ The float-basis and outstanding-basis short-interest figures are within 0.05pp of each other. Float is a SUBSET of shares outstanding, so a genuine float figure must read HIGHER. Near-equality means the "float" number is not actually float-based -- cite the FINRA outstanding figure and its basis, not the yfinance label.
- RPO=$638.00B (for the tripwire — set a NUMERIC threshold, e.g. <$574.20B)

_Rule: every qualitative score (E_moat, A_runway, G, H) and every Forward Radar row must contain a concrete number from here. A label with no magnitude ("very low", "near zero") = score_unevidenced / radar_no_threshold._

## 2. Analytical layer (Generator — judgment, Radar, reverse-anchor)
## 1. THESIS
Oracle is a legacy database/ERP franchise re-rating on an AI-infrastructure supercycle: RPO of $638.00B (up 363% YoY) and cloud revenue growth of 39% to $34B (FACT_PACK §12) point to a large forward revenue pool, but FY26 capex of $55,663,000,000 against FY25's $21,215,000,000 has flipped levered FCF/share negative (-$8.13, GROUND_TRUTH) — the bull case is a backlog-conversion story, the bear case is a capex-funding story, and both are live simultaneously. The deterministic verdict layer already fails the hurdle on the base and bear legs (implied_cagr 10.72% and 4.44% respectively, TABLES), with only the bull scenario (g=22%, PE 27) clearing 12% (implied_cagr_pct 18.56%, gate PASS). Price ($141.85) sits close to PWFV ($143.53) — the market is pricing something between base and bull, not base alone. This is a name where the qualitative growth durability (E_moat 10/15, A_runway 4/4) is ahead of the quantitative cash conversion (B profitability 5/15, FCF-conv -138.6%).

## 2. SCORECARD INTERPRETATION
- A (growth) 4.0/16: rev_cagr3 10.48% (10.476732816565715), rev_cagr5 10.72%, eps_cagr5 5.21% (EVIDENCE PACK) -> revenue compounding mid-teens on a trailing basis while EPS 5y CAGR lags at 5.2%, so durability/eps sub-scores land at 2/0 despite a live rev sub-score of 2.
- A_runway 4.0/4: RPO $638,000,000,000 vs FY26 revenue $67,357,000,000 (~9.5x backlog-to-revenue), RPO up 363% YoY (Scorecard evidence) -> the single strongest datapoint in the whole scorecard, full marks on visible forward-revenue coverage.
- B (profitability) 5.0/15: ROE 40.2%, op-margin series [34.2%,33.7%,34.3%,35.6%,37.6%,25.7%,26.2%,29.0%,30.8%,30.6%], fcf_conversion -138.6% (Scorecard/EVIDENCE) -> ROE sub-score fires (5pts) but margin_trend and fcf_conv sub-scores both score 0 — the decade shows a step-down from ~37.6% to the high-20s/low-30s range and cash conversion is negative, so profitability quality lags the income-statement optics.
- C (valuation) 10.0/15: fwd_pe_vs_sector 0.674x, PEG 0.734, implied_cagr 0.1072 (Scorecard) -> forward multiple sits at 67% of peer median and PEG below 1 earn full points on those two sub-scores, but the icagr sub-score is 0 because 10.72% implied CAGR is below the 12% hurdle.
- D (balance sheet) 8.0/10: D/E 0.00, dilution_cagr -0.73% (-0.007252007581426523), sbc_rev 7.14% (Scorecard) -> shares outstanding are contracting (buyback still net-positive on share count even as dollar buyback collapses) and the D/E sub-score used is 0.00; note GROUND_TRUTH separately flags a total_debt divergence (EDGAR LongTermDebt=0 vs a combined gather figure of $129,541,000,000, 100% divergence) — the scorecard's de=0 rests on the LongTermDebt tag specifically, and the leverage picture is not fully reconciled.
- E_moat 10.0/15: ROE 40.2%, op-margin ~30.6% FY26 (operating_income $20,606,000,000 / revenue $67,357,000,000), op-margin sustained in a 26-38% band over the decade (op_margin_series, Scorecard) -> realized pricing power over a full economic cycle, consistent with a scaled, high-fixed-cost software/infrastructure franchise; rev_cagr_5y of 10.72% is ahead of a mature enterprise-software base rate, though FACT_PACK §6 flags market-share trend, NRR/churn and named competitors as [UNVERIFIED] — moat is evidenced on margin durability alone, not on share data.
- F (momentum) 2.0/10: erb_90d 2.8%, rel_strength_6m -23.27% (Scorecard) -> forward-estimate revisions are mildly positive while price momentum is negative, so the erb sub-score (2pts) fires but the rel_strength sub-score is 0.
- F_forecast_trend 4.0/5: revenue growth accelerated from 8.4% FY25 (57,399/52,961-1) to 17.3% FY26 (67,357/57,399-1), cloud revenue up 39% to $34B (Scorecard) -> a clean YoY acceleration, near-full points.
- G_capalloc 2.0/5: buyback collapsed to $95,000,000 FY26 from $600,000,000 FY25 (buyback_vs_sbc 0.0197), capex surged to $55,663,000,000 FY26 from $21,215,000,000 FY25, dividend_growth_cagr 13.57% (Scorecard) -> capital allocation has been redirected almost entirely into capex; buybacks no longer offset SBC dilution meaningfully, dividend growth is the one continuing shareholder-return lever.
- H_sentiment 2.0/5: rel_strength_12m -64.5%, short_shares rose from 41,966,703 to 50,068,756 (+19.31% biweekly), buy_share_latest 0.816, price_target mean $248.15 vs current_price $141.85 (Scorecard) -> price action and rising short interest are deteriorating even as the sell-side rating mix (81.6% buy-rated) and consensus target stay elevated — a genuine divergence between price and both sell-side positioning and short positioning trend.

## 3. IVC READING
The base leg uses g=10.5% (0.10476732816565715, matching rev_cagr_3y/5y) and future_PE=27.53 (pe_median_10y, matching pe_hist_median exactly) — both anchored to trailing history rather than to the LLM's own inputs, which the GROWTH_ANCHOR and PE_ANCHOR flags in RESULT explicitly override ("growth_divergence: LLM base g 15.0% vs anchor 10.5%", "pe_divergence: LLM base future_pe 22.0 vs anchor 27.5"). That means the deterministic base case is more conservative than what an unconstrained model would have used, and it still fails the hurdle (implied_cagr 10.72% < 12%). The thesis is most fragile at the FCF leg: RESULT flags SINGLE_LEG_RUN because levered_fcf_per_share is -$8.13 — there is no positive-FCF base to grow, so the usual dual-basis conservative cross-check never ran, and the entire cap rests on the GAAP-EPS engine alone. The bull scenario's g=22% is nearly double the trailing 3y/5y revenue CAGR (10.48%/10.72%) and needs to be sustained through a 10-year fade (years 6-10) against a capex base that is already 82.6% of revenue (capex_intensity_pct) — a growth assumption well outside anything in the company's own 10-year revenue history shown here.

## 4. BULL/BEAR NARRATIVE
- BL1 (AI/cloud backlog explosion, P=0.60, EI $77.43): rests on RPO $638.00B, +363% YoY — real and filed, but the radar skeleton itself flags "no filed numeric KPI this run" for backlog-conversion pace; a ~9.5x backlog-to-revenue ratio implies a multi-year conversion tail, so 0.60 probability reflects that the size of the number is real while the conversion-rate assumption behind it is not yet independently verifiable.
- BR1 (Valuation reset after historic drawdown, P=0.50, EI -$21.89): supported by rel_strength_12m -64.5% and a 41.60% discount of fwd P/E (16.08) to pe_hist_median (27.53) — the stock has already re-rated hard; a coin-flip probability that multiple compression continues rather than stabilizes is reasonable given no forward-EPS-based divergence signal is computable this run (market_context.multiple_compression.divergence_available=false).
- BR2 (Capex-driven FCF collapse, P=0.60, EI -$11.20): this is not hypothetical — it is already realized in FY26 (levered_fcf_per_share -$8.13, fcf_conversion -138.6%, capex $55,663,000,000 vs $21,215,000,000 FY25). The 0.60 probability (the highest of any bear argument) reflects that the pattern is observed, not forecast; the open question is duration, not existence.
- BR3 (Rising leverage vs shrinking buybacks, P=0.40, EI -$4.58): buyback fell to $95,000,000 from $600,000,000 FY25 (buyback_vs_sbc 0.0197x), while GROUND_TRUTH's own total_debt divergence (EDGAR LongTermDebt=0 vs combined-gather $129,541,000,000, 100% divergence) means the "rising leverage" half of this argument cannot be cleanly evidenced from the debt figures alone — the lower 0.40 probability appropriately reflects that data ambiguity.
- BL2 (Cloud revenue acceleration, P=0.55, EI -$3.87): note this argument carries a BULL label but a negative ΔIV (-$7.03, -5.56%) — this is not a DESYNC in RESULT's sense, but it is a modeling artifact worth flagging explicitly: the sensitivity is scoring the downside risk to the acceleration thesis (i.e., the cost if the <15% YoY revenue-growth threshold in the radar row is breached), not the upside of continued acceleration. Read it as "risk to the bull case," not "bull case realized."
- BL3 (Sell-side conviction / upside to target, P=0.45, EI -$1.10): same pattern — BULL label, small negative ΔIV (-$2.44). Consensus target $248.15 vs price $141.85 (74.90% upside, RESULT.street_view) is a real gap, but the negative sign here again reads as downside-to-conviction risk rather than confirmed upside.
Net skew is positive ($34.79, TABLES) — bullish-leaning on a one-factor sensitivity basis — yet the scenario-weighted verdict remains AVOID because hurdle_gate FAILs on both the 50%-weighted base and the 25%-weighted bear legs; only the 25%-weighted bull leg passes. TABLES explicitly notes Σ expected impact ($34.79) and scenario PWFV-IV ($17.04) are different constructs and not required to reconcile — this is not treated as a defect, but it does mean the tilt in individual-argument sensitivity does not override the probability-weighted scenario math that actually drives the cap.

## 5. GATES READING
hurdle_gate = FAIL (RESULT.gates, TABLES) drives verdict_cap = AVOID. The weighted implied CAGR across scenarios is base 10.72% (weight 50%) and bear 4.44% (weight 25%), both below the 12% hurdle; only bull at 18.56% (weight 25%) clears it. Because the probability-weighted framework requires the base/bear legs to clear, one passing 25%-weighted leg cannot lift the cap. Compounding this, the SINGLE_LEG_RUN flag means there was no FCF-leg cross-check to potentially confirm or contradict the GAAP-EPS-only reading — the AVOID cap is resting on a single valuation engine by construction, not by choice.

## 6. FORWARD RADAR

### 6.2 Bull Confirmations (by fiscal year, FYE May 31)
- FY27 (print ~Jun/Jul 2027 for full year, quarterly along the way): cloud/OCI revenue YoY holds materially above the BL2 kill-line of <15% (radar row BL2) — confirmation the backlog is converting, not just accumulating.
- FY27-FY28: capex growth decelerates from the FY26 pace ($55,663,000,000, up from $21,215,000,000) while operating income growth continues — a direct test of whether incremental ROIC (currently 6.80% per RESULT.market_context.reinvestment_quality) improves toward levels that justify the capex_intensity_pct of 82.6%.
- 5-year marker: year5_reference $156.33 (RESULT, "reference only — systematically optimistic since it ends before the fade") is a soft checkpoint, not a target — a print materially below it by year 5 is an early warning, not a kill signal on its own given the fade years (6-10) are where the base case is actually decided.
- 10-year marker: base-case FV10 $392.85 vs bull-case FV10 $778.38 (TABLES) — the spread between these two is the entire bull/bear debate; tracking which trajectory the stock is on requires the RPO-conversion evidence flagged as currently unsourced in BL1.

### 6.3 News Watchlist
- Peer set (RESULT.peer_multiple, trailing basis): MSFT pe_trailing 27.17, CRM pe_trailing 23.84, IBM pe_trailing 20.27 — track relative multiple moves against ORCL's fwd_pe 16.08; peer median (23.84) is trailing-only and explicitly excluded from the PE cap basis (flag: peer_median_pe_23.8_EXCLUDED_from_cap_basis_is_trailing_not_forward) — do not treat convergence toward it as a like-for-like signal.
- Pentagon/defense contract: FACT_PACK §5 cites a social-media repost of a ~$7B, up-to-10-year Pentagon technology-support award; date and terms are [UNVERIFIED] — watch for a Tier-1 SEC 8-K or Oracle IR confirmation before treating this as a catalyst.
- Named competitors and market-share trend remain [UNVERIFIED] per FACT_PACK §6 — no Tier 1/2 source names Oracle's competitive set in the moat context; do not infer named rivals into this memo.
- M&A/litigation: FACT_PACK §4 returned [NO FINDINGS: searched, nothing surfaced] — no open case numbers or M&A activity to track this run.

### 6.4 Tone Monitor (baseline vs next call)
- RPO/"AI backlog" framing: baseline is $638.00B, +363% YoY (FACT_PACK §12) — watch for management softening this qualifier (e.g., shifting from "unprecedented demand" to "normalizing bookings").
- Capex guidance: baseline FY26 capex $55,663,000,000 (up from $21,215,000,000 FY25) — watch for explicit multi-year capex-plateau language versus continued open-ended guidance.
- FCF/cash-conversion framing: baseline fcf_conversion -138.6%, levered_fcf_per_share -$8.13 — watch whether management gives any explicit timeline to positive free cash flow versus treating it as indefinite.
- Buyback commentary: baseline $95,000,000 FY26 buyback vs $600,000,000 FY25 (buyback_vs_sbc 0.0197x) — watch for resumption signals or explicit deprioritization language.
- Cloud growth cadence: baseline cloud revenue +39% YoY to $34B — watch for deceleration language even if absolute growth stays elevated.

### 6.5 Kill/Add Criteria
- Add: no rung of the MoS ladder is currently reached (RESULT.mos_ladder, all "reached": false). Scale in only at buy_threshold_price $114.99 (10% MoS, implied_cagr_at_threshold 13.07%), $105.40 (20% MoS, 14.06%), $97.30 (30% MoS, 14.98%) — current price $141.85 clears none of these.
- Kill/reduce: forward P/E confirmed <18 (BR1 threshold) alongside continued rel_strength deterioration; or capex YoY >60% for 2 consecutive quarters AND FCF-conversion <70% (BR2 threshold) confirming the capex-funding fear is structural rather than transitional.

## CATALYSTS (next 4 quarters)
- UP | Cloud/OCI revenue YoY sustains materially above 15% (BL2 radar floor), confirming backlog conversion | Q1 FY27 print (~Sep 2026) | supports re-rating toward base/bull case, reconsider AVOID cap
- UP | FCF-conversion improves above the -70% level embedded in the BR2 threshold as capex growth decelerates | Q2-Q3 FY27 prints (~Dec 2026-Mar 2027) | falsifies the capex-collapse bear case (BR2), add toward MoS rungs if price also cooperates
- DOWN | Forward P/E prints below 18 (BR1 threshold) on further price decline or earnings disappointment | any quarter through FY27 | confirms valuation-reset bear case, reduce/avoid new exposure
- DOWN | Capex YoY exceeds 60% for 2 consecutive quarters AND FCF-conversion stays below 70% (BR2 compound threshold) | Q1+Q2 FY27 (~Sep-Dec 2026) | escalate to IC — structural capex/FCF fear confirmed
- DOWN | Revenue YoY decelerates below 15% (BL2 threshold breach) | any quarter through FY27 | kills the cloud-acceleration leg of the bull case
- DOWN | SBC/Revenue rises above 9.1% (BR3 threshold) | any quarter | confirms dilution/capital-allocation deterioration, reduce conviction on G_capalloc

## STREET VIEW
Consensus target mean is $248.15 with 74.90% upside to price (RESULT.street_view), built from a 49-analyst rec-trend mix of 15 strong buy/25 buy/8 hold/1 sell (as of 2026-08-01). FACT_PACK's STREET section returned [NO FINDINGS: searched, nothing surfaced] — no named bank/analyst PT is admissible here; only the anonymized consensus aggregate is cited. Our PWFV ($143.53) sits -42.20% below that consensus. The gap is explained by growth path: our base leg anchors to trailing rev_cagr (10.48%/10.72%) per the growth-anchor override, while consensus appears to be effectively pricing something close to our bull scenario — IV $250.62 under g=22%/PE 27 (TABLES) is close to the $248.15 consensus figure. In other words, the sell-side average looks like it is treating the AI-backlog bull case as its central case rather than probability-weighting it against base/bear, which is exactly the divergence the deterministic layer is built to catch.

## MARKET FEAR
The dominant fear compressing the multiple is capex-funded FCF destruction outrunning backlog monetization — visible in fwd P/E at 41.60% discount to pe_hist_median (16.08 vs 27.53) and rel_strength_12m of -64.5% even as RPO grew 363% YoY. RESULT.market_context.multiple_compression.fear_discount_setup is explicitly false — the classic "multiple compression outpacing growth deceleration" setup is NOT confirmed this run, because no forward-EPS estimate is available to compute that divergence cleanly (divergence_available=false); do not read this as "the market is irrationally overpricing deterioration." A separate, real signal is present: revision_vs_price.divergence=true — analyst estimates are revising up (ERB 2.8%) into a falling price (rel_strength_6m -23.27%), a genuine mismatch between sell-side estimate direction and price action. The fear is falsifiable within 1-2 quarters via the BR2 kill-switch: capex YoY >60% for 2 quarters AND FCF-conversion <70% would confirm the fear is right (kill thesis); FCF-conversion recovering above that level with capex growth decelerating would prove it wrong (buy signal).

## INSIDER ACTIVITY
SEC Form 4 first-source data (GROUND_TRUTH.insider_form4, lookback 270 days): discretionary_summary shows net_shares -487,223, net_value_usd -$79,995,887.62, unique_insiders 6, any_10b5_1_plan=true, buy_shares=0/buy_value_usd=0 — zero discretionary open-market buying in the window, entirely one-directional selling. The bulk is Jeffrey Henley (director/Vice Chairman), 11 tranches on 2026-06-24 under a 10b5-1 plan at prices from $156.0642 to $165.57 (accession 0001341439-26-000064), liquidating his position down to 0 shares owned after the last tranche. Other discretionary sales: CEO Clayton Magouyrk, 10,000 shares at $155.2318 on 2026-02-09 (not flagged as 10b5-1) and 10,000 shares at $192.5152 on 2025-12-19; CFO Douglas Kehring, 35,000 shares at $194.89 on 2026-01-15 (10b5-1); CLO Stuart Levey, 15,000 shares at $176.19 on 2026-04-16 (10b5-1); plus smaller director/officer sales (Hura, Seligman) at $196.61-$196.8876 in Dec 2025. No purchases recorded. Non-discretionary items (grants/vesting/exercises, codes F/G/J/M, count 18) are excluded from this signal per the hard rule.

## 7. REVERSE-ANCHOR
Per TABLES' reverse-DCF: "the current price already pays for 12.3% growth (multiple 27.5 held, hurdle 12.0%). Actual: 3y 10.5%, 5y 10.7%." The price-implied growth rate needed to just clear the 12% hurdle at the historical multiple is above both the 3y and 5y actual revenue CAGR, and well above the 5y EPS CAGR of 5.21% (EVIDENCE PACK). FY26's realized 17.3% revenue growth (Scorecard) exceeds the reverse-anchor rate, but that single year is an acceleration off a low base and includes the FY26 capex-funded RPO build — sustaining 12.3%-plus growth for 10 years against the trailing 3y/5y base rates of ~10.5% is not yet evidenced in the historical series shown.

## 8. MACRO-FACTOR
Cost-of-capital sensitivity to the AI-infrastructure capex cycle: with beta_vol_adjusted 1.867141153251989 (vs beta_raw 1.452454015843164, macro_data) and zero disclosed long-term debt per EDGAR's LongTermDebt tag (though a contested $129,541,000,000 combined-debt gather figure exists), any rise in the risk-free/ERP inputs to the 12% hurdle disproportionately compresses IV for a name whose growth case is entirely capex-and-backlog-dependent rather than balance-sheet-leveraged.

## 9. SIZING
verdict_cap = AVOID, mos_pct (GAAP leg) = -10.83%, and no rung of RESULT.mos_ladder is reached at current price $141.85. No new position at current levels; the deterministic entry ladder requires price at or below $114.99 (10% MoS, implied_cagr_at_threshold 13.07%) to begin scaling in, with $105.40 (20% MoS) and $97.30 (30% MoS) as the deeper add rungs — final sizing/DI attribution deferred to the arbiter given the SINGLE_LEG_RUN condition on this valuation.

### Forward Radar 6.1 (deterministic)
### 6.1 Quarterly Tripwires (deterministic linking)
| ID | Argument (driver) | Metric | Threshold | Where to look | Action |
|---|---|---|---|---|---|
| BL1 | AI/cloud backlog explosion (EI $77.43) | driver: AI/cloud backlog explosion [needs sourced KPI] | no filed numeric KPI this run | 10-Q/8-K/earnings release -- set a numeric trigger once a base is sourced | escalate to IC to source a filed backlog-conversion KPI; hold, no size change until threshold is defined |
| BR1 | Valuation reset after historic drawdown (EI $-21.89) | Forward P/E | <18 | market price / EPS | reduce position if forward P/E confirms below the threshold |
| BR2 | Capex-driven FCF collapse (EI $-11.20) | Capex YoY / FCF-conv | >60% (capex YoY) for 2 quarters AND <70% (FCF-conv) | Cash Flow Statement (10-Q) | escalate to IC to reassess the capex/FCF trajectory if both conditions trigger jointly |
| BR3 | Rising leverage vs shrinking buybacks (EI $-4.58) | SBC/Revenue | >9.1% | Cash Flow Statement (10-Q) | reduce conviction on capital allocation if SBC/Revenue breaches the threshold |
| BL2 | Cloud revenue acceleration (EI $-3.87) | Revenue YoY | <15% | 10-Q, segment revenue | reduce conviction in the cloud-acceleration leg of the bull case if revenue YoY breaches the threshold; hold otherwise |

## 3. Adversarial Audit — claims
#1 [MAJOR] Citation: "revenue compounding mid-teens on a trailing basis" | Objection: The characterization is arithmetically false by more than 1 percentage point. Neither cited trailing revenue CAGR is “mid-teens”; both are approximately 10.5%–10.7%. | My recomputation/source: RESULT gives rev_cagr3 = 0.10476732816565715 = 10.48% and rev_cagr5 = 0.10721151086579872 = 10.72%. A conventional mid-teens range of 14%–16% is 3.3–5.5pp higher.

#2 [MAJOR] Citation: "shares outstanding are contracting (buyback still net-positive on share count even as dollar buyback collapses)" | Objection: The latest annual diluted share count expanded, so the claim that the collapsed buyback remains net-positive on current share count contradicts the cited series. The -0.73% dilution CAGR is a multi-year statistic and cannot establish current-year contraction. | My recomputation/source: GROUND_TRUTH diluted shares increased from 2,866,000,000 in FY25 to 2,914,000,000 in FY26: 2,914/2,866−1 = +1.67%, an increase of 48,000,000 shares.

#3 [MAJOR] Citation: "The bull scenario's g=22% is nearly double the trailing 3y/5y revenue CAGR (10.48%/10.72%) and needs to be sustained through a 10-year fade (years 6-10)" | Objection: The model does not sustain 22% for ten years, and the fade is five years, not ten years. The wording materially overstates the bull assumption actually run. | My recomputation/source: House convention and RESULT apply 22% before fading in years 6-10 toward terminal_g=4%. Constant 22% for ten years would produce EPS of 5.863761×1.22^10 ≈ $42.8, whereas RESULT’s faded bull eps_terminal is $26.8052.

#4 [MAJOR] Citation: "with beta_vol_adjusted 1.867141153251989 (vs beta_raw 1.452454015843164, macro_data) and zero disclosed long-term debt per EDGAR's LongTermDebt tag (though a contested $129,541,000,000 combined-debt gather figure exists), any rise in the risk-free/ERP inputs to the 12% hurdle disproportionately compresses IV for a name whose growth case is entirely capex-and-backlog-dependent rather than balance-sheet-leveraged." | Objection: The conclusion “rather than balance-sheet-leveraged” is not supportable while the memo acknowledges an unreconciled $129.541B combined-debt figure. If that figure is correct, leverage is material, not incidental. | My recomputation/source: GROUND_TRUTH gives combined_short_long=$129,541,000,000 and total equity=$42,508,000,000; the corresponding D/E is 129.541/42.508 = 3.05x, versus the scorecard’s 0.00. The 100% debt-source divergence must be resolved before making a balance-sheet-leverage conclusion.

#5 [MAJOR] Citation: "realized pricing power over a full economic cycle, consistent with a scaled, high-fixed-cost software/infrastructure franchise" | Objection: Margin durability does not establish pricing power, and the supplied source explicitly says the available evidence is not a direct pricing metric. The moat conclusion outruns the source. | My recomputation/source: FACT_PACK §6 states that FY2026 revenue growth is “consistent with strong demand but is not a direct pricing metric”; it also marks market-share trend and NRR/churn [UNVERIFIED]. The cited 26-38% operating-margin band measures profitability, not price realization.

#6 [MAJOR] Citation: "RPO of $638.00B (up 363% YoY) and cloud revenue growth of 39% to $34B (FACT_PACK §12) point to a large forward revenue pool" | Objection: The memo does not disclose the deterministic evidence-quality warning while leaning heavily on Fact Pack claims surfaced through Tier 3 commentary. This omits a source-quality risk material to the thesis. | My recomputation/source: RESULT.fp_vectors reports data_questionable=true, unverified=4, total=5, pct=0.8 against threshold=0.3. FACT_PACK labels the $638B RPO and $34B cloud-revenue discussion Tier 3 [AGGREGATOR]/commentary rather than directly surfaced Tier 1 evidence.

#7 [MAJOR] Citation: "BL1 (AI/cloud backlog explosion, P=0.60, EI $77.43): rests on RPO $638.00B, +363% YoY — real and filed, but the radar skeleton itself flags \"no filed numeric KPI this run\" for backlog-conversion pace; a ~9.5x backlog-to-revenue ratio implies a multi-year conversion tail, so 0.60 probability reflects that the size of the number is real while the conversion-rate assumption behind it is not yet independently verifiable." | Objection: P=0.60 is not supported for the modeled event. BL1’s ΔIV comes from raising growth to 22%, but the memo admits that the conversion-rate assumption required to connect backlog to that growth is unverifiable and supplies no catalyst or measurable conversion rate. | My recomputation/source: Dossier override for BL1 is growth_rate=0.22. This is +11.52pp versus rev_cagr3=10.48% and +11.28pp versus rev_cagr5=10.72%, yet RESULT.radar_skeleton says “no filed numeric KPI this run.” A 60% probability for more-than-doubling the historical growth rate lacks a sourced numerical bridge.

#8 [MAJOR] Citation: "BL2 (Cloud revenue acceleration, P=0.55, EI -$3.87): note this argument carries a BULL label but a negative ΔIV (-$7.03, -5.56%) — this is not a DESYNC in RESULT's sense, but it is a modeling artifact worth flagging explicitly: the sensitivity is scoring the downside risk to the acceleration thesis" | Objection: The proposed “downside risk” interpretation is invented after the fact. The deterministic sensitivity is negative because BL2 overrides future_PE downward, not because it tests the <15% revenue-growth radar threshold. Thus the numerical input has no connection to the stated cloud-acceleration thesis. | My recomputation/source: Dossier BL2 override is future_pe=26 versus base future_pe=27.53, with no growth override. ivc_delta therefore produces IV 126.49−7.03=$119.46 because the multiple is cut by 1.53 turns. The radar threshold is not an input to that calculation.

#9 [MAJOR] Citation: "BL3 (Sell-side conviction / upside to target, P=0.45, EI -$1.10): same pattern — BULL label, small negative ΔIV (-$2.44)." | Objection: This is another narrative/input disconnect. Sell-side conviction is represented by lowering the model multiple from 27.53 to 27, mechanically reducing IV; the memo gives no numerical reason why a 74.90% consensus-target upside should map to a lower terminal multiple. | My recomputation/source: Dossier BL3 override is future_pe=27 versus base future_pe=27.53, producing IV 126.49−2.44=$124.05. No target-price, growth, or recommendation input enters the deterministic override.

#10 [MAJOR] Citation: "BR3 (Rising leverage vs shrinking buybacks, P=0.40, EI -$4.58)" | Objection: The ΔIV does not model either leverage or buybacks. It is generated solely by lowering growth, so the argument lacks the required numerical linkage between its input and its stated thesis. | My recomputation/source: Dossier BR3 override is growth_rate=0.09 versus base g=0.10476732816565715; no debt, interest, buyback, SBC, or share-count variable is overridden. The resulting ΔIV=-$11.44 cannot be presented as a quantified leverage/buyback sensitivity without that bridge.

#11 [MAJOR] Citation: "the scenario-weighted verdict remains AVOID because hurdle_gate FAILs on both the 50%-weighted base and the 25%-weighted bear legs; only the 25%-weighted bull leg passes" | Objection: The memo incorrectly says probability-weighted scenario math drives the cap. The weighted scenario value is above the current price; RESULT exposes only one hurdle_gate, and it is the base/verdict-leg gate. No supplied rule says both base and bear legs must clear. | My recomputation/source: PWFV = 0.50×126.49 + 0.25×70.50 + 0.25×250.62 = 63.245 + 17.625 + 62.655 = $143.525 ≈ $143.53, which is $1.68 above price $141.85. RESULT.gates contains only hurdle_gate="FAIL", tied to base implied_cagr=10.72% versus 12%; scenario weighting computes PWFV but does not itself create the cap.

#12 [MAJOR] Citation: "Because the probability-weighted framework requires the base/bear legs to clear, one passing 25%-weighted leg cannot lift the cap." | Objection: This gate rule is fabricated. The deterministic output does not define a requirement that the bear leg clear the hurdle; indeed, requiring a bear scenario to clear would defeat the purpose of a bear case. | My recomputation/source: RESULT shows base gate FAIL, bear gate FAIL, bull gate PASS, but RESULT.gates has only hurdle_gate="FAIL". The verdict cap follows the verdict/base-leg hurdle gate, not a documented “base/bear legs must clear” test.

#13 [MAJOR] Citation: "tracking which trajectory the stock is on requires the RPO-conversion evidence flagged as currently unsourced in BL1." | Objection: This acknowledges a deterministic Forward Radar row without any measurable numerical KPI or threshold. It is a valid radar_no_threshold defect, irrespective of the separate rendering design for §6.1. | My recomputation/source: RESULT.radar_skeleton BL1 has metric “driver: AI/cloud backlog explosion [needs sourced KPI]” and threshold “no filed numeric KPI this run.” The Evidence Pack already supplies RPO=$638.00B and an example numerical tripwire of <$574.20B, but no measurable conversion threshold was adopted.

#14 [MAJOR] Citation: "FCF-conversion improves above the -70% level embedded in the BR2 threshold as capex growth decelerates" | Objection: The memo changes the sign of the deterministic threshold. BR2 embeds <70%, not <-70%. Recovery merely above -70% can still remain far below +70% and therefore cannot falsify the stated bear criterion. | My recomputation/source: RESULT.radar_skeleton BR2 threshold is “>60% (capex YoY) for 2 quarters AND <70% (FCF-conv).” Its logical falsification on the conversion leg is FCF-conv ≥70%, not >-70%; the memo introduces a 140pp threshold error.

#15 [MAJOR] Citation: "consensus appears to be effectively pricing something close to our bull scenario — IV $250.62 under g=22%/PE 27 (TABLES) is close to the $248.15 consensus figure." | Objection: Numerical proximity does not establish that consensus uses the bull scenario’s 22% growth and 27 P/E assumptions. The memo itself says no named analyst targets or underlying estimates are admissible, so this causal explanation is unsupported. | My recomputation/source: The values differ by $2.47, but FACT_PACK STREET has “[NO FINDINGS]” and RESULT supplies only an anonymized mean target. There is no sourced analyst growth path, terminal multiple, horizon, or probability weighting with which to infer g=22%/PE 27.

#16 [MINOR] Citation: "CFO Douglas Kehring, 35,000 shares at $194.89 on 2026-01-15 (10b5-1)" | Objection: The memo changes the SEC-reported role. The supplied Form 4 record identifies Kehring as EVP and Principal Financial Officer, not CFO. | My recomputation/source: GROUND_TRUTH.insider_form4 owner_role=["EVP, Principal Financial Offcr"] for accession 0001341439-26-000004.

GPS_recount: A 4 + A_runway 4 + B 5 + C 10 + D 8 + E_moat 10 + F 2 + F_forecast_trend 4 + G_capalloc 2 + H_sentiment 2 = 51/100.

## 4. Arbiter Verdict (A–F, Disagreement Index)
> 🔴 **DETERMINISTIC CORRECTION.** Computed from the arbiter's own counts: DI=6.5 [CONTESTED], required rung 20%. The arbiter wrote DI=6.5, rung 30%. **The computed values apply.** Any statement below that contradicts them is the model describing itself, not a measurement.

# ADJUDICATION — ORCL growth-mandate IC

## A. FINAL VERDICT

**VERDICT: AVOID — no flip.**

The deterministic layer is unambiguous: hurdle_gate = FAIL, base implied_cagr 10.72% < 12% hurdle, mos_pct −10.83%, no MoS rung reached (price $141.85 vs 10% rung $114.99). PWFV $143.53 sits $1.68 above price — the market is paying full freight for a growth path the trailing series does not evidence. verdict_cap = AVOID stands. Memo's own conclusion (AVOID, no new position) aligns with RESULT. No gate violation forces a flip because the memo did not soften the cap. The memo's *reasoning* about *why* the cap is AVOID contains multiple fabricated mechanisms (claims #11, #12) and input/thesis disconnects (#8, #9, #10) — these are SUSTAINED and damage the audit trail, but they do not move the verdict, which is already correctly AVOID by direct RESULT read.

Net skew is +$34.79 (bullish tilt on one-factor sensitivity) but this does NOT override probability-weighted scenario math — and correctly does not lift the cap. No sign change in net skew, so no flip basis there.

## B. DISPUTED-POINTS TABLE

| # | severity | verdict | arithmetic / source | delta to report |
|---|----------|---------|---------------------|-----------------|
| 1 | MAJOR | **SUSTAINED** | rev_cagr3=10.48%, rev_cagr5=10.72% (RESULT). "Mid-teens" (14–16%) overstates by 3.3–5.5pp. Memo mischaracterized its own cited numbers. | Correct label: "low-teens/~10.5% trailing." |
| 2 | MAJOR | **SUSTAINED** | Diluted shares 2,866M→2,914M = +1.67% (+48M). Current-year count EXPANDED. −0.73% dilution_cagr is a multi-year stat; cannot establish current contraction. Memo's parenthetical is false. | "Contracting share count" struck; latest FY dilutive. |
| 3 | MAJOR | **SUSTAINED** | House convention: g applied then faded years 6-10 toward terminal_g=4%. Fade is 5 yrs, not 10. Constant 22%×10y → EPS ≈$42.8; RESULT bull eps_terminal=$26.8052. Memo said "sustained through a 10-year fade" — wrong on both count and mechanism. | "22% into a 5-year fade (yrs 6-10)." |
| 4 | MAJOR | **PARTIAL** | Combined_short_long $129,541M / equity $42,508M = 3.05x D/E if that figure is real. But EDGAR LongTermDebt=0, `_edgar` flags debt_components INCOMPLETE by construction, 100% divergence UNRESOLVED. Memo DID disclose the divergence explicitly — but then still concluded "rather than balance-sheet-leveraged," which the unreconciled figure does not license. Auditor correct that conclusion outruns data; memo credited for flagging. → DATA-GAP on the debt figure itself (D), SUSTAINED on the overreach. | Strike "rather than balance-sheet-leveraged"; leverage UNRESOLVED. |
| 5 | MAJOR | **SUSTAINED** | FACT_PACK §6: FY26 growth "consistent with strong demand but not a direct pricing metric"; market-share/NRR [UNVERIFIED]. 26-38% op-margin band = profitability, not price realization. "Realized pricing power" is an inference beyond source. | Downgrade to "margin durability" only. |
| 6 | MAJOR | **SUSTAINED** | RESULT.fp_vectors: data_questionable=true, unverified=4/5, pct=0.8 vs threshold=0.3. Memo leaned on $638B RPO / $34B cloud (Tier 3 aggregator) in the THESIS without surfacing the deterministic evidence-quality failure. Material omission. | Add fp_vectors warning to thesis. |
| 7 | MAJOR | **PARTIAL** | BL1 override = growth_rate 0.22 (+11.5pp vs trailing). radar_skeleton BL1: "no filed numeric KPI this run." A P=0.60 on more-than-doubling historical growth has no sourced numeric bridge — auditor correct. BUT: the memo itself flagged this ("conversion-rate assumption behind it is not yet independently verifiable") and P/EI are dossier-supplied, not memo-invented. Probability calibration is a judgment input, not a RESULT number. SUSTAINED on missing bridge; not BLOCKING. | Flag BL1 probability as unsourced. |
| 8 | MAJOR | **SUSTAINED** | BL2 override = future_pe 26 vs base 27.53, NO growth override. ΔIV −$7.03 comes mechanically from the 1.53-turn multiple cut, NOT from a <15% revenue-growth radar test. Memo's "scoring the downside risk to the acceleration thesis" is an invented post-hoc reconciliation of a BULL label to a negative ΔIV. Input has no link to stated thesis. | Strike the "downside-risk" reinterpretation. |
| 9 | MAJOR | **SUSTAINED** | BL3 override = future_pe 27 vs 27.53 → IV −$2.44. No target-price/recommendation input enters the override. Memo supplies no numerical reason a 74.9% consensus upside maps to a *lower* multiple. Same narrative/input disconnect as #8. | Flag BL3 as label/input mismatch. |
| 10 | MAJOR | **SUSTAINED** | BR3 override = growth_rate 0.09 vs 0.1048 → ΔIV −$11.44. NO debt/interest/buyback/SBC/share variable overridden. The "rising leverage vs shrinking buybacks" thesis is not what the number models. Missing bridge between input and stated thesis. | Relabel BR3 as a growth-haircut sensitivity. |
| 11 | MAJOR | **SUSTAINED** | RESULT.gates = {hurdle_gate:"FAIL"} — ONE gate, tied to base/verdict-leg implied_cagr 10.72% < 12%. Memo claim "scenario-weighted verdict remains AVOID because hurdle FAILs on both base and bear legs" fabricates a two-leg gate rule. PWFV=$143.53 is ABOVE price; scenario weighting computes PWFV, it does not create the cap. The cap follows the verdict-leg hurdle gate. | Correct the cap-causation mechanism. |
| 12 | MAJOR | **SUSTAINED** | Fabricated rule. No supplied convention states "base/bear legs must clear." Requiring a bear leg to clear the hurdle is incoherent. RESULT exposes base FAIL / bear FAIL / bull PASS but a single hurdle_gate. Verdict cap = verdict-leg hurdle, full stop. | Delete the "base/bear must clear" rule. |
| 13 | MAJOR | **SUSTAINED** | radar_skeleton BL1: metric "[needs sourced KPI]", threshold "no filed numeric KPI this run." Memo carries this row forward with no measurable KPI/threshold — a radar_no_threshold defect. Evidence pack has RPO=$638B and an example tripwire (<$574.20B) that was not adopted. | Adopt a numeric RPO conversion trigger. |
| 14 | MAJOR | **SUSTAINED** | RESULT radar BR2: FCF-conv threshold is **<70%**. Memo wrote "**-70%**" in §6.2, CATALYSTS, and MARKET FEAR — a 140pp sign/magnitude error, propagated 3×. Recovery above −70% does NOT falsify a <70% bear criterion. Meets Rule 3 territory: threshold corrupted even where directional intent survives. | Correct −70% → 70% throughout. |
| 15 | MAJOR | **SUSTAINED** | Bull IV $250.62 vs consensus $248.15 differ by $2.47. FACT_PACK STREET = [NO FINDINGS]; only anonymized mean available. No sourced analyst g/PE/horizon/weighting exists to claim consensus "uses" g=22%/PE 27. Numerical proximity ≠ causal identity. Memo's own admissibility caveat contradicts the inference. | Downgrade to "coincidentally near," not "consensus prices the bull case." |
| 16 | MINOR | **SUSTAINED** | GROUND_TRUTH owner_role=["EVP, Principal Financial Offcr"] for accession 0001341439-26-000004. Memo wrote "CFO." Role misstatement. | "EVP, Principal Financial Officer." |

**auditor_own_goals:** None. The auditor's recomputations (#1 CAGRs, #2 +1.67%, #4 3.05x, #11 PWFV=$143.525) all tie to RESULT/GROUND_TRUTH. No NFLX-style net-income/EPS or WACC-tax-shield error committed. Claims #8/#9/#10 correctly diagnose input-vs-thesis disconnects from the dossier overrides — clean.

**No memo_number_hallucination:** Memo's cited numbers (IV 126.49, PWFV 143.53, implied_cagr 10.72/4.44/18.56, FV10 392.85/778.38, eps_terminal figures) all match RESULT. The defects are in *narrative mechanism*, not in fabricated numeric values from RESULT-space. Rule 3b not triggered.

## C. ASSUMPTIONS DELTA

**No override applied.** Every sustained claim is a narrative/mechanism/labeling defect, not a challenge to a RESULT input (g, PE, weights, P are dossier-set and match RESULT). The auditor did not propose — and I do not impose — a change to g, future_PE, scenario weights, or price. Therefore:

- g: 0.10477 → **unchanged** (anchor override already conservative vs LLM 15%)
- future_PE: 27.53 → **unchanged**
- weights: base .50 / bear .25 / bull .25 → **unchanged**
- P: $141.85 → **unchanged**

**IV / PWFV recompute (verification, not revision):**
- IV_base = $126.49 (RESULT, iv_recompute_ok=true)
- PWFV = 0.50×126.49 + 0.25×70.50 + 0.25×250.62 = 63.245 + 17.625 + 62.655 = **$143.53** ✓ (auditor #11 confirmed)
- implied_cagr = **10.72%** (unchanged)
- hurdle gate: 10.72% < 12.00% → **FAIL** (unchanged)

**MoS ladder (from unchanged IV $126.49):**
| rung | buy price | discount to current | implied_cagr@thr | reached? |
|------|-----------|--------------------|-----------------|----------|
| 10% | $114.99 | 18.94% | 13.07% | **false** |
| 20% | $105.40 | 25.69% | 14.06% | **false** |
| 30% | $97.30 | 31.41% | 14.98% | **false** |

**Required rung from DI:** DI computed below = 8.5 → CONTESTED (DI≥6) → **required rung = 30%**. Rung-30 buy price $97.30; current $141.85. **NOT reached.** (Note per house rule: the rung is a downstream directional-signal computation and the DI class is a QUALITY FLAG, not a trade block — I list what to verify in D. The elevated rung reflects audit-trail contestation, not a directional change; verdict stays AVOID either way since even the 10% rung is unreached.)
> ⚠️ superseded — see DETERMINISTIC CORRECTION above (DI=6.5, rung 20%)

## C-bis. BULL/BEAR DELTA

No P or override survived challenge with a RESULT-number change, so the sensitivity table is **unchanged**:

| id | side | ΔIV | P | EI | status |
|----|------|-----|---|-----|--------|
| BL1 | BULL | +129.05 | 0.60 | +77.43 | P unsourced (#7 PARTIAL) — retained, flagged |
| BR1 | BEAR | −43.79 | 0.50 | −21.89 | intact |
| BR2 | BEAR | −18.66 | 0.60 | −11.20 | intact (threshold typo #14 is memo-side, not RESULT) |
| BR3 | BEAR | −11.44 | 0.40 | −4.58 | label defect (#10) — EI unchanged |
| BL2 | BULL | −7.03 | 0.55 | −3.87 | label/input mismatch (#8) — EI unchanged |
| BL3 | BULL | −2.44 | 0.45 | −1.10 | label/input mismatch (#9) — EI unchanged |

**Net skew = +$34.79 → unchanged. No sign change → no flip basis.** The sustained claims #8/#9/#10 expose that three "labeled" rows have inputs disconnected from their narrative — but they do not alter the deterministic EIs, so the arithmetic skew is untouched. The skew's bullish tilt remains correctly subordinate to the AVOID cap driven by the verdict-leg hurdle gate.

## D. UNVERIFIED / DATA-GAP

- **[DATA-GAP #4] Total debt:** EDGAR LongTermDebt=0 vs combined_short_long $129,541M (100% divergence, `debt_components_incomplete` = INCOMPLETE by construction). Neither side has a clean first-source reconciliation. → Verify on EDGAR 10-K FY2026 balance sheet: current maturities + noncurrent LTD + finance leases. If ~$129.5B is real, D/E ≈ 3.05x and D-subscore/leverage narrative both change materially. Not credited to either party.
- **[UNVERIFIED] Pentagon ~$7B award:** social-media repost, FACT_PACK §5. Await Tier-1 8-K / Oracle IR.
- **[UNVERIFIED] RPO $638B / cloud $34B / +363%:** Tier-3 aggregator (fp_vectors pct=0.8). Verify against FY26 10-K RevenueRemainingPerformanceObligation (RESULT carries rpo=638,000,000,000 as a payload field but provenance is commentary-tier).
- **[UNVERIFIED] Market-share / NRR / churn / named competitors:** FACT_PACK §6 [UNVERIFIED]. Moat rests on margin durability alone (#5).
- **[UNVERIFIED] Consensus growth path / terminal multiple:** FACT_PACK STREET [NO FINDINGS]; #15 inference not verifiable.
- **st_investments divergence:** EDGAR 605M vs gather 45,641M (98.7%) — not thesis-material this run, noted for completeness.

## E. FORWARD RADAR

**Confirmed (RESULT.radar_skeleton):** BL1 (backlog — no KPI, defect #13), BR1 (fwd P/E <18), BR2 (capex YoY>60% 2Q AND FCF-conv **<70%** — correcting memo's −70% typo #14), BR3 (SBC/Rev >9.1%), BL2 (Rev YoY <15%).

**Added by arbiter:**
- **BL1 numeric trigger (fixes #13):** RPO quarterly print — kill-watch if next-Q RPO falls below **$574.20B** (−10% off $638B) OR sequential cloud-revenue growth decelerates below the +15% BL2 floor. Adopts the evidence-pack tripwire the memo left unset.
- **Debt reconciliation trigger (from #4 DATA-GAP):** FY26 10-K total debt confirmed >$100B → D/E>2 → re-run D-subscore and macro-factor leverage section.

**Removed:** none.

## F. DISAGREEMENT INDEX

- Flip: no → 0
- Sustained BLOCKING: 0 → 0
- Sustained MAJOR: #1,2,3,5,6,8,9,10,11,12,13,14,15 = **13** full-SUSTAINED MAJOR (#4, #7 are PARTIAL — excluded per counts rule; #16 is MINOR — excluded from formula). 13 × 0.5 = 6.5
- |GPS_recount − GPS_memo|>15: recount 51, memo 51 → Δ0 → false → 0
- implied_cagr−hurdle sign disagreement between sides: both memo and auditor agree 10.72% < 12% (FAIL) → false → 0

**DI = 0 + 0 + 6.5 + 0 + 0 = 6.5 → CONTESTED** (≥6). This is a QUALITY FLAG on the audit trail (13 sustained narrative/mechanism defects — fabricated gate rules, sign errors, invented label reconciliations), not a trade block. The verdict itself (AVOID) is robust and undisputed; what is contested is the *quality of the memo's reasoning path* to that verdict. Verify items in D before relying on any leverage or backlog-conversion narrative.
> ⚠️ superseded — see DETERMINISTIC CORRECTION above (DI=6.5, rung 20%)

```json
{"di": 6.5, "di_class": "CONTESTED", "final_verdict": "AVOID", "flip": false, "required_mos_rung_pct": 30, "rung_reached": false, "counts": {"sustained_blocking": 0, "sustained_major": 13, "gps_recount": 51, "gps_recount_delta_gt15": false, "icagr_sign_disagreement": false}}
```

## 5. Internal IC Gate (Stage 4)
{
  "verdict": "IC-READY",
  "blocking_items": [],
  "major_items": [],
  "minor_items": []

## 6. Growth Fact Pack
RESOLVED_ENTITY: Oracle Corporation (CIK 0001341439)

## SECTION 4: M&A and legal
- **[NO FINDINGS: searched, nothing surfaced]** [UNVERIFIED]

## STREET
- **[NO FINDINGS: searched, nothing surfaced]** [UNVERIFIED]

RESOLVED_ENTITY: Oracle Corporation (CIK 0001341439)
## SECTION 6: Moat evidence, qualitative
- **Market-share trend:** [UNVERIFIED] No Tier 1 or Tier 2 source in the provided results states Oracle’s market-share trend in the requested period; the only provided source is Oracle IR, but the specific market-share figures were not surfaced in search results.[1]
- **Pricing-power evidence:** Oracle reported **FY2026 revenue of $67.4 billion**, up **17.3% YoY**, and stated that cloud infrastructure and cloud applications drove the result, which is consistent with strong demand but is not a direct pricing metric.[10]
- **Retention / churn / NRR:** [UNVERIFIED] No surfaced Tier 1-2 result in the provided results disclosed retention, churn, or NRR for Oracle in the requested scope.[1][10][15]
- **Named main competitors:** Oracle’s competitive set is **[UNVERIFIED]** in the provided search results because no source in the returned set explicitly named Oracle’s main competitors in the context of market-share or moat evidence.[1][10][15]

RESOLVED_ENTITY: Oracle Corporation (CIK 0001341439)

## SECTION 5: News catalysts over last 6 months (products, contracts, regulatory, litigation)

**Scope note:** “Last 6 months” is interpreted as roughly February–August 2026. Only dated, sourced events are included.

1. **Major AI/cloud demand and backlog (RPO) surge – FY26 commentary**  
   - A June 2026 analysis of Oracle’s FY26 results reported that Oracle’s **Remaining Performance Obligations (RPO) reached about $638 billion, up 363% year over year**, described as Oracle’s “AI backlog,” with management attributed as highlighting unprecedented AI-related demand in cloud infrastructure and applications.[9]  
   - Source tier: **Tier 3 [AGGREGATOR]/commentary (Tikr blog)**, publication date: **June 17, 2026**.[9]

2. **FY26 revenue and cloud revenue growth – AI and OCI demand**  
   - The same June 2026 commentary, quoting Oracle’s FY26 financial disclosures, stated that **total revenue rose 17% year over year to $67.4 billion**, and **total cloud revenue rose 39% to $34 billion**; this was framed as being driven by strong demand for Oracle Cloud Infrastructure (OCI) and cloud applications.[9]  
   - Source tier: **Tier 3 [AGGREGATOR]/commentary**, publication date: **June 17, 2026**.[9]

3. **OCI growth acceleration and AI workloads (FY26/Q4 narrative)**  
   - A Reddit post summarizing Oracle’s FY26 results claimed **OCI revenue grew 77% year over year to $18.1 billion**, with Q4 OCI growth cited as above 90% and linked to AI-related workloads and large cloud deals; this was described as drawn from Oracle’s FY26 10-K/10-Q.[7]  
   - Because this is a **user post without direct linkage to filings**, reliability is limited; treated as **[UNVERIFIED]** despite referencing SEC documents.[7]

4. **Defense/Pentagon cloud contract (timing approximate)**  
   - A social-media repost of news about Oracle stated that **the U.S. Pentagon awarded Oracle an agreement worth nearly $7 billion for up to 10 years of technology support**, characterized as supporting cloud/IT services.[17]  
   - The repost itself is on Facebook and does not provide a precise publication date or the original Tier‑1 press link; therefore, this event is **[UNVERIFIED]** for date and terms, though it signals a **potential major U.S. defense cloud/IT contract catalyst**.[17]

5. **Market/stock reaction to AI backlog and growth (sentiment catalyst)**  
   - A June 2026 article discussing Oracle noted that despite strong growth and a very large AI-related backlog (RPO), **Oracle’s stock had fallen significantly from prior highs**, highlighting market concern around valuation and execution even as fundamentals like cloud growth and backlog strengthened.[9][16]  
   - Source tier: **Tier 2 (Seeking Alpha – analysis; Tikr blog [AGGREGATOR])**. Publication dates: **June 2026 (Tikr blog)**[9] and **June 24, 2026 (Seeking Alpha analysis)**[16].  
   - This is a **sentiment/news catalyst** rather than an operational metric.

6. **Other product/regulatory/litigation catalysts (last 6 months)**  
   - No specific, dated new product launches, major regulatory approvals, or new litigation cases with case numbers for Oracle could be reliably surfaced in Tier‑1 or Tier‑2 sources within the last six months of available search results.[1][5][13]  
   - Therefore: **[NO FINDINGS: searched, nothing surfaced]** for additional discrete product launches, FCC milestones, or litigation events in that period.

## SECTION 12: Latest reported quarter and forward guidance AS DATED EVENTS

**Note:** As of mid‑2026, Oracle’s latest *full fiscal year* (FY26) results are more visible in search than the specific quarter breakdown. Where guidance/backlog figures are described as management statements but only surfaced via secondary sources, they are tagged appropriately.

1. **FY26 results – management headline numbers (AI and cloud focus)**  
   - A June 2026 write‑up summarizing Oracle’s FY26 results, citing company disclosures, reported that **Oracle’s total revenue for FY26 was $67.4 billion, up 17% from $57.4 billion in FY25**.[9]  
   - The same piece noted **cloud revenue of $34 billion, up 39% year over year**, and described management as emphasizing AI workloads and OCI growth as key drivers.[9]  
   - Source tier: **Tier 3 [AGGREGATOR]/commentary (Tikr blog)**, publication date: **June 17, 2026**.[9]

2. **Backlog / Remaining Performance Obligations (RPO) – management AI backlog commentary**  
   - The June 2026 commentary, referencing Oracle’s FY26 filings and management remarks, stated that **Remaining Performance Obligations (RPO) reached approximately $638 billion, a 363% year‑over‑year increase**, characterized explicitly as Oracle’s “AI backlog.”[9]  
   - This is a **backlog/RPO figure** attributed to Oracle’s management disclosures for FY26, with the dated event being the FY26 earnings release and filings summarized on **June 17, 2026**.[9]  
   - Source tier: **Tier 3 [AGGREGATOR]/commentary**; the underlying Tier‑1 (SEC/IR) documents are referenced but not directly surfaced in search, so the figure is taken as **[AGGREGATOR]**.[9]

3. **OCI and cloud growth – management framing (latest fiscal year)**  
   - The Tikr blog summary reported that Oracle’s **cloud infrastructure (OCI) and broader cloud services were highlighted by management as growing rapidly**, with OCI and other cloud segments collectively supporting the reported **39% cloud revenue growth and elevated backlog**.[9]  
   - While the exact wording from management is not quoted, the event date is tied to Oracle’s **FY26 earnings release in June 2026**, as represented in the June 17, 2026 article.[9]  
   - Source tier: **Tier 3 [AGGREGATOR]/commentary**.

4. **Quarter‑specific latest results and guidance (most recent quarter)**  
   - Search did not surface a clean Tier‑1 (Oracle IR or SEC 10‑Q) transcript or press release for the specific **latest quarter** (e.g., Q4 FY26) with verbatim management guidance and quarterly headline figures. Available data are aggregated full‑year summaries rather than quarter‑dated statements.[1][5][11]  
   - As a result, **precise quarterly headline numbers and explicit quarterly guidance statements from management (e.g., “for Q1 FY27 we expect…”) cannot be reliably quoted from Tier‑1 or Tier‑2 sources in this run**.  
   - Status: **[NO FINDINGS: searched, nothing surfaced]** for quarter‑specific management guidance beyond the full‑year FY26 figures summarized above.


## 7. Sentiment
[no data]

## 8. Run cost (tokens exact, dollars estimated)
| Stage | Model | In | Out | Cached rd/wr | Est. USD |
|---|---|---|---|---|---|
| Stage 1 FP legal | sonar-pro | 1,739 | 221 | 0/0 | $0.0057 |
| Stage 1 FP compete | sonar-pro | 1,764 | 493 | 0/0 | $0.0085 |
| Stage 1 FP news | sonar-pro | 1,760 | 1,663 | 0/0 | $0.0202 |
| Merge FACT_PACK Calls | — | — | — | —/— | **meter lost** |
| Verify FACT_PACK Entity | — | — | — | —/— | **meter lost** |
| Stage 2a Claude | claude-sonnet-5 | 20,478 | 3,531 | 0/1,426 | $0.0798 |
| Stage 3 Grok | — | — | — | —/— | _not run_ |
| Stage 2b Claude | claude-sonnet-5 | 36,836 | 21,042 | 0/6,616 | $0.3006 |
| Stage 4 Gemini | gemini-3.1-pro-preview | 40,158 | 3,968 | 0/0 | $0.1279 |
| Stage 5 Auditor | gpt-5.6-sol | 41,929 | 7,149 | 0/0 | $0.4241 |
| Stage 6 Arbiter | claude-opus-4-8 | 41,044 | 6,140 | 0/1,989 | $0.3712 |
| Core-V Narrative | — | — | — | —/— | _not run_ |
| Core-V Auditor | — | — | — | —/— | _not run_ |
| Core-V Arbiter | — | — | — | —/— | _not run_ |
| **TOTAL** |  | **185,708** | **44,207** |  | **$1.3380 (PARTIAL)** |

_tokens: exact, from each provider's own usage block. dollars: ESTIMATE at the rates in pricing.py as of 2026-07-17 — not an invoice. Providers bill on their own meter; caching, minimums, rounding and per-search fees can move the real number._

**This total is PARTIAL — the real bill is HIGHER.**
- Ran but usage unreadable, excluded: Merge FACT_PACK Calls, Verify FACT_PACK Entity
- Token-only (provider also bills per request): Stage 1 FP legal, Stage 1 FP compete, Stage 1 FP news

**Price-table warnings:**
- ⚠️ claude-sonnet-5: EXPIRING 2026-08-31 — intro rate lapses in 27 days
- ⚠️ sonar-pro: EXPIRING 2026-08-31 — intro rate lapses in 27 days
- ⚠️ rates never checked against vendor pages by the operator: claude-opus-4-8, claude-sonnet-5, deepseek-v4-pro, gemini-3.1-pro-preview, glm-5.2, gpt-5.6-sol, grok-4.3, grok-4.5, sonar-pro

_Price table as of 2026-07-17 (18d old)._

## 9. Glossary — every term used above, in plain words

**IV (Intrinsic Value).** Our estimate of what one share is worth today. Computed by projecting earnings per share ten years ahead, applying a terminal P/E, and discounting back at the hurdle rate. All in Python, never by the language model.
**IVC.** The intrinsic-value calculator itself — the fixed formula that turns growth, P/E and hurdle assumptions into IV.
**FV10.** Projected value of one share ten years from now, before discounting back to today.
**eps_terminal.** Earnings per share the model expects in year ten, after the fade.
**Fade.** Growth is not held constant: in years six to ten the growth rate glides down toward the terminal rate, because no company compounds at its peak rate forever.
**PWFV (Probability-Weighted Fair Value).** The bear, base and bull IVs blended by their scenario weights. This is the single fair-value number the verdict leans on.
**MoS (Margin of Safety).** How far the current price sits below IV, as a percent of price. Negative MoS means the stock trades ABOVE our estimate of its worth.
**MoS ladder.** The three entry prices at which you would own the stock with a 10, 20 or 30 percent discount to IV. The arbiter names which rung this idea must reach before any buy.
**Hurdle / hurdle_gate.** The minimum acceptable return: 12 percent per year. The gate FAILS when the implied ten-year return at today's price is below 12 percent — meaning the price already assumes more growth than the base case delivers.
**Implied CAGR.** The annual return you would earn over ten years buying at today's price if our base scenario plays out exactly. Compare it to the 12 percent hurdle.
**verdict_cap.** A hard ceiling on the verdict, set deterministically: implied CAGR below 12 percent caps the name at AVOID; between 12 and 16 percent caps it at WATCH+. No prose can override it.
**GPS.** The Growth Pipeline Scorecard, up to 100 points across blocks: A growth, B profitability, C valuation, D balance sheet, E moat, F forecast trend, G capital allocation, H sentiment. It describes QUALITY; it does not set the verdict — the gates do.
**GPS denominator (e.g. 62/95).** When an input for a block is unavailable, that block's maximum points are removed from the scale instead of scoring a silent zero. A score out of 95 means 5 points of scale were unmeasurable this run. Do not compare raw GPS across tickers without checking the denominator.
**Dual basis (GAAP vs FCF).** The same company valued twice: on GAAP earnings and on free cash flow per share. Stock-based compensation makes these diverge; the verdict always follows the more conservative leg.
**PEG.** Forward P/E divided by expected EPS growth in percent. Around 1 is conventionally fair; well above 2 means you pay heavily for each point of growth.
**Forward P/E.** Today's price divided by next year's CONSENSUS earnings estimate. Trailing P/E uses last year's reported earnings — the two are different bases and are never mixed here.
**ERB.** Earnings-revision breadth: whether analysts have been raising or cutting estimates over the last 90 days. Positive means estimates are rising.
**Days-to-cover.** Short interest divided by average daily volume: how many trading days shorts would need to buy back their entire position.
**Net skew.** The probability-weighted sum of all bull arguments minus all bear arguments, in dollars of IV impact. Negative skew with a BUY verdict demands an explanation.
**DI (Disagreement Index).** How much the adversarial audit and the arbiter disagreed with the memo. 0-2 consensus; 3-5 divergence; 6 or more CONTESTED — trades are blocked until the listed items are verified by hand.
**[UNVERIFIED].** The datum could not be confirmed from an acceptable source this run. It is a stated gap, never a zero.
**[AGGREGATOR].** The figure comes from a sell-side tracker (Benzinga, TipRanks and similar), not from primary filings or tier-1 press. Usable, lower confidence.
**EVIDENCE PACK.** The block of exact figures the memo is required to cite verbatim when justifying qualitative scores and radar thresholds.
**DATA DEFECTS banner.** When the deterministic layer detects its own data problem (a stale field, a basis error, an unconfirmed split), it prints the defect at the top of section 1 so the flaw travels with the report instead of hiding under it.