# ADR-005: Deployment Topology v0.1

Status: Accepted
Date: 2026-09-04

## Context

The MVP needs a low-operations deployment that supports a Next.js web app, Python API, asynchronous workers, Redis, PostgreSQL, and authentication without requiring Kubernetes or premature independent services.

## Decision

Use this production topology:

- Deploy the Next.js web app to Vercel.
- Deploy FastAPI as a containerized service.
- Deploy the Python worker runtime as a separate containerized process or processes.
- Use managed Redis where practical.
- Use Supabase-hosted PostgreSQL and Supabase Auth.
- Allow API and workers to share an initial VM/container host while remaining separate, independently restartable processes or containers.
- Do not require Kubernetes.

For development, run web, API, and worker components as separate local processes, with local or explicitly configured development Redis and Supabase services.

## Consequences

- The web tier uses a platform optimized for Next.js.
- Stateful persistence and authentication are delegated to Supabase.
- API and worker deployment stays portable across container hosts.
- Redis and the Python host still require operational ownership.
- The exact API/worker hosting vendor, networking, scaling thresholds, and recovery plan remain open.

## Revisit when

Load, reliability, isolation, compliance, or operational requirements justify separate hosts, orchestration, or a different managed platform.
