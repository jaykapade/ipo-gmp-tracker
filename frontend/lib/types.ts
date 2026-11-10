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

export interface HealthResponse {
  status: string;
  database: string;
  generated_at: string;
}
