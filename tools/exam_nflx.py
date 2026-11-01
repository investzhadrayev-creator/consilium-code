#!/usr/bin/env python3
"""К4 часть A: экзамен NFLX-FY2019 и контроли сторожа CASH_DECAY.

Правила -- mailbox/PREREG_2026-11-01_K4_NFLX_CASH_DECAY.md §5, §6. Этот файл ничего к ним не добавляет.

    SEC_USER_AGENT="Имя email" python3 tools/exam_nflx.py [--part exam|controls|all] [--out-dir Reports/exam]

ЖИВОЙ ПРОГОН -- ОТДЕЛЬНАЯ ЗАДАЧА ПОСЛЕ СЛИЯНИЯ (PREREG §7). Тесты не вызывают main() с реальным источником;
Reports/exam/* в PR с кодом не коммитится.

Загрузка -- только через адаптер К2 (tools/floor1_card.LiveSource: edgartools==5.48.0, SEC_USER_AGENT).
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "guards"))

import cash_decay as cd   # noqa: E402

EXAM = {"ticker": "NFLX", "as_of": "2020-02-15", "fy": "2019"}     # заморожено в PREREG_2026-10-11 v2
CONTROLS = [("META", "2021-02-15")] + [(t, d) for t in ("MA", "SPGI", "MSFT")
                                       for d in ("2020-02-15", "2022-02-15", "2024-02-15")]
MAX_SECONDS = 2 * 3600                                               # PREREG §5: время машины <= 2 ч


# ----------------------------------------------------------------------------- загрузка фактов

def _series(out, name):
    return out.get(name + "_audit") or out.get(name)     # тот же порядок, что в floor1_card.sec_fields


def load_facts(source, ticker, as_of):
    """-> (facts|None, cik, причина|None). Ряды как отдал адаптер К2; срез filed<=as_of сторож делает сам."""
    source.as_of = as_of          # LiveSource режет факты по своему as_of: на каждый снимок -- его дата
    out, sec_facts, cik = source.read(ticker)
    if out.get("_errors"):
        return None, cik, "адаптер К2: %s" % json.dumps(out["_errors"], ensure_ascii=False, sort_keys=True)
    capex = _series(out, "capex")
    if not capex and sec_facts is not None:               # штатных тегов capex нет вовсе: запасной тег цепочки этажа 1
        import floor1_card as fc
        ef, _ = fc.load_sec_modules()
        capex, _, _, _ = ef._annual_merged(sec_facts, fc.CAPEX_FALLBACK_TAGS)
    return {"ni": _series(out, "net_income"), "ocf": _series(out, "ocf"), "capex": capex,
            "revenue": _series(out, "revenue")}, cik, None


def input_hash(facts):
    return hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def check_filing_metadata(source, cik, as_of, fy):
    """PREREG §5: до прогона -- ТОЛЬКО метаданные: 10-K за ФГ<fy> подан <= as_of (по списку подач)."""
    try:
        listing = source.listing(cik)
    except Exception as e:      # список недоступен -- экзамен не проводится, причина записывается
        return {"ok": False, "reason": "список подач не прочитан: %s: %s" % (type(e).__name__, str(e)[:120])}
    hit = source.ad.select_filing(listing, as_of, source.ad.ANNUAL_FORMS)
    if hit is None:
        return {"ok": False, "reason": "нет годовой формы 10-K с filing_date <= %s" % as_of}
    if not str(hit.get("period_of_report") or "").startswith(fy):
        return {"ok": False, "accession": hit.get("accession"), "filing_date": hit.get("filing_date"),
                "reason": "последний 10-K с filing_date <= %s относится к периоду %s, а не к ФГ%s"
                          % (as_of, hit.get("period_of_report"), fy)}
    return {"ok": True, "accession": hit["accession"], "filing_date": str(hit["filing_date"]),
            "period_of_report": hit["period_of_report"], "reason": ""}


def run_snapshot(source, ticker, as_of):
    facts, cik, why = load_facts(source, ticker, as_of)
    if facts is None:
        return {"ticker": ticker, "as_of": as_of, "cik": cik, "verdict": cd.UNDEFINED, "rule": None,
                "reason": why, "evidence": None, "input_hash": None}
    res = cd.evaluate(facts, as_of)
    return dict(res, ticker=ticker, cik=cik, input_hash=input_hash(facts))


# ----------------------------------------------------------------------------- экзамен

def run_exam(source, started=None):
    """-> dict результата. Повторный прогон (перечитывание + оценка) должен дать тот же вердикт и тот же хэш входа."""
    t0 = time.monotonic() if started is None else started
    tk, as_of, fy = EXAM["ticker"], EXAM["as_of"], EXAM["fy"]
    cik = None
    try:
        cik = source.ef._resolve_cik(tk)
    except Exception:
        pass
    meta = check_filing_metadata(source, cik, as_of, fy) if cik else {"ok": False, "reason": "CIK не найден"}
    if not meta["ok"]:
        return {"ticker": tk, "as_of": as_of, "meta": meta, "verdict": cd.UNDEFINED, "rule": None,
                "reason": "экзамен не проводился: " + meta["reason"], "evidence": None, "reproducible": None,
                "seconds": round(time.monotonic() - t0, 1), "within_limit": True, "diagnostics": [], "notes": [],
                "input_hash": None}
    first = run_snapshot(source, tk, as_of)
    second = run_snapshot(source, tk, as_of)
    secs = round(time.monotonic() - t0, 1)
    first.update(meta=meta, seconds=secs, within_limit=secs <= MAX_SECONDS,
                 reproducible=(first["verdict"], first["input_hash"]) == (second["verdict"], second["input_hash"]))
    return first


def gate_line(res):
    ok = res["verdict"] == cd.RED and res["evidence"] and res.get("reproducible") and res.get("within_limit")
    return "ГЕЙТ: %s" % ("ПРОЙДЕН" if ok else "ПРОВАЛ (публикуется как провал, правило не подкручивается)")


def _diag_table(diag):
    lines = ["| конец ФГ | OCF/NI | capex/OCF | FCF/NI | почему не определено |", "|---|---|---|---|---|"]
    f = lambda v: "—" if v is None else "%.2f" % v
    for r in diag:
        lines.append("| %s | %s | %s | %s | %s |" % (r["end"] or "нет фактов", f(r["ocf_to_ni"]), f(r["capex_to_ocf"]),
                                                    f(r["fcf_to_ni"]), "; ".join("%s: %s" % kv for kv in sorted(r["why"].items())) or ""))
    return lines


def render_exam(res, run_date, command):
    L = ["# NFLX ФГ2019 — экзамен сторожа CASH_DECAY (прогон %s)" % run_date, "",
         "ВЕРДИКТ: %s" % res["verdict"], gate_line(res), "",
         "- Правило: %s. Причина: %s" % (res.get("rule") or "—", res.get("reason") or "—"),
         "- Улика: %s" % (res.get("evidence") or "нет"),
         "- as_of: %s; ФГ (конец): %s" % (res["as_of"], res.get("fiscal_year_end") or "—"),
         "- Подача 10-K (метаданные до прогона): %s" % json.dumps(res["meta"], ensure_ascii=False, sort_keys=True),
         "- Воспроизводимо (повторное чтение даёт тот же вердикт и хэш входа): %s" % res.get("reproducible"),
         "- Время машины: %s с (лимит %d с; в пределах: %s)" % (res.get("seconds"), MAX_SECONDS, res.get("within_limit")),
         "- Хэш входа (sha256 канонического JSON рядов NI/OCF/capex/выручка): %s" % res.get("input_hash"),
         "- Команда: `%s`" % command, "", "## Диагностика (в решение не входит), 5 ФГ", ""]
    L += _diag_table(res.get("diagnostics") or [])
    if res.get("notes"):
        L += ["", "## Замечания среза"] + ["- %s" % n for n in res["notes"]]
    L += ["", "Оговорка PREREG §2: слепого экзамена нет; правило знает ответ. Экзамен проверяет, что машина сама достаёт числа SEC "
          "и выносит RED с уликой, и что правило не завязано на capex."]
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------------- контроли

def run_controls(source, controls=CONTROLS):
    return [run_snapshot(source, t, d) for t, d in controls]


def false_red_share(rows):
    """PREREG §6: (число RED) / число контролей (10). НЕ_ОПРЕДЕЛЁН не прячется в знаменателе -- считается отдельно."""
    return sum(1 for r in rows if r["verdict"] == cd.RED), len(rows)


def render_controls(rows, run_date, command):
    n_red, n = false_red_share(rows)
    n_undef = sum(1 for r in rows if r["verdict"] == cd.UNDEFINED)
    L = ["# Контроли сторожа CASH_DECAY (прогон %s)" % run_date, "",
         "ДОЛЯ ЛОЖНЫХ RED: %d/%d = %.0f%%" % (n_red, n, 100.0 * n_red / n if n else 0),
         "НЕ_ОПРЕДЕЛЁН: %d/%d (не OK и не проход: сторож на этих снимках не высказался)" % (n_undef, n), "",
         "| тикер | as_of | вердикт | правило | причина | улика | хэш входа |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %s | %s | %s | %s | %s | %s |" % (r["ticker"], r["as_of"], r["verdict"], r.get("rule") or "—",
                                                          (r.get("reason") or "—").replace("|", "/"),
                                                          (r.get("evidence") or "—").replace("|", "/"), r.get("input_hash") or "—"))
    L += ["", "- Команда: `%s`" % command,
          "- Любой RED на контроле — ограничение сторожа с разбором механизма (PREREG §6); правило задним числом не меняется.",
          "- Провал контроля гейт не валит."]
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------------- main

def main(argv=None, source=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--part", choices=("exam", "controls", "all"), default="all")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "Reports", "exam"))
    ap.add_argument("--run-date", default=dt.date.today().isoformat())
    args = ap.parse_args(argv)
    command = "python3 tools/exam_nflx.py " + " ".join(argv if argv is not None else sys.argv[1:])
    if source is None:
        import floor1_card as fc
        try:
            source = fc.LiveSource(EXAM["as_of"])     # бросит, если SEC_USER_AGENT не задан -- не выдумываем
        except Exception as e:
            print("ОТКАЗ: источник SEC недоступен: %s: %s" % (type(e).__name__, e), file=sys.stderr)
            return 2
    os.makedirs(args.out_dir, exist_ok=True)
    written = []
    if args.part in ("exam", "all"):
        p = os.path.join(args.out_dir, "NFLX_FY2019_%s.md" % args.run_date)
        _write_new(p, render_exam(run_exam(source), args.run_date, command))
        written.append(p)
    if args.part in ("controls", "all"):
        p = os.path.join(args.out_dir, "CASH_DECAY_CONTROLS_%s.md" % args.run_date)
        _write_new(p, render_controls(run_controls(source), args.run_date, command))
        written.append(p)
    print("\n".join(written))
    return 0


def _write_new(path, text):
    """Append-only: результат прогона не перезаписывается (журнал первого прогона остаётся)."""
    with open(path, "x", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    sys.exit(main())
