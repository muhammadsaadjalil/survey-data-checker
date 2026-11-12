#!/usr/bin/env python3
"""Prepare and apply explicit decisions for a survey export."""

import argparse
import csv
import hashlib
import io
import json
import re
from contextlib import ExitStack
from pathlib import Path

from survey_check import check_survey_stream, load_rules


FIELDS = ("source_sha256", "csv_line", "decision", "column", "replacement", "reason")


def csv_stream(raw: bytes) -> io.StringIO:
    return io.StringIO(raw.decode("utf-8-sig"), newline="")


def create_template(raw: bytes, digest: str, rules_path: Path, output: Path) -> None:
    report = check_survey_stream(csv_stream(raw), load_rules(rules_path))
    with output.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(FIELDS)
        for row in report["flagged_rows"]:
            writer.writerow((digest, row["line"], "", "", "", ""))


def read_source(raw: bytes) -> tuple[list, dict]:
    reader = csv.reader(csv_stream(raw), strict=True)
    headers = next(reader, [])
    if not headers or any(not name.strip() for name in headers) or len(set(headers)) != len(headers):
        raise ValueError("Source CSV needs unique, nonempty column headers")
    rows = {}
    while True:
        line = reader.line_num + 1
        cells = next(reader, None)
        if cells is None:
            return headers, rows
        if len(cells) != len(headers):
            raise ValueError(f"Source CSV line {line}: expected {len(headers)} columns")
        rows[line] = cells


def read_decisions(path: Path, digest: str, headers: list, rows: dict) -> tuple[dict, list]:
    changes = {}
    audit = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        if tuple(next(reader, [])) != FIELDS:
            raise ValueError("Decisions CSV must use the original template headers")
        for fields in reader:
            location = f"Decisions CSV line {reader.line_num}"
            if len(fields) != len(FIELDS):
                raise ValueError(f"{location}: expected {len(FIELDS)} fields")
            fingerprint, line_text, action, column, replacement, reason = fields
            if fingerprint != digest:
                raise ValueError(f"{location}: source SHA-256 does not match the supplied CSV")
            if not re.fullmatch(r"[0-9]{1,18}", line_text) or int(line_text) not in rows:
                raise ValueError(f"{location}: csv_line does not identify a source record")
            line = int(line_text)
            action = action.strip().lower()
            if not action and not any((column, replacement, reason)):
                continue
            if action not in {"keep", "correct", "exclude"} or not reason.strip():
                raise ValueError(f"{location}: enter keep, correct, or exclude and a reason")
            if action == "correct":
                if column not in headers:
                    raise ValueError(f"{location}: correction column does not match a source header")
            elif column or replacement:
                raise ValueError(f"{location}: keep and exclude take no column or replacement")

            row_changes = changes.setdefault(line, {})
            if row_changes and (action != "correct" or "" in row_changes or column in row_changes):
                raise ValueError(f"{location}: conflicting or duplicate decisions for source line {line}")
            row_changes[column] = (action, replacement)
            audit.append({"csv_line": line, "decision": action, "column": column or None, "reason": reason.strip()})
    if not audit:
        raise ValueError("Enter at least one review decision before exporting")
    return changes, audit


def export_review(raw: bytes, digest: str, decisions: Path, output: Path, log: Path) -> None:
    headers, rows = read_source(raw)
    changes, audit = read_decisions(decisions, digest, headers, rows)
    excluded = 0
    with ExitStack() as rollback:
        with output.open("x", encoding="utf-8-sig", newline="") as csv_output:
            rollback.callback(output.unlink)
            with log.open("x", encoding="utf-8", newline="\n") as log_output:
                rollback.callback(log.unlink)
                writer = csv.writer(csv_output)
                writer.writerow(headers)
                for line, cells in rows.items():
                    row_changes = changes.get(line, {})
                    if row_changes.get("", ("", ""))[0] == "exclude":
                        excluded += 1
                        continue
                    writer.writerow([
                        row_changes[column][1] if column in row_changes else value
                        for column, value in zip(headers, cells)
                    ])
                json.dump({
                    "source_sha256": digest,
                    "input_rows": len(rows),
                    "exported_rows": len(rows) - excluded,
                    "excluded_rows": excluded,
                    "decisions": audit,
                }, log_output, indent=2)
                log_output.write("\n")
        rollback.pop_all()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Create a decisions template from flagged rows")
    prepare.add_argument("source", type=Path)
    prepare.add_argument("--rules", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    apply = commands.add_parser("apply", help="Write a reviewed CSV and JSON change log")
    apply.add_argument("source", type=Path)
    apply.add_argument("--decisions", type=Path, required=True)
    apply.add_argument("--output", type=Path, required=True)
    apply.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = args.source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if args.command == "prepare":
            create_template(raw, digest, args.rules, args.output)
        else:
            export_review(raw, digest, args.decisions, args.output, args.log)
    except (OSError, ValueError, csv.Error, RecursionError) as error:
        parser.exit(2, f"Survey review error: {error}\n")
    print(f"Created {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
