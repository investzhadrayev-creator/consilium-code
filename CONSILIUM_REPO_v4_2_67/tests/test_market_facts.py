"""
Regression tests for microservice/market_facts.py — the second-source market layer.

The module exists because ALL forward-looking fields hung off one unofficial scraper
(yfinance) that intermittently nulls out on cloud IPs. Tests verify the three promises:
computed-not-ingested ratios, loud divergence between sources, and honest degradation.

All offline: _get_json and edgar internals are monkeypatched; no network.
"""
import time
import unittest

from _support import load_microservice_module

mf = load_microservice_module("market_facts")
ef = load_microservice_module("edgar_facts")


AV_OK = {"Symbol": "TEST", "EPS": "16.70", "ForwardPE": "13.1", "PEGRatio": "1.42",
         "AnalystTargetPrice": "497.4", "TrailingPE": "13.2"}
FINN_OK = [
    {"period": "2026-07-01", "strongBuy": 18, "buy": 22, "hold": 8, "sell": 1, "strongSell": 0},
    {"period": "2026-06-01", "strongBuy": 17, "buy": 21, "hold": 10, "sell": 1, "strongSell": 0},
    {"period": "2026-05-01", "strongBuy": 15, "buy": 20, "hold": 12, "sell": 2, "strongSell": 0},
    {"period": "2026-04-01", "strongBuy": 14, "buy": 19, "hold": 13, "sell": 3, "strongSell": 0},
]


class MarketFactsBase(unittest.TestCase):
    def setUp(self):
        self._orig_get = mf._get_json
        self._orig_tiingo = mf.tiingo_last_price
        ef._FACTS_CACHE.clear()
        ef._CONCEPT_CACHE.clear()
        ef._CIK_CACHE.clear()

    def tearDown(self):
        mf._get_json = self._orig_get
        mf.tiingo_last_price = self._orig_tiingo
        ef._CIK_CACHE.clear()

    def mock_http(self, av=None, finn=None):
        def fake(url, timeout=15):
            if "alphavantage" in url:
                if av is None:
                    raise ValueError("AV down")
                return av
            if "finnhub" in url:
                if finn is None:
                    raise ValueError("finnhub down")
                return finn
            raise ValueError("unexpected url in test: " + url)
        mf._get_json = fake


class TestAlphaVantageLeg(MarketFactsBase):

    def test_overview_fields_coerced_from_strings(self):
        """AV returns everything as strings ('None', '13.1') — coercion must be honest."""
        self.mock_http(av=AV_OK)
        r = mf.market_facts("TEST", av_key="k", price=220.78)
        av = r["alpha_vantage"]
        self.assertEqual(av["eps_ttm"], 16.70)
        self.assertEqual(av["forward_pe_reported"], 13.1)
        self.assertEqual(av["analyst_target"], 497.4)

    def test_av_none_strings_become_none(self):
        av = dict(AV_OK, PEGRatio="None", AnalystTargetPrice="-")
        self.mock_http(av=av)
        r = mf.market_facts("TEST", av_key="k", price=220.78)
        self.assertIsNone(r["alpha_vantage"]["peg_reported"])
        self.assertIsNone(r["alpha_vantage"]["analyst_target"])

    def test_fwd_pe_is_COMPUTED_from_price_and_consensus(self):
        """The module's core promise: our arithmetic, not an ingested ratio.
        220.78 / (16.70 x 1.10) = 12.02."""
        self.mock_http(av=AV_OK)
        r = mf.market_facts("TEST", av_key="k", price=220.78,
                            yahoo={"eps_growth_1y": 0.10})
        self.assertAlmostEqual(r["fwd_pe_computed"], 12.02, places=2)
        self.assertIn("price / (AV eps_ttm", r["fwd_pe_computed_basis"])

    def test_no_growth_estimate_falls_back_to_reported_with_label(self):
        self.mock_http(av=AV_OK)
        r = mf.market_facts("TEST", av_key="k", price=220.78, yahoo={})
        self.assertEqual(r["fwd_pe_computed"], 13.1)
        self.assertIn("reported", r["fwd_pe_computed_basis"])

    def test_B1_reported_pe_survives_missing_eps_AND_blocked_yahoo(self):
        """v4.2.22 (B1). The [UNVERIFIED] fwd_pe defect, pinned at its root. AV returned an
        official ForwardPE but NO usable EPS, and Yahoo was rate-limited on the cloud IP (no
        growth number). Before the fix, forward_pe_reported was locked behind `if av.eps_ttm`
        AND the growth-based computation, so the one IP-independent official figure — sitting
        right there in the response — was never read, and the report printed [UNVERIFIED].
        Three AV-key swaps could not fix this because the key was never the cause."""
        av_no_eps = {"Symbol": "TEST", "ForwardPE": "27.5"}   # official PE present, EPS absent
        self.mock_http(av=av_no_eps)
        r = mf.market_facts("TEST", av_key="k", price=220.78, yahoo={})   # yahoo blocked -> {}
        self.assertEqual(r["fwd_pe_computed"], 27.5,
                         "AV ForwardPE must be reachable without eps_ttm or a Yahoo growth number")
        self.assertIn("official second source", r["fwd_pe_computed_basis"])

    def test_B1_computed_still_preferred_when_inputs_present(self):
        """The fix frees the reported fallback WITHOUT demoting the computed path: when we can
        compute our own ratio, we still do (explainable > ingested). Priority order preserved."""
        self.mock_http(av=AV_OK)
        r = mf.market_facts("TEST", av_key="k", price=220.78, yahoo={"eps_growth_1y": 0.10})
        self.assertAlmostEqual(r["fwd_pe_computed"], 12.02, places=2)
        self.assertIn("price / (AV eps_ttm", r["fwd_pe_computed_basis"])

    def test_rate_limited_av_degrades_with_error_not_crash(self):
        self.mock_http(av={"Note": "API call frequency limit"})
        r = mf.market_facts("TEST", av_key="k", price=220.78)
        self.assertNotIn("alpha_vantage", r)
        self.assertIn("alpha_vantage", r["_errors"])


