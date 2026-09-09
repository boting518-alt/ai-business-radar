# TASK-044G — Candidate activation workspace validation

Date: 2026-09-09. Scope: local development database only. No staging deployment or push.

## Assessment and implementation summary

The task is appropriate: candidates existed but operators could not find, curate or submit them
through the UI. The implementation reuses the existing human activation service rather than
introducing a second publication policy. The revised task is `docs/tasks/TASK-044G.md`.

Explicit revisions: retain ready/needs_review/not_ready; submission still requires effective
support but may allow other blockers for review; Publish rechecks all hard blockers. Add field
revision and activation event tables because the former review row overwrote repeated defer notes.
Use only actual editable schema fields (no invented distribution field); preserve source output,
scoring formulas and public visibility. Post-publication intelligence remains asynchronous.
No unresolved specification conflict; the old documented activation-history limitation is
explicitly superseded. TASK-044H and staging remain outside this task.

## Candidate inventory

| Real research inventory | Before | After validation/fixture cleanup |
| --- | ---: | ---: |
| Candidate Opportunities | 54 | 54 |
| Ready by existing checks | 20 | 20 |
| Needs review | 0 | 0 |
| Not ready / hard blockers | 34 | 34 |
| Open activation review | 0 | 1 |
| Deferred | 0 | 1 |

Fifteen candidates have some non-current semantic evidence; fourteen have semantic-under-review
Signals. These are quality warnings, not independent buyers or verified commercial demand.
There is still one meaningful active Opportunity (Dental). Two explicitly synthetic fixture
Opportunities were temporarily added and are now archived; their four Signals are ignored.
No meaningful research candidate was published or rejected.

## Workspace, readiness and evidence

Admin review navigation now offers a server-paginated candidate list and full dossier. Filters
cover search, industry/customer taxonomy, readiness, activation review state, semantic warnings
and sort. Default priority is readiness, effective support count, then recency. Counters count
unique Opportunities; deferred overlaps open review. Default page20, max100. An actual query-count
measurement returned **11 queries for both one-item and twenty-item list responses**. The backend
still scans the candidate population and bounded lexical pools; it is not a materialized search index.

All six readiness checks share one composition for lists, detail and the locked decision boundary.
The list transmits summary readiness; the dossier displays checks, reasons, metrics, next actions
and duplicate suggestions. No frontend scoring/readiness algorithm or automatic merge exists.

TASK-044E provenance/localization is reused. Effective evidence requires active/current; excluded
and semantic-under-review evidence is a separate paginated view and never effective support.
Original statement/excerpt, claim status, relationship, semantic state, source video/channel,
RAW comments where present, stored translations and source navigation are inspectable. Invalid
and superseded evidence cannot count as unresolved current evidence simply because lifecycle is
review. The public candidate and evidence visibility boundary remains unchanged.

## Editing and audit

Allowed fields: name, thesis, problem, solution, business model, existing numeric price/currency/
period fields, market stage, competition and build difficulty. Existing numeric precision is
preserved, including sub-cent pricing; negative/non-finite prices, inverted bounds, blank names,
invalid enums and unsupported fields are rejected. Taxonomy is read-only here, with selectors
for filtering; no distribution column is invented.

Saving uses a row lock plus expected_updated_at, so stale edits and edits after publication fail.
Each changed field appends actor/time/old/new/note to opportunity_revisions. Save does not create
an activation review or publish. Readiness reloads, and persisted translations become stale by
source hash when text changes. Source AI/raw output and historical scores are untouched.

Migration0022 also records activation submitted/claimed/deferred/published/invalid events in the
same parent transaction. Repeated idempotent operations do not add duplicate events. Earlier
review records remain labeled snapshots rather than fabricated event history. Both new tables
have restrictive FKs and admin-only read RLS, without authenticated mutation grants.

## Real candidate browser validation

Candidate: `32a1149c-f46c-491e-b0fb-1ee64e08d4a0`, Roller-skating duck robot companion.

- Found through search/list, inspected six readiness checks and 12 effective linked/supporting
  Signals from five videos/five channels; one excluded semantic-under-review Signal was inspected.
- Inspected stored Chinese evidence, canonical source links and a teacher/homework adoption
  statement whose relevance to this robot still needs human judgment.
- Saved a small thesis clarification: “robotic roller-skating duck product” became “robotic
  roller-skating duck companion product”, retaining “is presented as” attribution. The note
  ties the change to the already stored solution, not an invented demand conclusion.
- Submitted review `cf89b31b-18bf-4d22-b90c-bf04b5f453e9`, claimed it with the current admin and
  used Defer. The recorded reason requests relevance checking and a clearer customer problem.
