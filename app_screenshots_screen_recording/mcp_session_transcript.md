# MCP client session against the deployed server
_Recorded 2026-11-14 17:59 UTC with the official `mcp` Python client (Streamable HTTP) - endpoint `https://mock-apis-production-90b14573.up.railway.app/mcp`_

## 1. Discovery and auth
- Request without a token → **HTTP 401** (`WWW-Authenticate: Bearer error="invalid_token", error_description="Authentication required", resource_metada…`)
- Protected-resource metadata: `{"resource": "https://mock-apis-production-90b14573.up.railway.app/mcp", "authorization_servers": ["https://tnnriczwzupqlynftkoq.supabase.co/auth/v1"], "scopes_supported": ["repurpora:read"], "bearer_methods_supported": ["header"]}`
- Client then authenticates with a Supabase access token (bearer) issued to the demo analyst account.

## 2. Initialize
Server `repurpora` v1.0.0

## 3. tools/list
| tool | title | read-only |
|---|---|---|
| `molecule_profile` | Molecule profile | True |
| `market_insights` | Market insights (IQVIA mock) | True |
| `trade_flows` | API trade flows (EXIM mock) | True |
| `patent_landscape` | Patent landscape (USPTO clone) | True |
| `clinical_trials` | Clinical trials (ClinicalTrials.gov v2) | True |
| `web_intelligence` | Web intelligence | True |
| `internal_knowledge` | Internal knowledge search (RAG) | True |
| `opportunity_score` | Opportunity score (ML) | True |
| `my_reports` | My archived reports | True |

## 4. tools/call
**`patent_landscape`** `{"molecule": "colchicine"}`
→ USPTO API clone (synthetic): 11 filings, 5 active

**`opportunity_score`** `{"fto_risk": 2, "unmet_need": 0.8, "evidence_strength": 0.7, "region": "India", "innovation_type": "new_dosage_form"}`
→ p(success) = 0.96 (label 1 at threshold 0.66, model logistic_regression); top drivers: evidence_strength +0.059, unmet_need +0.046, innovation_type +0.032; imputed: 12 fields

**`my_reports`** `{"question": "how many reports per decision"}`
→ 1 row(s) for the caller only · SQL: SELECT decision, count(*) AS n_reports FROM my_reports GROUP BY decision ORDER BY n_reports DESC LIMIT 50

Every call above is recorded in the audit log as `mcp_tool_call` (see screenshot 24).
