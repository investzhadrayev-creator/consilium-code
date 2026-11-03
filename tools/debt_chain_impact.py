#!/usr/bin/env python3
"""Отчёт влияния DECISION_2026-11-02_DEBT_CHAIN §3: прежняя и новая цепочка долга на всех именах watchlist.

    SEC_USER_AGENT="Имя email" python3 tools/debt_chain_impact.py --as-of 2026-10-31 --out mailbox/REPORT_2026-11-03_DEBT_CHAIN_IMPACT.md

Числа берутся с выхода tools/floor1_card.py (build_name: поле net_debt_latest и meta.net_debt_prev_chain), ничего не пересчитывается
вручную. Цены не нужны (Tiingo не вызывается). Существующий файл не перезаписывается (append-only). Отказ нового правила там, где
прежнее давало число, выводится отдельным списком «пробел по нашей вине»."""
import argparse
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import floor1_card as fc    # noqa: E402


def usd(f):
    return format(round(f["value"]), ",") if fc.is_ok(f) else "—"


def line(ticker, new, old):
    """-> (строка таблицы, категория). Категории: SAME / CHANGED / FLAG / LOST (число -> отказ) / BOTH_REFUSED / GAINED."""
    flags = new.get("debt_flags") if fc.is_ok(new) else None
    flag = "; ".join("DEBT_TAG_INCONSISTENT: %s=%s vs части=%s" % (x["full_tag"], format(round(x["full_val"]), ","),
                                                                   format(round(x["parts_sum"]), ",")) for x in flags or []) or "—"
    if fc.is_ok(new) and fc.is_ok(old):
        o, n = old["value"], new["value"]
        pct = "%+.1f%%" % (100.0 * (n - o) / abs(o)) if o else ("0.0%" if n == 0 else "н/д (старое = 0)")
        reason = new["basis"].split("теги: ")[-1]
        cat = "SAME" if o == n else "CHANGED"
    elif fc.is_ok(old):
        pct, reason, cat = "—", "ОТКАЗ новой цепочки %s: %s" % (new["refused"], new["reason"]), "LOST"
    elif fc.is_ok(new):
        pct, reason, cat = "—", "старая цепочка отказ %s: %s; новая даёт число" % (old["refused"], old["reason"]), "GAINED"
    else:
        pct, reason, cat = "—", "отказ в обеих: старая %s, новая %s: %s" % (old["refused"], new["refused"], new["reason"]), "BOTH_REFUSED"
    return "| %s | %s | %s | %s | %s | %s |" % (ticker, usd(old), usd(new), pct, flag, reason), cat, bool(flags)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tickers", default="")
    a = ap.parse_args(argv)
    if os.path.exists(a.out):
        print("ОТКАЗ: %s уже существует (append-only); исправление — новым файлом с supersedes" % a.out, file=sys.stderr)
        return 2
    if not (os.environ.get("SEC_USER_AGENT") or "").strip():
        print("ОТКАЗ: нужен env SEC_USER_AGENT", file=sys.stderr)
        return 2
    names = [t for t in a.tickers.split(",") if t] or fc.read_watchlist(fc.WATCHLIST)
    src = fc.LiveSource(a.as_of)
    rows, cats = [], {}
    for i, t in enumerate(names, 1):
        r = fc.build_name(t, a.as_of, src, None, {}, "цены не нужны для отчёта по долгу")
        old = r["meta"].get("net_debt_prev_chain")
        new = r["fields"]["net_debt_latest"]
        if old is None:         # имя вне scope / SEC недоступен: обе цепочки не вычислялись
            old = new
        text, cat, flagged = line(t, new, old)
        rows.append(text)
        cats.setdefault(cat, []).append(t)
        if flagged:
            cats.setdefault("FLAG", []).append(t)
        print("[%d/%d] %s %s" % (i, len(names), t, cat), file=sys.stderr)
    L = ["# REPORT %s — влияние цепочки долга по DECISION_2026-11-02_DEBT_CHAIN §3" % dt.datetime.now(dt.timezone.utc).date().isoformat(), "",
         "Сгенерировано `tools/debt_chain_impact.py` (вывод `tools/floor1_card.py`: поле net_debt_latest и прежняя цепочка из той же "
         "функции-двойника). as_of SEC = %s; имён: %d; edgartools==%s; сформировано %s UTC. Значения — чистый долг в USD "
         "(долг минус Cash&Equivalents, ФГ последней карточки). Числа этого файла напечатаны инструментом, не набраны вручную." % (
             a.as_of, len(names), src.ad.EDGARTOOLS_PIN, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")), "",
         "## Итог", "",
         "- без изменения: %d (%s)" % (len(cats.get("SAME", [])), ", ".join(cats.get("SAME", [])) or "—"),
         "- значение изменилось: %d (%s)" % (len(cats.get("CHANGED", [])), ", ".join(cats.get("CHANGED", [])) or "—"),
         "- флаг DEBT_TAG_INCONSISTENT: %d (%s)" % (len(cats.get("FLAG", [])), ", ".join(cats.get("FLAG", [])) or "—"),
         "- **число -> отказ (пробел по нашей вине, в знаменателе (Б))**: %d (%s)" % (len(cats.get("LOST", [])), ", ".join(cats.get("LOST", [])) or "—"),
         "- отказ -> число: %d (%s)" % (len(cats.get("GAINED", [])), ", ".join(cats.get("GAINED", [])) or "—"),
         "- отказ в обеих цепочках: %d (%s)" % (len(cats.get("BOTH_REFUSED", [])), ", ".join(cats.get("BOTH_REFUSED", [])) or "—"), "",
         "## Таблица", "", "| имя | старое | новое | разница % | флаг | отказ/причина (теги нового) |", "|---|---|---|---|---|---|"] + rows + [""]
    with open(a.out, "x", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print("отчёт: %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
