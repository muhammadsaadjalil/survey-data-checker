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
    def run_check(self, csv_file, rules=RULES):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(csv_file), "--rules", str(rules)],
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
