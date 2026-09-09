BEGIN;
CREATE TABLE opportunity_revisions (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE RESTRICT,
 changed_by UUID NOT NULL REFERENCES user_profiles(id),
 changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 field TEXT NOT NULL,
 old_value JSONB,
 new_value JSONB,
 note TEXT
);
CREATE INDEX idx_opportunity_revisions_history ON opportunity_revisions(opportunity_id, changed_at DESC);
CREATE TABLE activation_review_events (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 review_task_id UUID NOT NULL REFERENCES review_tasks(id) ON DELETE RESTRICT,
 opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE RESTRICT,
 actor_id UUID REFERENCES user_profiles(id),
 event_type TEXT NOT NULL CHECK(event_type IN ('submitted','claimed','deferred','published','invalid')),
 previous_status TEXT,
 status TEXT NOT NULL,
 notes TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_activation_events_history ON activation_review_events(opportunity_id, created_at DESC);
ALTER TABLE opportunity_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE activation_review_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON opportunity_revisions, activation_review_events FROM anon, authenticated;
GRANT SELECT ON opportunity_revisions, activation_review_events TO authenticated;
CREATE POLICY opportunity_revisions_admin ON opportunity_revisions FOR SELECT TO authenticated
 USING(public.current_user_is_admin());
CREATE POLICY activation_events_admin ON activation_review_events FOR SELECT TO authenticated
 USING(public.current_user_is_admin());
COMMIT;
