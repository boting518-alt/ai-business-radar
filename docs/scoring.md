# Opportunity Scoring

Status: score-v001 frozen

The application—not an LLM—calculates Opportunity Score, Confidence Score, and Hype Risk from
persisted trend and FACT evidence. Scores remain in `opportunity_scores`; opportunity base rows and
market stage are never mutated by scoring.

## Trend momentum v0.1

`trend-v001` is a deterministic trend aggregate, not the final Opportunity Score. It counts only
active signals connected through `opportunity_signal_links`, using `observed_at` with `created_at`
as fallback and half-open UTC windows (`start <= event < end`). Comment signals resolve to their
parent canonical video. `video_count` is distinct contributing videos; `new_video_count` is the
subset whose `first_seen_at` is inside the window; channels are distinct. `comment_count` counts
persisted RAW comments published in the window. `total_views` sums each contributing video's latest
non-null snapshot strictly before the window end and excludes videos without one.

Momentum compares the current window with the immediately preceding equal window. For signal,
signal, new-video, channel, and view values, the bounded component is:

`clamp(50 + (50 / ln(2)) * ln((current + 1) / (previous + 1)), 0, 100)`

Weights are signal 35%, video 30%, channel 20%, and views 15%. If no earlier active linked signal
exists, all components use neutral 50. View growth also uses neutral 50 when any contributing video
lacks a qualifying snapshot at its comparison boundary. Results are rounded to two decimals.
Pain, demand, purchase-intent, revenue, and competition counts use exact signal taxonomy values;
no heuristic category merging, AI calculation, market-stage mutation, or final scoring occurs.

## Score version and final weights

`SCORING_VERSION = score-v001`. Formula changes require a new version. Components are combined
without intermediate rounding and persisted to two decimals:

| Component | Weight |
| --- | ---: |
| Trend Velocity | 20% |
| Demand Evidence | 20% |
| Revenue Evidence | 15% |
| Pain Severity | 15% |
| Competition White Space | 10% |
| Build Feasibility | 10% |
| Distribution Ease | 10% |

Confidence and Hype Risk are not inputs to Opportunity Score.

## Shared normalization

Count features use diminishing returns: `sat(count, scale) = 100 × (1 - exp(-count / scale))`.
Every score is clamped to `0..100`. Only active signals linked through
`opportunity_signal_links` participate. Comment signals resolve to their parent video; source
diversity uses distinct video/channel IDs and never author identity.

## Seven components

Trend Velocity uses the newest `trend-v001` snapshot in fallback order `7d`, `30d`, `90d`, taking
its stored momentum unchanged. No available trend means neutral 50.

Demand Evidence is `30% sat(purchase_intent,2) + 25% sat(demand,3) + 15% sat(adoption,3) + 10%
sat(feature_request,3) + 10% sat(workflow+complaint,4) + 10% diversity`. Diversity is the mean of
`sat(distinct videos,4)` and `sat(distinct channels,3)`.

Revenue Evidence assigns type weights revenue 1.0, pricing 0.7, customer 0.6, adoption 0.5, then
multiplies by claim quality: fact 1.00, creator claim 0.40, inferred/unknown 0.20, opinion 0.10,
speculation 0.05. Its formula is `70% sat(weighted evidence,3) + 15% sat(explicit numeric
evidence,2) + 15% diversity`. Monetary values are evidence-presence flags; they are never converted
to ARR or compared across unresolved currencies/periods.

Pain Severity is an evidence proxy, not true economic severity: `30% sat(pain,4) + 20%
sat(workflow,4) + 20% sat(price/spend evidence,3) + 15% sat(complaint,3) + 15%
sat(purchase_intent when pain exists,2)`.

Competition pressure is `sat(competition + product_launch,5)`. White Space uses linear
interpolation through explicit `(pressure, score)` points: `(0,55)`, `(25,85)`, `(45,100)`,
`(70,65)`, `(100,20)`. Thus absent competition is not maximum and saturation is penalized.

Build Feasibility starts at 50 only when structured fields exist. API, software, SaaS, automation,
cloud, no-code, and LLM tokens add 10 each, capped at +30. Hardware, robotics, device,
manufacturing, and proprietary-data tokens subtract 20 each, capped at -40. Healthcare, finance,
legal, or government context subtracts 10. Missing structured evidence is neutral 50.

Distribution Ease starts at 50. SMB/small/local business adds 15; enterprise subtracts 15;
government subtracts 25. Self-serve/SaaS/subscription adds 10; agency/marketplace business models
add 10. Marketplace, community, outbound, partner, and agency channel evidence adds 5 each, capped
at +20. Missing structured evidence is neutral 50.

## Confidence Score

Confidence is `25% evidence volume + 25% source diversity + 20% freshness + 15% claim quality +
15% agreement`. Volume is `sat(active signals,8)`. Diversity is the video/channel diversity above,
with +10 (capped at 100) when both video- and comment-derived evidence exist. Freshness steps are:
latest evidence <=7d: 100; <=30d: 70; <=90d: 40; <=180d: 20; older: 10; absent: 0. Claim quality
is the mean claim weight. When no contradicting link exists, agreement remains neutral 50 rather
than pretending contradiction detection is complete; otherwise it is the supporting share.

## Hype Risk Score

Attention is `40% Trend Velocity + 30% sat(trend video_count,5) + 30%
sat(trend total_views,100000)`. Commercial evidence is `40% Demand + 30% Revenue + 30% Pain`.
Hype Risk is `clamp(50 + 0.60 × (attention - commercial), 0, 100)`. It is deterministic and does
not invoke HypeDetector.

## Reproducibility, history, and missing data

`inputs_snapshot` stores scoring/evaluation time, selected trend ID/window/version and metrics,
signal IDs/types/claim states, type and claim counts, relationship counts, distinct-source metrics,
freshness, explicit numeric evidence, and structured build/distribution inputs. Re-running the pure
`score-v001` engine with that JSON reproduces all persisted scores.

Canonical sorted JSON is SHA-256 hashed, including scoring reference time because freshness depends
on it. Normal execution rounds reference time down to the UTC hour and reuses identical
`(opportunity, version, input_hash)` rows. Force uses the exact current UTC time, normally producing
a new append-only history row. Sparse evidence still scores: missing trend/build/distribution are
neutral while Confidence remains conservative. Eligible statuses are candidate, active, and review;
merged, rejected, and archived opportunities are excluded.

## v0.1 limitations

Pain is a proxy without separate urgency/risk/cost taxonomy. Competition counts evidence rather
than unique named competitors. Build and distribution rules use only structured fields and are
deliberately conservative. Contradiction coverage is incomplete. TASK-021 owns review decisions;
TASK-022 owns current-score Radar reads.
