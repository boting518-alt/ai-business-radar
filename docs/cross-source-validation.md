# Cross-Source Intelligence Validation v0.1

## Scope and safety

TASK-036 runs an artifact-only validation across dental reception, legal intake, property
management, ecommerce support, and bookkeeping. It uses only the official YouTube Data API and the
configured OpenAI structured-output client. It does not open a database session, enqueue jobs,
activate opportunities, publish Radar records, replace translations, or change runtime prompt
defaults.

The bounded run selected 20 videos: four distinct channels in each of five verticals. Ten videos
(two per vertical) received v001/v002 signal extraction and normalization comparison. Sixteen
fields across the four non-dental verticals received translation comparison. Comments were sampled
only as source-diversity diagnostics and were not sent to the model in this run.

## Reproduction

From `apps/api`, with credentials supplied through the ignored root `.env`:

```bash
uv run python scripts/validate_cross_source.py \
  --output ../../artifacts/cross-source-validation/<timestamp>/cases.json
```

The full run checkpoints after each bounded provider call. Candidate stress can be rerun against an
existing artifact with `--normalizer-stress-only`. The production-equivalent lexical ranking can be
replayed offline with `--lexical-only`.

## Human evaluation

Signal review uses the first three output slots for each of the ten A/B inputs (30 slots per
version), balanced at six per vertical. A schema-invalid response consumes its slots as failures.
Review dimensions are relevance, grounding, atomicity, category correctness, commercial
usefulness, claim preservation, and redundancy. These manual ratios are directional, not product
KPIs.

Opportunity review asks whether two independent sources describing the same buyer/workflow converge,
whether similar technology serving different buyers remains separate, whether names are
vendor-neutral, and whether lexical candidate retrieval exposes the expected candidate. Translation
review covers faithfulness, professional Chinese, domain terminology, proper names, claim strength,
and evidence integrity.

Cross-Source Convergence Rate is the share of human-defined groups with two or more independent
sources that normalize to one expected opportunity. False Merge Rate is the share of materially
different buyer/problem/workflow cases assigned to the same opportunity; Missed Merge Rate is the
share of same-pattern cases split or created again. Signal Redundancy Rate counts same-source or
semantically interchangeable assertions that add no evidence. Repeated claims from independent
channels remain distinct corroborating provenance and are not duplicates.

Source independence is established conservatively from distinct YouTube video and channel IDs.
Vendor identity is recorded only when explicit in public metadata; unclear ownership remains
unknown. Four uploads from one company channel would still count as one independent channel.

Canonical opportunity quality is assessed from buyer + problem/workflow + repeatable solution.
Vendor or product names may remain in evidence but must not control the canonical name, thesis,
problem, solution, or customer type.

## Interpretation policy

Prompt decisions follow `docs/prompt-tuning-policy.md`. A better result in one bounded run is not an
automatic promotion. Mixed evidence, unchanged output, insufficient negative cases, or a major
regression yields `KEEP_EXPERIMENTAL`. Any future promotion belongs to TASK-037 or another explicit
task and must not rewrite historical v001 records.

## Current findings and retrieval direction

The dated report records 10/10 correct normalization matches, five converged source groups, no
observed cross-vertical false merge, and first-place lexical retrieval in 10/10 explicit cases.
Signal v002 improved atomicity but retained category errors; translation v002 improved overall
fluency but remained awkward for legal intake. All v002 prompts therefore remain experimental.

Lexical retrieval is adequate when buyer and workflow vocabulary overlap directly. It has not been
validated for paraphrases, multilingual inputs, sparse comments, or close same-industry workflows.
The next justified architecture experiment is an offline lexical-versus-embedding retrieval
evaluation using reviewed negatives. pgvector or semantic retrieval must not be introduced until
that experiment demonstrates recall benefit without unacceptable false merges.

TASK-037 performs that harder lexical baseline with same-industry negatives and low-overlap
paraphrases. Its 83.3% low-overlap Recall@5 and one obvious missing dental-reception candidate
justify an offline hybrid-retrieval experiment, but not a production semantic retrieval change.
See `docs/semantic-separation-validation.md`.
