# Hosted Supabase Validation Report

- Project ref: `uhjj…upfm`
- Connection: direct PostgreSQL; asyncpg/psql successful
- Configuration: project URL, publishable key, server secret, JWKS, issuer, audience, hosted DB URL configured
- JWKS/Auth: real hosted tokens accepted; user/admin `/auth/me` 200; missing profile 403
- Authorization: user admin diagnostics 403; admin diagnostics 200
- Schema: all 26 application tables from migrations 0001–0017 present
- Schema verifier: passed; hosted RLS enabled on all 26 application tables
- RLS: user saw own Watchlist (1), not admin Watchlist (0); admin also did not bypass owner policy
- Product visibility: active Opportunity/localization visible; candidate equivalents invisible
- Taxonomy: authenticated reference read passed; ordinary taxonomy mutation denied
- Localization: ordinary mutation denied; original/canonical projection semantics unchanged
- Profile security: ordinary role escalation denied
- CORS: localhost:3000 preflight 200 with exact allow-origin
- Service role: used only to create/delete dedicated Auth drill identities
- Security scan: tracked secret values false; frontend bundle secret values false
- Cleanup: 2 localizations, 2 taxonomy mappings, 2 Watchlists, 2 Opportunities, 2 profiles,
  and 3 dedicated Auth identities deleted by exact recorded UUID

## RLS matrix

| Surface | Authenticated read | Owner scoped | Admin-only mutation | Service-role bypass expected |
| --- | --- | --- | --- | --- |
| Watchlists/items | own rows | yes | no application-admin bypass | yes, system work only |
| Active Opportunities | yes | no | lifecycle writes remain backend/admin | yes |
| Candidate/rejected Opportunities | no product exposure | no | review context only | yes |
| Taxonomy references | yes | no | yes | yes |
| Taxonomy mappings | visible only with visible parent | no | yes | yes |
| Intelligence localizations | visible only with active parent | no | yes | yes |
| User profiles | own profile | yes | role mutation denied | yes |

## HTTP failure matrix

| Case | Observed/expected |
| --- | --- |
| No or invalid Authorization | 401 |
| Expired/wrong issuer/wrong audience/unknown key | 401 by verifier tests |
| Valid hosted token, missing profile | 403 observed |
| User on admin runtime endpoint | 403 observed |
| Admin on admin runtime endpoint | 200 observed |
| Database unavailable | 503 where the route requires the database |
| RLS-hidden read | safe empty result observed |

## Known gaps

- Email/password login, refresh, logout, browser reload, and SSR cookie plumbing were inspected and
  covered by frontend tests/build, but this CLI drill did not automate a real browser.
- The repository PostgreSQL integration suite needs `POSTGRES_TEST_ADMIN_URL`; local PostgreSQL was
  unavailable during the final regression run, so 68 integration cases were skipped. Hosted schema
  verification and direct hosted RLS probes passed independently.
- This is a development-project drill, not staging or production readiness.

Dedicated users: `abr-hosted-drill-user-d26bbee9a6@example.com` (`f311fac6-1e38-40e6-8de6-e1104a3533ec`),
`abr-hosted-drill-admin-f3ec3fc996@example.com` (`afdea073-e2b5-464f-b30d-bcd9ddb58bb6`), and an
unprofiled denial identity `2cd38127-0c2c-431a-92ae-1977eafc01fa`. No password or token is recorded.

No local database was overwritten, no local business data was copied, and staging was not started.
