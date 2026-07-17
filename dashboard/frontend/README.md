# PRForge Dashboard (React + Vite)

Web UI to view runs, inspect diffs, and approve.

## Dev mode (with hot reload)

```bash
cd dashboard/frontend
npm install
npm run dev      # Vite dev server on :5173, proxies /api to :8000
```

In another terminal:
```bash
prforge dashboard   # FastAPI on :8000
```

Open http://localhost:5173

## Production build

```bash
cd dashboard/frontend
npm run build      # outputs to dashboard/frontend/dist/
```

`prforge dashboard` auto-serves the built `dist/` at `/` if it exists.
