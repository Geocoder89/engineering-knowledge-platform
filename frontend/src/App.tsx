import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router";
import { Layout } from "@/components/layout";
import { DecisionWorkspace } from "@/pages/decision-workspace";
import { DocumentLibrary, EvidenceSearch } from "@/pages/library";
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/decisions/DEC-024" replace />} />
          <Route path="decisions/DEC-024" element={<DecisionWorkspace />} />
          <Route path="documents" element={<DocumentLibrary />} />
          <Route path="search" element={<EvidenceSearch />} />
          <Route
            path="*"
            element={
              <div className="empty-state">
                <h1>This page isn't in the preview.</h1>
                <Link className="text-action" to="/decisions/DEC-024">
                  Return to the decision workspace
                </Link>
              </div>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
