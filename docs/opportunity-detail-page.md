# Opportunity Detail Page v0.1

## Purpose and information hierarchy

`/opportunities/[id]` is the authenticated intelligence dossier for one active opportunity. It
answers what the opportunity is, who it serves, which commercial problem it addresses, how current
intelligence scores it, how activity changes across time windows, and which evidence supports it.
The route accepts either the backend UUID or slug without exposing opportunity visibility status.

The order is identity and timestamps, four key intelligence metrics, business thesis, latest trend
overview, score breakdown, evidence summary and records, history, and stable metadata. This keeps
decision-critical information above audit detail without presenting the page as marketing copy.

## API dependencies and loading

The page resolves one Supabase browser session and uses the centralized `ApiClient`. It starts the
following authenticated reads in parallel:

- `GET /api/v1/opportunities/{id-or-slug}`
- `GET /api/v1/opportunities/{id-or-slug}/trends?window_type=...&limit=50`
- `GET /api/v1/opportunities/{id-or-slug}/scores?limit=50`
- `GET /api/v1/opportunities/{id-or-slug}/evidence?offset=...&limit=10`

The page performs no item-level follow-up requests. `trend_window` and `evidence_offset` are stored
in the URL so the selected history and evidence page remain shareable. The trend default is 7d.

## Score and trend presentation

Opportunity Score, Confidence, Hype Risk, and the selected window's Momentum come directly from
the current detail response. The seven score component values are shown as native progress meters
and exact numeric labels; the browser does not combine them or recreate `score-v001`.

The latest 7d, 30d, and 90d summaries display persisted momentum, video, new-video, channel,
comment, pain, demand, purchase-intent, and revenue counts. Trend history switches among those
three backend windows and uses a compact table instead of a new chart dependency. Score history
shows calculation time, Opportunity Score, Confidence, and Hype Risk and never receives or exposes
`inputs_snapshot`.

## Evidence presentation and safety

The detail response's evidence summary supplies Signal, Video, Channel, Pain, Demand, Purchase
Intent, and Revenue totals. Supporting evidence is fetched in bounded pages of ten. Each row may
show evidence type, safe summary, source type, observation date, strength, confidence, and video
title.

The UI does not render comment author identity, raw AI/provider output, scoring input snapshots,
provider request identifiers, or internal extraction errors. Watchlist state is visible but has no
mutation control because the write workflow remains assigned to TASK-027.

## Missing data and errors

Null metric values render as an em dash. Null business fields are omitted rather than displayed as
empty labels. Missing latest trends, trend history, evidence, current scoring, and score history
each have explicit section-level empty states without neutral or fabricated replacements.

An unauthenticated response returns to login. A 404 always says “Opportunity not found or
unavailable” so hidden status cannot be inferred. Other failures use the shared retry state and
display the API correlation request ID when supplied.

## Responsive behavior

The page is desktop-first but all overview grids collapse into stacked sections on small screens.
Core metrics remain a compact two-column grid on mobile. Historical tables have their own bounded
horizontal scroll container so the overall page does not overflow.

## Known limitations

- Evidence pagination cannot show an exact page total because the current endpoint returns a list
  without total metadata; Next is enabled only when the current page is full.
- Trend and score history are textual tables without charts.
- Watchlist state is read-only.
- Page-level URL changes currently refresh the four bounded detail requests together.
