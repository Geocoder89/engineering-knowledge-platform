import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { ArrowRight } from "lucide-react";
import { AuthLayout } from "@/components/auth-layout";
import { ApiFeedback } from "@/components/api-feedback";
import { Button } from "@/components/ui/button";
import { useAuthAction } from "@/auth/use-auth-action";
import { apiRequest } from "@/lib/api";

export function ResendVerificationPage() {
  const { busy, error, run } = useAuthAction();
  const [sent, setSent] = useState(false);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = String(
      new FormData(event.currentTarget).get("email") ?? "",
    ).trim();
    setSent(false);
    void run(async (signal) => {
      await apiRequest("/auth/resend-verification", {
        method: "POST",
        body: { email },
        signal,
        sessionRequired: false,
        expectedStatus: 202,
        responseType: "empty",
      });
      setSent(true);
    });
  }
  return (
    <AuthLayout
      title="A fresh link."
      description="Request another verification email to finish setting up your account."
    >
      {sent && (
        <p className="session-notice" role="status">
          If this email belongs to an account awaiting verification, a new link
          will be sent. Check your inbox and spam folder. Use the most recent
          link.
        </p>
      )}
      <form onSubmit={submit} aria-busy={busy}>
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
        {error && <ApiFeedback error={error} />}
        <Button type="submit" disabled={busy}>
          {busy ? "Requesting link…" : "Send verification link"}
          <ArrowRight size={16} />
        </Button>
      </form>
      <nav className="auth-links" aria-label="Account help">
        <Link to="/login">Back to sign in</Link>
        <Link to="/register">Create an account</Link>
      </nav>
    </AuthLayout>
  );
}
