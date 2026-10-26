"""K1 (issues #44 / #90): карточка этажа 1, tools/floor1_card.py.

Слои, каждый отвечает на свой вопрос:
  TestGoldens   -- consumer-тест на 4 имени с известными значениями: MU / INTC / META / GOOG, РЕАЛЬНЫЕ байты SEC
                   из tests/fixtures/k2 (без сети), через настоящий адаптер К2. Ожидаемые числа ниже --
                   арифметика от исходных значений фактов (они напечатаны в комментариях), не вывод самой карточки.
  TestMissingIsNotZero -- отсутствующее поле = именованный отказ с причиной, не 0 и не «последнее известное».
  TestProperties -- свойства чистых функций на синтетике (устаревший ряд, сплит, пороги флагов, цены).
  TestOutputs    -- контракт файлов и main(): имя под schedule_guard, покрытие, коды выхода, as_of до адаптера.
  TestWorkflowReport -- поставляемый panel_weekly.yml (mailbox/REPORT_2026-10-25_K1_WORKFLOWS.md).
Каждый пронумерованный пин f1-NN имеет мутацию в tools/mutation_probe.py, которая его краснит.
"""
import contextlib
import csv
import difflib
import io
import os
import re
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True   # мутационный зонд правит tools/ -- устаревший .pyc не должен пережить правку
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "tools"))

import floor1_card as fc          # noqa: E402
import schedule_guard as G        # noqa: E402

EF, AD = fc.load_sec_modules()
FIXROOT = os.path.join(REPO, "CONSILIUM_REPO_v4_2_83", "tests", "fixtures", "k2")
REPORT = os.path.join(REPO, "mailbox", "REPORT_2026-10-25_K1_WORKFLOWS.md")
ACCN_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")
CHECK_DATE = "2022-10-12"        # одна из дат check-#1 К2: во всех четырёх фикстурах есть и 10-K FY2021, и история
INTC_DATE = "2022-01-25"         # golden К2: FY2021 INTC подан 2022-01-27, т.е. ЗА срезом -- последний ФГ = FY2020
LOADER = AD.FixtureLoader(FIXROOT)


class FixtureSource:
    """Тот же контракт, что LiveSource.read(), но на захваченных байтах SEC (без сети)."""
    ef, ad = EF, AD

    def __init__(self, as_of):
        self.as_of = as_of

    def read(self, ticker):
        cik = LOADER.manifest["tickers"][ticker]["cik"]
        out = AD.read_as_of(ticker=ticker, cik=cik, as_of=self.as_of, loader=LOADER)
        return out, EF._filter_facts_as_of(EF._companyfacts(cik), self.as_of), cik


def card(ticker, as_of=CHECK_DATE):
    return fc.build_name(ticker, as_of, FixtureSource(as_of), None, {}, "no prices in this layer")


def val(row, name):
    f = row["fields"][name]
    assert fc.is_ok(f), "%s: %s" % (name, f)
    return f["value"]


def refused(row, name):
    f = row["fields"][name]
    assert not fc.is_ok(f), "%s expected a refusal, got %s" % (name, f)
    assert f["reason"].strip(), "%s: a refusal without a reason" % name
    return f["refused"]


def pt(end, v, accn="0000000000-00-000001"):
    return {"end": end, "val": v, "accn": accn}


def yearly(vals, last_year=2025):
    return [pt("%d-12-31" % (last_year - len(vals) + 1 + i), v) for i, v in enumerate(vals)]


def tag_facts(tags, accn="0000000000-25-000001"):
    """companyfacts-подобная синтетика: {тег: [(end, val)]} -> instant-факты 10-K (для net_debt_series)."""
    return {"facts": {"us-gaap": {t: {"units": {"USD": [{"end": e, "val": v, "form": "10-K", "filed": e, "accn": accn}
                                                         for e, v in pts]}} for t, pts in tags.items()}}}


def dur_facts(tags):
    """{тег: [(year, val, accn)]} -> годовые duration-факты 10-K с началом 01-01 (для вывода валовой прибыли)."""
    return {"facts": {"us-gaap": {t: {"units": {"USD": [
        {"start": "%d-01-01" % y, "end": "%d-12-31" % y, "val": v, "form": "10-K", "filed": "%d-12-31" % y, "accn": a}
        for y, v, a in pts]}} for t, pts in tags.items()}}}


