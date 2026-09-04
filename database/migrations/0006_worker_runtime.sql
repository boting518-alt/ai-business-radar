-- Timestamp metadata-collection claims for bounded stale recovery.
BEGIN;

ALTER TABLE youtube_discovery_items
    ADD COLUMN claimed_at TIMESTAMPTZ NULL;

ALTER TABLE youtube_discovery_items
    DROP CONSTRAINT ck_youtube_discovery_items_processing_result,
    ADD CONSTRAINT ck_youtube_discovery_items_processing_result CHECK (
        (processing_status = 'pending'
            AND claimed_at IS NULL AND processed_at IS NULL
            AND canonical_video_id IS NULL AND error_summary IS NULL)
        OR (processing_status = 'processing'
            AND claimed_at IS NOT NULL AND processed_at IS NULL
            AND canonical_video_id IS NULL AND error_summary IS NULL)
        OR (processing_status = 'processed'
            AND claimed_at IS NULL AND processed_at IS NOT NULL
            AND canonical_video_id IS NOT NULL AND error_summary IS NULL)
        OR (processing_status = 'failed'
            AND claimed_at IS NULL AND processed_at IS NOT NULL
            AND canonical_video_id IS NULL AND error_summary IS NOT NULL)
    );

CREATE INDEX idx_youtube_discovery_items_stale_claims
    ON youtube_discovery_items (claimed_at)
    WHERE processing_status = 'processing';

COMMIT;
