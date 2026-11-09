# IPO Research Framework

> **Purpose.** This is the research specification for the IPO Checker platform. It
> defines what must be collected, calculated, verified and analysed before an
> Indian IPO (NSE/BSE Mainboard or SME) can be assessed. It is a design document,
> not investment advice.
>
> **Design rule.** Deterministic code computes every number, threshold and score.
> A local LLM may read documents and write narratives, but it never invents a
> data point, changes a calculation, or overrides the 20% GMP filter.
>
> **Status.** Specification only. The current prototype stores IPO identity, GMP
> history, issue pricing and a lightweight deterministic analysis. The research
> tables, document store and local-AI layer described here are roadmap items.

---

## Table of contents

- [A. Complete research checklist](#a-complete-research-checklist)
- [B. Required data fields and database structure](#b-required-data-fields-and-database-structure)
- [C. Financial formulas and calculations](#c-financial-formulas-and-calculations)
- [D. Official and secondary data sources](#d-official-and-secondary-data-sources)
- [E. Document extraction requirements](#e-document-extraction-requirements)
- [F. Mainboard-specific research requirements](#f-mainboard-specific-research-requirements)
- [G. SME-specific research requirements](#g-sme-specific-research-requirements)
- [H. Five AI summary specifications](#h-five-ai-summary-specifications)
- [I. Detailed PDF report structure](#i-detailed-pdf-report-structure)
- [J. Summary PDF report structure](#j-summary-pdf-report-structure)
- [K. Automated research and verification workflow](#k-automated-research-and-verification-workflow)
- [L. Missing information and data-quality handling](#l-missing-information-and-data-quality-handling)
- [M. Recommended scoring framework](#m-recommended-scoring-framework)
- [N. Additional research categories](#n-additional-research-categories)
- [O. Implementation priorities](#o-implementation-priorities)

---

## A. Complete research checklist

Every item below must carry provenance (source, document, period, page, retrieval
date) and a data-quality status: `reported`, `calculated`, `estimated`,
`unverified` or `missing`. An item that cannot be sourced is marked `missing`,
never guessed.

### A1. IPO information and background

- [ ] Company legal name, brand name, CIN, incorporation date, registered office.
- [ ] Mainboard vs SME classification and the exact exchange/segment
      (NSE, BSE, NSE Emerge, BSE SME).
- [ ] IPO type: fresh issue, offer for sale, or a mix.
- [ ] Opening date, closing date, allotment date, refund date, listing date.
- [ ] Price band (lower/upper), issue price, face value, lot size, minimum
      retail application amount.
- [ ] Issue size (₹ crore and share count), fresh issue shares, OFS shares.
- [ ] Pre-issue and post-issue paid-up capital and share count.
- [ ] Pre-issue and post-issue shareholding pattern (promoter, promoter group,
      public, institutions, employees).
- [ ] Promoter holding before/after, dilution, any promoter selling in the OFS.
- [ ] Registrar, lead managers, underwriters, market maker (SME), legal counsel,
      statutory auditor, monitoring agency.
- [ ] Anchor investor allocation, anchor lock-in, other lock-ins.
- [ ] Objects of the issue and the amount allocated to each object.
- [ ] Use of proceeds vs historical capex/working-capital norms.
- [ ] IPO grade from a SEBI-registered credit-rating agency, where available.
- [ ] RHP/DRHP/prospectus URLs and filing dates.

### A2. Company and business research

- [ ] Business model and revenue streams, with segment split.
- [ ] Products/services and their stage of maturity.
- [ ] Customer segments (B2B, B2C, government, export) and contract types.
- [ ] Geographic presence and revenue by geography.
- [ ] Manufacturing/operational capacity, utilisation, expansion plans.
- [ ] Distribution network, dealers, branches, warehouses, service centres.
- [ ] Competitive advantages and their durability.
- [ ] Industry position and estimated market share.
- [ ] Customer concentration (top 1/5/10 customers as % of revenue).
- [ ] Supplier concentration and single-source dependencies.
- [ ] Order book, pipeline, long-term contracts, repeat revenue.
- [ ] Business scalability and operating leverage.
- [ ] Dependence on key individuals, promoters or a small technical team.
- [ ] Intellectual property, patents, trademarks, licences, technology stack.
- [ ] Subsidiaries, associates, joint ventures and group structure.
- [ ] Related-party transactions and their share of revenue/expenses.
- [ ] Employee count, attrition, union/labour exposure.
- [ ] Seasonality and working-capital intensity of the business model.
- [ ] ESG exposure: emissions, water, waste, safety, community, governance.

### A3. Complete financial analysis

Collect 3–5 financial years and, where available, 4–8 quarters. Prefer
consolidated statements; keep standalone separately if both exist.

**Income statement**

- [ ] Revenue from operations, other income, total income.
- [ ] Cost of goods sold / cost of materials / purchases.
- [ ] Employee benefit expense.
- [ ] Other expenses.
- [ ] EBITDA, EBIT, finance costs, depreciation and amortisation.
- [ ] Exceptional/extraordinary items and their nature.
- [ ] Profit before tax, tax expense, effective tax rate, PAT.
- [ ] EPS (basic and diluted), dividend per share.

**Balance sheet**

- [ ] Total assets, total liabilities, total equity.
- [ ] Current assets: cash, receivables, inventory, loans/advances, other.
- [ ] Current liabilities: payables, short-term borrowings, provisions, other.
- [ ] Long-term borrowings, lease liabilities, deferred tax.
- [ ] Net worth, reserves and surplus.
- [ ] Intangible assets, goodwill, capital work in progress.
- [ ] Contingent liabilities and commitments.
- [ ] Off-balance-sheet items, guarantees, letters of comfort.
- [ ] Share capital, preference shares, warrants, convertible instruments.

**Cash flow**

- [ ] Operating cash flow (OCF), investing cash flow, financing cash flow.
- [ ] Capex (tangible and intangible), free cash flow.
- [ ] OCF/EBITDA and OCF/PAT (earnings-quality checks).
- [ ] Working-capital movement and its drivers.
- [ ] Receivables and inventory trends vs revenue.
- [ ] Dividends, buybacks, debt repayment, equity raised.

**Ratios and quality checks**

- [ ] ROE, ROCE, ROA.
- [ ] Debt/equity, net debt/EBITDA, current ratio, quick ratio.
- [ ] Interest coverage.
- [ ] Asset turnover, inventory turnover, receivables turnover, payables days.
- [ ] Cash conversion cycle.
- [ ] EPS, book value per share, post-issue EPS and BVPS.
- [ ] Revenue/EBITDA/PAT growth (YoY, QoQ, 3-year CAGR).
- [ ] Margin trend and its drivers.
- [ ] Related-party revenue/expense share.
- [ ] Auditor qualifications, emphasis of matter, restatements.
- [ ] Accounting-policy changes, revenue-recognition concerns.
- [ ] Related-party loans, round-tripping indicators, evergreening.
- [ ] Aggressive capitalisation, low cash conversion, rising receivables.

### A4. Promoter and management investigation

- [ ] Promoter names, backgrounds, education, track record.
- [ ] Directors, KMP, CFO, company secretary, independent directors.
- [ ] Other directorships and previous companies.
- [ ] Previous business failures, insolvency, strikes-off, defaults.
- [ ] Litigation: civil, criminal, tax, regulatory, consumer, labour.
- [ ] SEBI orders, MCA action, RBI/other regulator action.
- [ ] Promoter shareholding, pledge, encumbrance, non-disposal undertakings.
- [ ] Related-party transactions and conflicts of interest.
- [ ] Corporate-governance structure, board independence, committees.
- [ ] Auditor identity, tenure, changes, qualifications, resignation.
- [ ] Management remuneration and related-party compensation.
- [ ] Insider selling, pre-IPO placement, warrants, ESOP dilution.
- [ ] Succession planning and key-person risk.

### A5. IPO valuation

- [ ] Issue market capitalisation at the upper band.
- [ ] Enterprise value at the upper band.
- [ ] Post-issue P/E (and pre-issue P/E).
- [ ] Price-to-book (post-issue).
- [ ] EV/EBITDA and EV/Sales.
- [ ] Earnings yield.
- [ ] Dilution and post-issue ownership.
- [ ] OFS percentage of the issue.
- [ ] Listed comparable companies and their multiples.
- [ ] Industry median/quartile multiples.
- [ ] Valuation premium/discount vs peers.
- [ ] Implied valuation at lower band and at listing price.
- [ ] Valuation vs recent comparable listings and their after-listing performance.
- [ ] Verdict: attractively priced / fair / expensive, with reasoning.

### A6. Industry and competitor research

- [ ] Total addressable market (TAM), serviceable market (SAM), CAGR.
- [ ] Industry growth drivers and cyclicality.
- [ ] Industry profitability and margin structure.
- [ ] Market structure, fragmentation, consolidation.
- [ ] Major competitors, listed and unlisted.
- [ ] Company market share and ranking.
- [ ] Competitive advantages and entry barriers.
- [ ] Regulatory environment and pending regulation.
- [ ] Technology disruption and substitution risk.
- [ ] Domestic and export demand.
- [ ] Import/export dependence, currency exposure, commodity exposure.
- [ ] Government policy, subsidies, PLI, taxation.

### A7. GMP and market sentiment (maximum five GMP sources)

- [ ] GMP history and daily changes.
- [ ] GMP absolute and GMP %.
- [ ] Kostak rate, where reliably available.
- [ ] Subject-to-sauda rate, where reliably available.
- [ ] Retail subscription (times and amount).
- [ ] NII subscription (small and big NII where available).
- [ ] QIB subscription.
- [ ] Employee and shareholder quota subscription.
- [ ] Overall subscription and day-wise subscription trend.
- [ ] Anchor investor participation and lock-in.
- [ ] Institutional demand signals.
- [ ] Listing price, listing gain/loss, post-listing performance.
- [ ] Explicit separation of sentiment from fundamentals.

### A8. Regulatory, legal and risk research

- [ ] SEBI observations, clarifications and pending proceedings.
- [ ] Material litigation and its financial exposure.
- [ ] Tax disputes and contingent liabilities.
- [ ] Environmental, safety and operational compliance.
- [ ] Pending investigations and show-cause notices.
- [ ] Licences, approvals, permits and their renewal risk.
- [ ] Related-party and group-company risks.
- [ ] Customer/supplier dependency risks.
- [ ] Industry-specific regulation.
- [ ] Business-continuity, disaster-recovery and cyber risk.
- [ ] Insurance coverage adequacy.
- [ ] Data privacy and information-security exposure.
- [ ] Key-person and succession risk.
- [ ] Litigation against promoters/directors.
- [ ] Red-flag synthesis and severity.

### A9. SME-specific investigation

- [ ] Operating scale and limited financial history.
- [ ] Liquidity and low free float.
- [ ] Market-maker arrangement, inventory and obligations.
- [ ] Shareholder concentration and promoter dependency.
- [ ] Working-capital and cash-flow risks.
- [ ] Corporate-governance quality and board independence.
- [ ] Trading restrictions and SME exchange rules.
- [ ] Valuation risk: SME multiples vs mainboard peers.
- [ ] Price manipulation, circular trading, pump-and-dump indicators.
- [ ] Migration path to mainboard, if stated.
- [ ] Disclosure quality and RHP completeness.
- [ ] Post-listing volatility and exit liquidity.

### A10. Post-listing tracking

- [ ] Issue price, listing price, listing gain/loss.
- [ ] Daily/weekly/monthly price performance.
- [ ] Quarterly results vs IPO projections.
- [ ] Promoter holding changes and pledge changes.
- [ ] Lock-in expiries and supply overhang.
- [ ] Corporate announcements and actions.
- [ ] Use of proceeds vs stated objects.
- [ ] Dividend/bonus/split/rights/buyback.
- [ ] Comparison of actual performance with the original assessment.
- [ ] Score calibration: did the verdict predict the outcome?

---

## B. Required data fields and database structure

### B1. Design principles

1. **One canonical IPO row** (`ipos`) plus source-specific provenance
   (`ipo_sources`). Never overwrite one source's value with another's without
   recording the conflict.
2. **Facts are periodised.** Financial values belong to a period and a basis
   (standalone/consolidated, audited/unaudited).
3. **Every fact is sourced.** `source_citations` links a fact to a document,
   page, quote and retrieval time.
4. **Derived values are reproducible.** Store the formula version and inputs
   used, or recompute from raw facts; never store only the output.
5. **AI output is separate.** `ai_outputs` stores model, prompt version, input
   hash, output, citations and confidence. It never overwrites facts.
6. **Soft-delete/history.** Keep snapshots and `created_at`/`updated_at`; do not
   destroy history needed for backtesting.

### B2. Proposed tables

Existing tables: `ipos`, `gmp_history`, `analysis_reports`, `scrape_runs`,
`ipo_sources`, `schema_migrations`.

| Table | Purpose | Key columns |
| --- | --- | --- |
| `companies` | Legal entity, CIN, incorporation, registered office, group | `id`, `ipo_id`, `legal_name`, `cin`, `incorporation_date`, `registered_office`, `parent_company_id` |
| `ipo_issue` | Issue structure | `ipo_id`, `issue_type`, `fresh_issue_shares`, `ofs_shares`, `total_offer_shares`, `price_lower`, `price_upper`, `face_value`, `lot_size`, `issue_size_cr`, `min_retail_amount`, `registrar`, `lead_managers`, `market_maker`, `underwriters`, `listing_exchange`, `listing_date`, `allotment_date`, `refund_date` |
| `issue_objects` | Objects of the issue | `ipo_id`, `rank`, `object`, `amount_cr`, `description` |
| `shareholding` | Pre/post-issue ownership | `ipo_id`, `as_of`, `holder_category`, `shares`, `percent`, `phase` (`pre`/`post`), `pledged_percent` |
| `financial_periods` | Period metadata | `id`, `ipo_id`, `period_type` (`annual`/`quarterly`), `fiscal_year`, `quarter`, `start_date`, `end_date`, `basis` (`standalone`/`consolidated`), `audited`, `currency`, `unit` |
| `financial_facts` | Normalised line items | `id`, `period_id`, `statement` (`pnl`/`balance_sheet`/`cash_flow`), `line_item`, `value`, `citation_id` |
| `financial_ratios` | Derived ratios | `id`, `period_id`, `ratio`, `value`, `formula_version`, `inputs_json` |
| `subscription_snapshots` | Demand by category/day | `id`, `ipo_id`, `snapshot_date`, `category` (`retail`/`nii_small`/`nii_big`/`qib`/`employee`/`shareholder`/`overall`), `shares_offered`, `shares_bid`, `times`, `amount_cr` |
| `gmp_history` (extend) | Sentiment history | add `kostak`, `subject_to_sauda`, `snapshot_date`, `scrape_run_id` |
| `peers` | Listed comparables | `id`, `ipo_id`, `peer_name`, `ticker`, `exchange`, `market_cap_cr`, `pe`, `pb`, `ev_ebitda`, `ev_sales`, `source_citation_id` |
| `industry_metrics` | Market context | `id`, `ipo_id`, `metric`, `value`, `unit`, `period`, `source_citation_id` |
| `documents` | RHP/DRHP/annual reports | `id`, `ipo_id`, `doc_type`, `title`, `url`, `local_path`, `sha256`, `published_at`, `retrieved_at`, `page_count`, `status` |
| `document_chunks` | RAG chunks | `id`, `document_id`, `page_start`, `page_end`, `text`, `token_count`, `embedding`, `embedding_model` |
| `source_citations` | Provenance per fact | `id`, `entity_type`, `entity_id`, `document_id`, `page`, `quote`, `source_url`, `published_at`, `retrieved_at`, `quality` (`reported`/`calculated`/`estimated`/`unverified`/`missing`) |
| `research_findings` | Litigation, governance, risks | `id`, `ipo_id`, `category`, `finding`, `severity`, `status` (`verified`/`alleged`/`unverified`), `citation_id` |
| `post_listing_prices` | After listing | `id`, `ipo_id`, `trade_date`, `open`, `high`, `low`, `close`, `volume`, `source` |
| `ai_outputs` | Local-model output | `id`, `ipo_id`, `kind`, `model`, `prompt_version`, `input_hash`, `output_json`, `citations_json`, `confidence`, `created_at` |
| `analysis_reports` (extend) | Deterministic analysis snapshots | add `model_version`, `inputs_hash`, `data_completeness` |
| `email_log` | Delivery audit | `id`, `report_id`, `sent_at`, `recipients`, `status`, `error` |
| `chat_sessions` / `chat_messages` | Chat history | session/message ids, role, content, citations, created_at |
| `review_queue` | Human review | `id`, `entity_type`, `entity_id`, `reason`, `status`, `assigned_to`, `resolved_at` |

### B3. Field-level metadata

For every stored fact, record:

| Field | Meaning |
| --- | --- |
| `source` | Publisher (SEBI, NSE, BSE, MCA, company, news). |
| `document_name` | Exact document title. |
| `document_url` | Stable URL or local path. |
| `reporting_period` | FY/quarter and basis. |
| `page` | Page number for PDF facts. |
| `published_at` | Document publication date. |
| `retrieved_at` | When we fetched it. |
| `quality` | `reported`, `calculated`, `estimated`, `unverified`, `missing`. |
| `confidence` | 0–1, required for estimates and AI extractions. |

### B4. Canonical units and conventions

- Money in **₹ crore** unless a field says otherwise; store the unit explicitly.
- Percentages as percentage points (`12.5` means 12.5%), not fractions.
- Dates as ISO-8601 (`YYYY-MM-DD`); timestamps as UTC ISO-8601.
- Financial years as `YYYY-YY` (Indian April–March).
- Shares as absolute counts; multiples as `x`.
- Null means unknown. `0` means a real zero. Never use `0` for missing.

---

## C. Financial formulas and calculations

All formulas must be implemented once in deterministic code, unit-tested, and
versioned. Guard every division by zero and return `None` with a reason.

### C1. Growth

| Metric | Formula |
| --- | --- |
| YoY growth | `(value_t / value_{t-1} - 1) × 100` |
| QoQ growth | `(value_q / value_{q-1} - 1) × 100` |
| CAGR (n years) | `(value_end / value_start)^(1/n) - 1`, expressed as % |
| 3-year average growth | Arithmetic mean of the available YoY growth rates |

### C2. Profitability

| Metric | Formula |
| --- | --- |
| Gross profit | `Revenue - COGS` |
| Gross margin | `Gross profit / Revenue × 100` |
| EBITDA | `EBIT + D&A` = `PBT + finance costs + D&A` (state the definition used) |
| EBITDA margin | `EBITDA / Revenue × 100` |
| EBIT | `PBT + finance costs` |
| Operating margin | `EBIT / Revenue × 100` |
| PAT margin | `PAT / Revenue × 100` |
| Effective tax rate | `Tax expense / PBT × 100` |
| EPS (basic) | `PAT / weighted average shares` |
| Post-issue EPS | `PAT / post-issue shares` |

### C3. Returns

| Metric | Formula |
| --- | --- |
| ROE | `PAT / average shareholders' equity × 100` |
| ROCE | `EBIT / average capital employed × 100`; capital employed = `total assets - current liabilities` (or `equity + total debt`) |
| ROA | `PAT / average total assets × 100` |
| DuPont ROE | `net margin × asset turnover × equity multiplier` |

### C4. Leverage and liquidity

| Metric | Formula |
| --- | --- |
| Debt/equity | `total debt / shareholders' equity` |
| Net debt | `total debt - cash and equivalents` |
| Net debt/EBITDA | `net debt / EBITDA` |
| Current ratio | `current assets / current liabilities` |
| Quick ratio | `(current assets - inventory - prepaid) / current liabilities` |
| Interest coverage | `EBIT / finance costs` |
| DSCR (where relevant) | `(PAT + D&A + interest) / (interest + scheduled principal)` |

### C5. Efficiency and working capital

| Metric | Formula |
| --- | --- |
| Asset turnover | `Revenue / average total assets` |
| Inventory turnover | `COGS / average inventory` |
| Days inventory (DIO) | `365 / inventory turnover` |
| Receivables turnover | `Revenue / average receivables` |
| Days sales outstanding (DSO) | `365 / receivables turnover` |
| Payables turnover | `COGS / average payables` |
| Days payables (DPO) | `365 / payables turnover` |
| Cash conversion cycle | `DIO + DSO - DPO` |
| Capex intensity | `Capex / Revenue × 100` |

### C6. Cash flow

| Metric | Formula |
| --- | --- |
| Free cash flow | `OCF - capex` |
| OCF/EBITDA | `OCF / EBITDA` |
| OCF/PAT | `OCF / PAT` (earnings-quality indicator) |
| Cash conversion | `OCF / EBITDA × 100` |
| FCF yield | `FCF / market cap × 100` |

### C7. Valuation

| Metric | Formula |
| --- | --- |
| Post-issue market cap | `issue_price × post-issue shares` |
| Enterprise value | `market cap + total debt - cash` |
| P/E | `issue_price / post-issue EPS` |
| P/B | `issue_price / post-issue BVPS` |
| BVPS | `post-issue equity / post-issue shares` |
| EV/EBITDA | `EV / EBITDA` |
| EV/Sales | `EV / Revenue` |
| Earnings yield | `post-issue EPS / issue_price × 100` = `1 / P/E × 100` |
| Dilution | `(post-issue shares - pre-issue shares) / post-issue shares × 100` |
| OFS share of issue | `OFS shares / total offer shares × 100` |
| Minimum retail application | `lot_size × issue_price_upper` |
| Peer premium/discount | `(company multiple / peer median multiple - 1) × 100` |
| Implied listing gain | `(estimated_listing_price - issue_price) / issue_price × 100` |

### C8. GMP and demand

| Metric | Formula |
| --- | --- |
| GMP % | `GMP / issue_price × 100` |
| GMP change | `GMP_t - GMP_{t-1}` |
| GMP trend | Slope or difference over 7–14 days; label Rising/Stable/Falling |
| Source spread | `max(latest GMP% by source) - min(latest GMP% by source)` |
| Subscription times | `shares bid / shares offered` |
| Day-wise subscription | Same formula per category and snapshot date |
| Demand score | Weighted blend of QIB, NII and retail subscription, normalised |

### C9. Calculation rules

- Use **average** balance-sheet values for ratios when two period-end values
  exist; otherwise use the closing value and mark the ratio `estimated`.
- Never mix standalone and consolidated figures in one ratio.
- Never mix annual and quarterly figures in one growth calculation.
- Recompute all ratios after a restatement; keep the previous version.
- Store `formula_version` with every derived ratio.
- Round only for display; store full precision.

---

## D. Official and secondary data sources

### D1. Source hierarchy

| Priority | Source | Use |
| --- | --- | --- |
| 1 | SEBI filings (DRHP, RHP, prospectus, observations) | Authoritative issue, business, risk, financial and object-of-issue facts. |
| 2 | NSE / BSE disclosures | Dates, price band, lot size, subscription, allotment, listing, corporate actions. |
| 3 | MCA records | Incorporation, directors, charges, filings, group structure. |
| 4 | Company annual reports and audited financials | Historical financials, auditor reports, related-party transactions. |
| 5 | Official industry/government sources | TAM, regulation, policy, macro data. |
| 6 | Reputable financial data providers | Peer multiples, consensus, price history. |
| 7 | Secondary news/research | Context only; never the sole source for a hard fact. |

### D2. Concrete sources

- **SEBI** — `sebi.gov.in` filings, EDIFAR (where available), orders, informal
  guidance.
- **NSE** — `nseindia.com` IPO page, allotment, subscription, listing,
  corporate announcements, bhavcopy.
- **BSE** — `bseindia.com` IPO page, SME platform, allotment, listing,
  announcements, bhavcopy.
- **MCA** — `mca.gov.in` company master data, directors, charges.
- **Company** — RHP/DRHP/prospectus, annual reports, investor presentations,
  credit-rating rationales.
- **Credit-rating agencies** — CRISIL, ICRA, CARE, India Ratings, Brickwork.
- **Industry** — ministry sites, RBI, NPCI, industry associations, trade bodies.
- **Market data** — NSE/BSE bhavcopy, Yahoo Finance (secondary), Screener
  (secondary).
- **GMP** — maximum five sources, e.g. InvestorGain, IPO Watch, Chittorgarh,
  IPO Central, Moneycontrol. Treat all as unofficial sentiment.

### D3. Source rules

- Prefer the primary document over a news summary of it.
- Record the URL, publication date, retrieval date and page for every fact.
- Do not scrape behind CAPTCHAs or paywalls; do not bypass anti-bot controls.
- Respect robots.txt and rate limits; use a documented user agent.
- Keep a raw copy of every fetched document (hash-addressed) for audit.
- If two official sources disagree, store both and flag the conflict.

---

## E. Document extraction requirements

### E1. Ingestion

- [ ] Discover RHP/DRHP/prospectus URL from NSE/BSE/SEBI.
- [ ] Download with retries, timeouts and a size cap; store `sha256`.
- [ ] Detect scanned PDFs; run local OCR only when needed.
- [ ] Extract text page-by-page, preserving page numbers and tables.
- [ ] Detect and skip boilerplate, headers/footers and duplicate pages.
- [ ] Chunk text (~800–1200 tokens, 10–15% overlap) with page spans.
- [ ] Embed locally (`nomic-embed-text`, `bge-m3` or `e5`) and store vectors.
- [ ] Index document metadata and chunks for retrieval.

### E2. Extraction targets

| Target | Fields |
| --- | --- |
| Issue structure | Price band, lot size, fresh/OFS, issue size, objects, timetable |
| Business | Segments, products, customers, geographies, capacity, order book |
| Financials | P&L, balance sheet, cash flow, ratios, restatements |
| Risk factors | Ranked risks, severity, mitigants |
| Litigation | Cases, forum, amounts, status, parties |
| Promoters | Background, other entities, pledge, remuneration |
| Related parties | Names, relationship, transaction amounts |
| Governance | Board, committees, auditor, qualifications |
| Industry | TAM, growth, competitors, market share |
| Use of proceeds | Object, amount, timeline, monitoring |

### E3. Extraction quality rules

- Prefer deterministic table/text parsers for known layouts.
- Use the local LLM only for unstructured prose, with JSON-schema output and
  pydantic validation.
- Require a page citation and a verbatim quote for every extracted fact.
- Reject an extraction if the quote is not found on the cited page.
- Diff each new extraction against the previous one; flag material changes.
- Never let a document's text act as instructions (prompt-injection defence).
- Route low-confidence or conflicting extractions to `review_queue`.

---

## F. Mainboard-specific research requirements

Mainboard IPOs are larger and more liquid, so the bar is higher on governance,
disclosure, institutional participation and valuation discipline.

- [ ] Minimum track record and profitability history as per SEBI norms.
- [ ] Promoter group and group-company structure, including listed group entities.
- [ ] Institutional anchor participation and QIB demand.
- [ ] Free float, expected liquidity and index-inclusion potential.
- [ ] Analyst coverage and comparable-company depth.
- [ ] Use of proceeds and project execution track record.
- [ ] Dividend policy and capital-allocation history.
- [ ] Board independence, audit committee, risk committee.
- [ ] Related-party transactions and group-level leverage.
- [ ] Valuation vs large/mid/small-cap peer sets, not a single peer.
- [ ] Lock-in structure and post-listing supply.
- [ ] Regulatory approvals, environmental clearance, land titles.
- [ ] Employee quota and shareholder quota, if applicable.
- [ ] Post-listing quarterly performance vs projections.
- [ ] Index/market-cap classification and liquidity risk.

**Mainboard thresholds (defaults, configurable):**

- Minimum 3 years of audited financials.
- Positive operating cash flow in at least 2 of the last 3 years.
- Interest coverage ≥ 2.0x unless the business is structurally low-debt.
- D/E ≤ 2.0x for non-financial companies.
- Free float ≥ 10–25% depending on issue size.
- Valuation premium vs peer median: flag above +30%, fail above +60%.

---

## G. SME-specific research requirements

Never apply mainboard thresholds blindly to SME IPOs. SME risk is dominated by
scale, liquidity, concentration and governance.

- [ ] Operating scale, revenue and employee count.
- [ ] Financial history (often only 2–3 years) and audit quality.
- [ ] Liquidity: low free float, wide spreads, market-maker dependence.
- [ ] Market-maker identity, inventory, obligations and track record.
- [ ] Shareholder concentration and promoter dependency.
- [ ] Working-capital intensity and receivables/inventory quality.
- [ ] Corporate-governance quality and board independence.
- [ ] SME exchange rules, trading restrictions and lot sizes.
- [ ] Valuation: SME multiples vs mainboard peers; avoid mechanical P/E comparison.
- [ ] Price manipulation, circular trading and pump-and-dump indicators.
- [ ] Disclosure completeness and RHP quality.
- [ ] Migration path to mainboard, if stated.
- [ ] Post-listing volatility and exit liquidity.
- [ ] Lock-in and market-maker inventory overhang.

**SME-specific rules (defaults, configurable):**

- Require positive OCF in the latest year.
- Cap D/E at 1.5x for non-financial SMEs; flag above 1.0x.
- Require a named market maker and a credible market-making track record.
- Flag free float below 25% or daily traded value below a liquidity floor.
- Apply a valuation discount/premium band to peer median, but also show the
  absolute valuation and the implied earnings yield.
- Treat GMP as sentiment only; give it less weight than for mainboard.
- Add an explicit "SME risk" block to every report.

---

## H. Five AI summary specifications

All five summaries are generated by a **local** model, with a fixed prompt
version, JSON-schema output, citations and confidence. If the model is missing,
the deterministic template is used instead.

Each summary must contain:

| Field | Meaning |
| --- | --- |
| `evidence` | Bullet list of facts with citations. |
| `conclusion` | Short, non-advisory conclusion. |
| `confidence` | `high` / `medium` / `low` with a reason. |
| `missing_information` | What would change the conclusion. |
| `citations` | `IPO · source · page · retrieved_at`. |
| `data_as_of` | Timestamp of the underlying data. |

### H1. Business Quality Summary

- Business model, revenue streams, customer segments, geography.
- Competitive advantages, market position, scalability.
- Customer/supplier concentration, key-person dependence.
- Conclusion on durability and quality of the franchise.
- Confidence based on disclosure completeness.

### H2. Financial Health Summary

- Revenue, EBITDA, PAT growth and margin trends.
- Balance-sheet strength, leverage, liquidity.
- Cash-flow quality, working capital, receivables/inventory.
- ROE/ROCE and earnings quality.
- Conclusion on financial resilience and sustainability.

### H3. Valuation and Pricing Summary

- Issue price vs peer multiples, P/E, P/B, EV/EBITDA.
- Implied market cap and enterprise value.
- Premium/discount vs peers and recent listings.
- Fresh vs OFS mix and dilution.
- Conclusion: attractive / fair / expensive, with sensitivity.

### H4. Risk and Red Flag Summary

- Ranked risks from the RHP and data.
- Litigation, regulatory, tax, governance, related-party issues.
- Customer/supplier/key-person/industry risks.
- SME-specific risks where applicable.
- Conclusion with severity and confidence.

### H5. Overall Investment Assessment

- Synthesise the four summaries and the deterministic score.
- State the verdict (`Strong` / `Watch` / `Avoid`) and why.
- Top 3 strengths and top 3 risks.
- What would change the view.
- Explicitly not investment advice; show data timestamps.

---

## I. Detailed PDF report structure

One PDF per IPO, generated locally, with page-level citations.

1. **Cover** — company, exchange/segment, issue dates, price band, report date,
   data-as-of timestamp, deep link/QR to the app detail page.
2. **Executive summary** — verdict, score, top strengths/risks, key metrics,
   data completeness.
3. **Issue snapshot** — issue size, fresh/OFS, lot size, minimum application,
   registrar, lead managers, market maker, objects of issue.
4. **Company and business** — history, model, products, customers, geography,
   capacity, order book, subsidiaries, related parties.
5. **Industry and peers** — TAM, growth, market share, competitors, peer table,
   valuation comparison.
6. **Financial analysis** — annual and quarterly tables, growth, margins,
   balance sheet, cash flow, ratios, charts, earnings-quality checks.
7. **Valuation** — market cap, EV, P/E, P/B, EV/EBITDA, earnings yield,
   dilution, peer premium/discount, fair-value range.
8. **Promoter and management** — backgrounds, track record, litigation, pledge,
   remuneration, governance, auditor.
9. **Risk and red flags** — ranked risks, severity, mitigants, contingent
   liabilities, regulatory issues.
10. **SME module** — only for SME IPOs; liquidity, market maker, concentration,
    manipulation indicators, valuation caveats.
11. **GMP and sentiment** — GMP history chart, source spread, subscription by
    category, anchor participation, listing performance (if listed).
12. **Post-listing tracking** — only if listed; price performance, results vs
    projections, promoter/lock-in changes.
13. **Five AI summaries** — one section each, with evidence, conclusion,
    confidence, missing information and citations.
14. **Deterministic checklist** — pass/warn/fail/manual with details.
15. **Sources and citations** — document list, page references, retrieval dates,
    data-quality status.
16. **Glossary and disclaimer** — definitions, methodology, not-investment-advice
    statement.

Every chart/table must state its source, period and whether values are reported,
calculated or estimated.

---

## J. Summary PDF report structure

One short PDF covering multiple IPOs, designed as an index into the app.

1. **Cover** — run date, filters (GMP ≥ 20%, upcoming included/excluded), data
   freshness, app base URL.
2. **Shortlist table** — name, segment, verdict, score, GMP %, issue price,
   issue size, close date, data completeness, deep link.
3. **One page per IPO** (or two if needed):
   - Snapshot: price band, dates, issue size, fresh/OFS, lot size.
   - Key metrics: GMP %, P/E, subscription, revenue/PAT growth, D/E.
   - Top 3 strengths and top 3 risks.
   - Verdict and confidence.
   - Data gaps and "read the full report in the app" call to action.
   - QR code and short URL to `/ipos/{id}`.
4. **Methodology and disclaimer** — scoring weights, data sources, not advice.
5. **Appendix** — data-quality summary, failed scrapes, stale data warnings.

**Deep-link rules**

- Base URL comes from config (`APP_BASE_URL`, default `http://localhost:3000`).
- Route pattern: `/ipos/{id}` (overview) and `/ipos/{id}?tab=financials`
  (in-depth).
- Include both a human-readable URL and a QR code.
- If the app is not reachable (e.g. printed at a remote location), the QR still
  encodes the IPO ID so the reader can look it up later.
- Never put secrets or tokens in the PDF.

---

## K. Automated research and verification workflow

```
Discover IPOs
  → fetch official documents (NSE/BSE/SEBI)
  → deterministic extraction + local-LLM fallback
  → schema validation + citation verification
  → source reconciliation + conflict flagging
  → compute financial facts and ratios
  → run deterministic checks and scoring
  → generate five local-AI summaries (optional)
  → route low-confidence items to review queue
  → render detailed + summary PDFs with deep links
  → email / publish
  → track post-listing outcomes
  → calibrate scoring against outcomes
```

### K1. Stages and gates

| Stage | Deterministic gate | Failure handling |
| --- | --- | --- |
| Discovery | Valid name, exchange, dates, status | Skip and log. |
| Document fetch | HTTP 200, valid PDF, hash stored | Retry, then mark missing. |
| Extraction | Schema valid, quote found on page | Reject, retry with parser, queue review. |
| Reconciliation | Conflicts recorded, not overwritten | Flag and use the higher-priority source. |
| Calculations | Inputs present, no divide-by-zero | Return `None` with reason. |
| Scoring | All required inputs present | Reduce confidence, never invent. |
| Summaries | JSON valid, citations valid | Fall back to template. |
| PDF | Non-empty, links resolve | Block send, alert. |
| Email | Recipients configured, PDF attached | Log and retry. |

### K2. Verification checklist

- [ ] Every hard fact has a citation.
- [ ] Every calculated metric has inputs and a formula version.
- [ ] Every AI claim has a citation or is labelled as interpretation.
- [ ] Conflicting sources are recorded, not silently resolved.
- [ ] Missing data is explicit and counted in completeness.
- [ ] Dates are ISO-8601 and timezone-aware where relevant.
- [ ] Units are explicit and consistent.
- [ ] Post-listing outcomes are linked back to the original assessment.

### K3. Feedback loop

- Store the original score, inputs and data completeness.
- After listing, store 1-week/1-month/3-month/6-month/1-year returns.
- Compare verdicts with outcomes; recalibrate weights only with evidence.
- Keep a changelog of scoring and formula versions.

---

## L. Missing information and data-quality handling

### L1. Data-quality states

| State | Meaning | UI treatment |
| --- | --- | --- |
| `reported` | Taken directly from an official document. | Normal. |
| `calculated` | Derived from reported values with a documented formula. | Show formula. |
| `estimated` | Inferred or approximated. | Show estimate badge + confidence. |
| `unverified` | From a secondary source or unconfirmed claim. | Show warning. |
| `missing` | Not found. | Show "missing", never a blank zero. |

### L2. Rules

- Never fabricate a value to fill a gap.
- Never treat a missing value as zero in a calculation.
- Show data completeness per IPO (e.g. 62% of checklist items sourced).
- Show the age of each data point; flag stale GMP or price data.
- If sources conflict, show both and the chosen value with a reason.
- Distinguish "verified disclosure" from "allegation" and "unverified claim".
- Route low-confidence AI extractions to human review.
- Degrade gracefully: a missing model or document must not block the pipeline.
- Make every report state what is missing and what would change the conclusion.

### L3. Validation rules

- `close_date >= open_date`; `listing_date >= close_date` where present.
- `price_lower <= price_upper`; `issue_price` within the band.
- `fresh_issue + ofs ≈ total_offer` within rounding tolerance.
- Balance sheet: `assets ≈ liabilities + equity` within tolerance.
- Cash flow: `ending cash ≈ beginning cash + net cash flow`.
- Subscription times non-negative; GMP outliers flagged (e.g. > 500%).
- Financial period dates must not overlap for the same basis/type.
- Duplicate detection on `ipo_sources`, normalized name and fuzzy similarity.

---

## M. Recommended scoring framework

Keep the current transparent weighted score as the baseline. The research-grade
version can add factors without becoming a black box.

### M1. Baseline (implemented today)

| Factor | Weight |
| --- | --- |
| GMP | 25% |
| Valuation | 25% |
| Fundamentals | 25% |
| Subscription | 15% |
| Risk | 10% |

Each factor has an explicit 0–100 score, a weight, a weighted contribution and a
plain-language explanation. Verdict: `Strong` / `Watch` / `Avoid`.

### M2. Proposed research-grade v2

| Factor | Weight | Inputs |
| --- | --- | --- |
| Financial quality | 25% | Growth, margins, ROE/ROCE, cash conversion, leverage |
| Valuation | 20% | P/E, P/B, EV/EBITDA vs peers, earnings yield |
| Business quality | 15% | Moat, market position, concentration, scalability |
| Issue structure | 10% | Fresh vs OFS, objects, dilution, anchor/lock-in |
| Demand and sentiment | 15% | Subscription, GMP trend, source spread |
| Risk and governance | 15% | Litigation, auditor, related-party, SME risks |

### M3. Score construction rules

- Each factor is scored 0–100 using documented thresholds.
- Missing inputs reduce **confidence**, not the score silently.
- Show `data_completeness` separately (0–100%).
- Show `confidence` (`high`/`medium`/`low`) alongside the score.
- Never let a single factor dominate; cap any factor's contribution.
- Publish the weights and thresholds in the report and in config.
- Recalibrate only with a documented backtest.

### M4. Verdict bands

| Score | Verdict | Meaning |
| --- | --- | --- |
| ≥ 75 | Strong | Multiple factors align; still not advice. |
| 55–74 | Watch | Mixed; needs monitoring or more data. |
| < 55 | Avoid | Material concerns or poor risk/reward. |

Always show the reasons, the data gaps and the confidence. A high score with low
completeness must be shown as "high score, low confidence".

---

## N. Additional research categories

Categories the first draft may have under-weighted:

1. **Tax** — historical tax disputes, effective tax rate, deferred tax, GST
   issues, transfer pricing.
2. **ESG** — emissions, water, waste, safety, labour, community, board diversity.
3. **Cyber and data privacy** — breaches, compliance, IT dependency.
4. **Insurance** — coverage vs exposure, claims history.
5. **FX and commodities** — export/import share, hedging policy, sensitivity.
6. **Interest-rate sensitivity** — floating-rate debt, refinancing risk.
7. **Seasonality** — revenue and working-capital seasonality.
8. **Capacity utilisation** — current vs optimal, capex timing.
9. **Order book quality** — cancellable vs firm, execution history.
10. **Customer credit quality** — receivables ageing, bad debts, write-offs.
11. **Supplier reliability** — single-source, lead times, price pass-through.
12. **Key-person and succession** — dependence, bench strength.
13. **Employee relations** — attrition, unions, strikes, safety incidents.
14. **Intellectual property** — patents, disputes, licensing, obsolescence.
15. **Brand and marketing** — spend efficiency, customer acquisition cost.
16. **Distribution** — dealer quality, channel conflict, dependence.
17. **Group structure** — cross-holdings, common control, group leverage.
18. **Pre-IPO transactions** — valuations, investors, warrants, anti-dilution.
19. **ESOP and dilution** — pool size, vesting, post-issue overhang.
20. **Lock-in and supply** — anchor, promoter, pre-IPO investor expiries.
21. **Market-maker quality (SME)** — inventory, spreads, track record.
22. **Registrar and lead-manager track record** — past issue performance.
23. **IPO grading** — rating-agency grade, if any.
24. **Anchor quality** — long-only vs trading, lock-in, concentration.
25. **Post-listing surveillance** — price bands, circuit limits, volumes.
26. **Corporate actions** — bonus, split, dividend, rights, buyback.
27. **Use-of-proceeds execution** — actual vs stated, monitoring agency reports.
28. **Related-party pricing** — fairness, transfer pricing, circular flows.
29. **Contingent liabilities** — guarantees, claims, tax demands.
30. **Regulatory change** — pending laws, licensing, tariffs, subsidies.
31. **Geopolitical and macro** — demand shocks, currency, inflation.
32. **Competitor actions** — capacity additions, pricing wars, new entrants.
33. **Technology disruption** — substitution, automation, AI exposure.
34. **Climate/physical risk** — floods, heat, water stress, transition risk.
35. **Business continuity** — single plant, single customer, single geography.
36. **Fraud and manipulation indicators** — circular trading, shell entities,
    sudden auditor resignation, unexplained related-party flows.
37. **Management guidance credibility** — past promises vs delivery.
38. **Working-capital financing** — receivable discounting, LC/BG dependence.
39. **Off-balance-sheet financing** — SPVs, joint ventures, guarantees.
40. **Minority-shareholder protection** — related-party approvals, veto rights,
    dividend policy, board representation.

---

## O. Implementation priorities

### P0 — Foundation for the app overview + in-depth analysis

- [ ] Add research tables: `ipo_issue`, `financial_periods`,
      `financial_facts`, `financial_ratios`, `source_citations`.
- [ ] Add `documents` and `document_chunks` scaffolding.
- [ ] Compute and persist annual/quarterly financial metrics.
- [ ] Add `GET /api/ipos/{id}/overview` and `GET /api/ipos/{id}/financials`.
- [ ] Build the app Overview and In-depth tabs.
- [ ] Add the summary PDF with deep links and QR codes.
- [ ] Add local-model provider abstraction (`LLM_ENABLED=false` fallback).

### P1 — Research-grade coverage

- [ ] RHP/DRHP ingestion, extraction and page-level citations.
- [ ] Promoter/management, litigation, related-party and governance findings.
- [ ] Peer and industry tables with source citations.
- [ ] Subscription snapshots by category and day.
- [ ] Five AI summaries with evidence, confidence and citations.
- [ ] Data-completeness and confidence scores in API, app and PDFs.
- [ ] Review queue for low-confidence/conflicting extractions.
- [ ] Post-listing tracking and score calibration.

### P2 — Scale, quality and automation

- [ ] Additional sources behind the scraper interface.
- [ ] Cross-source fuzzy matching + alias table.
- [ ] Evaluation harness with a golden set of RHP questions.
- [ ] Prompt-injection tests.
- [ ] Scheduled research runs and health alerts.
- [ ] Retention policy and audit trail.
- [ ] Backtesting of scoring weights against listing outcomes.

### Model choice (pending user installation)

The user will install the local models and confirm names. Until then, the
documented defaults are:

- Chat/reasoning/extraction: a 7B–14B instruct model, Q4 quantised
  (e.g. Qwen2.5 7B/14B, Llama 3.1 8B, Gemma 3 12B, or newer equivalents).
- Embeddings: `nomic-embed-text`, `bge-m3` or `e5`.
- Optional reranker: `bge-reranker` class.
- Runtime: Ollama (OpenAI-compatible at `http://localhost:11434/v1`),
  llama.cpp or LM Studio.

**Hard rule:** no cloud model calls. Everything stays on-device.

---

## Appendix: current gaps vs this specification

| Area | Current state | Needed |
| --- | --- | --- |
| Financial statements | Not stored | Periodised facts + ratios |
| Source citations | GMP/source provenance only | Per-fact document/page citations |
| RHP extraction | Not implemented | Ingestion + extraction + citations |
| Overview/in-depth app | No frontend | Tabs + API endpoints |
| PDF deep links | Not implemented | Base URL config + QR codes |
| Local AI | Not implemented | Provider abstraction + summaries |
| Post-listing tracking | Not implemented | Price/outcome tables + calibration |
| SME module | Checklist only | Dedicated scoring + report block |
