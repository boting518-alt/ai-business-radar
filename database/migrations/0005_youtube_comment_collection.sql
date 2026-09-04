-- Preserve the YouTube source edit timestamp separately from row maintenance time.
BEGIN;

ALTER TABLE comments
    ADD COLUMN source_updated_at TIMESTAMPTZ NULL;

COMMIT;
