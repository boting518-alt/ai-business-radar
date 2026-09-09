# TASK-044H implementation and local validation

Date: 2026-09-09. **Implementation complete; real-provider acceptance remains pending explicit
OpenAI destination authorization. Do not mark TASK-044H fully complete or production-ready.**

## Assessment and revised scope

The audit correctly found that MATCH added evidence without reconsolidating the Opportunity.
Dental retained “Dental appointment leads are organized inside the VitalDesk dashboard.” despite
38 effective Signals. The new workflow is a separate auditable editorial layer, preserving the
existing normalizer, Signal guardrails, deterministic scores and human publication policy.

Revisions are recorded in docs/tasks/TASK-044H.md. Human canonical fields are authoritative;
new machine output is versioned separately. Existing readiness checks remain unchanged, with
missing/stale case advisories. Public display additionally requires explicit human confirmation
of a current case, avoiding unreviewed new prose on an already active Opportunity.

## Implemented model and grounding

Eleven dimensions separate customer, problem, workflow, solution, business model, pricing, revenue,
distribution, competition, adoption and build considerations. Each carries text, Signal IDs,
information class, support level and uncertainty. Validation gaps are mandatory, supplemented by
deterministic missing-dimension and excluded-evidence warnings. Source claims, editorial synthesis,
hypotheses and unknowns remain distinct. Unknown text is null; public hypothetical proposals are
suppressed into unknown sections.

Prompt: opportunity-consolidation/v001, registered in the shared prompt registry. Structured schema
is authoritative Pydantic plus generated opportunity_consolidation.v001.schema.json. The existing
AIClient and AI_MODEL_OPPORTUNITY_NORMALIZATION configuration are reused. No extractor or
normalizer prompt/version was promoted or modified.

Only active/current linked Signals enter the input. Under-review, invalid, superseded, rejected and
ignored records contribute warning counts only. Each citation must be a persisted input Signal.
Category/role gates prevent pricing-as-revenue, seller-CTA-as-adoption, affiliate-as-product-revenue,
and video-appearance-as-distribution substitutions. Recorded contradicting links must be cited and
qualified. Multi-video coverage is computed per dimension from distinct cited supporting videos;
it never means independent buyers or verified commercial demand.

These are structural and category safeguards, not a universal semantic-entailment proof. Actual
vendor neutrality, correct customer scope and absence of unsupported commercial prose still require
the requested real-output human evaluation, which has not yet run.

## Persistence and workflow

Migration0023 is applied to local ai_business_radar_live_test only. Versioned rows retain evidence,
context and full input hashes; immutable input/output snapshots; prompt hash; provider/model/request/
usage audit; lifecycle timestamps and separate confirmation metadata. Completed/failed payloads
are protected by a database trigger. Direct table reads remain admin-only under RLS.

Concurrent preparation reuses one queued/running row; duplicate worker delivery claims once.
Completed identical input/prompt reuses without another provider call. Human-context or evidence
changes make the case stale. A new version preserves history. Provider failures do not overwrite
Opportunity fields or prior results. The job has a 240-second call deadline, bounded client/worker
retries, redispatchable queued failures and explicit 30-minute expired-lease recovery.

The candidate workspace provides Refresh, dimension evidence drilldown, acceptance/edit/keep-current,
confirmation and version history. A selected accepted field appends old/new/actor/note plus
source_consolidation_id to existing revisions. Acceptance is candidate-only and optimistic. The
accepted edit makes previous context stale; current numeric pricing, taxonomy and scoring fields
are not inferred. Confirmation does not publish a candidate.

Public active dossiers load only current confirmed cases. Unavailable dimensions explicitly say
Evidence insufficient. Both evidence drilldowns reuse the 044E joined source/localization projection;
there is no second evidence store. Fixed UI labels support zh-CN/en-US. Machine prose remains
labeled canonical English; accepted existing Opportunity text uses TASK-042 asynchronous translation.
No read endpoint performs AI/translation or queues work.

The bounded CLI defaults to dry-run, accepts max20 or one explicit UUID, reports state/eligibility,
and enqueues only with --enqueue. No automatic continuous consolidation sweep is installed.

## Real-data offline verification (no provider request)

| Case | Effective Signals | Videos / channels | Comments | Important scope |
| --- | ---: | ---: | ---: | --- |
| Dental | 38 | 4 / 4 | 0 | 10 pain, 21 workflow, 2 customer, 3 distribution, 2 technology; no pricing/revenue/purchase-intent |
| Micro Duck preorder | 6 | 5 / 5 | 4 | 3 purchase-intent, 1 demand, 1 pricing, 1 distribution |
| Roller-skating duck companion | 12 | 5 / 5 | 0 | Pricing and product revenue remain separate; one under-review link excluded |

