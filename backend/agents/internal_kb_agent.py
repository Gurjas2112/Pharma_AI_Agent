"""
Internal Knowledge Agent
Retrieves and summarizes internal documents using Supabase pgvector
Documents are pre-ingested from internal_knowledge_documents/ directory
Returns: Key takeaways, comparative tables, downloadable briefing PDFs
"""
from typing import Dict, Any, List
import os
import requests

try:
    import pdfplumber
except ImportError:
    pdfplumber = None
    print("Warning: pdfplumber not installed. PDF processing disabled.")


class InternalKnowledgeAgent:
    """
    Worker Agent: Internal Knowledge Base (RAG with pgvector)
    
    Uses Supabase pgvector for semantic search over internal documents
    Documents must be ingested first using scripts/ingest_documents.py
    
    Knowledge Base Sources:
    - Pharmaceutical textbooks (Applied Biopharmaceutics, Drug Discovery, etc.)
    - Big Data in Pharmaceutical Industry research papers
    - Product development and selection guides
    - Research dissertations and presentations
    """
    
    def __init__(self, llm_config: Dict[str, Any] = None, supabase_client = None, embedding_service = None):
        self.llm_config = llm_config
        self.supabase_client = supabase_client
        self.embedding_service = embedding_service
        self.use_mock = os.getenv("USE_MOCK_DATA", "true").lower() == "true"
    
    def _download_and_extract_pdf(self, pdf_url: str) -> str:
        """
        Download and extract text from a PDF URL
        
        Args:
            pdf_url: URL of the PDF to download
            
        Returns:
            Extracted text content
        """
        if not pdfplumber:
            print("pdfplumber not available for PDF processing")
            return ""
        
        try:
            # Download PDF
            response = requests.get(pdf_url, timeout=30, verify=False)
            
            if response.status_code == 200:
                # Save temporarily
                temp_path = f"temp_{hash(pdf_url)}.pdf"
                with open(temp_path, 'wb') as f:
                    f.write(response.content)
                
                # Extract text using pdfplumber
                extracted_text = ""
                with pdfplumber.open(temp_path) as pdf:
                    for page in pdf.pages[:10]:  # Extract first 10 pages
                        extracted_text += page.extract_text() or ""
                
                # Clean up
                os.remove(temp_path)
                
                return extracted_text[:5000]  # Limit to first 5000 chars
            else:
                print(f"Failed to download PDF from {pdf_url}")
                return ""
                
        except Exception as e:
            print(f"Error processing PDF {pdf_url}: {str(e)}")
            return ""
    
    async def execute(self, molecule: str = None, disease: str = None, context: Dict = None) -> Dict[str, Any]:
        """
        Execute internal knowledge retrieval
        
        Args:
            molecule: Drug molecule name
            disease: Target disease
            context: Previous agent findings
            
        Returns:
            Relevant internal documents and summaries
        """
        
        if not molecule:
            return {"error": "No molecule specified for internal knowledge search"}
        
        # Build search query
        search_query = f"{molecule}"
        if disease:
            search_query += f" {disease}"
        
        # Perform semantic search - Supabase configuration required
        if not self.supabase_client or not self.embedding_service:
            return {
                "error": "Internal knowledge base not configured",
                "message": "Supabase and embedding service are required. Run document ingestion first.",
                "molecule": molecule
            }
        
        try:
            results = await self._semantic_search(search_query)
            return {
                "molecule": molecule,
                "search_query": search_query,
                "documents_found": len(results),
                "relevant_documents": results,
                "key_insights": self._extract_key_insights(results),
                "summary": self._generate_summary(molecule, results)
            }
        except Exception as e:
            return {
                "error": "Failed to search internal knowledge base",
                "message": str(e),
                "molecule": molecule
            }
    
    async def _semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Perform semantic search using Supabase pgvector
        
        Steps:
        1. Generate embedding for query
        2. Search internal_docs table using cosine similarity
        3. Return top_k most relevant documents
        """
        # Generate embedding for query
        query_embedding = await self.embedding_service.generate_embedding(query)
        
        # Search in Supabase
        response = self.supabase_client.rpc(
            'match_internal_docs',
            {
                'query_embedding': query_embedding,
                'match_threshold': 0.7,
                'match_count': top_k
            }
        ).execute()
        
        # Format results
        results = []
        for doc in response.data:
            results.append({
                "doc_id": doc["id"],
                "source": doc["source"],
                "content_snippet": doc["content"][:500],  # First 500 chars
                "similarity_score": doc["similarity"],
                "metadata": doc.get("metadata", {})
            })
        
        return results
    

    
    def _extract_key_insights(self, documents: List[Dict]) -> List[str]:
        """
        Extract key insights from retrieved documents
        
        Args:
            documents: List of document results
            
        Returns:
            List of key insight strings
        """
        insights = []
        
        for doc in documents[:3]:  # Top 3 documents
            snippet = doc.get("content_snippet", "")
            if snippet:
                # Extract first sentence as insight
                sentences = snippet.split('. ')
                if sentences:
                    insights.append(sentences[0])
        
        return insights
    
    def _generate_summary(self, molecule: str, documents: List[Dict]) -> str:
        """
        Generate summary from internal knowledge
        
        Args:
            molecule: Drug molecule name
            documents: Retrieved documents
            
        Returns:
            Summary string
        """
        if not documents:
            return f"No internal knowledge found for {molecule}"
        
        doc_count = len(documents)
        avg_relevance = sum(doc.get("relevance_score", doc.get("similarity_score", 0)) for doc in documents) / doc_count
        
        return f"Found {doc_count} relevant internal documents for {molecule} (avg relevance: {avg_relevance:.2f}). Key sources include internal strategy reports, R&D pipeline reviews, and feasibility studies."
