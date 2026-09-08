# Discovery Console Validation Report

- Topic fixture: AI Dental Front Desk (manual, paused; not retained as a production seed)
- Intended queries: `AI dental receptionist`, `dental AI phone agent`
- Bounds: 5 videos, 1 page, 10 comments/video
- Scheduler: existing APScheduler due-topic polling path covered by worker tests
- Manual run: completed through the real worker execution path; 5 unique videos from 1 page
- Quota: 1 estimated unit persisted for the completed run
- Worker execution: run `d31dda7b-9a70-4ecf-8b8b-604a1b05a92e` completed
- Duplicate prevention: immediate second queue attempt returned `DiscoveryConflict`
- Failure: existing discovery service persists safe failed/partial outcomes and remains retry-bounded
- UI: admin route, create form, multiple query editor, actions, status and quota projections added
- Live provider run: official YouTube API completed with the strict 5-video limit
- Scheduled live run: not executed because the shared database contains legacy enabled queries;
  invoking the scheduler would enqueue those unrelated queries. Scheduler behavior is covered by
  isolated tests and the validation topic remains paused/manual.
- Known gaps: worker liveness unknown; no downstream per-run attribution; no arbitrary cron
