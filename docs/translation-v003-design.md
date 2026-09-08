# Intelligence Translation zh-CN v003 Design

Translation v003 adds evidence-driven terminology and fluency rules without changing its schema or
canonical English source.

- `creator`: `创作者` or contextually `发布者`, never `创建者`.
- Legal `retainer`: `预付律师费`, `律师聘用金`, or `聘用费` based on context.
- Human `handoff`: `转交人工` or `人工接管`; `escalation`: `升级处理`.
- Sales `lead`: `线索`; prospective person: `潜在客户`.
- Dental `recall`: `复诊召回`, `患者召回`, or `复诊提醒`.
- `invoice extraction`: `发票数据提取`; `month-end close`: `月末结账`.
- Avoid `被定位为可`, `被描述为可`, and unnecessary `进行/实现/相关/内部` while preserving claim
  attribution and uncertainty.

The 24-field A/B improved terminology and naturalness, but one passive construction remained and
one abandoned-checkout translation added a customer reference. Recommendation:
`KEEP_EXPERIMENTAL`. No runtime localization preference changed.
