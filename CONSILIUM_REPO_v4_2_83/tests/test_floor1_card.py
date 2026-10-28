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

    def listing(self, cik):
        return LOADER.listing(cik)


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
        # ConvertibleDebtCurrent=0 на 2025 -- факт «долговой» группы в окне 4 ФГ: K1.3 NOT_REPORTED не срабатывает, тег долга
        # LongTermDebt по-прежнему оборван -> STALE_SERIES (отказ «по нашей вине», не класс)
        facts = tag_facts({"LongTermDebt": [("2020-12-31", 90)], "ConvertibleDebtCurrent": [("2025-12-31", 0)],
                           "CashAndCashEquivalentsAtCarryingValue": [("%d-12-31" % y, 10) for y in range(2020, 2026)]})
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
        self.assertIn("NOT_REPORTED", rec["net_debt_latest__reason"])      # K1.3: у META в окне 4 ФГ нет ни одного долгового тега
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
        self.assertEqual(r["refused"], "NOT_APPLICABLE")      # K1.1 ч.2: математически не определено -> класс, не пробел
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
                self.assertIn(f["state"], ("RAISED", "CLEAR", "UNDETERMINED", "NOT_APPLICABLE"))
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
            self.assertEqual([r["ticker"] for r in recs if not r["ticker"].startswith("_")], ["INTC", "MU", "META", "GOOG"])
            self.assertEqual(recs[-1]["ticker"], "_TOTAL")   # VOO -- бенчмарк, не строка
            md = open(os.path.join(td, names[1]), encoding="utf-8").read()
            self.assertIn("Покрытие (А)", md)
            self.assertIn("Покрытие (Б)", md)
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

    def test_f1_32_current_main_workflow_card_failure_does_not_cancel_publication(self):
        # СВОЙСТВО текущего main, а не сравнение с историческим отчётом (тот отстаёт от движущегося main).
        wf = open(os.path.join(REPO, ".github", "workflows", "panel_weekly.yml"), encoding="utf-8").read()
        steps = re.split(r"(?m)^      - (?=name:|uses:)", wf)[1:]
        card = next(s for s in steps if "tools/floor1_card.py" in s and "name: Карточка этажа 1" in s)
        pub = next(s for s in steps if "name: Публикация через PR" in s)
        self.assertIn("SEC_USER_AGENT: ${{ secrets.SEC_USER_AGENT }}", card)
        self.assertIn("TIINGO_TOKEN: ${{ secrets.TIINGO_TOKEN }}", card)
        self.assertRegex(card, r"(?m)^        continue-on-error: true\b", "падение карточки не должно красить job до публикации")
        cond = re.search(r"(?m)^        if: (.*)$", pub)
        self.assertIsNotNone(cond, "у шага публикации нет условия if")
        self.assertIn("always()", cond.group(1))
        self.assertLess(wf.index("name: Карточка этажа 1"), wf.index("name: Публикация через PR"))

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

    def test_f1_48_restricted_cash_fallback_is_marked_and_never_yields_a_clear_debt_flag(self):
        yrs = ["%d-12-31" % y for y in range(2022, 2026)]
        debt = {"LongTermDebt": [(e, 50 + 10 * i) for i, e in enumerate(yrs)]}      # долг растёт: 50..80
        shrink = lambda: syn_out()                                                      # noqa: E731
        out = shrink()
        out["shares_diluted"] = yearly([8, 7, 6, 5])                                    # акции падают
        plain = tag_facts(dict(debt, CashAndCashEquivalentsAtCarryingValue=[(e, 10) for e in yrs]))
        fall = tag_facts(dict(debt, CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents=[(e, 10) for e in yrs]))
        Fp, rp = fc.sec_fields(out, plain, EF)
        Ff, rf = fc.sec_fields(out, fall, EF)
        # те же числа, но тег разный: значение не меняется, меняется честность пометки и флага
        self.assertEqual(Fp["net_debt_chg_3y"]["value"], Ff["net_debt_chg_3y"]["value"])
        self.assertFalse(Fp["net_debt_latest"]["cash_includes_restricted"])
        self.assertEqual(fc.flag_debt_for_buybacks(Fp)["state"], "RAISED")
        for n in ("net_debt_latest", "net_debt_chg_3y"):
            self.assertTrue(Ff[n]["cash_includes_restricted"], n)
            self.assertIn("ограниченные", Ff[n]["basis"])
            self.assertNotIn("ограниченные", Fp[n]["basis"])
        fl = fc.flag_debt_for_buybacks(Ff)
        self.assertEqual(fl["state"], "UNDETERMINED")
        self.assertIn("CASH_INCLUDES_RESTRICTED", fl["evidence"])
        # и там, где без пометки был бы CLEAR (долг падает), с пометкой -- не CLEAR
        down = tag_facts({"LongTermDebt": [(e, 80 - 10 * i) for i, e in enumerate(yrs)],
                          "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": [(e, 10) for e in yrs]})
        Fd, _ = fc.sec_fields(out, down, EF)
        self.assertEqual(fc.flag_debt_for_buybacks(Fd)["state"], "UNDETERMINED")
        # запасной тег только на ДАТЕ НАЧАЛА окна: последняя точка чистая, но изменение за окно -- нет
        start = tag_facts(dict(debt, CashAndCashEquivalentsAtCarryingValue=[(e, 10) for e in yrs[1:]],
                               CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents=[(yrs[0], 10)]))
        Fs, _ = fc.sec_fields(out, start, EF)
        self.assertFalse(Fs["net_debt_latest"]["cash_includes_restricted"])
        self.assertTrue(Fs["net_debt_chg_3y"]["cash_includes_restricted"])
        self.assertEqual(fc.flag_debt_for_buybacks(Fs)["state"], "UNDETERMINED")
        self.assertIn("†", fc._fmt(Ff["net_debt_latest"]))
        self.assertNotIn("†", fc._fmt(Fp["net_debt_latest"]))

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
        # K1.3: ни GrossProfit, ни одного тега себестоимости за 4 ФГ -> NOT_REPORTED (по-прежнему отказ, не ноль и не выручка)
        self.assertEqual(refused({"fields": F}, "gm_latest"), "NOT_REPORTED")
        self.assertEqual(refused({"fields": F}, "gm_med5"), "NOT_REPORTED")
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


