#!/usr/bin/env python3
"""Capture the K2 golden fixtures from SEC, byte-for-byte.

    SEC_USER_AGENT="Name email@host" python3 tools/k2_capture_fixtures.py

What is stored, and what is NOT touched:
  * companyfacts/CIK<cik>.json  -- the response body exactly as SEC served it (gzip transfer
    encoding as received; sha256 of the DECODED body recorded in manifest.json).
  * filings/<accession>.xml.gz  -- the filing's XBRL instance document, exactly as served, gzip-
    wrapped ONLY for repo size (sha256 of the raw, unwrapped bytes recorded).
  * manifest.json -- per ticker: cik, as_of dates, and for each filing used: accession, form,
    filing_date, period_of_report, instance file name, sha256. The filing LIST fields
    (accession/form/filing_date/period) are read from edgartools Filing objects; they are
    metadata about a filing, not bytes SEC served, and the manifest says so.
Nothing is edited, trimmed or re-serialised. SEC requests carry ONLY the User-Agent from env.
"""
import datetime as dt
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "microservice"))
import edgar_facts as ef  # noqa: E402
OUT = os.path.join(HERE, "..", "tests", "fixtures", "k2")

CASES = {
    "MU": {"cik": "0000723125", "as_of": ["2018-10-15"]},
    "INTC": {"cik": "0000050863", "as_of": ["2022-01-25"]},
    "META": {"cik": "0001326801",
             "as_of": ["2018-12-24", "2019-07-01", "2020-03-23", "2021-12-31", "2022-10-12"]},
    "GOOG": {"cik": "0001652044",
             "as_of": ["2018-12-24", "2019-07-01", "2020-03-23", "2021-12-31", "2022-10-12"]},
}
# MU / INTC are fast-path goldens (no share-class dimension); only META / GOOG need filing-level.
FILING_LEVEL = ("META", "GOOG")


def _ua():
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not ua or "NOT SET" in ua or "example.com" in ua:
        sys.exit("SEC_USER_AGENT is not set to a real contact; refusing to call SEC.")
    return ua


def _fetch(url, ua):
    time.sleep(0.2)
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        enc = r.headers.get("Content-Encoding")
    return gzip.decompress(raw) if enc == "gzip" else raw


def _fetch_or_status(url, ua):
    """(body, 200) or (None, http_status). A 404 is DATA here: edgar_facts' cover-count cascade
    reads companyconcept, and 'SEC has no such concept for this filer' must replay as 404."""
    try:
        return _fetch(url, ua), 200
    except urllib.error.HTTPError as e:
        return None, e.code


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _instance_name(filing):
    """The XBRL instance: inline filings serve it as *_htm.xml, pre-inline as EX-101.INS."""
    for a in filing.attachments:
        doc, typ = str(a.document), str(a.document_type)
        if typ == "EX-101.INS" or (doc.endswith("_htm.xml") and typ == "XML"):
            return doc
    return None


def main():
    ua = _ua()
    from edgar import Company, set_identity
    set_identity(ua)
    os.makedirs(os.path.join(OUT, "companyfacts"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "filings"), exist_ok=True)
    manifest = {"captured": dt.date.today().isoformat(), "edgartools": None, "tickers": {}}
    import edgar
    manifest["edgartools"] = getattr(edgar, "__version__", None)
    for tk, case in CASES.items():
        cik = case["cik"]
        body = _fetch("https://data.sec.gov/api/xbrl/companyfacts/CIK%s.json" % cik, ua)
        with gzip.GzipFile(os.path.join(OUT, "companyfacts", "CIK%s.json.gz" % cik), "wb", mtime=0) as g:
            g.write(body)
        entry = {"cik": cik, "as_of": case["as_of"], "companyfacts_sha256": _sha(body),
                 "filings": {}, "companyconcept": {}}
        # EVERY companyconcept URL edgar_facts() reads for these as_of dates (cover-count cascade
        # and split confirmation), recorded by running it for real. A 404 is data too.
        seen = {}
        cc_dir = os.path.join(OUT, "companyconcept")

        def _recording_get(url):
            if "/companyconcept/" not in url:
                raise RuntimeError("unexpected non-companyconcept fetch: " + url)
            body_, status_ = _fetch_or_status(url, ua)
            tax_, tag_ = url.split("/")[-2], url.split("/")[-1][:-len(".json")]
            seen[tax_ + "/" + tag_] = (body_, status_)
            if status_ != 200:
                raise urllib.error.HTTPError(url, status_, "recorded", None, None)
            return json.loads(body_.decode("utf-8"))

        ef._FACTS_CACHE[cik] = (time.time() + 10 ** 9, json.loads(body.decode("utf-8")))
        real_get, ef._get = ef._get, _recording_get
        try:
            for d in case["as_of"]:
                ef.edgar_facts(cik=cik, as_of=d)
        finally:
            ef._get = real_get
        os.makedirs(cc_dir, exist_ok=True)
        for key, (body_, status_) in sorted(seen.items()):
            entry["companyconcept"][key] = {"http_status": status_,
                                            "sha256": _sha(body_) if body_ else None}
            if body_:
                with gzip.GzipFile(os.path.join(cc_dir, "CIK%s_%s_%s.json.gz" % (
                        cik, key.split("/")[0], key.split("/")[1])), "wb", mtime=0) as g:
                    g.write(body_)
        if tk in FILING_LEVEL:
            company = Company(cik)
            for form in (["10-K"], ["10-K", "10-Q"]):
                for d in case["as_of"]:
                    # OUR filter on filing_date <= as_of -- the library's own date filter is not
                    # trusted for the as-of property (it had a filing_date bug before 5.39.1).
                    # OUR exact form match too: form=["10-K"] also returns 10-K/A, and GOOG's
                    # 10-K/A of 2019-02-06 is an exhibit-only amendment with no XBRL at all.
                    cands = [f for f in company.get_filings(form=form)
                             if str(f.filing_date) <= d and f.form in form]
                    f = max(cands, key=lambda x: (str(x.filing_date), x.accession_no))
                    acc = f.accession_no
                    if acc in entry["filings"]:
                        continue
                    name = _instance_name(f)
                    if not name:
                        sys.exit("no XBRL instance document found for %s" % acc)
                    url = "https://www.sec.gov/Archives/edgar/data/%d/%s/%s" % (
                        int(cik), acc.replace("-", ""), name)
                    raw = _fetch(url, ua)
                    with gzip.GzipFile(os.path.join(OUT, "filings", acc + ".xml.gz"), "wb", mtime=0) as g:
                        g.write(raw)
                    entry["filings"][acc] = {
                        "form": f.form, "filing_date": str(f.filing_date),
                        "period_of_report": str(f.period_of_report), "instance_file": name,
                        "instance_sha256": _sha(raw), "instance_url": url}
        manifest["tickers"][tk] = entry
        print(tk, cik, "companyfacts", len(body), "bytes;", len(entry["filings"]), "filings")
    with open(os.path.join(OUT, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    main()
