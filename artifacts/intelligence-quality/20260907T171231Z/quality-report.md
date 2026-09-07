# Local Intelligence Quality Report

Generated: 2026-09-07T17:12:31Z

Environment: local `ai_business_radar_live_test`

Purpose: bounded human evaluation; not production intelligence or a production KPI.

## Dataset summary

- 1 active dental opportunity.
- 40 linked active signals across 4 videos and 4 channels.
- Review sample: 20 signals, deterministically balanced at 5 per video/channel.
- 4 completed `signal_extractor/v001` audit records using `openai/gpt-5.6-terra`.
- 14 current `translation-zh-CN-v001` fields: 10 signal fields and 4 opportunity fields.
- Credential rotation was explicitly confirmed before provider calls.
- Missing `hype-detector/v001.md` was noted; only its README/schema placeholder exists and no hype
  prompt was invented because the deterministic Hype Risk implementation does not use it.

Rubric cells use `P` = pass, `m` = minor_issue, `M` = major_issue. Verdicts use `good`, `minor`
(`usable_with_minor_issue`), and `poor`.

## Signal review

| signal_id | type / claim | statement | evidence_text | Rel | Atom | Spec | Ground | Useful | Claim | Redund | Cat | Verdict / note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `30985cf2-b800-4263-9433-ecb03004c4ad` | pain / creator_claim | The booking process is presented as depending on the dentist being personally available for every call. | “create a clearer dental booking process without relying on you to be available for every call.” | P | P | P | P | P | P | P | P | good — concrete availability bottleneck. |
| `5bfc38cb-1ade-43d7-919e-69ce44d7f258` | distribution / creator_claim | The creator uses a comment keyword to offer a free audit of a viewer's booking process. | “Comment SYSTEM and I’ll send you a free audit of your current booking process.” | P | P | P | P | P | P | P | P | good — observable lead-generation path. |
| `d5fa6f77-bd70-4d71-80a7-9caaa6d04203` | workflow / creator_claim | The promoted AI receptionist is presented as answering calls, collecting caller details, and scheduling appointments on a calendar. | “An AI receptionist can help answer calls, capture the caller’s details, and schedule appointments onto your calendar.” | P | M | P | P | P | P | P | P | minor — useful but combines three separable workflow assertions. |
| `de86428a-d9a7-4c0c-a7d5-0369dd3dbc16` | pain / creator_claim | Dental practitioners may be unable to answer incoming calls while treating patients. | “When you’re treating a patient, you can’t always stop to answer an incoming call.” | P | P | P | P | P | P | P | P | good — qualified and directly grounded. |
| `f001fde2-91e9-4d7a-993c-59741d6f7bcc` | workflow / creator_claim | The product is positioned to let dentists continue patient care while appointment booking is handled. | “while you continue focusing on patient care.” | m | P | m | M | m | P | M | P | poor — excerpt does not support who/what handles booking and overlaps the fuller workflow signal. |
| `0a8529d9-ba73-44a9-9f87-ff8fe2208a1f` | pain / creator_claim | The creator identifies reception overload as a problem for dental practices. | “If your dental practice is dealing with... reception overload” | P | P | P | P | P | P | P | P | good — direct pain evidence. |
| `2ed1f7a5-d4ea-4164-a3c5-2232f256d54f` | workflow / creator_claim | The product is presented as handling incoming calls, patient enquiries, appointment bookings, recalls, conversations, and follow-up for dental clinics. | “handling incoming calls, patient enquiries, appointment bookings, recalls, conversations and follow-up” | P | M | P | P | P | P | m | P | minor — six distinct workflows are packed together. |
| `3a60ac8b-6f84-414a-9511-5d7dc8023cf9` | workflow / creator_claim | The product is positioned as allowing reception staff to focus on patients while AI handles repetitive front-desk work. | “give them more capacity to focus on patients while AI handles more of the repetitive front-desk workload” | P | P | P | P | P | P | P | P | good — specific operational value with attribution. |
| `4749d3e1-3ebb-41b2-a73f-550ee4b307f1` | workflow / creator_claim | The Dental Dashboard is presented as monitoring AI call-answering and appointment-booking activity. | “AI calls answered and appointments booked” | P | P | P | P | P | P | P | P | good — specific monitoring workflow. |
| `51d9f447-3df3-4051-9a9e-f9ead54be051` | pain / creator_claim | The creator identifies appointment gaps as a problem for dental practices. | “If your dental practice is dealing with... appointment gaps” | P | P | P | P | P | P | P | P | good — direct pain evidence. |
| `0a74cce1-79ee-47e1-b270-b7da6f6f5736` | workflow / creator_claim | Dental appointment leads are organized inside the VitalDesk dashboard. | “How dental appointment leads are organized inside the dashboard” | P | P | P | P | P | P | P | P | good — narrow but specific workflow evidence. |
| `3f5b6fcd-b047-4bf1-9785-678f9de34311` | workflow / creator_claim | VitalDesk is positioned to capture appointment requests and organize front-desk workflows for dental clinics. | “VitalDesk helps dental clinics answer patient calls, capture appointment requests, manage leads, and organize front-desk workflows” | P | m | P | P | P | P | m | P | minor — coherent but overlaps and combines capture/organization. |
| `4097d6ce-4c26-4e38-b190-c7da02030778` | workflow / creator_claim | Patient calls and website chat requests can be captured by the product. | “How patient calls and website chat requests are captured” | P | P | P | P | P | P | P | P | good — qualified channel-capture capability. |
| `63eda4a9-3176-45ad-8ecf-fecfcd7c954d` | technology / creator_claim | VitalDesk uses an AI receptionist for repetitive patient communication, call capture, and request routing. | “AI handles repetitive communication, call capture, and patient request routing 24/7” | P | m | P | P | P | P | m | m | minor — multiple workflows; category is arguably workflow rather than a concrete technical approach. |
| `6926dc73-ae72-4378-80df-c29a659dcd35` | workflow / creator_claim | Clinics can review conversation logs and request status in the product. | “How clinics can review conversation logs and request status” | P | P | P | P | P | P | P | P | good — actionable dashboard workflow. |
| `0c1ec7a5-52fd-44db-a820-ebf72e6de724` | workflow / creator_claim | AI-supported dental workflows require human judgment, practice-policy controls, and clear handoffs. | Description bullet: “Where human judgement, practice policy, and clear handoff are essential.” | P | m | m | P | P | P | P | P | minor — useful control boundary, but three related controls are combined and remain abstract. |
| `16e9da82-e39f-47ae-b756-938aae4f625a` | pain / creator_claim | Dental practices have repeatable front-desk bottlenecks. | Chapter title: “Start with repeatable front-desk bottlenecks.” | P | P | M | P | m | P | P | P | minor — grounded but too generic to identify the bottleneck. |
| `17215f45-18ac-4bf6-86e1-e5e6ed2b7d0d` | workflow / creator_claim | Dental AI is positioned for lead follow-up, consultation booking, reminders, and patient recall. | Description bullet: “Lead follow-up, consultation booking, reminders, and patient recall.” | P | M | P | P | P | P | m | P | minor — four independently useful workflows are combined. |
| `2029ca0f-110d-4301-977c-b90a41bb36fb` | technology / creator_claim | The creator identifies operational boundaries for situations where AI should not operate. | Chapter title: “Where AI should not operate.” | m | P | M | M | M | P | P | M | poor — heading does not state a boundary and is not technology evidence. |
| `241223ae-34fd-429f-8973-3110cf8b22eb` | workflow / creator_claim | Dental AI is positioned for appointment booking, appointment changes, cancellations, and routine administrative tasks. | Description bullet: “Using Dental AI for appointment booking, changes, and routine admin”; chapter: “Book, reschedule and cancel appointments.” | P | M | P | P | P | P | m | P | minor — useful but compound and partly overlaps the prior workflow bundle. |

