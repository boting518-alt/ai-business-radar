# Signals + Watchlist UI v0.1

## Signals page

`/signals` is a dense chronological feed of active commercial signals. It displays the canonical
signal type, statement, evidence excerpt, industry, customer type, claim status, confidence,
evidence strength, observed time, safe source type and video title, plus links to active related
opportunities. Creator claims remain explicitly labeled and confidence is supporting extraction
metadata, not a probability that a claim is true.

The page calls only `GET /api/v1/signals`; it does not fetch comments, videos, or opportunities per
row. Supported URL filters are `signal_type`, `industry`, `customer_type`, `opportunity_id`, and
`observed_after`, with `offset` and `limit` pagination. Applying or clearing filters resets the
offset. The default page size is 25, and a full page is the only indication that another page may
exist because the endpoint has no total count.

The projection and UI exclude comment author identity, author hashes, provider identifiers, raw AI
output, extraction state/errors, and internal database identifiers except the opportunity ID needed
for navigation. Loading, unfiltered-empty, filtered-empty, authentication, authorization, retry,
and request-ID error states are explicit.

## Personal watchlist semantics

v0.1 exposes one logical personal watchlist while preserving the existing multi-watchlist schema.
The backend deterministically uses the user's earliest watchlist. If none exists, the first valid
add creates `Watchlist`; listing an empty account does not create data. Ownership always comes from
the authenticated `CurrentUser`, never from a request parameter.

`GET /api/v1/watchlist` returns product-ready active opportunities with current `score-v001` values
and the latest `trend-v001` 7-day momentum in bounded set queries. It makes no per-opportunity API
or database query. `POST /api/v1/watchlist/items/{opportunity_id}` validates product visibility and
is idempotent. `DELETE` is also idempotent, hard-deletes only membership, and cannot address another
user's list. Existing RLS policies remain unchanged.

Radar, opportunity detail, and `/watchlist` reuse `WatchlistButton`. State changes only after the
backend confirms the mutation. Buttons disable while pending and expose safe inline success/error
feedback with request IDs. The watchlist page removes a row after confirmed deletion and links each
opportunity to its dossier. Desktop uses a compact table; mobile prioritizes name, stage, score,
momentum, and removal in stacked cards.

## Known limitations

Signals have no total count and opportunity context currently provides IDs rather than names in the
feed projection. The MVP does not expose multiple-list management, ordering, renaming, sharing,
notifications, or score-change deltas. The watchlist shows current score and momentum rather than
historical deltas because the product API has no frozen delta field. PostgreSQL integration tests
require `POSTGRES_TEST_ADMIN_URL`.
