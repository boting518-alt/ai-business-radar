# Opportunity business-case consolidation v0.1

## Meaning and precedence

An Opportunity represents a commercially scoped pattern, not a vendor feature summary. The
normalizer's existing MATCH/CREATE behavior is unchanged. A separate machine business case
synthesizes current linked evidence; canonical Opportunity fields remain human-authoritative.
A completed case never automatically updates a field, changes a score or publishes a candidate.

Information classes are source_grounded (attributed observations, preserving claim status),
editorial_synthesis (derived interpretation), hypothesis (explicit uncertainty), and unknown.
A source-grounded creator claim is still a claim. Machine prose is never independent verification.
Customer means the evidenced buyer/user/operator scope; taxonomy is guidance, not new evidence.
A beneficiary such as a dental patient is not automatically the purchaser.

## Dimensions and typed contract

`OpportunityConsolidationOutput` in the shared Python schema package defines:
customer_summary, problem_summary, workflow_summary, solution_pattern, business_model_summary,
pricing_summary, revenue_summary, distribution_summary, competition_summary, adoption_summary,
build_complexity_summary, plus validation_gaps. JSON Schema is generated from that contract.

Each dimension has text, evidence_signal_ids, information_class, support_level and uncertainty.
Supported/partially_supported require nonempty text and valid evidence IDs. Unknown requires null
text and no references. Hypotheses require explicit uncertainty and cannot invent pricing,
revenue, adoption or distribution. Confidence is deliberately not a proxy for support.

Application validation rejects foreign/non-effective references, omitted contradicting links,
unqualified cited contradictions, known market-sizing/corroboration phrases and mismatched
commercial categories/roles. Pricing requires pricing evidence; revenue requires product-owned
revenue evidence; a buyer preorder is neither realized company revenue nor deployment. Creator
monetization cannot support product revenue. Distribution requires explicit distribution evidence;
being mentioned on YouTube is insufficient. Model instructions require grounded monetization
structure rather than inferring SaaS from software. These controls do not prove semantic entailment:
reviewers still evaluate every supported statement before confirming display.

## Input universe and source diversity

One joined query loads linked Signals and their canonical video/channel lineage, including comment
parents. Only `status=active AND semantic_status=current` enters the evidence bundle. Excluded,
under-review, invalid, superseded, ignored and rejected text never enters the model input. Their
lifecycle/semantic counts are retained as validation warnings. Explicit standalone editorial
records are not converted into source-grounded Signals. Existing 044E evidence storage is reused.

Input includes Signal identity/content, actor/evidence/claim roles, commercial fields, relationship,
source identity and observed time. Current human definition and active buyer/industry taxonomy
are separate context. Scores, reviewer notes, profile identity and credentials are not supplied.
The default manual request accepts 1–200 effective Signals and a 250KB serialized input ceiling;
it rejects oversized input instead of silently truncating evidence.

Counts include linked/supporting Signals, distinct videos/channels, comment-derived Signals,
relationships and type distribution. A dimension's multi_video_coverage is true only for at least
two distinct supporting video IDs cited by that dimension. Comments share their parent video's
identity. This is coverage, not independent corroboration, independent customers or proven demand.

## Versioning, identity, failure and staleness

Migration0023 adds opportunity_consolidations and a nullable source_consolidation_id FK on the
existing opportunity_revisions. Records retain source_evidence_hash, context_hash, full input_hash,
input_snapshot, immutable prompt version/hash, provider/model, provider request/token audit,
raw output when available, parsed output, field metadata and creator/time.

Version numbers increase per Opportunity. Same complete input and immutable prompt hash/version
reuse the completed result without a provider call. The input hash includes current human scope,
active taxonomy and excluded-state warning counts as well as effective evidence. Therefore an
accepted human edit can make the previous case stale even when its evidence hash is unchanged.
Changes preserve old versions; completed/failed payloads are protected against UPDATE by a DB
trigger. Review confirmation metadata can change independently; source/output history cannot.

Only one queued/running attempt exists per Opportunity. Concurrent requests lock the Opportunity;
concurrent workers atomically claim the attempt. Duplicate delivery cannot re-call a completed or
running attempt. Transport dispatch failure leaves a durable queued row for redispatch. Requests
can recover an expired 30-minute queued/running lease into a retained failed attempt and a new
version. Provider calls have a 240-second service deadline and the existing bounded client retry
budget. Worker infrastructure retry ceiling is two. Provider/validation failure changes only the
attempt; current Opportunity and previous completed case remain intact. A failed attempt is retried
explicitly, never by a read. If evidence changes while work runs, its result is retained but stale;
refresh/reconcile prepares a new input rather than relabeling the old output current.

## Triggers, API and operations

