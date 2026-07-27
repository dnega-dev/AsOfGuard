import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from asof_guard.cli import main


class CliTests(unittest.TestCase):
    def run_cli(self, argv, stdin_text=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        input_stream = io.StringIO(stdin_text or "")
        with patch("sys.stdin", input_stream), redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_clean_fixture_exit_zero_and_json(self):
        code, stdout, stderr = self.run_cli(
            ["verify", "--fixture", "clean_historical", "--format", "json"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout)["status"], "clean")

    def test_contaminated_fixture_exit_two(self):
        code, stdout, _ = self.run_cli(["verify", "--fixture", "post_cutoff_retrieval"])
        self.assertEqual(code, 2)
        self.assertIn("CONTAMINATED", stdout)

    def test_metadata_gap_exit_three(self):
        code, stdout, _ = self.run_cli(["verify", "--fixture", "missing_artifact_timestamp"])
        self.assertEqual(code, 3)
        self.assertIn("INDETERMINATE", stdout)

    def test_stdin_jsonl(self):
        payload = "\n".join(
            [
                '{"type":"query","id":"q","as_of":"2020-01-01T00:00:00Z"}',
                '{"type":"model_knowledge","model":"m","knowledge_cutoff":"2019-01-01T00:00:00Z"}',
            ]
        )
        code, stdout, _ = self.run_cli(["verify", "-", "--format", "json"], payload)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["trace_id"], "<stdin>")

    def test_unknown_fixture_is_input_error(self):
        code, _, stderr = self.run_cli(["verify", "--fixture", "does_not_exist"])
        self.assertEqual(code, 4)
        self.assertIn("unknown fixture", stderr)

    def test_verify_requires_exactly_one_input(self):
        code, _, stderr = self.run_cli(["verify"])
        self.assertEqual(code, 4)
        self.assertIn("exactly one", stderr)
        code, _, stderr = self.run_cli(["verify", "trace.jsonl", "--fixture", "clean_historical"])
        self.assertEqual(code, 4)
        self.assertIn("exactly one", stderr)

    def test_fixtures_list_text_and_json(self):
        code, stdout, _ = self.run_cli(["fixtures", "list"])
        self.assertEqual(code, 0)
        self.assertIn("clean_historical", stdout)
        self.assertIn("fixture(s)", stdout)
        code, stdout, _ = self.run_cli(["fixtures", "list", "--format", "json"])
        self.assertEqual(code, 0)
        entries = json.loads(stdout)
        self.assertGreaterEqual(len(entries), 21)

    def test_fixtures_show_prints_jsonl(self):
        code, stdout, stderr = self.run_cli(["fixtures", "show", "clean_historical"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        first = json.loads(stdout.splitlines()[0])
        self.assertEqual(first["type"], "trace")

    def test_explain_one_rule_and_all_json(self):
        code, stdout, _ = self.run_cli(["explain", "expired_document"])
        self.assertEqual(code, 0)
        self.assertIn("EXPIRED_DOCUMENT", stdout)
        self.assertIn("Remediation:", stdout)
        code, stdout, _ = self.run_cli(["explain", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn("POST_CUTOFF_RETRIEVAL", json.loads(stdout))

    def test_unknown_explanation_is_input_error(self):
        code, _, stderr = self.run_cli(["explain", "NOT_A_RULE"])
        self.assertEqual(code, 4)
        self.assertIn("unknown rule code", stderr)

    def test_argparse_errors_return_without_raising(self):
        code, _, stderr = self.run_cli(["not-a-command"])
        self.assertEqual(code, 4)
        self.assertIn("invalid choice", stderr)

    def test_output_file_is_written(self):
        output = Path(__file__).with_name("_cli_output.json")
        try:
            code, stdout, stderr = self.run_cli(
                [
                    "verify",
                    "--fixture",
                    "clean_historical",
                    "--format",
                    "json",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(stdout, "")
            self.assertEqual(stderr, "")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "clean")
        finally:
            output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
