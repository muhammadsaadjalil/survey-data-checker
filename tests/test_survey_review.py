import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "survey_review.py"
RULES = ROOT / "examples" / "survey_rules.json"


class SurveyReviewTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.source = self.root / "source.csv"
        self.source.write_bytes((ROOT / "examples" / "survey_sample.csv").read_bytes())
        self.decisions = self.root / "decisions.csv"
        self.output = self.root / "reviewed.csv"
        self.log = self.root / "log.json"

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, encoding="utf-8")

    def prepare(self):
        return self.run_cli("prepare", self.source, "--rules", RULES, "--output", self.decisions)

    def apply_decisions(self):
        return self.run_cli("apply", self.source, "--decisions", self.decisions, "--output", self.output, "--log", self.log)

    def write_decisions(self, *decisions):
        with self.decisions.open(encoding="utf-8-sig", newline="") as stream:
            headers = next(csv.reader(stream))
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.decisions.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows((digest, *decision) for decision in decisions)

    def test_prepares_and_applies_corrections_exclusion_and_keep(self):
        original = self.source.read_bytes()
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.decisions.open(encoding="utf-8-sig", newline="") as stream:
            self.assertEqual([row["csv_line"] for row in csv.DictReader(stream)], ["3", "4"])
        self.write_decisions(
            (3, "correct", "satisfaction", "5", "Verified rating"),
            (3, "correct", "complaint_outcome", "", "Skip logic"),
            (4, "exclude", "", "", "Confirmed duplicate"),
            (5, "keep", "", "", "Reviewed"),
        )
        result = self.apply_decisions()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.source.read_bytes(), original)
        with self.output.open(encoding="utf-8-sig", newline="") as stream:
            records = list(csv.DictReader(stream))
        self.assertEqual(len(records), 3)
        self.assertEqual((records[1]["satisfaction"], records[1]["complaint_outcome"]), ("5", ""))
        log = json.loads(self.log.read_text(encoding="utf-8"))
        self.assertEqual((log["input_rows"], log["exported_rows"], log["excluded_rows"]), (4, 3, 1))
        self.assertEqual([item["decision"] for item in log["decisions"]], ["correct", "correct", "exclude", "keep"])
        self.assertNotIn("replacement", log["decisions"][0])

    def test_rejects_conflicting_decisions_and_changed_source(self):
        self.assertEqual(self.prepare().returncode, 0)
        self.write_decisions((3, "exclude", "", "", "Duplicate"), (3, "correct", "satisfaction", "5", "Verified"))
        result = self.apply_decisions()
        self.assertEqual(result.returncode, 2)
        self.assertIn("conflicting", result.stderr)
        self.write_decisions((3, "keep", "", "", "Reviewed"))
        self.source.write_bytes(self.source.read_bytes().replace(b"S004", b"S005"))
        result = self.apply_decisions()
        self.assertEqual(result.returncode, 2)
        self.assertIn("SHA-256", result.stderr)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.log.exists())

    def test_existing_log_is_preserved_without_leaving_partial_export(self):
        self.assertEqual(self.prepare().returncode, 0)
        self.write_decisions((3, "keep", "", "", "Reviewed"))
        self.log.write_text("existing log", encoding="utf-8")
        result = self.apply_decisions()
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.log.read_text(encoding="utf-8"), "existing log")
