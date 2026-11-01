"""К4 часть A: сторож CASH_DECAY (tools/guards/cash_decay.py) и прогон tools/exam_nflx.py.

Источник правил -- mailbox/PREREG_2026-11-01_K4_NFLX_CASH_DECAY.md §3-§6. Всё на синтетике, без сети.
Тесты проверяют СВОЙСТВО правила (граница порога, отсутствие факта, срез по дате), а не форму вывода; к каждому
условию правила есть мутация в tools/mutation_probe.py (id cd-NN), которая краснит соответствующий пин.

  TestRules          -- R1, R2, AMBER одного года, падение против медианы, границы порогов, NOT_APPLICABLE.
  TestMissingIsNotOK -- отсутствующий факт -> НЕ_ОПРЕДЕЛЁН (не OK, не 0).
  TestAsOfSlice      -- filed > as_of не используется; без filed не используется; поздняя поправка до as_of побеждает.
  TestEvidence       -- улика RED содержит accession каждого числа; диагностика за 5 ФГ, неопределимое -- None.
  TestExam           -- экзамен/контроли на подставном источнике: метаданные подачи, воспроизводимость, доля ложных RED.
"""
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True   # мутационный зонд правит tools/ -- устаревший .pyc не должен пережить правку
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, os.path.join(REPO, "tools", "guards"))

import cash_decay as cd   # noqa: E402
import exam_nflx as ex    # noqa: E402

AS_OF = "2020-02-15"
CODE = {"ni": 1, "ocf": 2, "capex": 3, "revenue": 4}


def accn(y, field):
    return "0000000000-%02d-%06d" % ((y + 1) % 100, CODE[field])


def rec(y, field, val, **kw):
    r = {"end": "%d-12-31" % y, "val": val, "accn": accn(y, field), "filed": "%d-02-10" % (y + 1), "unit": "USD"}
    r.update(kw)
    return r


def mk(years):
    """years: {год: (ni, ocf, capex[, revenue])}; revenue по умолчанию 10*max(|ni|,1) -- NI = 10% выручки (выше порога 1%)."""
    out = {"ni": [], "ocf": [], "capex": [], "revenue": []}
    for y in sorted(years):
        row = years[y]
        ni, ocf, cx = row[0], row[1], row[2]
        rev = row[3] if len(row) > 3 else 10 * max(abs(ni or 100), 1)
        for f, v in (("ni", ni), ("ocf", ocf), ("capex", cx), ("revenue", rev)):
            if v is not None:
                out[f].append(rec(y, f, v))
    return out


def healthy(upto=2018, frm=2015):
    """Здоровые предыдущие ФГ: NI 100, FCF/NI = 1.0."""
    return {y: (100, 150, 50) for y in range(frm, upto + 1)}


def case(fy0, fy1=None, prior=None, **kw):
    """FG0=2019 (ni, ocf, capex), FG-1=2018 (по умолчанию здоровый), остальные -- здоровые, если не заданы."""
    yrs = healthy()
    if fy1 is not None:
        yrs[2018] = fy1
    yrs.update(prior or {})
    yrs[2019] = fy0
    return cd.evaluate(mk(yrs), AS_OF, **kw) if kw else cd.evaluate(mk(yrs), AS_OF)


