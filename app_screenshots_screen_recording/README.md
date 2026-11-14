# Walkthrough: screenshots and screen recording

Recorded automatically with Playwright (`frontend/e2e/walkthrough.spec.ts`) against the **live production
deployment**: Vercel frontend → Railway Aegra agent server → Supabase. The LLM is Ollama behind the bearer-token proxy.

| File | What it shows |
|---|---|
| `full_walkthrough.mp4` / `.webm` | The whole flow, start to finish (72 s) |
| `01`–`05` | Landing page: hero, animated live agent run, agent constellation, end-to-end journey, trust layer |
| `06` | Sign-up (Supabase Auth, pre-confirmed user via server route) |
| `07` | Agent Chat UI empty state with sample strategic prompts |
| `08` | Master agent plan, with parallel worker results streaming in |
| `09`–`12` | Cited brief (`[E#]`), key data tables, evidence register, quality gates, archived report links |
| `13`–`14` | Portfolio question: *"Which respiratory diseases show low competition but high patient burden in India?"* |
| `15` | Guardrail blocks a prompt-injection attempt before planning |
| `16` | Sign-out returns to the landing page |
| `sample_report.pdf` | The PDF report the run archived to Supabase Storage |
| **Admin panel**, recorded by `frontend/e2e/admin.spec.ts` | |
| `admin_panel_walkthrough.mp4` | Admin flow (37 s): admin link in chat, every tab, and a non-admin being refused |
| `17` | "Admin" link appears in the chat toolbar only for users with the admin role |
| `18`–`19` | Overview: KPIs (reports, active users, LLM calls, tokens, estimated cost per report, guardrail blocks), charts, usage by model and by graph node |
| `20`–`21` | Models & safety: runtime model, temperature, quality-gate and agent settings; kill-switch draft with a required change reason (discarded, so production config was not modified) |
| `22` | Agents & knowledge: per-agent tool allow-list, RAG index stats, document management |
| `23` | Users & roles: emails **masked by default** (PII minimisation), make or revoke admin, suspend |
| `24`–`25` | Append-only audit log: all events (including `mcp_tool_call`), then filtered to guardrail events |
| `26` | A signed-in **non-admin** is refused by the server (403), not just hidden in the UI |
| **MCP server** | |
| `27_mcp_client_session_production.png` + `mcp_session_transcript.md` | Real session against the deployed MCP server with the official `mcp` client: 401 without a token, OAuth protected-resource metadata, initialize, `tools/list` (9 read-only tools), and three `tools/call` results. Re-create with `backend/scripts/mcp_demo.py`. |

The admin recording used a dedicated demo admin account whose role was **revoked** right after recording, so no
standing admin account exists on the public demo. Grant one with `backend/scripts/make_admin.py <email>`.

**Timing note.** These queries had already been run once before this recording, so the agent server answered from
its Redis LLM and tool cache, and the video moves fast. Uncached end-to-end latency on a single 6 GB GPU is about
2 minutes per full assessment; see `backend/evals/results/latest.md` for p50/p95.

To re-record:
`cd frontend && E2E_BASE_URL=https://repurpora.vercel.app npx playwright test e2e/walkthrough.spec.ts`
