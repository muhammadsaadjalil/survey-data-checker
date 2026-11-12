# Survey Data Checker

Check a survey CSV, review flagged responses, export a separate analysis copy, and generate an IBM SPSS Statistics import script. The tools run locally and require Python 3.10 or later.

## 1. Get the project and check Python

Download the repository using **Code → Download ZIP** and extract it, or clone it with Git. Open PowerShell in the extracted or cloned folder. It should contain `tools/` and `examples/`.

```powershell
py -3 --version
```

If the Windows launcher is unavailable, try `python --version` and use `python` in the commands below. On Linux or macOS, use `python3` instead of `py -3`. The tools use the Python standard library.

## 2. Prepare your survey CSV and rules

Start with the [synthetic survey](examples/survey_sample.csv) and [example rules](examples/survey_rules.json). For your own survey, export a UTF-8 comma-separated CSV with a header row. Copy the rules file and use your CSV's exact header names. Keep real survey exports, decisions, and outputs outside the repository.

| Rule | What it flags |
| --- | --- |
| `required` | Blank answers in listed columns |
| `duplicate_by` | Repeated combinations of nonblank values in listed columns |
| `integer_ranges` | Nonblank answers that are not whole numbers or fall outside the inclusive bounds |
| `skip` | Follow-up answers that should be blank when a specified answer is given |
| `required_when` | A blank `column` when the answer in `when_column` matches `equals` |
| `allowed_values` | Nonblank answers outside the configured `values` for a column |

Checks trim surrounding whitespace. Skip, conditional-required, and allowed-value comparisons are case-insensitive. Review the flags before editing your analysis copy. The tool does not modify the source CSV.

## 3. Check the data and export a review report

```powershell
py -3 tools/survey_check.py examples/survey_sample.csv --rules examples/survey_rules.json --summary --review-csv survey-review.csv
```

The example checks **four responses** and produces **four flags across two responses**. Open `survey-review.csv` in Excel. It contains one row per flag, with the physical CSV line number, affected column, and check. It omits response values. A clean export produces a report with only the header.

The command also prints JSON. With `--summary`, it includes answered and missing counts by column, missing percentages, and counts by check. Missing percentages use all response rows, including blanks expected by skip logic. Exit code `0` means no flags, `1` means flags were found and the report was generated, and `2` means an input or output error. Use a new filename for each report.

## 4. Prepare and record your review decisions

Investigate each flag against the source and your questionnaire. If no changes are needed, you can go straight to step 6 with your source CSV.

```powershell
py -3 tools/survey_review.py prepare examples/survey_sample.csv --rules examples/survey_rules.json --output decisions.csv
```

Import `decisions.csv` into Excel with all columns treated as text so values such as IDs with leading zeros are preserved. Keep the header row, `source_sha256`, and `csv_line` intact.

| Decision | What to enter |
| --- | --- |
| `keep` | A reason. Leave `column` and `replacement` blank. |
| `correct` | The exact CSV column name, a replacement, and a reason. Leave `replacement` blank to clear a cell. Duplicate the template row to correct another field on the same source line. |
| `exclude` | A reason. Leave `column` and `replacement` blank. This omits the entire response from the reviewed copy. |

To practice on the synthetic data, enter these example decisions. Keep the fingerprint already filled in by the template. The correction to `5` assumes the original answer was independently verified for this exercise.

| csv_line | decision | column | replacement | reason |
| --- | --- | --- | --- | --- |
| 3 | correct | satisfaction | 5 | Verified rating for this example |
| 3 | correct | complaint_outcome | | Follow-up does not apply |
| 4 | exclude | | | Confirmed duplicate for this example |

Save the edited template as a UTF-8 CSV. Blank decision fields leave that response unchanged. Enter at least one decision to create a reviewed export.

## 5. Export the reviewed CSV and verify it

```powershell
py -3 tools/survey_review.py apply examples/survey_sample.csv --decisions decisions.csv --output reviewed.csv --log review-log.json
py -3 tools/survey_check.py reviewed.csv --rules examples/survey_rules.json --summary
```

The tool checks the source fingerprint and rejects conflicting decisions. Keep the original CSV unchanged and choose unused output filenames. The example should produce **three responses and no remaining flags**. The JSON log records each decision, its original source line number, and its reason. Keep reasons free of respondent identifiers.

## 6. Set up your SPSS codebook and generate syntax

Copy [the synthetic codebook](examples/survey_codebook.json) and use your exact CSV headers as its keys. Give each column a unique SPSS variable name and a type. The generator uses the column order from your CSV.

| Codebook field | What it controls |
| --- | --- |
| `name`, `type` | SPSS variable name and either `numeric` or `string` |
| `width` | Required maximum UTF-8 byte width for a string |
| `decimals` | Optional number of display decimals for numeric variables |
| `label` | Question or variable label |
| `value_labels` | Mapping of response codes to display labels |
| `missing_values` | Up to three explicit user-missing codes per variable |

```powershell
py -3 tools/survey_spss.py reviewed.csv --codebook examples/survey_codebook.json --output survey-import.sps
```

If you skipped review and export, use the original CSV path in place of `reviewed.csv`. For real data, replace the synthetic codebook with your own. The generator checks numeric values, text widths, and that each response fits on one physical CSV line. Use dot decimals. Blank numeric cells are imported as system-missing, and explicit user-missing codes come from the codebook. The syntax uses the CSV's absolute path, so regenerate it if you move the CSV.

## 7. Run the syntax in IBM SPSS Statistics

1. Open `survey-import.sps` in the SPSS Syntax Editor and choose **Run → All**.
2. In Data View, confirm the case count. The worked example should have three cases.
3. In Variable View, confirm the names, types, question labels, response labels, and missing codes. The example defines satisfaction code `99` as user-missing.
4. Save the SPSS dataset as a separate `.sav` file if needed.

See the [IBM GET DATA reference](https://www.ibm.com/docs/en/spss-statistics/32.0.0?topic=data-subcommands-typetxt-get-command).

## Run the tests

```powershell
py -3 -m unittest discover -s tests -v
```