def sh_row(year, v, filed):
    return {"end": "%d-12-31" % year, "val": v, "accn": "0000000000-%02d-000001" % (year % 100), "filed": filed}


def split10(ends=(2022, 2023)):
    """10:1 сплит: старое значение подано <= 2023-02-01/2024-02-01, пересчитанное — 2025-02-01 (окно сплита (2024-02-01, 2025-02-01])."""
    ef = {2022: "2023-02-01", 2023: "2024-02-01"}
    return [{"end": "%d-12-31" % y, "factor": 10, "earliest_val": 100, "earliest_filed": ef[y],
             "latest_val": 1000, "latest_filed": "2025-02-01", "tag": "WeightedAverageNumberOfDilutedSharesOutstanding"}
            for y in ends]


def split_series():
    return [sh_row(2021, 100, "2022-02-01"), sh_row(2022, 1000, "2025-02-01"), sh_row(2023, 1000, "2025-02-01"),
            sh_row(2024, 1020, "2025-02-01")]


class TestSplitAdjustment(unittest.TestCase):
    """K1.1 ч.2 п.2: подтверждённый сплит -> пересчёт на сопоставимую базу (split_adjusted + коэффициент); отказ только
    для неподтверждённой базы."""

    def test_f1_39_confirmed_split_is_restated_to_a_comparable_base_and_marked(self):
        r = fc.share_change(split_series(), 3, split10(), None)
        self.assertTrue(fc.is_ok(r), r)
        self.assertAlmostEqual(r["value"], 1020 / (100 * 10) - 1, places=12)      # а не 1020/100 - 1 = +920%
        self.assertIs(r["split_adjusted"], True)
        self.assertEqual(r["split_factors"], [10])
        self.assertIn("split_adjusted", r["basis"])
        self.assertIn("10", r["basis"])

    def test_f1_40_a_window_without_a_split_is_not_marked_adjusted(self):
        r = fc.share_change(split_series(), 1, split10(), None)       # 2023 -> 2024: обе точки уже пост-сплитовые
        self.assertTrue(fc.is_ok(r), r)
        self.assertAlmostEqual(r["value"], 1020 / 1000 - 1, places=12)
        self.assertNotIn("split_adjusted", r)

    def test_f1_41_a_row_filed_inside_the_split_uncertainty_window_is_refused_not_guessed(self):
        rows = split_series()
        rows[0] = sh_row(2021, 100, "2024-08-01")          # подана между «старым» и «новым» значением: база недоказуема
        r = fc.share_change(rows, 3, split10(), None)
        self.assertEqual(r["refused"], "SPLIT_IN_WINDOW")
        self.assertIn("недоказуема", r["reason"])
        nofiled = split_series()
        del nofiled[0]["filed"]
        self.assertEqual(fc.share_change(nofiled, 3, split10(), None)["refused"], "SPLIT_IN_WINDOW")

    def test_f1_42_eps_is_computed_on_the_restated_share_base(self):
        out = syn_out()
        out["shares_diluted"] = split_series() + [sh_row(2025, 1030, "2026-02-01")]
        out["net_income"] = [{"end": "%d-12-31" % y, "val": 1000, "accn": "0000000000-00-000009"} for y in range(2021, 2026)]
        out["_flags"] = {"confirmed_splits": split10()}
        F, raw = fc.sec_fields(out, {"facts": {}}, EF)
        eps21 = next(r for r in raw["eps"] if r["end"] == "2021-12-31")
        self.assertAlmostEqual(eps21["val"], 1000 / 1000)           # 100 акций * 10 = 1000, а не 1000/100 = 10
        self.assertAlmostEqual(F["shares_chg_3y"]["value"], 1030 / 1000 - 1, places=12)   # 2022..2025 целиком пост-сплит
        self.assertNotIn("split_adjusted", F["shares_chg_3y"])
        self.assertTrue(fc.is_ok(F["eps_latest"]))


