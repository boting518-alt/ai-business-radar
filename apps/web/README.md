# Web application

The Next.js 16 App Router frontend uses TypeScript, Tailwind CSS, shadcn-compatible primitives,
and cookie-based Supabase SSR authentication.

```bash
cd apps/web
pnpm install
pnpm dev
```

The frontend runs at `http://localhost:3000` and expects FastAPI at `http://localhost:8000`.
Configure `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and
`NEXT_PUBLIC_API_BASE_URL` in `.env.local`. Never place a service-role key in frontend env.

Run `pnpm typecheck`, `pnpm lint`, `pnpm test`, and `pnpm build` before committing. The repository
uses pnpm consistently and checks in only `pnpm-lock.yaml`.

For real Radar data, configure the backend database/authentication environment and run it in a
second terminal:

```bash
cd apps/api
uv sync
uv run uvicorn ai_business_radar_api.main:app --reload
```

The web application has no production mock-data mode; UI fixtures exist only in the test suite.

API types are currently a small product-facing boundary in `lib/api/types.ts`. OpenAPI generation
was evaluated but deferred until the backend exports a checked-in OpenAPI artifact; do not edit
the frontend into a second business-logic authority.
