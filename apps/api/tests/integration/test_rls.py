from uuid import uuid4

import asyncpg
import pytest


@pytest.mark.asyncio
async def test_rls_user_ownership_visibility_and_admin_boundary(rls_postgres_url: str) -> None:
    connection = await asyncpg.connect(rls_postgres_url)
    user_auth_id, other_auth_id, admin_auth_id = uuid4(), uuid4(), uuid4()
    try:
        user_profile_id = await connection.fetchval(
            "INSERT INTO user_profiles (auth_user_id, role) VALUES ($1, 'user') RETURNING id",
            user_auth_id,
        )
        other_profile_id = await connection.fetchval(
            "INSERT INTO user_profiles (auth_user_id, role) VALUES ($1, 'user') RETURNING id",
            other_auth_id,
        )
        await connection.execute(
            "INSERT INTO user_profiles (auth_user_id, role) VALUES ($1, 'admin')", admin_auth_id
        )
        own_watchlist_id = await connection.fetchval(
            "INSERT INTO watchlists (user_profile_id, name) VALUES ($1, 'Own') RETURNING id",
            user_profile_id,
        )
        await connection.execute(
            "INSERT INTO watchlists (user_profile_id, name) VALUES ($1, 'Other')", other_profile_id
        )
        other_watchlist_id = await connection.fetchval(
            "SELECT id FROM watchlists WHERE user_profile_id = $1", other_profile_id
        )
        active_id = await connection.fetchval(
            """INSERT INTO opportunities
               (slug, name, market_stage, status, first_detected_at, last_activity_at)
               VALUES ('active', 'Active', 'emerging', 'active', NOW(), NOW()) RETURNING id"""
        )
        candidate_id = await connection.fetchval(
            """INSERT INTO opportunities
               (slug, name, market_stage, status, first_detected_at, last_activity_at)
               VALUES ('candidate', 'Candidate', 'emerging', 'candidate', NOW(), NOW())
               RETURNING id"""
        )
        await connection.executemany(
            """INSERT INTO intelligence_localizations
               (entity_type, entity_id, field_name, locale, translated_text,
                source_text_hash, translation_version, status)
               VALUES ('opportunity', $1, 'name', 'zh-CN', $2, $3, 'test-v1', 'current')""",
            [(active_id, "已发布", "active-hash"), (candidate_id, "候选", "candidate-hash")],
        )
        await connection.execute(
            """INSERT INTO review_tasks
               (review_type, target_type, target_id, status, priority)
               VALUES ('quality_review', 'opportunity', $1, 'pending', 1)""",
            active_id,
        )
        await connection.execute(
            "INSERT INTO watchlist_items (watchlist_id, opportunity_id) VALUES ($1, $2)",
            own_watchlist_id,
            active_id,
        )
        await connection.execute(
            "INSERT INTO watchlist_items (watchlist_id, opportunity_id) VALUES ($1, $2)",
            other_watchlist_id,
            active_id,
        )
        assert (
            await connection.fetchval(
                "SELECT count(*) FROM pg_class WHERE relkind = 'r' AND relrowsecurity"
            )
                == 32
        )

        await connection.execute("SET ROLE authenticated")
        await connection.execute(
            "SELECT set_config('request.jwt.claim.sub', $1, false)", str(user_auth_id)
        )
        assert await connection.fetchval("SELECT count(*) FROM user_profiles") == 1
        assert await connection.fetchval("SELECT count(*) FROM watchlists") == 1
        assert await connection.fetchval("SELECT count(*) FROM watchlist_items") == 1
        assert await connection.fetchval("SELECT count(*) FROM opportunities") == 1
        assert await connection.fetchval("SELECT count(*) FROM intelligence_localizations") == 1
        assert await connection.fetchval("SELECT count(*) FROM review_tasks") == 0
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await connection.fetchval("SELECT count(*) FROM channels")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await connection.fetchval("SELECT count(*) FROM youtube_discovery_items")
        with pytest.raises(asyncpg.PostgresError):
            await connection.execute(
                "INSERT INTO watchlists (user_profile_id, name) VALUES ($1, 'Forbidden')",
                other_profile_id,
            )
        with pytest.raises(asyncpg.PostgresError):
            await connection.execute(
                "INSERT INTO watchlist_items (watchlist_id, opportunity_id) VALUES ($1, $2)",
                other_watchlist_id,
                active_id,
            )
        with pytest.raises(asyncpg.PostgresError):
            await connection.execute(
                "UPDATE user_profiles SET role = 'admin' WHERE id = $1", user_profile_id
            )

        await connection.execute("RESET ROLE")
        await connection.execute("SET ROLE authenticated")
        await connection.execute(
            "SELECT set_config('request.jwt.claim.sub', $1, false)", str(admin_auth_id)
        )
        assert (
            await connection.fetchval(
                "SELECT count(*) FROM review_tasks WHERE target_id = $1", active_id
            )
            == 1
        )
        assert (
            await connection.fetchval(
                "SELECT count(*) FROM opportunities WHERE slug IN ('active', 'candidate')"
            )
            == 2
        )
        assert await connection.fetchval("SELECT count(*) FROM intelligence_localizations") == 2
        assert own_watchlist_id is not None
    finally:
        await connection.close()