class TestRules(unittest.TestCase):
    def test_cd_01_r1_profit_with_negative_ocf_is_red(self):
        r = case((100, -50, 10))
        self.assertEqual((r["verdict"], r["rule"]), (cd.RED, "R1"))

    def test_cd_02_r1_needs_strictly_negative_ocf(self):
        # OCF = 0: не R1. FCF/NI = 0 < 0.5, но ФГ-1 здоров -> AMBER одного года, не RED.
        r = case((100, 0, 0))
        self.assertEqual((r["verdict"], r["rule"]), (cd.AMBER, "AMBER_ONE_YEAR"))

    def test_cd_03_r2_two_weak_years_is_red(self):
        r = case((100, 60, 30), fy1=(100, 70, 30))           # FCF/NI 0.30 и 0.40
        self.assertEqual((r["verdict"], r["rule"]), (cd.RED, "R2"))

    def test_cd_04_one_weak_year_is_amber_not_red(self):
        # разовая крупная выплата: один год слабого потока при здоровом предыдущем -- AMBER (PREREG §4)
        r = case((100, 60, 30))
        self.assertEqual((r["verdict"], r["rule"]), (cd.AMBER, "AMBER_ONE_YEAR"))

    def test_cd_05_prior_year_at_threshold_is_not_weak(self):
        # FCF/NI(ФГ-1) = ровно 0.5 -> не «< 0.5» -> R2 не выполнен
        r = case((100, 60, 30), fy1=(100, 80, 30))
        self.assertEqual((r["verdict"], r["rule"]), (cd.AMBER, "AMBER_ONE_YEAR"))

    def test_cd_06_current_year_at_threshold_is_not_weak(self):
        # FCF/NI(ФГ0) = ровно 0.5, медиана 1.0, падение ровно 0.5 -> не «больше 0.5» -> OK
        r = case((100, 80, 30))
        self.assertEqual((r["verdict"], r["rule"]), (cd.OK, "OK"))

    def test_cd_07_threshold_is_one_half_not_other(self):
        # 0.45 и 0.45 -> RED; 0.55 и 0.55 -> не RED. Ловит сдвиг самого порога в обе стороны.
        self.assertEqual(case((100, 75, 30), fy1=(100, 75, 30))["verdict"], cd.RED)    # 0.45 / 0.45
        self.assertNotEqual(case((100, 85, 30), fy1=(100, 85, 30))["verdict"], cd.RED)  # 0.55 / 0.55

    def test_cd_08_prior_nonpositive_ni_is_not_r2_and_not_a_gap(self):
        # R2 требует NI > 0 в обоих ФГ: NI(ФГ-1) <= 0 -- условие не выполнено (AMBER), а не пробел данных
        for ni1 in (-20, 0):
            r = case((100, 60, 30), fy1=(ni1, 70, 30))
            self.assertEqual((r["verdict"], r["rule"]), (cd.AMBER, "AMBER_ONE_YEAR"), ni1)

    def test_cd_09_drop_against_median_is_amber(self):
        r = case((100, 105, 50), prior={2018: (100, 170, 50), 2017: (100, 150, 50), 2016: (100, 160, 50)})
        # FCF/NI(ФГ0) = 0.55; предыдущие 1.2, 1.0, 1.1 -> медиана 1.1; падение 0.55 > 0.5
        self.assertEqual((r["verdict"], r["rule"]), (cd.AMBER, "AMBER_DROP_VS_MEDIAN"))

    def test_cd_10_drop_of_exactly_half_is_ok(self):
        r = case((100, 105, 50), prior={2018: (100, 160, 50), 2017: (100, 150, 50), 2016: (100, 140, 50)})
        # 0.55 против медианы 1.0 -> падение 0.45 -> OK; и ровно 0.5 -- в test_cd_06
        self.assertEqual(r["verdict"], cd.OK)

    def test_cd_11_median_uses_three_previous_years_not_two(self):
        # без третьего предыдущего ФГ медиану не вычислить -> НЕ_ОПРЕДЕЛЁН, а не оценка по двум
        yrs = {2019: (100, 150, 50), 2018: (100, 150, 50), 2017: (100, 150, 50)}
        r = cd.evaluate(mk(yrs), AS_OF)
        self.assertEqual(r["verdict"], cd.UNDEFINED)
        self.assertIn("ФГ-3", r["reason"])

    def test_cd_12_not_applicable_nonpositive_ni(self):
        for ni in (-5, 0):
            r = case((ni, 50, 10, 1000))
            self.assertEqual((r["verdict"], r["rule"]), (cd.NOT_APPLICABLE, "NA_NI_NONPOSITIVE"), ni)

    def test_cd_13_not_applicable_ni_below_one_percent_of_revenue(self):
        r = case((9, -50, 10, 1000))                      # 0.9% выручки: даже OCF < 0 не делает RED
        self.assertEqual((r["verdict"], r["rule"]), (cd.NOT_APPLICABLE, "NA_NI_BELOW_1PCT_REVENUE"))

    def test_cd_14_ni_exactly_one_percent_of_revenue_is_applicable(self):
        r = case((10, -50, 10, 1000))                     # ровно 1% -- не «< 1%»
        self.assertEqual((r["verdict"], r["rule"]), (cd.RED, "R1"))

    def test_cd_15_na_threshold_is_one_percent(self):
        self.assertEqual(case((15, -50, 10, 1000))["verdict"], cd.RED)       # 1.5%: применимо
        self.assertEqual(case((5, -50, 10, 1000))["rule"], "NA_NI_BELOW_1PCT_REVENUE")


