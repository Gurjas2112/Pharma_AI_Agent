"""Run a small, deterministic benchmark for PharmaAI's evidence decision policy."""

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from agents.master_agent import MasterAgent


CASES_PATH = Path(__file__).with_name("decision_cases.json")


def evaluate_cases(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate expected decisions and report accuracy and runtime."""
    agent = MasterAgent(llm_config={})
    results = []

    for case in cases:
        findings = case["findings"]
        checks = {
            "market_attractive": agent._evaluate_market_attractiveness(
                findings.get("iqvia", {})
            ),
            "patents_clear": agent._evaluate_patent_landscape(
                findings.get("patent", {})
            ),
            "clinical_viable": agent._evaluate_clinical_viability(
                findings.get("clinical_trials", {})
            ),
        }

        started = time.perf_counter()
        actual = agent._synthesize_findings(findings, checks)["decision"]
        elapsed_ms = (time.perf_counter() - started) * 1000
        expected = case["expected_decision"]
        results.append(
            {
                "name": case["name"],
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
                "elapsed_ms": round(elapsed_ms, 3),
            }
        )

    total = len(results)
    passed = sum(result["passed"] for result in results)
    return {
        "benchmark": "evidence_decision_policy",
        "scope": "synthetic fixtures; policy behavior only, not LLM or clinical validation",
        "cases": total,
        "passed": passed,
        "accuracy": passed / total if total else 0.0,
        "mean_latency_ms": (
            round(sum(result["elapsed_ms"] for result in results) / total, 3)
            if total
            else 0.0
        ),
        "results": results,
    }


def main() -> int:
    with CASES_PATH.open(encoding="utf-8") as cases_file:
        cases = json.load(cases_file)
    report = evaluate_cases(cases)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] == report["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
