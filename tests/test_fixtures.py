import unittest

from asof_guard.fixture_library import fixture_catalog, fixture_names, fixture_text, load_fixture
from asof_guard.verifier import verify_trace


class FixtureLibraryTests(unittest.TestCase):
    def test_at_least_twenty_adversarial_plus_clean_fixture(self):
        names = fixture_names()
        self.assertGreaterEqual(len(names), 21)
        self.assertIn("clean_historical", names)
        adversarial = [name for name in names if name != "clean_historical"]
        self.assertGreaterEqual(len(adversarial), 20)

    def test_every_fixture_meets_header_expectations(self):
        for entry in fixture_catalog():
            with self.subTest(fixture=entry["name"]):
                verdict = verify_trace(load_fixture(entry["name"]))
                self.assertEqual(verdict.status.value, entry["expected_status"])
                actual_codes = {finding.code for finding in verdict.findings}
                self.assertTrue(
                    set(entry["expected_codes"]).issubset(actual_codes),
                    f"missing expected codes for {entry['name']}: "
                    f"{set(entry['expected_codes']) - actual_codes}",
                )
                self.assertTrue(entry["description"])

    def test_catalog_is_sorted_and_complete(self):
        catalog = fixture_catalog()
        catalog_names = [entry["name"] for entry in catalog]
        self.assertEqual(catalog_names, sorted(catalog_names))
        self.assertEqual(catalog_names, fixture_names())

    def test_fixture_name_rejects_path_traversal(self):
        for name in ("../clean_historical", "a/b", "a\\b", ".."):
            with self.subTest(name=name), self.assertRaises(KeyError):
                fixture_text(name)

    def test_jsonl_suffix_is_optional(self):
        self.assertEqual(
            fixture_text("clean_historical"),
            fixture_text("clean_historical.jsonl"),
        )


if __name__ == "__main__":
    unittest.main()
