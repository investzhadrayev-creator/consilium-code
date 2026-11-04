"""К6 часть A: генератор досье tools/dossier.py. Всё на синтетике, без сети, модели не вызываются.

Тесты проверяют СВОЙСТВА (арифметика на ручных примерах, отказ вместо нуля, срез по as_of, зависимость блока
«опровергнет» от входа), а не форму текста. К каждому пину dos-NN есть мутация в tools/mutation_probe.py.

  TestArithmetic   -- сетка доходности, требуемый рост, P/E-сетка, рост выручки по ФГ: ручные примеры.
  TestReverseDCF   -- решение воспроизводит порог; монотонность; отказы вместо подстановки.
  TestPrices       -- срез по as_of, устаревшая цена, годовая доходность пассива.
  TestMissingIsNotZero -- нет факта -> именованный отказ, нигде не 0.
  TestReports      -- 6 разделов machine даже при полном отказе; brief без вердикта; accession у чисел; блок «опровергнет».
  TestCli          -- хэш входа, append-only, коды выхода.
"""
import contextlib
import datetime as dt
import io
import os
import re
import sys
import tempfile
import unittest
import unittest.mock

sys.dont_write_bytecode = True   # мутационный зонд правит tools/ -- устаревший .pyc не должен пережить правку
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, os.path.join(REPO, "tools", "guards"))

import dossier as dos    # noqa: E402
import floor1_card as fc  # noqa: E402

EF, AD = fc.load_sec_modules()
AS_OF = "2020-02-15"
ACCN_RE = re.compile(r"\d{10}-\d{2}-\d{6}")


def rec(y, val, tag, code, filed=None, unit="USD"):
    return {"end": "%d-12-31" % y, "val": val, "accn": "0000000000-%02d-%06d" % ((y + 1) % 100, code),
            "filed": filed or "%d-02-10" % (y + 1), "unit": unit, "form": "10-K", "tag": tag}


def series(tag, code, vals, unit="USD", last_filed=None):
    ys = sorted(vals)
    return [rec(y, vals[y], tag, code, filed=(last_filed if (y == ys[-1] and last_filed) else None), unit=unit) for y in ys]


def mk_out(rev=None, ni=100, ocf=150, capex=50, shares=10, years=range(2015, 2020), name="Тестовая Компания", last_filed=None):
    """Адаптерный выход: годовые ряды, 100 NI, FCF/NI = 1.0 в каждом ФГ."""
    rev = rev or {y: int(1000 * 1.1 ** (y - 2015)) for y in years}
    out = {"_entity_name": name, "_ticker": "TEST", "_flags": {}, "_staleness": {}, "_refusals": {}}
    for key, tag, code, vals, unit in (
            ("revenue", "Revenues", 1, rev, "USD"),
            ("net_income", "NetIncomeLoss", 2, {y: ni for y in years}, "USD"),
            ("operating_income", "OperatingIncomeLoss", 3, {y: 200 for y in years}, "USD"),
            ("ocf", "NetCashProvidedByUsedInOperatingActivities", 4, {y: ocf for y in years}, "USD"),
            ("capex", "PaymentsToAcquirePropertyPlantAndEquipment", 5, {y: capex for y in years}, "USD"),
            ("shares_diluted", "WeightedAverageNumberOfDilutedSharesOutstanding", 6, {y: shares for y in years}, "shares")):
        if vals is None or (key in ("ocf", "capex", "net_income", "shares_diluted") and {"ocf": ocf, "capex": capex, "net_income": ni,
                                                                                           "shares_diluted": shares}[key] is None):
            continue
        out[key] = series(tag, code, vals, unit, last_filed)
        out[key + "_audit"] = out[key]
    return out


class FakeSource:
    ef, ad = EF, AD

    def __init__(self, out, facts=None):
        self.out, self.facts, self.as_of = out, facts, None

    def read(self, ticker):
        return self.out, self.facts, "0000000001"

    def listing(self, cik):
        return []


def daily(start, end, f):
    """{date: (close, adj)} каждый календарный день; f(дней от start) -> (close, adj)."""
    d0, d1 = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    return {(d0 + dt.timedelta(days=i)).isoformat(): f(i) for i in range((d1 - d0).days + 1)}


END = "2020-02-14"
GROW10 = lambda i: (100 * 1.1 ** (i / 365.0),) * 2          # noqa: E731  ровно +10% в год на любом окне


def fake_fetch(price=100.0, bench=None):
    def fetch(t):
        if t in fc.BENCH_RS:
            return bench if bench is not None else daily("2014-01-01", END, GROW10)
        return {END: (price, price), "2020-02-13": (price, price)}
    return fetch


