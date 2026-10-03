import { useState } from "react";
import { Link } from "react-router";
import { ArrowUpRight, CheckCircle2, Layers, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiFeedback } from "@/components/api-feedback";
import { ApiError, asApiError } from "@/lib/api";
import { useSession } from "@/auth/session-context";

export function WorkspaceHome() {
  const { session, signOut } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  if (session.status !== "authenticated") return null;
  const { user } = session;
  async function logout() {
    setBusy(true);
    setError(null);
    try {
      await signOut();
    } catch (failure) {
      setError(asApiError(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="account-page">
      <header className="account-header">
        <Link className="brand" to="/workspace">
          <Layers size={25} strokeWidth={1.4} />
          <span>
            Decision<span className="brand-second">workspace</span>
          </span>
        </Link>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => {
            void logout();
          }}
        >
          <LogOut size={15} />
          {busy ? "Signing out…" : "Sign out"}
        </Button>
      </header>
      <main className="account-main">
        <div className="page-heading-row">
          <span className="eyebrow">YOUR WORKSPACE</span>
          <span className="status-badge ready">
            <CheckCircle2 size={12} /> Signed in
          </span>
        </div>
        <h1>
          Welcome back,
          <br />
          <em>{user.display_name}.</em>
        </h1>
        <p className="intro-description">
          A clear place for the decisions that matter.
        </p>
        {error && <ApiFeedback error={error} />}
        <section className="account-record" aria-labelledby="account-heading">
          <h2 id="account-heading">Your account</h2>
          <dl>
            <div>
              <dt>Name</dt>
              <dd>{user.display_name}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{user.email}</dd>
            </div>
          </dl>
        </section>
        <section className="account-next">
          <div className="eyebrow">EXPLORE THE WORKFLOW</div>
          <h2>See the reasoning take shape.</h2>
          <p>
            Your document and decision tools are being connected. In the
            meantime, explore the sample workspace with fictional records.
            Sample edits do not affect your account.
          </p>
          <Button asChild>
            <Link to="/preview">
              Open sample workspace <ArrowUpRight size={16} />
            </Link>
          </Button>
        </section>
      </main>
      <footer className="app-footer">
        <span>KNOWLEDGE & DECISION PLATFORM</span>
        <span>Account details loaded from your session</span>
      </footer>
    </div>
  );
}
