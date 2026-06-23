export type DashboardSummary = {
  todayProduction: number;
  monthProduction: number;
  monthCollections: number;
  collectionPercent: number;
  monthIncome: number;
  monthExpenses: number;
  estimatedNetIncome: number;
  topExpenseCategory: string;
  totalAR: number;
  ar0to30: number;
  ar31to60: number;
  ar61to90: number;
  arOver90: number;
  lastImportAt: string;
  lastRefreshedAt: string;
  isStale: boolean;
};

export type TrendPoint = {
  date: string;
  production: number;
  collections: number;
  expenses: number;
  netIncome: number;
};

export type ExpenseCategory = {
  category: string;
  amount: number;
  percent: number;
};

export type ProviderProduction = {
  provider: string;
  production: number;
  collections: number;
};

export type ARBucket = {
  bucket: string;
  amount: number;
  percent: number;
};

export type ImportRecord = {
  id: string;
  source: "softdent" | "quickbooks";
  reportType: string;
  fileName: string;
  importedAt: string;
  reportStartDate?: string;
  reportEndDate?: string;
  rowCount: number;
  status: "success" | "error" | "pending";
  errorMessage?: string;
};