def make(out=None, price=100.0, nd=50, fetch=None, facts=None):
    """D для синтетики. Чистый долг карточка из пустых фактов не соберёт (отказ) -- подставляем точку и пересчитываем."""
    D = dos.build("TEST", AS_OF, FakeSource(out or mk_out(), facts), fetch or fake_fetch(price))
    if nd is not None:
        D["nd"] = fc.ok(nd, "USD", "тест", ["тест"])
        D["derived"] = dos.derive(D)
    return D


class TestArithmetic(unittest.TestCase):
    def test_dos_01_ev_s_grid_hand_examples(self):
        # выручка 100, 10 акций, цена 10, долга нет. g=100%, EV/S=1: EV_T=100*2^10=102400 -> 10240/акцию -> x1024 -> 2^10 -> ровно +100%/год
        self.assertAlmostEqual(dos.ev_s_return(100, 10, 0, 10, 1.0, 1), 1.0, places=9)
        # g=0, EV/S=2 -> EV_T=200 -> x2 за 10 лет
        self.assertAlmostEqual(dos.ev_s_return(100, 10, 0, 10, 0.0, 2), 2 ** 0.1 - 1, places=9)
        # долг 50, g=0, EV/S=1.5: EV_T=150, капитал 100 -> 10/акцию -> 0%
        self.assertAlmostEqual(dos.ev_s_return(100, 10, 50, 10, 0.0, 1.5), 0.0, places=9)

    def test_dos_02_negative_equity_is_a_refusal_not_minus_100(self):
        r = dos.ev_s_return(100, 10, 500, 10, 0.0, 1.0)
        self.assertTrue(dos.is_ref(r))
        self.assertEqual(r["refused"], "NONPOSITIVE_EQUITY")

    def test_dos_03_pe_grid_hand_and_nonpositive_ni(self):
        self.assertAlmostEqual(dos.pe_return(10, 10, 10, 1.0, 10), 1.0, places=9)    # P/E 10 на EPS 1 при цене 10, g=100% -> x1024
        self.assertAlmostEqual(dos.pe_return(10, 10, 10, 0.0, 10), 0.0, places=9)
        for ni in (0, -5, None):
            r = dos.pe_return(ni, 10, 10, 0.1, 20)
            self.assertTrue(dos.is_ref(r), ni)
            self.assertEqual(r["refused"], "NONPOSITIVE_NI")

    def test_dos_04_required_growth_hand_and_roundtrip(self):
        # EV/S=1, долга нет: цена должна вырасти x1.12^10, значит выручка растёт ровно на 12%
        self.assertAlmostEqual(dos.required_growth_ev_s(100, 10, 0, 10, 1.0), 0.12, places=9)
        self.assertAlmostEqual(dos.required_growth_ev_s(100, 10, 0, 10, 2.0), 1.12 / 2 ** 0.1 - 1, places=9)
        # долг входит в EV: при долге 50 и цене 10*10=100 нужный EV_T = 100*1.12^10 + 50
        g = dos.required_growth_ev_s(100, 10, 50, 10, 1.0)
        self.assertAlmostEqual(g, ((100 * 1.12 ** 10 + 50) / 100) ** 0.1 - 1, places=9)
        self.assertAlmostEqual(dos.ev_s_return(100, 10, 50, 10, g, 1.0), 0.12, places=9)   # обратная функция сходится

    def test_dos_05_last_growths_by_fiscal_year(self):
        pts = [{"end": "201%d-12-31" % i, "val": v} for i, v in enumerate((100, 110, 121))]
        got = dos.last_growths(pts, 2)
        self.assertEqual([e for e, _ in got], ["2011-12-31", "2012-12-31"])
        self.assertAlmostEqual(got[0][1], 0.10)
        self.assertAlmostEqual(got[1][1], 0.10)
        self.assertEqual(dos.last_growths(pts[:2], 2), [])      # не хватает ФГ -> пусто, не рост от нуля


