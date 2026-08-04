# Consilium Spine — AI-assisted equity research pipeline

This repo runs real money decisions. Read this file before changing anything.

## What this is

An n8n workflow + a Flask microservice that produce an investment-committee memo for a ticker.
The mandate is 12–16% CAGR over 10 years with a **12% hurdle floor** and Graham-Dodd margin-of-
safety discipline. The output is a verdict (BUY / WATCH+ / NEUTRAL / AVOID) with an auditable
numeric trail.

Two paths:
- **Core-P** — profitable companies. IVC/DCF-style valuation, GPS scorecard, gates, audit, arbiter.
- **Core-V** — pre-profit / Category-F names. Scenario tree, survival analysis, venture discount.

## The one idea that matters

> **LLM does judgment. Python does math.**

Every field an LLM could write freely eventually smuggled in a defect. The fix was never a
better prompt — it was always **moving the logic into the deterministic layer**. The history:

- LLM wrote the wiring code → it flaked, double-counted GPS blocks, sometimes crashed →
  replaced by a fixed harness (`analyze()`), and Stage2a now emits a JSON *spec*, not code.
- LLM declared the GPS total → it disagreed with the visible blocks → total is now the sum,
  by construction.
- LLM justified `future_pe` → it overreached → the cap is now enforced deterministically.
- LLM cited insider trades from prose → it produced a $2.76/share trade on a $1,852 stock →
  now read from SEC Form 4 XML, with grants/vesting structurally separated from real buys.
- The harness collapsed the mandate's THREE verdict bands into two → **BUY was structurally
  unreachable for every name, forever** → three bands restored (<12 AVOID / 12-16 WATCH+ /
  >=16 BUY), with a test that pins BUY reachability. The operator noticed this before the
  tests did.
- GAAP EPS double-counts SBC (charged in earnings AND diluting the count) → every SBC-heavy
  software name was structurally AVOID → dual basis: both legs priced, verdict follows the
  conservative one, and a >40% gap forces the memo to argue which basis is right.
- Diagnostics fired on artifacts: a fear-discount flag from comparing trailing-3y vs
  trailing-5y growth (overlapping windows), and a 568% incremental ROIC from dividing by an
  asset-light capex base. Both appeared in the run that produced the first-ever BUY — the
  worst possible moment for a phantom confirmation. Now: no forward estimate → no divergence
  claim at all; capex <5% of revenue → `not_meaningful`.
- `PEER_MAP` was a stub covering 8 tickers, so the entire portfolio silently got `peers=[]`.
  It looked exactly like a Yahoo outage. Not every data gap is an outage — check coverage
  before blaming the source.

If you find yourself writing a prompt to *ask* a model to be accurate about a number, stop.
Move it to Python instead.

## Source hierarchy

Prefer the ORIGIN of a number over anyone who republishes it, and compute ratios rather than
ingesting ready-made ones:

1. **SEC EDGAR** — all historical financials, share counts, insider Form 4. Never breaks.
2. **FINRA** — short interest. They collect it; Yahoo and every aggregator resell it.
3. **Alpha Vantage / Finnhub / Tiingo** — forward consensus, revision trends, prices.
4. **In-house computed** — peer P/E (EDGAR EPS x Tiingo price), fwd P/E (price / consensus EPS),
   short % (FINRA shares / EDGAR shares). Our arithmetic, auditable.
5. **yfinance** — last resort and cross-check only. Nulls out on cloud IPs without warning, and
   for a long time it was the ONLY source for every forward field. That was the bug.

Two rules that follow:

- **Divergence is loud.** Two sources disagreeing by >5% lands in `_divergence` — surfaced to
  the auditor, never silently averaged.
- **A number's BASIS travels with it.** Trailing P/E is not forward P/E. Shares outstanding is
  not float. FCF/share is not GAAP EPS. Every one of these pairs has already produced a wrong
  conclusion from a correct number in this pipeline. Label, or don't report.

## Layout

