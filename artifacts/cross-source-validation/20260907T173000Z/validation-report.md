# Cross-Source Intelligence Validation Report

Run: `20260907T173000Z`

Mode: bounded, artifact-only, real-provider validation

Model: `gpt-5.6-terra`

## Executive summary

The five-vertical sample materially broadens the dental-only baseline: 20 real YouTube videos from
20 distinct channels, with 30 comments sampled as source diagnostics. Ten videos were compared on
signal extraction and normalization, and 16 cross-domain fields were compared on Chinese
translation.

The strongest result is opportunity convergence: both prompt versions matched all 10 independent
source cases to the five expected vendor-neutral opportunities while five competing vertical
candidates were present. Production-equivalent lexical scoring ranked the expected candidate first
in all 10 cases. No cross-buyer false merge occurred.

The signal v002 prompt improved atomicity and evidence boundaries, but showed category drift in an
ecommerce capability case. Signal v001 also produced one schema-invalid pricing object. Translation
v002 improved attribution and several domain phrases but retained awkward legal-intake phrasing.
No candidate meets the evidence threshold for automatic promotion. All recommendations are
`KEEP_EXPERIMENTAL`; runtime defaults and persisted intelligence are unchanged.

## Dataset and provenance

| Vertical | Videos | Channels | Comments sampled | Query |
| --- | ---: | ---: | ---: | --- |
| Dental receptionist | 4 | 4 | 7 | `AI dental receptionist appointment booking` |
| Legal intake | 4 | 4 | 1 | `AI legal intake assistant law firm receptionist` |
| Property management | 4 | 4 | 6 | `AI property management tenant inquiry automation` |
| Ecommerce support | 4 | 4 | 10 | `AI ecommerce customer support agent Shopify` |
| Bookkeeping | 4 | 4 | 6 | `AI bookkeeping automation small business accounting` |
| **Total** | **20** | **20** | **30** | **5 bounded searches** |

The canonical machine-readable inventory, video/channel IDs, titles, prompt hashes, outputs, token
usage, expected opportunity IDs, and lexical ranks are in `cases.json`. Discovery used only the
official YouTube Data API. No transcript scraping or unofficial source was used.

## Signal quality

Manual review covered the first three output slots from each of the ten A/B inputs: 30 balanced
slots per version, six per vertical. An invalid response counts as three failed slots. Counts are
directional human judgments rather than automated truth labels.

| Metric | v001 | v002 |
| --- | ---: | ---: |
| Signal Useful Rate | 26/30 (86.7%) | 28/30 (93.3%) |
| Grounding Pass Rate | 27/30 (90.0%) | 29/30 (96.7%) |
| Atomicity Pass Rate | 22/30 (73.3%) | 28/30 (93.3%) |
| Category Correctness Rate | 24/30 (80.0%) | 26/30 (86.7%) |
| Commercial Usefulness Rate | 26/30 (86.7%) | 28/30 (93.3%) |
| Duplicate/near-duplicate Rate | 3/30 (10.0%) | 2/30 (6.7%) |

Claim attribution was preserved in all reviewed claim-bearing v002 statements. Improvements were
most visible where v002 split dental appointment handling and property maintenance automation into
single-workflow assertions. The most important regression is ecommerce: concrete support-agent
capabilities can still be labeled `technology` instead of `workflow`. Creator monetization links
also remain easy to confuse with evidence about the featured product's business model.

One v001 property-management response was rejected by Pydantic because a pricing range encoded
`currency: null` alongside numeric bounds. The runner recorded `invalid_output` without persisting
or coercing the result; v002 completed for the identical input.

## Cross-source convergence and normalization

Five expected opportunity clusters were defined before normalization. Each had two source videos
from distinct channels. Every case received all five candidates, rather than only its expected
candidate.