class TestReverseDCF(unittest.TestCase):
    ivc = staticmethod(dos.load_ivc())

    def test_dos_10_solution_reproduces_the_hurdle(self):
        r = dos.reverse_dcf(self.ivc, 100.0, 5.0, None, 20)
        self.assertFalse(dos.is_ref(r))
        got = self.ivc({"price": 100.0, "eps_normalized": 5.0, "growth_rate": r["g"], "future_pe": 20, "hurdle": 0.12, "years": 10,
                        "terminal_growth": min(0.04, r["g"]), "fade": True})["implied_cagr_pct"]
        self.assertAlmostEqual(got, 12.0, delta=0.1)

    def test_dos_11_higher_exit_multiple_needs_less_growth(self):
        gs = [dos.reverse_dcf(self.ivc, 100.0, 5.0, None, pe)["g"] for pe in (10, 15, 20, 25, 30)]
        self.assertEqual(gs, sorted(gs, reverse=True))
        self.assertLess(gs[-1], gs[0])

    def test_dos_12_nonpositive_base_is_refused_by_name(self):
        for eps in (0.0, -1.0):
            r = dos.reverse_dcf(self.ivc, 100.0, eps, None, 20)
            self.assertEqual(r.get("refused"), "NONPOSITIVE_BASE")
        r = dos.reverse_dcf(self.ivc, 100.0, None, -3.0, 20)
        self.assertEqual(r.get("refused"), "NONPOSITIVE_BASE")

    def test_dos_13_unreachable_growth_is_out_of_bounds_not_a_number(self):
        r = dos.reverse_dcf(self.ivc, 1e9, 1.0, None, 10)       # цена в миллиард раз выше прибыли: даже +100% в год не хватает
        self.assertEqual(r.get("refused"), "OUT_OF_BOUNDS")


class TestPrices(unittest.TestCase):
    def test_dos_20_price_uses_only_closes_up_to_as_of(self):
        s = {"2020-02-13": (100.0, 100.0), "2020-02-14": (101.0, 101.0), "2020-03-01": (999.0, 999.0)}
        p, d, ref = dos.spot_price(s, AS_OF)
        self.assertEqual((p, d, ref), (101.0, "2020-02-14", None))

    def test_dos_21_stale_price_is_a_refusal(self):
        p, d, ref = dos.spot_price({"2020-01-02": (50.0, 50.0)}, AS_OF)
        self.assertIsNone(p)
        self.assertEqual(ref["refused"], "PRICE_STALE")

    def test_dos_22_passive_return_is_annualised_and_windowed(self):
        s = daily("2014-01-01", END, GROW10)
        # добавляем «будущее» после as_of: оно не должно менять ничего
        s["2020-06-01"] = (1e6, 1e6)
        r = dos.passive_returns(s, AS_OF)
        for n in (1, 3, 5):
            self.assertAlmostEqual(r[n]["annual"], 0.10, places=3)
        self.assertAlmostEqual(r[3]["total"], 1.1 ** 3 - 1, places=3)
        self.assertEqual(r[5]["d1"], END)

    def test_dos_23_short_history_is_a_refusal(self):
        r = dos.passive_returns(daily("2019-06-01", END, GROW10), AS_OF)
        self.assertEqual(r[5]["refused"], "INSUFFICIENT_HISTORY")
        self.assertFalse(dos.is_ref(r[1]) and False)


class TestMissingIsNotZero(unittest.TestCase):
    def numbers_in_grid(self, D):
        return [v for v in D["derived"]["grid_ev_s"].values() if not dos.is_ref(v)]

    def test_dos_30_no_net_debt_refuses_the_ev_grid(self):
        D = make(nd=None)             # карточка из синтетики чистый долг не собирает: отказ, а не долг = 0
        self.assertTrue(dos.is_ref(D["nd"]))
        self.assertEqual(self.numbers_in_grid(D), [])
        self.assertTrue(dos.is_ref(D["derived"]["g_req"]))
        self.assertIn("чистый долг", D["derived"]["missing"])

    def test_dos_31_missing_ocf_gives_no_fcf_and_no_ratio(self):
        D = make(out=mk_out(ocf=None))
        self.assertIsNone(D["derived"]["fcf"])
        self.assertIsNone(D["derived"]["fcf_ni"])
        self.assertNotIn("0.00", dos.render_brief(D).split("## 2.")[1].split("## 3.")[0])

    def test_dos_32_price_outage_refuses_everything_priced(self):
        def boom(t):
            raise RuntimeError("Tiingo down")
        D = make(fetch=boom)
        self.assertIsNone(D["price"])
        self.assertEqual(self.numbers_in_grid(D), [])
        self.assertTrue(all(dos.is_ref(v) for v in D["derived"]["rdcf"].values()))
        self.assertTrue(all(dos.is_ref(D["passive"]["VOO"][n]) for n in (1, 3, 5)))

    def test_dos_33_nonpositive_ni_refuses_pe_grid_and_fcf_ni(self):
        D = make(out=mk_out(ni=-5))
        self.assertTrue(all(dos.is_ref(v) for v in D["derived"]["grid_pe"].values()))
        self.assertIsNone(D["derived"]["fcf_ni"])

    def test_dos_34_guard_slices_by_as_of(self):
        out = mk_out(last_filed="2020-03-01")                  # ФГ2019 подан ПОСЛЕ as_of, и в нём OCF < 0
        for k in ("ocf", "ocf_audit"):
            out[k] = out[k][:-1] + [dict(out[k][-1], val=-10)]
        D = make(out=out)
        self.assertEqual(D["guard"].get("fiscal_year_end"), "2018-12-31")
        self.assertNotEqual(D["guard"]["rule"], "R1")


