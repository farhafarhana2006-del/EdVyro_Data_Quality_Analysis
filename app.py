"""Interactive data-quality dashboard for the EdVyro churn project."""

from __future__ import annotations

import csv
from datetime import datetime
from hashlib import sha256
from io import BytesIO, StringIO
from pathlib import Path
import re
from typing import Any
from zipfile import BadZipFile

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


PROJECT_DIR = Path(__file__).resolve().parent
SAMPLE_CSV = PROJECT_DIR / "customer_churn_sample (1).csv"
VALIDATION_FILE = PROJECT_DIR / "validation_results.txt"
SUMMARY_FILE = PROJECT_DIR / "data_quality_summary.md"
SAVED_CHARTS = [
    PROJECT_DIR / "charts" / "churn_counts.png",
    PROJECT_DIR / "charts" / "churn_by_contract_type.png",
]

BLUE = "#3478F6"
PURPLE = "#7357C8"
TEAL = "#1D9A91"
AMBER = "#D98B26"
RED = "#C94C4C"
PALETTE = [BLUE, PURPLE, TEAL, AMBER, "#6384A8", "#C96C7A"]

STATUS_ORDER = ["PASS", "WARNING", "FAIL", "NOT APPLICABLE"]
ERROR_SEVERITY = "Error"
WARNING_SEVERITY = "Warning"

st.set_page_config(
    page_title="Customer Churn | Data Quality",
    page_icon="DQ",
    layout="wide",
    initial_sidebar_state="auto",
)


@st.cache_data(show_spinner=False)
def read_sample_csv(path: str, modified_at: int) -> pd.DataFrame:
    """Read the supplied sample; its modification time invalidates the cache."""
    return pd.read_csv(path, encoding="utf-8-sig")


@st.cache_data(show_spinner=False)
def parse_uploaded_dataset(content: bytes, extension: str) -> pd.DataFrame:
    """Read an uploaded CSV or Excel workbook from memory."""
    if not content:
        raise ValueError("The uploaded file is empty.")

    if extension == ".csv":
        decoding_errors: list[str] = []
        for encoding in ("utf-8-sig", "utf-8", "cp1252"):
            try:
                decoded = content.decode(encoding)
                try:
                    headers = next(csv.reader(StringIO(decoded), strict=True))
                except StopIteration as error:
                    raise ValueError("The CSV file does not contain a header row.") from error
                except csv.Error as error:
                    raise ValueError(f"Could not parse the CSV header: {error}") from error
                if any(not str(header).strip() for header in headers):
                    raise ValueError("The CSV contains a blank column name.")
                duplicate_headers = sorted(
                    {header for header in headers if headers.count(header) > 1}
                )
                if duplicate_headers:
                    raise ValueError(
                        "Duplicate column names are ambiguous and cannot be "
                        "profiled safely: "
                        + ", ".join(duplicate_headers)
                    )
                frame = pd.read_csv(
                    StringIO(decoded),
                    low_memory=False,
                )
                break
            except UnicodeDecodeError as error:
                decoding_errors.append(f"{encoding}: {error}")
            except (pd.errors.ParserError, pd.errors.EmptyDataError) as error:
                raise ValueError(f"Could not parse the CSV file: {error}") from error
        else:
            raise ValueError(
                "The CSV text encoding could not be identified. "
                + "; ".join(decoding_errors)
            )
    elif extension == ".xlsx":
        try:
            frame = pd.read_excel(BytesIO(content))
        except ImportError as error:
            raise ValueError(
                "Excel support requires openpyxl. Install it with "
                "`python -m pip install openpyxl`."
            ) from error
        except (ValueError, OSError, BadZipFile) as error:
            raise ValueError(f"Could not read the Excel workbook: {error}") from error
    else:
        raise ValueError("Unsupported file type. Upload a .csv or .xlsx file.")

    if frame.empty:
        raise ValueError("The uploaded file has column headers but no data rows.")
    if len(frame.columns) == 0:
        raise ValueError("The uploaded file has no columns.")
    if (frame.columns.astype(str).str.strip() == "").any():
        raise ValueError("The dataset contains one or more blank column names.")
    duplicate_headers = frame.columns[frame.columns.duplicated()].astype(str).tolist()
    if duplicate_headers:
        raise ValueError(
            "Duplicate column names are ambiguous and cannot be profiled safely: "
            + ", ".join(duplicate_headers)
        )

    frame.columns = [str(column) for column in frame.columns]
    return frame.reset_index(drop=True)


def normalized_name(value: Any) -> str:
    """Normalize a column name for flexible schema detection."""
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def find_column(data: pd.DataFrame, names: set[str]) -> str | None:
    """Return a matching column without imposing a required schema."""
    for column in data.columns:
        if normalized_name(column) in names:
            return column
    return None


def find_identifier_column(data: pd.DataFrame) -> str | None:
    """Find common customer or record identifier names."""
    exact = {
        "id",
        "customerid",
        "clientid",
        "accountid",
        "subscriberid",
        "userid",
        "recordid",
    }
    for column in data.columns:
        if normalized_name(column) in exact:
            return column
    return None


def numeric_columns(data: pd.DataFrame) -> list[str]:
    """Return numeric columns, excluding Boolean flags."""
    return [
        column
        for column in data.select_dtypes(include="number").columns
        if not pd.api.types.is_bool_dtype(data[column])
    ]


def values_as_text(series: pd.Series) -> pd.Series:
    """Convert non-null values to text without changing the underlying data."""
    return series.astype("string")


