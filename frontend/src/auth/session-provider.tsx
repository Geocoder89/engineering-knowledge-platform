import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  ApiError,
  apiRequest,
  asApiError,
  SESSION_EXPIRED_EVENT,
} from "@/lib/api";
import { SessionContext, type Session, type User } from "./session-context";

function userFromResponse(value: unknown): User {
  if (
    !value ||
    typeof value !== "object" ||
    !("id" in value) ||
    typeof value.id !== "string" ||
    !("email" in value) ||
    typeof value.email !== "string" ||
    !("display_name" in value) ||
    typeof value.display_name !== "string" ||
    !("status" in value) ||
    value.status !== "active"
  ) {
    throw new ApiError(
      "The service returned an unexpected account response. Please try again.",
    );
  }
  return {
    id: value.id,
    email: value.email,
    display_name: value.display_name,
    status: value.status,
  };
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>({ status: "loading" });
  const generation = useRef(0);
  const pending = useRef<AbortController | null>(null);
  const mutating = useRef(false);
  const channel = useRef<BroadcastChannel | null>(null);
  const refresh = useCallback(async () => {
    if (mutating.current) return;
    const current = ++generation.current;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    try {
      const user = userFromResponse(
        await apiRequest("/users/me", {
          signal: controller.signal,
          sessionRequired: false,
        }),
      );
      if (current === generation.current)
        setSession({ status: "authenticated", user });
    } catch (error) {
      if (controller.signal.aborted || current !== generation.current) return;
      const failure = asApiError(error);
      if (failure.status === 401)
        setSession((previous) => ({
          status: "anonymous",
          reason:
            previous.status === "authenticated"
              ? "expired"
              : previous.status === "anonymous"
                ? previous.reason
                : undefined,
        }));
      else setSession({ status: "unavailable", error: failure });
    }
  }, []);
  const invalidate = useCallback(() => {
    ++generation.current;
    pending.current?.abort();
  }, []);
  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- refresh updates state only after the session HTTP request settles.
    void refresh();
    const expired = () => {
      invalidate();
      setSession({ status: "anonymous", reason: "expired" });
    };
    const recheck = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    window.addEventListener("focus", recheck);
    document.addEventListener("visibilitychange", recheck);
    const interval = window.setInterval(recheck, 60000);
    if ("BroadcastChannel" in window) {
      channel.current = new BroadcastChannel("decision-session");
      // Only a recheck signal crosses tabs; account data and tokens never do.
      channel.current.onmessage = () => {
        void refresh();
      };
    }
    return () => {
      invalidate();
      window.clearInterval(interval);
      window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
      window.removeEventListener("focus", recheck);
      document.removeEventListener("visibilitychange", recheck);
      channel.current?.close();
      channel.current = null;
    };
  }, [refresh, invalidate]);
  async function signIn(email: string, password: string) {
    if (mutating.current) return false;
    mutating.current = true;
    const current = ++generation.current;
    pending.current?.abort();
    try {
      await apiRequest("/auth/login", {
        method: "POST",
        body: { email, password },
        sessionRequired: false,
      });
      // Confirm that the browser accepted the cookie before opening the workspace.
      let user: User;
      try {
        user = userFromResponse(
          await apiRequest("/users/me", { sessionRequired: false }),
        );
      } catch (failure) {
        const error = asApiError(failure);
        if (error.status === 401)
          throw new ApiError(
            "Sign-in could not be confirmed. Make sure cookies are enabled, then try again.",
            0,
            error.requestId,
          );
        throw error;
      }
      if (current !== generation.current) return false;
      setSession({ status: "authenticated", user });
      channel.current?.postMessage("changed");
      return true;
    } finally {
      mutating.current = false;
    }
  }
  async function signOut() {
    if (mutating.current) return;
    mutating.current = true;
    const current = ++generation.current;
    pending.current?.abort();
    try {
      await apiRequest("/auth/logout", {
        method: "POST",
        sessionRequired: false,
      });
      if (current !== generation.current) return;
      setSession({ status: "anonymous", reason: "logout" });
      channel.current?.postMessage("changed");
    } finally {
      mutating.current = false;
    }
  }
  return (
    <SessionContext.Provider value={{ session, refresh, signIn, signOut }}>
      {children}
    </SessionContext.Provider>
  );
}
