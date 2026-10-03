# Decision workspace frontend

The frontend provides real session-based sign-in and an authenticated account workspace, alongside the interactive design preview. Document, decision, and search screens still use fictional sample records under `/preview`.

## Run locally

Use Node.js 24 LTS (24.16 or newer within 24.x). From the repository root:

```bash
cd frontend
nvm use # if you manage Node with nvm
npm ci
npm run dev
```

Open http://127.0.0.1:5173. The root route opens your workspace or sends you to sign-in. To explore without a backend or account, open http://127.0.0.1:5173/preview directly.

## Connect your local API

Use an existing **email-verified account**. Registration, verification, and password recovery screens are not part of this PR; the existing registration/verification APIs and email delivery configuration are described in the root README. This change does not create an account, bypass verification, or configure an email provider.

1. In the repository's root `.env`, keep your database settings and set these local browser settings:

   ```dotenv
   SESSION_COOKIE_SECURE=false
   SESSION_COOKIE_SAMESITE=lax
   CSRF_TRUSTED_ORIGINS='["http://localhost:3000","http://127.0.0.1:5173"]'
   CSRF_COOKIE_NAME=decision_csrf
   ```

   Preserve any additional trusted origins you already need. The scheme, hostname, and port must match exactly. Use `127.0.0.1:5173` consistently; `localhost:5173` is a different origin. Use secure cookies and HTTPS when deploying publicly.

2. Restart the API so it reads the updated settings. For the existing Docker setup, run from the repository root:

   ```bash
   docker compose up -d --wait --force-recreate api
   ```

   If running Uvicorn directly, restart that process instead. Use the backend setup/migration instructions in the root README when starting a fresh database.

3. Vite proxies `/api/*` to `http://127.0.0.1:8000/*`. For another API port, copy `frontend/.env.example` to `frontend/.env.local`, change `API_PROXY_TARGET`, and restart Vite. If your backend uses another CSRF cookie name, also set `VITE_CSRF_COOKIE_NAME` to that same name.

4. Sign in at http://127.0.0.1:5173/login. The account page should show your real display name and email. Refresh to confirm the session is restored, then sign out. Returning to `/workspace` should require login again.

The Vite proxy preserves the browser's Origin header and forwards cookies; no browser CORS configuration is required for this setup. It does not manufacture a trusted Origin or disable the backend's CSRF checks. A `403` on login usually means the frontend origin was not included in the backend settings or the API was not restarted. A `401` means the credentials, account status, or email verification did not satisfy the backend. If login succeeds but the session check fails, check cookie acceptance and your HTTP/HTTPS cookie settings.

## Routes and behavior

| Route                        | Data and access                                                  |
| ---------------------------- | ---------------------------------------------------------------- |
| `/login`                     | Real login; redirects an existing session to `/workspace`        |
| `/workspace`                 | Protected account page backed by `GET /users/me`                 |
| `/preview/decisions/DEC-024` | Public sample alternatives, rationale, finalization, and history |
| `/preview/documents`         | Public sample document library and source excerpts               |
| `/preview/search`            | Public local-text search, with queries in the URL                |

- Login uses `POST /auth/login` through `/api`, then verifies cookie acceptance with `GET /users/me`.
- Logout uses `POST /auth/logout` and the current CSRF cookie in `X-CSRF-Token`. The frontend only confirms logout when the server request succeeds; failures offer a retry.
- Protected content stays hidden until the initial session check succeeds. A `401` clears session state and returns to sign-in. Network/server failures show a recoverable connection state instead of pretending the user is logged out.
- Session state is rechecked on focus, when the tab becomes visible, and every minute while visible. A BroadcastChannel tells other tabs to recheck after login/logout. It carries no account data or tokens.
- Credentials and session tokens are never stored in localStorage or sessionStorage. The session cookie remains HttpOnly. Authentication stays authoritative on the backend.
- Responses are not cached by the browser API client. Errors show safe messages, Retry-After guidance, and request IDs where available; raw backend validation input and server error bodies are not rendered.

## Try the sample workflow

Select an alternative, inspect its sources, edit the sample rationale, then review and finalize the preview. Browse Documents, filter by type, or search for `cooling pressure` and `electrical isolation`. Resize to a phone viewport to try the mobile navigation.

All preview records, names, and engineering excerpts are fictional. Search is a local text filter. Sample edits reset when leaving the decision screen or refreshing and do not affect your real account. Preview routes do not call the backend, upload files, or generate embeddings. They are not engineering advice.

## Design and implementation

Deep green navigation, cream surfaces, sage accents, and source citations keep evidence alongside the reasoning it supports. Instrument Serif, DM Sans, and IBM Plex Mono are bundled locally.

The app uses React, TypeScript, Vite, React Router, Tailwind CSS, and local Radix button/dialog wrappers with shadcn-compatible aliases. `src/lib/api.ts` centralizes same-origin API requests and CSRF handling; `src/auth/` owns session state and route protection. The existing simple login form and session provider do not require an additional form or query dependency. Sample data stays in `src/data/sample.ts`.

## Verify

```bash
npm run lint
npm run format:check
npm run build
npx playwright install chromium
npm run test:e2e
```

Desktop and mobile Playwright tests cover login, refresh, expiry, logout/CSRF headers, cross-tab logout, stale responses, unavailable services, safe errors, and the preview interactions. Axe checks and overflow assertions cover the main account and sample screens. Most tests intercept API responses to exercise failure cases deterministically.

**CI also runs real browser-to-API tests:** a disposable PostgreSQL database is migrated, and `scripts/browser_auth_server.py` seeds verified fixture users using the existing registration and verification services. Playwright logs in through Vite and the real FastAPI routes, checks HttpOnly cookie behavior and refresh, verifies invalid CSRF/Origin rejection, and checks database session revocation by replaying the old cookie after logout. No mail or embedding provider is called. This fixture requires explicit opt-in and a database name ending in `_browser_test`; it is not a development-account creation command for your normal database. Locally, those two tests are skipped unless that dedicated fixture environment is configured.

`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` can point to an existing local Chromium when the normal download is unavailable. Failure diagnostics are written to ignored directories and uploaded by CI for three days.

## Next integration steps

Build account registration/verification screens, then connect the decision list and assembled records, document upload/processing, semantic search, evidence editing, and audit history. Add server loading/error/empty states as each workflow becomes live.

Hosting and demo usage controls remain separate work. `npm run preview` only serves the static build; it is not the supported API proxy setup. A production reverse proxy must route `/api/*` to FastAPI with `/api` stripped, preserve the original browser Origin, and serve `index.html` for frontend routes. Keep the session and CSRF cookies on the same origin with HTTPS and secure cookies.
