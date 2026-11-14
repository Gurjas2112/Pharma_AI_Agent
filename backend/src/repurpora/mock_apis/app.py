"""Mock data-source server (deployed as its own Railway service).

Endpoints mirror the problem statement's mock sources. Also hosts the
report-download proxy and the internal-document upload endpoint used by the UI.
"""

from __future__ import annotations

import contextlib  # noqa: E402
import os

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from repurpora.admin.api import router as admin_router  # noqa: E402
from repurpora.mcp_server import asgi_app as mcp_asgi_app  # noqa: E402
from repurpora.mock_apis import data

_mcp, _mcp_app = mcp_asgi_app()


@contextlib.asynccontextmanager
async def lifespan(_app):
    async with _mcp.session_manager.run():  # MCP streamable-HTTP session manager
        yield


app = FastAPI(title="Repurpora aux service: mock data sources, uploads, admin API, MCP server",
              version="1.1.0", lifespan=lifespan)
app.include_router(admin_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def _api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("MOCK_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid api key")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mock-apis"}


@app.get("/iqvia/market", dependencies=[Depends(_api_key)])
def iqvia(molecule: str | None = None, therapy_area: str | None = None, region: str = "India",
          indications: str | None = None):
    return data.iqvia_market(molecule, therapy_area, region, indications)


@app.get("/exim/trade", dependencies=[Depends(_api_key)])
def exim(molecule: str, country: str = "India"):
    return data.exim_trade(molecule, country)


@app.get("/uspto/patents", dependencies=[Depends(_api_key)])
def uspto(molecule: str, indication: str | None = None):
    return data.uspto_patents(molecule, indication)


@app.get("/trials/search", dependencies=[Depends(_api_key)])
def trials(molecule: str, condition: str | None = None):
    return data.trials(molecule, condition)


@app.get("/web/search", dependencies=[Depends(_api_key)])
def web(q: str = Query(..., min_length=2), k: int = 5):
    return data.web_search(q, k)


@app.get("/molecule/profile", dependencies=[Depends(_api_key)])
def profile(molecule: str):
    return data.molecule_profile(molecule)


@app.get("/reports/{report_id}/url")
def report_url(report_id: str, authorization: str | None = Header(default=None)):
    """Return a fresh signed URL for an archived report (Supabase Storage)."""
    from repurpora.report.archive import signed_url_for

    url = signed_url_for(report_id)
    if not url:
        raise HTTPException(404, "report not found")
    return {"report_id": report_id, "url": url}


@app.post("/documents/upload")
async def upload(file: UploadFile = File(...), authorization: str | None = Header(default=None)):
    """Ingest an internal PDF (optional PS feature) into the RAG index."""
    from repurpora.auth import user_from_bearer
    from repurpora.rag.ingest import ingest_pdf_bytes

    user = user_from_bearer(authorization)
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "only PDF files are accepted")
    raw = await file.read()
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(413, "file too large (15MB max)")
    n = ingest_pdf_bytes(raw, file.filename or "upload.pdf", owner=user)
    return {"status": "ingested", "file": file.filename, "chunks": n}


# MCP (Streamable HTTP at /mcp + /.well-known/oauth-protected-resource). Mounted last so FastAPI routes win.
app.mount("/", _mcp_app)
