# Supabase Compatibility and Readiness v0.1

Status: **READY TO CREATE/CONNECT SUPABASE** for a development project; hosted drill still required

## Migration readiness

The 12 numeric migrations are ordered, transactional, and compatible with a fresh hosted Supabase
PostgreSQL project based on static review and PostgreSQL 16 integration coverage. Apply them with
the existing `psql` workflow; adopting Supabase CLI is not required for v0.1.

- `0001_initial_schema.sql`: generic PostgreSQL schema plus conditional local compatibility. It
  creates `anon`, `authenticated`, and `service_role` only when absent and creates `auth.uid()` only
  when Supabase has not already supplied it. On hosted Supabase those branches are no-ops; the
  hosted Auth implementation is not replaced.
- `0002_rls_baseline.sql`: Supabase-aware. It relies on existing `auth.uid()` and API roles, enables
  RLS on every application table, revokes broad grants, and defines application policies/helpers.
- `0003` through `0012`: generic PostgreSQL schema evolution. They do not require localhost helper
  objects, Supabase CLI metadata, pgvector, or external extensions beyond `pgcrypto` from `0001`.

The `auth.users` to `public.user_profiles` relationship is intentionally logical, not a cross-schema
foreign key. No local-only object is required at runtime on hosted Supabase. Hosted execution has
not yet occurred, so successful application against the selected project remains an operator gate.

## Auth and profile model

Supabase Auth issues an access token whose `sub` is the Auth user UUID. FastAPI validates the token,
then resolves `sub` through `public.user_profiles.auth_user_id`. The application authorization role
comes only from `user_profiles.role` (`user` or `admin`); JWT `role` or other arbitrary claims do not
grant application admin rights. A valid token without a matching profile receives HTTP 403.

For the first hosted drill, create the normal and admin Auth users in Dashboard, then manually insert
their matching profile rows. Automatic profile triggers remain deliberately deferred.

## JWT signing compatibility

Before TASK-030 the backend accepted only legacy HS256 tokens using `SUPABASE_JWT_SECRET`. That was
a concrete compatibility gap for projects using Supabase's recommended asymmetric signing keys.

The verifier now supports:

- `RS256` and `ES256` through the project's public JWKS endpoint;
- optional legacy `HS256` through the server-only JWT secret;
- exact configured issuer, audience, expiration, signature, and required subject validation.

Unknown signing algorithms and unknown `kid` values fail closed with HTTP 401. Configure
`SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, and `SUPABASE_JWT_AUDIENCE`. During a migration window,
JWKS and the legacy secret may both be configured; algorithm selection is constrained and does not
allow an asymmetric key to be treated as an HMAC secret.

Supabase documents the JWKS discovery endpoint as
`https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`. Its edge and client caching means
signing-key rotation/revocation procedures must allow for cache propagation.

## RLS readiness

RLS is enabled on all 19 application tables. Authenticated users receive narrowly scoped grants:

- own profile is readable; no profile write policy exists, preventing self-role escalation;
- own Watchlists and membership rows are readable and writable;
- active product opportunities/signals and related intelligence are readable;
- Review tasks are restricted by the database-backed admin helper;
- RAW tables such as comments and internal tables such as AI extractions have no authenticated
  policy and are denied;
- `service_role` remains server-only and bypasses RLS by design.

PostgreSQL integration tests exercise these policies locally. A real hosted test with separate user
access tokens is still required because FastAPI tests alone do not prove Supabase gateway behavior.
The read-only inventory and policy checks are in `scripts/verify_supabase_schema.sql`.
That script also confirms the hosted project's API-role table privileges. Supabase is expected to
grant `service_role` table access through its managed defaults; the portable local role created by
`0001` intentionally does not manufacture hosted gateway privileges and local tests use the database
owner for trusted API/worker access.

## Frontend environment readiness

The Next.js Supabase SSR setup reads only:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` (may contain the current publishable key despite the legacy name)
- `NEXT_PUBLIC_API_BASE_URL`

Frontend source does not reference database URLs, service-role keys, JWT secrets, Redis, YouTube, or
OpenAI credentials. The browser obtains a Supabase session and sends its access token to FastAPI;
frontend admin route handling is UX only, while FastAPI and RLS remain authoritative.

## Backend environment readiness

Supported Supabase/auth-related backend settings are:

- `DATABASE_URL` — secret PostgreSQL runtime URL used by API/workers;
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` — accepted settings, currently
  reserved and not used by FastAPI token verification;
- `SUPABASE_JWKS_URL` — public JWKS discovery URL for asymmetric verification;
- `SUPABASE_JWT_SECRET` — optional, secret legacy HS256 verification key;
- `SUPABASE_JWT_ISSUER` — expected token issuer;
- `SUPABASE_JWT_AUDIENCE` — expected audience, default `authenticated`.

The repository does not support differently named `SUPABASE_ISSUER` or `SUPABASE_AUDIENCE`
variables. `SUPABASE_JWT_ISSUER` should be configured for hosted use rather than omitted.

## Secrets handling

Never commit or print the database password/full URL, secret/service-role key, legacy JWT secret,
private signing key, or access/refresh token. JWKS contains public verification keys and is safe to
fetch, but no fetched payload is committed. Browser code receives only Project URL and a
publishable/anon API key.

## Known gaps

- The 12 migrations and RLS policies have not yet been executed against the selected hosted project.
- Real Supabase Auth tokens and JWKS rotation behavior have not yet been exercised end-to-end.
- The hosted RLS drill, including cross-user Watchlist denial, remains an explicit gate.
- Runtime connection mode depends on deployment networking: direct connection is preferred for
  migrations/long-lived IPv6-capable services; Supavisor session mode is the IPv4 fallback.
- No profile-creation trigger, account lifecycle automation, secret manager integration, backup
  rehearsal, or production deployment is included in this task.

## Exact next operator actions

1. Follow `docs/supabase-setup-checklist.md` to create a development project and record configuration.
2. Apply all numeric migrations with the temporary `SUPABASE_DEV_DB_URL` variable.
3. Run `scripts/verify_supabase_schema.sql` and retain a secret-free result summary.
4. Inspect the Dashboard signing-key method and configure JWKS/issuer/audience accordingly.
5. Create normal/admin Auth users and matching manual `user_profiles` rows.
6. Configure ignored Web/API environment files and restart both services.
7. Execute every normal-user/admin hosted RLS drill item before staging deployment.

## References

- [Supabase JWT signing keys](https://supabase.com/docs/guides/auth/signing-keys)
- [Supabase JWT verification](https://supabase.com/docs/guides/auth/jwts)
- [Supabase database connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