def syn_out(gp=None):
    out = {"revenue": yearly([100] * 8), "net_income": yearly([10] * 8), "ocf": yearly([30] * 8),
           "capex": yearly([5] * 8), "shares_diluted": yearly([5] * 8), "_flags": {}, "_refusals": {}}
    if gp is not None:
        out["gross_profit"] = gp
    return out


class TestGoldens(unittest.TestCase):
    """Исходные факты (USD) прочитаны с фикстур К2 и записаны здесь; ожидаемое -- арифметика от них."""

    @classmethod
    def setUpClass(cls):
        cls.intc = card("INTC", INTC_DATE)
        cls.mu = card("MU", "2018-10-15")
        cls.meta = card("META")
        cls.goog = card("GOOG")

    def test_f1_01_INTC_values_and_the_last_fiscal_year_is_the_one_filed_before_the_as_of_day(self):
        # FY2020 (2020-12-26): rev 77_867M, NI 20_899M, OCF 35_384M, capex 14_259M; diluted 4_232M (FY2019 4_473M).
        # FY2021 (10-K filed 2022-01-27) is OUTSIDE the 2022-01-25 slice.
        r = self.intc
        self.assertEqual(r["meta"]["fy_end"], "2020-12-26")
        self.assertEqual(val(r, "ni_latest"), 20_899_000_000)
        self.assertEqual(val(r, "fcf_latest"), 35_384_000_000 - 14_259_000_000)
        self.assertAlmostEqual(val(r, "fcf_to_ni"), 21_125 / 20_899, places=12)
        self.assertAlmostEqual(val(r, "eps_latest"), 20_899 / 4_232, places=12)
        self.assertAlmostEqual(val(r, "shares_chg_1y"), 4_232 / 4_473 - 1, places=12)
        self.assertAlmostEqual(val(r, "rev_cagr_3y"), (77_867 / 62_761) ** (1 / 3.0) - 1, places=12)  # FY2017 62_761M
        self.assertAlmostEqual(val(r, "om_latest"), 23_678 / 77_867, places=12)
        self.assertEqual(r["meta"]["as_of_violations"], [])

    def test_f1_02_MU_values_and_CYCLE_PEAK_on_the_2018_memory_peak(self):
        # FY2018 (2018-08-30): rev 30_391M, NI 14_135M, OCF 17_400M, capex 8_879M, operating income 14_994M.
        r = self.mu
        self.assertEqual(r["meta"]["fy_end"], "2018-08-30")
        self.assertEqual(val(r, "ni_latest"), 14_135_000_000)
        self.assertEqual(val(r, "fcf_latest"), 17_400_000_000 - 8_879_000_000)
        self.assertAlmostEqual(val(r, "fcf_to_ni"), 8_521 / 14_135, places=12)
        self.assertAlmostEqual(val(r, "om_latest"), 14_994 / 30_391, places=12)
        self.assertGreater(val(r, "om_latest"), val(r, "om_med5"))
        self.assertEqual(r["flags"]["CYCLE_PEAK"]["state"], "RAISED")
        self.assertIn("2018-08-30", r["flags"]["CYCLE_PEAK"]["evidence"])
        self.assertEqual(r["flags"]["BUYBACK_EPS"]["state"], "CLEAR")      # акции за 3 ФГ ВЫРОСЛИ

    def test_f1_03_INTC_buyback_flag_carries_its_numbers_as_evidence(self):
        f = self.intc["flags"]["BUYBACK_EPS"]
        self.assertEqual(f["state"], "RAISED")
        self.assertIn("-0.1247", f["evidence"])        # акции 3л: 4_232/4_835(FY2017 4_835M)... -> см. shares_chg_3y
        self.assertAlmostEqual(val(self.intc, "shares_chg_3y"), 4_232 / 4_835 - 1, places=12)

    def test_f1_04_META_values_and_no_gross_margin_invented(self):
        # FY2021: rev 117_929M, NI 39_370M, OCF 57_683M, capex 18_567M; diluted 2_859M (FY2020 2_888M).
        r = self.meta
        self.assertEqual(val(r, "fcf_latest"), 57_683_000_000 - 18_567_000_000)
        self.assertAlmostEqual(val(r, "fcf_to_ni"), 39_116 / 39_370, places=12)
        self.assertAlmostEqual(val(r, "shares_chg_1y"), 2_859 / 2_888 - 1, places=12)
        # GrossProfit у META нет в SEC-данных (K1.1 ч.1): маржа ВЫВЕДЕНА (rev 117_929M, CostOfRevenue 22_649M, оба из
        # 10-K 0001326801-22-000018) и честно помечена derived -- не выдана за отчётный GrossProfit
        self.assertAlmostEqual(val(r, "gm_latest"), (117_929 - 22_649) / 117_929, places=12)
        self.assertTrue(r["fields"]["gm_latest"]["derived"])
        self.assertEqual(r["fields"]["gm_latest"]["prov"], ["0001326801-22-000018"])

    def test_f1_05_GOOG_share_classes_are_refused_by_name_not_summed(self):
        # FY2021 FCF: OCF 91_652M - capex 24_640M. Консолидированного разводнённого числа акций у GOOG нет.
        r = self.goog
        self.assertEqual(val(r, "fcf_latest"), 91_652_000_000 - 24_640_000_000)
        for name in ("eps_latest", "shares_chg_1y", "shares_chg_3y"):
            self.assertEqual(refused(r, name), "MULTI_CLASS_NOT_SUMMED", name)
        self.assertEqual(r["flags"]["BUYBACK_EPS"]["state"], "UNDETERMINED")
        self.assertEqual(r["flags"]["DEBT_FOR_BUYBACKS"]["state"], "UNDETERMINED")

    def test_f1_06_every_number_carries_a_sec_accession(self):
        for r in (self.intc, self.mu, self.meta, self.goog):
            n = 0
            for name, f in r["fields"].items():
                if fc.is_ok(f):
                    n += 1
                    self.assertTrue(f["prov"], "%s %s: число без провенанса" % (r["ticker"], name))
                    for a in f["prov"]:
                        self.assertRegex(a, ACCN_RE, "%s %s" % (r["ticker"], name))
            self.assertGreater(n, 10, r["ticker"])

    def test_f1_07_nothing_after_the_as_of_day_leaks_into_a_card(self):
        for r in (self.intc, self.mu, self.meta, self.goog):
            self.assertEqual(r["meta"]["as_of_violations"], [], r["ticker"])