def assess_quality(data: pd.DataFrame) -> dict[str, Any]:
    """Calculate dynamic checks, issue rows, and exploratory review tables."""
    checks: list[dict[str, Any]] = []
    row_flags: dict[str, list[bool]] = {}
    n_rows = len(data)

    def add_check(
        rule: str,
        status: str,
        severity: str,
        columns: list[str],
        mask: pd.Series | list[bool] | None,
        recommendation: str,
        details: str,
    ) -> None:
        if mask is None:
            positions = [False] * n_rows
        elif isinstance(mask, pd.Series):
            positions = mask.fillna(False).to_numpy(dtype=bool).tolist()
        else:
            positions = list(mask)
        key = f"rule_{len(checks)}"
        row_flags[key] = positions
        checks.append(
            {
                "Status": status,
                "Severity": severity,
                "Rule": rule,
                "Affected columns": ", ".join(columns) if columns else "—",
                "Affected records": int(sum(positions)),
                "Recommendation": recommendation,
                "Details": details,
                "_flag_key": key,
            }
        )

    missing_by_column = data.isna().sum()
    missing_rows = data.isna().any(axis=1)
    missing_count = int(missing_by_column.sum())
    add_check(
        "Missing cells",
        "WARNING" if missing_count else "PASS",
        WARNING_SEVERITY if missing_count else "Info",
        data.columns[missing_by_column.gt(0)].tolist(),
        missing_rows,
        "Review whether values are required; choose a documented fill strategy only if appropriate.",
        f"{missing_count:,} missing cell(s) across {int(missing_by_column.gt(0).sum())} column(s).",
    )

    duplicate_rows = data.duplicated(keep=False)
    duplicate_count = int(data.duplicated().sum())
    add_check(
        "Exact duplicate rows",
        "FAIL" if duplicate_count else "PASS",
        ERROR_SEVERITY if duplicate_count else "Info",
        list(data.columns),
        duplicate_rows,
        "Review repeated full records. Remove only after explicit confirmation.",
        f"{duplicate_count:,} extra exact duplicate row(s).",
    )

    identifier = find_identifier_column(data)
    if identifier is None:
        add_check(
            "Customer identifier availability",
            "NOT APPLICABLE",
            "Info",
            [],
            None,
            "No common customer or record ID column was detected; no identifier rule was assumed.",
            "Identifier-related checks were not evaluated.",
        )
    else:
        identifier_values = values_as_text(data[identifier])
        empty_ids = data[identifier].isna() | identifier_values.str.strip().eq("")
        duplicate_ids = (
            identifier_values.str.strip().ne("")
            & identifier_values.str.strip().duplicated(keep=False)
        )
        add_check(
            "Blank identifiers",
            "FAIL" if bool(empty_ids.any()) else "PASS",
            ERROR_SEVERITY if bool(empty_ids.any()) else "Info",
            [identifier],
            empty_ids,
            "Supply a valid source identifier; do not fabricate an ID.",
            f"{int(empty_ids.sum()):,} blank identifier(s).",
        )
        add_check(
            "Duplicate identifiers",
            "FAIL" if bool(duplicate_ids.any()) else "PASS",
            ERROR_SEVERITY if bool(duplicate_ids.any()) else "Info",
            [identifier],
            duplicate_ids,
            "Review repeated IDs against the source system before merging or removing records.",
            f"{int(identifier_values.str.strip().duplicated().sum()):,} repeated identifier row(s).",
        )
        surrounding_space = identifier_values.notna() & (
            identifier_values != identifier_values.str.strip()
        )
        add_check(
            "Identifier whitespace",
            "WARNING" if bool(surrounding_space.any()) else "PASS",
            WARNING_SEVERITY if bool(surrounding_space.any()) else "Info",
            [identifier],
            surrounding_space,
            "Trim surrounding whitespace only after checking that identifiers are not intentionally formatted.",
            f"{int(surrounding_space.sum()):,} identifier(s) with surrounding whitespace.",
        )

    numeric_text_columns: list[str] = []
    numeric_text_masks: list[pd.Series] = []
    for column in data.select_dtypes(include=["object", "string"]).columns:
        non_missing = data[column].dropna()
        if len(non_missing) < 2:
            continue
        converted = pd.to_numeric(non_missing, errors="coerce")
        if converted.notna().all() and non_missing.nunique() > 3:
            numeric_text_columns.append(column)
            numeric_text_masks.append(
                pd.to_numeric(data[column], errors="coerce").notna()
            )
    if numeric_text_columns:
        numeric_text_rows = pd.Series(False, index=data.index)
        for mask in numeric_text_masks:
            numeric_text_rows |= mask
        add_check(
            "Numeric-looking text columns",
            "WARNING",
            WARNING_SEVERITY,
            numeric_text_columns,
            numeric_text_rows,
            "Confirm the field meaning, then convert its type in the cleaning workspace.",
            "One or more text columns contain values that all parse as numbers.",
        )
    else:
        add_check(
            "Numeric-looking text columns",
            "PASS",
            "Info",
            [],
            None,
            "No strongly numeric-looking text columns were detected.",
            "No numeric type conversion was inferred.",
        )

    category_variant_columns: list[str] = []
    category_variant_rows = pd.Series(False, index=data.index)
    for column in data.select_dtypes(include=["object", "string", "category"]).columns:
        series = values_as_text(data[column])
        normalized = series.str.strip().str.casefold()
        variants = series.notna() & normalized.map(
            normalized.value_counts(dropna=True)
        ).gt(1)
        if bool(variants.any()):
            observed_variants = pd.DataFrame(
                {"original": series[variants], "normalized": normalized[variants]}
            )
            changed_labels = observed_variants.groupby("normalized")["original"].nunique()
            changed_labels = changed_labels[changed_labels > 1].index
            affected = variants & normalized.isin(changed_labels)
            if bool(affected.any()):
                category_variant_columns.append(column)
                category_variant_rows |= affected
    add_check(
        "Category case/whitespace variants",
        "WARNING" if category_variant_columns else "PASS",
        WARNING_SEVERITY if category_variant_columns else "Info",
        category_variant_columns,
        category_variant_rows,
        "Review spelling variants; standardize only when labels are known to represent the same category.",
        (
            f"Variants detected in {len(category_variant_columns)} column(s)."
            if category_variant_columns
            else "No case/whitespace-only label variants were found."
        ),
    )

    numeric = numeric_columns(data)
    semantic_negative_masks: list[pd.Series] = []
    semantic_negative_columns: list[str] = []
    semantic_terms = (
        "age",
        "tenure",
        "ticket",
        "charge",
        "revenue",
        "cost",
        "price",
        "amount",
    )
    for column in numeric:
        name = normalized_name(column)
        if any(term in name for term in semantic_terms):
            invalid_negative = data[column] < 0
            if bool(invalid_negative.any()):
                semantic_negative_columns.append(column)
                semantic_negative_masks.append(invalid_negative)
    if numeric:
        negative_rows = pd.Series(False, index=data.index)
        for mask in semantic_negative_masks:
            negative_rows |= mask
        add_check(
            "Negative age/tenure/ticket/charge values",
            "FAIL" if semantic_negative_columns else "PASS",
            ERROR_SEVERITY if semantic_negative_columns else "Info",
            semantic_negative_columns or [
                column
                for column in numeric
                if any(term in normalized_name(column) for term in semantic_terms)
            ],
            negative_rows,
            "Verify negative values with the source; correct only from authoritative records.",
            f"{int(negative_rows.sum()):,} row(s) have negative values in relevant numeric fields.",
        )
    else:
        add_check(
            "Negative numeric values",
            "NOT APPLICABLE",
            "Info",
            [],
            None,
            "No numeric columns are available.",
            "Numeric range checks were not evaluated.",
        )

    churn_column = find_column(
        data,
        {"churn", "churnstatus", "ischurned", "customerchurn", "attrition"},
    )
    recognized_churn = {"yes", "no", "true", "false", "1", "0", "churned", "retained"}
    if churn_column is None:
        add_check(
            "Churn label domain",
            "NOT APPLICABLE",
            "Info",
            [],
            None,
            "No common churn column was detected; no label values were assumed.",
            "Churn labels were not evaluated.",
        )
    else:
        churn_labels = values_as_text(data[churn_column]).str.strip().str.casefold()
        present_labels = set(churn_labels.dropna().unique())
        unknown_labels = churn_labels.notna() & ~churn_labels.isin(recognized_churn)
        recognized_present = present_labels.intersection(recognized_churn)
        if present_labels and not bool(unknown_labels.any()):
            churn_status = "PASS"
            churn_severity = "Info"
        elif recognized_present:
            churn_status = "FAIL"
            churn_severity = ERROR_SEVERITY
        else:
            churn_status = "WARNING" if present_labels else "NOT APPLICABLE"
            churn_severity = WARNING_SEVERITY if present_labels else "Info"
        add_check(
            "Recognized churn labels",
            churn_status,
            churn_severity,
            [churn_column],
            unknown_labels if churn_status in {"FAIL", "WARNING"} else None,
            "Confirm the allowed churn labels from the dataset guide; unknown label conventions are not guessed.",
            "Observed labels: "
            + (", ".join(sorted(str(value) for value in present_labels)) or "none")
            + ".",
        )

    iqr_rows: list[dict[str, Any]] = []
    all_outlier_rows = pd.Series(False, index=data.index)
    for column in numeric:
        values = data[column].dropna()
        if values.empty:
            iqr_rows.append(
                {
                    "Column": column,
                    "Q1": None,
                    "Q3": None,
                    "IQR": None,
                    "Lower bound": None,
                    "Upper bound": None,
                    "Flagged values": 0,
                    "Example values": "",
                }
            )
            continue
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        spread = q3 - q1
        lower = q1 - 1.5 * spread
        upper = q3 + 1.5 * spread
        flagged = data[column].lt(lower) | data[column].gt(upper)
        all_outlier_rows |= flagged.fillna(False)
        examples = data.loc[flagged, column].head(8).tolist()
        iqr_rows.append(
            {
                "Column": column,
                "Q1": q1,
                "Q3": q3,
                "IQR": spread,
                "Lower bound": lower,
                "Upper bound": upper,
                "Flagged values": int(flagged.sum()),
                "Example values": ", ".join(map(str, examples)),
            }
        )
    outlier_value_count = sum(row["Flagged values"] for row in iqr_rows)
    add_check(
        "Numerical outliers (1.5×IQR)",
        "WARNING" if outlier_value_count else ("PASS" if numeric else "NOT APPLICABLE"),
        WARNING_SEVERITY if outlier_value_count else "Info",
        numeric,
        all_outlier_rows,
        "Review potential outliers; unusual values are not automatically errors and are never removed here.",
        f"{outlier_value_count:,} numeric value(s) flagged across {int(all_outlier_rows.sum()):,} record(s).",
    )

    monthly_column = find_column(
        data, {"monthlycharges", "monthlycharge", "monthlyfee", "monthlycost"}
    )
    tenure_column = find_column(
        data, {"tenure", "tenuremonths", "monthsactive", "customer_tenure"}
    )
    total_column = find_column(
        data, {"totalcharges", "totalcharge", "totalcost", "amountpaid"}
    )
    if monthly_column and tenure_column and total_column:
        expected_total = data[monthly_column] * data[tenure_column]
        tolerance = expected_total.abs().mul(0.02).clip(lower=1.0)
        mismatch = (
            data[total_column].notna()
            & expected_total.notna()
            & (data[total_column] - expected_total).abs().gt(tolerance)
        )
        add_check(
            "Charges compared with monthly charges × tenure",
            "WARNING" if bool(mismatch.any()) else "PASS",
            WARNING_SEVERITY if bool(mismatch.any()) else "Info",
            [monthly_column, tenure_column, total_column],
            mismatch,
            "Investigate differences with the billing definition; the 2% or one-unit tolerance is an exploratory heuristic.",
            f"{int(mismatch.sum()):,} record(s) differ by more than max(2% or one charge unit).",
        )
    else:
        add_check(
            "Charges compared with monthly charges × tenure",
            "NOT APPLICABLE",
            "Info",
            [column for column in (monthly_column, tenure_column, total_column) if column],
            None,
            "This comparison requires recognizable monthly charge, tenure, and total charge columns.",
            "The required combination of fields was not detected.",
        )

    evaluated = [check for check in checks if check["Status"] != "NOT APPLICABLE"]
    passed = sum(check["Status"] == "PASS" for check in evaluated)
    score = (passed / len(evaluated) * 100) if evaluated else None
    if score is None:
        score_label = "Not enough applicable checks"
    elif score >= 90:
        score_label = "Excellent"
    elif score >= 75:
        score_label = "Good"
    elif score >= 50:
        score_label = "Needs Review"
    else:
        score_label = "Poor"

    review_rows = pd.Series(False, index=data.index)
    error_rows = pd.Series(False, index=data.index)
    for check in checks:
        mask = pd.Series(row_flags[check["_flag_key"]], index=data.index)
        if check["Status"] in {"FAIL", "WARNING"}:
            review_rows |= mask
        if check["Status"] == "FAIL":
            error_rows |= mask
    for check in checks:
        check.pop("_flag_key", None)

    missing_table = pd.DataFrame(
        {
            "Column": data.columns,
            "Missing cells": missing_by_column.to_numpy(),
            "Missing percent": [
                (count / n_rows * 100) if n_rows else 0
                for count in missing_by_column
            ],
            "Data type": [str(dtype) for dtype in data.dtypes],
        }
    )
    return {
        "checks": pd.DataFrame(checks),
        "missing": missing_table,
        "iqr": pd.DataFrame(iqr_rows),
        "missing_cells": missing_count,
        "duplicate_rows": duplicate_count,
        "identifier_column": identifier,
        "duplicate_ids": int(
            values_as_text(data[identifier]).str.strip().duplicated().sum()
        )
        if identifier
        else None,
        "invalid_count": int(error_rows.sum()),
        "outlier_count": int(all_outlier_rows.sum()),
        "outlier_value_count": int(outlier_value_count),
        "review_count": int(review_rows.sum()),
        "passed": passed,
        "failed": sum(check["Status"] == "FAIL" for check in evaluated),
        "warning_count": sum(check["Status"] == "WARNING" for check in evaluated),
        "evaluated_count": len(evaluated),
        "score": score,
        "score_label": score_label,
        "issue_rows": review_rows,
        "error_rows": error_rows,
        "monthly_column": monthly_column,
        "tenure_column": tenure_column,
        "total_column": total_column,
    }


