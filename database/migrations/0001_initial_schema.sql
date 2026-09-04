BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Identity/support. auth_user_id logically references Supabase auth.users(id),
-- but no cross-schema FK is created in this portable initial migration.
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id UUID NOT NULL,
    role VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_profiles_auth_user_id UNIQUE (auth_user_id),
    CONSTRAINT ck_user_profiles_role CHECK (role IN ('user', 'admin'))
);

-- RAW: managed source discovery configuration.
CREATE TABLE search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    query_group VARCHAR NOT NULL,
    language VARCHAR NULL,
    region VARCHAR NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    priority NUMERIC NOT NULL,
    discovery_mode VARCHAR NOT NULL,
    last_run_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_search_queries_query_not_blank CHECK (btrim(query) <> ''),
    CONSTRAINT ck_search_queries_query_group CHECK (
        query_group IN ('technology', 'business', 'revenue', 'pain', 'industry', 'discovery')
    ),
    CONSTRAINT ck_search_queries_priority_non_negative CHECK (priority >= 0),
    CONSTRAINT ck_search_queries_discovery_mode CHECK (
        discovery_mode IN ('discovery', 'monitoring')
    )
);

CREATE UNIQUE INDEX uq_search_queries_definition
    ON search_queries (
        lower(query),
        query_group,
        COALESCE(language, ''),
        COALESCE(region, ''),
        discovery_mode
    );

CREATE INDEX idx_search_queries_enabled_priority
    ON search_queries (enabled, priority DESC);

CREATE INDEX idx_search_queries_last_run_at
    ON search_queries (last_run_at);

-- RAW: observable collection executions.
CREATE TABLE collection_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR NOT NULL,
    run_type VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    search_query_id UUID NULL,
    items_discovered INT NOT NULL DEFAULT 0,
    items_processed INT NOT NULL DEFAULT 0,
    items_failed INT NOT NULL DEFAULT 0,
    error_summary TEXT NULL,
    metadata JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_collection_runs_search_query_id
        FOREIGN KEY (search_query_id) REFERENCES search_queries (id) ON DELETE RESTRICT,
    CONSTRAINT ck_collection_runs_source_type CHECK (source_type = 'youtube'),
    CONSTRAINT ck_collection_runs_run_type CHECK (
        run_type IN ('discovery', 'channel_monitor', 'video_snapshot', 'comment_collection')
    ),
    CONSTRAINT ck_collection_runs_status CHECK (
        status IN ('pending', 'running', 'completed', 'partial', 'failed', 'cancelled')
    ),
    CONSTRAINT ck_collection_runs_items_discovered_non_negative CHECK (items_discovered >= 0),
    CONSTRAINT ck_collection_runs_items_processed_non_negative CHECK (items_processed >= 0),
    CONSTRAINT ck_collection_runs_items_failed_non_negative CHECK (items_failed >= 0),
    CONSTRAINT ck_collection_runs_finished_requires_started CHECK (
        finished_at IS NULL OR started_at IS NOT NULL
    ),
    CONSTRAINT ck_collection_runs_timestamp_order CHECK (
        finished_at IS NULL OR finished_at >= started_at
    )
);

CREATE INDEX idx_collection_runs_status_created_at
    ON collection_runs (status, created_at DESC);

CREATE INDEX idx_collection_runs_run_type_created_at
    ON collection_runs (run_type, created_at DESC);

CREATE INDEX idx_collection_runs_search_query_id_created_at
    ON collection_runs (search_query_id, created_at DESC);

-- RAW: canonical YouTube channels.
CREATE TABLE channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    youtube_channel_id VARCHAR NOT NULL,
    name TEXT NOT NULL,
    description TEXT NULL,
    country VARCHAR NULL,
    subscriber_count BIGINT NULL,
    video_count BIGINT NULL,
    view_count BIGINT NULL,
    channel_type VARCHAR NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_channels_youtube_channel_id UNIQUE (youtube_channel_id),
    CONSTRAINT ck_channels_youtube_channel_id_not_blank CHECK (btrim(youtube_channel_id) <> ''),
    CONSTRAINT ck_channels_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_channels_subscriber_count_non_negative CHECK (
        subscriber_count IS NULL OR subscriber_count >= 0
    ),
    CONSTRAINT ck_channels_video_count_non_negative CHECK (
        video_count IS NULL OR video_count >= 0
    ),
    CONSTRAINT ck_channels_view_count_non_negative CHECK (
        view_count IS NULL OR view_count >= 0
    ),
    CONSTRAINT ck_channels_channel_type CHECK (
        channel_type IS NULL OR channel_type IN (
            'founder', 'business_media', 'ai_educator', 'vc',
            'consultant', 'vendor', 'news', 'unknown'
        )
    ),
    CONSTRAINT ck_channels_seen_at_order CHECK (first_seen_at <= last_seen_at)
);

