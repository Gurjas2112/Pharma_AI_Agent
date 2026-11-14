"""Chunking strategies (benchmarked in ``evals/rag_bench.py``).

* ``fixed``     - naive fixed-size character windows (baseline)
* ``recursive`` - paragraph -> sentence -> word recursive splitter, overlap,
                  respects section headings (default for ingestion)
* ``parent``    - small child chunks for matching, mapped to a larger parent
                  window that is returned to the LLM (small-to-big retrieval)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class Chunk:
    content: str
    source: str
    page: int
    index: int
    strategy: str
    parent: str | None = None
    meta: dict = field(default_factory=dict)


_WS = re.compile(r"[ \t]+")
_HEADING = re.compile(r"^(?:\d+(?:\.\d+)*\s+[A-Z][^\n]{3,80}|[A-Z][A-Z \-&]{4,60})$", re.M)


def clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"-\n(\w)", r"\1", text)  # de-hyphenate line breaks
    text = _WS.sub(" ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fixed(pages: list[tuple[int, str]], source: str, size: int = 1000, overlap: int = 0) -> list[Chunk]:
    out: list[Chunk] = []
    for page, txt in pages:
        txt = clean(txt)
        step = max(1, size - overlap)
        for i in range(0, len(txt), step):
            piece = txt[i:i + size]
            if len(piece) > 80:
                out.append(Chunk(piece, source, page, len(out), "fixed"))
    return out


def recursive(pages: list[tuple[int, str]], source: str, size: int = 1200, overlap: int = 180) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size, chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
    )
    out: list[Chunk] = []
    for page, txt in pages:
        txt = clean(txt)
        heading = None
        if m := _HEADING.search(txt):
            heading = m.group(0).strip()[:80]
        for piece in splitter.split_text(txt):
            if len(piece) < 80:
                continue
            content = f"[{heading}] {piece}" if heading and heading not in piece[:100] else piece
            out.append(Chunk(content, source, page, len(out), "recursive", meta={"heading": heading}))
    return out


def parent_child(pages: list[tuple[int, str]], source: str, child: int = 400, parent: int = 1600) -> list[Chunk]:
    parent_split = RecursiveCharacterTextSplitter(chunk_size=parent, chunk_overlap=100)
    child_split = RecursiveCharacterTextSplitter(chunk_size=child, chunk_overlap=60)
    out: list[Chunk] = []
    for page, txt in pages:
        for p in parent_split.split_text(clean(txt)):
            for c in child_split.split_text(p):
                if len(c) >= 60:
                    out.append(Chunk(c, source, page, len(out), "parent", parent=p))
    return out


STRATEGIES = {"fixed": fixed, "recursive": recursive, "parent": parent_child}
