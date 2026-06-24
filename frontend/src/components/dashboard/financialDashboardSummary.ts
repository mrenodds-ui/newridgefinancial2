import type {
  FinancialSummaryMonthlyKpi,
  FinancialSummaryQuickBooksExpenseCategory,
  FinancialSummaryQuickBooksMonthlyExpense,
  FinancialSummaryQuickBooksProfitLoss,
  FinancialSummaryResponse,
} from "../../api/client";
import type { ProviderProduction, TrendPoint } from "../../types/dashboard";

type MonthlyKpiLike = {
  year_month?: string | null;
  gross_production?: number | null;
  net_production?: number | null;
  collections?: number | null;
  collection_rate?: number | null;
};

type DashboardDataRowLike = {
  provider?: unknown;
  period?: unknown;
  production?: unknown;
  collections?: unknown;
  insurance?: unknown;
  patient?: unknown;
};

type DashboardTrendDatum = Pick<TrendPoint, "date" | "production" | "collections">;

type FinancialSummaryProviderRowLike = Record<string, unknown>;

type ProfitLossLike = Pick<
  FinancialSummaryQuickBooksProfitLoss,
  "year_month" | "period_start" | "period_end" | "income_total" | "expense_total" | "net_income" | "base_ebitda_candidate"
>;

export type ProfitLossTrendDatum = {
  date: string;
  expenses: number;
  netIncome: number;
};

export type InsurancePatientTotals = {
  insurance: number;
  patient: number;
};

export type QuickBooksExpenseCategoryDatum = {
  category: string;
  amount: number;
  percent: number;
};

export type Trailing12Totals = {
  production: number;
  collections: number;
};

export type FinancialDashboardSummary = {
  monthProduction: number | null;
  monthCollections: number | null;
  collectionPercent: number | null;
  monthIncome: number | null;
  monthExpenses: number | null;
  estimatedNetIncome: number | null;
  topExpenseCategory: string | null;
  totalAR: number | null;
  ar0to30: number | null;
  ar31to60: number | null;
  ar61to90: number | null;
  arOver90: number | null;
  lastImportAt: string | null;
  lastRefreshedAt: string | null;
  isStale: boolean;
};

export const DASHBOARD_TREND_MONTH_WINDOW = 24;

export function buildArOver90AlertMessage(summary: FinancialDashboardSummary | null | undefined): string | null {
  const arOver90 = summary?.arOver90;
  if (typeof arOver90 !== "number" || !Number.isFinite(arOver90) || arOver90 <= 0) {
    return null;
  }

  return `Verified A/R over 90 days still needs follow-up: ${formatCurrency(arOver90)}.`;
}

function toFiniteNumber(value: unknown) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : 0;
  }

  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  return 0;
}

