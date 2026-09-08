BEGIN;
CREATE TABLE discovery_topic_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID NOT NULL REFERENCES discovery_topics(id),
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('manual','scheduled')),
    status TEXT NOT NULL CHECK (status IN ('queued','running','completed','partial','failed')),
    requested_query_count INTEGER NOT NULL CHECK (requested_query_count >= 0),
    queued_query_count INTEGER NOT NULL DEFAULT 0 CHECK (queued_query_count >= 0),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (queued_query_count <= requested_query_count),
    CHECK ((status IN ('queued','running') AND completed_at IS NULL) OR
           (status IN ('completed','partial','failed') AND completed_at IS NOT NULL))
);
ALTER TABLE collection_runs ADD COLUMN topic_run_id UUID REFERENCES discovery_topic_runs(id);
CREATE INDEX idx_discovery_topic_runs_topic_created ON discovery_topic_runs(topic_id,created_at DESC);
CREATE UNIQUE INDEX uq_discovery_topic_active_batch ON discovery_topic_runs(topic_id) WHERE status IN ('queued','running');
CREATE INDEX idx_collection_runs_topic_run ON collection_runs(topic_run_id,created_at) WHERE topic_run_id IS NOT NULL;
ALTER TABLE discovery_topic_runs ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE ON discovery_topic_runs TO authenticated;
CREATE POLICY discovery_topic_runs_admin ON discovery_topic_runs FOR ALL TO authenticated
USING (public.current_user_is_admin()) WITH CHECK (public.current_user_is_admin());
COMMIT;
