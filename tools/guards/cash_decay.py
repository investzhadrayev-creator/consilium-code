"""К4 часть A: сторож CASH_DECAY -- чистая функция «годовые факты -> вердикт + улика».

Источник правил: mailbox/PREREG_2026-11-01_K4_NFLX_CASH_DECAY.md (§3, §4). Ничего сверх него.
Правило -- заранее объявленная эвристика; менять пороги можно только новым PREREG с supersedes.

Вход (`facts`): четыре годовых ряда, каждый -- список записей
    {"end": "YYYY-MM-DD", "val": число (USD), "accn": "0001065280-20-000012", "filed": "YYYY-MM-DD", ["unit": "USD"]}
    ni      -- NetIncomeLoss
    ocf     -- NetCashProvidedByUsedInOperatingActivities
    capex   -- PaymentsToAcquirePropertyPlantAndEquipment (запасной тег подбирает загрузчик, не сторож)
    revenue -- цепочка выручки К2
Функция НЕ ходит в сеть и не знает про теги: загрузка -- tools/exam_nflx.py через адаптер К2.

Три инварианта проекта, воплощённые здесь:
  * filed <= as_of проверяется ЗДЕСЬ, независимо от загрузчика (§3): запись без filed не доказывает срез и не используется.
  * Нет факта -> вердикт НЕ_ОПРЕДЕЛЁН с причиной. Никогда не OK и не «0 по умолчанию».
  * Каждое число улики несёт accession.
"""
import datetime as _dt

RED, AMBER, OK, NOT_APPLICABLE, UNDEFINED = "RED", "AMBER", "OK", "NOT_APPLICABLE", "НЕ_ОПРЕДЕЛЁН"
VERDICTS = (RED, AMBER, OK, NOT_APPLICABLE, UNDEFINED)

FCF_NI_MIN = 0.5          # PREREG §4: «меньше половины прибыли превращается в свободные деньги»
NA_REVENUE_SHARE = 0.01   # PREREG §4: NI < 1% выручки -- отношения бессмысленны
DROP_VS_MEDIAN = 0.5      # PREREG §4: падение FCF/NI больше чем на 0,5 против медианы трёх предыдущих ФГ
N_DIAG = 5                # PREREG §4: диагностика за 5 ФГ
FY_DAYS = (350, 380)      # годовой период: календарный или 52/53 недели (как ANNUAL_DAYS адаптера К2)
FY_MATCH_DAYS = 21        # концы ФГ разных рядов одного ФГ различаются не более чем на это
FIELDS = ("ni", "ocf", "capex", "revenue")


def _d(s):
    return _dt.date.fromisoformat(str(s)[:10])


def _undefined(reason, **extra):
    out = {"verdict": UNDEFINED, "rule": None, "reason": reason, "evidence": None}
    out.update(extra)
    return out


# ----------------------------------------------------------------------------- срез по as_of

def slice_as_of(series, as_of):
    """-> ({end: запись}, [замечания]). На каждый конец ФГ -- запись с наибольшим filed среди filed <= as_of.
    Запись без filed / val / accn исключается (срез недоказуем, либо число без provenance) -- и это видно в замечаниях."""
    best, notes = {}, []
    for r in series or []:
        if not isinstance(r, dict) or not r.get("end"):
            notes.append("запись без end пропущена")
            continue
        if not r.get("filed"):
            notes.append("ФГ %s: нет даты подачи -- срез filed<=as_of недоказуем, запись не использована" % r["end"])
            continue
        if str(r["filed"]) > as_of:
            notes.append("ФГ %s: подана %s > as_of %s -- не использована" % (r["end"], r["filed"], as_of))
            continue
        if r.get("val") is None or not r.get("accn"):
            notes.append("ФГ %s: нет значения или accession -- не использована" % r["end"])
            continue
        if r.get("unit") not in (None, "USD"):
            notes.append("ФГ %s: единица %s, не USD -- не использована" % (r["end"], r.get("unit")))
            continue
        if r["end"] not in best or (str(r["filed"]), str(r["accn"])) > (str(best[r["end"]]["filed"]), str(best[r["end"]]["accn"])):
            best[r["end"]] = r
    return best, notes


