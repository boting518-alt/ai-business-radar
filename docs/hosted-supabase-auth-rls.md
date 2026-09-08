# Hosted Supabase Auth and RLS Drill v0.1

The browser uses only the project URL and publishable key. It obtains a user session through
Supabase SSR and sends the user access token to FastAPI. FastAPI verifies asymmetric tokens through
JWKS, then resolves `sub` through `public.user_profiles`; JWT metadata never grants application
admin rights. The secret/service-role key is restricted to explicit server-side Auth administration
for drill-user creation and cleanup.

Local mode keeps `DATABASE_URL` on local PostgreSQL. Hosted drill mode supplies the separate
server-only `HOSTED_SUPABASE_DATABASE_URL`; it never replaces `DATABASE_URL` automatically. Direct
PostgreSQL was validated for migrations and long-lived asyncpg connections. A session pooler is the
IPv4 fallback; transaction pooling is not used for migrations.

Browser-safe mapping: `NEXT_PUBLIC_SUPABASE_URL` plus `NEXT_PUBLIC_SUPABASE_ANON_KEY` containing the
project publishable key. Server-only mapping: `SUPABASE_SERVICE_ROLE_KEY` may contain `sb_secret_*`.
`SUPABASE_JWKS_URL`, issuer, and audience are public configuration. Both
`SUPABASE_JWT_ISSUER/AUDIENCE` and legacy local aliases `SUPABASE_ISSUER/AUDIENCE` are accepted.

Apply migrations only after a read-only inventory. Empty schemas receive numeric migrations in
order with stop-on-error; partially populated schemas require manual reconciliation. Run
`scripts/verify_supabase_schema.sql` afterward. The hosted drill uses dedicated email aliases and
synthetic rows containing `abr-hosted-drill`; it never copies local intelligence.

Expected failures: missing/invalid/expired token 401; valid token without profile 403; ordinary user
on admin endpoints 403; admin success 200; unavailable DB 503 where the endpoint requires it; RLS
denial is either a denied write or an empty result. Owner-scoped Watchlists remain isolated even
from application admins at the database policy layer.

Use `uv run python scripts/validate_hosted_supabase.py preflight|auth|rls|full`. `--dry-run` performs
only presence/schema planning. Auth validation accepts access tokens through untracked
`SUPABASE_TEST_USER_ACCESS_TOKEN` and `SUPABASE_TEST_ADMIN_ACCESS_TOKEN`, or through an explicitly
selected untracked `--state-file`. Real RLS probes require that state file so every query targets
the dedicated drill UUIDs.

Cleanup is explicit and marker-guarded:

```bash
uv run python scripts/validate_hosted_supabase.py full \
  --cleanup-test-data --state-file /private/tmp/abr-hosted-drill-state.json
```

This removes only the recorded application rows. Add `--delete-auth-users` to also delete the three
dedicated Auth identities; that flag is a separate, deliberate server-side admin action. The script
rejects state without an `abr-hosted-drill-` marker and never prints passwords, tokens, or keys.

Staging deployment remains a separate task after this drill. No service-role key belongs in browser
config, JavaScript bundles, normal API authorization, or user-facing database requests.