## Opportunity review

| opportunity_id | name | criterion | review |
| --- | --- | --- | --- |
| `7eea70c0-eeee-4db5-9cd0-ca73dcd42861` | AI receptionist and appointment-lead workflow management for dental practices | Naming clarity | pass — buyer and solution pattern are understandable. |
| same | same | Scope | correct — repeatable dental front-desk pattern, neither industry-wide nor one feature. |
| same | same | Customer specificity | minor_issue — dental context is clear, but the stored customer list mixes buyer organizations, staff, patients, and inferred subsegments. |
| same | same | Problem specificity | pass — missed/after-hours calls and request-routing burden are commercially meaningful. |
| same | same | Solution specificity | minor_issue — sellable workflow is clear, but `VitalDesk` makes the canonical solution vendor-specific. |
| same | same | Commercial cohesion | pass — 40 linked active signals consistently support front-desk/appointment workflows. |
| same | same | Duplication risk | pass — no other dental opportunity exists in the current database. |
| same | same | Evidence diversity | pass — four videos from four distinct channels. |
| same | same | Actionability | pass — a founder can investigate buyer workflows, integrations, handoffs, and sales motion. |
| same | same | Hype / claim discipline | minor_issue — no traction is invented, but the one-line thesis is a single VitalDesk feature rather than the broader evidence pattern. |

