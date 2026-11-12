import csv
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
    def run_check(self, csv_file, rules=RULES, *, summary=False, review_csv=None):
        command = [sys.executable, str(SCRIPT), str(csv_file), "--rules", str(rules)]
        if summary:
            command.append("--summary")
        if review_csv is not None:
            command.extend(("--review-csv", str(review_csv)))
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

    def test_review_csv_exports_each_flag_with_context(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review.csv"
            result = self.run_check(ROOT / "examples" / "survey_sample.csv", review_csv=output)
            self.assertEqual(result.returncode, 1, result.stderr)
            with output.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual([row["csv_line"] for row in rows], ["3", "3", "4", "4"])
        self.assertEqual([row["check"] for row in rows], ["integer_range", "skip_logic", "required", "possible_duplicate"])
        self.assertEqual((rows[0]["min"], rows[0]["max"]), ("1", "5"))
        self.assertEqual(rows[1]["when_column"], "filed_complaint")
        self.assertEqual(rows[3]["first_matching_line"], "2")
        self.assertNotIn("S001", repr(rows))

    def test_review_csv_protects_existing_files_and_spreadsheet_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample = root / "survey.csv"
            original = "=header,answer\n,\n"
            sample.write_bytes(original.encode("utf-8"))
            rules = root / "rules.json"
            rules.write_text('{"required": ["=header"]}', encoding="utf-8")
            result = self.run_check(sample, rules, review_csv=sample)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(sample.read_bytes(), original.encode("utf-8"))
            output = root / "review.csv"
            result = self.run_check(sample, rules, review_csv=output)
            self.assertEqual(result.returncode, 1, result.stderr)
            with output.open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(next(csv.DictReader(stream))["column"], "'=header")
