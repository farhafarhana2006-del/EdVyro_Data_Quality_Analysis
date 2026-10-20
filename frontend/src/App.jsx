import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  BarChart3,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Copy,
  Database,
  Download,
  FileCheck2,
  FileSpreadsheet,
  LayoutDashboard,
  LoaderCircle,
  Search,
  ShieldCheck,
  Table2,
  TriangleAlert,
  Users,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "quality", label: "Data quality", icon: ShieldCheck },
  { id: "explorer", label: "Data explorer", icon: Table2 },
  { id: "churn", label: "Churn analytics", icon: Activity },
  { id: "validation", label: "Validation", icon: ClipboardCheck },
  { id: "reports", label: "Reports", icon: FileCheck2 },
];

const chartColors = ["#4569e8", "#14a38b", "#9b75e8", "#e7a341", "#e46d76", "#5594c6"];
const filterColumns = ["Gender", "PaymentMethod", "SubscriptionType", "Churn", "ContractType"];
const pageSize = 8;

function number(value) {
  return new Intl.NumberFormat().format(value ?? 0);
}

function percent(value) {
  return value == null ? "Not available" : `${value.toFixed(1)}%`;
}

function formatPercentage(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? `${numericValue.toFixed(1)}%` : "—";
}

function formatPercentageTick(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? `${Math.round(numericValue)}%` : "—";
}

function Panel({ title, description, action, children, className = "" }) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function EmptyChart({ title }) {
  return (
    <div className="empty-chart" role="status">
      <CircleHelp size={21} />
      <strong>{title}</strong>
      <span>No matching data is available in the loaded dataset.</span>
    </div>
  );
}

function ChartTooltip({ active, payload, label, valueFormatter }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <strong>{label ?? payload[0].name}</strong>
      {payload.map((entry) => (
        <span key={entry.dataKey ?? entry.name}>
          {entry.name}: {valueFormatter ? valueFormatter(entry.value) : `${entry.value}${entry.unit ?? ""}`}
        </span>
      ))}
    </div>
  );
}