```
microservice/     Flask service (deployed to Railway as "growth-enrich"). ONE service, 9 routes.
  app.py            /health /enrich_yf /scenario_tree /edgar_facts /edgar_form4
                    /market_facts /macro_prices /analyze /cost
  pricing.py        v4.2.5. ONE home for LLM rates. Tokens are facts (provider usage blocks);
                    dollars are an ESTIMATE carrying the table's date. An unpriced model is
                    [UNVERIFIED], never $0 -- a run is never free. See SETUP_billing.md.
                    (this list said "7 routes" and omitted /macro_prices until 2026-07-17.
                     Not cosmetic: /macro_prices supplies pe_hist_median, the PE cap's best
                     anchor, and is smoke check #1 in VERIFY.md.)
                    `analyze()` IS the deterministic harness. This is the money-critical function.
  ivc_lib.py        PINNED valuation math (ivc, bull_bear_table, gps_quant). Treat as frozen.
  edgar_facts.py    SEC XBRL financials + sanity gates + confirmed-split detection.
  edgar_form4.py    SEC Form 4 insider transactions (discretionary P/S vs grants/vesting).
  market_facts.py   Second-source market layer: Alpha Vantage consensus, Finnhub revision
                    trends, in-house peer P/E (EDGAR EPS x Tiingo price), FINRA short interest,
                    and a >5% quorum check between sources.
  finra_short_interest.py  FINRA consolidatedShortInterest (OAuth2 client-credentials).
  scenario_f.py     Core-V Category-F scenario anchors.
  enrich_yf.py      yfinance enrichment (peers, PEG, ERB). Best-effort tier, degrades to null.
workflow/         The n8n workflow JSON. Highest version number = current.
tests/            Offline regression suite. Every test encodes a bug that actually happened.
```

There is no `/run` route and no code execution anywhere. That was removed deliberately —
after the harness landed, nothing needed to execute LLM-written code, so the capability was
deleted rather than left lying around.

## Commands

```bash
npm install                                 # ONCE per container. eslint 8, for the undef gate.
                                            # Skip it and run_tests.py prints NOT VERIFIED.
python3 run_tests.py                        # whole suite: offline, free, <1s. Do this before every deploy.
python3 -m unittest discover tests          # python tests only
node tests/test_render_tables.js            # the JS nodes (Render Tables / Build Radar)

cd microservice && python3 edgar_facts.py --selftest    # offline
cd microservice && python3 edgar_form4.py --selftest     # offline
cd microservice && python3 edgar_form4.py NOW            # LIVE SEC call — use sparingly, respect rate limits
cd microservice && python3 finra_short_interest.py AAPL <client_id> <client_secret>   # LIVE FINRA call
```

`requirements.txt` pins the deployed set. The python suite needs only `flask` — yfinance and
curl_cffi are imported lazily inside functions and are never touched by tests. The JS gates need
`node` plus `eslint` 8 (`package.json`, dev-only, never deployed). Absent either, the runner
reports NOT VERIFIED rather than green: for a long time it reported green instead, which is why
`package.json` exists at all.

## Rules

**Never weaken a gate to make a ticker pass.**
A BLOCKING gate that fires is the system working. If a healthy name is being rejected, the bug
is upstream in the deterministic layer — fix it there. Loosening a threshold, widening a
tolerance, or downgrading BLOCKING→MAJOR to get a green run destroys the margin of safety this
whole system exists to enforce, and it does so *silently*: the tests still pass and the report
still looks authoritative. This is the single most damaging change you could make here.
The three gates that were correctly relaxed (GPS_TOTAL_MISMATCH, gate_override,
pe_cap_unjustified) were relaxed **only after** the deterministic layer made the check
structurally unnecessary — never to make a run go green.

**Ask before touching these.** They are load-bearing for correctness, not style:
- `microservice/ivc_lib.py` — pinned valuation math
- `analyze()` in `microservice/app.py` — the harness
- gate/threshold logic in any prompt (`stage4`, `stage5_auditor`, `core_v_auditor`)
- `hurdle` (0.12), the PE-CAP constants, the venture discount rate

**Run the tests before proposing any diff to microservice/ or workflow/.** If a change is
money-critical, show the before/after numbers on a concrete ticker profile, not just "tests
pass".

