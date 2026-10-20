"""Profile and validate the supplied EdVyro customer churn sample."""

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
INPUT_CSV = PROJECT_DIR / "customer_churn_sample (1).csv"
CLEANED_CSV = PROJECT_DIR / "cleaned_customer_churn.csv"
REPORT_MD = PROJECT_DIR / "data_quality_summary.md"
CHART_DIR = PROJECT_DIR / "charts"


def format_value(value):
    """Make pandas and NumPy values readable in generated Markdown."""
    if pd.isna(value):
        return "Missing"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def markdown_table(frame):
    """Convert a small DataFrame to a Markdown table without extra packages."""
    if frame.empty:
        return "_No data available._"

    headers = [str(column) for column in frame.columns]
    rows = [
        [format_value(value) for value in row]
        for row in frame.itertuples(index=False, name=None)
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def load_dataset():
    """Read the original CSV and show a clear error if it cannot be loaded."""
    if not INPUT_CSV.is_file():
        raise FileNotFoundError(
            f"Dataset not found: {INPUT_CSV.name}. "
            "Place the supplied CSV in the project folder."
        )

    try:
        return pd.read_csv(INPUT_CSV)
    except (
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
        UnicodeDecodeError,
        OSError,
    ) as error:
        raise ValueError(f"Could not read {INPUT_CSV.name}: {error}") from error


def inspect_outliers(data):
    """Flag, but never remove, numeric values outside 1.5 times the IQR."""
    results = []
    for column in data.select_dtypes(include="number").columns:
        values = data[column].dropna()
        if values.empty:
            results.append(
                {
                    "column": column,
                    "lower_bound": None,
                    "upper_bound": None,
                    "flagged_count": 0,
                    "flagged_values": "",
                }
            )
            continue

        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        flagged = data.loc[
            (data[column] < lower_bound) | (data[column] > upper_bound),
            column,
        ].dropna()
        results.append(
            {
                "column": column,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "flagged_count": len(flagged),
                "flagged_values": ", ".join(map(str, flagged.tolist())),
            }
        )

    return pd.DataFrame(
        results,
        columns=[
            "column",
            "lower_bound",
            "upper_bound",
            "flagged_count",
            "flagged_values",
        ],
    )


def inspect_category_spelling(data):
    """Find category labels that differ only by surrounding spaces/case."""
    results = []
    for column in data.select_dtypes(include=["object", "string"]).columns:
        observed = data[column].dropna().astype(str)
        normalized = observed.str.strip().str.casefold()
        for _, labels in observed.groupby(normalized):
            distinct_labels = sorted(labels.unique().tolist())
            if len(distinct_labels) > 1:
                results.append(
                    {"column": column, "labels_to_review": ", ".join(distinct_labels)}
                )
    return pd.DataFrame(results, columns=["column", "labels_to_review"])


def make_charts(data):
    """Save charts only when the relevant columns exist in the supplied data."""
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    chart_paths = []

    if "Churn" in data.columns:
        churn_counts = data["Churn"].value_counts(dropna=False)
        figure, axis = plt.subplots(figsize=(6, 4))
        churn_counts.plot(kind="bar", ax=axis, color="#4472C4")
        axis.set_title("Customer count by churn status")
        axis.set_xlabel("Churn")
        axis.set_ylabel("Customer count")
        axis.tick_params(axis="x", rotation=0)
        figure.tight_layout()
        output = CHART_DIR / "churn_counts.png"
        figure.savefig(output, dpi=150)
        plt.close(figure)
        chart_paths.append(output.relative_to(PROJECT_DIR).as_posix())

    if {"Churn", "ContractType"}.issubset(data.columns):
        grouped = data.groupby("ContractType", dropna=False)["Churn"].apply(
            lambda values: values.astype(str).str.strip().str.casefold().eq("yes").mean()
        )
        figure, axis = plt.subplots(figsize=(7, 4))
        (grouped * 100).plot(kind="bar", ax=axis, color="#70AD47")
        axis.set_title("Observed churn share by contract type")
        axis.set_xlabel("Contract type")
        axis.set_ylabel("Customers labeled Yes (%)")
        axis.tick_params(axis="x", rotation=20)
        figure.tight_layout()
        output = CHART_DIR / "churn_by_contract_type.png"
        figure.savefig(output, dpi=150)
        plt.close(figure)
        chart_paths.append(output.relative_to(PROJECT_DIR).as_posix())

    return chart_paths


def build_validation(data, cleaned, reread_cleaned):
    """Run checks that can be established from the supplied guide and data."""
    checks = []

    def add_check(label, passed, detail):
        checks.append((label, "PASS" if passed else "FAIL", detail))

    add_check(
        "Cleaned file has the same row count as source",
        len(cleaned) == len(data),
        f"source={len(data)}, cleaned={len(cleaned)}",
    )
    add_check(
        "Cleaned file has the same column count as source",
        len(cleaned.columns) == len(data.columns),
        f"source={len(data.columns)}, cleaned={len(cleaned.columns)}",
    )
    add_check(
        "Cleaned file preserves source column names and order",
        cleaned.columns.tolist() == data.columns.tolist(),
        f"columns={cleaned.columns.tolist()}",
    )
    add_check(
        "Saved CSV preserves source values and row order",
        data.equals(reread_cleaned),
        "Compared the original data with the CSV read back from disk.",
    )
    add_check(
        "Output CSV can be read back with the same shape",
        reread_cleaned.shape == data.shape,
        f"source={data.shape}, reread_output={reread_cleaned.shape}",
    )
    add_check(
        "No missing values in cleaned dataset",
        int(cleaned.isna().sum().sum()) == 0,
        f"missing_cells={int(cleaned.isna().sum().sum())}",
    )
    add_check(
        "No exact duplicate rows in cleaned dataset",
        int(cleaned.duplicated().sum()) == 0,
        f"duplicate_rows={int(cleaned.duplicated().sum())}",
    )

    numeric_columns = data.select_dtypes(include="number").columns.tolist()
    numeric_check = all(
        pd.api.types.is_numeric_dtype(cleaned[column]) for column in numeric_columns
    )
    add_check(
        "Original numeric columns remain numeric",
        numeric_check,
        f"checked={numeric_columns}",
    )
    return checks


def create_report(data, outliers, category_issues, checks, chart_paths):
    """Write findings calculated from this run to a Markdown report."""
    categorical_columns = data.select_dtypes(
        include=["object", "string", "category"]
    ).columns.tolist()
    numeric_summary = data.describe(include="number").transpose().reset_index()
    numeric_summary = numeric_summary.rename(columns={"index": "column"})
    categorical_sections = []
    for column in categorical_columns:
        counts = data[column].value_counts(dropna=False).rename_axis("value")
        frequencies = counts.rename("count").reset_index()
        categorical_sections.append(
            f"### {column}\n\n{markdown_table(frequencies)}"
        )

    dtype_rows = pd.DataFrame(
        {
            "column": data.columns,
            "dtype": [str(dtype) for dtype in data.dtypes],
            "missing_values": [int(data[column].isna().sum()) for column in data],
            "unique_values": [int(data[column].nunique(dropna=False)) for column in data],
        }
    )
    category_text = (
        markdown_table(category_issues)
        if not category_issues.empty
        else "No labels differing only by case or surrounding spaces were detected."
    )
    outlier_display = outliers.copy()
    for column in ("lower_bound", "upper_bound"):
        outlier_display[column] = outlier_display[column].map(
            lambda value: "N/A" if pd.isna(value) else f"{value:.2f}"
        )
    outlier_text = markdown_table(outlier_display)
    validation_text = "\n".join(
        f"- **{status}** — {label}: {detail}"
        for label, status, detail in checks
    )
    failed_checks = sum(status == "FAIL" for _, status, _ in checks)
    validation_result = "all listed checks passed" if failed_checks == 0 else (
        f"{failed_checks} validation check(s) failed"
    )

    churn_summary = "The dataset has no `Churn` column, so churn-specific comparisons were not generated."
    churn_comparison = "No churn comparison was generated because the required fields were not available."
    if "Churn" in data.columns:
        counts = data["Churn"].value_counts(dropna=False)
        churn_summary = (
            f"Churn labels observed: {', '.join(f'{label}={count}' for label, count in counts.items())}. "
            "These are descriptive counts from this 15-row synthetic sample, not evidence of causation "
            "or a representative estimate."
        )
        if "ContractType" in data.columns:
            churn_yes = data["Churn"].astype(str).str.strip().str.casefold().eq("yes")
            comparison = data.assign(_churn_yes=churn_yes).groupby(
                "ContractType", dropna=False
            ).agg(
                customers=("_churn_yes", "size"),
                churn_yes=("_churn_yes", "sum"),
                churn_rate=("_churn_yes", "mean"),
            ).reset_index()
            comparison["churn_rate"] = comparison["churn_rate"].map(
                lambda value: f"{value:.1%}"
            )
            churn_comparison = markdown_table(comparison)

    chart_section = (
        "\n".join(f"- [{path}](./{path})" for path in chart_paths)
        if chart_paths
        else "No charts were generated because the required fields were not available."
    )
    report = f"""# Data Quality and Exploratory Analysis

## Dataset overview

- Source file: `{INPUT_CSV.name}` (original preserved unchanged)
- Dataset: {len(data)} rows and {len(data.columns)} columns
- EdVyro describes the supplied data as synthetic. This file contains only 15 records, so findings are limited to this small sample.

## Column profile

{markdown_table(dtype_rows)}

## Missing values and duplicates

- Missing cells in source: {int(data.isna().sum().sum())}
- Exact duplicate rows in source: {int(data.duplicated().sum())}

## Category spelling review

{category_text}

This check only flags category labels that differ by case or surrounding whitespace. It does not define which labels are valid; the supplied task guide does not provide allowed category lists.

## Exploratory outlier review

Numeric values were screened with the 1.5×IQR rule. A flagged value is only a review candidate, not automatically an error. No outliers were removed.

{outlier_text}

## Cleaning decisions

The guide requests cleaning with documented assumptions, but it does not specify value ranges, allowed categories, missing-value imputation, or record deletion rules. The source has no missing values, exact duplicate rows, or category spelling variants detected by the limited case/whitespace check. Therefore the cleaned CSV preserves every row and value unchanged. This avoids guessing business rules or deleting potentially valid observations.

## Validation

Validation result: **{validation_result}**.

{validation_text}

No official required-column list or business-valid ranges were supplied, so domain validity cannot be conclusively certified.

## Numerical summary statistics

{markdown_table(numeric_summary)}

## Categorical frequency distributions

{"".join(section + chr(10) + chr(10) for section in categorical_sections) if categorical_sections else "No categorical columns were found."}

## Initial churn observation

{churn_summary}

### Churn comparison by contract type

{churn_comparison}

Any observed differences are descriptive comparisons only. They do not show that contract type or another field causes churn. A sample of 15 synthetic records is too small for broad conclusions.

## Charts

{chart_section}

## Limitations

- Only 15 synthetic records are present; results may not generalize to real customers.
- The supplied task guide does not provide a separate data dictionary or detailed cleaning rules.
- Plausible value ranges and business consistency (for example, how charges relate to tenure) cannot be judged without an authoritative guide.
- The IQR rule is exploratory and may not identify all unusual or invalid values, especially in a small dataset.
"""
    REPORT_MD.write_text(report, encoding="utf-8")


def main():
    try:
        source = load_dataset()
        original_shape = source.shape
        print(f"Loaded {INPUT_CSV.name}: {source.shape[0]} rows, {source.shape[1]} columns")
        print("\nColumn names:")
        print(source.columns.tolist())
        print("\nData types:")
        print(source.dtypes.to_string())
        print("\nFirst five rows:")
        print(source.head().to_string(index=False))
        print("\nMissing values:")
        print(source.isna().sum().to_string())
        print(f"\nExact duplicate rows: {int(source.duplicated().sum())}")

        outliers = inspect_outliers(source)
        category_issues = inspect_category_spelling(source)

        # No cleaning transformations are justified by the supplied guide/data.
        cleaned = source.copy(deep=True)
        cleaned.to_csv(CLEANED_CSV, index=False)
        reread_cleaned = pd.read_csv(CLEANED_CSV)
        checks = build_validation(source, cleaned, reread_cleaned)
        chart_paths = make_charts(source)
        create_report(source, outliers, category_issues, checks, chart_paths)

        validation_file = PROJECT_DIR / "validation_results.txt"
        with validation_file.open("w", encoding="utf-8") as file:
            file.write(f"Source shape: {original_shape}\n")
            file.write(f"Cleaned output shape: {reread_cleaned.shape}\n\n")
            for label, status, detail in checks:
                file.write(f"{status}: {label} — {detail}\n")

        print("\nIQR outlier review:")
        print(outliers.to_string(index=False))
        print("\nValidation results:")
        for label, status, detail in checks:
            print(f"{status}: {label} — {detail}")
        print("\nGenerated files:")
        for path in [CLEANED_CSV, REPORT_MD, validation_file]:
            print(f"- {path.relative_to(PROJECT_DIR)}")
        for path in chart_paths:
            print(f"- {path}")
        if any(status == "FAIL" for _, status, _ in checks):
            return 1
        return 0
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"Analysis failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