CREATE INDEX idx_channels_last_seen_at ON channels (last_seen_at DESC);
CREATE INDEX idx_channels_channel_type ON channels (channel_type);

-- RAW: canonical YouTube videos.
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    youtube_video_id VARCHAR NOT NULL,
    channel_id UUID NOT NULL,
    title TEXT NOT NULL,
    description TEXT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    duration_seconds INT NULL,
    language VARCHAR NULL,
    category_id VARCHAR NULL,
    thumbnail_url TEXT NULL,
    current_view_count BIGINT NULL,
    current_like_count BIGINT NULL,
    current_comment_count BIGINT NULL,
    has_captions BOOLEAN NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    processing_status VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_videos_youtube_video_id UNIQUE (youtube_video_id),
    CONSTRAINT fk_videos_channel_id
        FOREIGN KEY (channel_id) REFERENCES channels (id) ON DELETE RESTRICT,
    CONSTRAINT ck_videos_youtube_video_id_not_blank CHECK (btrim(youtube_video_id) <> ''),
    CONSTRAINT ck_videos_title_not_blank CHECK (btrim(title) <> ''),
    CONSTRAINT ck_videos_duration_seconds_non_negative CHECK (
        duration_seconds IS NULL OR duration_seconds >= 0
    ),
    CONSTRAINT ck_videos_current_view_count_non_negative CHECK (
        current_view_count IS NULL OR current_view_count >= 0
    ),
    CONSTRAINT ck_videos_current_like_count_non_negative CHECK (
        current_like_count IS NULL OR current_like_count >= 0
    ),
    CONSTRAINT ck_videos_current_comment_count_non_negative CHECK (
        current_comment_count IS NULL OR current_comment_count >= 0
    ),
    CONSTRAINT ck_videos_processing_status CHECK (
        processing_status IN ('new', 'queued', 'processing', 'processed', 'review', 'ignored', 'failed')
    ),
    CONSTRAINT ck_videos_seen_at_order CHECK (first_seen_at <= last_seen_at)
);

CREATE INDEX idx_videos_channel_id ON videos (channel_id);
CREATE INDEX idx_videos_published_at ON videos (published_at DESC);
CREATE INDEX idx_videos_processing_status ON videos (processing_status);

-- RAW: append-only by application convention.
CREATE TABLE video_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    view_count BIGINT NULL,
    like_count BIGINT NULL,
    comment_count BIGINT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_video_snapshots_video_id
        FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE RESTRICT,
    CONSTRAINT ck_video_snapshots_view_count_non_negative CHECK (
        view_count IS NULL OR view_count >= 0
    ),
    CONSTRAINT ck_video_snapshots_like_count_non_negative CHECK (
        like_count IS NULL OR like_count >= 0
    ),
    CONSTRAINT ck_video_snapshots_comment_count_non_negative CHECK (
        comment_count IS NULL OR comment_count >= 0
    )
);

CREATE UNIQUE INDEX uq_video_snapshots_video_id_captured_at
    ON video_snapshots (video_id, captured_at DESC);

-- RAW: public comments without author display names.
CREATE TABLE comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    youtube_comment_id VARCHAR NOT NULL,
    video_id UUID NOT NULL,
    text TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    like_count INT NULL,
    reply_count INT NULL,
    author_hash VARCHAR NULL,
    is_question BOOLEAN NULL,
    language VARCHAR NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_comments_youtube_comment_id UNIQUE (youtube_comment_id),
    CONSTRAINT fk_comments_video_id
        FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE RESTRICT,
    CONSTRAINT ck_comments_youtube_comment_id_not_blank CHECK (btrim(youtube_comment_id) <> ''),
    CONSTRAINT ck_comments_text_not_blank CHECK (btrim(text) <> ''),
    CONSTRAINT ck_comments_like_count_non_negative CHECK (like_count IS NULL OR like_count >= 0),
    CONSTRAINT ck_comments_reply_count_non_negative CHECK (reply_count IS NULL OR reply_count >= 0)
);

