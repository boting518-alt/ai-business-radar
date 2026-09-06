# Opportunity Activation Workflow v0.1

## Purpose and lifecycle meaning

Activation is the human-controlled publication boundary between normalized intelligence and the product-visible Radar. A `candidate` is normalized but not visible. `active` means a human reviewer judged its evidence sufficiently coherent and its definition sufficiently clear to be visible and monitored. It does not mean proven demand, guaranteed success, an investment recommendation, or a high score.

`merged` identifies a duplicate retained through canonical merge history. `rejected` identifies an invalid, unsupported, malformed, or unusable standalone opportunity. `archived` is a historical or non-current entity.

## Decisions

| UI decision | Stored decision | Domain effect |
| --- | --- | --- |
| Publish | `approve` | `candidate → active`; resolve and audit the review |
| Defer | `defer` | Keep candidate; return review to pending and retain notes |
| Invalid | `reject` | `candidate → rejected`; retain evidence and history |

Weak or incomplete evidence normally means Defer. Invalid is reserved for a judgment that the entity itself is malformed, unsupported, or unusable. Merge remains a separate review type.

## Deterministic readiness checks

`OpportunityActivationReadinessService` performs six checks without an LLM:

1. Supporting evidence: at least one active supporting signal is a hard minimum.
2. Scope clarity: reject empty, placeholder-like, or obviously generic names; require specificity and descriptive context.
3. Commercial definition: at least two of `customer_type`, `problem`, and `solution` must be populated.
4. Duplicate risk: exact strong lexical collisions fail; possible near duplicates warn and never auto-merge.
5. Source diversity: two videos or two channels pass; lower diversity warns but does not hard-block by itself.
6. Contradiction and quality: recorded contradictions or unresolved linked signals warn. No recorded contradiction also warns because automated coverage is incomplete.

The result is `ready`, `needs_review`, or `not_ready`, with an advisory recommendation of `publish`, `defer`, or `invalid_review`. Hard blockers are non-candidate state, no active supporting evidence, invalid scope, insufficient commercial definition, and an obvious duplicate. Without a hard blocker, at least four passing checks with warning-only remainder recommends Publish.

## Advisory metrics

The reviewer sees active signal count, video/channel diversity, latest Opportunity Score, Confidence, Hype Risk, 7d Momentum, and activity dates. These values provide context only. No score, confidence, hype, or momentum threshold controls readiness or publication.

## Review creation and audit

`POST /api/v1/admin/opportunities/{id}/activation-review` creates an `opportunity_activation` task only for a candidate with active supporting evidence. The partial unique review index and service lookup reuse an existing pending/in-review activation task. Other opportunity statuses receive no activation review.

The task targets the opportunity and persists the readiness snapshot, metrics, recommendation, and bounded duplicate candidates in `review_tasks.context`. Final audit uses the existing decision, notes, `resolved_by`, and `resolved_at`; v0.1 needs no activation-history table.

## Decision-time safety and transaction

The existing review decision endpoint remains authoritative. Publish locks the review and opportunity, verifies candidate state, and re-runs hard checks inside the same PostgreSQL transaction before changing status and resolving the review. Any stale state or failed check rolls back both. Invalid verifies candidate state before setting `rejected`. Defer performs no opportunity mutation.

## Radar visibility and no automatic publication

Radar continues to select `active` opportunities only. Its default score sort requires a current score, so a published but unscored opportunity may remain absent until scoring runs. Publication does not change scoring or trend formulas.

Schedulers, workers, AI output, readiness recommendations, and score thresholds must not publish in v0.1. An administrator must explicitly claim and Publish through `ReviewWorkflowService`.

## Known limitations

Duplicate detection is bounded lexical retrieval rather than semantic embeddings. Contradiction coverage is incomplete and conservative. Source diversity counts videos and channels, never author identity. Claim-level quality remains a human judgment, and v0.1 retains current defer notes rather than complete claim/defer event history.
