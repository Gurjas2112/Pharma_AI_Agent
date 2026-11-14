"""Archive SQL agent: validator attack corpus, fallback, routing and DB-enforced isolation."""

import pytest

from repurpora.agents.sql_agent import ARCHIVE_RE, UnsafeSQL, template_sql, validate_sql

ALLOWED = [
    "SELECT report_id, molecule, decision FROM my_reports WHERE decision = 'GO' ORDER BY created_at DESC",
    "select decision, count(*) from my_reports group by decision",
    "SELECT molecule FROM my_reports WHERE query ILIKE '%reports%'",            # literal mentions are fine
    "SELECT r.molecule, u.model FROM my_reports r JOIN my_usage u ON true",
    "SELECT sum(input_tokens + output_tokens) FROM my_usage WHERE created_at > now() - interval '7 days'",
]
ATTACKS = [
    "DELETE FROM my_reports",
    "UPDATE my_reports SET decision = 'GO'",
    "SELECT * FROM reports",                                                    # physical table
    "SELECT * FROM public.reports",
    "SELECT * FROM my_reports, reports",                                        # comma join bypass
    "SELECT * FROM my_reports m, llm_usage",
    "SELECT * FROM my_reports WHERE report_id IN (SELECT report_id FROM reports)",
    "SELECT * FROM my_reports UNION SELECT * FROM audit_log",
    "SELECT * FROM my_reports; DROP TABLE reports",
    "SELECT * FROM my_reports -- comment",
    "SELECT pg_sleep(10) FROM my_reports",
    "SELECT current_setting('repurpora.owner') FROM my_reports",
    "SELECT * INTO stolen FROM my_reports",
    "WITH x AS (SELECT 1) SELECT * FROM x",
    "SELECT * FROM auth.users",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_validator_allows_safe_queries(sql):
    out = validate_sql(sql)
    assert out.upper().endswith("LIMIT 50") or "LIMIT" in out.upper()


@pytest.mark.parametrize("sql", ATTACKS)
def test_validator_rejects_attacks(sql):
    with pytest.raises(UnsafeSQL):
        validate_sql(sql)


def test_limit_is_capped():
    assert validate_sql("SELECT * FROM my_reports LIMIT 100000").endswith("LIMIT 50")


@pytest.mark.parametrize("q", ["list my GO reports", "how many reports per decision", "my token usage this week"])
def test_templates_are_always_safe(q):
    sql, _ = template_sql(q)
    validate_sql(sql)


def test_archive_routing_regex():
    assert ARCHIVE_RE.search("list my GO reports for metformin")
    assert ARCHIVE_RE.search("how many assessments did I run?")
    assert not ARCHIVE_RE.search("Assess metformin repurposing in India")


def test_graph_routes_archive_questions_to_sql_agent(monkeypatch):
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.store.memory import InMemoryStore

    monkeypatch.setattr("repurpora.agents.sql_agent.answer",
                        lambda q, owner: {"markdown": f"ARCHIVE for {owner}", "sql": "SELECT 1", "rows": 0,
                                          "source": "template"})
    monkeypatch.setattr("repurpora.observability._db_audit", lambda *a, **k: None)
    monkeypatch.setattr("repurpora.observability._cloudwatch", lambda *a, **k: None)
    from repurpora.graph import build_graph

    g = build_graph(InMemorySaver(), InMemoryStore())
    out = g.invoke({"messages": [("user", "list my previous reports")]},
                   {"configurable": {"thread_id": "sq1", "user_id": "u9"}})
    assert out["messages"][-1].content == "ARCHIVE for u9"
    assert not out.get("results")  # no research agents were run


def _db():
    from repurpora.db import db_available

    return db_available()


@pytest.mark.skipif(not _db(), reason="database not reachable")
def test_db_enforces_row_isolation_even_for_raw_sql():
    """Even raw SQL against the physical table returns only the owner's rows under archive_reader."""
    from repurpora.db import conn

    with conn() as c, c.transaction():
        c.execute("SELECT set_config('repurpora.owner', %s, true)", ("smoke-user",))
        c.execute("SET LOCAL ROLE archive_reader")
        owners = {r[0] for r in c.execute("select distinct owner from reports").fetchall()}
    assert owners <= {"smoke-user"}


@pytest.mark.skipif(not _db(), reason="database not reachable")
def test_answer_end_to_end_with_template(monkeypatch):
    from repurpora.agents import sql_agent

    monkeypatch.setattr(sql_agent, "_llm_sql", lambda q: (_ for _ in ()).throw(RuntimeError("llm down")))
    out = sql_agent.answer("how many reports per decision", "eval")
    assert out["source"] == "template" and "decision" in out["markdown"]
