# ADR-004: AI Provider Abstraction and Prompt Versioning

Status: Accepted
Date: 2026-09-04

## Context

AI extraction must be auditable and replaceable without coupling domain logic to one vendor. Prompt changes must not make historical extractions impossible to reproduce or explain.

## Decision

- Define an application-facing `AIClient` abstraction with conceptual classification, extraction, and structured-generation capabilities.
- Keep provider SDKs and provider-specific behavior behind adapters. The initial adapter may use OpenAI, but the provider/model is an implementation decision.
- Store prompts under `prompts/<task-name>/v001.*`.
- Require every extraction to reference its task type, prompt version, model identifier, and input hash, and to retain raw and parsed output with source/run traceability.
- Create a new prompt version for every used-prompt change. Never silently edit an already-used prompt version.
- Keep final Opportunity Score calculation in deterministic code. Final stored Confidence Score and Hype Risk calculations must also be reproducible from persisted inputs, even when structured AI classifications contribute inputs.

## Consequences

- Extraction workflows can change providers without changing domain interfaces.
- Historical outputs remain explainable and comparable.
- Prompt fixes create additional versioned files and require deliberate rollout.
- Provider-neutral interfaces may not expose every vendor feature; provider-specific optimizations must remain compatible with application contracts.

## Revisit when

Evaluation shows that the abstraction blocks necessary capabilities, or formal prompt release/evaluation tooling is required.
