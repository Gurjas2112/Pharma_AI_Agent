"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, LoaderCircle } from "lucide-react";
import { supabaseBrowser } from "@/lib/supabase/client";
import { RepurporaWordmark } from "@/components/brand/logo";
import { MoleculeField } from "./molecule-field";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isSignup = mode === "signup";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (isSignup) {
        const r = await fetch("/api/signup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password, fullName }),
        });
        const body = await r.json();
        if (!r.ok) throw new Error(body.error || "Sign-up failed");
      }
      const { error } = await supabaseBrowser().auth.signInWithPassword({ email, password });
      if (error) throw error;
      router.replace(params.get("next") || "/chat");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative min-h-screen bg-[#070B1A] text-white overflow-hidden flex items-center justify-center p-4">
      <MoleculeField className="absolute inset-0 opacity-60" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(20,184,166,0.12),transparent_60%)]" />
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative w-full max-w-md rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-8 shadow-2xl"
      >
        <Link href="/" className="inline-block mb-6">
          <RepurporaWordmark dark />
        </Link>
        <h1 className="text-2xl font-semibold">{isSignup ? "Create your research workspace" : "Welcome back"}</h1>
        <p className="text-sm text-white/60 mt-1 mb-6">
          {isSignup ? "Start finding repurposing opportunities in minutes." : "Sign in to continue your research threads."}
        </p>
        <form onSubmit={submit} className="space-y-4">
          {isSignup && <Field label="Full name" value={fullName} onChange={setFullName} type="text" name="name" autoComplete="name" />}
          <Field label="Work email" value={email} onChange={setEmail} type="email" name="email" autoComplete="email" required />
          <Field
            label="Password"
            value={password}
            onChange={setPassword}
            type="password"
            name="password"
            autoComplete={isSignup ? "new-password" : "current-password"}
            required
            minLength={8}
          />
          {error && (
            <p role="alert" className="text-sm text-rose-300 bg-rose-500/10 border border-rose-500/30 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-teal-400 to-violet-500 py-3 font-medium text-[#070B1A] hover:opacity-90 disabled:opacity-60 transition"
          >
            {busy ? <LoaderCircle className="size-4 animate-spin" /> : <ArrowRight className="size-4" />}
            {isSignup ? "Create account" : "Sign in"}
          </button>
        </form>
        <p className="text-sm text-white/60 mt-6 text-center">
          {isSignup ? "Already have an account? " : "New to Repurpora? "}
          <Link href={isSignup ? "/login" : "/signup"} className="text-teal-300 hover:underline">
            {isSignup ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </motion.div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  ...rest
}: { label: string; value: string; onChange: (v: string) => void } & Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  "value" | "onChange"
>) {
  return (
    <label className="block">
      <span className="text-xs uppercase tracking-wider text-white/50">{label}</span>
      <input
        {...rest}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-white placeholder-white/30 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-400/30 transition"
      />
    </label>
  );
}
