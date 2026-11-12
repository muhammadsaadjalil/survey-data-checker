#!/usr/bin/env python3
"""Generate IBM SPSS Statistics import syntax from a CSV and JSON codebook."""

import argparse
import csv
import json
import math
import re
from pathlib import Path


NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}")
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
RESERVED = {"ALL", "AND", "BY", "EQ", "GE", "GT", "LE", "LT", "NE", "NOT", "OR", "TO", "WITH"}


def literal(value: str, limit: int = 32767) -> str:
    if not isinstance(value, str) or any(ord(char) < 32 for char in value) or len(value.encode("utf-8")) > limit:
        raise ValueError(f"SPSS text must fit within {limit} UTF-8 bytes and contain no control characters")
    return "'" + value.replace("'", "''") + "'"


def numeric(value: str) -> str:
    if not NUMBER.fullmatch(value) or len(value) > 40 or not math.isfinite(float(value)):
        raise ValueError("Expected a finite dot-decimal number within 40 characters")
    return value


def value_literal(value, width: int | None, *, missing: bool = False) -> str:
    if width is not None:
        return literal(value, min(width, 8) if missing else width)
    if type(value) in (int, float):
        value = str(value)
    if not isinstance(value, str):
        raise ValueError("Numeric codes must be numbers or numeric strings")
    return numeric(value)


def load_variables(path: Path) -> dict:
    variables = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(variables, dict) or not variables:
        raise ValueError("Codebook must map exact CSV headers to variable definitions")
    used = set()
    for column, spec in variables.items():
        if not isinstance(spec, dict) or spec.keys() - {"name", "type", "width", "decimals", "label", "value_labels", "missing_values"}:
            raise ValueError(f"Invalid codebook definition for {column!r}")
        name = spec.get("name")
        if not isinstance(name, str) or not NAME.fullmatch(name) or name.upper() in RESERVED | used:
            raise ValueError(f"Invalid or duplicate SPSS variable name for {column!r}")
        used.add(name.upper())
        kind = spec.get("type")
        if kind == "string":
            width = spec.get("width")
            if type(width) is not int or not 1 <= width <= 32767 or "decimals" in spec:
                raise ValueError(f"{column!r}: string variables need a width of 1–32767 bytes")
        elif kind == "numeric":
            decimals = spec.get("decimals", 0)
            if type(decimals) is not int or not 0 <= decimals <= 16 or "width" in spec:
                raise ValueError(f"{column!r}: numeric variables accept 0–16 display decimals")
        else:
            raise ValueError(f"{column!r}: type must be numeric or string")
        labels = spec.get("value_labels", {})
        missing = spec.get("missing_values", [])
        if not isinstance(labels, dict) or not isinstance(missing, list) or len(missing) > 3:
            raise ValueError(f"{column!r}: value_labels must be an object and missing_values a list of up to three codes")
    return variables


def validate_csv(path: Path, variables: dict) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        headers = next(reader, [])
        if len(headers) != len(variables) or set(headers) != variables.keys():
            raise ValueError("Codebook must define every CSV header exactly once")
        for row in reader:
            if len(row) != len(headers):
                raise ValueError(f"CSV line {reader.line_num}: wrong number of columns")
            for column, value in zip(headers, row):
                try:
                    if "\r" in value or "\n" in value:
                        raise ValueError("Multiline fields are unsupported by this line-based import")
                    spec = variables[column]
                    if spec["type"] == "string":
                        if len(value.encode("utf-8")) > spec["width"]:
                            raise ValueError("Text exceeds the codebook width in UTF-8 bytes")
                    elif value.strip():
                        numeric(value.strip())
                except ValueError as error:
                    raise ValueError(f"CSV line {reader.line_num}, {column!r}: {error}") from error
    return headers


def generate_syntax(path: Path, variables: dict) -> str:
    headers = validate_csv(path, variables)
    commands = [
        "SET DECIMAL=DOT.",
        "GET DATA",
        " /TYPE=TXT",
        f" /FILE={literal(str(path.resolve()))}",
        " /ENCODING='UTF8'",
        " /ARRANGEMENT=DELIMITED",
        " /DELCASE=LINE",
        ' /DELIMITERS=","',
        """ /QUALIFIER='"'""",
        " /FIRSTCASE=2",
        " /VARIABLES=",
    ]
    formats = []
    metadata = []
    for column in headers:
        spec = variables[column]
        name = spec["name"]
        width = spec.get("width")
        fmt = f"A{width}" if width is not None else "F40.0"
        formats.append(f"  {name} {fmt}")
        if spec.get("decimals"):
            metadata.append(f"FORMATS {name} (F40.{spec['decimals']}).")
        if "label" in spec:
            metadata.append(f"VARIABLE LABELS {name} {literal(spec['label'], 256)}.")
        if labels := spec.get("value_labels"):
            entries = [f"  {value_literal(code, width)} {literal(label, 120)}" for code, label in labels.items()]
            metadata.append(f"VALUE LABELS {name}\n" + "\n".join(entries) + ".")
        if missing := spec.get("missing_values"):
            entries = ", ".join(value_literal(code, width, missing=True) for code in missing)
            metadata.append(f"MISSING VALUES {name} ({entries}).")
    return "\n".join([*commands, "\n".join(formats) + ".", *metadata, "EXECUTE.", ""])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--codebook", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        syntax = generate_syntax(args.csv_file, load_variables(args.codebook))
        with args.output.open("x", encoding="utf-8-sig", newline="\n") as stream:
            stream.write(syntax)
    except (OSError, ValueError, csv.Error, RecursionError) as error:
        parser.exit(2, f"SPSS export error: {error}\n")
    print(f"Created {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
