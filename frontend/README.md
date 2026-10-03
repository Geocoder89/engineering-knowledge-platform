# Decision workspace frontend

A visual prototype for the Engineering Knowledge and Decision Workflow Platform. The interface uses fictional records to demonstrate how alternatives, rationale, and source evidence fit together.

## Run locally

Use Node.js 24 LTS (24.16 or newer within the 24.x line) and npm. From the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. No database, API, Docker containers, API keys, or paid services are required for this preview. The development server binds only to loopback.

## Try the prototype

1. Open the decision workspace. Select either alternative and inspect its supporting source excerpts.
2. Edit the example rationale, review the selection, and finalize the preview. The history gains an illustrative event and editing is disabled.
3. Visit Documents and filter the sample library by type. Select a row to inspect its source excerpt.
4. Visit Search. Try `cooling pressure`, `pump changeover`, or `electrical isolation`, then follow a result to its source. Queries live in the URL; browser back/forward navigation restores them.
5. Resize to a mobile viewport and use the navigation menu.

**Scope:** all content is fictional, including names, document metadata, and engineering passages. It is not engineering advice. Search is a local text filter, not semantic search. No requests reach the backend, upload documents, or generate embeddings. Decision edits reset when navigating away from that screen or refreshing. This is not a persistent demo account or an authentication implementation.

## Design and implementation

- Deep green navigation, cream surfaces, restrained sage accents, and source citations positioned alongside the reasoning they support.
- Instrument Serif for editorial headings, DM Sans for interface text, IBM Plex Mono for metadata. Fonts are bundled locally; no external font requests.
- React, TypeScript, Vite, React Router, and Tailwind CSS. Sample content is centralized in `src/data/sample.ts`.
- Small local button/dialog wrappers use Radix primitives, with shadcn-compatible aliases and `components.json`. The dialog provides focus trapping, Escape dismissal, and accessible titles/descriptions. These wrappers are maintained in this repository.
- No data-fetching or form framework is installed until live API workflows need it.

## Verify

```bash
npm run lint
npm run format:check
npm run build
npx playwright install chromium
npm run test:e2e
```

Playwright runs the decision review, document filtering, source preview, URL-backed search, and navigation flows at desktop and mobile sizes. Tests also check key screens/dialogs with axe and detect horizontal overflow. They are prototype browser tests, not backend integration tests. CI installs Chromium and its Linux dependencies and runs the same checks independently of the backend jobs.

For an existing local Chromium installation, `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` can override Playwright's browser executable. Normally leave this unset. Failure screenshots and traces are written to ignored test output directories.

## Next integration steps

Connect session authentication and CSRF/Origin handling first, then replace sample records with the assembled decision record, documents, semantic search, and audit-history APIs. Add server loading/error/empty states and verify those flows against a real test backend. Keep authenticated attribution and workflow rules authoritative on the server.

Deployment and public demo usage controls are outside this prototype PR. A future static deployment must rewrite application routes to `index.html`.