class TestMissingIsNotOK(unittest.TestCase):
    def assertUndefined(self, r, *words):
        self.assertEqual(r["verdict"], cd.UNDEFINED, r)
        self.assertNotIn(r["verdict"], (cd.OK, cd.RED, cd.AMBER, cd.NOT_APPLICABLE))
        self.assertTrue(r["reason"])
        for w in words:
            self.assertIn(w, r["reason"])

    def test_cd_20_no_facts_at_all(self):
        self.assertUndefined(cd.evaluate({}, AS_OF))
        self.assertUndefined(cd.evaluate({"ni": [], "ocf": [], "capex": [], "revenue": []}, AS_OF))

    def test_cd_21_missing_ni_in_latest_year(self):
        yrs = healthy(2019)
        yrs[2019] = (None, 150, 50)                       # OCF за 2019 есть, NI нет: прошлый год NI подменой не берётся
        self.assertUndefined(cd.evaluate(mk(yrs), AS_OF), "NI")

    def test_cd_22_missing_revenue_when_ni_positive(self):
        yrs = healthy(2018)
        yrs[2019] = (100, 150, 50, None)
        self.assertUndefined(cd.evaluate(mk(yrs), AS_OF), "выручк")

    def test_cd_23_missing_ocf(self):
        yrs = healthy(2018)
        yrs[2019] = (100, None, 50)
        self.assertUndefined(cd.evaluate(mk(yrs), AS_OF), "OCF")

    def test_cd_24_missing_capex_is_not_zero_capex(self):
        # без capex FCF = OCF выглядел бы как «капекса нет» -> OK. Должен быть отказ.
        yrs = healthy(2018)
        yrs[2019] = (100, 150, None)
        self.assertUndefined(cd.evaluate(mk(yrs), AS_OF), "capex")

    def test_cd_25_r1_still_red_without_capex_but_free_cash_flow_is_named_undefined(self):
        yrs = healthy(2018)
        yrs[2019] = (100, -50, None)
        r = cd.evaluate(mk(yrs), AS_OF)
        self.assertEqual((r["verdict"], r["rule"]), (cd.RED, "R1"))
        self.assertIn("НЕ ОПРЕДЕЛЁН", r["evidence"])

    def test_cd_26_weak_latest_year_and_unreadable_previous_year(self):
        # RED и AMBER неразличимы без ФГ-1 -> отказ, не угадывание
        for fy1 in ((100, 70, None), (None, 70, 30)):
            yrs = healthy(2017)
            yrs[2018] = fy1
            yrs[2019] = (100, 60, 30)
            self.assertUndefined(cd.evaluate(mk(yrs), AS_OF), "ФГ-1")

    def test_cd_27_healthy_latest_year_with_gap_in_median_window(self):
        # OK и AMBER(падение) неразличимы без медианы -> отказ, не OK
        yrs = healthy(2018)
        del yrs[2016]
        yrs[2019] = (100, 150, 50)
        r = cd.evaluate(mk(yrs), AS_OF)
        self.assertUndefined(r, "ФГ-3")
        self.assertNotEqual(r["verdict"], cd.OK)

    def test_cd_28_nonpositive_ni_in_median_window_is_a_refusal_not_a_zero(self):
        r = case((100, 150, 50), prior={2016: (-10, 20, 5)})
        self.assertUndefined(r, "NI <= 0")

    def test_cd_29_negative_capex_is_refused(self):
        yrs = healthy(2018)
        yrs[2019] = (100, 150, -50)                       # выплата со знаком «минус» -- знак не по определению тега
        self.assertUndefined(cd.evaluate(mk(yrs), AS_OF), "capex")

    def test_cd_30_non_usd_unit_is_not_used(self):
        f = mk({**healthy(2018), **{2019: (100, 150, 50)}})
        for r in f["ni"]:
            if r["end"] == "2019-12-31":
                r["unit"] = "EUR"
        res = cd.evaluate(f, AS_OF)
        self.assertEqual(res["verdict"], cd.UNDEFINED)             # EUR-запись не использована: у ФГ2019 нет NI -> отказ
        self.assertTrue(any("не USD" in n for n in res["notes"]))