class StubSource:
    """Источник без сети: SEC-данных нет (пустые ряды), список подач задан тестом -- проверка правила scope."""
    ef, ad = EF, AD

    def __init__(self, listing_rows, boom=False):
        self.rows, self.boom = listing_rows, boom

    def read(self, ticker):
        return {"revenue": [], "net_income": []}, {"facts": {"dei": {}}}, "0000000001"

    def listing(self, cik):
        if self.boom:
            raise RuntimeError("sec listing down")
        return self.rows


def filing(form, date="2022-03-01"):
    return {"accession": "0000000001-22-%06d" % abs(hash((form, date)) % 999999), "form": form, "filing_date": date,
            "period_of_report": "2021-12-31"}


def stub_card(ticker, listing_rows, boom=False):
    return fc.build_name(ticker, "2022-10-12", StubSource(listing_rows, boom), None, {}, "no prices in this layer")


def cells(codes_f, codes_fl=()):
    """Строка для проверки счётчиков: поля с кодами отказа/значением и флаги с состоянием."""
    f = {"f%d" % i: (fc.ok(1, "USD", "b") if c == "OK" else fc.refusal(c, "r")) for i, c in enumerate(codes_f)}
    fl = {"F%d" % i: ({"state": c, "evidence": "e"} if c in ("RAISED", "CLEAR") else
                      {"state": "UNDETERMINED" if c == "UNDETERMINED" else c, "code": c, "evidence": "e"})
          for i, c in enumerate(codes_fl)}
    return f, fl


def mkrow(t, codes_f, codes_fl=(), scope="IN_SCOPE"):
    f, fl = cells(codes_f, codes_fl)
    return {"ticker": t, "fields": f, "flags": fl, "meta": {"scope": scope}}


