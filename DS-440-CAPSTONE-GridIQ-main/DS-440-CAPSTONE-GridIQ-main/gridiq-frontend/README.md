# GridIQ Frontend Starter (Vite + React + TS)

This is a front-end starter framework for **GridIQ**: an assistant coach UI with a football dashboard + chat interface.

## Requirements
- Node.js 18+ (recommended 20)
- VSCode (recommended extensions: ESLint, Prettier, Tailwind CSS IntelliSense)

## Quickstart
```bash
cd gridiq-frontend
npm install
npm run dev
```

Open http://localhost:5173

## Where to build next
- `src/pages/Chat.tsx` — threaded chat UI + streaming placeholder
- `src/pages/Dashboard.tsx` — team/game filters + insight cards
- `src/pages/Playbook.tsx` — play visualizer (SVG field) + route concepts
- `src/lib/api/` — API client + endpoints (swap to your backend when ready)

## Env
Create `.env` with:
```bash
VITE_API_BASE_URL=http://localhost:8000
```

> **Mocks note**  
> You can run offline by enabling **Settings → Use local mocks** or setting
> `VITE_USE_MOCKS=true`. In mock mode, chat returns a synthetic assistant reply.

## Tech decisions
- React Router for routing
- TanStack Query for server state / caching
- Zustand for lightweight app state (auth, UI)
- Zod for runtime validation of API payloads
- Tailwind for styling
