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

## Run the tests

```powershell
py -3 -m unittest discover -s tests -v
```
