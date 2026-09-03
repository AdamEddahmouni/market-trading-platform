# GridIQ (DS 440 Capstone)

<h2 align="center"><a href="https://ds-440-capstone-gridiq-1.onrender.com">Open the live app (Render) — no setup</a></h2>

<p align="center"><strong><a href="https://ds-440-capstone-gridiq-1.onrender.com">https://ds-440-capstone-gridiq-1.onrender.com</a></strong></p>

<p align="center">Use this <strong>deployed</strong> site first — it skips clone, installs, env files, and every local startup step below.</p>

<hr />

AI football coach: chat, NFL dashboards, and a **Playbook** (routes, coverages, line of scrimmage). **Stack:** React (Vite) + FastAPI, SQLite by default, Gemini for chat.

**Install:** [Git for Windows](https://git-scm.com/downloads) (includes **Git Bash** — required for the front-end terminal **(Windows only)**; macOS/Linux: any terminal) · [Node.js 18+](https://nodejs.org/) (20+ recommended) · [Python 3.10+](https://www.python.org/downloads/) · optional [Docker](https://www.docker.com/products/docker-desktop/) for Postgres  

Windows: if `python` fails, use `py -3`. macOS/Linux: use `python3` if needed.

```bash
git clone https://github.com/lucasheller22/DS-440-CAPSTONE-GridIQ.git
cd DS-440-CAPSTONE-GridIQ
```

### Git Bash (Windows — front end)

Use **Git Bash** for the UI terminal so `npm` / Vite paths and shell scripts behave consistently.

1. Download **Git for Windows** from [https://git-scm.com/downloads](https://git-scm.com/downloads) (choose *64-bit Git for Windows Setup* unless you need 32-bit).
2. Run the installer. Recommended: keep **Git Bash Here** / **Git GUI Here** context menus enabled; use the default **Git from Git Bash only** or **Git from the command line and also from 3rd-party software** depending on your preference.
3. Finish the wizard, then open **Git Bash** (Start menu → *Git* → *Git Bash*).
4. Go to the repo and run the front-end commands from **Full stack** below (`cd gridiq-frontend`, `npm install`, `npm run dev`).

---

## Full stack (two terminals)

**Terminal 1 — API** (from `gridiq-backend`):

```bash
cd gridiq-backend
python -m venv .venv
```

Activate: **PowerShell** `.venv\Scripts\Activate.ps1` · **cmd** `.venv\Scripts\activate.bat` · **macOS/Linux** `source .venv/bin/activate`  
(PowerShell blocked? `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyarrow
```

Create `.env` from the example: `cp .env.example .env` (Mac/Linux/Git Bash) or `copy .env.example .env` (cmd/PowerShell).

Edit `.env`: set **`JWT_SECRET`** (long random string). Optional: **`GEMINI_API_KEY`** ([Google AI Studio](https://aistudio.google.com/)) for chat. More keys: **`gridiq-backend/.env.example`**.

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Windows: if `python -m uvicorn` fails, from `gridiq-backend` run `py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` instead.

The dashboard needs a Parquet engine (`pyarrow` from the install step above). If reads still fail, try also installing `fastparquet`: `python -m pip install fastparquet` (or `py -m pip install fastparquet` on Windows).

→ API **http://localhost:8000** · docs **http://localhost:8000/docs**

**Terminal 2 — UI** (Git Bash on Windows; macOS/Linux: any terminal):

```bash
cd gridiq-frontend
npm install && npm run dev
```

→ **http://localhost:5173** — register, log in, then Dashboard / Chat / Playbook.

For local UI without the API: **Settings → Use local mocks** or add `gridiq-frontend/.env` with `VITE_USE_MOCKS=true`. With the API running, use `VITE_API_BASE_URL=http://localhost:8000` if needed.

---

## Optional

- **Postgres:** `cd gridiq-backend && docker compose up -d db`, set `DATABASE_URL` in `.env` (see `.env.example`), then `python -m alembic upgrade head`.
- **Sync NFL data:** `curl -X POST "http://localhost:8000/api/games/sync/games?season=2025" -H "Authorization: Bearer <JWT>"` — only seasons in **`NFLVERSE_SEASONS`** (default **`2025`** in **`gridiq-backend/.env.example`**) can be synced.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No module named 'app'` | Run `uvicorn` inside **`gridiq-backend`**. |
| Chat idle / setup message | Add `GEMINI_API_KEY`, restart API. |
| Parquet / dashboard errors | Ensure **`pyarrow`** installed (`pip install …` above). |
| nflverse **400** / wrong season | Backend defaults to **`NFLVERSE_SEASONS=2025`** only. Add years in **`gridiq-backend/.env`** (comma-separated), restart the API, and align the Dashboard season picker if you change it. |
| UI ↔ API | Open **http://localhost:8000/docs**; match port in **Settings** or `VITE_API_BASE_URL` / `CORS_ORIGINS`. |

## License

[LICENSE](LICENSE)
