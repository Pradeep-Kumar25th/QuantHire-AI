"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Brain,
  Calendar,
  FileCheck,
  MessageSquare,
  Network,
  Shield,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  Workflow,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { QuantHireLogo } from "@/components/brand/QuantHireLogo";
import { cn } from "@/lib/utils";

/** Malomatia brand palette */
const M = {
  red: "#CC112F",
  teal: "#437A8B",
  tealDeep: "#237690",
  charcoal: "#363636",
  gold: "#FFC000",
  grey: "#B0B0B0",
  light: "#E3E3E3",
} as const;

const FEATURES = [
  {
    icon: Brain,
    accent: "bg-[#CC112F]/12 text-[#CC112F]",
    title: "AI Job Spec Wizard",
    description:
      "Human-in-the-loop JD generation with enterprise sections, PDF export, and QuantChat indexing.",
  },
  {
    icon: FileCheck,
    accent: "bg-[#437A8B]/12 text-[#437A8B]",
    title: "Resume intelligence",
    description:
      "Structured profile extraction from PDFs — skills, experience, and screening signals ready to match.",
  },
  {
    icon: Target,
    accent: "bg-[#CC112F]/10 text-[#CC112F]",
    title: "Agentic job matching",
    description:
      "13-agent hierarchical swarm scores candidates across eight dimensions with live reasoning streams.",
  },
  {
    icon: MessageSquare,
    accent: "bg-[#237690]/12 text-[#237690]",
    title: "QuantChat",
    description:
      "Grounded Q&A over your talent pool and job library — RAG-backed answers for recruiters.",
  },
  {
    icon: Calendar,
    accent: "bg-[#FFC000]/15 text-[#363636]",
    title: "Interview orchestration",
    description:
      "Pipeline stages from application to offer with scheduling hooks for Microsoft Graph.",
  },
  {
    icon: TrendingUp,
    accent: "bg-[#437A8B]/10 text-[#437A8B]",
    title: "Explainable decisions",
    description:
      "Debate, bias audit, and evidence panels — every score traceable for HR and compliance review.",
  },
] as const;

const PIPELINE = [
  { step: "01", label: "Pre-flight", detail: "JD hygiene · location fit · orchestration" },
  { step: "02", label: "Specialist swarm", detail: "7 dimension agents score in parallel" },
  { step: "03", label: "Debate & audit", detail: "Synthesizer · critic · bias & groundedness" },
  { step: "04", label: "Insights", detail: "HR advisor · explainability · final verdict" },
] as const;

const METRICS = [
  { value: "13", label: "Agent swarm specialists", suffix: "" },
  { value: "8", label: "Match dimensions scored", suffix: "" },
  { value: "SSO", label: "Enterprise identity ready", suffix: "" },
  { value: "Live", label: "SSE reasoning transparency", suffix: "" },
] as const;

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.5, ease: "easeOut" },
};

