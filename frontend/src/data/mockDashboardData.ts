export const mockCaseAcceptance = {
  presented: 120,
  accepted: 90,
};

export const mockNoShowRate = [
  { date: "2025-06", noShowRate: 7 },
  { date: "2025-07", noShowRate: 8 },
  { date: "2025-08", noShowRate: 6 },
  { date: "2025-09", noShowRate: 9 },
  { date: "2025-10", noShowRate: 7 },
  { date: "2025-11", noShowRate: 8 },
  { date: "2025-12", noShowRate: 7 },
  { date: "2026-01", noShowRate: 6 },
  { date: "2026-02", noShowRate: 7 },
  { date: "2026-03", noShowRate: 8 },
  { date: "2026-04", noShowRate: 7 },
  { date: "2026-05", noShowRate: 6 },
];

export const mockPatientFlow = [
  { date: "2025-06", newPatients: 30, returningPatients: 120 },
  { date: "2025-07", newPatients: 32, returningPatients: 118 },
  { date: "2025-08", newPatients: 28, returningPatients: 122 },
  { date: "2025-09", newPatients: 35, returningPatients: 115 },
  { date: "2025-10", newPatients: 33, returningPatients: 117 },
  { date: "2025-11", newPatients: 31, returningPatients: 119 },
  { date: "2025-12", newPatients: 29, returningPatients: 121 },
  { date: "2026-01", newPatients: 34, returningPatients: 116 },
  { date: "2026-02", newPatients: 32, returningPatients: 118 },
  { date: "2026-03", newPatients: 30, returningPatients: 120 },
  { date: "2026-04", newPatients: 33, returningPatients: 117 },
  { date: "2026-05", newPatients: 31, returningPatients: 119 },
];

export const mockInsurancePatientBreakdown = {
  insurance: 60000,
  patient: 19000,
};
import type { ARBucket, DashboardSummary, ExpenseCategory, ImportRecord, ProviderProduction, TrendPoint } from "../types/dashboard";
export const mockARAging: ARBucket[] = [
  { bucket: "0–30", amount: 32000, percent: 47.8 },
  { bucket: "31–60", amount: 18000, percent: 26.9 },
  { bucket: "61–90", amount: 9000, percent: 13.4 },
  { bucket: "90+", amount: 8000, percent: 11.9 },
];

export const mockImportHistory: ImportRecord[] = [
  {
    id: "1",
    source: "softdent",
    reportType: "Production",
    fileName: "softdent_production_jan2026.xlsx",
    importedAt: "2026-05-25T08:30:00Z",
    reportStartDate: "2026-01-01",
    reportEndDate: "2026-01-31",
    rowCount: 100,
    status: "success",
  },
  {
    id: "2",
    source: "quickbooks",
    reportType: "Profit and Loss",
    fileName: "quickbooks_pnl_jan2026.csv",
    importedAt: "2026-05-25T08:31:00Z",
    reportStartDate: "2026-01-01",
    reportEndDate: "2026-01-31",
    rowCount: 50,
    status: "success",
  },
];

export const mockDashboardSummary: DashboardSummary = {
  todayProduction: 4200,
  monthProduction: 82000,
  monthCollections: 79000,
  collectionPercent: 96.3,
  monthExpenses: 54000,
  monthIncome: 82000,
  estimatedNetIncome: 25000,
  topExpenseCategory: "Staff Salaries",
  totalAR: 67000,
  ar0to30: 32000,
  ar31to60: 18000,
  ar61to90: 9000,
  arOver90: 8000,
  lastImportAt: "2026-05-25T08:30:00Z",
  lastRefreshedAt: new Date().toISOString(),
  isStale: false,
};

export const mockTrendData: TrendPoint[] = [
  {
    date: "2025-06",
    production: 70000,
    collections: 68000,
    expenses: 48000,
    netIncome: 20000,
  },
  {
    date: "2025-07",
    production: 72000,
    collections: 69000,
    expenses: 49000,
    netIncome: 20000,
  },
  {
    date: "2025-08",
    production: 75000,
    collections: 71000,
    expenses: 50000,
    netIncome: 21000,
  },
  {
    date: "2025-09",
    production: 78000,
    collections: 74000,
    expenses: 52000,
    netIncome: 22000,
  },
  {
    date: "2025-10",
    production: 80000,
    collections: 76000,
    expenses: 53000,
    netIncome: 23000,
  },
  {
    date: "2025-11",
    production: 82000,
    collections: 79000,
    expenses: 54000,
    netIncome: 25000,
  },
  {
    date: "2025-12",
    production: 83000,
    collections: 80000,
    expenses: 55000,
    netIncome: 25000,
  },
  {
    date: "2026-01",
    production: 81000,
    collections: 78000,
    expenses: 54000,
    netIncome: 24000,
  },
  {
    date: "2026-02",
    production: 82000,
    collections: 79000,
    expenses: 54000,
    netIncome: 25000,
  },
  {
    date: "2026-03",
    production: 83000,
    collections: 80000,
    expenses: 55000,
    netIncome: 25000,
  },
  {
    date: "2026-04",
    production: 82000,
    collections: 79000,
    expenses: 54000,
    netIncome: 25000,
  },
  {
    date: "2026-05",
    production: 82000,
    collections: 79000,
    expenses: 54000,
    netIncome: 25000,
  },
];

export const mockExpenseCategories: ExpenseCategory[] = [
  { category: "Staff Salaries", amount: 22000, percent: 40.7 },
  { category: "Supplies", amount: 7000, percent: 13.0 },
  { category: "Rent", amount: 6000, percent: 11.1 },
  { category: "Lab Fees", amount: 4000, percent: 7.4 },
  { category: "Utilities", amount: 2000, percent: 3.7 },
  { category: "Other", amount: 13000, percent: 24.1 },
];

export const mockProviderProduction: ProviderProduction[] = [
  { provider: "Dr. Smith", production: 42000, collections: 40000 },
  { provider: "Dr. Lee", production: 25000, collections: 24000 },
  { provider: "Dr. Patel", production: 15000, collections: 15000 },
];
