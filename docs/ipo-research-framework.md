# IPO Research Framework

What to collect, calculate, verify and analyse before assessing an Indian IPO
(NSE/BSE Mainboard or SME). A design spec, not investment advice.

**Design rule.** Deterministic code computes every number, threshold and
score. An LLM may read and write narratives but never invents a data point,
changes a calculation or overrides the GMP screen. Providers sit behind one
interface, so switching is config only.

## Contents

[A. Checklist](#a-research-checklist) ·
[B. Data model](#b-data-model) ·
[C. Formulas](#c-formulas) ·
[D. Sources](#d-sources) ·
[E. Document extraction](#e-document-extraction) ·
[F. Mainboard](#f-mainboard-rules) ·
[G. SME](#g-sme-rules) ·
[H. AI summaries](#h-ai-summaries) ·
[I. Detailed PDF](#i-detailed-pdf) ·
[J. Summary PDF](#j-summary-pdf) ·
[K. Workflow](#k-workflow-and-gates) ·
[L. Data quality](#l-data-quality) ·
[M. Scoring](#m-scoring) ·
[N. Extra categories](#n-extra-categories) ·
[O. Roadmap](#o-roadmap) ·
[P. AI stack](#p-ai-stack)

---

## A. Research checklist

Every item carries provenance (source, document, period, page, retrieval
date) and a status: `reported`, `calculated`, `estimated`, `unverified` or
`missing`. Never guess.

- **A1. Issue** — legal name, CIN, segment (NSE/BSE, Emerge/SME), fresh vs
  OFS, timetable (open/close/allotment/refund/listing), price band, face
  value, lot size, min retail amount, issue size, pre/post shares and
  shareholding, promoter dilution, intermediaries (registrar, lead managers,
  market maker), anchors and lock-ins, objects of the issue, IPO grade, RHP
  links.
- **A2. Business** — model and segments, products, customers and
  concentration (top 1/5/10), suppliers, geography, capacity and
  utilisation, distribution, moat, market share, order book, scalability,
  key-person dependence, IP, group structure, related parties, employees,
  seasonality, ESG.
- **A3. Financials** (3–5 years, 4–8 quarters, consolidated preferred) —
  full P&L, balance sheet and cash flow; ratios (ROE, ROCE, ROA, D/E, net
  debt/EBITDA, current/quick, interest cover, turnover and days, CCC,
  EPS/BVPS); growth and margin trends; earnings quality (OCF/EBITDA,
  OCF/PAT); auditor remarks, restatements, policy changes, related-party
  flows, aggressive capitalisation, rising receivables.
- **A4. Promoters and management** — backgrounds, track record, other
  directorships, past failures, litigation, SEBI/MCA/RBI action, pledges,
  governance and board independence, auditor tenure/changes, remuneration,
  pre-IPO selling, ESOP dilution, succession.
- **A5. Valuation** — market cap and EV at the upper band, pre/post P/E, P/B,
  EV/EBITDA, EV/Sales, earnings yield, dilution, OFS %, peer and industry
  multiples, premium/discount, recent comparable listings; verdict
  attractive/fair/expensive.
- **A6. Industry** — TAM/SAM and CAGR, drivers, cyclicality, margins,
  structure, competitors, entry barriers, regulation, disruption,
  FX/commodity exposure, policy (PLI, subsidies, tax).
- **A7. GMP and sentiment** (max five GMP sources) — GMP history and %,
  kostak and subject-to-sauda where reliable, subscription by category and
  day, anchor demand, listing performance. Keep sentiment separate from
  fundamentals.
- **A8. Legal and risk** — SEBI observations, material litigation, tax
  disputes, contingent liabilities, compliance, licences, related-party and
  dependency risks, cyber/privacy, insurance; ranked red-flag synthesis.
- **A9. SME** — see [§G](#g-sme-rules).
- **A10. Post-listing** — listing gain, price performance, results vs
  projections, promoter/pledge changes, lock-in expiries, use of proceeds,
  and whether the verdict predicted the outcome.

## B. Data model

### B1. Principles

1. One canonical `ipos` row plus per-source provenance (`ipo_sources`);
   record conflicts, never overwrite silently.
2. Financial facts belong to a period and basis (standalone/consolidated,
   audited or not).
3. Every fact links to a citation (document, page, quote, retrieval time).
4. Derived values store their formula version and inputs.
5. AI output lives in `ai_outputs` and never overwrites facts.
6. Keep history (`created_at`/`updated_at`, snapshots) for backtesting.

### B2. Tables

Existing: `ipos`, `gmp_history`, `ipo_sources`, `scrape_runs`,
`analysis_reports`, `research_runs`, `ai_outputs`, `subscribers`,
`schema_migrations`.

Planned:

| Table | Holds |
| --- | --- |
| `companies` | Legal entity, CIN, incorporation, group |
| `ipo_issue`, `issue_objects` | Issue structure, intermediaries, objects and amounts |
| `shareholding` | Pre/post ownership by category, pledges |
| `financial_periods`, `financial_facts`, `financial_ratios` | Periodised statements and derived ratios (`formula_version`, `inputs_json`) |
| `subscription_snapshots` | Demand by category and day |
| `peers`, `industry_metrics` | Comparables and market context |
| `documents`, `document_chunks` | RHP/DRHP files (`sha256`) and embedded chunks |
| `source_citations` | Per-fact provenance and quality state |
| `research_findings` | Litigation, governance, risk findings with severity |
| `post_listing_prices` | OHLCV after listing |
| `email_log`, `review_queue`, `chat_sessions`/`chat_messages` | Delivery audit, human review, chat history |

Extend `gmp_history` with `kostak`, `subject_to_sauda`, `scrape_run_id`, and
`analysis_reports` with `model_version`, `inputs_hash`, `data_completeness`.

### B3. Conventions

Money in ₹ crore (unit stored); percentages as points (`12.5`); ISO-8601
dates, UTC timestamps; FY as `YYYY-YY`; shares as counts. Null is unknown,
`0` is a real zero.

## C. Formulas

Implement once, unit-test, version. Division by zero returns `None` with a
reason.

| Group | Metrics |
| --- | --- |
| Growth | YoY/QoQ `(v_t / v_{t-1} - 1) × 100`; CAGR `(end/start)^(1/n) - 1` |
| Profitability | Gross margin; EBITDA = `PBT + finance costs + D&A`; EBIT = `PBT + finance costs`; EBITDA/EBIT/PAT margins; tax rate `tax / PBT`; EPS `PAT / weighted shares`; post-issue EPS `PAT / post-issue shares` |
| Returns | ROE `PAT / avg equity`; ROCE `EBIT / avg capital employed`; ROA `PAT / avg assets` |
| Leverage | D/E; net debt `debt - cash`; net debt/EBITDA; current and quick ratio; interest cover `EBIT / finance costs` |
| Efficiency | Asset turnover; DIO, DSO, DPO; CCC `DIO + DSO - DPO`; capex intensity |
| Cash flow | FCF `OCF - capex`; OCF/EBITDA; OCF/PAT; FCF yield |
| Valuation | Mcap `issue price × post shares`; EV `mcap + debt - cash`; P/E; P/B; EV/EBITDA; EV/Sales; earnings yield; dilution `(post - pre) / post`; OFS %; peer premium `(multiple / peer median - 1) × 100` |
| GMP and demand | GMP % `GMP / issue price × 100`; trend over 7–14 days (Rising/Stable/Falling); source spread; subscription `bid / offered` |

Rules: use average balances when two period ends exist (else closing value,
marked `estimated`); never mix standalone/consolidated or annual/quarterly;
recompute after restatements; round only for display.

## D. Sources

Priority: **SEBI filings** (DRHP/RHP) → **NSE/BSE** disclosures → **MCA** →
company annual reports → official industry/government data → reputable data
providers → news (context only, never the sole source for a hard fact). GMP:
up to five unofficial sources (InvestorGain, IPO Watch, Chittorgarh, IPO
Central, Moneycontrol).

Rules: prefer the primary document; record URL, dates and page; no CAPTCHA,
paywall or anti-bot bypass; respect robots.txt and rate limits; keep a hashed
raw copy; store both values when official sources disagree.

## E. Document extraction

- **Ingest:** discover the RHP from NSE/BSE/SEBI, download with retries and a
  size cap, store `sha256`; parse with Docling (MinerU fallback, OCR only for
  scanned pages); chunk ~800–1200 tokens with 10–15% overlap and page spans;
  embed locally (`qwen3-embedding:0.6b`).
- **Targets:** issue structure, business, financials, risk factors,
  litigation, promoters, related parties, governance, industry, use of
  proceeds.
- **Rules:** parsing is deterministic, never an LLM; the LLM only reads
  pre-extracted prose and returns schema-validated JSON with a page and a
  verbatim quote; reject if the quote is not on that page; diff against
  previous extractions; document text is never instructions; low-confidence
  results go to `review_queue`.

## F. Mainboard rules

Higher bar on governance, disclosure, institutional demand and valuation:
SEBI track-record norms, group structure, QIB/anchor demand, free float,
dividend and capital-allocation history, approvals and land titles, peer sets
by size. Default thresholds (configurable): ≥ 3 audited years; positive OCF
in 2 of the last 3 years; interest cover ≥ 2x; D/E ≤ 2x (non-financial);
flag peer premium above +30%, fail above +60%.

## G. SME rules

Never apply mainboard thresholds blindly; SME risk is scale, liquidity,
concentration and governance. Check market maker (identity, inventory, track
record), free float and spreads, promoter dependency, working capital,
disclosure quality, manipulation signals (circular trading, pump-and-dump),
migration path. Defaults: positive OCF in the latest year; D/E flag above 1x,
cap 1.5x; free float below 25% flagged; GMP weighted lower than for
mainboard; every report gets an "SME risk" block.

## H. AI summaries

Five perspectives, each with `evidence`, `conclusion`, `confidence`
(with reason), `missing_information`, `citations` and `data_as_of`:

| | Perspective | Covers |
| --- | --- | --- |
| H1 | Business quality | Model, moat, position, concentration, scalability |
| H2 | Financial health | Growth, margins, balance sheet, cash flow, ROE/ROCE |
| H3 | Valuation | Multiples vs peers, mcap/EV, fresh vs OFS, dilution |
| H4 | Risks | Ranked risks, litigation, governance, SME risks |
| H5 | Overall | `Strong`/`Watch`/`Avoid`, top 3 strengths and risks, what would change the view |

### H0. Orchestration

```text
for H1–H4: build evidence pack → analyst in a fresh context → validate schema + citations
verifier challenges findings (sees evidence, not reasoning) → dispute log
challenger rules on unresolved disputes (optional)
H5 synthesises H1–H4 + disputes, shown beside the deterministic score
```

Perspectives never see each other. Disagreements are logged, never merged
away. The deterministic score ([§M](#m-scoring)) is independent and always
shown. Prompts are versioned (`ai_outputs.prompt_version`). Calls run with
thinking off, JSON output, temperature 0. If no provider is available, a
deterministic template is used.

### H6. Interim evidence: web research

Until RHP extraction exists, a web-enabled **researcher** role builds the
evidence pack: official and exchange sources first, each fact with a URL and
a type (`official`, `exchange`, `secondary`), conflicts kept, gaps listed.
The pipeline assigns ids (`W1…`, app data as `D1…`); a citation gate drops
unknown ids. Web facts are unverified and become corroboration once RHP
extraction lands. Code: `backend/src/research/` (`research-v1`).

## I. Detailed PDF

One per IPO, with citations: cover (with deep link/QR) → executive summary →
issue snapshot → business → industry and peers → financials → valuation →
promoters → risks → SME module (SME only) → GMP and sentiment →
post-listing (if listed) → five AI summaries → checklist → sources →
glossary and disclaimer. Every chart/table states source, period and status.

## J. Summary PDF

One PDF across IPOs, built as an index into the app: cover (run date,
filters, freshness) → shortlist table → one page per IPO (snapshot, key
metrics, top 3 strengths/risks, verdict, gaps, QR and URL to `/ipos/{id}`) →
methodology → data-quality appendix. Base URL from config; never put secrets
in the PDF.

## K. Workflow and gates

Discover → fetch documents → extract → validate citations → reconcile
sources → compute ratios → score → AI summaries → review queue → PDFs →
email → track post-listing → calibrate.

| Stage | Gate | On failure |
| --- | --- | --- |
| Discovery | Valid name, exchange, dates | Skip and log |
| Fetch | HTTP 200, valid PDF, hash | Retry, then mark missing |
| Extraction | Schema valid, quote on page | Reject, queue review |
| Reconciliation | Conflicts recorded | Use higher-priority source, flag |
| Calculation | Inputs present | `None` with reason |
| Scoring | Required inputs | Lower confidence, never invent |
| Summaries | JSON and citations valid | Template fallback |
| PDF / email | Non-empty, recipients set | Block send, log, retry |

Feedback loop: store the original score and inputs, record 1-week to 1-year
returns after listing, recalibrate weights only with evidence, keep a
changelog of scoring and formula versions.

## L. Data quality

| State | Meaning | UI |
| --- | --- | --- |
| `reported` | From an official document | Normal |
| `calculated` | Derived by a documented formula | Show formula |
| `estimated` | Approximated | Badge + confidence |
| `unverified` | Secondary or unconfirmed | Warning |
| `missing` | Not found | "Missing", never zero |

Never fabricate or treat missing as zero. Show completeness per IPO, data
age and stale flags, both values when sources conflict, and what would change
the conclusion. A missing model or document must not block the pipeline.

Validation: `close ≥ open`, `listing ≥ close`; `price_lower ≤ price_upper`;
`fresh + OFS ≈ total`; `assets ≈ liabilities + equity`; non-negative
subscription; GMP outliers (> 500%) flagged; no overlapping periods.

## M. Scoring

**Today:** GMP 25%, valuation 25%, fundamentals 25%, subscription 15%,
risk 10%. Each factor is scored 0–100 with an explanation.

**Planned v2:** financial quality 25%, valuation 20%, business quality 15%,
issue structure 10%, demand and sentiment 15%, risk and governance 15%.

Verdicts: **≥ 75 Strong**, **55–74 Watch**, **< 55 Avoid**. Missing inputs
lower confidence, not the score; show completeness and confidence beside it
("high score, low confidence" is a valid result); cap any one factor; publish
weights; recalibrate only with a backtest.

## N. Extra categories

Worth covering beyond A: tax disputes and GST, ESG and climate risk,
insurance, FX/commodity and interest-rate sensitivity, order-book quality,
receivables ageing, pre-IPO deals and warrants, ESOP overhang, lock-in
expiries, anchor quality, lead-manager track record, use-of-proceeds
execution, related-party pricing, off-balance-sheet financing,
single-plant/customer concentration, fraud signals (sudden auditor
resignation, shell entities), management credibility, minority-shareholder
protection.

## O. Roadmap

Done: provider-agnostic AI layer with role routing and the `claude-code`
provider; web-evidence research (H1–H5, verifier, disputes, challenger);
daily scheduled run with AI verdicts in the PDF and email; subscriber digest
with Google sign-in.

Open:

- **AI layer** — `fastembed` and `llamacpp` rerankers; challenger loading
  with `keep_alive=0`; web research on the `anthropic` API provider.
- **Documents** — RHP discovery, download, Docling parse, chunk, embed;
  `documents`, `document_chunks`, `source_citations`; subscription snapshots.
- **Financial engine** — issue, shareholding, financial and peer tables;
  every §C metric in code with `formula_version`; `/overview` and
  `/financials` endpoints; completeness and confidence; in-depth app tab.
- **Extraction** — schema-validated RHP extraction with page quotes;
  prompt-injection defence; review queue.
- **Reports** — detailed (§I) and summary (§J) PDFs with charts, deep links
  and QR codes; `email_log` with retries.
- **Quality and ops** — more sources, fuzzy cross-source matching, golden-set
  evaluation, health alerts, retention, post-listing tracking and backtests,
  OpenAPI-generated frontend types, one-command stack.

## P. AI stack

Verified on Windows, AMD RX 9070 XT (16 GB), Ollama 0.40.12. A model is
trusted for a role only after `ollama ps` shows `100% GPU`.

### P1. Models

| Role | Local | Claude |
| --- | --- | --- |
| Analyst (H1–H5, chat) | `qwen3.5:9b-q4_K_M` | `claude-sonnet-5-5` |
| Verifier | `gemma4:12b` | `claude-opus-5-5` |
| Extractor (JSON, never decides) | `qwen3.5:4b-q4_K_M` | `claude-haiku-5-5` |
| Challenger (optional, disputes only) | `gpt-oss:20b` (loads solo, ~13 GB) | `claude-opus-5-5` |
| Researcher (web) | — | via `claude-code` |
| Embedder | `qwen3-embedding:0.6b` | stays local |
| Reranker | see §P3 | `llm` backend on the extractor |

The four core local models fit in VRAM together (~11 GB). On Claude, the
verifier's independence comes from a stronger tier plus an isolated context.
Document parsing always stays local.

```powershell
ollama pull qwen3-embedding:0.6b; ollama pull qwen3.5:4b-q4_K_M
ollama pull qwen3.5:9b-q4_K_M;   ollama pull gemma4:12b
ollama ps   # PROCESSOR must read 100% GPU
```

### P2. Reranking on Ollama

Ollama cannot serve a true reranker: `/api/rerank` returns 404, and
"reranker" registry models are served only as embedders. `bge-m3` is an
embedder; the cross-encoder is `bge-reranker-v2-m3`.

### P3. Reranker backends

Selected by `RERANK_PROVIDER`:

| Backend | What | Status |
| --- | --- | --- |
| `llm` / `ollama-llm` (default) | Extractor scores passages 0–10 as JSON | Done; validated live (4 passages, 0.65 s) |
| `fastembed` | BGE cross-encoder, ONNX, in-process CPU | Open |
| `llamacpp` | `llama-server --rerank-bge-v2-m3-default` on Vulkan (no `-fa` on AMD) | Open |

### P4. Role routing

```bash
LLM_ROLE_ANALYST_MODEL=qwen3.5:9b-q4_K_M
LLM_ROLE_VERIFIER_MODEL=gemma4:12b
LLM_ROLE_EXTRACTOR_MODEL=qwen3.5:4b-q4_K_M
LLM_ROLE_CHALLENGER_MODEL=gpt-oss:20b    # unset = skipped
LLM_ROLE_EMBEDDER_MODEL=qwen3-embedding:0.6b
# LLM_ROLE_RESEARCHER_*                  # inherits the extractor
RERANK_PROVIDER=ollama-llm
```

Any role can override `LLM_ROLE_<ROLE>_{MODEL,PROVIDER,BASE_URL,API_KEY,FALLBACKS}`;
unset keys inherit `LLM_*`. `LLMClient.for_role(role)` resolves them. Every
provider implements `generate`, `embed`, `health`, `capabilities`; the
OpenAI-compatible adapter covers most runtimes, with native Anthropic and
Gemini adapters.

### P5. Cloud policy

Local first. Cloud needs `LLM_ALLOW_CLOUD=true` plus a key, and is for one
role override, dev-time grading or a loudly logged fallback — never a silent
one. Every output records provider, model and prompt version.

### P6. Claude modes

`claude-code` (subscription) is personal use only: it strips
`ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`, caps calls at
`LLM_MAX_CONCURRENCY` (2) and reports the login in `/api/health`. Multi-user
or commercial use goes through `anthropic` with the same model ids. A local
fallback can pin a model, e.g. `LLM_FALLBACK_PROVIDERS=ollama=qwen3.5:9b-q4_K_M`.
