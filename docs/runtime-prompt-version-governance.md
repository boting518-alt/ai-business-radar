# Runtime Prompt-Version Governance v0.1

Status: Frozen by TASK-039

## Runtime matrix

| Pipeline | Runtime version/status |
| --- | --- |
| Relevance Filter | `v001` |
| Signal Extractor | `v003` (promoted) |
| Comment Pain Miner | `v001` |
| Opportunity Normalizer | `v001` |
| Translation zh-CN | `v001`; `v003` remains experimental |
| Hybrid Retrieval | offline only |
| Scoring | `score-v001` |
| Trend | `trend-v001` |

`RUNTIME_PROMPT_DEFAULTS` in the prompt registry is authoritative. Resolution returns immutable
content, version, SHA-256, and internal path metadata. Admin-only
`GET /api/v1/admin/runtime/ai-versions` exposes versions and hashes, never paths or secrets.

## Configuration and rollback

Signal extraction defaults to `SIGNAL_EXTRACTOR_PROMPT_VERSION=v003`. Set it to an existing version
such as `v001`, then restart API and workers, for code-free rollback. Unknown explicit versions fail
configuration validation without fallback. Restore `v003` and restart to end rollback. Model
selection remains independent.

## Immutability, audit, and history

Published prompt files are append-only. Regression hashes protect Signal v001/v002/v003. New Signal
extractions store task/family, version, prompt hash, provider, model, provider request ID when
available, token usage, and status. Historical rows may have null hashes because the audit column
was introduced without rewriting history.

Historical intelligence is versioned evidence and is never silently upgraded. TASK-039 performs no
historical reprocessing. A bounded admin/developer forced run with an explicitly selected known
version may create new extraction-owned Signals in review while retaining old history. Migration or
replacement requires a separate explicit task and review; it must not replace active evidence or
publish automatically.

## Promotion policy and experimental status

Promotion requires fixed fixtures, schema-valid A/B results, semantic/safety review, stable hashes,
an explicit runtime-matrix change, rollback coverage, bounded live validation, and a dedicated task.
Prompt content is not edited during promotion.

Translation v003 remains experimental: quality improved, but meaning risk remained non-zero,
including passive/calque issues and an unsupported abandoned-checkout semantic addition. Hybrid
retrieval remains offline: lexical 0.3/semantic 0.7 reached 100% Recall@5 and low-overlap Recall@5,
but candidate noise increased. Normalizer remains v001 because the surviving missed merge was
retrieval-caused rather than a demonstrated Normalizer failure.
