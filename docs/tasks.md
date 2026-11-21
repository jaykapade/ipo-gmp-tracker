# Tasks: scheduled run with AI research in the report

Temporary checklist; delete when everything is done and verified.

- [x] `RESEARCH_MAX_AGE_HOURS` config (default 24)
- [x] `src/research/digest.py`: `ResearchDigest`, `latest_digest`, `research_for_report` (reuse fresh, skip in-progress, survive failures/AI off)
- [x] CLI: `run`/`report` gain `--research` and `--research-max-age`
- [x] PDF: AI view column in summary + "AI research" section per IPO
- [x] Email/text summary: AI verdict, confidence, top strength/risk
- [x] Tests (digest reuse/skip/failure, report rendering) + ruff + full suite
- [x] Dry run against the real DB (`run --research --email --dry-run`): exit 0, PDF written, email dry-run OK (2026-11-21)
- [x] Scheduler script + docs (backend README, .env.example)
- [x] Scheduler script dry run (`scripts/scheduled-run.ps1 -DryRun`): exit 0, log in `backend/logs/` (2026-11-21)
- [x] Fix orphaned research runs: `mark_stale_research_runs_failed` now fails only queued/running runs older than 2 h and runs from both API startup and `research_for_report` (a live CLI run survives an API restart)
- [x] Re-run the dry run: run #2 failed as stale, IPO 2 researched again (run #3 done), Crystal Crop marked closed (2026-11-21)
- [x] CLI printed "₹" to redirected stdout as cp1252 and crashed; `main` now writes UTF-8
- [x] Audit fixes: scrape marks `open` IPOs past their close date `closed`; the research POST proxy refuses cross-site requests (CSRF)
- [x] Frontend: "Run AI research" is only offered while an IPO has no completed research
- [x] HTML email template (`src/reporting/email_html.py`, text alternative kept) + Date/Message-ID headers; PDF redesigned (overview page, one page per IPO, header/footer)
- [x] Real email sent and checked in Gmail: HTML template renders properly (2026-11-21)
- [ ] Move `EMAIL_FROM` to an own domain with SPF/DKIM/DMARC in Mailjet so mail stops landing in spam (your DNS + Mailjet account)
- [x] Sources in reports: per-IPO "Sources" block in the PDF (scraped market-data pages + AI research citations, clickable) and source links in the email body; tests in `tests/test_report_sources.py`
- [x] Email config: Mailjet SMTP (`in-v3.mailjet.com:587`), from/to `glitchharbor@gmail.com` in `.env.local`
- [x] Mailjet: verify `glitchharbor@gmail.com` as a sender, put the API key in `SMTP_USER` and the secret key in `SMTP_PASSWORD` (`backend/.env.local`), then send one real email (`report --email`, no `--dry-run`)
- [ ] Delete this file once the open items below are done

## Email subscribers

- [x] Backend: `subscribers` table (migration 8), double opt-in API (`POST /api/subscribers`, `/api/subscribers/{confirm|unsubscribe}`), confirmation email, 10-minute resend throttle
- [x] Daily digest: `notify` command emails confirmed subscribers the open IPOs + latest GMP, with a per-subscriber unsubscribe link and `List-Unsubscribe` header; the scheduled script runs it after the report (`-NoNotify` to skip)
- [x] Frontend: "Get the daily IPO email" form in the footer and `/subscription` confirm/unsubscribe page (Server Actions add `API_TOKEN`)
- [x] Tests (`tests/test_subscribers.py`), ruff, full suite (258 passed); frontend tsc, ESLint, `next build`
- [ ] Set `SITE_URL` in `backend/.env.local` to the address people open the frontend at (default `http://localhost:3000`)
- [x] Google sign-in replaces double opt-in: signed-in users toggle the email for their verified Google address; chat and research need sign-in
- [ ] Create the Google OAuth client and set `AUTH_GOOGLE_ID` / `AUTH_GOOGLE_SECRET` in `frontend/.env.local`
- [ ] Try it end to end: sign in, turn the daily email on in the footer, run `notify`, then use the email's unsubscribe link
- [ ] Sender that can mail any address (Mailjet with a verified own domain, same step as the spam fix above) before inviting other people
