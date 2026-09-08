# Discovery Console Reliability Validation

- Root cause: Pydantic validation occurred before `YouTubeDiscoveryService.discover`; generic
  permanent-error handling swallowed the exception without the pre-created run ID, leaving pending
  rows protected by the in-flight unique index.
- Repair: discovery-specific permanent error handling now records a safe failed terminal state;
  stale pending/running recovery is bounded, dry-runnable, idempotent, and scheduled.
- Stuck run before repair: 12 Micro Duck pending rows were preserved; dry-run reported 12 and wrote
  nothing, then actual recovery marked the same 12 failed with `stale_run_recovered`.
- Permanent failure test: `max_pages=99` finalized run `17916dfa-e2be-4d26-b927-e91ad5d37307`
  as failed with a safe field-level message, completed timestamp, and `invalid_discovery_request`.
- Subsequent Run Now: immediately created a new queued run after that failure; the validation-only
  follow-up was then safely finalized rather than left active.
- Subsequent Run Now: terminal failed/partial/completed rows are outside the unique index.
- UI: scoped Queuing state, disabled styling, immediate Queued notice, three-second active polling,
  topic progress, action-specific failures, and 409 domain messaging are covered by tests.
- 201 Create: the shared API client accepts every `response.ok` 2xx result and the UI refreshes.
- Micro Duck validation: a bounded real worker run completed with 5 videos and 1 estimated quota
  unit after stale recovery; no historical records were deleted.
- Limitation: worker liveness remains unknown; transient retry exhaustion is ultimately repaired by
  conservative stale recovery because Dramatiq has no persisted worker heartbeat in v0.1.
