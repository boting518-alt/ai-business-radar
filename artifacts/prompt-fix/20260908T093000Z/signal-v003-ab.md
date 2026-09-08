# Signal Extractor v002 vs v003

Twelve identical real metadata inputs across dental, legal, property, ecommerce, bookkeeping,
veterinary, and HVAC workflows were evaluated with the same model and schema.

| Local metric | v002 | v003 |
| --- | ---: | ---: |
| Useful Rate | 42/48 (87.5%) | 47/48 (97.9%) |
| Grounding Pass Rate | 44/48 (91.7%) | 47/48 (97.9%) |
| Atomicity Pass Rate | 43/48 (89.6%) | 45/48 (93.8%) |
| Category Accuracy | 38/48 (79.2%) | 45/48 (93.8%) |
| CTA errors | 0 | 0 |
| Monetization ownership errors | 0 | 0 |
| Community-as-customer/adoption errors | 1 | 0 |
| Under-fragmented inputs | 1/12 | 1/12 |
| Over-fragmented inputs | 1/12 | 0/12 |
| Structured-output success | 11/12 (91.7%) | 12/12 (100%) |

v003 treated call answering, billable-time/invoice analysis, and product recommendation as workflow
behavior while separately retaining supported mechanisms as technology. It collapsed the
live-stream sales substeps into one coherent workflow and represented the creator's 800-member
community as distribution rather than a featured-product customer/adoption signal.

The repeated invoice input `PD2eKTzkZ70` was schema-invalid under v002 and completed under v003 with
`pricing: null`, one pain, one workflow, and one technology signal.

The TASK-036 pricing failure and repeated invoice failure are consistent with prompt ambiguity
around incomplete/free pricing rather than a Pydantic contract mismatch: the schema correctly
rejects partial numeric/currency objects. v003 explicitly requires null for incomplete prices,
non-null currency for ranges, and forbids zero placeholders. No schema change is recommended.

Recommendation: `PROMOTE` v003 in TASK-039 after explicit runtime-switch review. This artifact does
not change the v001 runtime default. Signal v002 remains `KEEP_EXPERIMENTAL` rather than being
promoted.
