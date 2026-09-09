# TASK-044E validation — 2026-09-09

## Revision and implementation

Revised task: `docs/tasks/TASK-044E.md`. The revision corrects nonexistent link status,
record-only deduplication, supporting vs linked counts, global active-Signal visibility, canonical
intelligence vs RAW source text, and honest URL availability semantics.

Implemented SQL read projection over linked active Signals plus eligible explicit evidence. No
migration, backfill, paid source/LLM calls, Signal classification change, score recalculation, or
opportunity publication. Existing manual evidence storage is retained.

## Reproduced baseline and real result

Local database: ai_business_radar_live_test. Read-only baseline before implementation:

| Dental measure | Before | After |
| --- | ---: | ---: |
| Active linked Signals | 40 | 40 |
| Supporting linked Signals | 40 | 40 |
| Distinct videos | 4 | 4 |
| Distinct channels | 4 | 4 |
| Explicit opportunity_evidence rows | 0 | 0 |
| Available evidence in detail read model | 0 | 40 |
| First evidence page | 0 | 20 (has_more=true) |

Opportunity: `7eea70c0-eeee-4db5-9cd0-ca73dcd42861`, slug
`ai-receptionist-and-appointment-lead-workflow-management-for-dental-practices`.

Example persisted trace:

- Signal `0a8529d9-ba73-44a9-9f87-ff8fe2208a1f`, type pain, creator_claim, supporting.
- Canonical statement: The creator identifies reception overload as a problem for dental practices.
- Stored zh-CN statement and excerpt are returned; toggle reveals canonical English.
- Video `5d17d344-67de-49e6-a528-b63d663d5a11`, YouTube `38ZxuCL9bac`, aiconnectpro.
- Source observation: 2026-09-07T09:14:09Z.
- URL: https://www.youtube.com/watch?v=38ZxuCL9bac.
- Real browser click opened YouTube with the matching Dental AI Receptionist Demo title and
  aiconnectpro channel. Autoplay was paused. This validates this example, not every remote source.

Micro Duck baseline includes active video `947759ae-4d7e-4166-b8b6-fc27854643f8` from
`i_IMO0knP3I` and purchase-intent comment `1f94b9aa-fd70-4629-bd69-105898c25200` from
`9_cH8DVQ7Zs`, stored YouTube comment `UgwPZwAXJ4IU2Vu7Z1p4AaABAg`.
These remain globally visible without requiring active opportunity links.

## Automated validation

- API: 188 passed; 70 PostgreSQL-dependent cases skipped in this run and executed separately.
- Complete PostgreSQL integration suite: 70 passed in an isolated automatically cleaned DB.
- Final source-parent/navigation change: targeted PostgreSQL evidence regression passed again.
- Worker: 23 passed.
- Shared Python schemas: 59 passed using the API virtualenv (the schemas local env is stale).
- Frontend: 76 tests passed across 11 files; final typecheck and ESLint passed.
- API and worker Ruff passed. Final source/API targeted tests: 14 passed.
- Next.js production build (webpack): passed; all existing product/admin routes generated.
- git diff --check: passed. Generated next-env.d.ts unchanged.

Total distinct suite tests: 416 (188 + 70 + 23 + 59 + 76); targeted reruns are not extra coverage.
Existing dependency deprecation/config-loader warnings remain; no failing checks.

Evidence integration covers SQL union, no copied rows, active/rejected/ignored/review visibility,
candidate 404, linked vs supporting counts, contradiction/context, original comment and parent video,
stored localized text, stale fallback, same-source/same-text distinct Signals retained, exact Signal
reference dedupe, manual evidence retained, null observation ordering, empty/out-of-range pagination,
Signal type filter, public-field safety and malformed source identity. The zh-CN evidence query
count is four for one item and the whole fixture (visibility + count + page + one localization batch).

Frontend tests cover explicit links/target/rel, original-text toggle, RAW comment separation,
localized claim/relationship/type labels, English labels, safe missing source, unsafe URL rejection,
related Signals URL context, filter resets, bounded pagination, and empty states.

## Browser execution notes

Browser uses existing admin@test.com session on ordinary product pages. Separate normal-user login
is not claimed; endpoint auth tests exercise user/admin and PostgreSQL tests enforce product
visibility. Full dual-role login E2E remains TASK-046.

The initial development runtime intermittently returned `Failed to fetch` in the browser even
while server diagnostics showed the four detail endpoints returning200 with correct CORS headers.
Temporary endpoint/error and middleware diagnostics were fully removed. System Chrome automation
also stalled for an extended period; the original local runtime stopped during that interval.
Only API and frontend were restarted for validation, without worker/scheduler or ingestion jobs.
Production build browser validation successfully rendered Dental totals, 20 evidence cards,
Chinese statement/excerpt, claim and relationship, original English toggle and source navigation.
The intermittent browser transport failure is not declared fixed by this task.

Final browser checks also passed in the production frontend:

- Dental English All types reports 40; Pain reports 10; returning to All restores 40.
- Next displays the second evidence page with older records; Previous is enabled and Next disabled.
- View all related Signals opens the UUID-filtered feed with the correct opportunity name and link.
- Micro Duck purchase-intent comment renders in both locales with parent-video title/channel,
  expanded stored RAW comment and the absence of a published opportunity made explicit.
- Chinese comment's original-text toggle displays the canonical English statement and excerpt:
  "Price with shipping is $508. I still ordered one. It's so cool!"

Implementation and local validation are complete. The reviewed commit excludes unrelated artifacts;
no push is performed.

## Remaining scope limitations

No historical semantic merging/version repair (TASK-044F). No assertion of independent source
corroboration. No live remote-deletion monitoring or precise comment anchor. Explicit standalone
records have no Signal type and appear under All; filtered total is not linked-signal count.
Page-level URL/locale changes continue to refresh the existing four API reads together.
No staging/production-readiness claim. No unrelated audit/infographic artifacts included in commit.
