# QUORUM web

Next.js operations UI for the QUORUM attention-aware coordination backend.

From this directory:

```bash
npm install
npm run dev
```

The browser opens at `http://localhost:3000`. The server-side rewrite in
`next.config.ts` forwards `/api/quorum/*` to the backend defined by
`QUORUM_API_BASE_URL` (default `http://127.0.0.1:8000`).

Validation commands:

```bash
npm run lint
npm run typecheck
npm run build
```

See `../docs/frontend-development.md` for the complete two-process local setup
and current product limitations.
