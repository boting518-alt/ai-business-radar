# Semantic Separation Validation Report

Run: `20260908T020000Z`

Mode: bounded, artifact-only, real YouTube/OpenAI validation

Model: `gpt-5.6-terra`

## Executive summary

Fourteen official YouTube searches selected 14 real videos across same-industry workflows,
cross-buyer reception, and two alternate-language queries. Twelve videos received identical
signal v001/v002 inputs; 15 retrieval/normalizer cases and 24 translation fields were evaluated.

Same-industry separation and cross-buyer separation produced no false merges. The decisive finding
is retrieval: overall Recall@5 was 93.3%, but low-overlap Recall@5 fell to 83.3%, with the obvious
paraphrase `24/7 patient phone assistant` absent from the dental receptionist candidate set.
Recommendation: `HYBRID_RETRIEVAL_RECOMMENDED`, as an offline experiment only.

All v002 prompts remain `KEEP_EXPERIMENTAL`. No database, runtime default, or active intelligence
was mutated.

## Dataset and case families

| Family | Cases | Finding |
| --- | ---: | --- |
| Same industry / different workflow | 7 clear normalization cases | 7/7 separated; one appropriate REVIEW |
| Same workflow / different buyer | 2 real new cases plus TASK-036 baselines | Veterinary and HVAC remained buyer-specific |
| Low-overlap / same opportunity | 6 | One retrieval failure; one v002 REVIEW |
| Signal category/fragmentation | 12 real videos | v002 more atomic but category drift persists |
| Sparse metadata | 4 zero-comment sources | v002 avoided CTA demand/purchase-intent inference |
| Multilingual discovery | 2 queries | Japanese dental relevant but different workflow; Chinese legal poor |
| zh-CN terminology | 24 fields | v002 better overall, with remaining legal/word-choice issues |

The machine-readable artifact contains exact queries, video/channel IDs, titles, comment counts,
description lengths, prompt hashes, candidate ranks, model outputs, and stable expected IDs.

## Retrieval recall

| Metric | All 15 cases | Low-overlap 6 cases |
| --- | ---: | ---: |
| Recall@1 | 9/15 (60.0%) | 4/6 (66.7%) |
| Recall@3 | 12/15 (80.0%) | 5/6 (83.3%) |
| Recall@5 | 14/15 (93.3%) | 5/6 (83.3%) |

Dental recall ranked fourth and legal billing fifth despite being clear real-source matches. The
correct candidate was not retrieved for `24/7 patient phone assistant`. The failure is assigned
solely to `retrieval_failure`; no normalizer call was made for that case.

## Normalizer outcomes

| Metric | v001 | v002 |
| --- | ---: | ---: |
| Same-Industry Separation Accuracy | 7/7 (100%) | 7/7 (100%) |
| Cross-Buyer Separation Accuracy | 2/2 (100%) | 2/2 (100%) |
| False Merge Rate | 0/14 (0%) | 0/14 (0%) |
| Retrieval-attributed Missed Merge Rate | 1/15 (6.7%) | 1/15 (6.7%) |
| Review Appropriate Rate | 1/14 (7.1%) | 2/14 (14.3%) |

Property leasing appropriately returned REVIEW in both versions because the signal established
real-estate lead qualification but not property-manager leasing. v002 also returned REVIEW for
`building occupant communications automation`; its reason correctly identified missing buyer and
problem detail. These are `ambiguous_ground_truth`, not model failures. No surviving case had a
primary `normalizer_failure`.

Three searched sources were excluded from normalization ground truth: the ecommerce review result
covered live-stream sales rather than review generation; the accounting result did not establish
cash-flow advisory; and invoice extraction v002 was schema-invalid. Their primary causes are
`source_quality_problem`, `source_quality_problem`, and structured-output failure respectively.

## Signal quality and category drift

Manual review used four balanced output slots per input (48 per version); a missing schema-valid
output consumes four failed slots. These are local validation metrics, not production KPIs.

