# Open KT documentation in Cursor

All KT files are on branch **`main`** under `docs/`. Use this page when you want to read or present from **Cursor**, not GitHub.

---

## A. You already have the repo open in Cursor

**One-click hub:** open [OPEN-KT-DOCS-IN-CURSOR.md](../OPEN-KT-DOCS-IN-CURSOR.md) at repo root (`Ctrl+P` → `OPEN-KT-DOCS`) and **Ctrl+click** any document link.

1. Pull latest KT files:
   ```bash
   git checkout main && git pull origin main
   ```
2. Press **`Ctrl+P`** (Windows/Linux) or **`Cmd+P`** (Mac).
3. Type one of these (partial match is enough) and press **Enter**:

| Type in Quick Open | Document |
|--------------------|----------|
| `KT-MASTER` | Full catalog + GitHub download links |
| `KT-OPEN-IN-CURSOR` | This file |
| `QuantHire-AI-architecture` | Session 1 — main architecture reference |
| `kt-session-1-presenter` | Session 1 — presenter pack |
| `kt-session-1-executive` | Session 1 — presenter script |
| `session-2-code-walkthrough` | Session 2 — full code walkthrough |
| `session-2-agentic` | Session 2 — agentic code tour |
| `agentic-systems-quick` | Session 2/3 — line-number handout |
| `session-3-quick-reference` | Session 3 — printout / live session |
| `session-3-ai-components-complete` | Session 3 — full reference |
| `session-3-executive` | Session 3 — presenter script |
| `local-development-without-docker` | Run without Docker |
| `nonprod-deploy-handover` | Non-Prod ACR build + AKS deploy (KT) |

4. **Markdown preview:** with the file open, **`Ctrl+Shift+V`** / **`Cmd+Shift+V`**.

5. **Sidebar:** **`Ctrl+Shift+E`** / **`Cmd+Shift+E`** → folder **`docs`** → click any `.md` file.

**Cmd/Ctrl + click** a link like [session-3-quick-reference.md](./session-3-quick-reference.md) in the editor to open that file in a new tab.

---

## B. Open the GitHub repo in Cursor (first time)

1. Install [Cursor](https://cursor.com).
2. **Cursor → File → Open Clone from GitHub…** (or clone in terminal):
   ```bash
   git clone https://github.com/Pradeep-Kumar25th/QuantHire-AI.git
   ```
3. **File → Open Folder…** → choose the cloned **`QuantHire-AI`** folder (repo root).
4. **`Ctrl+P`** → `KT-MASTER-INDEX` → Enter.

**Optional — open repo from browser:** on [github.com/Pradeep-Kumar25th/QuantHire-AI](https://github.com/Pradeep-Kumar25th/QuantHire-AI), use **Code** and, if shown, **Open in Cursor** (requires Cursor GitHub / desktop integration).

---

## C. Open several KT files at once (terminal)

From repo root, if the `cursor` CLI is on your PATH:

```bash
cursor docs/KT-MASTER-INDEX.md docs/QuantHire-AI-architecture-and-resources.md docs/session-3-quick-reference.md
```

---

## D. Cloud Agent / remote workspace

If you are in a **Cursor Cloud Agent** or remote dev environment with this repo checked out:

- Paths are under the workspace root, e.g. **`docs/KT-MASTER-INDEX.md`**.
- Same **Quick Open** shortcuts apply.
- In chat you can ask the agent to open or summarize a path, e.g. `@docs/session-3-quick-reference.md`.

---

## E. Troubleshooting

| Problem | Fix |
|---------|-----|
| File not found | `git checkout main && git pull origin main` |
| Old Session 3 only on `main`, Session 1 missing | Same — Session 1–3 are all on **`main`** now |
| Preview looks plain | Use **Markdown Preview** (`Ctrl+Shift+V` / `Cmd+Shift+V`) |

---

**Next:** [KT-MASTER-INDEX.md](./KT-MASTER-INDEX.md) for the full document list and GitHub raw download links.