class TestMissingIsNotZero(unittest.TestCase):
    def test_f1_08_a_stale_series_is_refused_not_shown_as_the_latest_value(self):
        # Единственный тег долга оборвался в FY2020, карточка на FY2025: долг 2020 года -- не «текущий». (На реальном
        # MU LongTermDebt оборвался в 2012, но теперь есть DebtAndCapitalLeaseObligations -- см. f1_34.)
        facts = tag_facts({"LongTermDebt": [("2020-12-31", 90)], "CashAndCashEquivalentsAtCarryingValue":
                           [("%d-12-31" % y, 10) for y in range(2020, 2026)]})
        F, _ = fc.sec_fields(syn_out(), facts, EF)
        self.assertEqual(refused({"fields": F}, "net_debt_latest"), "STALE_SERIES")
        self.assertIn("2020", F["net_debt_latest"]["reason"])
        self.assertEqual(refused({"fields": F}, "net_debt_chg_3y"), "STALE_SERIES")
        self.assertEqual(fc.flags_for(F, _)["DEBT_FOR_BUYBACKS"]["state"], "UNDETERMINED")

    def test_f1_09_no_debt_tag_is_a_refusal_and_never_zero_debt(self):
        out, ref = fc.net_debt_series({"facts": {"us-gaap": {}}}, EF)
        self.assertIsNone(out)
        self.assertEqual(ref["refused"], "DEBT_TAG_ABSENT")
        meta = card("META")                       # у META нет полной пары долг+деньги: отказ, не 0
        self.assertFalse(fc.is_ok(meta["fields"]["net_debt_latest"]))
        self.assertNotEqual(meta["fields"].get("net_debt_latest", {}).get("value"), 0)

    def test_f1_10_a_noncurrent_debt_without_its_current_part_is_not_a_debt_point(self):
        def inst(tag, vals):
            return {tag: {"units": {"USD": [{"end": e, "val": v, "form": "10-K", "filed": e, "accn": a}
                                            for e, v, a in vals]}}}
        us = {}
        us.update(inst("LongTermDebtNoncurrent", [("2024-12-31", 90, "0000000000-24-000001")]))
        us.update(inst("CashAndCashEquivalentsAtCarryingValue", [("2024-12-31", 10, "0000000000-24-000001")]))
        out, ref = fc.net_debt_series({"facts": {"us-gaap": us}}, EF)
        self.assertIsNone(out, "текущая часть долга отсутствует в данных != текущая часть = 0")
        self.assertEqual(ref["refused"], "MISSING_INPUT")
        us.update(inst("LongTermDebtCurrent", [("2024-12-31", 5, "0000000000-24-000001")]))
        out, ref = fc.net_debt_series({"facts": {"us-gaap": us}}, EF)
        self.assertEqual(out[-1]["val"], 90 + 5 - 10)

    def test_f1_11_ocf_without_capex_gives_no_fcf(self):
        out = {"revenue": yearly([100] * 6), "net_income": yearly([10] * 6), "ocf": yearly([30] * 6),
               "capex": None, "shares_diluted": yearly([5] * 6), "_flags": {}, "_refusals": {}}
        F, _ = fc.sec_fields(out, {"facts": {"us-gaap": {}}}, EF)
        self.assertFalse(fc.is_ok(F["fcf_latest"]))
        self.assertFalse(fc.is_ok(F["fcf_to_ni"]))

    def test_f1_12_foreign_filer_is_named_not_zero_filled(self):
        facts = {"facts": {"ifrs-full": {"Revenue": {}}}}
        r = fc.sec_unavailable({"_missing": ["revenue"]}, facts)
        self.assertEqual(r["refused"], "FOREIGN_FILER_IFRS")
        self.assertEqual(fc.sec_unavailable({}, {"facts": {"us-gaap": {}}})["refused"], "NO_US_GAAP_ANNUAL_FACTS")

    def test_f1_13_csv_cell_of_a_refused_field_is_empty_with_a_reason(self):
        with tempfile.TemporaryDirectory() as td:
            rows = [card("META", CHECK_DATE)]
            fc.write_outputs(rows, CHECK_DATE, td, "test", {"edgartools": AD.EDGARTOOLS_PIN})
            with open(os.path.join(td, "FLOOR1_%s.csv" % CHECK_DATE), encoding="utf-8") as fh:
                rec = next(csv.DictReader(fh))
        self.assertEqual(rec["net_debt_latest"], "")
        self.assertIn("MISSING_INPUT", rec["net_debt_latest__reason"])
        self.assertEqual(rec["rs_voo_4w"], "")
        self.assertIn("TIINGO_UNAVAILABLE", rec["rs_voo_4w__reason"])
        self.assertNotEqual(rec["ni_latest"], "0")


