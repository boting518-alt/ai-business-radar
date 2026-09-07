# Intelligence Translation Worker v0.1

## Scope

The worker creates stored `zh-CN` projections from canonical `en-US` intelligence. It translates
only signal `statement`/`evidence_text` and opportunity `name`/`one_line_thesis`/`problem`/`solution`.
It does not translate taxonomy-like fields, mutate canonical rows, publish opportunities, or run on
product reads.

## Version and configuration

- Prompt: `prompts/intelligence-translation/zh-CN/v001.md`
- Translation version: `translation-zh-CN-v001`
- Model environment variable: `INTELLIGENCE_TRANSLATION_MODEL`
- Queue: `intelligence_translation`
- Batch limit: 1–50 entities

The provider/model setting is mandatory for non-dry runs and is recorded per projection. Prompt and
translation versions are immutable once used.

## Idempotency and staleness

Each canonical field is SHA-256 hashed. A current row with the same entity, field, locale, source
hash, and version is reused without an AI call. A changed source or version produces a new current
projection and retains the old row as `stale`. `force` regenerates the matching projection. All
requested fields for one entity validate before a single atomic database write.

## Entry points

The admin-only API endpoints enqueue work and return HTTP 202:

- `POST /api/v1/admin/localization/translate`
- `POST /api/v1/admin/localization/translate-batch`

The worker exposes `translate_signal`, `translate_opportunity`, and `translate_batch` actors.
Transient provider/rate-limit failures receive at most two worker retries. Configuration,
validation, authorization, and other permanent failures are not retried.

Run the local CLI from `apps/api`:

```bash
uv run python scripts/translate_intelligence.py signal --id <uuid> --dry-run --show-sample
uv run python scripts/translate_intelligence.py opportunity --id <uuid>
uv run python scripts/translate_intelligence.py batch --entity-type signals --limit 5
```

Dry-run calculates missing/stale/reusable fields but performs no provider call and no database
write. Add `--force` for explicit regeneration, `--only-stale` for stale-only batch selection, or
`--artifact-dir ../../artifacts/intelligence-translation` to create a local validation summary.

## Audit and verification

Every written projection records provider, model, deterministic prompt hash, provider request ID
when available, input/output token counts, canonical source hash, translation version, lifecycle
status, and timestamps. Never
place API keys, raw provider credentials, or secrets in validation artifacts.

Verification should cover schema export, service and database integration tests, worker actor tests,
API authorization/enqueue tests, linting, and frontend regressions. A live validation additionally
checks translated reads, canonical fallback for missing projections, original evidence retention,
and zero provider activity on read paths.
