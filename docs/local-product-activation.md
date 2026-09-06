# Local Product Activation Validation v0.1

## Scope

This validation inspected the existing `ai_business_radar_live_test` database and the product-facing Radar query path. It did not create synthetic data, edit lifecycle statuses directly, or bypass the review workflow.

## Local data snapshot

At validation time the database contained 5 videos, 26 AI extractions, 30 signals, 1 opportunity, 20 opportunity-signal links, 3 trend snapshots, and 1 opportunity score. No comments or review tasks were present.

The normalized opportunity was:

- `AI receptionist and appointment-lead workflow management for dental practices`
- lifecycle status: `candidate`
- 20 linked active signals
- persisted 7d, 30d, and 90d trend snapshots
- Opportunity Score `37.71`, Confidence `68.35`, and Hype Risk `54.49`

The source trail was internally consistent. The three processed dental videos were `LOREN`, `Where Can AI Help Dental`, and `VitalDesk`, with relevance confidence between 0.93 and 0.94. They produced signal extractions; normalization created one candidate and matched later signals to it; deterministic trend/scoring records were already persisted. Ten additional signals remained in review status. Comment-derived pain evidence was absent because no comments were collected.

## Why Radar is empty

The Radar query intentionally returns only opportunities whose lifecycle status is `active`. The only local opportunity is still `candidate`, so the real query returns zero rows even though trend and score records exist. A FastAPI `GET /api/v1/radar` executed through the application lifecycle against the configured local database returned HTTP 200 with `total: 0` and an empty `items` list.

No pending review task exists for this opportunity. The current `ReviewWorkflowService` can approve or reject signals, confirm opportunity matches and creation, merge opportunities, and resolve hype/quality reviews. None of its supported decisions promotes a candidate opportunity to `active`. Therefore local activation cannot be performed safely through the frozen workflow contract.

Direct SQL status edits and fabricated review tasks were rejected because they would bypass the product architecture and require inventing lifecycle semantics. A dedicated, specified candidate-activation transition is required before this record can appear on Radar.

## UI presentation changes

- Radar and Signals now use Chinese-first headings while retaining useful English metric names.
- Radar filters use a denser responsive layout.
- Confidence values are displayed as percentages while deterministic scores retain their 0–100 score presentation.
- Signals omit the evidence-strength panel when that value is absent.
- Admin users receive a visible role badge and a separated review-workspace navigation section.
- The empty Radar state now explains that opportunities must be reviewed, activated, and scored.

These are presentation-only changes. No frontend business rules, review decisions, or status mutations were added.

## Architectural question

What reviewed action is authorized to transition an opportunity from `candidate` to `active`, and which evidence/review preconditions must it enforce? This must be added to the product and API contracts before implementing activation.
