"""Evidence layer.

Every fact a worker produces is wrapped in an :class:`Evidence` record with
provenance (source, url, content hash, retrieval time, trust tier). The
synthesizer must cite ``[E#]`` ids and the judge measures evidence coverage =
supported claims / total claims (reference image 20).
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

Trust = Literal["internal", "regulatory", "registry", "licensed_db", "web", "synthetic"]


class Evidence(BaseModel):
    id: str = ""  # assigned at merge time: E1, E2 ...
    agent: str
    source: str  # e.g. "IQVIA (mock)", "ClinicalTrials.gov v2"
    title: str
    snippet: str
    url: str | None = None
    trust: Trust = "synthetic"
    retrieved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    sha256: str = ""

    def model_post_init(self, __context) -> None:  # noqa: D401
        if not self.sha256:
            self.sha256 = hashlib.sha256(
                f"{self.source}|{self.url}|{self.snippet}".encode()
            ).hexdigest()[:16]


def number_evidence(items: list[Evidence]) -> list[Evidence]:
    """De-duplicate by hash and assign stable E# ids."""
    seen: set[str] = set()
    out: list[Evidence] = []
    for ev in items:
        if ev.sha256 in seen:
            continue
        seen.add(ev.sha256)
        out.append(ev.model_copy(update={"id": f"E{len(out) + 1}"}))
    return out


def evidence_digest(items: list[Evidence], max_chars: int = 220) -> str:
    """Compact, token-budgeted rendering of the evidence for prompts."""
    lines = []
    for ev in items:
        snip = ev.snippet.replace("\n", " ")
        if len(snip) > max_chars:
            snip = snip[: max_chars - 1] + "…"
        lines.append(f"[{ev.id}] ({ev.agent} · {ev.source}) {ev.title}: {snip}")
    return "\n".join(lines)


_CITE = re.compile(r"\[(E\d+)\]")


def split_claims(text: str) -> list[str]:
    """Rough claim segmentation: sentences / bullet lines carrying content."""
    # move trailing citations in front of the terminator: "x. [E1]" -> "x [E1]."
    text = re.sub(r"([.!?])[ \t]*((?:\[E\d+\][ \t,]*)+)", lambda m: " " + m.group(2).strip(" ,") + m.group(1) + " ", text)
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    claims = []
    for p in parts:
        p = p.strip(" -*•#|")
        if len(p) < 25 or p.lower().startswith(("note", "disclaimer")):
            continue
        if p.count("|") > 2:  # table rows are data, cited at table level
            continue
        claims.append(p)
    return claims


def coverage(text: str, valid_ids: set[str]) -> tuple[float, list[str]]:
    """Return (evidence coverage, list of uncited claims)."""
    claims = split_claims(text)
    if not claims:
        return 1.0, []
    uncited = []
    supported = 0
    for c in claims:
        ids = set(_CITE.findall(c))
        if ids and ids <= valid_ids:
            supported += 1
        else:
            uncited.append(c)
    return supported / len(claims), uncited


_NUM = re.compile(r"\d+(?:\.\d+)?")
_WORD = re.compile(r"[a-z][a-z\-]{3,}")
_STOP = {"with", "that", "this", "from", "have", "which", "their", "there", "into", "than", "more", "also",
         "market", "india", "opportunity", "significant", "potential"}


def attribute_citations(text: str, items: list[Evidence], min_overlap: float = 0.3) -> tuple[str, int]:
    """Post-hoc attribution: append [E#] to uncited claims that an evidence snippet clearly supports.

    A claim is attributed only when every number it states appears in the snippet AND its content-word
    overlap with the snippet is >= ``min_overlap``. Unsupported claims stay uncited (and trigger redraft).
    Returns (text, n_attributed).
    """
    if not items:
        return text, 0
    ev_tokens = []
    for e in items:
        blob = f"{e.title} {e.snippet}".lower()
        ev_tokens.append((e.id, set(_NUM.findall(blob)), set(_WORD.findall(blob)) - _STOP))
    added = 0
    out_lines = []
    for line in text.split("\n"):
        if line.lstrip().startswith(("#", "|")) or not line.strip():
            out_lines.append(line)
            continue
        sents = re.split(r"(?<=[.!?])\s+", line)
        new_sents = []
        for s in sents:
            if _CITE.search(s) or len(s) < 25:
                new_sents.append(s)
                continue
            low = s.lower()
            nums = set(_NUM.findall(low))
            words = set(_WORD.findall(low)) - _STOP
            best, best_score = None, 0.0
            for eid, enums, ewords in ev_tokens:
                if nums and not nums <= enums:
                    continue
                if not words:
                    continue
                score = len(words & ewords) / len(words)
                if score > best_score:
                    best, best_score = eid, score
            if best and best_score >= min_overlap:
                m = re.match(r"^(.*?)([.!?]?)$", s.rstrip())
                s = f"{m.group(1)} [{best}]{m.group(2)}"
                added += 1
            new_sents.append(s)
        out_lines.append(" ".join(new_sents))
    return "\n".join(out_lines), added


def citation_accuracy(text: str, valid_ids: set[str]) -> float:
    cited = _CITE.findall(text)
    if not cited:
        return 0.0
    return sum(1 for c in cited if c in valid_ids) / len(cited)
