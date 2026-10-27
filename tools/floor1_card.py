#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Карточка этажа 1 (задача К1, issues #44 / #90): один прогон по config/watchlist.csv.

Выход: Reports/floor1/FLOOR1_<YYYY-MM-DD>.md + .csv (дата = дата запуска, as_of SEC = она же).
Вход: SEC — ТОЛЬКО через адаптер К2 (CONSILIUM_REPO_v4_2_<новейший>/microservice/edgar_adapter.py,
User-Agent из env SEC_USER_AGENT), цены — Tiingo (env TIINGO_TOKEN).

Главный инвариант: missing != zero != default. Каждое поле — либо {"value", "basis", ...}, либо
именованный отказ {"refused": КОД, "reason": причина}. Подстановок нет: нет данных — нет числа.
Провенанс (accession SEC, дата последней цены Tiingo) едет вместе с числом.

Определения (всё считается здесь, из рядов адаптера, и подписано basis'ом в самой карточке):
  * FCF = OCF - capex (capex = только PaymentsToAcquirePropertyPlantAndEquipment/ProductiveAssets);
    нет capex -> отказ, а не FCF=OCF.
  * EPS = NI / средневзвешенное РАЗВОДНЁННОЕ число акций (вычислено, это НЕ отчётный EPS).
  * чистый долг = долг по ФГ (LongTermDebt, а где его нет на дате — Noncurrent+Current при наличии обоих; без
    краткосрочных займов и аренды) - CashAndCashEquivalents (без ценных бумаг). Тега долга нет -> отказ.
  * RS = доходность тикера минус доходность бенчмарка за окно (п.п.), Tiingo adjClose;
    4н = 28 календарных дней, 13н = 91; просадка от max adjClose за 364 дня.
  * ускорение выручки = YoY(последний ФГ) - YoY(предыдущий ФГ) — НЕ разность перекрывающихся CAGR.
Флаги (CYCLE_PEAK, CASH_CONV_DIVERGENCE, BUYBACK_EPS, DEBT_FOR_BUYBACKS) — без числовых порогов:
сравнения знака/экстремума, каждый с именованной уликой; нет входа -> UNDETERMINED с причиной.
Пороги в #44 не заданы; правила ниже — предложение исполнителя, подлежат подтверждению архитектора.

Запуск: python3 tools/floor1_card.py [--as-of YYYY-MM-DD] [--tickers A,B] [--out-dir DIR]
Код выхода: 0 — карточка записана (пробелы названы в ней); 2 — нет env/watchlist, карточка НЕ записана.
"""
import argparse, csv, datetime as dt, glob, json, os, re, statistics, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST = os.path.join(ROOT, "config", "watchlist.csv")
OUT_DIR = os.path.join(ROOT, "Reports", "floor1")
BENCH_RS = ("VOO", "QQQ")
RS_WINDOWS = (("4w", 28), ("13w", 91))
YEAR_TOL = 21            # дней: ФГ на 52/53 недели дрейфует относительно календаря
PRICE_FRESH_DAYS = 5     # последний close старше — цена не «на дату запуска»
PRICE_FETCH_DAYS = 400
COVERAGE_TARGET = 0.95


def refusal(code, reason):
    return {"refused": code, "reason": reason}


def ok(value, unit, basis, prov=None, **extra):
    d = {"value": value, "unit": unit, "basis": basis, "prov": prov or []}
    d.update(extra)
    return d


def is_ok(f):
    return isinstance(f, dict) and "value" in f


def micro_dir():
    """Новейшее дерево CONSILIUM_REPO_v4_2_<N>/microservice (по числу N, не по алфавиту)."""
    best = None
    for p in glob.glob(os.path.join(ROOT, "CONSILIUM_REPO_v4_2_*")):
        m = re.search(r"_v4_2_(\d+)$", p)
        if m and os.path.isdir(os.path.join(p, "microservice")) and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), os.path.join(p, "microservice"))
    return best[1] if best else None


def load_sec_modules():
    md = micro_dir()
    if md is None:
        raise RuntimeError("no CONSILIUM_REPO_v4_2_*/microservice tree found")
    if md not in sys.path:
        sys.path.insert(0, md)
    import edgar_facts as ef
    import edgar_adapter as ad
    return ef, ad


# ----------------------------------------------------------------------------- series helpers

def _d(s):
    return dt.date.fromisoformat(s)


def at_offset(series, n):
    """Точка ряда ровно n ФГ раньше последней (по датам, с допуском YEAR_TOL), иначе None.
    series: oldest-first [{end,val,...}]."""
    if not series:
        return None
    last = _d(series[-1]["end"])
    for r in series:
        if abs((last - _d(r["end"])).days - 365.25 * n) <= YEAR_TOL:
            return r
    return None


def align(num, den):
    """Ряд отношений на общих датах: [{end, val, accn:[a,b]}] oldest-first; den==0 пропускается как отказ."""
    dm = {r["end"]: r for r in (den or [])}
    out = []
    for r in num or []:
        d = dm.get(r["end"])
        if d and d["val"]:
            out.append({"end": r["end"], "val": r["val"] / d["val"], "accn": accns(r, d)})
    return out


def accns(*pts):
    out = []
    for p in pts:
        a = p.get("accn")
        for x in (a if isinstance(a, list) else [a]):
            if x and x not in out:
                out.append(x)
    return out


def _need(series, name):
    if not series:
        return refusal("MISSING_INPUT", "%s: нет годового ряда в SEC-данных" % name)
    return None


def current(series, fy, name):
    """(series, None) если ряд кончается на ФГ карточки; (None, отказ) если ряда нет или он устарел.
    Устаревший ряд — не «последнее известное», а отказ: MU LongTermDebt оборвался в 2012."""
    if not series:
        return None, refusal("MISSING_INPUT", "%s: нет годового ряда в SEC-данных" % name)
    if series[-1]["end"] != fy:
        return None, refusal("STALE_SERIES", "%s: последняя точка %s, ФГ карточки %s (тег перестали заполнять или "
                             "поменяли)" % (name, series[-1]["end"], fy))
    return series, None


# ----------------------------------------------------------------------------- SEC-derived fields

def cagr(series, n, name):
    bad = _need(series, name)
    if bad:
        return bad
    a, b = at_offset(series, n), series[-1]
    if a is None:
        return refusal("INSUFFICIENT_HISTORY", "%s: нет точки за %d ФГ до %s" % (name, n, b["end"]))
    if a["val"] <= 0 or b["val"] <= 0:
        return refusal("CAGR_UNDEFINED", "%s: неположительная граница (%s=%s, %s=%s)" % (
            name, a["end"], a["val"], b["end"], b["val"]))
    return ok((b["val"] / a["val"]) ** (1.0 / n) - 1, "ratio", "CAGR %dл ФГ %s..%s" % (n, a["end"], b["end"]),
              accns(a, b))


def rev_accel(series):
    bad = _need(series, "revenue")
    if bad:
        return bad
    p0, p1, p2 = series[-1], at_offset(series, 1), at_offset(series, 2)
    if p1 is None or p2 is None:
        return refusal("INSUFFICIENT_HISTORY", "revenue: нужны три подряд идущих ФГ до %s" % p0["end"])
    if p1["val"] <= 0 or p2["val"] <= 0:
        return refusal("GROWTH_UNDEFINED", "revenue: неположительная база")
    g0, g1 = p0["val"] / p1["val"] - 1, p1["val"] / p2["val"] - 1
    return ok(g0 - g1, "ratio", "YoY(%s) - YoY(%s) = %.4f - %.4f" % (p0["end"], p1["end"], g0, g1),
              accns(p0, p1, p2))


def margin_pair(num, rev, name, fy):
    """-> (latest_field, median5_field) для маржи num/rev."""
    num, r = current(num, fy, "числитель " + name)
    if r:
        return r, r
    ms = align(num, rev)
    if not ms:
        r = refusal("MISSING_INPUT", "%s: нет совпадающих по датам рядов числителя и выручки" % name)
        return r, r
    last = ms[-1]
    latest = ok(last["val"], "ratio", "%s ФГ %s" % (name, last["end"]), accns(last))
    pts = [last] + [at_offset(ms, k) for k in range(1, 5)]
    if any(p is None for p in pts):
        return latest, refusal("INSUFFICIENT_HISTORY", "%s: нет 5 ФГ подряд до %s" % (name, last["end"]))
    return latest, ok(statistics.median(p["val"] for p in pts), "ratio",
                      "медиана %s за 5 ФГ до %s включительно" % (name, last["end"]), accns(*pts))


def fcf_series(ocf, capex):
    cm = {r["end"]: r for r in (capex or [])}
    return [{"end": r["end"], "val": r["val"] - cm[r["end"]]["val"],
             "accn": [r.get("accn"), cm[r["end"]].get("accn")]} for r in (ocf or []) if r["end"] in cm]


def eps_series(ni, shares):
    sm = {r["end"]: r for r in (shares or [])}
    return [{"end": r["end"], "val": r["val"] / sm[r["end"]]["val"], "accn": [r.get("accn"), sm[r["end"]].get("accn")]}
            for r in (ni or []) if r["end"] in sm and sm[r["end"]]["val"]]


def split_events(splits):
    """Подтверждённые сплиты адаптера (_flags.confirmed_splits) -> события [{factor, pre, post, ends}].
    Одно событие = несколько дат ФГ, пересчитанных одним сплитом (одинаковый factor, пересекающиеся окна). Сплит
    произошёл ПОСЛЕ подачи старого значения и НЕ ПОЗЖЕ подачи нового: дата сплита в (pre, post], где
    pre = max(earliest_filed), post = min(latest_filed). Запись без factor/filed события не даёт -> (None, плохие)."""
    good, bad = [], []
    for sp in splits or []:
        if sp.get("factor") and sp.get("earliest_filed") and sp.get("latest_filed") and sp["factor"] > 0:
            good.append(sp)
        else:
            bad.append(sp.get("end", "?"))
    events = []
    for sp in sorted(good, key=lambda x: (x["earliest_filed"], x["end"])):
        ev = events[-1] if events else None
        if ev and ev["factor"] == sp["factor"] and sp["earliest_filed"] < ev["post"] and ev["pre"] < sp["latest_filed"]:
            ev["pre"], ev["post"] = max(ev["pre"], sp["earliest_filed"]), min(ev["post"], sp["latest_filed"])
            ev["ends"].append(sp["end"])
        else:
            events.append({"factor": sp["factor"], "pre": sp["earliest_filed"], "post": sp["latest_filed"],
                           "ends": [sp["end"]]})
    return events, bad


def split_adjust_point(row, events):
    """-> (val_на_пост-сплитовой_базе, [применённые factor], None) или (None, [], причина). Базу строки определяет дата
    подачи её accession: filed <= pre -> значение до сплита (умножаем на factor); filed >= post -> уже после; между
    или нет filed -> база недоказуема (отказ, не угадывание)."""
    val, applied = row["val"], []
    for ev in events:
        f = row.get("filed")
        if not f:
            return None, [], "у строки %s нет даты подачи (filed): база до/после сплита недоказуема" % row["end"]
        if f <= ev["pre"]:
            val, applied = val * ev["factor"], applied + [ev["factor"]]
        elif f < ev["post"]:
            return None, [], ("строка %s подана %s внутри окна неопределённости сплита (%s, %s]: база недоказуема"
                              % (row["end"], f, ev["pre"], ev["post"]))
    return val, applied, None


def split_adjust_series(rows, splits):
    """Ряд акций на сопоставимой (пост-сплитовой) базе. Подтверждённый сплит -> пересчёт с пометкой split_adjusted и
    коэффициентом; строки с недоказуемой базой выбрасываются (и возвращаются в bad_ends), не угадываются."""
    events, bad_sp = split_events(splits)
    if not events or not rows:
        return list(rows or []), [], bad_sp
    out, bad_ends = [], []
    for r in rows:
        v, applied, why = split_adjust_point(r, events)
        if why:
            bad_ends.append(r["end"])
        elif applied:
            out.append(dict(r, val=v, orig_val=r["val"], split_adjusted=True, split_factors=applied))
        else:
            out.append(r)
    return out, bad_ends, bad_sp


def share_change(shares, n, splits, shares_refusal):
    if shares_refusal:
        return shares_refusal
    if not shares:
        return refusal("MISSING_INPUT", "shares_diluted: нет годового ряда")
    a, b = at_offset(shares, n), shares[-1]
    if a is None:
        return refusal("INSUFFICIENT_HISTORY", "shares_diluted: нет точки за %d ФГ до %s" % (n, b["end"]))
    hit = [s["end"] for s in splits if a["end"] < s.get("end", "") <= b["end"]]
    adj_note, factors = "", []
    if hit:
        events, bad_sp = split_events(splits)
        if bad_sp or not events:
            return refusal("SPLIT_IN_WINDOW", "подтверждённый сплит %s внутри окна %s..%s, но у записи нет factor/дат "
                           "подачи: пересчёт на сопоставимую базу невозможен, числа акций несопоставимы"
                           % (",".join(hit), a["end"], b["end"]))
        pts = []
        for r in (a, b):
            v, ap, why = split_adjust_point(r, events)
            if why:
                return refusal("SPLIT_IN_WINDOW", "подтверждённый сплит %s внутри окна %s..%s; %s"
                               % (",".join(hit), a["end"], b["end"], why))
            pts.append((v, ap))
        (a_val, a_ap), (b_val, b_ap) = pts
        factors = sorted(set(a_ap + b_ap))
        a, b = dict(a, val=a_val), dict(b, val=b_val)
        adj_note = " [split_adjusted: пересчёт на пост-сплитовую базу, коэффициенты %s]" % ",".join("%g" % f for f in factors)
    if not a["val"]:
        return refusal("SHARES_UNDEFINED", "shares_diluted: нулевая база на %s" % a["end"])
    extra = {"split_adjusted": True, "split_factors": factors} if factors else {}
    return ok(b["val"] / a["val"] - 1, "ratio", "средневзв. разводнённые акции %s vs %s%s" % (b["end"], a["end"], adj_note),
              accns(a, b), **extra)


# Цепочки альтернативных us-gaap тегов (K1.1 ч.1). Эмитент мог перестать заполнять один тег и перейти на другой
# (MU: LongTermDebt оборвался в FY2012, дальше DebtAndCapitalLeaseObligations). Точка берётся из ПЕРВОГО тега цепочки,
# у которого есть эта дата; какой тег дал число -- в provenance (tags). Теги с разным смыслом (LongTermDebt vs
# DebtAndCapitalLeaseObligations -- со своими арендами) в одном расчёте изменения помечаются mixed_tags.
DEBT_FULL_CHAIN = ["LongTermDebt", "DebtAndCapitalLeaseObligations"]
DEBT_NONC_CHAIN = ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"]
DEBT_CUR_CHAIN = ["LongTermDebtCurrent", "DebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"]
CASH_CHAIN = ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]
COST_TAGS = ["CostOfRevenue", "CostOfGoodsAndServicesSold"]


def _by_end(facts, ef, chain):
    """{end: row-with-tag}: для каждой даты строка из первого тега цепочки, у которого она есть."""
    out = {}
    for tag in chain:
        rows, _ = ef._annual_instant_series(facts, [tag])
        for r in rows:
            out.setdefault(r["end"], r)
    return out


def net_debt_series(facts, ef):
    """-> (series, refusal). Долг на дате ФГ: полный долг (цепочка DEBT_FULL_CHAIN), а если его на этой дате нет --
    нетекущая + текущая часть (цепочки), но только когда ОБА слагаемых есть на этой дате (нет текущей части в данных
    != текущая часть ноль). Минус деньги (CASH_CHAIN) на той же дате. Точка несёт tags -- теги, давшие число."""
    full, nonc, cur = (_by_end(facts, ef, c) for c in (DEBT_FULL_CHAIN, DEBT_NONC_CHAIN, DEBT_CUR_CHAIN))
    if not full and not nonc:
        return None, refusal("DEBT_TAG_ABSENT", "нет ни одного тега долга из цепочек %s / %s: «долга нет» и "
                             "«тег не заполнен» неотличимы, ноль не подставляется"
                             % (",".join(DEBT_FULL_CHAIN), ",".join(DEBT_NONC_CHAIN)))
    cm = _by_end(facts, ef, CASH_CHAIN)
    out = []
    for end in sorted(set(full) | set(nonc)):
        if end not in cm:
            continue
        if end in full:
            debt, parts = full[end]["val"], [full[end]]
        elif end in nonc and end in cur:
            debt, parts = nonc[end]["val"] + cur[end]["val"], [nonc[end], cur[end]]
        else:
            continue
        out.append({"end": end, "val": debt - cm[end]["val"], "accn": [r.get("accn") for r in parts + [cm[end]]],
                    "tags": [r["tag"] for r in parts + [cm[end]]]})
    if not out:
        return None, refusal("MISSING_INPUT", "нет ни одной даты, где есть и полный долг, и денежные средства")
    return out, None


def tag_note(*pts):
    """-> (tags, mixed): все теги точек (без повторов) и признак «точки собраны из разных наборов тегов»."""
    sets = [tuple(p.get("tags") or ()) for p in pts]
    tags = []
    for t in sets:
        for x in t:
            if x not in tags:
                tags.append(x)
    return tags, len(set(sets)) > 1


def gross_profit_derived(facts, ef):
    """-> (gp_series, rev_series, refusal). Валовая прибыль = выручка - себестоимость из ОДНОГО отчёта: точка есть
    только там, где accession выручки и себестоимости совпадают (иначе это склейка двух отчётов). Нет второго
    слагаемого -- отказ MISSING_INPUT, не ноль и не «выручка = прибыль»."""
    rev, _, _, _ = ef._annual_merged(facts, ef.DURATION_TAGS["revenue"], drop_zero=True)
    cost, _, _, _ = ef._annual_merged(facts, COST_TAGS)
    if not rev or not cost:
        return None, None, refusal("MISSING_INPUT", "gross profit: нет GrossProfit и нет %s (нет %s) -- вывести "
                                   "не из чего, ноль не подставляется"
                                   % ("выручки" if not rev else "себестоимости", "/".join(COST_TAGS)))
    cm = {r["end"]: r for r in cost}
    gp, rv = [], []
    for r in rev:
        c = cm.get(r["end"])
        if c and c.get("accn") and c["accn"] == r.get("accn"):
            gp.append({"end": r["end"], "val": r["val"] - c["val"], "accn": [r["accn"], c["accn"]],
                       "tags": [r["tag"], c["tag"]]})
            rv.append(dict(r, accn=[r["accn"]], tags=[r["tag"]]))
    if not gp:
        return None, None, refusal("MISSING_INPUT", "gross profit: выручка и себестоимость не совпадают ни по одной "
                                   "дате в одном accession (разные отчёты не склеиваются)")
    return gp, rv, None


def sec_fields(out, facts, ef):
    """Все SEC-поля одного имени + сырые ряды для флагов. out — выход адаптера."""
    F, raw = {}, {}
    rev, ni = out.get("revenue_audit") or out.get("revenue"), out.get("net_income_audit") or out.get("net_income")
    ocf, capex = out.get("ocf_audit") or out.get("ocf"), out.get("capex_audit") or out.get("capex")
    opi, gp = out.get("operating_income_audit") or out.get("operating_income"), out.get("gross_profit_audit") or out.get("gross_profit")
    fy = next((x[-1]["end"] for x in (rev, ni, ocf) if x), None)   # ФГ карточки: выручка, иначе NI, иначе OCF
    ni, ni_ref = current(ni, fy, "net_income")
    sh_rows = out.get("shares_diluted_audit") or out.get("shares_diluted")
    fsrc = (out.get("_field_sources") or {}).get("shares_diluted")
    if sh_rows and isinstance(fsrc, str) and fsrc.startswith("filing_xbrl:"):
        sh_rows = [dict(r, accn=r.get("accn") or fsrc.split(":", 1)[1]) for r in sh_rows]   # filing-level путь К2
    shares, sh_ref = current(sh_rows, fy, "shares_diluted")
    sh_ref = (out.get("_refusals") or {}).get("shares_diluted") or sh_ref
    ocf_c, ocf_ref = current(ocf, fy, "ocf")
    capex_c, capex_ref = current(capex, fy, "capex")
    splits = (out.get("_flags") or {}).get("confirmed_splits") or []

    F["rev_cagr_3y"] = cagr(rev, 3, "revenue")
    F["rev_cagr_5y"] = cagr(rev, 5, "revenue")
    F["rev_accel"] = rev_accel(rev)
    for key, num, nm in (("gm", gp, "gross margin"), ("om", opi, "operating margin"), ("nm", ni, "net margin")):
        F[key + "_latest"], F[key + "_med5"] = margin_pair(num, rev, nm, fy)
    if not is_ok(F["gm_latest"]):        # нет GrossProfit (или ряд устарел): Revenue - CostOfRevenue из одного отчёта
        gp_d, rev_d, gp_ref = gross_profit_derived(facts, ef)
        if gp_d:
            F["gm_latest"], F["gm_med5"] = margin_pair(gp_d, rev_d, "gross margin (выручка - себестоимость)", fy)
            for k in ("gm_latest", "gm_med5"):
                if is_ok(F[k]):
                    F[k]["derived"] = True
                    F[k]["tags"] = tag_note(gp_d[-1])[0]
        elif F["gm_latest"].get("refused") == "MISSING_INPUT":
            F["gm_latest"] = F["gm_med5"] = refusal("MISSING_INPUT", F["gm_latest"]["reason"] + "; " + gp_ref["reason"])
    raw["om"] = align(opi, rev)

    F["ni_latest"] = (ok(ni[-1]["val"], "USD", "NetIncomeLoss ФГ %s" % ni[-1]["end"], accns(ni[-1]))
                      if ni else ni_ref)
    fcf = fcf_series(ocf_c, capex_c)
    raw["fcf"], raw["ni"] = fcf, ni
    if fcf:
        F["fcf_latest"] = ok(fcf[-1]["val"], "USD", "OCF - capex(PP&E) ФГ %s" % fcf[-1]["end"], accns(fcf[-1]))
    else:
        F["fcf_latest"] = ocf_ref or capex_ref or refusal(
            "MISSING_INPUT", "fcf: нет пересечения рядов OCF и capex (OCF без capex не подставляется)")
    if is_ok(F["fcf_latest"]) and ni and ni[-1]["end"] == fcf[-1]["end"]:
        if ni[-1]["val"] > 0:
            F["fcf_to_ni"] = ok(fcf[-1]["val"] / ni[-1]["val"], "ratio", "FCF/NI ФГ %s" % ni[-1]["end"],
                                accns(ni[-1], fcf[-1]))
        else:
            F["fcf_to_ni"] = refusal("RATIO_UNDEFINED", "FCF/NI: NI <= 0 (%s)" % ni[-1]["val"])
    else:
        F["fcf_to_ni"] = F["fcf_latest"] if not is_ok(F["fcf_latest"]) else refusal(
            "FY_MISMATCH", "последние ФГ NI и FCF не совпадают")
    sh_adj, _, _ = split_adjust_series(shares, splits) if shares else (shares, [], [])
    eps = [] if sh_ref or not sh_adj else eps_series(ni, sh_adj)     # EPS на сопоставимой базе акций
    if shares and sh_adj and sh_adj[-1]["end"] != shares[-1]["end"]:
        eps, sh_ref = [], refusal("SPLIT_IN_WINDOW", "shares_diluted: база акций последнего ФГ %s недоказуема относительно "
                                  "подтверждённого сплита (дата подачи внутри окна неопределённости)" % shares[-1]["end"])
    raw["eps"], raw["shares"] = eps, sh_adj
    if eps:
        F["eps_latest"] = ok(eps[-1]["val"], "USD/sh", "вычислено: NI / средневзв. разводнённые акции, ФГ %s "
                             "(НЕ отчётный EPS)" % eps[-1]["end"], accns(eps[-1]))
    else:
        F["eps_latest"] = sh_ref or ni_ref or refusal("MISSING_INPUT", "eps: нет пересечения NI и акций")

    F["shares_chg_1y"] = share_change(shares, 1, splits, sh_ref)
    F["shares_chg_3y"] = share_change(shares, 3, splits, sh_ref)

    nd, nd_ref = net_debt_series(facts, ef)
    if nd:
        nd, nd_ref = current(nd, fy, "net debt (LongTermDebt - Cash)")
    raw["nd"] = nd
    if nd_ref:
        F["net_debt_latest"] = F["net_debt_chg_3y"] = nd_ref
    else:
        tags, _ = tag_note(nd[-1])
        F["net_debt_latest"] = ok(nd[-1]["val"], "USD", "долг - Cash ФГ %s; теги: %s" % (nd[-1]["end"], ",".join(tags)),
                                  accns(nd[-1]), tags=tags)
        a = at_offset(nd, 3)
        if a:
            tags, mixed = tag_note(a, nd[-1])
            F["net_debt_chg_3y"] = ok(nd[-1]["val"] - a["val"], "USD", "net debt %s минус %s; теги: %s%s" % (
                nd[-1]["end"], a["end"], ",".join(tags),
                " [РАЗНЫЕ ТЕГИ на концах окна: определения долга могут отличаться]" if mixed else ""),
                accns(a, nd[-1]), tags=tags, mixed_tags=mixed)
        else:
            F["net_debt_chg_3y"] = refusal("INSUFFICIENT_HISTORY", "net debt: нет точки за 3 ФГ до %s" % nd[-1]["end"])
    return F, raw


# ----------------------------------------------------------------------------- flags

def _und(code, reason):
    return {"state": "UNDETERMINED", "evidence": "%s: %s" % (code, reason)}


def _need_fields(F, names):
    for n in names:
        if not is_ok(F.get(n)):
            r = F.get(n) or {}
            return "%s отказано (%s)" % (n, r.get("refused", "нет поля"))
    return None


def flag_cycle_peak(raw):
    ms = raw.get("om") or []
    pts = [ms[-1]] + [at_offset(ms, k) for k in range(1, 5)] if ms else []
    if len(pts) < 5 or any(p is None for p in pts):
        return _und("INSUFFICIENT_HISTORY", "операционная маржа: нет 5 ФГ подряд")
    med, last = statistics.median(p["val"] for p in pts), pts[0]["val"]
    ev = "оп.маржа ФГ %s = %.4f; max за 5 ФГ = %.4f; медиана = %.4f" % (pts[0]["end"], last, max(p["val"] for p in pts), med)
    return {"state": "RAISED" if (last >= max(p["val"] for p in pts) and last > med) else "CLEAR", "evidence": ev}


def flag_cash_conv(raw):
    ni, fcf = raw.get("ni") or [], raw.get("fcf") or []
    if not ni or not fcf or ni[-1]["end"] != fcf[-1]["end"]:
        return _und("MISSING_INPUT", "нужны NI и FCF на одном последнем ФГ")
    n1, f1 = at_offset(ni, 1), at_offset(fcf, 1)
    if n1 is None or f1 is None:
        return _und("INSUFFICIENT_HISTORY", "нет предыдущего ФГ для NI/FCF")
    ev = "NI %s: %s -> %s; FCF: %s -> %s" % (ni[-1]["end"], n1["val"], ni[-1]["val"], f1["val"], fcf[-1]["val"])
    return {"state": "RAISED" if (ni[-1]["val"] > n1["val"] and fcf[-1]["val"] < f1["val"]) else "CLEAR", "evidence": ev}


def flag_buyback_eps(F, raw):
    why = _need_fields(F, ["shares_chg_3y"])
    if why:
        return _und("MISSING_INPUT", why)
    ni, eps = raw.get("ni") or [], raw.get("eps") or []
    a_n, a_e = at_offset(ni, 3), at_offset(eps, 3)
    if not ni or not eps or a_n is None or a_e is None:
        return _und("INSUFFICIENT_HISTORY", "нет NI/EPS за 3 ФГ до последнего")
    if min(a_n["val"], ni[-1]["val"], a_e["val"], eps[-1]["val"]) <= 0:
        return _und("CAGR_UNDEFINED", "неположительная граница NI/EPS")
    g_ni, g_eps = (ni[-1]["val"] / a_n["val"]) ** (1 / 3.0) - 1, (eps[-1]["val"] / a_e["val"]) ** (1 / 3.0) - 1
    sh = F["shares_chg_3y"]["value"]
    ev = "акции 3л %+.4f; CAGR3 NI %.4f, CAGR3 EPS(вычисл.) %.4f" % (sh, g_ni, g_eps)
    return {"state": "RAISED" if (sh < 0 and g_eps > g_ni) else "CLEAR", "evidence": ev}


def flag_debt_for_buybacks(F):
    why = _need_fields(F, ["shares_chg_3y", "net_debt_chg_3y"])
    if why:
        return _und("MISSING_INPUT", why)
    sh, dn = F["shares_chg_3y"]["value"], F["net_debt_chg_3y"]["value"]
    return {"state": "RAISED" if (sh < 0 and dn > 0) else "CLEAR",
            "evidence": "акции 3л %+.4f; изменение чистого долга за 3 ФГ %+d USD" % (sh, dn)}


def flags_for(F, raw):
    return {"CYCLE_PEAK": flag_cycle_peak(raw), "CASH_CONV_DIVERGENCE": flag_cash_conv(raw),
            "BUYBACK_EPS": flag_buyback_eps(F, raw), "DEBT_FOR_BUYBACKS": flag_debt_for_buybacks(F)}


# ----------------------------------------------------------------------------- prices

def tiingo_prices(ticker, token, as_of, retries=2):
    """-> {date: adjClose} или бросает исключение (вызывающий превращает в именованный отказ)."""
    start = (_d(as_of) - dt.timedelta(days=PRICE_FETCH_DAYS)).isoformat()
    url = "https://api.tiingo.com/tiingo/daily/%s/prices?startDate=%s&endDate=%s&token=%s" % (ticker, start, as_of, token)
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Consilium floor1 card"})
            with urllib.request.urlopen(req, timeout=45) as r:
                rows = json.loads(r.read().decode("utf-8"))
            return {row["date"][:10]: float(row["adjClose"]) for row in rows if row.get("adjClose") is not None}
        except Exception as e:
            last = str(e).replace(token, "***")[:160]
            time.sleep(1 + i)
    raise RuntimeError(last)


def _at_or_before(px, date):
    ds = [d for d in px if d <= date]
    return (max(ds), px[max(ds)]) if ds else (None, None)


def _ret(px, as_of, days):
    d1, p1 = _at_or_before(px, as_of)
    if d1 is None:
        return None, refusal("NO_PRICES", "нет цен на дату")
    if (_d(as_of) - _d(d1)).days > PRICE_FRESH_DAYS:
        return None, refusal("PRICE_STALE", "последний close %s старше %d дн. от %s" % (d1, PRICE_FRESH_DAYS, as_of))
    tgt = (_d(as_of) - dt.timedelta(days=days)).isoformat()
    d0, p0 = _at_or_before(px, tgt)
    if d0 is None or (_d(tgt) - _d(d0)).days > PRICE_FRESH_DAYS:
        return None, refusal("INSUFFICIENT_HISTORY", "нет close около %s" % tgt)
    return (p1 / p0 - 1, d0, d1), None


def price_fields(px, bench, as_of, price_err=None):
    """px: {date:adj} тикера; bench: {'VOO': px|Exception-string, 'QQQ': ...}."""
    F = {}
    names = ["rs_%s_%s" % (b.lower(), w) for b in BENCH_RS for w, _ in RS_WINDOWS] + ["dd_52w"]
    if price_err or not px:
        r = refusal("TIINGO_UNAVAILABLE" if price_err else "NO_PRICES", price_err or "Tiingo вернул пустой ряд")
        return {n: r for n in names}
    for b in BENCH_RS:
        bpx = bench.get(b)
        for w, days in RS_WINDOWS:
            name = "rs_%s_%s" % (b.lower(), w)
            if not isinstance(bpx, dict) or not bpx:
                F[name] = refusal("BENCHMARK_UNAVAILABLE", "%s: %s" % (b, bpx if isinstance(bpx, str) else "нет цен"))
                continue
            t, e1 = _ret(px, as_of, days)
            m, e2 = _ret(bpx, as_of, days)
            if e1 or e2:
                F[name] = e1 or refusal(e2["refused"], "%s: %s" % (b, e2["reason"]))
                continue
            F[name] = ok(t[0] - m[0], "ratio", "доходность тикера %.4f минус %s %.4f, adjClose %s..%s" % (
                t[0], b, m[0], t[1], t[2]), ["Tiingo adjClose %s" % t[2]])
    d1, p1 = _at_or_before(px, as_of)
    lo = (_d(as_of) - dt.timedelta(days=364)).isoformat()
    first = min(px)
    if (_d(as_of) - _d(d1)).days > PRICE_FRESH_DAYS:
        F["dd_52w"] = refusal("PRICE_STALE", "последний close %s старше %d дн." % (d1, PRICE_FRESH_DAYS))
    elif (_d(lo) - _d(first)).days < -PRICE_FRESH_DAYS:
        F["dd_52w"] = refusal("INSUFFICIENT_HISTORY", "ряд цен начинается %s, окно 52н с %s" % (first, lo))
    else:
        window = {d: v for d, v in px.items() if lo <= d <= as_of}
        mx_d = max(window, key=window.get)
        F["dd_52w"] = ok(p1 / window[mx_d] - 1, "ratio", "close %s %s к max adjClose %s (%s)" % (
            d1, round(p1, 4), round(window[mx_d], 4), mx_d), ["Tiingo adjClose %s" % d1])
    return F


# ----------------------------------------------------------------------------- one name

FIELD_ORDER = ["rev_cagr_3y", "rev_cagr_5y", "rev_accel", "gm_latest", "gm_med5", "om_latest", "om_med5",
               "nm_latest", "nm_med5", "ni_latest", "eps_latest", "fcf_latest", "fcf_to_ni",
               "shares_chg_1y", "shares_chg_3y", "net_debt_latest", "net_debt_chg_3y",
               "rs_voo_4w", "rs_voo_13w", "rs_qqq_4w", "rs_qqq_13w", "dd_52w"]
FLAG_ORDER = ["CYCLE_PEAK", "CASH_CONV_DIVERGENCE", "BUYBACK_EPS", "DEBT_FOR_BUYBACKS"]
SEC_ONLY = [f for f in FIELD_ORDER if not f.startswith(("rs_", "dd_"))]


def sec_unavailable(out, facts):
    taxes = sorted((facts or {}).get("facts", {}).keys()) if facts else []
    if out.get("_errors"):
        code, why = "SEC_READ_FAILED", "; ".join("%s: %s" % kv for kv in out["_errors"].items())
    elif "ifrs-full" in taxes and "us-gaap" not in taxes:
        code, why = "FOREIGN_FILER_IFRS", "companyfacts содержит только ifrs-full (иностранный эмитент, 20-F/40-F); адаптер читает us-gaap"
    else:
        code, why = "NO_US_GAAP_ANNUAL_FACTS", "нет годовых us-gaap фактов (revenue и net_income пусты); таксономии: %s" % (taxes or "нет")
    return refusal(code, why)


def build_name(ticker, as_of, source, px, bench, price_err=None):
    """source.read(ticker) -> (adapter_out, companyfacts_filtered, cik). Любое исключение — именованный отказ."""
    ef = source.ef
    row = {"ticker": ticker, "fields": {}, "flags": {}, "meta": {}}
    try:
        out, facts, cik = source.read(ticker)
    except Exception as e:
        out, facts, cik = {"_errors": {"adapter": "%s: %s" % (type(e).__name__, str(e)[:140])}}, None, None
    row["meta"]["cik"] = cik
    if out.get("_errors") or (not out.get("revenue") and not out.get("net_income")):
        r = sec_unavailable(out, facts)
        F = {n: r for n in SEC_ONLY}
        raw = {}
        row["flags"] = {f: _und(r["refused"], r["reason"]) for f in FLAG_ORDER}
    else:
        F, raw = sec_fields(out, facts, ef)
        row["flags"] = flags_for(F, raw)
        rev = out.get("revenue") or []
        st = out.get("_staleness") or {}
        row["meta"].update(fy_end=st.get("latest_annual_end") or (rev[-1]["end"] if rev else None),
                           fy_age_days=st.get("latest_annual_age_days"),
                           as_of_violations=(out.get("_as_of_check") or {}).get("violations"),
                           adapter_path=(out.get("_adapter") or {}).get("path"))
    F.update(price_fields(px, bench, as_of, price_err))
    row["fields"] = {n: F[n] for n in FIELD_ORDER}
    return row


# ----------------------------------------------------------------------------- coverage + output

def coverage(rows):
    per, tot_ok, tot = {}, 0, 0
    for r in rows:
        ok_n = sum(1 for f in r["fields"].values() if is_ok(f)) + sum(1 for f in r["flags"].values() if f["state"] != "UNDETERMINED")
        n = len(r["fields"]) + len(r["flags"])
        per[r["ticker"]] = (ok_n, n)
        tot_ok, tot = tot_ok + ok_n, tot + n
    return per, (tot_ok / tot if tot else 0.0), tot_ok, tot


def limitations(rows):
    out = []
    for r in rows:
        for n, f in r["fields"].items():
            if not is_ok(f):
                out.append((r["ticker"], n, f["refused"], f["reason"]))
        for n, f in r["flags"].items():
            if f["state"] == "UNDETERMINED":
                out.append((r["ticker"], n, "UNDETERMINED", f["evidence"]))
    return out


def _fmt(f):
    if not is_ok(f):
        return "—[%s]" % f["refused"]
    v, u = f["value"], f["unit"]
    if u == "ratio":
        return "%+.1f%%" % (v * 100) if abs(v) < 10 else "%.2f" % v
    if u == "USD":
        return "%.2fB" % (v / 1e9)
    return "%.2f" % v


def write_outputs(rows, as_of, out_dir, bench_status, run_info):
    os.makedirs(out_dir, exist_ok=True)
    per, cov, n_ok, n_all = coverage(rows)
    lim = limitations(rows)
    base = os.path.join(out_dir, "FLOOR1_%s" % as_of)
    cols = ["ticker", "fy_end", "fy_age_days"]
    for n in FIELD_ORDER:
        cols += [n, n + "__reason"]
    for n in FLAG_ORDER:
        cols += [n, n + "__evidence"]
    cols += ["prov_accessions"]
    with open(base + ".csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            line = [r["ticker"], r["meta"].get("fy_end") or "", "" if r["meta"].get("fy_age_days") is None else r["meta"]["fy_age_days"]]
            prov = []
            for n in FIELD_ORDER:
                f = r["fields"][n]
                line += [repr(f["value"]) if is_ok(f) else "", "" if is_ok(f) else "%s: %s" % (f["refused"], f["reason"])]
                if is_ok(f):
                    prov += [p for p in f["prov"] if p not in prov]
            for n in FLAG_ORDER:
                line += [r["flags"][n]["state"], r["flags"][n]["evidence"]]
            line.append(" ".join(prov))
            w.writerow(line)
    L = ["# FLOOR1 — карточка этажа 1, %s" % as_of, "",
         "Сгенерировано `tools/floor1_card.py` (К1, #44/#90). as_of SEC = %s; SEC через адаптер К2 (edgartools==%s); цены — Tiingo adjClose." % (as_of, run_info["edgartools"]),
         "Имён: %d. Бенчмарки RS: VOO, QQQ (%s)." % (len(rows), bench_status),
         "Подстановок нет: пустая ячейка = именованный отказ (причина в колонке `__reason` CSV и в списке ниже).", "",
         "**Покрытие полей: %d/%d = %.1f%%** (цель ≥%d%% ИЛИ named limitation; все %d пробелов названы ниже)." % (
             n_ok, n_all, cov * 100, COVERAGE_TARGET * 100, len(lim)), ""]
    keys = ["rev_cagr_3y", "rev_cagr_5y", "rev_accel", "om_latest", "om_med5", "fcf_to_ni", "shares_chg_3y",
            "net_debt_latest", "rs_voo_13w", "rs_qqq_13w", "dd_52w"]
    L += ["| тикер | ФГ | " + " | ".join(keys) + " | флаги | покрытие |", "|" + "---|" * (len(keys) + 4)]
    for r in rows:
        raised = ",".join(n for n in FLAG_ORDER if r["flags"][n]["state"] == "RAISED") or "—"
        L.append("| %s | %s | %s | %s | %d/%d |" % (r["ticker"], r["meta"].get("fy_end") or "—",
                 " | ".join(_fmt(r["fields"][k]) for k in keys), raised, *per[r["ticker"]]))
    L += ["", "## Флаги с уликой", ""]
    for r in rows:
        for n in FLAG_ORDER:
            f = r["flags"][n]
            if f["state"] == "RAISED":
                L.append("- **%s** %s: %s" % (r["ticker"], n, f["evidence"]))
    L += ["", "## Named limitations (%d)" % len(lim), ""]
    grouped = {}
    for t, n, code, why in lim:
        grouped.setdefault((t, code, why), []).append(n)
    L += ["- %s / %s — `%s`: %s" % (t, ", ".join(ns), code, why) for (t, code, why), ns in grouped.items()] or ["- нет"]
    L += ["", "## Базисы и провенанс", "",
          "Каждое число в CSV сопровождается колонкой `prov_accessions` (accession SEC ФГ-фактов) и для цен — датой Tiingo в basis. "
          "Определения полей — в докстринге `tools/floor1_card.py`. FCF = OCF − capex(PP&E); EPS вычислен как NI/разводнённые акции; "
          "чистый долг = LongTermDebt − Cash&Equivalents; пороги флагов не заданы — только сравнения (правила — предложение исполнителя).", ""]
    with open(base + ".md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return base, cov, len(lim)


# ----------------------------------------------------------------------------- live source + main

class LiveSource:
    def __init__(self, as_of):
        self.ef, self.ad = load_sec_modules()
        self.as_of = as_of
        self.loader = self.ad.LiveLoader()          # бросит, если SEC_USER_AGENT не задан

    def read(self, ticker):
        cik = self.ef._resolve_cik(ticker)
        if not cik:
            return {"_errors": {"cik": "тикер не найден в SEC company_tickers"}}, None, None
        out = self.ad.read_as_of(ticker=ticker, cik=cik, as_of=self.as_of, loader=self.loader)
        facts = None if out.get("_errors") else self.ef._filter_facts_as_of(self.ef._companyfacts(cik), self.as_of)
        return out, facts, cik


def read_watchlist(path):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return [r["ticker"].strip() for r in rows if r["role"].strip() == "watch"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    ap.add_argument("--tickers", default="")
    ap.add_argument("--watchlist", default=WATCHLIST)
    ap.add_argument("--out-dir", default=OUT_DIR)
    a = ap.parse_args(argv)
    token = os.environ.get("TIINGO_TOKEN") or ""
    if not token or not (os.environ.get("SEC_USER_AGENT") or "").strip():
        print("ОТКАЗ: нужны env TIINGO_TOKEN и SEC_USER_AGENT; карточка НЕ записана (карточка из одних отказов — не карточка).", file=sys.stderr)
        return 2
    try:
        names = [t for t in a.tickers.split(",") if t] or read_watchlist(a.watchlist)
    except Exception as e:
        print("ОТКАЗ: watchlist недоступен: %s" % e, file=sys.stderr)
        return 2
    if not names:
        print("ОТКАЗ: watchlist пуст", file=sys.stderr)
        return 2
    src = LiveSource(a.as_of)
    bench, bstat = {}, []
    for b in BENCH_RS:
        try:
            bench[b] = tiingo_prices(b, token, a.as_of)
            bstat.append("%s до %s" % (b, max(bench[b])))
        except Exception as e:
            bench[b] = "Tiingo: %s" % e
            bstat.append("%s НЕДОСТУПЕН" % b)
    rows = []
    for i, t in enumerate(names, 1):
        t0 = time.time()
        try:
            px, err = tiingo_prices(t, token, a.as_of), None
        except Exception as e:
            px, err = None, "Tiingo %s: %s" % (t, e)
        rows.append(build_name(t, a.as_of, src, px, bench, err))
        print("[%d/%d] %s %.1fs" % (i, len(names), t, time.time() - t0), file=sys.stderr)
    base, cov, nlim = write_outputs(rows, a.as_of, a.out_dir, "; ".join(bstat), {"edgartools": src.ad.EDGARTOOLS_PIN})
    print("карточка: %s.{md,csv}; покрытие %.1f%%; named limitations: %d" % (base, cov * 100, nlim))
    return 0


if __name__ == "__main__":
    sys.exit(main())
