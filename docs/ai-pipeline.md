# YouTube AI Business Radar — AI Pipeline Contracts v0.1

Status: Implemented through TASK-017
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

TASK-015 implements this first gate using immutable prompt `relevance-filter/v001` and
metadata-only video/channel input. The canonical SHA-256 input identity includes the input,
task type, and prompt version; the selected model is stored separately. Equivalent completed
attempts are reused unless an explicit forced rerun is requested. Every attempt transitions
through the `ai_extractions` audit record, while the video transitions through `processing` to
`queued`, `ignored`, `review`, or `failed`. This gate creates no signals or opportunities.

The provider boundary is an application-owned `AIClient`; v0.1 supplies an OpenAI Responses API
adapter with schema-constrained output. Provider errors are persisted with safe error categories,
and provider raw output is never returned by the admin API.

The provider performs only a small configured retry budget for transient transport/service errors;
the worker retains its existing infrastructure-only retry boundary. A returned response that fails
schema validation is recorded once as `invalid_output` and routed to review, not blindly retried.
Relevant videos enter `queued` for TASK-016 signal extraction. `ignored` retains the RAW video and
means only that the current prompt version classified it as irrelevant; a later explicit prompt
version may evaluate it again.

### Business signal extractor

Returns structured industry, customer, problem, solution, business-model, technology, distribution, and pricing context plus a list of atomic signals. Every signal contains a canonical signal type, statement, source evidence text, explicit claim status, and normalized confidence.

The list is not a video summary. Each item must represent one commercial observation.

TASK-016 processes only canonical videos in `queued` state during normal batches and uses the
immutable `signal-extractor/v001` prompt with bounded metadata-only video/channel input. Each
validated output signal becomes one FACT `signals` row in `review` state, with statement and
`evidence_text` stored separately and linked to both the video and producing extraction. The model's
claim status is preserved exactly; confidence never upgrades a creator claim to fact.

Top-level industry, customer, problem, solution, business-model, technology, and distribution
context is copied only where present. The shared v001 schema has no revenue amount, geography, or
sub-industry output, so those columns remain null. Pricing context is attached only to pricing
signals. No transcript is requested.

The extraction completion, all produced signals, and return of the video to `queued` commit in one
transaction. A persistence failure rolls back the complete signal set. Provider failure creates no
signals and marks the video failed; invalid structured output creates no signals and routes it to
review. Normal identity reuse returns existing signals without duplication; a forced rerun creates
a new extraction and a new extraction-owned signal history. `queued` remains the conservative video
state because later opportunity normalization is not represented by the video lifecycle.

### Comment pain miner

Returns atomic comment-derived pain signals containing category, pain, current/requested solutions, optional non-negative spend, purchase intent, evidence strength, and the internal comment UUID. It never includes author identity.

TASK-017 uses one canonical comment per extraction so source identity, input hashing, reruns, and
signal lineage remain exact. Input contains comment text/public counters plus bounded parent
video/channel context; author hash, author identity, replies, transcripts, demographics, and
sensitive-trait inference are excluded. The model-returned UUID must equal `comments.id`—the shared
schema defines an internal UUID, not YouTube's string comment identifier.

Categories are normalized deterministically: existing pain → `pain`; current workaround and
workflow inefficiency → `workflow`; purchase intent and willingness to pay → `purchase_intent`;
existing spending → `pricing`; feature request → `feature_request`; adoption blocker → `complaint`;
competitor usage → `competition`; unmet need → `demand`. Unknown categories invalidate the output
rather than extending the taxonomy. Ordinary comment evidence uses conservative claim status
`unknown`, never `creator_claim`, and starts in `review`.

A valid empty signal list is a completed extraction with zero FACT rows. Successful signal writes
and extraction completion are atomic; provider, schema, source-ID, category, or persistence failures
create no partial signals and never mutate the parent video's status. Identity reuse makes no AI
call and inserts nothing; forced reruns retain prior extraction-owned signal history. TASK-018 may
consume reviewed candidates for opportunity normalization but is not implemented here.

### Opportunity normalizer

TASK-018 normalizes one FACT signal per extraction using the explicit actions `MATCH`, `CREATE`,
and `REVIEW`:

- `MATCH` requires `opportunity_id`.
- `CREATE` requires `opportunity_id` to be null.
- `REVIEW` permits either null or a candidate opportunity ID.

Candidate retrieval is deterministic lexical matching over eligible `candidate`, `active`, and
`review` opportunities. At most 10 candidates (hard ceiling 20) are sent to the model; a returned
MATCH UUID outside that set is `invalid_output`. No embedding or pgvector dependency is introduced.

Application policy—not the model—owns side effects. MATCH confidence below 0.70 and CREATE
confidence below 0.75 route to REVIEW; both thresholds are environment-configurable. MATCH adds a
supporting link and advances only `last_activity_at`. CREATE derives a deterministic slug, creates a
`candidate` with `unknown` market stage using signal fields only, then links the signal. Slug
collision routes to review without a random suffix. REVIEW creates an `opportunity_match` or
`opportunity_creation` task with reconstructable JSON context and leaves the signal in review.

