import type { ApiError } from "@/lib/api";
export function ApiFeedback({
  error,
  message,
}: {
  error: ApiError;
  message?: string;
}) {
  return (
    <div className="api-feedback" role="alert">
      <p>{message ?? error.message}</p>
      {import.meta.env.DEV && error.forbiddenReason === "untrusted-origin" && (
        <p className="development-guidance">
          Local setup: add <code>{window.location.origin}</code> to{" "}
          <code>CSRF_TRUSTED_ORIGINS</code> in the backend’s root{" "}
          <code>.env</code>, then restart the API. With Docker, run{" "}
          <code>docker compose up -d --wait --force-recreate api</code> from the
          repository root. Refreshing this page alone will not change that
          setting.
        </p>
      )}
      {error.retryAfter && (
        <p>
          Try again in about {Math.ceil(error.retryAfter / 60)}{" "}
          {error.retryAfter <= 60 ? "minute" : "minutes"}.
        </p>
      )}
      {error.requestId && (
        <small>
          Support reference: <code>{error.requestId}</code>
        </small>
      )}
    </div>
  );
}
