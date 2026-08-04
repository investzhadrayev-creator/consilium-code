# NFLX — GROWTH ALPHA (machine report) — 2026-08-03

> Mandate: 12–16% CAGR / 10y, hurdle 12% (floor). DI=2 [consensus] | final: AVOID | rung 20% (base — no directional signal)
> FACT_PACK vectors: 14/14 unresolved (100%) | 🟠 data_questionable — most of the qualitative side is absent, not merely thin | threshold 30% (PROVISIONAL calibration, n=4 (1 clean); recalibrate at 6 clean runs)

**CENTRAL LENS:** IV 93.30 (growth 15.65% = median of annual increments; P/E 33.53 = window median, NO ceiling) | computed on gaap_base, delta vs verdict_leg(fcf_per_share) = 59.0% | ADVISORY: no verdict, alert or entry rung reads this.

**REVERSE DCF:** the current price already pays for 16.14% growth (multiple 30.0 held, hurdle 12.0%). Actual: 3y 12.6%, 5y 12.6%.

---

## FIELD GLOSSARY (read this before the tables)

*New in v4.2.65. Stable field names, one line each. Anything not listed here is not published.*

| field | meaning | who computes it |
|---|---|---|
| `iv` / IV | intrinsic value per share at the 12% hurdle | Python, deterministic |
| `implied_cagr_pct` | annual return the CURRENT price implies over 10y | Python |
| `fv10_per_share` | value per share at year 10, before discounting | Python |
| `verdict_leg` | which leg (gaap_eps / fcf_per_share) issues the verdict — the more conservative | Python |
| `verdict_cap` | ceiling on how bullish the arbiter may be; never forces a BUY | Python |
| `mos_ladder` | entry prices at 10/20/30% margin of safety | Python |
| `required_mos_rung_pct` | which rung applies THIS run | Python, from directional signals only |
| `rung_signals` | the directional signals that raised the rung; empty = base 20% | Python |
| `central_lens.iv` | IV without the conservative layers — **ADVISORY, decides nothing** | Python |
| `central_lens.computed_on` | which base the lens was computed FROM (`gaap_base`) | Python |
| `central_lens.delta_vs` | which leg the delta is measured AGAINST | Python |
| `reverse_dcf.g_implied_at_current_price` | growth the current price already embeds | Python, bisection + self-check |
| `gps.total` | quality score 0–100, ten blocks | Python |
| `_fp_vectors` | FACT_PACK sections that came back unresolved, and the share | Python (in the entity gate) |
| `pe_anchor.base_future_pe_used` | exit multiple actually used, after min() | Python |
| `dual_basis.gap_iv_pct` | disagreement between the two legs; >100% marks the FCF leg unreliable | Python |
| `DI` | disagreement index between memo, auditor and arbiter — **a quality flag, NOT a trade block** | Python, from arbiter counts |

---

## 0. EDGAR provenance & cross-check

```json
{
  "cik": "0001065280",
  "entity_name": "NETFLIX INC",
  "entity_lock": "RESOLVED_ENTITY echo verified against GROUND_TRUTH CIK — PASS",
  "latest_fy": "2025",
  "revenue_source": ["Revenues"],
  "confirmed_splits": [{"period": "2015-07-15", "factor": 7}],
  "dps_series": null,
  "dps_series_absent": "no CommonStockDividendsPerShare* facts in companyfacts; the filer may pay no dividend, or may tag it under a name not in DURATION_TAGS['dps']",
  "total_debt_source": "us-gaap:LongTermDebtNoncurrent + LongTermDebtCurrent",
  "debt_uncertain": false
}
```

---

## 1. Numeric layer (deterministic, Python)

### Verdict

| ticker | GPS | implied_cagr (verdict leg) | IV | MoS | verdict_cap |
| --- | --- | --- | --- | --- | --- |
| NFLX | 70/100 | 9.78% | $58.68 | −18.2% | AVOID |

`verdict_leg = fcf_per_share` (conservative of the two). Price $71.71, snapshot 2026-08-02.

### Dual basis

| leg | base_per_share | dilution basis | dilution | multiple | IV | implied_cagr |
| --- | --- | --- | --- | --- | --- | --- |
| gaap_eps | 2.5280 | net_after_buybacks | −0.888% | 30 | 68.96 | 11.56% |
| **fcf_per_share** | **2.1780** | gross_before_buybacks | **−0.765%** | **30** | **58.68** | **9.78%** |

`gap_iv_pct = −14.9` (below the 100% unreliability threshold).

