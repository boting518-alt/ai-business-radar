# Opportunity Library v0.1

## Purpose

The authenticated Opportunity Library is the durable catalogue of published (`active`)
opportunities. It is distinct from Radar: Radar emphasizes ranking within a selected trend window,
while the library emphasizes retrieval, filtering, stable pagination, and watchlist management.

## API contract

`GET /api/v1/opportunities` accepts `q`, `industry_code`, `customer_code`, `market_stage`,
`min_score`, `max_score`, `min_confidence`, `max_hype_risk`, `watchlisted`, `sort`, `page`,
`page_size`, and `locale`. Page sizes are restricted to 20, 50, or 100 and default to 20.
The default sort is `last_activity_desc`; other sorts are `first_detected_desc`, `score_desc`,
`confidence_desc`, `momentum_desc`, and `name_asc`.

Only active opportunities are returned. Search covers the displayed locale's current stored
name, thesis, problem, and solution projections, with canonical fallback. Reads never invoke an
LLM. Each row includes current score/confidence/hype risk, the latest persisted 7-day momentum,
batched evidence counts, taxonomy projections, timestamps, and user-specific watchlist state.

## Frontend behavior

`/opportunities` keeps filters, sort, page, and page size in the URL. It provides desktop and
mobile result layouts, authenticated loading/error handling, distinct unfiltered and filtered
empty states, detail links, and the shared watchlist mutation control. The backend remains the
authority for visibility, filtering, ordering, and paging semantics.

## Known limit

The v0.1 service performs filtering and paging over a bounded in-process projection assembled by
fixed-count batched database queries. This avoids N+1 access and is suitable for the current MVP
dataset. A single SQL page/count query should replace it before catalogue size requires database-
native search indexes and keyset pagination.
