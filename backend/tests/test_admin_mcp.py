"""Admin API (RBAC, validation, self-protection), runtime config effects, and the MCP server."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from repurpora import runtime_config


@pytest.fixture(scope="module")
def client():
    from repurpora.mock_apis.app import app

    with TestClient(app) as c:
        yield c


def _as(monkeypatch, role: str | None, sub: str = "user-1"):
    claims = {"sub": sub, "email": f"{sub}@x.io", "app_metadata": {"role": role} if role else {}}
    monkeypatch.setattr("repurpora.auth.verify", lambda token: claims)
    return {"Authorization": "Bearer test"}


# ------------------------------------------------------------------ RBAC --

def test_admin_requires_token(client):
    assert client.get("/admin/config").status_code == 401


def test_admin_rejects_non_admin(client, monkeypatch):
    assert client.get("/admin/config", headers=_as(monkeypatch, "analyst")).status_code == 403
    assert client.get("/admin/config", headers=_as(monkeypatch, None)).status_code == 403


def test_admin_can_read_config_and_agents(client, monkeypatch):
    h = _as(monkeypatch, "admin")
    body = client.get("/admin/config", headers=h).json()
    assert "llm_model_primary" in body["config"] and set(body["agents"]) >= {"iqvia", "patent"}
    agents = client.get("/admin/agents", headers=h).json()
    assert {a["agent"] for a in agents} == set(runtime_config.ALL_AGENTS)


@pytest.mark.parametrize("changes", [
    {"llm_temperature": 9},
    {"evidence_coverage_threshold": 2},
    {"disabled_agents": ["teleport"]},
    {"disabled_agents": runtime_config.ALL_AGENTS},
    {"not_a_setting": 1},
])
def test_config_update_is_validated(client, monkeypatch, changes):
    monkeypatch.setattr("repurpora.db.conn", lambda: (_ for _ in ()).throw(AssertionError("must not write")))
    r = client.put("/admin/config", headers=_as(monkeypatch, "admin"), json={"changes": changes, "reason": "test"})
    assert r.status_code == 422


def test_admin_cannot_lock_themselves_out(client, monkeypatch):
    h = _as(monkeypatch, "admin", sub="me")
    assert client.post("/admin/users/me/role", headers=h, json={"role": "analyst"}).status_code == 400
    assert client.post("/admin/users/me/suspend", headers=h, json={"suspend": True}).status_code == 400


# ------------------------------------------------- runtime config effects --

def _cfg(**over):
    base = runtime_config.defaults().model_dump()
    return runtime_config.RuntimeConfig(**{**base, **over})


@pytest.fixture
def graph(monkeypatch):
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.store.memory import InMemoryStore

    from repurpora.nodes import core

    class Fake(GenericFakeChatModel):
        def with_structured_output(self, *a, **k):
            raise NotImplementedError

    monkeypatch.setattr(core, "get_llm", lambda *a, **k: Fake(messages=iter(
        [AIMessage(json.dumps({"faithfulness": 4, "unsupported": []}) if k.get("json_mode")
                   else "## Executive summary\nA finding [E1].")])))
    monkeypatch.setattr("repurpora.agents.workers._note", lambda agent, res: "- note")
    monkeypatch.setattr("repurpora.report.archive.upload_supabase", lambda *a, **k: False)
    monkeypatch.setattr("repurpora.report.archive.save_metadata", lambda *a, **k: None)
    monkeypatch.setattr("repurpora.observability._db_audit", lambda *a, **k: None)
    monkeypatch.setattr("repurpora.observability._cloudwatch", lambda *a, **k: None)
    from repurpora.graph import build_graph

    return build_graph(InMemorySaver(), InMemoryStore())


def test_kill_switch_refuses_all_requests(graph, monkeypatch):
    monkeypatch.setattr(runtime_config, "get", lambda force=False: _cfg(kill_switch=True, maintenance_message="Paused."))
    out = graph.invoke({"messages": [("user", "Assess metformin in India")]},
                       {"configurable": {"thread_id": "k1", "user_id": "u"}})
    assert "Paused." in out["messages"][-1].content and not out.get("results")


def test_disabled_agents_are_not_dispatched(graph, monkeypatch):
    monkeypatch.setattr(runtime_config, "get", lambda force=False: _cfg(disabled_agents=["exim", "web"]))
    out = graph.invoke({"messages": [("user", "Assess montelukast repurposing in India")]},
                       {"configurable": {"thread_id": "k2", "user_id": "u"}})
    ran = {r["agent"] for r in out["results"]}
    assert ran and not ran & {"exim", "web"}


# ------------------------------------------------------------------- MCP --

def test_mcp_http_requires_bearer_and_publishes_resource_metadata(client):
    hdr = {"accept": "application/json, text/event-stream", "host": "localhost:8081"}
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=hdr)
    assert r.status_code == 401
    prm = client.get("/.well-known/oauth-protected-resource/mcp", headers={"host": "localhost:8081"}).json()
    assert prm["resource"].endswith("/mcp") and prm["scopes_supported"] == ["repurpora:read"]
    assert prm["authorization_servers"][0].endswith("/auth/v1")


def test_mcp_exposes_read_only_tools_and_calls_them():
    from repurpora.mcp_server import build

    mcp = build()
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {"molecule_profile", "market_insights", "trade_flows", "patent_landscape", "clinical_trials",
                     "web_intelligence", "internal_knowledge", "opportunity_score", "my_reports"}
    assert all(t.annotations and t.annotations.read_only_hint for t in tools)
    res = asyncio.run(mcp.call_tool("opportunity_score", {"fto_risk": 2, "unmet_need": 0.8,
                                                           "evidence_strength": 0.7}))
    payload = json.loads(res.content[0].text)
    assert 0 <= payload["probability"] <= 1 and "imputed_fields" in payload
