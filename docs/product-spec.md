# YouTube AI Business Radar — Product Specification v0.1

Status: Frozen for v0.1
Version: 0.1
Last updated: 2026-09-04

## Product purpose

YouTube AI Business Radar is a business-intelligence product that discovers, structures, evaluates, and tracks emerging AI-related business opportunities using YouTube as its primary discovery source.

The product turns source material into traceable business signals, normalizes related signals into commercial opportunities, measures how those opportunities change over time, and presents the results for human review and analysis.

The core product pipeline is:

```text
YouTube Discovery
→ Video Metadata
→ Comments
→ AI Business Signal Extraction
→ Opportunity Normalization
→ Trend Aggregation
→ Opportunity Scoring
→ Human Review
→ Radar Dashboard
```

## Non-goals

YouTube AI Business Radar v0.1 is not:

- A YouTube summarization product
- A video recommendation product
- A generic AI news reader
- A creator analytics tool
- A multi-tenant team product

The following capabilities are explicitly out of scope for v0.1:

- Reddit ingestion
- GitHub ingestion
- Product Hunt ingestion
- Google Trends ingestion
- LinkedIn or job-board ingestion
- Large-scale unofficial transcript scraping
- Billing
- Team accounts and collaboration
- Mobile applications
- A public API
- Browser extensions
- Notifications

## Users and permissions

### Analyst/User

An Analyst/User can:

- View the radar
- Search and browse opportunities
- Inspect opportunity details and supporting evidence
- Inspect the chronological signal feed
- Add opportunities to or remove them from a personal watchlist
- Track changes in watched opportunities

### Reviewer/Admin

A Reviewer/Admin can:

- Inspect AI-generated review tasks
- Approve normalized opportunities
- Merge duplicate opportunities
- Create a new opportunity during review
- Ignore or reject bad signals or opportunities
- Mark items for later review

v0.1 does not define multi-tenant organizations, teams, or collaborative workflows.

## Domain concepts

### Video

A YouTube video discovered or monitored by the system. Its source metadata and historical statistics contribute evidence but do not, by themselves, constitute a business opportunity.

### Signal

An atomic, evidence-backed business observation extracted from a source. A signal preserves its connection to the evidence from which it was derived.

The initial signal taxonomy is:

- `pain`
- `demand`
- `purchase_intent`
- `revenue`
- `pricing`
- `customer`
- `product_launch`
- `growth`
- `competition`
- `distribution`
- `workflow`
- `technology`
- `market_change`
- `complaint`
- `feature_request`
- `adoption`

### Opportunity

A normalized commercial opportunity supported by one or more signals, potentially across many videos. For example, multiple pieces of evidence may support an opportunity named “AI Dental Receptionist.”

### Trend

The time-series behavior of an opportunity. Trends are derived from historical observations and snapshots rather than from a single source item.

### Evidence

A traceable source record supporting a signal or an opportunity conclusion. Evidence may originate from an in-scope automated source or be added manually.

### Opportunity Score

A deterministic score calculated by application code from structured inputs. It ranks commercial opportunities; it is not generated directly by an LLM.

The initial scoring dimensions and weights are:

| Dimension | Weight |
| --- | ---: |
| Trend Velocity | 20% |
| Demand Evidence | 20% |
| Revenue Evidence | 15% |
| Pain Severity | 15% |
| Competition White Space | 10% |
| Build Feasibility | 10% |
| Distribution Ease | 10% |

Detailed formulas, normalization, and missing-data behavior belong in `docs/scoring.md` and are not defined here.

### Confidence Score

A score separate from the Opportunity Score that indicates the quality and coverage of the supporting evidence.

### Hype Risk

A measure separate from the Opportunity Score and Confidence Score that distinguishes content-driven attention from demand-driven commercial evidence.

### Market Stage

The current product classification of an opportunity’s market maturity or trajectory. The allowed v0.1 stages are:

- `unknown`
- `emerging`
- `accelerating`
- `validated`
- `crowded`
- `mature`
- `declining`

## Data-source scope

### In scope

- YouTube search and discovery
- YouTube video metadata
- YouTube channel metadata
- YouTube public comments
- Legally available transcript data when explicitly available
- Manually added evidence
- Architecture hooks for future external evidence

YouTube is the primary automated discovery source in v0.1. Architecture hooks do not authorize ingestion from an out-of-scope source.

### Out of scope

