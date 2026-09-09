# TASK-044H implementation and local validation

Date: 2026-09-09. **Implementation and authorized 8-case real-provider evaluation complete. Full canonical
launcher smoke remains blocked by automatic approval review; do not mark full task acceptance
or production readiness complete.**

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

Prompt: opportunity-consolidation/v002, registered in the shared prompt registry; used v001 remains immutable. Structured schema
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
source-comparison review. The bounded real-output review below is performed by Codex, not an
independent customer/domain expert; commercial claims remain unverified.

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

## Authorized real-provider benchmark

The user explicitly authorized sending these eight opportunities and their effective evidence/context
to OpenAI. Two rounds used the same eight records with configured model gpt-5.6-terra: 16 generation
attempts, recorded usage 113,524 input / 28,964 output tokens. No wider backfill was performed.

v001 completed5/8;3/8 were rejected as invalid_output: preorder business-model category mismatch,
companion adoption category mismatch, and plush competition category mismatch. Raw rejected output
and failed records remain auditable; none replaced canonical definitions. No guardrail was relaxed.
New immutable v002 explicitly instructs per-dimension eligibility and source-excerpt support:
preorder availability is not a business model/channel, revenue or buyer intent is not adoption,
and adjacent product names alone are not competition. It also rejects inherited metadata as sufficient
channel evidence. All8/8 v002 outputs completed; all101/101 cited Signal occurrences belong to their
exact effective input bundles and pass category/role checks.

Codex reviewed customer scope, problem grounding, vendor neutrality where justified, pricing,
revenue ownership, distribution, contradiction/context retention, unknowns, references and useful
next validation steps. Pass below means appropriately bounded against supplied sources, including
explicit unknowns; it does not mean the opportunity is commercially validated.

| Case | Scope/problem/solution assessment | Commercial boundaries and next validation |
| --- | --- | --- |
| Dental | Pass: dental organizations/operators; repeated vendor-claimed front-office problems; vendor-neutral receptionist/dashboard pattern with3 vendor examples | Pricing/revenue/adoption/build/competition/business model unknown; seller demo/consultation/audit channels are CTAs, not conversion. Validate buyer, operations, integrations and economics. |
| Micro Duck preorder | Pass:3 individual buyer comment Signals retained; problem/workflow unknown; limited vendor-specific description | $508 including shipping remains self-reported, currency unspecified; one transaction interpretation is qualified, not a formal seller business model. No revenue, distribution or adoption inferred. |
| Duck companion | Pass: adult users attributed to creator, buyer unknown; vendor-only capabilities; problem unknown | $399/$400 contexts preserved; $2.5M first24h sales explicitly unverified creator claim, not net revenue; no adoption/channel inference. |
| Open-source bipedal platform | Pass: developer operator, buyer unknown; Linux/Windows GPU setup friction; vendor-only RL workflow | $399 before tax/shipping vs preorder contexts; GitHub/Hub software sharing not customer acquisition;10,000-unit adoption Signal remains unverified sales claim, not usage/retention. Build inference explicitly bounded. |
| AI voice receptionists | Pass: general businesses vs clinics distinguished; clinic missed-call problem scoped; shared call-handling pattern with vendor-specific workflows | All monetization, pricing, revenue, distribution, adoption, competition/build unknown. Validate actual operators, integration and deployments. |
| AI companionship apps | Pass: creator-framed potential men/end users, not confirmed buyers; category positioning and risk claims qualified | No pricing/revenue/channel/adoption/model inferred. Human connection is only an opinion-based alternative, not verified competitive positioning. |
| Interactive AI plush | Pass: child user only evidenced for Haivivi; vendor-specific features not combined into universal capabilities | Pricing/revenue/channel/adoption/competition/model/build unknown; affiliate context not product revenue. Validate parent purchaser, real workflow and safeguards. |
| Defence robotics | Pass: defence buyer framing unconfirmed; terrain need creator-claimed; vendor stack distinct from unrelated reconnaissance example | No prices/revenue/adoption/channel/model/build invented. Boston Dynamics comparison and99% concentration assertions remain creator claims, not verified market shares. |

All8 cases preserve unknowns and concrete validation gaps.5/8 have supported problem prose;3/8
appropriately leave it unknown.4/8 provide a cross-vendor or category pattern (Dental, voice reception,
companionship apps, plush);4/8 remain explicitly vendor-specific because evidence does not justify
broader generalization. The companion price-context discrepancy is retained (1/1 observed differing
price case); there are no effective explicit contradicting links in this selected real sample, so
contradiction-link enforcement is tested by fixtures, not claimed tested by real contradictions.

No unsupported monetary/channel assertions were identified in the final source-comparison review:
pricing0/3 nonempty sections (other5 unknown), revenue0/1 (other7 unknown), distribution0/2
(other6 unknown). These are observed sample counts, not production hallucination rates. Semantic
classification remains an upstream dependency; for example, the platform's sales claim is already
an adoption Signal and remains labeled as an unverified sales claim, not independently validated use.

See quality-benchmark.json for all dimension-to-Signal mappings and unchanged-definition checks;
case-*-v002.json for complete actual input/output/model/token audit; case-*.json for first-round
history. Eight real definitions and lifecycle states are unchanged and all cases await confirmation.

Dental before: “Dental appointment leads are organized inside the VitalDesk dashboard.”
After machine solution: an AI receptionist/front-desk dashboard pattern assisting inbound communication,
appointment administration, request routing and staff visibility, with named vendors only as examples.
The original published thesis and solution remain unchanged as explicitly required.


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

528 tests passed: API271, PostgreSQL73, worker24, shared schemas60, frontend100 (13 files).
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

Local API and the bounded single-process/single-thread opportunity_consolidation worker both report
fingerprint0b0184355f0cb72c against local PostgreSQL/Redis. Existing production frontend runs on3000.
An exact duplicate of completed real Dental v2 was delivered through Redis and acknowledged by the
worker; its entire persisted record stayed byte-equivalent after canonicalization, with no additional
provider call. Same-input service request also reused that identity. See bounded-runtime-smoke.json.
The dedicated worker was stopped after the smoke check. No other queues were consumed by this test.

Real browser verification: Chinese Dental v2 shows38 effective links, separate supported/unknown
sections and pending confirmation. Solution drilldown returns exactly5 cited records across3 videos
with source links and creator-claim status. English Micro Duck v2 shows three buyer comments with
parent video/original-comment provenance; pricing and absent adoption/channel/revenue remain separate.
Both cases remain unpublished/unconfirmed as appropriate; UI language restored to Chinese. The earlier
synthetic candidate UI acceptance/revision/immutable-history and public confirmed dossier checks remain
valid, with fixtures archived afterwards.

Automatic approval review rejected ./scripts/dev-runtime.sh because it also starts the scheduler
and every queue consumer, potentially processing YouTube/translation jobs beyond the expressly
allowed eight-case OpenAI scope. The safer dedicated-worker smoke was approved and completed.
The attempted obsolete-fixture queue cleanup was sandbox-blocked before mutation; no queue cleanup
was applied. Full canonical launcher smoke remains pending explicit authorization for those broader
background consumers. This is the only remaining task acceptance item; the development-plan checkbox
stays open. No staging deployment or push occurred.

Known limits: machine prose is English; one-field-at-a-time acceptance may require reconsolidation
before accepting another field; input200 Signals/250KB and history100 display caps; explicit rather
than continuous reconciliation; bounded semantic validation and lexical source relationships do
not prove factual entailment. Existing intermittent in-app browser transport failures are not claimed
generally fixed. TASK-044I/J/K and staging remain unstarted.
