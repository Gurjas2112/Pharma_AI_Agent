-- Repurpora / Lazarus Graph - Supabase schema (idempotent)
-- Apply:  uv run python scripts/apply_schema.py
create extension if not exists vector;
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------- RAG ----
create table if not exists rag_documents (
  id          bigserial primary key,
  sha256      text unique not null,
  source      text not null,
  owner       text,                      -- null = shared corpus; else auth.uid()
  n_chunks    int default 0,
  version     int default 1,
  created_at  timestamptz default now()
);

create table if not exists rag_chunks (
  id             bigserial primary key,
  document_id    bigint references rag_documents(id) on delete cascade,
  owner          text,
  source         text not null,
  page           int,
  chunk_index    int,
  strategy       text default 'recursive',
  content        text not null,
  parent_content text,
  embedding      vector(768) not null,   -- nomic-embed-text
  fts            tsvector generated always as (to_tsvector('english', content)) stored,
  created_at     timestamptz default now()
);
create index if not exists rag_chunks_embedding_hnsw on rag_chunks
  using hnsw (embedding vector_cosine_ops) with (m = 16, ef_construction = 64);
create index if not exists rag_chunks_fts on rag_chunks using gin (fts);
create index if not exists rag_chunks_owner on rag_chunks (owner);

-- Hybrid search: dense + sparse fused with Reciprocal Rank Fusion (k = 60)
create or replace function hybrid_search(
  query_embedding vector(768),
  query_text      text,
  match_count     int default 15,
  p_owner         text default null,
  rrf_k           int default 60
) returns table (id bigint, source text, page int, content text, parent_content text,
                 dense_sim float, rrf_score float)
language sql stable as $$
  with dense as (
    select c.id, 1 - (c.embedding <=> query_embedding) as sim,
           row_number() over (order by c.embedding <=> query_embedding) as rnk
    from rag_chunks c
    where c.owner is null or c.owner = p_owner
    order by c.embedding <=> query_embedding
    limit match_count * 2
  ),
  sparse as (
    select c.id,
           row_number() over (order by ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) desc) as rnk
    from rag_chunks c
    where (c.owner is null or c.owner = p_owner)
      and c.fts @@ websearch_to_tsquery('english', query_text)
    limit match_count * 2
  ),
  fused as (
    select coalesce(d.id, s.id) as id,
           coalesce(1.0 / (rrf_k + d.rnk), 0) + coalesce(1.0 / (rrf_k + s.rnk), 0) as score,
           d.sim
    from dense d full outer join sparse s on d.id = s.id
  )
  select c.id, c.source, c.page, c.content, c.parent_content,
         coalesce(f.sim, 1 - (c.embedding <=> query_embedding)) as dense_sim, f.score as rrf_score
  from fused f join rag_chunks c on c.id = f.id
  order by f.score desc
  limit match_count;
$$;

-- ------------------------------------------------------------ Reports ----
create table if not exists reports (
  id            uuid primary key default gen_random_uuid(),
  report_id     text unique not null,
  owner         text,
  thread_id     text,
  query         text,
  molecule      text,
  indication    text,
  decision      text,
  confidence    int,
  ml_score      float,
  evidence_coverage float,
  storage_path  text,
  excel_path    text,
  s3_key        text,
  findings      jsonb,
  created_at    timestamptz default now()
);
create index if not exists reports_owner on reports(owner, created_at desc);

-- ------------------------------------------------------ Observability ----
create table if not exists llm_usage (
  id            bigserial primary key,
  run_id        text,
  thread_id     text,
  owner         text,
  model         text,
  node          text,
  input_tokens  int,
  output_tokens int,
  latency_ms    int,
  cached        boolean default false,
  created_at    timestamptz default now()
);

-- append-only audit trail (no update/delete grants)
create table if not exists audit_log (
  id          bigserial primary key,
  ts          timestamptz default now(),
  thread_id   text,
  owner       text,
  event       text not null,           -- guard_input | plan | tool_call | policy | judge | archive
  detail      jsonb,
  prompt_sha  text
);

create table if not exists feedback (
  id          bigserial primary key,
  owner       text,
  thread_id   text,
  run_id      text,
  score       int check (score in (-1, 1)),
  comment     text,
  created_at  timestamptz default now()
);

-- -------------------------------------------------------------- RLS ------
-- Backend uses the service role (bypasses RLS). Browser clients may only read
-- their own reports and write their own feedback. No anon writes.
alter table rag_documents enable row level security;
alter table rag_chunks    enable row level security;
alter table reports       enable row level security;
alter table llm_usage     enable row level security;
alter table audit_log     enable row level security;
alter table feedback      enable row level security;

drop policy if exists reports_owner_read on reports;
create policy reports_owner_read on reports for select to authenticated
  using (owner = auth.uid()::text);

drop policy if exists feedback_owner_insert on feedback;
create policy feedback_owner_insert on feedback for insert to authenticated
  with check (owner = auth.uid()::text);

drop policy if exists feedback_owner_read on feedback;
create policy feedback_owner_read on feedback for select to authenticated
  using (owner = auth.uid()::text);

-- ------------------------------------------------------------ Storage ----
insert into storage.buckets (id, name, public)
values ('reports', 'reports', false)
on conflict (id) do nothing;

-- ------------------------------------------------- Archive SQL agent (v2) ----
-- Least-privilege role used by the text-to-SQL agent. Even if generated SQL bypassed the
-- application validator, Postgres only lets this role SELECT the caller's own rows.
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'archive_reader') then
    create role archive_reader nologin;
  end if;
end $$;
grant archive_reader to current_user;
grant usage on schema public to archive_reader;
revoke all on all tables in schema public from archive_reader;
grant select (report_id, created_at, query, molecule, indication, decision, confidence, ml_score,
              evidence_coverage, owner) on reports to archive_reader;
grant select (created_at, model, node, input_tokens, output_tokens, latency_ms, owner) on llm_usage to archive_reader;

drop policy if exists archive_reader_own_reports on reports;
create policy archive_reader_own_reports on reports for select to archive_reader
  using (owner is not distinct from nullif(current_setting('repurpora.owner', true), ''));
drop policy if exists archive_reader_own_usage on llm_usage;
create policy archive_reader_own_usage on llm_usage for select to archive_reader
  using (owner is not distinct from nullif(current_setting('repurpora.owner', true), ''));

-- ------------------------------------------------- Admin: runtime config (v3) ----
-- Versioned runtime settings editable from the admin panel (no redeploy). Every change is
-- appended to app_config_history (who, when, old -> new) for the governance change log.
create table if not exists app_config (
  key         text primary key,
  value       jsonb not null,
  version     int not null default 1,
  updated_by  text,
  updated_at  timestamptz default now()
);
create table if not exists app_config_history (
  id          bigserial primary key,
  key         text not null,
  old_value   jsonb,
  new_value   jsonb,
  version     int,
  changed_by  text,
  reason      text,
  changed_at  timestamptz default now()
);
alter table app_config enable row level security;
alter table app_config_history enable row level security;
