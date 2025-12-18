"""
FastAPI Backend for PharmaAI Agentic System
Main entry point for the chatbot API
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import os
from dotenv import load_dotenv
from fastmcp import FastMCP

# Import agents
from agents.master_agent import MasterAgent
from agents.iqvia_agent import IQVIAAgent
from agents.exim_agent import EXIMAgent
from agents.patent_agent import PatentAgent
from agents.clinical_trials_agent import ClinicalTrialsAgent
from agents.internal_kb_agent import InternalKnowledgeAgent
from agents.web_intel_agent import WebIntelligenceAgent
from agents.report_agent import ReportGeneratorAgent

# Import services
from services.supabase_client import supabase_service
from services.embedding_service import embedding_service

# Import MCP tools
from mcp_tools import initialize_mcp_tools

load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="PharmaAI Agentic System",
    description="AI-powered drug repurposing research assistant",
    version="1.0.0"
)

# Initialize MCP Server
mcp = FastMCP("PharmaAI MCP Server")

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
        os.getenv("FRONTEND_URL", "http://localhost:3000")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static report files
if os.path.exists("backend/reports"):
    app.mount("/reports", StaticFiles(directory="backend/reports"), name="reports")

# Request/Response models
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessage]] = []

class ChatResponse(BaseModel):
    message: str
    decision: Optional[str] = None
    confidence: Optional[float] = None
    report_url: Optional[str] = None
    findings: Optional[Dict[str, Any]] = None
    status: str = "success"


# Initialize Master Agent and Worker Agents
llm_config = {
    "model": os.getenv("LLM_MODEL", "mistral"),
    "temperature": 0.7,
    "max_tokens": 2000
}

# Initialize all agents
master_agent = MasterAgent(llm_config=llm_config)

# Initialize and register Worker Agents
iqvia_agent = IQVIAAgent(llm_config=llm_config)
exim_agent = EXIMAgent(llm_config=llm_config)
patent_agent = PatentAgent(llm_config=llm_config)
clinical_trials_agent = ClinicalTrialsAgent(llm_config=llm_config)
internal_kb_agent = InternalKnowledgeAgent(
    llm_config=llm_config,
    supabase_client=supabase_service.get_client() if supabase_service.is_configured() else None,
    embedding_service=embedding_service
)
web_intel_agent = WebIntelligenceAgent(llm_config=llm_config)
report_generator_agent = ReportGeneratorAgent(llm_config=llm_config)

# Register Worker Agents with Master Agent
master_agent.register_worker_agent("iqvia", iqvia_agent)
master_agent.register_worker_agent("exim", exim_agent)
master_agent.register_worker_agent("patent", patent_agent)
master_agent.register_worker_agent("clinical_trials", clinical_trials_agent)
master_agent.register_worker_agent("internal_knowledge", internal_kb_agent)
master_agent.register_worker_agent("web_intelligence", web_intel_agent)
master_agent.register_worker_agent("report_generator", report_generator_agent)

# Initialize MCP tools with agent instances
agents_dict = {
    "master": master_agent,
    "iqvia": iqvia_agent,
    "exim": exim_agent,
    "patent": patent_agent,
    "clinical_trials": clinical_trials_agent,
    "internal_kb": internal_kb_agent,
    "web_intel": web_intel_agent,
    "report_generator": report_generator_agent
}
initialize_mcp_tools(mcp, agents_dict)

# Note: FastMCP 1.0 runs as a standalone server, not mounted to FastAPI
# To use MCP, run it separately with: python -m fastmcp run main:mcp
# Or access it via stdio/SSE transport

print("✓ PharmaAI backend initialized successfully")
print(f"  - LLM Model: {llm_config['model']}")
print(f"  - Supabase: {'Configured' if supabase_service.is_configured() else 'Mock mode'}")
print(f"  - Embedding: {os.getenv('EMBEDDING_MODEL_TYPE', 'mistral_local')}")
print(f"  - MCP Server: Initialized (run separately with 'python -m fastmcp run main:mcp')")


# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "PharmaAI Agentic System",
        "version": "1.0.0",
        "agents": {
            "master": "active",
            "workers": list(master_agent.worker_agents.keys())
        }
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint
    
    Receives user message, orchestrates Master Agent, returns response
    """
    try:
        # Convert conversation history to dict format
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ]
        
        # Process query through Master Agent
        result = await master_agent.process_query(
            user_query=request.message,
            conversation_history=history
        )
        
        # Format response
        response_message = f"""
**Decision:** {result.get('decision', 'PENDING')}  
**Confidence:** {result.get('confidence_score', 0)}/100

**Analysis:**
{result.get('reasoning', 'Processing...')}

{result.get('synthesis', '')}
"""
        
        if result.get('report_url'):
            response_message += f"\n\n📄 **[Download Full Report]({result['report_url']})**"
        
        return ChatResponse(
            message=response_message.strip(),
            decision=result.get("decision"),
            confidence=result.get("confidence_score"),
            report_url=result.get("report_url"),
            findings=result.get("findings"),
            status="success"
        )
    
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent processing error: {str(e)}")


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str):
    """
    Retrieve generated report
    
    Args:
        report_id: Report filename (without extension)
    """
    # Try PDF first
    pdf_path = f"backend/reports/{report_id}.pdf"
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, media_type="application/pdf", filename=f"{report_id}.pdf")
    
    # Fallback to Markdown
    md_path = f"backend/reports/{report_id}.md"
    if os.path.exists(md_path):
        return FileResponse(md_path, media_type="text/markdown", filename=f"{report_id}.md")
    
    raise HTTPException(status_code=404, detail="Report not found")


@app.get("/api/agents/status")
async def get_agent_status():
    """Get status of all agents"""
    return {
        "master_agent": {
            "status": "active",
            "decision_thresholds": master_agent.decision_thresholds
        },
        "worker_agents": {
            name: "active" for name in master_agent.worker_agents.keys()
        },
        "services": {
            "supabase": "configured" if supabase_service.is_configured() else "mock",
            "embeddings": os.getenv("EMBEDDING_MODEL_TYPE", "mistral_local")
        }
    }


@app.post("/api/documents/upload")
async def upload_document(file_content: str, file_name: str):
    """
    Upload internal document to vector database
    
    Args:
        file_content: Document text content
        file_name: Document filename
    """
    if not supabase_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Supabase not configured. Cannot upload documents."
        )
    
    try:
        # Generate embedding
        embedding = await embedding_service.generate_embedding(file_content)
        
        # Insert into Supabase
        result = await supabase_service.insert_document(
            source=file_name,
            content=file_content,
            embedding=embedding,
            metadata={"uploaded_via": "api"}
        )
        
        return {
            "status": "success",
            "message": f"Document '{file_name}' uploaded successfully",
            "document_id": result[0].get("id") if result else None
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")


# Run server
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
