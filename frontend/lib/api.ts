/**
 * Small read-only client for the IPO Checker FastAPI service.
 *
 * Requests run in Server Components unless noted. Next.js does not cache
 * `fetch` by default, so pages always render the current shortlist. Callers
 * wrap the async components in `<Suspense>` so Cache Components can prerender
 * the static shell.
 */

import type {
  HealthResponse,
  IPODetail,
  IPOPage,
  ReportInfo,
} from "@/lib/types";

const configuredBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const API_BASE_URL = configuredBaseUrl.replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly path: string;

  constructor(
    message: string,
    status: number,
    path: string,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "ApiError";
    this.status = status;
    this.path = path;
  }
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit & { next?: { revalidate?: number } },
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...init?.headers,
      },
    });
  } catch (error) {
    throw new ApiError(
      `Could not reach the IPO Checker API at ${API_BASE_URL}.`,
      0,
      path,
      { cause: error },
    );
  }

  if (!response.ok) {
    throw new ApiError(
      `API request failed with status ${response.status}.`,
      response.status,
      path,
    );
  }

  return (await response.json()) as T;
}

export interface ListIposOptions {
  status?: string | null;
  minGmpPercent?: number | null;
  limit?: number;
  offset?: number;
}

export const api = {
  health(): Promise<HealthResponse> {
    return apiFetch<HealthResponse>("/api/health");
  },

  listIpos(options: ListIposOptions = {}): Promise<IPOPage> {
    const params = new URLSearchParams();
    const { status, minGmpPercent, limit = 100, offset = 0 } = options;

    if (status) params.set("status", status);
    if (minGmpPercent != null) {
      params.set("min_gmp", String(minGmpPercent));
    }
    params.set("limit", String(limit));
    params.set("offset", String(offset));

    return apiFetch<IPOPage>(`/api/ipos?${params.toString()}`);
  },

  getIpo(id: number | string): Promise<IPODetail> {
    return apiFetch<IPODetail>(`/api/ipos/${encodeURIComponent(String(id))}`);
  },

  listReports(): Promise<ReportInfo[]> {
    return apiFetch<ReportInfo[]>("/api/reports");
  },

  reportDownloadUrl(filename: string): string {
    return `${API_BASE_URL}/api/reports/${encodeURIComponent(filename)}`;
  },
};
