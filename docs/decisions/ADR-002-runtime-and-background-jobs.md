# ADR-002: Runtime and Background Jobs

Status: Accepted
Date: 2026-09-04

## Context

Collection, AI extraction, and aggregation are asynchronous, retryable workloads with different operational profiles. The MVP needs durable queueing and scheduling without adopting a distributed-workflow platform or splitting worker modules into microservices.

## Decision

- Run the web app, FastAPI API, and Python worker runtime as distinct runtime components.
- Keep `workers/youtube`, `workers/extraction`, and `workers/aggregation` as modules of one worker runtime.
- Use Dramatiq backed by Redis for queued jobs.
- Use a lightweight Dramatiq-compatible scheduler to submit discovery, snapshot, monitoring, and aggregation jobs.
- Design jobs for at-least-once delivery with stable inputs, practical idempotency keys, bounded retry/backoff for transient failures, persisted run status, and a failed/dead-letter path for exhausted or terminal failures.
- Do not introduce Kafka, Temporal, Celery, Kubernetes-native orchestration, or worker microservices in v0.1.

## Consequences

- API requests remain responsive while long-running work executes asynchronously.
- All worker modules share a Python deployment and can share carefully owned domain packages.
- Redis becomes required infrastructure for queued work.
- Implementers must make persistence effects retry-safe and provide deliberate replay tooling for failures.
- Exact queue names, retry limits, scheduler package, and retention remain later implementation choices.

## Revisit when

Workflows require durable multi-step orchestration, substantially different scaling or isolation boundaries, or operational evidence shows Dramatiq is insufficient.
