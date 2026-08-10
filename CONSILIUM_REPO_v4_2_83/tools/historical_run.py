#!/usr/bin/env python3
# __build__ = "v4.2.83"
"""
tools/historical_run.py — Счёт проверки №1: историческая проверка методики.

Источник методики: mailbox/PREREG_2026-08-06_HISTORICAL_VALIDATION.md (заморожен, не
переписывается). Исполнение разрешено при действующем STOP BUILD решением
mailbox/DECISION_2026-08-09_ARBITRATION.md, пункты В1 ("счёт проверки №1... исполнение
протокола, замороженного до событий, — не стройка") и В4 (теневой FCFF/DCF мост, EXPLORATORY).

Это НЕ стройка новой методики. Каждая формула ниже либо переиспользует существующий
код микросервиса как библиотеку — ivc_lib.py (ivc()) вызывается ЖИВЬЁМ отсюда; edgar_facts.py
(as_of-фильтрация, roe_median_5y, серии) и macro_prices.py (split_factor_since, same-share-basis
логика) были вызваны ЖИВЬЁМ один раз, ОФЛАЙН от этого скрипта, при сборке самого архива — их
готовый вывод и есть содержимое *_edgar.json / *_price.json, см. ФОРМАТ АРХИВА ниже — либо
реализует буквально то, что PREREG §8 определяет как формулу.
ivc_lib.py / edgar_facts.py / macro_prices.py / app.py НЕ модифицируются этим изменением.

ЧТО НЕ ВХОДИТ (по мандату карточки issue #28):
  - CASH_DECAY — под STOP BUILD, не реализуется ни в каком виде.
  - воркфлоу (workflow/) — не читается и не трогается.
  - LLM-вызовы, сценарии, качественный слой, арбитраж, новостной ярус — вне PREREG §2.

ФОРМАТ АРХИВА (Reports/histrun_2026-08-08/histrun_raw_v3.zip, читается через zipfile, никогда
не распаковывается на диск): пары файлов `<TICKER>_<YYYYMMDD>_edgar.json` /
`<TICKER>_<YYYYMMDD>_price.json` на каждое наблюдение.
  issue #30: первый реальный прогон (175/175 REFUSED на "cik") показал, что первоначальное
  допущение ниже было угадано неверно; форма исправлена по факту реального архива, не по новой
  догадке — сверено построчно по образцу NVDA_20200323 (та же пара теперь лежит в
  tests/fixtures/ как обязательный пин, см. TestRealArchiveFixtureNVDA):
    *_edgar.json  — уже ГОТОВЫЙ ВЫВОД microservice/edgar_facts.py:edgar_facts(ticker, cik, as_of)
                    (as_of-отфильтрованный на дату проверки), НЕ RAW SEC companyfacts. Служебные
                    поля несут подчёркивание ровно как их пишет сама edgar_facts(): _cik, _as_of,
                    _entity_name, _errors, _field_sources, _flags, _missing, _source, _ticker.
                    Числовые ряды (revenue/net_income/ocf/capex/shares_diluted/...) уже лежат как
                    [{"end":..., "val":...}, ...]; roe_median_5y — уже посчитанное число или null.
                    cik (без подчёркивания, на верхнем уровне) — запасное имя, только для старых
                    синтетических фикстур этого теста; реальный архив несёт _cik.
    *_price.json  — ОБЪЕКТ (не список!) {date, ticker, price_record, split_factor,
                    pe_same_share_basis, _errors}. price_record — ОДНА дневная запись Tiingo
                    (close/adjClose/splitFactor/divCash/date) на проверяемую дату, или null,
                    если торгов в этот день не было (тикер ещё не торговался). split_factor —
                    УЖЕ посчитанный кумулятивный множитель сплита (тот самый вывод
                    macro_prices.split_factor_since(), посчитанный при сборке архива по полной
                    истории дневных строк, которую этот скрипт никогда не видит), не список
                    сырых строк для пересчёта на лету. _errors — словарь по ключам
                    "tiingo_price_on_date_<TICKER>" / "split_factor_<TICKER>" /
                    "pe_same_share_basis_<TICKER>", ровно как их пишут одноимённые функции
                    macro_prices.py — используется как ГОТОВАЯ причина отказа, а не
                    перевычисляется. Поле "pe_hist_median" (см. PROTOCOL_GAPS) — ни разу не
                    встречено ни в одной из 175 реальных записей архива v3; если оператор его
                    когда-нибудь добавит, ищем НА ВЕРХНЕМ уровне *_price.json (рядом с
                    split_factor), не внутри price_record — задокументированное допущение
                    по аналогии с остальными вычисленными полями объекта, не угаданное вслепую.
  Если операторский архив несёт другую форму — каждая пара откажет по имени (KeyError/типовая
  ошибка ловится и публикуется как REFUSED с причиной), а не молча даёт неверное число.

Использование:
    python3 tools/historical_run.py --archive ../Reports/histrun_2026-08-08/histrun_raw_v3.zip \\
        --outdir ../Reports/histrun_2026-08-08
"""
import argparse
import csv
import json
import os
import re
import sys
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_MICROSERVICE = os.path.join(_REPO, "microservice")
if _MICROSERVICE not in sys.path:
    sys.path.insert(0, _MICROSERVICE)