| Metric | v001 | v002 |
| --- | ---: | ---: |
| Correct source-to-opportunity match | 10/10 | 10/10 |
| Same-pattern convergence | 5/5 clusters | 5/5 clusters |
| Missed-merge cases | 0/10 | 0/10 |
| Cross-vertical false merges | 0/10 | 0/10 |
| Vendor-neutral canonical names | 5/5 | 5/5 |
| Correct buyer/workflow granularity | 5/5 | 5/5 |

Dental reception and legal intake are deliberately similar in technology but have different buyers
and downstream workflows; both versions kept them separate. This run does **not** contain enough
same-industry, different-workflow negative pairs to establish a general false-merge rate. That is a
required follow-up dataset, not evidence to infer from these clean verticals.

## Lexical candidate retrieval

The artifact replays the exact term extraction and substring scoring formula used by the
normalization service against the five in-run candidates. The expected opportunity ranked first in
10/10 cases. Top expected scores ranged from 11 to 15 shared terms. This demonstrates adequate
recall for explicit buyer/workflow wording, but not semantic recall for paraphrases, multilingual
signals, sparse comments, or same-industry near-neighbors.

## Translation quality

Sixteen fields covered legal intake, property management, ecommerce support, and bookkeeping.

| Metric | v001 | v002 |
| --- | ---: | ---: |
| Translation Good Rate | 10/16 (62.5%) | 12/16 (75.0%) |
| Meaning-Risk Rate | 0/16 (0%) | 0/16 (0%) |
| Proper/domain term preservation | 16/16 | 16/16 |
| Claim-strength preservation | 16/16 | 16/16 |

Both versions preserved `Shopify`, `QuickBooks`, `MagicDoor`, prices, and attributed claims. v002
improved phrases such as bookkeeping context pre-prompting and Shopify attribution. Repeated legal
phrasing such as `被定位为可` remains unnatural, so the improvement is not broad enough to promote.
Canonical English evidence stayed unchanged; translations exist only in this artifact.

## Prompt decisions

| Prompt family | Decision | Evidence |
| --- | --- | --- |
| Signal extractor v002 | `KEEP_EXPERIMENTAL` | Better atomicity/grounding, but category drift remains and only 10 inputs were tested. |
| Opportunity normalizer v002 | `KEEP_EXPERIMENTAL` | 10/10 correct, but materially identical to v001 and negative-pair coverage is insufficient. |
| zh-CN translation v002 | `KEEP_EXPERIMENTAL` | Better overall language, but legal phrasing remains awkward and the sample is 16 fields. |

These are recommendations only. No prompt was promoted and no existing v001 file was modified.

## Budget and operational notes

- YouTube quota estimate: 530 units (five searches dominate at 500 units).
- Final artifact contains 48 provider outcomes: 47 completed and one schema-invalid.
- Recorded completed usage: 49,095 input tokens and 15,541 output tokens.
- A prior interrupted attempt and the 20-call candidate-stress rerun created additional provider
  usage that cannot be reconstructed reliably from the final overwritten checkpoint; no false USD
  estimate is reported.
- Secrets, authorization headers, full comment text, and `.env` values are absent from artifacts.

## Observed failure modes and next actions

1. Keep all three v002 prompt families experimental.
2. Add real same-industry/different-workflow pairs and sparse paraphrased comment signals before a
   normalizer promotion decision.
3. Add signal guidance/tests separating workflow capabilities from enabling technology and creator
   monetization from featured-product monetization.
4. Add legal-intake Chinese fluency cases targeting repetitive `被定位为可` construction.
5. Preserve the property pricing schema failure and ecommerce category regression as golden cases.
6. Defer any active-prompt promotion, reprocessing, or migration to TASK-037.

## Limitations

Search results are time-dependent and the selected videos are metadata/description-heavy. Comments
were too sparse in legal intake to support comment-mining comparison. The five canonical candidates
were human-authored for validation and contain explicit lexical overlap, which favors retrieval.
Only one configured model and one stochastic run per prompt/input were evaluated. Results do not
measure opportunity scoring, trend aggregation, review activation, publication, or Radar UI.
