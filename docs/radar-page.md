# Radar Page v0.1

## Purpose and information hierarchy

`/radar` is the authenticated landing page for comparing active AI business opportunities. Its
priority is opportunity identity, persisted Opportunity Score, momentum, Confidence, Hype Risk,
market stage, evidence summary, and last activity. The small summary bar describes only the
current response page and qualifying total; it is not presented as a global market statistic.

## Data contract and fetching

The page uses the centralized authenticated `ApiClient.getRadar()` boundary and the backend
`RadarResponse` model. One request supplies every displayed row; the page does not fetch detail,
evidence, or trend history per opportunity. Frontend types mirror the current backend compact
model, including nested trend and evidence summary fields.

The browser displays persisted Opportunity Score, Confidence, Hype Risk, momentum, and market
stage without recomputation or inference. Opportunity Score is the deterministic composite
commercial ranking. Confidence describes supporting-evidence strength and coverage, not business
success probability. Hype Risk increases when attention outweighs commercial evidence. Momentum
is recent trend activity for the selected window.

## URL state, filters, sorting, and pagination

The default query is `window_type=7d`, `sort=score`, `direction=desc`, `offset=0`, and `limit=25`.
The page supports 7d, 30d, and 90d windows plus `q`, `industry`, `business_model`,
`customer_type`, `market_stage`, `score_min`, `confidence_min`, and `hype_max`. Search and filters
are submitted explicitly. Industry, business model, and customer type are text inputs because the
API has no taxonomy enumeration endpoint; stage uses the frozen v0.1 values.

Score, momentum, Confidence, Hype Risk, and recent sorting are sent to the backend. No returned
page is sorted locally. Filter, window, and sort changes reset offset, while Previous and Next
advance through the backend offset/limit contract.

## Missing values and interface states

Null score, Confidence, Hype Risk, or momentum renders as `—`; no fallback number or direction is
invented. Loading uses an in-place table skeleton. Errors provide safe text, retry, and the API
request ID when present; 401 redirects to login and 403 receives an access message. An empty
unfiltered response says that no scored opportunities are available, while a filtered empty
response offers to clear filters. No production fixtures or sample opportunities are rendered.

## Responsive behavior and detail transition

Large screens use a semantic sortable table. Smaller screens use stacked compact records that
prioritize Score, momentum, Confidence, and Hype Risk without horizontal overflow. Opportunity
names link to the implemented evidence-backed `/opportunities/{slug}` dossier. Watchlist
membership remains read-only.

## Known limitations

- Filters accept one exact value per classification field in the current UI, although the API can
  accept repeated values.
- The summary averages describe only the returned page.
- No watchlist mutation, chart, or saved view is included.
