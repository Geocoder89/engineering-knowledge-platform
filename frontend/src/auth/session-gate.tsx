import { Link, Navigate, Outlet, useLocation } from "react-router";
import { Button } from "@/components/ui/button";
import { useSession } from "./session-context";
import { ApiFeedback } from "@/components/api-feedback";

export function SessionStatus() {
  const { session, refresh } = useSession();
  return (
    <main className="session-status">
      <div className="eyebrow">DECISION WORKSPACE</div>
      <h1>
        {session.status === "unavailable"
          ? "Let’s reconnect."
          : "Opening your workspace."}
      </h1>
      {session.status === "unavailable" ? (
        <>
          <ApiFeedback error={session.error} />
          <Button
            onClick={() => {
              void refresh();
            }}
          >
            Try again
          </Button>
        </>
      ) : (
        <p role="status">Checking your session…</p>
      )}
      <Link to="/preview" className="text-action">
        Explore the sample workspace
      </Link>
    </main>
  );
}
export function RequireSession() {
  const { session } = useSession();
  const location = useLocation();
  if (session.status === "loading" || session.status === "unavailable")
    return <SessionStatus />;
  if (session.status === "anonymous")
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname + location.search + location.hash }}
      />
    );
  return <Outlet />;
}
