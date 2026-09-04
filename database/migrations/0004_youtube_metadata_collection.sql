-- Metadata-collection lifecycle and canonical linkage for discovery staging.
BEGIN;

ALTER TABLE collection_runs
    DROP CONSTRAINT ck_collection_runs_run_type,
    ADD CONSTRAINT ck_collection_runs_run_type CHECK (
        run_type IN (
            'discovery', 'metadata_collection', 'channel_monitor',
            'video_snapshot', 'comment_collection'
        )
    );

ALTER TABLE youtube_discovery_items
    ADD COLUMN canonical_video_id UUID NULL,
    ADD COLUMN processed_at TIMESTAMPTZ NULL,
    ADD COLUMN error_summary TEXT NULL,
    ADD CONSTRAINT fk_youtube_discovery_items_canonical_video_id
        FOREIGN KEY (canonical_video_id) REFERENCES videos (id) ON DELETE RESTRICT;

ALTER TABLE youtube_discovery_items
    DROP CONSTRAINT ck_youtube_discovery_items_processing_status,
    ADD CONSTRAINT ck_youtube_discovery_items_processing_status
        CHECK (processing_status IN ('pending', 'processing', 'processed', 'failed')),
    ADD CONSTRAINT ck_youtube_discovery_items_processing_result CHECK (
        (processing_status IN ('pending', 'processing')
            AND processed_at IS NULL AND canonical_video_id IS NULL AND error_summary IS NULL)
        OR (processing_status = 'processed'
            AND processed_at IS NOT NULL AND canonical_video_id IS NOT NULL
            AND error_summary IS NULL)
        OR (processing_status = 'failed'
            AND processed_at IS NOT NULL AND canonical_video_id IS NULL
            AND error_summary IS NOT NULL)
    );

CREATE INDEX idx_youtube_discovery_items_canonical_video_id
    ON youtube_discovery_items (canonical_video_id)
    WHERE canonical_video_id IS NOT NULL;

COMMIT;
