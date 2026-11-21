# IPO Checker — frontend

Next.js app for the IPO Checker: a filterable dashboard of tracked IPOs, an
IPO page with GMP history, the rule-based score and **AI research**, a reports
page and a streaming chat assistant. It talks only to the FastAPI backend in
`../backend`; filtering and scoring happen there, never in the browser.

> Not investment advice. Grey-market premium is unofficial and speculative.

## Stack

- Next.js **16.4** (App Router, Cache Components, Turbopack) · React **19.3**
- TypeScript 5 · Tailwind CSS **4** · Recharts 3
- pnpm

## Getting started

1. Start the API (see `../backend/README.md`):

   ```bash
   cd backend
   uv run python -m src.main serve        # http://localhost:8000
   ```

2. Configure and run the app:

   ```bash
   cd frontend
   cp .env.example .env.local
   pnpm install
   pnpm dev                               # http://localhost:3000
   ```

| Variable | Where it is used | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | browser + server | Backend URL, default `http://localhost:8000`. |
| `API_TOKEN` | **server only** | Must equal `API_TOKEN` in the backend env. Used by `app/api/research/[id]/route.ts` to start AI research; never sent to the browser. |

Restart `pnpm dev` after changing `.env.local`. If the API is unreachable,
pages show a "backend not reachable" panel, and the header pill reads
"API offline".

If `node`/`pnpm` are not found in PowerShell (fnm users):
`fnm env --use-on-cd | Out-String | Invoke-Expression`.

## Pages

| Route | What it shows |
| --- | --- |
| `/` | Dashboard: filter bar, summary stats, IPO table (cards on phones). |
| `/ipos/[id]` | **Overview** tab: GMP chart/history, issue details, sources, rule-based analysis. **AI research** tab: run research, live stage progress, H5 assessment beside the rule-based score, H1–H4 perspectives with citation chips, dispute log, cited evidence. |
| `/reports` | Generated PDF reports, newest first. |
| `/chat` | Streaming grounded chat with starter questions built from current IPOs. |

### Dashboard filters

All filters live in the URL (`?q=&category=&min_gmp=&status=&researched=1&sort=&order=`),
so views can be bookmarked and every control also works without JavaScript.

- **Search** — company name, applied as you type.
- **Board** — All / Mainboard / SME, with counts.
- **Latest GMP** — Any (default) / ≥10% / ≥20% (the backend screen) / ≥30%.
  The default shows everything; rows at or above the screen are marked
  "meets screen".
- **Status** — only shown when the data has more than one status (the
  scrapers currently keep open IPOs only). Options come from
  `GET /api/ipos/facets`, so a filter that cannot match is never offered.
- **AI research** — All / Researched.
- Active filters appear as removable chips; column headers sort.

### AI research tab

"Run AI research" calls the local route handler, which adds the server-side
`API_TOKEN` and queues a run on the backend. The tab polls every 3 seconds and
shows each stage (gather → perspectives → verify → challenge → synthesis).
While a re-run is in progress the last completed result stays visible. Runs
continue on the server if you leave the page.

The header pill shows the backend's AI provider ("Claude · subscription",
"Ollama · local", "AI off"); hover it for per-role models.

## Scripts

| Command | Purpose |
| --- | --- |
| `pnpm dev` | Development server (Turbopack). |
| `pnpm build` / `pnpm start` | Production build / serve it. |
| `pnpm lint` | ESLint (not run by `build` in Next 16). |
| `pnpm typegen` | Regenerate route types (`PageProps`, `RouteContext`) after adding routes. |

Type-check with `pnpm exec tsc --noEmit`.

## Structure

```text
frontend/
├── app/
│   ├── page.tsx                  # dashboard
│   ├── ipos/[id]/page.tsx        # IPO detail (tabs via ?tab=)
│   ├── reports/page.tsx
│   ├── chat/page.tsx
│   ├── api/research/[id]/route.ts  # token-adding proxy for AI research
│   ├── layout.tsx, error.tsx, not-found.tsx
├── components/
│   ├── dashboard/                # filter bar, table/cards, API-offline panel
│   ├── ipo/                      # detail tabs, GMP chart/history, analysis
│   ├── research/                 # research panel (client) + result views
│   ├── chat/                     # streaming chat client
│   ├── reports/
│   ├── shell/                    # header, nav, AI status pill
│   └── ui/                       # badge, card, stat, skeleton, empty state
└── lib/
    ├── api.ts                    # typed API client
    ├── dashboard-query.ts        # URL ⇄ filter state
    ├── types.ts                  # mirrors backend/src/api/schemas.py
    ├── format.ts                 # currency, percent, dates (IST), issue size
    └── utils.ts
```

## Limitations

- Types are copied by hand from the backend schemas (OpenAPI generation is
  planned).
- No user accounts: the shared `API_TOKEN` is fine for localhost only.
- The table is hand-rolled; no virtualisation (fine for tens of IPOs).
- AI research facts come from the web and are unverified until checked against
  the RHP; secondary sources are flagged in the evidence list.
