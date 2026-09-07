# Prompt Tuning and Promotion Policy v0.1

## Versioning

Prompts become immutable after first provider use. Changes require a new file such as `v002.md`;
the previous bytes, extraction records, prompt hashes, and generated intelligence remain intact.
Schema compatibility and prompt version are reviewed separately.

Creating an experimental prompt does not change the configured runtime default. Translation prompt
`zh-CN/v002` maps to `translation-zh-CN-v002` only if promoted. Existing v001 localization rows
remain historical and must never be destructively rewritten.

## Bounded A/B validation

Compare v001 and the candidate prompt using identical canonical inputs, provider, model, structured
output schema, and evaluation rubric. Record input IDs, prompt hashes/versions, provider/model,
token usage, output verdicts, regressions, and stochastic limitations. Initial local validation is
bounded to at most 20 signals, five opportunities, and 20 translated fields.

After credential rotation is confirmed, the current dental comparison can be reproduced from
`apps/api` without persistence:

```bash
uv run python scripts/compare_quality_prompts.py --output <artifact-path>/ab-results.json
```

The script uses fixed bounded local entity IDs, stores no provider credentials or raw authorization
metadata, and never calls extraction/localization persistence services.

Synthetic golden fixtures guard semantic properties and forbidden behavior; they do not substitute
for real-data human review. Avoid brittle exact wording checks except immutable hashes and explicit
known-bad regression phrases.

Cross-source evaluation uses the bounded protocol in `docs/cross-source-validation.md`. It adds
multiple verticals, distinct channels, lexical-candidate stress, false-merge review, and domain-term
translation checks while remaining artifact-only. Cross-source results can recommend a decision but
cannot change the active prompt configuration.

## Promotion rule

A candidate becomes the default only when all conditions hold:

1. no major regression is observed;
2. evidence grounding is equal or better;
3. claim preservation is equal or better;
4. commercial usefulness materially improves for the observed failure modes;
5. structured output remains schema-compatible;
6. golden fixtures and the complete regression suite pass.

If evidence is mixed or validation is blocked, keep v001 and label v002 experimental. Model changes
must be evaluated separately from prompt changes; do not hide a prompt weakness by silently moving
to a stronger model.

## Reprocessing safety

Signal or normalization re-evaluation creates new versioned `ai_extractions` and never overwrites
v001 history. New signals remain in the normal review/normalization workflow and are never
automatically activated or published. Translation v002 creates separate versioned projection rows;
read preference changes only as an explicit promotion step. No score, trend, activation, review, or
Radar visibility rule changes as part of prompt tuning.

Quality review remains an artifact plus checked-in fixtures while the methodology evolves. A
permanent database quality-review model is not justified for v0.1.