### Anchors

| anchor | value | basis | which element bound |
| --- | --- | --- | --- |
| growth | 12.5695% | min(rev_cagr_3y 12.640%, rev_cagr_5y 12.570%) | rev_cagr_5y |
| exit multiple | 30 | min(pe_median_5y 33.53, pe_median_10y 44.51, PE_ABS_CAP 30) | **PE_ABS_CAP** |
| terminal growth | 4.00% | min(0.04, base_g) | 0.04 |
| dividend growth | 0.0 | the filer reports no per-share dividend — a CORRECT zero, a fact about the company, not a data gap | — |

`llm_base_g = 0.1565` and `llm_base_pe = 22` recorded, neither steers the base.

### MoS ladder

| target | entry price | discount to current | implied_cagr at entry | reached |
| --- | --- | --- | --- | --- |
| 10% | 53.35 | −25.6% | 13.07% | no |
| **20% (applies)** | **48.90** | **−31.8%** | **14.06%** | no |
| 30% | 45.14 | −37.0% | 14.98% | no |

`rung_signals = []` → base rung. No verdict flip, no sustained BLOCKING, no icagr sign disagreement, no GPS recount below published.

### Two lenses

| | verdict lens | central lens |
| --- | --- | --- |
| growth | 12.5695% (min of windows) | 15.6499% (median of annual increments) |
| exit multiple | 30 (PE_ABS_CAP bound) | 33.53 (window median, no ceiling) |
| fv10_per_share | 182.25 | 289.76 |
| **IV** | **58.68** | **93.30** |
| implied_cagr | 9.78% | 14.99% |
| computed on | fcf leg | gaap_base |
| decides | verdict, alerts, rung | **nothing** |

### Reverse DCF

| field | value |
| --- | --- |
| g_implied_at_current_price | 16.14% |
| at_hurdle_pct | 12.0 |
| future_pe_held | 30 (verdict multiple) |
| actual_rev_cagr_3y | 12.64% |
| actual_rev_cagr_5y | 12.57% |
| selftest_reverse_matches_forward | **true** |

### Scorecard (GPS 70/100)

| block | points | max | evidence |
| --- | --- | --- | --- |
| A (growth) | 13 | 16 | rev_cagr3 12.64%, rev_cagr5 12.57%, eps_cagr5 32.98% |
| A_runway | 3 | 4 | — |
| B (profitability) | 13 | 15 | — |
| C (valuation) | 7 | 15 | fwd_pe 22.73 vs pe_hist_median 44.51 |
| D (balance sheet) | 8 | 10 | dilution −0.888%, debt within band |
| E_moat | 12 | 15 | — |
| F (momentum) | 2 | 10 | 6m price growth −27.57% |
| F_forecast_trend | 4 | 5 | — |
| G_capalloc | 4 | 5 | — |
| H_sentiment | 4 | 5 | — |

### Bull / bear (IV deltas at the verdict lens)

| side | probability | ΔIV | ΔIV % | expected | driver |
| --- | --- | --- | --- | --- | --- |
| BULL | 0.35 | +23.24 | +39.6% | +8.13 | Ad-tier + paid-sharing monetization sustaining above-corridor growth |
| BULL | 0.25 | +13.88 | +23.7% | +3.47 | Quarterly revenue acceleration vs trailing CAGR |
| BULL | 0.30 | +2.35 | +4.0% | +0.70 | Margin expansion supports premium terminal multiple |
| BEAR | 0.30 | −11.93 | −20.3% | −3.58 | Reversion to trailing 3–5y revenue CAGR |
| BEAR | 0.25 | −16.43 | −28.0% | −4.11 | Multiple compression toward low-growth media peer trailing PE |
| BEAR | 0.20 | −14.85 | −25.3% | −2.97 | Content cost inflation / competitive bundling pressures growth |

### Market context

| field | value |
| --- | --- |
| fwd_pe | 22.73 |
| pe_hist_median | 44.51 |
| multiple_discount_pct | 48.9 |
| fear_discount_setup | false |
| divergence_available | false — no forward EPS estimate; a trailing-window comparison would be an artifact |

### Street

| field | value |
| --- | --- |
| consensus_target_mean | 94.33 |
| analyst_count | 58 (buy 29 / hold 13 / sell 16) |
| tier | yahoo consensus; named-bank targets belong to FACT_PACK with source+date |

### Self-tests

| test | result |
| --- | --- |
| run_complete | true |
| iv_computable | true |
| _FALLBACK | false |
| self_tests_all | true |
| selftest_mos_at_threshold_ok | true (all three rungs) |
| selftest_reverse_matches_forward | true |

