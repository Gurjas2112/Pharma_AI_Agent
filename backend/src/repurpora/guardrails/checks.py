"""Input / content / output guardrails (reference images 1, 5, 18).

* ``scan_input``     - prompt-injection + jailbreak heuristics, length cap, scope.
* ``sanitize_untrusted`` - neutralises instructions embedded in retrieved web /
  document content and tags it untrusted before it reaches a prompt.
* ``dlp_redact``     - removes secrets and PII from model output.
* ``authorize_tool`` - policy gateway: per-agent tool allow-list + call budget.

Deterministic, dependency-free and fast so they run on every turn; the
regex layer is complemented by the LLM judge downstream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

INJECTION_PATTERNS = [
    r"ignore (all|any|the)?\s*(previous|prior|above) (instructions|prompts|rules)",
    r"disregard (the|your|all) (system|previous|above)",
    r"you are now (?:in )?(dan|developer mode|jailbreak)",
    r"reveal (your|the) (system prompt|instructions|hidden)",
    r"print (your|the) (system prompt|secret|api key|env)",
    r"(system|assistant)\s*:\s*you must",
    r"<\s*/?\s*(system|instructions?)\s*>",
    r"act as (?:an? )?unrestricted",
    r"exfiltrate|send (?:the )?(?:data|keys?) to http",
    r"base64 decode and (run|execute)",
]
_INJ = [re.compile(p, re.I) for p in INJECTION_PATTERNS]

HARMFUL_PATTERNS = [
    r"synthesi[sz]e (?:a )?(?:nerve agent|sarin|vx|ricin|fentanyl analog)",
    r"(make|cook|produce) (?:meth|methamphetamine|heroin)",
    r"lethal dose to (kill|poison)",
    r"evade (fda|regulator|detection)",
]
_HARM = [re.compile(p, re.I) for p in HARMFUL_PATTERNS]

SECRET_PATTERNS = {
    "api_key": re.compile(r"\b(sk|fc|rlwy|sb_secret|sb_publishable|lsv2)[-_][A-Za-z0-9_\-]{12,}\b"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "jwt": re.compile(r"(?<![?&]token=)\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    "pg_url": re.compile(r"postgres(?:ql)?://[^\s]+:[^\s]+@[^\s]+"),
}
PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?\d{10}(?!\d)"),
    "aadhaar": re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}

DOMAIN_HINTS = re.compile(
    r"molecule|drug|repurpos|indication|disease|patent|trial|market|iqvia|exim|api\b|formulation|"
    r"dosage|therap|pharma|clinical|fto|generic|cagr|competition|patient|import|export|report|"
    r"guideline|mechanism|moa|unmet|portfolio|respiratory|oncology|cardio|diabet|asthma|copd|"
    r"tablet|injection|inhal|paediatric|pediatric|biosimilar|regulatory|fda|cdsco|ema|hello|hi\b|help|remember|memory|history|forget",
    re.I,
)


@dataclass
class GuardResult:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    risk: float = 0.0
    sanitized: str = ""


def scan_input(text: str, max_chars: int = 4000) -> GuardResult:
    reasons: list[str] = []
    risk = 0.0
    if len(text) > max_chars:
        reasons.append(f"input exceeds {max_chars} chars")
        text = text[:max_chars]
        risk += 0.2
    if any(p.search(text) for p in _INJ):
        reasons.append("prompt-injection attempt detected")
        risk += 0.6
    if any(p.search(text) for p in _HARM):
        reasons.append("harmful-use request")
        risk += 1.0
    mostly_ascii = sum(ch.isascii() for ch in text) >= 0.8 * max(len(text), 1)
    # the keyword scope check is English-only; other languages are scoped by the LLM planner instead
    if not reasons and mostly_ascii and not DOMAIN_HINTS.search(text) and len(text.split()) > 6:
        reasons.append("off-topic for pharmaceutical portfolio research")
        risk += 0.6
    return GuardResult(allowed=risk < 0.6, reasons=reasons, risk=min(risk, 1.0), sanitized=text)


def sanitize_untrusted(text: str) -> str:
    """Strip instruction-like spans from retrieved content (indirect injection)."""
    out = text
    for p in _INJ:
        out = p.sub("[removed: instruction-like content]", out)
    out = re.sub(r"(?i)\b(system|assistant|user)\s*:", r"\1 -", out)
    return out


def dlp_redact(text: str) -> tuple[str, list[str]]:
    found: list[str] = []
    for name, p in SECRET_PATTERNS.items():
        if p.search(text):
            found.append(name)
            text = p.sub(f"[REDACTED:{name}]", text)
    for name, p in PII_PATTERNS.items():
        if p.search(text):
            found.append(name)
            text = p.sub(f"[REDACTED:{name}]", text)
    return text, found


# ----------------------------- policy gateway -------------------------------

TOOL_ALLOWLIST: dict[str, set[str]] = {
    "iqvia": {"iqvia_market", "molecule_profile"},
    "exim": {"exim_trade"},
    "patent": {"uspto_patents"},
    "clinical_trials": {"clinical_trials"},
    "internal": {"rag_search"},
    "web": {"web_search"},
    "report": {"render_pdf", "render_excel", "archive"},
}
MAX_TOOL_CALLS_PER_AGENT = 4


def authorize_tool(agent: str, tool: str, calls_so_far: int) -> tuple[bool, str]:
    if tool not in TOOL_ALLOWLIST.get(agent, set()):
        return False, f"tool '{tool}' not allow-listed for agent '{agent}'"
    if calls_so_far >= MAX_TOOL_CALLS_PER_AGENT:
        return False, f"tool-call budget exhausted for agent '{agent}'"
    return True, "allow"