Dental excludes one invalid and one under-review active record. Micro Duck preorder likewise
excludes one invalid and one under-review record while retaining buyer-side comment evidence.
See input-*.json for exact IDs, roles, taxonomy and hashes. These files are local input snapshots,
not generated business cases or quality ratings. Dental's public thesis/solution remain unchanged.

The intended 8-case benchmark is prepared in benchmark-plan.json. Status is pending, actual provider
calls = 0, and no hallucination rate, vendor-neutrality score or production accuracy is claimed.
The documented ten-question review rubric is ready for evaluating each actual output.

## Browser and deterministic fixture validation

Two synthetic Opportunities were clearly labeled TASK-044H LOCAL TEST ONLY. Pure local FakeAI
outputs were used, not external model calls and not purported commercial research.

- Candidate dossier displayed separate dimensions, explicit unknowns and citations.
- Dimension drilldown returned the exact two referenced synthetic Signals with retained source
  status. Invalid synthetic YouTube identities correctly showed unavailable navigation.
- Browser acceptance edited only solution, retaining the original machine v1 and source-linked
  old/new revision with the current admin actor and explanatory note.
- The v1 case became stale immediately after that human edit. Browser Refresh queued work; a pure
  local fixture executor completed it. Same-input rerun reused v2 without another fake call.
- Updating one synthetic effective Signal produced a distinct v3; v1/v2 remained immutable.
- A separate synthetic active case was explicitly confirmed through the browser. Its public dossier
  displayed the reviewed case while keeping original canonical fields separate.
- Final browser inspection confirmed the English public business-case sections and Chinese admin
  workflow, including English evidence drilldown; the browser was restored to Chinese. Both
  locales and the no-admin-controls projection also pass UI tests.

See fixture-versioning-acceptance.json, fixture-public-projection.json and fixture-cleanup.json.
Temporary fixture Opportunities are archived after validation; their Signals/videos are ignored,
while source and revision/consolidation history are retained. No real candidate was published or
rejected, and no real Opportunity definition was changed in this task.

## Tests and build

527 tests passed: API270, PostgreSQL73, worker24, shared schemas60, frontend100 (13 files).
The ordinary API run skips73 PostgreSQL tests; those pass separately on a fresh migrated temporary
DB. Ruff, frontend typecheck, ESLint, production build and git diff --check passed.

Coverage includes effective-state exclusions, reference validation, money/adoption/distribution
role separation, deterministic hashes, concurrent reuse, immutable versions, non-destructive
failure, human precedence, stale acceptance/approval rejection, public candidate hiding, public
hypothesis suppression, admin-only audit RLS and fixed four-query case reads. UI tests exercise
unknowns/gaps, source drilldown, Refresh, selected edit acceptance, keep current, confirmation,
stale output, bilingual labels and stale-evidence clearing after a failed fetch.

Existing Watchlist tests intermittently failed because their mock returned a fresh router object
on every render, repeatedly restarting a loading effect. The test harness now returns a stable
router, matching the actual hook; Watchlist product behavior is unchanged. Standard Starlette and
Vite-loader warnings remain. The bundled old shared-schema venv had an unavailable Python runtime;
the passing shared tests used the working API Python environment against the same schema package.

## Runtime and remaining acceptance

Final local API/frontend run against local PostgreSQL/Redis; API fingerprint is
0b0184355f0cb72c. Full canonical launcher/worker/provider smoke validation is pending alongside
real-provider authorization. Workers were not started to process real external AI jobs as a way
around the approval block. No staging deployment or push occurred.

Automatic approval review rejected the intended real benchmark twice. Its final stated reason was
that the task authorizes bounded real validation but does not explicitly name OpenAI as the allowed
external data destination. A concise destination-specific approval question was sent to the user.
Until answered, no real opportunity input is sent externally. This is an approval block, not an AI
provider failure or an implemented feature's successful quality evaluation.

Remaining: authorized 8-case real-provider evaluation; Dental vendor-neutral output inspection;
Micro Duck buyer/seller/affiliate output inspection; real-output rubric and evidence mapping review;
canonical runtime smoke and final acceptance update. Existing intermittent in-app browser transport
failures are not claimed generally fixed. The detail loader now stops superseded locale loads
between bounded requests, reducing duplicate fan-out while keeping explicit retry behavior.

Known limits: machine prose is English; one-field-at-a-time acceptance may require reconsolidation
before accepting another field; input200 Signals/250KB and history100 display caps; explicit rather
than continuous reconciliation; bounded semantic validation and lexical source relationships do
not prove factual entailment. TASK-044I/J/K and staging remain unstarted.
