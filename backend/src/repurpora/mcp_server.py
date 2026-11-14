"""Outbound MCP server: exposes Repurpora's research tools to external MCP clients.

Clients such as Claude Desktop, Cursor or another team's agent can call the same tools the LangGraph worker
agents use. Internally the graph keeps calling these functions in-process; MCP is only the **external** contract,
so internal calls don't pay a network hop.

Transport: Streamable HTTP at ``/mcp`` on the aux (mock-apis) service.
Auth (reference image 4): OAuth 2.1 resource server. Bearer = Supabase access token (ES256 via JWKS), audience
checked by the verifier, scope ``repurpora:read``. Protected-resource metadata is served at
``/.well-known/oauth-protected-resource`` so compliant clients can discover the issuer (Supabase Auth).
Every tool is read-only, user-scoped where it touches user data, audited, and covered by the same tool cache.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from repurpora.observability import audit
from repurpora.settings import get_settings

log = logging.getLogger(__name__)
SCOPE = "repurpora:read"
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)


class SupabaseTokenVerifier:
    """Verify Supabase-issued JWTs (ES256 via JWKS, aud=authenticated) and map them to MCP access tokens."""

    async def verify_token(self, token: str) -> AccessToken | None:
        from repurpora.auth import verify

        try:
            claims = verify(token)
        except Exception:
            return None
        return AccessToken(token=token, client_id=str(claims.get("client_id") or "supabase"), scopes=[SCOPE],
                           expires_at=claims.get("exp"), subject=claims["sub"],
                           claims={k: claims.get(k) for k in ("iss", "email", "role")})


def _caller() -> str | None:
    tok = get_access_token()
    return tok.subject if tok else None


def _audited(tool: str, args: dict[str, Any]) -> str | None:
    owner = _caller()
    audit("mcp_tool_call", {"tool": tool, "args": {k: v for k, v in args.items() if v is not None}}, owner=owner)
    return owner


def _strip(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def build() -> MCPServer:
    s = get_settings()
    public = os.getenv("MCP_PUBLIC_URL", "http://localhost:8081").rstrip("/")
    mcp = MCPServer(
        name="repurpora",
        title="Repurpora research tools",
        instructions=("Pharmaceutical drug-repurposing research tools: market (IQVIA mock), trade (EXIM mock), "
                      "patents (USPTO clone), live ClinicalTrials.gov, live web search, internal knowledge RAG, "
                      "an ML opportunity scorer and your own archived reports. All tools are read-only."),
        version="1.0.0",
        token_verifier=SupabaseTokenVerifier(),
        auth=AuthSettings(issuer_url=f"{(s.supabase_url or 'https://example.supabase.co').rstrip('/')}/auth/v1",
                          resource_server_url=f"{public}/mcp", required_scopes=[SCOPE],
                          validate_token_resource=False),
    )

    @mcp.tool(title="Molecule profile", annotations=READ_ONLY)
    def molecule_profile(molecule: str) -> dict:
        """Approved indications, mechanism and candidate repurposing indications for a molecule (INN name)."""
        from repurpora.tools import sources

        _audited("molecule_profile", {"molecule": molecule})
        return _strip(sources.molecule_profile(molecule.lower().strip()))

    @mcp.tool(title="Market insights (IQVIA mock)", annotations=READ_ONLY)
    def market_insights(molecule: str | None = None, therapy_area: str | None = None, region: str = "India") -> dict:
        """Market size, 5-year CAGR, competitors and patient burden by indication for a molecule or therapy area."""
        from repurpora.regions import canonical
        from repurpora.tools import sources

        _audited("market_insights", {"molecule": molecule, "therapy_area": therapy_area, "region": region})
        return _strip(sources.iqvia_market(molecule, therapy_area, canonical(region)))

    @mcp.tool(title="API trade flows (EXIM mock)", annotations=READ_ONLY)
    def trade_flows(molecule: str, country: str = "India") -> dict:
        """API import partners, sourcing concentration and 5-year trade volumes for a molecule."""
        from repurpora.tools import sources

        _audited("trade_flows", {"molecule": molecule, "country": country})
        return _strip(sources.exim_trade(molecule, country))

    @mcp.tool(title="Patent landscape (USPTO clone)", annotations=READ_ONLY)
    def patent_landscape(molecule: str, indication: str | None = None) -> dict:
        """Patent filings with type, assignee, filing/expiry year, status and claim scope."""
        from repurpora.tools import sources

        _audited("patent_landscape", {"molecule": molecule, "indication": indication})
        return _strip(sources.uspto_patents(molecule, indication))

    @mcp.tool(title="Clinical trials (ClinicalTrials.gov v2)", annotations=READ_ONLY)
    def clinical_trials(molecule: str, condition: str | None = None) -> dict:
        """Registered trials for a molecule (live ClinicalTrials.gov v2, stub fallback): phase, status, sponsor."""
        from repurpora.tools import sources

        _audited("clinical_trials", {"molecule": molecule, "condition": condition})
        return _strip(sources.clinical_trials(molecule, condition))

    @mcp.tool(title="Web intelligence", annotations=READ_ONLY)
    def web_intelligence(query: str, k: int = 5) -> dict:
        """Live web search (Firecrawl, mock fallback) for guidelines, publications and news. Content is sanitised."""
        from repurpora.guardrails.checks import sanitize_untrusted
        from repurpora.tools import sources

        _audited("web_intelligence", {"query": query})
        out = _strip(sources.web_search(query, max(1, min(k, 10))))
        for r in out.get("results", []):
            r["snippet"] = sanitize_untrusted(r.get("snippet", ""))
        return out

    @mcp.tool(title="Internal knowledge search (RAG)", annotations=READ_ONLY)
    def internal_knowledge(query: str, k: int = 5) -> list[dict]:
        """Hybrid (vector + full-text, RRF) search over shared internal documents and the caller's private uploads."""
        from repurpora.rag.retriever import rag_search

        owner = _audited("internal_knowledge", {"query": query})
        return [{"source": h["source"], "page": h.get("page"), "score": round(h.get("score", 0), 4),
                 "content": h["content"][:1200]} for h in rag_search(query, max(1, min(k, 10)), owner)]

    @mcp.tool(title="Opportunity score (ML)", annotations=READ_ONLY)
    def opportunity_score(market_usd_mn: float | None = None, cagr_pct: float | None = None,
                          competitors: float | None = None, patients_mn: float | None = None,
                          fto_risk: float | None = None, unmet_need: float | None = None,
                          evidence_strength: float | None = None, therapy_area: str | None = None,
                          region: str | None = None, innovation_type: str | None = None) -> dict:
        """Calibrated probability that a repurposing project launches successfully, with top drivers.
        Unknown inputs may be omitted; they are imputed and reported in `imputed_fields`."""
        from repurpora.ml.predict import predict

        args = {k: v for k, v in locals().items() if v is not None}
        _audited("opportunity_score", args)
        return predict(args)

    @mcp.tool(title="My archived reports", annotations=READ_ONLY)
    def my_reports(question: str) -> dict:
        """Ask about YOUR saved reports in plain English (e.g. 'GO reports for metformin'). Read-only, user-scoped SQL."""
        from repurpora.agents.sql_agent import answer

        owner = _audited("my_reports", {"question": question})
        out = answer(question, owner)
        return {"markdown": out["markdown"], "sql": out["sql"], "rows": out["rows"]}

    return mcp


def asgi_app():
    """Starlette app serving /mcp (+ OAuth protected-resource metadata), host-checked against DNS rebinding."""
    mcp = build()
    hosts = [h.strip() for h in os.getenv("MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*").split(",") if h.strip()]
    app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True,
                                  transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                                                               allowed_hosts=hosts))
    return mcp, app
