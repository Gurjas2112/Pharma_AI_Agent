"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Brain,
  FileCheck2,
  FlaskConical,
  Gauge,
  Globe,
  Library,
  Lock,
  PackageSearch,
  ScrollText,
  ShieldCheck,
  Ship,
  Sparkles,
  Stethoscope,
} from "lucide-react";
import { MoleculeField } from "@/components/landing/molecule-field";
import { RepurporaMark, RepurporaWordmark } from "@/components/brand/logo";

const AGENTS = [
  { name: "IQVIA Insights", icon: BarChart3, desc: "Market size, CAGR, competition", color: "from-teal-400 to-cyan-500" },
  { name: "EXIM Trends", icon: Ship, desc: "API sourcing & import dependency", color: "from-sky-400 to-blue-500" },
  { name: "Patent Landscape", icon: ScrollText, desc: "Expiry timelines & FTO risk", color: "from-violet-400 to-purple-500" },
  { name: "Clinical Trials", icon: FlaskConical, desc: "Live ClinicalTrials.gov pipeline", color: "from-amber-300 to-orange-500" },
  { name: "Internal Knowledge", icon: Library, desc: "Hybrid RAG over strategy docs", color: "from-emerald-400 to-teal-600" },
  { name: "Web Intelligence", icon: Globe, desc: "Guidelines, papers, news", color: "from-pink-400 to-rose-500" },
];

const JOURNEY = [
  { icon: FlaskConical, t: "Pick a molecule", d: "Start from any approved generic: “Assess montelukast in India”." },
  { icon: Stethoscope, t: "Find unmet needs", d: "Patient burden vs competition across indications and populations." },
  { icon: Activity, t: "Scan clinical trials", d: "Who is running what, in which phase, and where the gaps are." },
  { icon: Brain, t: "Explore new diseases", d: "Mechanism-led signals for new indications and dosage forms." },
  { icon: ScrollText, t: "Check patents & FTO", d: "Active filings, expiries and freedom-to-operate risk flags." },
  { icon: Sparkles, t: "Innovative product story", d: "A cited brief, ML-scored, archived as PDF + Excel." },
];

const TRUST = [
  { icon: ShieldCheck, t: "Guardrails", d: "Prompt-injection firewall, untrusted-content sanitising, PII & secret DLP, tool allow-lists." },
  { icon: FileCheck2, t: "Evidence layer", d: "Every claim cites [E#] evidence with source, trust tier and SHA-256 provenance." },
  { icon: Gauge, t: "Evaluation", d: "LLM-as-judge faithfulness, evidence coverage gate, golden-set regression suite." },
  { icon: Lock, t: "Governance", d: "Per-user threads, append-only audit log, secrets in a vault, never in prompts." },
];

const STACK = ["LangGraph", "LangChain", "Ollama on AWS", "Supabase pgvector", "LangSmith", "scikit-learn", "Railway", "Vercel"];

const LIVE_LINES = [
  "› Master agent: decomposing “Assess montelukast for repurposing in India”",
  "› Dispatching 6 agents in parallel…",
  "  ✓ IQVIA        Post-viral chronic cough · 5 competitors · CAGR 12.7%",
  "  ✓ Trials       ClinicalTrials.gov live · phase distribution ready",
  "  ✓ Patents      FTO risk scored · expiry timeline built",
  "  ✓ Internal RAG Field report: 63% adherence gap in children < 6",
  "› ML opportunity scorer · p(success) computed",
  "› Judge: evidence coverage 92% · faithfulness 4/5",
  "✦ Report RPR-… archived → PDF + Excel",
];

