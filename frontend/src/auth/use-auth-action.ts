import { useEffect, useRef, useState } from "react";
import { asApiError, type ApiError } from "@/lib/api";

export function useAuthAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  async function run(action: (signal: AbortSignal) => Promise<void>) {
    if (request.current && !request.current.signal.aborted) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError(null);
    try {
      await action(controller.signal);
    } catch (failure) {
      if (!controller.signal.aborted) setError(asApiError(failure));
    } finally {
      if (!controller.signal.aborted) setBusy(false);
      if (request.current === controller) request.current = null;
    }
  }
  return { busy, error, run };
}
