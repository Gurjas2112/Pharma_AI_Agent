"""Apply scripts/supabase_schema.sql to DATABASE_URL (idempotent)."""
from pathlib import Path

import psycopg

from repurpora.settings import get_settings

sql = (Path(__file__).parent / "supabase_schema.sql").read_text(encoding="utf-8")
with psycopg.connect(get_settings().database_url, autocommit=True) as c:
    c.execute(sql)
    tables = c.execute(
        "select table_name from information_schema.tables where table_schema='public' "
        "and table_name in ('rag_documents','rag_chunks','reports','llm_usage','audit_log','feedback') order by 1"
    ).fetchall()
    print("tables:", [t[0] for t in tables])
    print("bucket:", c.execute("select id, public from storage.buckets where id='reports'").fetchone())
