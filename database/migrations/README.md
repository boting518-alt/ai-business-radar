# Database Migrations

## Target

Migrations target PostgreSQL as provided by Supabase. They must also remain executable against a compatible standalone PostgreSQL instance unless a migration explicitly documents a Supabase dependency.

## Naming and order

Migration files use a zero-padded numeric prefix followed by a descriptive snake_case name, for example `0001_initial_schema.sql`. Apply files exactly once in ascending numeric order. Do not edit an applied migration; create a new migration for later changes.

The expected application mechanism will be selected with deployment tooling. Until then, apply migrations with an authenticated PostgreSQL migration client or Supabase migration workflow in a controlled environment. Never place credentials in this directory or command examples committed to the repository.

## Migration contents

- `0001_initial_schema.sql` creates the core relational schema.
- `0002_rls_baseline.sql` adds the Supabase Auth/RLS boundary separately so policy changes remain auditable.
- `0003_youtube_discovery_staging.sql` adds internal RAW staging for bounded discovery results.
- `0004_youtube_metadata_collection.sql` adds metadata-run taxonomy and staging claim/result fields.
- `0005_youtube_comment_collection.sql` separates YouTube comment edit time from row update time.
- `0006_worker_runtime.sql` timestamps metadata staging claims for bounded stale recovery.
- `0018_discovery_operations.sql` adds admin-managed discovery topics, bounded query overrides,
  durable queued runs, schedule state, and duplicate in-flight protection.
- `0019_discovery_topic_runs.sql` correlates each Topic execution with its child query runs.

Apply migrations in numeric order. `0001` creates `auth.uid()` only when it is absent so standalone
PostgreSQL can apply the RLS baseline without manual schema state; Supabase's existing function is
never replaced. The RLS migration creates missing `anon`/`authenticated`/`service_role` roles for a
portable local validation, while managed Supabase retains ownership of its existing roles. A
standalone PostgreSQL run does not constitute full Supabase Local validation.

## Initial-schema boundaries

`0001_initial_schema.sql` creates the core relational schema and enables only `pgcrypto` for `gen_random_uuid()`.

- Row Level Security policies are deferred to TASK-009 so policy behavior can be designed and tested explicitly against Supabase Auth.
- pgvector is not enabled and no vector column exists because the embedding model, dimensions, distance metric, and retrieval query are not yet defined.
- `user_profiles.auth_user_id` is the logical Supabase `auth.users.id`, but 0001 does not create a cross-schema foreign key so the migration remains portable.
- `updated_at` defaults to `NOW()` and is application-maintained in v0.1; no update trigger is installed.

## Auth and RLS baseline

0002 enables RLS on the initial 18 application tables, and 0003 enables it on discovery staging. Authenticated users can read their own profile, own and mutate only their watchlists, and read active product intelligence. Candidate/non-active intelligence is visible directly only to admins where required for review. RAW/operational tables have no authenticated policy. Review tasks have an admin-only policy, and normal users receive no profile write permission, preventing direct role escalation.

The relationship from `user_profiles.auth_user_id` to `auth.users.id` remains logical rather than a cross-schema FK, preserving migration portability and avoiding coupling profile retention to Supabase internals. Profiles are not auto-created by a trigger.

Supabase service-role connections bypass RLS and are restricted to trusted API/workers. RLS is defense-in-depth and never replaces FastAPI authorization.

## History and deletion

Video snapshots, trend snapshots, opportunity scores, AI extraction attempts, collection runs, merge history, and resolved reviews are conceptually retained. The schema does not install update-prevention triggers in 0001, so application and repository code must honor append-only rules.

Foreign keys default to restrictive behavior for source and historical intelligence. The only ownership cascade is from a deleted watchlist to its disposable watchlist items. Removing a watchlist item directly is allowed. Broad cascades must not be introduced casually.

## Source integrity

`ai_extractions` and `signals` retain `source_type` and `source_id` for a stable application-facing identity while also storing explicit nullable foreign keys. Named CHECK constraints enforce exactly one allowed source FK and require the discriminator and UUID to agree. Review-task `target_type`/`target_id` is the documented narrow polymorphic exception and remains service-enforced.
