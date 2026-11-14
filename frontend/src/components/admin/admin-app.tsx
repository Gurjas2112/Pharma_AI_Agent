"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  Bot,
  Database,
  ExternalLink,
  Gauge,
  LoaderCircle,
  LogOut,
  MessageSquare,
  Power,
  RefreshCw,
  ScrollText,
  ShieldAlert,
  Trash2,
  Users,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useAuth } from "@/providers/Auth";
import { RepurporaMark } from "@/components/brand/logo";
import { AdminError, AdminUser, Overview, RuntimeConfig, adminFetch } from "@/lib/admin-api";

// Chart colours: categorical slots 1-2 and the reserved status palette (validated reference palette).
const SERIES_1 = "#2a78d6";
const SERIES_2 = "#eb6834";
const STATUS: Record<string, string> = { GO: "#0ca30c", PARTIAL_GO: "#fab219", NO_GO: "#d03b3b" };
const NEUTRAL = "#8a8985";
const GRID = "#e7e6e2";
const AXIS = { fontSize: 11, fill: "#52514e" };

type Tab = "overview" | "models" | "knowledge" | "users" | "audit";
const TABS: { id: Tab; label: string; icon: typeof Gauge }[] = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "models", label: "Models & safety", icon: Bot },
  { id: "knowledge", label: "Agents & knowledge", icon: BookOpen },
  { id: "users", label: "Users & roles", icon: Users },
  { id: "audit", label: "Audit log", icon: ScrollText },
];
const SUPABASE_STUDIO = `https://supabase.com/dashboard/project/${(process.env.NEXT_PUBLIC_SUPABASE_URL || "")
  .replace("https://", "")
  .split(".")[0]}`;

