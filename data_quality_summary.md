# Data Quality and Exploratory Analysis

## Dataset overview

- Source file: `customer_churn_sample (1).csv` (original preserved unchanged)
- Dataset: 15 rows and 11 columns
- EdVyro describes the supplied data as synthetic. This file contains only 15 records, so findings are limited to this small sample.

## Column profile

| column | dtype | missing_values | unique_values |
| --- | --- | --- | --- |
| CustomerID | object | 0 | 15 |
| Gender | object | 0 | 2 |
| Age | int64 | 0 | 15 |
| TenureMonths | int64 | 0 | 15 |
| SubscriptionType | object | 0 | 3 |
| MonthlyCharges | float64 | 0 | 3 |
| TotalCharges | float64 | 0 | 15 |
| ContractType | object | 0 | 3 |
| SupportTickets | int64 | 0 | 7 |
| PaymentMethod | object | 0 | 4 |
| Churn | object | 0 | 2 |

## Missing values and duplicates

- Missing cells in source: 0
- Exact duplicate rows in source: 0

## Category spelling review

No labels differing only by case or surrounding spaces were detected.

This check only flags category labels that differ by case or surrounding whitespace. It does not define which labels are valid; the supplied task guide does not provide allowed category lists.

## Exploratory outlier review

Numeric values were screened with the 1.5×IQR rule. A flagged value is only a review candidate, not automatically an error. No outliers were removed.

| column | lower_bound | upper_bound | flagged_count | flagged_values |
| --- | --- | --- | --- | --- |
| Age | 4.50 | 72.50 | 0 |  |
| TenureMonths | -23.00 | 57.00 | 0 |  |
| MonthlyCharges | -47.51 | 212.49 | 0 |  |
| TotalCharges | -3689.82 | 7349.46 | 0 |  |
| SupportTickets | -3.50 | 8.50 | 0 |  |

## Cleaning decisions

The guide requests cleaning with documented assumptions, but it does not specify value ranges, allowed categories, missing-value imputation, or record deletion rules. The source has no missing values, exact duplicate rows, or category spelling variants detected by the limited case/whitespace check. Therefore the cleaned CSV preserves every row and value unchanged. This avoids guessing business rules or deleting potentially valid observations.

## Validation

Validation result: **all listed checks passed**.

- **PASS** — Cleaned file has the same row count as source: source=15, cleaned=15
- **PASS** — Cleaned file has the same column count as source: source=11, cleaned=11
- **PASS** — Cleaned file preserves source column names and order: columns=['CustomerID', 'Gender', 'Age', 'TenureMonths', 'SubscriptionType', 'MonthlyCharges', 'TotalCharges', 'ContractType', 'SupportTickets', 'PaymentMethod', 'Churn']
- **PASS** — Saved CSV preserves source values and row order: Compared the original data with the CSV read back from disk.
- **PASS** — Output CSV can be read back with the same shape: source=(15, 11), reread_output=(15, 11)
- **PASS** — No missing values in cleaned dataset: missing_cells=0
- **PASS** — No exact duplicate rows in cleaned dataset: duplicate_rows=0
- **PASS** — Original numeric columns remain numeric: checked=['Age', 'TenureMonths', 'MonthlyCharges', 'TotalCharges', 'SupportTickets']

No official required-column list or business-valid ranges were supplied, so domain validity cannot be conclusively certified.

## Numerical summary statistics

| column | count | mean | std | min | 25% | 50% | 75% | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Age | 15.00 | 39.07 | 11.39 | 23.00 | 30.00 | 38.00 | 47.00 | 60.00 |
| TenureMonths | 15.00 | 18.80 | 14.33 | 2.00 | 7.00 | 15.00 | 27.00 | 48.00 |
| MonthlyCharges | 15.00 | 84.66 | 42.74 | 49.99 | 49.99 | 79.99 | 114.99 | 149.99 |
| TotalCharges | 15.00 | 2088.48 | 2407.37 | 99.98 | 449.91 | 1099.78 | 3209.73 | 7199.52 |
| SupportTickets | 15.00 | 2.53 | 1.92 | 0.00 | 1.00 | 2.00 | 4.00 | 6.00 |

## Categorical frequency distributions

### CustomerID

| value | count |
| --- | --- |
| CUST-1001 | 1 |
| CUST-1002 | 1 |
| CUST-1003 | 1 |
| CUST-1004 | 1 |
| CUST-1005 | 1 |
| CUST-1006 | 1 |
| CUST-1007 | 1 |
| CUST-1008 | 1 |
| CUST-1009 | 1 |
| CUST-1010 | 1 |
| CUST-1011 | 1 |
| CUST-1012 | 1 |
| CUST-1013 | 1 |
| CUST-1014 | 1 |
| CUST-1015 | 1 |

### Gender

| value | count |
| --- | --- |
| Female | 8 |
| Male | 7 |

### SubscriptionType

| value | count |
| --- | --- |
| Basic | 7 |
| Pro | 4 |
| Enterprise | 4 |

### ContractType

| value | count |
| --- | --- |
| Month-to-Month | 7 |
| One Year | 4 |
| Two Year | 4 |

### PaymentMethod

| value | count |
| --- | --- |
| Credit Card | 6 |
| UPI | 4 |
| Bank Transfer | 3 |
| Debit Card | 2 |

### Churn

| value | count |
| --- | --- |
| No | 8 |
| Yes | 7 |



## Initial churn observation

Churn labels observed: No=8, Yes=7. These are descriptive counts from this 15-row synthetic sample, not evidence of causation or a representative estimate.

### Churn comparison by contract type

| ContractType | customers | churn_yes | churn_rate |
| --- | --- | --- | --- |
| Month-to-Month | 7 | 7 | 100.0% |
| One Year | 4 | 0 | 0.0% |
| Two Year | 4 | 0 | 0.0% |

Any observed differences are descriptive comparisons only. They do not show that contract type or another field causes churn. A sample of 15 synthetic records is too small for broad conclusions.

## Charts

- [charts/churn_counts.png](./charts/churn_counts.png)
- [charts/churn_by_contract_type.png](./charts/churn_by_contract_type.png)

## Limitations

- Only 15 synthetic records are present; results may not generalize to real customers.
- The supplied task guide does not provide a separate data dictionary or detailed cleaning rules.
- Plausible value ranges and business consistency (for example, how charges relate to tenure) cannot be judged without an authoritative guide.
- The IQR rule is exploratory and may not identify all unusual or invalid values, especially in a small dataset.
