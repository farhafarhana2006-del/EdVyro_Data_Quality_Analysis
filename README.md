# Customer Churn Data Quality and Exploratory Analysis

## Project objective

This beginner-friendly project audits the supplied EdVyro customer churn sample, creates a reproducible analysis-ready CSV, validates the exported file, and summarizes initial patterns. It uses descriptive analysis only; it does not train a churn prediction model.

## Dataset

The supplied file is `customer_churn_sample (1).csv`. The task guide describes the customer records as synthetic. The inspected file contains 15 rows and 11 columns. It includes a `CustomerID` identifier and customer attributes such as age, tenure, subscription, charges, contract type, support tickets, payment method, and churn label.

The original CSV is read-only from the analysis script's perspective: the script reads it and writes a separate `cleaned_customer_churn.csv` output. Check the EdVyro task page's terms before redistributing the supplied CSV in a public repository.

## Tools

- Python 3
- pandas for reading, profiling, summarizing, and validating tabular data
- Plotly for interactive dashboard charts
- matplotlib for charts
- openpyxl for `.xlsx` uploads
- tabulate for Markdown report tables
- Standard Python libraries for file paths and error messages

## Data-quality checks

The script reports the dataset shape, columns, data types, first five rows, missing values, exact duplicate rows, and category labels that differ only by case or surrounding whitespace. It checks numeric columns for exploratory outliers using the 1.5×IQR rule and reports the bounds and any flagged values without deleting them.

It also calculates numeric descriptive statistics and categorical frequency distributions, then compares the observed `Churn` labels by `ContractType` when both columns exist.

## Interactive dashboard

`app.py` contains the Streamlit application. Its sidebar sections are Dashboard Overview, Data Quality, Data Explorer, Churn Analytics, Validation Results, Cleaning Workspace, and Reports. The project sample is available as a demonstration dataset; users can also upload CSV or `.xlsx` files. Uploaded files are analyzed in the current session and are not written over the sample dataset.

## React dashboard (new frontend)

The React/Vite dashboard is an additional interface to the same Python analysis; the original `app.py`, analysis functions, datasets, and generated reports are retained. A local Flask API reads the project CSVs and calls the original analysis validation and IQR functions. The browser does not write to either CSV. API routes are limited to dashboard data, validation, cleaned records, and fixed report downloads; arbitrary local file paths are not accepted.

The React interface includes the five project KPIs, column profile, data-quality checks, the existing Python validation rules, missing-value and churn charts, contract/subscription summaries, a selectable numeric distribution, searchable and filterable records, pagination, and report downloads. The numeric distribution uses dynamically calculated bins for display; the source of the data and quality checks remains Python.

### Start the React dashboard on Windows

Open two VS Code PowerShell terminals, both in the project folder. Install the dependencies once:

```powershell
python -m pip install -r .\requirements.txt
Push-Location .\frontend
npm install
Pop-Location
```

In **terminal 1**, start the API from the project root:

```powershell
python .\backend\app.py
```

In **terminal 2**, start Vite:

```powershell
Set-Location .\frontend
npm run dev
```

Open **http://localhost:5173**. The React development server proxies `/api` requests to the local Flask service at `http://127.0.0.1:5000`. Keep both terminals running while using the dashboard. The API is bound to localhost and allows browser requests only from the local Vite origins. To stop either service, press **Ctrl+C** in its terminal.

To create and check a production frontend bundle:

```powershell
Set-Location .\frontend
npm run build
```

### Project layout

```text
backend/
└── app.py                 # Local Flask API; reads existing project outputs
frontend/
├── index.html
├── package.json
├── vite.config.js
└── src/
    ├── App.jsx
    ├── main.jsx
    └── styles.css
data_quality_analysis.py   # Original Python analysis remains authoritative
app.py                      # Existing Streamlit dashboard remains available
```

The API requires the original sample CSV, generated cleaned CSV, and existing analysis/report outputs in the project root. If either required data CSV is missing, the React page displays an API error rather than inventing KPI values. Validation results are evaluated by the Python script's existing validation functions against the current source and cleaned CSV.

The dashboard calculates missing-value completeness, exact duplicate rows and duplicate identifiers, likely text/numeric type mismatches, category capitalization/whitespace variants, recognizable negative numeric values, churn labels when recognizable, 1.5×IQR review flags, and an exploratory charge-versus-tenure check when suitable columns exist. It does not impose a universal mandatory schema on uploaded files.

The quality score is **evaluated PASS checks divided by all evaluated checks, multiplied by 100**. Each rule has equal weight; WARNING and FAIL checks count as not passed, and NOT APPLICABLE checks are excluded. The displayed bands are Excellent (90–100%), Good (75–<90%), Needs Review (50–<75%), and Poor (<50%). This is a transparent summary of the implemented checks, not a certified business-quality metric.

Cleaning actions run on a separate in-session working copy. Users preview proposed changes and must explicitly confirm before applying them. The original sample or uploaded file is not overwritten; outliers are flagged but never removed automatically. The working copy can be restored from the current session's original data.

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
├── app.py                          # Interactive Streamlit dashboard
├── .streamlit/
│   └── config.toml                 # Default light dashboard theme
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
python -m streamlit run .\app.py --server.address 127.0.0.1 --server.port 8501
```

If PowerShell blocks environment activation, run the script with the virtual-environment interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\data_quality_analysis.py
.\.venv\Scripts\python.exe -m streamlit run .\app.py --server.address 127.0.0.1 --server.port 8501
```

The input CSV must remain in the project root with the exact supplied filename `customer_churn_sample (1).csv`. The script prints profile and validation results and writes or refreshes the cleaned CSV, Markdown report, validation text, and chart images.

### Launch the interactive dashboard

From the project root, run:

```powershell
python -m streamlit run .\app.py --server.address 127.0.0.1 --server.port 8501
```

Streamlit will print a local address. Open **http://localhost:8501** in your browser if it does not open automatically. Binding to `127.0.0.1` keeps the dashboard on your computer instead of exposing it on the network. The dashboard reads the cleaned CSV, validation results, and summary report using paths relative to `app.py`; it also checks whether the analysis chart files exist. If the cleaned CSV is missing but the original CSV exists, it displays the original data with a warning. Missing reports, validation files, or saved chart images are reported in the dashboard rather than causing a crash. The interactive charts are drawn from the currently loaded dataset. Rerun `python .\data_quality_analysis.py` to regenerate analysis outputs.

The dashboard includes a demonstration dataset and CSV/Excel upload option, executive KPIs with a transparent quality score, missing-value and severity charts, IQR review, interactive numeric and churn charts, a searchable/filterable/sortable explorer, paginated records, a cleaning workspace with preview and confirmation, validation results, and downloadable data and Markdown reports. Rules are based on fields detected in the active dataset; rules that cannot be evaluated are reported as not applicable.

The dashboard heading is followed by the subtitle **“Data Quality Assessment and Validation Report.”** Choose Light or Dark appearance in the sidebar. The local run command binds to `127.0.0.1`; uploads are kept in the active Streamlit session and are not written to project files.

## Limitations

- The dataset contains only 15 synthetic records, so results are illustrative and not representative.
- The task guide does not provide a detailed data dictionary or authoritative business validation rules.
- IQR is an exploratory statistical screen, not proof that a value is valid or invalid.
- No causal claims or churn predictions are made.
