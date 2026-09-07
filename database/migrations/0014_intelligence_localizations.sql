-- Stored, read-only localization projections for product intelligence.
BEGIN;

CREATE TABLE intelligence_localizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    field_name TEXT NOT NULL,
    locale TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    source_text_hash TEXT NOT NULL,
    translation_version TEXT NOT NULL,
    translation_provider TEXT,
    translation_model TEXT,
    status TEXT NOT NULL DEFAULT 'current',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_intelligence_localizations_entity_type
        CHECK (entity_type IN ('signal', 'opportunity')),
    CONSTRAINT ck_intelligence_localizations_field_name CHECK (
        (entity_type = 'signal' AND field_name IN (
            'statement', 'evidence_text', 'industry', 'customer_type'
        )) OR
        (entity_type = 'opportunity' AND field_name IN (
            'name', 'one_line_thesis', 'industry', 'customer_type', 'problem', 'solution'
        ))
    ),
    CONSTRAINT ck_intelligence_localizations_locale
        CHECK (locale ~ '^[a-z]{2,3}(-[A-Z][A-Za-z0-9]{1,7})?$'),
    CONSTRAINT ck_intelligence_localizations_status
        CHECK (status IN ('current', 'stale', 'failed')),
    CONSTRAINT ck_intelligence_localizations_text
        CHECK (length(btrim(translated_text)) > 0),
    CONSTRAINT uq_intelligence_localizations_projection UNIQUE (
        entity_type, entity_id, field_name, locale, source_text_hash, translation_version
    )
);

CREATE INDEX idx_intelligence_localizations_lookup ON intelligence_localizations (
    entity_type, entity_id, locale, field_name, status, updated_at DESC
);

ALTER TABLE intelligence_localizations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON intelligence_localizations FROM anon, authenticated;
GRANT SELECT ON intelligence_localizations TO authenticated;

CREATE POLICY intelligence_localizations_read_visible ON intelligence_localizations
FOR SELECT TO authenticated
USING (
    public.current_user_is_admin()
    OR (
        entity_type = 'signal'
        AND EXISTS (
            SELECT 1 FROM signals
            WHERE signals.id = intelligence_localizations.entity_id
              AND signals.status = 'active'
        )
    )
    OR (
        entity_type = 'opportunity'
        AND EXISTS (
            SELECT 1 FROM opportunities
            WHERE opportunities.id = intelligence_localizations.entity_id
              AND opportunities.status = 'active'
        )
    )
);

COMMIT;
