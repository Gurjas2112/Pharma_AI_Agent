"""Ingestion: PDF -> pages -> chunks -> embeddings -> Supabase pgvector.

A local JSONL mirror (``data/index/chunks.jsonl``) is written too, so retrieval
still works offline / when the database is unreachable.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
from pathlib import Path

from pypdf import PdfReader

from repurpora.rag.chunking import Chunk, recursive
from repurpora.settings import BACKEND_DIR

log = logging.getLogger(__name__)
LOCAL_INDEX = BACKEND_DIR / "data" / "index" / "chunks.jsonl"


def pdf_pages(raw: bytes, max_pages: int = 400) -> list[tuple[int, str]]:
    reader = PdfReader(io.BytesIO(raw))
    pages = []
    for i, p in enumerate(reader.pages[:max_pages]):
        try:
            t = p.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            pages.append((i + 1, t))
    return pages


def embed_chunks(chunks: list[Chunk], batch: int = 32) -> list[list[float]]:
    from repurpora.llm import get_embeddings

    emb = get_embeddings()
    out: list[list[float]] = []
    for i in range(0, len(chunks), batch):
        texts = [f"search_document: {c.content}" for c in chunks[i:i + batch]]
        out.extend(emb.embed_documents(texts))
    return out


def _write_db(doc_sha: str, source: str, owner: str | None, chunks: list[Chunk], vecs: list[list[float]]) -> bool:
    from repurpora.db import conn, vec_literal

    try:
        with conn() as c, c.transaction():
            row = c.execute(
                "insert into rag_documents(sha256, source, owner, n_chunks) values (%s,%s,%s,%s) "
                "on conflict (sha256) do update set n_chunks = excluded.n_chunks returning id",
                (doc_sha, source, owner, len(chunks)),
            ).fetchone()
            doc_id = row[0]
            c.execute("delete from rag_chunks where document_id = %s", (doc_id,))
            with c.cursor() as cur:
                cur.executemany(
                    "insert into rag_chunks(document_id, owner, source, page, chunk_index, strategy, content, "
                    "parent_content, embedding) values (%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)",
                    [(doc_id, owner, source, ch.page, ch.index, ch.strategy, ch.content, ch.parent,
                      vec_literal(v)) for ch, v in zip(chunks, vecs, strict=True)],
                )
        return True
    except Exception as exc:
        log.warning("db write failed for %s: %s", source, exc)
        return False


def _write_local(source: str, owner: str | None, chunks: list[Chunk], vecs: list[list[float]]) -> None:
    LOCAL_INDEX.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if LOCAL_INDEX.exists():
        existing = [ln for ln in LOCAL_INDEX.read_text(encoding="utf-8").splitlines()
                    if json.loads(ln)["source"] != source]
    with LOCAL_INDEX.open("w", encoding="utf-8") as f:
        for ln in existing:
            f.write(ln + "\n")
        for ch, v in zip(chunks, vecs, strict=True):
            f.write(json.dumps({"source": source, "owner": owner, "page": ch.page, "index": ch.index,
                                "content": ch.content, "embedding": [round(x, 5) for x in v]}) + "\n")


def ingest_pdf_bytes(raw: bytes, source: str, owner: str | None = None, max_pages: int = 400) -> int:
    pages = pdf_pages(raw, max_pages=max_pages)
    chunks = recursive(pages, source)
    if not chunks:
        return 0
    vecs = embed_chunks(chunks)
    sha = hashlib.sha256(raw).hexdigest()
    _write_db(sha, source, owner, chunks, vecs)
    _write_local(source, owner, chunks, vecs)
    from repurpora.rag import retriever

    retriever.reset_local_index()
    log.info("ingested %s: %d pages -> %d chunks", source, len(pages), len(chunks))
    return len(chunks)


def ingest_dir(path: Path, max_pages: int = 120) -> dict[str, int]:
    stats = {}
    for pdf in sorted(path.glob("*.pdf")):
        try:
            stats[pdf.name] = ingest_pdf_bytes(pdf.read_bytes(), pdf.name, owner=None, max_pages=max_pages)
        except Exception as exc:
            log.error("failed %s: %s", pdf.name, exc)
            stats[pdf.name] = -1
    return stats