class TestQuorum(MarketFactsBase):

    def test_divergent_sources_are_flagged_loudly(self):
        """Yahoo says fwd_pe 20, AV says 13.1 — a 52% disagreement must not pass quietly."""
        self.mock_http(av=AV_OK)
        r = mf.market_facts("TEST", av_key="k", price=220.78,
                            yahoo={"fwd_pe": 20.0, "peg": 1.45, "price_target_mean": 500.0})
        self.assertIn("fwd_pe", r["_divergence"])
        self.assertGreater(r["_divergence"]["fwd_pe"]["rel_diff_pct"], 40)

    def test_agreeing_sources_stay_quiet(self):
        self.mock_http(av=AV_OK)
        r = mf.market_facts("TEST", av_key="k", price=220.78,
                            yahoo={"fwd_pe": 13.0, "peg": 1.40, "price_target_mean": 497.0})
        self.assertNotIn("_divergence", r)

    def test_one_sided_field_makes_no_divergence_claim(self):
        self.mock_http(av=AV_OK)
        r = mf.market_facts("TEST", av_key="k", price=220.78, yahoo={"fwd_pe": None})
        self.assertNotIn("_divergence", r)


class TestRecTrends(MarketFactsBase):

    def test_buy_share_and_3m_delta(self):
        """Buy-share latest = (18+22)/49 = .816; oldest = (14+19)/49 = .673; delta +.143 —
        analysts getting MORE positive: a real revision-breadth signal."""
        self.mock_http(av=AV_OK, finn=FINN_OK)
        r = mf.market_facts("TEST", av_key="k", finnhub_key="f", price=220.78)
        rec = r["rec_trends"]
        self.assertAlmostEqual(rec["buy_share_latest"], 0.816, places=3)
        self.assertAlmostEqual(rec["buy_share_delta_3m"], 0.143, places=3)

    def test_empty_rec_feed_degrades(self):
        self.mock_http(av=AV_OK, finn=[])
        r = mf.market_facts("TEST", av_key="k", finnhub_key="f", price=220.78)
        self.assertNotIn("rec_trends", r)
        self.assertIn("finnhub_rec", r["_errors"])


