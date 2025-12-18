"""
Document Ingestion Script
Processes PDF documents from internal_knowledge_documents directory
Extracts text, chunks it, generates embeddings, and stores in Supabase
"""
import os
import sys
import asyncio
from pathlib import Path
from typing import List, Dict
import re

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.supabase_client import supabase_service
from services.embedding_service import embedding_service

# Try to import pdfplumber
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("⚠️  pdfplumber not installed. Install with: pip install pdfplumber")
    sys.exit(1)


class DocumentIngester:
    """
    Processes PDF documents for vector database ingestion
    
    Steps:
    1. Read PDF files from internal_knowledge_documents/
    2. Extract text using pdfplumber
    3. Chunk text into manageable segments
    4. Generate embeddings for each chunk
    5. Insert into Supabase internal_docs table
    """
    
    def __init__(self, docs_directory: str = "internal_knowledge_documents"):
        self.docs_directory = docs_directory
        self.chunk_size = 1000  # characters per chunk
        self.chunk_overlap = 200  # overlap between chunks
        
        # Verify directory exists
        if not os.path.exists(self.docs_directory):
            raise FileNotFoundError(f"Documents directory not found: {self.docs_directory}")
    
    def get_pdf_files(self) -> List[Path]:
        """Get all PDF files from the documents directory"""
        pdf_files = list(Path(self.docs_directory).glob("*.pdf"))
        print(f"Found {len(pdf_files)} PDF files")
        return pdf_files
    
    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """
        Extract text from PDF using pdfplumber
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text content
        """
        try:
            text_content = []
            
            with pdfplumber.open(pdf_path) as pdf:
                print(f"Processing {pdf_path.name} ({len(pdf.pages)} pages)...")
                
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
            
            full_text = "\n\n".join(text_content)
            print(f"  ✓ Extracted {len(full_text)} characters from {pdf_path.name}")
            return full_text
            
        except Exception as e:
            print(f"  ✗ Error extracting text from {pdf_path.name}: {e}")
            return ""
    
    def chunk_text(self, text: str, source: str) -> List[Dict]:
        """
        Split text into overlapping chunks
        
        Args:
            text: Full text content
            source: Source filename
            
        Returns:
            List of chunks with metadata
        """
        chunks = []
        
        # Clean text
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split into chunks with overlap
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk_text.rfind('. ')
                if last_period > self.chunk_size * 0.5:  # At least halfway through
                    chunk_text = chunk_text[:last_period + 1]
                    end = start + last_period + 1
            
            chunks.append({
                "source": source,
                "content": chunk_text.strip(),
                "metadata": {
                    "chunk_index": chunk_index,
                    "total_chunks": None,  # Will update after
                    "chunk_start": start,
                    "chunk_end": end
                }
            })
            
            chunk_index += 1
            start = end - self.chunk_overlap
        
        # Update total_chunks in metadata
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = len(chunks)
        
        print(f"  ✓ Created {len(chunks)} chunks from {source}")
        return chunks
    
    async def generate_embeddings(self, chunks: List[Dict]) -> List[Dict]:
        """
        Generate embeddings for each chunk
        
        Args:
            chunks: List of text chunks with metadata
            
        Returns:
            Chunks with embeddings added
        """
        print(f"  Generating embeddings for {len(chunks)} chunks...")
        
        for i, chunk in enumerate(chunks):
            try:
                # Generate embedding using local Mistral model
                embedding = await embedding_service.generate_embedding(chunk["content"])
                chunk["embedding"] = embedding
                
                if (i + 1) % 10 == 0:
                    print(f"    Progress: {i + 1}/{len(chunks)} embeddings generated")
                    
            except Exception as e:
                print(f"    ✗ Error generating embedding for chunk {i}: {e}")
                chunk["embedding"] = None
        
        # Filter out chunks without embeddings
        valid_chunks = [c for c in chunks if c["embedding"] is not None]
        print(f"  ✓ Generated {len(valid_chunks)} valid embeddings")
        return valid_chunks
    
    async def insert_chunks_to_db(self, chunks: List[Dict]):
        """
        Insert chunks with embeddings into Supabase
        
        Args:
            chunks: List of chunks with embeddings
        """
        print(f"  Inserting {len(chunks)} chunks into Supabase...")
        
        success_count = 0
        
        for i, chunk in enumerate(chunks):
            try:
                result = await supabase_service.insert_document(
                    source=chunk["source"],
                    content=chunk["content"],
                    embedding=chunk["embedding"],
                    metadata=chunk["metadata"]
                )
                
                if result:
                    success_count += 1
                    
                if (i + 1) % 10 == 0:
                    print(f"    Progress: {i + 1}/{len(chunks)} chunks inserted")
                    
            except Exception as e:
                print(f"    ✗ Error inserting chunk {i}: {e}")
        
        print(f"  ✓ Successfully inserted {success_count}/{len(chunks)} chunks")
        return success_count
    
    async def ingest_document(self, pdf_path: Path):
        """
        Complete ingestion pipeline for a single document
        
        Args:
            pdf_path: Path to PDF file
        """
        print(f"\n{'='*60}")
        print(f"Ingesting: {pdf_path.name}")
        print(f"{'='*60}")
        
        # Step 1: Extract text
        text = self.extract_text_from_pdf(pdf_path)
        if not text:
            print(f"  ✗ Skipping {pdf_path.name} - no text extracted")
            return
        
        # Step 2: Chunk text
        chunks = self.chunk_text(text, pdf_path.name)
        
        # Step 3: Generate embeddings
        chunks_with_embeddings = await self.generate_embeddings(chunks)
        
        # Step 4: Insert into database
        inserted = await self.insert_chunks_to_db(chunks_with_embeddings)
        
        print(f"✓ Completed ingestion of {pdf_path.name} - {inserted} chunks stored")
    
    async def ingest_all(self):
        """Ingest all PDF documents in the directory"""
        pdf_files = self.get_pdf_files()
        
        if not pdf_files:
            print("No PDF files found to ingest")
            return
        
        print(f"\n{'='*60}")
        print(f"Starting batch ingestion of {len(pdf_files)} documents")
        print(f"{'='*60}\n")
        
        total_documents = 0
        
        for pdf_path in pdf_files:
            try:
                await self.ingest_document(pdf_path)
                total_documents += 1
            except Exception as e:
                print(f"✗ Failed to ingest {pdf_path.name}: {e}")
        
        print(f"\n{'='*60}")
        print(f"Batch ingestion completed")
        print(f"Successfully processed: {total_documents}/{len(pdf_files)} documents")
        print(f"{'='*60}\n")


async def main():
    """Main entry point"""
    print("PharmaAI Document Ingestion Script")
    print("="*60)
    
    # Check Supabase connection
    if not supabase_service.is_configured():
        print("✗ Supabase not configured. Check .env file.")
        sys.exit(1)
    
    print("✓ Supabase connected")
    
    # Check embedding service
    if not embedding_service.model:
        print("⚠️  Embedding service not fully loaded. Will use mock embeddings.")
    else:
        print("✓ Embedding service ready")
    print()
    
    # Initialize ingester
    ingester = DocumentIngester("internal_knowledge_documents")
    
    # Run ingestion
    await ingester.ingest_all()
    
    print("\n✓ Document ingestion completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
