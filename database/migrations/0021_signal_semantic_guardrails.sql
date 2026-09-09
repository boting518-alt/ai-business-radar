BEGIN;
ALTER TABLE signals
 ADD COLUMN semantic_status VARCHAR NOT NULL DEFAULT 'current'
   CHECK (semantic_status IN ('current','under_review','invalid_semantic','superseded')),
 ADD COLUMN actor_role VARCHAR NOT NULL DEFAULT 'unknown'
   CHECK (actor_role IN ('buyer','seller_vendor','creator_channel','affiliate_referrer','platform_marketplace','featured_product_company','unknown')),
 ADD COLUMN evidence_role VARCHAR NOT NULL DEFAULT 'unknown'
   CHECK (evidence_role IN ('buyer_expression','seller_cta','seller_claim','creator_monetization','product_monetization','product_pricing','observed_transaction','third_party_observation','unknown')),
 ADD COLUMN guardrail_version VARCHAR,
 ADD COLUMN guardrail_decision VARCHAR CHECK (guardrail_decision IN ('accept','review','reject_semantic')),
 ADD COLUMN guardrail_reason_code VARCHAR,
 ADD COLUMN superseded_by UUID REFERENCES signals(id) ON DELETE RESTRICT,
 ADD CONSTRAINT ck_signal_semantic_supersession CHECK (
   (semantic_status = 'superseded') = (superseded_by IS NOT NULL) AND superseded_by IS DISTINCT FROM id);
CREATE INDEX idx_signals_effective ON signals(status, semantic_status, signal_type);
CREATE TABLE signal_semantic_audits (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 signal_id UUID NOT NULL REFERENCES signals(id) ON DELETE RESTRICT,
 guardrail_version VARCHAR NOT NULL,
 guardrail_decision VARCHAR NOT NULL CHECK (guardrail_decision IN ('accept','review','reject_semantic')),
 guardrail_reason_code VARCHAR NOT NULL,
 original_signal_type VARCHAR NOT NULL,
 canonical_signal_type VARCHAR NOT NULL,
 actor_role VARCHAR NOT NULL,
 evidence_role VARCHAR NOT NULL,
 previous_semantic_status VARCHAR NOT NULL,
 semantic_status VARCHAR NOT NULL,
 superseded_by UUID REFERENCES signals(id) ON DELETE RESTRICT,
 input_hash VARCHAR NOT NULL,
 operator_note TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(signal_id, guardrail_version, input_hash, semantic_status)
);
ALTER TABLE signal_semantic_audits ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON signal_semantic_audits FROM anon, authenticated;
GRANT SELECT ON signal_semantic_audits TO authenticated;
CREATE POLICY signal_semantic_audits_admin ON signal_semantic_audits FOR SELECT TO authenticated
 USING (public.current_user_is_admin());
DROP POLICY signals_read_visible ON signals;
CREATE POLICY signals_read_visible ON signals FOR SELECT TO authenticated
 USING ((status = 'active' AND semantic_status = 'current') OR public.current_user_is_admin());
DROP POLICY opportunity_evidence_read_visible ON opportunity_evidence;
CREATE POLICY opportunity_evidence_read_visible ON opportunity_evidence FOR SELECT TO authenticated
 USING (public.current_user_is_admin() OR (
 EXISTS (SELECT 1 FROM opportunities o WHERE o.id=opportunity_id AND o.status='active')
 AND (signal_id IS NULL OR EXISTS (SELECT 1 FROM signals s WHERE s.id=signal_id
 AND s.status='active' AND s.semantic_status='current'))));
COMMIT;
