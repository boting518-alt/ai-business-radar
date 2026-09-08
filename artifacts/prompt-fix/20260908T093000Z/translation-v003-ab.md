# Translation zh-CN v002 vs v003

The same 24 TASK-037 fields were evaluated with the same model and schema.

| Local metric | v002 | v003 |
| --- | ---: | ---: |
| Good Rate | 20/24 (83.3%) | 21/24 (87.5%) |
| Meaning Risk Rate | 1/24 (4.2%) | 1/24 (4.2%) |
| Domain-Term Accuracy | 21/24 (87.5%) | 23/24 (95.8%) |
| Natural Chinese Rate | 21/24 (87.5%) | 22/24 (91.7%) |
| Proper-Name Preservation | 4/4 | 4/4 |
| Claim-Strength Preservation | 4/4 | 4/4 |

v003 corrected `creator` to `创作者`, legal `retainer` to `预付律师费`, human handoff to `转交人工`,
dental recall to `患者召回`, and preserved QuickBooks, Shopify, n8n, and claim attribution. It still
used `被定位为用于` in one legal sentence, and translated abandoned checkout by adding `客户`, which
is a small meaning risk.

Recommendation: `KEEP_EXPERIMENTAL`. The targeted improvement is real but not yet clean enough for
promotion. No localization version or read preference changed.
