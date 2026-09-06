-- Read-only hosted Supabase schema and RLS verification for AI Business Radar v0.1.
-- Run with: psql -X "$SUPABASE_DEV_DB_URL" -v ON_ERROR_STOP=1 \
--             -f scripts/verify_supabase_schema.sql
-- This script performs SELECTs only and must not be used as a migration.

\echo 'A. Public application tables (expected: 19)'
SELECT tablename
FROM pg_catalog.pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

\echo 'B. Expected-table comparison (both result sets should be empty)'
WITH expected(name) AS (
    VALUES
        ('ai_extractions'), ('channels'), ('collection_runs'), ('comments'),
        ('opportunities'), ('opportunity_evidence'), ('opportunity_merge_history'),
        ('opportunity_scores'), ('opportunity_signal_links'), ('review_tasks'),
        ('search_queries'), ('signals'), ('trend_snapshots'), ('user_profiles'),
        ('video_snapshots'), ('videos'), ('watchlist_items'), ('watchlists'),
        ('youtube_discovery_items')
), actual(name) AS (
    SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'
)
SELECT 'missing' AS finding, name FROM expected EXCEPT SELECT 'missing', name FROM actual;

WITH expected(name) AS (
    VALUES
        ('ai_extractions'), ('channels'), ('collection_runs'), ('comments'),
        ('opportunities'), ('opportunity_evidence'), ('opportunity_merge_history'),
        ('opportunity_scores'), ('opportunity_signal_links'), ('review_tasks'),
        ('search_queries'), ('signals'), ('trend_snapshots'), ('user_profiles'),
        ('video_snapshots'), ('videos'), ('watchlist_items'), ('watchlists'),
        ('youtube_discovery_items')
), actual(name) AS (
    SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'
)
SELECT 'unexpected' AS finding, name FROM actual EXCEPT SELECT 'unexpected', name FROM expected;

\echo 'C. RLS status (rowsecurity should be true for every expected table)'
SELECT c.relname AS table_name, c.relrowsecurity AS rowsecurity,
       c.relforcerowsecurity AS force_rowsecurity
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relname;

\echo 'D. RLS policies'
SELECT schemaname, tablename, policyname, roles, cmd, qual, with_check
FROM pg_catalog.pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

\echo 'E. user_profiles role constraint (must allow only user/admin)'
SELECT conname, pg_catalog.pg_get_constraintdef(oid) AS definition
FROM pg_catalog.pg_constraint
WHERE conrelid = 'public.user_profiles'::regclass
  AND conname IN ('ck_user_profiles_role', 'uq_user_profiles_auth_user_id')
ORDER BY conname;

\echo 'F. Watchlist ownership policies (expected: four per table)'
SELECT tablename, policyname, cmd, qual, with_check
FROM pg_catalog.pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('watchlists', 'watchlist_items')
ORDER BY tablename, policyname;

\echo 'G. Review-task admin policy (expected: review_tasks_admin_all)'
SELECT tablename, policyname, roles, cmd, qual, with_check
FROM pg_catalog.pg_policies
WHERE schemaname = 'public' AND tablename = 'review_tasks'
ORDER BY policyname;

\echo 'H. Supabase identity helpers and grants'
SELECT n.nspname AS schema_name, p.proname AS function_name,
       pg_catalog.pg_get_function_identity_arguments(p.oid) AS arguments
FROM pg_catalog.pg_proc AS p
JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
WHERE (n.nspname = 'auth' AND p.proname = 'uid')
   OR (n.nspname = 'public' AND p.proname IN (
       'current_user_profile_id', 'current_user_is_admin',
       'current_user_owns_watchlist'
   ))
ORDER BY schema_name, function_name;

\echo 'I. API-role table privileges (service_role should be true; anon should be false)'
SELECT c.relname AS table_name,
       has_table_privilege('service_role', c.oid, 'SELECT') AS service_role_select,
       has_table_privilege('authenticated', c.oid, 'SELECT') AS authenticated_select,
       has_table_privilege('anon', c.oid, 'SELECT') AS anon_select
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relname;
