"""Local read-only API for the existing customer churn analysis outputs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, send_file
from flask_cors import CORS
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = PROJECT_ROOT / "customer_churn_sample (1).csv"
CLEANED_CSV = PROJECT_ROOT / "cleaned_customer_churn.csv"
VALIDATION_FILE = PROJECT_ROOT / "validation_results.txt"
SUMMARY_FILE = PROJECT_ROOT / "data_quality_summary.md"

sys.path.insert(0, str(PROJECT_ROOT))
import data_quality_analysis as analysis  # noqa: E402


app = Flask(__name__)
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
        }
    },
)


def load_project_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the original and cleaned files without changing either one."""
    missing_files = [
        path.name for path in (SOURCE_CSV, CLEANED_CSV) if not path.is_file()
    ]
    if missing_files:
        raise FileNotFoundError(
            "Required project file(s) are missing: " + ", ".join(missing_files)
        )
    try:
        source = pd.read_csv(SOURCE_CSV)
        cleaned = pd.read_csv(CLEANED_CSV)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as error:
        raise ValueError(f"Could not read a project CSV: {error}") from error
    return source, cleaned


def records_from_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-safe row dictionaries."""
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def validation_data(
    source: pd.DataFrame, cleaned: pd.DataFrame
) -> tuple[list[dict[str, str]], str]:
    """Re-run the analysis script's validation rules against current files."""
    reread_cleaned = pd.read_csv(CLEANED_CSV)
    checks = analysis.build_validation(source, cleaned, reread_cleaned)
    rows = [
        {"status": status, "rule": rule, "details": details}
        for rule, status, details in checks
    ]
    if VALIDATION_FILE.is_file():
        saved_report = VALIDATION_FILE.read_text(encoding="utf-8")
    else:
        saved_report = ""
    return rows, saved_report