The external sources listed under [Non-goals](#non-goals) are not ingested in v0.1. In particular, unofficial transcript scraping at scale is excluded.

## Product data layers

Industry and customer taxonomy is additive controlled metadata. Stable taxonomy-v001 codes enable
filtering while source-derived free text remains canonical evidence; ambiguous records stay unmapped.

The product keeps three concepts separate:

- **RAW:** API or source data preserved with source timestamps.
- **FACT:** Structured, evidence-backed signals extracted from source data.
- **INTELLIGENCE:** Normalized opportunities, trends, deterministic scores, and classifications.

Data may move through this pipeline only with traceable lineage. A creator claim remains a claim unless independently verified; extraction must not silently convert it into a fact.

## MVP pages

### `/radar`

Purpose: Show the most important emerging and accelerating opportunities.

Required elements:

- Time range selector for 7D, 30D, and 90D
- Opportunity ranking
- Opportunity Score
- Confidence Score
- Momentum
- Hype Risk
- Market Stage
- Filters for industry, business model, customer type, technology, competition, build difficulty, and stage

### `/opportunities`

Purpose: Search and browse normalized opportunities.

Required elements:

- Search
- Sorting
- Filters
- Compact opportunity cards or table

### `/opportunities/[id]`

Purpose: Explain why an opportunity is interesting and make its conclusions inspectable.

Required sections:

- Opportunity thesis
- Customer
- Problem
- Solution
- Business model
- Pricing range
- Distribution
- Score breakdown
- Trend history
- Evidence
- Supporting videos
- Customer-demand signals
- Competition summary

### `/signals`

Purpose: Provide a chronological feed of business signals.

The feed may include pain, revenue claim, new product, purchase intent, trend acceleration, competition, and pricing signals. Each displayed signal must remain traceable to evidence.

### `/watchlist`

Purpose: Let an Analyst/User track selected opportunities.

Required behavior:

- Add opportunities to the watchlist
- Remove opportunities from the watchlist
- Display score changes
- Display momentum changes
- Display new evidence counts

Notifications are not part of v0.1.

### `/admin/review`

Purpose: Support human validation of AI-generated intelligence.

Required review actions:

- Approve
- Merge
- Create a new opportunity
- Ignore or reject
- Mark for later review

## Core user workflows

### Discover and assess opportunities

1. The system discovers videos from managed YouTube search queries.
2. It captures source metadata, public comments, and explicitly available transcript evidence.
3. AI extraction produces structured, evidence-backed business signals.
4. Related signals are normalized into candidate opportunities.
5. The system aggregates historical trend metrics and calculates deterministic scores.
6. A Reviewer/Admin validates AI-generated intelligence.
7. A candidate becomes Radar-visible only after an administrator explicitly publishes an
   `opportunity_activation` review. `active` means sufficiently supported and coherent for
   monitoring; it does not mean proven commercial success or an investment recommendation.
7. An Analyst/User views ranked opportunities on the radar and opens detail pages to inspect the reasoning and evidence.

### Browse evidence and signals

1. An Analyst/User opens the chronological signal feed or an opportunity detail page.
2. The user filters or inspects relevant observations.
3. The user follows each important conclusion back to its supporting evidence and source video.

### Review AI-generated intelligence

1. A Reviewer/Admin opens a pending review task.
2. The reviewer inspects the proposed signal or normalized opportunity and its evidence.
3. The reviewer approves it, merges it with an existing opportunity, creates a new opportunity, rejects or ignores it, or defers it for later review.

### Monitor known opportunities

1. An Analyst/User adds an opportunity to the watchlist.
2. The system continues monitoring known videos, channels, or opportunities separately from discovery.
3. The watchlist shows changes in score, momentum, and new evidence count.
4. The user may remove the opportunity from the watchlist.

## Product principles

1. **Evidence over summary.** The product extracts business evidence rather than merely summarizing videos.
2. **Claims are not facts.** Creator claims remain labeled as claims unless independently verified.
3. **Traceability.** Every important derived record is traceable to supporting evidence.
4. **Time series matter.** Historical snapshots are preserved so acceleration and other changes can be detected.
5. **AI extracts; code scores.** LLMs may extract and classify evidence, but deterministic application code calculates the final Opportunity Score.
6. **Human review is part of the MVP.** The product does not assume fully automated intelligence generation.
7. **Discovery and monitoring are distinct.** Discovery searches for unknown opportunities; monitoring tracks already known channels, videos, and opportunities.
8. **RAW, FACT, and INTELLIGENCE remain separate.** Source data, extracted observations, and derived intelligence have distinct responsibilities.
9. **Localization is a projection.** Canonical v0.1 intelligence remains English; stored localized
   projections may be selected for presentation without overwriting canonical content or original
   evidence. Product reads never invoke an LLM to translate content.

## Success criteria

v0.1 succeeds at the product level when it can:

1. Discover YouTube videos from managed search queries.
2. Store video and channel metadata.
3. Capture historical video statistics.
4. Collect useful public comments.
5. Extract structured business signals.
6. Normalize related signals into opportunities.
7. Maintain evidence traceability.
8. Aggregate opportunity trend metrics.
9. Calculate Opportunity Score deterministically.
10. Calculate Confidence Score and Hype Risk separately.
11. Surface opportunities in a Radar UI.
12. Support human review of AI-generated intelligence.
13. Support watchlisting of opportunities.
14. Provide an authenticated Opportunity Library for searching and filtering published opportunities.

### Initial quality targets

- Relevance precision greater than 90%.
- Useful business-signal precision greater than 85%.
- Opportunity merge/match accuracy greater than 90%.

These are product quality targets, not guarantees that individual automated acceptance tests must satisfy.

## Non-functional requirements

- API keys and secrets must never be committed.
- AI outputs must be versioned and auditable.
- Each AI extraction must retain its source, model, prompt version, input hash, raw output, and parsed output.
- Scoring must be deterministic and reproducible from structured inputs.
- Source records must preserve source timestamps.
- AI extraction errors must not corrupt raw source data.
- Data ingestion should be idempotent where practical.
- Opportunity conclusions must preserve links to supporting evidence.
- Future external evidence sources must be addable without redesigning the core opportunity model.

## Deferred Architecture Decisions

The following implementation choices are intentionally unresolved in the product specification and must be decided in later architecture tasks:

- Monorepo and package-management tooling
- Background job queue and scheduler
- Authentication implementation
- Deployment topology
- AI provider choice
- Schema code-generation strategy
