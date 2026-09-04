# Opportunity Scoring

Status: Placeholder

This document will define the deterministic Opportunity Score calculated by application code. No scoring formula has been selected yet.

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

## To be defined

- Score dimensions and inputs
- Normalization and weighting
- Missing-data behavior
- Explainability and evidence links
- Validation and recalculation rules
