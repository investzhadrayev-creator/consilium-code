#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Панель режима рынка — машинные оси (DECISION_2026-08-13 §1 + 6B + DECISION_2026-10-11).
Оси: волатильность (VIX vs 50DMA, Cboe CSV), участие (RSP/SPY adjClose vs 50DMA отношения,
Tiingo), кредит (HY OAS vs уровня 20 торговых точек назад, FRED). Ось ожиданий (ERI) и CNN —
ручные аргументы; в автоматическом режиме NA. n_valid>=3 — панель валидна.
Пишет строку замороженного формата в journal/PANEL_LOG.csv (append-only, --append).
Missing = NA, никогда не подстановка. Запуск: python3 tools/panel_axes.py --append
"""
import argparse, csv, datetime as dt, io, json, os, sys, urllib.request

UA = {"User-Agent": "Consilium panel (ops contact in repo)"}
NA = "NA"

def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")

def last_and_ma(values, window=50):
    vals = [v for v in values if v is not None]
    if len(vals) < window + 1:
        return None, None
    return vals[-1], sum(vals[-window:]) / window

def ax_vix():
    """-> (vix, vix50, vote, vix3m, vol_stress)"""
    try:
        rows = list(csv.reader(io.StringIO(
            fetch("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"))))
        closes = [float(r[4]) for r in rows[1:] if len(r) >= 5 and r[4]]
        vix, ma = last_and_ma(closes)
        if vix is None:
            return NA, NA, NA, NA, NA
        vote = "1" if vix < ma else "-1"
        vix3m, stress = NA, NA
        try:
            rows3 = list(csv.reader(io.StringIO(fetch(
                "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv"))))
            closes3 = [float(r[4]) for r in rows3[1:] if len(r) >= 5 and r[4]]
            if closes3:
                vix3m = f"{closes3[-1]:.2f}"
                stress = "TRUE" if vix > closes3[-1] else "FALSE"
        except Exception as e:
            print("WARN vix3m:", e, file=sys.stderr)
        return f"{vix:.2f}", f"{ma:.2f}", vote, vix3m, stress
    except Exception as e:
        print("WARN vix axis:", e, file=sys.stderr)
        return NA, NA, NA, NA, NA

def tiingo_adjclose(ticker, token, days=160):
    start = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    j = json.loads(fetch(
        f"https://api.tiingo.com/tiingo/daily/{ticker}/prices?startDate={start}&token={token}"))
    return {row["date"][:10]: float(row["adjClose"]) for row in j}

def ax_participation():
    """EQUAL_WEIGHT_PARTICIPATION: RSP/SPY по adjClose одного Tiingo (6B)."""
    token = os.environ.get("TIINGO_TOKEN") or ""
    if not token:
        print("WARN participation: TIINGO_TOKEN not set", file=sys.stderr)
        return NA, NA, NA
    try:
        rsp, spy = tiingo_adjclose("RSP", token), tiingo_adjclose("SPY", token)
        dates = sorted(set(rsp) & set(spy))
        ratios = [rsp[d] / spy[d] for d in dates]
        last, ma = last_and_ma(ratios)
        if last is None:
            return NA, NA, NA
        return f"{last:.5f}", f"{ma:.5f}", ("1" if last > ma else "-1")
    except Exception as e:
        print("WARN participation axis:", e, file=sys.stderr)
        return NA, NA, NA

def ax_credit():
    try:
        rows = fetch("https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2"
                     ).strip().splitlines()[1:]
        vals = [float(v) for _, v in (r.split(",", 1) for r in rows) if v not in (".", "")]
        if len(vals) < 21:
            return NA, NA, NA
        cur, ago = vals[-1], vals[-21]
        return f"{cur:.2f}", f"{ago:.2f}", ("1" if cur <= ago else "-1")
    except Exception as e:
        print("WARN credit axis:", e, file=sys.stderr)
        return NA, NA, NA

def regime_and_size(votes, cnn, vol_stress):
    valid = [int(v) for v in votes if v in ("1", "-1")]
    n = len(valid)
    if n < 3:
        return n, NA, "REGIME_INSUFFICIENT_DATA", NA, ""
    R = sum(valid) / n
    regime = "RISK_ON" if R >= 0.5 else ("RISK_OFF" if R <= -0.5 else "MIXED")
    greed = ""
    try:
        if cnn != NA and float(cnn) >= 75:
            greed = "GREED"
    except ValueError:
        pass
    if regime == "RISK_ON":
        size = "0.50" if greed else "1.00"
    elif regime == "MIXED":
        size = "0.75"
    else:
        size = "0.25" if vol_stress == "TRUE" else "0.50"
    return n, f"{R:+.2f}", regime, size, greed

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--eri", default=NA, help="значение Citi ERI (глазами) или NA")
    p.add_argument("--eri-source", default=NA, choices=[NA, "CITI_ERI", "FACTSET"])
    p.add_argument("--cnn", default=NA, help="CNN Fear&Greed 0-100 (контекст, не голосует) или NA")
    p.add_argument("--append", action="store_true", help="дописать строку в journal/PANEL_LOG.csv")
    p.add_argument("--notes", default="auto")
    a = p.parse_args()

    eri_vote = NA
    if a.eri != NA:
        try:
            eri_vote = "1" if float(a.eri) > 0 else "-1"
        except ValueError:
            pass
    vix, vix50, vix_vote, vix3m, stress = ax_vix()
    rsp, rsp50, part_vote = ax_participation()
    oas, oas20, credit_vote = ax_credit()
    n, R, regime, size, greed = regime_and_size(
        [eri_vote, vix_vote, part_vote, credit_vote], a.cnn, stress)

    row = [dt.date.today().isoformat(), a.eri, eri_vote,
           a.eri_source if a.eri != NA else NA,
           vix, vix50, vix_vote, vix3m, stress,
           rsp, rsp50, part_vote, oas, oas20, credit_vote,
           a.cnn, greed, str(n), R, regime, size, a.notes]
    line = ",".join(row)
    print(line)
    if a.append:
        path = "journal/PANEL_LOG.csv"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(f"appended -> {path}", file=sys.stderr)
    # панель невалидна — сигнал workflow (не подстановка, честный провал)
    sys.exit(0 if regime != "REGIME_INSUFFICIENT_DATA" else 3)

if __name__ == "__main__":
    main()
