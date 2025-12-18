"""
MCP Tool Definitions for PharmaAI Agents
Exposes each agent as an MCP tool for external integration
"""
from typing import Dict, Any, Optional
from fastmcp import FastMCP

# Initialize agents (will be injected from main.py)
_master_agent = None
_iqvia_agent = None
_exim_agent = None
_patent_agent = None
_clinical_trials_agent = None
_internal_kb_agent = None
_web_intel_agent = None
_report_generator_agent = None


def initialize_mcp_tools(mcp: FastMCP, agents: Dict[str, Any]):
    """
    Initialize MCP tools with agent instances
    
    Args:
        mcp: FastMCP server instance
        agents: Dictionary of agent instances
    """
    global _master_agent, _iqvia_agent, _exim_agent, _patent_agent
    global _clinical_trials_agent, _internal_kb_agent, _web_intel_agent, _report_generator_agent
    
    _master_agent = agents.get("master")
    _iqvia_agent = agents.get("iqvia")
    _exim_agent = agents.get("exim")
    _patent_agent = agents.get("patent")
    _clinical_trials_agent = agents.get("clinical_trials")
    _internal_kb_agent = agents.get("internal_kb")
    _web_intel_agent = agents.get("web_intel")
    _report_generator_agent = agents.get("report_generator")
    
    # Register tools
    register_master_agent_tool(mcp)
    register_iqvia_agent_tool(mcp)
    register_exim_agent_tool(mcp)
    register_patent_agent_tool(mcp)
    register_clinical_trials_agent_tool(mcp)
    register_internal_kb_agent_tool(mcp)
    register_web_intel_agent_tool(mcp)
    register_report_generator_tool(mcp)


