#!/usr/bin/env python3
"""Отчёт влияния DECISION_2026-11-17_DEBT_CHAIN_v2_1 (§4): цепочка v2 (до закона) против v2.1 на всех именах watchlist.
Поля долга: net_debt_latest, net_debt_chg_3y, флаг DEBT_FOR_BUYBACKS. as_of фиксируется параметром (по закону -- 2026-11-14);
v2.1 включается подменой fc.DEBT_CHAIN_V2_1_FROM на as_of в памяти процесса (код репозитория не меняется), v2 -- штатный путь
для as_of < 2026-11-28. SEC читается один раз на имя; цены не нужны (Tiingo не вызывается).

    SEC_USER_AGENT="..." python3 tools/debt_chain_v21_impact.py --as-of 2026-11-14 --out Reports/floor1/REPORT_2026-11-18_DEBT_CHAIN_v2_1_IMPACT.md

Все числа отчёта печатает инструмент (build_name), вручную ничего не набирается. Существующий файл не перезаписывается.
Выход 3, если есть хотя бы одна ячейка «число -> отказ» (условие §4 не выполнено)."""
import argparse
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import floor1_card as fc    # noqa: E402

FIELDS = ["net_debt_latest", "net_debt_chg_3y"]
CELLS = FIELDS + ["DEBT_FOR_BUYBACKS"]


class CachedSource:
    """Читает SEC один раз на имя; обе цепочки считаются по одним и тем же фактам."""
    def __init__(self, src):
        self._src, self._c, self.ef, self.ad = src, {}, src.ef, src.ad

    def read(self, t):
        if t not in self._c:
            self._c[t] = self._src.read(t)
        return self._c[t]

    def listing(self, cik):
        return self._src.listing(cik)


def cell(row, name):
    """-> (is_number, текст значения, причина-отказа). Флаг DEBT_FOR_BUYBACKS -- «число», если state != UNDETERMINED."""
    if name == "DEBT_FOR_BUYBACKS":
        f = row["flags"][name]
        det = f.get("state") != "UNDETERMINED"
        return det, (f["state"] if det else "—"), (None if det else f.get("evidence"))
    f = row["fields"][name]
    if fc.is_ok(f):
        return True, format(round(f["value"]), ","), None
    return False, "—", "%s: %s" % (f.get("refused"), f.get("reason"))


def classify(old, new):
    (on, ov, orr), (nn, nv, nr) = old, new
    if on and nn:
        return "SAME" if ov == nv else "NUM_TO_NUM"
    if on and not nn:
        return "NUM_TO_REFUSAL"
    if nn and not on:
        return "REFUSAL_TO_NUM"
    return "REFUSAL_SAME" if orr == nr else "REFUSAL_REASON_CHANGED"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tickers", default="")
    a = ap.parse_args(argv)
    if os.path.exists(a.out):
        print("ОТКАЗ: %s уже существует (append-only)" % a.out, file=sys.stderr)
        return 2
    if not (os.environ.get("SEC_USER_AGENT") or "").strip():
        print("ОТКАЗ: нужен env SEC_USER_AGENT", file=sys.stderr)
        return 2
    names = [t for t in a.tickers.split(",") if t] or fc.read_watchlist(fc.WATCHLIST)
    src = CachedSource(fc.LiveSource(a.as_of))
    real_from = fc.DEBT_CHAIN_V2_1_FROM
    counts, changed, per_name = {}, [], []
    for i, t in enumerate(names, 1):
        fc.DEBT_CHAIN_V2_1_FROM = "9999-12-31"        # v2: до закона
        old = fc.build_name(t, a.as_of, src, None, {}, "цены не нужны для отчёта по долгу")
        fc.DEBT_CHAIN_V2_1_FROM = a.as_of             # v2.1: закон «включён» на as_of
        new = fc.build_name(t, a.as_of, src, None, {}, "цены не нужны для отчёта по долгу")
        fc.DEBT_CHAIN_V2_1_FROM = real_from
        for c in CELLS:
            o, n = cell(old, c), cell(new, c)
            k = classify(o, n)
            counts[k] = counts.get(k, 0) + 1
            if k not in ("SAME", "REFUSAL_SAME"):
                changed.append((t, c, k, o, n))
        per_name.append(t)
        print("[%d/%d] %s" % (i, len(names), t), file=sys.stderr)
    assert fc.DEBT_CHAIN_V2_1_FROM == real_from
    total = len(names) * len(CELLS)
    now = dt.datetime.now(dt.timezone.utc)
    L = ["## ДЛЯ ОПЕРАТОРА",
         "- Что меняется: ничего в карточках. Это проверка по всем 34 компаниям: что изменили бы новые правила выбора подачи долга.",
         "- Тип: КОД (отчёт к закону DECISION_2026-11-17_DEBT_CHAIN_v2_1, п. 4).",
         "- Риск, если слить с ошибкой: нулевой (новый файл); неверный вывод в тексте проверит архитектор по таблице.", "",
         "# REPORT 2026-11-18 — влияние цепочки долга v2.1 (DECISION_2026-11-17 §4)", "",
         "Сгенерировано `tools/debt_chain_v21_impact.py` (вывод `build_name` из `tools/floor1_card.py`); as_of = %s; имён: %d; ячеек: %d "
         "(%s); edgartools==%s; сформировано %s UTC. «v2» = цепочка до закона, «v2.1» = выбор подачи и причина по §1–2 закона, "
         "включённые подменой даты в памяти. Цены не нужны (Tiingo не вызывался). Числа напечатаны инструментом." % (
             a.as_of, len(names), total, ", ".join(CELLS), src.ad.EDGARTOOLS_PIN, now.strftime("%Y-%m-%d %H:%M")), "",
         "## Итог", ""]
    labels = [("SAME", "без изменения (число = число)"), ("NUM_TO_NUM", "число → другое число"),
              ("NUM_TO_REFUSAL", "**число → отказ** (условие §4: должно быть 0)"), ("REFUSAL_TO_NUM", "отказ → число"),
              ("REFUSAL_REASON_CHANGED", "отказ → отказ с другой причиной"), ("REFUSAL_SAME", "отказ без изменения")]
    L += ["- %s: %d" % (lab, counts.get(k, 0)) for k, lab in labels]
    lost = counts.get("NUM_TO_REFUSAL", 0)
    L += ["", "Условие §4 (0 ячеек «число → отказ»): **%s**." % ("ВЫПОЛНЕНО" if lost == 0 else "НЕ ВЫПОЛНЕНО — код не сливается")]
    if changed:
        L += ["", "## Изменившиеся ячейки (все)", "", "| имя | ячейка | класс | v2 | v2.1 | причина (v2 → v2.1) |", "|---|---|---|---|---|---|"]
        for t, c, k, o, n in changed:
            L.append("| %s | %s | %s | %s | %s | %s |" % (t, c, k, o[1], n[1], " → ".join(x or "—" for x in (o[2], n[2]))))
    else:
        L += ["", "## Изменившиеся ячейки", "", "Нет."]
    L.append("")
    with open(a.out, "x", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print("отчёт: %s" % a.out)
    return 3 if lost else 0


if __name__ == "__main__":
    sys.exit(main())
