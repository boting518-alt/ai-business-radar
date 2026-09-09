# Development Plan

## Current Phase

Phase 6 — Live Validation / Product Activation

MVP STATUS: READY WITH KNOWN GAPS

## Completed

- [x] TASK-001 Repository Bootstrap
- [x] TASK-002 Product Specification
- [x] TASK-003 Architecture Baseline
- [x] TASK-004 Database Domain Model
- [x] TASK-005 Initial SQL Migration
- [x] TASK-006 Shared Domain Schemas
- [x] TASK-007 Backend Application Skeleton
- [x] TASK-008 Database Repository Layer
- [x] TASK-009 Supabase Auth + RLS Baseline
- [x] TASK-010 YouTube API Client
- [x] TASK-011 YouTube Discovery Pipeline
- [x] TASK-012 Metadata / Snapshot Collection
- [x] TASK-013 Comment Collection
- [x] TASK-014 Collection Worker Runtime
- [x] TASK-015 Relevance Filter Pipeline
- [x] TASK-016 Signal Extraction Pipeline
- [x] TASK-017 Comment Pain Mining Pipeline
- [x] TASK-018 Opportunity Normalization Pipeline
- [x] TASK-019 Trend Aggregation
- [x] TASK-020 Opportunity Scoring
- [x] TASK-021 Review Workflow Service
- [x] TASK-022 Radar Query API
- [x] TASK-023 Frontend Skeleton
- [x] TASK-024 Radar Page
- [x] TASK-025 Opportunity Detail Page
- [x] TASK-026 Admin Review UI
- [x] TASK-027 Signals + Watchlist UI
- [x] TASK-028 End-to-End MVP QA
- [x] TASK-029 Local Live API & Intelligence Validation
- [x] TASK-029A OpenAI Structured Output Schema Compatibility Fix
- [x] TASK-029B Local Validation Search Query Taxonomy Fix
- [x] TASK-030 Supabase Project Compatibility & Auth/RLS Readiness Check
- [x] TASK-031 Local Product Activation & UI Polish (activation blocked pending a specified candidate-to-active workflow)
- [x] TASK-032 Opportunity Activation Readiness + Publish Workflow
- [x] TASK-033 Signal Semantics + Intelligence Localization Foundation
- [x] TASK-034 Intelligence Translation Worker v0.1
- [x] TASK-035 Local Intelligence Quality Review + Prompt Tuning
- [x] TASK-036 Broader Discovery + Cross-Source Intelligence Validation
- [x] TASK-037 Semantic Separation + Low-Overlap Retrieval Validation
- [x] TASK-038 Hybrid Retrieval Offline Prototype + Prompt Fix Plan
- [x] TASK-039 Promote Signal Extractor v003 + Runtime Version Governance
- [x] TASK-040 Industry + Customer Taxonomy Foundation
- [x] TASK-041 Hosted Supabase Auth + RLS Drill
- [x] TASK-042 Automatic Intelligence Translation Orchestration

## Next

- [x] TASK-043 Opportunity Library v0.1
- [x] TASK-044 Discovery Operations Console v0.1
- [x] TASK-044A Discovery Run Reliability + Run Now UX Fix
- [x] TASK-044B Discovery Topic Execution Batch + Polling Correctness Fix
- [x] TASK-044C Runtime Configuration Consistency + Discovery Worker Finalization
- [x] TASK-044D Discovery-to-Intelligence Pipeline Orchestration
- [x] TASK-044E Evidence Chain + Source Traceability (validated locally; see artifacts/evidence-chain/2026-09-09/validation-report.md)
- [x] TASK-044F Signal Semantic Guardrails + Historical Quality Repair (validated locally; see artifacts/signal-semantic-quality/2026-09-09/validation-report.md)
- [x] TASK-044G Candidate Opportunity Review & Activation Workspace — local validation complete; see [report](../artifacts/candidate-activation-workspace/2026-09-09/validation-report.md)
- [x] TASK-044H Opportunity Thesis & Business Case Consolidation — 528 tests, 8-case real-provider validation and authorized full canonical launcher smoke passed; local acceptance complete ([report](../artifacts/opportunity-business-case/2026-09-09/validation-report.md))
- [ ] TASK-044I Discovery Console Operational Completion
- [ ] TASK-044J Watchlist Change Tracking + Monitoring Freshness
- [ ] TASK-044K Taxonomy Selectors + Review UX + Localization Polish
- [ ] TASK-045 Staging Infrastructure Deployment
- [ ] TASK-046 Staging Full Integration + Dual-role E2E
- [ ] TASK-047 Hybrid Retrieval Runtime Prototype
- [ ] TASK-048 AI-Assisted Taxonomy Mapping + Review

## Validation debt

No local validation debt. All migrations, API/PostgreSQL integration tests, shared schemas, workers,
frontend checks, and a real local Redis broker smoke test passed during TASK-028. Live YouTube,
OpenAI, staging infrastructure, and production deployment verification remain explicit environment
gaps. Hosted development Supabase Auth/JWKS/RLS was validated in TASK-041.

## Deferred

TASK-039 does not mark the product production-ready.

- Reddit integration
- GitHub integration
- Product Hunt integration
- Google Trends integration
- Billing
- Team accounts
- Public API
- Mobile application
