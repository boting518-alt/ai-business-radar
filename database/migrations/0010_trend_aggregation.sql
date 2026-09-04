BEGIN;

ALTER TABLE trend_snapshots
    ADD COLUMN aggregation_version VARCHAR NOT NULL DEFAULT 'trend-v001';

ALTER TABLE trend_snapshots
    DROP CONSTRAINT uq_trend_snapshots_opportunity_window_period;

ALTER TABLE trend_snapshots
    ADD CONSTRAINT uq_trend_snapshots_opportunity_window_period_version
    UNIQUE (opportunity_id, window_type, period_start, period_end, aggregation_version),
    ADD CONSTRAINT ck_trend_snapshots_aggregation_version_not_blank
    CHECK (btrim(aggregation_version) <> '');

COMMIT;