class TestScopeAndApplicabilityClasses(unittest.TestCase):
    """K1.1 ч.2 п.4-5: классы по ПРАВИЛУ (список подач / математика), счётчики (А) и (Б)."""

    def test_f1_43_out_of_scope_form_is_decided_by_the_filing_list_not_the_ticker(self):
        no_10k = [filing("20-F"), filing("10-Q")]
        r = stub_card("NBIS", no_10k)
        self.assertEqual(r["meta"]["scope"], "OUT_OF_SCOPE_FORM")
        for n in fc.SEC_ONLY:
            self.assertEqual(refused(r, n), "OUT_OF_SCOPE_FORM", n)
        self.assertTrue(all(f["state"] == "UNDETERMINED" and f["code"] == "OUT_OF_SCOPE_FORM" for f in r["flags"].values()))
        self.assertIn("20-F", r["fields"]["rev_cagr_3y"]["reason"])
        # тот же тикер, но в списке есть 10-K до as_of -> в scope (пробел остаётся пробелом, не классом)
        r2 = stub_card("NBIS", [filing("10-K", "2022-02-01")])
        self.assertEqual(r2["meta"]["scope"], "IN_SCOPE")
        self.assertNotEqual(refused(r2, "rev_cagr_3y"), "OUT_OF_SCOPE_FORM")
        # 10-K подан ПОСЛЕ as_of -> на дату карточки годовой формы ещё нет
        r3 = stub_card("AAA", [filing("10-K", "2022-11-01")])
        self.assertEqual(r3["meta"]["scope"], "OUT_OF_SCOPE_FORM")
        # 10-K/A не годовая форма адаптера (точное совпадение)
        self.assertEqual(stub_card("AAA", [filing("10-K/A")])["meta"]["scope"], "OUT_OF_SCOPE_FORM")

    def test_f1_44_an_unreadable_filing_list_never_declares_a_name_out_of_scope(self):
        r = stub_card("NBIS", [], boom=True)
        self.assertEqual(r["meta"]["scope"], "IN_SCOPE")
        self.assertNotEqual(refused(r, "rev_cagr_3y"), "OUT_OF_SCOPE_FORM")
        self.assertEqual(fc.cell_class(r["fields"]["rev_cagr_3y"]), "GAP")

    def test_f1_45_not_applicable_is_a_class_for_mathematically_undefined_metrics_with_a_reason(self):
        for r in (fc.cagr(yearly([-5, 1, 2, 3]), 3, "ni"), fc.cagr(yearly([5, 1, 2, -3]), 3, "ni"),
                  fc.rev_accel(yearly([100, 0, 50]))):
            self.assertEqual(r["refused"], "NOT_APPLICABLE", r)
            self.assertTrue(r["reason"].strip())
        out = syn_out()
        out["net_income"] = yearly([10] * 7 + [-4])                       # NI <= 0 на последнем ФГ
        out["revenue"] = yearly([100] * 7 + [-5])                         # выручка <= 0 на последнем ФГ
        F, _ = fc.sec_fields(out, {"facts": {}}, EF)
        for n in ("fcf_to_ni", "nm_latest", "nm_med5", "rev_cagr_3y"):
            self.assertEqual(F[n]["refused"], "NOT_APPLICABLE", (n, F[n]))
            self.assertEqual(fc.cell_class(F[n]), "NOT_APPLICABLE")
        # положительные значения -- по-прежнему число, не класс
        ok_ = syn_out()
        F, _ = fc.sec_fields(ok_, {"facts": {}}, EF)
        self.assertTrue(fc.is_ok(F["fcf_to_ni"]))
        # отсутствие данных -- НЕ NOT_APPLICABLE
        self.assertEqual(fc.cell_class(fc.cagr([], 3, "revenue")), "GAP")

    def test_f1_46_counters_A_and_B_follow_the_definitions(self):
        # имя 1 (в scope): 2 заполнено, 1 пробел, 1 NOT_APPLICABLE; флаги: CLEAR, NOT_APPLICABLE, UNDETERMINED(пробел)
        a = mkrow("A", ["OK", "OK", "MISSING_INPUT", "NOT_APPLICABLE"], ["CLEAR", "NOT_APPLICABLE", "UNDETERMINED"])
        # имя 2 вне scope: 3 поля OUT_OF_SCOPE_FORM + цены (1 заполнено, 1 пробел): в (А) считаются, в (Б) -- нет
        b = mkrow("B", ["OUT_OF_SCOPE_FORM"] * 3 + ["OK", "TIINGO_UNAVAILABLE"], [], scope="OUT_OF_SCOPE_FORM")
        ab = fc.coverage_ab([a, b])
        self.assertEqual((ab["a_num"], ab["a_den"]), (4, 12))      # NOT_APPLICABLE не в числителе (А); вне-scope в знаменателе (А)
        self.assertEqual((ab["b_num"], ab["b_den"]), (3, 5))       # знаменатель (Б): 3 заполнено + 2 пробела (по нашей вине)
        self.assertAlmostEqual(ab["a"], 4 / 12.0)
        self.assertAlmostEqual(ab["b"], 0.6)
        self.assertEqual((ab["not_applicable_cells"], ab["gap_cells"], ab["out_of_scope_names"]), (2, 3, 1))
        per, cov, n_ok, n_all = fc.coverage([a, b])
        self.assertEqual((n_ok, n_all), (4, 12))
        # пустой знаменатель (Б) -- None, не 0 и не 100%
        self.assertIsNone(fc.coverage_ab([b])["b"])
        # пробел остаётся в знаменателе: добавление пробела снижает (Б)
        c = mkrow("C", ["OK", "MISSING_INPUT"])
        self.assertAlmostEqual(fc.coverage_ab([c])["b"], 0.5)
        # а NOT_APPLICABLE (Б) не снижает
        d = mkrow("D", ["OK", "NOT_APPLICABLE"])
        self.assertAlmostEqual(fc.coverage_ab([d])["b"], 1.0)

    def test_f1_47_limitations_exclude_the_two_classes_and_outputs_show_both_counters(self):
        a = mkrow("A", ["OK", "MISSING_INPUT", "NOT_APPLICABLE"], ["CLEAR", "NOT_APPLICABLE"])
        b = mkrow("B", ["OUT_OF_SCOPE_FORM"] * 2, ["UNDETERMINED"], scope="OUT_OF_SCOPE_FORM")
        b["flags"]["F0"]["code"] = "OUT_OF_SCOPE_FORM"
        self.assertEqual([(t, n) for t, n, _, _ in fc.limitations([a, b])], [("A", "f1")])
        for r in (a, b):
            r["meta"].update(fy_end=None, fy_age_days=None)
        full = lambda r: dict(r, fields={n: r["fields"].get(n, fc.refusal("MISSING_INPUT", "x")) for n in fc.FIELD_ORDER},
                              flags={n: r["flags"].get(n, {"state": "CLEAR", "evidence": "e"}) for n in fc.FLAG_ORDER})
        rows = [full(a), full(b)]
        with tempfile.TemporaryDirectory() as td:
            base, _, _ = fc.write_outputs(rows, CHECK_DATE, td, "t", {"edgartools": "x"})
            recs = list(csv.DictReader(open(base + ".csv", encoding="utf-8")))
            md = open(base + ".md", encoding="utf-8").read()
        tot = recs[-1]
        ab = fc.coverage_ab(rows)
        self.assertEqual(tot["ticker"], "_TOTAL")
        self.assertEqual(tot["coverage_A_raw"], "%.1f%%" % (100.0 * ab["a_num"] / ab["a_den"]))
        self.assertEqual(tot["coverage_B_applicable"], "%.1f%%" % (100.0 * ab["b_num"] / ab["b_den"]))
        self.assertEqual(recs[1]["coverage_B_applicable"], "")           # вне scope: (Б) не определено
        self.assertIn("Покрытие (А)", md)
        self.assertIn("Покрытие (Б)", md)
        self.assertIn("## NOT_APPLICABLE", md)
        self.assertIn("## OUT_OF_SCOPE_FORM", md)


