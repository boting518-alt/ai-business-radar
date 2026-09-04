# Frontend Architecture v0.1

## Goals and routing

`apps/web` is a desktop-first Next.js App Router product shell, not a marketing site. `/` routes
authenticated users to `/radar` and others to `/login`. The protected route group contains Radar,
opportunities, opportunity detail, signals, watchlist, and admin review routes matching the frozen
MVP. Pages are structural placeholders until their owning follow-up tasks.

## App shell and design

The shared shell provides a restrained intelligence-terminal sidebar, identity header, logout,
responsive content area, accessible focus behavior, tabular numerals, and neutral light/dark-aware
styling. Admin Review appears only after `/api/v1/auth/me` returns `admin`; backend authorization
remains authoritative. Reusable primitives cover headers, stats, score/stage badges, filters,
table shells, empty/error/loading states, and skeleton tables without scoring logic.

## Authentication and security

Supabase Auth uses `@supabase/ssr` browser/server clients and cookie refresh in Next.js `proxy.ts`,
following the current App Router SSR approach. Dashboard layouts validate a server session; admin
routes additionally resolve the application role from FastAPI. Email/password login and logout are
the only v0.1 auth interactions. The browser receives only the public Supabase URL/anon key and API
base URL. Database, service-role, JWT, AI, YouTube, and Redis secrets are forbidden.

## API client and types

One `ApiClient` owns base URLs, bearer headers, JSON parsing, no-store reads, typed errors, HTTP
status, safe message/details, and `X-Request-ID`. Components do not scatter raw `fetch` calls.
Methods cover every currently implemented product and review API.

OpenAPI TypeScript generation was evaluated. It is deferred because the backend does not yet
publish a checked-in reproducible OpenAPI artifact and generation by importing a configured live
app would make frontend installation depend on the Python environment. The small read boundary is
typed manually for this skeleton; TASK-024 may add an explicit export/generation pipeline before
expanding response types.

## Rendering and state

Layouts and read-heavy route shells are Server Components. Login, logout, and error retry are
Client Components because they are interactive. Initial skeleton pages do not fetch intelligence.
Future authenticated data can use the central client consistently. No Redux, React Query, global
business store, GraphQL, or response cache is introduced; URL params and local state are preferred.

## Errors, loading, and tests

The dashboard route group provides skeleton loading and a retryable error boundary without stack
traces. Opportunity absence has a safe not-found page. Vitest and Testing Library cover navigation,
role visibility, API authentication/error behavior, and structural pages. TypeScript, ESLint, tests,
and production build are required.

## Known limitations and TASK-024 transition

There is no signup/magic-link UI, theme toggle, mobile drawer, live Radar data, visualization,
review action UI, signal feed, or watchlist write flow. TASK-024 should connect `/radar` to the
existing typed API client and preserve this session/error/state strategy.
