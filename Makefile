# IPO Checker shortcuts. Run `make help` for the list.
# Recipes only use `cd dir && command`, so they work from cmd, PowerShell and Git Bash.

CLI = cd backend && uv run python -m src.main
FLAGS = $(if $(RESEARCH),--research) $(if $(DRY),--dry-run)
ID ?= 1

.PHONY: help install dev api web scrape analyze report run research research-all \
	notify schedule test lint typecheck build check

help:
	@echo Setup:    make install
	@echo Dev:      make dev (API + frontend), make api, make web
	@echo Pipeline: make scrape, make analyze, make report, make run (scrape to email)
	@echo AI:       make research ID=3, make research-all
	@echo Subs:     make notify (digest; with RESEARCH=1 the full report + PDF)
	@echo Daily:    make schedule (the scheduled job)
	@echo Checks:   make test, make lint, make typecheck, make build, make check (all)
	@echo Flags:    RESEARCH=1 adds AI research to run/report/notify, DRY=1 sends nothing

install:
	cd backend && uv venv --allow-existing && uv pip install -r requirements-dev.txt
	cd frontend && pnpm install

# Both servers in one terminal; Ctrl+C stops both.
dev:
	$(MAKE) -j2 api web

api:
	$(CLI) serve --reload

web:
	cd frontend && pnpm dev

scrape:
	$(CLI) scrape

analyze:
	$(CLI) analyze

report:
	$(CLI) report $(FLAGS)

run:
	$(CLI) run --email $(FLAGS)

research:
	$(CLI) research $(ID)

research-all:
	$(CLI) research --all-open

notify:
	$(CLI) notify $(FLAGS)

schedule:
	cd backend && powershell -NoProfile -ExecutionPolicy Bypass -File scripts/scheduled-run.ps1 $(if $(DRY),-DryRun)

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check src tests
	cd frontend && pnpm lint

typecheck:
	cd frontend && pnpm exec tsc --noEmit

build:
	cd frontend && pnpm build

check: test lint typecheck