class TestProperties(unittest.TestCase):
    def test_f1_14_current_refuses_a_series_that_ends_before_the_card_year(self):
        s, r = fc.current(yearly([1, 2, 3], 2020), "2025-12-31", "x")
        self.assertIsNone(s)
        self.assertEqual(r["refused"], "STALE_SERIES")
        s, r = fc.current(yearly([1, 2, 3], 2025), "2025-12-31", "x")
        self.assertIsNone(r)

    def test_f1_15_cagr_of_a_non_positive_boundary_is_undefined_not_a_number(self):
        r = fc.cagr(yearly([-5, 1, 2, 3]), 3, "ni")
        self.assertEqual(r["refused"], "CAGR_UNDEFINED")
        self.assertAlmostEqual(fc.cagr(yearly([100, 110, 121, 133.1]), 3, "rev")["value"], 0.10, places=9)

    def test_f1_16_a_confirmed_split_inside_the_window_refuses_the_share_change(self):
        sh = yearly([100, 100, 100, 50])
        split = [{"end": "2024-12-31"}]
        r = fc.share_change(sh, 3, split, None)
        self.assertEqual(r["refused"], "SPLIT_IN_WINDOW")
        self.assertTrue(fc.is_ok(fc.share_change(sh, 3, [{"end": "2010-12-31"}], None)))

    def test_f1_17_cycle_peak_needs_the_max_AND_above_median(self):
        def raw(margins):
            return {"om": yearly(margins)}
        self.assertEqual(fc.flag_cycle_peak(raw([.10, .12, .11, .13, .30]))["state"], "RAISED")
        self.assertEqual(fc.flag_cycle_peak(raw([.10, .40, .11, .13, .30]))["state"], "CLEAR")   # выше медианы, но не максимум
        self.assertEqual(fc.flag_cycle_peak(raw([.10, .12, .11]))["state"], "UNDETERMINED")

    def test_f1_18_cash_conversion_divergence_is_NI_up_AND_FCF_down(self):
        def raw(ni, fcf):
            return {"ni": yearly(ni), "fcf": yearly(fcf)}
        self.assertEqual(fc.flag_cash_conv(raw([10, 20], [30, 15]))["state"], "RAISED")
        self.assertEqual(fc.flag_cash_conv(raw([10, 20], [30, 35]))["state"], "CLEAR")
        self.assertEqual(fc.flag_cash_conv(raw([20, 10], [30, 15]))["state"], "CLEAR")
        self.assertEqual(fc.flag_cash_conv(raw([10], [30]))["state"], "UNDETERMINED")

    def test_f1_19_debt_for_buybacks_needs_shrinking_shares_AND_growing_net_debt(self):
        def F(sh, dn):
            return {"shares_chg_3y": fc.ok(sh, "ratio", "t"), "net_debt_chg_3y": fc.ok(dn, "USD", "t")}
        self.assertEqual(fc.flag_debt_for_buybacks(F(-.05, 1_000))["state"], "RAISED")
        self.assertEqual(fc.flag_debt_for_buybacks(F(-.05, -1_000))["state"], "CLEAR")
        self.assertEqual(fc.flag_debt_for_buybacks(F(.05, 1_000))["state"], "CLEAR")
        und = fc.flag_debt_for_buybacks({"shares_chg_3y": fc.refusal("X", "y"), "net_debt_chg_3y": fc.ok(1, "USD", "t")})
        self.assertEqual(und["state"], "UNDETERMINED")

    def test_f1_20_relative_strength_and_drawdown_on_a_synthetic_tape(self):
        a = "2026-10-23"
        D = lambda n: (fc._d(a) - fc.dt.timedelta(days=n)).isoformat()      # noqa: E731
        t = {D(370): 300.0, D(200): 150.0, D(91): 80.0, D(28): 100.0, a: 120.0}   # 300 -- вне окна 52н
        b = {D(370): 90.0, D(91): 100.0, D(28): 100.0, a: 110.0}
        F = fc.price_fields(t, {"VOO": b, "QQQ": b}, a)
        self.assertAlmostEqual(F["rs_voo_4w"]["value"], (120 / 100 - 1) - (110 / 100 - 1), places=12)     # +0.10
        self.assertAlmostEqual(F["rs_voo_13w"]["value"], (120 / 80 - 1) - (110 / 100 - 1), places=12)     # +0.40
        self.assertAlmostEqual(F["dd_52w"]["value"], 120 / 150 - 1, places=12)                           # -0.20, не к 300

    def test_f1_21_a_stale_last_close_is_refused_not_used(self):
        a = "2026-10-23"
        D = lambda n: (fc._d(a) - fc.dt.timedelta(days=n)).isoformat()      # noqa: E731
        t = {D(370): 100.0, D(100): 100.0, D(28 + 10): 100.0, D(10): 100.0}   # последний close на 10 дней старше
        b = dict(t)
        F = fc.price_fields(t, {"VOO": b, "QQQ": b}, a)
        self.assertEqual(F["rs_voo_4w"]["refused"], "PRICE_STALE")
        self.assertEqual(F["dd_52w"]["refused"], "PRICE_STALE")

    def test_f1_22_unavailable_benchmark_or_tiingo_is_named(self):
        a = "2026-10-23"
        D = lambda n: (fc._d(a) - fc.dt.timedelta(days=n)).isoformat()      # noqa: E731
        t = {D(370): 100.0, D(91): 100.0, D(28): 100.0, a: 100.0}
        F = fc.price_fields(t, {"VOO": "Tiingo: HTTP 429", "QQQ": t}, a)
        self.assertEqual(F["rs_voo_4w"]["refused"], "BENCHMARK_UNAVAILABLE")
        self.assertTrue(fc.is_ok(F["rs_qqq_4w"]))
        G_ = fc.price_fields(None, {}, a, "Tiingo X: HTTP 500")
        self.assertEqual({f["refused"] for f in G_.values()}, {"TIINGO_UNAVAILABLE"})

    def test_f1_23_a_builder_exception_becomes_a_named_refusal_for_that_name_only(self):
        class Boom:
            ef, ad = EF, AD

            def read(self, t):
                raise RuntimeError("SEC 503")
        r = fc.build_name("XXXX", CHECK_DATE, Boom(), None, {}, "x")
        self.assertEqual(r["fields"]["rev_cagr_3y"]["refused"], "SEC_READ_FAILED")
        self.assertIn("SEC 503", r["fields"]["rev_cagr_3y"]["reason"])
        self.assertEqual(r["flags"]["CYCLE_PEAK"]["state"], "UNDETERMINED")

    def test_f1_24_the_newest_tree_is_chosen_by_number_not_by_string(self):
        with tempfile.TemporaryDirectory() as td:
            for n in (9, 83, 100):
                os.makedirs(os.path.join(td, "CONSILIUM_REPO_v4_2_%d" % n, "microservice"))
            old = fc.ROOT
            fc.ROOT = td
            try:
                self.assertTrue(fc.micro_dir().endswith("CONSILIUM_REPO_v4_2_100/microservice"))
            finally:
                fc.ROOT = old

    def test_f1_25_a_refusal_never_carries_an_empty_reason_on_any_golden(self):
        for t, a in (("MU", "2018-10-15"), ("INTC", INTC_DATE), ("META", CHECK_DATE), ("GOOG", CHECK_DATE)):
            r = card(t, a)
            for name, f in r["fields"].items():
                if not fc.is_ok(f):
                    self.assertTrue(f["refused"] and f["reason"].strip(), "%s %s" % (t, name))
                else:
                    self.assertIsNotNone(f["value"], "%s %s" % (t, name))
                    self.assertEqual(f["value"], f["value"], "NaN %s %s" % (t, name))
            for name, f in r["flags"].items():
                self.assertIn(f["state"], ("RAISED", "CLEAR", "UNDETERMINED"))
                self.assertTrue(f["evidence"].strip(), "%s %s: флаг без улики" % (t, name))


