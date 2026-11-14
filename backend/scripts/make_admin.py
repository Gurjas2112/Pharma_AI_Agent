"""Grant or revoke the admin role (app_metadata.role) through the Supabase admin API.

usage: uv run python scripts/make_admin.py user@example.com [--revoke]
Requires SUPABASE_SECRET_KEY (service role). The user must sign in again for the new role to appear in the JWT.
"""

import sys

import httpx

from repurpora.settings import get_settings

if len(sys.argv) < 2:
    sys.exit(__doc__)
s = get_settings()
email, revoke = sys.argv[1].lower(), "--revoke" in sys.argv
h = {"apikey": s.supabase_secret_key, "Authorization": f"Bearer {s.supabase_secret_key}"}
users = httpx.get(f"{s.supabase_url}/auth/v1/admin/users", headers=h, params={"per_page": 1000},
                  timeout=20).json()["users"]
u = next((x for x in users if (x.get("email") or "").lower() == email), None)
if not u:
    sys.exit(f"no user with email {email}")
meta = {**(u.get("app_metadata") or {}), "role": "analyst" if revoke else "admin"}
httpx.put(f"{s.supabase_url}/auth/v1/admin/users/{u['id']}", headers=h, json={"app_metadata": meta},
          timeout=20).raise_for_status()
print(f"{email}: role={meta['role']}")
