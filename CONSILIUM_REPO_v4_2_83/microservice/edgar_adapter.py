"""K2 (issue #43): edgartools adapter -- as-of reads with a filing-level fallback.

DIVISION OF LABOUR (round 7 decision, task K2 point 2)
  The library (edgartools, pinned in requirements.txt) is TRANSPORT and PARSER only: it lists
  filings and turns an XBRL instance document into fact rows. Everything that decides what a
  number MEANS stays here, in code we can read and test:
    * the as-of slice          -- `filed <= as_of`, inclusive, our comparison, never the lib's
    * period / basis           -- annual durations only, unit must be `shares`
    * dimension aggregation    -- share classes are NEVER summed (see below)
    * staleness                -- measured ages, no invented threshold
    * provenance               -- accession / form / filing date / concept / member on every value
    * named refusal            -- an unknown is a `{code, reason}` dict, never a plausible number

FAST PATH is `edgar_facts.edgar_facts()` on the companyfacts payload (unchanged). The filing-level
path runs ONLY when the fast path reports a gap that companyfacts cannot close:
  * `shares_diluted` missing  -- GOOG: diluted shares exist only per share class
  * `shares_current_proxied`  -- META/GOOG: the cover count exists only per share class, and the
                                 fast path substituted the weighted-average diluted count

WHY SHARE CLASSES ARE NOT SUMMED
  Measured on the fixtures: META FY2021 reports a CONSOLIDATED diluted count of 2.859B, and its
  Class A diluted count is also 2.859B -- the Class A figure already embeds the if-converted
  Class B shares. Adding Class A + Class B (2.859B + 0.432B) would double-count 432M shares.
  GOOG's per-class diluted figures carry the same structure. A class-wise total is therefore a
  METHOD decision, not arithmetic; this module refuses it by name and publishes the classes.
"""
import datetime as _dt
import gzip
import json
import os

import edgar_facts as ef

EDGARTOOLS_PIN = "5.48.0"          # must equal the pin in requirements.txt (a test compares)
CLASS_AXIS = "us-gaap:StatementClassOfStockAxis"
C_DILUTED = "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"
C_COVER = "dei:EntityCommonStockSharesOutstanding"
WANTED_CONCEPTS = (C_DILUTED, C_COVER)
ANNUAL_FORMS = ("10-K",)            # exact match: edgartools' form=["10-K"] also returns 10-K/A
COVER_FORMS = ("10-K", "10-Q")      # amendments are excluded for the same reason
ANNUAL_DAYS = (350, 380)            # a 52/53-week or calendar fiscal year


def refusal(code, reason):
    return {"refused": code, "reason": reason}


# ----------------------------------------------------------------------------- selection

def select_filing(listing, as_of, forms):
    """Latest filing of an EXACT form in `forms` with filing_date <= as_of (inclusive).

    `listing` rows: {accession, form, filing_date 'YYYY-MM-DD', period_of_report}. The comparison
    is made here on ISO strings; the library's own date filter is not used for the as-of property
    (it carried a filing_date bug before 5.39.1, and the property is too important to delegate).
    """
    ok = [r for r in listing if r.get("form") in forms and str(r.get("filing_date") or "") != ""
          and str(r["filing_date"]) <= as_of]
    if not ok:
        return None
    return max(ok, key=lambda r: (str(r["filing_date"]), r["accession"]))


# ----------------------------------------------------------------------------- fact rows

def _dims(row, dim_cols):
    d = {}
    for c in dim_cols:
        v = row.get(c)
        if isinstance(v, str) and v:
            d[c[len("dim_"):].replace("_", ":", 1)] = v
    ax = row.get("dimension")
    if isinstance(ax, str) and ax and ax not in d:
        d[ax] = row.get("member")
    return d


def facts_from_instance(instance_path):
    """Parse one XBRL instance document with edgartools into plain dict rows (the only place the
    library is touched for parsing). Rows: concept, val, unit, start, end, instant, dims."""
    from edgar.xbrl import XBRL
    df = XBRL.from_files(instance_file=str(instance_path)).facts.to_dataframe()
    dim_cols = [c for c in df.columns if str(c).startswith("dim_")]
    rows = []
    for r in df[df["concept"].isin(WANTED_CONCEPTS)].to_dict("records"):
        def _s(k):
            v = r.get(k)
            return v if isinstance(v, str) else None
        v = r.get("numeric_value")
        rows.append({"concept": r["concept"],
                     "val": None if v is None or v != v else v,
                     "unit": _s("unit_ref"), "start": _s("period_start"), "end": _s("period_end"),
                     "instant": _s("period_instant"), "dims": _dims(r, dim_cols)})
    return rows


# ----------------------------------------------------------------------------- loaders