function fmt(n: number | null | undefined, digits = 0) {
  if (n === null || n === undefined) return "–";
  return n.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function AdminApp() {
  const { session, loading, signOut } = useAuth();
  const [tab, setTab] = useState<Tab>("overview");
  const [state, setState] = useState<"checking" | "ok" | "forbidden" | "error">("checking");

  useEffect(() => {
    if (loading) return;
    if (!session) {
      window.location.href = "/login?next=/admin";
      return;
    }
    adminFetch(session, "/me")
      .then(() => setState("ok"))
      .catch((e: AdminError) => setState(e.status === 403 ? "forbidden" : "error"));
  }, [session, loading]);

  if (state === "checking") {
    return (
      <div className="flex h-screen items-center justify-center gap-2 text-sm text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin" /> Verifying admin access…
      </div>
    );
  }
  if (state !== "ok") {
    return (
      <div className="flex h-screen items-center justify-center p-6">
        <div className="max-w-md rounded-2xl border bg-white p-8 text-center shadow-sm">
          <ShieldAlert className="mx-auto size-10 text-[#d03b3b]" />
          <h1 className="mt-4 text-xl font-semibold">
            {state === "forbidden" ? "Admin access required" : "Admin service unavailable"}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {state === "forbidden"
              ? "Your account is signed in but does not have the admin role. Ask an administrator to grant it (scripts/make_admin.py), then sign in again."
              : "The admin API could not be reached. Please try again shortly."}
          </p>
          <Link href="/chat" className="mt-6 inline-flex items-center gap-2 text-sm text-teal-700 hover:underline">
            <MessageSquare className="size-4" /> Back to research chat
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f6f6f4]">
      <header className="sticky top-0 z-20 border-b bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3">
          <div className="flex items-center gap-3">
            <RepurporaMark size={28} />
            <span className="text-lg font-semibold">repurpora</span>
            <span className="rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-xs text-violet-700">
              Admin
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <a href={SUPABASE_STUDIO} target="_blank" rel="noreferrer" className="hidden md:inline-flex items-center gap-1 text-muted-foreground hover:text-foreground">
              <Database className="size-4" /> Supabase Studio <ExternalLink className="size-3" />
            </a>
            <a href="https://smith.langchain.com" target="_blank" rel="noreferrer" className="hidden md:inline-flex items-center gap-1 text-muted-foreground hover:text-foreground">
              <Activity className="size-4" /> LangSmith traces <ExternalLink className="size-3" />
            </a>
            <Link href="/chat" className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground">
              <MessageSquare className="size-4" /> Chat
            </Link>
            <button onClick={signOut} aria-label="Sign out" className="text-muted-foreground hover:text-foreground">
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
        <nav className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-5" aria-label="Admin sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              data-testid={`tab-${t.id}`}
              aria-current={tab === t.id ? "page" : undefined}
              className={`inline-flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm ${
                tab === t.id ? "border-teal-600 font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <t.icon className="size-4" /> {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-7xl px-5 py-6">
        {tab === "overview" && <OverviewTab />}
        {tab === "models" && <ModelsTab />}
        {tab === "knowledge" && <KnowledgeTab />}
        {tab === "users" && <UsersTab />}
        {tab === "audit" && <AuditTab />}
      </main>
    </div>
  );
}

function useAdmin<T>(path: string) {
  const { session } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => {
    setErr(null);
    adminFetch<T>(session, path)
      .then(setData)
      .catch((e: Error) => setErr(e.message));
  }, [session, path]);
  useEffect(load, [load]);
  return { data, err, reload: load, session };
}

function Card({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="rounded-2xl border bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Stat({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "alert" }) {
  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${tone === "alert" ? "text-[#d03b3b]" : ""}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

function Loading({ err }: { err: string | null }) {
  return err ? (
    <p className="text-sm text-[#d03b3b]">Failed to load: {err}</p>
  ) : (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <LoaderCircle className="size-4 animate-spin" /> Loading…
    </p>
  );
}

// ------------------------------------------------------------------ overview --

function OverviewTab() {
  const [days, setDays] = useState(14);
  const { data, err, reload } = useAdmin<Overview>(`/overview?days=${days}`);
  if (!data) return <Loading err={err} />;
  const k = data.kpis;
  const decisions = data.decisions.map((d) => ({ ...d, fill: STATUS[d.decision] || NEUTRAL }));
  return (
    <div className="space-y-5" data-testid="admin-overview">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground">Window</span>
        {[7, 14, 30, 90].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`rounded-full border px-3 py-1 text-xs ${days === d ? "border-teal-600 bg-teal-50 text-teal-800" : "bg-white"}`}
          >
            {d} days
          </button>
        ))}
        <button onClick={reload} className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          <RefreshCw className="size-3.5" /> Refresh
        </button>
      </div>
      {k.kill_switch && (
        <div role="alert" className="flex items-center gap-2 rounded-xl border border-[#d03b3b]/40 bg-[#d03b3b]/5 p-3 text-sm">
          <Power className="size-4 text-[#d03b3b]" /> <b>Kill switch is ON</b>: all research requests are being refused.
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Stat label="Reports archived" value={fmt(k.reports)} />
        <Stat label="Active users" value={fmt(k.active_users)} />
        <Stat label="LLM calls" value={fmt(k.llm_calls)} />
        <Stat label="Tokens" value={fmt(k.tokens)} />
        <Stat label="Est. cost" value={`$${fmt(k.est_cost_usd, 2)}`} hint={k.cost_per_report_usd !== null ? `$${fmt(k.cost_per_report_usd, 3)} per report` : undefined} />
        <Stat label="Guardrail blocks" value={fmt(k.guard_blocks)} tone={k.guard_blocks > 0 ? "alert" : undefined} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Tokens per day">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.usage_by_day} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="day" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} width={56} />
              <Tooltip formatter={(v: number) => [fmt(v), "tokens"]} cursor={{ fill: "#00000008" }} />
              <Bar dataKey="tokens" fill={SERIES_1} radius={[4, 4, 0, 0]} maxBarSize={28} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="LLM latency (ms)">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data.usage_by_day} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="day" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} width={56} />
              <Tooltip formatter={(v: number, n: string) => [`${fmt(v)} ms`, n]} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="avg_latency_ms" name="average" stroke={SERIES_1} strokeWidth={2} dot={{ r: 4 }} />
              <Line type="monotone" dataKey="p95_latency_ms" name="p95" stroke={SERIES_2} strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Decisions in window">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={decisions} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 0 }}>
              <XAxis type="number" tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
              <YAxis type="category" dataKey="decision" tick={AXIS} tickLine={false} axisLine={false} width={90} />
              <Tooltip formatter={(v: number) => [fmt(v), "reports"]} cursor={{ fill: "#00000008" }} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={22} label={{ position: "right", fontSize: 11, fill: "#52514e" }}>
                {decisions.map((d) => (
                  <Cell key={d.decision} fill={d.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Answer quality: average evidence coverage per day">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data.quality_by_day} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="day" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
              <YAxis domain={[0, 1]} tick={AXIS} tickLine={false} axisLine={false} width={40} />
              <Tooltip formatter={(v: number) => [`${Math.round(v * 100)}%`, "evidence coverage"]} />
              <Line type="monotone" dataKey="evidence_coverage" stroke={SERIES_1} strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Usage by model">
          <SimpleTable
            cols={["model", "calls", "tokens", "avg latency"]}
            rows={data.by_model.map((m) => [m.model, fmt(m.calls), fmt(m.tokens), `${fmt(m.avg_latency_ms)} ms`])}
          />
        </Card>
        <Card title="Usage by graph node">
          <SimpleTable cols={["node", "calls", "tokens"]} rows={data.by_node.map((n) => [n.node, fmt(n.calls), fmt(n.tokens)])} />
        </Card>
      </div>
    </div>
  );
}

function SimpleTable({ cols, rows }: { cols: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            {cols.map((c) => (
              <th key={c} className="py-2 pr-4 font-medium">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={cols.length} className="py-4 text-muted-foreground">No data in this window.</td>
            </tr>
          )}
          {rows.map((r, i) => (
            <tr key={i} className="border-b last:border-0">
              {r.map((v, j) => (
                <td key={j} className="py-2 pr-4 tabular-nums">{v}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------ models & safety --

function ModelsTab() {
  const { data, err, reload, session } = useAdmin<{ config: RuntimeConfig; agents: string[]; provider: string }>("/config");
  const history = useAdmin<{ key: string; old: unknown; new: unknown; version: number; by: string; reason: string; at: string }[]>(
    "/config/history?limit=20",
  );
  const [draft, setDraft] = useState<RuntimeConfig | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (data) setDraft(data.config);
  }, [data]);
  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(data?.config), [draft, data]);
  if (!data || !draft) return <Loading err={err} />;
  const set = <K extends keyof RuntimeConfig>(k: K, v: RuntimeConfig[K]) => setDraft({ ...draft, [k]: v });

  const save = async () => {
    const changes = Object.fromEntries(
      Object.entries(draft).filter(([k, v]) => JSON.stringify(v) !== JSON.stringify(data.config[k as keyof RuntimeConfig])),
    );
    setSaving(true);
    try {
      await adminFetch(session, "/config", { method: "PUT", body: JSON.stringify({ changes, reason }) });
      toast.success("Configuration saved", { description: "Applies to new requests within ~15 seconds." });
      setReason("");
      reload();
      history.reload();
    } catch (e) {
      toast.error("Rejected", { description: (e as Error).message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid gap-5 lg:grid-cols-3" data-testid="admin-models">
      <div className="space-y-5 lg:col-span-2">
        <Card title="Kill switch">
          <label className="flex items-start gap-3">
            <input type="checkbox" className="mt-1 size-4 accent-[#d03b3b]" checked={draft.kill_switch} onChange={(e) => set("kill_switch", e.target.checked)} />
            <span className="text-sm">
              <b>Pause all research requests.</b> Users see the maintenance message below; nothing reaches the LLM or the data tools.
            </span>
          </label>
          <input
            className="mt-3 w-full rounded-lg border px-3 py-2 text-sm"
            value={draft.maintenance_message}
            onChange={(e) => set("maintenance_message", e.target.value)}
            aria-label="Maintenance message"
          />
        </Card>
        <Card title={`Models (provider: ${data.provider})`}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Primary model (planner, writer, SQL agent)">
              <input className="w-full rounded-lg border px-3 py-2 text-sm" value={draft.llm_model_primary} onChange={(e) => set("llm_model_primary", e.target.value)} />
            </Field>
            <Field label="Fast model (agent notes, judge)">
              <input className="w-full rounded-lg border px-3 py-2 text-sm" value={draft.llm_model_fast} onChange={(e) => set("llm_model_fast", e.target.value)} />
            </Field>
            <Field label={`Temperature: ${draft.llm_temperature.toFixed(2)}`}>
              <input type="range" min={0} max={1.5} step={0.05} className="w-full" value={draft.llm_temperature} onChange={(e) => set("llm_temperature", Number(e.target.value))} />
            </Field>
            <Field label="Cost estimate (USD per 1k tokens)">
              <input type="number" step="0.0001" min={0} className="w-full rounded-lg border px-3 py-2 text-sm" value={draft.cost_per_1k_tokens_usd} onChange={(e) => set("cost_per_1k_tokens_usd", Number(e.target.value))} />
            </Field>
          </div>
        </Card>
        <Card title="Quality gates & human oversight">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={`Evidence-coverage gate: ${Math.round(draft.evidence_coverage_threshold * 100)}%`}>
              <input type="range" min={0.5} max={1} step={0.05} className="w-full" value={draft.evidence_coverage_threshold} onChange={(e) => set("evidence_coverage_threshold", Number(e.target.value))} />
            </Field>
            <Field label="Max redrafts">
              <select className="w-full rounded-lg border px-3 py-2 text-sm" value={draft.max_redrafts} onChange={(e) => set("max_redrafts", Number(e.target.value))}>
                {[0, 1, 2, 3].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </Field>
          </div>
          <label className="mt-4 flex items-start gap-3 text-sm">
            <input type="checkbox" className="mt-1 size-4" checked={draft.require_human_approval} onChange={(e) => set("require_human_approval", e.target.checked)} />
            <span>Require human approval before archiving a <b>GO</b> recommendation (LangGraph interrupt).</span>
          </label>
        </Card>
        <Card title="Agents enabled">
          <div className="flex flex-wrap gap-2">
            {data.agents.map((a) => {
              const on = !draft.disabled_agents.includes(a);
              return (
                <button
                  key={a}
                  onClick={() => set("disabled_agents", on ? [...draft.disabled_agents, a] : draft.disabled_agents.filter((x) => x !== a))}
                  aria-pressed={on}
                  className={`rounded-full border px-3 py-1.5 text-sm ${on ? "border-teal-600 bg-teal-50 text-teal-800" : "bg-white text-muted-foreground line-through"}`}
                >
                  {a.replace("_", " ")}
                </button>
              );
            })}
          </div>
        </Card>
        <div className="flex flex-wrap items-center gap-3 rounded-2xl border bg-white p-4 shadow-sm">
          <input
            className="min-w-60 flex-1 rounded-lg border px-3 py-2 text-sm"
            placeholder="Reason for change (required, kept in the change log)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            aria-label="Reason for change"
          />
          <button onClick={() => setDraft(data.config)} disabled={!dirty} className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50">
            Discard
          </button>
          <button
            onClick={save}
            disabled={!dirty || reason.trim().length < 3 || saving}
            className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
      <Card title="Change history">
        {!history.data ? (
          <Loading err={history.err} />
        ) : history.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No changes yet. Defaults come from the deployment environment.</p>
        ) : (
          <ol className="space-y-3 text-sm">
            {history.data.map((h, i) => (
              <li key={i} className="border-l-2 border-teal-600/40 pl-3">
                <div className="font-medium">
                  {h.key} <span className="text-xs text-muted-foreground">v{h.version}</span>
                </div>
                <div className="text-xs text-muted-foreground">
                  {JSON.stringify(h.old)} → <b className="text-foreground">{JSON.stringify(h.new)}</b>
                </div>
                <div className="text-xs text-muted-foreground">
                  {h.by} · {new Date(h.at).toLocaleString()} · “{h.reason}”
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

// --------------------------------------------------------- agents & knowledge --

type RagDocs = {
  index: { type: string; dim: number; chunks: number; documents: number };
  documents: { id: number; source: string; scope: string; owner: string | null; created_at: string; chunks: number; chars: number }[];
};

function KnowledgeTab() {
  const agents = useAdmin<{ agent: string; tools: string[]; enabled: boolean }[]>("/agents");
  const docs = useAdmin<RagDocs>("/rag/documents");
  const remove = async (id: number, source: string) => {
    if (!window.confirm(`Delete "${source}" and all its chunks from the knowledge index? This cannot be undone.`)) return;
    try {
      await adminFetch(docs.session, `/rag/documents/${id}`, { method: "DELETE" });
      toast.success(`Removed ${source}`);
      docs.reload();
    } catch (e) {
      toast.error("Delete failed", { description: (e as Error).message });
    }
  };
  return (
    <div className="space-y-5" data-testid="admin-knowledge">
      <Card title="Agent tool permissions (policy gateway allow-list)">
        {!agents.data ? (
          <Loading err={agents.err} />
        ) : (
          <SimpleTable
            cols={["agent", "allowed tools", "status"]}
            rows={agents.data.map((a) => [
              a.agent.replace("_", " "),
              a.tools.join(", "),
              a.enabled ? "● enabled" : "○ disabled",
            ])}
          />
        )}
        <p className="mt-2 text-xs text-muted-foreground">Each agent may call only its listed tools (max 4 calls per run). Enable or disable agents in Models & safety.</p>
      </Card>
      <Card title="Knowledge index (RAG)" action={<button onClick={docs.reload} className="text-xs text-muted-foreground hover:text-foreground"><RefreshCw className="size-3.5" /></button>}>
        {!docs.data ? (
          <Loading err={docs.err} />
        ) : (
          <>
            <div className="mb-3 grid grid-cols-3 gap-3">
              <Stat label="Documents" value={fmt(docs.data.index.documents)} />
              <Stat label="Chunks" value={fmt(docs.data.index.chunks)} />
              <Stat label="Embedding dim" value={String(docs.data.index.dim)} hint={docs.data.index.type} />
            </div>
            <SimpleTable
              cols={["document", "scope", "chunks", "added", ""]}
              rows={docs.data.documents.map((d) => [
                d.source,
                d.scope,
                fmt(d.chunks),
                new Date(d.created_at).toLocaleDateString(),
                <button key={d.id} onClick={() => remove(d.id, d.source)} aria-label={`Delete ${d.source}`} className="text-muted-foreground hover:text-[#d03b3b]">
                  <Trash2 className="size-4" />
                </button>,
              ])}
            />
          </>
        )}
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------- users --

function UsersTab() {
  const { data, err, reload, session } = useAdmin<AdminUser[]>("/users");
  const [busy, setBusy] = useState<string | null>(null);
  const act = async (u: AdminUser, kind: "role" | "suspend") => {
    const label = kind === "role" ? (u.role === "admin" ? "remove admin from" : "make admin") : u.suspended ? "reactivate" : "suspend";
    if (!window.confirm(`Really ${label} ${u.email}?`)) return;
    setBusy(u.id);
    try {
      if (kind === "role")
        await adminFetch(session, `/users/${u.id}/role`, { method: "POST", body: JSON.stringify({ role: u.role === "admin" ? "analyst" : "admin" }) });
      else await adminFetch(session, `/users/${u.id}/suspend`, { method: "POST", body: JSON.stringify({ suspend: !u.suspended }) });
      toast.success("Updated", { description: "Role changes take effect at the user's next sign-in." });
      reload();
    } catch (e) {
      toast.error("Action rejected", { description: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };
  if (!data) return <Loading err={err} />;
  return (
    <Card title={`Users (${data.length})`}>
      <div data-testid="admin-users">
        <SimpleTable
          cols={["email", "role", "status", "reports", "last sign-in", "actions"]}
          rows={data.map((u) => [
            u.email,
            u.role,
            u.suspended ? (
              <span key="s" className="inline-flex items-center gap-1 text-[#d03b3b]"><AlertTriangle className="size-3.5" /> suspended</span>
            ) : (
              "active"
            ),
            fmt(u.reports),
            u.last_sign_in_at ? new Date(u.last_sign_in_at).toLocaleString() : "–",
            <div key="a" className="flex gap-2">
              <button disabled={busy === u.id} onClick={() => act(u, "role")} className="rounded-md border px-2 py-1 text-xs disabled:opacity-50">
                {u.role === "admin" ? "Revoke admin" : "Make admin"}
              </button>
              <button disabled={busy === u.id} onClick={() => act(u, "suspend")} className="rounded-md border px-2 py-1 text-xs disabled:opacity-50">
                {u.suspended ? "Reactivate" : "Suspend"}
              </button>
            </div>,
          ])}
        />
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------- audit --

const AUDIT_EVENTS = ["", "guard_input", "plan", "tool_call", "judge", "archive", "sql_agent", "mcp_tool_call", "memory_write",
  "memory_forget", "dlp_redaction", "kill_switch_refusal", "admin_config_update", "admin_role_change", "admin_suspend", "admin_rag_delete"];

function AuditTab() {
  const [event, setEvent] = useState("");
  const { data, err } = useAdmin<{ ts: string; event: string; owner: string | null; thread_id: string | null; detail: unknown }[]>(
    `/audit?limit=200${event ? `&event=${event}` : ""}`,
  );
  return (
    <Card
      title="Append-only audit log"
      action={
        <select value={event} onChange={(e) => setEvent(e.target.value)} className="rounded-lg border px-2 py-1 text-xs" aria-label="Filter by event">
          {AUDIT_EVENTS.map((e) => (
            <option key={e} value={e}>{e || "all events"}</option>
          ))}
        </select>
      }
    >
      {!data ? (
        <Loading err={err} />
      ) : (
        <div data-testid="admin-audit">
          <SimpleTable
            cols={["time", "event", "user", "detail"]}
            rows={data.map((a) => [
              new Date(a.ts).toLocaleString(),
              a.event,
              a.owner ? `${a.owner.slice(0, 8)}…` : "–",
              <code key="d" className="block max-w-xl truncate text-xs text-muted-foreground" title={JSON.stringify(a.detail)}>
                {JSON.stringify(a.detail)}
              </code>,
            ])}
          />
        </div>
      )}
    </Card>
  );
}
