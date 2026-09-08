# Signal Extractor v003 Design

Signal v003 responds only to observed v002 failures. It does not add categories or schema fields.

- Workflow describes what happens in a business process; technology describes how it is enabled.
- Behavior and mechanism may become separate signals only when independently evidenced.
- Creator/channel monetization must not become featured-product pricing, revenue, or business model.
- CTAs, views, affiliate links, and community size do not establish demand, adoption, customers, or
  purchase intent.
- Split independently meaningful actions; keep tightly coupled substeps together when fragments
  lose buyer/problem context.
- Incomplete price evidence must produce `pricing: null`; ranges require currency and coherent
  bounds, and zero cannot be a placeholder.

The schema-invalid property pricing and invoice extraction cases indicate optional-price prompt
ambiguity, not a need to weaken the Pydantic contract. The strict contract prevented corrupt FACT
data. v003 completed the repeated invoice case without a schema change.

The bounded A/B improved reviewed category accuracy, balanced fragmentation, community ownership,
and structured-output success. TASK-039 promoted v003 through centralized, configurable runtime
selection. Promotion did not modify v001/v002/v003 bytes or historical extraction records.

TASK-039 live validation ran two dental videos and one non-dental bookkeeping/invoice video through
the normal provider path. All three completed with v003 and hash
`d91be041c6f50c0f97f5c9ba9d3469778ba92f1ee91d7063531df003a1c792e3`; created Signals remained in
review. A separate one-video process override completed with v001 and its historical hash, after
which the ordinary configuration resolved back to v003.
