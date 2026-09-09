# TASK-044E — Evidence Chain + Source Traceability v0.1 (revised)

Status: Complete. Revised and validated 2026-09-09. See artifacts/evidence-chain/2026-09-09/validation-report.md for results and limitations.

## Goal and scope

Repair Opportunity → linked Signal → persisted Video/Comment provenance → source navigation,
including stored zh-CN localization and canonical intelligence text. Extend the existing evidence
endpoint and Signals UI. No new evidence generation, schema migration, prompts, scoring,
normalization, historical semantic repair, transcripts, ingestion sources, or publishing behavior.

## Corrections to the proposed task

1. `opportunity_signal_links` has no status. Eligibility is `Signal.status = active` and, for
   opportunity evidence, `Opportunity.status = active`. Preserve and display relationship_type;
   contradicting/contextual evidence is not supporting evidence.
2. Keep `active_signal_count` as all active linked signals for compatibility. Add supporting count.
   Distinct videos/channels describe source diversity, not independent corroboration/customers.
   Evidence pagination reports filtered total and has_more; explicit records and page size need
   not equal linked signal count. Explain any difference.
3. Deduplicate by record identity only. A Signal linked to this opportunity and also referenced
   by opportunity_evidence appears once. Multiple explicit references to one active Signal appear
   once. Standalone explicit evidence retains its own record identity. Do not merge similar text,
   shared videos, extraction versions, or infer supersession from AIExtraction alone (TASK-044F).
4. Opportunity endpoints hide candidates from all public readers. The global Signals feed keeps
   existing semantics: active signals remain visible without an active linked opportunity.
5. English canonical statement/evidence is extracted intelligence, not necessarily verbatim RAW
   source text. Label canonical text and stored RAW comment text separately. Localizations are
   hash/version-validated stored projections; missing/stale values fall back without provider calls.
6. Use `GET /api/v1/opportunities/{identifier}/evidence`; return a typed envelope with items,
   total, offset, limit and has_more. Accept locale and current signal_type values; default20,
   maximum100. Coordinate API/types/UI/tests/docs; do not add a redundant endpoint.
7. URLs use persisted RAW video IDs, never model text. Comment evidence links to its parent
   video and exposes stored comment text/identity, without invented precise location. A URL means
   navigation is possible, not remote availability verified. Missing provenance retains evidence
   with an explicit limitation. No source probes or paid calls during reads.
8. Record actual current Dental/Micro Duck baselines; 40/4/4 is historical, not a fixed assertion.

## Read model and implementation

- SQL query projection combines linked active Signals with eligible explicit evidence; no copies
  or writes on read. Explicit records referencing inactive Signals are excluded.
- Return signal/evidence identity, kind, relationship, statement/excerpt, claim status, observed_at,
  strength/confidence, video/channel/comment provenance, source URL and localization flags.
- Sort observed_at descending (null last), then stable kind/record identity. SQL pagination and
  filtering precede batch localization. Joins and localization must not grow per evidence row.
- Opportunity UI displays evidence, claim/type/relationship labels, original canonical toggle,
  source navigation, required type filters, pagination, and related Signals link using UUID.
- Signals source links use the same provenance contract. Preserve URL-driven opportunity filter.
- Distinguish true empty, filtered/page empty, and evidence with incomplete source metadata.
- Preserve opportunity_evidence and existing active-signal scoring semantics.

## Validation and delivery

Read AGENTS and source-of-truth docs; inspect runtime baseline before edits. Cover linked evidence
without explicit rows; video/comment/missing provenance; localization and stale fallback; hidden
statuses/candidate visibility; explicit evidence and dedupe; contradiction counts; SQL pagination,
filtering and bounded query count; response safety; frontend rendering, links, locales, toggles,
filters and related navigation. Run API, PostgreSQL integration, workers, shared schema, Ruff,
frontend tests/lint/typecheck/build and real browser Dental/Micro Duck checks.

Update evidence-chain-source-traceability.md, opportunity-detail-page.md, signal-semantics.md,
frontend-architecture.md, api-contract.md and development-plan.md. Save actual validation and
limitations under artifacts/evidence-chain/2026-09-09/. Mark done only when verified; preserve
TASK-047/048 and append 044F–K, 045/046. No production-ready assertion.

Preserve unrelated artifacts and generated next-env.d.ts. Review diff and create focused commit:
`feat: connect opportunity evidence to source provenance`. Do not push.