Successful side effects and extraction completion share one transaction. A successful MATCH or
CREATE makes the signal active. Provider/validation/persistence failures create no opportunity or
link. Identity reuse makes no provider call and does not repeat side effects; `force` creates a new
audited attempt. No automatic schedule is installed.

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

The exporter calls Pydantic `model_json_schema(mode="validation")` for the authoritative output models and writes deterministic, formatted JSON to `packages/schemas/json/`.

Tests regenerate schemas into a temporary directory and compare them with direct Pydantic output. Changes to a Pydantic contract require regenerated artifacts and review of prompt compatibility.

### OpenAI structured-output numeric compatibility

The AI transport models use JSON `number` fields with simple `minimum` and `maximum` constraints.
They must not emit Decimal compatibility branches such as `number|string`, or regex patterns with
lookaround assertions, because those constructs are not accepted by OpenAI Structured Outputs.

This is a transport-boundary rule only. Domain calculations and PostgreSQL `NUMERIC` persistence
continue to use `Decimal`; application services convert validated AI floats explicitly with
`Decimal(str(value))`. Compatibility tests inspect all five structured-output schemas before their
generated artifacts are committed. The semantic `v001` contracts and prompts are unchanged by this
provider-compatibility correction.

### Intelligence translation

`IntelligenceTranslationOutput` is the strict transport contract for stored locale projections.
The caller supplies the exact requested field names, and the response must contain each field once
with no extras. The `zh-CN/v001` prompt requires faithful meaning, preservation of claims and
uncertainty, proper-name and numeric stability, and translated evidence that remains visibly a
projection of the original evidence.

Translation runs asynchronously on the dedicated `intelligence_translation` queue or explicitly
through the local CLI. Source hashes and `translation-zh-CN-v001` determine reuse and staleness.
Provider/model/request ID/token audit data is persisted. No read endpoint invokes this pipeline.

### Quality review and experimental prompts

TASK-035 adds a bounded human-evaluation baseline over real dental metadata. Experimental
`signal-extractor/v002`, `opportunity-normalizer/v002`, and
`intelligence-translation/zh-CN/v002` prompts address observed compound signals, weak heading-only
evidence, customer over-expansion, vendor-specific opportunity framing, and Chinese word-order
calques. Their structured-output schemas are unchanged.

Creation does not imply promotion: runtime constants and current localization read preference stay
on v001 until the documented A/B and promotion gates pass. Signal/normalizer reprocessing must
create new extraction history; translation promotion must use `translation-zh-CN-v002`. See
`docs/intelligence-quality-review.md` and `docs/prompt-tuning-policy.md`.

TASK-036 adds a bounded cross-source evaluation path outside the active pipeline. It uses official
YouTube metadata, identical A/B inputs, current structured-output schemas, five-candidate
normalization stress, and artifact-only translation output. It intentionally opens no database
session, queues no worker job, and cannot activate or publish intelligence. See
`docs/cross-source-validation.md`.

TASK-038 keeps semantic retrieval outside the active pipeline. Its proposed future flow is lexical
top-k plus semantic top-k, deterministic bounded union/rerank, then the unchanged Normalizer, with a
lexical fallback. Experimental signal/translation v003 prompts retain existing structured-output
schemas and do not alter v001 runtime constants. See `docs/hybrid-retrieval-evaluation.md`,
`docs/signal-v003-design.md`, and `docs/translation-v003-design.md`.

## Prompt/schema version relationship

Prompt and schema versions begin at `v001` and are independently identifiable but released deliberately as a compatible pair for each task.

- A prompt version is immutable once used.
- A generated schema artifact is regenerated only from the authoritative model.
- An incompatible contract change requires a new schema version and a compatible new prompt version; it must not overwrite the historical `v001` contract in a deployed pipeline.
- Provider and model identifiers belong to runtime/extraction records, not prompt directories.
- TASK-006 creates prompt-folder guidance only, not production prompt text.

## Evaluation and failure handling

## Discovery operations

TASK-044 adds a Topic/Query control plane around the existing YouTube discovery service and worker.
Manual and scheduled executions share the same durable collection-run lifecycle; no frontend or
second scheduler calls YouTube directly. See `docs/discovery-operations-console.md`.

TASK-044D connects terminal Topic discovery batches to the existing FACT and INTELLIGENCE workers.
Stages remain separately queued and retryable; canonical-video deduplication and immutable
extraction reuse prevent query overlap from multiplying work. Topic execution status is operational
provenance and never replaces source evidence. See
`docs/discovery-to-intelligence-orchestration.md`.

Provider output must be validated against the corresponding Pydantic model before it becomes parsed output or downstream FACT data. Invalid output is recorded as `invalid_output`; raw output and extraction metadata remain available for audit. Later tasks will define retries, prompt regression datasets, and evaluation gates.

TASK-039 promotes immutable Signal Extractor v003 as the configurable runtime default. Prompt
selection and hashing are centralized, unknown overrides fail explicitly, and new Signal audit rows
store the SHA-256. Translation v003 and hybrid retrieval remain experimental; Normalizer stays v001.
See `docs/runtime-prompt-version-governance.md`.