class TestInHousePeerPE(MarketFactsBase):

    def _mock_peer_edgar(self, ticker, ni, sh):
        ef._CIK_CACHE[ticker] = "%010d" % (abs(hash(ticker)) % 10000)
        cik = ef._CIK_CACHE[ticker]
        ef._FACTS_CACHE[cik] = (time.time(), {"facts": {"us-gaap": {
            "NetIncomeLoss": {"units": {"USD": [
                {"start": "2025-01-01", "end": "2025-12-31", "val": ni,
                 "form": "10-K", "accn": "a", "filed": "2026-02-01"}]}},
            "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [
                {"start": "2025-01-01", "end": "2025-12-31", "val": sh,
                 "form": "10-K", "accn": "a", "filed": "2026-02-01"}]}},
        }}})
        for tax, tag in ef.SHARES_CURRENT:
            ef._CONCEPT_CACHE[(cik, tax, tag)] = (time.time(), None)

    def test_peer_pe_computed_from_edgar_eps_and_tiingo_price(self):
        """CRM: NI $6.2B / 980M sh = EPS $6.327; price $284 -> P/E 44.89. Two primary
        sources, our arithmetic — Yahoo is not in this path at all."""
        self.mock_http(av=AV_OK)
        self._mock_peer_edgar("CRM", 6.2e9, 0.98e9)
        mf.tiingo_last_price = lambda t, tok, err: 284.0
        r = mf.market_facts("TEST", peers=["CRM"], av_key="k", tiingo_token="t", price=220.78)
        peer = r["peer_pe_inhouse"]["rows"][0]
        self.assertAlmostEqual(peer["eps_fy"], 6.327, places=3)
        self.assertAlmostEqual(peer["pe_trailing"], 44.89, places=1)
        self.assertIn("TRAILING", r["peer_pe_inhouse"]["basis"])

    def test_loss_making_peer_gets_no_pe(self):
        """Negative EPS -> P/E is meaningless; the row must carry no ratio, not a negative one."""
        self.mock_http(av=AV_OK)
        self._mock_peer_edgar("LOSS", -1.5e9, 1.0e9)
        mf.tiingo_last_price = lambda t, tok, err: 50.0
        r = mf.market_facts("TEST", peers=["LOSS"], av_key="k", tiingo_token="t", price=100)
        self.assertNotIn("pe_trailing", r["peer_pe_inhouse"]["rows"][0])
        self.assertIsNone(r["peer_pe_inhouse"]["peer_median_pe_trailing"])

    def test_median_over_priced_peers(self):
        self.mock_http(av=AV_OK)
        for t, ni, sh, px in [("P1", 5e9, 1e9, 100.0), ("P2", 2e9, 1e9, 80.0),
                              ("P3", 4e9, 1e9, 120.0)]:
            self._mock_peer_edgar(t, ni, sh)
        prices = {"P1": 100.0, "P2": 80.0, "P3": 120.0}
        mf.tiingo_last_price = lambda t, tok, err: prices[t]
        r = mf.market_facts("TEST", peers=["P1", "P2", "P3"], av_key="k",
                            tiingo_token="t", price=100)
        # P/Es: 20, 40, 30 -> sorted [20,30,40] -> median 30
        self.assertEqual(r["peer_pe_inhouse"]["peer_median_pe_trailing"], 30.0)
        self.assertEqual(r["peer_pe_inhouse"]["n_priced"], 3)


