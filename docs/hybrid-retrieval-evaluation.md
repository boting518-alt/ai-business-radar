# Hybrid Retrieval Offline Evaluation v0.1

TASK-038 evaluates retrieval outside the production service. Candidate text is a deterministic
concatenation of opportunity name, customer, problem, solution, and industry. Signal query text
contains the statement only. Expected labels, scores, status, review notes, and IDs are excluded.

The experiment uses lexical top 5 plus `text-embedding-3-small` cosine-similarity top 5, deduplicates
their union, caps it at the existing ten-candidate contract, and compares three weighted reranks.
The embedding endpoint accepts a batch of string inputs and returned all candidate/query vectors in
one request. No vectors are stored in PostgreSQL.

Weighted lexical 0.3 / semantic 0.7 achieved 100% Recall@5 overall and on low-overlap cases, versus
93.3% and 83.3% for lexical. Candidate noise increased, and semantic ranking lost two of nine hard
negative comparisons. Hybrid Normalizer runs created no false matches but appropriately returned
REVIEW for sparse phrases. The decision is `HYBRID_NEEDS_MORE_VALIDATION`, not a runtime rollout.

A future runtime design, if separately approved, should combine cached lexical and semantic top-k,
deduplicate, rerank within ten candidates, and fall back to lexical when the semantic provider is
unavailable. Opportunity vectors should refresh only when canonical retrieval fields change; query
vectors should use a bounded cache. Latency, provider cost, batch behavior, multilingual recall,
hard-negative false merges, and database storage design require a separate prototype. Semantic-only
retrieval is not recommended.

TASK-039 freezes this result as offline-only; no embedding or pgvector runtime change is authorized.
