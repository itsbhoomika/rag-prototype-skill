-- Supabase / Postgres + pgvector schema for the Next.js variant of the RAG prototype.
-- Run once in the Supabase SQL editor. Authorization lives inside match_chunks(),
-- so the application cannot "forget" to filter: rows outside the caller's groups are never scored.

create extension if not exists vector;

create table if not exists documents (
  id             bigint generated always as identity primary key,
  source         text not null unique,          -- path relative to the data folder
  title          text,
  metadata       jsonb not null default '{}',
  allowed_groups text[] not null,               -- e.g. {'policies'}; '*' = everyone
  created_at     timestamptz not null default now()
);

create table if not exists chunks (
  id             text primary key,               -- 'source::n', stable across re-ingests
  document_id    bigint not null references documents(id) on delete cascade,
  content        text not null,
  metadata       jsonb not null default '{}',   -- section, page, type
  allowed_groups text[] not null,               -- copied from the document for fast filtering
  embedding      vector(768),                   -- gemini-embedding-001 at 768 dims; change with the model
  fts            tsvector generated always as (to_tsvector('english', content)) stored
);

create index if not exists chunks_embedding_hnsw on chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_groups_gin    on chunks using gin (allowed_groups);
create index if not exists chunks_fts_gin       on chunks using gin (fts);

-- Dense search restricted to the caller's groups (filter before scoring).
create or replace function match_chunks(
  query_embedding vector(768),
  user_groups     text[],
  match_count     int default 30
) returns table (id text, document_id bigint, content text, metadata jsonb, similarity float)
language sql stable as $$
  select c.id, c.document_id, c.content, c.metadata,
         1 - (c.embedding <=> query_embedding) as similarity
  from chunks c
  where c.embedding is not null
    and (c.allowed_groups && user_groups or '*' = any(c.allowed_groups) or '*' = any(user_groups))
  order by c.embedding <=> query_embedding
  limit match_count;
$$;

-- Keyword search with the same group filter (for hybrid / RRF in application code).
create or replace function match_chunks_fts(
  query_text  text,
  user_groups text[],
  match_count int default 30
) returns table (id text, document_id bigint, content text, metadata jsonb, rank float)
language sql stable as $$
  select c.id, c.document_id, c.content, c.metadata,
         ts_rank(c.fts, websearch_to_tsquery('english', query_text)) as rank
  from chunks c
  where c.fts @@ websearch_to_tsquery('english', query_text)
    and (c.allowed_groups && user_groups or '*' = any(c.allowed_groups) or '*' = any(user_groups))
  order by rank desc
  limit match_count;
$$;

-- The service-role key bypasses row-level security: use it only on the server, never in the browser.
alter table documents enable row level security;
alter table chunks    enable row level security;
