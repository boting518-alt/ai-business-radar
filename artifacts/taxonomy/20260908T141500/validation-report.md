# Taxonomy v001 Local Validation

Reference migration validation loaded 17 industry nodes and 22 customer nodes with `en-US` and
`zh-CN` labels. Dental hierarchy resolved `healthcare.dental` under `healthcare`; labels were
`Dental` and `牙科`. Customer code `organization.dental_practice` resolved as `Dental Practice` and
`牙科诊所` without changing either code.

Exact/normalized aliases mapped `Dental Practices!` to `healthcare.dental`; `Dental practices`
mapped to `organization.dental_practice`. Local validation added two reviewed manual mappings to one
active dental Opportunity and 15 rule mappings across a bounded maximum of 20 matching active
Signals. Canonical industry/customer filters returned the mapped entities; original free text
remained unchanged. Labels switched between `Dental`/`牙科` and `Dental Practice`/`牙科诊所` while
codes stayed stable.

Unmapped/ambiguous checks: `Dental patients` did not become a buyer organization; bare `Shopify`
did not imply ecommerce; `Legal services` remains context-dependent; bare `front desk` remains
unmapped while explicit `front desk teams` maps to `team.front_desk`. No LLM was invoked.

Limitations: taxonomy-v001 is intentionally small; only one active primary mapping per taxonomy
type is supported; no bulk historical mapping, fuzzy matching, AI classification, or automatic
Opportunity aggregation was performed.
