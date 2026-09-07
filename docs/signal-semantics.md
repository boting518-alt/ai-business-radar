# Signal Semantics v0.1

Signals are atomic, evidence-backed commercial observations. They are not video summaries. The UI
keeps the normalized assertion, its source evidence, classification, provenance, and opportunity
relationship visually distinct.

| Field | Meaning | Not | UI treatment |
| --- | --- | --- | --- |
| `signal_type` | Canonical category of the commercial signal, such as `workflow`, `pain`, `demand`, `pricing`, `purchase_intent`, `feature_request`, `complaint`, or `competition`. | YouTube category, content genre, or industry. | Locale-aware badge; stored enum is unchanged. |
| `statement` | Normalized atomic commercial statement produced by extraction. | Video title, subtitle, or raw quotation. | Primary card content. |
| `evidence_text` | Source-grounded excerpt or close evidence wording supporting the statement. | Generic subtitle or the normalized statement. | Secondary block labeled `证据摘录` / `Evidence`; translated projections are identified and original text remains available. |
| `industry` | Associated business domain. It remains free text in v0.1. | Signal type. | Dedicated field, separate from customer. |
| `customer_type` | Customer/user segment affected by or buying the product or service. | Industry. | Dedicated field. |
| `claim_status` | Epistemic/source status. `creator_claim` means the creator/vendor stated it; Radar has not independently verified it. | A verification result. | Locale-aware label; canonical value remains unchanged. |
| `confidence` | Model extraction confidence in the structured extraction. | Probability that a claim is factually true. | Decimal formatted as a percentage only. |
| `observed_at` | Source publication time used when intelligence entered the pipeline: video publication time for video signals and comment publication time for comment signals. | Extraction execution time or verification time. | Locale-formatted time beside the type badge. |
| `source_type` | Canonical source kind: `video` or `comment`. | Provider name or media category. | Locale-aware provenance label. |
| `video` | Original YouTube source video; its title is source provenance. | AI-generated summary. | Original title, never dictionary-translated. |
| `channel` | YouTube channel associated with the source video. | Industry or publisher classification. | Original proper name. |
| `opportunity` | Normalized business opportunity linked through `opportunity_signal_links`. | A required property of every signal or proof of publication. | Names of visible active opportunities; an unlinked state is explicit. |

Industry and customer values need canonical taxonomy codes in a future migration. For example,
`healthcare.dental` could have Chinese and English display labels. TASK-033 does not rewrite or
automatically map existing free text because an unsafe mapping would change product meaning.
