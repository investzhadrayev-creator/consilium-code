# __build__ = "v4.2.83"   # ЕДИНАЯ версия СБОРКИ микросервиса: deploy пушит microservice/
# целиком, поэтому версия отдельного файла ничего не говорит о том, что крутится на
# Railway. Этот маркер одинаков во всех файлах и бампается при каждом деплое —
# grep -h __build__ microservice/*.py | sort -u должен давать РОВНО ОДНУ строку.
"""
macro_prices.py — risk-free rate (FRED) + adjusted price series (Tiingo).

WHY THIS EXISTS: these two calls used to be made from the n8n `Gather Data` Code node, which
meant the FRED and Tiingo keys had to live inside n8n. As of n8n 2.x, Code nodes run inside a
**task runner** — a separate sandboxed process that deliberately does NOT inherit the main
container's environment ("access to env vars denied"). Passing the keys any other way would put
them back into the exported workflow JSON.

The fix is architectural, not a workaround: a key belongs to the service that USES it. These
calls now happen here, on the Railway service, which reads its own environment. n8n orchestrates
and never sees a key.

ENV (set on the growth-enrich Railway service -> Variables):
  FRED_KEY       — https://fred.stlouisfed.org/docs/api/api_key.html (free)
  TIINGO_TOKEN   — https://www.tiingo.com (free tier is enough)

ENDPOINT: POST /macro_prices   BODY: {"ticker": "ADBE", "benchmark": "SPY", "start": "2023-01-01"}
RETURNS: {"risk_free": 0.0421, "prices": [...], "benchmark_prices": [...],
          "monthly_prices": [{"date","adjClose"}...], "_errors": {...}}

`monthly_prices` (10y, month-end) feeds pe_hist_median in Growth Enrich. It lives here for the
same reason as everything else on this route: it is a Tiingo call, and Tiingo's token lives
here. v4.2 briefly left that fetch in the Code node after deleting its token -> ReferenceError,
swallowed by a try/catch, pe_hist_median silently null, PE cap left without its best anchor.

Same discipline as the rest of the service: never throws, every failure lands in `_errors`,
a missing value is null with a reason — never a plausible default. `risk_free` in particular
must NOT fall back to a hardcoded 4% guess: the whole valuation hangs off it.
"""
import json
import os
import time
import urllib.request

_UA = "ConsiliumSpine/1.0 macro_prices"
_LAST = {"t": 0.0}


def _get_json(url, timeout=25):
    """Small throttled GET->JSON. Module-level so tests can monkeypatch it."""
    wait = 0.2 - (time.time() - _LAST["t"])
    if wait > 0:
        time.sleep(wait)
    _LAST["t"] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            import gzip
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8", errors="replace"))


def fred_risk_free(errors, series="DGS10"):
    """10y Treasury constant maturity, latest observation, as a decimal (4.21% -> 0.0421)."""
    key = os.environ.get("FRED_KEY")
    if not key:
        errors["fred"] = "FRED_KEY not set on this service"
        return None
    try:
        d = _get_json("https://api.stlouisfed.org/fred/series/observations"
                      "?series_id=%s&api_key=%s&file_type=json&sort_order=desc&limit=1"
                      % (series, key))
        obs = (d or {}).get("observations") or []
        if not obs:
            errors["fred"] = "no observations returned"
            return None
        # FRED marks missing values with "." on holidays — that is not a zero rate.
        raw = obs[0].get("value")
        if raw in (None, ".", ""):
            errors["fred"] = "latest observation is missing (value='%s')" % raw
            return None
        return float(raw) / 100.0
    except Exception as e:
        errors["fred"] = str(e)[:140]
        return None


def tiingo_series(symbol, errors, start="2023-01-01"):
    """Adjusted close series. Adjusted matters: splits would otherwise read as crashes."""
    token = os.environ.get("TIINGO_TOKEN")
    if not token:
        errors["tiingo"] = "TIINGO_TOKEN not set on this service"
        return []
    try:
        rows = _get_json("https://api.tiingo.com/tiingo/daily/%s/prices?startDate=%s&token=%s"
                         % (symbol, start, token))
        if not isinstance(rows, list):
            errors["tiingo_%s" % symbol] = "unexpected shape: %s" % str(rows)[:80]
            return []
        return [r.get("adjClose") for r in rows if r.get("adjClose") is not None]
    except Exception as e:
        errors["tiingo_%s" % symbol] = str(e)[:140]
        return []


def tiingo_monthly(symbol, errors, years=10):
    """Month-end adjClose for the last `years`. adjClose IS split-adjusted; the EPS series it is
    joined against (in Growth Enrich) is NOT, so the caller must split-normalize EPS first or the
    resulting P/E is nonsense for every pre-split year."""
    token = os.environ.get("TIINGO_TOKEN")
    if not token:
        errors["tiingo_monthly"] = "TIINGO_TOKEN not set on this service"
        return []
    start = time.strftime("%Y-%m-%d", time.gmtime(time.time() - years * 365.25 * 86400))
    try:
        rows = _get_json("https://api.tiingo.com/tiingo/daily/%s/prices"
                         "?startDate=%s&resampleFreq=monthly&token=%s" % (symbol, start, token))
        if not isinstance(rows, list):
            errors["tiingo_monthly"] = "unexpected response for %s" % symbol
            return []
        return [{"date": r.get("date"), "adjClose": r.get("adjClose")}
                for r in rows if r.get("adjClose") is not None and r.get("date")]
    except Exception as exc:
        errors["tiingo_monthly"] = "%s: %s" % (symbol, str(exc)[:120])
        return []