# issue #30: the archive's *_edgar.json / *_price.json already ARE the live output of
# edgar_facts.edgar_facts() / macro_prices.split_factor_since() (see module docstring's ФОРМАТ
# АРХИВА) -- score_pair() below reads those computed fields directly and never re-invokes either
# module, so neither is imported here anymore (no cache to preseed, no network path to guard).
import ivc_lib                    # noqa: E402

# ---- PREREG §2 / §8 constants — the frozen protocol, not a tunable ----------------------------
HURDLE = 0.12
K_EXIT_GRID = (0.08, 0.09, 0.10)
K_EXIT_MAIN = 0.09
ROE_CAP = 0.40
TERMINAL_GROWTH_CAP = 0.04
GROWTH_CAP = 0.20
MOS_TARGET_A = 0.0    # PREREG §2: вариант А — без скидки
MOS_TARGET_B = 0.10   # PREREG §2: вариант Б — со скидкой 10%

FILENAME_RE = re.compile(r"^([A-Z][A-Z0-9.\-]*)_(\d{8})_(edgar|price)\.json$")

# ---- Именованные пробелы протокола (см. модульный docstring и текст PR) -----------------------
PROTOCOL_GAPS = [
    "Внутренняя форма *_edgar.json/*_price.json не описана нигде в PREREG или в карточке — issue "
    "#30 сверил с первым реальным архивом и заменил первоначальную (неверную) догадку: "
    "*_edgar.json — готовый вывод edgar_facts.edgar_facts(), *_price.json — объект с ОДНОЙ "
    "дневной записью и уже посчитанным split_factor, а не списки сырых записей (см. docstring "
    "файла, раздел ФОРМАТ АРХИВА).",
    "Формула нога денежного потока (levered FCF/share) не определена в PREREG буквально — "
    "использовано стандартное отраслевое определение (OCF - capex) / shares_diluted, то же, что "
    "упоминает CLAUDE.md ('Owner-earnings third leg'); сама формула в проекте живёт в JS-ноде "
    "workflow, которую по правилам этой карточки читать нельзя (контекстная бомба).",
    "PREREG §8 не определяет terminal-multiplier формулу для ROE_terminal(capped) <= "
    "terminal_growth (payout был бы отрицательным/неопределённым) — реализовано как именованный "
    "отказ пары, а не подстановка.",
    "PREREG §8 не говорит, что делать, если pe_hist_median недоступен на дату — прочитано как "
    "'историческая медиана — necessary только когда есть' (её роль уже понижена до проверки "
    "разумности §8), формульный потолок используется один, факт недоступности медианы отмечен "
    "флагом на строке, пара не отказывает по этой причине одной.",
    "pe_hist_median ни разу не встречен ни в одной из 175 записей реального архива v3 (issue "
    "#30) -- где именно в *_price.json оператор положил бы его, если когда-нибудь положит, "
    "нигде не задокументировано; читается с ВЕРХНЕГО уровня объекта (рядом с split_factor), по "
    "аналогии с остальными вычисленными полями того же объекта, а не изнутри price_record "
    "(которое по всем 175 образцам — сырая Tiingo-строка без места для добавленных полей).",
    "Рост (growth_rate) не имеет пола (floor) по тексту PREREG — отрицательный рост не "
    "обрезается нулём, только потолок 20% применяется, как написано.",
    "Универсум 34 имён нигде не перечислен (ни в PREREG, ни в карточке) — тикер×дата пары "
    "берутся из содержимого архива (какие пары оператор загрузил, те и считаются), а не из "
    "жёстко зашитого списка.",
    "Теневой FCFF/DCF мост (решение В4) не имеет собственной пре-регистрации методики — "
    "реализован тем же пинованным движком ivc_lib.ivc(), но с Gordon-growth терминальным "
    "мультипликатором (1+tg)/(hurdle-tg) вместо мультипликатора-как-в-официальном счёте; это "
    "самостоятельный дизайн-выбор для EXPLORATORY-моста, не значение из документа.",
    "confirmed_splits наследуется этим перепрогоном как есть из архивного gt['_flags'] -- "
    "историческая проверка больше не вызывает edgar_facts() сама (issue #30: архив уже несёт её "
    "готовый вывод) и поэтому не управляет тем, каким плечом (companyfacts vs companyconcept) "
    "confirmed_splits был вычислен при сборке архива; чем бы он ни был на момент сборки, тем и "
    "остаётся на момент перепрогона.",
]