def value_counts(frame: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    """Return actual value frequencies, including missing labels."""
    counts = frame[column].value_counts(dropna=False)
    return [
        {
            "label": "(Missing)" if pd.isna(label) else str(label),
            "count": int(count),
        }
        for label, count in counts.items()
    ]


def dashboard_payload() -> dict[str, Any]:
    """Calculate API values from the supplied files and original analysis rules."""
    source, cleaned = load_project_data()
    checks, saved_validation = validation_data(source, cleaned)
    passed = sum(check["status"] == "PASS" for check in checks)
    failed = sum(check["status"] == "FAIL" for check in checks)

    column_profile = [
        {
            "column": str(column),
            "dtype": str(cleaned[column].dtype),
            "missing": int(cleaned[column].isna().sum()),
            "unique": int(cleaned[column].nunique(dropna=False)),
        }
        for column in cleaned.columns
    ]
    missing = [
        {"column": str(column), "count": int(cleaned[column].isna().sum())}
        for column in cleaned.columns
    ]
    outliers = analysis.inspect_outliers(cleaned)
    outlier_rows = [
        {
            "column": str(row["column"]),
            "lower_bound": None if pd.isna(row["lower_bound"]) else float(row["lower_bound"]),
            "upper_bound": None if pd.isna(row["upper_bound"]) else float(row["upper_bound"]),
            "flagged_count": int(row["flagged_count"]),
            "flagged_values": str(row["flagged_values"]),
        }
        for _, row in outliers.iterrows()
    ]

    churn_column = "Churn" if "Churn" in cleaned.columns else None
    churn_counts = value_counts(cleaned, churn_column) if churn_column else []
    contract_churn: list[dict[str, Any]] = []
    churn_rate: float | None = None
    if churn_column:
        churn_values = cleaned[churn_column].astype("string").str.strip().str.casefold()
        positive_labels = {"yes", "true", "1", "churned"}
        negative_labels = {"no", "false", "0", "retained"}
        observed_labels = set(churn_values.dropna().unique())
        if observed_labels and observed_labels.issubset(positive_labels | negative_labels):
            churn_yes = churn_values.isin(positive_labels)
            churn_rate = float(churn_yes.mean() * 100) if len(cleaned) else 0.0
            if "ContractType" in cleaned.columns:
                grouped = cleaned.assign(_churn_yes=churn_yes).groupby(
                    "ContractType", dropna=False, sort=False
                )
                contract_churn = []
                for label, group in grouped:
                    customers = int(len(group))
                    churned = int(group["_churn_yes"].sum())
                    rate_percent = (
                        (churned / customers) * 100 if customers else 0.0
                    )
                    contract_churn.append(
                        {
                            "contract": "(Missing)" if pd.isna(label) else str(label),
                            "customers": customers,
                            "churned": churned,
                            "rate_percent": rate_percent,
                        }
                    )

    numeric_names = [
        str(column)
        for column in cleaned.select_dtypes(include="number").columns
        if not pd.api.types.is_bool_dtype(cleaned[column])
    ]
    subscription = (
        value_counts(cleaned, "SubscriptionType")
        if "SubscriptionType" in cleaned.columns
        else []
    )

    findings = [
        f"{len(cleaned):,} records and {len(cleaned.columns):,} columns are present.",
        f"{int(cleaned.isna().sum().sum()):,} missing cell(s) and "
        f"{int(cleaned.duplicated().sum()):,} exact duplicate row(s) were found.",
        f"{sum(row['flagged_count'] for row in outlier_rows):,} numeric value(s) "
        "were flagged by the 1.5×IQR review; flags are not automatic errors.",
    ]
    return {
        "dataset": {
            "filename": CLEANED_CSV.name,
            "rows": int(len(cleaned)),
            "columns": int(len(cleaned.columns)),
            "column_names": [str(column) for column in cleaned.columns],
            "column_profile": column_profile,
            "records": records_from_frame(cleaned),
        },
        "kpis": {
            "total_records": int(len(cleaned)),
            "total_columns": int(len(cleaned.columns)),
            "missing_values": int(cleaned.isna().sum().sum()),
            "duplicate_rows": int(cleaned.duplicated().sum()),
            "validation_passed": passed,
            "validation_total": len(checks),
            "validation_failed": failed,
            "churn_rate": churn_rate,
        },
        "charts": {
            "missing": missing,
            "churn": churn_counts,
            "subscription": subscription,
            "contract_churn": contract_churn,
            "numeric_columns": numeric_names,
            "outliers": outlier_rows,
        },
        "validation": checks,
        "saved_validation_available": bool(saved_validation),
        "findings": findings,
        "disclaimer": (
            "The supplied dataset is a small synthetic sample. Observed patterns "
            "are descriptive and should not be interpreted as causal or representative."
        ),
        "scope_note": (
            "Passing checks cover only the rules implemented in the project; they "
            "do not certify every business or domain rule."
        ),
    }


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/dashboard")
def dashboard():
    try:
        return jsonify(dashboard_payload())
    except (FileNotFoundError, ValueError, OSError, pd.errors.ParserError) as error:
        return jsonify({"error": str(error)}), 503


@app.get("/api/records")
def records():
    try:
        _, cleaned = load_project_data()
        return jsonify(
            {
                "filename": CLEANED_CSV.name,
                "columns": [str(column) for column in cleaned.columns],
                "records": records_from_frame(cleaned),
            }
        )
    except (FileNotFoundError, ValueError, OSError, pd.errors.ParserError) as error:
        return jsonify({"error": str(error)}), 503


@app.get("/api/validation")
def validation():
    try:
        source, cleaned = load_project_data()
        checks, saved_report = validation_data(source, cleaned)
        return jsonify(
            {
                "checks": checks,
                "saved_report": saved_report,
                "passed": sum(check["status"] == "PASS" for check in checks),
                "failed": sum(check["status"] == "FAIL" for check in checks),
                "total": len(checks),
            }
        )
    except (FileNotFoundError, ValueError, OSError, pd.errors.ParserError) as error:
        return jsonify({"error": str(error)}), 503


@app.get("/api/download/cleaned.csv")
def download_cleaned():
    if not CLEANED_CSV.is_file():
        return jsonify({"error": "The cleaned dataset is not available."}), 404
    return send_file(CLEANED_CSV, as_attachment=True, download_name=CLEANED_CSV.name)


@app.get("/api/download/summary.md")
def download_summary():
    if not SUMMARY_FILE.is_file():
        return jsonify({"error": "The data quality summary report is not available."}), 404
    return send_file(SUMMARY_FILE, as_attachment=True, download_name=SUMMARY_FILE.name)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
