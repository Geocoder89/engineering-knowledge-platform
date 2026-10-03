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
