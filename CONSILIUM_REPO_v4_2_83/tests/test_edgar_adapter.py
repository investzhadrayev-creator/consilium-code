"""K2 (issue #43): edgartools adapter + goldens.

Three layers, each answering a different question:

  TestSelection / TestAggregation -- PROPERTIES of the pure functions, on synthetic rows. They need
      no library and no fixture; they pin the rules (inclusive as-of, exact form match, share
      classes never summed, wrong unit / wrong period / foreign axis refused and COUNTED).
  TestGoldens -- the registered goldens, driven end to end on REAL SEC bytes
      (tests/fixtures/k2, captured by tools/k2_capture_fixtures.py): MU 2018-10-15, INTC 2022-01-25,
      META and GOOG on all five check-#1 dates. They parse real XBRL with the pinned edgartools,
      so a missing library is an ERROR here, never a skip.
  TestConsumer -- the callers of the contract: what a reader of `read_as_of()` output sees.

Expected values below are READ OFF the tool output on the captured fixtures (2026-10-18), not
recalled; the comment on each table says where. Every numbered pin has a mutation in
tools/mutation_probe.py (ids k2-NN) that turns it red.
"""
import gzip
import hashlib
import importlib.metadata
import json
import os
import unittest

from _support import load_microservice_module, REPO_ROOT

ef = load_microservice_module("edgar_facts")
ad = load_microservice_module("edgar_adapter")

FIX = os.path.join(REPO_ROOT, "tests", "fixtures", "k2")
CHECK1_DATES = ["2018-12-24", "2019-07-01", "2020-03-23", "2021-12-31", "2022-10-12"]
CIK = {"MU": "0000723125", "INTC": "0000050863", "META": "0001326801", "GOOG": "0001652044"}


