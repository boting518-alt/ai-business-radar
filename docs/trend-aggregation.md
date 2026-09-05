# Trend Aggregation v0.1

`trend-v001` is the deterministic, non-AI time-series layer between active FACT signals and
Opportunity Scoring. It stores append-only 7-day, 30-day, and 90-day snapshots using half-open UTC
windows. Only active signals linked through `opportunity_signal_links` participate; comment signals
resolve to their canonical video.

Each snapshot records distinct videos, new videos, distinct channels, latest qualifying views,
comments, and canonical pain, demand, purchase-intent, revenue, and competition counts. Momentum
compares the current window with the immediately preceding equal window using the bounded logarithmic
formula frozen in [scoring.md](scoring.md). Missing history and incomplete view boundaries use the
documented neutral behavior rather than invented growth.

Aggregation is idempotent for the same opportunity, window, period, version, and inputs unless a
forced run intentionally appends a new reproducible result. It never changes Opportunity Score,
market stage, FACT signals, or source data. Workers use the `aggregation` queue; the scheduler
enqueues three bounded daily windows with `TREND_AGGREGATION_BATCH_SIZE`.

Known v0.1 limits: there is no external trend source, no automatic stage policy, and no distributed
scheduler lock beyond `max_instances=1` inside one scheduler process.
