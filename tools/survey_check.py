#!/usr/bin/env python3
"""Flag survey CSV rows that need review using a JSON rules file."""

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def load_rules(path: Path) -> dict:
    rules = json.loads(path.read_text(encoding="utf-8-sig"))
    sections = {"required", "duplicate_by", "integer_ranges", "skip"}
    if not isinstance(rules, dict) or rules.keys() - sections:
        raise ValueError("Rules must be an object with required, duplicate_by, integer_ranges, or skip")
    rules = {section: rules.get(section, []) for section in sections}
    for section, entries in rules.items():
        if not isinstance(entries, list):
            raise ValueError(f"{section} must be a list")
    for section in ("required", "duplicate_by"):
        if any(not isinstance(column, str) or not column.strip() for column in rules[section]):
            raise ValueError(f"{section} must contain nonempty column names")
        if len(set(rules[section])) != len(rules[section]):
            raise ValueError(f"{section} contains duplicate column names")
    for rule in rules["integer_ranges"]:
        if (
            not isinstance(rule, dict) or rule.keys() != {"column", "min", "max"}
            or not isinstance(rule["column"], str) or not rule["column"].strip()
            or type(rule["min"]) is not int or type(rule["max"]) is not int
            or rule["min"] > rule["max"]
        ):
            raise ValueError("Each integer range needs a column and ordered integer min and max")
    for rule in rules["skip"]:
        if (
            not isinstance(rule, dict) or rule.keys() != {"when_column", "equals", "blank_column"}
            or any(not isinstance(value, str) or not value.strip() for value in rule.values())
        ):
            raise ValueError("Each skip rule needs nonempty when_column, equals, and blank_column strings")
    if not any(rules.values()):
        raise ValueError("Configure at least one survey check")
    return rules


def check_survey(path: Path, rules: dict) -> dict:
    required = rules["required"]
    duplicate_by = rules["duplicate_by"]
    ranges = rules["integer_ranges"]
    skip_rules = rules["skip"]
    referenced = set(required + duplicate_by)
    referenced.update(rule["column"] for rule in ranges)
    for rule in skip_rules:
        referenced.update((rule["when_column"], rule["blank_column"]))

    flagged_rows = []
    seen = {}
    checked = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        headers = next(reader, [])
        if not headers or any(not column.strip() for column in headers) or len(set(headers)) != len(headers):
            raise ValueError("CSV needs unique, nonempty column headers")
        missing = referenced.difference(headers)
        if missing:
            raise ValueError("CSV is missing configured columns: " + ", ".join(sorted(missing)))

        while True:
            line = reader.line_num + 1
            cells = next(reader, None)
            if cells is None:
                break
            checked += 1
            if len(cells) != len(headers):
                raise ValueError(f"CSV line {line}: expected {len(headers)} columns, found {len(cells)}")
            row = dict(zip(headers, (cell.strip() for cell in cells)))
            flags = []
            for column in required:
                if not row[column]:
                    flags.append({"check": "required", "column": column})
            for rule in ranges:
                column = rule["column"]
                value = row[column]
                if not value:
                    continue
                try:
                    number = int(value) if re.fullmatch(r"[+-]?[0-9]+", value) else None
                except ValueError:
                    number = None
                if number is None or not rule["min"] <= number <= rule["max"]:
                    flags.append({"check": "integer_range", **rule})
            for rule in skip_rules:
                column = rule["blank_column"]
                if row[rule["when_column"]].casefold() == rule["equals"].strip().casefold() and row[column]:
                    flags.append({"check": "skip_logic", "column": column, "when_column": rule["when_column"]})
            key = tuple(row[column] for column in duplicate_by)
            if key and all(key):
                first_line = seen.setdefault(key, line)
                if first_line != line:
                    flags.append({"check": "possible_duplicate", "columns": duplicate_by, "first_line": first_line})
            if flags:
                flagged_rows.append({"line": line, "flags": flags})

    return {"rows_checked": checked, "rows_flagged": len(flagged_rows), "flagged_rows": flagged_rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="UTF-8 survey export")
    parser.add_argument("--rules", required=True, type=Path, help="JSON file containing survey rules")
    args = parser.parse_args()
    try:
        result = check_survey(args.csv_file, load_rules(args.rules))
    except (OSError, ValueError, csv.Error, RecursionError) as error:
        parser.exit(2, f"Survey check error: {error}\n")
    print(json.dumps(result, indent=2))
    return 1 if result["rows_flagged"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
