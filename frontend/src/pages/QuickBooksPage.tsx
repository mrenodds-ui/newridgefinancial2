import { useQuery } from "@tanstack/react-query";
import { fetchFinancialSummary } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { PageSurfaceHeader, PageSurfaceShell } from "../components/PageSurfaceHeader";
import { ChartCard } from "../components/dashboard/ChartCard";
import { CurrencyBarChart } from "../components/dashboard/CurrencyBarChart";
import { CurrencyLineChart } from "../components/dashboard/CurrencyLineChart";
import { HorizontalExpenseBarChart } from "../components/dashboard/HorizontalExpenseBarChart";
import { selectLatestProfitLoss } from "../components/dashboard/financialDashboardSummary";
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
    return (
      <PageSurfaceShell className="quickbooks-page">
        <LoadingSpinner label="Loading QuickBooks financial summary..." />
      </PageSurfaceShell>
    );
  }

  if (financialSummaryQuery.isError || !financialSummaryQuery.data) {
    return (
      <PageSurfaceShell className="quickbooks-page">
        <div className="page-state-card page-state-card--error">Unable to load live QuickBooks summary data.</div>
      </PageSurfaceShell>
    );
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
  const performanceTrend = (financialSummary.quickBooksProfitLossSummary ?? []).map((row) => ({
    date: row.year_month ?? row.period_end ?? row.period_start ?? "",
    revenue: toNumber(row.income_total) ?? 0,
    netIncome: toNumber(row.net_income) ?? 0,
  }));
  const operatingMargin = latestIncome && latestNetIncome !== null ? Math.round((latestNetIncome / latestIncome) * 100) : null;
  const expenseShare = latestIncome && latestExpenses !== null ? Math.round((latestExpenses / latestIncome) * 100) : null;
  const leadingExpense = expenseCategories[0]?.category ?? "Unavailable";
  const leadingExpenseValue = expenseCategories[0]?.amount ?? null;
  const hasExpenseCategoryData = expenseCategories.length > 0;

  return (
    <PageSurfaceShell className="quickbooks-page">
      <PageSurfaceHeader
        breadcrumbs="Data sources / QuickBooks"
        eyebrow="Accounting feed"
        title="Business financials"
        titleId="quickbooks-page-title"
        description="Revenue, operating costs, and profit movement from approved QuickBooks import exports."
        badges={[
          { label: "QuickBooks Read-Only" },
          { label: "No Writeback" },
          { label: "Import Cache" },
        ]}
        statusItems={[
          { label: "Feed status", value: financialSummary.quickBooksStatus?.status ?? "Unknown" },
          { label: "P&L months", value: String(financialSummary.quickBooksProfitLossSummary?.length ?? 0) },
          { label: "Expense categories", value: String(expenseCategories.length) },
        ]}
      />
      <section className="dashboard-toolbar" aria-label="QuickBooks summary">
        <div>
          <div className="dashboard-toolbar__label">Operating margin</div>
          <div className="dashboard-toolbar__value">{operatingMargin === null ? "Unavailable" : `${operatingMargin}%`}</div>
        </div>
        <div>
          <div className="dashboard-toolbar__label">Expense share</div>
          <div className="dashboard-toolbar__value">{expenseShare === null ? "Unavailable" : `${expenseShare}%`}</div>
        </div>
        <div>
          <div className="dashboard-toolbar__label">Leading spend bucket</div>
          <div className="dashboard-toolbar__value">{leadingExpense}</div>
        </div>
      </section>
      <div className="kpi-grid">
        <SummaryCard title="Revenue">
          <div>
            Monthly revenue: <strong>{formatCurrency(latestIncome)}</strong>
          </div>
          <div>
            Net Income: <strong>{formatCurrency(latestNetIncome)}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="Expenses">
          <div>
            Monthly expenses: <strong>{formatCurrency(latestExpenses)}</strong>
          </div>
          <div>
            Expense share: <strong>{expenseShare === null ? "Unavailable" : `${expenseShare}%`}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="Leading Category">
          <ul className={styles["quickbooks-list"]}>
            <li>
              {leadingExpense}: <strong>{formatCurrency(leadingExpenseValue)}</strong>
            </li>
            <li>
              Active categories: <strong>{expenseCategories.length}</strong>
            </li>
          </ul>
        </SummaryCard>
        <SummaryCard title="Expense Focus">
          <ul className={styles["quickbooks-list"]}>
            {expenseCategories.slice(0, 2).map((expense) => (
              <li key={expense.category}>
                {expense.category}: <strong>{formatCurrency(expense.amount)}</strong>
              </li>
            ))}
          </ul>
        </SummaryCard>
      </div>
      <div className="dashboard-charts">
        <ChartCard title="Revenue vs Net Income">
          <CurrencyLineChart
            data={performanceTrend}
            lines={[
              { dataKey: "revenue", name: "Revenue", color: "#4C84FF" },
              { dataKey: "netIncome", name: "Net Income", color: "#69E6FF" },
            ]}
          />
        </ChartCard>
        <ChartCard title="Monthly Expenses">
          <CurrencyBarChart data={monthlyExpenseTrend} bars={[{ dataKey: "expenses", name: "Expenses", color: "#E4ECFF" }]} legend={false} />
        </ChartCard>
      </div>
      <div className="dashboard-charts">
        <ChartCard title="Expense Categories">
          {hasExpenseCategoryData ? (
            <HorizontalExpenseBarChart data={expenseCategories.map((expense) => ({ ...expense, amount: expense.amountValue })).slice(0, 6)} />
          ) : (
            <div className="page-state-card page-state-card--info">Expense category detail will appear after a QuickBooks expense export is connected.</div>
          )}
        </ChartCard>
        <section className="dashboard-card">
          <div className="dashboard-card__title">Expense Posture</div>
          <div className="dashboard-kpi-main">{formatCurrency(latestExpenses)}</div>
          <div className="dashboard-kpi-label">Current monthly spend</div>
          <div className="dashboard-kpi-support">
            <span>
              Revenue: <strong>{formatCurrency(latestIncome)}</strong>
            </span>
            <span>
              Net income: <strong>{formatCurrency(latestNetIncome)}</strong>
            </span>
            <span>
              Largest category: <strong>{leadingExpense}</strong>
            </span>
          </div>
        </section>
      </div>
    </PageSurfaceShell>
  );
}
