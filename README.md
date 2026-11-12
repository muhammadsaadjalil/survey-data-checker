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

## Generate SPSS import syntax

Copy [the synthetic codebook](examples/survey_codebook.json) and use your exact CSV headers as its keys. Give each column a unique SPSS variable name and a type. The generator uses the column order from your CSV.

| Codebook field | What it controls |
| --- | --- |
| `name`, `type` | SPSS variable name and either `numeric` or `string` |
| `width` | Required maximum UTF-8 byte width for a string |
| `decimals` | Optional number of display decimals for numeric variables |
| `label` | Question or variable label |
| `value_labels` | Mapping of response codes to display labels |
| `missing_values` | Up to three explicit user-missing codes per variable |

Try the generator on the synthetic survey before using it on your reviewed export.

```powershell
py -3 tools/survey_spss.py examples/survey_sample.csv --codebook examples/survey_codebook.json --output sample-import.sps
```

For your reviewed data, replace the sample CSV and codebook paths with your own. Open the resulting `.sps` in IBM SPSS Statistics and run it to load the data and apply the metadata. The syntax uses the CSV's absolute path. Regenerate it if you move the CSV. The command refuses to overwrite an existing output file.

Use a UTF-8 comma-separated file with a header and one physical line per response. The generator reports incompatible numeric fields, over-width text, or embedded line breaks before writing syntax. Numeric fields use dot decimals. A numeric blank is left empty for SPSS to interpret as system-missing. Explicit missing codes come from the codebook. This step validates import compatibility. Run the survey checks separately to flag issues such as ratings outside the questionnaire scale.

See IBM's [GET DATA reference](https://www.ibm.com/docs/en/spss-statistics/32.0.0?topic=data-subcommands-typetxt-get-command) for the import syntax.

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
