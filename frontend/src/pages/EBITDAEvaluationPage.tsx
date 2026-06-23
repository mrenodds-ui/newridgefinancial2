import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { fetchFinancialSummary } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { selectLatestProfitLoss } from "../components/dashboard/financialDashboardSummary";
import { SourceReviewContent } from "../components/dashboard/SourceReviewContent";

function toNumber(value: number | string | null | undefined) {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

export default function EBITDAEvaluationPage() {
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
  });

  if (financialSummaryQuery.isPending) {
    return (
      <div className="dashboard-page">
        <LoadingSpinner label="Loading EBITDA inputs..." />
      </div>
    );
  }

  if (financialSummaryQuery.isError || !financialSummaryQuery.data) {
    return (
      <div className="dashboard-page">
        <div className="page-state-card page-state-card--error">Unable to load live QuickBooks EBITDA data.</div>
      </div>
    );
  }

  const financialSummary = financialSummaryQuery.data;
  // Editable inputs
  const [ownerAdj, setOwnerAdj] = useState(60000);
  const [replacementDoc, setReplacementDoc] = useState(220000);
  const [addBacks, setAddBacks] = useState(15000);
  const [lowMult, setLowMult] = useState(3.5);
  const [midMult, setMidMult] = useState(4.5);
  const [highMult, setHighMult] = useState(5.5);

  const latestProfitLoss = selectLatestProfitLoss(financialSummary.quickBooksProfitLossSummary);
  const latestEbitdaCandidate = selectLatestProfitLoss(financialSummary.quickBooksEbitdaCandidates);
  const netIncome = toNumber(latestProfitLoss?.net_income);
  const adjustedEBITDA = netIncome + addBacks + ownerAdj - replacementDoc;
  const revenue = toNumber(latestProfitLoss?.income_total);
  const sourceEbitda = toNumber(latestEbitdaCandidate?.base_ebitda_candidate);
  const ebitdaMargin = revenue > 0 ? Math.round((adjustedEBITDA / revenue) * 100) : 0;
  const lowVal = adjustedEBITDA * lowMult;
  const midVal = adjustedEBITDA * midMult;
  const highVal = adjustedEBITDA * highMult;
  const quickBooksReview = financialSummary.sourceReview?.quickBooks ?? null;

  return (
    <div className="dashboard-page">
      <h1>EBITDA Evaluation</h1>
      <div className="dashboard-description">Practice sale and DSO readiness analysis using live QuickBooks profit and loss data.</div>
      <section className="dashboard-import-history">
        <h2>QuickBooks Source Review</h2>
        <SourceReviewContent review={quickBooksReview} emptyMessage="QuickBooks source review metadata is unavailable." />
      </section>
      <div className="kpi-grid">
        <div className="dashboard-card">
          <div className="kpi-title">Net Income</div>
          <div className="kpi-value">${netIncome.toLocaleString()}</div>
        </div>
        <div className="dashboard-card">
          <div className="kpi-title">Adjusted EBITDA</div>
          <div className="kpi-value">${adjustedEBITDA.toLocaleString()}</div>
        </div>
        <div className="dashboard-card">
          <div className="kpi-title">EBITDA Margin</div>
          <div className="kpi-value">{ebitdaMargin}%</div>
        </div>
        <div className="dashboard-card">
          <div className="kpi-title">Source EBITDA Candidate</div>
          <div className="kpi-value">${sourceEbitda.toLocaleString()}</div>
        </div>
      </div>
      <div className="dashboard-ebitda-inputs">
        <h2>Editable Inputs</h2>
        <label>
          Owner Comp Adjustment: <input type="number" value={ownerAdj} onChange={(e) => setOwnerAdj(Number(e.target.value))} />
        </label>
        <label>
          Replacement Doctor Cost:{" "}
          <input type="number" value={replacementDoc} onChange={(e) => setReplacementDoc(Number(e.target.value))} />
        </label>
        <label>
          Add-backs: <input type="number" value={addBacks} onChange={(e) => setAddBacks(Number(e.target.value))} />
        </label>
        <label>
          Low Multiple: <input type="number" step="0.1" value={lowMult} onChange={(e) => setLowMult(Number(e.target.value))} />
        </label>
        <label>
          Mid Multiple: <input type="number" step="0.1" value={midMult} onChange={(e) => setMidMult(Number(e.target.value))} />
        </label>
        <label>
          High Multiple: <input type="number" step="0.1" value={highMult} onChange={(e) => setHighMult(Number(e.target.value))} />
        </label>
      </div>
      <div className="dashboard-ebitda-valuation">
        <h2>Valuation Range</h2>
        <div>
          Low: <strong>${lowVal.toLocaleString()}</strong>
        </div>
        <div>
          Mid: <strong>${midVal.toLocaleString()}</strong>
        </div>
        <div>
          High: <strong>${highVal.toLocaleString()}</strong>
        </div>
      </div>
      <div className="dashboard-ebitda-notes">
        <h2>Notes</h2>
        <div>
          Owner compensation, replacement doctor cost, and add-backs remain editable assumptions layered on top of the latest QuickBooks net
          income.
        </div>
      </div>
    </div>
  );
}
