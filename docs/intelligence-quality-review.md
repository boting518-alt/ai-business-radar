# Intelligence Quality Review v0.1

## Purpose and dataset

This document defines the first local, human-evaluation baseline for AI Business Radar
intelligence. It is not a production KPI or an automated publication gate.

The TASK-035 primary dataset uses persisted real dental data from
`ai_business_radar_live_test`: one active opportunity supported by 40 active signals from four
videos and four channels. The bounded review sample contains 20 signals, selected as the earliest
five persisted signals per source video, the active opportunity, its source/audit lineage, and all
14 current `zh-CN` v001 projection fields. Full record-level judgments are in the checked-in quality
report under `artifacts/intelligence-quality/`.

## Signal rubric

Each dimension receives `pass`, `minor_issue`, or `major_issue`:

- Relevance: contains commercially useful information rather than generic content.
- Atomicity: expresses one independently useful commercial assertion.
- Specificity: identifies a concrete buyer, pain, workflow, capability, channel, or behavior.
- Evidence grounding: the complete statement is directly supported by `evidence_text`.
- Commercial usefulness: informs pain, workflow, demand, pricing, adoption, competition,
  monetization, distribution, or technology capability.
- Claim preservation: retains creator/vendor attribution and uncertainty.
- Redundancy: does not substantially repeat another sampled signal.
- Category correctness: `signal_type` reflects the evidence rather than an inferred market meaning.

Overall verdicts are `good`, `usable_with_minor_issue`, or `poor`. A useful signal is either good or
usable with a minor issue.

## Opportunity rubric

Opportunities are reviewed for naming clarity, scope, customer specificity, problem specificity,
solution specificity, commercial cohesion, duplication risk, evidence diversity, actionability,
and hype/claim discipline. Verdicts are `strong`, `acceptable`, `weak`, or `invalid`.

Correct granularity is a repeatable commercial pattern combining a buyer, problem/workflow, and
sellable solution pattern. A single vendor feature, one source sentence, an entire industry, or a
technology label without buyer/problem context is not an opportunity.

## Translation rubric

Every translated field is reviewed for faithfulness, natural professional Chinese, business
terminology, claim-strength preservation, proper-name preservation, technical-term handling, and
evidence integrity. Verdicts are `good`, `minor_language_issue`, `meaning_risk`, or `unacceptable`.
Translated evidence remains a presentation projection and the canonical original remains visible.

## Current findings

Local validation quality metrics for the bounded dataset:

| Metric | Result |
| --- | ---: |
| Signal Useful Rate | 18/20 (90%) |
| Signal Grounding Pass Rate | 18/20 (90%) |
| Claim Preservation Pass Rate | 20/20 (100%) |
| Duplicate Signal Rate | 2/20 (10%) |
| Opportunity Acceptable Rate | 1/1 (100%) |
| Opportunity Over-broad Rate | 0/1 (0%) |
| Opportunity Duplicate Risk Rate | 0/1 (0%) |
| Translation Good Rate | 10/14 (71.4%) |
| Translation Meaning-Risk Rate | 1/14 (7.1%) |

The signals are generally useful, grounded commercial intelligence, but v001 often packs multiple
workflow capabilities into one signal. Two sampled records are poor: one statement relies on an
evidence fragment that does not support the whole assertion, and one generic chapter heading is
treated as concrete technology evidence. Customer context is also over-expanded at extraction
level beyond the source's narrower wording.

The active opportunity is acceptable and correctly scoped around AI reception/workflow management
for dental practices. Its 40 active signals and four independent source channels provide strong
cohesion and diversity, with no competing dental opportunity currently present. It is not rated
strong because `one_line_thesis` and `solution` retain a narrow VitalDesk feature/vendor framing,
and `customer_type` mixes buyers with patients and enumerates unsupported subsegments.

Translation is faithful overall and preserves names and claims. The TASK-034 regression is:

- Canonical: `Dental appointment leads are organized inside the VitalDesk dashboard.`
- Current v001: `牙科预约潜在客户在线索 VitalDesk 仪表板中进行整理。`
- Problem: `lead` is duplicated across incompatible senses and modifiers are ordered incorrectly.
- Recommended: `牙科预约线索会统一整理到 VitalDesk 仪表盘中。`

The database row is deliberately unchanged. This case is captured as a golden semantic fixture.

## Observed failure modes and prompt response

Only observed patterns are included:

- distinct workflow actions are combined into one signal;
- generic chapter headings can become vague signals without a concrete boundary;
- a statement can include context not present in its selected evidence excerpt;
- same-source workflow signals sometimes substantially overlap;
- product capability is occasionally assigned an imprecise technology category;
- top-level customer scope is expanded into unsupported segments/beneficiaries;
- opportunity summary fields can remain vendor-feature-specific after evidence broadens;
- Chinese may mirror English syntax, overuse `进行`, or mishandle the commercial sense of `lead`.

These findings justify experimental `signal-extractor/v002`, `opportunity-normalizer/v002`, and
`intelligence-translation/zh-CN/v002` prompts. Runtime defaults remain v001 until the promotion
criteria in `docs/prompt-tuning-policy.md` are satisfied.

## Limitations

The sample is one vertical, four channels, one active opportunity, metadata-only extraction, and
one configured model. Human rubric judgments are directional and not production KPIs. Absence of a
duplicate opportunity in this database does not prove robust semantic deduplication. Real-provider
v002 A/B used the same bounded inputs and configured models after credential rotation was
confirmed. Signal and translation v002 improved the targeted sample, while normalizer output was
unchanged. All v002 prompts remain experimental because the dataset is too narrow to establish
stochastic robustness; no active intelligence was replaced during evaluation.
