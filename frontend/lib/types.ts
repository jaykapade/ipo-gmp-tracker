/**
 * Types mirroring the FastAPI schemas in `backend/src/api/schemas.py`.
 *
 * Keep these in sync with the backend until shared TypeScript types are
 * generated from the OpenAPI schema (see the roadmap).
 */

export type Verdict = "Strong" | "Watch" | "Avoid";
export type ChecklistStatus = "pass" | "warn" | "fail" | "manual";

export interface IPOSummary {
  id: number;
  name: string;
  category: string | null;
  status: string | null;
  sector: string | null;
  exchange: string | null;
  issue_price: number | null;
  issue_price_lower: number | null;
  issue_price_upper: number | null;
  estimated_listing_price: number | null;
  ipo_size_cr: string | null;
  lot_size: string | null;
  subscription: number | null;
  pe: number | null;
  gmp: number | null;
  gmp_percent: number | null;
  gmp_percent_derived: boolean;
  latest_gmp_source: string | null;
  latest_gmp_recorded_at: string | null;
  open_date: string | null;
  close_date: string | null;
  listing_date: string | null;
  source_url: string | null;
  research_status: ResearchStatus | null;
  research_verdict: Verdict | null;
}

export interface IPOPage {
  items: IPOSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface GMPPoint {
  source: string;
  gmp: number | null;
  gmp_percent: number | null;
  recorded_at: string;
}

export interface IPOSource {
  source: string;
  source_ipo_id: string | null;
  source_url: string | null;
  first_seen_at: string;
  last_seen_at: string;
}

export interface ScoreFactor {
  key: string;
  label: string;
  weight: number;
  score: number;
  weighted_score: number;
  explanation: string;
  data_available: boolean;
}

export interface ChecklistItem {
  key: string;
  label: string;
  status: ChecklistStatus;
  detail: string;
}

export interface IPOAnalysis {
  ipo_id: number;
  name: string;
  score: number;
  verdict: Verdict;
  gmp: number | null;
  gmp_percent: number | null;
  gmp_percent_derived: boolean;
  issue_price: number | null;
  issue_size_cr: number | null;
  subscription: number | null;
  pe: number | null;
  close_date: string | null;
  factors: ScoreFactor[];
  checklist: ChecklistItem[];
  strengths: string[];
  risks: string[];
  data_gaps: string[];
  generated_at: string;
}

export interface IPODetail extends IPOSummary {
  rhp_url: string | null;
  gmp_history: GMPPoint[];
  sources: IPOSource[];
  latest_analysis: IPOAnalysis | null;
}

export interface ReportInfo {
  filename: string;
  size_bytes: number;
  modified_at: string;
  download_url: string;
}

export interface AIRoleHealth {
  enabled: boolean;
  provider: string;
  model: string;
  available: boolean;
  detail: string;
}

export interface AIHealth extends AIRoleHealth {
  embed_provider: string;
  embed_model: string;
  rerank_provider: string;
  roles: Record<string, AIRoleHealth>;
}

export interface HealthResponse {
  status: string;
  database: string;
  generated_at: string;
  ai: AIHealth;
}

// --- Dashboard facets --------------------------------------------------------

export interface FacetValue {
  value: string | null;
  count: number;
}

export interface IPOFacets {
  total: number;
  statuses: FacetValue[];
  categories: FacetValue[];
  sectors: FacetValue[];
  researched: number;
  screen_floor: number;
}

// --- AI research (mirrors backend/src/research/schemas.py) -------------------

export type ResearchStatus = "queued" | "running" | "done" | "failed";
export type ConfidenceLevel = "high" | "medium" | "low";
export type SourceType = "official" | "exchange" | "secondary" | "database";
export type PerspectiveKey = "h1" | "h2" | "h3" | "h4";

export interface Fact {
  id: string;
  category: string;
  claim: string;
  value: string | null;
  period: string | null;
  source_url: string | null;
  source_title: string | null;
  source_type: SourceType;
  as_of: string | null;
}

export interface FactPack {
  ipo_id: number;
  ipo_name: string;
  facts: Fact[];
  gaps: string[];
  rhp_url: string | null;
  gathered_at: string;
}

export interface Confidence {
  level: ConfidenceLevel;
  reason: string;
}

export interface PerspectiveRecord {
  key: PerspectiveKey;
  title: string;
  evidence: { point: string; fact_ids: string[] }[];
  conclusion: string;
  confidence: Confidence;
  missing_information: string[];
  dropped_evidence: string[];
  error: string | null;
}

export interface Dispute {
  finding_id: string;
  perspective: PerspectiveKey;
  finding: string;
  stance: "disagree" | "unsupported";
  verifier_reason: string;
  ruling: "uphold_finding" | "uphold_verifier" | "unresolved";
  ruling_reason: string | null;
}

export interface Assessment {
  verdict: Verdict;
  conclusion: string;
  strengths: string[];
  risks: string[];
  what_would_change: string[];
  confidence: Confidence;
  notes?: string[];
}

export interface ResearchOutput {
  id: number;
  kind: string;
  provider: string | null;
  model: string | null;
  prompt_version: string;
  confidence: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  data_left_machine: boolean;
  created_at: string;
  output: Record<string, unknown>;
  citations: unknown[] | null;
}

export interface ResearchRun {
  id: number;
  ipo_id: number;
  status: ResearchStatus;
  stage: string | null;
  error: string | null;
  prompt_version: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  stages: string[];
}

export interface ResearchDetail extends ResearchRun {
  outputs: ResearchOutput[];
  latest_completed: ResearchDetail | null;
}

/** One chat message rendered in the conversation list. */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  dataAsOf?: string | null;
  citations?: ChatCitation[];
  refusal?: boolean;
}

/** A citation attached to an assistant message. */
export interface ChatCitation {
  type: string;
  label?: string;
  ipo_id?: number;
  name?: string;
}

/** Result of submitting one chat message. */
export interface ChatResult {
  conversationId: string;
  dataAsOf: string | null;
  citations: ChatCitation[];
  refusal: boolean;
}

/** One Server-Sent Event received from the streaming chat endpoint. */
export interface ChatEvent {
  type: string;
  data: unknown;
}
