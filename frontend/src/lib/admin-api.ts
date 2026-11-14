import type { Session } from "@supabase/supabase-js";

const BASE = process.env.NEXT_PUBLIC_MOCK_API_URL || "http://localhost:8081";

export class AdminError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function adminFetch<T>(session: Session | null, path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(`${BASE}/admin${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...(init.headers || {}),
    },
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new AdminError(r.status, typeof body.detail === "string" ? body.detail : r.statusText);
  }
  return r.json() as Promise<T>;
}

export type Overview = {
  window_days: number;
  kpis: {
    llm_calls: number;
    tokens: number;
    reports: number;
    active_users: number;
    guard_blocks: number;
    est_cost_usd: number;
    cost_per_report_usd: number | null;
    kill_switch: boolean;
  };
  usage_by_day: { day: string; calls: number; tokens: number; avg_latency_ms: number; p95_latency_ms: number }[];
  by_model: { model: string; calls: number; tokens: number; avg_latency_ms: number }[];
  by_node: { node: string; calls: number; tokens: number }[];
  decisions: { decision: string; count: number }[];
  quality_by_day: { day: string; evidence_coverage: number | null; ml_score: number | null; reports: number }[];
  audit_events: { event: string; count: number }[];
};

export type RuntimeConfig = {
  llm_model_primary: string;
  llm_model_fast: string;
  llm_temperature: number;
  evidence_coverage_threshold: number;
  max_redrafts: number;
  require_human_approval: boolean;
  disabled_agents: string[];
  kill_switch: boolean;
  maintenance_message: string;
  cost_per_1k_tokens_usd: number;
};

export type AdminUser = {
  id: string;
  email: string | null;
  role: "admin" | "analyst";
  suspended: boolean;
  created_at: string | null;
  last_sign_in_at: string | null;
  reports: number;
};
