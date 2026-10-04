# Decision workspace frontend

The frontend provides account registration, email verification, and real session-based sign-in and an authenticated account workspace, alongside the interactive design preview. Document, decision, and search screens still use fictional sample records under `/preview`.

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

Sign in with an existing **email-verified account**, or create one at `/register`. New accounts must verify their email before signing in. See [Test account onboarding](#test-account-onboarding) below for a free, isolated local test or real email delivery. Password recovery remains upcoming work.

1. In the repository's root `.env`, keep your database settings and set these local browser settings:

   ```dotenv
   SESSION_COOKIE_SECURE=false
   SESSION_COOKIE_SAMESITE=lax
   CSRF_TRUSTED_ORIGINS='["http://localhost:3000","http://127.0.0.1:5173","http://localhost:5173"]'
   CSRF_COOKIE_NAME=decision_csrf
   ```

   Preserve any additional trusted origins you already need. The scheme, hostname, and port must match exactly. The example allows both `127.0.0.1:5173` and `localhost:5173`. They are different origins with separate cookie storage; sign in again when switching between them. Updating `.env.example` does not update your existing `.env`. Use secure cookies and HTTPS when deploying publicly.

2. Restart the API so it reads the updated settings. For the existing Docker setup, run from the repository root:

   ```bash
   docker compose up -d --wait --force-recreate api
   ```

   If running Uvicorn directly, restart that process instead. Use the backend setup/migration instructions in the root README when starting a fresh database.

3. Vite proxies `/api/*` to `http://127.0.0.1:8000/*`. For another API port, copy `frontend/.env.example` to `frontend/.env.local`, change `API_PROXY_TARGET`, and restart Vite. If your backend uses another CSRF cookie name, also set `VITE_CSRF_COOKIE_NAME` to that same name.

4. Sign in at http://127.0.0.1:5173/login. The account page should show your real display name and email. Refresh to confirm the session is restored, then sign out. Returning to `/workspace` should require login again.

The Vite proxy preserves the browser's Origin header and forwards cookies; no browser CORS configuration is required for this setup. It does not manufacture a trusted Origin or disable the backend's CSRF checks. A rejected origin now has a specific error message and, in development, instructions containing the exact current origin. Other permission and CSRF errors have separate messages; unknown server details are never displayed. A `403` on login usually means the frontend origin was not included in the backend settings or the API was not restarted. A `401` means the credentials, account status, or email verification did not satisfy the backend. If login succeeds but the session check fails, check cookie acceptance and your HTTP/HTTPS cookie settings.

## Routes and behavior

| Route                        | Data and access                                                  |
| ---------------------------- | ---------------------------------------------------------------- |
| `/register`                  | Create an account and request a verification email               |
| `/verify-email?token=…`      | Confirm a one-time email verification link                       |
| `/resend-verification`       | Request a replacement link; generic response                     |
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

**CI also runs real browser-to-API tests:** a disposable PostgreSQL database is migrated, and `scripts/browser_auth_server.py` seeds verified fixture users using the existing registration and verification services. Playwright logs in through Vite and the real FastAPI routes, checks HttpOnly cookie behavior and refresh, verifies invalid CSRF/Origin rejection, and checks database session revocation by replaying the old cookie after logout. The onboarding flow registers an unverified user, rejects premature login, resends through a local file mailbox, rejects the superseded link, verifies the new link, rejects token reuse, and signs in/out. Only the email transport is replaced; routes, rate limits, token validation, and database transactions are real. No mail or embedding provider is called. This fixture requires explicit opt-in and a database name ending in `_browser_test`; it is not a development-account creation command for your normal database. Locally, those four tests are skipped unless that dedicated fixture environment is configured.

`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` can point to an existing local Chromium when the normal download is unavailable. Failure diagnostics are written to ignored directories and uploaded by CI for three days.

## Test account onboarding

### Free local test with a disposable database

This uses the real API and captures verification links in private temporary files. It sends no email and makes no embedding requests. Use fictional addresses and test-only passwords. Your usual Docker API and database can stay running; this fixture uses PostgreSQL port **5544** and API port **8001**.

1. Pull the PR branch, then start a separate disposable database:

   ```bash
   docker run --rm -d --name decision-onboarding-db \
     -p 127.0.0.1:5544:5432 \
     -e POSTGRES_USER=browser_user \
     -e POSTGRES_PASSWORD=browser_password \
     -e POSTGRES_DB=onboarding_browser_test \
     pgvector/pgvector:0.8.6-pg17-bookworm
   docker exec decision-onboarding-db pg_isready -U browser_user -d onboarding_browser_test
   ```

   Wait until `pg_isready` reports **accepting connections** before proceeding. These credentials belong only to the disposable local test database. Do not put them in production settings.

2. In a terminal at the repository root with your Python virtual environment active:

   ```bash
   export DATABASE_URL='postgresql+psycopg://browser_user:browser_password@127.0.0.1:5544/onboarding_browser_test'
   export RUN_BROWSER_AUTH_TESTS=1
   export SESSION_COOKIE_SECURE=false
   export CSRF_TRUSTED_ORIGINS='["http://127.0.0.1:5173","http://localhost:5173"]'
   python -m alembic upgrade head
   python -m scripts.browser_auth_server
   ```

   Leave that terminal running. The fixture refuses to start without explicit opt-in and a database name ending in `_browser_test`. It does not modify your normal database. It is a test-only process, not a deployment mode, and is not included in the runtime Docker image.

3. In another terminal, stop any existing Vite server and start this one:

   ```bash
   cd frontend
   npm ci
   API_PROXY_TARGET=http://127.0.0.1:8001 npm run dev
   ```

4. Open http://127.0.0.1:5173/register. Enter a display name, an unused fictional email such as `samuel@example.com`, and a test password of 12–128 characters. Submit. Expect **Check your inbox.** Try signing in before verification: it should fail.

5. In a third terminal, at the repository root with your virtual environment active, read the captured link:

   ```bash
   python -m scripts.browser_auth_server --show-link samuel@example.com
   ```

   Open the displayed URL. Its token disappears from the address bar; click **Verify email**. Expect **Email verified.** Sign in, refresh the account page, and sign out. Reading a link does not consume it. Links are saved under the system temporary directory in `decision-browser-outbox`, with private directory/file permissions; they are never written to API logs or committed. `BROWSER_AUTH_OUTBOX_DIR` can override the location, but set it consistently for the fixture, link reader, and tests.

6. Try these failure cases:

   | Action                                                             | Expected result                                                                     |
   | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
   | Reopen the same email link and click Verify email                  | Invalid, expired, or already-used message; sign-in and resend links                 |
   | Open `/verify-email` without a token, or refresh before confirming | Instructions to reopen the email link or request another                            |
   | Register another address, then resend before verifying             | Generic confirmation; read its latest captured link again; the older link must fail |
   | Resend for an unknown address                                      | Same generic confirmation; no captured email                                        |
   | Enter a short password or invalid email                            | Browser validation prevents submission                                              |
   | Stop the fixture API, then submit registration                     | Recoverable service error; entered fields remain                                    |

   Real authentication rate limits remain enabled. If you reach a limit while testing, follow the displayed retry interval or recreate the **disposable** database. A lost response can be ambiguous: if retrying registration reports a conflict, use sign-in/resend rather than assuming no account was created.

When finished, stop the fixture API and Vite with Ctrl+C, then run `docker stop decision-onboarding-db`. Because the test container uses `--rm` and no named volume, its database is discarded. Close the terminal containing exported test settings. Restart Vite normally with `npm run dev` to reconnect to your usual API on port 8000. Remove the captured temporary mailbox files when you no longer need them.

### Automated checks, including the real API

For the mocked browser checks, use `npm run test:e2e` from `frontend`; no database or email provider is required. For real API checks, start/migrate the disposable database using steps 1–2, but **do not start** the fixture server manually. Stop Vite too. In the terminal with the exported test variables, run:

```bash
cd frontend
API_PROXY_TARGET=http://127.0.0.1:8001 npm run test:e2e
```

Playwright starts and stops both servers. Use a fresh disposable database for repeated full runs so previous rate-limit counters cannot affect the result. CI follows this path automatically. Live tests use fixture-only tokens; browser traces may contain those test tokens, so do not run the suite against real accounts.

### Real email delivery

To test your normal backend with actual email, configure all three settings in the root `.env`:

```dotenv
RESEND_API_KEY=your-provider-key
EMAIL_SENDER_IDENTITY=Your configured sender identity
EMAIL_VERIFICATION_URL=http://127.0.0.1:5173/verify-email
```

Keep the trusted-origin and local cookie settings above, then recreate the API:

```bash
docker compose up -d --wait --force-recreate api
```

Run Vite against port 8000, register using an inbox you control, and open the actual email link. This uses your configured provider and its sending restrictions. Never put the provider key in frontend environment variables. When delivery is unconfigured, registration returns a service error and rolls back account creation; the UI must not claim an email was sent. Resend intentionally uses a generic response even when no matching account exists or delivery fails.

Verification uses an explicit confirmation button rather than an automatic POST on page load. The token is removed from the URL before React mounts and is not saved in localStorage, sessionStorage, or router history. A no-referrer policy prevents sending the link in outgoing referrers. The initial email URL still reaches the frontend server: configure any deployment proxy/access logs to omit query strings for this route.

## Next integration steps

Connect the decision list and assembled records, document upload/processing, semantic search, evidence editing, and audit history. Add server loading/error/empty states as each workflow becomes live.

Hosting and demo usage controls remain separate work. `npm run preview` only serves the static build; it is not the supported API proxy setup. A production reverse proxy must route `/api/*` to FastAPI with `/api` stripped, preserve the original browser Origin, and serve `index.html` for frontend routes. Keep the session and CSRF cookies on the same origin with HTTPS and secure cookies.