def _fmt_date(ymd):
    return "%s-%s-%s" % (ymd[0:4], ymd[4:6], ymd[6:8])


def discover_pairs(names):
    """Group archive filenames into (ticker, ymd, edgar_name, price_name) — BOTH files required.
    A ticker/date with only one file present is a named refusal ('incomplete_pair'), never
    silently dropped and never processed with a half-missing input."""
    have = {}
    for n in names:
        m = FILENAME_RE.match(os.path.basename(n))
        if not m:
            continue
        ticker, ymd, kind = m.groups()
        have.setdefault((ticker, ymd), {})[kind] = n
    pairs, incomplete = [], []
    for (ticker, ymd), kinds in sorted(have.items()):
        if "edgar" in kinds and "price" in kinds:
            pairs.append((ticker, ymd, kinds["edgar"], kinds["price"]))
        else:
            missing = "price" if "edgar" in kinds else "edgar"
            incomplete.append({"ticker": ticker, "date": _fmt_date(ymd),
                                "reason": "incomplete_pair_missing_%s_file" % missing})
    return pairs, incomplete


def _latest_common_end(*series_list):
    """Most recent 'end' present in EVERY given series (each [{'end','val'}], already as_of-
    filtered by edgar_facts()). None if any series is empty or they share no common FY end."""
    if not series_list or any(not s for s in series_list):
        return None
    common = set(r["end"] for r in series_list[0] if r.get("val") is not None)
    for s in series_list[1:]:
        common &= set(r["end"] for r in s if r.get("val") is not None)
    return max(common) if common else None


def _value_at(series, end):
    for r in series or []:
        if r.get("end") == end:
            return r.get("val")
    return None


def compute_eps_leg(gt):
    """Base (GAAP EPS) leg, AS-FILED basis. PREREG §2/§9: inputs of the LAST FY as of the test
    date — a single year, per §7's own reasoning (a single year never spans a split break)."""
    end = _latest_common_end(gt.get("net_income") or [], gt.get("shares_diluted") or [])
    if end is None:
        return None, None, "net_income/shares_diluted: no common FY end available as of date"
    sh = _value_at(gt["shares_diluted"], end)
    if not sh or sh <= 0:
        return None, end, "shares_diluted is zero/missing for FY %s" % end
    ni = _value_at(gt["net_income"], end)
    if ni is None:
        return None, end, "net_income missing for FY %s" % end
    return ni / sh, end, None


def compute_fcf_leg(gt):
    """Cash-flow leg, AS-FILED basis: levered FCF/share = (OCF - capex) / diluted shares — see
    PROTOCOL_GAPS: PREREG names the leg, not the formula; this is the standard definition."""
    end = _latest_common_end(gt.get("ocf") or [], gt.get("capex") or [], gt.get("shares_diluted") or [])
    if end is None:
        return None, None, "ocf/capex/shares_diluted: no common FY end available as of date"
    sh = _value_at(gt["shares_diluted"], end)
    if not sh or sh <= 0:
        return None, end, "shares_diluted is zero/missing for FY %s" % end
    ocf = _value_at(gt["ocf"], end)
    capex = _value_at(gt["capex"], end)
    if ocf is None or capex is None:
        return None, end, "ocf/capex missing for FY %s" % end
    return (ocf - capex) / sh, end, None


def compute_growth_anchor(gt):
    """PREREG §2: min(rev_cagr_3y, rev_cagr_5y), ceiling 20%. No floor — see PROTOCOL_GAPS."""
    revenue = gt.get("revenue") or []
    rc3 = ivc_lib._cagr(revenue, 3)
    rc5 = ivc_lib._cagr(revenue, 5)
    if rc3 is None or rc5 is None:
        return None, rc3, rc5, (
            "revenue history insufficient for both the 3y and 5y CAGR window required by "
            "PREREG §2's growth anchor (a young name, or a gap in the as-of-filtered series)")
    g = min(min(rc3, rc5), GROWTH_CAP)
    return g, rc3, rc5, None


def compute_terminal_multiple(roe_median_5y, g, k_exit):
    """PREREG §8, literally. Refuses (does not saturate/invent) outside the formula's domain —
    see PROTOCOL_GAPS for the roe<=g case, which the document does not address."""
    if roe_median_5y is None:
        return None, None, None, None, ("roe_median_5y unavailable "
                                         "(see edgar_facts _flags.roe_median_5y_refused)")
    roe_capped = min(roe_median_5y, ROE_CAP)
    excess = max(0.0, roe_median_5y - ROE_CAP)
    if roe_capped <= 0:
        return None, None, roe_capped, excess, "roe_median_5y (capped) is <= 0 -- payout ratio undefined"
    if roe_capped <= g:
        return None, None, roe_capped, excess, (
            "roe_median_5y (capped %.4f) <= terminal growth %.4f -- payout ratio would be "
            "negative; PREREG §8 does not define this case" % (roe_capped, g))
    payout = 1 - g / roe_capped
    denom = k_exit - g
    if denom <= 0:
        return None, payout, roe_capped, excess, "k_exit <= terminal growth -- undefined"
    return payout / denom, payout, roe_capped, excess, None


