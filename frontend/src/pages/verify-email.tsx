import { useEffect, useState } from "react";
import { Link } from "react-router";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { AuthLayout } from "@/components/auth-layout";
import { ApiFeedback } from "@/components/api-feedback";
import { Button } from "@/components/ui/button";
import { useAuthAction } from "@/auth/use-auth-action";
import { apiRequest } from "@/lib/api";
import {
  forgetVerificationToken,
  getVerificationToken,
} from "@/lib/verification-link";

export function VerifyEmailPage() {
  const [token, setToken] = useState(getVerificationToken);
  const [verified, setVerified] = useState(false);
  const { busy, error, run } = useAuthAction();
  useEffect(() => {
    forgetVerificationToken();
  }, []);
  const invalid = error?.status === 400 || error?.status === 422;
  function verify() {
    if (!token) return;
    void run(async (signal) => {
      await apiRequest("/auth/verify-email", {
        method: "POST",
        body: { verification_token: token },
        signal,
        sessionRequired: false,
        expectedStatus: 204,
        responseType: "empty",
      });
      setToken(null);
      setVerified(true);
    });
  }
  return (
    <AuthLayout
      title={verified ? "Email verified." : "Make it yours."}
      description={
        verified
          ? "Your account is ready. Sign in to enter your workspace."
          : "Confirm your email to complete your account setup."
      }
    >
      {verified ? (
        <div className="auth-success" role="status">
          <CheckCircle2 aria-hidden="true" size={28} />
          <p>Your email has been verified. You can now sign in.</p>
        </div>
      ) : !token ? (
        <p className="session-notice" role="status">
          This page needs a verification link. Open the complete link from your
          email, or request a new one below. If you refreshed this page, reopen
          the email link.
        </p>
      ) : (
        <>
          <p className="field-help verification-note">
            Ready to finish? Confirm below to use this verification link. It can
            only be used once.
          </p>
          {error && (
            <ApiFeedback
              error={error}
              message={
                invalid
                  ? "This verification link is invalid, expired, or already used. Try signing in if you have already verified, or request a new link."
                  : undefined
              }
            />
          )}
          {!invalid && (
            <Button
              className="verification-button"
              onClick={verify}
              disabled={busy}
            >
              {busy ? "Verifying email…" : "Verify email"}
              <ArrowRight size={16} />
            </Button>
          )}
        </>
      )}
      <nav className="auth-links" aria-label="Next steps">
        <Link to="/login">
          Go to sign in <ArrowRight size={14} />
        </Link>
        {!verified && (
          <Link to="/resend-verification">Request a new verification link</Link>
        )}
      </nav>
    </AuthLayout>
  );
}
