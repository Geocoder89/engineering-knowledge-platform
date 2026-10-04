// Capture before React mounts. The token stays in memory, never router/browser storage.
let token: string | null = null;
export function captureVerificationLink() {
  if (window.location.pathname !== "/verify-email") return;
  const values = new URLSearchParams(window.location.search).getAll("token");
  token =
    values.length === 1 && values[0].trim() && values[0].length <= 256
      ? values[0]
      : null;
  window.history.replaceState(window.history.state, "", "/verify-email");
}
export function getVerificationToken() {
  return token;
}
export function forgetVerificationToken() {
  token = null;
}