class TestFinraShortInterestLeg(MarketFactsBase):
    """v4.0: short interest from the primary source, and percent-of-shares computed here."""

    def mock_finra(self, payload):
        mf.finra_short_interest = lambda t, cid, sec, err=None: payload

    def setUp(self):
        super().setUp()
        self._orig_finra = mf.finra_short_interest

    def tearDown(self):
        super().tearDown()
        mf.finra_short_interest = self._orig_finra

    def test_short_interest_included_when_credentials_present(self):
        self.mock_http(av=AV_OK)
        self.mock_finra({"settlement_date": "2026-07-15", "short_shares": 10500000,
                         "days_to_cover": 3.0})
        r = mf.market_facts("ADBE", av_key="k", price=220.78,
                            finra_client_id="cid", finra_client_secret="sec")
        self.assertEqual(r["short_interest"]["settlement_date"], "2026-07-15")
        self.assertIn("finra", r["_sources_used"])

    def test_percent_computed_from_finra_shares_and_edgar_count(self):
        """10.5M short / 397M shares = 2.64%. Both inputs are primary-source; the ratio is
        ours."""
        self.mock_http(av=AV_OK)
        self.mock_finra({"settlement_date": "2026-07-15", "short_shares": 10500000})
        r = mf.market_facts("ADBE", av_key="k", price=220.78,
                            finra_client_id="cid", finra_client_secret="sec",
                            shares_outstanding=397000000)
        si = r["short_interest"]
        self.assertAlmostEqual(si["short_pct_shares_outstanding"], 2.64, places=2)

    def test_percent_basis_is_labelled_shares_not_float(self):
        """EDGAR gives shares OUTSTANDING; Yahoo's short_pct_float uses FLOAT. Comparing them
        silently would understate ours — the label must travel with the number."""
        self.mock_http(av=AV_OK)
        self.mock_finra({"settlement_date": "2026-07-15", "short_shares": 10500000})
        r = mf.market_facts("ADBE", av_key="k", price=220.78,
                            finra_client_id="cid", finra_client_secret="sec",
                            shares_outstanding=397000000)
        self.assertIn("not float", r["short_interest"]["_pct_basis"])

    def test_no_share_count_means_no_percent_claim(self):
        self.mock_http(av=AV_OK)
        self.mock_finra({"settlement_date": "2026-07-15", "short_shares": 10500000})
        r = mf.market_facts("ADBE", av_key="k", price=220.78,
                            finra_client_id="cid", finra_client_secret="sec")
        self.assertNotIn("short_pct_shares_outstanding", r["short_interest"])

    def test_no_credentials_skips_the_leg_entirely(self):
        self.mock_http(av=AV_OK)
        r = mf.market_facts("ADBE", av_key="k", price=220.78)
        self.assertNotIn("short_interest", r)
        self.assertNotIn("finra", r["_sources_used"])

    def test_finra_failure_degrades_without_breaking_other_legs(self):
        self.mock_http(av=AV_OK)
        self.mock_finra(None)
        r = mf.market_facts("ADBE", av_key="k", price=220.78,
                            finra_client_id="cid", finra_client_secret="sec")
        self.assertNotIn("short_interest", r)
        self.assertIn("alpha_vantage", r)      # unrelated leg still worked


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestErrorSanitization(unittest.TestCase):
    """v4.2.11 SECURITY. Alpha Vantage's rate-limit message quotes the API key back
    ('We have detected your API key as <KEY>...') and on 2026-07-17 that string travelled
    errors -> growth_diag -> the Render Tables reason row -> the shipped NFLX report.
    Every error string leaving market_facts must be redacted."""

    def setUp(self):
        self.mod = load_microservice_module("market_facts")

    def test_known_secret_redacted_verbatim(self):
        errors = {"alpha_vantage": "rate-limited or empty: {'Information': 'We have detected "
                                   "your API key as A263Z7Y0ZBAIK3OC and our standard limit'}"}
        self.mod._sanitize_errors(errors, ["A263Z7Y0ZBAIK3OC"])
        self.assertNotIn("A263Z7Y0ZBAIK3OC", errors["alpha_vantage"])
        self.assertIn("[REDACTED]", errors["alpha_vantage"])

    def test_key_shaped_residue_redacted_even_when_secret_unknown(self):
        """The provider may echo a key we were never passed (rotated, second account). Anything
        key-shaped goes, known or not."""
        errors = {"alpha_vantage": "detected your API key as ZZ93K1M4Q8R7T2B5 today",
                  "tiingo_NFLX": "https://api.tiingo.com/x?token=abcd1234efgh5678 failed"}
        self.mod._sanitize_errors(errors, [])
        self.assertNotIn("ZZ93K1M4Q8R7T2B5", errors["alpha_vantage"])
        self.assertNotIn("abcd1234efgh5678", errors["tiingo_NFLX"])
        self.assertIn("token=[REDACTED]", errors["tiingo_NFLX"])

    def test_ordinary_error_text_survives_untouched(self):
        """Redaction must not eat the diagnostic value: short words, status codes and hosts
        stay readable — the WHY is the whole point of carrying the error."""
        errors = {"finnhub_rec": "empty", "alpha_vantage": "HTTP 429 too many requests"}
        self.mod._sanitize_errors(errors, ["SOMEKEY123456789"])
        self.assertEqual(errors["finnhub_rec"], "empty")
        self.assertEqual(errors["alpha_vantage"], "HTTP 429 too many requests")

    def test_non_string_values_pass_through(self):
        errors = {"weird": {"nested": 1}, "n": None}
        self.mod._sanitize_errors(errors, ["K"])
        self.assertEqual(errors["weird"], {"nested": 1})
