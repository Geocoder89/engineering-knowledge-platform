import { Link, NavLink, Outlet } from "react-router";
import { Layers, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiFeedback } from "@/components/api-feedback";
import { useSession } from "@/auth/session-context";
import { useAuthAction } from "@/auth/use-auth-action";

export function WorkspaceLayout() {
  const { signOut } = useSession();
  const { busy, error, run } = useAuthAction();
  return (
    <div className="account-page">
      <header className="account-header">
        <Link className="brand" to="/workspace">
          <Layers size={25} strokeWidth={1.4} />
          <span>
            Decision<span className="brand-second">workspace</span>
          </span>
        </Link>
        <nav className="workspace-nav" aria-label="Workspace">
          <NavLink to="/workspace/decisions">Decisions</NavLink>
          <NavLink to="/workspace" end>
            Account
          </NavLink>
        </nav>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => {
            void run(async () => {
              await signOut();
            });
          }}
        >
          <LogOut size={15} />
          {busy ? "Signing out…" : "Sign out"}
        </Button>
      </header>
      <main className="account-main">
        {error && <ApiFeedback error={error} />}
        <Outlet />
      </main>
      <footer className="app-footer">
        <span>KNOWLEDGE & DECISION PLATFORM</span>
        <span>Your account · Your decisions</span>
      </footer>
    </div>
  );
}
