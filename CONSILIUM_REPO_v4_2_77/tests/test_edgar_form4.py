"""
Regression tests for microservice/edgar_form4.py — SEC Form 4 insider transactions.

Why this module exists: the memo used to source insider activity from Perplexity's FACT_PACK
prose, which on a live run produced an impossible trade — "600 shares for $1,655" ($2.76/share
against a ~$1,852 stock). The auditor caught it, but it should never have been possible. Pulling
structured data from the filing itself makes that class of error structurally impossible.

Two failure modes are guarded here:
  1. PARSING (v2.9): the real client parsed 0 of 40 filings because SEC's `primaryDocument`
     for a Form 4 points at the XSL-RENDERED HTML view, not the machine-readable XML.
  2. CATEGORISATION: conflating grants/vesting/exercises (A/M/F/X — nominal or strike price)
     with real open-market buys/sells (P/S) is precisely how a $2.76/share "purchase" looks
     plausible in prose.

All tests are offline (no SEC request).
"""
import unittest

from _support import load_microservice_module

f4 = load_microservice_module("edgar_form4")


SAMPLE_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <issuer><issuerTradingSymbol>TEST</issuerTradingSymbol></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>Jane Doe</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>0</isDirector><isOfficer>1</isOfficer>
      <officerTitle>CEO</officerTitle><isTenPercentOwner>0</isTenPercentOwner>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-05-01</value></transactionDate>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>600</value></transactionShares>
        <transactionPricePerShare><value>1852.30</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>50000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-04-15</value></transactionDate>
      <transactionCoding><transactionCode>F</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1200</value></transactionShares>
        <transactionPricePerShare><value>0.00</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>50600</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  <footnotes><footnote id="F1">Sold pursuant to a Rule 10b5-1 trading plan adopted March 2026.</footnote></footnotes>
</ownershipDocument>"""


class TestXslDocumentResolution(unittest.TestCase):
    """v2.9 regression — the bug that silently returned ZERO insider data.

    SEC's primaryDocument for Form 4 is usually 'xslF345X05/wf-form4_x.xml', which serves an
    HTML rendering. Fetching it verbatim yields unparseable content for EVERY filing, so the
    pipeline reported 'no insider data' rather than 'parser broken' — a silent, total failure.
    """

    def test_xsl_prefix_is_stripped_to_reach_the_real_xml(self):
        self.assertEqual(f4._raw_doc_name("xslF345X05/wf-form4_174628.xml"),
                         "wf-form4_174628.xml")

    def test_other_xsl_variants_are_also_stripped(self):
        self.assertEqual(f4._raw_doc_name("xslF345X03/edgardoc.xml"), "edgardoc.xml")

    def test_plain_document_name_is_left_alone(self):
        self.assertEqual(f4._raw_doc_name("wf-form4_1746.xml"), "wf-form4_1746.xml")

    def test_missing_document_returns_none_not_exception(self):
        self.assertIsNone(f4._raw_doc_name(None))


class TestTransactionCategorisation(unittest.TestCase):
    """The heart of the $2.76/share fix: discretionary vs non-discretionary."""

    def setUp(self):
        self.parsed = f4._parse_form4(SAMPLE_XML, "0000000000-26-000001", "2026-05-03")
        self.by_code = {t["code"]: t for t in self.parsed["transactions"]}

    def test_open_market_sale_is_discretionary(self):
        self.assertTrue(self.by_code["S"]["discretionary"])

    def test_tax_withholding_is_NOT_discretionary(self):
        """An F (tax withholding on vesting) is not a conviction signal and must never be
        described as an insider 'sale'."""
        self.assertFalse(self.by_code["F"]["discretionary"])

    def test_every_non_discretionary_code_is_classified(self):
        """Grants, exercises, gifts and conversions all carry nominal/strike prices — if any
        of them leaked into the discretionary bucket, a fake 'purchase price' becomes possible."""
        for code in ("A", "M", "F", "X", "G", "C"):
            self.assertIn(code, f4.NON_DISCRETIONARY_CODES)
        for code in ("P", "S"):
            self.assertIn(code, f4.DISCRETIONARY_CODES)

    def test_discretionary_and_non_discretionary_sets_do_not_overlap(self):
        self.assertEqual(f4.DISCRETIONARY_CODES & f4.NON_DISCRETIONARY_CODES, set())

    def test_price_is_the_real_market_price_from_the_filing(self):
        """The original bug in one assertion: same 600 shares, but the price now comes from
        the SEC filing ($1852.30), not from an LLM's paraphrase ($2.76)."""
        self.assertEqual(self.by_code["S"]["price_per_share"], 1852.30)

    def test_value_equals_shares_times_price(self):
        """Arithmetic self-consistency — the exact sanity check that exposed the fake trade."""
        s = self.by_code["S"]
        self.assertAlmostEqual(s["value"], s["shares"] * s["price_per_share"], places=2)

    def test_10b5_1_plan_detected_from_footnote(self):
        """A pre-scheduled sale carries different signal than an opportunistic one."""
        self.assertTrue(self.by_code["S"]["is_10b5_1_plan"])

    def test_owner_and_role_extracted(self):
        self.assertEqual(self.parsed["owner_name"], "Jane Doe")
        self.assertEqual(self.parsed["owner_role"], ["CEO"])

    def test_code_labels_are_human_readable(self):
        self.assertEqual(self.by_code["S"]["code_label"], "open-market/private sale")
        self.assertEqual(self.by_code["F"]["code_label"], "tax withholding on vesting")


class TestRobustness(unittest.TestCase):
    """Malformed input must degrade honestly, never fabricate."""

    def test_malformed_xml_raises_and_is_caught_by_the_caller(self):
        with self.assertRaises(Exception):
            f4._parse_form4("<not-xml", "accn", "2026-01-01")

    def test_missing_price_yields_none_value_not_zero(self):
        """A missing price must not silently become $0 — that would understate a real sale."""
        xml = SAMPLE_XML.replace(
            "<transactionPricePerShare><value>1852.30</value></transactionPricePerShare>",
            "<transactionPricePerShare></transactionPricePerShare>")
        parsed = f4._parse_form4(xml, "accn", "2026-01-01")
        s = next(t for t in parsed["transactions"] if t["code"] == "S")
        self.assertIsNone(s["price_per_share"])
        self.assertIsNone(s["value"])

    def test_unknown_ticker_returns_error_dict_not_exception(self):
        f4_facts = load_microservice_module("edgar_facts")
        f4_facts._CIK_CACHE.clear()
        f4_facts._CIK_CACHE["AAPL"] = "0000320193"   # non-empty -> no network lookup
        try:
            r = f4.edgar_form4(ticker="___NOSUCH___")
            self.assertIsInstance(r, dict)
            self.assertIn("cik", r["_errors"])
        finally:
            f4_facts._CIK_CACHE.clear()


if __name__ == "__main__":
    unittest.main(verbosity=2)
