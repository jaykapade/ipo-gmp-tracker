# Tasks: scheduled run with AI research in the report

Temporary checklist; delete when everything is done and verified.

- [x] `RESEARCH_MAX_AGE_HOURS` config (default 24)
- [x] `src/research/digest.py`: `ResearchDigest`, `latest_digest`, `research_for_report` (reuse fresh, skip in-progress, survive failures/AI off)
- [x] CLI: `run`/`report` gain `--research` and `--research-max-age`
- [x] PDF: AI view column in summary + "AI research" section per IPO
- [x] Email/text summary: AI verdict, confidence, top strength/risk
- [x] Tests (digest reuse/skip/failure, report rendering) + ruff + full suite
- [ ] Dry run against the real DB (`run --research --email --dry-run`) — running
- [x] Scheduler script + docs (backend README, .env.example)
- [ ] Scheduler script dry run (`scripts/scheduled-run.ps1 -DryRun`)
- [ ] Delete this file
