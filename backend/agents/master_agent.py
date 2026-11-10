"""LangGraph-based orchestration for the PharmaAI research workflow."""

from operator import or_
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph


class ResearchState(TypedDict, total=False):
    """State shared by the research graph nodes."""

    user_query: str
    conversation_history: List[Dict[str, str]]
    molecule: Optional[str]
    disease: Optional[str]
    findings: Annotated[Dict[str, Any], or_]
    synthesis: Dict[str, Any]
    decision: str
    reasoning: str
    confidence_score: int
    report_url: Optional[str]


class MasterAgent:
    """Coordinates specialist agents as a deterministic, inspectable graph."""

    RESEARCH_STEPS = (
        "iqvia",
        "patent",
        "clinical_trials",
        "exim",
        "internal_knowledge",
        "web_intelligence",
    )

    def __init__(self, llm_config: Dict[str, Any]):
        self.llm_config = llm_config
        self.worker_agents: Dict[str, Any] = {}
        self.decision_thresholds = {
            "min_market_size_million_usd": 50,
            "max_patent_risk_score": 7,
            "max_clinical_saturation": 15,
            "min_cagr_percent": 3,
        }
        self.graph = self._build_graph()

    def register_worker_agent(self, name: str, agent: Any) -> None:
        """Register a specialist or report-generation agent."""
        self.worker_agents[name] = agent

    async def process_query(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Run the research graph and return its final decision and findings."""
        result = await self.graph.ainvoke(
            {
                "user_query": user_query,
                "conversation_history": conversation_history or [],
                "findings": {},
            }
        )
        return {
            "decision": result["decision"],
            "reasoning": result["reasoning"],
            "findings": result["findings"],
            "synthesis": result["synthesis"]["summary"],
            "report_url": result.get("report_url"),
            "confidence_score": result["confidence_score"],
        }

    def _build_graph(self):
        builder = StateGraph(ResearchState)
        builder.add_node("parse_intent", self._parse_intent_node)

        for agent_name in self.RESEARCH_STEPS:
            builder.add_node(
                agent_name,
                self._make_research_node(agent_name),
            )

        builder.add_node("synthesize", self._synthesize_node)
        builder.add_node("generate_report", self._report_node)
        builder.add_edge(START, "parse_intent")

        previous = "parse_intent"
        for agent_name in self.RESEARCH_STEPS:
            builder.add_edge(previous, agent_name)
            previous = agent_name

        builder.add_edge(previous, "synthesize")
        builder.add_edge("synthesize", "generate_report")
        builder.add_edge("generate_report", END)
        return builder.compile()

    async def _parse_intent_node(self, state: ResearchState) -> Dict[str, Any]:
        intent = self._parse_user_intent(
            state["user_query"],
            state.get("conversation_history", []),
        )
        return {"molecule": intent["molecule"], "disease": intent["disease"]}

    def _make_research_node(self, agent_name: str):
        async def run_agent(state: ResearchState) -> Dict[str, Any]:
            agent = self.worker_agents.get(agent_name)
            if agent is None:
                return {
                    "findings": {
                        agent_name: {"error": f"Agent {agent_name} not registered"}
                    }
                }

            result = await agent.execute(
                molecule=state.get("molecule"),
                disease=state.get("disease"),
                context=state.get("findings", {}),
            )
            return {"findings": {agent_name: result}}

        return run_agent

    def _synthesize_node(self, state: ResearchState) -> Dict[str, Any]:
        findings = state.get("findings", {})
        checks = {
            "market_attractive": self._evaluate_market_attractiveness(
                findings.get("iqvia", {})
            ),
            "patents_clear": self._evaluate_patent_landscape(
                findings.get("patent", {})
            ),
            "clinical_viable": self._evaluate_clinical_viability(
                findings.get("clinical_trials", {})
            ),
        }
        synthesis = self._synthesize_findings(findings, checks)
        return {
            "synthesis": synthesis,
            "decision": synthesis["decision"],
            "reasoning": synthesis["reasoning"],
            "confidence_score": synthesis["confidence"],
        }

    async def _report_node(self, state: ResearchState) -> Dict[str, Any]:
        report_agent = self.worker_agents.get("report_generator")
        if report_agent is None:
            return {"report_url": None}

        report_result = await report_agent.execute(
            synthesis=state["synthesis"],
            raw_findings=state.get("findings", {}),
        )
        return {"report_url": report_result.get("pdf_url")}

    def _parse_user_intent(
        self, query: str, conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Optional[str]]:
        def extract(text: str) -> Dict[str, Optional[str]]:
            text_lower = text.lower()
            return {
                "molecule": next(
                    (
                        name
                        for name in ("Montelukast", "Metformin", "Aspirin")
                        if name.lower() in text_lower
                    ),
                    None,
                ),
                "disease": next(
                    (
                        name
                        for name, term in (
                            ("asthma", "asthma"),
                            ("diabetes", "diabetes"),
                            ("respiratory diseases", "respiratory"),
                        )
                        if term in text_lower
                    ),
                    None,
                ),
            }

        intent = extract(query)
        if intent["molecule"] is None or intent["disease"] is None:
            for message in reversed(conversation_history or []):
                if message.get("role") != "user":
                    continue
                previous_intent = extract(message.get("content", ""))
                for key in ("molecule", "disease"):
                    if intent[key] is None:
                        intent[key] = previous_intent[key]
                if intent["molecule"] is not None and intent["disease"] is not None:
                    break
        return intent

    def _evaluate_market_attractiveness(
        self, market_data: Dict[str, Any]
    ) -> Optional[bool]:
        if market_data.get("error"):
            return None

        market_size = market_data.get("market_size_usd_million")
        cagr = market_data.get("cagr_percent")
        if market_size is None or cagr is None:
            return None

        return (
            market_size >= self.decision_thresholds["min_market_size_million_usd"]
            and cagr >= self.decision_thresholds["min_cagr_percent"]
        )

    def _evaluate_patent_landscape(
        self, patent_data: Dict[str, Any]
    ) -> Optional[bool]:
        if patent_data.get("error") or patent_data.get("fto_risk_score") is None:
            return None
        return (
            patent_data["fto_risk_score"]
            <= self.decision_thresholds["max_patent_risk_score"]
        )

    def _evaluate_clinical_viability(
        self, clinical_data: Dict[str, Any]
    ) -> Optional[bool]:
        if (
            clinical_data.get("error")
            or clinical_data.get("total_active_trials") is None
        ):
            return None
        return (
            clinical_data["total_active_trials"]
            <= self.decision_thresholds["max_clinical_saturation"]
        )

    def _synthesize_findings(
        self, findings: Dict[str, Any], checks: Dict[str, Optional[bool]]
    ) -> Dict[str, Any]:
        if checks["market_attractive"] is False:
            decision = "NO_GO"
            confidence = 70
        elif all(value is True for value in checks.values()):
            decision = "GO"
            confidence = 85
        else:
            decision = "REVIEW"
            confidence = 40 + 15 * sum(value is not None for value in checks.values())

        labels = {
            "market_attractive": "Market",
            "patents_clear": "Patent",
            "clinical_viable": "Clinical",
        }
        reasoning = " | ".join(
            f"{labels[key]}: "
            + (
                "favorable"
                if value is True
                else "risk identified"
                if value is False
                else "insufficient data"
            )
            for key, value in checks.items()
        )
        summary_lines = [
            f"**{name.upper()} Analysis:**\n{result}"
            for name, result in findings.items()
        ]
        return {
            "decision": decision,
            "reasoning": reasoning,
            "confidence": confidence,
            "summary": "\n\n".join(summary_lines),
            "evidence_status": checks,
        }
