begin;

alter table discovery_topic_runs
  add column intelligence_status text not null default 'not_started'
    check (intelligence_status in ('not_started', 'queued', 'processing', 'completed', 'partial', 'failed')),
  add column intelligence_metrics jsonb not null default '{}'::jsonb,
  add column intelligence_error_summary text,
  add column intelligence_started_at timestamptz,
  add column intelligence_completed_at timestamptz;

create index idx_discovery_topic_runs_intelligence_status
  on discovery_topic_runs (intelligence_status, created_at);

commit;