class TestK12TagChainExtensions(unittest.TestCase):
    """K1.2: расширенные цепочки тегов (теги найдены в companyfacts живых 10-K) и именованные отказы там, где данных нет."""
    YRS = ["%d-12-31" % y for y in range(2022, 2026)]
    A = "0000000000-25-000007"

    def nd(self, tags):
        F, _ = fc.sec_fields(syn_out(), tag_facts(tags), EF)
        return F

    def test_f1_49_nflx_style_noncurrent_plus_short_term_borrowings_is_summed_with_tags(self):
        y = self.YRS
        F = self.nd({"LongTermDebtNoncurrent": [(e, 100) for e in y], "ShortTermBorrowings": [(e, 7) for e in y],
                     "CashAndCashEquivalentsAtCarryingValue": [(e, 30) for e in y]})
        f = F["net_debt_latest"]
        self.assertEqual(f["value"], 100 + 7 - 30)
        self.assertEqual(f["tags"], ["LongTermDebtNoncurrent", "ShortTermBorrowings", "CashAndCashEquivalentsAtCarryingValue"])
        self.assertFalse(F["net_debt_chg_3y"]["mixed_tags"])

    def test_f1_50_orcl_style_notes_payable_pair_and_combined_total_tag(self):
        y = self.YRS
        F = self.nd({"LongTermNotesPayable": [(e, 120) for e in y], "NotesPayableCurrent": [(e, 9) for e in y],
                     "CashAndCashEquivalentsAtCarryingValue": [(e, 20) for e in y]})
        self.assertEqual(F["net_debt_latest"]["value"], 120 + 9 - 20)
        self.assertIn("LongTermNotesPayable", F["net_debt_latest"]["tags"])
        F = self.nd({"DebtLongtermAndShorttermCombinedAmount": [(e, 50) for e in y],
                     "CashAndCashEquivalentsAtCarryingValue": [(e, 20) for e in y]})
        self.assertEqual(F["net_debt_latest"]["value"], 30)
        self.assertEqual(F["net_debt_latest"]["tags"][0], "DebtLongtermAndShorttermCombinedAmount")

    def test_f1_51_noncurrent_without_any_current_part_is_a_named_refusal_not_zero_current(self):
        y = self.YRS
        F = self.nd({"LongTermDebtNoncurrent": [(e, 100) for e in y], "CashAndCashEquivalentsAtCarryingValue": [(e, 30) for e in y]})
        for n in ("net_debt_latest", "net_debt_chg_3y"):
            self.assertEqual(refused({"fields": F}, n), "MISSING_INPUT")
        self.assertIn("не раскрыт", F["net_debt_latest"]["reason"])
        # долг оборвался давно (PLTR): тоже отказ с причиной, а не ноль и не «последнее известное»
        old = self.nd({"LongTermDebtNoncurrent": [("2020-12-31", 200), ("2021-12-31", 0)], "ConvertibleDebtCurrent": [("2025-12-31", 0)],
                       "CashAndCashEquivalentsAtCarryingValue": [(e, 30) for e in ["2020-12-31", "2021-12-31"] + self.YRS]})
        self.assertNotEqual(old["net_debt_latest"].get("refused"), None)
        self.assertIn(old["net_debt_latest"]["refused"], ("MISSING_INPUT", "STALE_SERIES"))

    def test_f1_52_cost_excluding_da_gives_gross_margin_labelled_with_its_basis(self):
        a = self.A
        facts = dur_facts({"Revenues": [(y, 100, a) for y in range(2018, 2026)],
                           fc.COST_EXDA_TAG: [(y, 40, a) for y in range(2018, 2026)]})
        F, _ = fc.sec_fields(syn_out(), facts, EF)
        g = F["gm_latest"]
        self.assertAlmostEqual(g["value"], 0.6, places=12)
        self.assertTrue(g["derived"])
        self.assertIn(fc.COST_EXDA_TAG, g["tags"])
        self.assertIn("БЕЗ амортизации", g["basis"])
        plain = dur_facts({"Revenues": [(y, 100, a) for y in range(2018, 2026)],
                           "CostOfRevenue": [(y, 40, a) for y in range(2018, 2026)]})
        F, _ = fc.sec_fields(syn_out(), plain, EF)
        self.assertNotIn("БЕЗ амортизации", F["gm_latest"]["basis"])

    def test_f1_53_capex_fallback_tag_only_when_standard_capex_is_absent_and_is_marked(self):
        a = self.A
        facts = dur_facts({fc.CAPEX_FALLBACK_TAGS[0]: [(y, 8, a) for y in range(2018, 2026)]})
        out = syn_out()
        del out["capex"]
        F, _ = fc.sec_fields(out, facts, EF)
        self.assertEqual(F["fcf_latest"]["value"], 30 - 8)
        self.assertIn("запасного тега", F["fcf_latest"]["basis"])
        self.assertEqual(F["fcf_latest"]["tags"], fc.CAPEX_FALLBACK_TAGS)
        # штатный capex есть -- запасной не используется и не подмешивается
        F, _ = fc.sec_fields(syn_out(), facts, EF)
        self.assertEqual(F["fcf_latest"]["value"], 30 - 5)
        self.assertNotIn("запасного", F["fcf_latest"]["basis"])
        # нет ни штатного, ни запасного -- отказ, не «OCF без capex»
        out = syn_out()
        del out["capex"]
        F, _ = fc.sec_fields(out, dur_facts({"Revenues": [(2025, 1, a)]}), EF)
        self.assertEqual(refused({"fields": F}, "fcf_latest"), "NOT_REPORTED")   # K1.3: capex-тегов в окне нет вовсе
        # capex-тег есть, но не на последний ФГ (факт 2023 в окне 4 ФГ) -- класса нет, прежний отказ по нашей части
        F, _ = fc.sec_fields(out, dur_facts({"PaymentsToAcquirePropertyPlantAndEquipment": [(2023, 1, a)],
                                                         "NetCashProvidedByUsedInOperatingActivities": [(2025, 30, a)]}), EF)
        self.assertEqual(refused({"fields": F}, "fcf_latest"), "MISSING_INPUT")