CREATE INDEX idx_comments_video_id ON comments (video_id);
CREATE INDEX idx_comments_published_at ON comments (published_at DESC);

-- INTELLIGENCE parent is created before ai_extractions because opportunity-level
-- normalization and hype-detection runs use an explicit opportunity FK.
CREATE TABLE opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR NOT NULL,
    name TEXT NOT NULL,
    one_line_thesis TEXT NULL,
    industry VARCHAR NULL,
    sub_industry VARCHAR NULL,
    customer_type VARCHAR NULL,
    problem TEXT NULL,
    solution TEXT NULL,
    business_model VARCHAR NULL,
    primary_technology VARCHAR NULL,
    typical_price_min NUMERIC NULL,
    typical_price_max NUMERIC NULL,
    typical_price_currency VARCHAR NULL,
    typical_price_period VARCHAR NULL,
    market_stage VARCHAR NOT NULL,
    competition_level VARCHAR NULL,
    build_difficulty VARCHAR NULL,
    sales_difficulty VARCHAR NULL,
    status VARCHAR NOT NULL,
    first_detected_at TIMESTAMPTZ NOT NULL,
    last_activity_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_opportunities_slug UNIQUE (slug),
    CONSTRAINT ck_opportunities_slug_not_blank CHECK (btrim(slug) <> ''),
    CONSTRAINT ck_opportunities_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_opportunities_market_stage CHECK (
        market_stage IN ('unknown', 'emerging', 'accelerating', 'validated', 'crowded', 'mature', 'declining')
    ),
    CONSTRAINT ck_opportunities_status CHECK (
        status IN ('candidate', 'active', 'review', 'merged', 'rejected', 'archived')
    ),
    CONSTRAINT ck_opportunities_typical_price_min_non_negative CHECK (
        typical_price_min IS NULL OR typical_price_min >= 0
    ),
    CONSTRAINT ck_opportunities_typical_price_max_non_negative CHECK (
        typical_price_max IS NULL OR typical_price_max >= 0
    ),
    CONSTRAINT ck_opportunities_typical_price_range CHECK (
        typical_price_min IS NULL
        OR typical_price_max IS NULL
        OR typical_price_min <= typical_price_max
    ),
    CONSTRAINT ck_opportunities_typical_price_currency CHECK (
        (typical_price_min IS NULL AND typical_price_max IS NULL)
        OR typical_price_currency IS NOT NULL
    ),
    CONSTRAINT ck_opportunities_activity_order CHECK (first_detected_at <= last_activity_at)
);

CREATE INDEX idx_opportunities_market_stage ON opportunities (market_stage);
CREATE INDEX idx_opportunities_status ON opportunities (status);
CREATE INDEX idx_opportunities_industry ON opportunities (industry);
CREATE INDEX idx_opportunities_last_activity_at ON opportunities (last_activity_at DESC);
CREATE INDEX idx_opportunities_status_stage_activity
    ON opportunities (status, market_stage, last_activity_at DESC);

