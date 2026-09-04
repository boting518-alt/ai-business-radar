# ADR-003: Authentication v0.1

Status: Accepted
Date: 2026-09-04

## Context

v0.1 supports individual analysts and administrative reviewers but explicitly excludes team accounts and collaboration. Authentication and authorization should match that scope without creating a general permission system.

## Decision

- Use Supabase Auth for authenticated individual users.
- Define two application roles: `user` and `admin`.
- Permit `user` access to radar, opportunities, signals, and that user’s watchlist.
- Permit `admin` all `user` capabilities plus `/admin/review` and administrative review actions.
- Enforce API authorization in FastAPI; browser route guards are not authoritative.
- Do not introduce organizations, teams, invitations, enterprise RBAC, or arbitrary permissions in v0.1.

## Consequences

- Authentication integrates with the chosen database platform.
- Authorization remains small enough to audit and test.
- User-owned watchlists have an authenticated owner without implying multi-tenancy.
- A future team model will require an explicit product and data-model decision rather than an incidental extension of these roles.

## Revisit when

The frozen product scope adds organizations, team collaboration, delegated administration, or other requirements that cannot be represented by the two roles.