function toNonEmptyString(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function formatCurrency(value: number) {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function getRecordValue(record: Record<string, unknown>, ...keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (value === undefined || value === null) {
      continue;
    }
    if (typeof value === "string" && value.trim() === "") {
      continue;
    }
    return value;
  }

  return undefined;
}

export function selectLatestMonthlyKpi(monthlyKpis: MonthlyKpiLike[] | null | undefined) {
  return monthlyKpis?.at(-1) ?? null;
}

export function selectLatestProfitLoss<T extends ProfitLossLike>(rows: T[] | null | undefined) {
  return rows?.at(-1) ?? null;
}

function sliceTrailingRows<T>(rows: T[], maxRows?: number) {
  if (typeof maxRows !== "number" || maxRows <= 0) {
    return rows;
  }

  return rows.slice(-maxRows);
}

export function buildProductionCollectionsSeries(monthlyKpis: MonthlyKpiLike[] | null | undefined): DashboardTrendDatum[] {
  return (monthlyKpis ?? []).map((row) => ({
    date: row.year_month ?? "",
    production: toFiniteNumber(row.gross_production),
    collections: toFiniteNumber(row.collections),
  }));
}

export function buildDashboardTrendData(financialSummary: FinancialSummaryResponse | null | undefined): DashboardTrendDatum[] {
  const preferredRows = financialSummary?.fourYearMonthlyKpis?.length
    ? financialSummary.fourYearMonthlyKpis
    : financialSummary?.trailing12Months?.length
      ? financialSummary.trailing12Months
      : financialSummary?.monthlyKpis;

  return buildProductionCollectionsSeries(sliceTrailingRows(preferredRows ?? [], DASHBOARD_TREND_MONTH_WINDOW));
}

export function sumTrailing12ProductionCollections(
  monthlyKpis: FinancialSummaryMonthlyKpi[] | null | undefined,
): Trailing12Totals {
  return (monthlyKpis ?? []).slice(-12).reduce<Trailing12Totals>(
    (totals, row) => ({
      production: totals.production + toFiniteNumber(row.gross_production),
      collections: totals.collections + toFiniteNumber(row.collections),
    }),
    { production: 0, collections: 0 },
  );
}

export function buildProfitLossTrendData(rows: ProfitLossLike[] | null | undefined, maxRows?: number): ProfitLossTrendDatum[] {
  return sliceTrailingRows(
    (rows ?? []).map((row) => ({
      date: toNonEmptyString(row.year_month) || toNonEmptyString(row.period_end) || toNonEmptyString(row.period_start),
      expenses: toFiniteNumber(row.expense_total),
      netIncome: toFiniteNumber(row.net_income),
    })),
    maxRows,
  );
}

export function buildQuickBooksMonthlyExpenseTrendData(
  rows: FinancialSummaryQuickBooksMonthlyExpense[] | null | undefined,
  maxRows?: number,
): Array<{ date: string; expenses: number }> {
  return sliceTrailingRows(
    (rows ?? [])
      .map((row) => ({
        date: toNonEmptyString(row.year_month),
        expenses: toFiniteNumber(row.expense_total),
      }))
      .filter((row) => row.date),
    maxRows,
  );
}

export function sumTrailing12NetIncome(rows: ProfitLossLike[] | null | undefined): number | null {
  const trailingRows = buildProfitLossTrendData(rows).slice(-12);
  if (trailingRows.length === 0) {
    return null;
  }

  return trailingRows.reduce((total, row) => total + row.netIncome, 0);
}

function selectTopExpenseCategory(rows: FinancialSummaryQuickBooksExpenseCategory[] | null | undefined) {
  return (rows ?? [])
    .map((row) => ({
      label: toNonEmptyString(row.expense_category) || toNonEmptyString(row.account_name) || "Uncategorized",
      amount: toFiniteNumber(row.total_amount),
    }))
    .sort((left, right) => right.amount - left.amount || left.label.localeCompare(right.label))[0]?.label;
}

function isSoftdentArAvailable(
  latestAr: FinancialSummaryResponse["latestAr"],
): latestAr is NonNullable<FinancialSummaryResponse["latestAr"]> {
  if (!latestAr) {
    return false;
  }
  const availability = (latestAr as { available?: boolean }).available;
  return availability !== false;
}

export function buildDashboardSummaryFromFinancialSummary(
  financialSummary: FinancialSummaryResponse | null | undefined,
): FinancialDashboardSummary | null {
  if (!financialSummary) {
    return null;
  }

  const latestMonthlyKpi = selectLatestMonthlyKpi(financialSummary.monthlyKpis);
  const latestProfitLoss = selectLatestProfitLoss(financialSummary.quickBooksProfitLossSummary);
  const latestAr = financialSummary.latestAr;

  if (!latestMonthlyKpi && !latestProfitLoss && !isSoftdentArAvailable(latestAr)) {
    return null;
  }

  const latestSoftDentRefreshAt = toNonEmptyString(financialSummary.latestSoftDentRefreshAt);
  const lastRefreshed = toNonEmptyString(financialSummary.lastRefreshed);
  const generatedAt = toNonEmptyString(financialSummary.generatedAt);
  const refreshTimestamp = latestSoftDentRefreshAt || lastRefreshed || generatedAt || null;

  return {
    monthProduction: latestMonthlyKpi ? toFiniteNumber(latestMonthlyKpi.gross_production) : null,
    monthCollections: latestMonthlyKpi ? toFiniteNumber(latestMonthlyKpi.collections) : null,
    collectionPercent: latestMonthlyKpi ? toFiniteNumber(latestMonthlyKpi.collection_rate) : null,
    monthIncome: latestProfitLoss ? toFiniteNumber(latestProfitLoss.income_total) : null,
    monthExpenses: latestProfitLoss ? toFiniteNumber(latestProfitLoss.expense_total) : null,
    estimatedNetIncome: latestProfitLoss ? toFiniteNumber(latestProfitLoss.net_income) : null,
    topExpenseCategory: selectTopExpenseCategory(financialSummary.quickBooksExpenseCategories) ?? null,
    totalAR: isSoftdentArAvailable(latestAr) ? toFiniteNumber(latestAr.total_ar) : null,
    ar0to30: isSoftdentArAvailable(latestAr) ? toFiniteNumber(latestAr.current_balance) : null,
    ar31to60: isSoftdentArAvailable(latestAr) ? toFiniteNumber(latestAr.balance_30) : null,
    ar61to90: isSoftdentArAvailable(latestAr) ? toFiniteNumber(latestAr.balance_60) : null,
    arOver90: isSoftdentArAvailable(latestAr) ? toFiniteNumber(latestAr.balance_90) : null,
    lastImportAt: refreshTimestamp,
    lastRefreshedAt: refreshTimestamp,
    isStale: financialSummary.dataFreshnessStatus === "stale",
  };
}

export function buildQuickBooksExpenseCategoryData(
  financialSummary: FinancialSummaryResponse | null | undefined,
): QuickBooksExpenseCategoryDatum[] {
  const latestExpenseTotal = toFiniteNumber(selectLatestProfitLoss(financialSummary?.quickBooksProfitLossSummary)?.expense_total);

  return (financialSummary?.quickBooksExpenseCategories ?? [])
    .map((row) => {
      const amount = toFiniteNumber(row.total_amount);
      return {
        category: toNonEmptyString(row.expense_category) || toNonEmptyString(row.account_name) || "Uncategorized",
        amount,
        percent: latestExpenseTotal > 0 ? (amount / latestExpenseTotal) * 100 : 0,
      };
    })
    .filter((row) => row.category && row.amount > 0)
    .sort((left, right) => right.amount - left.amount || left.category.localeCompare(right.category));
}

export function buildFinancialSummaryProviderProduction(
  financialSummary: FinancialSummaryResponse | null | undefined,
): ProviderProduction[] {
  const totalsByProvider = new Map<string, ProviderProduction>();

  for (const row of financialSummary?.providerProduction ?? []) {
    if (!row || typeof row !== "object") {
      continue;
    }

    const record = row as FinancialSummaryProviderRowLike;
    const provider = toNonEmptyString(getRecordValue(record, "provider", "provider_name"));
    if (!provider) {
      continue;
    }

    const current = totalsByProvider.get(provider) ?? {
      provider,
      production: 0,
      collections: 0,
    };

    current.production += toFiniteNumber(getRecordValue(record, "production", "production_amount"));
    current.collections += toFiniteNumber(getRecordValue(record, "collections", "collection_amount"));
    totalsByProvider.set(provider, current);
  }

  return [...totalsByProvider.values()].sort((left, right) => right.production - left.production || left.provider.localeCompare(right.provider));
}

export function buildFinancialSummaryInsurancePatientTotals(
  financialSummary: FinancialSummaryResponse | null | undefined,
): InsurancePatientTotals {
  return (financialSummary?.providerProduction ?? []).reduce<InsurancePatientTotals>((totals, row) => {
    if (!row || typeof row !== "object") {
      return totals;
    }

    const record = row as FinancialSummaryProviderRowLike;
    return {
      insurance: totals.insurance + toFiniteNumber(getRecordValue(record, "insurance")),
      patient: totals.patient + toFiniteNumber(getRecordValue(record, "patient")),
    };
  }, { insurance: 0, patient: 0 });
}

export function buildLiveDashboardTrendData(rows: DashboardDataRowLike[] | null | undefined): DashboardTrendDatum[] {
  const totalsByPeriod = new Map<string, DashboardTrendDatum>();

  for (const row of rows ?? []) {
    const date = toNonEmptyString(row.period);
    if (!date) {
      continue;
    }

    const current = totalsByPeriod.get(date) ?? {
      date,
      production: 0,
      collections: 0,
    };

    current.production += toFiniteNumber(row.production);
    current.collections += toFiniteNumber(row.collections);
    totalsByPeriod.set(date, current);
  }

  return [...totalsByPeriod.values()].sort((left, right) => left.date.localeCompare(right.date));
}

export function buildLiveProviderProduction(rows: DashboardDataRowLike[] | null | undefined): ProviderProduction[] {
  const totalsByProvider = new Map<string, ProviderProduction>();

  for (const row of rows ?? []) {
    const provider = toNonEmptyString(row.provider);
    if (!provider) {
      continue;
    }

    const current = totalsByProvider.get(provider) ?? {
      provider,
      production: 0,
      collections: 0,
    };

    current.production += toFiniteNumber(row.production);
    current.collections += toFiniteNumber(row.collections);
    totalsByProvider.set(provider, current);
  }

  return [...totalsByProvider.values()].sort((left, right) => right.production - left.production || left.provider.localeCompare(right.provider));
}

export function buildLiveInsurancePatientTotals(rows: DashboardDataRowLike[] | null | undefined): { insurance: number; patient: number } {
  return (rows ?? []).reduce<{ insurance: number; patient: number }>(
    (totals, row) => ({
      insurance: totals.insurance + toFiniteNumber(row.insurance),
      patient: totals.patient + toFiniteNumber(row.patient),
    }),
    { insurance: 0, patient: 0 },
  );
}