def official_future_pe(roe_median_5y, g, k_exit, pe_hist_median):
    """PREREG §8: the historical median is a SANITY CHECK, not an anchor. If it is BELOW the
    formula ceiling, it wins and the discarded formula excess is named; if unavailable, the
    formula ceiling governs alone (see PROTOCOL_GAPS)."""
    multiple, payout, roe_capped, excess, reason = compute_terminal_multiple(roe_median_5y, g, k_exit)
    meta = {"formula_cap": multiple, "payout": payout, "roe_terminal_capped": roe_capped,
            "roe_excess_discarded_pp": round(excess, 4) if excess is not None else None,
            "pe_hist_median": pe_hist_median, "reason": reason}
    if multiple is None:
        meta["source"] = None
        return None, meta
    if pe_hist_median is not None and pe_hist_median < multiple:
        meta["source"] = "historical_median"
        meta["formula_excess_discarded"] = round(multiple - pe_hist_median, 4)
        return pe_hist_median, meta
    meta["source"] = "formula" if pe_hist_median is not None else "formula_no_median_available"
    return multiple, meta


def basis_adjust(value_as_filed, split_factor, split_factor_reason, errors, symbol):
    """AS-FILED basis -> TODAY's basis — PREREG §7, the technical trap this whole stand exists to
    catch. issue #30: the archive ships split_factor ALREADY computed (macro_prices.
    split_factor_since()'s own output, from the full daily-row history at archive-build time,
    which this offline replay never sees — see module docstring's ФОРМАТ АРХИВА), so this divides
    by that precomputed number rather than recomputing it from raw daily rows."""
    if value_as_filed is None:
        return None, None
    if not isinstance(split_factor, (int, float)) or split_factor <= 0:
        errors["split_factor_%s" % symbol] = (
            split_factor_reason or "split_factor missing/invalid in the archived price record")
        return None, None
    return value_as_filed / split_factor, split_factor


def shadow_fcff_dcf(fcf_today, price, g, tg, official_iv):
    """Decision В4 — a full FCFF/DCF bridge in PARALLEL, tagged EXPLORATORY, never feeding the
    official verdict. See PROTOCOL_GAPS for the method choice: same pinned engine
    (ivc_lib.ivc), Gordon-growth perpetuity terminal multiple instead of the §8 exit multiple."""
    label = "EXPLORATORY -- NOT USED FOR TEST #1 VERDICT"
    if fcf_today is None or HURDLE <= tg:
        return {"label": label, "intrinsic_value": None, "delta_to_official": None,
                "delta_to_official_pct": None,
                "reason": "no FCF/share base available, or hurdle <= terminal growth"}
    perpetuity_multiple = round((1 + tg) / (HURDLE - tg), 4)
    r = ivc_lib.ivc({"price": price, "levered_fcf_per_share": fcf_today, "growth_rate": g,
                     "future_pe": perpetuity_multiple, "hurdle": HURDLE, "discount_rate": HURDLE,
                     "terminal_growth": tg})
    if "error" in r:
        return {"label": label, "intrinsic_value": None, "delta_to_official": None,
                "delta_to_official_pct": None, "reason": r["error"]}
    iv = r["intrinsic_value"]
    delta = None if official_iv is None else round(iv - official_iv, 2)
    delta_pct = (None if not official_iv else round((iv / official_iv - 1) * 100, 2))
    return {"label": label, "method": "gordon_growth_perpetuity_on_fcf_leg",
            "perpetuity_multiple": perpetuity_multiple, "intrinsic_value": iv,
            "implied_cagr_pct": r["implied_cagr_pct"], "delta_to_official": delta,
            "delta_to_official_pct": delta_pct}


