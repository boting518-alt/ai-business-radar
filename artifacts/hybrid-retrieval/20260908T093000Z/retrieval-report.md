# Hybrid Retrieval Offline Evaluation

Run: `20260908T093000Z`

This is a local validation artifact, not a production KPI or runtime implementation.

## Frozen TASK-037 baseline

| Area | v001 | v002 |
| --- | ---: | ---: |
| Overall Recall@1 / @3 / @5 | 60.0% / 80.0% / 93.3% | same retrieval baseline |
| Low-overlap Recall@1 / @3 / @5 | 66.7% / 83.3% / 83.3% | same retrieval baseline |
| Same-industry separation | 7/7 | 7/7 |
| Cross-buyer separation | 2/2 | 2/2 |
| False Merge Rate | 0/14 | 0/14 |
| Retrieval-attributed Missed Merge | 1/15 | 1/15 |
| Signal Useful Rate | 87.5% | 87.5% |
| Signal Grounding | 93.8% | 91.7% |
| Signal Atomicity | 77.1% | 89.6% |
| Signal Category Accuracy | 81.3% | 79.2% |
| CTA errors | 2 | 0 |
| Under-/over-fragmented inputs | 5 / 0 | 1 / 1 |
| Translation Good Rate | 70.8% | 83.3% |
| Translation Meaning Risk | 8.3% | 4.2% |
| Translation Domain-Term Accuracy | 79.2% | 87.5% |
| Translation Natural Chinese Rate | 75.0% | 87.5% |

These values are copied without reinterpretation from the TASK-037 report.

## Approach

The frozen 15-case TASK-037 corpus was embedded with `text-embedding-3-small` in one batch. Candidate
text deterministically concatenated name, customer, problem, solution, and industry. Query text was
the original signal statement only; no expected label or canonical name was injected.

- Lexical: production-equivalent top 5.
- Semantic: cosine-similarity top 5.
- Union: lexical then semantic, deduplicated and capped at 10.
- Weighted rerank: normalized lexical and semantic scores at 0.7/0.3, 0.5/0.5, and 0.3/0.7.
- Best bounded strategy: lexical 0.3 / semantic 0.7.

## Recall comparison

| Strategy | Recall@1 | Recall@3 | Recall@5 | MRR | Mean set size | Noise proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Lexical baseline | 60.0% | 80.0% | 93.3% | 0.730 | 3.93 | 76.3% |
| Semantic only | 73.3% | 93.3% | 100% | 0.836 | 5.00 | 80.0% |
| Union only | 60.0% | 86.7% | 100% | 0.752 | 6.60 | 84.8% |
| Weighted 0.7/0.3 | 80.0% | 93.3% | 100% | 0.861 | 6.60 | 84.8% |
| Weighted 0.5/0.5 | 80.0% | 100% | 100% | 0.878 | 6.60 | 84.8% |
| Weighted 0.3/0.7 | 80.0% | 100% | 100% | 0.889 | 6.60 | 84.8% |

The noise proxy treats every non-expected candidate as irrelevant, so it is deliberately strict;
some same-industry candidates are useful hard negatives for the Normalizer. Nevertheless, union
increased the proxy by 8.5 percentage points and therefore has a real candidate-noise cost.

## Low-overlap results

| Strategy | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: |
| Lexical | 66.7% | 83.3% | 83.3% | 0.750 |
| Semantic | 66.7% | 83.3% | 100% | 0.783 |
| Union | 66.7% | 100% | 100% | 0.806 |
| Weighted best | 83.3% | 100% | 100% | 0.917 |

`24/7 patient phone assistant` previously retrieved only dental recall lexically. Semantic retrieval
ranked veterinary reception first and dental reception second; the weighted hybrid ranked dental
reception second and restored it inside the candidate set. Both Normalizer versions then returned
REVIEW because the phrase did not specify a dental buyer. Retrieval was fixed, but automatic match
was appropriately not forced.

Dental recall improved from lexical rank 4 to weighted rank 2. Legal billing improved from lexical
rank 5 to weighted rank 1.

## Hard-negative safety

The semantic positive ranked above every named hard negative in 7/9 groups. Failures:

- Property maintenance ranked below broader property tenant support.
- HVAC reception ranked below veterinary and dental reception.

These errors show semantic-only retrieval can overvalue shared workflow language and blur buyer or
workflow boundaries. It is not recommended as a standalone replacement.

## Normalizer with hybrid candidates

All 15 cases received at most ten unique hybrid candidates. No v001 or v002 output produced a false
MATCH. Clear same-industry and cross-buyer cases remained correctly matched; property leasing stayed
REVIEW in both versions. Several deliberately sparse low-overlap phrases returned REVIEW, including
the recovered dental phone-assistant case. The larger candidate set increased useful ambiguity
rather than false merges.

## Cost and architecture decision

Embedding cost was one API request, 31 inputs, and 565 tokens. The final artifact contains 65
completed structured-output calls, one invalid v002 signal output, 77,002 structured input tokens,
and 20,856 structured output tokens. YouTube metadata refresh used two list requests and no search.

Decision: `HYBRID_NEEDS_MORE_VALIDATION`.

Recall improvement is material and false merges stayed at zero, but candidate noise increased and
two hard-negative groups exposed semantic boundary weakness. A future runtime prototype should use
lexical top-k plus cached semantic top-k, deterministic deduplication, bounded rerank, and lexical
fallback when embeddings are unavailable. Candidate embeddings should refresh only when canonical
fields change. Runtime latency/cost should be amortized by query and opportunity-vector caches.
No runtime implementation, pgvector storage, migration, or configuration change is made here.
