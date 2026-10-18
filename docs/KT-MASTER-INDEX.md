# QuantHire AI — KT & handover documentation index

**Prepared:** Oct 7–15, 2026 (Sessions 1–3, architecture deep-dives, local dev guide)  
**Repository:** [Pradeep-Kumar25th/QuantHire-AI](https://github.com/Pradeep-Kumar25th/QuantHire-AI)  
**Non-Prod:** https://quanthire-npd.malomatia.com  

Use this page to find and download every KT document.

| Where to open | How |
|---------------|-----|
| **Cursor (recommended)** | **`Ctrl+P`** / **`Cmd+P`** → type **`KT-OPEN-IN-CURSOR`** or see [KT-OPEN-IN-CURSOR.md](./KT-OPEN-IN-CURSOR.md) |
| **GitHub (browser / raw download)** | Links in sections below, or **Code → Download ZIP** |

---

## Open in Cursor (local IDE)

### One-time setup

1. **Clone** (if you do not have the repo yet):
   ```bash
   git clone https://github.com/Pradeep-Kumar25th/QuantHire-AI.git
   ```
2. **Open the repo as a folder:** Cursor → **File → Open Folder…** → select the `QuantHire-AI` directory (repo root, not only `docs/`).
3. **Use the branch that has all KT files:**
   ```bash
   git checkout main
   git pull origin main
   ```

### Fastest ways to open a doc

| Action | Windows / Linux | macOS |
|--------|-----------------|--------|
| **Quick Open** (type filename) | `Ctrl+P` | `Cmd+P` |
| **Quick Open by path** | `Ctrl+P` then paste path below | `Cmd+P` |
| **Markdown preview** | `Ctrl+Shift+V` | `Cmd+Shift+V` |
| **Explorer: `docs` folder** | `Ctrl+Shift+E` → expand **docs** | `Cmd+Shift+E` |

**Start here in Quick Open (`Ctrl+P` / `Cmd+P`):** type `KT-MASTER-INDEX` and press Enter.

### Paths to paste in Quick Open (`Ctrl+P` / `Cmd+P`)

Copy a path, paste into Quick Open, Enter:

```
docs/KT-MASTER-INDEX.md
docs/QuantHire-AI-architecture-and-resources.md
docs/session-1-architecture-and-resources-complete.md
docs/kt-session-1-presenter-pack.md
docs/kt-session-1-executive-presenter-script.md
docs/kt-session-1-architecture-and-resources.md
docs/project-resources-inventory.md
docs/jd-generation-architecture.md
docs/session-2-code-walkthrough-complete.md
docs/session-2-agentic-code-tour.md
docs/agentic-systems-quick-reference.md
docs/session-3-README.md
docs/session-3-quick-reference.md
docs/session-3-ai-components-complete.md
docs/session-3-executive-presenter-script.md
docs/session-3-ai-agents-observability-presenter-pack.md
docs/local-development-without-docker.md
QuantHire-AI-architecture-and-resources.md.txt
SESSION-3-QUICK-REFERENCE.md
```

### Open several docs at once (optional)

- **File → Open File…** and multi-select from `docs/`.
- Or in the terminal (repo root), Cursor CLI if installed:
  ```bash
  cursor docs/KT-MASTER-INDEX.md docs/session-3-quick-reference.md
  ```

### If a file does not appear

You are probably on an old branch or stale clone. Run `git checkout main && git pull origin main`, then try Quick Open again.

---

## Session 1 — Architecture & resources

| Document | Purpose |
|----------|---------|
| [QuantHire-AI-architecture-and-resources.md](./QuantHire-AI-architecture-and-resources.md) | **Primary complete reference** — diagrams, Azure resources, rationale (uploaded consolidated doc) |
| [session-1-architecture-and-resources-complete.md](./session-1-architecture-and-resources-complete.md) | Full Session 1 agenda coverage (alternate complete doc) |
| [kt-session-1-architecture-and-resources.md](./kt-session-1-architecture-and-resources.md) | Session 1 architecture & Azure resources guide |
| [kt-session-1-presenter-pack.md](./kt-session-1-presenter-pack.md) | Presenter pack: diagrams + full speaking script |
| [kt-session-1-executive-presenter-script.md](./kt-session-1-executive-presenter-script.md) | Executive presenter script (Session 1) |
| [project-resources-inventory.md](./project-resources-inventory.md) | Azure / infra resource inventory |
| [jd-generation-architecture.md](./jd-generation-architecture.md) | JD generation workflow architecture |

**Root copy (same as architecture complete, `.txt` extension):** [../QuantHire-AI-architecture-and-resources.md.txt](../QuantHire-AI-architecture-and-resources.md.txt)

---

## Session 2 — Code walkthrough & agentic systems

| Document | Purpose |
|----------|---------|
| [session-2-code-walkthrough-complete.md](./session-2-code-walkthrough-complete.md) | Full code walkthrough: repo layout, auth, data, deploy, limitations |
| [session-2-agentic-code-tour.md](./session-2-agentic-code-tour.md) | Agentic systems code tour (JD, resume, matching, QuantChat paths) |
| [agentic-systems-quick-reference.md](./agentic-systems-quick-reference.md) | **Handout** — Layer \| File \| Function \| Line \| Brief tables |

---

## Session 3 — AI components, agents & observability

| Document | Purpose |
|----------|---------|
| [session-3-README.md](./session-3-README.md) | Session 3 mini-index |
| [session-3-quick-reference.md](./session-3-quick-reference.md) | **Live session / printout** — main line tables + demo paths |
| [session-3-quick-reference.txt](./session-3-quick-reference.txt) | Plain-text copy of quick reference |
| [Session3QuickReference.md](./Session3QuickReference.md) | Alternate filename (same family as quick reference) |
| [session-3-executive-presenter-script.md](./session-3-executive-presenter-script.md) | Spoken KT script |
| [session-3-ai-components-complete.md](./session-3-ai-components-complete.md) | Full reference + master line index |
| [session-3-ai-agents-observability-presenter-pack.md](./session-3-ai-agents-observability-presenter-pack.md) | Agenda + timeboxing |

**Root shortcut:** [../SESSION-3-QUICK-REFERENCE.md](../SESSION-3-QUICK-REFERENCE.md)

---

## Onboarding & operations (cross-session)

| Document | Purpose |
|----------|---------|
| [local-development-without-docker.md](./local-development-without-docker.md) | Run frontend + API natively (for engineers avoiding heavy Docker images) |
| [nonprod-deploy-handover-guide.md](./nonprod-deploy-handover-guide.md) | **Non-Prod deploy:** ACR build/push, AKS rollout, Alembic (KT handover) |
| [TECHNICAL-HANDOVER-TO-MALOMATIA.md](./TECHNICAL-HANDOVER-TO-MALOMATIA.md) | **Email Hazim/Shraddha:** consolidated handover + BRD note + local setup pointer |

---

## Suggested reading order for handover (e.g. Farhaan)

1. [KT-MASTER-INDEX.md](./KT-MASTER-INDEX.md) (this file)  
2. Session 1: [QuantHire-AI-architecture-and-resources.md](./QuantHire-AI-architecture-and-resources.md)  
3. Session 2: [session-2-code-walkthrough-complete.md](./session-2-code-walkthrough-complete.md) + [agentic-systems-quick-reference.md](./agentic-systems-quick-reference.md)  
4. Session 3: [session-3-quick-reference.md](./session-3-quick-reference.md) → [session-3-ai-components-complete.md](./session-3-ai-components-complete.md)  
5. Local setup: [local-development-without-docker.md](./local-development-without-docker.md)

---

## Download entire `docs/` folder (Git)

```bash
git clone https://github.com/Pradeep-Kumar25th/QuantHire-AI.git
cd QuantHire-AI/docs
```

Or download ZIP from GitHub: **Code → Download ZIP**.
