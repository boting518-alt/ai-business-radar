BEGIN;
CREATE TABLE opportunity_consolidations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE RESTRICT,
 version INTEGER NOT NULL CHECK(version > 0),
 status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed')),
 source_evidence_hash TEXT NOT NULL,
 context_hash TEXT NOT NULL,
 input_hash TEXT NOT NULL,
 prompt_version TEXT NOT NULL,
 prompt_hash TEXT NOT NULL,
 provider TEXT,
 model TEXT,
 input_snapshot JSONB NOT NULL,
 raw_output JSONB,
 parsed_output JSONB,
 field_metadata JSONB,
 error_code TEXT,
 provider_request_id TEXT,
 input_tokens INTEGER,
 output_tokens INTEGER,
 created_by UUID REFERENCES user_profiles(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 started_at TIMESTAMPTZ,
 completed_at TIMESTAMPTZ,
 review_status TEXT NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending','approved')),
 reviewed_by UUID REFERENCES user_profiles(id) ON DELETE RESTRICT,
 reviewed_at TIMESTAMPTZ,
 UNIQUE(opportunity_id,version),
 CHECK(status <> 'completed' OR (parsed_output IS NOT NULL AND completed_at IS NOT NULL)),
 CHECK(review_status <> 'approved' OR (status = 'completed' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
);
CREATE INDEX idx_consolidation_identity ON opportunity_consolidations(opportunity_id,input_hash,prompt_hash);
CREATE UNIQUE INDEX uq_consolidation_work ON opportunity_consolidations(opportunity_id) WHERE status IN ('queued','running');
ALTER TABLE opportunity_revisions ADD COLUMN source_consolidation_id UUID REFERENCES opportunity_consolidations(id) ON DELETE RESTRICT;
ALTER TABLE opportunity_consolidations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON opportunity_consolidations FROM anon, authenticated;
GRANT SELECT ON opportunity_consolidations TO authenticated;
CREATE POLICY consolidation_admin ON opportunity_consolidations FOR SELECT TO authenticated USING(public.current_user_is_admin());
-- Raw bundles/audit are never directly user-readable; API projects reviewed current sections only.
CREATE FUNCTION protect_completed_consolidation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.status IN ('completed','failed') AND
 (to_jsonb(NEW) - ARRAY['review_status','reviewed_by','reviewed_at']) IS DISTINCT FROM
 (to_jsonb(OLD) - ARRAY['review_status','reviewed_by','reviewed_at']) THEN
  RAISE EXCEPTION 'terminal consolidation payload is immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER consolidation_immutable BEFORE UPDATE ON opportunity_consolidations
FOR EACH ROW EXECUTE FUNCTION protect_completed_consolidation();
COMMIT;