export function HomeLanding() {
  return (
    <div
      className="relative min-h-screen overflow-hidden text-[#E3E3E3]"
      style={{ backgroundColor: M.charcoal }}
    >
      <AgenticBackground />

      <header className="relative z-20 border-b border-[#B0B0B0]/20 bg-[#363636]/80 backdrop-blur-xl">
        <div className="malomatia-cta-gradient h-0.5 w-full" aria-hidden />
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-4 sm:px-6 lg:px-8">
          <QuantHireLogo
            href="/"
            variant="nav"
            size="sm"
            surface="dark"
            priority
            className="shrink-0 max-w-[240px]"
            imageClassName="h-[44px] w-auto max-w-full object-contain"
          />

          <nav className="hidden shrink-0 items-center gap-8 text-sm text-[#B0B0B0] md:flex">
            <a href="#platform" className="transition hover:text-[#FFC000]">
              Platform
            </a>
            <a href="#swarm" className="transition hover:text-[#FFC000]">
              Agent swarm
            </a>
            <a href="#capabilities" className="transition hover:text-[#FFC000]">
              Capabilities
            </a>
          </nav>

          <div className="flex items-center gap-2">
            <Link href="/login">
              <Button
                variant="ghost"
                size="sm"
                className="text-[#E3E3E3] hover:bg-white/10 hover:text-white"
              >
                Sign in
              </Button>
            </Link>
            <Link href="/login">
              <Button
                size="sm"
                className="malomatia-cta-gradient border-0 text-white shadow-lg shadow-[#CC112F]/25 hover:opacity-95"
              >
                Get started
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative z-10 mx-auto grid max-w-7xl gap-12 px-4 pb-20 pt-10 sm:px-6 lg:grid-cols-2 lg:items-center lg:gap-16 lg:px-8 lg:pb-28 lg:pt-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="flex flex-col items-start space-y-6 lg:space-y-7"
        >
          <div className="relative w-full max-w-[min(100%,480px)]">
            <div
              aria-hidden
              className="pointer-events-none absolute -inset-8 rounded-[2rem] bg-[radial-gradient(ellipse_at_center,rgba(204,17,47,0.22)_0%,rgba(35,118,144,0.14)_45%,transparent_72%)] blur-2xl"
            />
            <QuantHireLogo
              variant="full"
              size="2xl"
              surface="dark"
              priority
              className="relative z-[1]"
              imageClassName="h-[140px] w-auto max-w-[min(100%,560px)] object-contain sm:h-[168px] lg:h-[196px]"
            />
          </div>

          <div className="inline-flex items-center gap-2 rounded-full border border-[#437A8B]/40 bg-[#437A8B]/10 px-3 py-1 text-xs font-medium text-[#E3E3E3] backdrop-blur-sm">
            <span className="relative flex h-2 w-2">
              <span
                className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
                style={{ backgroundColor: M.gold }}
              />
              <span
                className="relative inline-flex h-2 w-2 rounded-full"
                style={{ backgroundColor: M.gold }}
              />
            </span>
            Agentic AI hiring platform · HSS-D swarm
          </div>

          <div className="space-y-4">
            <h1 className="text-4xl font-bold leading-[1.08] tracking-tight text-white sm:text-5xl lg:text-6xl">
              Hire with a{" "}
              <span className="malomatia-headline-gradient">multi-agent swarm</span>, not a
              black box.
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-[#B0B0B0]">
              QuantHireAI orchestrates specialist agents across requisition, resume intelligence,
              semantic matching, and explainable decisions — built for enterprise HR teams who
              need transparency at scale.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link href="/login">
              <Button
                size="lg"
                className="malomatia-cta-gradient h-12 border-0 px-8 text-base text-white shadow-xl shadow-[#CC112F]/30 hover:opacity-95"
              >
                Launch workspace
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <a href="#platform">
              <Button
                size="lg"
                variant="outline"
                className="h-12 border-[#437A8B]/50 bg-[#437A8B]/10 px-8 text-base text-white backdrop-blur-sm hover:bg-[#437A8B]/20"
              >
                Explore platform
              </Button>
            </a>
          </div>

          <div className="flex flex-wrap gap-4 pt-2 text-xs text-[#B0B0B0]">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-[#437A8B]/30 bg-[#363636]/60 px-2.5 py-1">
              <Shield className="h-3.5 w-3.5 text-[#437A8B]" />
              SSO · Entra ID
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-[#FFC000]/30 bg-[#363636]/60 px-2.5 py-1">
              <Network className="h-3.5 w-3.5 text-[#FFC000]" />
              Live agent SSE feed
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-[#CC112F]/30 bg-[#363636]/60 px-2.5 py-1">
              <Zap className="h-3.5 w-3.5 text-[#CC112F]" />
              Evidence-backed scoring
            </span>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, delay: 0.15 }}
          className="relative mx-auto w-full max-w-lg lg:max-w-none"
        >
          <SwarmHeroVisual />
        </motion.div>
      </section>

      {/* Metrics */}
      <section className="relative z-10 border-y border-[#B0B0B0]/15 bg-[#363636]/70 backdrop-blur-sm">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-6 px-4 py-12 sm:px-6 md:grid-cols-4 lg:px-8">
          {METRICS.map((m, i) => (
            <motion.div
              key={m.label}
              {...fadeUp}
              transition={{ ...fadeUp.transition, delay: i * 0.08 }}
              className="text-center md:text-left"
            >
              <div className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                {m.value}
                {m.suffix}
              </div>
              <div className="mt-1 text-sm text-[#B0B0B0]">{m.label}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Platform features — Malomatia light section */}
      <section
        id="platform"
        className="relative z-10 px-4 py-20 sm:px-6 lg:px-8"
        style={{ backgroundColor: M.light }}
      >
        <div className="mx-auto max-w-7xl">
          <motion.div {...fadeUp} className="mb-12 max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-widest text-[#437A8B]">
              Platform
            </p>
            <h2
              className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl"
              style={{ color: M.charcoal }}
            >
              Everything your talent team needs — one agentic workspace
            </h2>
            <p className="mt-3 text-[#B0B0B0]">
              From JD authoring to match verdicts, every workflow is designed for recruiters,
              hiring managers, and compliance reviewers.
            </p>
          </motion.div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature, i) => (
              <motion.div
                key={feature.title}
                {...fadeUp}
                transition={{ ...fadeUp.transition, delay: i * 0.06 }}
              >
                <FeatureCard {...feature} />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Agent swarm pipeline */}
      <section
        id="swarm"
        className="relative z-10 border-t border-[#B0B0B0]/15 px-4 py-20 sm:px-6 lg:px-8"
        style={{
          background: `linear-gradient(180deg, #2e2e2e 0%, ${M.charcoal} 100%)`,
        }}
      >
        <div className="mx-auto max-w-7xl">
          <motion.div
            {...fadeUp}
            className="mb-12 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"
          >
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-widest text-[#CC112F]">
                Agent swarm
              </p>
              <h2 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">
                Watch specialists debate — then trust the verdict
              </h2>
              <p className="mt-3 text-[#B0B0B0]">
                Our hierarchical swarm runs pre-flight checks, parallel dimension scoring, bias
                audit, synthesizer–critic debate, and HR-grade explainability — streamed live to
                your team.
              </p>
            </div>
            <Link href="/login">
              <Button className="malomatia-cta-gradient shrink-0 border-0 text-white">
                Run a match
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </motion.div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {PIPELINE.map((step, i) => (
              <motion.div
                key={step.step}
                {...fadeUp}
                transition={{ ...fadeUp.transition, delay: i * 0.1 }}
                className="group relative overflow-hidden rounded-2xl border border-[#437A8B]/25 bg-[#437A8B]/5 p-5 backdrop-blur-sm transition hover:border-[#FFC000]/40 hover:bg-[#437A8B]/10"
              >
                <div className="text-[10px] font-mono font-bold text-[#FFC000]">{step.step}</div>
                <div className="mt-2 text-lg font-semibold text-white">{step.label}</div>
                <p className="mt-2 text-sm text-[#B0B0B0]">{step.detail}</p>
                <Workflow className="absolute -bottom-2 -right-2 h-16 w-16 text-white/[0.04] transition group-hover:text-[#437A8B]/15" />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section id="capabilities" className="relative z-10 mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <motion.div
          {...fadeUp}
          className="relative overflow-hidden rounded-3xl border border-[#437A8B]/30 p-8 sm:p-12"
          style={{ backgroundColor: M.charcoal }}
        >
          <div
            className="pointer-events-none absolute inset-0 opacity-30"
            style={{
              background:
                "radial-gradient(ellipse 70% 80% at 100% 0%, #CC112F 0%, transparent 50%), radial-gradient(ellipse 60% 70% at 0% 100%, #237690 0%, transparent 50%)",
            }}
            aria-hidden
          />
          <div className="relative z-10 max-w-2xl">
            <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Ready for enterprise agentic hiring?
            </h2>
            <p className="mt-4 text-lg text-[#B0B0B0]">
              Sign in with your organisation SSO and start matching candidates with full swarm
              transparency — no opaque scores, no dummy data.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/login">
                <Button size="lg" className="malomatia-cta-gradient border-0 text-white shadow-lg">
                  Get started
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </div>
          </div>
          <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-[#437A8B]/20 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-16 right-1/3 h-48 w-48 rounded-full bg-[#CC112F]/20 blur-3xl" />
        </motion.div>
      </section>

      <footer className="relative z-10 border-t border-[#B0B0B0]/15 px-4 py-8 text-center text-xs text-[#B0B0B0] sm:px-6">
        © {new Date().getFullYear()} QuantHireAI · Multi-Agent · Explainable · Evidence-Backed
      </footer>
    </div>
  );
}

function AgenticBackground() {
  const networkNodes = [
    { cx: 8, cy: 15 },
    { cx: 22, cy: 28 },
    { cx: 38, cy: 12 },
    { cx: 55, cy: 22 },
    { cx: 72, cy: 8 },
    { cx: 88, cy: 18 },
    { cx: 15, cy: 45 },
    { cx: 35, cy: 52 },
    { cx: 58, cy: 48 },
    { cx: 78, cy: 55 },
    { cx: 92, cy: 42 },
    { cx: 25, cy: 72 },
    { cx: 50, cy: 78 },
    { cx: 75, cy: 70 },
    { cx: 45, cy: 92 },
    { cx: 65, cy: 88 },
  ];

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      {/* Malomatia radial washes */}
      <div
        className="absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse 80% 55% at 50% -5%, rgba(67, 122, 139, 0.35) 0%, transparent 55%),
            radial-gradient(ellipse 55% 45% at 95% 15%, rgba(204, 17, 47, 0.22) 0%, transparent 50%),
            radial-gradient(ellipse 50% 40% at 5% 55%, rgba(255, 192, 0, 0.1) 0%, transparent 45%),
            radial-gradient(ellipse 40% 35% at 80% 75%, rgba(35, 118, 144, 0.18) 0%, transparent 50%)
          `,
        }}
      />

      {/* Agent network wallpaper */}
      <svg
        className="absolute inset-0 h-full w-full opacity-[0.14]"
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid slice"
      >
        {networkNodes.map((a, i) =>
          networkNodes.slice(i + 1, i + 4).map((b, j) => (
            <motion.line
              key={`${i}-${j}`}
              x1={a.cx}
              y1={a.cy}
              x2={b.cx}
              y2={b.cy}
              stroke="#437A8B"
              strokeWidth="0.15"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 0.6 }}
              transition={{ duration: 2, delay: (i + j) * 0.08, repeat: Infinity, repeatType: "reverse", repeatDelay: 3 }}
            />
          )),
        )}
        {networkNodes.map((n, i) => (
          <motion.circle
            key={i}
            cx={n.cx}
            cy={n.cy}
            r="0.6"
            fill={i % 3 === 0 ? M.red : i % 3 === 1 ? M.teal : M.gold}
            initial={{ opacity: 0.3 }}
            animate={{ opacity: [0.3, 0.8, 0.3] }}
            transition={{ duration: 3 + (i % 4), repeat: Infinity, delay: i * 0.2 }}
          />
        ))}
      </svg>

      {/* Subtle grid */}
      <div
        className="absolute inset-0 opacity-[0.25]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(227, 227, 227, 0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(227, 227, 227, 0.04) 1px, transparent 1px)
          `,
          backgroundSize: "56px 56px",
        }}
      />

      {/* Floating orbs */}
      <motion.div
        animate={{ y: [0, -20, 0], opacity: [0.35, 0.55, 0.35] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        className="absolute left-[12%] top-[18%] h-72 w-72 rounded-full blur-3xl"
        style={{ backgroundColor: "rgba(67, 122, 139, 0.15)" }}
      />
      <motion.div
        animate={{ y: [0, 24, 0], opacity: [0.25, 0.45, 0.25] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 1 }}
        className="absolute right-[8%] top-[28%] h-96 w-96 rounded-full blur-3xl"
        style={{ backgroundColor: "rgba(204, 17, 47, 0.12)" }}
      />
      <motion.div
        animate={{ y: [0, -16, 0], opacity: [0.2, 0.4, 0.2] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut", delay: 2 }}
        className="absolute bottom-[15%] left-[40%] h-64 w-64 rounded-full blur-3xl"
        style={{ backgroundColor: "rgba(35, 118, 144, 0.1)" }}
      />
    </div>
  );
}

function SwarmHeroVisual() {
  const nodes = [
    { x: 50, y: 12, label: "Orchestrator", fill: M.grey },
    { x: 22, y: 38, label: "Skills", fill: M.teal },
    { x: 38, y: 32, label: "Experience", fill: M.teal },
    { x: 54, y: 38, label: "Domain", fill: M.teal },
    { x: 70, y: 32, label: "Culture", fill: M.teal },
    { x: 86, y: 38, label: "Risk", fill: M.teal },
    { x: 35, y: 58, label: "Bias audit", fill: M.tealDeep },
    { x: 65, y: 58, label: "Evidence", fill: M.tealDeep },
    { x: 42, y: 78, label: "Debate", fill: M.gold },
    { x: 58, y: 78, label: "Verdict", fill: M.red },
  ];

  return (
    <div className="relative rounded-2xl border border-[#437A8B]/30 bg-[#363636]/80 p-4 shadow-2xl shadow-black/40 backdrop-blur-xl">
      <div className="malomatia-cta-gradient absolute inset-x-4 top-0 h-px rounded-full opacity-60" />
      <div className="mb-3 flex items-center justify-between border-b border-[#B0B0B0]/15 pb-3">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-[#437A8B]" />
          <span className="text-xs font-semibold text-[#E3E3E3]">Live swarm topology</span>
        </div>
        <span className="rounded-full bg-[#437A8B]/20 px-2 py-0.5 text-[10px] font-medium text-[#FFC000]">
          Running
        </span>
      </div>

      <div
        className="relative aspect-[4/3] w-full overflow-hidden rounded-xl"
        style={{ backgroundColor: "#2a2a2a" }}
      >
        <svg viewBox="0 0 100 100" className="h-full w-full" preserveAspectRatio="xMidYMid meet">
          <g opacity={0.25}>
            {nodes.slice(1, 6).map((n, i) => (
              <line
                key={i}
                x1="50"
                y1="12"
                x2={n.x}
                y2={n.y}
                stroke={M.teal}
                strokeWidth="0.25"
              />
            ))}
            <line x1="50" y1="12" x2="50" y2="58" stroke={M.tealDeep} strokeWidth="0.25" />
            <line x1="35" y1="58" x2="42" y2="78" stroke={M.gold} strokeWidth="0.25" />
            <line x1="65" y1="58" x2="58" y2="78" stroke={M.red} strokeWidth="0.25" />
          </g>
          {nodes.map((node, i) => (
            <motion.g
              key={node.label}
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.3 + i * 0.06, duration: 0.4 }}
            >
              <circle cx={node.x} cy={node.y} r="3.5" fill={node.fill} opacity={0.95} />
              <text
                x={node.x}
                y={node.y + 7}
                textAnchor="middle"
                fill={M.grey}
                fontSize="3"
                fontWeight="500"
              >
                {node.label}
              </text>
            </motion.g>
          ))}
        </svg>

        <motion.div
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="absolute bottom-3 left-3 right-3 rounded-lg border border-[#437A8B]/25 bg-[#363636]/95 px-3 py-2 text-[10px] text-[#B0B0B0] backdrop-blur-sm"
        >
          <span className="font-semibold text-[#437A8B]">SkillsAgent</span>
          {" · "}Scoring dimension with evidence-backed rationale…
        </motion.div>
      </div>
    </div>
  );
}

function FeatureCard({
  icon: Icon,
  accent,
  title,
  description,
}: {
  icon: typeof Brain;
  accent: string;
  title: string;
  description: string;
}) {
  return (
    <div
      className="group h-full rounded-2xl border border-[#B0B0B0]/40 bg-white p-6 shadow-sm transition duration-300 hover:-translate-y-1 hover:border-[#437A8B]/50 hover:shadow-xl hover:shadow-[#437A8B]/10"
    >
      <div className={cn("mb-4 inline-flex rounded-xl p-3", accent)}>
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="text-lg font-semibold" style={{ color: M.charcoal }}>
        {title}
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-[#B0B0B0]">{description}</p>
    </div>
  );
}