- Candidate remains non-public, review is pending/unassigned, and submit/claim/defer plus field
  history remain visible. A subsequent service submission reused this same open review.

Final browser checks also verified the English list/detail, deferred-review history and excluded
evidence labels; the UI was restored to Chinese.

See real-candidate-after-defer.json and duplicate-submission.json. This is a real local workflow,
not a database-only demonstration of UI actions.

## Disposable Publish and Invalid validation

Publish fixture: `4a0de110-a892-4bf7-958e-72d71acf5d31`.
Invalid fixture: `334d1e4f-0e58-4488-a4ac-b5f053c25fcc`.

Both were clearly marked LOCAL TEST ONLY / synthetic, with two synthetic supporting observations
and no fabricated real video URL. The source UI correctly showed unavailable source navigation.
Their near-duplicate warning was visible; it was not silently merged or treated as a hard blocker.

Publish fixture browser path: candidate → submit → claim → explicit Publish confirmation → active.
The dossier confirmed visibility using the ordinary read API, offered the public detail link and
showed score/translation pending without promising Radar rank. Its ordinary detail opened with
two visible evidence records. The ordinary Opportunity Library displayed it alongside Dental.
Searching candidates for TASK-044G then returned only the still-unpublished Invalid fixture.

The second fixture used submit → claim → explicit Invalid confirmation. It became rejected with
notes/event history retained. Ordinary read visibility was rejected, while the admin dossier stayed
read-only. Test cleanup subsequently archived both Opportunities, ignored all four synthetic
Signals/videos and preserved all provenance/review history. See fixture-*-decision.json,
fixture-public-visibility.json and fixture-cleanup.json.

## Regression and checks

**487 tests passed:** API243; PostgreSQL integration72; worker23; shared Python schemas59;
frontend90 across12 files. The ordinary API run skips the72 PostgreSQL tests, which pass separately
against a freshly migrated temporary database. Ruff, frontend TypeScript, ESLint, production Next.js
build and git diff --check passed. Existing Starlette deprecation/Vite-loader warnings remain.

Important regressions cover admin authorization, normal-user403, candidate/public404 boundary,
admin-only audit RLS, semantic evidence exclusion, stable query counts, pagination/filtering,
readiness equivalence, stale edit rejection/rollback, exact old/new values, concurrent submission
reuse, repeated Defer history and single-winner final decision. Existing activation tests cover
Invalid, stale evidence at Publish and downstream translation enqueue.

Frontend tests cover navigation/filtering, draft save without submission/publication, duplicate-click
protection, existing-review action, claim/decision confirmation, Defer, hard blockers, excluded
states, zh-CN/en-US, transport retry and post-publish links. Browser QA found and fixed stale evidence
remaining under a newly selected tab after fetch failure. It also corrected post-publish readiness
presentation (non-candidates show read-only/not-applicable) and the public unscored-history empty
state, which previously implied a current score existed.

Dental regression: still active; **38 effective linked/supporting Signals, zero purchase intent**;
three retained score records, latest **48.56**. No Dental content, links, source records or scores
were changed. See dental-regression.json.

The canonical `./scripts/dev-runtime.sh` was exercised: API/worker/scheduler all reported
`0b0184355f0cb72c`, local database ai_business_radar_live_test and local Redis. It was then stopped
for production-build browser validation. Final local API/frontend are running; worker/scheduler
from that validation launcher are stopped. There was no forced discovery, prompt change or source
fetch. Existing best-effort translation enqueue behavior was retained.

## Limits and handoff

- This is local validation, not production readiness or TASK-046 full staging dual-role E2E.
  Ordinary-user boundaries were verified by backend auth/RLS tests; browser mutations used admin.
- Default list/detail now use summary payloads and sequential bounded page requests. Earlier
  intermittent browser fetch failures occurred during validation; their general transport cause
  is not claimed fixed. Explicit retries and no-stale-evidence behavior are covered.
- Business-definition text and backend readiness explanations may remain English. Full taxonomy
  curation/reviewer UX polish belongs to TASK-044K; multi-source thesis work belongs to TASK-044H.
- Duplicate detection is bounded lexical matching; contradiction coverage is incomplete. A ready
  recommendation is not independent validation or automatic publication.
- History UI shows the most recent100 rows with truncation notice; older events remain in the DB.
- Publication does not synchronously recalculate scores/trends. Freshness is a documented
  presentation heuristic (24hours / relevant activity / edits), not a new scoring formula.
- Unrelated product-audit, positioning and technical-architecture artifacts are preserved and
  excluded from this task commit. next-env.d.ts is unchanged.

Dedicated commit message: `feat: add candidate opportunity activation workspace`. Do not push.
