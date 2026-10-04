import { useEffect, useState } from "react";
import { apiRequest, asApiError, type ApiError } from "./api";
type Resource<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; error: ApiError };
export function useApiResource<T>(
  path: string | null,
  parse: (value: unknown) => T,
) {
  const [attempt, setAttempt] = useState(0);
  const key = `${path}:${attempt}`;
  const [result, setResult] = useState<{
    key: string;
    resource: Resource<T>;
  } | null>(null);
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    void apiRequest<unknown>(path, {
      signal: controller.signal,
      expectedStatus: 200,
    })
      .then((value) => {
        if (!controller.signal.aborted)
          setResult({ key, resource: { status: "ready", data: parse(value) } });
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setResult({
            key,
            resource: { status: "error", error: asApiError(error) },
          });
      });
    return () => controller.abort();
  }, [path, parse, key]);
  // Hide results immediately when the route or retry changes, before effects run.
  const resource: Resource<T> =
    result?.key === key ? result.resource : { status: "loading" };
  return { resource, retry: () => setAttempt((value) => value + 1) };
}
