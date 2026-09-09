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

TASK-041 verified real hosted asymmetric JWT/JWKS login against local FastAPI, exact localhost CORS,
SSR publishable-key boundaries, and absence of server secret values from the production bundle.

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

## Radar implementation

`/radar` is a client data surface inside the authenticated server-rendered dashboard layout. It
obtains the current Supabase access token, makes exactly one list request through `ApiClient`, and
renders the persisted `RadarResponse`; it does not calculate scores, infer stages, or issue
per-row requests. A 401 returns the browser to login, while other API failures remain retryable
and preserve request correlation IDs.

Radar query state is encoded in URL search parameters. Time window, query, classification and
numeric filters, sorting, direction, and offset therefore remain bookmarkable. Filter and sort
changes reset offset; previous/next pagination keeps the 25-item backend limit. Search is
explicitly submitted rather than requested on every keystroke.

The information surface is a dense semantic table on desktop and a compact stacked list below
the large breakpoint. Both display backend score, Confidence, Hype Risk, momentum, stage,
evidence counts, and read-only watchlist state. Null intelligence uses an em dash. Loading keeps
the controls visible with a table skeleton; empty states distinguish an unpopulated Radar from a
filtered result with no matches.

## Opportunity detail implementation

`/opportunities/[id]` accepts the backend's UUID-or-slug identifier and renders an authenticated
intelligence dossier. After resolving the browser session, it starts detail, bounded trend
history, bounded score history, and paginated evidence reads together with `Promise.all`. There
are no per-evidence, per-video, or per-history-row requests. The four typed responses remain
separate because the detail endpoint intentionally carries only current intelligence and compact
summaries.

The detail response owns identity, business thesis, current score components, latest 7d/30d/90d
trends, evidence totals, and watchlist state. History and evidence endpoints supply their own
sections. The frontend formats dates, prices, and null values only; it never recomputes a score or
infers market stage. `trend_window`, `evidence_signal_type` and `evidence_offset` are URL state, with trend history bounded
to 50 rows and evidence pages bounded to 20 rows.

The dossier uses a dense research layout: header and key metrics first, then business thesis,
three-window trend overview, seven persisted score components, evidence totals and supporting
evidence, followed by trend/score history and metadata. Sections stack naturally on small screens;
history tables alone use bounded horizontal scrolling. A 404 uses the same message for missing and
invisible records. Evidence renders only the safe API fields and excludes author identity, raw AI
output, reproducibility inputs, and provider internals.

## Admin review implementation

`/admin/review` is a URL-addressable queue/detail workspace. Its default queue is `pending`, with
status, type, assignee, offset, and selection encoded in search parameters. Queue reads are bounded
to 25 tasks. Detail reads use the safe presentation projection documented in the API contract; the
component never displays arbitrary context JSON or AI provenance internals.

Claim and decision mutations go only through `ApiClient`. The interface waits for confirmed server
results, prevents duplicate submission, refreshes the queue, and advances selection after success.
Conflict, validation, missing-record, and authorization states fail safely and retain request IDs.
Merge targets are bounded by task context and require an explicit confirmation dialog describing
the history-preserving merge behavior. Backend workflow validation remains authoritative.

## Signals and watchlist implementation

`/signals` consumes one safe chronological feed request and keeps every supported filter and page
position in URL parameters. It uses semantic list/article markup, compact metadata, explicit claim
labels, and responsive columns without locally reordering server pages. No author or raw extraction
data is rendered.

`/watchlist` consumes one product-ready response containing current persisted intelligence. Radar,
opportunity detail, and the watchlist page reuse a single local-state mutation control. Add/remove
state changes only after the API confirms it; no global cache, direct database access, scoring, or
optimistic domain mutation is introduced.

## Known limitations after MVP QA

## Opportunity Library implementation

## Discovery Operations Console

`/admin/discovery` is protected by the existing server-side admin layout. It provides bounded topic
creation, multiple-query editing, system status, topic actions, latest result and estimated quota.
All mutations call admin APIs and never invoke YouTube from the browser.

`/opportunities` is a URL-driven authenticated catalogue, separate from the trend-window-oriented
Radar. It delegates search, taxonomy/stage/metric/watchlist filters, deterministic sort, and
20/50/100-item pagination to the product API. Results reuse the shared stage, score, error/empty,
and watchlist controls and link to the canonical opportunity dossier. See
`docs/opportunity-library.md`.

TASK-040 adds optional canonical industry/customer projections and code filters. Normal UX displays
localized labels and retains source-derived free text; admin/debug surfaces may expose codes.

There is no signup/magic-link UI, theme toggle, mobile drawer, or visualization. Industry, business
model, and customer type remain exact text filters because
no taxonomy endpoint exists. Detail history is presented as compact tables without a charting
dependency. The review queue has no total count or admin directory. Signals have no total count,
and v0.1 presents one logical personal watchlist without list management. End-to-end validation
status and deployment gaps are maintained in `docs/mvp-release-readiness.md`.

## Localization and Signal semantics

Fixed UI text uses a small typed React context and dictionaries rather than a routing-scale i18n
framework. It supports `zh-CN` (default) and `en-US`, initializes identically during SSR/hydration,
persists the preference locally, and centralizes canonical enum display labels. The locale selector
also refreshes localized Radar, Signal, and Opportunity detail reads through the explicit API
locale parameter.

Dynamic intelligence never enters the UI dictionary. The backend returns a stored localized
projection or canonical fallback. Signal cards distinguish statement from evidence, display
industry/customer/claim as separate semantic fields, retain original translated evidence behind a
toggle, and keep video/channel proper names unchanged. See `docs/signal-semantics.md` and
`docs/intelligence-localization.md`.

## Evidence chain presentation (TASK-044E)

The existing evidence endpoint returns an EvidencePage envelope. Dossier filters, total and Next
use server metadata, with a UUID link to related Signals. EvidenceList renders typed public records;
SourceTrace is shared with Signals for safe external links, parent-video labels, RAW comment text,
and incomplete-source fallback. Canonical extracted English and stored zh-CN projections remain
separate from RAW text. Batch localization and provenance joins happen in the API, without per-card
requests. Supporting vs contradicting/context links keep their stored meanings.
