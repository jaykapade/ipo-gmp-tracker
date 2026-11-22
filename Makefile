# IPO Checker shortcuts. Run `make help` for the list.
# Recipes only use `cd dir && command`, so they work from cmd, PowerShell and Git Bash.

# Backend CLI entry point.
CLI = cd backend && uv run python -m src.main
# Optional flags: RESEARCH=1 adds AI research, DRY=1 validates without sending email.
FLAGS = $(if $(RESEARCH),--research) $(if $(DRY),--dry-run)
# IPO id for `make research` (override with ID=3).
ID ?= 1

.PHONY: help install dev api web scrape analyze report run research research-all \
	notify schedule test lint typecheck build check

# Print this list of shortcuts.
help:
	@echo Setup:    make install
	@echo Dev:      make dev (API + frontend), make api, make web
	@echo Pipeline: make scrape, make analyze, make report, make run (scrape to email)
	@echo AI:       make research ID=3, make research-all
	@echo Subs:     make notify (digest; with RESEARCH=1 the full report + PDF)
	@echo Daily:    make schedule (the scheduled job)
	@echo Checks:   make test, make lint, make typecheck, make build, make check (all)
	@echo Flags:    RESEARCH=1 adds AI research to run/report/notify, DRY=1 sends nothing

# Create the backend venv, install Python deps, then install frontend packages.
install:
	cd backend && uv venv --allow-existing && uv pip install -r requirements-dev.txt
	cd frontend && pnpm install

# Run API and frontend together in one terminal; Ctrl+C stops both.
dev:
	$(MAKE) -j2 api web

# Start the FastAPI backend on :8000 with auto-reload.
api:
	$(CLI) serve --reload

# Start the Next.js dev server on :3000.
web:
	cd frontend && pnpm dev

# Fetch open IPOs and today's GMP from every source into SQLite.
scrape:
	$(CLI) scrape

# Screen IPOs by latest GMP, score them and store the analysis.
analyze:
	$(CLI) analyze

# Analyse and write a PDF report to backend/reports/ (no email).
report:
	$(CLI) report $(FLAGS)

# Full pipeline: scrape, analyse, PDF, then email it (RESEARCH=1 adds AI, DRY=1 skips sending).
run:
	$(CLI) run --email $(FLAGS)

# AI research for one IPO (ID=<id>, default 1).
research:
	$(CLI) research $(ID)

# AI research for every open IPO, one after another.
research-all:
	$(CLI) research --all-open

# Email the daily digest to subscribers (RESEARCH=1 sends the full report + PDF).
notify:
	$(CLI) notify $(FLAGS)

# Run the daily scheduled job by hand: run --research --email, then notify (DRY=1 sends nothing).
schedule:
	cd backend && powershell -NoProfile -ExecutionPolicy Bypass -File scripts/scheduled-run.ps1 $(if $(DRY),-DryRun)

# Backend test suite (offline).
test:
	cd backend && uv run pytest -q

# Ruff on the backend, ESLint on the frontend.
lint:
	cd backend && uv run ruff check src tests
	cd frontend && pnpm lint

# TypeScript type check for the frontend.
typecheck:
	cd frontend && pnpm exec tsc --noEmit

# Production build of the frontend.
build:
	cd frontend && pnpm build

# Tests, lint and type check in one go.
check: test lint typecheck
