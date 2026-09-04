BEGIN;
ALTER TABLE signals
    ADD COLUMN evidence_text TEXT NULL,
    ADD CONSTRAINT ck_signals_evidence_text_not_blank CHECK (
        evidence_text IS NULL OR btrim(evidence_text) <> ''
    );
COMMIT;