def churn_values(data: pd.DataFrame, column: str) -> pd.Series:
    """Identify positive churn labels only when values follow known conventions."""
    normalized = values_as_text(data[column]).str.strip().str.casefold()
    positive = {"yes", "true", "1", "churned"}
    negative = {"no", "false", "0", "retained"}
    known = set(normalized.dropna().unique())
    if not known or not known.issubset(positive | negative):
        return pd.Series(False, index=data.index)
    return normalized.isin(positive)


def quality_report(
    data: pd.DataFrame,
    filename: str,
    assessment: dict[str, Any],
    modified_log: list[str],
) -> str:
    """Create a report for the currently selected session dataset."""
    checks = assessment["checks"]
    return "\n".join(
        [
            "# Customer Churn Data Quality Dashboard Report",
            "",
            f"- Dataset: `{filename}`",
            f"- Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
            f"- Dimensions: {len(data):,} rows × {len(data.columns):,} columns",
            f"- Data-quality score: {assessment['score']:.1f}% ({assessment['score_label']})"
            if assessment["score"] is not None
            else "- Data-quality score: Not available",
            "",
            "## Score definition",
            "",
            "The score is the percentage of evaluated dynamic rules with PASS status. "
            "Each evaluated rule has equal weight. WARNING and FAIL rules do not count "
            "as passed. NOT APPLICABLE rules are excluded from the denominator. This "
            "is a transparent rule summary, not a certified business-quality metric.",
            "",
            "## Data-quality checks",
            "",
            checks.to_markdown(index=False),
            "",
            "## Missing values",
            "",
            assessment["missing"].to_markdown(index=False),
            "",
            "## IQR outlier review",
            "",
            "Flags are review signals and do not automatically mean a value is invalid.",
            "",
            assessment["iqr"].to_markdown(index=False),
            "",
            "## Applied session transformations",
            "",
            *([f"- {item}" for item in modified_log] or ["- No cleaning changes applied."]),
            "",
            "The source file is preserved; cleaning actions affect only the session working copy.",
        ]
    )


def reset_explorer_state() -> None:
    """Clear explorer widgets before their next render."""
    for key in list(st.session_state):
        if key.startswith(("explorer_cat_", "explorer_range_")) or key in {
            "explorer_search",
            "explorer_display_columns",
            "explorer_sort_column",
            "explorer_sort_ascending",
            "explorer_page_size",
            "explorer_page_number",
            "explorer_detail",
        }:
            del st.session_state[key]