def _walk_numbers(o):
    if isinstance(o, bool):
        return
    if isinstance(o, (int, float)):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _walk_numbers(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _walk_numbers(v)


def _row(concept, val, dims=None, start=None, end=None, instant=None, unit="shares"):
    return {"concept": concept, "val": val, "unit": unit, "start": start, "end": end,
            "instant": instant, "dims": dims or {}}


FILING = {"accession": "0000000000-00-000001", "form": "10-K", "filing_date": "2020-02-01",
          "period_of_report": "2019-12-31"}
A, B, C = ("us-gaap:CommonClassAMember", "us-gaap:CommonClassBMember", "goog:CapitalClassCMember")
AX = ad.CLASS_AXIS


class TestSelection(unittest.TestCase):
    LISTING = [
        {"accession": "a-1", "form": "10-K", "filing_date": "2018-10-15", "period_of_report": "x"},
        {"accession": "a-2", "form": "10-K/A", "filing_date": "2018-12-01", "period_of_report": "x"},
        {"accession": "a-3", "form": "10-Q", "filing_date": "2019-01-10", "period_of_report": "x"},
        {"accession": "a-4", "form": "10-K", "filing_date": "2019-10-16", "period_of_report": "x"},
    ]

    def test_k2_01_a_filing_dated_on_the_as_of_day_is_inside_the_slice(self):
        got = ad.select_filing(self.LISTING, "2018-10-15", ("10-K",))
        self.assertEqual(got["accession"], "a-1")

    def test_a_filing_dated_after_as_of_is_never_selected(self):
        got = ad.select_filing(self.LISTING, "2018-10-14", ("10-K",))
        self.assertIsNone(got)
        got = ad.select_filing(self.LISTING, "2019-10-15", ("10-K", "10-Q"))
        self.assertEqual(got["accession"], "a-3")

    def test_k2_04_amendments_are_not_the_annual_filing(self):
        # edgartools' form=["10-K"] also returns 10-K/A; GOOG's 2019-02-06 10-K/A has no XBRL.
        got = ad.select_filing(self.LISTING, "2018-12-31", ("10-K",))
        self.assertEqual(got["accession"], "a-1")
        self.assertEqual(got["form"], "10-K")

    def test_no_filing_is_None_not_a_default(self):
        self.assertIsNone(ad.select_filing([], "2020-01-01", ("10-K",)))
        self.assertIsNone(ad.select_filing(
            [{"accession": "z", "form": "10-K", "filing_date": "", "period_of_report": ""}],
            "2020-01-01", ("10-K",)))


class TestAggregation(unittest.TestCase):
    D = ad.C_DILUTED
    V = ad.C_COVER

    def _dil(self, rows):
        return ad.aggregate_diluted(FILING, rows)

    def test_k2_05_classes_without_a_consolidated_count_are_published_never_summed(self):
        rows = [_row(self.D, 346.0e6, {AX: A}, "2019-01-01", "2019-12-31"),
                _row(self.D, 46.0e6, {AX: B}, "2019-01-01", "2019-12-31"),
                _row(self.D, 352.0e6, {AX: C}, "2019-01-01", "2019-12-31")]
        periods, _ = self._dil(rows)
        p = periods["2019-12-31"]
        self.assertIsNone(p["total"])
        self.assertEqual(p["total_refusal"]["refused"], "MULTI_CLASS_NOT_SUMMED")
        self.assertEqual(sorted(p["classes"]), sorted([A, B, C]))
        self.assertNotIn(346.0e6 + 46.0e6 + 352.0e6, list(_walk_numbers(periods)))

    def test_a_consolidated_count_is_taken_as_reported_not_rebuilt_from_classes(self):
        # META shape: consolidated 2859M == Class A 2859M (A embeds the if-converted B of 432M).
        rows = [_row(self.D, 2859e6, {}, "2021-01-01", "2021-12-31"),
                _row(self.D, 2859e6, {AX: A}, "2021-01-01", "2021-12-31"),
                _row(self.D, 432e6, {AX: B}, "2021-01-01", "2021-12-31")]
        p = self._dil(rows)[0]["2021-12-31"]
        self.assertEqual(p["total"]["val"], 2859e6)
        self.assertNotIn("total_refusal", p)
        self.assertNotIn(2859e6 + 432e6, list(_walk_numbers(p)))

    def test_k2_06_a_non_share_unit_is_refused_and_counted(self):
        rows = [_row(self.D, 5.0, {}, "2019-01-01", "2019-12-31", unit="USD/shares")]
        periods, ignored = self._dil(rows)
        self.assertEqual(periods, {})
        self.assertEqual(ignored["wrong_unit"], 1)

    def test_k2_10_only_annual_durations_are_read(self):
        rows = [_row(self.D, 9e8, {}, "2019-10-01", "2019-12-31"),     # a quarter
                _row(self.D, 9e8, {}, "2019-01-01", "2019-12-31")]     # a year
        periods, ignored = self._dil(rows)
        self.assertEqual(list(periods), ["2019-12-31"])
        self.assertEqual(ignored["not_annual"], 1)

    def test_a_row_on_a_foreign_axis_is_not_a_class_and_is_counted(self):
        rows = [_row(self.D, 1e8, {"us-gaap:StatementBusinessSegmentsAxis": "x:SegMember"},
                     "2019-01-01", "2019-12-31")]
        periods, ignored = self._dil(rows)
        self.assertEqual(ignored["other_axes"], 1)
        p = periods["2019-12-31"]
        self.assertEqual((p["total"], p["classes"]), (None, {}))
        self.assertEqual(p["total_refusal"]["refused"], "NO_DILUTED_COUNT_IN_FILING")

    def test_a_null_value_is_not_zero(self):
        periods, ignored = self._dil([_row(self.D, None, {}, "2019-01-01", "2019-12-31")])
        self.assertEqual(periods, {})
        self.assertEqual(ignored["null_value"], 1)

    def test_cover_count_per_class_has_a_named_total_refusal(self):
        rows = [_row(self.V, 2.28e9, {AX: A}, instant="2022-07-22"),
                _row(self.V, 4.07e8, {AX: B}, instant="2022-07-22")]
        cover, _ = ad.aggregate_cover(FILING, rows)
        self.assertIsNone(cover["total"])
        self.assertEqual(cover["total_refusal"]["refused"], "MULTI_CLASS_NOT_SUMMED")
        self.assertNotIn(2.28e9 + 4.07e8, list(_walk_numbers(cover)))

    def test_cover_count_takes_the_latest_instant_in_the_filing(self):
        rows = [_row(self.V, 1.0, {}, instant="2022-01-01"), _row(self.V, 2.0, {}, instant="2022-02-01")]
        cover, _ = ad.aggregate_cover(FILING, rows)
        self.assertEqual((cover["instant"], cover["total"]["val"]), ("2022-02-01", 2.0))

    def test_no_cover_rows_is_None(self):
        self.assertEqual(ad.aggregate_cover(FILING, [])[0], None)

    def test_every_published_value_carries_provenance(self):
        rows = [_row(self.D, 1e8, {AX: A}, "2019-01-01", "2019-12-31")]
        v = self._dil(rows)[0]["2019-12-31"]["classes"][A]
        for k in ("accn", "form", "filed", "concept", "member", "unit", "source"):
            self.assertTrue(v.get(k), k)
        self.assertEqual(v["source"], "filing_xbrl:edgartools==" + ad.EDGARTOOLS_PIN)


class TestPinAndFixtures(unittest.TestCase):
    def test_k2_08_edgartools_is_pinned_exactly_and_matches_the_adapter(self):
        with open(os.path.join(REPO_ROOT, "microservice", "requirements.txt")) as fh:
            lines = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
        self.assertIn("edgartools==" + ad.EDGARTOOLS_PIN, lines)
        self.assertFalse([ln for ln in lines if ln.lower().startswith("edgartools")
                          and "==" not in ln], "edgartools must be pinned with ==")
        major = tuple(int(x) for x in ad.EDGARTOOLS_PIN.split("."))
        self.assertGreaterEqual(major, (5, 39, 1), "filing_date bugfix floor from the task card")

    def test_the_installed_library_is_the_pinned_one(self):
        self.assertEqual(importlib.metadata.version("edgartools"), ad.EDGARTOOLS_PIN)

    def test_fixtures_are_the_captured_bytes_unchanged(self):
        L = ad.FixtureLoader(FIX)
        for tk, e in L.manifest["tickers"].items():
            with gzip.open(os.path.join(FIX, "companyfacts", "CIK%s.json.gz" % e["cik"])) as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), e["companyfacts_sha256"], tk)
            for key, meta in e["companyconcept"].items():
                if meta["http_status"] == 200:
                    tax, tag = key.split("/")
                    p = os.path.join(FIX, "companyconcept", "CIK%s_%s_%s.json.gz" % (e["cik"], tax, tag))
                    with gzip.open(p) as fh:
                        self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), meta["sha256"], key)
            for acc, f in e["filings"].items():
                with gzip.open(os.path.join(FIX, "filings", acc + ".xml.gz")) as fh:
                    self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), f["instance_sha256"], acc)


