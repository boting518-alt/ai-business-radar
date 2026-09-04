BEGIN;

ALTER TABLE opportunity_scores
    ADD COLUMN input_hash VARCHAR NULL;

UPDATE opportunity_scores
SET input_hash = 'legacy-' || replace(id::text, '-', '')
WHERE input_hash IS NULL;

ALTER TABLE opportunity_scores
    ALTER COLUMN input_hash SET NOT NULL;

ALTER TABLE opportunity_scores
    ADD CONSTRAINT ck_opportunity_scores_input_hash_not_blank
    CHECK (btrim(input_hash) <> '');

CREATE UNIQUE INDEX uq_opportunity_scores_opportunity_version_input_hash
    ON opportunity_scores (opportunity_id, scoring_version, input_hash);

COMMIT;
