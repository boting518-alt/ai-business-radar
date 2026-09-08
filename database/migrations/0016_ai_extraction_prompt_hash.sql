ALTER TABLE ai_extractions
    ADD COLUMN prompt_hash VARCHAR(64),
    ADD CONSTRAINT ck_ai_extractions_prompt_hash
        CHECK (prompt_hash IS NULL OR prompt_hash ~ '^[0-9a-f]{64}$');

COMMENT ON COLUMN ai_extractions.prompt_hash IS
    'SHA-256 of the immutable prompt content used for this extraction; null for historical records.';