def score_pair(ticker, date_iso, gt, price_json):
    """The official score for ONE (ticker, date) pair, strictly per PREREG_2026-08-06, plus the
    parallel EXPLORATORY shadow DCF (decision В4). Returns a dict; status is SCORED or REFUSED —
    never a number in place of a refusal (mandate: 'никаких подстановок').

    `gt` is the archived *_edgar.json record itself — issue #30: that record already IS
    edgar_facts.edgar_facts()'s own output (as-of filtered, series as [{end,val}], roe_median_5y
    already computed — see module docstring's ФОРМАТ АРХИВА), so this reads gt's fields directly
    and never re-invokes edgar_facts() or touches the network. `price_json` is the archived
    *_price.json record — a dict carrying price_record (one Tiingo daily row) and split_factor
    (already computed), not a list of raw daily rows."""
    row = {"ticker": ticker, "date": date_iso}
    if not isinstance(gt, dict):
        row.update(status="REFUSED", reason="edgar archive record is not a JSON object")
        return row
    cik = gt.get("_cik") or gt.get("cik")
    if not cik:
        row.update(status="REFUSED",
                   reason="edgar archive record has no usable '_cik' (or legacy 'cik') field")
        return row
    cik_str = str(cik).zfill(10)
    if gt.get("_errors"):
        row.update(status="REFUSED", reason="edgar_facts errors: %s" % gt["_errors"])
        return row

    if not isinstance(price_json, dict):
        row.update(status="REFUSED",
                   reason="price archive record is not the expected object shape (need a dict "
                          "with 'price_record'/'split_factor', see module docstring)")
        return row
    price_record = price_json.get("price_record")
    if price_record is None:
        arch_errors = price_json.get("_errors") or {}
        reason = arch_errors.get("tiingo_price_on_date_%s" % ticker) or (
            "no trading record for %s on %s in the archive (stand refusal, not "
            "a guess at the nearest day)" % (ticker, date_iso))
        row.update(status="REFUSED", reason=reason)
        return row
    price = price_record.get("adjClose")
    if not isinstance(price, (int, float)) or price <= 0:
        row.update(status="REFUSED", reason="no usable adjClose in the archived price record")
        return row

    eps_af, eps_end, eps_leg_err = compute_eps_leg(gt)
    fcf_af, fcf_end, fcf_leg_err = compute_fcf_leg(gt)
    perrors = {}
    split_factor = price_json.get("split_factor")
    arch_errors = price_json.get("_errors") or {}
    split_factor_reason = arch_errors.get("split_factor_%s" % ticker)
    eps_today, eps_factor = basis_adjust(eps_af, split_factor, split_factor_reason, perrors, ticker + "_eps")
    fcf_today, fcf_factor = basis_adjust(fcf_af, split_factor, split_factor_reason, perrors, ticker + "_fcf")
    # Причина недоступности КАЖДОЙ ноги, published on every SCORED row (None when the leg is
    # usable) -- covers both compute-leg refusals AND a basis_adjust (split-factor) failure that
    # leaves the leg itself computed but unusable. Needed to explain single_leg rows by name,
    # not just by omission (issue #28 audit round 2, item 2).
    eps_reason = (eps_leg_err or perrors.get(ticker + "_eps")) if eps_today is None else None
    fcf_reason = (fcf_leg_err or perrors.get(ticker + "_fcf")) if fcf_today is None else None
    if eps_today is None and fcf_today is None:
        reasons = [r for r in [eps_leg_err, fcf_leg_err] if r] + list(perrors.values())
        row.update(status="REFUSED",
                   reason="no usable base leg: " + "; ".join(reasons) if reasons else
                          "no usable base (EPS/FCF) leg, or share-basis undeterminable")
        return row

    g, rc3, rc5, g_reason = compute_growth_anchor(gt)
    if g is None:
        row.update(status="REFUSED", reason=g_reason)
        return row
    tg = min(TERMINAL_GROWTH_CAP, g)

    pe_hist_median = None
    pe_hist_note = ("not present in the archive record -- treated as absent per PREREG §8 "
                    "(the historical median is a sanity check, not a required input)")
    # issue #30 / PROTOCOL_GAPS: read from the TOP level of price_json (alongside split_factor),
    # never seen in any of the 175 real archive records -- see module docstring.
    if isinstance(price_json.get("pe_hist_median"), (int, float)):
        pe_hist_median = price_json["pe_hist_median"]
        pe_hist_note = None

    grid = {}
    for k_exit in K_EXIT_GRID:
        fpe, meta = official_future_pe(gt.get("roe_median_5y"), tg, k_exit, pe_hist_median)
        if fpe is None:
            grid[k_exit] = {"error": meta["reason"], "meta": meta}
            continue
        leg_results = {}
        for leg_name, base_val in (("gaap_eps", eps_today), ("fcf_per_share", fcf_today)):
            if base_val is None:
                continue
            inp = {"price": price, "growth_rate": g, "future_pe": fpe, "hurdle": HURDLE,
                  "discount_rate": HURDLE, "terminal_growth": tg,
                  "pe_hist_median": pe_hist_median,
                  "mos_targets": [MOS_TARGET_A, MOS_TARGET_B]}
            if leg_name == "gaap_eps":
                inp["eps_normalized"] = base_val
            else:
                inp["levered_fcf_per_share"] = base_val
            leg_results[leg_name] = ivc_lib.ivc(inp)
        grid[k_exit] = {"future_pe": fpe, "meta": meta, "legs": leg_results}

    main = grid.get(K_EXIT_MAIN, {})
    if "error" in main:
        row.update(status="REFUSED", reason="terminal multiplier: " + main["error"], _grid=grid)
        return row
    main_legs = main.get("legs") or {}
    usable = {k: v for k, v in main_legs.items() if "error" not in v}
    if not usable:
        row.update(status="REFUSED",
                   reason="both legs errored at k_exit=9%%: %s" %
                          [v.get("error") for v in main_legs.values()], _grid=grid)
        return row
    if len(usable) == 2:
        conservative = ("gaap_eps" if usable["gaap_eps"]["implied_cagr_pct"] <=
                        usable["fcf_per_share"]["implied_cagr_pct"] else "fcf_per_share")
        leg_note = "dual_basis_conservative"
    else:
        conservative = next(iter(usable))
        leg_note = "single_leg"

    verdict_leg = usable[conservative]
    ladder = {r["mos_target_pct"]: r for r in verdict_leg["mos_ladder"]}
    # decision В4: the shadow bridge is computed BEFORE the official fields are published, so
    # that the two never touch the same assignment — a mutation swapping one for the other is
    # then a single, isolated line (see mutation_probe.py "shadow-swap-01").
    shadow = shadow_fcff_dcf(fcf_today, price, g, tg, verdict_leg["intrinsic_value"])
    row.update(
        status="SCORED", cik=cik_str, verdict_leg=conservative, verdict_leg_note=leg_note,
        eps_basis_end=eps_end, fcf_basis_end=fcf_end,
        split_factor_eps=eps_factor, split_factor_fcf=fcf_factor,
        rev_cagr_3y=rc3, rev_cagr_5y=rc5, growth_rate=g, terminal_growth=tg,
        roe_median_5y=gt.get("roe_median_5y"),
        future_pe_k9=main["future_pe"], future_pe_source=main["meta"]["source"],
        pe_hist_median=pe_hist_median, pe_hist_median_note=pe_hist_note,
        intrinsic_value=verdict_leg["intrinsic_value"],   # OFFICIAL — never the shadow leg
        implied_cagr_pct=verdict_leg["implied_cagr_pct"], hurdle_gate=verdict_leg["hurdle_gate"],
        buy_A_no_discount=ladder.get(0.0, {}).get("reached"),
        buy_B_10pct_discount=ladder.get(10.0, {}).get("reached"),
        sensitivity={str(k): grid[k].get("future_pe") for k in K_EXIT_GRID},
        eps_reason=eps_reason, fcf_reason=fcf_reason,
        _grid=grid, _gt_flags=gt.get("_flags"), shadow_dcf=shadow,
    )
    return row