def machine_and_brief(D):
    return dos.render_machine(D), dos.render_brief(D)


class TestReports(unittest.TestCase):
    def test_dos_40_all_six_sections_exist_even_when_everything_is_refused(self):
        src = FakeSource({"_errors": {"adapter": "SEC down"}})
        D = dos.build("TEST", AS_OF, src, lambda t: (_ for _ in ()).throw(RuntimeError("down")))
        text, _ = machine_and_brief(D)
        for letter in dos.SECTIONS:
            m = re.search(r"^## \(%s\)[^\n]*\n(.*?)(?=^## \(|\Z)" % letter, text, re.M | re.S)
            self.assertIsNotNone(m, "нет раздела (%s)" % letter)
            self.assertTrue(m.group(1).strip(), "раздел (%s) пуст: пустой раздел должен быть именованным отказом" % letter)
        self.assertIn("ОТКАЗ", text)

    def test_dos_41_numbers_in_section_a_carry_accession(self):
        text, _ = machine_and_brief(make())
        a = text.split("## (а)")[1].split("## (б)")[0]
        rows = [l for l in a.splitlines() if l.startswith("| ") and "---" not in l and "Строка" not in l and "| — |" not in l]
        self.assertGreaterEqual(len(rows), 6)
        for l in rows:
            self.assertRegex(l, ACCN_RE, l)

    def test_dos_42_non_gaap_is_named_not_checked(self):
        text, _ = machine_and_brief(make())
        self.assertIn("NON_GAAP_NOT_CHECKED", text)

    def test_dos_43_brief_has_no_verdict_and_five_blocks(self):
        _, brief = machine_and_brief(make())
        for bad in (r"\bBUY\b", r"\bAVOID\b", r"\bWATCH", "покупать", "Покупать", "продавать"):
            self.assertIsNone(re.search(bad, brief), bad)
        for n in range(1, 6):
            self.assertIn("## %d." % n, brief)
        self.assertLessEqual(len([l for l in brief.splitlines() if l.strip()]), 70)      # 1-2 страницы

    def test_dos_44_refute_block_changes_with_inputs(self):
        a = make(price=100.0)
        b = make(price=200.0)
        ta, xa = dos.truth_refute(a)
        tb, xb = dos.truth_refute(b)
        self.assertNotEqual(ta, tb)
        self.assertNotEqual(xa, xb)
        # порог «опровергнет» = требуемый рост - 5 п.п., по формуле от данных
        for D, X in ((a, xa), (b, xb)):
            self.assertIn(dos.pp(D["derived"]["g_req"] - 0.05), X[0])
        # и от денежной конвертации
        c = make(out=mk_out(ocf=80, capex=50))        # FCF/NI = 0.30
        self.assertIn("0.30", " ".join(dos.truth_refute(c)[1]))
        self.assertIn("1.00", " ".join(dos.truth_refute(a)[1]))

    def test_dos_45_truth_block_uses_the_computed_required_growth(self):
        D = make()
        T, _ = dos.truth_refute(D)
        g = dos.required_growth_ev_s(_v(D, "revenue"), _v(D, "shares_diluted"), 50, 100.0, D["derived"]["ev_s"])
        self.assertIn(dos.pp(g), T[0])

    def test_dos_46_grid_in_report_matches_function(self):
        D = make()
        text = dos.render_machine(D)
        rev, sh = _v(D, "revenue"), _v(D, "shares_diluted")
        want = dos.pc(dos.ev_s_return(rev, sh, 50, 100.0, 0.10, 20))
        row = [l for l in text.splitlines() if l.startswith("| 10% |")][0]
        self.assertIn(want, row)

    def test_dos_47_machine_report_has_time_and_hash(self):
        D = make()
        text = dos.render_machine(D)
        self.assertIn(D["input_hash"], text)
        self.assertRegex(text, r"Время машины[^\n]*с ")

    def test_dos_48_dossier_never_calls_a_model(self):
        src = open(os.path.join(REPO, "tools", "dossier.py"), encoding="utf-8").read()
        for bad in ("anthropic", "openai", "llm_clients", "messages.create"):
            self.assertNotIn(bad, src)


def _v(D, k):
    return D["raw"][k]["val"]


