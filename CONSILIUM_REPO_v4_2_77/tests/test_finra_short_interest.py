"""
Regression tests for microservice/finra_short_interest.py.

Short interest ORIGINATES at FINRA (broker-dealers report biweekly); Yahoo and every
aggregator republish it. These tests pin the two things that broke elsewhere in this
pipeline before: an auth flow guessed rather than read from docs (cf. the Form 4 XSL bug),
and a field name assumed rather than verified.

All offline — _post_json is monkeypatched; no network, no credentials.
"""
import time
import unittest

from _support import load_microservice_module

fsi = load_microservice_module("finra_short_interest")


TOKEN_OK = {"access_token": "tok-abc", "scope": "any", "token_type": "Bearer",
            "expires_in": "43170"}

# Shape copied from the dataset's documented sample response.
ROWS_OK = [
    {"symbolCode": "ADBE", "settlementDate": "2026-06-30", "marketClassCode": "NMS",
     "currentShortPositionQuantity": 9000000, "previousShortPositionQuantity": 8000000,
     "changePercent": 12.5, "averageDailyVolumeQuantity": 3000000,
     "daysToCoverQuantity": 3.0, "revisionFlag": None, "stockSplitFlag": None},
    {"symbolCode": "ADBE", "settlementDate": "2026-07-15", "marketClassCode": "NMS",
     "currentShortPositionQuantity": 10500000, "previousShortPositionQuantity": 9000000,
     "changePercent": 16.67, "averageDailyVolumeQuantity": 3500000,
     "daysToCoverQuantity": 3.0, "revisionFlag": None, "stockSplitFlag": None},
    {"symbolCode": "ADBE", "settlementDate": "2026-06-15", "marketClassCode": "NMS",
     "currentShortPositionQuantity": 8000000, "previousShortPositionQuantity": 7800000,
     "changePercent": 2.56, "averageDailyVolumeQuantity": 2900000,
     "daysToCoverQuantity": 2.76, "revisionFlag": None, "stockSplitFlag": None},
]


class FinraBase(unittest.TestCase):
    def setUp(self):
        self._orig = fsi._post_json
        fsi._TOKEN_CACHE.update({"token": None, "exp": 0.0, "cid": None})
        self.calls = []

    def tearDown(self):
        fsi._post_json = self._orig
        fsi._TOKEN_CACHE.update({"token": None, "exp": 0.0, "cid": None})

    def mock(self, token=TOKEN_OK, rows=None, token_exc=None, data_exc=None):
        rows = ROWS_OK if rows is None else rows

        def fake(url, headers, body=None, timeout=20):
            self.calls.append({"url": url, "headers": headers, "body": body})
            if "oauth2/access_token" in url:
                if token_exc:
                    raise token_exc
                return token
            if data_exc:
                raise data_exc
            return rows
        fsi._post_json = fake


class TestOAuthFlow(FinraBase):
    """The auth flow is read from the docs, not guessed — these assertions pin it."""

    def test_token_request_uses_basic_auth_with_client_credentials_grant(self):
        self.mock()
        fsi.finra_short_interest("ADBE", "cid", "secret")
        tok_call = self.calls[0]
        self.assertIn("grant_type=client_credentials", tok_call["url"])
        self.assertTrue(tok_call["headers"]["Authorization"].startswith("Basic "))

    def test_basic_token_is_base64_of_id_colon_secret(self):
        """The colon is required INSIDE the string before encoding."""
        import base64
        self.mock()
        fsi.finra_short_interest("ADBE", "cid", "secret")
        b64 = self.calls[0]["headers"]["Authorization"].split(" ", 1)[1]
        self.assertEqual(base64.b64decode(b64).decode(), "cid:secret")

    def test_data_request_uses_bearer_not_basic(self):
        """Docs are explicit: the access_token is a BEARER token on data calls, not Basic."""
        self.mock()
        fsi.finra_short_interest("ADBE", "cid", "secret")
        data_call = self.calls[1]
        self.assertEqual(data_call["headers"]["Authorization"], "Bearer tok-abc")

    def test_token_is_cached_across_calls(self):
        """Docs recommend caching ~30 min; re-authenticating per request wastes the quota."""
        self.mock()
        fsi.finra_short_interest("ADBE", "cid", "secret")
        fsi.finra_short_interest("CRM", "cid", "secret")
        token_calls = [c for c in self.calls if "access_token" in c["url"]]
        self.assertEqual(len(token_calls), 1)

    def test_expired_token_is_refetched(self):
        self.mock()
        fsi.finra_short_interest("ADBE", "cid", "secret")
        fsi._TOKEN_CACHE["exp"] = time.time() - 1      # force expiry
        fsi.finra_short_interest("ADBE", "cid", "secret")
        token_calls = [c for c in self.calls if "access_token" in c["url"]]
        self.assertEqual(len(token_calls), 2)

    def test_token_failure_degrades_to_none_with_reason(self):
        self.mock(token_exc=ValueError("401 Unauthorized"))
        errs = {}
        r = fsi.finra_short_interest("ADBE", "cid", "bad", errs)
        self.assertIsNone(r)
        self.assertIn("finra_token", errs)

    def test_missing_credentials_makes_no_network_call(self):
        self.mock()
        errs = {}
        self.assertIsNone(fsi.finra_short_interest("ADBE", None, None, errs))
        self.assertEqual(self.calls, [])
        self.assertIn("finra_short", errs)


