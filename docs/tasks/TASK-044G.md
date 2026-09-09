# TASK-044G — Candidate Opportunity Review & Activation Workspace (revised)

Status: Complete — implemented and locally validated 2026-09-09. Assessed and revised before implementation.

Validation: [report](../../artifacts/candidate-activation-workspace/2026-09-09/validation-report.md).

The task is appropriate and closes the audited candidate-to-publication UI gap.
Implementation constraints after inspecting the existing service and schema:

1. Reuse `/admin/review` with candidate list/detail routes and existing activation submission,
   claim and decision APIs. Candidates remain hidden from ordinary Opportunity APIs.
2. Preserve the six existing readiness checks and `ready / needs_review / not_ready` semantics.
   Submission requires current active supporting evidence; other hard failures may be submitted
   for review but cannot be published. Warnings are advisory, not a new publication threshold.
3. Share readiness composition between batch list and decision-time assessment; no per-row
   database queries. Server evaluates filters/sorts/counts and returns at most 100 (default 20).
4. Add append-only human field revisions and activation events because current task fields
   overwrite earlier defer notes. Historical tasks retain a labeled legacy snapshot; do not
   fabricate unknown historical claim/submit events. This explicitly supersedes the old
   documented limitation on activation event history, without changing domain transitions.
5. Edit actual schema fields only, validate on the server and use optimistic updated_at checking.
   No distribution column exists: show missing schema support and linked distribution evidence,
   rather than inventing a writable field. Taxonomy mappings remain read-only here; filtering uses
   existing taxonomy selectors. No arbitrary creation or AI-source editing.
6. Effective supporting evidence requires active/current. Admin can separately inspect excluded
   linked evidence with semantic warnings, provenance and stored localization; it never counts
   toward readiness. Public visibility and evidence APIs remain unchanged.
7. Duplicate suggestions remain the existing bounded lexical policy; no automatic merge.
8. Publish uses existing locked review service and best-effort translation orchestration. Current
   service does not synchronously calculate scores/trends; show persisted timestamps and pending/
   stale states, verify the ordinary read API, and do not promise immediate Radar ranking.
9. Validate a safe real local candidate with draft/submit/reuse/Defer. Publish and Invalid tests
   use clearly marked disposable local fixtures; archive test data afterwards. No meaningful
   research candidate is published. No staging deployment or prompt/scoring changes.
10. Add backend/UI regressions, run required suites and browser checks, record inventory and
    limitations under artifacts/candidate-activation-workspace/. Preserve unrelated artifacts and
    next-env.d.ts. Commit `feat: add candidate opportunity activation workspace`; do not push.