class TestK13NotReported(unittest.TestCase):
    """K1.3 п.1: NOT_REPORTED -- по ПРАВИЛУ над companyfacts: ни одного факта по тегам цепочки поля за последний ФГ карточки
    и 3 предшествующих. Хоть один факт в окне -- класса нет (пробел по нашей вине)."""
    A = "0000000000-25-000007"
    CASH = {"CashAndCashEquivalentsAtCarryingValue": [("%d-12-31" % y, 10) for y in range(2021, 2026)]}

    def fields(self, facts, out=None):
        F, _ = fc.sec_fields(out or syn_out(), facts, EF)
        return F

    def test_f1_54_no_fact_in_four_fiscal_years_is_not_reported_and_names_every_checked_tag(self):
        F = self.fields(tag_facts(self.CASH))          # долговых тегов в companyfacts нет вовсе
        for n in ("net_debt_latest", "net_debt_chg_3y"):
            self.assertEqual(refused({"fields": F}, n), fc.NOT_REPORTED, n)
            self.assertEqual(fc.cell_class(F[n]), fc.NOT_REPORTED)
        r = F["net_debt_latest"]
        for tag in fc.DEBT_FULL_CHAIN + fc.DEBT_NONC_CHAIN + fc.DEBT_CUR_CHAIN + [fc.CONVERTIBLE_PREFIX + "*"]:
            self.assertIn(tag, r["tags_checked"])      # проверены ВСЕ долговые теги цепочки и ConvertibleDebt*
            self.assertIn(tag, r["reason"])
        self.assertIn("не представлено компанией: долг", r["reason"])
        self.assertEqual(r["fy"], "2025-12-31")
        # выручка не отчитана -> и рост, и все шесть маржей: NOT_REPORTED (OKLO)
        F = self.fields(dur_facts({"NetIncomeLoss": [(y, 10, self.A) for y in range(2021, 2026)]}), dict(syn_out(), revenue=None))
        for n in ("rev_cagr_3y", "rev_cagr_5y", "rev_accel", "gm_latest", "gm_med5", "om_latest", "om_med5", "nm_latest", "nm_med5"):
            self.assertEqual(fc.cell_class(F[n]), fc.NOT_REPORTED, n)
            self.assertIn("выручка", F[n]["reason"], n)

    def test_f1_55_a_single_fact_in_any_of_the_four_fiscal_years_means_a_gap_not_a_class(self):
        # окно: ФГ 2025 и 3 предыдущих => end >= 2022-12-10; факт 2022-12-31 (3 ФГ назад) -- в окне; 2021-12-31 -- вне
        inside = tag_facts(dict(self.CASH, LongTermDebtNoncurrent=[("2022-12-31", 5)]))
        outside = tag_facts(dict(self.CASH, LongTermDebtNoncurrent=[("2021-12-31", 5)]))
        self.assertNotEqual(fc.cell_class(self.fields(inside)["net_debt_latest"]), fc.NOT_REPORTED)
        self.assertEqual(fc.cell_class(self.fields(outside)["net_debt_latest"]), fc.NOT_REPORTED)
        # SHOP: единственный долговой факт -- ConvertibleDebtCurrent = 0 на последний ФГ: это факт, значит пробел, не класс
        shop = self.fields(tag_facts(dict(self.CASH, ConvertibleDebtCurrent=[("2025-12-31", 0)])))
        for n in ("net_debt_latest", "net_debt_chg_3y"):
            self.assertEqual(fc.cell_class(shop[n]), "GAP", n)
        # запасной тег цепочки (не первый) тоже считается: NotesPayableCurrent
        fb = self.fields(tag_facts(dict(self.CASH, NotesPayableCurrent=[("2024-12-31", 1)])))
        self.assertEqual(fc.cell_class(fb["net_debt_latest"]), "GAP")

    def test_f1_56_class_only_for_absence_refusals_never_for_our_own_decision_refusals(self):
        # GOOG: акции раскрыты по классам, отказ MULTI_CLASS_NOT_SUMMED -- наш. Тегов общего числа акций в companyfacts нет,
        # но это НЕ «компания не представила»: класс не ставится
        out = syn_out()
        del out["shares_diluted"]
        out["_refusals"] = {"shares_diluted": fc.refusal("MULTI_CLASS_NOT_SUMMED", "акции по классам не суммируются")}
        F = self.fields(dur_facts({"Revenues": [(y, 100, self.A) for y in range(2021, 2026)]}), out)
        for n in ("eps_latest", "shares_chg_1y", "shares_chg_3y"):
            self.assertEqual(F[n]["refused"], "MULTI_CLASS_NOT_SUMMED", n)

    def test_f1_57_a_filled_cell_and_a_missing_companyfacts_are_never_reclassified(self):
        F = self.fields(dur_facts({"Revenues": [(y, 100, self.A) for y in range(2021, 2026)]}))
        self.assertTrue(fc.is_ok(F["rev_cagr_3y"]))
        # нет companyfacts вообще (чтение не удалось) -- ничего не объявляем «не представлено»
        F, _ = fc.sec_fields(dict(syn_out(), revenue=None), None, EF)
        self.assertFalse(any(fc.cell_class(f) == fc.NOT_REPORTED for f in F.values()))


