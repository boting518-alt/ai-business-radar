# Industry and Customer Taxonomy Foundation v0.1

Status: Frozen by TASK-040. Version: `taxonomy-v001`.

Taxonomy adds stable, language-neutral codes for filtering and aggregation while preserving
source-derived `industry` and `customer_type` text. Mapping never overwrites canonical intelligence;
unknown or ambiguous text remains unmapped.

Industry and customer are separate hierarchies. Industry describes the business domain. Customer
describes the likely buyer, operator, organization, professional, or team. Beneficiaries such as
patients, callers, tenants, prospects, and shoppers are not automatically buyers. `front desk` is a
team role, `small business` is normally a customer, and bare `Shopify` is a platform reference—not
enough to infer ecommerce. `Legal services` requires buyer context and is deliberately not an alias.

Controlled labels live in `taxonomy_localizations`, independently of AI-generated
`intelligence_localizations`. Codes remain stable when locale changes; `zh-CN` falls back to
`en-US`, then canonical name. Initial aliases use only exact/normalized-exact matching after trim,
lowercase, and basic punctuation cleanup. There is no fuzzy, vector, or LLM mapping.

Signal and Opportunity mappings retain source (`manual`, `rule`, future `ai`/`migration`), optional
confidence, lifecycle status, and timestamps. One active mapping per entity/type is enforced;
replacement rejects the previous row and clearing preserves history. Rule matches use confidence
1.0. Opportunity classification uses its own semantics and never majority-votes linked Signals.

Authenticated users may read reference nodes/labels and mappings only when their source entity is
visible. Admin APIs list nodes and set, replace, or clear mappings. Radar and Signals filter by
canonical `industry_code`/`customer_code`, never labels, while legacy free-text filters remain.
Candidate/rejected Opportunities cannot enter Radar through mappings.

Future changes create `taxonomy-v002` rather than deforming codes. Expansion and AI-assisted mapping
require separate tasks, bounded evaluation, provenance, and human review.