v0.1 uses explicit admin refresh and bounded reconciliation, avoiding paid work on every MATCH.
No new automatic scheduler or normalizer hook is installed. Reviewers see missing/stale warnings
before Publish in the full candidate dossier; existing six readiness checks and hard blockers are
unchanged. Neither a missing nor a generated case automatically determines publication.

Admin API:

- POST `/api/v1/admin/opportunities/{uuid}/consolidation`: durable prepare + asynchronous enqueue.
- GET `/api/v1/admin/opportunities/{uuid}/consolidation/current` and `/consolidations`: current/stale
  projection, latest attempt and latest100 history rows. Full raw/provider payloads are not returned.
- POST `/api/v1/admin/opportunities/{uuid}/consolidations/{case_id}/accept`: candidate-only selected
  field acceptance, with dimension, expected_updated_at, optional edited_text and required note.
- POST the same version's `/approve`: confirm current business case for display, with actor/time.
  This operation does not activate a candidate or overwrite the public Opportunity definition.
- GET `/api/v1/admin/opportunities/{uuid}/consolidation/evidence/{dimension}`: exact cited effective
  Signal drilldown through the 044E projection, locale and bounded pagination.

Worker: `consolidate_opportunity` on `opportunity_consolidation`, using the existing AIClient and
configured `AI_MODEL_OPPORTUNITY_NORMALIZATION` model. This reuses configuration, not normalizer
semantics. Prompt default is registered once as `opportunity-consolidation/v002`. Used prompt files
must not be edited; changes require a new version and review. v001 remains retained. v002 was
promoted after the bounded real benchmark exposed three category-mismatch failures; it explicitly
aligns model instructions with the existing validator without relaxing evidence gates.

From apps/api:

```bash
uv run python scripts/consolidate_opportunities.py --status candidate --limit 20 --dry-run
uv run python scripts/consolidate_opportunities.py --opportunity-id UUID --enqueue
```

Default is dry-run, max20 Opportunities. Reports selected/eligible/current/stale/missing/would_enqueue
and per-entity results. Explicit selection accepts eligible active/review/candidate identities.
Queue dispatch is recoverable with the same command. Reads never enqueue, translate or call AI.

## Human acceptance and public display

Machine fields remain separate. Selected mappings reuse existing columns: problem_summary→problem,
solution_pattern→solution, workflow_summary→one_line_thesis, business_model_summary→business_model.
The admin can edit the proposed text or keep the current value. Unsupported/hypothetical fields,
numeric price ranges, taxonomy and scoring classifications are not accepted through this action.
Acceptance locks the candidate, verifies current version/context and optimistic updated_at, appends
old/new/actor/note/source-consolidation audit and changes only the chosen column. No-op acceptance
creates no misleading revision. Accepted edits do not alter immutable machine output.

For active Opportunities, GET `/api/v1/opportunities/{uuid}/business-case` exposes only a current,
admin-confirmed case. Candidate/non-active identities return404 even for an admin using this public
API. Missing/stale/unreviewed cases show explicit Evidence insufficient / Awaiting review sections.
Hypothetical proposals are suppressed into unknown fields on the public projection. Historical raw
bundles, creator identity and audit internals remain admin-only under RLS. Evidence drilldown uses
`/business-case/evidence/{dimension}` and requires the same currently visible case.

## Localization

All fixed labels support zh-CN/en-US. Machine text is explicitly labeled canonical English; no
inline translator is added. Accepted Opportunity text uses existing TASK-042 best-effort async
translation enqueue and stored hash-aware projection. 044E cited evidence uses existing stored
localized statement/excerpt, canonical provenance and source links. Original claim status remains.

## Human review rubric and limits

For each case record pass/fail/uncertain and cite the actual Signal IDs:

1. Buyer/operator correctly scoped, distinct from end beneficiary?
2. Problem grounded without invented severity/frequency?
3. Solution neutral where justified, with vendor-only limits retained?
4. Pricing grounded with offered/paid/recurring context?
5. Revenue ownership correct and separate from pricing/creator income?
6. Acquisition/distribution explicitly evidenced?
7. Contradictions and differing commercial contexts preserved?
8. Missing information and assumptions explicit?
9. References belong to the exact effective bundle and support the dimension?
10. Does this give an operator concrete next validation questions?

A bounded 8–15 item, single-reviewer benchmark is a development check, not production accuracy.
Reference validity and category gates are automatable; vendor neutrality, buyer scope and factual
entailment require human evaluation. Current semantic filters cannot resolve every cross-entity
linking error. Lexical references and model-generated prose can still be misleading without review.
History reads are limited to100 rows; older rows remain stored. The input cap and explicit
reconciliation avoid unbounded provider work; automatic continuous refresh remains future work.