class FixtureLoader:
    """Offline replay of captured SEC bytes (tests/fixtures/k2, see tools/k2_capture_fixtures.py)."""

    def __init__(self, root):
        self.root = root
        with open(os.path.join(root, "manifest.json")) as fh:
            self.manifest = json.load(fh)

    def _entry(self, cik):
        for e in self.manifest["tickers"].values():
            if e["cik"] == cik:
                return e
        raise KeyError("no fixture for CIK %s" % cik)

    def companyfacts(self, cik):
        p = os.path.join(self.root, "companyfacts", "CIK%s.json.gz" % cik)
        with gzip.open(p) as fh:
            return json.loads(fh.read().decode("utf-8"))

    def seed(self, cik):
        """Pre-load edgar_facts' caches with the captured responses so the fast path makes no
        network call. Returns the (cik, taxonomy, tag) keys seeded, for the hermeticity test."""
        import time
        far = time.time() + 10 ** 9
        ef._FACTS_CACHE[cik] = (far, self.companyfacts(cik))
        keys = []
        for key, meta in self._entry(cik).get("companyconcept", {}).items():
            tax, tag = key.split("/")
            units = None
            if meta["http_status"] == 200:
                p = os.path.join(self.root, "companyconcept", "CIK%s_%s_%s.json.gz" % (cik, tax, tag))
                with gzip.open(p) as fh:
                    units = json.loads(fh.read().decode("utf-8")).get("units")
            ef._CONCEPT_CACHE[(cik, tax, tag)] = (far, units)   # 404 replays as "no such concept"
            keys.append((cik, tax, tag))
        return keys

    def listing(self, cik):
        return [{"accession": a, "form": f["form"], "filing_date": f["filing_date"],
                 "period_of_report": f["period_of_report"]}
                for a, f in self._entry(cik)["filings"].items()]

    def facts(self, cik, accession):
        import tempfile
        meta = self._entry(cik)["filings"][accession]
        with gzip.open(os.path.join(self.root, "filings", accession + ".xml.gz")) as fh:
            raw = fh.read()
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, meta["instance_file"])
            with open(p, "wb") as out:
                out.write(raw)
            return facts_from_instance(p)


class LiveLoader:
    """Production transport: edgartools for the filing list, urllib + SEC_USER_AGENT for bytes."""

    def __init__(self, user_agent=None):
        self.ua = user_agent or ef.SEC_USER_AGENT
        if "NOT SET" in self.ua:
            raise RuntimeError("SEC_USER_AGENT is not set; refusing to call SEC unidentified")
        from edgar import set_identity
        set_identity(self.ua)

    def listing(self, cik):
        from edgar import Company
        return [{"accession": f.accession_no, "form": f.form, "filing_date": str(f.filing_date),
                 "period_of_report": str(f.period_of_report), "_filing": f}
                for f in Company(cik).get_filings(form=list(COVER_FORMS))]

    def facts(self, cik, accession):
        import tempfile
        import urllib.request
        from edgar import Company
        f = next(x for x in Company(cik).get_filings(form=list(COVER_FORMS))
                 if x.accession_no == accession)
        name = next(str(a.document) for a in f.attachments
                    if str(a.document_type) == "EX-101.INS"
                    or (str(a.document).endswith("_htm.xml") and str(a.document_type) == "XML"))
        url = "https://www.sec.gov/Archives/edgar/data/%d/%s/%s" % (
            int(cik), accession.replace("-", ""), name)
        ef._throttle()
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=60) as r, tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, name)
            with open(p, "wb") as out:
                out.write(r.read())
            return facts_from_instance(p)


# ----------------------------------------------------------------------------- aggregation

def _prov(filing, row, member=None):
    return {"concept": row["concept"], "member": member, "unit": row["unit"],
            "accn": filing["accession"], "form": filing["form"],
            "filed": filing["filing_date"], "source": "filing_xbrl:edgartools==" + EDGARTOOLS_PIN}


def _annual(row):
    return bool(row.get("start") and row.get("end")
                and ANNUAL_DAYS[0] <= ef._days(row["start"], row["end"]) <= ANNUAL_DAYS[1])


