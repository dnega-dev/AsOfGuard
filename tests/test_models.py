import unittest
from datetime import datetime, timedelta, timezone

from asof_guard.fixture_library import load_fixture
from asof_guard.models import TraceFormatError, format_timestamp, parse_timestamp
from asof_guard.verifier import verify_trace


class ModelTests(unittest.TestCase):
    def test_timestamp_round_trip_uses_canonical_utc(self):
        parsed = parse_timestamp("2020-01-01T05:30:00+05:30", "time")
        self.assertEqual(format_timestamp(parsed), "2020-01-01T00:00:00Z")

    def test_timestamp_accepts_fractional_seconds(self):
        parsed = parse_timestamp("2020-01-01T00:00:00.123456Z", "time")
        self.assertEqual(format_timestamp(parsed), "2020-01-01T00:00:00.123456Z")

    def test_timestamp_rejects_non_string(self):
        with self.assertRaisesRegex(TraceFormatError, "ISO-8601 string"):
            parse_timestamp(123, "time")

    def test_verdict_exit_codes(self):
        self.assertEqual(verify_trace(load_fixture("clean_historical")).exit_code, 0)
        self.assertEqual(verify_trace(load_fixture("post_cutoff_retrieval")).exit_code, 2)
        self.assertEqual(verify_trace(load_fixture("missing_retrieval_timestamp")).exit_code, 3)

    def test_to_dict_findings_are_json_compatible_values(self):
        payload = verify_trace(load_fixture("multiple_contaminants")).to_dict()
        self.assertIsInstance(payload["findings"], list)
        self.assertTrue(all(isinstance(finding["timestamp"], (str, type(None))) for finding in payload["findings"]))


if __name__ == "__main__":
    unittest.main()