class TestAsOfSlice(unittest.TestCase):
    def test_cd_40_fact_filed_after_as_of_is_not_used(self):
        # ФГ2019 подан ПОСЛЕ as_of -> FG0 = ФГ2018. Если бы он использовался, вердикт был бы RED (R1).
        f = mk({**healthy(2018), **{2019: (100, -50, 10)}})
        for fld in f.values():
            for r in fld:
                if r["end"] == "2019-12-31":
                    r["filed"] = "2020-02-16"
        res = cd.evaluate(f, AS_OF)
        self.assertEqual(res["fiscal_year_end"], "2018-12-31")
        self.assertEqual(res["verdict"], cd.OK)

    def test_cd_41_filed_equal_to_as_of_is_used(self):
        f = mk({**healthy(2018), **{2019: (100, -50, 10)}})
        for fld in f.values():
            for r in fld:
                if r["end"] == "2019-12-31":
                    r["filed"] = AS_OF
        self.assertEqual(cd.evaluate(f, AS_OF)["rule"], "R1")

    def test_cd_42_record_without_filed_is_not_used(self):
        # срез недоказуем -> запись не используется (и это видно в замечаниях); NI с filed="" -> ФГ2019 без NI
        for bad in ("", None):
            f = mk({**healthy(2018), **{2019: (100, -50, 10)}})
            for r in f["ni"]:
                if r["end"] == "2019-12-31":
                    r["filed"] = bad
            res = cd.evaluate(f, AS_OF)
            self.assertEqual(res["verdict"], cd.UNDEFINED, bad)       # OCF за 2019 есть, NI нет -> отказ, не подмена
            self.assertTrue(any("нет даты подачи" in n for n in res["notes"]), bad)

    def test_cd_43_record_without_accession_is_not_used(self):
        f = mk({**healthy(2018), **{2019: (100, -50, 10)}})
        for r in f["ocf"]:
            if r["end"] == "2019-12-31":
                r["accn"] = None
        self.assertEqual(cd.evaluate(f, AS_OF)["verdict"], cd.UNDEFINED)    # число без provenance не считается

    def test_cd_44_later_filed_restatement_before_as_of_wins(self):
        f = mk({**healthy(2018), **{2019: (100, 150, 50)}})
        f["ocf"].append(rec(2019, "ocf", -50, filed="2020-02-14", accn="0000000000-20-999999"))   # поправка до as_of
        f["ocf"].append(rec(2019, "ocf", 999, filed="2020-03-01", accn="0000000000-20-888888"))    # после as_of
        res = cd.evaluate(f, AS_OF)
        self.assertEqual(res["rule"], "R1")
        self.assertIn("0000000000-20-999999", res["evidence"])
        self.assertNotIn("888888", res["evidence"])