def filter_dataset(data: pd.DataFrame) -> pd.DataFrame:
    """Render dynamic explorer filters and return filtered data."""
    st.button(
        "Reset all filters",
        key="explorer_reset",
        on_click=reset_explorer_state,
    )

    search = st.text_input(
        "Search all columns",
        placeholder="Search customer ID, category, or value",
        key="explorer_search",
    )
    filtered = data
    if search.strip():
        matches = data.astype("string").fillna("").apply(
            lambda column: column.str.contains(
                search.strip(), case=False, regex=False
            )
        ).any(axis=1)
        filtered = filtered.loc[matches]

    categorical = [
        column
        for column in data.select_dtypes(include=["object", "string", "category"]).columns
        if data[column].nunique(dropna=True) <= 50
    ]
    if categorical:
        st.markdown("**Category filters**")
        columns = st.columns(min(3, len(categorical)))
        for position, column in enumerate(categorical):
            choices = sorted(data[column].dropna().unique().tolist(), key=str)
            missing_choice = "(Missing)"
            options: list[Any] = choices.copy()
            if data[column].isna().any():
                options.append(missing_choice)
            key = f"explorer_cat_{normalized_name(column)}"
            selected = columns[position % len(columns)].multiselect(
                column,
                options=options,
                default=options,
                key=key,
            )
            if len(selected) < len(options):
                keep_missing = missing_choice in selected
                selected_values = [value for value in selected if value != missing_choice]
                mask = filtered[column].isin(selected_values)
                if keep_missing:
                    mask |= filtered[column].isna()
                filtered = filtered.loc[mask]

    numbers = numeric_columns(data)
    if numbers:
        st.markdown("**Numeric range filters**")
        columns = st.columns(min(3, len(numbers)))
        for position, column in enumerate(numbers):
            values = data[column].dropna()
            if values.empty or values.min() == values.max():
                continue
            key = f"explorer_range_{normalized_name(column)}"
            low, high = columns[position % len(columns)].slider(
                column,
                min_value=float(values.min()),
                max_value=float(values.max()),
                value=(float(values.min()), float(values.max())),
                key=key,
            )
            filtered = filtered.loc[filtered[column].between(low, high)]
    return filtered


def apply_cleaning_options(
    data: pd.DataFrame,
    trim_whitespace: bool,
    case_mode: str,
    convert_columns: list[str],
    missing_columns: list[str],
    missing_strategy: str,
    remove_duplicates: bool,
    remove_error_rows: bool,
    flagged_error_rows: pd.Series,
) -> tuple[pd.DataFrame, list[str]]:
    """Apply selected transforms to a new copy and explain every change."""
    cleaned = data.copy(deep=True)
    changes: list[str] = []

    text_columns = cleaned.select_dtypes(include=["object", "string"]).columns.tolist()
    if trim_whitespace:
        affected: list[str] = []
        for column in text_columns:
            original = cleaned[column]
            trimmed = original.map(
                lambda value: value.strip() if isinstance(value, str) else value
            )
            if not original.equals(trimmed):
                cleaned[column] = trimmed
                affected.append(column)
        changes.append(
            "Trimmed surrounding whitespace in: "
            + (", ".join(affected) if affected else "no affected columns")
        )

    if case_mode != "Preserve":
        identifier = find_identifier_column(cleaned)
        targets = [
            column
            for column in cleaned.select_dtypes(include=["object", "string"]).columns
            if column != identifier
        ]
        for column in targets:
            cleaned[column] = cleaned[column].map(
                lambda value: (
                    value.upper()
                    if isinstance(value, str) and case_mode == "UPPERCASE"
                    else value.lower()
                    if isinstance(value, str) and case_mode == "lowercase"
                    else value.title()
                    if isinstance(value, str) and case_mode == "Title Case"
                    else value
                )
            )
        changes.append(f"Standardized text capitalization to {case_mode} in non-ID text columns.")

    for column in convert_columns:
        if column in cleaned:
            before = cleaned[column]
            converted = pd.to_numeric(before, errors="coerce")
            changed = int((before.notna() & converted.isna()).sum())
            cleaned[column] = converted
            changes.append(
                f"Converted `{column}` to numeric; {changed} nonnumeric value(s) became missing."
            )

    if missing_strategy != "Leave unchanged":
        for column in missing_columns:
            if column not in cleaned or not cleaned[column].isna().any():
                continue
            missing_count = int(cleaned[column].isna().sum())
            if missing_strategy == "Median / most frequent":
                if pd.api.types.is_numeric_dtype(cleaned[column]):
                    fill_value = cleaned[column].median()
                else:
                    modes = cleaned[column].mode(dropna=True)
                    fill_value = modes.iloc[0] if not modes.empty else pd.NA
            elif missing_strategy == "Zero / Not provided":
                fill_value = 0 if pd.api.types.is_numeric_dtype(cleaned[column]) else "Not provided"
            else:
                continue
            if pd.notna(fill_value):
                cleaned[column] = cleaned[column].fillna(fill_value)
                changes.append(
                    f"Filled {missing_count} missing value(s) in `{column}` using `{fill_value}` ({missing_strategy})."
                )

    if remove_error_rows and len(flagged_error_rows) == len(cleaned):
        count = int(flagged_error_rows.sum())
        cleaned = cleaned.loc[~flagged_error_rows.to_numpy()].reset_index(drop=True)
        changes.append(f"Removed {count} row(s) flagged by deterministic error checks.")

    if remove_duplicates:
        count = int(cleaned.duplicated().sum())
        cleaned = cleaned.drop_duplicates().reset_index(drop=True)
        changes.append(f"Removed {count} exact duplicate row(s).")

    if not changes:
        changes.append("No transformations selected.")
    return cleaned, changes


