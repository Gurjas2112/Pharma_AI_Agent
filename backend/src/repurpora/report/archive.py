"""Archival system: Supabase Storage (primary) + S3 (LocalStack in prototype)
+ ``reports`` metadata table + local disk fallback."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from repurpora.settings import get_settings
from repurpora.vault import get_secret

log = logging.getLogger(__name__)


def _sb_headers(content_type: str | None = None) -> dict[str, str]:
    key = get_secret("SUPABASE_SECRET_KEY") or get_settings().supabase_secret_key
    h = {"apikey": key or "", "Authorization": f"Bearer {key}"}
    if content_type:
        h["Content-Type"] = content_type
    return h


def upload_supabase(path: str, data: bytes, content_type: str) -> bool:
    s = get_settings()
    if not s.supabase_url:
        return False
    try:
        r = httpx.post(f"{s.supabase_url}/storage/v1/object/{s.reports_bucket}/{path}",
                       headers={**_sb_headers(content_type), "x-upsert": "true"}, content=data, timeout=30)
        r.raise_for_status()
        return True
    except Exception as exc:
        log.warning("supabase upload failed: %s", exc)
        return False


def signed_url(path: str, expires: int = 7 * 24 * 3600) -> str | None:
    s = get_settings()
    if not s.supabase_url:
        return None
    try:
        r = httpx.post(f"{s.supabase_url}/storage/v1/object/sign/{s.reports_bucket}/{path}",
                       headers=_sb_headers("application/json"), json={"expiresIn": expires}, timeout=15)
        r.raise_for_status()
        return f"{s.supabase_url}/storage/v1{r.json()['signedURL']}"
    except Exception as exc:
        log.warning("sign url failed: %s", exc)
        return None


def upload_s3(key: str, data: bytes, content_type: str) -> bool:
    s = get_settings()
    if not s.aws_endpoint_url:
        return False
    try:
        import boto3

        boto3.client("s3", endpoint_url=s.aws_endpoint_url, region_name=s.aws_region).put_object(
            Bucket=s.aws_reports_bucket, Key=key, Body=data, ContentType=content_type,
            ServerSideEncryption="AES256")
        return True
    except Exception as exc:
        log.info("s3 mirror skipped: %s", type(exc).__name__)
        return False


def save_metadata(row: dict[str, Any]) -> None:
    from psycopg.types.json import Jsonb

    from repurpora.db import conn

    try:
        with conn() as c:
            c.execute(
                "insert into reports(report_id, owner, thread_id, query, molecule, indication, decision, confidence,"
                " ml_score, evidence_coverage, storage_path, excel_path, s3_key, findings) values"
                " (%(report_id)s,%(owner)s,%(thread_id)s,%(query)s,%(molecule)s,%(indication)s,%(decision)s,"
                " %(confidence)s,%(ml_score)s,%(coverage)s,%(storage_path)s,%(excel_path)s,%(s3_key)s,%(findings)s)"
                " on conflict (report_id) do nothing",
                {**row, "findings": Jsonb(row.get("findings", {}))},
            )
    except Exception as exc:
        log.warning("report metadata insert failed: %s", exc)


def archive(report_id: str, owner: str | None, pdf: bytes, xlsx: bytes, meta: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    folder = f"{owner or 'anonymous'}/{report_id}"
    pdf_path, xls_path = f"{folder}/report.pdf", f"{folder}/report.xlsx"
    (s.reports_dir / f"{report_id}.pdf").write_bytes(pdf)
    (s.reports_dir / f"{report_id}.xlsx").write_bytes(xlsx)
    sb_pdf = upload_supabase(pdf_path, pdf, "application/pdf")
    sb_xls = upload_supabase(xls_path, xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    s3_ok = upload_s3(f"reports/{folder}/report.pdf", pdf, "application/pdf")
    pdf_url = signed_url(pdf_path) if sb_pdf else None
    xls_url = signed_url(xls_path) if sb_xls else None
    save_metadata({**meta, "report_id": report_id, "owner": owner, "storage_path": pdf_path if sb_pdf else None,
                   "excel_path": xls_path if sb_xls else None, "s3_key": f"reports/{folder}/report.pdf" if s3_ok else None})
    return {"report_id": report_id, "pdf_url": pdf_url, "excel_url": xls_url, "supabase": sb_pdf, "s3_mirror": s3_ok,
            "local_path": str(s.reports_dir / f"{report_id}.pdf")}


def signed_url_for(report_id: str) -> str | None:
    from repurpora.db import conn

    try:
        with conn() as c:
            row = c.execute("select storage_path from reports where report_id=%s", (report_id,)).fetchone()
        return signed_url(row[0]) if row and row[0] else None
    except Exception:
        return None