-- FACT: retained audit record for each AI attempt.
CREATE TABLE ai_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR NOT NULL,
    source_id UUID NOT NULL,
    video_id UUID NULL,
    comment_id UUID NULL,
    opportunity_id UUID NULL,
    task_type VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    prompt_version VARCHAR NOT NULL,
    input_hash VARCHAR NOT NULL,
    attempt_number INT NOT NULL DEFAULT 1,
    supersedes_extraction_id UUID NULL,
    status VARCHAR NOT NULL,
    raw_output JSONB NULL,
    parsed_output JSONB NULL,
    confidence NUMERIC NULL,
    error_message TEXT NULL,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_ai_extractions_video_id
        FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE RESTRICT,
    CONSTRAINT fk_ai_extractions_comment_id
        FOREIGN KEY (comment_id) REFERENCES comments (id) ON DELETE RESTRICT,
    CONSTRAINT fk_ai_extractions_opportunity_id
        FOREIGN KEY (opportunity_id) REFERENCES opportunities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_ai_extractions_supersedes_extraction_id
        FOREIGN KEY (supersedes_extraction_id) REFERENCES ai_extractions (id) ON DELETE RESTRICT,
    CONSTRAINT ck_ai_extractions_source_type CHECK (
        source_type IN ('video', 'comment', 'opportunity')
    ),
    CONSTRAINT ck_ai_extractions_source_integrity CHECK (
        (
            source_type = 'video'
            AND video_id IS NOT NULL
            AND source_id = video_id
            AND comment_id IS NULL
            AND opportunity_id IS NULL
        ) OR (
            source_type = 'comment'
            AND comment_id IS NOT NULL
            AND source_id = comment_id
            AND video_id IS NULL
            AND opportunity_id IS NULL
        ) OR (
            source_type = 'opportunity'
            AND opportunity_id IS NOT NULL
            AND source_id = opportunity_id
            AND video_id IS NULL
            AND comment_id IS NULL
        )
    ),
    CONSTRAINT ck_ai_extractions_task_type CHECK (
        task_type IN (
            'relevance_filter', 'signal_extractor', 'comment_pain_miner',
            'opportunity_normalizer', 'hype_detector'
        )
    ),
    CONSTRAINT ck_ai_extractions_provider_not_blank CHECK (btrim(provider) <> ''),
    CONSTRAINT ck_ai_extractions_model_not_blank CHECK (btrim(model) <> ''),
    CONSTRAINT ck_ai_extractions_prompt_version_not_blank CHECK (btrim(prompt_version) <> ''),
    CONSTRAINT ck_ai_extractions_input_hash_not_blank CHECK (btrim(input_hash) <> ''),
    CONSTRAINT ck_ai_extractions_attempt_number_positive CHECK (attempt_number >= 1),
    CONSTRAINT ck_ai_extractions_status CHECK (
        status IN ('pending', 'running', 'completed', 'failed', 'invalid_output')
    ),
    CONSTRAINT ck_ai_extractions_confidence CHECK (
        confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
    ),
    CONSTRAINT ck_ai_extractions_completed_requires_started CHECK (
        completed_at IS NULL OR started_at IS NOT NULL
    ),
    CONSTRAINT ck_ai_extractions_timestamp_order CHECK (
        completed_at IS NULL OR completed_at >= started_at
    ),
    CONSTRAINT ck_ai_extractions_not_self_superseding CHECK (
        supersedes_extraction_id IS NULL OR supersedes_extraction_id <> id
    )
);

CREATE INDEX idx_ai_extractions_source_type_source_id
    ON ai_extractions (source_type, source_id);
CREATE INDEX idx_ai_extractions_task_type_status
    ON ai_extractions (task_type, status);
CREATE INDEX idx_ai_extractions_identity_lookup
    ON ai_extractions (
        source_type, source_id, task_type, prompt_version, model, input_hash
    );
CREATE INDEX idx_ai_extractions_video_id ON ai_extractions (video_id);
CREATE INDEX idx_ai_extractions_comment_id ON ai_extractions (comment_id);
CREATE INDEX idx_ai_extractions_opportunity_id ON ai_extractions (opportunity_id);

