"""Ingest internal knowledge PDFs into the RAG index (Supabase pgvector + local mirror).

usage: uv run python scripts/ingest.py [--dir data/internal_docs] [--max-pages 120]
"""
import argparse
import json
import logging
import time
from pathlib import Path

from repurpora.rag.ingest import ingest_dir
from repurpora.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
for noisy in ("httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
ap = argparse.ArgumentParser()
ap.add_argument("--dir", default=str(get_settings().internal_docs_dir))
ap.add_argument("--max-pages", type=int, default=120)
a = ap.parse_args()
t0 = time.time()
stats = ingest_dir(Path(a.dir), max_pages=a.max_pages)
print(json.dumps(stats, indent=2), f"\nelapsed {time.time() - t0:.0f}s")
