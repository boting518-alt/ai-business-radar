# Human Review Workflow v0.1

## Purpose

Human review is the application-controlled boundary between AI suggestions and canonical domain
changes. `ReviewWorkflowService` validates persisted context and applies one decision atomically;
routes and repositories contain no decision policy.

## Lifecycle and assignment

Tasks start `pending`. Claiming uses a row lock and moves `pending -> in_review`, recording the
admin in `assigned_to`. A second admin receives a conflict. A final decision moves a task to
`resolved`, except `ignore`, which moves it to `ignored`; `resolved_by` identifies the deciding
admin and may differ from the claimant. `defer` returns the task to `pending`, clears assignment,
retains decision notes, and does not set `resolved_at`. Claim history is not retained in v0.1.

Resolved tasks cannot be reopened or decided again. Repeated claims by the assigned admin are
idempotent and have no additional side effect.

## Decision matrix

| Review type | Allowed decisions |
| --- | --- |
| `signal_validation` | `approve`, `reject`, `ignore`, `defer` |
| `opportunity_match` | `approve`, `merge`, `create_new`, `reject`, `defer` |
| `opportunity_creation` | `approve`, `create_new`, `reject`, `defer` |
| `opportunity_merge` | `merge`, `reject`, `defer` |
| `hype_review` | `approve`, `reject`, `defer` |
| `quality_review` | `approve`, `reject`, `ignore`, `defer` |

## Domain effects

Signal validation maps approve/reject/ignore to `active`/`rejected`/`ignored`. It never deletes a
signal or changes source or extraction provenance.

Match approval validates the persisted proposed ID against the persisted candidate set, links the
signal without duplication, activates it, and advances opportunity activity time. `create_new`
(and approval of an opportunity-creation task) derives a candidate solely from the source signal
and the persisted normalizer extraction. Insufficient context fails safely. Match rejection rejects
the normalization outcome only: the signal remains `review` for possible rematching.

Merge requires distinct existing opportunities, a non-merged source, and an eligible canonical
target. The service locks both rows, detects lineage cycles, records merge history, marks the source
`merged`, moves current signal links and evidence, and reconciles watchlists. Duplicate links are
collapsed. For duplicate watchlist membership, the canonical item retains the earlier `added_at`;
source-only membership changes to the canonical ID. The source row, and its historical trends and
scores, remain untouched and queryable under the source ID.

Hype and quality decisions are audit-only in v0.1. They do not rewrite deterministic scores,
Hype Risk, other target state, or `market_stage`.

## Context, transactions, and authorization

Context is persisted input, not trusted state. UUIDs, entity existence, target eligibility,
candidate membership, extraction output, and canonical names are revalidated at decision time.
Decision notes are human audit text and never machine state.

The detail read model may add safe signal and opportunity summaries to the returned context for
human inspection. This transient presentation projection does not alter persisted context; the
service continues to validate decisions exclusively against locked database state and the original
workflow inputs.

The task lock and every domain effect share one PostgreSQL transaction. A validation or persistence
failure rolls back the complete decision. Admin authorization is enforced by FastAPI and existing
RLS policies continue to restrict `review_tasks` to application admins. Watchlist reconciliation
changes only the referenced opportunity and never crosses watchlist ownership.

## v0.1 limitations and UI transition

Claim/defer event history is intentionally limited to current task fields; final decisions remain
auditable. Release is deferred because direct decision and defer provide the minimum admin flow.
There is no task reopening, manual score override, market-stage policy, or autonomous merge.
The TASK-026 admin UI uses the list/detail/claim/decision endpoints without duplicating workflow
policy. TASK-022 consumes approved state for Radar queries.
