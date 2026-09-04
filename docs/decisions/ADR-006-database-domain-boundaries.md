# ADR-006: Database Domain Boundaries

Status: Accepted
Date: 2026-09-04

## Context

The v0.1 database must retain source data, extracted facts, and derived intelligence with strong lineage while allowing evolving product taxonomies. It must support retries, historical analysis, reproducible scores, human review, and opportunity merging without introducing separate databases or source systems outside the frozen MVP.

## Decision

- Use one Supabase-hosted PostgreSQL database with logical RAW, FACT, and INTELLIGENCE ownership boundaries.
- Use UUID primary keys and `TIMESTAMPTZ` timestamps.
- Use relational columns for stable domain attributes and JSONB only for genuinely semi-structured payloads or calculation snapshots.
- Use `VARCHAR` plus PostgreSQL `CHECK` constraints rather than PostgreSQL ENUM types for evolving statuses and taxonomies.
- Treat source snapshots, AI extraction audit records, trend snapshots, score history, merge history, and resolved review decisions as retained historical records.
- Treat video and trend snapshots and opportunity score rows as append-only. Corrections create new observations or calculations rather than rewriting history.
- Require signals and opportunity evidence to retain source and extraction provenance. Claims remain explicitly classified and are never promoted to facts by storage convention.
- For the small known v0.1 source universe, retain required `source_type`/`source_id` identity fields but add explicit nullable foreign keys with constraints matching the discriminator: video/comment for signals, and video/comment/opportunity for AI extraction targets. This avoids unconstrained polymorphic references in high-value provenance tables.
- Preserve opportunity merges in a dedicated `opportunity_merge_history` table. The canonical opportunity survives, the duplicate remains queryable with `status = 'merged'`, and evidence provenance is never destroyed.
- Defer vector columns and pgvector indexes until semantic opportunity-candidate retrieval is implemented and its embedding model and query shape are known.

## Consequences

- Logical layers can evolve independently without operationally separating databases.
- CHECK-constrained strings are easier to extend than PostgreSQL ENUM types, but migrations must still update allowed-value constraints deliberately.
- Explicit source foreign keys add columns and validation rules, but make orphaned or mistyped high-value provenance less likely.
- Append-only history increases storage use while preserving auditability and reproducibility.
- Merge operations require a transaction and retained lineage rather than destructive deduplication.
- Similarity search cannot be implemented until a later task defines vector ownership, dimensions, model versioning, and indexes.

## Revisit when

New evidence sources make explicit source foreign keys unwieldy, storage volume requires formal retention/partitioning, or semantic retrieval requirements justify pgvector schema and index decisions.
