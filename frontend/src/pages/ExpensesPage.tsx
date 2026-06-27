import { useQuery } from "@tanstack/react-query";

import { fetchFinancialSummary } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { PageSurfaceHeader, PageSurfaceShell } from "../components/PageSurfaceHeader";
import { ChartCard } from "../components/dashboard/ChartCard";
import { CurrencyLineChart } from "../components/dashboard/CurrencyLineChart";
import { selectLatestProfitLoss } from "../components/dashboard/financialDashboardSummary";
import { HorizontalExpenseBarChart } from "../components/dashboard/HorizontalExpenseBarChart";
import { SummaryCard } from "../components/dashboard/SummaryCard";

function toNumber(value: number | string | null | undefined) {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

export default function ExpensesPage() {
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
  });
  if (financialSummaryQuery.isPending) {
    return (
      <PageSurfaceShell className="expenses-page">
        <LoadingSpinner label="Loading expense data..." />
      </PageSurfaceShell>
    );
  }

  if (financialSummaryQuery.isError || !financialSummaryQuery.data) {
    return (
      <PageSurfaceShell className="expenses-page">
        <div className="page-state-card page-state-card--error">Unable to load live expense data.</div>
      </PageSurfaceShell>
    );
  }

  const financialSummary = financialSummaryQuery.data;
  const latestProfitLoss = selectLatestProfitLoss(financialSummary.quickBooksProfitLossSummary);
  const latestExpenses = toNumber(latestProfitLoss?.expense_total);
  const latestIncome = toNumber(latestProfitLoss?.income_total);
  const expenseCategories = (financialSummary.quickBooksExpenseCategories ?? []).map((row) => ({
    category: row.expense_category ?? row.account_name ?? "Uncategorized",
    amount: toNumber(row.total_amount),
    percent: latestExpenses > 0 ? (toNumber(row.total_amount) / latestExpenses) * 100 : 0,
  }));
  const expenseTrend = (financialSummary.quickBooksMonthlyExpenses ?? []).map((row) => ({
    date: row.year_month ?? "",
    expenses: toNumber(row.expense_total),
  }));
  const expenseShare = latestIncome > 0 ? Math.round((latestExpenses / latestIncome) * 100) : null;
  const topExpense = expenseCategories[0]?.category ?? "Unavailable";
  const hasExpenseCategoryData = expenseCategories.length > 0;

  return (
    <PageSurfaceShell className="expenses-page">
      <PageSurfaceHeader
        breadcrumbs="Analytics / Expense analysis"
        eyebrow="Expense analysis"
        title="Expenses"
        titleId="expenses-page-title"
        description="Overhead control and category drill-down from approved QuickBooks expense exports."
        badges={[
          { label: "QuickBooks Read-Only" },
          { label: "Import Cache" },
        ]}
        statusItems={[
          { label: "Monthly spend", value: `$${latestExpenses.toLocaleString()}` },
          { label: "Top category", value: topExpense },
          { label: "Expense share", value: expenseShare === null ? "Unavailable" : `${expenseShare}%` },
        ]}
      />
      <div className="kpi-grid">
        <SummaryCard title="Total expenses">
          <div>
            Latest: <strong>${latestExpenses.toLocaleString()}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="Top expense">
          <div>{topExpense}</div>
        </SummaryCard>
        <SummaryCard title="Expense share of revenue">
          <div>{expenseShare === null ? "Unavailable" : `${expenseShare}%`}</div>
        </SummaryCard>
      </div>
      <div className="dashboard-charts">
        <ChartCard title="Expense categories">
          {hasExpenseCategoryData ? (
            <HorizontalExpenseBarChart data={expenseCategories} />
          ) : (
            <div className="page-state-card page-state-card--info">Expense category detail will appear after a QuickBooks expense export is connected.</div>
          )}
        </ChartCard>
        <ChartCard title="Monthly expense trend">
          <CurrencyLineChart data={expenseTrend} lines={[{ dataKey: "expenses", name: "Expenses", color: "#4c84ff" }]} />
        </ChartCard>
      </div>
      <section className="page-surface__focus-card" aria-label="Expense posture">
        <div className="page-surface__focus-title">Current monthly expenses</div>
        <div className="page-surface__focus-metric">${latestExpenses.toLocaleString()}</div>
        <div className="page-surface__focus-detail">Verified QuickBooks expense snapshot</div>
        <div className="page-surface__focus-support">
          <span>
            Top category: <strong>{topExpense}</strong>
          </span>
          <span>
            Expense share: <strong>{expenseShare === null ? "Unavailable" : `${expenseShare}%`}</strong>
          </span>
          <span>
            Categories tracked: <strong>{expenseCategories.length}</strong>
          </span>
        </div>
      </section>
    </PageSurfaceShell>
  );
}
