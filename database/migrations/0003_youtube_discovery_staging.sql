-- Internal RAW staging for bounded YouTube discovery results.
BEGIN;

CREATE TABLE youtube_discovery_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_run_id UUID NOT NULL,
    search_query_id UUID NOT NULL,
    youtube_video_id VARCHAR NOT NULL,
    youtube_channel_id VARCHAR NOT NULL,
    title TEXT NULL,
    description TEXT NULL,
    published_at TIMESTAMPTZ NULL,
    channel_title TEXT NULL,
    thumbnail_url TEXT NULL,
    discovered_at TIMESTAMPTZ NOT NULL,
    processing_status VARCHAR NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_youtube_discovery_items_collection_run_id
        FOREIGN KEY (collection_run_id) REFERENCES collection_runs (id) ON DELETE RESTRICT,
    CONSTRAINT fk_youtube_discovery_items_search_query_id
        FOREIGN KEY (search_query_id) REFERENCES search_queries (id) ON DELETE RESTRICT,
    CONSTRAINT uq_youtube_discovery_items_run_video
        UNIQUE (collection_run_id, youtube_video_id),
    CONSTRAINT ck_youtube_discovery_items_video_id_not_blank
        CHECK (btrim(youtube_video_id) <> ''),
    CONSTRAINT ck_youtube_discovery_items_channel_id_not_blank
        CHECK (btrim(youtube_channel_id) <> ''),
    CONSTRAINT ck_youtube_discovery_items_processing_status
        CHECK (processing_status IN ('pending', 'processed', 'failed'))
);

CREATE INDEX idx_youtube_discovery_items_youtube_video_id
    ON youtube_discovery_items (youtube_video_id);
CREATE INDEX idx_youtube_discovery_items_pending
    ON youtube_discovery_items (created_at)
    WHERE processing_status = 'pending';

ALTER TABLE youtube_discovery_items ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON youtube_discovery_items FROM anon, authenticated;

COMMIT;
