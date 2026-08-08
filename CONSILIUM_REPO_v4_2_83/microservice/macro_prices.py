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


_CLEAN_SPLIT_FACTORS = (2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20)


def tiingo_price_on_date(symbol, date, errors):
    """Full Tiingo daily record for exactly ONE trading day -- issue #14 pt.2, the historical-
    reconstruction stand. Same endpoint and the same startDate param `tiingo_series` already
    uses, with endDate pinned to the same value: no new endpoint, no guessed parameter.

    Returns the RAW row UNMODIFIED -- close, adjClose, splitFactor, divCash, and their open/
    high/low/volume twins -- rather than a hand-picked subset. Point 3 of the mandate needs the
    exact field composition Tiingo actually reports to reconcile price and EPS onto one share
    basis (see pe_same_share_basis below); guessing which fields matter here would just move the
    guess one function earlier.

    None on any failure -- a missing historical price is a refusal, not a 0 or an estimate.
    """
    token = os.environ.get("TIINGO_TOKEN")
    if not token:
        errors["tiingo_price_on_date_%s" % symbol] = "TIINGO_TOKEN not set on this service"
        return None
    try:
        rows = _get_json("https://api.tiingo.com/tiingo/daily/%s/prices?startDate=%s&endDate=%s&token=%s"
                         % (symbol, date, date, token))
        if not isinstance(rows, list) or not rows:
            errors["tiingo_price_on_date_%s" % symbol] = "no trading data for %s on %s" % (symbol, date)
            return None
        return rows[0]
    except Exception as e:
        errors["tiingo_price_on_date_%s" % symbol] = str(e)[:140]
        return None


def split_factor_since(price_record):
    """Cumulative share-split multiplier between a historical Tiingo daily record's OWN date and
    TODAY -- derived from the SAME response the price came from (mandate: 'коэффициент сплита
    приходит от Tiingo в том же ответе, что и цена').

    `close` is the raw price as it actually traded that day -- in THAT DAY's share basis.
    `adjClose` is rebased to TODAY's share count. Their ratio close/adjClose is therefore the
    cumulative split multiplier between then and now: a 10:1 split since that date makes today's
    share count 10x larger, so adjClose reads 10x smaller than close for that same day.

    Tiingo's adjustment also folds in cash dividends, so the raw ratio is not a pure split
    factor by construction. It is only TRUSTED when it lands within 1% of one of the clean
    multiples an actual split produces (the same list edgar_facts.py's confirmed-split detector
    uses) or reads as effectively 1 (no split since that date). Anything else is REFUSED, never
    rounded to the nearest clean factor and never defaulted to 1 -- mandate: 'отсутствие данных
    для приведения — отказ, а не подстановка коэффициента 1'; a silent 1 here is the exact
    class of confident-looking wrong answer the whole stand exists to catch.

    Returns (factor, None) on success, (None, reason) on refusal.
    """
    if not isinstance(price_record, dict):
        return None, "split_factor_undeterminable: no price record"
    close = price_record.get("close")
    adj = price_record.get("adjClose")
    if (not isinstance(close, (int, float)) or not isinstance(adj, (int, float))
            or close <= 0 or adj <= 0):
        return None, "split_factor_undeterminable: missing close/adjClose in price record"
    ratio = close / adj
    if abs(ratio - 1.0) <= 0.01:
        return 1.0, None
    for f in _CLEAN_SPLIT_FACTORS:
        if abs(ratio - f) / f <= 0.01:
            return float(f), None
    return None, ("split_factor_undeterminable: close/adjClose ratio %.4f matches no clean "
                  "split multiple and is not ~1.0" % ratio)


def pe_same_share_basis(price_record, eps_as_filed, errors, symbol=""):
    """Price / EPS with BOTH legs forced onto the SAME share-count basis -- issue #14 pt.3, "the
    most important part of the task".

    `price_record["adjClose"]` is expressed in TODAY's share basis. `eps_as_filed` -- EPS read
    from a filing made as of a past date -- is expressed in THAT FILING's basis. Dividing them
    as-is mixes the two bases and the resulting P/E is wrong by exactly the split multiple (a
    10:1 split understates it tenfold, per the mandate's own example).

    Chosen base: TODAY's (adjClose unchanged). Every OTHER Tiingo price consumer in this
    codebase already expects an adjusted price (see tiingo_monthly's docstring: an unadjusted
    series reads a split as a crash), so EPS is the leg that moves --
    eps_today_basis = eps_as_filed / split_factor_since(...).

    Refuses (never silently assumes factor=1) when the factor cannot be pinned down.
    """
    if eps_as_filed is None:
        errors["pe_same_share_basis_%s" % symbol] = "no EPS supplied"
        return None
    factor, reason = split_factor_since(price_record)
    if factor is None:
        errors["pe_same_share_basis_%s" % symbol] = reason
        return None
    adj = (price_record or {}).get("adjClose")
    if not isinstance(adj, (int, float)):
        errors["pe_same_share_basis_%s" % symbol] = "no adjClose in price record"
        return None
    eps_today_basis = eps_as_filed / factor
    if eps_today_basis == 0:
        errors["pe_same_share_basis_%s" % symbol] = "eps_today_basis is zero"
        return None
    return adj / eps_today_basis


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
