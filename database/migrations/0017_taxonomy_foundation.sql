BEGIN;

CREATE TABLE industry_taxonomy_nodes (
    code TEXT PRIMARY KEY, parent_code TEXT REFERENCES industry_taxonomy_nodes(code),
    canonical_name TEXT NOT NULL, description TEXT, is_active BOOLEAN NOT NULL DEFAULT TRUE,
    taxonomy_version TEXT NOT NULL DEFAULT 'taxonomy-v001',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (code ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$'),
    CHECK (taxonomy_version = 'taxonomy-v001')
);
CREATE TABLE customer_taxonomy_nodes (
    code TEXT PRIMARY KEY, parent_code TEXT REFERENCES customer_taxonomy_nodes(code),
    canonical_name TEXT NOT NULL, description TEXT, is_active BOOLEAN NOT NULL DEFAULT TRUE,
    taxonomy_version TEXT NOT NULL DEFAULT 'taxonomy-v001',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (code ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$'),
    CHECK (taxonomy_version = 'taxonomy-v001')
);
CREATE TABLE taxonomy_localizations (
    taxonomy_type TEXT NOT NULL CHECK (taxonomy_type IN ('industry','customer')),
    taxonomy_code TEXT NOT NULL, locale TEXT NOT NULL CHECK (locale IN ('en-US','zh-CN')),
    label TEXT NOT NULL CHECK (length(btrim(label)) > 0), short_label TEXT, description TEXT,
    PRIMARY KEY (taxonomy_type, taxonomy_code, locale)
);
CREATE TABLE taxonomy_aliases (
    taxonomy_type TEXT NOT NULL CHECK (taxonomy_type IN ('industry','customer')),
    alias_text_normalized TEXT NOT NULL, taxonomy_code TEXT NOT NULL, locale TEXT,
    match_type TEXT NOT NULL CHECK (match_type IN ('exact','normalized_exact')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (taxonomy_type, alias_text_normalized, taxonomy_code)
);
CREATE TABLE signal_taxonomy_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), signal_id UUID NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    taxonomy_type TEXT NOT NULL CHECK (taxonomy_type IN ('industry','customer')), taxonomy_code TEXT NOT NULL,
    mapping_source TEXT NOT NULL CHECK (mapping_source IN ('manual','rule','ai','migration','unknown')),
    mapping_confidence NUMERIC CHECK (mapping_confidence IS NULL OR mapping_confidence BETWEEN 0 AND 1),
    mapping_status TEXT NOT NULL CHECK (mapping_status IN ('active','review','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE opportunity_taxonomy_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    taxonomy_type TEXT NOT NULL CHECK (taxonomy_type IN ('industry','customer')), taxonomy_code TEXT NOT NULL,
    mapping_source TEXT NOT NULL CHECK (mapping_source IN ('manual','rule','ai','migration','unknown')),
    mapping_confidence NUMERIC CHECK (mapping_confidence IS NULL OR mapping_confidence BETWEEN 0 AND 1),
    mapping_status TEXT NOT NULL CHECK (mapping_status IN ('active','review','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_signal_taxonomy_active ON signal_taxonomy_mappings(signal_id,taxonomy_type) WHERE mapping_status='active';
CREATE UNIQUE INDEX uq_opportunity_taxonomy_active ON opportunity_taxonomy_mappings(opportunity_id,taxonomy_type) WHERE mapping_status='active';
CREATE INDEX idx_signal_taxonomy_filter ON signal_taxonomy_mappings(taxonomy_type,taxonomy_code,signal_id) WHERE mapping_status='active';
CREATE INDEX idx_opportunity_taxonomy_filter ON opportunity_taxonomy_mappings(taxonomy_type,taxonomy_code,opportunity_id) WHERE mapping_status='active';

INSERT INTO industry_taxonomy_nodes(code,parent_code,canonical_name) VALUES
('technology.ai',NULL,'Artificial Intelligence'),('healthcare',NULL,'Healthcare'),('healthcare.dental','healthcare','Dental'),
('healthcare.veterinary','healthcare','Veterinary'),('legal',NULL,'Legal'),('legal.law_firms','legal','Law Firms'),
('real_estate',NULL,'Real Estate'),('real_estate.property_management','real_estate','Property Management'),
('commerce',NULL,'Commerce'),('commerce.ecommerce','commerce','E-commerce'),('finance',NULL,'Finance'),
('finance.accounting','finance','Accounting'),('finance.bookkeeping','finance','Bookkeeping'),
('home_services',NULL,'Home Services'),('home_services.hvac','home_services','HVAC'),
('software',NULL,'Software'),('software.saas','software','SaaS');
INSERT INTO customer_taxonomy_nodes(code,parent_code,canonical_name) VALUES
('organization',NULL,'Organization'),('individual',NULL,'Individual'),('professional',NULL,'Professional'),('team',NULL,'Team'),('operator',NULL,'Operator'),
('organization.dental_practice','organization','Dental Practice'),('organization.veterinary_clinic','organization','Veterinary Clinic'),
('organization.law_firm','organization','Law Firm'),('organization.property_management_company','organization','Property Management Company'),
('organization.ecommerce_store','organization','E-commerce Store'),('organization.accounting_firm','organization','Accounting Firm'),
('organization.small_business','organization','Small Business'),('organization.hvac_company','organization','HVAC Company'),
('professional.dentist','professional','Dentist'),('professional.attorney','professional','Attorney'),
('professional.accountant','professional','Accountant'),('professional.property_manager','professional','Property Manager'),
('team.front_desk','team','Front Desk'),('team.reception','team','Reception'),('team.leasing','team','Leasing'),
('team.customer_support','team','Customer Support'),('team.bookkeeping','team','Bookkeeping');
INSERT INTO taxonomy_localizations(taxonomy_type,taxonomy_code,locale,label) SELECT 'industry',code,'en-US',canonical_name FROM industry_taxonomy_nodes;
INSERT INTO taxonomy_localizations(taxonomy_type,taxonomy_code,locale,label) VALUES
('industry','technology.ai','zh-CN','人工智能'),('industry','healthcare','zh-CN','医疗健康'),('industry','healthcare.dental','zh-CN','牙科'),('industry','healthcare.veterinary','zh-CN','兽医'),
('industry','legal','zh-CN','法律'),('industry','legal.law_firms','zh-CN','律师事务所'),('industry','real_estate','zh-CN','房地产'),('industry','real_estate.property_management','zh-CN','物业管理'),
('industry','commerce','zh-CN','商业'),('industry','commerce.ecommerce','zh-CN','电子商务'),('industry','finance','zh-CN','金融'),('industry','finance.accounting','zh-CN','会计'),
('industry','finance.bookkeeping','zh-CN','记账'),('industry','home_services','zh-CN','家庭服务'),('industry','home_services.hvac','zh-CN','暖通空调'),('industry','software','zh-CN','软件'),('industry','software.saas','zh-CN','SaaS');
INSERT INTO taxonomy_localizations(taxonomy_type,taxonomy_code,locale,label) SELECT 'customer',code,'en-US',canonical_name FROM customer_taxonomy_nodes;
INSERT INTO taxonomy_localizations(taxonomy_type,taxonomy_code,locale,label) VALUES
('customer','organization','zh-CN','组织'),('customer','individual','zh-CN','个人'),('customer','professional','zh-CN','专业人士'),('customer','team','zh-CN','团队'),('customer','operator','zh-CN','运营者'),
('customer','organization.dental_practice','zh-CN','牙科诊所'),('customer','organization.veterinary_clinic','zh-CN','兽医诊所'),('customer','organization.law_firm','zh-CN','律师事务所'),
('customer','organization.property_management_company','zh-CN','物业管理公司'),('customer','organization.ecommerce_store','zh-CN','电商店铺'),('customer','organization.accounting_firm','zh-CN','会计师事务所'),
('customer','organization.small_business','zh-CN','小型企业'),('customer','organization.hvac_company','zh-CN','暖通空调公司'),('customer','professional.dentist','zh-CN','牙医'),
('customer','professional.attorney','zh-CN','律师'),('customer','professional.accountant','zh-CN','会计师'),('customer','professional.property_manager','zh-CN','物业经理'),
('customer','team.front_desk','zh-CN','前台团队'),('customer','team.reception','zh-CN','接待团队'),('customer','team.leasing','zh-CN','租赁团队'),('customer','team.customer_support','zh-CN','客户支持团队'),('customer','team.bookkeeping','zh-CN','记账团队');
INSERT INTO taxonomy_aliases(taxonomy_type,alias_text_normalized,taxonomy_code,locale,match_type) VALUES
('industry','dental practices','healthcare.dental','en-US','normalized_exact'),('industry','dental clinics','healthcare.dental','en-US','normalized_exact'),('industry','dental offices','healthcare.dental','en-US','normalized_exact'),
('industry','law firms','legal.law_firms','en-US','normalized_exact'),('industry','property management','real_estate.property_management','en-US','normalized_exact'),
('industry','e-commerce','commerce.ecommerce','en-US','normalized_exact'),('industry','shopify stores','commerce.ecommerce','en-US','normalized_exact'),
('industry','accounting','finance.accounting','en-US','normalized_exact'),('industry','bookkeeping','finance.bookkeeping','en-US','normalized_exact'),('industry','hvac','home_services.hvac','en-US','normalized_exact'),
('customer','dental practices','organization.dental_practice','en-US','normalized_exact'),('customer','dental clinics','organization.dental_practice','en-US','normalized_exact'),('customer','dental offices','organization.dental_practice','en-US','normalized_exact'),
('customer','dentists','professional.dentist','en-US','normalized_exact'),('customer','law firms','organization.law_firm','en-US','normalized_exact'),('customer','property managers','professional.property_manager','en-US','normalized_exact'),
('customer','front desk teams','team.front_desk','en-US','normalized_exact'),('customer','small businesses','organization.small_business','en-US','normalized_exact'),('customer','hvac companies','organization.hvac_company','en-US','normalized_exact');

ALTER TABLE industry_taxonomy_nodes ENABLE ROW LEVEL SECURITY; ALTER TABLE customer_taxonomy_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxonomy_localizations ENABLE ROW LEVEL SECURITY; ALTER TABLE taxonomy_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE signal_taxonomy_mappings ENABLE ROW LEVEL SECURITY; ALTER TABLE opportunity_taxonomy_mappings ENABLE ROW LEVEL SECURITY;
GRANT SELECT ON industry_taxonomy_nodes,customer_taxonomy_nodes,taxonomy_localizations TO authenticated;
GRANT SELECT ON signal_taxonomy_mappings,opportunity_taxonomy_mappings TO authenticated;
CREATE POLICY industry_taxonomy_read ON industry_taxonomy_nodes FOR SELECT TO authenticated USING (TRUE);
CREATE POLICY customer_taxonomy_read ON customer_taxonomy_nodes FOR SELECT TO authenticated USING (TRUE);
CREATE POLICY taxonomy_localizations_read ON taxonomy_localizations FOR SELECT TO authenticated USING (TRUE);
CREATE POLICY signal_taxonomy_visible ON signal_taxonomy_mappings FOR SELECT TO authenticated USING (public.current_user_is_admin() OR EXISTS(SELECT 1 FROM signals s WHERE s.id=signal_id AND s.status='active'));
CREATE POLICY opportunity_taxonomy_visible ON opportunity_taxonomy_mappings FOR SELECT TO authenticated USING (public.current_user_is_admin() OR EXISTS(SELECT 1 FROM opportunities o WHERE o.id=opportunity_id AND o.status='active'));
COMMIT;