class TestDebtRaw(unittest.TestCase):
    """Сырые факты чистого долга (К6 ч. B): слагаемые, а не только итог; расхождение тегов видно читателю."""
    @staticmethod
    def facts(rows):
        """{тег: {год: значение}} -> companyfacts-подобный dict (годовые instant-факты 10-K)."""
        return {"facts": {"us-gaap": {tag: {"units": {"USD": [
            {"end": "%d-12-31" % y, "val": v, "accn": "0000000000-%02d-%06d" % ((y + 1) % 100, 1), "fy": y, "fp": "FY",
             "form": "10-K", "filed": "%d-02-10" % (y + 1)} for y, v in sorted(vals.items())]}} for i, (tag, vals) in enumerate(rows.items(), 1)}}}

    def nd(self, facts):
        series, ref = fc.net_debt_series(facts, EF)
        self.assertIsNone(ref)
        last = series[-1]
        return fc.ok(last["val"], "USD", "тест", last["accn"], tags=last["tags"])

    def test_dos_60_raw_parts_are_the_exact_terms_of_the_card_number(self):
        f = self.facts({"LongTermDebt": {2018: 100, 2019: 700}, "CashAndCashEquivalentsAtCarryingValue": {2018: 30, 2019: 250}})
        r = dos.debt_raw(f, EF, self.nd(f))
        self.assertEqual([(p["tag"], p["val"], p["end"]) for p in r["debt"]], [("LongTermDebt", 700, "2019-12-31")])
        self.assertEqual((r["cash"]["tag"], r["cash"]["val"]), ("CashAndCashEquivalentsAtCarryingValue", 250))
        self.assertEqual(r["total"], 450)
        self.assertEqual(sum(p["val"] for p in r["debt"]) - r["cash"]["val"], r["total"])

    def test_dos_61_nonprimary_tag_on_same_date_is_shown_but_not_used(self):
        # NFLX 2019: LongTermDebt = «итого обязательств по долгу» (с процентами), баланс -- LongTermDebtNoncurrent
        # (DECISION_2026-11-02: в расчёт идут балансовые части, «полный» тег показан справочно + флаг)
        f = self.facts({"LongTermDebt": {2019: 700}, "LongTermDebtNoncurrent": {2019: 480},
                        "CashAndCashEquivalentsAtCarryingValue": {2019: 250}})
        r = dos.debt_raw(f, EF, self.nd(f))
        self.assertEqual(r["total"], 230)                        # число не подменено «правдоподобным» тегом
        self.assertEqual([(p["tag"], p["val"]) for p in r["unused"]], [("LongTermDebt", 700)])
        self.assertEqual([x["full_val"] for x in r["flags"]], [700])

    def test_dos_62_split_debt_shows_both_terms(self):
        f = self.facts({"LongTermDebtNoncurrent": {2019: 500}, "LongTermDebtCurrent": {2019: 40},
                        "CashAndCashEquivalentsAtCarryingValue": {2019: 100}})
        r = dos.debt_raw(f, EF, self.nd(f))
        self.assertEqual(sorted(p["val"] for p in r["debt"]), [40, 500])
        self.assertEqual(r["total"], 440)

    def test_dos_63_mismatch_with_card_is_a_refusal_not_a_fit(self):
        f = self.facts({"LongTermDebt": {2019: 700}, "CashAndCashEquivalentsAtCarryingValue": {2019: 250}})
        r = dos.debt_raw(f, EF, fc.ok(451, "USD", "тест", ["x"]))
        self.assertTrue(dos.is_ref(r))
        self.assertEqual(r["refused"], "RAW_MISMATCH")

    def test_dos_64_refused_net_debt_gives_refusal_not_empty_table(self):
        ref = fc.refusal("NOT_REPORTED", "нет тегов долга")
        self.assertIs(dos.debt_raw(self.facts({}), EF, ref), ref)
        self.assertEqual(dos.debt_raw(None, EF, fc.ok(1, "USD", "т", ["x"]))["refused"], "NOT_IN_SOURCE")

    def test_dos_65_report_prints_terms_formula_and_accession(self):
        f = self.facts({"LongTermDebt": {2019: 700}, "LongTermDebtNoncurrent": {2019: 480},
                        "CashAndCashEquivalentsAtCarryingValue": {2019: 250}})
        D = make(nd=None)
        D["nd"] = self.nd(f)
        D["nd_raw"] = dos.debt_raw(f, EF, D["nd"])
        b = dos.render_machine(D).split("## (б)")[1].split("## (в)")[0]
        sec = b.split("Чистый долг — сырые факты")[1]
        self.assertIn("480 − cash = 480 − 250 = 230", sec)
        flag_line = [l for l in sec.split("\n") if l.startswith("**DEBT_TAG_INCONSISTENT**")]
        self.assertEqual(len(flag_line), 1)                   # отдельная строка флага, а не только строка basis
        self.assertIn("700", flag_line[0])                    # расхождение 700 vs 480 названо в досье с обоими числами
        self.assertIn("480", flag_line[0])
        self.assertEqual(len(ACCN_RE.findall(sec.split("Формула")[0])), 2)    # accession у долга и у cash
        self.assertIn("LongTermDebtNoncurrent", sec)

    def test_dos_67_raw_facts_follow_the_card_chain_switch_and_the_forced_v2_exception(self):
        # сырые слагаемые берутся из ТОЙ ЖЕ точки ряда, что число карточки, при любой цепочке (иначе RAW_MISMATCH)
        f = self.facts({"LongTermDebt": {2019: 700}, "LongTermDebtNoncurrent": {2019: 480},
                        "CashAndCashEquivalentsAtCarryingValue": {2019: 250}})
        def raw(as_of, force):
            series, ref = fc.net_debt_series(f, EF, as_of, force)
            last = series[-1]
            nd = fc.ok(last["val"], "USD", "тест", last["accn"], tags=last["tags"])
            return dos.debt_raw(f, EF, nd, as_of, force)
        self.assertEqual(raw("2026-11-07", False)["total"], 700 - 250)         # до 14.11: прежняя цепочка (полный тег)
        self.assertEqual(raw("2026-11-14", False)["total"], 480 - 250)         # с 14.11: части
        self.assertEqual(raw("2020-02-15", True)["total"], 480 - 250)          # исключение: v2 на старом as_of
        self.assertEqual(raw("2020-02-15", False)["total"], 700 - 250)

    def test_dos_68_forced_v2_is_named_in_the_header_only_when_it_changes_the_chain_and_build_passes_it(self):
        D = make(nd=None)
        self.assertNotIn("принудительно", dos.render_machine(D))
        D["debt_chain_forced_v2"], D["as_of"] = True, "2020-02-15"
        self.assertIn("v2 применена принудительно", dos.render_machine(D))
        D["as_of"] = "2026-11-14"                                              # с 14.11 v2 и так обычная: пометка не нужна
        self.assertNotIn("принудительно", dos.render_machine(D))
        seen = []
        real = fc.build_name
        with unittest.mock.patch.object(fc, "build_name", lambda *a, **k: (seen.append(a), real(*a, **k))[1]):
            dos.build("TEST", AS_OF, FakeSource(mk_out()), fake_fetch(100.0), force_v2=True)
            dos.build("TEST", AS_OF, FakeSource(mk_out()), fake_fetch(100.0))
        self.assertEqual([x[-1] for x in seen], [True, False])
        raw_calls = []
        real_raw = dos.debt_raw
        with unittest.mock.patch.object(dos, "debt_raw", lambda *x, **k: (raw_calls.append(x), real_raw(*x, **k))[1]):
            dos.build("TEST", AS_OF, FakeSource(mk_out(), self.facts({"LongTermDebtNoncurrent": {2019: 1}})), fake_fetch(100.0), force_v2=True)
        self.assertEqual([(x[3], x[4]) for x in raw_calls], [(AS_OF, True)])        # сырые факты получают тот же as_of и флаг, что карточка

    def test_dos_66_report_names_refusal_when_raw_facts_unavailable(self):
        D = make(nd=None)
        D["nd_raw"] = fc.refusal("NOT_REPORTED", "нет тегов долга")
        sec = dos.render_machine(D).split("Чистый долг — сырые факты")[1].split("## (в)")[0]
        self.assertIn("ОТКАЗ NOT_REPORTED", sec)


