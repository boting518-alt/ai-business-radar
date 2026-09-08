# Hosted Supabase Setup Checklist

TASK-041 completed the development-project drill. Use the separate
`HOSTED_SUPABASE_DATABASE_URL` and `apps/api/scripts/validate_hosted_supabase.py`; never repoint the
ordinary local `DATABASE_URL` implicitly.

Status: operator checklist for a non-production development project

## Secrets and environments

Use a newly created development project. Never paste credentials into source files, issue trackers,
shell output, or chat. Keep these values in an ignored local environment file or a secrets manager:

- **SECRET:** database password and complete database connection URL
- **SECRET:** Supabase secret/service-role key
- **SECRET:** legacy `SUPABASE_JWT_SECRET`, if legacy HS256 is retained
- **SECRET:** user access/refresh tokens

The Project URL, publishable/anon key, JWT issuer, audience, and JWKS URL are configuration rather
than credentials. The publishable/anon key is browser-safe but still belongs in environment
configuration, not hard-coded source.

## Project and database

- [ ] Create a new Supabase development project; do not use a production project.
- [ ] Record the Project URL: `https://<project-ref>.supabase.co`.
- [ ] Record the publishable key (or legacy anon key during transition).
- [ ] Record the secret key (or legacy service-role key) in server-only secret storage.
- [ ] Copy the database direct connection string from Dashboard **Connect**. Prefer the direct
      connection for migrations; if this machine cannot reach its IPv6 endpoint, use the documented
      Supavisor session endpoint instead.
- [ ] Put the password-bearing URL in a temporary, unprinted variable:

```bash
export SUPABASE_DEV_DB_URL='postgresql://postgres:<PASSWORD>@db.<PROJECT_REF>.supabase.co:5432/postgres'
```

- [ ] From the repository root, apply migrations in numeric order and stop on the first error:

```bash
for migration in database/migrations/[0-9]*.sql; do
  psql -X "$SUPABASE_DEV_DB_URL" -v ON_ERROR_STOP=1 -f "$migration" || break
done
```

- [ ] Run the read-only verification script and review every section:

```bash
psql -X "$SUPABASE_DEV_DB_URL" -v ON_ERROR_STOP=1 \
  -f scripts/verify_supabase_schema.sql
```

- [ ] Confirm all 26 expected application `public` tables exist, all have RLS enabled, and the expected
      Watchlist and Review policies are present.
- [ ] Remove the temporary secret from the shell after completing database work:

```bash
unset SUPABASE_DEV_DB_URL
```

## Auth signing configuration

- [ ] In Dashboard, inspect Auth JWT Signing Keys; do not assume HS256.
- [ ] For asymmetric signing, configure:
      `SUPABASE_JWKS_URL=https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`.
- [ ] Configure `SUPABASE_JWT_ISSUER=https://<project-ref>.supabase.co/auth/v1` and
      `SUPABASE_JWT_AUDIENCE=authenticated`.
- [ ] Prefer asymmetric JWKS verification. Set the server-only `SUPABASE_JWT_SECRET` only when
      legacy HS256 tokens must remain valid during a deliberate transition.

## Test identities and application profiles

- [ ] Create one normal test user and one admin test user in Supabase Auth.
- [ ] Copy each Auth user's UUID from Dashboard. Do not use their access tokens as IDs.
- [ ] Insert matching profiles through SQL Editor or `psql`; substitute only the two UUIDs:

```sql
INSERT INTO public.user_profiles (auth_user_id, role)
VALUES
    ('<NORMAL_AUTH_USER_UUID>'::uuid, 'user'),
    ('<ADMIN_AUTH_USER_UUID>'::uuid, 'admin')
ON CONFLICT (auth_user_id) DO UPDATE
SET role = EXCLUDED.role, updated_at = now();
```

Manual creation is intentional for this validation stage. There is no automatic Auth-user profile
trigger. Never infer the application role from arbitrary JWT claims.

## Application configuration

- [ ] Configure `apps/web/.env.local` with browser-safe values only:

```dotenv
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<PUBLISHABLE_OR_LEGACY_ANON_KEY>
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

- [ ] Configure `apps/api/.env` using placeholders as a guide. Required for hosted authentication:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:<PASSWORD>@<RUNTIME_DB_HOST>:5432/postgres
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_JWKS_URL=https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_JWT_ISSUER=https://<project-ref>.supabase.co/auth/v1
SUPABASE_JWT_AUDIENCE=authenticated
```

- [ ] Add server-only `SUPABASE_SERVICE_ROLE_KEY` only for a workflow that actually needs it. The
      current API uses direct PostgreSQL and does not require this key for token verification.
- [ ] Restart API and Web after changing environment files.

## Hosted Auth/RLS drill

- [ ] Sign in as the normal user and confirm `/api/v1/auth/me` resolves role `user`.
- [ ] Confirm the normal user can read their own profile and create/read/update/delete only their
      own Watchlist and Watchlist items through a user-scoped Supabase client.
- [ ] Confirm the normal user cannot read or mutate the other user's Watchlist.
- [ ] Confirm the normal user cannot read `comments`, `ai_extractions`, or `review_tasks` through
      Supabase Data API, and cannot update `user_profiles` to escalate role.
- [ ] Confirm the normal user can read only active opportunities/signals and their permitted
      supporting intelligence.
- [ ] Confirm `/admin/review` and admin API endpoints deny the normal user.
- [ ] Sign in as the admin; confirm `/api/v1/auth/me` resolves role `admin` and `/admin/review`
      loads through the FastAPI authorization boundary.
- [ ] Confirm the admin can execute the intended Review workflow. Do not use the service-role key
      to perform these user-token tests because it bypasses RLS.
- [ ] Record pass/fail evidence without recording access tokens or secrets.
