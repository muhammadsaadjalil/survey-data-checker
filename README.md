# Survey Data Checker

Check a UTF-8 CSV before importing survey data into SPSS or another analysis tool. Requires Python 3.10 or later and uses the standard library.

## Run the example

```powershell
py -3 tools/survey_check.py examples/survey_sample.csv --rules examples/survey_rules.json
```

On Linux or macOS, replace `py -3` with `python3`. The synthetic example checks four rows and flags two. The report lists CSV line numbers and checks without including respondent values. To save the report, redirect output to a new file such as `survey-review.json`.

## Set up your own rules

Copy `examples/survey_rules.json` and replace the column names with the exact headers from your export.

| Rule | What it flags |
| --- | --- |
| `required` | Blank answers in listed columns |
| `duplicate_by` | Repeated combinations of nonblank values in listed columns |
| `integer_ranges` | Nonblank answers that are not whole numbers or fall outside the inclusive bounds |
| `skip` | Follow-up answers that should be blank when a specified answer is given |
| `required_when` | A blank `column` when the answer in `when_column` matches `equals` |
| `allowed_values` | Nonblank answers outside the configured `values` for a column |

Checks trim surrounding whitespace. Skip, conditional-required, and allowed-value comparisons are case-insensitive. Review the flags before editing your analysis copy. The tool does not modify the source CSV. Exit codes are 0 for no flags, 1 for flags found, and 2 for input or rule errors.

## Summarize missing answers

```powershell
py -3 tools/survey_check.py examples/survey_sample.csv --rules examples/survey_rules.json --summary
```

The summary adds answered counts, missing counts, and missing percentages for every column, plus counts by check type. Percentages use all data rows as the denominator, so they include blanks expected by skip logic. A header-only file has no percentage. A row can trigger several checks.

## Apply review decisions and export for SPSS

Use the review report to investigate each flag. Then prepare a separate decisions file from the same source CSV and rules.

```powershell
py -3 tools/survey_review.py prepare examples/survey_sample.csv --rules examples/survey_rules.json --output decisions.csv
```

The template lists each flagged source line once. Import the template into Excel with the columns treated as text to preserve exact replacement values such as IDs with leading zeros. Keep the headers, `source_sha256`, and `csv_line` intact.

| Decision | What to enter |
| --- | --- |
| `keep` | A reason. Leave `column` and `replacement` blank. |
| `correct` | The exact source column name, the replacement value, and a reason. A blank replacement clears the cell. Copy the template row to correct another column on the same source line. |
| `exclude` | A reason. Leave `column` and `replacement` blank. The entire response is omitted from the reviewed copy. |

Completely blank decision fields leave a response unchanged. Enter at least one decision before exporting. Save the edited file as a UTF-8 CSV.

```powershell
py -3 tools/survey_review.py apply examples/survey_sample.csv --decisions decisions.csv --output reviewed.csv --log review-log.json
```

The export checks the source fingerprint and rejects conflicting decisions. It creates two new files and preserves the source CSV. Import `reviewed.csv` into SPSS as UTF-8 with the first row as column headers, then assign variable types and missing-value settings as needed. The JSON log records actions, source line numbers, and reasons. Keep reasons free of respondent identifiers.

## Run the tests

## Export a review CSV

```powershell
py -3 tools/survey_check.py examples/survey_sample.csv --rules examples/survey_rules.json --review-csv survey-review.csv
```

Open the report in Excel to review the flags. It has one row per flag with the physical CSV line number, the check name, and the affected column. It also includes range bounds, the trigger column, or the first matching line when applicable. The synthetic example produces four flags across two response rows. A clean export produces a report with only the header.

Choose a new output filename each time. The command leaves existing files intact and still prints the regular JSON report. Exit code 1 means it found flags and generated the report.

## Run the tests

```powershell
py -3 -m unittest discover -s tests -v
```
