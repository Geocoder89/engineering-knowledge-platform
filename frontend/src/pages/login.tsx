import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation } from "react-router";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiFeedback } from "@/components/api-feedback";
import { ApiError, asApiError } from "@/lib/api";
import { useSession } from "@/auth/session-context";
import { AuthLayout } from "@/components/auth-layout";
import { SessionStatus } from "@/auth/session-gate";

export function LoginPage() {
  const { session, signIn } = useSession();
  const location = useLocation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  // Only workspace-relative destinations are accepted; external redirects are rejected.
  const from: unknown = location.state?.from;
  const destination =
    typeof from === "string" && /^\/workspace(?:\/|[?#]|$)/.test(from)
      ? from
      : "/workspace";
  if (session.status === "loading" || session.status === "unavailable")
    return <SessionStatus />;
  if (session.status === "authenticated")
    return <Navigate to={destination} replace />;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await signIn(
        String(form.get("email") ?? "").trim(),
        String(form.get("password") ?? ""),
      );
    } catch (failure) {
      setError(asApiError(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthLayout
      title="Welcome back."
      description="Sign in with your verified account to continue."
    >
      {session.reason === "expired" && (
        <p className="session-notice" role="status">
          Your session has ended. Sign in again to continue.
        </p>
      )}
      {session.reason === "logout" && (
        <p className="session-notice" role="status">
          You have been signed out.
        </p>
      )}
      <form onSubmit={submit} aria-busy={busy}>
        <label htmlFor="email">Email address</label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          required
          maxLength={320}
          disabled={busy}
        />
        <label htmlFor="password">Password</label>
        <div className="password-field">
          <input
            id="password"
            name="password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            required
            maxLength={128}
            disabled={busy}
          />
          <button
            type="button"
            aria-label={showPassword ? "Hide password" : "Show password"}
            aria-pressed={showPassword}
            onClick={() => setShowPassword((value) => !value)}
          >
            {showPassword ? "Hide" : "Show"}
          </button>
        </div>
        {error && (
          <ApiFeedback
            error={error}
            message={
              error.status === 401
                ? "We could not sign you in. Check your email and password, and make sure your email is verified."
                : undefined
            }
          />
        )}
        <Button type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
          <ArrowRight size={16} />
        </Button>
      </form>
      <nav className="auth-links" aria-label="Account help">
        <Link to="/register">Create an account</Link>
        <Link to="/resend-verification">Resend verification email</Link>
      </nav>
      <div className="login-preview">
        <span>Want to look around first?</span>
        <Link to="/preview">
          Explore the sample workspace <ArrowRight size={14} />
        </Link>
      </div>
    </AuthLayout>
  );
}
