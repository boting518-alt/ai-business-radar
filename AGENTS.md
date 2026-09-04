# YouTube AI Business Radar — Agent Instructions

## Project Goal

Build a business-intelligence system that detects emerging AI business
opportunities from YouTube signals.

The product is not a YouTube summarization application.

The core pipeline is:

YouTube Discovery
→ Metadata / Comments
→ AI Signal Extraction
→ Opportunity Normalization
→ Trend Aggregation
→ Opportunity Scoring
→ Human Review
→ Radar Dashboard

## Product Source of Truth

Before changing architecture or product behavior, read:

- docs/product-spec.md
- docs/architecture.md
- docs/database.md
- docs/api-contract.md
- docs/ai-pipeline.md
- docs/scoring.md
- docs/development-plan.md

Do not silently override these documents.

If implementation conflicts with the specification, report the conflict
instead of inventing a new product behavior.

## Technology Stack

Frontend:
- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui

Backend:
- Python
- FastAPI
- Pydantic

Database:
- PostgreSQL
- Supabase
- pgvector where needed

Workers:
- Python

## Architecture Principles

1. Separate RAW, FACT, and INTELLIGENCE data layers.

2. LLMs extract evidence.
   Deterministic application code calculates Opportunity Score.

3. Every AI extraction must be traceable to:
   - source
   - model
   - prompt version
   - input hash
   - raw output
   - parsed output

4. Claims must not be converted into facts.

5. Opportunity records must preserve supporting evidence.

6. Human review is part of the MVP architecture.

7. External sources such as Reddit, Product Hunt and GitHub are not part
   of the first implementation unless explicitly requested.

## Scope Guard

MVP pages:

- /radar
- /opportunities
- /opportunities/[id]
- /signals
- /watchlist
- /admin/review

Do not add unrelated features without explicit instruction.

## Implementation Rules

Before implementing a task:

1. Inspect the repository.
2. Read the relevant specification files.
3. Identify affected files.
4. Implement the smallest coherent change.
5. Add or update tests.
6. Run relevant tests and linting.
7. Review the diff.
8. Report:
   - files changed
   - tests run
   - unresolved issues
   - spec conflicts

## Git Rules

Do not make unrelated changes.

Do not modify generated files unless required.

Do not rewrite existing architecture without explicit instruction.

Keep commits focused and descriptive.

## Security

Never commit:
- API keys
- service role keys
- OAuth secrets
- tokens
- passwords

Use environment variables and .env.example.

## Definition of Done

A task is complete only when:

- implementation matches the specification
- tests pass
- lint/type checks pass when applicable
- no unrelated changes are present
- documentation is updated when behavior changes