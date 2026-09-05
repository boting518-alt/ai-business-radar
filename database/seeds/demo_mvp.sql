-- YouTube AI Business Radar synthetic local-demo data.
-- These fictional records are not production intelligence and contain no auth credentials.
BEGIN;

INSERT INTO user_profiles (id, auth_user_id, role) VALUES
('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101', 'admin'),
('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000102', 'user')
ON CONFLICT DO NOTHING;

INSERT INTO channels (id, youtube_channel_id, name, description, first_seen_at, last_seen_at) VALUES
('20000000-0000-0000-0000-000000000001', 'synthetic-demo-channel', 'Synthetic Demo Channel',
 'Fictional channel used only for local MVP demonstration.', NOW() - INTERVAL '90 days', NOW())
ON CONFLICT DO NOTHING;

INSERT INTO videos (id, youtube_video_id, channel_id, title, description, published_at,
 current_view_count, current_like_count, current_comment_count, first_seen_at, last_seen_at,
 processing_status) VALUES
('30000000-0000-0000-0000-000000000001', 'synthetic-demo-video',
 '20000000-0000-0000-0000-000000000001', 'Synthetic AI workflow field report',
 'Fictional source material for local QA.', NOW() - INTERVAL '14 days', 12000, 640, 83,
 NOW() - INTERVAL '14 days', NOW(), 'processed')
ON CONFLICT DO NOTHING;

INSERT INTO opportunities (id, slug, name, one_line_thesis, industry, customer_type, problem,
 solution, business_model, primary_technology, market_stage, competition_level,
 build_difficulty, sales_difficulty, status, first_detected_at, last_activity_at) VALUES
('40000000-0000-0000-0000-000000000001', 'demo-ai-invoice-operations',
 'Demo: AI Invoice Operations', 'Synthetic accelerating opportunity for local QA.', 'Finance',
 'SMB', 'Manual invoice review consumes staff time.', 'AI-assisted invoice workflow', 'SaaS',
 'Document AI', 'accelerating', 'medium', 'medium', 'low', 'active', NOW()-INTERVAL '80 days', NOW()),
('40000000-0000-0000-0000-000000000002', 'demo-clinic-scheduling-copilot',
 'Demo: Clinic Scheduling Copilot', 'Synthetic high-confidence opportunity for local QA.',
 'Healthcare', 'SMB', 'Clinics miss calls and appointments.', 'Voice scheduling assistant', 'SaaS',
 'Voice AI', 'validated', 'medium', 'medium', 'medium', 'active', NOW()-INTERVAL '70 days', NOW()),
('40000000-0000-0000-0000-000000000003', 'demo-viral-avatar-studio',
 'Demo: Viral Avatar Studio', 'Synthetic high-hype opportunity for local QA.', 'Media', 'Creator',
 'Video production is expensive.', 'Generative avatar production', 'Subscription', 'Generative AI',
 'crowded', 'high', 'low', 'low', 'active', NOW()-INTERVAL '40 days', NOW()),
('40000000-0000-0000-0000-000000000004', 'demo-new-compliance-assistant',
 'Demo: New Compliance Assistant', 'Synthetic sparse opportunity for local QA.', 'Legal', 'SMB',
 'Small firms struggle to track obligations.', 'AI compliance checklist', 'SaaS', 'LLM',
 'emerging', 'unknown', 'medium', 'high', 'active', NOW()-INTERVAL '5 days', NOW())
ON CONFLICT DO NOTHING;

INSERT INTO signals (id, source_type, source_id, video_id, signal_type, statement, industry,
 customer_type, problem, solution, claim_status, confidence, evidence_strength, observed_at, status)
VALUES
('50000000-0000-0000-0000-000000000001', 'video',
 '30000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
 'pain', 'Synthetic teams report spending hours reviewing invoices.', 'Finance', 'SMB',
 'Manual invoice review', 'AI document workflow', 'creator_claim', 0.88, 0.82,
 NOW()-INTERVAL '3 days', 'active'),
('50000000-0000-0000-0000-000000000002', 'video',
 '30000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
 'purchase_intent', 'Synthetic buyers ask for automated reconciliation.', 'Finance', 'SMB',
 'Manual reconciliation', 'Automated reconciliation', 'inferred', 0.76, 0.70,
 NOW()-INTERVAL '2 days', 'active'),