def _build_years(facts, as_of):
    """-> (годы [FG0, FG-1, ... FG-(N_DIAG-1)] как dict с полями ni/ocf/capex/revenue (запись или None) и end, notes)."""
    sliced, notes = {}, []
    for f in FIELDS:
        sliced[f], n = slice_as_of((facts or {}).get(f), as_of)
        notes += ["%s: %s" % (f, x) for x in n]
    ends = sorted({e for f in FIELDS for e in sliced[f]})
    if not ends:
        return [], notes

    def at(anchor):
        out = {"end": anchor}
        for f in FIELDS:
            near = [e for e in sliced[f] if abs((_d(e) - _d(anchor)).days) <= FY_MATCH_DAYS]
            out[f] = sliced[f][max(near)] if near else None
        return out

    years, prev = [at(ends[-1])], _d(ends[-1])
    for _ in range(N_DIAG - 1):
        cand = [e for e in ends if FY_DAYS[0] <= (prev - _d(e)).days <= FY_DAYS[1]]
        if cand:
            years.append(at(max(cand)))
            prev = _d(max(cand))
        else:
            prev = prev - _dt.timedelta(days=365)
            years.append({"end": None, **{f: None for f in FIELDS}})   # ФГ без единого факта -- пустой слот, не пропуск
    return years, notes


# ----------------------------------------------------------------------------- арифметика ФГ

def _fcf(y):
    """-> (fcf|None, причина|None). Capex без знака по определению тега (выплата); отрицательный -- аномалия, отказ."""
    if y["ocf"] is None or y["capex"] is None:
        return None, "нет %s" % " и ".join(n for n, k in (("OCF", "ocf"), ("capex", "capex")) if y[k] is None)
    if y["capex"]["val"] < 0:
        return None, "capex < 0 (%s): знак не соответствует определению тега" % y["capex"]["val"]
    return y["ocf"]["val"] - y["capex"]["val"], None


def _fcf_ni(y):
    """-> (FCF/NI|None, причина|None). Определено только при NI > 0."""
    if y["ni"] is None:
        return None, "нет NI"
    if y["ni"]["val"] <= 0:
        return None, "NI <= 0"
    fcf, why = _fcf(y)
    return (None, why) if fcf is None else (fcf / y["ni"]["val"], None)


def diagnostics(years):
    """Показывается всегда, в решение не входит (§4). Неопределимое -- None + причина, не 0."""
    rows = []
    for y in years:
        row = {"end": y["end"], "ocf_to_ni": None, "capex_to_ocf": None, "fcf_to_ni": None, "why": {}}
        if y["end"] is None:
            row["why"]["all"] = "нет фактов за этот ФГ"
        else:
            if y["ni"] is None or y["ocf"] is None:
                row["why"]["ocf_to_ni"] = "нет %s" % ("NI" if y["ni"] is None else "OCF")
            elif y["ni"]["val"] <= 0:
                row["why"]["ocf_to_ni"] = "NI <= 0"
            else:
                row["ocf_to_ni"] = y["ocf"]["val"] / y["ni"]["val"]
            if y["ocf"] is None or y["capex"] is None:
                row["why"]["capex_to_ocf"] = "нет %s" % ("OCF" if y["ocf"] is None else "capex")
            elif y["ocf"]["val"] <= 0:
                row["why"]["capex_to_ocf"] = "OCF <= 0"
            else:
                row["capex_to_ocf"] = y["capex"]["val"] / y["ocf"]["val"]
            row["fcf_to_ni"], w = _fcf_ni(y)
            if w:
                row["why"]["fcf_to_ni"] = w
        rows.append(row)
    return rows


def _usd(rec):
    return "$%s [%s]" % (format(rec["val"], ",.0f"), rec["accn"])


def evidence_line(y):
    """«ФГ2019: прибыль $X; операционный поток $Y; свободный поток $Z; FCF/NI = …» с accession каждого числа."""
    fcf, why = _fcf(y)
    if fcf is None:
        fcf_s = "НЕ ОПРЕДЕЛЁН (%s)" % why
        ratio_s = "не определено"
    else:
        fcf_s = "$%s [OCF %s - capex %s]" % (format(fcf, ",.0f"), y["ocf"]["accn"], y["capex"]["accn"])
        ratio_s = "%.2f" % (fcf / y["ni"]["val"])
    return "ФГ%s (конец %s): прибыль %s; операционный поток %s; свободный поток %s; FCF/NI = %s" % (
        y["end"][:4], y["end"], _usd(y["ni"]), _usd(y["ocf"]), fcf_s, ratio_s)


def _median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


# ----------------------------------------------------------------------------- правило §4

