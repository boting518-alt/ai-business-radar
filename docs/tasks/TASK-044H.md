# TASK-044H — Opportunity Thesis & Business Case Consolidation (revised)

Status: Implemented and locally tested; real-provider acceptance pending explicit OpenAI destination approval.
Assessed 2026-09-09 before implementation.

See [validation report](../../artifacts/opportunity-business-case/2026-09-09/validation-report.md).

The requested task closes the audited first-Signal/vendor-specific thesis defect and is reasonable.
Implement a separate versioned machine business case, not a second normalizer or scoring policy.

Implementation decisions:

- Only active/current linked Signals enter the supplied evidence bundle; under-review and other
  excluded evidence contribute counts/warnings, not prose input or support. Source diversity is
  not customer validation. Two distinct videos per dimension means multi-video coverage only.
- Strict structured dimensions preserve source claims, editorial synthesis, hypotheses and unknowns.
  References are checked against this exact bundle, with additional category/role gates for money,
  adoption and distribution. These checks do not claim universal semantic entailment.
- Store immutable completed outputs and input snapshots; queued/running/failed attempts remain
  auditable. Identity includes evidence hash, context hash and immutable prompt hash/version.
  Context changes can invalidate a case even when Signal identities do not change.
- Manual refresh and explicit bounded reconciliation enqueue asynchronous work. No automatic paid
  sweep, read-path generation, extractor/normalizer changes or new publication threshold.
- Candidate review shows missing/stale case advisories independently of the existing six checks.
  Machine output alone never publishes. Public sections require an admin-confirmed current case;
  stale/unreviewed output is not silently introduced into an existing published dossier.
- Human Opportunity fields remain authoritative. Selected proposal acceptance (with optional edit)
  is explicit, candidate-only, optimistic and audited with source consolidation identity. Existing
  fields are reused; no numeric price, buyer taxonomy or scoring classification is inferred.
- English machine output remains labeled canonical; accepted existing Opportunity text uses the
  existing asynchronous localization architecture. Fixed labels support Chinese/English.
- Validate Dental and Micro Duck, a bounded 8–15 item real-provider benchmark, fixture versioning,
  failure/idempotency, candidate acceptance, public/auth boundaries and browser flows. Preserve
  unrelated artifacts and next-env.d.ts. Do not publish meaningful candidates or overwrite Dental.
- Commit `feat: consolidate opportunity business cases`; do not push or deploy staging.
