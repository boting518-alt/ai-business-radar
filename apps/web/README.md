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

Run `pnpm typecheck`, `pnpm lint`, `pnpm test`, and `pnpm build` before committing. This host does
not provide npm, so the repository uses the available pnpm toolchain and checks in
`pnpm-lock.yaml`.

API types are currently a small product-facing boundary in `lib/api/types.ts`. OpenAPI generation
was evaluated but deferred until the backend exports a checked-in OpenAPI artifact; do not edit
the frontend into a second business-logic authority.