class TestOutputs(unittest.TestCase):
    def test_f1_26_coverage_counts_only_determined_fields(self):
        row = {"ticker": "T", "fields": {"a": fc.ok(1, "USD", "b"), "b": fc.refusal("X", "y"),
                                         "c": fc.ok(2, "USD", "b"), "d": fc.refusal("X", "y")},
               "flags": {"F1": {"state": "RAISED", "evidence": "e"}, "F2": {"state": "UNDETERMINED", "evidence": "e"}},
               "meta": {}}
        per, cov, n_ok, n_all = fc.coverage([row])
        self.assertEqual((n_ok, n_all), (3, 6))
        self.assertAlmostEqual(cov, 0.5)

    def test_f1_27_main_writes_the_files_the_schedule_guard_looks_for(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as wl:
            wlp = os.path.join(wl, "watchlist.csv")
            with open(wlp, "w", encoding="utf-8") as fh:
                fh.write("ticker,role\nINTC,watch\nMU,watch\nMETA,watch\nGOOG,watch\nVOO,benchmark\n")
            env = {"TIINGO_TOKEN": "t", "SEC_USER_AGENT": "Consilium test (x@example.org)"}
            saved = (fc.LiveSource, fc.tiingo_prices)
            fc.LiveSource = lambda as_of: FixtureSource(as_of)
            fc.tiingo_prices = lambda t, token, as_of, retries=2: (_ for _ in ()).throw(RuntimeError("no network in test"))
            try:
                with unittest.mock.patch.dict(os.environ, env), contextlib.redirect_stderr(io.StringIO()), \
                        contextlib.redirect_stdout(io.StringIO()):
                    code = fc.main(["--as-of", CHECK_DATE, "--watchlist", wlp, "--out-dir", td])
            finally:
                fc.LiveSource, fc.tiingo_prices = saved
            self.assertEqual(code, 0)
            names = sorted(os.listdir(td))
            self.assertEqual(names, ["FLOOR1_%s.csv" % CHECK_DATE, "FLOOR1_%s.md" % CHECK_DATE])
            self.assertIsNotNone(G.FLOOR1_RE.match("FLOOR1_%s.md" % CHECK_DATE))
            with open(os.path.join(td, names[0]), encoding="utf-8") as fh:
                recs = list(csv.DictReader(fh))
            self.assertEqual([r["ticker"] for r in recs], ["INTC", "MU", "META", "GOOG"])   # VOO -- бенчмарк, не строка
            md = open(os.path.join(td, names[1]), encoding="utf-8").read()
            self.assertIn("Покрытие полей", md)
            self.assertIn("Named limitations", md)

    def test_f1_28_without_credentials_no_card_is_written(self):
        with tempfile.TemporaryDirectory() as td:
            env = {k: v for k, v in os.environ.items() if k not in ("SEC_USER_AGENT", "TIINGO_TOKEN")}
            env["TIINGO_TOKEN"] = "t"
            saved = fc.LiveSource
            fc.LiveSource = lambda as_of: FixtureSource(as_of)
            try:
                with unittest.mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stderr(io.StringIO()):
                    code = fc.main(["--as-of", CHECK_DATE, "--tickers", "INTC", "--out-dir", td])
            finally:
                fc.LiveSource = saved
            self.assertEqual(code, 2)
            self.assertEqual(os.listdir(td), [])

    def test_f1_29_the_run_date_is_the_sec_as_of_handed_to_the_adapter(self):
        seen = {}

        class FakeAd:
            EDGARTOOLS_PIN = "x"

            class LiveLoader:
                pass

            @staticmethod
            def read_as_of(ticker=None, cik=None, as_of=None, loader=None):
                seen["read"] = as_of
                return {"_errors": {"stop": "test"}}

        class FakeEf:
            _resolve_cik = staticmethod(lambda t: "0000000001")
            _companyfacts = staticmethod(lambda cik: {"facts": {}})

            @staticmethod
            def _filter_facts_as_of(facts, as_of):
                seen["filter"] = as_of
                return facts
        saved = fc.load_sec_modules
        fc.load_sec_modules = lambda: (FakeEf, FakeAd)
        try:
            fc.LiveSource("2026-10-31").read("ZZZ")
        finally:
            fc.load_sec_modules = saved
        self.assertEqual(seen["read"], "2026-10-31")


class TestWorkflowReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = open(REPORT, encoding="utf-8").read()
        m = re.search(r"### `\.github/workflows/panel_weekly\.yml`\n\n```yaml\n(.*?)\n```", text, re.S)
        assert m, "panel_weekly.yml block not found in the report"
        cls.new = m.group(1)
        cls.cur = open(os.path.join(REPO, ".github", "workflows", "panel_weekly.yml"), encoding="utf-8").read().rstrip("\n")

    def _card_step(self):
        i = self.new.index("name: Карточка этажа 1")
        return self.new[i:self.new.index("- name: Публикация через PR")]

    def test_f1_30_card_step_gets_both_secrets_the_script_requires(self):
        step = self._card_step()
        self.assertIn("TIINGO_TOKEN: ${{ secrets.TIINGO_TOKEN }}", step)
        self.assertIn("SEC_USER_AGENT: ${{ secrets.SEC_USER_AGENT }}", step)
        self.assertIn("python3 tools/floor1_card.py", step)

    def test_f1_31_edgartools_is_installed_from_the_requirements_pin_before_the_card(self):
        self.assertLess(self.new.index("pip install"), self.new.index("tools/floor1_card.py"))
        line = next(l for l in self.new.splitlines() if "pip install" in l)
        self.assertIn("grep -i '^edgartools=='", line)
        self.assertIn("requirements.txt", self.new)
        self.assertNotRegex(line, r"pip install[^\n]*\bedgartools\b(?!==)[^\n]*$" if "grep" not in line else r"^\b$")

    def test_f1_32_the_delivered_file_differs_from_main_only_in_the_card_step(self):
        diff = [l for l in difflib.unified_diff(self.cur.splitlines(), self.new.splitlines(), lineterm="", n=0)
                if l[:1] in "+-" and not l.startswith(("+++", "---"))]
        removed = [l for l in diff if l.startswith("-")]
        self.assertEqual(removed, ["-      - name: Карточка этажа 1 (появится после задачи К1)"], removed)
        added = "\n".join(l for l in diff if l.startswith("+"))
        self.assertNotIn("cron", added)
        self.assertNotIn("concurrency", added)

    def test_f1_33_the_report_admits_the_secret_name_is_an_unverified_assumption(self):
        text = open(REPORT, encoding="utf-8").read()
        self.assertIn("ДОПУЩЕНИЕ", text)
        self.assertIn("403", text)


class TestTagChainsAndDerivedGrossProfit(unittest.TestCase):
    """K1.1 ч.1: дрейф тегов (цепочки) и валовая прибыль = выручка - себестоимость из одного отчёта."""

    def test_f1_34_mu_net_debt_comes_from_the_alternative_tag_and_says_which(self):
        # MU FY2018: LongTermDebt нет с 2012; DebtAndCapitalLeaseObligations 4_636M, деньги 6_506M (из фактов фикстуры)
        mu = card("MU", "2018-10-15")
        self.assertEqual(val(mu, "net_debt_latest"), 4_636_000_000 - 6_506_000_000)
        self.assertEqual(mu["fields"]["net_debt_latest"]["tags"],
                         ["DebtAndCapitalLeaseObligations", "CashAndCashEquivalentsAtCarryingValue"])
        self.assertIn("DebtAndCapitalLeaseObligations", mu["fields"]["net_debt_latest"]["basis"])

    def test_f1_35_change_across_different_tag_sets_is_marked_mixed(self):
        yrs = lambda a, b: ["%d-12-31" % y for y in range(a, b + 1)]
        cash = [(e, 10) for e in yrs(2022, 2025)]
        mixed = tag_facts({"LongTermDebt": [(yrs(2022, 2022)[0], 50)], "DebtAndCapitalLeaseObligations":
                           [(e, 80) for e in yrs(2023, 2025)], "CashAndCashEquivalentsAtCarryingValue": cash})
        F, _ = fc.sec_fields(syn_out(), mixed, EF)
        f = F["net_debt_chg_3y"]
        self.assertEqual(f["value"], (80 - 10) - (50 - 10))
        self.assertTrue(f["mixed_tags"])
        self.assertIn("РАЗНЫЕ ТЕГИ", f["basis"])
        same = tag_facts({"LongTermDebt": [(e, 50) for e in yrs(2022, 2025)], "CashAndCashEquivalentsAtCarryingValue": cash})
        F, _ = fc.sec_fields(syn_out(), same, EF)
        self.assertFalse(F["net_debt_chg_3y"]["mixed_tags"])
        self.assertNotIn("РАЗНЫЕ", F["net_debt_chg_3y"]["basis"])

    def test_f1_36_derived_gross_profit_carries_both_accessions_from_one_report(self):
        a = "0000000000-25-000007"
        facts = dur_facts({"Revenues": [(y, 100 + y - 2018, a) for y in range(2018, 2026)],
                           "CostOfRevenue": [(y, 40, a) for y in range(2018, 2026)]})
        gp, rv, ref = fc.gross_profit_derived(facts, EF)
        self.assertIsNone(ref)
        self.assertEqual(gp[-1]["val"], 107 - 40)
        self.assertEqual(gp[-1]["accn"], [a, a])
        self.assertEqual(gp[-1]["tags"], ["Revenues", "CostOfRevenue"])
        F, _ = fc.sec_fields(syn_out(), facts, EF)
        g = F["gm_latest"]
        self.assertTrue(g["derived"])
        self.assertAlmostEqual(g["value"], 67 / 107, places=12)
        self.assertEqual(g["prov"], [a])
        self.assertEqual(g["tags"], ["Revenues", "CostOfRevenue"])

    def test_f1_37_missing_cost_or_report_mismatch_is_a_refusal_never_zero_or_revenue(self):
        years = range(2018, 2026)
        only_rev = dur_facts({"Revenues": [(y, 100, "0000000000-25-000007") for y in years]})
        gp, rv, ref = fc.gross_profit_derived(only_rev, EF)
        self.assertIsNone(gp)
        self.assertEqual(ref["refused"], "MISSING_INPUT")
        F, _ = fc.sec_fields(syn_out(), only_rev, EF)
        self.assertEqual(refused({"fields": F}, "gm_latest"), "MISSING_INPUT")
        self.assertEqual(refused({"fields": F}, "gm_med5"), "MISSING_INPUT")
        a = "0000000000-25-000007"          # себестоимости за последний ФГ нет: он не «ноль», маржа за него не считается
        no_last_cost = dur_facts({"Revenues": [(y, 100, a) for y in years],
                                  "CostOfRevenue": [(y, 40, a) for y in years if y < 2025]})
        F, _ = fc.sec_fields(syn_out(), no_last_cost, EF)
        self.assertEqual(refused({"fields": F}, "gm_latest"), "STALE_SERIES")
        two_reports = dur_facts({"Revenues": [(y, 100, "0000000000-25-000007") for y in years],
                                 "CostOfRevenue": [(y, 40, "0000000000-25-000008") for y in years]})
        gp, rv, ref = fc.gross_profit_derived(two_reports, EF)
        self.assertIsNone(gp, "выручка из одного отчёта и себестоимость из другого не склеиваются")
        self.assertEqual(ref["refused"], "MISSING_INPUT")

    def test_f1_38_reported_gross_profit_wins_and_is_not_marked_derived(self):
        a = "0000000000-25-000007"
        facts = dur_facts({"Revenues": [(y, 100, a) for y in range(2018, 2026)],
                           "CostOfRevenue": [(y, 40, a) for y in range(2018, 2026)]})
        F, _ = fc.sec_fields(syn_out(gp=yearly([55] * 8)), facts, EF)
        self.assertAlmostEqual(F["gm_latest"]["value"], 0.55)     # 55/100 отчётный, а не (100-40)/100
        self.assertNotIn("derived", F["gm_latest"])


import unittest.mock  # noqa: E402  (после классов: используется внутри тестов выше)

if __name__ == "__main__":
    unittest.main()
