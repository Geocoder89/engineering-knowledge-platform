import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/dm-sans/latin-400.css";
import "@fontsource/dm-sans/latin-500.css";
import "@fontsource/dm-sans/latin-600.css";
import "@fontsource/instrument-serif/latin-400.css";
import "@fontsource/instrument-serif/latin-400-italic.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "./index.css";
import "./workspace.css";
import App from "./App";
import { captureVerificationLink } from "./lib/verification-link";
captureVerificationLink();
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
