import { useQuery } from "@tanstack/react-query";
import { fetchFinancialSummary } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ChartCard } from "../components/dashboard/ChartCard";
import { CurrencyLineChart } from "../components/dashboard/CurrencyLineChart";
import { HorizontalExpenseBarChart } from "../components/dashboard/HorizontalExpenseBarChart";
import { selectLatestProfitLoss } from "../components/dashboard/financialDashboardSummary";
import { SourceReviewContent } from "../components/dashboard/SourceReviewContent";
import { SummaryCard } from "../components/dashboard/SummaryCard";

import styles from "./QuickBooksPage.module.css";

function toNumber(value: number | string | null | undefined) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export default function QuickBooksPage() {
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
  });

  if (financialSummaryQuery.isPending) {
    return <LoadingSpinner label="Loading QuickBooks financial summary..." />;
  }

  if (financialSummaryQuery.isError || !financialSummaryQuery.data) {
    return <div className="hal-answer-card">Unable to load live QuickBooks summary data.</div>;
  }

  const financialSummary = financialSummaryQuery.data;
  const latestProfitLoss = selectLatestProfitLoss(financialSummary.quickBooksProfitLossSummary);
  const latestIncome = toNumber(latestProfitLoss?.income_total);
  const latestExpenses = toNumber(latestProfitLoss?.expense_total);
  const latestNetIncome = toNumber(latestProfitLoss?.net_income);
  const latestExpensesValue = latestExpenses ?? 0;
  const expenseCategories = (financialSummary.quickBooksExpenseCategories ?? []).map((row) => {
    const amount = toNumber(row.total_amount);
    return {
      category: row.expense_category ?? row.account_name ?? "Uncategorized",
      amount,
      amountValue: amount ?? 0,
      percent: latestExpensesValue > 0 && amount !== null ? (amount / latestExpensesValue) * 100 : 0,
    };
  });
  const monthlyExpenseTrend = (financialSummary.quickBooksMonthlyExpenses ?? []).map((row) => ({
    date: row.year_month ?? "",
    expenses: toNumber(row.expense_total) ?? 0,
  }));
  const quickBooksStatus = financialSummary.quickBooksStatus;
  const quickBooksReview = financialSummary.sourceReview?.quickBooks ?? null;
  const quickBooksSnapshotRows = [
    ["Status", quickBooksStatus?.status ?? "Unavailable"],
    ["Message", quickBooksStatus?.message ?? "No QuickBooks status message returned"],
    ["Last imported", quickBooksStatus?.lastImportedAtUtc ?? latestProfitLoss?.last_imported_at_utc ?? "Unavailable"],
    ["Last checked", quickBooksStatus?.lastCheckedAtUtc ?? "Unavailable"],
    ["Profit/loss rows", String(financialSummary.quickBooksProfitLossSummary?.length ?? 0)],
    ["Expense category rows", String(financialSummary.quickBooksExpenseCategories?.length ?? 0)],
  ];

  return (
    <div className="dashboard-page">
      <h1>QuickBooks Financials</h1>
      <div className="dashboard-description">Business accounting and expense management from QuickBooks.</div>
      <section className="dashboard-import-history">
        <h2>QuickBooks Source Review</h2>
        <SourceReviewContent review={quickBooksReview} emptyMessage="QuickBooks source review metadata is unavailable." />
      </section>
      <section>
        <h2>Verified QuickBooks Data</h2>
        <div className="hal-answer-card">
          This page is limited to verified QuickBooks summaries from the approved production pipeline. Raw ODBC queries remain available
          only through explicit admin diagnostics.
        </div>
      </section>
      <div className="kpi-grid">
        <SummaryCard title="Income">
          <div>
            Latest Income: <strong>{formatCurrency(latestIncome)}</strong>
          </div>
          <div>
            Net Income: <strong>{formatCurrency(latestNetIncome)}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="Expenses">
          <div>
            Latest Expenses: <strong>{formatCurrency(latestExpenses)}</strong>
          </div>
          <div>
            Top Expense: <strong>{expenseCategories[0]?.category ?? "Unavailable"}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="Expense Categories">
          <ul className={styles["quickbooks-list"]}>
            {expenseCategories.slice(0, 3).map((expense) => (
              <li key={expense.category}>
                {expense.category}: {formatCurrency(expense.amount)}
              </li>
            ))}
          </ul>
        </SummaryCard>
      </div>
      <div className="dashboard-charts">
        <ChartCard title="Monthly Expenses">
          <CurrencyLineChart data={monthlyExpenseTrend} lines={[{ dataKey: "expenses", name: "Expenses", color: "#C96A5B" }]} />
        </ChartCard>
        <ChartCard title="Expense Categories">
          <HorizontalExpenseBarChart data={expenseCategories.map((expense) => ({ ...expense, amount: expense.amountValue }))} />
        </ChartCard>
      </div>
      <div className="dashboard-import-history">
        <h2>QuickBooks Source Snapshot</h2>
        <table className="import-history-table">
          <thead>
            <tr>
              <th>Measure</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {quickBooksSnapshotRows.map(([label, value]) => (
              <tr key={label}>
                <td>{label}</td>
                <td>{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
