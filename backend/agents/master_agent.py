"""
Master Agent: Conversation Orchestrator
Coordinates Worker Agents, applies decision logic, and synthesizes findings
"""
from typing import Dict, List, Any
from crewai import Agent, Task, Crew
import json


class MasterAgent:
    """
    Master Agent orchestrates the entire research workflow:
    1. Interprets user intent
    2. Decomposes into research tasks
    3. Invokes Worker Agents in logical order
    4. Applies decision logic (market attractiveness, patent FTO, clinical saturation)
    5. Synthesizes findings and triggers report generation
    """
    
    def __init__(self, llm_config: Dict[str, Any]):
        """
        Initialize Master Agent with LLM configuration
        Args:
            llm_config: Configuration for the LLM (Mistral local or API)
        """
        self.llm_config = llm_config
        self.worker_agents = {}
        self.decision_thresholds = {
            "min_market_size_million_usd": 50,  # Minimum market size to be attractive
            "max_patent_risk_score": 7,  # Patent risk above 7/10 is blocking
            "max_clinical_saturation": 15,  # More than 15 active trials = saturated
            "min_cagr_percent": 3  # Minimum growth rate
        }
    
    def register_worker_agent(self, name: str, agent: Any):
        """Register a Worker Agent"""
        self.worker_agents[name] = agent
    
    async def process_query(self, user_query: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Main orchestration logic
        
        Args:
            user_query: User's natural language prompt
            conversation_history: Previous messages in the conversation
            
        Returns:
            Dict containing:
                - decision: GO/NO-GO/PARTIAL
                - reasoning: Explanation of decision
                - findings: Aggregated research results
                - report_url: PDF report link (if generated)
        """
        
        # Step 1: Parse user intent (extract molecule name, research goals)
        intent = self._parse_user_intent(user_query)
        
        # Step 2: Plan research workflow
        workflow = self._plan_research_workflow(intent)
        
        # Step 3: Execute Worker Agents in sequence
        findings = {}
        decision_flags = {
            "market_attractive": False,
            "patents_clear": False,
            "clinical_viable": False
        }
        
        for step in workflow:
            agent_name = step["agent"]
            if agent_name not in self.worker_agents:
                findings[agent_name] = {"error": f"Agent {agent_name} not registered"}
                continue
            
            # Invoke Worker Agent
            agent_result = await self.worker_agents[agent_name].execute(
                molecule=intent.get("molecule"),
                disease=intent.get("disease"),
                context=findings  # Pass previous findings for context
            )
            findings[agent_name] = agent_result
            
            # Apply decision logic after each critical agent
            if agent_name == "iqvia":
                # Skip evaluation if agent returned an error
                if "error" not in agent_result:
                    decision_flags["market_attractive"] = self._evaluate_market_attractiveness(agent_result)
                    if not decision_flags["market_attractive"]:
                        # Early stop: Market too small/unattractive
                        return self._build_rejection_response(
                            reason="Market size too small or low growth rate",
                            findings=findings
                        )
                else:
                    # IQVIA unavailable - continue without market data
                    decision_flags["market_attractive"] = True  # Don't block on missing data
                    findings["_decision_note"] = "IQVIA market data unavailable - proceeding without market size validation"
            
            elif agent_name == "patent":
                # Skip evaluation if agent returned an error
                if "error" not in agent_result:
                    decision_flags["patents_clear"] = self._evaluate_patent_landscape(agent_result)
                    if not decision_flags["patents_clear"]:
                        # Deprioritize but don't hard stop
                        findings["_decision_note"] = "Patent landscape shows high FTO risk"
                else:
                    # Patent data unavailable - continue without patent validation
                    decision_flags["patents_clear"] = True  # Don't block on missing data
            
            elif agent_name == "clinical_trials":
                # Skip evaluation if agent returned an error
                if "error" not in agent_result:
                    decision_flags["clinical_viable"] = self._evaluate_clinical_viability(agent_result)
                    if not decision_flags["clinical_viable"]:
                        findings["_decision_note"] = "Clinical space appears saturated"
                else:
                    # Clinical trials data unavailable - continue without clinical validation
                    decision_flags["clinical_viable"] = True  # Don't block on missing data
        
        # Step 4: Synthesize findings
        synthesis = self._synthesize_findings(findings, decision_flags)
        
        # Step 5: Generate report
        report_result = await self.worker_agents["report_generator"].execute(
            synthesis=synthesis,
            raw_findings=findings
        )
        
        # Step 6: Return final decision
        return {
            "decision": synthesis["decision"],
            "reasoning": synthesis["reasoning"],
            "findings": findings,
            "synthesis": synthesis["summary"],
            "report_url": report_result.get("pdf_url"),
            "confidence_score": synthesis["confidence"]
        }
    
    def _parse_user_intent(self, query: str) -> Dict[str, Any]:
        """
        Extract key information from user query
        Example: "Find repurposing opportunities for Montelukast in asthma"
        Returns: {"molecule": "Montelukast", "disease": "asthma", "goal": "repurposing"}
        """
        # Simple keyword extraction (in production, use NER or LLM-based extraction)
        intent = {
            "molecule": None,
            "disease": None,
            "goal": "repurposing",
            "raw_query": query
        }
        
        # Basic extraction logic (can be enhanced with spaCy NER)
        query_lower = query.lower()
        
        # Common molecule patterns
        if "montelukast" in query_lower:
            intent["molecule"] = "Montelukast"
        elif "metformin" in query_lower:
            intent["molecule"] = "Metformin"
        elif "aspirin" in query_lower:
            intent["molecule"] = "Aspirin"
        
        # Disease extraction
        if "asthma" in query_lower:
            intent["disease"] = "asthma"
        elif "diabetes" in query_lower:
            intent["disease"] = "diabetes"
        elif "respiratory" in query_lower:
            intent["disease"] = "respiratory diseases"
        
        return intent
    
    def _plan_research_workflow(self, intent: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Define the sequence of Worker Agents to invoke
        """
        # Standard workflow for drug repurposing
        workflow = [
            {"agent": "iqvia", "priority": "critical"},
            {"agent": "patent", "priority": "critical"},
            {"agent": "clinical_trials", "priority": "high"},
            {"agent": "exim", "priority": "medium"},
            {"agent": "internal_knowledge", "priority": "medium"},
            {"agent": "web_intelligence", "priority": "low"},
        ]
        return workflow
    
    def _evaluate_market_attractiveness(self, market_data: Dict) -> bool:
        """
        Decision Logic: Is the market attractive enough?
        Checks: Market size, growth rate, competition
        """
        try:
            market_size = market_data.get("market_size_usd_million", 0)
            cagr = market_data.get("cagr_percent", 0)
            
            if market_size < self.decision_thresholds["min_market_size_million_usd"]:
                return False
            if cagr < self.decision_thresholds["min_cagr_percent"]:
                return False
            
            return True
        except Exception:
            return True  # Default to continue if data incomplete
    
    def _evaluate_patent_landscape(self, patent_data: Dict) -> bool:
        """
        Decision Logic: Is there Freedom to Operate?
        Checks: Active patents, FTO risk score
        """
        try:
            fto_risk_score = patent_data.get("fto_risk_score", 5)  # 1-10 scale
            
            if fto_risk_score > self.decision_thresholds["max_patent_risk_score"]:
                return False
            
            return True
        except Exception:
            return True
    
    def _evaluate_clinical_viability(self, clinical_data: Dict) -> bool:
        """
        Decision Logic: Is the clinical space too saturated?
        Checks: Number of active trials, phase distribution
        """
        try:
            active_trials = clinical_data.get("total_active_trials", 0)
            
            if active_trials > self.decision_thresholds["max_clinical_saturation"]:
                return False
            
            return True
        except Exception:
            return True
    
    def _synthesize_findings(self, findings: Dict, decision_flags: Dict) -> Dict[str, Any]:
        """
        Synthesize all Worker Agent findings into a coherent summary
        """
        # Determine overall decision
        if all(decision_flags.values()):
            decision = "GO"
            confidence = 85
        elif decision_flags["market_attractive"] and decision_flags["patents_clear"]:
            decision = "PARTIAL_GO"
            confidence = 65
        else:
            decision = "NO_GO"
            confidence = 40
        
        # Build reasoning
        reasoning_parts = []
        
        if decision_flags["market_attractive"]:
            reasoning_parts.append("✓ Market shows attractive size and growth")
        else:
            reasoning_parts.append("✗ Market too small or low growth")
        
        if decision_flags["patents_clear"]:
            reasoning_parts.append("✓ Patent landscape favorable for FTO")
        else:
            reasoning_parts.append("✗ Patent risks identified")
        
        if decision_flags["clinical_viable"]:
            reasoning_parts.append("✓ Clinical space has room for innovation")
        else:
            reasoning_parts.append("✗ Clinical space highly saturated")
        
        return {
            "decision": decision,
            "reasoning": " | ".join(reasoning_parts),
            "confidence": confidence,
            "summary": self._build_summary_text(findings)
        }
    
    def _build_summary_text(self, findings: Dict) -> str:
        """Build a human-readable summary of all findings"""
        summary_lines = []
        
        for agent_name, result in findings.items():
            if agent_name.startswith("_"):
                continue
            summary_lines.append(f"\n**{agent_name.upper()} Analysis:**")
            summary_lines.append(str(result))
        
        return "\n".join(summary_lines)
    
    def _build_rejection_response(self, reason: str, findings: Dict) -> Dict[str, Any]:
        """Build response for early rejection"""
        return {
            "decision": "NO_GO",
            "reasoning": f"Early stop: {reason}",
            "findings": findings,
            "synthesis": f"Research terminated early due to: {reason}",
            "report_url": None,
            "confidence_score": 30
        }
