# TASK-044F — Signal Semantic Guardrails + Historical Quality Repair (revised)

Status: Complete (local validation). Revised and implemented 2026-09-09.

Validation: artifacts/signal-semantic-quality/2026-09-09/validation-report.md.

The proposed task is accepted with the following implementation constraints:

1. Use additive persisted semantic projection fields and append-only decision audit. Preserve
   Signal type, claim_status, source, AI raw/parsed outputs, links and prior scores. Semantic
   validity is independent of lifecycle status. Legacy rows initially retain compatibility;
   bounded audit and every runtime normalization/approval boundary enforce the guardrail.
2. Freeze actor_role and evidence_role separately; unknown is legitimate. Speaker is not always
   the commercial subject. Deterministic rules inspect the individual evidence and statement,
   not unrelated affiliate boilerplate elsewhere in a video. Mixed/unsupported attribution goes
   to review. Recognized seller CTA cannot be activated through a review shortcut.
3. Exact duplicate suppression only: same source, extractor family, full statement, evidence,
   category, claim status and commercial context. Preserve the oldest validated active record;
   a newer prompt alone confers no authority. Similar/paraphrased/compound claims remain separate
   candidates for human inspection, never automatic semantic merges. No universal dedupe claim.
4. Runtime v003/schema v001 remain unchanged. v004 is experimental and uses the same strict schema;
   actor/role audit is a deterministic projection, not an incompatible unversioned AI schema edit.
5. Repair CLI defaults to read-only and caps work at 100 active purchase_intent/revenue/adoption/
   pricing records. Apply is explicit, transactional, idempotent, reports exact IDs and impact.
   No bulk provider re-extraction. A/B calls are bounded, artifact-only and use identical inputs.
6. Filter current semantic validity in feed/evidence/counts, activation, normalization, translation,
   trends and score inputs, including decision-time checks. Preserve linked vs supporting semantics.
7. Recompute affected trends at a new timestamp, then append score-v001 history; never rewrite
   historical snapshots or formula coefficients. Original task references docs/opportunity-scoring.md,
   which does not exist; docs/scoring.md is authoritative. Pricing legitimately contributes to the
   frozen revenue-evidence proxy; it is not reclassified as actual revenue or buyer demand.
8. Reuse signal_validation review, with explicit notes for ambiguous human approval; deterministic
   invalid/superseded records cannot be approved. No new admin dashboard/API is necessary.
9. Benchmark separates curated deterministic regression from actual v003/v004 generation. Record
   denominators, unmeasurable fields, failures and promotion decision honestly; no production-accuracy
   claim. Keep v004 experimental absent adequate independent promotion evidence.

Deliver code/migration, focused regression and full required checks; bounded real Dental/Micro Duck/
affiliate audit, reviewed apply, score history and browser validation; docs and artifacts under
artifacts/signal-semantic-quality/. Preserve unrelated artifacts and next-env.d.ts. Dedicated commit:
`fix: harden signal semantic quality and history`. Do not push.
