import type { ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./layout/AppShell";
import ARCollectionsPage from "./pages/ARCollectionsPage";
import AccountingDocumentsPage from "./pages/AccountingDocumentsPage";
import AccountingPolicyPage from "./pages/AccountingPolicyPage";
import AdminPage from "./pages/AdminPage";
import AskHal9000Page from "./pages/AskHal9000Page";
import ClaimsWorkbenchPage from "./pages/ClaimsWorkbenchPage";
import DashboardPage from "./pages/DashboardPage";
import DocumentLibraryPage from "./pages/DocumentLibraryPage";
import EBITDAEvaluationPage from "./pages/EBITDAEvaluationPage";
import ExpensesPage from "./pages/ExpensesPage";
import HalLandingPage from "./pages/HalLandingPage";
import JournalDraftPage from "./pages/JournalDraftPage";
import PostingQueueReviewPage from "./pages/PostingQueueReviewPage";
import QuickBooksPage from "./pages/QuickBooksPage";
import SettingsPage from "./pages/SettingsPage";
import SoftDentPage from "./pages/SoftDentPage";
import TrendsPage from "./pages/TrendsPage";
import RequireApiAuth from "./components/RequireApiAuth";

const DASHBOARD_READ_ROLE = "dashboard:read";
const HAL_OPERATOR_ROLE = "hal:operator";

function requireApiAuth(resourceName: string, element: ReactElement, requiredRoles?: readonly string[]) {
  return (
    <RequireApiAuth resourceName={resourceName} requiredRoles={requiredRoles}>
      {element}
    </RequireApiAuth>
  );
}

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/softdent" element={requireApiAuth("the SoftDent financial page", <SoftDentPage />, [DASHBOARD_READ_ROLE])} />
        <Route path="/quickbooks" element={requireApiAuth("the QuickBooks financial page", <QuickBooksPage />, [DASHBOARD_READ_ROLE])} />
        <Route path="/ebitda" element={requireApiAuth("the EBITDA evaluation page", <EBITDAEvaluationPage />, [DASHBOARD_READ_ROLE])} />
        <Route path="/expenses" element={requireApiAuth("the expense analysis page", <ExpensesPage />, [DASHBOARD_READ_ROLE])} />
        <Route path="/ar" element={requireApiAuth("the A/R and collections page", <ARCollectionsPage />, [DASHBOARD_READ_ROLE])} />
        <Route path="/trends" element={requireApiAuth("the trends page", <TrendsPage />, [DASHBOARD_READ_ROLE])} />
        <Route path="/admin" element={<AdminPage />} />
        <Route
          path="/claims-workbench"
          element={requireApiAuth("the claims workbench", <ClaimsWorkbenchPage />, [HAL_OPERATOR_ROLE, DASHBOARD_READ_ROLE])}
        />
        <Route path="/accounting-documents" element={requireApiAuth("the accounting documents page", <AccountingDocumentsPage />, [HAL_OPERATOR_ROLE])} />
        <Route path="/document-library" element={requireApiAuth("the document library", <DocumentLibraryPage />, [HAL_OPERATOR_ROLE])} />
        <Route path="/accounting-policy" element={requireApiAuth("the accounting policy guidance page", <AccountingPolicyPage />, [HAL_OPERATOR_ROLE])} />
        <Route path="/posting-queue" element={requireApiAuth("the posting queue review page", <PostingQueueReviewPage />, [HAL_OPERATOR_ROLE])} />
        <Route path="/hal" element={requireApiAuth("the Ask Hal 9000 page", <AskHal9000Page />, [HAL_OPERATOR_ROLE, DASHBOARD_READ_ROLE])} />
        <Route path="/hal-9000" element={<Navigate to="/hal" replace />} />
        <Route path="/hal-landing" element={requireApiAuth("the HAL landing page", <HalLandingPage />, [DASHBOARD_READ_ROLE])} />
        <Route path="/journal-draft" element={requireApiAuth("the journal draft review page", <JournalDraftPage />, [HAL_OPERATOR_ROLE])} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
