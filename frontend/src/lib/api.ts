export const SESSION_EXPIRED_EVENT = "decision:session-expired";
const csrfCookieName = import.meta.env.VITE_CSRF_COOKIE_NAME || "decision_csrf";

export type ForbiddenReason = "untrusted-origin" | "invalid-csrf" | null;

export class ApiError extends Error {
  readonly status: number;
  readonly forbiddenReason: ForbiddenReason;
  readonly requestId: string | null;
  readonly retryAfter: number | null;
  constructor(
    message: string,
    status = 0,
    requestId: string | null = null,
    retryAfter: number | null = null,
    forbiddenReason: ForbiddenReason = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.forbiddenReason = forbiddenReason;
    this.requestId = requestId;
    this.retryAfter = retryAfter;
  }
}

function csrfToken(): string | undefined {
  const cookie = document.cookie
    .split("; ")
    .find((value) => value.startsWith(`${csrfCookieName}=`));
  if (!cookie) return undefined;
  try {
    return decodeURIComponent(cookie.slice(csrfCookieName.length + 1));
  } catch {
    return undefined;
  }
}

function failureMessage(status: number, reason: ForbiddenReason): string {
  if (reason === "untrusted-origin")
    return "This app address is not allowed to contact the service. Use the configured app address or contact the administrator.";
  if (reason === "invalid-csrf")
    return "Your browser security token is missing or no longer valid. Clear this app’s cookies and sign in again.";
  if (status === 401) return "Your session has ended. Please sign in again.";
  if (status === 403)
    return "You do not have permission to complete this request. Contact the administrator if you need access.";
  if (status === 429)
    return "Too many attempts. Please wait before trying again.";
  if (status === 422) return "Please check the information you entered.";
  return "The service could not complete this request. Please try again.";
}

/** All browser requests stay on this origin. The dev/reverse proxy strips /api. */
export async function apiRequest<T>(
  path: string,
  options: {
    method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    body?: unknown;
    signal?: AbortSignal;
    sessionRequired?: boolean;
    expectedStatus?: number;
    responseType?: "json" | "empty";
  } = {},
): Promise<T> {
  if (!path.startsWith("/") || path.startsWith("//"))
    throw new Error("API paths must be relative to /api");
  const method = options.method ?? "GET";
  const headers = new Headers({ Accept: "application/json" });
  if (options.body !== undefined)
    headers.set("Content-Type", "application/json");
  if (method !== "GET") {
    const token = csrfToken();
    if (token) headers.set("X-CSRF-Token", token);
  }
  let response: Response;
  try {
    const timeout = AbortSignal.timeout(10000);
    response = await fetch(`/api${path}`, {
      method,
      headers,
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
      body:
        options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal
        ? AbortSignal.any([options.signal, timeout])
        : timeout,
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError(
      "We could not reach the service. Check your connection and try again.",
    );
  }
  // Never surface raw backend details, validation input, or HTML error pages.
  const requestId = response.headers.get("X-Request-ID");
  if (!response.ok) {
    if (response.status === 401 && options.sessionRequired !== false)
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    // Recognize only these public middleware responses; never echo arbitrary details.
    let reason: ForbiddenReason = null;
    if (
      response.status === 403 &&
      response.headers.get("Content-Type")?.includes("application/json")
    ) {
      try {
        const body: unknown = await response.json();
        if (body && typeof body === "object" && "detail" in body) {
          if (body.detail === "Request origin is not allowed")
            reason = "untrusted-origin";
          if (body.detail === "CSRF token is invalid") reason = "invalid-csrf";
        }
      } catch {
        /* An unreadable error body uses the safe status-based fallback. */
      }
    }
    const seconds = Number(response.headers.get("Retry-After"));
    throw new ApiError(
      failureMessage(response.status, reason),
      response.status,
      requestId,
      response.status === 429 && Number.isFinite(seconds) && seconds > 0
        ? seconds
        : null,
      reason,
    );
  }
  if (options.expectedStatus && response.status !== options.expectedStatus)
    throw new ApiError(
      "The service returned an unexpected response. Please try again.",
      response.status,
      requestId,
    );
  if (response.status === 204 || options.responseType === "empty")
    return undefined as T;
  if (!response.headers.get("Content-Type")?.includes("application/json"))
    throw new ApiError(
      "The service returned an unexpected response. Please try again.",
      response.status,
      requestId,
    );
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(
      "The service returned an unexpected response. Please try again.",
      response.status,
      requestId,
    );
  }
}

export function asApiError(error: unknown): ApiError {
  return error instanceof ApiError
    ? error
    : new ApiError("Something went wrong. Please try again.");
}