| Metric | v001 | v002 |
| --- | ---: | ---: |
| Useful Rate | 42/48 (87.5%) | 42/48 (87.5%) |
| Grounding Pass Rate | 45/48 (93.8%) | 44/48 (91.7%) |
| Atomicity Pass Rate | 37/48 (77.1%) | 43/48 (89.6%) |
| Category Accuracy | 39/48 (81.3%) | 38/48 (79.2%) |
| CTA-as-demand/purchase-intent errors | 2 | 0 |
| Under-fragmented inputs | 5/12 | 1/12 |
| Over-fragmented inputs | 0/12 | 1/12 |

v002 correctly separates many independent workflow actions, but labels call answering, automated
billable-time capture, and product recommendation as `technology` in cases where `workflow` is the
better category. The live-stream sales sentence was split into four near-adjacent substeps, an
observed over-fragmentation regression. The invoice case returned schema-invalid v002 output.

## Creator versus featured-product monetization

Four mixed-ownership examples covered a creator community, creator store/CTA, featured-product
pricing navigation, and a vendor revenue claim. Direct creator-to-product revenue misattribution was
0/4 for both versions. v002 emitted no CTA-as-demand signal in the sparse cases; v001 emitted two.
Community size becoming customer/adoption evidence remains semantically questionable but is not a
featured-product revenue claim.

## Sparse evidence and multilingual discovery

Four reviewed sources had zero comments. v002 made no purchase-intent or demand inference from
their CTAs, while v001 labeled a product-page link as demand and an assessment CTA as purchase
intent. Missing comments were not treated as negative evidence.

`歯科 AI 受付` found a Japanese dental voice-subchart automation video, relevant to dental AI but
not the requested receptionist workflow. `AI 律所接待` returned a Japanese generic discussion of
professional work and is `insufficient_source_quality`. No multilingual quality conclusion is made.

## Translation metrics

| Metric | v001 | v002 |
| --- | ---: | ---: |
| Translation Good Rate | 17/24 (70.8%) | 20/24 (83.3%) |
| Meaning Risk Rate | 2/24 (8.3%) | 1/24 (4.2%) |
| Domain-Term Accuracy | 19/24 (79.2%) | 21/24 (87.5%) |
| Proper-Name Preservation | 4/4 (100%) | 4/4 (100%) |
| Claim-Strength Preservation | 4/4 (100%) | 4/4 (100%) |
| Natural Chinese Rate | 18/24 (75.0%) | 21/24 (87.5%) |

v002 improved `handoff`, abandoned checkout, ledger, and document-drafting phrasing. Remaining
issues include `creator` → `创建者`, a generic translation of legal `retainer`, and continued passive
`被定位为` wording. Meaning and attribution were otherwise preserved.

## Decisions

| Area | Recommendation | Reason |
| --- | --- | --- |
| Retrieval | `HYBRID_RETRIEVAL_RECOMMENDED` | Low-overlap Recall@5 dropped and one obvious paraphrase was absent. |
| Signal v002 | `KEEP_EXPERIMENTAL` | Atomicity and CTA discipline improved, but category accuracy dipped and one schema failure occurred. |
| Normalizer v002 | `KEEP_EXPERIMENTAL` | No false merges, but no separation gain and more conservative REVIEW behavior. |
| Translation v002 | `KEEP_EXPERIMENTAL` | Material language improvement, but legal terminology and one meaning error remain. |

Hybrid means evaluating lexical union semantic candidates offline with reviewed positives and hard
negatives. It does not authorize embeddings, pgvector, migrations, or runtime changes.

## Usage and limitations

- YouTube quota estimate: 1,428 units.
- Final artifact: 63 completed provider calls and one schema-invalid response.
- Final artifact token usage: 69,342 input and 21,744 output tokens.
- A design-correction rerun replaced 24 earlier normalizer results after internal case IDs were found
  in source context. Those invalidated calls add provider cost but their token totals are no longer
  reconstructable; total physical provider calls were 88 including the invalid output.
- No repeated stochastic trial was used for conclusions; the rerun removed validation leakage.
- Candidate corpus is frozen and small; lexical ordering in production also depends on database
  recency before application scoring.
- Signal metrics are bounded human judgments, not statistically powered estimates.
- Search result relevance varied, particularly for ecommerce reviews, cash-flow advisory, and the
  Chinese legal query.
