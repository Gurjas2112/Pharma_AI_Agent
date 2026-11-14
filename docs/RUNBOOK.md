# Runbook

## Services
| Service | Where | Health |
|---|---|---|
| Frontend | Vercel `repurpora` | `GET https://repurpora.vercel.app` → 200 |
| Agent server (Aegra) | Railway `agent-server` | `GET /health` → `{"status":"healthy", database/checkpointer/store connected}` |
| Mock data APIs + upload | Railway `mock-apis` | `GET /health` → `{"status":"ok"}` |
| Cache | Railway `Redis` | Railway dashboard |
| LLM | Ollama behind Caddy bearer proxy (local GPU + Cloudflare tunnel in the prototype; EC2 in production) | `GET $OLLAMA_BASE_URL/api/tags` with Bearer → 200, without → 401 |
| AWS emulator | `docker compose up -d localstack aws-bootstrap` | `GET :4566/_localstack/health` |

## Common operations
| Task | Command |
|---|---|
| Restart the LLM tunnel (new URL each time) | `docker compose --profile demo up -d --force-recreate tunnel`. Read the URL with `docker compose logs tunnel \| grep trycloudflare`, then `railway variables -s agent-server --set OLLAMA_BASE_URL=<url>` and `railway variables -s mock-apis --set OLLAMA_BASE_URL=<url>` |
| Redeploy backend | `cd backend && railway up . --path-as-root -s agent-server -d` (same for `mock-apis`) |
| Redeploy frontend | `cd frontend && vercel deploy --prod` |
| Apply DB schema | `cd backend && uv run python scripts/apply_schema.py` |
| Re-index documents | `uv run python scripts/ingest.py --dir data/internal_docs` |
| Retrain the ML scorer | `uv run python -m repurpora.ml.opportunity_scorer --train` (the Docker build also does this) |
| Flush caches | `docker exec repurpora-redis-1 redis-cli FLUSHALL` (local) |
| Start the EC2 GPU host (production) | `AWS_ENDPOINT_URL= OLLAMA_PROXY_TOKEN=... infra/aws/ec2_ollama.sh` |
| Stop the EC2 GPU host (cost) | `infra/aws/teardown.sh` (or `teardown.sh terminate`) |

## Incidents
| Symptom | Likely cause | Fix |
|---|---|---|
| `EMAXCONNSESSION max clients reached` | Supabase session pooler exhausted | Keep `LANGGRAPH_MAX_POOL_SIZE=4`, `SQLALCHEMY_POOL_SIZE=2`. The app pool uses the transaction pooler (`APP_DATABASE_URL` on :6543). Stop stray local Aegra instances. |
| Chat shows "Agent server unreachable" | Railway is cold-starting or crashed | `railway logs -s agent-server`, then redeploy |
| Runs hang at `planner` | LLM unreachable (tunnel URL changed or GPU host stopped) | Check `OLLAMA_BASE_URL` and the bearer token, then restart the tunnel |
| Ollama returns 403 through the proxy | Host header not rewritten | Caddy needs `header_up Host {upstream_hostport}` |
| 401 on every request | Expired Supabase session, or wrong JWKS URL | Sign in again; check `SUPABASE_JWKS_URL` |
| Secret exposure | A key was committed or pasted | Rotate it in Supabase/Firecrawl/LangSmith/Railway, update the Railway/Vercel env and the vault (`aws-bootstrap`), and record it in `governance/evidence/incident_log.md` |
