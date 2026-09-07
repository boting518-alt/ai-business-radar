-- Provider usage metadata for the TASK-034 translation runtime.
BEGIN;

ALTER TABLE intelligence_localizations
    ADD COLUMN prompt_hash VARCHAR(64),
    ADD COLUMN provider_request_id TEXT,
    ADD COLUMN input_tokens INTEGER,
    ADD COLUMN output_tokens INTEGER,
    ADD CONSTRAINT ck_intelligence_localizations_input_tokens
        CHECK (input_tokens IS NULL OR input_tokens >= 0),
    ADD CONSTRAINT ck_intelligence_localizations_output_tokens
        CHECK (output_tokens IS NULL OR output_tokens >= 0),
    ADD CONSTRAINT ck_intelligence_localizations_prompt_hash
        CHECK (prompt_hash IS NULL OR prompt_hash ~ '^[0-9a-f]{64}$');

COMMIT;
