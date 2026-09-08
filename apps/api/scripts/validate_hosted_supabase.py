#!/usr/bin/env python3
"""Bounded hosted Supabase validation without printing credentials or tokens."""

import argparse
import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import asyncpg
import httpx

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.supabase import SupabaseJWTVerifier

ROOT = Path(__file__).parents[3]


def tables() -> list[str]:
    sql = "\n".join(
        path.read_text() for path in sorted((ROOT / "database/migrations").glob("[0-9]*.sql"))
    )
    return sorted(set(re.findall(r"^CREATE TABLE (\w+)", sql, re.MULTILINE)))


def database_url(settings: Settings) -> str:
    if settings.hosted_supabase_database_url is None:
        raise RuntimeError("HOSTED_SUPABASE_DATABASE_URL is missing")
    value = settings.hosted_supabase_database_url.get_secret_value().replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )
    if (urlparse(value).hostname or "") in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Hosted URL must not target localhost")
    return value


async def preflight(settings: Settings) -> dict:
    expected = tables()
    result = {
        "config": {
            name: "configured" if getattr(settings, name) else "missing"
            for name in (
                "supabase_url",
                "supabase_anon_key",
                "supabase_service_role_key",
                "supabase_jwks_url",
                "supabase_jwt_issuer",
                "supabase_jwt_audience",
                "hosted_supabase_database_url",
            )
        }
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(settings.supabase_jwks_url or "")
        keys = response.json().get("keys", []) if response.is_success else []
        result["jwks"] = {
            "reachable": response.is_success,
            "key_count": len(keys),
            "algorithms": sorted({key.get("alg") for key in keys if key.get("alg")}),
        }
    connection = await asyncpg.connect(database_url(settings), timeout=15)
    try:
        present = await connection.fetchval(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=ANY($1::text[])",
            expected,
        )
        rls = await connection.fetchval(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname=ANY($1::text[]) AND c.relrowsecurity",
            expected,
        )
        result["schema"] = {"expected": len(expected), "present": present, "rls_enabled": rls}
        host = urlparse(database_url(settings)).hostname or ""
        result["connection_mode"] = "direct" if host.startswith("db.") else "pooler"
    finally:
        await connection.close()
    return result


async def auth(settings: Settings) -> dict:
    verifier = SupabaseJWTVerifier(
        None,
        jwks_url=settings.supabase_jwks_url,
        issuer=settings.supabase_jwt_issuer,
        audience=settings.supabase_jwt_audience,
    )
    output = {}
    for role, variable in (
        ("user", "SUPABASE_TEST_USER_ACCESS_TOKEN"),
        ("admin", "SUPABASE_TEST_ADMIN_ACCESS_TOKEN"),
    ):
        token = os.getenv(variable)
        if not token:
            output[role] = "token_missing"
            continue
        identity = verifier.verify(token)
        connection = await asyncpg.connect(database_url(settings), timeout=15)
        try:
            profile_role = await connection.fetchval(
                "SELECT role FROM user_profiles WHERE auth_user_id=$1", identity.auth_user_id
            )
        finally:
            await connection.close()
        output[role] = "verified" if profile_role == role else "profile_role_mismatch"
    return output


def load_state(path: Path | None) -> dict[str, Any]:
    if path is None:
        raise RuntimeError("A drill state file is required for this command")
    state = json.loads(path.read_text())
    marker = state.get("marker", "")
    if not marker.startswith("abr-hosted-drill-"):
        raise RuntimeError("Refusing state without the hosted drill marker")
    return state


def drill_users(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {user["role"]: user for user in state.get("users", [])}


async def _as_authenticated(connection: asyncpg.Connection, auth_user_id: str) -> None:
    await connection.execute("SET LOCAL ROLE authenticated")
    await connection.execute(
        "SELECT set_config('request.jwt.claim.sub', $1, true)", str(UUID(auth_user_id))
    )


async def rls(settings: Settings, state: dict[str, Any]) -> dict:
    users = drill_users(state)
    user_id = users["user"]["auth_user_id"]
    admin_id = users["admin"]["auth_user_id"]
    connection = await asyncpg.connect(database_url(settings), timeout=15)
    try:
        async with connection.transaction():
            await _as_authenticated(connection, user_id)
            own_watchlist = await connection.fetchval(
                "SELECT count(*) FROM watchlists WHERE id=$1", UUID(state["user_watchlist_id"])
            )
            other_watchlist = await connection.fetchval(
                "SELECT count(*) FROM watchlists WHERE id=$1", UUID(state["admin_watchlist_id"])
            )
            active_opportunity = await connection.fetchval(
                "SELECT count(*) FROM opportunities WHERE id=$1",
                UUID(state["active_opportunity_id"]),
            )
            candidate_opportunity = await connection.fetchval(
                "SELECT count(*) FROM opportunities WHERE id=$1",
                UUID(state["candidate_opportunity_id"]),
            )
            active_localization = await connection.fetchval(
                "SELECT count(*) FROM intelligence_localizations "
                "WHERE entity_type='opportunity' AND entity_id=$1",
                UUID(state["active_opportunity_id"]),
            )
            candidate_localization = await connection.fetchval(
                "SELECT count(*) FROM intelligence_localizations "
                "WHERE entity_type='opportunity' AND entity_id=$1",
                UUID(state["candidate_opportunity_id"]),
            )
            taxonomy_nodes = await connection.fetchval(
                "SELECT count(*) FROM industry_taxonomy_nodes"
            )

        async with connection.transaction():
            await _as_authenticated(connection, admin_id)
            admin_sees_user_watchlist = await connection.fetchval(
                "SELECT count(*) FROM watchlists WHERE id=$1", UUID(state["user_watchlist_id"])
            )

        mutation_denials: dict[str, bool] = {}
        mutations = {
            "other_watchlist": (
                "UPDATE watchlists SET name=name WHERE id=$1",
                UUID(state["admin_watchlist_id"]),
            ),
            "profile_role": (
                "UPDATE user_profiles SET role='admin' WHERE auth_user_id=$1",
                UUID(user_id),
            ),
            "taxonomy": (
                "UPDATE industry_taxonomy_nodes SET canonical_name=canonical_name "
                "WHERE code='technology.ai'",
            ),
            "localization": (
                "UPDATE intelligence_localizations SET translated_text=translated_text "
                "WHERE entity_id=$1",
                UUID(state["active_opportunity_id"]),
            ),
        }
        for name, statement in mutations.items():
            transaction = connection.transaction()
            await transaction.start()
            try:
                await _as_authenticated(connection, user_id)
                status = await connection.execute(statement[0], *statement[1:])
                mutation_denials[name] = status.endswith(" 0")
            except asyncpg.PostgresError:
                mutation_denials[name] = True
            finally:
                await transaction.rollback()

        return {
            "user_own_watchlist": own_watchlist == 1,
            "user_other_watchlist_hidden": other_watchlist == 0,
            "admin_owner_policy_not_bypassed": admin_sees_user_watchlist == 0,
            "active_opportunity_visible": active_opportunity == 1,
            "candidate_opportunity_hidden": candidate_opportunity == 0,
            "taxonomy_readable": taxonomy_nodes > 0,
            "active_localization_visible": active_localization > 0,
            "candidate_localization_hidden": candidate_localization == 0,
            "mutation_denials": mutation_denials,
        }
    finally:
        await connection.close()


async def cleanup(settings: Settings, state: dict[str, Any], delete_auth_users: bool) -> dict:
    opportunity_ids = [
        UUID(state["active_opportunity_id"]),
        UUID(state["candidate_opportunity_id"]),
    ]
    watchlist_ids = [UUID(state["user_watchlist_id"]), UUID(state["admin_watchlist_id"])]
    auth_ids = [UUID(user["auth_user_id"]) for user in state.get("users", [])]
    auth_ids.append(UUID(state["missing_profile_user"]["auth_user_id"]))
    connection = await asyncpg.connect(database_url(settings), timeout=15)
    try:
        async with connection.transaction():
            counts = {}
            for table, column, values in (
                ("intelligence_localizations", "entity_id", opportunity_ids),
                ("opportunity_taxonomy_mappings", "opportunity_id", opportunity_ids),
                ("watchlists", "id", watchlist_ids),
                ("opportunities", "id", opportunity_ids),
                ("user_profiles", "auth_user_id", auth_ids),
            ):
                status = await connection.execute(
                    f"DELETE FROM {table} WHERE {column}=ANY($1::uuid[])", values
                )
                counts[table] = int(status.rsplit(" ", 1)[-1])
    finally:
        await connection.close()

    deleted_auth_users = 0
    if delete_auth_users:
        service_key = settings.supabase_service_role_key
        if service_key is None or not settings.supabase_url:
            raise RuntimeError("Server secret and Supabase URL are required for Auth cleanup")
        secret = service_key.get_secret_value()
        async with httpx.AsyncClient(timeout=15) as client:
            for auth_id in auth_ids:
                response = await client.delete(
                    f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{auth_id}",
                    headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
                )
                if response.status_code not in {200, 404}:
                    raise RuntimeError("Hosted Auth cleanup failed")
                deleted_auth_users += response.status_code == 200
    return {"database_rows": counts, "auth_users": deleted_auth_users}


async def run(command: str, dry_run: bool, state_path: Path | None) -> dict:
    settings = Settings()
    report = await preflight(settings)
    report.update(command=command, dry_run=dry_run)
    if command in {"auth", "full"} and not dry_run:
        if state_path:
            state = load_state(state_path)
            for user in state.get("users", []):
                os.environ.setdefault(
                    f"SUPABASE_TEST_{user['role'].upper()}_ACCESS_TOKEN", user["access_token"]
                )
        report["auth"] = await auth(settings)
    if command in {"rls", "full"}:
        report["rls"] = (
            {"planned": "real auth.uid() visibility and denied-mutation probes"}
            if dry_run
            else await rls(settings, load_state(state_path))
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "auth", "rls", "full"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cleanup-test-data", action="store_true")
    parser.add_argument("--delete-auth-users", action="store_true")
    parser.add_argument("--state-file", type=Path)
    args = parser.parse_args()
    if args.cleanup_test_data:
        try:
            result = asyncio.run(
                cleanup(Settings(), load_state(args.state_file), args.delete_auth_users)
            )
            print(json.dumps({"cleanup": result}, indent=2))
            return 0
        except Exception as error:
            print(json.dumps({"status": "failed", "error": type(error).__name__}))
            return 1
    try:
        print(json.dumps(asyncio.run(run(args.command, args.dry_run, args.state_file)), indent=2))
        return 0
    except Exception as error:
        print(json.dumps({"status": "failed", "error": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
