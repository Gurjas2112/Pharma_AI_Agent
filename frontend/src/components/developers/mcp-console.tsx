"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Copy, KeyRound, LoaderCircle, LogOut, MessageSquare, Play, Plug, ShieldX } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/providers/Auth";
import { RepurporaMark } from "@/components/brand/logo";

const AUX = process.env.NEXT_PUBLIC_MOCK_API_URL || "http://localhost:8081";
const MCP_URL = `${AUX}/mcp`;

type Json = Record<string, unknown>;
type Tool = {
  name: string;
  title?: string;
  description?: string;
  annotations?: { readOnlyHint?: boolean };
  inputSchema?: { properties?: Record<string, { type?: string; anyOf?: { type?: string }[]; default?: unknown }>; required?: string[] };
};
type WireEntry = { dir: "→" | "←"; label: string; body: unknown; status?: number; ms?: number };

const EXAMPLES: Record<string, Json> = {
  molecule_profile: { molecule: "montelukast" },
  market_insights: { therapy_area: "Respiratory", region: "India" },
  trade_flows: { molecule: "metformin", country: "India" },
  patent_landscape: { molecule: "colchicine" },
  clinical_trials: { molecule: "budesonide" },
  web_intelligence: { query: "montelukast post-viral cough evidence" },
  internal_knowledge: { query: "pharmaceutical product selection criteria" },
  opportunity_score: { fto_risk: 2, unmet_need: 0.8, evidence_strength: 0.7, region: "India", innovation_type: "new_dosage_form" },
  my_reports: { question: "how many reports per decision" },
};

/** Redact anything token-like before it is rendered (the bearer token is never shown). */
function redact(v: unknown): unknown {
  return JSON.parse(JSON.stringify(v ?? null).replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+/g, "eyJ…[redacted]"));
}

function typeOf(p: { type?: string; anyOf?: { type?: string }[] }) {
  return p.type || p.anyOf?.map((a) => a.type).filter((t) => t && t !== "null").join(" | ") || "any";
}

