# MASTER PROMPT — QuantHire HSS-D UI (exact clone for Codex)

**For you (human):** Attach **`hssd-ui-bundle.zip`** (or copy from QuantHire `apps/web`). Paste **everything inside the ` ```text ` block below** into Codex as message #1. Backend must expose `/api/v1/job-matching/*` (separate agents bundle).

---

````text
═══════════════════════════════════════════════════════════════════════════════
CODEX TASK: BUILD THE EXACT QUANTHIRE HSS-D JOB MATCHING UI
═══════════════════════════════════════════════════════════════════════════════

ROLE
You are a senior frontend engineer. Recreate the QuantHire AI **Job Matching** page
(`/dashboard/job-matching`) so it is visually and behaviorally INDISTINGUISHABLE from
production. The user has attached **hssd-ui-bundle.zip** (or QuantHire apps/web sources).

This task is **UI ONLY**: Next.js, Tailwind, components, SSE client, BFF proxy, colors,
layout, animations. Do NOT redesign. Do NOT use a different theme. COPY the reference files.

SUCCESS = A recruiter sees the same page: emerald swarm chrome, 3-stage stepper, dual-pane
live monitor (graph + thoughts), collapsible run log, tabbed results with gauge/radar/debate.

──────────────────────────────────────────────────────────────────────────────
1. REFERENCE FILES (COPY VERBATIM — DO NOT REWRITE FROM MEMORY)
──────────────────────────────────────────────────────────────────────────────

Required files (paths relative to Next.js `src/`):

  app/globals.css                          ← ALL colors/tokens
  app/layout.tsx
  app/dashboard/layout.tsx                 ← Sidebar + Header + QuantChat shell
  app/dashboard/job-matching/page.tsx      ← Main page state machine
  app/api/[...path]/route.ts               ← BFF SSE proxy, 620s timeout

  components/matching/
    use-match-stream.ts                    ← EventSource; CRITICAL
    swarm-visualizer.tsx                   ← Framer Motion SVG graph
    agent-thoughts-stream.tsx
    run-hud.tsx
    match-launcher.tsx
    match-result-view.tsx
    score-gauge.tsx | score-radar.tsx | score-breakdown.tsx
    debate-panel.tsx | evidence-panel.tsx | insights-panel.tsx
    risk-bias-cards.tsx | verdict-badge.tsx
    manual-upload-panel.tsx                ← optional if in zip (hackathon uploads)

  components/ui/*                          ← full shadcn from zip
  components/layout/sidebar.tsx | header.tsx
  components/brand/QuantHireLogo.tsx
  components/usage/ai-hub-feedback.tsx
  components/providers.tsx
  components/auth/require-auth.tsx

  lib/utils.ts | api.ts | api-client.ts | api-errors.ts | api-health.ts
  lib/azure-messages.ts | candidate-mapper.ts | usage-telemetry.ts

  Root: tailwind.config.ts | postcss.config.js | components.json | package.json
  public/brand/*                             ← logos for sidebar/header

If a file exists in the zip, **use that file** with only import-path fixes allowed.

──────────────────────────────────────────────────────────────────────────────
2. BRAND & COLOR SYSTEM (MUST MATCH)
──────────────────────────────────────────────────────────────────────────────

Copy `globals.css` exactly. Key hex values:

  Malomatia red (primary):     #CC112F   --primary: 350 85% 43%
  Teal (secondary):            #437A8B   --secondary: 194 35% 40%
  Teal deep (gradients):       #237690
  Gold (accent):               #FFC000   --accent: 45 100% 50%
  Charcoal text:               #363636   --foreground: 0 0% 21%
  Page background:             ~#F5F5F5   --background: 0 0% 96%
  Card:                        white     --card: 0 0% 100%
  Border radius:               0.5rem    --radius

Gradients in CSS:
  .malomatia-cta-gradient: linear-gradient(90deg, #cc112f 0%, #237690 100%)

Typography:
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif
  h1–h6: font-weight 700

Tailwind must map semantic colors via hsl(var(--primary)) etc. (see tailwind.config.ts).

HSS-D page uses **emerald** for AI/swarm (NOT primary red for swarm highlights):
  - Header icon: bg-gradient-to-br from-emerald-500 to-emerald-600, white Target icon
  - Pill "Agentic Swarm · v1": bg-emerald-50 text-emerald-700 (dark: emerald-950/300)
  - Active stepper chip: bg-emerald-600 text-white shadow-emerald-600/20
  - Completed step: bg-emerald-50 text-emerald-700, emerald-400 connector line
  - Launcher toolbar: from-emerald-50/60 via-background to-amber-50/40
  - Match hero gauge card: to-emerald-50/30 dark:to-emerald-950/10
  - "Verdict Rationale" labels: text-emerald-700 uppercase tracking-wider text-[10px]
  - Strength bullets: text-emerald-500; gaps: text-orange-700
  - Error swarm banner: border-amber-400 bg-amber-50
  - Live status rings on graph: emerald-500 active/done, amber fallback, red error

Swarm visualizer layer palette (stroke/fill classes in swarm-visualizer.tsx):
  Layer 1: slate
  Layer 2: emerald
  Layer 2.5: cyan
  Layer 3: amber (debate)
  Layer 4: violet (insights)

Dashboard shell:
  main: bg-slate-50/40 dark:bg-background
  cards: rounded-xl border bg-card shadow-sm

FORBIDDEN: default shadcn blue/zinc-only theme; stripping emerald accents; removing dark mode.

──────────────────────────────────────────────────────────────────────────────
3. PAGE LAYOUT & STATE MACHINE (page.tsx)
──────────────────────────────────────────────────────────────────────────────

Route: /dashboard/job-matching
Wrapper: Suspense with "Loading job matching…" fallback

State: stage = "setup" | "running" | "results"
Hook: const stream = useMatchStream()

Header (always visible):
  - Emerald gradient square + lucide Target (white)
  - h1 "Job Matching" + monospace pill "Agentic Swarm · v1"
  - Subtitle: "13-agent hierarchical swarm · evidence-backed scoring"
  - StageStepper: Configure | Swarm run | Results (Settings2, Loader2 spin when running, BarChart3)

setup:
  - <MatchLauncher onLaunch={handleLaunch} disabled={stream.status==="running"}
      initialCandidateId={searchParams candidateId} />

running | results:
  - activeStrip: Sparkles, candidate name → job title, Cancel/New match, optional Jump to scores
  - results stage FIRST: <MatchResultView result={stream.result} ... />
  - error panel: red border, AlertCircle, Retry → handleRunAgain
  - empty running: "Spinning up the HSS-D specialist swarm…" + pulsing Sparkles
  - Collapsible "Live swarm monitor" / "Agent run log":
      RunHud + grid lg:grid-cols-2:
        SwarmVisualizer (fillHeight, min-h 480px)
        AgentThoughtsStream (fillHeight)
      Heights: running min(780px,82vh); results compact min(620px,70vh)
  - Escape key → handleReset when running

Launch flow:
  handleLaunch → setStage("running") → stream.start({ candidate_id, jd_id, weights })
  useEffect: when stream.result && stage running → setStage("results"), collapse log optional

──────────────────────────────────────────────────────────────────────────────
4. MATCH LAUNCHER (match-launcher.tsx)
──────────────────────────────────────────────────────────────────────────────

Structure:
  - Optional ManualUploadPanel above main card (hackathon)
  - Rounded-2xl card, border, shadow-sm
  - Top toolbar: gradient emerald/amber wash, Refresh, HSS health from testJobMatchingReady()
  - Two columns (ScrollArea): searchable candidate list + JD list
  - Row cards: name, headline, skill badges (max 3 chips), metadata
  - Selected summary bar with Badge chips + X clear
  - Advanced weights: 8 sliders (skills 0.26, experience 0.18, education 0.08, domain 0.13,
    culture 0.09, growth 0.09, projects 0.12, risk 0.05) — pass only if customized
  - Primary CTA: "Launch Swarm" + Sparkles, size lg, disabled until both selected + health ok

Data:
  api.jobMatching.listCandidates() / listJDs()
  Alert banners: AZURE_HSS_HINT, AZURE_MATCHING_DATA_HINT on errors

──────────────────────────────────────────────────────────────────────────────
5. LIVE SSE CLIENT (use-match-stream.ts) — BEHAVIOR MUST MATCH
──────────────────────────────────────────────────────────────────────────────

URL construction (lib/api.ts):
  const API_URL = "/api"
  streamUrl(...) → `/api/v1/job-matching/match-stream?candidate_id=...&jd_id=...&weights=...`
  weights query = URL-encoded JSON when present

Connection:
  const source = new EventSource(url, { withCredentials: true })

Event listeners (custom names — NOT generic "message"):
  "open"     → status = running
  "thought"  → JSON.parse → append to thoughts[]
  "result"   → JSON.parse → set result
  "error"    → set error message, status error
  "close"    → status done

Reconnect: ONE retry on unclean disconnect; clear thoughts+result before retry
Ticker: elapsedMs every 200ms while running/connecting
Derive agents{} for visualizer: idle|active|done|fallback|skipped|error
Derive signals: cacheHit, fastPath, criticSkipped, swarmHealth, groundedness, jdHygiene, locationFit
currentLayer from AgentThought.state: PRE_FLIGHT=1, SWARM=2, DEBATE=3, INSIGHT/DONE=4

DO NOT point EventSource at http://localhost:8000 — only same-origin /api via BFF.

──────────────────────────────────────────────────────────────────────────────
6. SWARM VISUALIZER (swarm-visualizer.tsx)
──────────────────────────────────────────────────────────────────────────────

18 agent nodes — IDs must match backend AgentThought.agent exactly:

  Layer 1: Orchestrator, JDHygieneAgent, LocationFitAgent
  Layer 2: SkillsAgent, ExperienceAgent, EducationAgent, DomainAgent, CultureAgent,
           GrowthAgent, ProjectsAgent, RiskAgent
  Layer 2.5: EvidenceVerifier, BiasAuditor
  Layer 3: Synthesizer, Critic, Arbitrator
  Layer 4: HRAdvisor, ExplainabilityAgent

Framer Motion: AnimatePresence on nodes; status rings (STATUS_RING map)
focusedAgent sync with AgentThoughtsStream click
Tooltips: latency, score, thought count
compact mode when stage=results

──────────────────────────────────────────────────────────────────────────────
7. AGENT THOUGHTS STREAM (agent-thoughts-stream.tsx)
──────────────────────────────────────────────────────────────────────────────

ScrollArea with auto-scroll during run
Filter Input by agent name / thought text
Phase chips: OBSERVE, ACT, REFLECT, etc.
Click row → onFocusAgent(agent) for graph sync
Relative timestamps from startedAt
PANEL_SHELL styling consistent with visualizer

──────────────────────────────────────────────────────────────────────────────
8. RUN HUD (run-hud.tsx)
──────────────────────────────────────────────────────────────────────────────

Shows: stream.status, elapsedMs, sinceLastEventMs, currentLayer, totalThoughts
Signal chips when metadata present: cache hit, fast-path, critic skipped,
  groundedness %, JD hygiene severity, location fit, specialist fallbacks

──────────────────────────────────────────────────────────────────────────────
9. MATCH RESULT VIEW (match-result-view.tsx)
──────────────────────────────────────────────────────────────────────────────

Tabs: overview | dimensions | debate | evidence | insights

overview:
  - Header: New Match, Run Again, Export JSON
  - Degraded swarm_health amber banner if placeholders used
  - Grid: ScoreGauge (220px) + rationale / strengths / gaps
  - ScoreRadar + ScoreBreakdown
  - RiskCard + BiasCard
  - AiHubFeedback if usage_event_id

Other tabs: DebatePanel, EvidencePanel, InsightsPanel with dimension cards

VerdictBadge: color per STRONG_HIRE, HIRE, CONSIDER, NO_HIRE, STRONG_NO_HIRE

Uses arbitrator.final_score / verdict / rationale; synthesis top_strengths/gaps

──────────────────────────────────────────────────────────────────────────────
10. DASHBOARD SHELL (layout.tsx)
──────────────────────────────────────────────────────────────────────────────

flex min-h-screen: Sidebar | (Header + main children) | QuantChat floating widget
main: flex-1 bg-slate-50/40 overflow-x-hidden
RequireAuth wrapper — for hackathon set NEXT_PUBLIC_HACKATHON_OPEN_DASHBOARD=true
  → require-auth.tsx returns children without redirect (see bundle patch)

Sidebar: QuantHire logo, nav groups, "Match" → /dashboard/job-matching with Target icon
Header: search placeholder, user dropdown (useAuth)

Copy QuantChat.tsx stack if included in zip (optional widget; same as QuantHire).

──────────────────────────────────────────────────────────────────────────────
11. BFF PROXY (app/api/[...path]/route.ts)
──────────────────────────────────────────────────────────────────────────────

Environment: BFF_BACKEND_URL default http://localhost:8000
Strip /api prefix when forwarding to backend /api/v1/...

LONG_RUNNING_PROXY_TIMEOUT_MS = 620000 for paths:
  v1/job-matching/match
  v1/job-matching/rank
  v1/job-matching/match-stream

For match-stream:
  Detect text/event-stream; stream response body without buffering
  Forward X-Accel-Buffering, no content-encoding from backend

next.config.js: compress: false

──────────────────────────────────────────────────────────────────────────────
12. NPM DEPENDENCIES (package.json from zip)
──────────────────────────────────────────────────────────────────────────────

Must include at minimum:
  next@15, react@18, typescript
  tailwindcss, tailwindcss-animate, tailwind-merge, class-variance-authority, clsx
  framer-motion@11, lucide-react
  axios, @radix-ui/react-* (tabs, scroll-area, progress, etc.)
  next-themes, @tanstack/react-query

Run: npm install && npm run dev -p 3000

──────────────────────────────────────────────────────────────────────────────
13. ENVIRONMENT (.env.local)
──────────────────────────────────────────────────────────────────────────────

BFF_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_USE_BFF=true
NEXT_PUBLIC_HACKATHON_OPEN_DASHBOARD=true

──────────────────────────────────────────────────────────────────────────────
14. MOCK BACKEND FOR UI-ONLY DEV (if API not ready yet)
──────────────────────────────────────────────────────────────────────────────

Temporary only — replace with real API before claiming done:
  Proxy still required; optional MSW or minimal FastAPI returning canned SSE.
Real acceptance requires live match-stream thoughts from backend agents.

──────────────────────────────────────────────────────────────────────────────
15. BUILD STEPS (ORDER)
──────────────────────────────────────────────────────────────────────────────

1. Create Next 15 app with App Router + TypeScript
2. Copy tailwind.config.ts, postcss.config.js, components.json, globals.css
3. Copy all src/ files from hssd-ui-bundle preserving @/ aliases in tsconfig paths
4. Copy public/brand
5. Implement BFF route exactly
6. npm install, fix any missing ui components by copying from zip
7. Start backend or mock SSE; open /dashboard/job-matching
8. Visual compare: header, stepper, launcher, live grid, result tabs
9. DevTools → Network → match-stream → text/event-stream + thought events

──────────────────────────────────────────────────────────────────────────────
16. UI ACCEPTANCE CHECKLIST (ALL REQUIRED)
──────────────────────────────────────────────────────────────────────────────

[ ] globals.css variables match #CC112F / #437A8B / emerald swarm accents
[ ] 3-stage stepper with emerald active state and spin on "Swarm run"
[ ] Launcher two-column picker + weight sliders + Launch Swarm button styling
[ ] During run: RunHud + 2-column SwarmVisualizer | AgentThoughtsStream
[ ] Graph shows 18 nodes with layer colors slate/emerald/cyan/amber/violet
[ ] Thoughts list updates live; filter works; click focuses graph node
[ ] Results: ScoreGauge, tabs, debate/evidence/insights render
[ ] Dark mode toggle works (next-themes) without broken contrast
[ ] BFF uses /api/v1/... not direct :8000
[ ] No console errors on happy path

──────────────────────────────────────────────────────────────────────────────
17. FORBIDDEN (UI TASK FAILS IF ANY)
──────────────────────────────────────────────────────────────────────────────

✗ Rebuilding page in Material UI / Chakra / default blue Tailwind only
✗ Replacing SwarmVisualizer with a static image or simple list
✗ Polling POST /match instead of EventSource match-stream for live run
✗ Removing Framer Motion node animations
✗ Changing tab names or removing Export JSON / Run Again
✗ Omitting emerald styling on HSS-D-specific elements
✗ 120s default fetch timeout on BFF for match-stream

──────────────────────────────────────────────────────────────────────────────
18. DELIVERABLES
──────────────────────────────────────────────────────────────────────────────

1. Runnable Next.js app with files copied from reference
2. README: npm install, .env.local, npm run dev
3. Screenshot: setup + running (graph) + results overview tab
4. UI_DEVIATIONS.md — must be empty or list only env/hackathon auth differences

Start with step 1. Copy from hssd-ui-bundle.zip before writing new JSX.

END OF UI MASTER PROMPT
````

---

## Attachment for Codex

Attach **`hssd-ui-bundle.zip`** (UI only) when using this prompt.