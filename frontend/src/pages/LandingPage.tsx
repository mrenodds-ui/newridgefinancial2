import classNames from "classnames";
import { type FormEvent, useRef, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { askHalQuestion, createHalConversationId } from "../api/client";
import { DashboardCard } from "../components/DashboardCard";
import { EmptyState } from "../components/EmptyState";
import ImportPanel from "../components/dashboard/ImportPanel";
import { InsurancePatientBreakdown } from "../components/dashboard/InsurancePatientBreakdown";
import { useDashboardData } from "../hooks/useDashboardData";
import { useDashboardDataPersistence } from "../hooks/useDashboardDataPersistence";
import { useDashboardExport } from "../utils/useDashboardExport";
// import { mockProviderProduction, mockInsurancePatientBreakdown } from "../data/mockDashboardData";
import styles from "./LandingPage.module.css";
import "./LandingPage.dark.css";

type TrendRow = {
  date: string;
  value: number;
};

type TrendKey = keyof TrendRow;

export default function LandingPage() {
  useDashboardDataPersistence();
  const [question, setQuestion] = useState("");
  const [advice, setAdvice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<TrendKey | null>(null);
  const [sortAsc, setSortAsc] = useState(true);
  const [visibleKpis, setVisibleKpis] = useState<TrendKey[]>(["date", "value"]);
  const [darkMode, setDarkMode] = useState(false);
  const halConversationIdRef = useRef(createHalConversationId());
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Dashboard state from centralized hook
  const { trends, lastRefreshedAt, refreshing, refreshDashboard } = useDashboardData();

  // For export, combine all dashboard data as needed
  const { exportToCSV } = useDashboardExport(trends, "landing-trend-data.csv");

  async function askHalDesignAdvice(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setAdvice(null);
    try {
      const response = await askHalQuestion(question.trim(), {
        conversationId: halConversationIdRef.current,
      });
      setAdvice(response.answer || "No advice returned.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get advice from HAL.");
    } finally {
      setLoading(false);
    }
  }

  // Responsive and dark mode classes
  const rootClass = classNames(styles["landing-root"], { dark: darkMode });

  // Table filtering, sorting, and search

  // Table filtering, sorting, and search for trends/expenses (mocked for demo)
  // In a real app, you would have provider/row data; here we use trends as a stand-in
  const filteredData = trends.filter((row: TrendRow) =>
    visibleKpis.some((kpi) =>
      String(row[kpi] || "")
        .toLowerCase()
        .includes(search.toLowerCase()),
    ),
  );
  const sortedData = sortKey
    ? [...filteredData].sort((a, b) => {
        if (a[sortKey] < b[sortKey]) return sortAsc ? -1 : 1;
        if (a[sortKey] > b[sortKey]) return sortAsc ? 1 : -1;
        return 0;
      })
    : filteredData;

  // Summary KPIs (totals)
  const totalProduction = trends.reduce((sum, row) => sum + (Number(row.value) || 0), 0);
  const totalCollections = trends.reduce((sum, row) => sum + (Number(row.value) || 0) * 0.9, 0);
  const collectionPercent = totalProduction > 0 ? (totalCollections / totalProduction) * 100 : 0;

  // Trends (by period if available)
  const trendByPeriod = trends.map((row) => ({
    period: row.date,
    production: row.value,
    collections: row.value * 0.9,
  }));

  // Insurance vs Patient breakdown (mocked)
  const insuranceSum = 6000;
  const patientSum = 4000;
  const collectionPercentClassName =
    collectionPercent > 95
      ? styles["landing-kpi-value-success"]
      : collectionPercent > 90
        ? styles["landing-kpi-value-warning"]
        : styles["landing-kpi-value-danger"];

  // KPI customization
  const allKpis: TrendKey[] = ["date", "value"];

  return (
    <div className={rootClass}>
      <DashboardCard title="Dental Practice Financial Dashboard" accent="gold">
        <div className={styles["landing-toolbar"]}>
          <button
            type="button"
            className={`${styles["landing-btn"]} ${styles["landing-btn-float"]}`}
            onClick={() => setDarkMode((d) => !d)}
            aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
            data-testid="dark-mode-toggle"
          >
            {darkMode ? "🌙 Dark Mode" : "☀️ Light Mode"}
          </button>
          <button
            type="button"
            className={classNames(styles["landing-btn"], styles["landing-btn-min-width"])}
            onClick={refreshDashboard}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing…" : "Refresh Now"}
          </button>
          <span className={styles["landing-refresh-label"]}>Last refreshed: {lastRefreshedAt.toLocaleString()}</span>
          <button type="button" className={`${styles["landing-btn"]} ${styles["landing-btn-float-margin"]}`} onClick={exportToCSV}>
            Export Dashboard Data (CSV)
          </button>
        </div>
        <h2 className={styles["landing-card-title"]}>Welcome to New Ridge Family Financial</h2>
        <p className={styles["landing-card-desc"]}>
          Track, analyze, and optimize your dental practice's financial performance. Import data from SoftDent and QuickBooks, view KPIs,
          trends, and actionable insights—all in one secure dashboard.
        </p>
        <ul className={styles["landing-card-list"]}>
          <li>✔️ Automated data ingestion from SoftDent Bridge and QuickBooks</li>
          <li>✔️ Real-time KPI and financial trend analysis</li>
          <li>✔️ Secure, modern, and easy to use</li>
        </ul>
        {/* --- Live KPIs from imported data --- */}
        <div className={styles["landing-kpis"]}>
          <div className={styles["landing-kpi-card"]}>
            <div className={styles["landing-kpi-label"]}>Total Production</div>
            <div className={classNames(styles["landing-kpi-value"], styles["landing-kpi-value-production"])}>
              ${totalProduction.toLocaleString()}
            </div>
          </div>
          <div className={styles["landing-kpi-card"]}>
            <div className={styles["landing-kpi-label"]}>Total Collections</div>
            <div className={classNames(styles["landing-kpi-value"], styles["landing-kpi-value-collections"])}>
              ${totalCollections.toLocaleString()}
            </div>
          </div>
          <div className={styles["landing-kpi-card"]}>
            <div className={styles["landing-kpi-label"]}>Collection %</div>
            <div className={classNames(styles["landing-kpi-value"], collectionPercentClassName)}>{collectionPercent.toFixed(1)}%</div>
          </div>
        </div>
        <EmptyState title="Get Started" message="Use the navigation menu to import data or view your dashboard." />
        <form onSubmit={askHalDesignAdvice} className={styles["landing-form"]}>
          <h3>Ask HAL for Design Advice</h3>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g., How should I design my landing page?"
            className={styles["landing-input"]}
            required
          />
          <br />
          <button type="submit" className={styles["landing-btn"]} disabled={loading}>
            {loading ? "Asking HAL..." : "Ask HAL"}
          </button>
        </form>
        {advice && (
          <div className={styles["landing-advice"]}>
            <strong>HAL's Advice:</strong>
            <p className={styles["landing-advice-text"]}>{advice}</p>
          </div>
        )}
        {error && <div className={styles["landing-error"]}>{error}</div>}
      </DashboardCard>

      {/* Interactive Chart (Recharts) */}
      <div className={styles["landing-section"]}>
        <h3>Production & Collections Trend</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={trendByPeriod} margin={{ top: 16, right: 24, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="period" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="production" stroke="#2563eb" activeDot={{ r: 8 }} />
            <Line type="monotone" dataKey="collections" stroke="#22c55e" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Table Filtering, Sorting, Search, KPI Customization */}
      <div className={styles["landing-section"]}>
        <h3>Sample Data Table</h3>
        <div className={styles["landing-flex-row"]}>
          <input
            ref={searchInputRef}
            type="search"
            placeholder="Search..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search table"
            className={styles["landing-search-input"]}
          />
          <span>Columns:</span>
          {allKpis.map((kpi) => (
            <label key={kpi} className={styles["landing-label-margin"]}>
              <input
                type="checkbox"
                checked={visibleKpis.includes(kpi)}
                onChange={(e) => setVisibleKpis((v) => (e.target.checked ? [...v, kpi] : v.filter((x) => x !== kpi)))}
                aria-label={`Show ${kpi}`}
              />{" "}
              {kpi}
            </label>
          ))}
        </div>
        <div className={styles["landing-table-scroll"]}>
          <table className={styles["dashboard-table"]} aria-label="Sample data table">
            <thead>
              <tr>
                {visibleKpis.map((kpi) => (
                  <th
                    key={kpi}
                    className={sortKey === kpi ? `${styles["landing-th-sort"]} ${styles["landing-th-active"]}` : styles["landing-th-sort"]}
                  >
                    <button
                      type="button"
                      className={styles["landing-th-button"]}
                      onClick={() => {
                        setSortKey(kpi);
                        setSortAsc((s) => (sortKey === kpi ? !s : true));
                      }}
                    >
                      {kpi} {sortKey === kpi ? (sortAsc ? "▲" : "▼") : ""}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedData.map((row) => (
                <tr key={row.date}>
                  {visibleKpis.map((kpi) => (
                    <td key={kpi}>{row[kpi]}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Insurance vs Patient Payments */}
      <div className={styles["landing-section"]}>
        <InsurancePatientBreakdown insurance={insuranceSum} patient={patientSum} />
      </div>

      {/* Import Panel (history, status) */}
      <div className={styles["landing-section"]}>
        <ImportPanel />
      </div>
    </div>
  );
}
