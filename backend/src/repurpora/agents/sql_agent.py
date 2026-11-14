"""Archive SQL agent: answers questions about the user's own saved reports and usage.

Examples:
  "list my GO reports for metformin" · "how many assessments did I run this week?"
  "which molecule had the highest ML score?" · "how many tokens have my sessions used?"

Security model (the LLM is treated as untrusted):
1. The model only ever sees two **virtual tables**, ``my_reports`` and ``my_usage``.
2. The server wraps the generated query in CTEs **pre-filtered by the caller's user id**, so a query can
   never reach another user's rows, whatever SQL it contains.
3. A validator allows only a single SELECT over those virtual tables: no DML/DDL, comments, extra statements,
   system catalogs or functions with side effects. LIMIT is capped at 50.
4. Execution happens in a READ ONLY transaction with a 5 s statement timeout.
5. If the LLM fails or its SQL is rejected, deterministic template queries answer instead.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

log = logging.getLogger(__name__)

ARCHIVE_RE = re.compile(
    r"\b(my|our|past|previous|saved|archived|earlier)\b.{0,40}\b(reports?|assessments?|analys[ie]s|runs|sessions|decisions)\b"
    r"|\bhow many (reports|assessments|analyses|runs|tokens)\b|\btoken usage\b|\b(list|show) (all )?reports\b",
    re.I,
)

VIRTUAL_SCHEMA = """my_reports(report_id text, created_at timestamptz, query text, molecule text, indication text,
           decision text  -- one of GO, PARTIAL_GO, NO_GO, INSIGHT
           , confidence int, ml_score float  -- 0..1 success probability
           , evidence_coverage float)        -- 0..1
my_usage(created_at timestamptz, model text, node text, input_tokens int, output_tokens int, latency_ms int)"""

SYSTEM = f"""You translate a user's question about THEIR OWN saved research archive into ONE PostgreSQL SELECT.
Tables you may use (and nothing else):
{VIRTUAL_SCHEMA}
Words like "my", "past", "previous", "saved" mean ALL of the user's reports. Add a date filter ONLY when the user
states an explicit window (today, this week, last 30 days, since <date>).
Rules: a single SELECT statement; no semicolons or comments; only these two tables; use ILIKE for text matching;
use now() - interval '7 days' style filters for dates; order results sensibly; LIMIT at most 20.
Respond ONLY as JSON: {{"sql": "...", "explanation": "one short sentence"}}

Examples:
Q: list my GO reports for metformin
{{"sql": "SELECT report_id, created_at, molecule, indication, decision, ml_score FROM my_reports WHERE decision = 'GO' AND molecule ILIKE '%metformin%' ORDER BY created_at DESC LIMIT 20", "explanation": "GO reports for metformin, newest first."}}
Q: how many assessments did I run per decision?
{{"sql": "SELECT decision, count(*) AS n_reports FROM my_reports GROUP BY decision ORDER BY n_reports DESC", "explanation": "Report counts per decision."}}
Q: total tokens used this week
{{"sql": "SELECT sum(input_tokens + output_tokens) AS tokens FROM my_usage WHERE created_at > now() - interval '7 days'", "explanation": "Tokens in the last 7 days."}}"""

ALLOWED_TABLES = {"my_reports", "my_usage"}
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|copy|merge|call|do|execute|prepare|"
    r"vacuum|analyze|listen|notify|lock|set|reset|load|security|pg_\w+|information_schema|current_setting|"
    r"set_config|dblink|lo_\w+|pg_sleep|into)\b|;|--|/\*|\\",
    re.I,
)
MAX_LIMIT = 50
# any identifier that is not one of the two virtual tables but names a physical table/schema is rejected
REAL_TABLES = re.compile(
    r"\b(reports|llm_usage|audit_log|feedback|rag_chunks|rag_documents|thread|runs|store|checkpoints?|"
    r"checkpoint_\w+|assistant\w*|auth|storage|users|crons|public)\b",
    re.I,
)


class UnsafeSQL(ValueError):
    pass


def validate_sql(sql: str) -> str:
    """Return a normalised safe query or raise UnsafeSQL."""
    q = (sql or "").strip().rstrip(";").strip()
    if not re.match(r"(?is)^select\b", q):
        raise UnsafeSQL("only SELECT statements are allowed")
    if FORBIDDEN.search(q):
        raise UnsafeSQL("forbidden keyword or construct")
    # strip string literals before scanning identifiers, so ILIKE '%reports%' is not a false positive
    bare = re.sub(r"'(?:[^']|'')*'", "''", q)
    if REAL_TABLES.search(bare):
        raise UnsafeSQL("physical or schema-qualified tables are not allowed")
    tables = {t.lower() for t in re.findall(r"(?i)\b(?:from|join)\s+([a-z_][a-z0-9_\.]*)", bare)}
    if not tables or not tables <= ALLOWED_TABLES:
        raise UnsafeSQL(f"only {sorted(ALLOWED_TABLES)} may be queried (got {sorted(tables)})")
    m = re.search(r"(?i)\blimit\s+(\d+)\s*$", q)
    if m:
        if int(m.group(1)) > MAX_LIMIT:
            q = q[: m.start()] + f"LIMIT {MAX_LIMIT}"
    else:
        q = f"{q} LIMIT {MAX_LIMIT}"
    return q


def wrap(sql: str) -> str:
    """Bind the virtual tables to the caller's rows. The owner value is a bound parameter, never string-formatted."""
    return (
        "WITH my_reports AS (SELECT report_id, created_at, query, molecule, indication, decision, confidence, "
        "ml_score, evidence_coverage FROM reports WHERE owner IS NOT DISTINCT FROM %(owner)s), "
        "my_usage AS (SELECT created_at, model, node, input_tokens, output_tokens, latency_ms FROM llm_usage "
        "WHERE owner IS NOT DISTINCT FROM %(owner)s) " + sql
    )


