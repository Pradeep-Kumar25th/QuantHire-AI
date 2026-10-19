# READ ME FIRST — Run QuantHire AI on your laptop

You received the **QuantHire AI** folder (zip from Teams).

**Full step-by-step guide (start here):**

→ **`docs/LOCAL-SETUP-GUIDE-ZIP-HANDOVER.md`**

Open that file in Notepad, VS Code, or Cursor.

---

**Quick summary**

1. Install **Node 20** and **Python 3.11**.  
2. Unzip to e.g. `D:\QuantHire AI`.  
3. **Do not use** the included `venv` or `node_modules` — recreate on your PC (see guide §4).  
4. Copy **`.env.example`** → **`.env`** at project root; set **`MILVUS_ENABLED=false`**.  
5. Copy **`apps\web\.env.example`** → **`apps\web\.env.local`** with `BFF_BACKEND_URL=http://localhost:8000`.  
6. Start Postgres (guide §6) for login and data.  
7. **Terminal 1:** API — `python run.py` in `apps\api` (see guide §7).  
8. **Terminal 2:** Web — `npm run dev` in `apps\web` (see guide §8).  
9. Browser: **http://localhost:3000**

**Use Non-Prod without local setup:** https://quanthire-npd.malomatia.com (Entra/TAMM access).

---

Other docs: **`docs/`** folder (BRD, consolidated technical documentation, deploy guide).