-- FACT: atomic evidence-backed observations.
CREATE TABLE signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR NOT NULL,
    source_id UUID NOT NULL,
    video_id UUID NULL,
    comment_id UUID NULL,
    ai_extraction_id UUID NULL,
    signal_type VARCHAR NOT NULL,
    statement TEXT NOT NULL,
    normalized_statement TEXT NULL,
    industry VARCHAR NULL,
    sub_industry VARCHAR NULL,
    customer_type VARCHAR NULL,
    problem TEXT NULL,
    solution TEXT NULL,
    business_model VARCHAR NULL,
    price_min NUMERIC NULL,
    price_max NUMERIC NULL,
    price_currency VARCHAR NULL,
    price_period VARCHAR NULL,
    revenue_claim_amount NUMERIC NULL,
    revenue_claim_currency VARCHAR NULL,
    revenue_claim_period VARCHAR NULL,
    customer_count_claim INT NULL,
    technology JSONB NULL,
    distribution_channels JSONB NULL,
    geography JSONB NULL,
    claim_status VARCHAR NOT NULL,
    confidence NUMERIC NOT NULL,
    evidence_strength NUMERIC NULL,
    observed_at TIMESTAMPTZ NULL,
    status VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_signals_video_id
        FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE RESTRICT,
    CONSTRAINT fk_signals_comment_id
        FOREIGN KEY (comment_id) REFERENCES comments (id) ON DELETE RESTRICT,
    CONSTRAINT fk_signals_ai_extraction_id
        FOREIGN KEY (ai_extraction_id) REFERENCES ai_extractions (id) ON DELETE RESTRICT,
    CONSTRAINT ck_signals_source_type CHECK (source_type IN ('video', 'comment')),
    CONSTRAINT ck_signals_source_integrity CHECK (
        (
            source_type = 'video'
            AND video_id IS NOT NULL
            AND source_id = video_id
            AND comment_id IS NULL
        ) OR (
            source_type = 'comment'
            AND comment_id IS NOT NULL
            AND source_id = comment_id
            AND video_id IS NULL
        )
    ),
    CONSTRAINT ck_signals_signal_type CHECK (
        signal_type IN (
            'pain', 'demand', 'purchase_intent', 'revenue', 'pricing',
            'customer', 'product_launch', 'growth', 'competition',
            'distribution', 'workflow', 'technology', 'market_change',
            'complaint', 'feature_request', 'adoption'
        )
    ),
    CONSTRAINT ck_signals_statement_not_blank CHECK (btrim(statement) <> ''),
    CONSTRAINT ck_signals_claim_status CHECK (
        claim_status IN ('fact', 'creator_claim', 'inferred', 'opinion', 'speculation', 'unknown')
    ),
    CONSTRAINT ck_signals_confidence CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT ck_signals_evidence_strength CHECK (
        evidence_strength IS NULL OR (evidence_strength >= 0 AND evidence_strength <= 1)
    ),
    CONSTRAINT ck_signals_price_min_non_negative CHECK (price_min IS NULL OR price_min >= 0),
    CONSTRAINT ck_signals_price_max_non_negative CHECK (price_max IS NULL OR price_max >= 0),
    CONSTRAINT ck_signals_price_range CHECK (
        price_min IS NULL OR price_max IS NULL OR price_min <= price_max
    ),
    CONSTRAINT ck_signals_price_currency CHECK (
        (price_min IS NULL AND price_max IS NULL) OR price_currency IS NOT NULL
    ),
    CONSTRAINT ck_signals_revenue_claim_amount_non_negative CHECK (
        revenue_claim_amount IS NULL OR revenue_claim_amount >= 0
    ),
    CONSTRAINT ck_signals_revenue_claim_currency CHECK (
        revenue_claim_amount IS NULL OR revenue_claim_currency IS NOT NULL
    ),
    CONSTRAINT ck_signals_customer_count_claim_non_negative CHECK (
        customer_count_claim IS NULL OR customer_count_claim >= 0
    ),
    CONSTRAINT ck_signals_status CHECK (status IN ('active', 'review', 'ignored', 'rejected'))
);

CREATE INDEX idx_signals_signal_type ON signals (signal_type);
CREATE INDEX idx_signals_status ON signals (status);
CREATE INDEX idx_signals_observed_at ON signals (observed_at DESC);
CREATE INDEX idx_signals_video_id ON signals (video_id);
CREATE INDEX idx_signals_comment_id ON signals (comment_id);
CREATE INDEX idx_signals_ai_extraction_id ON signals (ai_extraction_id);
CREATE INDEX idx_signals_status_observed_at ON signals (status, observed_at DESC);

-- INTELLIGENCE: normalized FACT relationship.
CREATE TABLE opportunity_signal_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id UUID NOT NULL,
    signal_id UUID NOT NULL,
    relationship_type VARCHAR NOT NULL,
    confidence NUMERIC NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_opportunity_signal_links_opportunity_id
        FOREIGN KEY (opportunity_id) REFERENCES opportunities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_opportunity_signal_links_signal_id
        FOREIGN KEY (signal_id) REFERENCES signals (id) ON DELETE RESTRICT,
    CONSTRAINT uq_opportunity_signal_links_opportunity_signal
        UNIQUE (opportunity_id, signal_id),
    CONSTRAINT ck_opportunity_signal_links_relationship_type CHECK (
        relationship_type IN ('supporting', 'contradicting', 'context', 'candidate_match')
    ),
    CONSTRAINT ck_opportunity_signal_links_confidence CHECK (
        confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
    )
);

CREATE INDEX idx_opportunity_signal_links_signal_id
    ON opportunity_signal_links (signal_id);

