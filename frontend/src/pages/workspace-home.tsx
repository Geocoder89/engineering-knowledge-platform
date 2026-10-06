import { Link } from "react-router";
import { ArrowUpRight, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSession } from "@/auth/session-context";

export function WorkspaceHome() {
  const { session } = useSession();
  if (session.status !== "authenticated") return null;
  const { user } = session;
  return (
    <>
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
        <div className="eyebrow">YOUR DECISION RECORDS</div>
        <h2>Give the next decision a place.</h2>
        <p>
          Create a decision, capture the question, and return to its saved
          record.
        </p>
        <Button asChild>
          <Link to="/workspace/decisions">
            Open your decisions <ArrowUpRight size={16} />
          </Link>
        </Button>
      </section>
      <section className="account-next">
        <div className="eyebrow">EXPLORE THE WORKFLOW</div>
        <h2>See the reasoning take shape.</h2>
        <p>
          Explore alternatives, evidence, and review in the sample workspace.
          These fictional records are separate from your saved decisions.
        </p>
        <Button asChild>
          <Link to="/preview">
            Open sample workspace <ArrowUpRight size={16} />
          </Link>
        </Button>
      </section>
    </>
  );
}