def evaluate(facts, as_of):
    """facts + as_of -> {"verdict", "rule", "reason", "evidence", "fiscal_year_end", "diagnostics", "notes", "thresholds"}."""
    years, notes = _build_years(facts, as_of)
    base = {"notes": notes, "as_of": as_of,
            "thresholds": {"fcf_ni_min": FCF_NI_MIN, "na_revenue_share": NA_REVENUE_SHARE, "drop_vs_median": DROP_VS_MEDIAN}}
    if not years:
        return dict(base, **_undefined("нет ни одного факта с filed <= %s" % as_of, diagnostics=[]))
    y0, y1 = years[0], years[1]
    base["fiscal_year_end"] = y0["end"]
    base["diagnostics"] = diagnostics(years)

    def undefined(reason):
        return dict(base, **_undefined(reason))

    if y0["ni"] is None:
        return undefined("ФГ %s: нет NI (NetIncomeLoss) с filed <= as_of" % y0["end"])
    ni0 = y0["ni"]["val"]
    if ni0 <= 0:
        return dict(base, verdict=NOT_APPLICABLE, rule="NA_NI_NONPOSITIVE", evidence=None,
                    reason="ФГ %s: NI = %s <= 0, отношения бессмысленны" % (y0["end"], ni0))
    if y0["revenue"] is None:
        return undefined("ФГ %s: нет выручки -- порог 1%% выручки не проверить" % y0["end"])
    if ni0 < NA_REVENUE_SHARE * y0["revenue"]["val"]:
        return dict(base, verdict=NOT_APPLICABLE, rule="NA_NI_BELOW_1PCT_REVENUE", evidence=None,
                    reason="ФГ %s: NI %s < 1%% выручки %s, отношения бессмысленны" % (y0["end"], ni0, y0["revenue"]["val"]))
    if y0["ocf"] is None:
        return undefined("ФГ %s: нет OCF (NetCashProvidedByUsedInOperatingActivities)" % y0["end"])
    if y0["ocf"]["val"] < 0:
        return dict(base, verdict=RED, rule="R1", evidence=evidence_line(y0),
                    reason="R1: NI > 0 и OCF < 0 -- операции сжигают деньги при прибыли")
    r0, why0 = _fcf_ni(y0)
    if r0 is None:
        return undefined("ФГ %s: FCF/NI не вычислить (%s)" % (y0["end"], why0))

    if r0 < FCF_NI_MIN:
        if y1["ni"] is not None and y1["ni"]["val"] <= 0:
            weak1 = False          # R2 требует NI > 0 в ОБОИХ ФГ: условие не выполнено, это не пробел данных
        else:
            r1, why1 = _fcf_ni(y1)
            if r1 is None:
                return undefined("FCF/NI(ФГ0) = %.2f < %s, но ФГ-1 не оценить (%s): RED и AMBER неразличимы"
                                 % (r0, FCF_NI_MIN, why1))
            weak1 = r1 < FCF_NI_MIN
        if weak1:
            return dict(base, verdict=RED, rule="R2",
                        evidence=evidence_line(y0) + " | " + evidence_line(y1),
                        reason="R2: NI > 0 и FCF/NI < %s в обоих ФГ -- устойчиво слабая конвертация" % FCF_NI_MIN)
        return dict(base, verdict=AMBER, rule="AMBER_ONE_YEAR", evidence=evidence_line(y0),
                    reason="FCF/NI(ФГ0) = %.2f < %s только в последнем ФГ" % (r0, FCF_NI_MIN))

    prior, gaps = [], []
    for k, y in enumerate(years[1:4], start=1):
        r, why = _fcf_ni(y)
        if r is None:
            gaps.append("ФГ-%d: %s" % (k, why))
        else:
            prior.append(r)
    if gaps:
        return undefined("FCF/NI(ФГ0) = %.2f >= %s, но медиана трёх предыдущих ФГ не вычислима (%s): OK и AMBER неразличимы"
                         % (r0, FCF_NI_MIN, "; ".join(gaps)))
    med = _median(prior)
    if med - r0 > DROP_VS_MEDIAN:
        return dict(base, verdict=AMBER, rule="AMBER_DROP_VS_MEDIAN", evidence=evidence_line(y0),
                    reason="FCF/NI упал с медианы %.2f до %.2f (падение %.2f > %s)" % (med, r0, med - r0, DROP_VS_MEDIAN))
    return dict(base, verdict=OK, rule="OK", evidence=None,
                reason="FCF/NI(ФГ0) = %.2f; медиана трёх предыдущих ФГ = %.2f" % (r0, med))
