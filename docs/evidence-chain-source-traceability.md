# Evidence Chain and Source Traceability v0.1

## Canonical read model

TASK-044E repairs the split between linked FACT counts and the formerly explicit-only evidence
list. Product reads do not materialize or generate evidence. The existing evidence endpoint queries
one SQL UNION of:

1. Active Signals linked to the active Opportunity, retaining `relationship_type`.
2. Active Signals referenced by explicit `opportunity_evidence`, when not already linked.
3. Standalone explicit/editorial records with no Signal reference.

Links have no status. Signal visibility is `status = active`. Linked records may be supporting,
contradicting, context, or candidate_match; the UI preserves that distinction. The public endpoint
returns 404 for absent/non-active opportunities even to admins; internal review remains separate.
Explicit references to review/rejected/ignored Signals are excluded. The global Signals feed
continues to show active Signals without a published Opportunity, with only active opportunity
names/IDs in its related list.

## Counts and deduplication

`active_signal_count` retains its existing meaning: all active linked Signals.
`supporting_signal_count` counts only links with `relationship_type = supporting`.
Distinct video/channel counts and the existing type counts use the same active linked universe.
These are record/source counts, not independent corroboration or independent customers.
No score/trend formulas or stored aggregates change.

The evidence envelope's `total` counts eligible records after the optional Signal type filter.
Standalone explicit evidence contributes to that total but not linked Signal counts. Explicit-only
Signal references also contribute to evidence total, not linked counts. Standalone explicit rows
have no signal_type and appear under All. Each page contains at most `limit` items; `has_more` is
computed from total, offset, and returned length.

One linked Signal appears once; explicit references to it do not create another card. Multiple
explicit-only references to one Signal choose the lowest explicit record UUID deterministically.
Standalone explicit records keep their own UUID. Persisted editorial rows remain untouched;
Signal-backed projections present canonical Signal content rather than historical copied summaries.
Similar text, shared video/comment IDs, and extraction versions do not define duplication. Historical
semantic/version repair belongs to TASK-044F; the schema has no Signal superseded status.

## Public provenance

Both evidence and Signals return persisted `source_video_id`, `youtube_video_id`, `video_title`,
`channel_name`, `source_comment_id`, `youtube_comment_id`, `source_comment_text`, `source_url`, and
`source_navigation`. Comment sources resolve their canonical parent video via `comments.video_id`.
Neither AI text nor discovery snippets supply source identity. No author hash, raw AI/parsed output,
provider metadata, or review notes enter the public models.

A valid persisted 11-character YouTube ID yields `https://www.youtube.com/watch?v=<id>`.
Comment navigation uses that parent video and `source_navigation = parent_video`; there is no
invented timestamp or exact comment location. Standalone editorial rows may use a saved http(s)
URL with hostname and without embedded credentials. Other malformed/missing identities yield null
URL and `unavailable`, retaining the evidence text. `video`, `parent_video`, or `external` means
navigable from stored provenance; it does not mean the remote resource was verified as available.
The database does not currently track remote deletion, so GET requests do not claim to detect it
or probe YouTube. External links use `_blank` and `noopener noreferrer`.

`observed_at` remains persisted source observation time, never Opportunity updated_at. No source
snapshot fallback is invented for null timestamps.

## Localization and claim meaning

The API defaults to en-US. zh-CN uses stored current-version, matching-source-hash projections of
Signal statement/evidence. Missing or stale translations fall back to canonical English. Both
`original_statement` and `original_evidence_text` retain canonical extracted intelligence. They are
not necessarily verbatim source quotations. Stored RAW comment text is separate and explicitly
labeled original source comment; it is not translated. Video/channel names remain source metadata.
A toggle reveals canonical statement and excerpt when either is localized.

Claim status is displayed unchanged with locale labels. `creator_claim` remains an attributed
claim; `fact` is the persisted extraction classification, not a new verification action. Explicit
records without a Signal have null claim status rather than an invented fact label.

## API, pagination and performance

`GET /api/v1/opportunities/{identifier}/evidence` accepts UUID or slug, `offset >= 0`,
`limit = 20` (1–100), `locale = en-US|zh-CN`, and optional canonical `signal_type`.
Response: `{items, total, offset, limit, has_more}`. Items retain legacy summary/evidence_type fields
and add evidence_kind, Signal identity/content/claim/relationship, provenance and localization.
Sorting is observed_at descending, null last, then evidence_kind and evidence_id ascending.
The API and frontend are upgraded together from the previous array response.

Visibility lookup, count, and SQL-limited joined page take three queries. zh-CN adds at most one
localization batch. Query count does not grow per evidence card (integration regression checks
one item versus all fixture items). Signals likewise batches Signal and opportunity-name localization.
No LLM, provider/network call, write, taxonomy per-row lookup, or page-side source request occurs.

## UI and limitations

Opportunity detail has All/Pain/Purchase intent/Pricing/Revenue/Competition/Workflow filters,
20-item pagination, related Signals navigation with the Opportunity UUID, relationship/claim labels,
source links and canonical-text toggles. Signal type filter and evidence offset are URL state.
True empty, filtered/out-of-range page empty, and incomplete source are distinguished. Signals
already accepts opportunity_id from URL and displays its name from available returned context.

The page still reloads its four bounded API reads together. Offset pagination is stable over
unchanged data, not a snapshot across concurrent ingestion. No direct-comment anchor, historical
semantic repair, external availability monitoring, new source ingestion, or multi-source thesis
generation is claimed. The task does not mark staging or production ready.
