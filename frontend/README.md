# IPO Checker — frontend

Next.js App Router frontend for the IPO Checker. It is a read-only view over the
existing FastAPI service: dashboard shortlist, per-IPO detail with GMP history and
deterministic analysis, and generated PDF reports.

The backend remains the single source of truth for filtering and scoring. Nothing
in this app calls an AI model or re-implements the analysis rules.

## Stack

- Next.js **16.4** (App Router, Cache Components, Turbopack)
- React **19.3**
- TypeScript 5
- Tailwind CSS **4**
- Recharts 3 for the GMP trend chart
- pnpm for package management

## Getting started

Start the API first, from `backend/`:

```bash
cd backend
uv run python -m src.main serve   # http://localhost:8000
```

Then run the frontend:

```bash
cd frontend
cp .env.example .env.local        # optional; defaults to http://localhost:8000
pnpm install
pnpm dev                          # http://localhost:3000
```

`NEXT_PUBLIC_API_BASE_URL` points the browser and server components at the API.
If the API is unreachable, pages render an explicit "backend not reachable"
panel instead of a blank screen.

The backend commands use **uv** (run them from `backend/`); this app uses
**pnpm**. Plain `npm` works too, but `pnpm-lock.yaml` is the committed lockfile.

## Scripts

| Command | Purpose |
| --- | --- |
| `pnpm dev` | Development server with Turbopack. |
| `pnpm build` | Production build. Next 16 no longer runs lint during build. |
| `pnpm start` | Serve the production build. |
| `pnpm lint` | ESLint. Run this explicitly; `build` does not. |
| `pnpm typegen` | Regenerate `PageProps` / `LayoutProps` route types after adding routes. |

## Structure

```text
frontend/
├── app/
│   ├── layout.tsx              # Root layout, metadata, app shell
│   ├── page.tsx                # Dashboard (Suspense + searchParams)
│   ├── error.tsx               # Client error boundary (retry)
│   ├── not-found.tsx           # 404
│   ├── ipos/[id]/page.tsx      # IPO detail
│   ├── reports/page.tsx        # PDF report list
│   └── chat/page.tsx           # Chat placeholder (not wired up yet)
├── components/
│   ├── dashboard/              # Filters, table, API error panel
│   ├── ipo/                    # Detail, analysis, GMP chart/history
│   ├── reports/                # Report list
│   ├── shell/                  # Header, nav, page header
│   └── ui/                     # Small local primitives (card, badge, …)
└── lib/
    ├── api.ts                  # Typed read-only API client
    ├── types.ts                # Mirrors backend/src/api/schemas.py
    ├── format.ts               # Currency, percent, date helpers
    └── utils.ts                # cn()
```

## Data rules

- The dashboard defaults to a **20% minimum GMP** filter, matching the backend.
- Search and sort are executed by the API (`q`, `sort`, `order`), not in the
  browser, so results stay consistent with backend filters.
- A `gmp_percent` marked **derived** was computed as GMP ÷ issue price because
  the source omitted it.
- Analysis panels only show stored analyses. Run
  `uv run python -m src.main analyze` from `backend/` to populate them.

## Limitations / next steps

- Chat is a placeholder. Streaming chat and the provider-agnostic AI layer are
  not implemented.
- shadcn/ui and TanStack Table are not installed; the table is hand-rolled.
  Recharts powers the GMP trend chart.
- Types are duplicated by hand from the backend schemas; generating them from
  the OpenAPI schema is planned.

## Not investment advice

GMP is an unofficial, speculative signal and can disappear before listing.
Verify every fact against the official RHP and NSE/BSE filings.
