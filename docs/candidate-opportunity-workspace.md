# Candidate Opportunity Workspace v0.1

## Semantics and navigation

`/admin/review/candidates` and `/admin/review/candidates/{id}` extend the existing review shell.
A candidate is a machine-normalized, unpublished Opportunity, not an approved commercial finding.
The ordinary library/detail/evidence APIs still require active status, including for admin callers.
Admin-only dossier reads may retain an active/rejected/archived record after a decision for audit;
only candidate records can be edited or submitted. No manual Opportunity creation is exposed.

`opportunity_creation` targets a Signal and decides whether normalization should create a candidate.
`opportunity_activation` targets an already existing Opportunity and decides publication. They are
not interchangeable. Creating a candidate does not automatically create an activation review.

## List, filters and performance

The list shows canonical name/thesis, mapped taxonomy or original industry/customer text, effective
linked/supporting counts, distinct videos/channels, score/confidence/hype, activity, freshness,
semantic warning count and open activation review. UUIDs are links/internal identities, not titles.

Filters: search, industry/customer taxonomy, readiness, review state, presence of semantic warnings.
Sort defaults to readiness, effective supporting evidence count, then recent activity (stable ID tie
order). Recent and name sorts are also available. No confidence threshold sorts or publishes.
Counters cover all candidates before filters: total, ready, needs_review, not_ready, with an open
activation review, and deferred. Deferred is an existing pending task whose latest decision is defer;
it overlaps the open-review count. Counts are Opportunities, not number of actions.

The backend follows the existing library's batch projection approach: constant-count set queries,
server-side filtering/sorting and slicing, default20/max100, never all records in the browser.
List readiness includes status/metrics; detailed checks and duplicate suggestions are omitted there
and provided in the dossier. The backend still scans the candidate population and eligible lexical
pool; v0.1 is not an indexed readiness search service. Large-scale materialization is future work.
The fixed-query regression compares one-item and full-page reads; evidence pages use joined bounded
queries and one optional localization batch, never a follow-up request per card.

## Readiness and evidence

The same six checks compose single and batch readiness. Existing ready/needs_review/not_ready,
recommendations and hard publication checks are preserved. The UI renders each result, original
backend explanation, metrics and an operator action, without recomputing readiness. No score
formula changes. Semantic-under-review linked evidence now appears in unresolved quality warnings.

The effective evidence tab reuses TASK-044E's linked/explicit UNION, provenance resolution, original
extracted text, RAW comment distinction, and stored zh-CN localization. Effective Signal evidence
requires active/current. The excluded tab uses the same joined projection for non-effective Signal
references, clearly labeled, without contributing to counts or readiness. Standalone editorial
records stay in the effective tab only; no invented semantic status. Source availability is not
checked. Missing fields and unavailable sources are explicit. No LLM or translation on reads.

Duplicate suggestions retain the existing recent-first, 20-candidate lexical pool and up-to-five
suggestions. Exact/strong collisions block; near duplicates warn. No merge action is added.

## Draft curation and audit

Editable: name, one_line_thesis, problem, solution, business_model, typical_price_min/max/currency/
period, market_stage, competition_level, build_difficulty. There is no distribution column; the
workspace explicitly points to linked distribution evidence. Industry/customer mappings are shown
and filterable but not edited here. Taxonomy curation improvements remain TASK-044K/048.

PATCH forbids unknown fields, blank/null names, invalid stages/levels, negative or malformed prices,
lowercase/non-three-letter currency and inverted price bounds. `expected_updated_at` plus a row
lock prevents lost updates and edits after publication. No-op saves create no fake revision.
Each changed field records old/new value, actor, timestamp and optional note in opportunity_revisions.
Save changes neither publication state nor review assignment and creates no review task. Readiness
reloads after save. Existing translations naturally become stale by content hash; no read generates
replacement text. Source/AI output, evidence, scores and task audit cannot be edited.

## Submission and decisions

Submission reuses POST `/admin/opportunities/{id}/activation-review`. Candidate + at least one
active/current supporting Signal are required. Other hard blockers can be sent for explicit human
inspection, but Publish always rechecks them in the existing locked review transaction.
Open pending/in_review task uniqueness and Opportunity locking prevent duplicate submissions.
The button becomes View activation review when one exists; mutation controls also prevent double
clicks. The current admin claims the task without typing a reviewer UUID.

Publish (approve) makes the Opportunity active; Defer returns the review to pending/unassigned and
keeps the candidate; Invalid (reject) makes it rejected without deleting sources or audit. Publish
and Invalid have explicit UI confirmation. Only the claimed admin can use the UI decision controls;
existing backend decision/assignment policy remains authoritative. The queue links to the complete
dossier, and its activation checks reload from current candidate state rather than a stale submitted
snapshot. Final decisions remain single-winner transactional operations.

Migration0022 adds activation_review_events: submitted, claimed, deferred, published, invalid, with
actor/time/notes and previous/new review state. Idempotent repeated claim/submission adds no event.
Earlier tasks are displayed as legacy snapshots; no historical events are fabricated. The new
append-only application tables have admin-only SELECT RLS and no authenticated mutation grant.
History UI displays the latest100 revisions/events and flags truncation; older rows remain retained.

## Publication confirmation, freshness and permissions

After Publish the UI checks the ordinary Opportunity read API, displays confirmed/pending visibility
and a front-end detail link. Scores/trends remain persisted asynchronous intelligence; Publish does
not synchronously recompute them. Existing best-effort translation enqueue remains in the service.
Translation readiness checks the existing required Opportunity fields against current stored hashes.
Score/trend freshness is pending when missing, stale when older than relevant activity or24hours;
score additionally flags subsequent Opportunity edits. These are presentation indicators only.
No claim of guaranteed Radar position or real-time recalculation is made.

All new API reads/writes require an application admin (ordinary user403); existing SSR admin layout
also protects both routes. Public candidate lookup remains404 and explicit evidence cannot leak
through these routes. The existing global Signals feed remains independently governed: it can show
valid Signals without a published Opportunity, but it does not reveal candidate identity or audit.

Fixed workspace labels support zh-CN/en-US. Canonical business text and backend readiness explanations
may remain English; evidence uses stored localized projections with canonical fallback. Loading,
true-empty, filtered-empty, missing-support and transport-retry states are distinct. Existing
intermittent browser transport failures are not asserted fixed by this task.
