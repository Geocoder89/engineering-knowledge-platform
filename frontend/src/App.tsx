import {
  BrowserRouter,
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router";
import { Layout } from "@/components/layout";
import { DecisionWorkspace } from "@/pages/decision-workspace";
import { DocumentLibrary, EvidenceSearch } from "@/pages/library";
import { SessionProvider } from "@/auth/session-provider";
import { RequireSession } from "@/auth/session-gate";
import { LoginPage } from "@/pages/login";
import { WorkspaceHome } from "@/pages/workspace-home";
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <SessionProvider>
              <Outlet />
            </SessionProvider>
          }
        >
          <Route index element={<Navigate to="/workspace" replace />} />
          <Route path="login" element={<LoginPage />} />
          <Route element={<RequireSession />}>
            <Route path="workspace" element={<WorkspaceHome />} />
          </Route>
        </Route>
        <Route path="preview" element={<Layout />}>
          <Route index element={<Navigate to="decisions/DEC-024" replace />} />
          <Route path="decisions/DEC-024" element={<DecisionWorkspace />} />
          <Route path="documents" element={<DocumentLibrary />} />
          <Route path="search" element={<EvidenceSearch />} />
          <Route
            path="*"
            element={
              <div className="empty-state">
                <h1>This page isn't in the preview.</h1>
                <Link className="text-action" to="/preview/decisions/DEC-024">
                  Return to the decision workspace
                </Link>
              </div>
            }
          />
        </Route>
        <Route
          path="*"
          element={
            <main className="session-status">
              <h1>Page not found.</h1>
              <Link to="/workspace" className="text-action">
                Return to your workspace
              </Link>
            </main>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
