import { NextResponse } from "next/server";

/**
 * Prototype signup: creates a pre-confirmed user with the Supabase admin API
 * (server-side secret key, never shipped to the browser). Production swaps this
 * for standard email confirmation / SSO.
 */
export async function POST(req: Request) {
  const { email, password, fullName } = await req.json().catch(() => ({}));
  if (typeof email !== "string" || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))
    return NextResponse.json({ error: "Enter a valid email address." }, { status: 400 });
  if (typeof password !== "string" || password.length < 8)
    return NextResponse.json({ error: "Password must be at least 8 characters." }, { status: 400 });

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SECRET_KEY;
  if (!url || !key) return NextResponse.json({ error: "Auth backend not configured." }, { status: 500 });

  const res = await fetch(`${url}/auth/v1/admin/users`, {
    method: "POST",
    headers: { apikey: key, Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      email_confirm: true,
      user_metadata: { full_name: String(fullName || "").slice(0, 80) },
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg: string = body?.msg || body?.message || body?.error_description || "Sign-up failed.";
    const status = /already/i.test(msg) ? 409 : 400;
    return NextResponse.json({ error: /already/i.test(msg) ? "An account with this email already exists." : msg }, { status });
  }
  return NextResponse.json({ ok: true });
}