export function McpConsole() {
  const { session, signOut } = useAuth();
  const [wire, setWire] = useState<WireEntry[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [server, setServer] = useState<Json | null>(null);
  const [prm, setPrm] = useState<Json | null>(null);
  const [protocol, setProtocol] = useState<string | null>(null);
  const [tools, setTools] = useState<Tool[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [args, setArgs] = useState("{}");
  const [result, setResult] = useState<{ text: string; ms: number; isError?: boolean } | null>(null);
  const [unauth, setUnauth] = useState<{ status: number; challenge: string | null } | null>(null);
  const nextId = useMemo(() => ({ v: 1 }), []);

  const log = (e: WireEntry) => setWire((w) => [...w, e].slice(-14));

  async function rpc(method: string, params?: Json, notify = false, auth = true) {
    const body: Json = { jsonrpc: "2.0", method, ...(params ? { params } : {}), ...(notify ? {} : { id: nextId.v++ }) };
    log({ dir: "→", label: method, body });
    const t0 = performance.now();
    const r = await fetch(MCP_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
        ...(protocol ? { "MCP-Protocol-Version": protocol } : {}),
        ...(auth && session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
      },
      body: JSON.stringify(body),
    });
    const ms = Math.round(performance.now() - t0);
    const text = await r.text();
    const parsed = text ? (() => { try { return JSON.parse(text); } catch { return text; } })() : null;
    log({ dir: "←", label: `${method} · HTTP ${r.status}`, body: parsed, status: r.status, ms });
    return { r, parsed, ms };
  }

  async function tryWithoutToken() {
    setBusy("unauth");
    try {
      const { r } = await rpc("tools/list", undefined, false, false);
      setUnauth({ status: r.status, challenge: r.headers.get("www-authenticate") });
    } finally {
      setBusy(null);
    }
  }

  async function connect() {
    setBusy("connect");
    try {
      const meta = await fetch(`${AUX}/.well-known/oauth-protected-resource/mcp`).then((x) => x.json());
      setPrm(meta);
      log({ dir: "←", label: "GET /.well-known/oauth-protected-resource/mcp", body: meta, status: 200 });
      const init = await rpc("initialize", {
        protocolVersion: "2025-06-18",
        capabilities: {},
        clientInfo: { name: "repurpora-web-console", version: "1.0.0" },
      });
      if (init.r.status !== 200) throw new Error(`initialize failed: HTTP ${init.r.status}`);
      const res = (init.parsed as { result: Json }).result;
      setServer(res);
      setProtocol(res.protocolVersion as string);
      await rpc("notifications/initialized", undefined, true);
      const list = await rpc("tools/list");
      const ts = ((list.parsed as { result: { tools: Tool[] } }).result.tools || []) as Tool[];
      setTools(ts);
      if (ts[0]) pick(ts[0].name);
      toast.success(`Connected · ${ts.length} tools`);
    } catch (e) {
      toast.error("Connection failed", { description: (e as Error).message });
    } finally {
      setBusy(null);
    }
  }

  function pick(name: string) {
    setSelected(name);
    setArgs(JSON.stringify(EXAMPLES[name] || {}, null, 2));
    setResult(null);
  }

  async function run() {
    if (!selected) return;
    let parsedArgs: Json;
    try {
      parsedArgs = JSON.parse(args);
    } catch {
      toast.error("Arguments must be valid JSON");
      return;
    }
    setBusy("call");
    try {
      const { parsed, ms } = await rpc("tools/call", { name: selected, arguments: parsedArgs });
      const res = (parsed as { result?: { content?: { text?: string }[]; isError?: boolean }; error?: Json }).result;
      const raw = res?.content?.[0]?.text ?? JSON.stringify(parsed);
      let pretty = raw;
      try { pretty = JSON.stringify(JSON.parse(raw), null, 2); } catch { /* plain text */ }
      setResult({ text: pretty, ms, isError: res?.isError });
    } finally {
      setBusy(null);
    }
  }

  const tool = tools.find((t) => t.name === selected);
  const connected = tools.length > 0;

  return (
    <div className="min-h-screen bg-[#0b1226] text-slate-100">
      <header className="border-b border-white/10">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3">
          <div className="flex items-center gap-3">
            <RepurporaMark size={28} />
            <span className="text-lg font-semibold">repurpora</span>
            <span className="rounded-full border border-teal-400/30 bg-teal-400/10 px-2 py-0.5 text-xs text-teal-200">Developers · MCP</span>
          </div>
          <div className="flex items-center gap-4 text-sm text-slate-400">
            <Link href="/chat" className="inline-flex items-center gap-1 hover:text-white"><MessageSquare className="size-4" /> Chat</Link>
            <button onClick={signOut} aria-label="Sign out" className="hover:text-white"><LogOut className="size-4" /></button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 px-5 py-6">
        <section className="grid gap-5 lg:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 lg:col-span-2">
            <h1 className="text-xl font-semibold">Repurpora MCP server</h1>
            <p className="mt-1 text-sm text-slate-400">
              Connect Claude Desktop, Cursor or your own agent to the same research tools Repurpora&apos;s agents use. Streamable HTTP,
              OAuth 2.1 resource server (Supabase sign-in), every tool read-only and audited.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <code className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-teal-200" data-testid="mcp-endpoint">{MCP_URL}</code>
              <button onClick={() => { navigator.clipboard?.writeText(MCP_URL); toast.success("Endpoint copied"); }} aria-label="Copy endpoint"
                className="rounded-lg border border-white/10 p-2 text-slate-300 hover:bg-white/10"><Copy className="size-4" /></button>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button onClick={tryWithoutToken} disabled={!!busy} data-testid="mcp-unauth"
                className="inline-flex items-center gap-2 rounded-lg border border-white/15 px-3 py-2 text-sm hover:bg-white/10 disabled:opacity-50">
                {busy === "unauth" ? <LoaderCircle className="size-4 animate-spin" /> : <ShieldX className="size-4 text-rose-300" />} Call without a token
              </button>
              <button onClick={connect} disabled={!!busy} data-testid="mcp-connect"
                className="inline-flex items-center gap-2 rounded-lg bg-teal-500 px-4 py-2 text-sm font-medium text-[#0b1226] hover:bg-teal-400 disabled:opacity-50">
                {busy === "connect" ? <LoaderCircle className="size-4 animate-spin" /> : <Plug className="size-4" />} Connect with my session
              </button>
            </div>
            {unauth && (
              <div className="mt-3 rounded-lg border border-rose-400/30 bg-rose-400/10 p-3 text-xs" data-testid="mcp-unauth-result">
                <b className="text-rose-200">HTTP {unauth.status}</b> <span className="text-slate-300">WWW-Authenticate: {unauth.challenge || "(not exposed)"}</span>
              </div>
            )}
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 text-sm">
            <h2 className="mb-2 font-semibold">Session</h2>
            <dl className="space-y-1.5 text-slate-300">
              <div className="flex justify-between gap-2"><dt className="text-slate-500">Signed in as</dt><dd className="truncate">{session?.user?.email}</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-slate-500">Auth</dt><dd className="inline-flex items-center gap-1"><KeyRound className="size-3.5" /> Bearer (hidden)</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-slate-500">Server</dt><dd>{server ? `${(server.serverInfo as Json).name} v${(server.serverInfo as Json).version}` : "–"}</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-slate-500">Protocol</dt><dd>{protocol || "–"}</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-slate-500">Issuer</dt><dd className="truncate">{(prm?.authorization_servers as string[] | undefined)?.[0]?.replace("https://", "") || "–"}</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-slate-500">Scope</dt><dd>{(prm?.scopes_supported as string[] | undefined)?.join(", ") || "–"}</dd></div>
            </dl>
            {connected && <p className="mt-3 inline-flex items-center gap-1 text-xs text-teal-300"><CheckCircle2 className="size-4" /> Connected</p>}
          </div>
        </section>

        {connected && (
          <section className="grid gap-5 lg:grid-cols-5" data-testid="mcp-tools">
            <div className="space-y-2 lg:col-span-2">
              <h2 className="text-sm font-semibold text-slate-300">tools/list · {tools.length} tools</h2>
              {tools.map((t) => (
                <button key={t.name} onClick={() => pick(t.name)} data-testid={`tool-${t.name}`}
                  className={`w-full rounded-xl border p-3 text-left transition ${selected === t.name ? "border-teal-400/60 bg-teal-400/10" : "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"}`}>
                  <div className="flex items-center justify-between gap-2">
                    <code className="text-sm text-teal-200">{t.name}</code>
                    {t.annotations?.readOnlyHint && <span className="rounded-full border border-white/15 px-2 py-0.5 text-[10px] text-slate-300">read-only</span>}
                  </div>
                  <div className="mt-0.5 text-xs text-slate-400">{t.title}</div>
                </button>
              ))}
            </div>
            <div className="space-y-4 lg:col-span-3">
              {tool && (
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
                  <h2 className="font-semibold"><code className="text-teal-200">{tool.name}</code> <span className="text-sm font-normal text-slate-400">· {tool.title}</span></h2>
                  <p className="mt-1 text-sm text-slate-400">{tool.description}</p>
                  <table className="mt-3 w-full text-xs">
                    <thead><tr className="text-left text-slate-500"><th className="py-1">parameter</th><th>type</th><th>required</th></tr></thead>
                    <tbody>
                      {Object.entries(tool.inputSchema?.properties || {}).map(([k, p]) => (
                        <tr key={k} className="border-t border-white/5"><td className="py-1 font-mono text-slate-200">{k}</td><td className="text-slate-400">{typeOf(p)}</td>
                          <td className="text-slate-400">{tool.inputSchema?.required?.includes(k) ? "yes" : "no"}</td></tr>
                      ))}
                    </tbody>
                  </table>
                  <label className="mt-3 block text-xs text-slate-500" htmlFor="mcp-args">arguments (JSON)</label>
                  <textarea id="mcp-args" value={args} onChange={(e) => setArgs(e.target.value)} rows={5}
                    className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 p-3 font-mono text-xs text-slate-100" />
                  <button onClick={run} disabled={!!busy} data-testid="mcp-run"
                    className="mt-3 inline-flex items-center gap-2 rounded-lg bg-teal-500 px-4 py-2 text-sm font-medium text-[#0b1226] hover:bg-teal-400 disabled:opacity-50">
                    {busy === "call" ? <LoaderCircle className="size-4 animate-spin" /> : <Play className="size-4" />} tools/call
                  </button>
                </div>
              )}
              {result && (
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5" data-testid="mcp-result">
                  <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
                    <span>result {result.isError ? "· error" : ""}</span><span>{result.ms} ms</span>
                  </div>
                  <pre className="max-h-80 overflow-auto rounded-lg bg-black/40 p-3 text-xs text-slate-200">{result.text.slice(0, 6000)}</pre>
                </div>
              )}
            </div>
          </section>
        )}

        <section className="rounded-2xl border border-white/10 bg-black/30 p-5" data-testid="mcp-wire">
          <h2 className="mb-2 text-sm font-semibold text-slate-300">JSON-RPC wire log <span className="font-normal text-slate-500">(tokens redacted)</span></h2>
          {wire.length === 0 && <p className="text-xs text-slate-500">Connect to see the protocol exchange.</p>}
          <ol className="space-y-1.5 font-mono text-[11px]">
            {wire.map((w, i) => (
              <li key={i} className="truncate">
                <span className={w.dir === "→" ? "text-amber-300" : "text-teal-300"}>{w.dir} {w.label}</span>
                {w.ms !== undefined && <span className="text-slate-500"> ({w.ms} ms)</span>}{" "}
                <span className="text-slate-400">{JSON.stringify(redact(w.body)).slice(0, 220)}</span>
              </li>
            ))}
          </ol>
        </section>

        <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 text-sm">
          <h2 className="mb-2 font-semibold">Connect an MCP client</h2>
          <pre className="overflow-auto rounded-lg bg-black/40 p-3 text-xs text-slate-200">{`{
  "mcpServers": {
    "repurpora": {
      "type": "http",
      "url": "${MCP_URL}",
      "headers": { "Authorization": "Bearer <your Supabase access token>" }
    }
  }
}`}</pre>
        </section>
      </main>
    </div>
  );
}
