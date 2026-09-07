# Intelligence Localization v0.1

## Two separate localization systems

Fixed interface text uses the frontend's typed, in-repository dictionaries for `zh-CN` and
`en-US`. The default is Chinese, the header selector changes language, and the browser stores the
choice under `ai-business-radar.locale`. The provider renders Chinese initially on server and
client, then applies a saved preference after hydration to avoid a mismatch. A later authenticated
preference may move this setting server-side.

Dynamic Signals and Opportunities are intelligence content, not UI copy. English is the v0.1
canonical language. Translations are stored projections in `intelligence_localizations`; canonical
records remain authoritative and historical records are not rewritten.

## Storage and lookup

Each projection identifies `entity_type`, `entity_id`, `field_name`, `locale`, source hash, and
translation version. It stores translated text, lifecycle status, optional provider/model lineage,
and timestamps. The version-safe unique constraint prevents duplicate runs while allowing a new
source hash or translation version. Signal fields are `statement`, optional `evidence_text`,
`industry`, and `customer_type`. Opportunity fields are `name`, `one_line_thesis`, `industry`,
`customer_type`, `problem`, and `solution`.

`IntelligenceLocalizationService` hashes the current canonical field using SHA-256. A matching
`current` record supplies the projection. A missing record returns canonical English. A mismatched
hash or non-current record is internally marked stale and also falls back to canonical content.
Fallback never blocks rendering.

Product reads accept an explicit `locale=zh-CN|en-US` query on `/signals`, `/radar`,
`/opportunities`, and `/opportunities/{identifier}`. The API defaults to canonical `en-US`; the
frontend always sends its active locale. Read paths query the database only and must never invoke
OpenAI or another translation provider.

## Evidence and proper names

Original evidence is always returned separately from a translated projection. Chinese UI labels a
translated excerpt as translated and offers `查看原文`; it never replaces or misrepresents the source
quotation. UUIDs, enums, scores, confidence, source IDs, URLs, company/product names, channel names,
and video titles are not localized. Brand preservation remains the default even inside prose.

RLS permits authenticated reads only when the corresponding signal or opportunity is active;
admins retain review visibility. Product repositories independently enforce active opportunity
visibility, so candidate/rejected localization cannot enter Radar or linked-opportunity output.

## Future direction

TASK-034 may add an explicit worker/admin batch job that writes auditable projections. It must not
run from a GET request. Industry and customer free text should later migrate to stable taxonomy
codes with per-locale labels; TASK-033 deliberately performs no automatic taxonomy mapping.
