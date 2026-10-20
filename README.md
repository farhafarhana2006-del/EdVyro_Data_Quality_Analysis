# Customer Churn Data Quality and Exploratory Analysis

## Project objective

This beginner-friendly project audits the supplied EdVyro customer churn sample, creates a reproducible analysis-ready CSV, validates the exported file, and summarizes initial patterns. It uses descriptive analysis only; it does not train a churn prediction model.

## Dataset

The supplied file is `customer_churn_sample (1).csv`. The task guide describes the customer records as synthetic. The inspected file contains 15 rows and 11 columns. It includes a `CustomerID` identifier and customer attributes such as age, tenure, subscription, charges, contract type, support tickets, payment method, and churn label.

The original CSV is read-only from the analysis script's perspective: the script reads it and writes a separate `cleaned_customer_churn.csv` output. Check the EdVyro task page's terms before redistributing the supplied CSV in a public repository.

## Tools

- Python 3
- pandas for reading, profiling, summarizing, and validating tabular data
- matplotlib for charts
- Standard Python libraries for file paths and error messages

## Data-quality checks

The script reports the dataset shape, columns, data types, first five rows, missing values, exact duplicate rows, and category labels that differ only by case or surrounding whitespace. It checks numeric columns for exploratory outliers using the 1.5×IQR rule and reports the bounds and any flagged values without deleting them.

It also calculates numeric descriptive statistics and categorical frequency distributions, then compares the observed `Churn` labels by `ContractType` when both columns exist.

## Cleaning decisions

The supplied task guide asks for cleaning with documented assumptions but does not define business-valid ranges, allowed category lists, missing-value imputation, or deletion rules. The inspected sample had no missing cells, exact duplicate rows, category spelling variations flagged by the script, or numeric IQR outliers. Therefore the script preserves every row and value rather than guessing at business rules or removing valid-looking data.

The cleaned CSV is validated against the source for row and column counts, column order, values, and row order. The script also checks missing values, exact duplicate rows, and preservation of numeric data types.

## Exploratory findings

In the supplied 15-record sample, 7 records are labeled `Yes` for churn and 8 are labeled `No`. The observed churn rate by contract type is 100% for Month-to-Month (7 of 7), 0% for One Year (0 of 4), and 0% for Two Year (0 of 4). These are descriptions of a very small synthetic sample; they do not show causation and should not be generalized to real customers.

## Project files

```text
.
├── customer_churn_sample (1).csv   # Supplied source data; preserved unchanged
├── data-analytics-task-1 (1).md    # Supplied task guide
├── data_quality_analysis.py        # Reproducible profiling and analysis script
├── cleaned_customer_churn.csv      # Generated cleaned copy
├── data_quality_summary.md         # Generated findings and limitations
├── validation_results.txt          # Generated validation check results
├── requirements.txt                # Python dependencies
└── charts/
    ├── churn_counts.png
    └── churn_by_contract_type.png
```

The generated CSV, report, and charts are outputs of the script and can be recreated. The source dataset is not an output and is not modified by running the script.

## Setup and execution

Open a terminal in the project root folder in VS Code. On Windows PowerShell, run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python .\data_quality_analysis.py
```

If PowerShell blocks environment activation, run the script with the virtual-environment interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\data_quality_analysis.py
```

The input CSV must remain in the project root with the exact supplied filename `customer_churn_sample (1).csv`. The script prints profile and validation results and writes or refreshes the cleaned CSV, Markdown report, validation text, and chart images.

## Limitations

- The dataset contains only 15 synthetic records, so results are illustrative and not representative.
- The task guide does not provide a detailed data dictionary or authoritative business validation rules.
- IQR is an exploratory statistical screen, not proof that a value is valid or invalid.
- No causal claims or churn predictions are made.