-- INTELLIGENCE: presentation/research provenance.
CREATE TABLE opportunity_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id UUID NOT NULL,
    source_type VARCHAR NOT NULL,
    source_external_id VARCHAR NULL,
    signal_id UUID NULL,
    video_id UUID NULL,
    comment_id UUID NULL,
    evidence_type VARCHAR NOT NULL,
    summary TEXT NOT NULL,
    source_url TEXT NULL,
    strength NUMERIC NULL,
    confidence NUMERIC NULL,
    observed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_opportunity_evidence_opportunity_id
        FOREIGN KEY (opportunity_id) REFERENCES opportunities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_opportunity_evidence_signal_id
        FOREIGN KEY (signal_id) REFERENCES signals (id) ON DELETE RESTRICT,
    CONSTRAINT fk_opportunity_evidence_video_id
        FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE RESTRICT,
    CONSTRAINT fk_opportunity_evidence_comment_id
        FOREIGN KEY (comment_id) REFERENCES comments (id) ON DELETE RESTRICT,
    CONSTRAINT ck_opportunity_evidence_source_type CHECK (
        source_type IN ('youtube_video', 'youtube_comment', 'manual')
    ),
    CONSTRAINT ck_opportunity_evidence_source_integrity CHECK (
        (source_type = 'youtube_video' AND video_id IS NOT NULL AND comment_id IS NULL)
        OR (source_type = 'youtube_comment' AND comment_id IS NOT NULL)
        OR source_type = 'manual'
    ),
    CONSTRAINT ck_opportunity_evidence_evidence_type CHECK (
        evidence_type IN (
            'pain', 'demand', 'pricing', 'revenue', 'competition',
            'adoption', 'distribution', 'growth', 'market_context'
        )
    ),
    CONSTRAINT ck_opportunity_evidence_summary_not_blank CHECK (btrim(summary) <> ''),
    CONSTRAINT ck_opportunity_evidence_strength CHECK (
        strength IS NULL OR (strength >= 0 AND strength <= 1)
    ),
    CONSTRAINT ck_opportunity_evidence_confidence CHECK (
        confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
    )
);

CREATE INDEX idx_opportunity_evidence_opportunity_id
    ON opportunity_evidence (opportunity_id);
CREATE INDEX idx_opportunity_evidence_source_type
    ON opportunity_evidence (source_type);
CREATE INDEX idx_opportunity_evidence_source_external_id
    ON opportunity_evidence (source_type, source_external_id);
CREATE INDEX idx_opportunity_evidence_signal_id ON opportunity_evidence (signal_id);
CREATE INDEX idx_opportunity_evidence_video_id ON opportunity_evidence (video_id);
CREATE INDEX idx_opportunity_evidence_comment_id ON opportunity_evidence (comment_id);
CREATE INDEX idx_opportunity_evidence_observed_at ON opportunity_evidence (observed_at DESC);

-- INTELLIGENCE: append-only by application convention.
CREATE TABLE trend_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id UUID NOT NULL,
    window_type VARCHAR NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    video_count INT NOT NULL DEFAULT 0,
    new_video_count INT NOT NULL DEFAULT 0,
    unique_channel_count INT NOT NULL DEFAULT 0,
    total_views BIGINT NOT NULL DEFAULT 0,
    comment_count INT NOT NULL DEFAULT 0,
    pain_signal_count INT NOT NULL DEFAULT 0,
    demand_signal_count INT NOT NULL DEFAULT 0,
    purchase_intent_signal_count INT NOT NULL DEFAULT 0,
    revenue_signal_count INT NOT NULL DEFAULT 0,
    competitor_signal_count INT NOT NULL DEFAULT 0,
    momentum_score NUMERIC NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_trend_snapshots_opportunity_id
        FOREIGN KEY (opportunity_id) REFERENCES opportunities (id) ON DELETE RESTRICT,
    CONSTRAINT uq_trend_snapshots_opportunity_window_period
        UNIQUE (opportunity_id, window_type, period_start, period_end),
    CONSTRAINT ck_trend_snapshots_window_type CHECK (window_type IN ('7d', '30d', '90d')),
    CONSTRAINT ck_trend_snapshots_period_order CHECK (period_start < period_end),
    CONSTRAINT ck_trend_snapshots_video_count_non_negative CHECK (video_count >= 0),
    CONSTRAINT ck_trend_snapshots_new_video_count_non_negative CHECK (new_video_count >= 0),
    CONSTRAINT ck_trend_snapshots_unique_channel_count_non_negative CHECK (unique_channel_count >= 0),
    CONSTRAINT ck_trend_snapshots_total_views_non_negative CHECK (total_views >= 0),
    CONSTRAINT ck_trend_snapshots_comment_count_non_negative CHECK (comment_count >= 0),
    CONSTRAINT ck_trend_snapshots_pain_signal_count_non_negative CHECK (pain_signal_count >= 0),
    CONSTRAINT ck_trend_snapshots_demand_signal_count_non_negative CHECK (demand_signal_count >= 0),
    CONSTRAINT ck_trend_snapshots_purchase_intent_count_non_negative CHECK (
        purchase_intent_signal_count >= 0
    ),
    CONSTRAINT ck_trend_snapshots_revenue_signal_count_non_negative CHECK (revenue_signal_count >= 0),
    CONSTRAINT ck_trend_snapshots_competitor_signal_count_non_negative CHECK (
        competitor_signal_count >= 0
    ),
    CONSTRAINT ck_trend_snapshots_momentum_score CHECK (
        momentum_score IS NULL OR (momentum_score >= 0 AND momentum_score <= 100)
    )
);