**Never touch the n8n service's own env vars.** All data-source keys belong to the
growth-enrich service. Railway's RAW Editor REPLACES the variable set rather than appending to
it, and the n8n service's set includes `N8N_ENCRYPTION_KEY` — wipe it and every stored
credential becomes undecryptable ("a different encryptionKey was used"). Workflows survive
(they aren't encrypted); credentials must be recreated. This already happened once, following
setup instructions that were themselves wrong — the instruction, not the operator, was the
defect.

**Change the topology → bump the meter map.** `Collect Usage` holds a second copy of the path
topology (the `NOT_ON_PATH` set: disabled Grok, the Core-V branch, and — under gated mode — Stage
5/6). It decides whether a stage's silence is a free zero (`not_run`) or spent-but-unmeasured money
(`meter_lost`). If you re-wire a stage (re-enable Grok, add an LLM node, re-route Core-V) and leave
that set stale, the meters lie again — silently, the way they did on 2026-07-18. So: any edit to the
workflow connections that adds, removes, or re-routes an LLM stage MUST update `NOT_ON_PATH` in the
same changeset. `TestMeterMapTopologyV4221` pins the map to the actual graph and fails on drift
(negative-control verified: re-wiring Grok without touching the map turns it red).

**ALL GREEN means the runner's exit code is 0 — and you say so explicitly in the handoff.** Not "the
python summary printed OK", not a grep of the log. `python run_tests.py; echo $?` must print `0`, and
the handoff must name it. A partial grep once masked a JS gate that had been red since v4.2.20
(`test_cost_section.js`), and "safe to deploy" was claimed on a run whose true exit code was 1. A
check whose result you did not read has not passed.

**Diagnose an integration defect from the source's RAW response, never from the symptom in the
report.** A null/`[UNVERIFIED]` field in the output tells you *that* something failed, not *why* or
*where*. The 2026-07-19 case: `fwd_pe` printed `[UNVERIFIED]`, the backlog blamed the AV key, and the
operator swapped the AV key three times to no effect — because `fwd_pe` reaches the report from Yahoo
(rate-limited on cloud IPs), and AV's own `forward_pe_reported` was locked behind an `eps_ttm`/growth
gate it never cleared. Only reading the actual `/market_facts` response path found it. So: before
proposing a cause, trace the field back through the raw response of each source it touches; a fix aimed
at the symptom's assumed cause is a guess until the raw log confirms it.

**Never edit node source by position.** Two v4.2 defects, one root cause. (1) A patch spliced
`Gather Data` by character offset and chopped 87 chars off its head -> `SyntaxError: Unexpected
token ')'` in production; the workflow JSON stayed valid and every python test passed, because
nothing in the suite parsed node source. (2) v4.0 packs three consts onto ONE line
(`const FINN=...; const TIINGO=...; const AVKEY=...;`), so a line-oriented regex intended for a
later comment matched the FIRST `//` on a merged line and ate a freshly-inserted comment.
Both are the same mistake: treating JS source as positions/lines rather than as anchored text.
Rules: anchor on exact substrings; when a region spans several statements, replace the WHOLE
span in one cut; re-parse every touched node afterwards (`node tests/test_syntax.js`, now in
run_tests.py, 18 nodes, negative-control verified).

**One canonical home per fact.** Env-var NAMES live in SETUP_railway.md, nowhere else -- not in
JS comments, not in the changelog. The secret-hygiene test scans for the bare names, and a
comment reciting them trips it. That is the test being right for a slightly wrong reason, but
the fix is still to reword rather than exempt comments: a stale name in an old changelog entry
is something a reader can copy back into the JSON, reopening exactly the leak v4.2 closed.

**A green suite is not coverage.** Every render block sits behind `if (isObj(res.<section>))`.
If the mock in `tests/test_render_tables.js` lacks that key, the branch never executes and the
test passes without testing anything — that is exactly how a `gt is not defined` ReferenceError
reached a live run while the suite reported 10/10. **Adding a render section requires extending
MOCK_RESULT in the same change.** When you fix a bug the suite missed, ask first why it missed
it, and fix that too.

The same disease reached the RUNNER (found 2026-07-17). `test_undef.js` exited **0** when eslint
was missing, so `run_tests.py` printed "ALL GREEN — safe to deploy" having resolved zero
identifiers in zero nodes — and eslint is missing in every fresh container, which is every chat
session. The gate that exists because `gt is not defined` shipped twice was itself the gate not
running, and the only trace was one dim stderr line that any `| tail` swallowed. Both JS gates
now enforce a coverage floor (`total >= 19`), missing tooling exits **2**, and the runner prints
**NOT VERIFIED** — a third state, distinct from pass and fail, because "did not run" is neither.
The rule generalises: **a check reports what it examined, or it reports nothing. Never let
"skipped" and "passed" print the same word.** This is the v4.2.2 lesson — unknown spelled "0" —
one level up, in the very thing that certifies the others.

And a third face of it, found 2026-07-17 by reading a live report rather than by any test: an
honest number computed and then DISCARDED AT THE BOUNDARY. `gps_quant` correctly reduced a
block's max and correctly asked for `implied_cagr_base`; `analyze()` hardcoded the nominal maxima
over the first and never supplied the second. Both units were individually correct and 165 tests
passed, because every test drove `gps_quant` and none drove its CALLER. **Where a docstring says
"consumers must read X", write the test against the CONSUMER.** A contract asserted only in prose
is a contract nobody checks — and the caller is where contracts die.

**Honest failure beats an invented number.** If a driver is missing, return an error and let
the run fail conservatively. Never substitute a plausible default for a number you don't have.
`growth_rate` and `future_pe` are deliberately None-able for exactly this reason.

**Missing data is null, never zero.** A zero flows through arithmetic and corrupts everything
downstream; a null stops and says so. Placeholder zeros from EDGAR are dropped and *recorded*
in `_flags.dropped_zero` — visible, not silent.

**Don't trust the LLM spec's shape.** `dict.get(k, default)` does NOT substitute the default
when the key exists with value `None` — that exact gotcha emptied PLTR's entire numeric layer.
Sanitize at the boundary.

**Never run with `--dangerously-skip-permissions` in this repo.** It's a financial tool; a
silently auto-approved bad edit costs real money.

## Language

The report is written in **English** (it's fed to NotebookLM, which translates to Russian and
preserves the numbers). Deterministic nodes that render report text — `Render Tables`,
`Build Radar`, `Assemble Report`, `Assemble Core-V` — must contain **zero Cyrillic**; there is
a test for this, because the leak happened twice.

Two deliberate exceptions:
- `Prompts Growth` — Russian text there is *instructions* to a multilingual model, not output.
- `Gather Data` — its Russian strings are operator-facing Telegram errors shown to the user
  directly ("Пустой ввод — укажите тикер"). Correctly Russian. Leave them.

## Deploy

1. `python3 run_tests.py` — must be green.
2. Push `microservice/` to the growth-enrich Railway repo. Redeploy.
3. Import `workflow/consilium_spine_vX_Y.json` into n8n.
4. Nothing to fill in. As of v4.1 the workflow contains **no keys and no placeholders**: HTTP
   nodes bind to n8n credentials BY NAME (`Anthropic API`, `OpenAI API`, `xAI API`,
   `Perplexity API`, `Gemini API` — the last is Query Auth, the rest Header Auth), and code
   nodes read `$env.*` (`PYTHON_SERVICE_URL`, `TIINGO_TOKEN`, `FRED_KEY`, `FINNHUB_KEY`,
   `ALPHAVANTAGE_KEY`, `FINRA_CLIENT_ID`, `FINRA_CLIENT_SECRET`, `SEC_USER_AGENT`,
   `TELEGRAM_CHAT_ID`). Credential names must match exactly or n8n won't rebind on import.
   **Never reintroduce a key into the JSON** — the export is meant to be safe to share, and
   that property is only one careless edit away from being lost.
5. Set the env vars (docker-compose) and create the credentials — once, see SETUP.md §3.3.
   A missing key disables only its own source: the run degrades to `[UNVERIFIED]` rather than
   failing. FINRA credential type must be **Public**, not Mock (Mock returns randomized data).
6. `SEC_USER_AGENT` must carry a real contact email (SEC fair-access rule). It is an **env var
   on growth-enrich** — `edgar_facts.py` reads it via `os.environ.get` and falls back to a
   string containing `SEC_USER_AGENT NOT SET`, which is what to grep the Railway logs for. This
   said "the constant in `edgar_facts.py` for the Railway side" until 2026-07-17; that was
   stale, and SETUP.md §1.2 still told the operator to hardcode it. Do not edit the source.
7. Set `Consilium Error Handler` as the workflow's Error workflow, or failures stay silent
   until someone opens n8n.

## Known open items

- **PE-CAP no-anchor default (20x)** is a blunt constant. If live runs show it systematically
  mis-pricing a sector, make it sector-aware — but only with evidence from real runs.
- **Form4 lookback** is capped at 40 filings / 270 days. A mega-cap with very active insiders
  could brush the node's 40s timeout.
- **Render Tables is ~26KB** of rendering logic. The Cyrillic tests cover the paths a normal
  run takes; a rare branch could still hide something.
- **Verdicts are unstable at band edges.** ADBE landed BUY at 16.22% implied CAGR against a
  16.0% threshold — a 0.22pp margin, while `growth_rate`/`future_pe` are LLM judgment that
  drifts between runs (a prior run gave 18.08% and WATCH+). Any threshold has an edge; just
  don't read a near-edge verdict as precision.
- **The hurdle (12%) sits below the operator's own goal** (~15-18% CAGR to reach the target).
  Approving 12-13% names cannot compound to the goal. Unresolved by design — the operator
  decides whether to raise the hurdle or make up the gap in the speculative sleeve.
- **Owner-earnings third leg.** The FCF leg punishes capex-heavy names (MSFT), which is the
  market's fear materialized rather than an accounting artifact. A maintenance-capex-only
  ("owner earnings") leg would address it, but splitting growth vs maintenance capex is
  judgment, not a fact — needs the operator's call before building.
- **No last-known-good cache.** A transient source outage still nulls a field for that run.
  Approved in principle, not built.

## Lesson (v4.2.2, NFLX 2026-07-16): "unknown" needs a vocabulary, or it gets spelled "0"

Four defects in one run. All four came from the **deterministic layer** — the one we call
trusted. All four were caught by an **LLM**: Stage 2b read `growth_diag` and wrote that the EPS
CAGR was "contaminated"; Stage 2b named the trailing peer multiple as WBD's distressed 95x;
Stage 2b diagnosed the C block as "structurally starved of forward-PE data, not a judgment that
valuation is cheap." The judgment layer worked exactly as designed. The math layer lied.

"LLM does judgment, Python does math" remains right. It does **not** follow that Python is
therefore correct. Our tests checked that code parses, that identifiers resolve, that secrets do
not leak. Not one checked that a **number means what it says**.

The root pattern, `0 if x is None else ...`, appeared nine times. It reads as conservative and
is the opposite: it states a confident falsehood where it should state a gap. NFLX paid three
ways at once — punished for a split we failed to confirm, punished for dilution while it was
buying back 96.5% of FCF, punished for a valuation field we never fetched. A reader cannot
distinguish "scored zero" from "we didn't look", and neither can the memo, the auditor or the
arbiter downstream. **A model with no way to say "I don't know" will say something else instead,
and it will sound just as certain.**

Corollaries earned here, each with a case of record:

- **The basis travels with the number, or the number is a lie.** A 2022 numerator over a 2026
  denominator; a trailing median under a hardcoded "fwd" label. Both survived every gate because
  gates check *values*, and the defect was in the *units*.
- **A client-side sort cannot repair a server-side truncation.** We sorted the wrong 60 rows for
  three and a half years.
- **A wrong anchor is worse than no anchor.** A 143x PE cap is not a loose cap; it is the
  absence of one, wearing a cap's name.
- **Absence must be stated.** `confirmed_splits` returning empty was indistinguishable from
  "no split ever happened" — so a real split became 56%/yr dilution.
- **What the reader never sees reaches the verdict anyway.** Hence the DATA DEFECTS banner.

Note what held: the verdict. `eps0` is a single year and never spanned the break, so IV, PWFV,
MoS and implied_cagr were clean and AVOID was correct throughout. The defects hit *comparisons
across time*, not point-in-time facts. That distinction is the reason to keep the deterministic
and judgment layers separate — and the reason to stop assuming the deterministic one is honest
just because it is code.

## Работа с workflow/ — контекстная бомба
Поля jsCode в спайне — одиночные строки до 58 000 символов. Обычный grep по workflow/*.json
выбрасывает в контекст сотни килобайт и съедает треть окна чата. ВСЕГДА используй grep -c или
grep -o с узким шаблоном, либо читай через python3 с точечным срезом по индексу. Никогда не
печатай ноду целиком. В репозитории держится ТОЛЬКО текущий спайн — мёртвые версии удаляются при
бампе, их история остаётся в HANDOFF.
