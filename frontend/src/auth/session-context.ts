import { createContext, useContext } from "react";
import type { ApiError } from "@/lib/api";
export type User = {
  id: string;
  email: string;
  display_name: string;
  status: string;
};
export type Session =
  | { status: "loading" }
  | { status: "authenticated"; user: User }
  | { status: "anonymous"; reason?: "expired" | "logout" }
  | { status: "unavailable"; error: ApiError };
export type SessionContextValue = {
  session: Session;
  refresh: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<boolean>;
  signOut: () => Promise<void>;
};
export const SessionContext = createContext<SessionContextValue | null>(null);
export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("Session provider is required");
  return value;
}