def price_on_date(ticker, date, errors):
    """Full Tiingo daily-price row for a SINGLE day (startDate=endDate=date), for the
    historical-validation stand (issue #14 pt.2). Same address and startDate param already used
    by tiingo_series/tiingo_monthly above; endDate pins it to exactly one day instead of a range.

    Returns the RAW row unfiltered -- every price and corporate-action field Tiingo sends
    (unadjusted close, adjClose, splitFactor, divCash, ...), not just adjClose. Deliberately: the
    basis-reconciliation this feeds (normalize_pe, below) needs BOTH the unadjusted and adjusted
    close from the SAME row, and picking fields here would silently decide, on this caller's
    behalf, which ones a later consumer is allowed to see.
    """
    token = os.environ.get("TIINGO_TOKEN")
    if not token:
        errors["tiingo_price_on_date"] = "TIINGO_TOKEN not set on this service"
        return None
    try:
        rows = _get_json("https://api.tiingo.com/tiingo/daily/%s/prices?startDate=%s&endDate=%s&token=%s"
                         % (ticker, date, date, token))
        if not isinstance(rows, list) or not rows:
            errors["tiingo_price_on_date_%s" % ticker] = "no price data for %s on %s" % (ticker, date)
            return None
        return rows[0]
    except Exception as e:
        errors["tiingo_price_on_date_%s" % ticker] = str(e)[:140]
        return None


def normalize_pe(price_row, eps_asof, errors, key="normalize_pe"):
    """Reconcile a historical EPS (as-of basis) against Tiingo's split-adjusted close (today's
    basis) so price and EPS land on ONE share-count basis before they are divided (issue #14
    pt.3 -- "the main thing in this task"). Un-reconciled, the ratio is wrong by exactly the
    split multiple: a 10:1 split after the as-of date understates P/E tenfold and the system
    confidently recommends a buy on a phantom cheapness.

    BASIS CHOSEN: today's (adjClose). Every other price series this service returns
    (tiingo_series, tiingo_monthly above) is adjClose-only, so a P/E computed here stays
    comparable to anything else in the pipeline built from those series. The alternative --
    unadjusted `close`, already in the as-of basis, needing no conversion at all -- is locally
    simpler but would silently mix bases the moment this number sits next to an adjClose-based
    one computed anywhere else. That silent mix is the defect class this task exists to close,
    not a shortcut worth taking to avoid one division.

    THE CONVERSION: `close` is what actually traded that day (as-of basis); `adjClose` is that
    same trade restated into today's basis by Tiingo. Their ratio close/adjClose IS the
    cumulative basis-conversion factor since as-of, however many splits (and dividend
    adjustments) produced it -- and both values arrive in the ONE row price_on_date already
    fetched, so this needs no separate walk over confirmed_splits/SEC restatements.
    eps_today_basis = eps_asof / (close/adjClose) = eps_asof * adjClose/close.

    Refuses (returns None, records `errors[key]`) rather than defaulting the factor to 1 when
    close/adjClose cannot be read -- a silent 1.0 here is indistinguishable from "no split
    happened" and is exactly the confident-wrong-number failure mode this function exists to
    prevent.
    """
    if not isinstance(price_row, dict):
        errors[key] = "no price row to normalize against"
        return None
    close = price_row.get("close")
    adj_close = price_row.get("adjClose")
    if not isinstance(close, (int, float)) or close <= 0 or \
       not isinstance(adj_close, (int, float)) or adj_close <= 0:
        errors[key] = "split factor not determinable: close/adjClose missing or non-positive"
        return None
    if not isinstance(eps_asof, (int, float)):
        errors[key] = "eps_asof missing or not numeric"
        return None
    split_factor = close / adj_close
    eps_today_basis = eps_asof / split_factor
    if eps_today_basis == 0:
        errors[key] = "normalized EPS is zero — P/E undefined"
        return None
    return {"pe": adj_close / eps_today_basis,
           "price_used": adj_close, "price_basis": "adjClose_today",
           "eps_asof": eps_asof, "eps_today_basis": eps_today_basis,
           "split_factor_since_as_of": split_factor}


def macro_prices(ticker, benchmark="SPY", start="2023-01-01"):
    out = {"_errors": {}}
    out["risk_free"] = fred_risk_free(out["_errors"])
    out["prices"] = tiingo_series(ticker, out["_errors"], start) if ticker else []
    out["benchmark_prices"] = tiingo_series(benchmark, out["_errors"], start)
    out["monthly_prices"] = tiingo_monthly(ticker, out["_errors"]) if ticker else []
    out["_meta"] = {"ticker": ticker, "benchmark": benchmark, "start": start,
                    "n_prices": len(out["prices"]),
                    "n_monthly": len(out["monthly_prices"]),
                    "n_benchmark": len(out["benchmark_prices"]),
                    "risk_free_series": "FRED DGS10 (10y CMT), latest observation"}
    return out


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    r = macro_prices(t)
    r["prices"] = r["prices"][:3] + (["...(%d total)" % len(r["prices"])] if r["prices"] else [])
    r["benchmark_prices"] = r["benchmark_prices"][:3]
    r["monthly_prices"] = r["monthly_prices"][:2] + (["...(%d total)" % len(r["monthly_prices"])]
                                                     if r["monthly_prices"] else [])
    print(json.dumps(r, indent=2))
