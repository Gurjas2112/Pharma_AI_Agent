"""
Supabase Client Service
Handles connection to Supabase PostgreSQL with pgvector extension
"""
from typing import Optional
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


class SupabaseService:
    """
    Manages Supabase connection for:
    1. Auth & Storage
    2. pgvector semantic search
    3. Document storage
    """
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_ANON_KEY")
        self.client: Optional[Client] = None
        
        if self.url and self.key:
            self.client = create_client(self.url, self.key)
        else:
            print("⚠️  Supabase credentials not found. Running in mock mode.")
    
    def is_configured(self) -> bool:
        """Check if Supabase is properly configured"""
        return self.client is not None
    
    def get_client(self) -> Optional[Client]:
        """Get Supabase client instance"""
        return self.client
    
    async def initialize_schema(self):
        """
        Initialize database schema for internal_docs table
        
        Creates:
        - vector extension
        - internal_docs table with pgvector column
        - RPC function for similarity search
        """
        if not self.client:
            print("Cannot initialize schema - Supabase not configured")
            return
        
        # SQL for schema initialization
        schema_sql = """
        -- Enable vector extension
        CREATE EXTENSION IF NOT EXISTS vector;
        
        -- Create internal_docs table
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
        """
        
        try:
            # Execute schema SQL (would need admin access in production)
            print("Schema initialization SQL generated. Execute manually in Supabase SQL editor:")
            print(schema_sql)
            return schema_sql
        except Exception as e:
            print(f"Schema initialization error: {e}")
            return None
    
    async def insert_document(self, source: str, content: str, embedding: list, metadata: dict = None):
        """
        Insert a document into internal_docs table
        
        Args:
            source: Document source/filename
            content: Full text content
            embedding: Vector embedding (1536-dim)
            metadata: Additional metadata (optional)
        """
        if not self.client:
            print("Cannot insert document - Supabase not configured")
            return None
        
        try:
            result = self.client.table("internal_docs").insert({
                "source": source,
                "content": content,
                "embedding": embedding,
                "metadata": metadata or {}
            }).execute()
            
            return result.data
        except Exception as e:
            print(f"Document insertion error: {e}")
            return None
    
    async def search_documents(self, query_embedding: list, match_threshold: float = 0.7, match_count: int = 5):
        """
        Search documents using vector similarity
        
        Args:
            query_embedding: Query vector (1536-dim)
            match_threshold: Minimum similarity score (0-1)
            match_count: Number of results to return
            
        Returns:
            List of matching documents with similarity scores
        """
        if not self.client:
            print("Cannot search documents - Supabase not configured")
            return []
        
        try:
            result = self.client.rpc(
                "match_internal_docs",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": match_threshold,
                    "match_count": match_count
                }
            ).execute()
            
            return result.data
        except Exception as e:
            print(f"Document search error: {e}")
            return []
    
    async def insert_report(self, report_id: str, molecule: str, decision: str, 
                           confidence: int, findings: dict, file_path: str, 
                           pdf_binary: bytes = None, disease: str = None):
        """
        Insert a generated report into reports table
        
        Args:
            report_id: Unique report identifier
            molecule: Drug molecule name
            decision: GO/NO-GO/PARTIAL_GO decision
            confidence: Confidence score (0-100)
            findings: Raw findings from all agents (JSONB)
            file_path: Local file path to PDF
            pdf_binary: Optional PDF binary data
            disease: Optional disease/indication
        """
        if not self.client:
            print("Cannot insert report - Supabase not configured")
            return None
        
        try:
            result = self.client.table("reports").insert({
                "report_id": report_id,
                "molecule": molecule,
                "disease": disease,
                "decision": decision,
                "confidence": confidence,
                "findings": findings,
                "file_path": file_path,
                "pdf_binary": pdf_binary
            }).execute()
            
            return result.data
        except Exception as e:
            print(f"Report insertion error: {e}")
            return None
    
    async def get_report(self, report_id: str):
        """
        Retrieve a report by report_id
        
        Args:
            report_id: Unique report identifier
            
        Returns:
            Report record with metadata and binary data
        """
        if not self.client:
            print("Cannot retrieve report - Supabase not configured")
            return None
        
        try:
            result = self.client.table("reports").select("*").eq("report_id", report_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Report retrieval error: {e}")
            return None


# Global instance
supabase_service = SupabaseService()