('50000000-0000-0000-0000-000000000003', 'video',
 '30000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
 'feature_request', 'Synthetic users request exception routing.', 'Legal', 'SMB',
 'Compliance exceptions', 'Guided routing', 'opinion', 0.65, 0.55,
 NOW()-INTERVAL '1 day', 'review')
ON CONFLICT DO NOTHING;

INSERT INTO opportunity_signal_links (opportunity_id, signal_id, relationship_type, confidence)
VALUES
('40000000-0000-0000-0000-000000000001','50000000-0000-0000-0000-000000000001','supporting',0.90),
('40000000-0000-0000-0000-000000000001','50000000-0000-0000-0000-000000000002','supporting',0.80)
ON CONFLICT DO NOTHING;

INSERT INTO opportunity_evidence (id, opportunity_id, source_type, signal_id, video_id,
 evidence_type, summary, strength, confidence, observed_at) VALUES
('60000000-0000-0000-0000-000000000001','40000000-0000-0000-0000-000000000001',
 'youtube_video','50000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000001',
 'pain','Synthetic evidence: invoice review consumes repeated staff hours.',0.82,0.88,NOW()-INTERVAL '3 days'),
('60000000-0000-0000-0000-000000000002','40000000-0000-0000-0000-000000000001',
 'manual',NULL,NULL,'demand','Synthetic QA evidence added to demonstrate evidence history.',0.70,0.75,
 NOW()-INTERVAL '2 days')
ON CONFLICT DO NOTHING;

INSERT INTO trend_snapshots (opportunity_id, window_type, period_start, period_end, video_count,
 new_video_count, unique_channel_count, total_views, comment_count, pain_signal_count,
 demand_signal_count, purchase_intent_signal_count, revenue_signal_count, competitor_signal_count,
 momentum_score, aggregation_version) VALUES
('40000000-0000-0000-0000-000000000001','7d','2026-08-29T00:00:00Z','2026-09-05T00:00:00Z',5,3,3,120000,48,4,3,2,1,1,82,'trend-v001'),
('40000000-0000-0000-0000-000000000002','7d','2026-08-29T00:00:00Z','2026-09-05T00:00:00Z',4,2,3,85000,32,3,4,2,1,1,68,'trend-v001'),
('40000000-0000-0000-0000-000000000003','7d','2026-08-29T00:00:00Z','2026-09-05T00:00:00Z',12,10,8,950000,250,1,1,0,0,5,94,'trend-v001'),
('40000000-0000-0000-0000-000000000004','7d','2026-08-29T00:00:00Z','2026-09-05T00:00:00Z',1,1,1,2500,3,1,0,0,0,0,52,'trend-v001')
ON CONFLICT DO NOTHING;

INSERT INTO opportunity_scores (opportunity_id, calculated_at, scoring_version,
 trend_velocity_score, demand_evidence_score, revenue_evidence_score, pain_severity_score,
 competition_white_space_score, build_feasibility_score, distribution_ease_score,
 opportunity_score, confidence_score, hype_risk_score, inputs_snapshot, input_hash) VALUES
('40000000-0000-0000-0000-000000000001',NOW(),'score-v001',82,86,72,84,75,70,78,81,88,24,'{"demo":true}','demo-score-1'),
('40000000-0000-0000-0000-000000000002',NOW(),'score-v001',68,78,70,75,72,65,70,74,94,18,'{"demo":true}','demo-score-2'),
('40000000-0000-0000-0000-000000000003',NOW(),'score-v001',94,35,18,25,20,82,88,47,42,91,'{"demo":true}','demo-score-3'),
('40000000-0000-0000-0000-000000000004',NOW(),'score-v001',52,38,20,48,58,62,45,46,31,36,'{"demo":true}','demo-score-4')
ON CONFLICT DO NOTHING;

INSERT INTO review_tasks (id, review_type, target_type, target_id, status, priority, context)
VALUES ('70000000-0000-0000-0000-000000000001','signal_validation','signal',
'50000000-0000-0000-0000-000000000003','pending',0.65,'{"reason":"Synthetic QA review task"}')
ON CONFLICT DO NOTHING;

INSERT INTO watchlists (id,user_profile_id,name) VALUES
('80000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000002','Watchlist')
ON CONFLICT DO NOTHING;
INSERT INTO watchlist_items (watchlist_id,opportunity_id) VALUES
('80000000-0000-0000-0000-000000000001','40000000-0000-0000-0000-000000000001')
ON CONFLICT DO NOTHING;

COMMIT;