Overall verdict: `acceptable`. Desired normalized level: **AI receptionist and front-desk workflow
automation for dental practices**. “AI for healthcare” would be too broad; “VitalDesk dashboard for
appointment lead cards” would be too narrow.

## Translation review

All records preserve canonical originals separately. Proper names, claim strength, and evidence
projection integrity pass unless noted.

| entity / field | canonical | current zh-CN v001 | verdict / note |
| --- | --- | --- | --- |
| opportunity / name | AI receptionist and appointment-lead workflow management for dental practices | 面向牙科诊所的 AI 接待员和预约线索工作流管理 | good |
| opportunity / one_line_thesis | Dental appointment leads are organized inside the VitalDesk dashboard. | 牙科预约线索在 VitalDesk 仪表板内进行整理。 | minor_language_issue — faithful but stiff and literal. |
| opportunity / problem | Missed patient calls and after-hours inquiries, plus the administrative burden of capturing and routing appointment-related patient requests. | 漏接患者来电和非工作时间咨询，以及记录和分流与预约相关的患者请求所带来的行政负担。 | good |
| opportunity / solution | VitalDesk, an AI receptionist and dashboard for capturing patient communications and organizing front-desk workflows. | VitalDesk，一款用于记录患者沟通并整理前台工作流的 AI 接待员和仪表板。 | good |
| `0a74cce1` / evidence_text | “How dental appointment leads are organized inside the dashboard” | “牙科预约潜在客户如何在仪表板中进行整理” | minor_language_issue — `leads` is better rendered as `线索` in this context. |
| `0a74cce1` / statement | Dental appointment leads are organized inside the VitalDesk dashboard. | 牙科预约潜在客户在线索 VitalDesk 仪表板中进行整理。 | meaning_risk — malformed modifier order and duplicated lead sense. Recommended: `牙科预约线索会统一整理到 VitalDesk 仪表盘中。` |
| `3f5b6fcd` / evidence_text | “VitalDesk helps dental clinics answer patient calls, capture appointment requests, manage leads, and organize front-desk workflows” | “VitalDesk 帮助牙科诊所接听患者来电、获取预约请求、管理潜在客户并组织前台工作流程” | good |
| `3f5b6fcd` / statement | VitalDesk is positioned to capture appointment requests and organize front-desk workflows for dental clinics. | VitalDesk 的定位是为牙科诊所获取预约请求并组织前台工作流程。 | good — positioning remains qualified. |
| `4097d6ce` / evidence_text | “How patient calls and website chat requests are captured” | “如何捕获患者来电和网站聊天请求” | good |
| `4097d6ce` / statement | Patient calls and website chat requests can be captured by the product. | 患者来电和网站聊天请求可以由该产品捕获。 | minor_language_issue — correct but passive/calqued; `该产品可接收…` is more natural. |
| `63eda4a9` / evidence_text | “AI handles repetitive communication, call capture, and patient request routing 24/7” | “AI 全天候 24/7 处理重复性沟通、来电记录和患者请求路由” | good |
| `63eda4a9` / statement | VitalDesk uses an AI receptionist for repetitive patient communication, call capture, and request routing. | VitalDesk 使用 AI 接待员处理重复性的患者沟通、来电记录和请求路由。 | good |
| `6926dc73` / evidence_text | “How clinics can review conversation logs and request status” | “诊所如何查看对话日志和请求状态” | good |
| `6926dc73` / statement | Clinics can review conversation logs and request status in the product. | 诊所可以在产品中查看对话日志和请求状态。 | good |

## Local validation quality metrics

| Metric | Formula | Result |
| --- | --- | ---: |
| Signal Useful Rate | good + minor / reviewed | 18/20 (90%) |
| Signal Grounding Pass Rate | grounding pass / reviewed | 18/20 (90%) |
| Claim Preservation Pass Rate | claim pass / reviewed | 20/20 (100%) |
| Duplicate Signal Rate | substantially duplicative / reviewed | 2/20 (10%) |
| Opportunity Acceptable Rate | strong + acceptable / reviewed | 1/1 (100%) |
| Opportunity Over-broad Rate | over-broad / reviewed | 0/1 (0%) |
| Opportunity Duplicate Risk Rate | material merge risk / reviewed | 0/1 (0%) |
| Translation Good Rate | good / translated fields | 10/14 (71.4%) |
| Translation Meaning-Risk Rate | meaning_risk + unacceptable / translated fields | 1/14 (7.1%) |