class TestEvidence(unittest.TestCase):
    def test_cd_50_red_evidence_carries_accession_of_every_number(self):
        r = case((100, -50, 10))
        for f in ("ni", "ocf", "capex"):
            self.assertIn(accn(2019, f), r["evidence"], f)
        self.assertIn("ФГ2019", r["evidence"])

    def test_cd_51_r2_evidence_covers_both_years(self):
        r = case((100, 60, 30), fy1=(100, 70, 30))
        self.assertIn("ФГ2019", r["evidence"])
        self.assertIn("ФГ2018", r["evidence"])
        self.assertIn(accn(2018, "ocf"), r["evidence"])

    def test_cd_52_free_cash_flow_is_ocf_minus_capex(self):
        r = case((100, 60, 30))                           # FCF = 30; 0.30
        self.assertIn("$30 [", r["evidence"])
        self.assertIn("FCF/NI = 0.30", r["evidence"])

    def test_cd_53_diagnostics_cover_five_fiscal_years_and_never_invent_zero(self):
        yrs = healthy(2018)
        yrs[2016] = (-10, 20, 5)                          # NI <= 0 -> отношения этого ФГ не определены
        yrs[2019] = (100, 150, 50)
        d = cd.evaluate(mk(yrs), AS_OF)["diagnostics"]
        self.assertEqual(len(d), 5)
        self.assertEqual([x["end"] for x in d][:2], ["2019-12-31", "2018-12-31"])
        by = {x["end"]: x for x in d}
        self.assertIsNone(by["2016-12-31"]["fcf_to_ni"])
        self.assertIsNone(by["2016-12-31"]["ocf_to_ni"])          # NI <= 0 -> не 0.0, а None с причиной
        self.assertIn("NI <= 0", by["2016-12-31"]["why"]["ocf_to_ni"])
        gap = cd.evaluate(mk({y: v for y, v in yrs.items() if y != 2017}), AS_OF)["diagnostics"][2]
        self.assertEqual((gap["end"], gap["ocf_to_ni"], gap["capex_to_ocf"], gap["fcf_to_ni"]), (None, None, None, None))
        self.assertIn("NI <= 0", by["2016-12-31"]["why"]["fcf_to_ni"])
        self.assertAlmostEqual(by["2019-12-31"]["fcf_to_ni"], 1.0)
        self.assertAlmostEqual(by["2019-12-31"]["capex_to_ocf"], 50 / 150)
        self.assertAlmostEqual(by["2019-12-31"]["ocf_to_ni"], 1.5)

    def test_cd_54_diagnostics_do_not_change_the_verdict(self):
        a = case((100, 150, 50))
        self.assertEqual(a["verdict"], cd.OK)
        self.assertEqual(a["reason"].count("диагностик"), 0)

    def test_cd_55_gap_year_is_an_empty_slot_not_a_skipped_one(self):
        yrs = healthy(2018)
        del yrs[2017]
        yrs[2019] = (100, 150, 50)
        d = cd.evaluate(mk(yrs), AS_OF)["diagnostics"]
        self.assertEqual([x["end"] for x in d], ["2019-12-31", "2018-12-31", None, "2016-12-31", "2015-12-31"])

    def test_cd_56_verdict_is_always_one_of_the_named_values(self):
        for r in (case((100, -50, 10)), case((100, 60, 30)), case((100, 150, 50)), case((-1, 1, 1, 100)),
                  cd.evaluate({}, AS_OF)):
            self.assertIn(r["verdict"], cd.VERDICTS)


# ----------------------------------------------------------------------------- экзамен: подставной источник

class FakeAd:
    ANNUAL_FORMS = ("10-K",)

    @staticmethod
    def select_filing(listing, as_of, forms):
        ok = [r for r in listing if r.get("form") in forms and str(r["filing_date"]) <= as_of]
        return max(ok, key=lambda r: (str(r["filing_date"]), r["accession"])) if ok else None


class FakeEf:
    @staticmethod
    def _resolve_cik(ticker):
        return {"NFLX": "0001065280", "BAD": None}.get(ticker, "0000000001")


class FakeSource:
    """Тот же контракт, что floor1_card.LiveSource: .read(ticker) -> (out, facts, cik) на текущем self.as_of."""
    ad, ef = FakeAd, FakeEf

    def __init__(self, table, listing=None):
        self.table, self._listing, self.as_of, self.asked = table, listing, None, []

    def read(self, ticker):
        self.asked.append((ticker, self.as_of))
        t = self.table.get((ticker, self.as_of))
        if t is None:
            return {"_errors": {"data": "нет снимка"}}, None, "0000000001"
        return {"net_income": t.get("ni"), "ocf": t.get("ocf"), "capex": t.get("capex"), "revenue": t.get("revenue")}, None, "0000000001"

    def listing(self, cik):
        if isinstance(self._listing, Exception):
            raise self._listing
        return self._listing