---

## 2. FACT_PACK coverage

**Renamed in v4.2.65.** The marker used to read `[UNVERIFIED]` and sat next to section names that
match financial metrics — `Gross Profit [UNVERIFIED]` reads as "gross profit is unverified", when
the EDGAR figure is untouched and only the qualitative section is empty. The name lied about what
it marked. Sections are now prefixed `FP:` and the marker is `[NO SOURCED FACTS]`.

| vector | status |
| --- | --- |
| FP: Revenue commentary | [NO SOURCED FACTS] |
| FP: Profitability commentary | [NO SOURCED FACTS] |
| FP: Street view | [NO SOURCED FACTS] |
| FP: Regulation | [NO SOURCED FACTS] |
| FP: Litigation | [NO SOURCED FACTS] |
| FP: Competition | [NO SOURCED FACTS] |
| FP: Management tone | [NO SOURCED FACTS] |
| FP: Catalysts | [NO SOURCED FACTS] |
| FP: M&A | [NO SOURCED FACTS] |
| FP: Moat evidence | [NO SOURCED FACTS] |
| FP: Capital allocation | [NO SOURCED FACTS] |
| FP: Insider activity | resolved (Form 4, six filings) |
| FP: Segment detail | [NO SOURCED FACTS] |
| FP: Guidance | [NO SOURCED FACTS] |

`_fp_vectors`: 14 total, 14 unresolved, 100%, `data_questionable: true`, threshold 0.30
(PROVISIONAL, n=4).

**None of these markers reaches the investor brief.** The brief states the consequence in plain
language instead: the qualitative sections are absent this run, and the SEC figures are unaffected.

---

## 3. Why these parameters

*Printed by the assembler from constants — not written by a model. Each line carries its date and author.*

- **Entry rung 20%** — operator decision 23.07 / 02.08.2026: insurance against calculation error. Price measured: −16.7% on the entry price. Raised only by directional signals, never by DI class.
- **P/E ceiling 30 (PE_ABS_CAP)** — architect mandate 03.08.2026, conservative lens: the company is valued on its OWN median where that is lower; the absolute cap is bubble insurance. For NFLX the cap bound (own medians 33.53 / 44.51). The central lens is computed without it; the level itself stays open until the six-name comparison.
- **Fade to 4% terminal** — Graham-Dodd standard: no company outgrows the economy forever. The tail may only be slowed toward terminal, never lifted.
- **Growth base min(3y, 5y)** — protection against paying up front for one good stretch. The central lens uses the median of annual increments instead.
- **Verdict from the conservative lens** — the cost of being wrong is asymmetric in money: overpaying costs capital, a missed idea costs return.

---

## 4. Provenance

| data | source |
| --- | --- |
| revenue, income, FCF, share count, debt | SEC EDGAR, Netflix Inc. CIK 0001065280, 10-K FY2020–FY2025 |
| insider transactions | SEC EDGAR Form 4 — accession 0001065280-26-000188, 0001065280-26-000169, 0001583109-26-000002 |
| price and price history | Tiingo adjusted close |
| price snapshot | $71.71 at 2026-08-02 |
| risk-free rate | FRED DGS10 |
| ERP | Damodaran, pinned 4.6% |
| consensus | 58 analysts, mean target 94.33 |

---

## 5. Cross-document consistency

Every number below appears in BOTH this report and the investor brief, and must match exactly.

| field | value |
| --- | --- |
| verdict IV | 58.68 |
| central lens IV | 93.30 |
| price | 71.71 |
| implied_cagr (verdict) | 9.78% |
| g_implied (reverse DCF) | 16.14% |
| rung applied | 20% → $48.90 |
| ladder 10 / 20 / 30 | 53.35 / 48.90 / 45.14 |
| GPS | 70/100 |
| consensus | 94.33 |
| exit multiple used | 30 (PE_ABS_CAP bound) |
| year-5 reference | 69.64 |
| terminal FCF/share, dilution-adjusted | 6.075 |


---

## 6. Delivery contract

**Operator decision 03.08.2026.** A run's output is a **PAIR**: this machine report and the
investor brief. Delivering both is part of publication, not a courtesy. A run that produced one
without the other is a publication defect of class "a surface went missing" (lesson
`lensrender-01`) — to be diagnosed, not re-run.

Pin to be added with the render changeset: the run emits both documents, and every field in
§5 above holds the same value in both.
