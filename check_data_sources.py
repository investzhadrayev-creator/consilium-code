#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_data_sources.py — проверка живости всех источников данных Consilium.
Запуск:  python3 check_data_sources.py
Зависимости: только стандартная библиотека Python 3.8+.
Опционально: переменная окружения TIINGO_TOKEN для проверки Tiingo.

Статусы:
  OK    — источник жив и отдаёт то, что нам нужно
  WARN  — источник закрыт для скриптов (403/бот-защита), но это страница
          «для глаз»: открой её в браузере и убедись сам; системе не критично
  FAIL  — машинно-критичный источник не отвечает — разбираться обязательно
  SKIP  — проверка пропущена (нет токена и т.п.)
"""
import json, os, ssl, sys, urllib.request, urllib.error
from datetime import date

UA = {"User-Agent": "Consilium data-source check (contact: operator@consilium.local)",
      "Accept": "*/*"}
CTX = ssl.create_default_context()
RESULTS = []

def fetch(url, timeout=25, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.status, r.read()

def record(name, status, note):
    RESULTS.append((name, status, note))
    mark = {"OK": "✅", "WARN": "🟡", "FAIL": "❌", "SKIP": "⏭️ "}[status]
    print(f"{mark} [{status}] {name}: {note}")

def check(name, url, critical, expect=None, parser=None, headers=None):
    """Единый проверщик. parser(data)->note может бросить исключение."""
    try:
        code, data = fetch(url, headers=headers)
        if parser:
            note = parser(data)
        elif expect and expect.encode() not in data:
            record(name, "WARN", f"HTTP {code}, но маркер «{expect}» не найден — проверь глазами: {url}")
            return
        else:
            note = f"HTTP {code}, {len(data)//1024} КБ"
        record(name, "OK", note)
    except urllib.error.HTTPError as e:
        if critical:
            record(name, "FAIL", f"HTTP {e.code} — {url}")
        else:
            record(name, "WARN", f"HTTP {e.code} (бот-защита?) — открой в браузере: {url}")
    except Exception as e:
        record(name, "FAIL" if critical else "WARN", f"{type(e).__name__}: {e} — {url}")

print("=" * 78)
print(f"ПРОВЕРКА ИСТОЧНИКОВ ДАННЫХ CONSILIUM — {date.today().isoformat()}")
print("=" * 78)

# ---------- БЛОК 1. МАШИННО-КРИТИЧНЫЕ (система зависит напрямую) ----------
print("\n--- Блок 1. Машинно-критичные источники ---")

def p_meta(data):
    j = json.loads(data)
    facts = j.get("facts", {})
    has_dei = "dei" in facts and bool(facts.get("dei"))
    n = sum(len(v) for v in facts.values())
    return (f"companyfacts META: {n} тегов; dei "
            + ("ПРИСУТСТВУЕТ — дыра закрыта источником!" if has_dei
               else "ОТСУТСТВУЕТ (как и намерено — идём через edgartools/Tiingo)"))

check("SEC companyfacts (META, проверка dei)",
      "https://data.sec.gov/api/xbrl/companyfacts/CIK0001326801.json",
      critical=True, parser=p_meta)

def p_goog(data):
    j = json.loads(data)
    units = j.get("units", {})
    n = sum(len(v) for v in units.values())
    return f"companyconcept GOOG выручка: {n} наблюдений"

check("SEC companyconcept (GOOG, выручка)",
      "https://data.sec.gov/api/xbrl/companyconcept/CIK0001652044/us-gaap/"
      "RevenueFromContractWithCustomerExcludingAssessedTax.json",
      critical=True, parser=p_goog)

check("SEC RSS-лента филингов (META)",
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001326801"
      "&type=8-K&dateb=&owner=include&count=10&output=atom",
      critical=True, expect="<entry>")

def p_fred(series):
    def inner(data):
        lines = data.decode().strip().split("\n")
        first = lines[1].split(",")[0] if len(lines) > 1 else "?"
        last = lines[-1].split(",")[0] if len(lines) > 1 else "?"
        yrs = max(0, int(last[:4]) - int(first[:4])) if first[:4].isdigit() else "?"
        return f"{series}: {len(lines)-1} строк, {first} → {last} (~{yrs} лет истории)"
    return inner

check("FRED DGS10 (безрисковая ставка)",
      "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
      critical=True, parser=p_fred("DGS10"))

check("FRED HY OAS (кредитные спреды, ось панели)",
      "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2",
      critical=True, parser=p_fred("BAMLH0A0HYM2"))

tok = os.environ.get("TIINGO_TOKEN", "").strip()
if tok:
    def p_tiingo(data):
        j = json.loads(data)
        return f"Tiingo META: {len(j)} баров, последний {j[-1]['date'][:10]}, adjClose {j[-1]['adjClose']}"
    check("Tiingo (цены, adjClose)",
          f"https://api.tiingo.com/tiingo/daily/META/prices?token={tok}",
          critical=True, parser=p_tiingo)
else:
    record("Tiingo (цены)", "SKIP",
           "нет TIINGO_TOKEN в окружении; в проде работает (прайс-апдейтер v1.0.1) — "
           "для полной проверки: TIINGO_TOKEN=... python3 check_data_sources.py")

def p_vix(data):
    lines = data.decode().strip().split("\n")
    return f"история VIX: {len(lines)-1} строк, {lines[1].split(',')[0]} → {lines[-1].split(',')[0]}"

check("Cboe VIX — историческая CSV",
      "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
      critical=True, parser=p_vix)

# ---------- БЛОК 2. СТРАНИЦЫ «ДЛЯ ГЛАЗ» (панель и ожидания) ----------
print("\n--- Блок 2. Страницы для глаз (WARN здесь — не поломка) ---")

check("Zacks Detailed Estimates (пересмотры по имени)",
      "https://www.zacks.com/stock/quote/META/detailed-estimates",
      critical=False, expect="Detailed Estimates")

check("MacroMicro — Citi ERI (ERB рынка)",
      "https://en.macromicro.me/charts/55746/us-eu-jp-citi-earnings-revision-index",
      critical=False, expect="Earnings Revision")

check("Yardeni — запасной источник пересмотров (PDF-страница)",
      "https://yardeni.com/charts/stock-market-earnings-revisions/",
      critical=False, expect="Revisions")

check("CNN Fear & Greed (JSON-фид)",
      "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
      critical=False,
      parser=lambda d: "fear_and_greed сейчас: "
      + str(json.loads(d).get("fear_and_greed", {}).get("score", "?")))

check("TradingView S5TH (ширина рынка)",
      "https://www.tradingview.com/symbols/INDEX-S5TH/",
      critical=False, expect="S5TH")

check("Cboe — страница термструктуры VIX",
      "https://www.cboe.com/tradable-products/vix/term-structure/",
      critical=False, expect="Term Structure")

check("Finviz (short float и скринер)",
      "https://finviz.com/quote.ashx?t=META",
      critical=False, expect="Short Float")

check("Koyfin (экран watchlist)",
      "https://www.koyfin.com/",
      critical=False, expect="Koyfin")

# ---------- БЛОК 3. БИБЛИОТЕКИ ----------
print("\n--- Блок 3. Библиотеки ---")
try:
    import edgar  # edgartools
    v = getattr(edgar, "__version__", "?")
    ok = tuple(int(x) for x in str(v).split(".")[:2]) >= (5, 39) if v != "?" else False
    record("edgartools (будущий транспорт SEC)",
           "OK" if ok else "WARN",
           f"версия {v}; " + ("≥5.39.1 — багфикс filing_date включён; ПИН этой версии"
                              if ok else "нужна ≥5.39.1, обнови и запини"))
except ImportError:
    record("edgartools", "WARN",
           "не установлен здесь; поставить при старте эксперимента: "
           "pip install edgartools && запинить версию")

# ---------- ИТОГ ----------
print("\n" + "=" * 78)
counts = {}
for _, s, _ in RESULTS:
    counts[s] = counts.get(s, 0) + 1
print("ИТОГ:", ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
fails = [n for n, s, _ in RESULTS if s == "FAIL"]
if fails:
    print("❌ КРИТИЧНЫЕ ОТКАЗЫ — разбираться до старта эксперимента:")
    for n in fails:
        print("   -", n)
    sys.exit(1)
print("Машинно-критичный контур жив. WARN-строки открой глазами в браузере.")
sys.exit(0)