## Observed failure modes and v001 weaknesses

1. Compound workflow lists survive the current atomicity instruction.
2. Generic headings can be elevated without the concrete information required to support them.
3. Selected `evidence_text` does not always support every element of the generated statement.
4. Similar workflow bundles create limited within-source redundancy.
5. Product capabilities and operational boundaries can receive imprecise categories.
6. Extraction-level customer text expands beyond explicit source scope.
7. The opportunity name is appropriately granular, but thesis/solution retain a vendor-feature lens.
8. Translation v001 lacks strong enough native-word-order and contextual `lead` guidance.

## Prompt changes made

- Added experimental `signal-extractor/v002`: evidence completeness, atomic splitting, heading
  rejection, category discipline, conservative customers, and redundancy control.
- Added experimental `opportunity-normalizer/v002`: buyer + problem/workflow + repeatable solution,
  vendor-neutral names, near-synonym matching, and REVIEW for uncertain granularity.
- Added experimental `intelligence-translation/zh-CN/v002`: native Chinese order, reduced calques and
  filler, contextual `lead`, proper-name and uncertainty preservation.
- v001 prompt hashes are frozen in regression tests; runtime defaults remain v001.

## v001 versus v002 comparison

The real A/B used identical inputs and `openai/gpt-5.6-terra` for each prompt pair. It was read-only:
the database contains zero `v002` AI extractions and zero `translation-zh-CN-v002` projections after
the run. Full structured outputs and prompt hashes are in `ab-results.json` beside this report.

| Pipeline | v001 | v002 | Human comparison |
| --- | --- | --- | --- |
| Signal extractor | 4 signals; 964 input / 366 output tokens | 6 signals; 1,189 input / 402 output tokens | v002 materially improves atomicity by splitting answer/caller-detail/scheduling workflows, corrects the free-audit CTA from `demand` to `distribution`, and narrows customer scope. Attribution remains `creator_claim`. One split workflow still uses a partial excerpt and should be watched for over-fragmentation. |
| Opportunity normalizer | MATCH current opportunity; 752 / 93 tokens | MATCH same opportunity; 906 / 96 tokens | Both make the correct non-duplicate decision and return the same canonical name. v002's reason is more explicitly buyer/problem/pattern-based, but this single case shows no material outcome gain. |
| Translation | 9 fields; 2,711 / 416 tokens; 6/9 good | 9 fields; 3,725 / 417 tokens; 8/9 good | Both avoid the previously persisted malformed word order on this stochastic rerun. v002 improves passive/calqued sentences and concise business phrasing while preserving `VitalDesk`, positioning, and `can`. One opportunity problem translation remains slightly awkward. |

Total A/B usage was 10,247 input and 1,790 output tokens. Structured output remained compatible in
all 16 provider calls. No major regression, claim-strength loss, proper-name loss, or invented
traction was observed. v002 prompts cost more input tokens because their instructions are longer.

## Promotion recommendation and reprocessing

**Decision: retain v001 runtime defaults and keep all three v002 prompts experimental.** Signal and
translation v002 are promising enough for broader validation, but one source video and nine
translation fields are insufficient to establish stable improvement or stochastic robustness.
Normalizer v002 produced no different action/name and needs more duplicate/granularity cases.

Recommended next reprocessing step is a separately authorized, bounded multi-video v002 extraction
run that creates new `ai_extractions`, leaves new signals in review, and compares duplication and
grounding before promotion. Translation promotion would change generation/read preference to
`translation-zh-CN-v002`, generate separate v002 rows, and preserve v001 history. Existing active
intelligence must not be overwritten.

## Remaining limitations

- One vertical, four source channels, one opportunity, metadata-only inputs, and one model family.
- Human labels are directional and have not been calibrated between multiple reviewers.
- Current lexical candidate retrieval cannot prove semantic duplicate avoidance.
- Translation review covers 14 fields, not broad terminology or long-form evidence.
- Single-run A/B cannot measure stochastic variance; repeated trials were intentionally avoided for
  cost control.
