import json
import unittest
import xml.etree.ElementTree as ET

from asof_guard.fixture_library import load_fixture
from asof_guard.reporting import render_json, render_junit, render_sarif, render_text, render_verdict
from asof_guard.verifier import verify_trace


class ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean = verify_trace(load_fixture("clean_historical"))
        cls.bad = verify_trace(load_fixture("multiple_contaminants"))

    def test_text_distinguishes_observable_failure_and_weight_uncertainty(self):
        text = render_text(self.bad)
        self.assertIn("Observable trace integrity: FAILED", text)
        self.assertIn("Model-weight purity: UNVERIFIABLE", text)
        self.assertIn("Earliest invalid timestamp: 2017-01-01T00:00:00Z", text)
        self.assertIn("artifact:a1", text)
        self.assertIn("document:d1", text)

    def test_clean_text_does_not_claim_weight_purity(self):
        text = render_text(self.clean)
        self.assertIn("NO OBSERVABLE FAILURE FOUND", text)
        self.assertIn("UNVERIFIABLE", text)
        self.assertNotIn("Model-weight purity: VERIFIED", text)

    def test_model_boundary_risk_does_not_masquerade_as_observable_failure(self):
        risk = verify_trace(load_fixture("model_knowledge_after_cutoff"))
        report = json.loads(render_json(risk))
        self.assertEqual(report["status"], "indeterminate")
        self.assertEqual(report["observable_temporal_integrity"], "passed")
        self.assertEqual(report["model_weight_purity"], "unverifiable")

    def test_json_is_valid_and_contains_exact_items(self):
        report = json.loads(render_json(self.bad))
        self.assertEqual(report["status"], "contaminated")
        self.assertEqual(report["observable_temporal_integrity"], "failed")
        self.assertEqual(report["model_weight_purity"], "unverifiable")
        self.assertEqual(report["earliest_invalid_timestamp"], "2017-01-01T00:00:00Z")
        items = {(item["type"], item["id"]) for item in report["contaminating_items"]}
        self.assertIn(("memory", "m1"), items)

    def test_junit_is_well_formed_and_classifies_findings(self):
        root = ET.fromstring(render_junit(self.bad))
        self.assertEqual(root.tag, "testsuite")
        self.assertGreater(int(root.attrib["failures"]), 0)
        self.assertEqual(int(root.attrib["errors"]), len(self.bad.metadata_gaps))
        failures = root.findall(".//failure")
        skipped = root.findall(".//skipped")
        self.assertEqual(len(failures), len(self.bad.observable_failures))
        self.assertEqual(len(skipped), len(self.bad.uncertainties))

    def test_junit_escapes_trace_controlled_text(self):
        # The fixture output contains normal text; well-formed parsing is the key
        # invariant because ElementTree escapes message attributes and bodies.
        ET.fromstring(render_junit(self.clean))

    def test_sarif_is_valid_21_and_has_rules(self):
        report = json.loads(render_sarif(self.bad))
        self.assertEqual(report["version"], "2.1.0")
        run = report["runs"][0]
        self.assertEqual(run["tool"]["driver"]["name"], "AsOfGuard")
        rule_ids = {rule["id"] for rule in run["tool"]["driver"]["rules"]}
        result_ids = {result["ruleId"] for result in run["results"]}
        self.assertEqual(rule_ids, result_ids)
        self.assertTrue(any(result["level"] == "error" for result in run["results"]))
        self.assertEqual(run["properties"]["modelWeightPurity"], "unverifiable")

    def test_dispatch_rejects_unknown_format(self):
        with self.assertRaisesRegex(ValueError, "unsupported output format"):
            render_verdict(self.clean, "yaml")


if __name__ == "__main__":
    unittest.main()
