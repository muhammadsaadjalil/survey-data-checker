import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "survey_check.py"
RULES = ROOT / "examples" / "survey_rules.json"


class SurveyCheckTests(unittest.TestCase):
    def run_check(self, csv_file, rules=RULES, *, summary=False):
        command = [sys.executable, str(SCRIPT), str(csv_file), "--rules", str(rules)]
        if summary:
            command.append("--summary")
        return subprocess.run(
            command,
            capture_output=True, encoding="utf-8", check=False,
        )

    def test_sample_flags_all_four_checks_without_changing_input(self):
        sample = ROOT / "examples" / "survey_sample.csv"
        original = sample.read_bytes()
        result = self.run_check(sample)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual((report["rows_checked"], report["rows_flagged"]), (4, 2))
        self.assertEqual([row["line"] for row in report["flagged_rows"]], [3, 4])
        self.assertEqual(
            [[flag["check"] for flag in row["flags"]] for row in report["flagged_rows"]],
            [["integer_range", "skip_logic"], ["required", "possible_duplicate"]],
        )
        self.assertEqual(report["flagged_rows"][1]["flags"][1]["first_line"], 2)
        self.assertNotIn("S001", result.stdout)
        self.assertEqual(sample.read_bytes(), original)

    def test_clean_utf8_bom_and_multiline_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "clean.csv"
            sample.write_bytes(
                '\ufeffresponse_id,satisfaction,filed_complaint,complaint_outcome\r\n'
                'S001,5,Yes,"Résolu\r\nConfirmed"\r\n'.encode("utf-8")
            )
            result = self.run_check(sample)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"rows_checked": 1, "rows_flagged": 0, "flagged_rows": []})

    def test_missing_configured_columns_returns_error_without_report(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "bad.csv"
            sample.write_text("response_id\nS001\n", encoding="utf-8")
            result = self.run_check(sample)
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing configured columns", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_conditional_required_allowed_values_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "survey.csv"
            sample.write_text(
                "response_id,satisfaction,filed_complaint,complaint_outcome\n"
                "S001,4, YES ,\nS002,3,Maybe,\nS003,5,no,\n",
                encoding="utf-8",
            )
            result = self.run_check(sample, summary=True)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["rows_flagged"], 2)
        self.assertEqual(report["summary"]["flags_by_check"], {"required_when": 1, "allowed_values": 1})
        self.assertEqual(
            report["summary"]["missing_by_column"]["complaint_outcome"],
            {"missing": 3, "answered": 0, "missing_percent": 100.0},
        )
        self.assertNotIn("Maybe", result.stdout)

    def test_existing_rules_still_work(self):
        with tempfile.TemporaryDirectory() as directory:
            rules = Path(directory) / "rules.json"
            rules.write_text('{"required": ["response_id"]}', encoding="utf-8")
            result = self.run_check(ROOT / "examples" / "survey_sample.csv", rules)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"rows_checked": 4, "rows_flagged": 0, "flagged_rows": []})
