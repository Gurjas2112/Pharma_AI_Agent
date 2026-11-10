"""Chainlit chat interface backed by the PharmaAI LangGraph workflow."""

import os
from pathlib import Path
from typing import Any, Dict

import chainlit as cl
from dotenv import load_dotenv

from agents.master_agent import MasterAgent
from agents.iqvia_agent import IQVIAAgent
from agents.exim_agent import EXIMAgent
from agents.patent_agent import PatentAgent
from agents.clinical_trials_agent import ClinicalTrialsAgent
from agents.internal_kb_agent import InternalKnowledgeAgent
from agents.web_intel_agent import WebIntelligenceAgent
from agents.report_agent import ReportGeneratorAgent
from services.supabase_client import supabase_service
from services.embedding_service import embedding_service


load_dotenv()

llm_config: Dict[str, Any] = {
    "model": os.getenv("LLM_MODEL", "mistral"),
    "temperature": 0.7,
    "max_tokens": 2000,
}

research_graph = MasterAgent(llm_config=llm_config)
report_generator = ReportGeneratorAgent(llm_config=llm_config)
research_graph.register_worker_agent("iqvia", IQVIAAgent(llm_config=llm_config))
research_graph.register_worker_agent("exim", EXIMAgent(llm_config=llm_config))
research_graph.register_worker_agent("patent", PatentAgent(llm_config=llm_config))
research_graph.register_worker_agent(
    "clinical_trials", ClinicalTrialsAgent(llm_config=llm_config)
)
research_graph.register_worker_agent(
    "internal_knowledge",
    InternalKnowledgeAgent(
        llm_config=llm_config,
        supabase_client=(
            supabase_service.get_client()
            if supabase_service.is_configured()
            else None
        ),
        embedding_service=embedding_service,
    ),
)
research_graph.register_worker_agent(
    "web_intelligence", WebIntelligenceAgent(llm_config=llm_config)
)
research_graph.register_worker_agent("report_generator", report_generator)


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("conversation_history", [])
    await cl.Message(
        content=(
            "Welcome to PharmaAI. Ask about drug repurposing, clinical trials, "
            "patents, or pharmaceutical supply-chain research. Research findings "
            "are decision support, not medical or legal advice."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    history = cl.user_session.get("conversation_history", [])
    result = await research_graph.process_query(
        user_query=message.content,
        conversation_history=history,
    )

    content = (
        f"**Decision:** {result['decision']}  \n"
        f"**Evidence confidence:** {result['confidence_score']}%  \n\n"
        f"**Assessment:** {result['reasoning']}  \n\n"
        f"{result['synthesis']}"
    )
    elements = []
    report_url = result.get("report_url")
    if report_url:
        report_path = Path(report_generator.output_directory) / Path(report_url).name
        if report_path.is_file():
            elements.append(
                cl.File(
                    name=report_path.name,
                    path=str(report_path),
                    display="inline",
                )
            )
        else:
            content += "\n\n_Report file was not found in the local reports directory._"

    await cl.Message(content=content, elements=elements).send()
    history.extend(
        [
            {"role": "user", "content": message.content},
            {"role": "assistant", "content": content},
        ]
    )
    cl.user_session.set("conversation_history", history)
