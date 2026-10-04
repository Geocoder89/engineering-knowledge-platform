import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { ArrowRight, MailCheck } from "lucide-react";
import { AuthLayout } from "@/components/auth-layout";
import { ApiFeedback } from "@/components/api-feedback";
import { Button } from "@/components/ui/button";
import { useAuthAction } from "@/auth/use-auth-action";
import { apiRequest } from "@/lib/api";

export function RegisterPage() {
  const { busy, error, run } = useAuthAction();
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [validation, setValidation] = useState<string | null>(null);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const displayName = String(form.get("display_name") ?? "").trim();
    const password = String(form.get("password") ?? "");
    if (!displayName || !password.trim()) {
      setValidation("Enter a display name and a password that are not blank.");
      return;
    }
    setValidation(null);
    void run(async (signal) => {
      await apiRequest("/auth/register", {
        method: "POST",
        body: { email, display_name: displayName, password },
        signal,
        sessionRequired: false,
        expectedStatus: 201,
      });
      setSentTo(email);
    });
  }
  return (
    <AuthLayout
      title={sentTo ? "Check your inbox." : "Start with a question."}
      description={
        sentTo
          ? "One more step before your first decision."
          : "Create an account to keep your evidence and decisions together."
      }
    >
      {sentTo ? (
        <>
          <div className="auth-success" role="status">
            <MailCheck aria-hidden="true" size={28} />
            <p>
              We sent a verification link to <strong>{sentTo}</strong>.
            </p>
            <p>
              Open the link, verify your email, then sign in. Check your spam
              folder if it has not arrived.
            </p>
          </div>
          <nav className="auth-links" aria-label="Next steps">
            <Link to="/login">
              Go to sign in <ArrowRight size={14} />
            </Link>
            <Link to="/resend-verification">Resend verification email</Link>
            <button type="button" onClick={() => setSentTo(null)}>
              Use a different email
            </button>
          </nav>
        </>
      ) : (
        <>
          <form onSubmit={submit} aria-busy={busy}>
            <label htmlFor="display-name">Display name</label>
            <input
              id="display-name"
              name="display_name"
              autoComplete="name"
              required
              maxLength={200}
              disabled={busy}
            />
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              maxLength={320}
              disabled={busy}
            />
            <label htmlFor="password">Password</label>
            <p id="password-help" className="field-help">
              Use 12–128 characters. A memorable passphrase works well.
            </p>
            <div className="password-field">
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                aria-describedby="password-help"
                required
                minLength={12}
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
            {validation && (
              <p className="api-feedback" role="alert">
                {validation}
              </p>
            )}
            {error && (
              <ApiFeedback
                error={error}
                message={
                  error.status === 409
                    ? "We could not create this account. Try signing in or requesting a verification email."
                    : error.status === 503
                      ? "We could not send your verification email. Please try again later."
                      : undefined
                }
              />
            )}
            <Button type="submit" disabled={busy}>
              {busy ? "Creating account…" : "Create account"}
              <ArrowRight size={16} />
            </Button>
          </form>
          <nav className="auth-links" aria-label="Account help">
            <Link to="/login">Already have an account? Sign in</Link>
            <Link to="/resend-verification">Resend verification email</Link>
          </nav>
        </>
      )}
    </AuthLayout>
  );
}
