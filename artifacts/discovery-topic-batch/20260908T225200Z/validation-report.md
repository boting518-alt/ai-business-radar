# TASK-044B live browser validation

- Validated: 2026-09-08 (Asia/Shanghai)
- Page: `http://localhost:3000/admin/discovery`
- Browser: Google Chrome driven by Playwright Core
- Topic: `Micro Duck Trend Spillover`
- Topic batch: `57e4781a-df41-439f-8af8-572c2583f07b`
- Bounds: max videos 5, max pages 1, max comments/video 10
- Enabled queries: 12

## Recovery prerequisite

The first browser attempt exposed 12 legacy ungrouped runs left `pending` beyond the 15-minute
stale threshold. The existing recovery endpoint marked all 12 failed. No Topic batch was created
by that failed attempt.

## Successful browser flow

The subsequent authorized browser click produced HTTP 202 and exactly one Topic batch. The page
rendered `queued · 0 / 12 complete`, displayed all 12 child queries, and disabled Run Now. It then
reached `completed · 12 / 12 complete`, displayed every child as completed, showed quota 12, and
restored Run Now.

Captured discovery traffic:

- Topic Run POST requests: 1
- Batch polling paths: only
  `/api/v1/admin/discovery/topic-runs/57e4781a-df41-439f-8af8-572c2583f07b`
- Historical `/runs` polling requests: 0
- HTTP statuses: 200 and 202 only

Database verification: requested 12, queued 12, child count 12, completed 12, failed 0,
estimated quota units 12. Temporary validation admin credentials and profile were deleted.

Screenshot: `browser-terminal.png`.