class TestDataQuery(FinraBase):

    def test_filter_uses_symbolCode_field(self):
        """consolidatedShortInterest uses symbolCode; issueSymbolIdentifier belongs to the
        legacy EquityShortInterest dataset. Guessing this wrong returns an empty result that
        looks exactly like 'no short interest'."""
        self.mock()
        fsi.finra_short_interest("ADBE", "cid", "secret")
        cf = self.calls[1]["body"]["compareFilters"][0]
        self.assertEqual(cf["fieldName"], "symbolCode")
        self.assertEqual(cf["fieldValue"], "ADBE")
        self.assertEqual(cf["compareType"], "EQUAL")

    def test_json_accept_header_requested(self):
        self.mock()
        fsi.finra_short_interest("ADBE", "cid", "secret")
        self.assertEqual(self.calls[1]["headers"]["Accept"], "application/json")

    def test_latest_settlement_row_selected_regardless_of_api_order(self):
        """Rows arrive unsorted (server-side sortFields needs partition filters we don't
        send). Same class of bug as the yfinance upgrades ordering: 'recent' must mean
        recent."""
        self.mock()
        r = fsi.finra_short_interest("ADBE", "cid", "secret")
        self.assertEqual(r["settlement_date"], "2026-07-15")
        self.assertEqual(r["short_shares"], 10500000)

    def test_fields_carried_verbatim_from_finra(self):
        self.mock()
        r = fsi.finra_short_interest("ADBE", "cid", "secret")
        self.assertEqual(r["days_to_cover"], 3.0)
        self.assertEqual(r["avg_daily_volume"], 3500000)
        self.assertEqual(r["change_pct_biweekly"], 16.67)

    def test_history_is_newest_first(self):
        self.mock()
        r = fsi.finra_short_interest("ADBE", "cid", "secret")
        self.assertEqual([h["settlement_date"] for h in r["history"]],
                         ["2026-07-15", "2026-06-30", "2026-06-15"])

    def test_change_pct_derived_when_absent(self):
        """FINRA usually supplies changePercent; if it doesn't, derive rather than drop —
        but only from two real reported quantities."""
        rows = [dict(ROWS_OK[1])]
        rows[0].pop("changePercent")
        self.mock(rows=rows)
        r = fsi.finra_short_interest("ADBE", "cid", "secret")
        self.assertAlmostEqual(r["change_pct_biweekly"], 16.67, places=2)

    def test_empty_result_is_honest_none(self):
        self.mock(rows=[])
        errs = {}
        self.assertIsNone(fsi.finra_short_interest("NOSUCH", "cid", "secret", errs))
        self.assertIn("finra_short", errs)

    def test_data_error_degrades_without_throwing(self):
        self.mock(data_exc=ValueError("503 Service Unavailable"))
        errs = {}
        self.assertIsNone(fsi.finra_short_interest("ADBE", "cid", "secret", errs))
        self.assertIn("finra_short", errs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
