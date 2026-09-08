# Semantic Separation and Low-Overlap Retrieval Validation v0.2

## Purpose

TASK-037 tests the gaps left by the broad cross-source run: different workflows inside one
industry, similar workflows for materially different buyers, low lexical overlap, signal category
drift, monetization ownership, fragmentation, sparse metadata, multilingual discovery, and zh-CN
domain language. It is an artifact-only evaluation and never opens a database session or changes
active intelligence.

## Separation rules

Same-industry signals remain separate when buyer context is similar but the commercial workflow or
problem differs materially. Same-workflow signals remain separate across buyers when serving both
would require meaningful compliance, domain-model, or integration changes. `REVIEW` is correct when
the source does not identify enough buyer/workflow context; uncertain cases are not counted as
false merges.

Every failure receives one primary attribution: `retrieval_failure`, `normalizer_failure`,
`opportunity_definition_problem`, `ambiguous_ground_truth`, or `source_quality_problem`. If the
expected candidate is absent from the production-equivalent lexical candidate set, the normalizer
is not called and cannot receive blame.

## Retrieval methodology

The runner reproduces the current term extraction, substring filtering, lexical scoring, and
ten-candidate cap over a frozen validation corpus. Low-overlap phrases avoid canonical opportunity
names. Recall@1, Recall@3, and Recall@5 use only expected same-opportunity cases.

The observed low-overlap Recall@5 is 5/6 (83.3%), versus 14/15 (93.3%) overall. The obvious phrase
`24/7 patient phone assistant` did not retrieve the dental receptionist opportunity. Common words
also admit irrelevant candidates. This supports `HYBRID_RETRIEVAL_RECOMMENDED`: retain lexical
precision and add an offline semantic-recall experiment before any pgvector implementation.

## Signal review

Twelve real metadata inputs use identical v001/v002 inputs. Manual review covers usefulness,
grounding, atomicity, category, claim status, CTA handling, monetization ownership, and
fragmentation. Workflow actions include answering calls, booking, qualifying, routing, and checking
status. Technology is reserved for mechanisms such as n8n, Vapi, speech recognition, and concrete
integration architecture.

Creator consulting, memberships, stores, and affiliate links are not featured-product revenue.
Featured-product subscriptions, usage fees, and attributed revenue claims remain product evidence.
The observed mixed descriptions produced no direct owner misattribution, although creator community
size was still emitted as customer evidence and remains a review concern.

v002 reduced CTA-as-demand behavior and compound signals, but it classified several operational
capabilities as technology and produced one schema-invalid invoice-extraction response. It also
over-split one sales-process sentence into four closely coupled workflow signals. These prevent
promotion.

## Sparse and multilingual evidence

Four zero-comment sources were reviewed. Missing comments are not negative evidence. v002 did not
infer demand or purchase intent from their CTAs; v001 did so twice. Neither version may infer prices,
customers, demand, or outcomes beyond supplied metadata.

The Japanese query `歯科 AI 受付` returned a relevant Japanese dental AI record, though it concerned
voice clinical notes rather than reception. The Chinese query `AI 律所接待` returned a Japanese
generic professional-futures video and is classified `insufficient_source_quality`. Discovery
success therefore cannot be inferred from two queries.

## Translation review

The 24-field identical-input sample covers intake, prospective client, retainer, case status,
tenant/resident, maintenance triage, vendor assignment, amenity, handoff, escalation, abandoned
checkout, upsell, reconciliation, ledger, close, cash flow, recall, appointment lead, front desk,
and insurance verification. Proper names and claim strength remain canonical constraints.

v002 is more concise and usually more natural, but `creator` became `创建者`, `retainer` lost legal
specificity, and the legal receptionist sentence still used the passive `被定位为`. It therefore
remains experimental.

## Promotion guidance

- Signal extractor v002: `KEEP_EXPERIMENTAL`.
- Opportunity normalizer v002: `KEEP_EXPERIMENTAL`.
- zh-CN translation v002: `KEEP_EXPERIMENTAL`.

No prompt file, model selection, runtime default, active opportunity, score, trend, review state, or
localized projection is changed. Prompt fixes or promotion planning belong to TASK-038.