CREATE INDEX idx_trend_snapshots_opportunity_window_period_end
    ON trend_snapshots (opportunity_id, window_type, period_end DESC);

-- INTELLIGENCE: reproducible, append-only score history by application convention.
CREATE TABLE opportunity_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id UUID NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL,
    scoring_version VARCHAR NOT NULL,
    trend_velocity_score NUMERIC NOT NULL,
    demand_evidence_score NUMERIC NOT NULL,
    revenue_evidence_score NUMERIC NOT NULL,
    pain_severity_score NUMERIC NOT NULL,
    competition_white_space_score NUMERIC NOT NULL,
    build_feasibility_score NUMERIC NOT NULL,
    distribution_ease_score NUMERIC NOT NULL,
    opportunity_score NUMERIC NOT NULL,
    confidence_score NUMERIC NULL,
    hype_risk_score NUMERIC NULL,
    inputs_snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_opportunity_scores_opportunity_id
        FOREIGN KEY (opportunity_id) REFERENCES opportunities (id) ON DELETE RESTRICT,
    CONSTRAINT uq_opportunity_scores_opportunity_version_calculated
        UNIQUE (opportunity_id, scoring_version, calculated_at),
    CONSTRAINT ck_opportunity_scores_scoring_version_not_blank CHECK (btrim(scoring_version) <> ''),
    CONSTRAINT ck_opportunity_scores_trend_velocity CHECK (
        trend_velocity_score >= 0 AND trend_velocity_score <= 100
    ),
    CONSTRAINT ck_opportunity_scores_demand_evidence CHECK (
        demand_evidence_score >= 0 AND demand_evidence_score <= 100
    ),
    CONSTRAINT ck_opportunity_scores_revenue_evidence CHECK (
        revenue_evidence_score >= 0 AND revenue_evidence_score <= 100
    ),
    CONSTRAINT ck_opportunity_scores_pain_severity CHECK (
        pain_severity_score >= 0 AND pain_severity_score <= 100
    ),
    CONSTRAINT ck_opportunity_scores_competition_white_space CHECK (
        competition_white_space_score >= 0 AND competition_white_space_score <= 100
    ),
    CONSTRAINT ck_opportunity_scores_build_feasibility CHECK (
        build_feasibility_score >= 0 AND build_feasibility_score <= 100
    ),
    CONSTRAINT ck_opportunity_scores_distribution_ease CHECK (
        distribution_ease_score >= 0 AND distribution_ease_score <= 100
    ),
    CONSTRAINT ck_opportunity_scores_opportunity_score CHECK (
        opportunity_score >= 0 AND opportunity_score <= 100
    ),
    CONSTRAINT ck_opportunity_scores_confidence_score CHECK (
        confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)
    ),
    CONSTRAINT ck_opportunity_scores_hype_risk_score CHECK (
        hype_risk_score IS NULL OR (hype_risk_score >= 0 AND hype_risk_score <= 100)
    ),
    CONSTRAINT ck_opportunity_scores_inputs_snapshot_object CHECK (
        jsonb_typeof(inputs_snapshot) = 'object'
    )
);

CREATE INDEX idx_opportunity_scores_opportunity_id_calculated_at
    ON opportunity_scores (opportunity_id, calculated_at DESC);

