# Automatic Translation Orchestration Validation

## Trigger and eligibility matrix

| Case | Result |
| --- | --- |
| New review Signal | post-commit best-effort enqueue enabled |
| Signal becomes active | post-commit coverage check/enqueue enabled |
| Ignored/rejected Signal | excluded |
| Activation review created/reused | post-commit coverage check/enqueue enabled |
| Opportunity becomes active | post-commit coverage check/enqueue enabled |
| Rejected/merged/archived Opportunity | excluded |

Automatic fields are Signal `statement`/`evidence_text` and Opportunity
`name`/`one_line_thesis`/`problem`/`solution`. Runtime translation remains v001 via the prompt
registry. Canonical values and original evidence are never mutated.

## Automated validation

- Coverage states: current, missing, partial, stale, and failed are projected without AI calls.
- Dry-run: bounded read only; zero enqueue and zero write.
- Missing/stale retry: submitted to `intelligence_translation`; current and ineligible rows skipped.
- Duplicate active jobs: suppressed by a 15-minute Redis entity/locale/version lease.
- Queue failure: absorbed by the best-effort boundary after domain commit.
- Scheduler: bounded reconciliation every 20 minutes, default limit 100.
- Existing translation worker: maximum two retries; structured-output failures remain permanent.
- Read/API behavior: unchanged database-only localization lookup and canonical English fallback.

## Local validation status

Local PostgreSQL and Redis responded successfully. A bounded read-only scan of
`ai_business_radar_live_test` found 50 eligible missing Signals at limit 50, with zero writes and
zero enqueue. A fairness recheck at limit 2 returned one missing Signal and one current Opportunity,
confirming Signal volume does not starve Opportunity reconciliation.

One missing Signal was enqueued. An already-running local Worker consumed the message but produced
no localization row, reproducing the required worker-environment failure case: the canonical row
remained readable and a later reconciliation still classified it as missing. After explicit user
authorization, the dedicated worker execution path repaired exactly that Signal through OpenAI.
Both `statement` and `evidence_text` were stored as current v001 projections with matching source
hashes and provider/model audit. A second non-dry reconciliation reported current=1,
would_enqueue=0, and enqueued=0. No historical bulk translation was attempted.

Local FastAPI returned 200 for both zh-CN and en-US Signal reads using an existing active localized
Signal. zh-CN marked statement/evidence localized, en-US remained canonical, and both original
statement and original evidence matched the canonical response.

## Regression results

- API/unit/PostgreSQL integration: 240 passed.
- Shared schemas: 59 passed.
- Worker/Ruff: 17 passed; Ruff passed for API and Worker workspaces.
- Frontend: typecheck and lint passed; 66 tests passed; clean production build passed.
- Warnings: two existing Starlette/httpx deprecation warnings and one Vite config warning.

## Remaining limitation

The duplicate lease is deliberately time-bounded rather than a durable job ledger. Jobs running
longer than 15 minutes may become eligible for resubmission; the worker's source-hash/version upsert
still preserves a single valid current projection.