def load_pair(zf, edgar_name, price_name):
    with zf.open(edgar_name) as f:
        gt = json.load(f)
    with zf.open(price_name) as f:
        price_json = json.load(f)
    return gt, price_json


def run_archive(archive_path):
    if not os.path.exists(archive_path):
        return None, ("archive not found: %s -- per the mandate, stop rather than fabricate "
                      "a run" % archive_path)
    rows = []
    with zipfile.ZipFile(archive_path) as zf:
        pairs, incomplete = discover_pairs(zf.namelist())
        for meta in incomplete:
            rows.append({"ticker": meta["ticker"], "date": meta["date"], "status": "REFUSED",
                        "reason": meta["reason"]})
        for ticker, ymd, edgar_name, price_name in pairs:
            date_iso = _fmt_date(ymd)
            try:
                gt, price_json = load_pair(zf, edgar_name, price_name)
                row = score_pair(ticker, date_iso, gt, price_json)
            except Exception as e:
                row = {"ticker": ticker, "date": date_iso, "status": "REFUSED",
                      "reason": "unhandled exception while scoring: %s: %s" %
                                (type(e).__name__, str(e)[:200])}
            rows.append(row)
    return rows, None


CSV_FIELDS = ["ticker", "date", "status", "reason", "cik", "verdict_leg", "verdict_leg_note",
              "eps_basis_end", "fcf_basis_end", "eps_reason", "fcf_reason",
              "growth_rate", "rev_cagr_3y", "rev_cagr_5y", "terminal_growth", "roe_median_5y",
              "future_pe_k9", "future_pe_source", "sensitivity_pe_k8", "sensitivity_pe_k10",
              "pe_hist_median", "pe_hist_median_note", "intrinsic_value",
              "implied_cagr_pct", "hurdle_gate", "buy_A_no_discount", "buy_B_10pct_discount",
              "split_factor_eps", "split_factor_fcf", "shadow_dcf_iv", "shadow_dcf_delta",
              "shadow_dcf_delta_pct"]