NFLX_LISTING = [{"accession": "0001065280-20-000012", "form": "10-K", "filing_date": "2020-01-29", "period_of_report": "2019-12-31"},
                {"accession": "0001065280-19-000043", "form": "10-K", "filing_date": "2019-01-29", "period_of_report": "2018-12-31"}]
RED_FACTS = mk({**healthy(2018), **{2019: (100, -50, 10)}})
OK_FACTS = mk({**healthy(2018), **{2019: (100, 150, 50)}})


class TestExam(unittest.TestCase):
    def test_cd_60_metadata_ok_when_10k_for_fy_filed_before_as_of(self):
        m = ex.check_filing_metadata(FakeSource({}, NFLX_LISTING), "c", AS_OF, "2019")
        self.assertTrue(m["ok"])
        self.assertEqual(m["accession"], "0001065280-20-000012")

    def test_cd_61_metadata_fails_when_10k_filed_after_as_of(self):
        late = [dict(NFLX_LISTING[0], filing_date="2020-02-16"), NFLX_LISTING[1]]
        m = ex.check_filing_metadata(FakeSource({}, late), "c", AS_OF, "2019")
        self.assertFalse(m["ok"])
        self.assertIn("2018-12-31", m["reason"])             # последний подходящий 10-K -- за ФГ2018, не ФГ2019

    def test_cd_62_metadata_fails_without_listing(self):
        self.assertFalse(ex.check_filing_metadata(FakeSource({}, []), "c", AS_OF, "2019")["ok"])
        self.assertFalse(ex.check_filing_metadata(FakeSource({}, RuntimeError("down")), "c", AS_OF, "2019")["ok"])

    def test_cd_63_exam_red_is_reproducible_and_passes_gate(self):
        src = FakeSource({("NFLX", AS_OF): RED_FACTS}, NFLX_LISTING)
        res = ex.run_exam(src)
        self.assertEqual((res["verdict"], res["rule"]), (cd.RED, "R1"))
        self.assertTrue(res["reproducible"])
        self.assertTrue(res["within_limit"])
        self.assertTrue(ex.gate_line(res).startswith("ГЕЙТ: ПРОЙДЕН"))
        self.assertEqual(len(res["input_hash"]), 64)

    def test_cd_64_exam_is_not_run_when_metadata_fails_and_that_is_a_failure(self):
        src = FakeSource({("NFLX", AS_OF): RED_FACTS}, [NFLX_LISTING[1]])
        res = ex.run_exam(src)
        self.assertEqual(res["verdict"], cd.UNDEFINED)
        self.assertIn("экзамен не проводился", res["reason"])
        self.assertEqual(src.asked, [])                      # фактов не читали: до метаданных данные не трогаются
        self.assertTrue(ex.gate_line(res).startswith("ГЕЙТ: ПРОВАЛ"))

    def test_cd_65_ok_amber_na_undefined_are_a_gate_failure(self):
        for facts in (OK_FACTS, mk({**healthy(2018), **{2019: (100, 60, 30)}}), mk({**healthy(2018), **{2019: (-1, 1, 1)}}), {"ni": []}):
            res = ex.run_exam(FakeSource({("NFLX", AS_OF): facts}, NFLX_LISTING))
            self.assertNotEqual(res["verdict"], cd.RED)
            self.assertTrue(ex.gate_line(res).startswith("ГЕЙТ: ПРОВАЛ"), res["verdict"])

    def test_cd_66_non_reproducible_red_is_a_gate_failure(self):
        res = dict(ex.run_exam(FakeSource({("NFLX", AS_OF): RED_FACTS}, NFLX_LISTING)), reproducible=False)
        self.assertTrue(ex.gate_line(res).startswith("ГЕЙТ: ПРОВАЛ"))

    def test_cd_67_each_snapshot_is_read_at_its_own_as_of(self):
        table = {(t, d): OK_FACTS for t, d in ex.CONTROLS}
        src = FakeSource(table)
        ex.run_controls(src)
        self.assertEqual(src.asked, list(ex.CONTROLS))

    def test_cd_68_controls_are_exactly_the_ten_snapshots_of_the_prereg(self):
        self.assertEqual(len(ex.CONTROLS), 10)
        self.assertIn(("META", "2021-02-15"), ex.CONTROLS)
        for t in ("MA", "SPGI", "MSFT"):
            for d in ("2020-02-15", "2022-02-15", "2024-02-15"):
                self.assertIn((t, d), ex.CONTROLS)
        self.assertNotIn("INTC", [t for t, _ in ex.CONTROLS])   # Intel -- сожжённый случай

    def test_cd_69_false_red_share_counts_red_only_over_ten(self):
        table = {(t, d): OK_FACTS for t, d in ex.CONTROLS}
        table[("MA", "2022-02-15")] = RED_FACTS
        table[("SPGI", "2024-02-15")] = {"ni": []}           # НЕ_ОПРЕДЕЛЁН: не RED и не «проход»
        rows = ex.run_controls(FakeSource(table))
        self.assertEqual(ex.false_red_share(rows), (1, 10))
        text = ex.render_controls(rows, "2026-11-02", "cmd")
        self.assertIn("ДОЛЯ ЛОЖНЫХ RED: 1/10 = 10%", text)
        self.assertIn("НЕ_ОПРЕДЕЛЁН: 1/10", text)

    def test_cd_70_missing_control_snapshot_is_undefined_not_ok(self):
        rows = ex.run_controls(FakeSource({}))
        self.assertTrue(all(r["verdict"] == cd.UNDEFINED for r in rows))
        self.assertEqual(ex.false_red_share(rows), (0, 10))

    def test_cd_71_exam_report_has_verdict_line_numbers_accession_command_and_hash(self):
        res = ex.run_exam(FakeSource({("NFLX", AS_OF): RED_FACTS}, NFLX_LISTING))
        text = ex.render_exam(res, "2026-11-02", "python3 tools/exam_nflx.py --part exam")
        self.assertIn("\nВЕРДИКТ: RED\n", text)
        self.assertIn(accn(2019, "ocf"), text)
        self.assertIn("python3 tools/exam_nflx.py --part exam", text)
        self.assertIn(res["input_hash"], text)
        self.assertIn("0001065280-20-000012", text)

    def test_cd_72_report_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.md")
            ex._write_new(p, "первый прогон")
            with self.assertRaises(FileExistsError):
                ex._write_new(p, "второй")
            with open(p, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "первый прогон")

    def test_cd_73_main_refuses_by_name_when_the_sec_source_cannot_start(self):
        # Сеть не трогаем НИКОГДА: LiveSource подменён заглушкой с тем же отказом, что у LiveLoader без SEC_USER_AGENT.
        # (Реальный LiveSource здесь нельзя: другие тесты сьюта выставляют SEC_USER_AGENT, и main пошёл бы в живой SEC.)
        import contextlib
        import io
        import floor1_card as fc

        class Refusing:
            def __init__(self, as_of):
                raise RuntimeError("SEC_USER_AGENT is not set; refusing to call SEC unidentified")

        real = fc.LiveSource
        fc.LiveSource = Refusing
        try:
            with tempfile.TemporaryDirectory() as d:
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc = ex.main(["--out-dir", d])
                self.assertEqual(rc, 2)
                self.assertIn("ОТКАЗ", err.getvalue())
                self.assertEqual(os.listdir(d), [])             # файл-«результат» без данных не создан
        finally:
            fc.LiveSource = real

    def test_cd_74_main_writes_both_reports_via_injected_source(self):
        table = {(t, d): OK_FACTS for t, d in ex.CONTROLS}
        table[("NFLX", AS_OF)] = RED_FACTS
        with tempfile.TemporaryDirectory() as d:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                rc = ex.main(["--out-dir", d, "--run-date", "2026-11-02"], source=FakeSource(table, NFLX_LISTING))
            self.assertEqual(rc, 0)
            self.assertEqual(sorted(os.listdir(d)), ["CASH_DECAY_CONTROLS_2026-11-02.md", "NFLX_FY2019_2026-11-02.md"])


if __name__ == "__main__":
    unittest.main()