-- INTELLIGENCE: human review queue. target_type/target_id is the narrow,
-- service-enforced polymorphic exception and is restricted to known values.
CREATE TABLE review_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_type VARCHAR NOT NULL,
    target_type VARCHAR NOT NULL,
    target_id UUID NOT NULL,
    status VARCHAR NOT NULL,
    priority NUMERIC NOT NULL,
    assigned_to UUID NULL,
    decision VARCHAR NULL,
    decision_notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ NULL,
    CONSTRAINT fk_review_tasks_assigned_to
        FOREIGN KEY (assigned_to) REFERENCES user_profiles (id) ON DELETE SET NULL,
    CONSTRAINT ck_review_tasks_review_type CHECK (
        review_type IN (
            'signal_validation', 'opportunity_match', 'opportunity_merge',
            'opportunity_creation', 'hype_review', 'quality_review'
        )
    ),
    CONSTRAINT ck_review_tasks_target_type CHECK (target_type IN ('signal', 'opportunity')),
    CONSTRAINT ck_review_tasks_status CHECK (
        status IN ('pending', 'in_review', 'resolved', 'ignored')
    ),
    CONSTRAINT ck_review_tasks_priority_non_negative CHECK (priority >= 0),
    CONSTRAINT ck_review_tasks_decision CHECK (
        decision IS NULL OR decision IN ('approve', 'merge', 'create_new', 'reject', 'ignore', 'defer')
    ),
    CONSTRAINT ck_review_tasks_resolution_state CHECK (
        (
            status IN ('pending', 'in_review')
            AND resolved_at IS NULL
        ) OR (
            status IN ('resolved', 'ignored')
            AND resolved_at IS NOT NULL
            AND decision IS NOT NULL
        )
    ),
    CONSTRAINT ck_review_tasks_resolved_at_order CHECK (
        resolved_at IS NULL OR resolved_at >= created_at
    )
);

CREATE UNIQUE INDEX uq_review_tasks_open_target
    ON review_tasks (review_type, target_type, target_id)
    WHERE status IN ('pending', 'in_review');

CREATE INDEX idx_review_tasks_status_priority_created_at
    ON review_tasks (status, priority DESC, created_at);
CREATE INDEX idx_review_tasks_target_type_target_id
    ON review_tasks (target_type, target_id);
CREATE INDEX idx_review_tasks_assigned_to_status
    ON review_tasks (assigned_to, status);

-- INTELLIGENCE: non-destructive opportunity merge lineage. Cycle and canonical
-- state validation require a transaction in the application/service layer.
CREATE TABLE opportunity_merge_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_opportunity_id UUID NOT NULL,
    canonical_opportunity_id UUID NOT NULL,
    merged_at TIMESTAMPTZ NOT NULL,
    merged_by UUID NULL,
    reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_opportunity_merge_history_source_opportunity_id
        FOREIGN KEY (source_opportunity_id) REFERENCES opportunities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_opportunity_merge_history_canonical_opportunity_id
        FOREIGN KEY (canonical_opportunity_id) REFERENCES opportunities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_opportunity_merge_history_merged_by
        FOREIGN KEY (merged_by) REFERENCES user_profiles (id) ON DELETE SET NULL,
    CONSTRAINT ck_opportunity_merge_history_distinct_opportunities CHECK (
        source_opportunity_id <> canonical_opportunity_id
    )
);

CREATE INDEX idx_opportunity_merge_history_source_opportunity_id
    ON opportunity_merge_history (source_opportunity_id);
CREATE INDEX idx_opportunity_merge_history_canonical_opportunity_id
    ON opportunity_merge_history (canonical_opportunity_id);
CREATE INDEX idx_opportunity_merge_history_merged_at
    ON opportunity_merge_history (merged_at DESC);

-- INTELLIGENCE: private, individual-user watchlists.
CREATE TABLE watchlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_profile_id UUID NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_watchlists_user_profile_id
        FOREIGN KEY (user_profile_id) REFERENCES user_profiles (id) ON DELETE RESTRICT,
    CONSTRAINT ck_watchlists_name_not_blank CHECK (btrim(name) <> '')
);

CREATE UNIQUE INDEX uq_watchlists_user_profile_name
    ON watchlists (user_profile_id, lower(name));

CREATE TABLE watchlist_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watchlist_id UUID NOT NULL,
    opportunity_id UUID NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_watchlist_items_watchlist_id
        FOREIGN KEY (watchlist_id) REFERENCES watchlists (id) ON DELETE CASCADE,
    CONSTRAINT fk_watchlist_items_opportunity_id
        FOREIGN KEY (opportunity_id) REFERENCES opportunities (id) ON DELETE RESTRICT,
    CONSTRAINT uq_watchlist_items_watchlist_opportunity UNIQUE (watchlist_id, opportunity_id)
);

CREATE INDEX idx_watchlist_items_opportunity_id ON watchlist_items (opportunity_id);

COMMIT;
