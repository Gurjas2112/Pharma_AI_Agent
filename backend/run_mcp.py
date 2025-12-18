"""
Standalone MCP Server for PharmaAI
Run this to expose PharmaAI agents via Model Context Protocol
"""
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
from config import Config

load_dotenv()

# Initialize configuration
Config.validate()

# Get LLM config
llm_config = {
    "model": Config.LLM_MODEL,
    "temperature": 0.7,
    "max_tokens": 2048
}

# Initialize MCP Server
mcp = FastMCP("PharmaAI MCP Server")

# Initialize all agents
master_agent = MasterAgent(llm_config=llm_config)
iqvia_agent = IQVIAAgent(llm_config=llm_config)
exim_agent = EXIMAgent(llm_config=llm_config)
patent_agent = PatentAgent(llm_config=llm_config)
clinical_trials_agent = ClinicalTrialsAgent(llm_config=llm_config)
internal_kb_agent = InternalKnowledgeAgent(
    llm_config=llm_config,
    supabase_client=supabase_service.client,
    embedding_service=embedding_service
)
web_intel_agent = WebIntelligenceAgent(llm_config=llm_config)
report_generator_agent = ReportGeneratorAgent(llm_config=llm_config)

# Register worker agents with master
master_agent.register_worker_agent("iqvia", iqvia_agent)
master_agent.register_worker_agent("exim", exim_agent)
master_agent.register_worker_agent("patent", patent_agent)
master_agent.register_worker_agent("clinical_trials", clinical_trials_agent)
master_agent.register_worker_agent("internal_kb", internal_kb_agent)
master_agent.register_worker_agent("web_intelligence", web_intel_agent)
master_agent.register_worker_agent("report_generator", report_generator_agent)

# Initialize MCP tools
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

print("✓ PharmaAI MCP Server initialized successfully")
print(f"  - LLM Model: {llm_config['model']}")
print(f"  - Supabase: {'Configured' if supabase_service.is_configured() else 'Mock mode'}")
print(f"  - Embedding: {os.getenv('EMBEDDING_MODEL_TYPE', 'mistral_local')}")
print(f"  - Transport: stdio (default)")
print("\nMCP Server ready. Waiting for client connection...")

if __name__ == "__main__":
    # Run MCP server with stdio transport (default for Claude Desktop, etc.)
    mcp.run(transport="stdio")
