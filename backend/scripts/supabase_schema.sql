-- PharmaAI Supabase Database Schema
-- Run this SQL in your Supabase SQL Editor to create the necessary tables

-- Enable vector extension for pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Create internal_docs table for storing document chunks with embeddings
CREATE TABLE IF NOT EXISTS internal_docs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),  -- Standard embedding dimension (compatible with Mistral)
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for vector similarity search
CREATE INDEX IF NOT EXISTS internal_docs_embedding_idx 
ON internal_docs 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create reports table for storing generated research reports
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id TEXT UNIQUE NOT NULL,
    molecule TEXT NOT NULL,
    disease TEXT,
    decision TEXT NOT NULL,
    confidence INTEGER,
    findings JSONB,
    file_path TEXT NOT NULL,
    pdf_binary BYTEA,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create RPC function for similarity search
CREATE OR REPLACE FUNCTION match_internal_docs(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    source TEXT,
    content TEXT,
    similarity float,
    metadata JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        internal_docs.id,
        internal_docs.source,
        internal_docs.content,
        1 - (internal_docs.embedding <=> query_embedding) AS similarity,
        internal_docs.metadata
    FROM internal_docs
    WHERE 1 - (internal_docs.embedding <=> query_embedding) > match_threshold
    ORDER BY internal_docs.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Grant necessary permissions (adjust for your security needs)
ALTER TABLE internal_docs ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

-- Example policies (customize based on your auth requirements)
-- For now, allow authenticated users to read/write
DROP POLICY IF EXISTS "Allow authenticated users to read internal_docs" ON internal_docs;
CREATE POLICY "Allow authenticated users to read internal_docs"
    ON internal_docs FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS "Allow authenticated users to insert internal_docs" ON internal_docs;
CREATE POLICY "Allow authenticated users to insert internal_docs"
    ON internal_docs FOR INSERT
    TO authenticated
    WITH CHECK (true);

DROP POLICY IF EXISTS "Allow authenticated users to read reports" ON reports;
CREATE POLICY "Allow authenticated users to read reports"
    ON reports FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS "Allow authenticated users to insert reports" ON reports;
CREATE POLICY "Allow authenticated users to insert reports"
    ON reports FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- For anon key access (development only - remove in production)
DROP POLICY IF EXISTS "Allow anon to read internal_docs" ON internal_docs;
CREATE POLICY "Allow anon to read internal_docs"
    ON internal_docs FOR SELECT
    TO anon
    USING (true);

DROP POLICY IF EXISTS "Allow anon to insert internal_docs" ON internal_docs;
CREATE POLICY "Allow anon to insert internal_docs"
    ON internal_docs FOR INSERT
    TO anon
    WITH CHECK (true);

DROP POLICY IF EXISTS "Allow anon to read reports" ON reports;
CREATE POLICY "Allow anon to read reports"
    ON reports FOR SELECT
    TO anon
    USING (true);

DROP POLICY IF EXISTS "Allow anon to insert reports" ON reports;
CREATE POLICY "Allow anon to insert reports"
    ON reports FOR INSERT
    TO anon
    WITH CHECK (true);
