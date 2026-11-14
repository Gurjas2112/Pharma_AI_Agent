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

**Timing note.** These queries had already been run once before this recording, so the agent server answered from
its Redis LLM and tool cache, and the video moves fast. Uncached end-to-end latency on a single 6 GB GPU is about
2 minutes per full assessment; see `backend/evals/results/latest.md` for p50/p95.

To re-record:
`cd frontend && E2E_BASE_URL=https://repurpora.vercel.app npx playwright test e2e/walkthrough.spec.ts`
