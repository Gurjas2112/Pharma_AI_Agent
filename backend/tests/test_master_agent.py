import asyncio
import unittest

from agents.master_agent import MasterAgent


class FakeAgent:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class MasterAgentTests(unittest.TestCase):
    def test_graph_runs_research_and_reports(self):
        graph = MasterAgent(llm_config={})
        for name in graph.RESEARCH_STEPS:
            result = {"source": name}
            if name == "iqvia":
                result.update(market_size_usd_million=100, cagr_percent=4)
            elif name == "patent":
                result["fto_risk_score"] = 6
            elif name == "clinical_trials":
                result["total_active_trials"] = 10
            graph.register_worker_agent(name, FakeAgent(result))
        report = FakeAgent({"pdf_url": "/reports/test-report.pdf"})
        graph.register_worker_agent("report_generator", report)

        result = asyncio.run(graph.process_query("Montelukast for asthma"))

        self.assertEqual(result["decision"], "GO")
        self.assertEqual(
            result["findings"]["clinical_trials"]["source"], "clinical_trials"
        )
        self.assertEqual(
            result["findings"]["clinical_trials"]["total_active_trials"], 10
        )
        self.assertEqual(result["report_url"], "/reports/test-report.pdf")
        self.assertTrue(
            all(
                agent.calls[0]["molecule"] == "Montelukast"
                for name, agent in graph.worker_agents.items()
                if name != "report_generator"
            )
        )
        self.assertEqual(report.calls[0]["synthesis"]["decision"], "GO")

    def test_missing_market_data_does_not_create_false_no_go(self):
        graph = MasterAgent(llm_config={})

        self.assertIsNone(
            graph._evaluate_market_attractiveness(
                {"error": "market source unavailable"}
            )
        )

    def test_incomplete_evidence_requires_review(self):
        graph = MasterAgent(llm_config={})

        synthesis = graph._synthesize_findings(
            {},
            {
                "market_attractive": None,
                "patents_clear": None,
                "clinical_viable": None,
            },
        )

        self.assertEqual(synthesis["decision"], "REVIEW")

    def test_known_failed_market_threshold_returns_no_go(self):
        graph = MasterAgent(llm_config={})

        self.assertFalse(
            graph._evaluate_market_attractiveness(
                {"market_size_usd_million": 20, "cagr_percent": 5}
            )
        )

    def test_follow_up_query_reuses_prior_molecule(self):
        graph = MasterAgent(llm_config={})
        agents = {}
        for name in graph.RESEARCH_STEPS:
            agents[name] = FakeAgent({"source": name})
            graph.register_worker_agent(name, agents[name])

        result = asyncio.run(
            graph.process_query(
                "What about cancer?",
                conversation_history=[
                    {"role": "user", "content": "Assess Montelukast"}
                ],
            )
        )

        self.assertTrue(
            all(agent.calls[0]["molecule"] == "Montelukast" for agent in agents.values())
        )
        self.assertEqual(result["findings"]["clinical_trials"], {"source": "clinical_trials"})
