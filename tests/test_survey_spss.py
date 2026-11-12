import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "survey_spss.py"
CODEBOOK = ROOT / "examples" / "survey_codebook.json"
SAMPLE = ROOT / "examples" / "survey_sample.csv"


class SpssTests(unittest.TestCase):
    def generate(self, source, codebook, output):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(source), "--codebook", str(codebook), "--output", str(output)],
            capture_output=True, encoding="utf-8", check=False,
        )

    def test_generates_ordered_import_and_escaped_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "team's survey.csv"
            source.write_bytes(SAMPLE.read_bytes())
            definitions = json.loads(CODEBOOK.read_text(encoding="utf-8"))
            definitions["satisfaction"]["label"] = "Respondent's rating"
            definitions["satisfaction"]["decimals"] = 2
            codebook = root / "book.json"
            codebook.write_text(json.dumps(dict(reversed(list(definitions.items())))), encoding="utf-8")
            output = root / "import.sps"
            result = self.generate(source, codebook, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            syntax = output.read_text(encoding="utf-8-sig")
            self.assertIn("team''s survey.csv", syntax)
            self.assertIn("response_id A16\n  satisfaction F40.0\n  filed_complaint A8", syntax)
            self.assertIn("FORMATS satisfaction (F40.2).", syntax)
            self.assertIn("VARIABLE LABELS satisfaction 'Respondent''s rating'.", syntax)
            self.assertIn("MISSING VALUES satisfaction (99).", syntax)
            self.assertIn("'Yes' 'Filed a complaint'", syntax)
            self.assertEqual(self.generate(source, codebook, output).returncode, 2)
            self.assertEqual(output.read_text(encoding="utf-8-sig"), syntax)

    def test_rejects_incompatible_csv_without_creating_syntax(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "survey.csv"
            output = root / "import.sps"
            header = "response_id,satisfaction,filed_complaint,complaint_outcome\n"
            for row, expected in (
                ("S001,unknown,No,\n", "dot-decimal"),
                ("S001,3,Yes,\"first\nsecond\"\n", "Multiline"),
                ("S001,3,more than eight bytes,\n", "width"),
            ):
                with self.subTest(row=row):
                    source.write_text(header + row, encoding="utf-8")
                    result = self.generate(source, CODEBOOK, output)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(expected, result.stderr)
                    self.assertFalse(output.exists())
