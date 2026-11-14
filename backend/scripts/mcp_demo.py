"""Record a real MCP client session against the deployed MCP server.

Writes app_screenshots_screen_recording/mcp_session_transcript.md (+ .html for a screenshot).
usage: MCP_URL=https://<aux>/mcp DEMO_USER_EMAIL=... DEMO_USER_PASSWORD=... uv run python scripts/mcp_demo.py
"""

import asyncio
import html
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from repurpora.settings import get_settings

OUT = Path(__file__).resolve().parents[2] / "app_screenshots_screen_recording"
URL = os.environ["MCP_URL"]
CALLS = [
    ("patent_landscape", {"molecule": "colchicine"}),
    ("opportunity_score", {"fto_risk": 2, "unmet_need": 0.8, "evidence_strength": 0.7, "region": "India",
                           "innovation_type": "new_dosage_form"}),
    ("my_reports", {"question": "how many reports per decision"}),
]


def summarise(name: str, d: dict) -> str:
    if name == "patent_landscape":
        active = [p for p in d["patents"] if p["status"] == "Active"]
        return f"{d['source']}: {len(d['patents'])} filings, {len(active)} active"
    if name == "opportunity_score":
        return (f"p(success) = {d['probability']:.2f} (label {d['label']} at threshold {d['threshold']:.2f}, "
                f"model {d['model']}); top drivers: " + ", ".join(f"{f} {v:+.3f}" for f, v in d["drivers"][:3])
                + f"; imputed: {len(d['imputed_fields'])} fields")
    if name == "my_reports":
        return f"{d['rows']} row(s) for the caller only · SQL: {d['sql']}"
    return json.dumps(d)[:200]


async def main() -> None:
    s = get_settings()
    tok = httpx.post(f"{s.supabase_url}/auth/v1/token?grant_type=password",
                     headers={"apikey": s.supabase_publishable_key},
                     json={"email": os.environ["DEMO_USER_EMAIL"], "password": os.environ["DEMO_USER_PASSWORD"]},
                     timeout=30).json()["access_token"]
    base = URL.rsplit("/mcp", 1)[0]
    prm = httpx.get(f"{base}/.well-known/oauth-protected-resource/mcp", timeout=30).json()
    no_auth = httpx.post(URL, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                         headers={"accept": "application/json, text/event-stream"}, timeout=30)
    lines = [f"# MCP client session against the deployed server",
             f"_Recorded {datetime.now(UTC):%Y-%m-%d %H:%M} UTC with the official `mcp` Python client "
             f"(Streamable HTTP) - endpoint `{URL}`_", "",
             "## 1. Discovery and auth",
             f"- Request without a token → **HTTP {no_auth.status_code}** "
             f"(`WWW-Authenticate: {no_auth.headers.get('www-authenticate', '')[:90]}…`)",
             f"- Protected-resource metadata: `{json.dumps(prm)}`",
             "- Client then authenticates with a Supabase access token (bearer) issued to the demo analyst account.", ""]
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {tok}"}, timeout=120) as hc:
        async with streamable_http_client(URL, http_client=hc) as (r, w, *_):
            async with ClientSession(r, w) as sess:
                init = await sess.initialize()
                lines += [f"## 2. Initialize\nServer `{init.server_info.name}` v{init.server_info.version}", ""]
                tools = (await sess.list_tools()).tools
                lines += ["## 3. tools/list", "| tool | title | read-only |", "|---|---|---|"]
                lines += [f"| `{t.name}` | {t.title or ''} | {bool(t.annotations and t.annotations.read_only_hint)} |"
                          for t in tools]
                lines += ["", "## 4. tools/call"]
                for name, args in CALLS:
                    res = await sess.call_tool(name, args)
                    d = json.loads(res.content[0].text)
                    lines += [f"**`{name}`** `{json.dumps(args)}`", f"→ {summarise(name, d)}", ""]
    lines += ["Every call above is recorded in the audit log as `mcp_tool_call` (see screenshot 24)."]
    md = "\n".join(lines) + "\n"
    (OUT / "mcp_session_transcript.md").write_text(md, encoding="utf-8")
    body = "".join(
        f"<h2>{html.escape(ln[3:])}</h2>" if ln.startswith("## ") else
        f"<h1>{html.escape(ln[2:])}</h1>" if ln.startswith("# ") else
        f"<p>{html.escape(ln)}</p>" for ln in lines if ln and not ln.startswith("|"))
    rows = "".join(f"<tr><td><code>{t.name}</code></td><td>{html.escape(t.title or '')}</td>"
                   f"<td>{'✓ read-only' if t.annotations and t.annotations.read_only_hint else ''}</td></tr>"
                   for t in tools)
    body = body.replace("<h2>4. tools/call</h2>",
                        f"<table><tr><th>tool</th><th>title</th><th>annotations</th></tr>{rows}</table><h2>4. tools/call</h2>")
    (OUT / "mcp_session_transcript.html").write_text(f"""<!doctype html><html><head><meta charset="utf-8">
<style>body{{font:14px/1.5 -apple-system,Segoe UI,Inter,sans-serif;background:#0b1226;color:#e2e8f0;padding:32px;max-width:1200px}}
h1{{font-size:22px;color:#5eead4}}h2{{font-size:15px;color:#f5b642;margin-top:22px}}p{{margin:4px 0;font-family:ui-monospace,Consolas,monospace;font-size:12.5px}}
table{{border-collapse:collapse;margin:8px 0}}td,th{{border:1px solid #334155;padding:4px 10px;font-size:12.5px;text-align:left}}code{{color:#93c5fd}}</style>
</head><body>{body}</body></html>""", encoding="utf-8")
    print(md)


asyncio.run(main())
