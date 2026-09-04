BEGIN;

ALTER TABLE ai_extractions
    ADD COLUMN signal_id UUID NULL,
    ADD CONSTRAINT fk_ai_extractions_signal_id
        FOREIGN KEY (signal_id) REFERENCES signals(id) ON DELETE RESTRICT;

ALTER TABLE ai_extractions DROP CONSTRAINT ck_ai_extractions_source_type;
ALTER TABLE ai_extractions ADD CONSTRAINT ck_ai_extractions_source_type CHECK (
    source_type IN ('video', 'comment', 'signal', 'opportunity')
);

ALTER TABLE ai_extractions DROP CONSTRAINT ck_ai_extractions_source_integrity;
ALTER TABLE ai_extractions ADD CONSTRAINT ck_ai_extractions_source_integrity CHECK (
    (source_type = 'video' AND source_id = video_id AND video_id IS NOT NULL
        AND comment_id IS NULL AND signal_id IS NULL AND opportunity_id IS NULL)
    OR
    (source_type = 'comment' AND source_id = comment_id AND comment_id IS NOT NULL
        AND video_id IS NULL AND signal_id IS NULL AND opportunity_id IS NULL)
    OR
    (source_type = 'signal' AND source_id = signal_id AND signal_id IS NOT NULL
        AND video_id IS NULL AND comment_id IS NULL AND opportunity_id IS NULL)
    OR
    (source_type = 'opportunity' AND source_id = opportunity_id AND opportunity_id IS NOT NULL
        AND video_id IS NULL AND comment_id IS NULL AND signal_id IS NULL)
);

CREATE INDEX idx_ai_extractions_signal_id ON ai_extractions (signal_id);

ALTER TABLE review_tasks ADD COLUMN context JSONB NULL;

COMMIT;