function LiveRun() {
  const [n, setN] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setN((v) => (v >= LIVE_LINES.length + 3 ? 0 : v + 1)), 900);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="rounded-2xl border border-white/10 bg-[#0B1226]/80 backdrop-blur-xl shadow-2xl shadow-teal-500/10 overflow-hidden">
      <div className="flex items-center gap-1.5 px-4 py-3 border-b border-white/10">
        <span className="size-2.5 rounded-full bg-rose-400" />
        <span className="size-2.5 rounded-full bg-amber-300" />
        <span className="size-2.5 rounded-full bg-emerald-400" />
        <span className="ml-3 text-xs text-white/40 font-mono">lazarus-graph · live run</span>
      </div>
      <div className="p-4 font-mono text-[12.5px] leading-6 min-h-[260px]">
        {LIVE_LINES.slice(0, n).map((l, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            className={l.startsWith("  ✓") ? "text-teal-300" : l.startsWith("✦") ? "text-amber-300" : "text-white/80"}
          >
            {l}
          </motion.div>
        ))}
        {n < LIVE_LINES.length && <span className="inline-block w-2 h-4 bg-teal-300 animate-pulse align-middle" />}
      </div>
    </div>
  );
}

function Constellation() {
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[520px]">
      <svg viewBox="0 0 520 520" className="absolute inset-0 w-full h-full">
        {AGENTS.map((_, i) => {
          const a = (i / AGENTS.length) * Math.PI * 2 - Math.PI / 2;
          const x = 260 + Math.cos(a) * 190,
            y = 260 + Math.sin(a) * 190;
          return (
            <g key={i}>
              <line x1="260" y1="260" x2={x} y2={y} stroke="rgba(148,163,255,0.25)" strokeDasharray="4 6" />
              <circle r="4" fill="#5EEAD4">
                <animateMotion dur={`${2.2 + i * 0.3}s`} repeatCount="indefinite" path={`M260,260 L${x},${y}`} />
              </circle>
            </g>
          );
        })}
        <circle cx="260" cy="260" r="200" fill="none" stroke="rgba(255,255,255,0.05)" />
      </svg>
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
        <div className="rounded-full p-5 bg-gradient-to-br from-teal-400/20 to-violet-500/30 border border-white/15 shadow-[0_0_60px_rgba(20,184,166,0.35)]">
          <RepurporaMark size={56} />
        </div>
        <span className="mt-2 text-sm font-semibold">Master agent</span>
        <span className="text-xs text-white/50">plans · delegates · synthesises</span>
      </div>
      {AGENTS.map((ag, i) => {
        const a = (i / AGENTS.length) * Math.PI * 2 - Math.PI / 2;
        const left = 50 + (Math.cos(a) * 190 * 100) / 520;
        const top = 50 + (Math.sin(a) * 190 * 100) / 520;
        const Icon = ag.icon;
        return (
          <motion.div
            key={ag.name}
            initial={{ opacity: 0, scale: 0.6 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 * i }}
            className="absolute -translate-x-1/2 -translate-y-1/2 w-36 text-center"
            style={{ left: `${left}%`, top: `${top}%` }}
          >
            <div className={`mx-auto size-12 rounded-2xl bg-gradient-to-br ${ag.color} grid place-items-center shadow-lg`}>
              <Icon className="size-6 text-[#070B1A]" />
            </div>
            <div className="mt-1.5 text-xs font-semibold">{ag.name}</div>
            <div className="text-[11px] text-white/50 leading-tight">{ag.desc}</div>
          </motion.div>
        );
      })}
    </div>
  );
}