def aggregate_diluted(filing, rows):
    """Per fiscal period: consolidated (undimensioned) value if the filing reports one, plus the
    per-class values. Returns (periods, ignored) where `ignored` counts rows we refuse to read."""
    periods, ignored = {}, {"not_annual": 0, "wrong_unit": 0, "other_axes": 0, "null_value": 0}
    for r in rows:
        if r["concept"] != C_DILUTED:
            continue
        if not _annual(r):
            ignored["not_annual"] += 1
            continue
        if r["unit"] != "shares":
            ignored["wrong_unit"] += 1
            continue
        if r["val"] is None:
            ignored["null_value"] += 1
            continue
        p = periods.setdefault(r["end"], {"start": r["start"], "total": None, "classes": {}})
        if not r["dims"]:
            p["total"] = dict(_prov(filing, r), val=r["val"], start=r["start"], end=r["end"])
        elif list(r["dims"]) == [CLASS_AXIS]:
            m = r["dims"][CLASS_AXIS]
            p["classes"][m] = dict(_prov(filing, r, m), val=r["val"], start=r["start"], end=r["end"])
        else:
            ignored["other_axes"] += 1
    for end, p in periods.items():
        if p["total"] is None:
            p["total_refusal"] = refusal(
                "MULTI_CLASS_NOT_SUMMED" if p["classes"] else "NO_DILUTED_COUNT_IN_FILING",
                "the filing reports no consolidated diluted count for this period; per-class "
                "diluted counts may embed other classes (if-converted), so they are not summed")
    return periods, ignored


def aggregate_cover(filing, rows):
    """The cover-page count at its own date: consolidated if reported, else per class."""
    best = {}
    ignored = {"wrong_unit": 0, "other_axes": 0, "null_value": 0}
    for r in rows:
        if r["concept"] != C_COVER or not r.get("instant"):
            continue
        if r["unit"] != "shares":
            ignored["wrong_unit"] += 1
            continue
        if r["val"] is None:
            ignored["null_value"] += 1
            continue
        slot = best.setdefault(r["instant"], {"total": None, "classes": {}})
        if not r["dims"]:
            slot["total"] = dict(_prov(filing, r), val=r["val"], instant=r["instant"])
        elif list(r["dims"]) == [CLASS_AXIS]:
            m = r["dims"][CLASS_AXIS]
            slot["classes"][m] = dict(_prov(filing, r, m), val=r["val"], instant=r["instant"])
        else:
            ignored["other_axes"] += 1
    if not best:
        return None, ignored
    instant = max(best)
    slot = best[instant]
    out = {"instant": instant, "total": slot["total"], "classes": slot["classes"]}
    if slot["total"] is None:
        out["total_refusal"] = refusal(
            "MULTI_CLASS_NOT_SUMMED" if slot["classes"] else "NO_COVER_COUNT_IN_FILING",
            "no consolidated cover count; per-class counts are published, the total is a method "
            "decision (voting vs economic classes), so it is not computed here")
    return out, ignored


# ----------------------------------------------------------------------------- the read

def _needs_filing_level(out):
    why = []
    if "shares_diluted" in out.get("_missing", []):
        why.append("shares_diluted missing from companyfacts")
    if "shares_current_proxied" in out.get("_flags", {}):
        why.append("shares_current proxied from weighted-average diluted (cover count absent)")
    return why


def _companyfacts_filed(facts, accession):
    """The `filed` date companyfacts attaches to an accession, or None when it never mentions it."""
    seen = set()
    for tax in (facts.get("facts") or {}).values():
        for block in tax.values():
            for rows in (block.get("units") or {}).values():
                for f in rows:
                    if f.get("accn") == accession and f.get("filed"):
                        seen.add(f["filed"])
    return sorted(seen)


def _age_days(later, earlier):
    try:
        return (_dt.date.fromisoformat(later) - _dt.date.fromisoformat(earlier)).days
    except Exception:
        return None


def read_as_of(ticker=None, cik=None, as_of=None, loader=None):
    """The adapter entry point. `as_of` is required: the unqualified read is edgar_facts().
    A loader with `seed()` (FixtureLoader) replays captured responses; pass `cik` with it."""
    if not as_of:
        raise ValueError("as_of is required (use edgar_facts.edgar_facts for the live read)")
    if cik and hasattr(loader, "seed"):
        loader.seed(cik)
    out = ef.edgar_facts(ticker=ticker, cik=cik, as_of=as_of)
    out["_adapter"] = {"path": "fast", "edgartools": EDGARTOOLS_PIN, "as_of": as_of}
    out["_refusals"] = {}
    if out.get("_errors"):
        return out
    cik = out["_cik"]

    why = _needs_filing_level(out)
    if why:
        out["_adapter"]["path"] = "filing_level"
        out["_adapter"]["filing_level_reasons"] = why
        if loader is None:
            for fld in ("shares_diluted", "shares_current"):
                if fld in out["_missing"] or out.get(fld) is None or "shares_current_proxied" in out["_flags"]:
                    out["_refusals"][fld] = refusal(
                        "FILING_LEVEL_UNAVAILABLE", "fast path has a gap and no loader was given: "
                        + "; ".join(why))
        else:
            _filing_level(out, cik, as_of, loader)

    out["_staleness"] = _staleness(out, as_of)
    out["_as_of_check"] = _as_of_check(out, as_of)
    return out