function ContractChurnChart({ rows }) {
  if (!rows.length) return <EmptyChart title="Contract or churn labels are not available" />;
  return (
    <div className="chart-area">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={rows}
          margin={{ top: 20, right: 20, left: 4, bottom: 12 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="contract" tick={{ fontSize: 11 }} interval={0} />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 20, 40, 60, 80, 100]}
            tickFormatter={formatPercentageTick}
            tick={{ fontSize: 11 }}
            width={48}
          />
          <Tooltip
            content={<ChartTooltip valueFormatter={formatPercentage} />}
          />
          <Bar
            dataKey="rate_percent"
            name="Churn rate"
            fill="#9b75e8"
            radius={[5, 5, 0, 0]}
          >
            <LabelList
              dataKey="rate_percent"
              position="top"
              formatter={formatPercentage}
              style={{ fill: "#5b4b7d", fontSize: 10, fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function KPI({ label, value, detail, icon: Icon, accent, status }) {
  return (
    <article className={`kpi-card ${accent ?? ""}`}>
      <div className="kpi-top">
        <span>{label}</span>
        <span className="kpi-icon"><Icon size={18} /></span>
      </div>
      <strong className="kpi-value">{value}</strong>
      <div className="kpi-detail">
        {status && <span className={`status-pill ${status.kind}`}>{status.label}</span>}
        {detail && <span>{detail}</span>}
      </div>
    </article>
  );
}

function MissingChart({ rows }) {
  const hasMissing = rows.some((row) => row.count > 0);
  if (!hasMissing) {
    return (
      <div className="zero-state">
        <CheckCircle2 size={20} />
        <div><strong>No missing cells detected</strong><span>All {rows.length} columns contain zero missing values.</span></div>
        <b>0</b>
      </div>
    );
  }
  return (
    <div className="chart-area tall-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ left: 12, right: 24 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" allowDecimals={false} />
          <YAxis dataKey="column" type="category" width={120} tick={{ fontSize: 11 }} />
          <Tooltip content={<ChartTooltip />} />
          <Bar dataKey="count" name="Missing cells" fill="#e3a33d" radius={[0, 5, 5, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function DistributionChart({ rows }) {
  if (!rows.length) return <EmptyChart title="Churn labels not available" />;
  return (
    <div className="chart-area">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={rows} dataKey="count" nameKey="label" innerRadius={68} outerRadius={104} paddingAngle={3}>
            {rows.map((row, index) => <Cell key={row.label} fill={chartColors[index % chartColors.length]} />)}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      <div className="legend-list">
        {rows.map((row, index) => (
          <div className="legend-item" key={row.label}>
            <i style={{ backgroundColor: chartColors[index % chartColors.length] }} />
            <span>{row.label}</span><b>{number(row.count)}</b>
          </div>
        ))}
      </div>
    </div>
  );
}

function CountChart({ rows, labelKey = "label", valueKey = "count", valueName = "Customers" }) {
  if (!rows.length) return <EmptyChart title="This chart is not applicable" />;
  return (
    <div className="chart-area">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 12, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={labelKey} tick={{ fontSize: 11 }} interval={0} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip content={<ChartTooltip />} />
          <Bar dataKey={valueKey} name={valueName} fill="#496bea" radius={[5, 5, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function App() {
  const [data, setData] = useState(null);
  const [activeSection, setActiveSection] = useState("overview");
  const [loadError, setLoadError] = useState("");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({});
  const [page, setPage] = useState(1);
  const [numericColumn, setNumericColumn] = useState("");

  useEffect(() => {
    let mounted = true;
    fetch("/api/dashboard")
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || "The dashboard API could not load project data.");
        return body;
      })
      .then((payload) => {
        if (!mounted) return;
        setData(payload);
        setNumericColumn(payload.charts.numeric_columns[0] ?? "");
      })
      .catch((error) => mounted && setLoadError(error.message));
    return () => { mounted = false; };
  }, []);

  const filteredRecords = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLocaleLowerCase();
    return data.dataset.records.filter((record) => {
      const matchesSearch = !needle || Object.values(record).some(
        (value) => String(value ?? "").toLocaleLowerCase().includes(needle),
      );
      const matchesFilters = filterColumns.every((column) => (
        !filters[column] || String(record[column] ?? "(Missing)") === filters[column]
      ));
      return matchesSearch && matchesFilters;
    });
  }, [data, query, filters]);

  useEffect(() => setPage(1), [query, filters]);

  const maxPage = Math.max(1, Math.ceil(filteredRecords.length / pageSize));
  const visibleRecords = filteredRecords.slice((page - 1) * pageSize, page * pageSize);
  const numericValues = useMemo(() => (
    data?.dataset.records
      .map((record) => Number(record[numericColumn]))
      .filter(Number.isFinite) ?? []
  ), [data, numericColumn]);

  const numericDistribution = useMemo(() => {
    if (!numericValues.length) return [];
    const min = Math.min(...numericValues);
    const max = Math.max(...numericValues);
    const binCount = Math.min(8, Math.max(1, Math.ceil(Math.sqrt(numericValues.length))));
    const width = max === min ? 1 : (max - min) / binCount;
    return Array.from({ length: binCount }, (_, index) => {
      const start = min + width * index;
      const end = index === binCount - 1 ? max : start + width;
      const count = numericValues.filter((value) => (
        index === binCount - 1 ? value >= start && value <= end : value >= start && value < end
      )).length;
      return { label: max === min ? String(min) : `${start.toFixed(1)}–${end.toFixed(1)}`, count };
    });
  }, [numericValues]);

  if (loadError) {
    return (
      <main className="error-screen">
        <div className="error-card">
          <AlertCircle size={30} />
          <h1>Could not load the dashboard</h1>
          <p>{loadError}</p>
          <span>Start the Flask backend, then refresh this page.</span>
          <code>python .\backend\app.py</code>
        </div>
      </main>
    );
  }
  if (!data) {
    return <main className="loading-screen"><LoaderCircle className="spin" /><span>Loading verified project data…</span></main>;
  }

  const { kpis, charts, validation, dataset } = data;
  const validationStatus = kpis.validation_failed
    ? { kind: "fail", label: `${kpis.validation_failed} failed` }
    : { kind: "pass", label: `${kpis.validation_passed}/${kpis.validation_total} passed` };
  const activeTitle = navigation.find((item) => item.id === activeSection)?.label ?? "Overview";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview" onClick={() => setActiveSection("overview")}>
          <span className="brand-mark"><BarChart3 size={21} /></span>
          <span><strong>EdVyro Analytics</strong><small>DATA QUALITY WORKSPACE</small></span>
        </a>
        <div className="nav-heading">WORKSPACE</div>
        <nav aria-label="Dashboard navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              className={`nav-link ${activeSection === id ? "selected" : ""}`}
              key={id}
              onClick={() => setActiveSection(id)}
            >
              <Icon size={18} /><span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="api-status"><i /> Local API connected</span>
          <span className="privacy-note"><ShieldCheck size={15} /> Data remains on this computer</span>
        </div>
      </aside>

      <main className="main-content">
        <header className="page-header">
          <div className="header-title">
            <div className="eyebrow">CUSTOMER ANALYTICS <span>/</span> {activeTitle.toUpperCase()}</div>
            <h1>Customer Churn Data Quality Dashboard</h1>
            <p>Data Quality Assessment and Validation Report</p>
          </div>
          <div className="dataset-status">
            <span className="status-dot" />
            <div><strong>Analysis ready</strong><small>{dataset.filename}</small></div>
          </div>
        </header>

        {activeSection === "overview" && (
          <>
            <div className="section-intro">
              <div><h2>Dashboard overview</h2><p>A verified snapshot of the current cleaned dataset and its checks.</p></div>
              <a className="button button-primary" href="/api/download/cleaned.csv"><Download size={16} /> Download cleaned CSV</a>
            </div>
            <div className="kpi-grid">
              <KPI label="Total records" value={number(kpis.total_records)} detail="customer rows" icon={Users} />
              <KPI label="Total columns" value={number(kpis.total_columns)} detail="dataset fields" icon={Database} accent="violet" />
              <KPI label="Missing values" value={number(kpis.missing_values)} detail="cells across all fields" icon={CircleHelp} accent="amber" />
              <KPI label="Duplicate rows" value={number(kpis.duplicate_rows)} detail="exact matches" icon={Copy} accent="rose" />
              <KPI label="Validation checks" value={`${kpis.validation_passed}/${kpis.validation_total}`} detail="implemented checks" icon={ClipboardCheck} accent="green" status={validationStatus} />
            </div>
            <div className="chart-grid">
              <Panel title="Missing values by column" description="Completeness counts calculated from the cleaned CSV">
                <MissingChart rows={charts.missing} />
              </Panel>
              <Panel title="Customer churn distribution" description="Observed labels in the supplied sample">
                <DistributionChart rows={charts.churn} />
              </Panel>
              <Panel title="Churn Rate by Contract Type" description="Observed churn share; descriptive, not causal">
                <ContractChurnChart rows={charts.contract_churn} />
              </Panel>
              <Panel title="Subscription type distribution" description="Customer count per supplied subscription label">
                <CountChart rows={charts.subscription} />
              </Panel>
            </div>
            <DatasetProfile data={data} />
          </>
        )}

        {activeSection === "quality" && (
          <>
            <div className="section-intro"><div><h2>Data quality findings</h2><p>Checks and statistical review based on the Python project analysis.</p></div></div>
            <div className="quality-summary">
              <span className="summary-icon"><ShieldCheck size={21} /></span>
              <div><strong>{number(kpis.missing_values)} missing cells · {number(kpis.duplicate_rows)} exact duplicate rows</strong><p>{data.scope_note}</p></div>
            </div>
            <div className="chart-grid">
              <Panel title="Missing values by column" description="A zero state is shown when the dataset is complete."><MissingChart rows={charts.missing} /></Panel>
              <Panel title="IQR outlier review" description="1.5×IQR flags are statistical review candidates, not automatic errors.">
                <OutlierTable rows={charts.outliers} />
              </Panel>
            </div>
            <Panel title="Column profile" description="Data types, unique values, and null counts from the cleaned data">
              <ColumnTable columns={dataset.column_profile} />
            </Panel>
            <p className="disclaimer"><TriangleAlert size={16} /> {data.scope_note}</p>
          </>
        )}

        {activeSection === "explorer" && (
          <>
            <div className="section-intro"><div><h2>Dataset explorer</h2><p>Search and filter the cleaned records. Filtering never changes the source CSV.</p></div>
              <a className="button button-primary" href="/api/download/cleaned.csv"><Download size={16} /> Export CSV</a>
            </div>
            <Panel title="Customer records" description={`${number(filteredRecords.length)} matching records out of ${number(dataset.rows)}`}>
              <div className="table-controls">
                <label className="search-box"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search across all columns…" /></label>
                <button className="button button-secondary" onClick={() => { setQuery(""); setFilters({}); }}>Reset filters</button>
              </div>
              <div className="filter-row">
                {filterColumns.filter((column) => dataset.column_names.includes(column)).map((column) => {
                  const choices = [...new Set(dataset.records.map((row) => String(row[column] ?? "(Missing)")))].sort();
                  return (
                    <label className="filter-field" key={column}>
                      <span>{column}</span>
                      <select value={filters[column] ?? ""} onChange={(event) => setFilters((current) => ({ ...current, [column]: event.target.value }))}>
                        <option value="">All values</option>
                        {choices.map((choice) => <option key={choice} value={choice}>{choice}</option>)}
                      </select>
                    </label>
                  );
                })}
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr>{dataset.column_names.map((column) => <th key={column}>{column}</th>)}</tr></thead>
                  <tbody>
                    {visibleRecords.map((record, index) => (
                      <tr key={`${record.CustomerID ?? "row"}-${index}`}>
                        {dataset.column_names.map((column) => (
                          <td key={column}>{column === "Churn" ? <span className={`churn-badge ${String(record[column]).toLowerCase() === "yes" ? "churned" : "retained"}`}>{String(record[column] ?? "—")}</span> : String(record[column] ?? "—")}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!visibleRecords.length && <EmptyChart title="No records match the current filters" />}
              </div>
              <div className="pagination">
                <span>Showing {filteredRecords.length ? (page - 1) * pageSize + 1 : 0}–{Math.min(page * pageSize, filteredRecords.length)} of {number(filteredRecords.length)}</span>
                <div>
                  <button aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}><ChevronLeft size={17} /></button>
                  <span>Page {page} of {maxPage}</span>
                  <button aria-label="Next page" disabled={page >= maxPage} onClick={() => setPage((current) => Math.min(maxPage, current + 1))}><ChevronRight size={17} /></button>
                </div>
              </div>
            </Panel>
          </>
        )}

        {activeSection === "churn" && (
          <>
            <div className="section-intro"><div><h2>Churn analytics</h2><p>Exploratory views of the actual sample, not a prediction or causal analysis.</p></div></div>
            <div className="kpi-grid churn-kpi">
              <KPI label="Observed churn rate" value={percent(kpis.churn_rate)} detail="among recognized labels" icon={Activity} accent="violet" />
              <KPI label="Records in sample" value={number(dataset.rows)} detail="small synthetic dataset" icon={Users} />
            </div>
            <div className="chart-grid">
              <Panel title="Churn status counts" description="Counts by the observed churn label"><CountChart rows={charts.churn} /></Panel>
              <Panel title="Churn Rate by Contract Type" description="Share labeled as churned within each contract group">
                <ContractChurnChart rows={charts.contract_churn} />
              </Panel>
              <Panel title="Subscription type" description="Observed customer count by subscription">
                <CountChart rows={charts.subscription} />
              </Panel>
              <Panel title="Numeric distribution" description="Select a numeric dataset column">
                {charts.numeric_columns.length ? (
                  <>
                    <label className="select-control"><span>Numeric column</span><select value={numericColumn} onChange={(event) => setNumericColumn(event.target.value)}>{charts.numeric_columns.map((column) => <option key={column}>{column}</option>)}</select></label>
                    <CountChart rows={numericDistribution} valueName="Records" />
                  </>
                ) : <EmptyChart title="No numeric columns are available" />}
              </Panel>
            </div>
            <p className="disclaimer"><TriangleAlert size={16} /> {data.disclaimer}</p>
          </>
        )}

        {activeSection === "validation" && (
          <>
            <div className="section-intro"><div><h2>Validation results</h2><p>These checks are re-evaluated using the original Python analysis functions.</p></div>
              <span className={`status-pill large ${kpis.validation_failed ? "fail" : "pass"}`}>{kpis.validation_passed}/{kpis.validation_total} passed</span>
            </div>
            <div className={`validation-banner ${kpis.validation_failed ? "has-fail" : ""}`}>
              {kpis.validation_failed ? <AlertCircle size={22} /> : <CheckCircle2 size={22} />}
              <div><strong>{kpis.validation_failed ? `${kpis.validation_failed} validation checks need attention` : "All implemented validation checks passed"}</strong><span>{data.scope_note}</span></div>
            </div>
            <Panel title="Validation checks" description="Pass/fail results are based on the existing Python rules">
              <div className="validation-list">
                {validation.map((check) => (
                  <article className="validation-row" key={check.rule}>
                    <span className={`validation-icon ${check.status.toLowerCase()}`}>{check.status === "PASS" ? <CheckCircle2 size={17} /> : <AlertCircle size={17} />}</span>
                    <div><strong>{check.rule}</strong><p>{check.details}</p></div>
                    <span className={`status-pill ${check.status.toLowerCase()}`}>{check.status}</span>
                  </article>
                ))}
              </div>
            </Panel>
            <p className="disclaimer"><TriangleAlert size={16} /> Passing these checks does not certify every possible business rule or dataset requirement.</p>
          </>
        )}

        {activeSection === "reports" && (
          <>
            <div className="section-intro"><div><h2>Reports and downloads</h2><p>Download existing project outputs without changing source files.</p></div></div>
            <div className="report-grid">
              <ReportCard icon={FileSpreadsheet} title="Cleaned customer dataset" description={`${number(dataset.rows)} rows · ${number(dataset.columns)} columns · CSV`} href="/api/download/cleaned.csv" />
              <ReportCard icon={FileCheck2} title="Data quality summary" description="Existing project findings, validation, and limitations · Markdown" href="/api/download/summary.md" />
            </div>
            <Panel title="Data quality findings" description="Calculated from the loaded cleaned dataset">
              <ul className="finding-list">{data.findings.map((finding) => <li key={finding}><CheckCircle2 size={17} />{finding}</li>)}</ul>
              <div className="notice-box"><TriangleAlert size={18} /><p>{data.disclaimer}<br /><br />{data.scope_note}</p></div>
            </Panel>
          </>
        )}

        <footer className="app-footer"><span>EdVyro · Data Quality Assessment</span><span>Local analysis · No external upload</span></footer>
      </main>
    </div>
  );
}

function DatasetProfile({ data }) {
  return (
    <Panel title="Dataset overview" description={`${number(data.dataset.rows)} records × ${number(data.dataset.columns)} columns · data types from the cleaned CSV`}>
      <div className="profile-table">
        {data.dataset.column_profile.map((column) => (
          <div className="profile-row" key={column.column}>
            <code>{column.column}</code><span className="type-tag">{column.dtype}</span><span>{number(column.unique)} unique</span><span>{number(column.missing)} missing</span>
          </div>
        ))}
      </div>
      <div className="column-chips">{data.dataset.column_names.map((column) => <span key={column}>{column}</span>)}</div>
      <div className="notice-box compact"><TriangleAlert size={17} /><p>{data.disclaimer}</p></div>
    </Panel>
  );
}

function ColumnTable({ columns }) {
  return (
    <div className="table-wrap">
      <table className="small-table">
        <thead><tr><th>Column</th><th>Data type</th><th>Unique values</th><th>Missing values</th></tr></thead>
        <tbody>{columns.map((column) => <tr key={column.column}><td><code>{column.column}</code></td><td><span className="type-tag">{column.dtype}</span></td><td>{number(column.unique)}</td><td>{number(column.missing)}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

function OutlierTable({ rows }) {
  if (!rows.length) return <EmptyChart title="No numeric columns to review" />;
  const total = rows.reduce((sum, row) => sum + row.flagged_count, 0);
  return (
    <>
      <div className={`outlier-summary ${total ? "review" : ""}`}>
        {total ? <TriangleAlert size={18} /> : <CheckCircle2 size={18} />}
        <strong>{number(total)} flagged numeric values</strong>
        <span>{total ? "Review candidates only" : "No values outside the 1.5×IQR bounds"}</span>
      </div>
      <div className="table-wrap">
        <table className="small-table">
          <thead><tr><th>Numeric column</th><th>Lower bound</th><th>Upper bound</th><th>Flags</th></tr></thead>
          <tbody>{rows.map((row) => <tr key={row.column}><td>{row.column}</td><td>{row.lower_bound == null ? "—" : row.lower_bound.toFixed(2)}</td><td>{row.upper_bound == null ? "—" : row.upper_bound.toFixed(2)}</td><td>{row.flagged_count}</td></tr>)}</tbody>
        </table>
      </div>
      <p className="table-footnote">IQR flags indicate unusual statistical observations, not automatically invalid records. No outliers are removed by this review.</p>
    </>
  );
}

function ReportCard({ icon: Icon, title, description, href }) {
  return (
    <article className="report-card">
      <span className="report-icon"><Icon size={21} /></span>
      <div><h3>{title}</h3><p>{description}</p></div>
      <a className="button button-secondary" href={href}><Download size={16} /> Download</a>
    </article>
  );
}

export default App;
