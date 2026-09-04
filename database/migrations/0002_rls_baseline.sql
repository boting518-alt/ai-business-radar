-- Supabase Auth and RLS baseline. Requires Supabase-provided auth.uid() and roles.
BEGIN;

CREATE OR REPLACE FUNCTION public.current_user_profile_id()
RETURNS UUID
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT id FROM public.user_profiles WHERE auth_user_id = auth.uid()
$$;

CREATE OR REPLACE FUNCTION public.current_user_is_admin()
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT COALESCE(
        (SELECT role = 'admin' FROM public.user_profiles WHERE auth_user_id = auth.uid()),
        FALSE
    )
$$;

CREATE OR REPLACE FUNCTION public.current_user_owns_watchlist(target_watchlist_id UUID)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.watchlists
        WHERE id = target_watchlist_id
          AND user_profile_id = public.current_user_profile_id()
    )
$$;

REVOKE ALL ON FUNCTION public.current_user_profile_id() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.current_user_is_admin() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.current_user_owns_watchlist(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_user_profile_id() TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.current_user_is_admin() TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.current_user_owns_watchlist(UUID) TO authenticated, service_role;

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE collection_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE opportunity_signal_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE opportunity_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE trend_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE opportunity_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE opportunity_merge_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist_items ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON user_profiles, search_queries, collection_runs, channels, videos,
    video_snapshots, comments, ai_extractions, signals, opportunities,
    opportunity_signal_links, opportunity_evidence, trend_snapshots,
    opportunity_scores, review_tasks, opportunity_merge_history, watchlists,
    watchlist_items FROM anon, authenticated;

GRANT SELECT ON user_profiles TO authenticated;
CREATE POLICY user_profiles_select_self_or_admin ON user_profiles
FOR SELECT TO authenticated
USING (auth_user_id = auth.uid() OR public.current_user_is_admin());

GRANT SELECT, INSERT, UPDATE, DELETE ON watchlists, watchlist_items TO authenticated;
CREATE POLICY watchlists_select_own ON watchlists
FOR SELECT TO authenticated
USING (user_profile_id = public.current_user_profile_id());
CREATE POLICY watchlists_insert_own ON watchlists
FOR INSERT TO authenticated
WITH CHECK (user_profile_id = public.current_user_profile_id());
CREATE POLICY watchlists_update_own ON watchlists
FOR UPDATE TO authenticated
USING (user_profile_id = public.current_user_profile_id())
WITH CHECK (user_profile_id = public.current_user_profile_id());
CREATE POLICY watchlists_delete_own ON watchlists
FOR DELETE TO authenticated
USING (user_profile_id = public.current_user_profile_id());

CREATE POLICY watchlist_items_select_own ON watchlist_items
FOR SELECT TO authenticated
USING (public.current_user_owns_watchlist(watchlist_id));
CREATE POLICY watchlist_items_insert_own ON watchlist_items
FOR INSERT TO authenticated
WITH CHECK (public.current_user_owns_watchlist(watchlist_id));
CREATE POLICY watchlist_items_update_own ON watchlist_items
FOR UPDATE TO authenticated
USING (public.current_user_owns_watchlist(watchlist_id))
WITH CHECK (public.current_user_owns_watchlist(watchlist_id));
CREATE POLICY watchlist_items_delete_own ON watchlist_items
FOR DELETE TO authenticated
USING (public.current_user_owns_watchlist(watchlist_id));

GRANT SELECT ON opportunities, opportunity_signal_links, opportunity_evidence,
    trend_snapshots, opportunity_scores, signals TO authenticated;
CREATE POLICY opportunities_read_visible ON opportunities
FOR SELECT TO authenticated
USING (status = 'active' OR public.current_user_is_admin());
CREATE POLICY signals_read_visible ON signals
FOR SELECT TO authenticated
USING (status = 'active' OR public.current_user_is_admin());
CREATE POLICY opportunity_signal_links_read_visible ON opportunity_signal_links
FOR SELECT TO authenticated
USING (EXISTS (
    SELECT 1 FROM opportunities
    WHERE opportunities.id = opportunity_signal_links.opportunity_id
      AND (opportunities.status = 'active' OR public.current_user_is_admin())
));
CREATE POLICY opportunity_evidence_read_visible ON opportunity_evidence
FOR SELECT TO authenticated
USING (EXISTS (
    SELECT 1 FROM opportunities
    WHERE opportunities.id = opportunity_evidence.opportunity_id
      AND (opportunities.status = 'active' OR public.current_user_is_admin())
));
CREATE POLICY trend_snapshots_read_visible ON trend_snapshots
FOR SELECT TO authenticated
USING (EXISTS (
    SELECT 1 FROM opportunities
    WHERE opportunities.id = trend_snapshots.opportunity_id
      AND (opportunities.status = 'active' OR public.current_user_is_admin())
));
CREATE POLICY opportunity_scores_read_visible ON opportunity_scores
FOR SELECT TO authenticated
USING (EXISTS (
    SELECT 1 FROM opportunities
    WHERE opportunities.id = opportunity_scores.opportunity_id
      AND (opportunities.status = 'active' OR public.current_user_is_admin())
));

GRANT SELECT, INSERT, UPDATE, DELETE ON review_tasks TO authenticated;
CREATE POLICY review_tasks_admin_all ON review_tasks
FOR ALL TO authenticated
USING (public.current_user_is_admin())
WITH CHECK (public.current_user_is_admin());

COMMIT;