export default function Landing() {
  return (
    <main className="bg-[#070B1A] text-white min-h-screen overflow-x-hidden">
      {/* NAV */}
      <nav className="fixed top-0 inset-x-0 z-40 border-b border-white/5 bg-[#070B1A]/70 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-5 h-16">
          <Link href="/">
            <RepurporaWordmark dark />
          </Link>
          <div className="hidden md:flex items-center gap-8 text-sm text-white/70">
            <a href="#agents" className="hover:text-white">Agents</a>
            <a href="#journey" className="hover:text-white">Journey</a>
            <a href="#trust" className="hover:text-white">Trust layer</a>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/login" className="px-4 py-2 text-sm text-white/80 hover:text-white" data-testid="nav-login">
              Sign in
            </Link>
            <Link
              href="/signup"
              data-testid="nav-signup"
              className="px-4 py-2 text-sm rounded-full bg-white text-[#070B1A] font-medium hover:bg-teal-200 transition"
            >
              Get started
            </Link>
          </div>
        </div>
      </nav>

      {/* HERO */}
      <section className="relative pt-32 pb-24 min-h-[92vh] flex items-center">
        <MoleculeField className="absolute inset-0 opacity-70" />
        <div className="absolute inset-0 bg-[radial-gradient(60%_50%_at_30%_40%,rgba(20,184,166,0.18),transparent),radial-gradient(50%_50%_at_80%_60%,rgba(124,58,237,0.22),transparent)]" />
        <div className="relative max-w-7xl mx-auto px-5 grid lg:grid-cols-2 gap-14 items-center">
          <div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="inline-flex items-center gap-2 rounded-full border border-teal-400/30 bg-teal-400/10 px-3 py-1 text-xs text-teal-200"
            >
              <Sparkles className="size-3.5" /> Agentic AI · LangGraph multi-agent · Evidence-cited
            </motion.div>
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="mt-6 text-5xl md:text-6xl font-bold tracking-tight leading-[1.05]"
            >
              Revive approved molecules.
              <br />
              <span className="bg-gradient-to-r from-teal-300 via-sky-300 to-violet-400 bg-clip-text text-transparent">
                Find the next indication
              </span>
              <br />
              in minutes, not months.
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="mt-6 text-lg text-white/70 max-w-xl"
            >
              Repurpora&apos;s master agent turns one prompt into a full innovation case: market, trade, patents,
              trials, internal knowledge and the web, scored by ML and archived as a cited report.
            </motion.p>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="mt-8 flex flex-wrap gap-3"
            >
              <Link
                href="/signup"
                data-testid="hero-cta"
                className="group inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-teal-400 to-violet-500 px-6 py-3.5 font-semibold text-[#070B1A] shadow-lg shadow-teal-500/25 hover:shadow-teal-500/40 transition"
              >
                Start researching free <ArrowRight className="size-4 group-hover:translate-x-0.5 transition" />
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center gap-2 rounded-full border border-white/20 px-6 py-3.5 text-white/90 hover:bg-white/5"
              >
                I have an account
              </Link>
            </motion.div>
            <div className="mt-12 grid grid-cols-3 gap-6 max-w-lg">
              {[
                ["2–3 mo → min", "literature review time"],
                ["6 agents", "run in parallel"],
                ["100%", "claims evidence-gated"],
              ].map(([k, v]) => (
                <div key={k}>
                  <div className="text-2xl font-bold text-white">{k}</div>
                  <div className="text-xs text-white/50">{v}</div>
                </div>
              ))}
            </div>
          </div>
          <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.35 }}>
            <LiveRun />
          </motion.div>
        </div>
      </section>

      {/* AGENTS */}
      <section id="agents" className="relative py-24 border-t border-white/5">
        <div className="max-w-7xl mx-auto px-5 grid lg:grid-cols-2 gap-10 items-center">
          <div>
            <p className="text-teal-300 text-sm font-semibold uppercase tracking-widest">The agent constellation</p>
            <h2 className="mt-3 text-4xl font-bold tracking-tight">One master. Six specialists. Zero guesswork.</h2>
            <p className="mt-4 text-white/70">
              The master agent decomposes your question into a typed research plan and fans out to domain workers with
              LangGraph&apos;s <code className="text-teal-200">Send</code> API. Each worker is sandboxed to its own
              allow-listed tools, returns tables, charts and provenance-tagged evidence, then the master synthesises a
              brief that must pass an evidence-coverage gate.
            </p>
            <div className="mt-8 grid grid-cols-2 gap-3">
              {[
                [PackageSearch, "Mock IQVIA / EXIM / USPTO APIs"],
                [FlaskConical, "Live ClinicalTrials.gov v2"],
                [Globe, "Live web search (Firecrawl)"],
                [Library, "Hybrid RAG: pgvector + BM25 + RRF"],
              ].map(([Icon, t]) => {
                const I = Icon as typeof Globe;
                return (
                  <div key={t as string} className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm">
                    <I className="size-4 text-teal-300" /> {t as string}
                  </div>
                );
              })}
            </div>
          </div>
          <Constellation />
        </div>
      </section>

      {/* JOURNEY */}
      <section id="journey" className="py-24 border-t border-white/5 bg-gradient-to-b from-transparent to-[#0B1226]">
        <div className="max-w-7xl mx-auto px-5">
          <p className="text-teal-300 text-sm font-semibold uppercase tracking-widest text-center">End-to-end journey</p>
          <h2 className="mt-3 text-4xl font-bold tracking-tight text-center">From a molecule to a product story</h2>
          <div className="mt-14 grid md:grid-cols-3 lg:grid-cols-6 gap-4 relative">
            <div className="hidden lg:block absolute top-7 left-[8%] right-[8%] h-px bg-gradient-to-r from-teal-400/0 via-teal-400/50 to-violet-500/0" />
            {JOURNEY.map((s, i) => (
              <motion.div
                key={s.t}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="relative rounded-2xl border border-white/10 bg-white/[0.03] p-5 hover:border-teal-400/40 hover:bg-white/[0.06] transition"
              >
                <div className="size-14 rounded-2xl bg-[#0B1226] border border-white/10 grid place-items-center mb-4">
                  <s.icon className="size-6 text-teal-300" />
                </div>
                <div className="text-xs text-white/40">Step {i + 1}</div>
                <div className="font-semibold mt-1">{s.t}</div>
                <div className="text-sm text-white/60 mt-1">{s.d}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* TRUST */}
      <section id="trust" className="py-24 border-t border-white/5">
        <div className="max-w-7xl mx-auto px-5">
          <p className="text-teal-300 text-sm font-semibold uppercase tracking-widest">Built for regulated work</p>
          <h2 className="mt-3 text-4xl font-bold tracking-tight max-w-2xl">A trust layer around every answer</h2>
          <div className="mt-12 grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {TRUST.map((c) => (
              <div key={c.t} className="rounded-2xl border border-white/10 bg-gradient-to-b from-white/[0.06] to-transparent p-6">
                <c.icon className="size-7 text-violet-300" />
                <div className="mt-4 font-semibold">{c.t}</div>
                <div className="mt-2 text-sm text-white/60">{c.d}</div>
              </div>
            ))}
          </div>
          <div className="mt-14 flex flex-wrap gap-2 justify-center">
            {STACK.map((s) => (
              <span key={s} className="rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs text-white/70">
                {s}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 border-t border-white/5">
        <div className="max-w-4xl mx-auto px-5 text-center rounded-3xl border border-white/10 bg-[radial-gradient(80%_120%_at_50%_0%,rgba(20,184,166,0.25),transparent)] py-16">
          <h2 className="text-4xl font-bold tracking-tight">Your next differentiated product is already approved.</h2>
          <p className="mt-4 text-white/70">Ask Repurpora where to take it next.</p>
          <Link
            href="/signup"
            className="mt-8 inline-flex items-center gap-2 rounded-full bg-white text-[#070B1A] px-7 py-3.5 font-semibold hover:bg-teal-200 transition"
          >
            Create your workspace <ArrowRight className="size-4" />
          </Link>
        </div>
        <p className="mt-10 text-center text-xs text-white/40">
          Prototype · market, trade and patent data are synthetic mocks per the problem statement · not medical or legal advice
        </p>
      </section>
    </main>
  );
}
