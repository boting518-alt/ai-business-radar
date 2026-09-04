# Database Migrations

## Target

Migrations target PostgreSQL as provided by Supabase. They must also remain executable against a compatible standalone PostgreSQL instance unless a migration explicitly documents a Supabase dependency.

## Naming and order

Migration files use a zero-padded numeric prefix followed by a descriptive snake_case name, for example `0001_initial_schema.sql`. Apply files exactly once in ascending numeric order. Do not edit an applied migration; create a new migration for later changes.

The expected application mechanism will be selected with deployment tooling. Until then, apply migrations with an authenticated PostgreSQL migration client or Supabase migration workflow in a controlled environment. Never place credentials in this directory or command examples committed to the repository.

## Initial-schema boundaries

`0001_initial_schema.sql` creates the core relational schema and enables only `pgcrypto` for `gen_random_uuid()`.

- Row Level Security policies are deferred to TASK-009 so policy behavior can be designed and tested explicitly against Supabase Auth.
- pgvector is not enabled and no vector column exists because the embedding model, dimensions, distance metric, and retrieval query are not yet defined.
- `user_profiles.auth_user_id` is the logical Supabase `auth.users.id`, but 0001 does not create a cross-schema foreign key so the migration remains portable.
- `updated_at` defaults to `NOW()` and is application-maintained in v0.1; no update trigger is installed.

## History and deletion

Video snapshots, trend snapshots, opportunity scores, AI extraction attempts, collection runs, merge history, and resolved reviews are conceptually retained. The schema does not install update-prevention triggers in 0001, so application and repository code must honor append-only rules.

Foreign keys default to restrictive behavior for source and historical intelligence. The only ownership cascade is from a deleted watchlist to its disposable watchlist items. Removing a watchlist item directly is allowed. Broad cascades must not be introduced casually.

## Source integrity

`ai_extractions` and `signals` retain `source_type` and `source_id` for a stable application-facing identity while also storing explicit nullable foreign keys. Named CHECK constraints enforce exactly one allowed source FK and require the discriminator and UUID to agree. Review-task `target_type`/`target_id` is the documented narrow polymorphic exception and remains service-enforced.