def register_master_agent_tool(mcp: FastMCP):
    """Register Master Agent orchestration tool"""
    
    @mcp.tool()
    async def pharma_research_orchestrator(
        query: str,
        conversation_history: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Master orchestrator for pharmaceutical drug repurposing research.
        
        Analyzes research queries, coordinates 7 specialized worker agents,
        and provides GO/NO-GO recommendations based on market, patent, clinical,
        and trade intelligence.
        
        Args:
            query: Research query (e.g., "Find repurposing opportunities for Montelukast")
            conversation_history: Optional list of previous messages
            
        Returns:
            Comprehensive research findings with decision recommendation
        """
        if not _master_agent:
            return {"error": "Master agent not initialized"}
        
        result = await _master_agent.process_query(
            user_query=query,
            conversation_history=conversation_history or []
        )
        return result


def register_iqvia_agent_tool(mcp: FastMCP):
    """Register IQVIA Market Intelligence Agent tool"""
    
    @mcp.tool()
    async def iqvia_market_analysis(
        molecule: str,
        disease: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyzes pharmaceutical market dynamics using IQVIA-style data.
        
        Provides market size, CAGR, competitive landscape, and market
        attractiveness scoring for drug molecules.
        
        Args:
            molecule: Drug molecule name (e.g., "Montelukast", "Metformin")
            disease: Optional target disease/indication
            
        Returns:
            Market intelligence including size, growth rate, competition
        """
        if not _iqvia_agent:
            return {"error": "IQVIA agent not initialized"}
        
        result = await _iqvia_agent.execute(molecule=molecule, disease=disease)
        return result


def register_exim_agent_tool(mcp: FastMCP):
    """Register EXIM Trade Intelligence Agent tool"""
    
    @mcp.tool()
    async def exim_trade_analysis(
        molecule: str,
        disease: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyzes global import/export trends for pharmaceutical molecules.
        
        Uses UN Comtrade data to assess trade volumes, key exporters/importers,
        sourcing risks, and supply chain dynamics.
        
        Args:
            molecule: Drug molecule name
            disease: Optional target disease context
            
        Returns:
            Trade intelligence including volumes, top countries, sourcing risk
        """
        if not _exim_agent:
            return {"error": "EXIM agent not initialized"}
        
        result = await _exim_agent.execute(molecule=molecule, disease=disease)
        return result


def register_patent_agent_tool(mcp: FastMCP):
    """Register Patent Landscape Agent tool"""
    
    @mcp.tool()
    async def patent_landscape_analysis(
        molecule: str,
        disease: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyzes patent landscape and Freedom to Operate (FTO) status.
        
        Searches USPTO and EPO databases for active/expired patents,
        calculates FTO risk scores, and identifies blocking patents.
        
        Args:
            molecule: Drug molecule name
            disease: Optional target disease for repurposing context
            
        Returns:
            Patent analysis including active patents, FTO score, expiry dates
        """
        if not _patent_agent:
            return {"error": "Patent agent not initialized"}
        
        result = await _patent_agent.execute(molecule=molecule, disease=disease)
        return result


def register_clinical_trials_agent_tool(mcp: FastMCP):
    """Register Clinical Trials Intelligence Agent tool"""
    
    @mcp.tool()
    async def clinical_trials_analysis(
        molecule: str,
        disease: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyzes clinical trial pipeline and research activity.
        
        Queries ClinicalTrials.gov for active trials, phase distribution,
        recruitment status, and identifies repurposing signals.
        
        Args:
            molecule: Drug molecule name
            disease: Optional target disease to focus on
            
        Returns:
            Clinical trial intelligence including active trials, phases, sponsors
        """
        if not _clinical_trials_agent:
            return {"error": "Clinical trials agent not initialized"}
        
        result = await _clinical_trials_agent.execute(molecule=molecule, disease=disease)
        return result


def register_internal_kb_agent_tool(mcp: FastMCP):
    """Register Internal Knowledge Base Agent tool"""
    
    @mcp.tool()
    async def internal_knowledge_search(
        query: str,
        molecule: Optional[str] = None,
        disease: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Performs semantic search over internal pharmaceutical documents.
        
        Uses Supabase pgvector with Mistral embeddings for RAG-based retrieval
        of relevant research papers, guidelines, and internal documentation.
        
        Args:
            query: Search query
            molecule: Optional drug molecule name
            disease: Optional disease context
            
        Returns:
            Relevant document excerpts with similarity scores
        """
        if not _internal_kb_agent:
            return {"error": "Internal KB agent not initialized"}
        
        result = await _internal_kb_agent.execute(
            molecule=molecule,
            disease=disease,
            context={"query": query}
        )
        return result


def register_web_intel_agent_tool(mcp: FastMCP):
    """Register Web Intelligence Agent tool"""
    
    @mcp.tool()
    async def web_intelligence_search(
        molecule: str,
        disease: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gathers real-time intelligence from web sources.
        
        Uses DuckDuckGo to search for recent publications, guidelines,
        news articles, and forum discussions about drug molecules.
        
        Args:
            molecule: Drug molecule name
            disease: Optional target disease context
            
        Returns:
            Web intelligence including news, publications, forum insights
        """
        if not _web_intel_agent:
            return {"error": "Web intelligence agent not initialized"}
        
        result = await _web_intel_agent.execute(molecule=molecule, disease=disease)
        return result


def register_report_generator_tool(mcp: FastMCP):
    """Register Report Generator Agent tool"""
    
    @mcp.tool()
    async def generate_research_report(
        molecule: str,
        findings: Dict[str, Any],
        decision: str,
        confidence: int
    ) -> Dict[str, Any]:
        """
        Generates comprehensive PDF research reports.
        
        Converts agent findings into formatted PDF reports using
        WeasyPrint with tables, charts, and executive summaries.
        
        Args:
            molecule: Drug molecule name
            findings: Dictionary of findings from all agents
            decision: GO/NO-GO/CONDITIONAL decision
            confidence: Confidence score (0-100)
            
        Returns:
            Report metadata including filename and download URL
        """
        if not _report_generator_agent:
            return {"error": "Report generator agent not initialized"}
        
        result = await _report_generator_agent.execute(
            molecule=molecule,
            findings=findings,
            decision=decision,
            confidence=confidence
        )
        return result