def render_overview(
    data: pd.DataFrame,
    filename: str,
    file_size: int,
    loaded_at: str,
    assessment: dict[str, Any],
) -> None:
    """Render executive metrics and compact dataset profile."""
    st.header("Dashboard Overview")
    score_text = (
        f"{assessment['score']:.1f}%"
        if assessment["score"] is not None
        else "N/A"
    )
    churn_column = find_column(
        data,
        {"churn", "churnstatus", "ischurned", "customerchurn", "attrition"},
    )
    if churn_column is not None:
        labels = values_as_text(data[churn_column]).str.strip().str.casefold()
        recognized = {
            "yes",
            "no",
            "true",
            "false",
            "1",
            "0",
            "churned",
            "retained",
        }
        if set(labels.dropna().unique()).issubset(recognized) and labels.notna().any():
            churn_mask = churn_values(data, churn_column)
            churn_rate = f"{churn_mask.sum() / labels.notna().sum():.1%}"
        else:
            churn_rate = "N/A"
    else:
        churn_rate = "N/A"

    st.markdown(
        f"""
        <div class="dataset-banner">
          <div><b>Active dataset</b><br>{filename}</div>
          <div><b>File size</b><br>{file_size / 1024:,.1f} KB</div>
          <div><b>Loaded</b><br>{loaded_at}</div>
          <div><b>Quality status</b><br>{assessment['score_label']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metrics = st.columns(5)
    metrics[0].metric("Total records", f"{len(data):,}")
    metrics[1].metric("Total columns", f"{len(data.columns):,}")
    metrics[2].metric("Missing cells", f"{assessment['missing_cells']:,}")
    metrics[3].metric("Exact duplicate rows", f"{assessment['duplicate_rows']:,}")
    metrics[4].metric("Data-quality score", score_text)
    second = st.columns(6)
    second[0].metric(
        "Duplicate customer IDs",
        str(assessment["duplicate_ids"])
        if assessment["duplicate_ids"] is not None
        else "N/A",
    )
    second[1].metric("Invalid records", f"{assessment['invalid_count']:,}")
    second[2].metric("IQR outlier values", f"{assessment['outlier_value_count']:,}")
    second[3].metric("Records requiring review", f"{assessment['review_count']:,}")
    second[4].metric(
        "Active rules passed",
        f"{assessment['passed']}/{assessment['evaluated_count']}",
    )
    second[5].metric("Churn rate", churn_rate)

    if assessment["score"] is not None:
        st.progress(
            min(100, max(0, int(round(assessment["score"])))),
            text=(
                f"Assessment status: {assessment['score_label']} · "
                f"{assessment['passed']} passed, {assessment['failed']} failed, "
                f"{assessment['warning_count']} warning(s), "
                f"{len(assessment['checks']) - assessment['evaluated_count']} not applicable"
            ),
        )
    st.caption(
        "Score method: PASS checks ÷ evaluated checks × 100; equal weight per "
        "check. Warnings and failures are not passes; not-applicable checks "
        "are excluded. Status bands: Excellent ≥90%, Good ≥75%, Needs Review "
        "≥50%, Poor <50%."
    )

    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("Missing values by column")
        missing = assessment["missing"]
        plot_data = missing.loc[missing["Missing cells"] > 0]
        if plot_data.empty:
            st.success(
                f"No missing cells found across {len(data.columns)} columns."
            )
        else:
            figure = px.bar(
                plot_data.sort_values("Missing cells"),
                x="Missing cells",
                y="Column",
                orientation="h",
                hover_data=["Missing percent", "Data type"],
                color_discrete_sequence=[BLUE],
                title="Missing cells and percentages",
            )
            figure.update_layout(margin=dict(l=10, r=10, t=55, b=10))
            st.plotly_chart(figure, use_container_width=True, key="overview_missing")
    with right:
        st.subheader("Issue severity")
        severity_counts = (
            assessment["checks"]
            .loc[assessment["checks"]["Status"].isin(["FAIL", "WARNING"])]
            .groupby(["Severity", "Status"], dropna=False)
            .size()
            .reset_index(name="Rules")
        )
        if severity_counts.empty:
            st.success("No warning or failed rules were reported.")
        else:
            figure = px.bar(
                severity_counts,
                x="Severity",
                y="Rules",
                color="Status",
                color_discrete_map={"FAIL": RED, "WARNING": AMBER},
                title="Rules needing attention",
                text="Rules",
            )
            figure.update_layout(margin=dict(l=10, r=10, t=55, b=10))
            st.plotly_chart(figure, use_container_width=True, key="overview_severity")

    st.subheader("Dataset dimensions and columns")
    st.write(f"**{len(data):,} rows × {len(data.columns):,} columns**")
    st.code(" · ".join(map(str, data.columns)), language=None)
    dtype_table = pd.DataFrame(
        {
            "Column": data.columns,
            "Data type": [str(dtype) for dtype in data.dtypes],
            "Missing cells": data.isna().sum().to_numpy(),
            "Missing percent": [
                (int(data[column].isna().sum()) / len(data) * 100) if len(data) else 0
                for column in data.columns
            ],
        }
    )
    st.dataframe(dtype_table, use_container_width=True, hide_index=True)


def render_quality(data: pd.DataFrame, assessment: dict[str, Any]) -> None:
    st.header("Data Quality")
    st.caption(
        "Rules are inferred only from recognizable column names and general "
        "data consistency. No universal mandatory-column list is imposed."
    )
    missing_tab, checks_tab, outliers_tab = st.tabs(
        ["Completeness", "Rules and issues", "Outlier review"]
    )
    with missing_tab:
        st.metric(
            "Completeness",
            f"{100 * (1 - assessment['missing_cells'] / max(1, data.size)):.1f}%",
        )
        st.dataframe(
            assessment["missing"],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Missing percent": st.column_config.ProgressColumn(
                    "Missing percent", min_value=0, max_value=100, format="%.1f%%"
                )
            },
        )
    with checks_tab:
        frame = assessment["checks"]
        counts = frame["Status"].value_counts().reindex(STATUS_ORDER, fill_value=0)
        cols = st.columns(4)
        for col, status in zip(cols, STATUS_ORDER):
            col.metric(status.title(), int(counts[status]))
        show_only = st.multiselect(
            "Filter rule statuses",
            options=STATUS_ORDER,
            default=STATUS_ORDER,
            key="quality_status_filter",
        )
        st.dataframe(
            frame.loc[frame["Status"].isin(show_only)],
            use_container_width=True,
            hide_index=True,
        )
        st.info(
            "The charge consistency rule is a review heuristic: it compares "
            "total charges with monthly charges × tenure using a tolerance of "
            "the greater of 2% or one charge unit. Confirm billing semantics "
            "before treating a mismatch as erroneous."
        )
    with outliers_tab:
        if assessment["iqr"].empty:
            st.info("No numeric columns were detected; IQR screening is not applicable.")
        else:
            st.caption(
                "The 1.5×IQR rule flags statistical extremes for review. It does "
                "not prove values are invalid and does not remove records."
            )
            st.dataframe(assessment["iqr"], use_container_width=True, hide_index=True)
            numeric = numeric_columns(data)
            if numeric:
                selected = st.multiselect(
                    "Numeric columns for box plots",
                    options=numeric,
                    default=numeric[: min(4, len(numeric))],
                    key="quality_box_columns",
                )
                if selected:
                    figure = go.Figure()
                    for column in selected:
                        figure.add_trace(
                            go.Box(
                                y=data[column],
                                name=column,
                                boxpoints="outliers",
                                marker_color=PALETTE[len(figure.data) % len(PALETTE)],
                                hovertemplate=f"{column}: %{{y}}<extra></extra>",
                            )
                        )
                    figure.update_layout(
                        title="Numeric distributions and potential outliers",
                        yaxis_title="Observed value",
                        showlegend=False,
                    )
                    st.plotly_chart(figure, use_container_width=True, key="quality_boxes")

    flagged = data.loc[assessment["issue_rows"]]
    st.subheader(f"Records for review ({len(flagged):,})")
    if flagged.empty:
        st.success("No records were flagged by the evaluated warning/error checks.")
    else:
        st.dataframe(flagged, use_container_width=True, hide_index=True)


def render_churn(data: pd.DataFrame) -> None:
    st.header("Churn Analytics")
    churn_column = find_column(
        data,
        {"churn", "churnstatus", "ischurned", "customerchurn", "attrition"},
    )
    if churn_column is None:
        st.info(
            "No recognizable churn field was found. Churn charts are not "
            "available for this dataset."
        )
        return
    churn_mask = churn_values(data, churn_column)
    normalized = values_as_text(data[churn_column]).str.strip().str.casefold()
    recognized = {"yes", "no", "true", "false", "1", "0", "churned", "retained"}
    labels = set(normalized.dropna().unique())
    if not labels.issubset(recognized):
        st.warning(
            f"`{churn_column}` includes labels outside the recognized binary "
            "conventions. Confirm the label meanings before interpreting churn rates."
        )
        return

    left, right = st.columns(2)
    with left:
        st.subheader("Churned and retained")
        counts = data[churn_column].value_counts(dropna=False).rename_axis("Label").reset_index(name="Customers")
        figure = px.pie(
            counts,
            names="Label",
            values="Customers",
            hole=0.55,
            color_discrete_sequence=[BLUE, PURPLE, "#A8B4C4"],
            title="Customer distribution by churn label",
        )
        figure.update_traces(textposition="inside", textinfo="label+value+percent")
        st.plotly_chart(figure, use_container_width=True, key="churn_distribution")

    def render_rate_chart(group_column: str, chart_key: str) -> None:
        chart_data = data.assign(_is_churned=churn_mask).groupby(
            group_column, dropna=False
        ).agg(
            customers=("_is_churned", "size"),
            churned=("_is_churned", "sum"),
            churn_rate=("_is_churned", "mean"),
        ).reset_index()
        chart_data["churn_rate_percent"] = chart_data["churn_rate"] * 100
        figure = px.bar(
            chart_data,
            x=group_column,
            y="churn_rate_percent",
            color=group_column,
            hover_data={"customers": True, "churned": True, "churn_rate": ":.1%"},
            title=f"Observed churn rate by {group_column}",
            labels={"churn_rate_percent": "Churn rate (%)"},
            color_discrete_sequence=PALETTE,
        )
        figure.update_layout(showlegend=False, yaxis_ticksuffix="%")
        st.plotly_chart(figure, use_container_width=True, key=chart_key)

    common_groups = [
        find_column(data, {"contracttype", "contract"}),
        find_column(data, {"subscriptiontype", "subscription", "plantype"}),
        find_column(data, {"paymentmethod", "paymenttype", "payment"}),
    ]
    common_groups = list(dict.fromkeys(
        column
        for column in common_groups
        if column is not None
        and column != churn_column
        and data[column].nunique(dropna=True) <= 40
    ))
    st.subheader("Churn rate by contract, subscription, and payment")
    if common_groups:
        group_columns = st.columns(min(3, len(common_groups)))
        for position, (column, slot) in enumerate(zip(common_groups, group_columns)):
            with slot:
                render_rate_chart(column, f"churn_common_group_{position}")
    else:
        st.info(
            "Contract type, subscription type, and payment method comparisons "
            "are not available because recognizable grouping fields were not found."
        )

    other_groups = [
        column
        for column in data.select_dtypes(include=["object", "string", "category"]).columns
        if column != churn_column
        and column not in common_groups
        and data[column].nunique(dropna=True) <= 40
    ]
    if other_groups:
        group_column = st.selectbox(
            "Explore churn by another category",
            options=other_groups,
            key="churn_group_column",
        )
        render_rate_chart(group_column, "churn_other_group")

    st.subheader("Numeric distributions")
    numeric = numeric_columns(data)
    if numeric:
        selected_numeric = st.multiselect(
            "Choose numeric fields to compare",
            options=numeric,
            default=numeric[: min(4, len(numeric))],
            key="churn_numeric_columns",
        )
        if selected_numeric:
            numeric_long = data[selected_numeric].melt(
                var_name="Measure", value_name="Value"
            ).dropna()
            figure = px.histogram(
                numeric_long,
                x="Value",
                facet_col="Measure",
                facet_col_wrap=2,
                color="Measure",
                color_discrete_sequence=PALETTE,
                title="Distributions for selected numerical fields",
            )
            figure.update_layout(showlegend=False)
            st.plotly_chart(figure, use_container_width=True, key="churn_numeric_dist")
        correlation = data[numeric].corr()
        if len(numeric) > 1:
            heatmap = go.Figure(
                data=go.Heatmap(
                    z=correlation.to_numpy(),
                    x=correlation.columns,
                    y=correlation.index,
                    zmin=-1,
                    zmax=1,
                    colorscale="RdBu",
                    colorbar_title="Correlation",
                    hovertemplate="%{y} × %{x}: %{z:.2f}<extra></extra>",
                )
            )
            heatmap.update_layout(title="Numeric correlation heatmap")
            st.plotly_chart(heatmap, use_container_width=True, key="churn_corr")
    else:
        st.info("No numeric fields are available for distribution or correlation plots.")
    st.caption(
        "These are descriptive comparisons of the active dataset. They do not "
        "establish causation or representativeness."
    )


def render_data_explorer(data: pd.DataFrame, assessment: dict[str, Any]) -> None:
    st.header("Data Explorer")
    filtered = filter_dataset(data)
    st.caption(f"**{len(filtered):,} matching records** out of {len(data):,}")
    if filtered.empty:
        st.info("No records match the current search and filters.")
        return

    st.subheader("Charts for matching records")
    filtered_churn = find_column(
        filtered,
        {"churn", "churnstatus", "ischurned", "customerchurn", "attrition"},
    )
    if filtered_churn:
        filtered_categories = filtered[filtered_churn].value_counts(
            dropna=False
        ).rename_axis("Churn status").reset_index(name="Records")
        figure = px.bar(
            filtered_categories,
            x="Churn status",
            y="Records",
            color="Churn status",
            color_discrete_sequence=PALETTE,
            text="Records",
            title="Churn labels in the filtered records",
        )
        st.plotly_chart(figure, use_container_width=True, key="explorer_filtered_churn")
    filtered_numeric = numeric_columns(filtered)
    if filtered_numeric:
        selected_chart_column = st.selectbox(
            "Numeric chart for filtered records",
            options=filtered_numeric,
            key="explorer_chart_column",
        )
        figure = px.histogram(
            filtered,
            x=selected_chart_column,
            color_discrete_sequence=[PURPLE],
            title=f"{selected_chart_column} distribution in the filtered records",
        )
        st.plotly_chart(figure, use_container_width=True, key="explorer_filtered_numeric")

    options = list(data.columns)
    display_columns = st.multiselect(
        "Columns to display",
        options=options,
        default=options,
        key="explorer_display_columns",
    )
    if not display_columns:
        st.warning("Select at least one column to display.")
        return
    sort_column = st.selectbox(
        "Sort by",
        options=display_columns,
        key="explorer_sort_column",
    )
    ascending = st.toggle("Sort ascending", value=True, key="explorer_sort_ascending")
    sorted_data = filtered.sort_values(sort_column, ascending=ascending, na_position="last")

    page_size = st.selectbox(
        "Rows per page",
        options=[10, 25, 50, 100],
        index=0,
        key="explorer_page_size",
    )
    page_count = max(1, (len(sorted_data) + page_size - 1) // page_size)
    page_number = st.number_input(
        "Page",
        min_value=1,
        max_value=page_count,
        value=1,
        step=1,
        key="explorer_page_number",
    )
    first = (int(page_number) - 1) * page_size
    page = sorted_data.iloc[first : first + page_size]
    def highlight_review_rows(row: pd.Series) -> list[str]:
        if bool(assessment["issue_rows"].iloc[row.name]):
            return ["background-color: #FFF1D6"] * len(row)
        return [""] * len(row)

    styled_page = page[display_columns].style.apply(
        highlight_review_rows,
        axis=1,
    )
    st.dataframe(
        styled_page,
        use_container_width=True,
        hide_index=True,
    )

    csv_bytes = sorted_data[display_columns].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export filtered records as CSV",
        data=csv_bytes,
        file_name="filtered_customer_data.csv",
        mime="text/csv",
        key="explorer_download",
    )

    if not sorted_data.empty:
        id_column = assessment["identifier_column"]
        record_choices = sorted_data.index.tolist()
        if id_column and id_column in sorted_data.columns:
            labels = {
                index: f"{sorted_data.at[index, id_column]} (row {index + 1})"
                for index in record_choices
            }
            chosen = st.selectbox(
                "Inspect a record",
                options=record_choices,
                format_func=lambda index: labels[index],
                key="explorer_detail",
            )
        else:
            chosen = st.selectbox(
                "Inspect a record",
                options=record_choices,
                format_func=lambda index: f"Record {index + 1}",
                key="explorer_detail",
            )
        with st.expander("Selected record details", expanded=False):
            record = sorted_data.loc[chosen]
            st.json({str(key): (None if pd.isna(value) else value) for key, value in record.items()})
            if bool(assessment["issue_rows"].iloc[chosen]):
                st.warning("This record is flagged by one or more quality checks.")
            else:
                st.success("No evaluated quality rule flagged this record.")


def render_cleaning_workspace(
    original_data: pd.DataFrame,
    working_data: pd.DataFrame,
    assessment: dict[str, Any],
) -> None:
    st.header("Safe Cleaning Workspace")
    st.caption(
        "Changes are proposed against a separate in-session working copy. The "
        "uploaded/source file is never overwritten. Outliers remain untouched."
    )
    identifier = find_identifier_column(working_data)
    text_columns = working_data.select_dtypes(include=["object", "string"]).columns.tolist()
    numeric_text = working_data.select_dtypes(include=["object", "string"]).columns.tolist()
    numeric_text = [
        column
        for column in numeric_text
        if working_data[column].dropna().size
        and pd.to_numeric(working_data[column].dropna(), errors="coerce").notna().all()
    ]
    columns_with_missing = working_data.columns[working_data.isna().any()].tolist()

    trim = st.checkbox("Trim surrounding whitespace in text values", value=True)
    case_mode = st.selectbox(
        "Category capitalization",
        options=["Preserve", "Title Case", "lowercase", "UPPERCASE"],
        help="ID columns are excluded from case conversion.",
    )
    convert = st.multiselect(
        "Convert numeric-looking text columns",
        options=numeric_text,
        default=[],
    )
    missing_columns = st.multiselect(
        "Columns eligible for missing-value handling",
        options=columns_with_missing,
        default=[],
    )
    missing_strategy = st.selectbox(
        "Missing-value strategy",
        options=["Leave unchanged", "Median / most frequent", "Zero / Not provided"],
    )
    remove_duplicates = st.checkbox(
        "Remove exact duplicate rows in the working copy",
        value=False,
        disabled=not bool(working_data.duplicated().any()),
    )
    remove_errors = st.checkbox(
        "Remove rows flagged by deterministic error checks",
        value=False,
        help="Only failed data-error rules are considered. Warnings and outliers are not deleted.",
        disabled=not bool(assessment["error_rows"].any()),
    )
    st.caption(
        f"Identifier column detected: `{identifier}`."
        if identifier
        else "No common ID column detected; duplicate-ID rules are not applicable."
    )

    if st.button("Preview proposed changes", type="primary", key="clean_preview"):
        preview, changes = apply_cleaning_options(
            working_data,
            trim,
            case_mode,
            convert,
            missing_columns,
            missing_strategy,
            remove_duplicates,
            remove_errors,
            assessment["error_rows"],
        )
        st.session_state["clean_preview_data"] = preview
        st.session_state["clean_preview_changes"] = changes
        st.session_state["clean_preview_signature"] = (
            trim,
            case_mode,
            tuple(convert),
            tuple(missing_columns),
            missing_strategy,
            remove_duplicates,
            remove_errors,
            len(working_data),
            len(working_data.columns),
            tuple(working_data.columns),
        )

    signature = (
        trim,
        case_mode,
        tuple(convert),
        tuple(missing_columns),
        missing_strategy,
        remove_duplicates,
        remove_errors,
        len(working_data),
        len(working_data.columns),
        tuple(working_data.columns),
    )
    preview = st.session_state.get("clean_preview_data")
    preview_changes = st.session_state.get("clean_preview_changes", [])
    pending_signature = st.session_state.get("clean_preview_signature")
    if preview is not None:
        if pending_signature != signature:
            st.warning("Cleaning options changed. Create a new preview before applying.")
        else:
            st.subheader("Proposed change summary")
            for change in preview_changes:
                st.write(f"- {change}")
            change_frame = pd.DataFrame(
                [
                    {"Measure": "Rows", "Before": len(working_data), "After": len(preview)},
                    {"Measure": "Columns", "Before": len(working_data.columns), "After": len(preview.columns)},
                    {"Measure": "Missing cells", "Before": int(working_data.isna().sum().sum()), "After": int(preview.isna().sum().sum())},
                    {"Measure": "Exact duplicate rows", "Before": int(working_data.duplicated().sum()), "After": int(preview.duplicated().sum())},
                ]
            )
            st.dataframe(change_frame, use_container_width=True, hide_index=True)
            with st.expander("Compare first rows before and after", expanded=True):
                before_col, after_col = st.columns(2)
                before_col.caption("Current working copy")
                before_col.dataframe(working_data.head(10), use_container_width=True, hide_index=True)
                after_col.caption("Proposed working copy")
                after_col.dataframe(preview.head(10), use_container_width=True, hide_index=True)
            confirm = st.checkbox(
                "I reviewed the preview and confirm applying these changes to the session working copy.",
                key="clean_confirm",
            )
            if st.button(
                "Apply proposed changes",
                disabled=not confirm,
                key="clean_apply",
            ):
                st.session_state["working_data"] = preview.copy(deep=True)
                st.session_state["cleaning_log"].extend(preview_changes)
                st.session_state["clean_preview_data"] = None
                st.session_state["clean_preview_changes"] = []
                st.session_state["clean_preview_signature"] = None
                st.session_state["working_version"] += 1
                st.success("Changes applied to the session working copy only.")
                st.rerun()

    left, right = st.columns(2)
    with left:
        st.subheader("Current working copy")
        st.dataframe(working_data.head(10), use_container_width=True, hide_index=True)
    with right:
        st.subheader("Original upload/sample")
        st.dataframe(original_data.head(10), use_container_width=True, hide_index=True)

    if st.session_state.get("cleaning_log"):
        with st.expander("Applied transformation log", expanded=True):
            for item in st.session_state["cleaning_log"]:
                st.write(f"- {item}")
    if st.button("Restore working copy from original", key="clean_restore"):
        st.session_state["working_data"] = original_data.copy(deep=True)
        st.session_state["cleaning_log"] = []
        st.session_state["clean_preview_data"] = None
        st.session_state["clean_preview_changes"] = []
        st.session_state["clean_preview_signature"] = None
        st.session_state["working_version"] += 1
        st.success("Restored the working copy. Original data was not changed.")
        st.rerun()

    st.download_button(
        "Download current working copy as CSV",
        data=working_data.to_csv(index=False).encode("utf-8"),
        file_name="cleaned_working_copy.csv",
        mime="text/csv",
        key="clean_download",
    )


def render_validation(assessment: dict[str, Any], saved_validation: list[dict[str, str]]) -> None:
    st.header("Validation Results")
    checks = assessment["checks"]
    counts = checks["Status"].value_counts().reindex(STATUS_ORDER, fill_value=0)
    cards = st.columns(4)
    for column, status in zip(cards, STATUS_ORDER):
        column.metric(status.title(), int(counts[status]))

    if assessment["failed"] == 0 and assessment["warning_count"] == 0:
        st.success(
            f"All {assessment['passed']} evaluated data-quality rules passed."
        )
    elif assessment["failed"]:
        st.error(
            f"{assessment['failed']} evaluated rule(s) failed. Review the affected records."
        )
    else:
        st.warning(
            f"No hard failures, but {assessment['warning_count']} warning(s) need review."
        )

    st.subheader("Active dataset checks")
    st.dataframe(checks, use_container_width=True, hide_index=True)
    if saved_validation:
        st.subheader("Saved project validation file")
        st.caption(
            "These checks were generated for the original project sample, not "
            "for an uploaded file or session-only cleaning changes."
        )
        st.dataframe(
            pd.DataFrame(saved_validation),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No saved validation results file is available.")


def render_reports(
    data: pd.DataFrame,
    filename: str,
    assessment: dict[str, Any],
    original_data: pd.DataFrame,
) -> None:
    st.header("Reports")
    report = quality_report(
        data,
        filename,
        assessment,
        st.session_state.get("cleaning_log", []),
    )
    st.download_button(
        "Download active dataset quality report",
        data=report.encode("utf-8"),
        file_name="active_dataset_quality_report.md",
        mime="text/markdown",
        key="report_download",
    )
    st.download_button(
        "Download active dataset as CSV",
        data=data.to_csv(index=False).encode("utf-8"),
        file_name="active_dataset.csv",
        mime="text/csv",
        key="active_data_download",
    )
    if SUMMARY_FILE.is_file():
        with st.expander("Existing project report"):
            st.markdown(SUMMARY_FILE.read_text(encoding="utf-8"))
    existing_charts = [path for path in SAVED_CHARTS if path.is_file()]
    if existing_charts:
        st.subheader("Existing project charts")
        columns = st.columns(len(existing_charts))
        for column, image_path in zip(columns, existing_charts):
            column.image(
                str(image_path),
                caption=image_path.stem.replace("_", " ").title(),
                use_column_width=True,
            )


def main() -> None:
    """Render the app and its interactive dataset workspace."""
    st.markdown(
        """
        <style>
        [data-testid="stMainBlockContainer"] {padding-top: 1rem; max-width: 1480px;}
        .dataset-banner {
            display:flex; flex-wrap:wrap; gap:1.2rem; justify-content:space-between;
            background:var(--secondary-background-color); border:1px solid #dce4ef;
            border-left:4px solid #3478F6; border-radius:10px; padding:12px 16px;
            margin:0.2rem 0 1rem 0; color:var(--text-color); font-size:0.9rem;
        }
        div[data-testid="stMetric"] {
            background:var(--secondary-background-color); border:1px solid #dce4ef;
            border-radius:10px; padding:12px 14px;
            box-shadow:0 2px 8px rgba(20,36,58,0.05);
        }
        [data-testid="stDataFrame"] {border:1px solid #dce4ef; border-radius:8px;}
        @media(max-width:700px) {
            [data-testid="stMainBlockContainer"] {padding-left:0.8rem; padding-right:0.8rem;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("Customer Churn Data Quality Dashboard")
    st.caption("Data Quality Assessment and Validation Report")

    with st.sidebar:
        st.title("Data Quality")
        st.caption("Customer Churn Analytics")
        theme = st.radio(
            "Appearance",
            options=["Light", "Dark"],
            horizontal=True,
            key="theme_choice",
        )
        if theme == "Dark":
            st.markdown(
                """
                <style>
                .stApp {background:#101B2B; color:#E8EEF8;}
                h1,h2,h3,p,label,[data-testid="stMetricLabel"],[data-testid="stMetricValue"] {
                    color:#E8EEF8 !important;
                }
                [data-testid="stMetric"] {border-color:#314158; box-shadow:none;}
                [data-testid="stDataFrame"] {border-color:#314158;}
                </style>
                """,
                unsafe_allow_html=True,
            )
        st.divider()
        source_choice = st.radio(
            "Dataset source",
            options=["Project sample", "Upload a file"],
            key="dataset_source",
        )
        uploaded = None
        if source_choice == "Upload a file":
            uploaded = st.file_uploader(
                "Upload CSV or Excel",
                type=["csv", "xlsx"],
                help="Files are read in this local Streamlit session and are not uploaded by this code to an external service.",
            )
        navigation = st.radio(
            "Navigate",
            options=[
                "Dashboard Overview",
                "Data Quality",
                "Data Explorer",
                "Churn Analytics",
                "Validation Results",
                "Cleaning Workspace",
                "Reports",
            ],
            key="navigation",
        )

    if source_choice == "Project sample":
        if not SAMPLE_CSV.is_file():
            st.error(
                f"Project sample `{SAMPLE_CSV.name}` is missing. Place it in "
                "the project folder or select Upload a file."
            )
            st.stop()
        try:
            source_data = read_sample_csv(
                str(SAMPLE_CSV), SAMPLE_CSV.stat().st_mtime_ns
            )
            filename = SAMPLE_CSV.name
            file_size = SAMPLE_CSV.stat().st_size
            dataset_key = f"sample:{SAMPLE_CSV.stat().st_mtime_ns}"
        except (
            pd.errors.ParserError,
            pd.errors.EmptyDataError,
            UnicodeDecodeError,
            OSError,
        ) as error:
            st.error(f"Could not read project sample: {error}")
            st.stop()
    else:
        if uploaded is None:
            st.info("Choose a CSV or Excel file above, or switch back to Project sample.")
            st.stop()
        filename = uploaded.name
        content = uploaded.getvalue()
        extension = Path(filename).suffix.casefold()
        dataset_key = f"upload:{sha256(content).hexdigest()}"
        try:
            source_data = parse_uploaded_dataset(content, extension)
        except ValueError as error:
            st.error(str(error))
            st.stop()
        file_size = len(content)

    if len(source_data.columns) == 0:
        st.error("The active dataset has no usable columns.")
        st.stop()
    source_data = source_data.reset_index(drop=True)

    if st.session_state.get("dataset_key") != dataset_key:
        st.session_state["dataset_key"] = dataset_key
        st.session_state["original_data"] = source_data.copy(deep=True)
        st.session_state["working_data"] = source_data.copy(deep=True)
        st.session_state["cleaning_log"] = []
        st.session_state["working_version"] = 0
        st.session_state["dataset_loaded_at"] = datetime.now().astimezone().strftime(
            "%Y-%m-%d %H:%M %Z"
        )
        st.session_state["clean_preview_data"] = None
        st.session_state["clean_preview_changes"] = []
        st.session_state["clean_preview_signature"] = None

    original_data = st.session_state["original_data"]
    working_data = st.session_state["working_data"]
    assessment = assess_quality(working_data)
    saved_validation: list[dict[str, str]] = []
    if VALIDATION_FILE.is_file():
        try:
            for line in VALIDATION_FILE.read_text(encoding="utf-8").splitlines():
                match = re.match(r"^(PASS|FAIL|WARNING|NOT APPLICABLE):\s*(.*)", line)
                if match:
                    saved_validation.append(
                        {"Status": match.group(1), "Rule": match.group(2)}
                    )
        except OSError as error:
            st.warning(f"Could not read saved validation results: {error}")

    with st.sidebar:
        st.divider()
        st.markdown(f"**Active file:** `{filename}`")
        st.caption(f"{len(working_data):,} rows · {len(working_data.columns):,} columns · {file_size / 1024:,.1f} KB")
        st.caption(
            f"Loaded: {st.session_state['dataset_loaded_at']}"
        )
        st.caption("Changes made in Cleaning Workspace stay in this session until reset.")

    if navigation == "Dashboard Overview":
        render_overview(
            working_data,
            filename,
            file_size,
            st.session_state["dataset_loaded_at"],
            assessment,
        )
    elif navigation == "Data Quality":
        render_quality(working_data, assessment)
    elif navigation == "Data Explorer":
        render_data_explorer(working_data, assessment)
    elif navigation == "Churn Analytics":
        render_churn(working_data)
    elif navigation == "Validation Results":
        render_validation(assessment, saved_validation)
    elif navigation == "Cleaning Workspace":
        render_cleaning_workspace(original_data, working_data, assessment)
    elif navigation == "Reports":
        render_reports(working_data, filename, assessment, original_data)

    st.caption(
        "Quality indicators are descriptive. Business-specific validity and "
        "cleaning choices require an authoritative dataset guide."
    )


if __name__ == "__main__":
    main()
