# Opportunity Normalizer Prompts

Prompt versions are immutable after first use. TASK-018 implements `v001` for one-signal bounded
candidate normalization. Application code validates candidate IDs and owns confidence thresholds,
slug generation, persistence, and review routing.

The corresponding generated contract is `packages/schemas/json/opportunity_normalizer.v001.schema.json`. Provider and model selection are runtime configuration and must not be hardcoded in this folder.
