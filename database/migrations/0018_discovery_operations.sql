BEGIN;

CREATE TABLE discovery_topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 160),
    description TEXT,
    status TEXT NOT NULL DEFAULT 'paused' CHECK (status IN ('active','paused','archived')),
    default_schedule TEXT NOT NULL DEFAULT 'manual' CHECK (default_schedule IN ('manual','6h','12h','daily','weekly')),
    default_max_videos INTEGER NOT NULL DEFAULT 25 CHECK (default_max_videos BETWEEN 1 AND 100),
    default_max_pages INTEGER NOT NULL DEFAULT 1 CHECK (default_max_pages BETWEEN 1 AND 5),
    default_max_comments_per_video INTEGER NOT NULL DEFAULT 20 CHECK (default_max_comments_per_video BETWEEN 0 AND 100),
    created_by UUID REFERENCES user_profiles(id),
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE search_queries ADD COLUMN topic_id UUID REFERENCES discovery_topics(id);
ALTER TABLE search_queries ADD COLUMN max_videos INTEGER CHECK (max_videos BETWEEN 1 AND 100);
ALTER TABLE search_queries ADD COLUMN max_pages INTEGER CHECK (max_pages BETWEEN 1 AND 5);
ALTER TABLE search_queries ADD COLUMN max_comments_per_video INTEGER CHECK (max_comments_per_video BETWEEN 0 AND 100);
ALTER TABLE search_queries ADD COLUMN schedule_override TEXT CHECK (schedule_override IS NULL OR schedule_override IN ('manual','6h','12h','daily','weekly'));
CREATE UNIQUE INDEX uq_discovery_topic_query ON search_queries(topic_id, lower(btrim(query))) WHERE topic_id IS NOT NULL;
CREATE INDEX idx_discovery_topics_due ON discovery_topics(next_run_at) WHERE status='active' AND default_schedule<>'manual';

ALTER TABLE collection_runs ADD COLUMN discovery_topic_id UUID REFERENCES discovery_topics(id);
ALTER TABLE collection_runs ADD COLUMN trigger_type TEXT CHECK (trigger_type IS NULL OR trigger_type IN ('manual','scheduled'));
ALTER TABLE collection_runs ADD COLUMN worker_message_id TEXT;
CREATE INDEX idx_collection_runs_discovery_console ON collection_runs(discovery_topic_id, created_at DESC) WHERE run_type='discovery';
CREATE UNIQUE INDEX uq_discovery_query_inflight ON collection_runs(search_query_id) WHERE run_type='discovery' AND status IN ('pending','running');

ALTER TABLE discovery_topics ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE ON discovery_topics TO authenticated;
CREATE POLICY discovery_topics_admin ON discovery_topics FOR ALL TO authenticated
USING (public.current_user_is_admin()) WITH CHECK (public.current_user_is_admin());

COMMIT;
