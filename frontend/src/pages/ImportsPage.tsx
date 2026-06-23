import ImportPanel from "../components/dashboard/ImportPanel";

export default function ImportsPage() {
  return (
    <div className="dashboard-page">
      <div className="page-content">
        <header className="page-header">
          <p className="eyebrow">Data Imports</p>
          <h1>Imports</h1>
          <p>Import SoftDent and QuickBooks files through the canonical staging and backend refresh pipeline.</p>
        </header>
        <ImportPanel />
      </div>
    </div>
  );
}
