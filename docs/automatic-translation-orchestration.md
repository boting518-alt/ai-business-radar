# Automatic Intelligence Translation Orchestration v0.1

TASK-042 connects stored zh-CN translation to the normal intelligence lifecycle without adding an
LLM call to any read path. Canonical English remains authoritative and immediately readable.

## Eligibility and fields

| Entity | Eligible state | Automatic fields |
| --- | --- | --- |
| Signal | `review`, `active` | `statement`, `evidence_text` |
| Opportunity | `candidate` with open `opportunity_activation` review; `active` | `name`, `one_line_thesis`, `problem`, `solution` |

Ignored/rejected Signals and rejected/merged/archived Opportunities are excluded. Empty optional
fields are skipped. Industry/customer free text, source titles, brands, enums, and taxonomy labels
are not automatically translated; taxonomy labels remain fixed controlled localizations.

## Lifecycle and transaction boundary

Signal extraction and comment pain mining commit new review Signals before best-effort enqueue.
Activation-review creation commits before Opportunity enqueue. Review approval commits the Signal
or Opportunity active transition before enqueue. Redis or coverage-check failure is logged as
`translation_enqueue_failed` and never rolls back creation, review, or Publish.

The dedicated worker queue performs provider work asynchronously with its existing bounded retry
policy. Invalid structured output fails safely. Existing current projections remain untouched, and
canonical English plus original Signal evidence continues to provide fallback.

## Coverage, versioning, and reconciliation

`TranslationCoverageReconciliationService` projects required, translated, missing, stale, and
failed fields into `complete`, `partial`, `missing`, `stale`, or `failed`. A field is current only
when locale, SHA-256 source hash, `current` status, and the runtime translation version all match.
The version is resolved from `RUNTIME_PROMPT_DEFAULTS`; v0.1 remains
`translation-zh-CN-v001`, while v003 remains experimental.

The maintenance scheduler scans a bounded batch every 20 minutes by default. The default limit is
100 and the hard request limit is 500. It enqueues only eligible non-current entities. Worker-side
translation remains idempotent, so a repeated reconciliation after completion reuses all fields and
makes no provider call. A Redis `SET NX` lease keyed by entity, locale, and version suppresses
simultaneous active jobs for 15 minutes. Enqueue failure releases the lease; its bounded expiry lets
later reconciliation repair worker/provider failures.

Manual CLI from `apps/api`:

```bash
uv run python scripts/reconcile_translations.py --locale zh-CN --limit 100 --dry-run
uv run python scripts/reconcile_translations.py --locale zh-CN --limit 100
uv run python scripts/reconcile_translations.py --locale zh-CN --limit 50 \
  --use-live-validation-db
```

Admin-only API:

```text
POST /api/v1/admin/localization/reconcile
{"locale":"zh-CN","limit":100,"dry_run":false}
```

Dry-run reads coverage only: it performs no database write, enqueue, or model request.

## Observability and limitations

Structured events distinguish review/active triggers, reconciliation scans/enqueues/skips, and
enqueue failure, with entity type/ID, locale, version, and reason. Provider/model/token audit remains
on persisted localization rows. There is no frontend status badge in v0.1; localized text is shown
when current, otherwise canonical English is shown without waiting.
