BEGIN;
ALTER TABLE ai_extractions
    ADD COLUMN input_tokens INT NULL,
    ADD COLUMN output_tokens INT NULL,
    ADD COLUMN total_tokens INT NULL,
    ADD COLUMN provider_request_id VARCHAR NULL,
    ADD CONSTRAINT uq_ai_extractions_identity_attempt UNIQUE (
        source_type, source_id, task_type, prompt_version, model, input_hash, attempt_number
    ),
    ADD CONSTRAINT ck_ai_extractions_token_counts CHECK (
        (input_tokens IS NULL OR input_tokens >= 0) AND
        (output_tokens IS NULL OR output_tokens >= 0) AND
        (total_tokens IS NULL OR total_tokens >= 0)
    );
COMMIT;