class TestPsPath(unittest.TestCase):
    """К6 ч. C: путь по капитализации (P/S) при NOT_REPORTED долге и известных деньгах
    (DECISION_2026-11-02_DOSSIER_COMPLETENESS §1 п. 5, §3). Пины на СВОЙСТВО включения, не на форму текста."""
    CASH = {"CashAndCashEquivalentsAtCarryingValue": {2019: 250}}

    @staticmethod
    def build(nd_code, cash_facts=CASH):
        """D, где чистый долг -- отказ класса nd_code, а в фактах SEC (не) лежат деньги на конец ФГ 2019."""
        facts = TestDebtRaw.facts(cash_facts) if cash_facts else None
        D = dos.build("TEST", AS_OF, FakeSource(mk_out(), facts), fake_fetch(100.0))
        D["nd"] = fc.refusal(nd_code, "тест: %s" % nd_code) if nd_code else fc.ok(50, "USD", "тест", ["тест"])
        D["derived"] = dos.derive(D)
        return D

    def cells(self, D):
        return [v for v in D["derived"]["grid_ps"].values() if not dos.is_ref(v)]

    def test_dos_70_ps_arithmetic_hand_and_roundtrip(self):
        # 100 выручка, 10 акций, цена 10 (капитализация 100): g=0, P/S=1 -> 0%; P/S=4 -> 4^(1/10)-1
        self.assertAlmostEqual(dos.ps_return(100, 10, 10, 0.0, 1), 0.0, places=12)
        self.assertAlmostEqual(dos.ps_return(100, 10, 10, 0.0, 4), 4 ** 0.1 - 1, places=12)
        self.assertAlmostEqual(dos.ps_return(100, 10, 10, 0.10, 1), 1.1 - 1, places=12)
        g = dos.required_growth_ps(100, 10, 10, 2.0)
        self.assertAlmostEqual(dos.ps_return(100, 10, 10, g, 2.0), dos.HURDLE, places=9)
        self.assertTrue(dos.is_ref(dos.ps_return(0, 10, 10, 0.1, 2)))
        self.assertTrue(dos.is_ref(dos.ps_return(100, 10, None, 0.1, 2)))

    def test_dos_71_ps_path_on_only_for_not_reported_debt_with_known_cash(self):
        D = self.build("NOT_REPORTED")
        d = D["derived"]
        self.assertTrue(d["ps_mode"])
        self.assertEqual(d["cash_val"], 250)
        self.assertEqual(len(self.cells(D)), len(dos.GRID_GROWTH) * len(dos.GRID_PS))
        self.assertAlmostEqual(d["g_req_ps"], dos.HURDLE, places=9)            # при неизменном P/S -- тождество
        self.assertGreater(d["g_req_ps_sens"][0.5], d["g_req_ps_sens"][1.0])   # ниже выходной P/S -> нужен больший рост
        # EV/S-путь остаётся отказом, и класс отказа -- класс отказа долга, а не «наша вина»
        ev = [v for v in d["grid_ev_s"].values()]
        self.assertTrue(ev and all(dos.is_ref(v) and v["refused"] == "NOT_REPORTED" for v in ev))
        self.assertTrue(dos.is_ref(d["g_req"]) and d["g_req"]["refused"] == "NOT_REPORTED")

    def test_dos_72_other_debt_refusal_does_not_enable_ps_path(self):
        for code in ("DEBT_TAG_ABSENT", "MISSING_INPUT"):       # пробел по нашей вине -- не «долг не представлен»
            D = self.build(code)
            self.assertFalse(D["derived"]["ps_mode"], code)
            self.assertEqual(self.cells(D), [], code)
            self.assertTrue(all(dos.is_ref(v) and v["refused"] == code for v in D["derived"]["grid_ev_s"].values()), code)
        D = self.build(None)                                    # долг известен: основной путь EV/S
        self.assertFalse(D["derived"]["ps_mode"])
        self.assertTrue(self.cells(D) == [] and any(not dos.is_ref(v) for v in D["derived"]["grid_ev_s"].values()))

    def test_dos_73_unknown_cash_leaves_section_empty_and_says_not_complete(self):
        for facts in (None, {"CashAndCashEquivalentsAtCarryingValue": {2018: 250}}):    # нет фактов / деньги на другой дате
            D = self.build("NOT_REPORTED", cash_facts=facts)
            self.assertFalse(D["derived"]["ps_mode"])
            self.assertEqual(self.cells(D), [])
            self.assertTrue(dos.is_ref(D["cash"]) and D["cash"]["refused"] == "MISSING_INPUT")
            self.assertIn("досье не полное", D["derived"]["ps_reason"])
            self.assertIn("досье не полное", dos.render_machine(D))
            self.assertNotIn("Таблица 1а", dos.render_machine(D))

    def test_dos_74_cash_must_be_at_the_fiscal_year_end_not_the_latest_available(self):
        r = dos.cash_raw(TestDebtRaw.facts({"CashAndCashEquivalentsAtCarryingValue": {2017: 1, 2018: 2}}), EF, "2019-12-31")
        self.assertTrue(dos.is_ref(r) and r["refused"] == "MISSING_INPUT")
        ok = dos.cash_raw(TestDebtRaw.facts({"CashAndCashEquivalentsAtCarryingValue": {2018: 2, 2019: 3}}), EF, "2019-12-31")
        self.assertEqual((ok["val"], ok["end"]), (3, "2019-12-31"))
        self.assertRegex(ok["accn"], ACCN_RE)

    def test_dos_75_report_carries_the_decision_note_and_block_d_uses_ps(self):
        D = self.build("NOT_REPORTED")
        machine, brief = dos.render_machine(D), dos.render_brief(D)
        note = "долг не представлен в отчётности; оценка по капитализации, не по стоимости компании"
        self.assertIn(note, machine)
        self.assertIn(note, brief)
        self.assertRegex(machine, ACCN_RE.pattern)
        T, X = dos.truth_refute(D)
        self.assertTrue(any("по капитализации" in t and dos.pp(D["derived"]["g_req_ps"]) in t for t in T))
        self.assertTrue(any("по капитализации" in x for x in X))
        # без пути P/S блок (д) такого пункта не содержит
        T0, _ = dos.truth_refute(self.build("DEBT_TAG_ABSENT"))
        self.assertFalse(any("по капитализации" in t for t in T0))

    def test_dos_76_ps_result_does_not_depend_on_the_cash_amount(self):
        # деньги -- только условие включения; в P/S-сетку они не входят (оценка капитала, не стоимости компании)
        a = self.build("NOT_REPORTED", {"CashAndCashEquivalentsAtCarryingValue": {2019: 250}})["derived"]["grid_ps"]
        b = self.build("NOT_REPORTED", {"CashAndCashEquivalentsAtCarryingValue": {2019: 9999}})["derived"]["grid_ps"]
        self.assertEqual(a, b)

    def test_dos_77_brief_first_line_counts_refusals_by_class(self):
        D = self.build("NOT_REPORTED")
        for name, code in (("rev_cagr_5y", "SHORT_HISTORY"), ("gm_med5", "SHORT_HISTORY"), ("om_med5", "SHORT_HISTORY"),
                           ("net_debt_chg_3y", "NOT_REPORTED")):
            D["card"]["fields"][name] = fc.refusal(code, "тест")
        D["card"]["fields"]["net_debt_latest"] = fc.refusal("NOT_REPORTED", "тест")
        import collections
        cnt = collections.Counter(D["card"]["fields"][n]["refused"] for n in fc.FIELD_ORDER if not fc.is_ok(D["card"]["fields"][n]))
        self.assertGreaterEqual(cnt["SHORT_HISTORY"], 3)
        self.assertGreaterEqual(cnt["NOT_REPORTED"], 2)
        first = dos.render_brief(D).split("## 5. Чего машина не знает")[1].strip().splitlines()[0]
        head, tail = first.split(": ", 1)
        self.assertEqual(head, "%d отказов из %d полей" % (sum(cnt.values()), len(fc.FIELD_ORDER)))
        got = {k: int(v) for k, v in (x.rsplit(" ", 1) for x in tail.split(", "))}
        self.assertEqual(got, dict(cnt))                       # каждый класс со своим числом, ничего не слито и не потеряно

    def test_dos_78_cash_is_part_of_the_input_hash(self):
        a = self.build("NOT_REPORTED", {"CashAndCashEquivalentsAtCarryingValue": {2019: 250}})["input_hash"]
        b = self.build("NOT_REPORTED", {"CashAndCashEquivalentsAtCarryingValue": {2019: 251}})["input_hash"]
        self.assertNotEqual(a, b)