class _Replay(unittest.TestCase):
    """Reads through the adapter with every network door shut and the calls RECORDED, so a
    golden that silently reached SEC would fail instead of passing on whatever SEC says today."""

    @classmethod
    def setUpClass(cls):
        cls.L = ad.FixtureLoader(FIX)
        cls.calls = []

    def setUp(self):
        self._real_get = ef._get
        self.calls = []

        def blocked(url):
            self.calls.append(url)
            raise OSError("network is closed in golden tests")
        ef._get = blocked
        for c in ef._FACTS_CACHE, ef._CONCEPT_CACHE:
            c.clear()

    def tearDown(self):
        ef._get = self._real_get
        for c in ef._FACTS_CACHE, ef._CONCEPT_CACHE:
            c.clear()

    def read(self, tk, as_of):
        out = ad.read_as_of(cik=CIK[tk], as_of=as_of, loader=self.L)
        self.assertEqual(self.calls, [], "golden read reached for the network: %r" % self.calls)
        return out


class TestGoldens(_Replay):
    # (as_of -> filing used), READ OFF the manifest the capture tool wrote from edgartools' listing.
    META_COVER = {"2018-12-24": ("0001326801-18-000067", "10-Q", "2018-10-31"),
                  "2019-07-01": ("0001326801-19-000037", "10-Q", "2019-04-25"),
                  "2020-03-23": ("0001326801-20-000013", "10-K", "2020-01-30"),
                  "2021-12-31": ("0001326801-21-000065", "10-Q", "2021-10-26"),
                  "2022-10-12": ("0001326801-22-000082", "10-Q", "2022-07-28")}
    GOOG_COVER = {"2018-12-24": ("0001652044-18-000035", "10-Q", "2018-10-26"),
                  "2019-07-01": ("0001652044-19-000015", "10-Q", "2019-04-30"),
                  "2020-03-23": ("0001652044-20-000008", "10-K", "2020-02-04"),
                  "2021-12-31": ("0001652044-21-000057", "10-Q", "2021-10-27"),
                  "2022-10-12": ("0001652044-22-000071", "10-Q", "2022-07-27")}
    GOOG_ANNUAL = {"2018-12-24": ("0001652044-18-000007", "2018-02-06"),
                   "2019-07-01": ("0001652044-19-000004", "2019-02-05"),
                   "2020-03-23": ("0001652044-20-000008", "2020-02-04"),
                   "2021-12-31": ("0001652044-21-000010", "2021-02-03"),
                   "2022-10-12": ("0001652044-22-000019", "2022-02-02")}
    # META consolidated diluted shares: last FY in the as-of slice, from companyfacts.
    META_DILUTED_LAST = {"2018-12-24": ("2017-12-31", 2956e6), "2019-07-01": ("2018-12-31", 2921e6),
                         "2020-03-23": ("2019-12-31", 2876e6), "2021-12-31": ("2020-12-31", 2888e6),
                         "2022-10-12": ("2021-12-31", 2859e6)}

    def test_k2_02_MU_2018_10_15_the_10K_filed_that_very_day_is_inside_the_slice(self):
        out = self.read("MU", "2018-10-15")
        self.assertEqual(out["_adapter"]["path"], "fast")
        self.assertEqual(out["_errors"], {})
        last = out["revenue_audit"][-1]
        self.assertEqual((last["end"], last["val"], last["accn"], last["filed"], last["form"]),
                         ("2018-08-30", 30391000000, "0000723125-18-000092", "2018-10-15", "10-K"))
        self.assertEqual(out["net_income_audit"][-1]["val"], 14135000000)
        self.assertEqual(out["shares_diluted_audit"][-1]["val"], 1229000000)
        self.assertEqual(out["_as_of_check"]["max_filed"], "2018-10-15")
        self.assertEqual(out["_as_of_check"]["violations"], [])

    def test_k2_03_INTC_2022_01_25_FY2021_filed_two_days_later_is_outside_the_slice(self):
        # The raw fixture DOES contain FY2021 filed 2022-01-27 -- proving the exclusion is the
        # slice at work and not an absence in the data.
        raw = self.L.companyfacts(CIK["INTC"])
        rev = raw["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
        later = [f for f in rev if f["filed"] == "2022-01-27" and f["end"] == "2021-12-25"]
        self.assertTrue(later, "fixture lost the FY2021 row the slice must exclude")
        out = self.read("INTC", "2022-01-25")
        self.assertEqual(out["_adapter"]["path"], "fast")
        last = out["revenue_audit"][-1]
        self.assertEqual((last["end"], last["val"], last["accn"], last["filed"]),
                         ("2020-12-26", 77867000000, "0000050863-21-000010", "2021-01-22"))
        self.assertEqual(out["_staleness"]["latest_annual_end"], "2020-12-26")
        self.assertLessEqual(out["_as_of_check"]["max_filed"], "2022-01-25")
        self.assertEqual(out["_as_of_check"]["violations"], [])
        self.assertEqual(out["shares_current"], 4067000000)
        self.assertEqual(out["shares_current_audit"]["filed"], "2021-10-22")

    def test_k2_07_META_reads_on_all_five_check1_dates_without_a_substitution(self):
        for d in CHECK1_DATES:
            with self.subTest(as_of=d):
                out = self.read("META", d)
                self.assertEqual(out["_errors"], {})
                self.assertEqual(out["_adapter"]["path"], "filing_level")
                # the cover count exists only per class: no number, a NAMED refusal, no proxy
                self.assertIsNone(out["shares_current"])
                self.assertEqual(out["_refusals"]["shares_current"]["refused"], "MULTI_CLASS_NOT_SUMMED")
                self.assertNotIn("shares_current_proxied", out["_flags"])
                self.assertIn("shares_current_proxy_rejected", out["_flags"])
                acc, form, filed = self.META_COVER[d]
                f = out["shares_current_filing"]
                self.assertEqual((f["filing"]["accession"], f["filing"]["form"], f["filing"]["filing_date"]),
                                 (acc, form, filed))
                cls = f["cover"]["classes"]
                self.assertEqual(sorted(cls), sorted([A, B]))
                for m, v in cls.items():
                    self.assertEqual((v["accn"], v["unit"], v["concept"]), (acc, "shares", ad.C_COVER))
                    self.assertLessEqual(v["filed"], d)
                self.assertEqual(out["_as_of_check"]["violations"], [])
                end, val = self.META_DILUTED_LAST[d]
                self.assertEqual((out["shares_diluted"][-1]["end"], out["shares_diluted"][-1]["val"]),
                                 (end, val))

    def test_k2_09_GOOG_reads_on_all_five_check1_dates_with_classes_not_a_total(self):
        for d in CHECK1_DATES:
            with self.subTest(as_of=d):
                out = self.read("GOOG", d)
                self.assertEqual(out["_errors"], {})
                self.assertEqual(out["_adapter"]["path"], "filing_level")
                # annual diluted shares: three classes, no consolidated figure, total refused
                self.assertIn("shares_diluted", out["_missing"])
                self.assertIsNone(out["shares_diluted"])
                self.assertEqual(out["_refusals"]["shares_diluted"]["refused"], "MULTI_CLASS_NOT_SUMMED")
                sd = out["shares_diluted_filing"]
                acc, filed = self.GOOG_ANNUAL[d]
                self.assertEqual((sd["filing"]["accession"], sd["filing"]["form"], sd["filing"]["filing_date"]),
                                 (acc, "10-K", filed))
                self.assertGreaterEqual(len(sd["periods"]), 3)
                for end, p in sd["periods"].items():
                    self.assertEqual(sorted(p["classes"]), sorted([A, B, C]), end)
                    self.assertIsNone(p["total"], end)
                    classsum = sum(v["val"] for v in p["classes"].values())
                    self.assertNotIn(classsum, list(_walk_numbers(out)), "class sum leaked: " + end)
                    for v in p["classes"].values():
                        self.assertEqual((v["accn"], v["unit"], v["concept"]), (acc, "shares", ad.C_DILUTED))
                        self.assertLessEqual(v["filed"], d)
                # shares_current: GOOG's fast path holds a balance-sheet count of the latest 10-K/
                # 10-Q in the slice (not proxied), so no cover read happens and none is claimed.
                cacc, cform, cfiled = self.GOOG_COVER[d]
                self.assertNotIn("shares_current_filing", out)
                self.assertEqual(out["_field_sources"]["shares_current"],
                                 "us-gaap:CommonStockSharesOutstanding (companyfacts)")
                self.assertEqual(out["shares_current_audit"]["accn"], cacc)
                self.assertEqual(out["shares_current_audit"]["filed"], cfiled)
                self.assertEqual(out["_as_of_check"]["violations"], [])

    def test_the_listing_agrees_with_companyfacts_on_every_filing_date_and_the_check_is_not_vacuous(self):
        # The 5.39.1 filing_date bug class: the library's date vs SEC's own `filed`.
        for tk in ("META", "GOOG"):
            for d in CHECK1_DATES:
                out = self.read(tk, d)
                self.assertNotIn("filing_date_mismatch", out["_flags"], (tk, d))
                for key in ("shares_diluted_filing", "shares_current_filing"):
                    if key in out:
                        seen = out[key]["companyfacts_filed_for_accession"]
                        self.assertEqual(seen, [out[key]["filing"]["filing_date"]], (tk, d, key))

    def test_golden_reads_are_deterministic(self):
        a = json.dumps(self.read("GOOG", "2022-10-12"), sort_keys=True, default=str)
        for c in ef._FACTS_CACHE, ef._CONCEPT_CACHE:
            c.clear()
        b = json.dumps(self.read("GOOG", "2022-10-12"), sort_keys=True, default=str)
        self.assertEqual(a, b)


class TestConsumer(_Replay):
    def test_k2_11_the_as_of_check_names_a_fact_filed_after_the_day(self):
        out = {"revenue_audit": [{"end": "2020-12-26", "filed": "2021-01-22"},
                                 {"end": "2021-12-25", "filed": "2022-01-27"}]}
        chk = ad._as_of_check(out, "2022-01-25")
        self.assertEqual(chk["violations"], ["2022-01-27"])
        self.assertEqual(chk["max_filed"], "2022-01-27")

    def test_k2_12_a_listing_date_that_disagrees_with_companyfacts_is_flagged_loudly(self):
        class Skewed(ad.FixtureLoader):
            def listing(self, cik):
                rows = super().listing(cik)
                for r in rows:
                    if r["accession"] == "0001326801-18-000067":
                        r["filing_date"] = "2018-10-30"        # SEC's `filed` is 2018-10-31
                return rows
        L = Skewed(FIX)
        out = ad.read_as_of(cik=CIK["META"], as_of="2018-12-24", loader=L)
        mm = out["_flags"]["filing_date_mismatch"]
        self.assertEqual(mm[0]["accession"], "0001326801-18-000067")
        self.assertEqual(mm[0]["companyfacts"], ["2018-10-31"])
        self.assertEqual(mm[0]["listing"], "2018-10-30")

    def test_without_a_loader_a_gap_is_a_named_refusal_not_a_proxy(self):
        self.L.seed(CIK["META"])
        out = ad.read_as_of(cik=CIK["META"], as_of="2022-10-12", loader=None)
        self.assertEqual(self.calls, [])
        self.assertEqual(out["_refusals"]["shares_current"]["refused"], "FILING_LEVEL_UNAVAILABLE")
        self.assertIn("shares_current_proxied", out["_flags"])      # the fast path's flag is untouched

    def test_staleness_is_measured_in_days_from_the_registered_dates(self):
        out = self.read("META", "2022-10-12")
        s = out["_staleness"]
        self.assertEqual((s["latest_annual_end"], s["cover_count_date"]), ("2021-12-31", "2022-07-22"))
        self.assertEqual(s["latest_annual_age_days"], 285)       # 2021-12-31 -> 2022-10-12
        self.assertEqual(s["cover_count_age_days"], 82)          # 2022-07-22 -> 2022-10-12
        self.assertNotIn("stale", json.dumps(s))                 # no threshold verdict is invented

    def test_as_of_is_required(self):
        with self.assertRaises(ValueError):
            ad.read_as_of(cik=CIK["MU"], as_of=None)

    def test_the_fast_path_is_untouched_when_there_is_no_gap(self):
        out = self.read("MU", "2018-10-15")
        direct = ef.edgar_facts(cik=CIK["MU"], as_of="2018-10-15")
        for k in ("revenue", "net_income", "shares_diluted", "shares_current", "_missing"):
            self.assertEqual(out[k], direct[k], k)
        self.assertEqual(out["_refusals"], {})


if __name__ == "__main__":
    unittest.main()
