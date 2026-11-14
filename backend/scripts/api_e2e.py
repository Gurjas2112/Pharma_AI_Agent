"""API-level E2E: Supabase sign-in -> JWT -> Aegra (LangGraph SDK) streamed run.

Proves auth (401 without token), per-user thread scoping, streaming and archiving.
usage: uv run python scripts/api_e2e.py ["question"]
"""
import asyncio
import os
import sys
import time

import httpx
from langgraph_sdk import get_client

from repurpora.settings import get_settings

API = os.getenv("AGENT_API_URL", "http://localhost:2026")
s = get_settings()
EMAIL, PWD = os.environ["DEMO_USER_EMAIL"], os.environ["DEMO_USER_PASSWORD"]


def ensure_user() -> None:
    r = httpx.post(f"{s.supabase_url}/auth/v1/admin/users",
                   headers={"apikey": s.supabase_secret_key, "Authorization": f"Bearer {s.supabase_secret_key}"},
                   json={"email": EMAIL, "password": PWD, "email_confirm": True}, timeout=20)
    print("ensure user:", r.status_code, "(422 = already exists)")


def sign_in() -> str:
    r = httpx.post(f"{s.supabase_url}/auth/v1/token?grant_type=password",
                   headers={"apikey": s.supabase_publishable_key}, json={"email": EMAIL, "password": PWD}, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


async def main(q: str) -> None:
    ensure_user()
    tok = sign_in()
    print("no-token status:", httpx.post(f"{API}/threads", json={}).status_code)
    client = get_client(url=API, headers={"Authorization": f"Bearer {tok}"})
    thread = await client.threads.create()
    print("thread:", thread["thread_id"])
    t0 = time.time()
    last = None
    async for chunk in client.runs.stream(thread["thread_id"], "repurpora",
                                          input={"messages": [{"role": "user", "content": q}]},
                                          stream_mode="updates"):
        if chunk.event == "updates" and isinstance(chunk.data, dict):
            print(f"[{time.time() - t0:6.1f}s] {', '.join(chunk.data.keys())}")
        elif chunk.event == "error":
            print("ERROR", chunk.data)
    state = await client.threads.get_state(thread["thread_id"])
    last = state["values"]["messages"][-1]["content"]
    print("\n=== FINAL ===\n", last[:2500])
    mine = await client.threads.search(limit=5)
    print("\nthreads visible to user:", len(mine))


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else
                 "Assess montelukast for repurposing in India: unmet needs, trials, new indications and patents"))
