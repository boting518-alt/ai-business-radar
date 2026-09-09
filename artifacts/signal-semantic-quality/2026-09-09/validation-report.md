# TASK-044F — Local validation, 2026-09-09

## Assessment and revised scope

The proposed task addresses confirmed commercial-evidence errors and is appropriate before
candidate activation and business-case consolidation. The revised task is in
`docs/tasks/TASK-044F.md`. Corrections: use the existing `docs/scoring.md`; retain immutable
extractions and score-v001; separate semantic validity from lifecycle; suppress only exact
cross-extraction duplicates; repair trends before appending scores; keep v004 experimental.
These are explicit documented changes, with no unresolved specification conflict.

## Implementation

- Migration 0021 and FACT models add actor/evidence roles, semantic state, replacement lineage
  and append-only application decision audit, including ordinary-user RLS filtering.
- `signal_semantics.py` implements conservative deterministic recognition; extraction and
  comment mining persist decisions transactionally. Normalization and review recheck validity,
  including locked completion boundaries. Hard invalid evidence cannot bypass review controls.
- Feed, evidence, counts, activation, trends, scoring and translation exclude non-current
  evidence. Ambiguous human approval requires notes and retains an audit decision.
- Three scripts provide bounded audit/apply, recoverable history recomputation, and artifact-only
  prompt comparison. Frontend source and review panels expose roles and semantic reasons.
- Documentation and focused unit/integration/UI regressions accompany these changes.

## Actual local repair

Migration applied to localhost `ai_business_radar_live_test`. No staging/production deployment.
All 34 active purchase_intent/revenue/adoption/pricing records were inspected, then explicitly
applied: **13 accepted, 18 under review, 3 invalid, 0 exact duplicates**. There are 34 audit
decisions and 21 validation review tasks. Repeated apply made zero additional changes.
Physical active lifecycle rows remain 260; effective current active evidence is 239.
Sources, original categories, claim status, extraction raw/parsed output and links are preserved.
No Opportunity publication status was changed.

Dental (`7eea70c0-eeee-4db5-9cd0-ca73dcd42861`) retains all 40 historical links but has
**38 effective linked/supporting Signals**, four videos, four channels, ten pain Signals and
**zero purchase-intent Signals**. The AI Connect Pro invitation is invalid buyer evidence;
the adoption encouragement requires review. Microduck creator pre-order CTA is invalid.
The Amazon Associate disclosure is invalid featured-product revenue. The genuine comment
“Price with shipping is $508. I still ordered one. It's so cool!” remains buyer evidence,
with its original unknown claim status.

Sixteen affected Opportunities received 48 new trend snapshots and 16 appended score-v001
records. Repeating the same applied report reused all 48 snapshots and all 16 scores.
Dental history remains 37.71, 44.74, then 48.56. The later observation window raises its trend
component, so comparing old timestamps does not isolate this repair. At the same new time and
trend inputs, the read-only old-evidence counterfactual is 53.24 versus corrected 48.56
(`dental-counterfactual.json`); the counterfactual was not persisted as a product score.

## Quality evaluation

Forty curated real cases comprise all 34 risk records and six controls, from v001/v003;
no active v002 example exists in this population. These single-agent development labels are
not independent ground truth or a representative production evaluation.

| Deterministic projection metric | Result |
| --- | --- |
| Accepted purchase-intent precision | 5/5 |
| Accepted revenue ownership/category correctness | 5/5 |
| Actor role agreement | 27/40 |
| Evidence role agreement | 29/40 |
| False CTA acceptance | 0/3 |
| Creator/product monetization confusion | 0/1 |
| Decision agreement | 35/40 |

Conservative review reduces coverage: legitimate expressions can remain unavailable pending
human review. The revenue metric is a curated category/ownership check, not verified entity
resolution. Unknown role assignments and multilingual expressions remain limitations.

Four identical persisted video inputs were compared with v003 and v004: eight real provider
calls, no source fetching or product-data writes. Raw/parsed outputs, model, input hashes and
usage are recorded in `prompt-*-v00*.json`; manual criteria are in `prompt-review.json`.

| Prompt metric | v003 | v004 |
| --- | --- | --- |
| Schema success | 4/4 | 4/4 |
| Excerpt grounding, manual | 19/19 | 17/17 |
| Atomicity, manual | 15/19 | 14/17 |
| Revenue ownership | 1/2 | 1/1 |
| False CTA acceptance | 0/2 | 0/2 |

v003 again classified affiliate disclosure as revenue; v004 used creator-attributed distribution.
Neither emitted buyer-positive purchase intent in these metadata inputs, so prompt purchase-intent
precision is unmeasured. Schema v001 has no actor/role fields, so prompt actor/role metrics are
also unmeasured. Compound assertions remain. **KEEP_EXPERIMENTAL**: runtime stays v003/schema
v001; these small reused examples do not justify promotion.

## Validation

**463 distinct tests passed**: API 232 (71 PostgreSQL tests skipped in the ordinary run and
then run separately), PostgreSQL integration 71, worker 23, shared Python 59, frontend 78.
Ruff, frontend lint, TypeScript validation, production Next.js build and `git diff --check`
passed. Existing Starlette deprecation and Vite loader warnings remain.
Regression coverage includes audit idempotency/rollback, hard-invalid approval rejection,
normalization blocking without provider calls, exact duplicate preservation, effective read
models, score history and ordinary-user RLS restrictions.

The canonical launcher was exercised: API, worker and scheduler agreed on fingerprint
`0b0184355f0cb72c` (local profile/database/Redis). For final browser validation, the production
frontend and API were started; worker/scheduler from the launcher were stopped. No runtime
configuration or prompt promotion was changed.

Browser checks observed Dental's 38 evidence count, zero purchase-intent filter results and
three preserved scores; the genuine buyer comment and its source trace; and semantic status/
reason in admin review. No review decision was submitted. Ordinary-user data isolation was
tested through integration/RLS; this is not a claim of completing TASK-046 dual-role E2E.
Previously observed intermittent browser fetch failures also occurred during dev navigation;
the production Dental check succeeded. Transport reliability is not fixed by this task.

## Remaining work and handoff

Operators must adjudicate the 18 ambiguous cases. Exact duplicate protection is tested but no
duplicate was found in the bounded real repair; paraphrase/compound deduplication is not solved.
Regex recognition is deliberately bounded, and entity attribution is not identity verification.
Broader independent evaluation is required before prompt promotion. TASK-044G and later tasks,
including full staging dual-role acceptance, remain separate work.

Unrelated audit/positioning/architecture artifacts are excluded from the task commit;
`next-env.d.ts` is unchanged. Commit message: `fix: harden signal semantic quality and history`.
No push is authorized or performed.