def _filing_level(out, cik, as_of, loader):
    listing = loader.listing(cik)
    facts = ef._companyfacts(cik)        # cached by the fast path just before; same payload

    # --- annual diluted shares (only if the fast path could not supply them) ---
    if "shares_diluted" in out["_missing"]:
        f = select_filing(listing, as_of, ANNUAL_FORMS)
        if f is None:
            out["_refusals"]["shares_diluted"] = refusal(
                "NO_FILING_AS_OF", "no 10-K filed on or before %s in the filing list" % as_of)
        else:
            periods, ignored = aggregate_diluted(f, loader.facts(cik, f["accession"]))
            out["shares_diluted_filing"] = {
                "filing": {k: f[k] for k in ("accession", "form", "filing_date", "period_of_report")},
                "periods": periods, "ignored_rows": ignored,
                "companyfacts_filed_for_accession": _companyfacts_filed(facts, f["accession"])}
            totals = [{"end": e, "val": p["total"]["val"]} for e, p in sorted(periods.items())
                      if p["total"]]
            if totals and len(totals) == len(periods):
                out["shares_diluted"] = totals
                out["_missing"].remove("shares_diluted")
                out["_field_sources"]["shares_diluted"] = "filing_xbrl:" + f["accession"]
            else:
                missing = [e for e, p in sorted(periods.items()) if not p["total"]]
                out["_refusals"]["shares_diluted"] = (
                    periods[missing[0]]["total_refusal"] if missing else
                    refusal("NO_DILUTED_COUNT_IN_FILING", "no annual diluted rows in %s" % f["accession"]))

    # --- cover count (replaces the proxy; never a substitution) ---
    if "shares_current_proxied" in out["_flags"]:
        f = select_filing(listing, as_of, COVER_FORMS)
        proxy = out.get("shares_current")
        if f is None:
            out["_refusals"]["shares_current"] = refusal(
                "NO_FILING_AS_OF", "no 10-K/10-Q filed on or before %s in the filing list" % as_of)
        else:
            cover, ignored = aggregate_cover(f, loader.facts(cik, f["accession"]))
            out["shares_current_filing"] = {
                "filing": {k: f[k] for k in ("accession", "form", "filing_date", "period_of_report")},
                "cover": cover, "ignored_rows": ignored,
                "companyfacts_filed_for_accession": _companyfacts_filed(facts, f["accession"])}
            if cover and cover["total"]:
                out["shares_current"] = cover["total"]["val"]
                out["shares_current_audit"] = cover["total"]
                out["_field_sources"]["shares_current"] = "filing_xbrl:" + f["accession"]
            else:
                out["shares_current"] = None
                out["_refusals"]["shares_current"] = (
                    cover["total_refusal"] if cover else
                    refusal("NO_COVER_COUNT_IN_FILING", "no cover share count in %s" % f["accession"]))
                out["_field_sources"]["shares_current"] = None
        out["_flags"]["shares_current_proxy_rejected"] = (
            "the fast path's weighted-average diluted proxy (%s) is not a cover count and was "
            "dropped" % (proxy,))
        del out["_flags"]["shares_current_proxied"]

    for f in (out.get("shares_diluted_filing"), out.get("shares_current_filing")):
        if not f:
            continue
        cf = f["companyfacts_filed_for_accession"]
        if cf and f["filing"]["filing_date"] not in cf:
            out["_flags"].setdefault("filing_date_mismatch", []).append(
                {"accession": f["filing"]["accession"], "listing": f["filing"]["filing_date"],
                 "companyfacts": cf})


def _staleness(out, as_of):
    """Measured ages in days at `as_of`; no threshold is applied here (none is registered)."""
    s = {"as_of": as_of}
    ends = [r["end"] for r in (out.get("revenue") or [])]
    s["latest_annual_end"] = max(ends) if ends else None
    s["latest_annual_age_days"] = _age_days(as_of, s["latest_annual_end"]) if ends else None
    cover = (out.get("shares_current_filing") or {}).get("cover")
    inst = cover["instant"] if cover else (out.get("shares_current_audit") or {}).get("end")
    s["cover_count_date"] = inst
    s["cover_count_age_days"] = _age_days(as_of, inst) if inst else None
    return s


def _as_of_check(out, as_of):
    """Consumer-side proof of the slice: the largest `filed` date among everything returned."""
    filed = []
    for k, v in out.items():
        if k.endswith("_audit") and isinstance(v, list):
            filed += [x.get("filed") for x in v if isinstance(x, dict)]
        elif k.endswith("_audit") and isinstance(v, dict):
            filed.append(v.get("filed"))
    for k in ("shares_diluted_filing", "shares_current_filing"):
        if out.get(k):
            filed.append(out[k]["filing"]["filing_date"])
    filed = [x for x in filed if x]
    violations = [x for x in filed if x > as_of]
    return {"max_filed": max(filed) if filed else None, "n_dated": len(filed),
            "violations": violations}
