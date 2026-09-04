# YouTube AI Business Radar — AI Pipeline Contracts v0.1

Status: Frozen for TASK-006
Version: 0.1
Last updated: 2026-09-04

## Scope and ownership

The authoritative Python domain and AI structured-output models live in:

```text
packages/schemas/python/ai_business_radar_schemas/
```

Pydantic v2 models are the single source for validation and generated JSON Schema. Generated files under `packages/schemas/json/` are artifacts and must not be edited as independent schema definitions.

This package defines contracts only. It does not invoke a provider, choose a model, implement prompts, normalize opportunities, calculate scores, or persist records.

## Domain boundary

Canonical Python enums mirror the frozen PostgreSQL CHECK values. Tests compare each database-backed enum with the relevant named constraint in `database/migrations/0001_initial_schema.sql` to detect drift.

Domain contracts cover:

- Explicit video, comment, and opportunity source references.
- Atomic signal creation, extraction candidates, and reads.
- Opportunity creation, reads, and summaries without embedded current-score columns.
- Structured scoring inputs, components, and results without formulas.
- Review-task reads and decision requests.

Optional opportunity classifications without frozen database values—`competition_level`, `build_difficulty`, and `sales_difficulty`—remain strings rather than enums.

## Structured-output requirements

All AI output models reject undocumented extra fields. Confidence, monetary values, counts, prices, and scores use shared bounded types. Task-specific validators enforce cross-field rules that JSON primitive types cannot express alone.

Each persisted AI extraction must still record its source/target, task type, provider, model, prompt version, input hash, status, raw output, and parsed output as defined by the database model.

## Task-to-schema mapping

| AI task type | Pydantic model | Generated JSON Schema | Prompt directory |
| --- | --- | --- | --- |
| `relevance_filter` | `RelevanceFilterOutput` | `relevance_filter.v001.schema.json` | `prompts/relevance-filter/` |
| `signal_extractor` | `BusinessSignalExtractorOutput` | `signal_extractor.v001.schema.json` | `prompts/signal-extractor/` |
| `comment_pain_miner` | `CommentPainMinerOutput` | `comment_pain_miner.v001.schema.json` | `prompts/comment-pain-miner/` |
| `opportunity_normalizer` | `OpportunityNormalizerOutput` | `opportunity_normalizer.v001.schema.json` | `prompts/opportunity-normalizer/` |
| `hype_detector` | `HypeDetectorOutput` | `hype_detector.v001.schema.json` | `prompts/hype-detector/` |

## Contract semantics

### Relevance filter

Returns whether content is relevant, normalized relevance confidence, optional content/topic labels, and a reason.

### Business signal extractor

Returns structured industry, customer, problem, solution, business-model, technology, distribution, and pricing context plus a list of atomic signals. Every signal contains a canonical signal type, statement, source evidence text, explicit claim status, and normalized confidence.

The list is not a video summary. Each item must represent one commercial observation.

### Comment pain miner

Returns atomic comment-derived pain signals containing category, pain, current/requested solutions, optional non-negative spend, purchase intent, evidence strength, and the internal comment UUID. It never includes author identity.

### Opportunity normalizer

Uses the explicit actions `MATCH`, `CREATE`, and `REVIEW`:

- `MATCH` requires `opportunity_id`.
- `CREATE` requires `opportunity_id` to be null.
- `REVIEW` permits either null or a candidate opportunity ID.

The output proposes normalization; it does not bypass human review or perform persistence.

### Hype detector

Returns content-hype and real-demand scores on `0..100`, an explicit classification, and a reason.

TASK-006 freezes the previously unspecified classification taxonomy as:

- `content_driven`
- `mixed`
- `demand_driven`
- `insufficient_evidence`

This classification is an AI structured input. Final stored Hype Risk calculations must remain reproducible from persisted inputs and deterministic application rules.

## JSON Schema generation

Run the exporter from `packages/schemas/python`:

```bash
uv run python scripts/export_ai_json_schemas.py
```

The exporter calls Pydantic `model_json_schema(mode="validation")` for the five authoritative output models and writes deterministic, formatted JSON to `packages/schemas/json/`.

Tests regenerate schemas into a temporary directory and compare them with direct Pydantic output. Changes to a Pydantic contract require regenerated artifacts and review of prompt compatibility.

## Prompt/schema version relationship

Prompt and schema versions begin at `v001` and are independently identifiable but released deliberately as a compatible pair for each task.

- A prompt version is immutable once used.
- A generated schema artifact is regenerated only from the authoritative model.
- An incompatible contract change requires a new schema version and a compatible new prompt version; it must not overwrite the historical `v001` contract in a deployed pipeline.
- Provider and model identifiers belong to runtime/extraction records, not prompt directories.
- TASK-006 creates prompt-folder guidance only, not production prompt text.

## Evaluation and failure handling

Provider output must be validated against the corresponding Pydantic model before it becomes parsed output or downstream FACT data. Invalid output is recorded as `invalid_output`; raw output and extraction metadata remain available for audit. Later tasks will define retries, prompt regression datasets, and evaluation gates.
