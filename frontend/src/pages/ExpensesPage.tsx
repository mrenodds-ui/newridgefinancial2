import { useQuery } from "@tanstack/react-query";

import { fetchFinancialSummary } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ChartCard } from "../components/dashboard/ChartCard";
import { CurrencyLineChart } from "../components/dashboard/CurrencyLineChart";
import { selectLatestProfitLoss } from "../components/dashboard/financialDashboardSummary";
import { HorizontalExpenseBarChart } from "../components/dashboard/HorizontalExpenseBarChart";
import { SourceReviewContent } from "../components/dashboard/SourceReviewContent";
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
      <div className="dashboard-page">
        <LoadingSpinner label="Loading expense data..." />
      </div>
    );
  }

  if (financialSummaryQuery.isError || !financialSummaryQuery.data) {
    return (
      <div className="dashboard-page">
        <div className="page-state-card page-state-card--error">Unable to load live expense data.</div>
      </div>
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
  const quickBooksReview = financialSummary.sourceReview?.quickBooks ?? null;

  return (
    <div className="dashboard-page">
      <h1>Expenses</h1>
      <div className="dashboard-description">Detailed overhead control and expense analysis.</div>
      <section className="dashboard-import-history">
        <h2>QuickBooks Source Review</h2>
        <SourceReviewContent review={quickBooksReview} emptyMessage="QuickBooks source review metadata is unavailable." />
      </section>
      <div className="kpi-grid">
        <SummaryCard title="Total Expenses">
          <div>
            Latest: <strong>${latestExpenses.toLocaleString()}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="Top Expense">
          <div>{expenseCategories[0]?.category ?? "Unavailable"}</div>
        </SummaryCard>
        <SummaryCard title="Expense % of Collections">
          <div>{latestIncome > 0 ? `${Math.round((latestExpenses / latestIncome) * 100)}%` : "N/A"}</div>
        </SummaryCard>
      </div>
      <div className="dashboard-charts">
        <ChartCard title="Expense Categories">
          <HorizontalExpenseBarChart data={expenseCategories} />
        </ChartCard>
        <ChartCard title="Monthly Expense Trend">
          <CurrencyLineChart data={expenseTrend} lines={[{ dataKey: "expenses", name: "Expenses", color: "#C96A5B" }]} />
        </ChartCard>
      </div>
    </div>
  );
}
