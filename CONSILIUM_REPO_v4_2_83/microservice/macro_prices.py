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


def tiingo_daily_rows_since(symbol, start, errors):
    """Full daily Tiingo rows (close, adjClose, splitFactor, ...) from `start` through today --
    issue #24. SAME endpoint and SAME startDate-only query `tiingo_series` already uses; the only
    difference is that rows are returned whole instead of projected down to adjClose, because
    `split_factor_since`'s primary signal (below) needs every row's `splitFactor` field.

    [] on any failure -- callers treat an empty list as split-factor-undeterminable, never as
    'no split happened'.
    """
    token = os.environ.get("TIINGO_TOKEN")
    if not token:
        errors["tiingo_daily_rows_%s" % symbol] = "TIINGO_TOKEN not set on this service"
        return []
    try:
        rows = _get_json("https://api.tiingo.com/tiingo/daily/%s/prices?startDate=%s&token=%s"
                         % (symbol, start, token))
        if not isinstance(rows, list):
            errors["tiingo_daily_rows_%s" % symbol] = "unexpected shape: %s" % str(rows)[:80]
            return []
        return rows
    except Exception as e:
        errors["tiingo_daily_rows_%s" % symbol] = str(e)[:140]
        return []


# Issue #24: NVDA 2020-03-23 lived at close/adjClose = 40.2006 -- two real splits (4:1, 10:1)
# compound to EXACTLY 40, and the leftover 0.2006 is accumulated-dividend admixture folded into
# Tiingo's adjustment, not a third split. A tolerance is needed to tell "the same event, seen
# through a noisier lens" from "the two signals disagree about what actually happened". 5% is
# chosen because it comfortably covers multi-year dividend drag for the low-to-moderate-yield
# growth names this pipeline evaluates (NVDA's own case above lands at ~0.5%, an order of
# magnitude inside it) while staying far below the smallest possible real split: any split at
# all -- 2:1, or a reverse 1:2 -- moves the ratio by at least 100% (2x or 1/2x), so a genuine
# extra or missing split can never hide inside this margin.
_SPLIT_RATIO_TOLERANCE = 0.05


def split_factor_since(price_record, daily_rows):
    """Cumulative share-split multiplier between a historical Tiingo daily record's OWN date and
    TODAY -- issue #24 (composite splits + dividend admixture broke the single-day ratio test).

    PRIMARY signal: the PRODUCT of `splitFactor` across every daily row from that date through
    today (`daily_rows`, from `tiingo_daily_rows_since`) -- Tiingo reports 1.0 on every day
    without a split and the exact multiple on a split day, so the product is the exact cumulative
    multiplier, free of dividend admixture, and needs no list of "clean" multiples: a 4:1 then a
    10:1 split simply multiply to 40, whatever "40" is.

    SECONDARY check: `close` is the raw price as it actually traded that day -- in THAT DAY's
    share basis. `adjClose` is rebased to TODAY's share count. Their ratio close/adjClose is
    therefore ALSO the cumulative split multiplier, but Tiingo's adjustment folds in cash
    dividends too, so this ratio is contaminated by however much has been paid out since. The two
    signals must agree within `_SPLIT_RATIO_TOLERANCE`; if they don't, something neither signal
    alone would catch is wrong (a bad row, a data gap, a corporate action this model doesn't
    know), and the mandate is a refusal quoting BOTH numbers, not a guess at which one to trust.

    Undeterminable -- missing rows, missing fields, or a disagreement beyond tolerance -- is
    ALWAYS a refusal, never defaulted to 1.0: mandate 'отсутствие данных для приведения — отказ,
    а не подстановка коэффициента 1'; a silent 1 here is the exact class of confident-looking
    wrong answer the whole stand exists to catch.

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

    if not isinstance(daily_rows, list) or not daily_rows:
        return None, "split_factor_undeterminable: no daily rows to compute the splitFactor product"
    product = 1.0
    for row in daily_rows:
        sf = (row or {}).get("splitFactor")
        if not isinstance(sf, (int, float)) or sf <= 0:
            return None, "split_factor_undeterminable: a daily row is missing a usable splitFactor"
        product *= sf

    if abs(ratio - product) / product > _SPLIT_RATIO_TOLERANCE:
        return None, ("split_factor_undeterminable: splitFactor product %.4f and close/adjClose "
                      "ratio %.4f disagree by more than the %.0f%% dividend-drag tolerance"
                      % (product, ratio, _SPLIT_RATIO_TOLERANCE * 100))
    return product, None


def pe_same_share_basis(price_record, eps_as_filed, errors, symbol="", daily_rows=None):
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

    `daily_rows` (issue #24): daily Tiingo rows from the record's date through today, needed by
    split_factor_since's product signal -- see `tiingo_daily_rows_since`.

    Refuses (never silently assumes factor=1) when the factor cannot be pinned down.
    """
    if eps_as_filed is None:
        errors["pe_same_share_basis_%s" % symbol] = "no EPS supplied"
        return None
    factor, reason = split_factor_since(price_record, daily_rows)
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
