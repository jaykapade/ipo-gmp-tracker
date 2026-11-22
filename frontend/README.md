# IPO Checker — frontend

Next.js 16 (App Router, Turbopack) · React 19 · TypeScript · Tailwind 4 ·
Recharts · pnpm. Talks only to the FastAPI backend; filtering and scoring
happen there.

## Run

Start the backend first (`uv run python -m src.main serve` in `backend/`),
then:

```bash
cp .env.example .env.local
pnpm install
pnpm dev        # http://localhost:3000
```

| Variable | Notes |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Backend URL, default `http://localhost:8000`. |
| `API_TOKEN` | Server only; must match the backend's `API_TOKEN`. |
| `AUTH_SECRET` | Server only; any long random string (`npx auth secret`). |
| `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET` | Google OAuth web client; redirect URI `http://localhost:3000/api/auth/callback/google`. |

Restart `pnpm dev` after editing `.env.local`. fnm users in PowerShell:
`fnm env --use-on-cd | Out-String | Invoke-Expression`.

Other scripts: `pnpm build`, `pnpm start`, `pnpm lint`, `pnpm typegen`
(after adding routes), `pnpm exec tsc --noEmit`.

## Pages

| Route | Shows |
| --- | --- |
| `/` | Dashboard: search, board, GMP, status and research filters (all in the URL), sortable table, cards on phones. |
| `/ipos/[id]` | **Overview** (GMP chart, issue details, sources, rule-based analysis) and **AI research** (run, live progress, H1–H5, disputes, cited evidence). |
| `/reports` | Generated PDFs. |
| `/chat` | Streaming grounded chat. |
| `/subscription` | Unsubscribe target for email links. |

Sign-in is Google only (Auth.js, cookie session, no user table). Chat,
starting research and the daily email need it; browsing does not. "Run AI
research" only appears while an IPO has no completed research.

## Structure

```text
app/          routes; api/ holds the auth, chat and research proxies (add API_TOKEN server-side)
components/   dashboard, ipo, research, chat, reports, shell, ui
lib/          api client, types (hand-copied from backend schemas), Server Actions, formatting
```

## Limitations

- Types are copied by hand from the backend (no OpenAPI codegen yet).
- Any Google account can sign in; no allow-list or per-user limits.
