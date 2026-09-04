# ADR-001: Monorepo and Tooling

Status: Accepted
Date: 2026-09-04

## Context

The product contains a TypeScript web application, Python API and workers, shared contracts, scoring code, prompts, database assets, and documentation. v0.1 needs consistent coordination without the setup and maintenance cost of a monorepo framework or a single cross-language package manager.

## Decision

Keep the existing coordinated monorepo layout. Use lightweight independent toolchains:

- Node.js, TypeScript, Next.js, and npm within `apps/web`.
- Python 3.12+, FastAPI, Pydantic v2, and uv for the API, workers, and Python packages.
- No Nx, Turborepo, Bazel, Pants, or similar framework in v0.1.
- Run commands from the owning workspace unless a later explicit root workspace adds coordinated commands.
- Keep Python/Pydantic authoritative for backend API schemas.
- Reserve `packages/schemas` for justified language-neutral, AI-output, or generated contracts rather than duplicating all Pydantic models.

## Consequences

- Each ecosystem retains familiar tooling and independent dependency resolution.
- Initial setup and CI remain straightforward.
- Cross-workspace coordination is documented rather than enforced by a monorepo orchestrator.
- TypeScript contracts may temporarily be maintained separately; OpenAPI generation can be adopted later when its value outweighs its cost.

## Revisit when

Build/test coordination becomes slow or error-prone enough to justify orchestration, or contract drift demonstrates a need for automated OpenAPI client generation.