class TestK13ShortHistory(unittest.TestCase):
    """K1.3 п.2: SHORT_HISTORY -- окну поля нужно N ФГ, а самый ранний годовой факт выручки позже начала окна. Есть ранняя
    история, но нет конкретной точки (CELH) -- пробел, не класс."""
    A = "0000000000-25-000007"

    def short_out(self, n_years):
        return dict(syn_out(), revenue=yearly([100] * n_years), net_income=yearly([10] * n_years),
                    shares_diluted=yearly([5] * n_years))

    def rev_facts(self, years, tag="Revenues"):
        return dur_facts({tag: [(y, 100, self.A) for y in years]})

    def test_f1_58_window_longer_than_revenue_history_is_short_history_with_dates(self):
        F, _ = fc.sec_fields(self.short_out(2), self.rev_facts([2024, 2025]), EF)
        for n, need in (("rev_cagr_3y", 3), ("rev_cagr_5y", 5), ("rev_accel", 2), ("nm_med5", 4)):
            f = F[n]
            self.assertEqual(f.get("refused"), fc.SHORT_HISTORY, n)
            self.assertEqual(fc.cell_class(f), fc.SHORT_HISTORY)
            self.assertEqual((f["need_fy"], f["earliest_revenue_end"], f["fy"]), (need, "2024-12-31", "2025-12-31"), n)
            self.assertIn("2024-12-31", f["reason"])
            self.assertIn(f["window_start"], f["reason"])
        self.assertTrue(fc.is_ok(F["rev_cagr_3y"]) is False and fc.is_ok(F["ni_latest"]))

    def test_f1_59_early_history_but_missing_point_is_a_gap_not_a_class(self):
        # CELH: выручка есть с 2016, а точки долга за 3 ФГ назад нет -- наша дыра, не короткая история
        facts = self.rev_facts(range(2016, 2026))
        facts["facts"]["us-gaap"].update(tag_facts({"LongTermDebt": [("2024-12-31", 9), ("2025-12-31", 9)],
                                                    "CashAndCashEquivalentsAtCarryingValue": [("2024-12-31", 1), ("2025-12-31", 1)]})
                                         ["facts"]["us-gaap"])
        F, _ = fc.sec_fields(syn_out(), facts, EF)
        self.assertEqual(F["net_debt_chg_3y"]["refused"], "INSUFFICIENT_HISTORY")
        self.assertEqual(fc.cell_class(F["net_debt_chg_3y"]), "GAP")
        # то же для окна, где история короче нужной ровно в пределах допуска ФГ 52/53 недели (точка могла бы быть)
        F, _ = fc.sec_fields(self.short_out(3), self.rev_facts([2023, 2024, 2025]), EF)
        self.assertEqual(fc.cell_class(F["rev_cagr_3y"]), fc.SHORT_HISTORY)          # 2023-12-31 позже 2022-12-30 на 366 дн.
        facts = self.rev_facts([2025])
        facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"].append(
            {"start": "2022-01-10", "end": "2023-01-10", "val": 100, "form": "10-K", "filed": "2023-02-01", "accn": self.A})
        F, _ = fc.sec_fields(self.short_out(3), facts, EF)
        self.assertEqual(fc.cell_class(F["rev_cagr_3y"]), "GAP")                      # 2023-01-10 - 2022-12-30 = 11 дн. <= допуска

    def test_f1_60_early_revenue_history_under_any_revenue_tag_counts_as_history(self):
        facts = self.rev_facts([2024, 2025])
        facts["facts"]["us-gaap"].update(self.rev_facts(range(2016, 2024), tag="SalesRevenueNet")["facts"]["us-gaap"])
        F, _ = fc.sec_fields(self.short_out(2), facts, EF)
        self.assertEqual(fc.cell_class(F["rev_cagr_5y"]), "GAP")

    def test_f1_61_short_history_needs_annual_revenue_to_prove_and_only_replaces_insufficient_history(self):
        F, _ = fc.sec_fields(self.short_out(2), dur_facts({"NetIncomeLoss": [(2024, 1, self.A), (2025, 1, self.A)]}), EF)
        self.assertFalse(any(fc.cell_class(f) == fc.SHORT_HISTORY for f in F.values()))    # нет выручки -- доказать нечем
        F, _ = fc.sec_fields(self.short_out(2), self.rev_facts([2024, 2025]), EF)
        self.assertTrue(all(fc.cell_class(F[n]) == "FILLED" for n in ("ni_latest", "eps_latest")))
        # другой код пробела (операционная прибыль в companyfacts есть, а ряда в данных адаптера нет -> MISSING_INPUT) при
        # короткой выручке НЕ превращается в SHORT_HISTORY: класс заменяет только INSUFFICIENT_HISTORY
        facts = self.rev_facts([2024, 2025])
        facts["facts"]["us-gaap"].update(dur_facts({"OperatingIncomeLoss": [(2025, 1, self.A)]})["facts"]["us-gaap"])
        F, _ = fc.sec_fields(self.short_out(2), facts, EF)
        self.assertEqual(F["om_med5"]["refused"], "MISSING_INPUT")
        self.assertEqual(fc.cell_class(F["om_med5"]), "GAP")

    def test_f1_62_dd_52w_short_price_series_is_short_history_with_first_quote_date(self):
        a = "2026-10-27"
        d0 = dt.date.fromisoformat(a)
        short = {(d0 - dt.timedelta(days=i)).isoformat(): 10.0 + i for i in range(120)}
        full = {(d0 - dt.timedelta(days=i)).isoformat(): 10.0 + i for i in range(400)}
        b = full
        F = fc.price_fields(short, {"VOO": b, "QQQ": b}, a)
        self.assertEqual(F["dd_52w"]["refused"], fc.SHORT_HISTORY)
        self.assertEqual(F["dd_52w"]["first_quote"], min(short))
        self.assertIn(min(short), F["dd_52w"]["reason"])
        self.assertTrue(fc.is_ok(fc.price_fields(full, {"VOO": b, "QQQ": b}, a)["dd_52w"]))


import datetime as dt  # noqa: E402


import unittest.mock  # noqa: E402  (после классов: используется внутри тестов выше)

if __name__ == "__main__":
    unittest.main()