class TestCli(unittest.TestCase):
    def test_dos_50_hash_is_stable_and_depends_on_inputs(self):
        h1, h2 = make()["input_hash"], make()["input_hash"]
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, make(price=101.0)["input_hash"])
        self.assertNotEqual(h1, make(out=mk_out(ni=101))["input_hash"])

    def test_dos_51_existing_dossier_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "TEST_%s_machine.md" % AS_OF)
            open(path, "w").write("старое")
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                rc = dos.main(["TEST", "--as-of", AS_OF, "--out-dir", td], source=FakeSource(mk_out()), fetch=fake_fetch())
            self.assertEqual(rc, 2)
            self.assertEqual(open(path).read(), "старое")

    def test_dos_52_main_writes_both_files(self):
        with tempfile.TemporaryDirectory() as td:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = dos.main(["TEST", "--as-of", AS_OF, "--out-dir", td], source=FakeSource(mk_out()), fetch=fake_fetch())
            self.assertEqual(rc, 0)
            self.assertEqual(sorted(os.listdir(td)), ["TEST_%s_brief.md" % AS_OF, "TEST_%s_machine.md" % AS_OF])

    def test_dos_53_missing_credentials_write_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            env = {k: os.environ.pop(k) for k in ("TIINGO_TOKEN", "SEC_USER_AGENT") if k in os.environ}
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    rc = dos.main(["TEST", "--as-of", AS_OF, "--out-dir", td])
            finally:
                os.environ.update(env)
            self.assertEqual(rc, 2)
            self.assertEqual(os.listdir(td), [])

    def test_dos_54_bad_date_is_refused(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(dos.main(["TEST", "--as-of", "15.02.2020"]), 2)


if __name__ == "__main__":
    unittest.main()