def template_sql(question: str) -> tuple[str, str]:
    """Deterministic fallback when the LLM is unavailable or produced unsafe SQL."""
    q = question.lower()
    if "token" in q or "usage" in q:
        return ("SELECT model, count(*) AS calls, sum(input_tokens + output_tokens) AS tokens, "
                "round(avg(latency_ms)) AS avg_latency_ms FROM my_usage GROUP BY model ORDER BY tokens DESC",
                "Token usage per model.")
    if re.search(r"how many|count|per decision|breakdown", q):
        return ("SELECT decision, count(*) AS n_reports, round(avg(ml_score)::numeric, 2) AS avg_ml_score "
                "FROM my_reports GROUP BY decision ORDER BY n_reports DESC", "Report counts per decision.")
    where = []
    if m := re.search(r"\b(go|partial[_ ]go|no[_ ]go|insight)\b", q):
        where.append(f"decision = '{m.group(1).upper().replace(' ', '_')}'")
    sql = ("SELECT report_id, created_at, molecule, indication, decision, ml_score, evidence_coverage "
           "FROM my_reports" + (" WHERE " + " AND ".join(where) if where else "")
           + " ORDER BY created_at DESC LIMIT 20")
    return sql, "Your most recent reports."


def _llm_sql(question: str) -> tuple[str, str]:
    from repurpora.llm import get_llm

    raw = get_llm("primary", json_mode=True).invoke([SystemMessage(SYSTEM), HumanMessage(question)],
                                                   config={"run_name": "sql_agent"}).content
    j = json.loads(raw)
    return j["sql"], j.get("explanation", "")


def execute(sql: str, owner: str | None) -> tuple[list[str], list[tuple]]:
    from repurpora.db import conn

    with conn() as c, c.transaction():
        c.execute("SET TRANSACTION READ ONLY")
        c.execute("SET LOCAL statement_timeout = '5s'")
        # defence in depth: least-privilege role + RLS keyed on a transaction-local owner setting
        c.execute("SELECT set_config('repurpora.owner', %s, true)", (owner or "",))
        c.execute("SET LOCAL ROLE archive_reader")
        cur = c.execute(wrap(sql.replace("%", "%%")), {"owner": owner})  # literal % (ILIKE) vs param markers
        cols = [d.name for d in cur.description]
        return cols, cur.fetchall()


def _fmt(v: Any) -> str:
    if v is None:
        return "–"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, (float, Decimal)):
        return f"{float(v):.2f}"
    return str(v).replace("|", "/")[:60]


def answer(question: str, owner: str | None) -> dict[str, Any]:
    """Run the full NL -> SQL -> validated read-only execution -> markdown flow."""
    source = "llm"
    try:
        sql, why = _llm_sql(question)
        sql = validate_sql(sql)
    except Exception as exc:  # LLM down, bad JSON or unsafe SQL -> safe template
        log.info("sql agent fallback (%s)", type(exc).__name__)
        sql, why = template_sql(question)
        sql = validate_sql(sql)
        source = "template"
    try:
        cols, rows = execute(sql, owner)
        explicit_window = re.search(r"\b(today|yesterday|this (week|month|year)|last \d+|since|past \d+|20\d\d)\b",
                                    question, re.I)
        if not rows and source == "llm" and not explicit_window:
            # the LLM may have over-filtered (e.g. read "previous" as "older than a day"); fall back to the template
            t_sql, t_why = template_sql(question)
            t_cols, t_rows = execute(validate_sql(t_sql), owner)
            if t_rows:
                sql, why, cols, rows, source = validate_sql(t_sql), t_why, t_cols, t_rows, "template (llm result empty)"
    except Exception as exc:
        if source == "llm":  # LLM SQL was valid but failed at runtime -> retry with template once
            sql, why = template_sql(question)
            sql, source = validate_sql(sql), "template"
            cols, rows = execute(sql, owner)
        else:
            raise exc
    lines = ["### 🗂️ Your research archive", f"_{why}_", ""]
    if not rows:
        lines.append("No matching saved reports yet. Run an assessment and it will be archived automatically.")
    else:
        links = {}
        if "report_id" in cols:
            from repurpora.report.archive import signed_url_for

            for r in rows[:10]:
                rid = r[cols.index("report_id")]
                if rid and (u := signed_url_for(rid)):
                    links[rid] = u
        show_cols = cols + (["PDF"] if links else [])
        lines += ["| " + " | ".join(show_cols) + " |", "|" + "---|" * len(show_cols)]
        for r in rows[:20]:
            cells = [_fmt(v) for v in r]
            if links:
                rid = r[cols.index("report_id")]
                cells.append(f"[open]({links[rid]})" if rid in links else "–")
            lines.append("| " + " | ".join(cells) + " |")
        if len(rows) > 20:
            lines.append(f"\n_{len(rows) - 20} more row(s) not shown._")
    lines += ["", "<details><summary>SQL that ran (read-only, scoped to your account)</summary>", "",
              f"```sql\n{sql}\n```", f"Generated by: {source}", "</details>"]
    return {"markdown": "\n".join(lines), "sql": sql, "rows": len(rows), "source": source}
