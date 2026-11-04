#!/usr/bin/env python3
"""К6 часть A: генератор досье «запрос -> досье» (DECISION_2026-10-11 (б); гейт PREREG_2026-10-11 v2 п. 2).

    SEC_USER_AGENT="Имя email" TIINGO_TOKEN=... python3 tools/dossier.py NFLX --as-of 2020-02-15 [--out-dir Reports/dossiers]

Выход: <out-dir>/<TICKER>_<as_of>_machine.md (для аудиторов: accession у каждого числа) и
       <out-dir>/<TICKER>_<as_of>_brief.md   (для человека, простым русским, без вердикта).

Детерминированно: модели не вызываются, числа только с выхода инструментов (адаптер К2, Tiingo, чистые функции).
Missing != zero != default: нет факта -> именованный отказ с причиной. Вердиктов «покупать / не покупать» здесь нет
(боевые вердикты запрещены до нового затвора, DECISION_2026-08-09).

Переиспользовано, не переписано: tools/floor1_card.py (поля, флаги, цены), tools/guards/cash_decay.py (CASH_DECAY),
tools/exam_nflx.load_facts (загрузка фактов сторожа), CONSILIUM_REPO_v4_2_83/microservice/ivc_lib.ivc (чистая функция
старого конвейера; обратный DCF -- бисекция по ней, как в app.py).
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "guards"))

import floor1_card as fc    # noqa: E402
import cash_decay as cd     # noqa: E402
import exam_nflx as ex      # noqa: E402

OUT_DIR = os.path.join(ROOT, "Reports", "dossiers")
IVC_PATH = os.path.join(ROOT, "CONSILIUM_REPO_v4_2_83", "microservice", "ivc_lib.py")

HURDLE = 0.12                                # порог мандата; параметр, не прогноз
YEARS = 10
GRID_GROWTH = (0.00, 0.05, 0.10, 0.15, 0.20, 0.25)
GRID_EV_S = (10, 15, 20, 25, 30)
GRID_PS = (2, 4, 6, 8, 10)
GRID_PE = (10, 15, 20, 25, 30)
PASSIVE_WINDOWS = ((1, 365), (3, 1095), (5, 1826))   # лет, дней
PRICE_DAYS = 1850                            # глубина загрузки Tiingo: 5 лет + запас
SECTIONS = ("а", "б", "в", "г", "д", "е")
SEC_FIELDS = (("revenue", "Выручка"), ("operating_income", "Операционная прибыль"), ("net_income", "Чистая прибыль (NI)"),
              ("ocf", "Операционный денежный поток (OCF)"), ("capex", "Капзатраты (capex)"),
              ("shares_diluted", "Акции, разводнённые средневзвешенные за ФГ"), ("sbc", "SBC (справочно)"))


PS_NOTE_TEXT = "долг не представлен в отчётности; оценка по капитализации, не по стоимости компании"


def refusal(code, reason):
    return fc.refusal(code, reason)


def is_ref(x):
    return isinstance(x, dict) and "refused" in x


def load_ivc():
    spec = importlib.util.spec_from_file_location("ivc_lib_dossier", IVC_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.ivc


# ----------------------------------------------------------------------------- сырые факты чистого долга

def debt_raw(facts, ef, nd_field, as_of=None, force_v2=False):
    """Сырые факты, из которых карточка собрала net_debt_latest: каждое слагаемое долга и cash с тегом, accession,
    концом периода и значением; плюс остальные теги цепочек долга, у которых на ТОМ ЖЕ конце периода есть значение
    (показаны, не используются: чтобы расхождение тегов было видно читателю, а не угадывалось). Ничего не выбирается
    заново: отбор слагаемых -- логика net_debt_series карточки (повторена по тем же цепочкам, затем сверена с числом
    карточки; не сошлось -- отказ RAW_MISMATCH, а не подгонка).
    -> dict | отказ."""
    if is_ref(nd_field):
        return nd_field
    if facts is None:
        return refusal("NOT_IN_SOURCE", "нет фактов SEC для разбора слагаемых чистого долга")
    series, ref = fc.net_debt_series(facts, ef, as_of, force_v2)
    if ref:
        return ref
    pt = series[-1]
    end, parts, cash = pt["end"], pt["parts"], pt["cash"]
    total = sum(r["val"] for r in parts) - cash["val"]
    if total != nd_field["value"]:
        return refusal("RAW_MISMATCH", "слагаемые на %s дают %s, а карточка — %s: сырые факты не показаны" % (end, total, nd_field["value"]))
    used = {r["tag"] for r in parts} | {cash["tag"]}
    unused = []
    for tag in fc.DEBT_FULL_CHAIN + fc.DEBT_NONC_CHAIN + fc.DEBT_NONC_V2 + fc.DEBT_CUR_CHAIN + fc.DEBT_CUR_TAGS + fc.CASH_CHAIN:
        if tag in used or any(u["tag"] == tag for u in unused):
            continue
        rows, _ = ef._annual_instant_series(facts, [tag])
        for r in rows:
            if r["end"] == end:
                unused.append(r)
    return {"end": end, "debt": parts, "cash": cash, "total": total, "unused": unused,
            "basis": pt["debt_basis"], "flags": pt["debt_flags"]}


def cash_raw(facts, ef, fy):
    """Деньги на конец ФГ `fy` (CASH_CHAIN карточки), с тегом и accession. Нужны гейту пути по капитализации
    (DECISION_2026-11-02_DOSSIER_COMPLETENESS §1 п. 5): «деньги известны». -> строка факта | отказ.
    Нет фактов / нет ФГ / нет денег именно на эту дату -- MISSING_INPUT (наш пробел), не ноль."""
    if facts is None or not fy:
        return refusal("MISSING_INPUT", "нет фактов SEC или даты ФГ: деньги не прочитаны")
    row = fc._by_end(facts, ef, fc.CASH_CHAIN).get(fy)
    if row is None:
        return refusal("MISSING_INPUT", "нет денег (теги %s) на конец ФГ %s: ноль не подставляется" % (",".join(fc.CASH_CHAIN), fy))
    return row


# ----------------------------------------------------------------------------- чистая арифметика

def _annual(ratio, years):
    return ratio ** (1.0 / years) - 1


def ev_s_return(rev0, shares, net_debt, price, g, mult, years=YEARS):
    """Годовая доходность на `years` лет: выручка растёт g в год, выходной EV/S = mult, чистый долг и число акций
    неизменны, дивидендов нет. -> число | отказ. Отрицательный капитал на выходе -- отказ, не -100%."""
    if price is None or price <= 0 or not shares or shares <= 0:
        return refusal("NO_PRICE_OR_SHARES", "нет положительной цены или числа акций")
    eq_t = mult * rev0 * (1 + g) ** years - net_debt
    if eq_t <= 0:
        return refusal("NONPOSITIVE_EQUITY", "EV на выходе %.0f не покрывает чистый долг %.0f" % (mult * rev0 * (1 + g) ** years, net_debt))
    return _annual(eq_t / shares / price, years)


def ps_return(rev0, shares, price, g, mult, years=YEARS):
    """Путь по капитализации (долг не представлен): выручка растёт g в год, выходной P/S = mult (капитализация / выручка),
    число акций неизменно, дивидендов нет. Чистый долг НЕ участвует -- это оценка капитала, не стоимости компании."""
    if rev0 is None or rev0 <= 0:
        return refusal("NONPOSITIVE_REVENUE", "выручка <= 0: P/S-сетка не определена")
    if price is None or price <= 0 or not shares or shares <= 0:
        return refusal("NO_PRICE_OR_SHARES", "нет положительной цены или числа акций")
    return _annual(mult * rev0 * (1 + g) ** years / shares / price, years)


def required_growth_ps(rev0, shares, price, mult, hurdle=HURDLE, years=YEARS):
    """Рост выручки в год, при котором ps_return == hurdle (закрытая форма). -> число | отказ."""
    if price is None or price <= 0 or not shares or shares <= 0 or mult is None or mult <= 0 or rev0 is None or rev0 <= 0:
        return refusal("NO_INPUT", "нужны положительные цена, акции, выручка и множитель")
    return _annual(price * shares * (1 + hurdle) ** years / (mult * rev0), years)


def pe_return(ni0, shares, price, g, mult, years=YEARS):
    """То же для P/E: чистая прибыль растёт g в год (маржа не меняется), выходной P/E = mult, число акций неизменно."""
    if ni0 is None or ni0 <= 0:
        return refusal("NONPOSITIVE_NI", "NI <= 0: P/E-сетка не определена")
    if price is None or price <= 0 or not shares or shares <= 0:
        return refusal("NO_PRICE_OR_SHARES", "нет положительной цены или числа акций")
    return _annual(mult * ni0 * (1 + g) ** years / shares / price, years)


def required_growth_ev_s(rev0, shares, net_debt, price, mult, hurdle=HURDLE, years=YEARS):
    """Рост выручки в год, при котором ev_s_return == hurdle (закрытая форма). -> число | отказ."""
    if price is None or price <= 0 or not shares or shares <= 0 or mult is None or mult <= 0 or rev0 <= 0:
        return refusal("NO_INPUT", "нужны положительные цена, акции, выручка и множитель")
    ev_t = price * shares * (1 + hurdle) ** years + net_debt
    if ev_t <= 0:
        return refusal("NONPOSITIVE_EV", "требуемый EV на выходе <= 0")
    return _annual(ev_t / (mult * rev0), years)


def reverse_dcf(ivc, price, eps, fcf_ps, pe, hurdle=HURDLE):
    """Рост базы (EPS или FCF/акцию), уже заложенный в цену при пороге hurdle и выходном P/E = pe.
    Бисекция по ivc старого конвейера (app.py), с самопроверкой: решение обязано воспроизвести порог."""
    leg = "gaap_eps" if eps is not None else "fcf_per_share"
    base = eps if eps is not None else fcf_ps
    if base is None or base <= 0:
        return refusal("NONPOSITIVE_BASE", "база %s <= 0: обратный DCF не определён" % leg)

    def at(g):
        inp = {"price": price, "growth_rate": g, "future_pe": pe, "hurdle": hurdle, "years": YEARS,
               "terminal_growth": min(0.04, g), "fade": True}
        inp.update({"eps_normalized": base} if leg == "gaap_eps" else {"eps_normalized": None, "levered_fcf_per_share": base})
        return ivc(inp).get("implied_cagr_pct")
    lo, hi, tgt = -0.50, 1.00, hurdle * 100
    v_lo, v_hi = at(lo), at(hi)
    if not isinstance(v_lo, (int, float)) or not isinstance(v_hi, (int, float)):
        return refusal("IVC_ERROR", "ivc не вернул implied_cagr на границах поиска")
    if v_hi < tgt:
        return refusal("OUT_OF_BOUNDS", "даже при росте %.0f%% доходность %.2f%% < порога %.0f%%" % (hi * 100, v_hi, tgt))
    if v_lo > tgt:
        return refusal("OUT_OF_BOUNDS", "даже при росте %.0f%% доходность %.2f%% > порога %.0f%%" % (lo * 100, v_lo, tgt))
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if at(mid) < tgt:
            lo = mid
        else:
            hi = mid
    g = (lo + hi) / 2.0
    chk = at(g)
    if abs(chk - tgt) >= 0.1:
        return refusal("SELFTEST_FAILED", "решение g=%.4f даёт %.2f%%, не %.2f%%" % (g, chk, tgt))
    return {"g": g, "leg": leg, "base_per_share": base, "future_pe": pe, "selftest_cagr_pct": chk}


# ----------------------------------------------------------------------------- цены

def tiingo_series(ticker, token, as_of, days=PRICE_DAYS, retries=2):
    """-> {date: (close, adjClose)} или RuntimeError. close -- как торговался (для цены/акцию против акций из SEC на ту
    дату); adjClose -- пересчитан на последующие сплиты и дивиденды (для доходностей)."""
    start = (fc._d(as_of) - dt.timedelta(days=days)).isoformat()
    url = "https://api.tiingo.com/tiingo/daily/%s/prices?startDate=%s&endDate=%s&token=%s" % (ticker, start, as_of, token)
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Consilium dossier"})
            with urllib.request.urlopen(req, timeout=45) as r:
                rows = json.loads(r.read().decode("utf-8"))
            return {x["date"][:10]: (float(x["close"]) if x.get("close") is not None else None,
                                     float(x["adjClose"]) if x.get("adjClose") is not None else None) for x in rows}
        except Exception as e:
            last = str(e).replace(token, "***")[:160]
            time.sleep(1 + i)
    raise RuntimeError(last)


def _col(series, i):
    return {d: v[i] for d, v in series.items() if v[i] is not None}


def spot_price(series, as_of):
    """Цена «как торговалась» на последнюю дату <= as_of (не старше PRICE_FRESH_DAYS). -> (цена, дата, отказ)."""
    px = _col(series, 0)
    d, p = fc._at_or_before(px, as_of)
    if d is None:
        return None, None, refusal("NO_PRICES", "нет close на дату")
    if (fc._d(as_of) - fc._d(d)).days > fc.PRICE_FRESH_DAYS:
        return None, d, refusal("PRICE_STALE", "последний close %s старше %d дн. от %s" % (d, fc.PRICE_FRESH_DAYS, as_of))
    return p, d, None


def passive_returns(series, as_of):
    """-> {n_лет: {"total","annual","d0","d1"} | отказ} по adjClose за 1/3/5 лет до as_of."""
    out = {}
    px = _col(series, 1) if isinstance(series, dict) else {}
    for n, days in PASSIVE_WINDOWS:
        if not px:
            out[n] = refusal("BENCHMARK_UNAVAILABLE", series if isinstance(series, str) else "нет цен")
            continue
        t, err = fc._ret(px, as_of, days)
        out[n] = err if err else {"total": t[0], "annual": _annual(1 + t[0], n), "d0": t[1], "d1": t[2]}
    return out


# ----------------------------------------------------------------------------- сбор данных

def pt(series, fy, name):
    """Точка ФГ `fy` ряда или отказ (нет ряда / ряд кончился раньше)."""
    ser, ref = fc.current(series, fy, name)
    return ref if ser is None else ser[-1]


def build(ticker, as_of, source, fetch, started=None, force_v2=False):
    """source.read(ticker) -> (out, facts, cik); fetch(ticker) -> {date: (close, adj)} (бросает исключение).
    -> dict D со всеми данными досье. Любой сбой источника -- именованный отказ в соответствующем поле."""
    t0 = time.monotonic() if started is None else started
    D = {"ticker": ticker, "as_of": as_of, "refusals": {}, "debt_chain_forced_v2": bool(force_v2)}
    source.as_of = as_of
    try:
        out, facts, cik = source.read(ticker)
    except Exception as e:
        out, facts, cik = {"_errors": {"adapter": "%s: %s" % (type(e).__name__, str(e)[:140])}}, None, None
    D["cik"], D["entity"] = cik, out.get("_entity_name")
    sec_ok = not out.get("_errors") and (out.get("revenue") or out.get("net_income"))
    D["sec_error"] = None if sec_ok else fc.sec_unavailable(out, facts)

    px = {}
    bench = {}
    for t in (ticker,) + fc.BENCH_RS:
        try:
            px[t] = fetch(t)
        except Exception as e:
            px[t] = "Tiingo %s: %s" % (t, e)
    D["px"] = px
    own = px[ticker]
    adj_own = _col(own, 1) if isinstance(own, dict) else None
    for b in fc.BENCH_RS:
        bench[b] = _col(px[b], 1) if isinstance(px[b], dict) else px[b]
    D["card"] = fc.build_name(ticker, as_of, source, adj_own, bench, None if adj_own else (own if isinstance(own, str) else "нет цен"), force_v2)
    D["passive"] = {b: passive_returns(px[b], as_of) for b in fc.BENCH_RS}
    D["price"], D["price_date"], D["price_ref"] = (None, None, refusal("TIINGO_UNAVAILABLE", own)) if isinstance(own, str) else spot_price(own, as_of)

    D["raw"] = {}
    D["fy"] = None
    if sec_ok:
        series = {k: out.get(k + "_audit") or out.get(k) for k, _ in SEC_FIELDS}
        D["fy"] = next((s[-1]["end"] for s in (series["revenue"], series["net_income"], series["ocf"]) if s), None)
        D["raw"] = {k: (pt(s, D["fy"], k) if s else refusal("NOT_IN_SOURCE", "адаптер К2 не вернул ряд %s" % k)) for k, s in series.items()}
        if not series["capex"] and facts is not None:    # запасной тег capex, как в карточке
            cx, _, _, _ = source.ef._annual_merged(facts, fc.CAPEX_FALLBACK_TAGS)
            if cx:
                D["raw"]["capex"] = pt(cx, D["fy"], "capex")
        D["rev_series"] = series["revenue"] or []
    else:
        D["raw"] = {k: D["sec_error"] for k, _ in SEC_FIELDS}
        D["rev_series"] = []
    D["nd"] = D["card"]["fields"]["net_debt_latest"]
    D["nd_raw"] = debt_raw(facts, source.ef, D["nd"], as_of, force_v2) if sec_ok else D["sec_error"]
    D["cash"] = cash_raw(facts, source.ef, D["fy"]) if sec_ok else D["sec_error"]
    D["guard"] = _guard(source, ticker, as_of)
    D["seconds"] = round(time.monotonic() - t0, 1)
    D["input_hash"] = input_hash(D, ticker, as_of)
    D["derived"] = derive(D)
    return D


def _guard(source, ticker, as_of):
    try:
        facts, cik, why = ex.load_facts(source, ticker, as_of)
    except Exception as e:
        return {"verdict": cd.UNDEFINED, "reason": "загрузка фактов сторожа: %s: %s" % (type(e).__name__, str(e)[:120]),
                "evidence": None, "rule": None, "diagnostics": [], "notes": []}
    if facts is None:
        return {"verdict": cd.UNDEFINED, "reason": why, "evidence": None, "rule": None, "diagnostics": [], "notes": []}
    return cd.evaluate(facts, as_of)


def input_hash(D, ticker, as_of):
    """Хэш входа: все факты SEC и цены, от которых зависят числа досье (без времени и без сгенерированного текста)."""
    spot = {"price": D["price"], "price_date": D["price_date"]}
    bench = {b: ({d: v for d, v in sorted(D["px"][b].items())} if isinstance(D["px"][b], dict) else D["px"][b]) for b in fc.BENCH_RS}
    blob = {"ticker": ticker, "as_of": as_of, "raw": D["raw"], "rev_series": D["rev_series"], "nd": D["nd"], "cash": D.get("cash"), "spot": spot,
            "bench": bench, "guard_diag": D["guard"].get("diagnostics")}
    return hashlib.sha256(json.dumps(blob, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def _v(x):
    return None if x is None or is_ref(x) else x["val"]


def derive(D):
    """Всё, что считается из собранного: капитализация, сетки, обратный DCF, 'что должно быть правдой / что опровергнет'."""
    R, d = D["raw"], {}
    rev, ni, ocf, cx, sh = (_v(R.get(k)) for k in ("revenue", "net_income", "ocf", "capex", "shares_diluted"))
    d["fcf"] = None if ocf is None or cx is None else ocf - cx
    d["eps"] = None if ni is None or not sh else ni / sh
    d["fcf_ps"] = None if d["fcf"] is None or not sh else d["fcf"] / sh
    nd = None if is_ref(D["nd"]) else D["nd"]["value"]
    price = D["price"]
    miss = [n for n, x in (("цена", price), ("акции", sh), ("чистый долг", nd), ("выручка", rev)) if x is None]
    d["missing"] = miss
    d["mcap"] = None if price is None or not sh else price * sh
    d["ev"] = None if d["mcap"] is None or nd is None else d["mcap"] + nd
    d["ev_s"] = None if d["ev"] is None or not rev else d["ev"] / rev
    why = "нет: %s" % ", ".join(miss) if miss else None
    # Класс отказа EV/S-пути. Единственный пробел -- чистый долг: класс берём у отказа самого поля (NOT_REPORTED --
    # не наша вина; DEBT_TAG_ABSENT / MISSING_INPUT -- наша, и это видно по коду). Иначе -- MISSING_INPUT.
    miss_code = D["nd"]["refused"] if miss == ["чистый долг"] and is_ref(D["nd"]) else "MISSING_INPUT"
    ev_ref = (lambda reason: refusal(miss_code, reason))
    d["grid_ev_s"] = {(g, m): (ev_s_return(rev, sh, nd, price, g, m) if not miss else ev_ref(why))
                      for g in GRID_GROWTH for m in GRID_EV_S}
    # Путь по капитализации (DECISION_2026-11-02_DOSSIER_COMPLETENESS §1 п. 5): ТОЛЬКО если чистый долг -- именно
    # NOT_REPORTED (компания не представила), деньги известны, и есть цена, акции, выручка. Иной отказ долга (наш
    # пробел) путь не включает: это не «долг не представлен», а «мы не прочитали».
    cash = D.get("cash")
    d["cash_val"] = None if cash is None or is_ref(cash) else cash["val"]
    d["ps_mode"], d["ps_reason"] = False, None
    if not is_ref(D["nd"]):
        d["ps_reason"] = "чистый долг известен: EV/S-путь основной"
    elif D["nd"]["refused"] != "NOT_REPORTED":
        d["ps_reason"] = "отказ чистого долга класса %s, не NOT_REPORTED: путь по капитализации не включается" % D["nd"]["refused"]
    elif cash is None or is_ref(cash):
        d["ps_reason"] = "деньги неизвестны (%s): раздел (г) пуст, досье не полное" % ("нет чтения" if cash is None else cash["refused"])
    elif price is None or not sh or not rev:
        d["ps_reason"] = "нет: %s" % ", ".join(n for n, x in (("цена", price), ("акции", sh), ("выручка", rev)) if not x)
    else:
        d["ps_mode"] = True
    d["ps"] = None if d["mcap"] is None or not rev or rev <= 0 else d["mcap"] / rev
    ps_ref = refusal("PS_PATH_OFF", d["ps_reason"] or "путь по капитализации не включён")
    d["grid_ps"] = {(g, m): (ps_return(rev, sh, price, g, m) if d["ps_mode"] else ps_ref)
                    for g in GRID_GROWTH for m in GRID_PS}
    d["g_req_ps"] = required_growth_ps(rev, sh, price, d["ps"]) if d["ps_mode"] and d["ps"] else ps_ref
    d["g_req_ps_sens"] = {k: (required_growth_ps(rev, sh, price, d["ps"] * k) if d["ps_mode"] and d["ps"] else ps_ref)
                          for k in (0.5, 1.0, 1.5)}
    d["grid_pe"] = {(g, m): (pe_return(ni, sh, price, g, m) if price is not None and sh else refusal("MISSING_INPUT", "нет цены или акций"))
                    for g in GRID_GROWTH for m in GRID_PE}
    d["g_req"] = (required_growth_ev_s(rev, sh, nd, price, d["ev_s"]) if d["ev_s"] and not miss else ev_ref(why or "нет EV/S"))
    d["g_req_sens"] = {}
    for k in (0.5, 1.0, 1.5):
        d["g_req_sens"][k] = (required_growth_ev_s(rev, sh, nd, price, d["ev_s"] * k) if d["ev_s"] and not miss
                              else ev_ref(why or "нет EV/S"))
    ivc = load_ivc()
    d["rdcf"] = {}
    for leg, base in (("gaap_eps", d["eps"]), ("fcf_per_share", d["fcf_ps"])):
        for pe in GRID_PE:
            if price is None or base is None:
                d["rdcf"][(leg, pe)] = refusal("MISSING_INPUT", "нет цены или базы %s" % leg)
            else:
                d["rdcf"][(leg, pe)] = reverse_dcf(ivc, price, base if leg == "gaap_eps" else None,
                                                   base if leg == "fcf_per_share" else None, pe)
    d["yoy"] = last_growths(D["rev_series"], 2)
    d["fcf_ni"] = None if d["fcf"] is None or not ni or ni <= 0 else d["fcf"] / ni
    return d


def last_growths(rev_series, n):
    """Рост выручки за последние n ФГ подряд: [(конец ФГ, рост)] от старого к новому, либо []. Нужны n+1 соседних ФГ."""
    pts = [r for r in rev_series if r.get("val") is not None]
    out = []
    for i in range(len(pts) - n, len(pts)):
        if i < 1 or pts[i - 1]["val"] <= 0:
            return []
        out.append((pts[i]["end"], pts[i]["val"] / pts[i - 1]["val"] - 1))
    return out


# ----------------------------------------------------------------------------- форматирование

def usd(x):
    return "%s USD" % format(round(x), ",")


def pc(x, d=1):
    return "%+.*f%%" % (d, x * 100)


def pp(x, d=1):
    return "%.*f%%" % (d, x * 100)


def ref_text(r):
    return "ОТКАЗ %s: %s" % (r["refused"], r["reason"])


def prov(p):
    if is_ref(p):
        return ref_text(p)
    return "SEC %s, ФГ %s, тег %s, подан %s" % (p.get("accn"), p.get("end"), p.get("tag"), p.get("filed"))


# ----------------------------------------------------------------------------- machine-отчёт

def sec_a(D):
    L = ["## (а) Провенанс и basis-check GAAP / non-GAAP", ""]
    L += ["| Строка | Значение | Откуда |", "|---|---|---|"]
    for k, title in SEC_FIELDS:
        p = D["raw"].get(k)
        L.append("| %s | %s | %s |" % (title, "—" if is_ref(p) else usd(p["val"]) if k != "shares_diluted" else format(round(p["val"]), ","),
                                       prov(p)))
    d = D["derived"]
    ni, opi = _v(D["raw"].get("net_income")), _v(D["raw"].get("operating_income"))
    ocf, cx = D["raw"].get("ocf"), D["raw"].get("capex")
    L += ["", "FCF = OCF − capex (вычислено здесь): " + (usd(d["fcf"]) + " [accn %s и %s]" % (ocf["accn"], cx["accn"])
                                                         if d["fcf"] is not None else
                                                         ref_text(refusal("MISSING_INPUT", "нет OCF или capex на ФГ %s" % D["fy"]))), ""]
    L.append("**Расхождение NI / операционная прибыль / FCF** (отношения; знаменатель <= 0 -> отказ, не 0):")
    for name, num, den in (("NI / операционная прибыль", ni, opi), ("FCF / NI", d["fcf"], ni), ("FCF / операционная прибыль", d["fcf"], opi)):
        if num is None or den is None:
            L.append("- %s: %s" % (name, ref_text(refusal("MISSING_INPUT", "нет одного из членов отношения"))))
        elif den <= 0:
            L.append("- %s: %s" % (name, ref_text(refusal("NONPOSITIVE_DENOMINATOR", "знаменатель %s <= 0" % usd(den)))))
        else:
            L.append("- %s: %.3f" % (name, num / den))
    marks = []
    if ni is not None and d["fcf"] is not None and (ni > 0) != (d["fcf"] > 0):
        marks.append("знаки NI (%s) и FCF (%s) различаются" % (usd(ni), usd(d["fcf"])))
    if d["fcf_ni"] is not None and d["fcf_ni"] < cd.FCF_NI_MIN:
        marks.append("FCF/NI = %.2f < порога %s (PREREG K4 §4)" % (d["fcf_ni"], cd.FCF_NI_MIN))
    L.append("- Метки расхождения: " + ("; ".join(marks) if marks else "нет (по правилам выше)"))
    L += ["", "**Non-GAAP:** " + ref_text(refusal("NON_GAAP_NOT_CHECKED", "не проверено машиной: показатели, которые компания публикует "
                                                "вне GAAP (adjusted EBITDA, non-GAAP EPS), в XBRL us-gaap не лежат; публикует ли компания "
                                                "non-GAAP -- машина не знает"))]
    return L


def sec_b(D):
    L = ["## (б) Факты этажа 1 (те же функции, что карточка, на as_of %s)" % D["as_of"], ""]
    if D["sec_error"]:
        L.append("SEC-поля: " + ref_text(D["sec_error"]))
        L.append("")
    L += ["| Поле | Значение | Единица | Основание (basis) | Провенанс |", "|---|---|---|---|---|"]
    for name in fc.FIELD_ORDER:
        f = D["card"]["fields"][name]
        if fc.is_ok(f):
            L.append("| %s | %s | %s | %s | %s |" % (name, f["value"], f["unit"], f["basis"], "; ".join(f["prov"]) or "—"))
        else:
            L.append("| %s | — | — | %s | — |" % (name, ref_text(f)))
    L += sec_b_debt(D)
    return L


def sec_b_debt(D):
    """Сырые факты net_debt_latest: слагаемые долга, cash, формула; прочие теги долга на той же дате -- справочно."""
    L = ["", "**Чистый долг — сырые факты** (поле net_debt_latest)", ""]
    r = D.get("nd_raw")
    if is_ref(r):
        return L + ["- " + ref_text(r)]
    L += ["| Роль | Тег | Accession | Конец периода | Значение, USD |", "|---|---|---|---|---|"]
    for p in r["debt"]:
        L.append("| долг | %s | %s | %s | %s |" % (p["tag"], p.get("accn"), p["end"], format(round(p["val"]), ",")))
    c = r["cash"]
    L.append("| cash | %s | %s | %s | %s |" % (c["tag"], c.get("accn"), c["end"], format(round(c["val"]), ",")))
    L += ["", "Формула: net_debt = %s − cash = %s − %s = %s USD" % (
        " + ".join(format(round(p["val"]), ",") for p in r["debt"]), format(round(sum(p["val"] for p in r["debt"])), ","),
        format(round(c["val"]), ","), format(round(r["total"]), ","))]
    L += ["", "Базис долга: %s." % r["basis"]]
    for x in r["flags"]:
        L += ["", "**%s**: %s = %s USD, сумма балансовых частей = %s USD (accession %s) — расхождение больше 10 %%; "
              "в расчёте — балансовые части." % (fc.DEBT_FLAG, x["full_tag"], format(round(x["full_val"]), ","),
                                                  format(round(x["parts_sum"]), ","), x["accn"])]
    if r["unused"]:
        L += ["", "Другие теги цепочек долга/cash со значением на %s (в расчёте НЕ использованы; показаны для сверки читателем):" % r["end"]]
        for p in r["unused"]:
            L.append("- %s = %s USD (accession %s)" % (p["tag"], format(round(p["val"]), ","), p.get("accn")))
    return L


def sec_c(D):
    g = D["guard"]
    L = ["## (в) Сторожа с уликами", "", "**CASH_DECAY** (правила PREREG_2026-11-01_K4_NFLX_CASH_DECAY §4): **%s**%s" % (
        g["verdict"], " (правило %s)" % g["rule"] if g.get("rule") else ""),
        "- Причина: %s" % g.get("reason"), "- Улика: %s" % (g.get("evidence") or "нет (вердикт без улики: не RED/AMBER)")]
    for n in g.get("notes") or []:
        L.append("- Замечание загрузки: %s" % n)
    if g.get("diagnostics"):
        L += ["", "Диагностика FCF/NI по ФГ (из сторожа, как есть):"]
        L += ["- " + json.dumps(x, ensure_ascii=False, sort_keys=True, default=str) for x in g["diagnostics"]]
    L += ["", "**Флаги карточки этажа 1:**"]
    for name in fc.FLAG_ORDER:
        f = D["card"]["flags"].get(name)
        if not f:
            L.append("- %s: %s" % (name, ref_text(refusal("NOT_COMPUTED", "флаг не вычислен"))))
            continue
        extra = " [%s]" % f["code"] if f.get("code") else ""
        L.append("- %s: **%s**%s — %s" % (name, f.get("state"), extra, f.get("evidence") or f.get("reason") or "без улики"))
    return L


def sec_g(D):
    d = D["derived"]
    L = ["## (г) Сценарная поверхность", ""]
    L.append("Допущения (basis): цена — Tiingo close «как торговалась» %s на %s; акции — разводнённые средневзвешенные за ФГ %s из SEC "
             "(не на дату, не float); чистый долг — поле net_debt_latest этажа 1; горизонт %d лет; число акций, чистый долг и "
             "дивиденды (нет) не меняются; множитель — параметр сетки, не прогноз." % (
                 "—" if D["price"] is None else round(D["price"], 2), D["price_date"], D["fy"], YEARS))
    if D["price_ref"]:
        L.append("Цена: " + ref_text(D["price_ref"]))
    L.append("Текущая капитализация: %s; EV: %s; EV/S: %s." % (
        "ОТКАЗ" if d["mcap"] is None else usd(d["mcap"]), "ОТКАЗ (нет %s)" % ", ".join(d["missing"]) if d["ev"] is None else usd(d["ev"]),
        "ОТКАЗ" if d["ev_s"] is None else "%.2f" % d["ev_s"]))
    L += ["", "**Таблица 1. Подразумеваемая годовая доходность за 10 лет: рост выручки в год × выходной EV/S** "
          "(EV_T = EV/S × Выручка₀ × (1+g)^10; цена_T = (EV_T − чистый долг) / акции)", "",
          "| рост \\ EV/S | " + " | ".join(str(m) for m in GRID_EV_S) + " |", "|---|" + "---|" * len(GRID_EV_S)]
    for g_ in GRID_GROWTH:
        cells = [(pc(v) if not is_ref(v) else "ОТКАЗ:" + v["refused"]) for v in (d["grid_ev_s"][(g_, m)] for m in GRID_EV_S)]
        L.append("| %d%% | %s |" % (round(g_ * 100), " | ".join(cells)))
    if d["ps_mode"]:
        L += ["", "**Таблица 1а. Путь по капитализации (P/S вместо EV/S): " + PS_NOTE_TEXT + ".** Чистый долг в расчёте не участвует. "
              "Деньги на конец ФГ %s: %s (SEC %s, тег %s) -- справочно, как условие включения пути. Текущий P/S = капитализация / выручка = %s." % (
                  D["fy"], usd(d["cash_val"]), D["cash"].get("accn"), D["cash"].get("tag"), "ОТКАЗ" if d["ps"] is None else "%.2f" % d["ps"]),
              "(цена_T = P/S × Выручка₀ × (1+g)^10 / акции; число акций неизменно)", "",
              "| рост \\ P/S | " + " | ".join(str(m) for m in GRID_PS) + " |", "|---|" + "---|" * len(GRID_PS)]
        for g_ in GRID_GROWTH:
            cells = [(pc(v) if not is_ref(v) else "ОТКАЗ:" + v["refused"]) for v in (d["grid_ps"][(g_, m)] for m in GRID_PS)]
            L.append("| %d%% | %s |" % (round(g_ * 100), " | ".join(cells)))
    else:
        L += ["", "Путь по капитализации (P/S): не включён -- %s." % d["ps_reason"]]
    L += ["", "**Таблица 2. То же: рост чистой прибыли в год × выходной P/E** (маржа неизменна; NI₀ = %s)" % (
        "ОТКАЗ" if _v(D["raw"].get("net_income")) is None else usd(_v(D["raw"]["net_income"]))), "",
        "| рост \\ P/E | " + " | ".join(str(m) for m in GRID_PE) + " |", "|---|" + "---|" * len(GRID_PE)]
    for g_ in GRID_GROWTH:
        cells = [(pc(v) if not is_ref(v) else "ОТКАЗ:" + v["refused"]) for v in (d["grid_pe"][(g_, m)] for m in GRID_PE)]
        L.append("| %d%% | %s |" % (round(g_ * 100), " | ".join(cells)))
    L += ["", "**Ориентир «что даёт пассив»** — доходность за N лет до %s по Tiingo adjClose (с учётом дивидендов и сплитов):" % D["as_of"], "",
          "| | 1 год | 3 года (в год) | 5 лет (в год) |", "|---|---|---|---|"]
    for b in fc.BENCH_RS:
        cells = []
        for n, _ in PASSIVE_WINDOWS:
            r = D["passive"][b][n]
            cells.append(ref_text(r) if is_ref(r) else ("%s за период; %s в год [adjClose %s..%s]" % (pc(r["total"]), pc(r["annual"]), r["d0"], r["d1"])))
        L.append("| %s | %s |" % (b, " | ".join(cells)))
    L += ["", "**Обратный DCF** (функция ivc старого конвейера, бисекция; порог %d%%, 10 лет, fade на годах 6–10 к min(4%%, g), "
         "разводнение 0, дивиденды 0): какой рост базы на акцию уже заложен в цену при выходном P/E:" % round(HURDLE * 100), "",
         "| База \\ выходной P/E | " + " | ".join(str(m) for m in GRID_PE) + " |", "|---|" + "---|" * len(GRID_PE)]
    for leg, title, base in (("gaap_eps", "GAAP EPS", d["eps"]), ("fcf_per_share", "FCF/акцию", d["fcf_ps"])):
        cells = []
        for pe in GRID_PE:
            r = d["rdcf"][(leg, pe)]
            cells.append(("ОТКАЗ:" + r["refused"]) if is_ref(r) else pp(r["g"]))
        L.append("| %s (%s) | %s |" % (title, "ОТКАЗ" if base is None else "%.4f USD" % base, " | ".join(cells)))
    first_ref = next((r for r in d["rdcf"].values() if is_ref(r)), None)
    if first_ref:
        L += ["", "Причина первого отказа обратного DCF: " + first_ref["reason"]]
    return L


def truth_refute(D):
    """Блок (д): только формулы от данных. -> (строки 'что должно быть правдой', строки 'что опровергнет')."""
    d = D["derived"]
    gr = d["g_req"]
    T, X = [], []
    gp = d["g_req_ps"]
    if is_ref(gr):
        T.append("ОТКАЗ %s: %s" % (gr["refused"], gr["reason"]))
        if d["ps_mode"]:
            T.append("Путь по капитализации (%s): при неизменном P/S = %.2f капитал даёт %d%% годовых 10 лет, только если выручка растёт "
                     "**%s в год** (при неизменном P/S и числе акций это тождественно порогу: рост капитализации = рост выручки)." % (
                         PS_NOTE_TEXT, d["ps"], round(HURDLE * 100), pp(gp)))
            for k in (0.5, 1.5):
                r = d["g_req_ps_sens"][k]
                T.append("Путь по капитализации: при выходном P/S, равном %s от нынешнего (%.2f): нужен рост выручки %s в год." % (
                    "половине" if k == 0.5 else "1,5-кратному", d["ps"] * k, ref_text(r) if is_ref(r) else pp(r)))
    else:
        T.append("Чтобы цена %s дала %d%% годовых 10 лет при неизменном EV/S = %.2f: выручка должна расти **%s в год** 10 лет."
                 % (D["price_date"], round(HURDLE * 100), d["ev_s"], pp(gr)))
        for k in (0.5, 1.5):
            r = d["g_req_sens"][k]
            T.append("При выходном EV/S, равном %s от нынешнего (%.2f): нужен рост выручки %s в год." % (
                "половине" if k == 0.5 else "1,5-кратному", d["ev_s"] * k, ref_text(r) if is_ref(r) else pp(r)))
    if d["fcf_ni"] is None:
        T.append("Денежная конвертация: " + ref_text(refusal("MISSING_INPUT", "FCF/NI не определено (нет OCF/capex или NI <= 0)")))
    else:
        T.append("Прибыль должна превращаться в деньги: FCF/NI за ФГ %s = %.2f (порог CASH_DECAY %s)." % (D["fy"], d["fcf_ni"], cd.FCF_NI_MIN))
    base_g = gr if not is_ref(gr) else (gp if d["ps_mode"] and not is_ref(gp) else None)
    if base_g is not None:
        gr = base_g
        thr = gr - 0.05
        yy = d["yoy"]
        now = "; ".join("%s: %s" % (e, pc(g)) for e, g in yy) if yy else "ОТКАЗ: нужны 3 соседних ФГ выручки"
        X.append("Рост выручки ниже **%s** (= %s − 5 п.п.%s) два ФГ подряд. Сейчас, последние два ФГ: %s." % (
            pp(thr), pp(gr), "; порог по капитализации, не по стоимости компании" if is_ref(d["g_req"]) else "", now))
    else:
        X.append("Порог роста выручки: " + ref_text(gr))
    X.append("FCF/NI < %s (порог CASH_DECAY). Сейчас: %s." % (cd.FCF_NI_MIN, "ОТКАЗ (не определено)" if d["fcf_ni"] is None else "%.2f" % d["fcf_ni"]))
    return T, X


def sec_d(D):
    T, X = truth_refute(D)
    return ["## (д) ЧТО ДОЛЖНО БЫТЬ ПРАВДОЙ / ЧТО ОПРОВЕРГНЕТ", "", "Генерируется формулами из чисел раздела (г); суждений нет. Порог 12% и горизонт "
            "10 лет — параметры мандата.", "", "**Что должно быть правдой:**"] + ["- " + x for x in T] + ["", "**Что опровергнет:**"] + ["- " + x for x in X]


def sec_e(D):
    return ["## (е) Время машины и хэш входа", "", "- Время машины (от чтения SEC до готового отчёта): %s с (предел гейта: 7200 с)" % D["seconds"],
            "- Хэш входа (sha256 фактов SEC, цен бенчмарков и точки цены): `%s`" % D["input_hash"],
            "- Источники: SEC EDGAR через адаптер К2 (edgartools==%s), Tiingo; as_of %s; цены строго <= as_of." % (fc.load_sec_modules()[1].EDGARTOOLS_PIN, D["as_of"])]


def render_machine(D):
    head = ["# Досье (machine) — %s, срез %s" % (D["ticker"], D["as_of"]), "",
            "%s (CIK %s). Сгенерировано `tools/dossier.py` (К6 ч. A). Детерминированно, модели не вызывались. Вердикта нет: решение за оператором." % (
                D["entity"] or "название: ОТКАЗ (нет в SEC-ответе)", D["cik"] or "ОТКАЗ"), ""]
    if D.get("debt_chain_forced_v2") and not fc.debt_chain_is_v2(D["as_of"]):
        head += ["Цепочка долга: v2 применена принудительно (флаг --debt-chain-v2) при as_of %s < %s — исключение для пересборки досье; "
                 "обычные срезы до %s считаются по прежней цепочке." % (D["as_of"], fc.DEBT_CHAIN_V2_FROM, fc.DEBT_CHAIN_V2_FROM), ""]
    body = []
    for fn in (sec_a, sec_b, sec_c, sec_g, sec_d, sec_e):
        body += fn(D) + [""]
    return "\n".join(head + body)


# ----------------------------------------------------------------------------- brief

def guard_words(D):
    v = D["guard"]["verdict"]
    return {cd.RED: "горит красным", cd.AMBER: "тлеет (жёлтый)", cd.OK: "в норме", cd.NOT_APPLICABLE: "не применим",
            cd.UNDEFINED: "не определён"}.get(v, v)


def refusal_summary(D):
    """Первая строка раздела «Чего машина не знает» (DECISION_2026-11-02_DOSSIER_COMPLETENESS §3): число отказов и их классы
    по полям этажа 1: «N отказов из M полей: КЛАСС k, …». Классы берутся из кода отказа поля, не из текста; по убыванию, затем по имени."""
    codes = {}
    for name in fc.FIELD_ORDER:
        f = D["card"]["fields"][name]
        if not fc.is_ok(f):
            codes[f["refused"]] = codes.get(f["refused"], 0) + 1
    n = sum(codes.values())
    tail = ", ".join("%s %d" % (c, k) for c, k in sorted(codes.items(), key=lambda x: (-x[1], x[0])))
    return "%d отказов из %d полей%s" % (n, len(fc.FIELD_ORDER), ": " + tail if tail else "")


def render_brief(D):
    d = D["derived"]
    T, X = truth_refute(D)
    fy = D["fy"]
    L = ["# Досье для человека — %s, срез %s" % (D["ticker"], D["as_of"]), "", "## 1. Что за компания", "",
         "%s, последний годовой отчёт — за ФГ, закончившийся %s (подан до %s). Источник: SEC." % (
             D["entity"] or "название — ОТКАЗ: SEC не вернул", fy or "ОТКАЗ: нет годовых данных", D["as_of"]), "",
         "## 2. Три главных числа", ""]
    gr = d["g_req"]
    if is_ref(gr) and d["ps_mode"] and not is_ref(d["g_req_ps"]):
        s_lo, s_hi = d["g_req_ps_sens"][0.5], d["g_req_ps_sens"][1.5]
        L.append("1. Рост выручки, нужный для 12%% в год 10 лет (%s). Если оценка капитала к выручке (P/S) не изменится, нужен ровно порог "
                 "**%s в год** -- это тождество, не открытие. Содержательно другое: при P/S вдвое ниже нынешнего нужно %s в год, при "
                 "P/S в 1,5 раза выше -- %s в год. По стоимости компании (EV/S): %s." % (
                     PS_NOTE_TEXT, pp(d["g_req_ps"]), ref_text(s_lo) if is_ref(s_lo) else pp(s_lo),
                     ref_text(s_hi) if is_ref(s_hi) else pp(s_hi), ref_text(gr)))
    else:
        L.append("1. Рост выручки, который уже заложен в цену (чтобы получить 12%% в год 10 лет, если оценка компании к выручке не изменится): %s." %
                 (ref_text(gr) if is_ref(gr) else "**%s в год**" % pp(gr)))
    L.append("2. Сколько прибыли превращается в свободные деньги (FCF/NI за ФГ): %s." %
             ("ОТКАЗ: не определено" if d["fcf_ni"] is None else "**%.2f**" % d["fcf_ni"]))
    r5 = D["passive"]["VOO"][5]
    r5q = D["passive"]["QQQ"][5]
    L.append("3. Что давал пассивный индекс за 5 лет до среза (в год): VOO %s, QQQ %s." % (
        ref_text(r5) if is_ref(r5) else "**%s**" % pc(r5["annual"]), ref_text(r5q) if is_ref(r5q) else "**%s**" % pc(r5q["annual"])))
    L += ["", "## 3. Сторожа: что горит и почему", "", "- Сторож «деньги не догоняют прибыль» (CASH_DECAY): **%s**. %s" % (guard_words(D), D["guard"].get("reason")),
          "  Улика: %s" % (D["guard"].get("evidence") or "нет")]
    for name in fc.FLAG_ORDER:
        f = D["card"]["flags"].get(name) or {}
        L.append("- %s: %s. %s" % (name, f.get("state", "не вычислен"), f.get("evidence") or f.get("reason") or ""))
    L += ["", "## 4. Что должно быть правдой / что опровергнет", ""] + ["- " + x for x in T] + ["- Опровергнет: " + x for x in X]
    L += ["", "## 5. Чего машина не знает", "", refusal_summary(D),
          "- Non-GAAP показатели компании: не проверено машиной (в XBRL us-gaap их нет).",
          "- Будущее: сетка и обратный DCF — арифметика от допущений (множитель, горизонт, неизменные акции и долг), не прогноз."]
    refs = []
    for name in fc.FIELD_ORDER:
        f = D["card"]["fields"][name]
        if not fc.is_ok(f):
            refs.append("%s — %s: %s" % (name, f["refused"], f["reason"]))
    L += ["- Поля этажа 1 без значения (названные отказы): " + ("; ".join(refs) if refs else "нет")]
    L += ["", "Решение о покупке или отказе — за оператором; досье вердикта не содержит. Подробности и accession — в `%s_%s_machine.md`." % (D["ticker"], D["as_of"])]
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------------- CLI

def write_new(path, text):
    with open(path, "x", encoding="utf-8") as fh:      # существующий файл не перезаписывается (append-only)
        fh.write(text)


def main(argv=None, source=None, fetch=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--debt-chain-v2", action="store_true",
                    help="цепочка долга v2 при любом as_of (исключение для пересборки досье до 2026-11-14, DECISION_2026-11-04 §2/v1 §4)")
    a = ap.parse_args(argv)
    try:
        dt.date.fromisoformat(a.as_of)
    except ValueError:
        print("ОТКАЗ: --as-of должен быть YYYY-MM-DD", file=sys.stderr)
        return 2
    if source is None:
        token = os.environ.get("TIINGO_TOKEN") or ""
        if not token or not (os.environ.get("SEC_USER_AGENT") or "").strip():
            print("ОТКАЗ: нужны env TIINGO_TOKEN и SEC_USER_AGENT; досье НЕ записано.", file=sys.stderr)
            return 2
        source = fc.LiveSource(a.as_of)
        fetch = lambda t: tiingo_series(t, token, a.as_of)     # noqa: E731
    D = build(a.ticker.upper(), a.as_of, source, fetch, force_v2=a.debt_chain_v2)
    os.makedirs(a.out_dir, exist_ok=True)
    base = os.path.join(a.out_dir, "%s_%s" % (D["ticker"], a.as_of))
    try:
        write_new(base + "_machine.md", render_machine(D))
        write_new(base + "_brief.md", render_brief(D))
    except FileExistsError as e:
        print("ОТКАЗ: файл уже существует (append-only, не перезаписываю): %s" % e.filename, file=sys.stderr)
        return 2
    print("досье: %s_{machine,brief}.md; время машины %s с; хэш входа %s" % (base, D["seconds"], D["input_hash"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