# Compound fields deliberately excluded from CSV_FIELDS verbatim: each is flattened into other
# named CSV_FIELDS columns by write_csv() below and read directly (unflattened) by write_report().
# This is the ONLY escape hatch TestEveryRowKeyIsPublished (tests/test_historical_run.py) allows --
# issue #28 audit round 3, item 3: any score_pair() key that ends up neither directly in
# CSV_FIELDS nor listed here fails that test by construction, closing the class of bug audit
# rounds 1-2 each found one field at a time (pe_hist_median_note, then eps_reason/fcf_reason).
CSV_COMPOUND_FIELDS = {"sensitivity", "shadow_dcf"}


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            flat = dict(r)
            sens = r.get("sensitivity") or {}
            flat["sensitivity_pe_k8"] = sens.get(str(K_EXIT_GRID[0]))
            flat["sensitivity_pe_k10"] = sens.get(str(K_EXIT_GRID[-1]))
            sd = r.get("shadow_dcf") or {}
            flat["shadow_dcf_iv"] = sd.get("intrinsic_value")
            flat["shadow_dcf_delta"] = sd.get("delta_to_official")
            flat["shadow_dcf_delta_pct"] = sd.get("delta_to_official_pct")
            w.writerow(flat)


# PREREG §4 — quoted verbatim next to the measured number in the report (mandate: "каждый
# критерий процитирован и рядом измеренное число").
CRITERIA_TEXT = {
    1: "Критерий 1 — чувствительность: на каждой из трёх донных дат вердикт «покупать» "
       "(вариант А) получают не менее 20% имён, доступных к оценке на ту дату.",
    2: "Критерий 2 — избирательность: на каждой из двух контрольных дат вердикт «покупать» "
       "получают не более 2 имён из 34.",
    3: "Критерий 3 — различающая способность: имена, помеченные покупкой 23 марта 2020, за "
       "последующие пять лет показывают более высокую медианную полную доходность, чем имена, "
       "помеченные отказом на ту же дату.",
    4: "Критерий 4 — исправность стенда: тикер со сплитом после проверяемой даты воспроизводит "
       "P/E, посчитанный вручную, с расхождением не более 1%.",
}

POSITIVE_CONTROL_DATES = {"2018-12-24", "2020-03-23", "2022-10-12"}
NEGATIVE_CONTROL_DATES = {"2021-12-31", "2019-07-01"}


def _pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def evaluate_criteria(rows):
    scored = [r for r in rows if r.get("status") == "SCORED"]
    out = {}
    by_date = {}
    for r in scored:
        by_date.setdefault(r["date"], []).append(r)

    c1 = {}
    for d in sorted(POSITIVE_CONTROL_DATES):
        names = by_date.get(d, [])
        buys = [r for r in names if r.get("buy_A_no_discount")]
        c1[d] = {"available": len(names), "buys": len(buys), "pct": _pct(len(buys), len(names)),
                 "pass": (_pct(len(buys), len(names)) or 0) >= 20.0 if names else None}
    out[1] = c1

    c2 = {}
    for d in sorted(NEGATIVE_CONTROL_DATES):
        names = by_date.get(d, [])
        buys = [r for r in names if r.get("buy_A_no_discount")]
        c2[d] = {"available": len(names), "buys": len(buys),
                 "pass": len(buys) <= 2 if names else None}
    out[2] = c2

    out[3] = {"note": "требует форвардной доходности за 5 лет (до 2025-03-23) — вне данных "
                      "этого прогона; не вычисляется здесь."}
    out[4] = {"note": "проверяется отдельными пинами теста на архивных парах со сплитом, "
                      "см. tests/test_historical_run.py; агрегат по прогону не публикуется "
                      "здесь без реального архива."}
    return out


def write_report(rows, path):
    scored = [r for r in rows if r.get("status") == "SCORED"]
    refused = [r for r in rows if r.get("status") == "REFUSED"]
    total = len(rows)
    crit = evaluate_criteria(rows)

    lines = []
    lines.append("# RESULTS — Счёт проверки №1 (историческая проверка методики)")
    lines.append("")
    lines.append("Источник методики: `mailbox/PREREG_2026-08-06_HISTORICAL_VALIDATION.md` "
                 "(заморожена). Решение об исполнении при STOP BUILD: "
                 "`mailbox/DECISION_2026-08-09_ARBITRATION.md` (В1, В4).")
    lines.append("")
    lines.append("Пар обработано: **%d**. Посчитано: **%d**. Отказано: **%d** (%s%%)." %
                 (total, len(scored), len(refused), _pct(len(refused), total) if total else "n/a"))
    lines.append("")
    lines.append("## Критерии (PREREG §4), число рядом с формулировкой")
    lines.append("")
    for i in (1, 2, 3, 4):
        lines.append("### " + CRITERIA_TEXT[i])
        c = crit[i]
        if i in (1, 2):
            for d, m in c.items():
                if i == 1:
                    lines.append("- %s: %d/%d доступных (%s%%) -> %s" %
                                 (d, m["buys"], m["available"], m["pct"],
                                  ("PASS" if m["pass"] else "FAIL" if m["pass"] is False else "n/a — данных нет")))
                else:
                    lines.append("- %s: %d/%d покупок -> %s" %
                                 (d, m["buys"], m["available"],
                                  ("PASS" if m["pass"] else "FAIL" if m["pass"] is False else "n/a — данных нет")))
        else:
            lines.append("- " + c["note"])
        lines.append("")
    if len(rows) and _pct(len(refused), total) and _pct(len(refused), total) > 33.3:
        lines.append("**ВНИМАНИЕ:** доля отказов превышает треть универсума — по правилу §8 "
                     "проверка считается несостоявшейся по недостатку данных, а не пройденной "
                     "или проваленной.")
        lines.append("")

    lines.append("## Отказы поимённо")
    lines.append("")
    if refused:
        lines.append("| Тикер | Дата | Причина |")
        lines.append("|---|---|---|")
        for r in refused:
            lines.append("| %s | %s | %s |" % (r["ticker"], r["date"],
                                                (r.get("reason") or "").replace("|", "/")))
    else:
        lines.append("(нет)")
    lines.append("")

    lines.append("## Посчитанные пары")
    lines.append("")
    if scored:
        lines.append("| Тикер | Дата | Leg | Leg note | EPS basis FY | FCF basis FY | g | "
                     "terminal_g | future_pe(8%) | future_pe(9%) | "
                     "future_pe(10%) | IV | implied_CAGR% | A | Б | Shadow IV (EXPLORATORY) | "
                     "Δ vs official | PE-hist медиана (примечание) | "
                     "Причина недоступности второй ноги |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in scored:
            sd = r.get("shadow_dcf") or {}
            sens = r.get("sensitivity") or {}
            sens_k8 = sens.get(str(K_EXIT_GRID[0]))
            sens_k10 = sens.get(str(K_EXIT_GRID[-1]))
            # never blank: absence of the historical median always carries a reason (see
            # score_pair's pe_hist_median_note); presence is marked "-", not left empty (issue
            # #28 audit round 2, item 1).
            pe_note_cell = (r.get("pe_hist_median_note") or "-").replace("|", "/")
            # populated only for single_leg rows -- the one leg that's None on a dual_basis row
            # carries no reason, so this is "-" there by construction (item 2).
            leg_reason_cell = (r.get("eps_reason") or r.get("fcf_reason") or "-").replace("|", "/")
            # issue #28 audit round 3, item 2: verdict_leg_note/eps_basis_end/fcf_basis_end were
            # already computed and published in the CSV but never reached this table.
            eps_end_cell = r.get("eps_basis_end") or "n/a"
            fcf_end_cell = r.get("fcf_basis_end") or "n/a"
            lines.append("| %s | %s | %s | %s | %s | %s | %.4f | %.4f | %s | %.2f | %s | %.2f | %.2f | %s | %s | %s | %s | %s | %s |" % (
                r["ticker"], r["date"], r["verdict_leg"], r["verdict_leg_note"],
                eps_end_cell, fcf_end_cell, r["growth_rate"], r["terminal_growth"],
                ("%.2f" % sens_k8) if sens_k8 is not None else "n/a",
                r["future_pe_k9"],
                ("%.2f" % sens_k10) if sens_k10 is not None else "n/a",
                r["intrinsic_value"], r["implied_cagr_pct"],
                "BUY" if r["buy_A_no_discount"] else "-",
                "BUY" if r["buy_B_10pct_discount"] else "-",
                ("%.2f" % sd["intrinsic_value"]) if sd.get("intrinsic_value") is not None else "n/a",
                ("%.2f" % sd["delta_to_official"]) if sd.get("delta_to_official") is not None else "n/a",
                pe_note_cell, leg_reason_cell))
    else:
        lines.append("(нет — архив недоступен или отказал каждой паре)")
    lines.append("")

    lines.append("## Документированные пробелы протокола (PREREG молчит или двусмыслен)")
    lines.append("")
    for g in PROTOCOL_GAPS:
        lines.append("- " + g)
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main(argv=None):
    default_archive = os.path.normpath(os.path.join(
        _REPO, "..", "Reports", "histrun_2026-08-08", "histrun_raw_v3.zip"))
    default_outdir = os.path.normpath(os.path.join(
        _REPO, "..", "Reports", "histrun_2026-08-08"))
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--archive", default=default_archive,
                  help="path to histrun_raw_v3.zip (v3 only — v2 has 6 stale-code files)")
    p.add_argument("--outdir", default=default_outdir,
                  help="directory for RESULTS_test1.md / RESULTS_test1.csv")
    args = p.parse_args(argv)

    rows, err = run_archive(args.archive)
    if err:
        print(err, file=sys.stderr)
        return 1
    os.makedirs(args.outdir, exist_ok=True)
    write_csv(rows, os.path.join(args.outdir, "RESULTS_test1.csv"))
    write_report(rows, os.path.join(args.outdir, "RESULTS_test1.md"))
    scored = len([r for r in rows if r["status"] == "SCORED"])
    refused = len([r for r in rows if r["status"] == "REFUSED"])
    print("scored=%d refused=%d total=%d -- wrote %s" %
         (scored, refused, len(rows), args.outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
