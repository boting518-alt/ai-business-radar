# Signal semantic guardrails v0.1

TASK-044F adds a deterministic projection alongside the original FACT Signal. It does not rewrite
AI extraction raw/parsed output, claim_status, Signal category, source, links or prior scores.
The runtime remains Signal Extractor v003 with schema v001. v004 is experimental.

## Actor and evidence roles

`actor_role` describes the commercial subject of the individual observation, not a verified
identity or necessarily the narrator. Values: buyer, seller_vendor, creator_channel,
affiliate_referrer, platform_marketplace, featured_product_company, unknown. For example, a
creator relaying a buyer's order may contain buyer-side evidence. A role never verifies the claim.

`evidence_role` describes what the observation establishes: buyer_expression, seller_cta,
seller_claim, creator_monetization, product_monetization, product_pricing, observed_transaction,
third_party_observation, unknown. These are separate from both signal_type and claim_status.
The deterministic classifier assigns only supported roles; platform/third-party ownership may
remain unknown rather than inferred. Named-product ownership is not proof of fit to every linked
Opportunity; ambiguous cross-entity statements still need review.

Purchase intent requires explicit buyer willingness or action. Seller “buy/book/pre-order now”,
“call us” and limited-slot promotion cannot establish it. Conditional intent retains its condition;
negation, hypothetical/mixed expressions and unrecognized language route conservatively to review.
The statement itself must describe buying: a price-only statement cannot borrow a neighboring
purchase sentence from its excerpt to become purchase intent.

Pricing is a separate dimension. An explicit offered price, including a pre-order price, establishes
pricing only; it does not establish demand, completed sales or adoption. Existing score-v001 uses
pricing as a weighted revenue-evidence proxy. That formula remains unchanged and is not a claim of
realized revenue. Qualitative affordability without explicit price requires review in this version.

Revenue must concern the stated product/company's monetization. Creator/channel affiliate
commissions, Amazon Associate disclosures, referral income, video sponsorship and ad income are
creator_monetization, not featured-product revenue. Funding, valuation and forecasts route to
review. Rules inspect each Signal statement/excerpt, not unrelated whole-video boilerplate. Useful
creator monetization retained as distribution is labeled 创作者变现 / Creator monetization.

Adoption needs buyer/user action or an attributed usage/transaction claim. “500 clinics use X”
remains a claim. A feature, invitation, suggestion or vague claim of autonomous robot behavior is
insufficient. Rules do not upgrade model confidence into factual confidence.

## Persisted projection and audit

Migration 0021 adds checked Signal fields: semantic_status, actor_role, evidence_role,
guardrail_version, guardrail_decision, guardrail_reason_code, superseded_by. Decisions are accept,
review, reject_semantic. Status is current, under_review, invalid_semantic, superseded. Lifecycle
status is retained separately; an historically active row can remain active but semantically invalid.
Product-valid means `status = active AND semantic_status = current`.

`signal_semantic_audits` is append-only application history with source-input fingerprint, prior/new
semantic status, original/canonical category (identical: no silent reclassification), role, stable
reason, version, replacement ID, time and optional operator note. The original Signal's extraction
FK retains full model/prompt/raw-output lineage. RLS restricts audit rows to admins and filters
invalid evidence from ordinary direct Signal/explicit evidence reads. No cascade deletes history.
Legacy rows start current/unknown for additive migration compatibility; migration itself performs
no historical classification. The bounded repair covers the four risk categories, and normalization
and approval also evaluate legacy inputs. Legacy unknown is not a claim that a row was audited.

Stable reasons include seller_cta_not_purchase_intent, seller_cta_not_adoption,
affiliate_revenue_not_product_revenue, creator_monetization_scope, price_without_buyer_intent,
ambiguous_actor, ambiguous_revenue_owner, non_realized_revenue_scope, unverified_adoption_scope,
price_not_explicit, duplicate_current_evidence and human_semantic_approval.

## Runtime and review boundaries

Video extraction and comment mining persist all original proposed Signals and audit decisions in
the extraction-completion transaction. Rejected semantic proposals remain inspectable; only current
proposals may normalize or translate. Normalization evaluates before provider work, rechecks locked
state at completion, and cannot bypass semantic validity with force. Source-level completion locks
serialize concurrent normalization. Discovery pipeline selection excludes blocked proposals.

Existing signal_validation tasks receive semantic context. Open-task uniqueness and audit identity
make repeated repair idempotent. A deterministic invalid or superseded record cannot be approved.
An ambiguous case can be approved only through signal_validation with nonempty decision notes;
that explicit human override is audited. Ordinary match/create approval cannot bypass this step.
Reject/ignore retain original data. No Opportunity is automatically published, rejected or archived.

Feed, linked/explicit evidence, counts, activation readiness, trends and score repositories share
the effective-state predicate. Linked vs supporting relationships are still distinct. Translation
coverage and execution skip non-current or rejected/ignored Signals; stored translations remain.

## Conservative duplicate identity

A duplicate requires exactly equal source identity, extractor family, statement, evidence, category,
claim status and full commercial fields, plus a different completed extraction. Current active
validated evidence is retained; redundant later evidence points to it as superseded. Historical
comparison prefers the older active record. A review candidate reuses an already active equivalent.
A newer prompt version alone does not replace earlier evidence. Links and audit rows remain intact.

Different statements/excerpts/roles/context, multiple observations within the same extraction and
paraphrased or compound claims are not automatically merged. Source hashes include prompt versions,
so extraction input_hash alone cannot identify cross-version duplicates. There is no reliable span
identity in the existing schema. This is exact duplicate protection, not universal semantic dedupe;
manual claim-level lineage repair remains necessary for ambiguous replacements.

## Operator workflow and score repair

From apps/api, against the explicitly configured database:

```bash
uv run python scripts/audit_signal_semantics.py --status active --limit 100 --dry-run --output /tmp/semantic-plan.json
uv run python scripts/audit_signal_semantics.py --status active --limit 100 --apply --output /tmp/semantic-applied.json
uv run python scripts/recompute_semantic_impacts.py --audit-report /tmp/semantic-applied.json --output /tmp/corrected-history.json
uv run python scripts/recompute_semantic_impacts.py --audit-report /tmp/semantic-applied.json --output /tmp/corrected-history.json --apply
```

Review exact IDs, reasons, preserved buyer examples and score impacts before apply. Default audit
mode is dry-run, max100 active purchase_intent/revenue/adoption/pricing Signals. Apply locks selected
rows and commits the projection/audits/reviews together; failure rolls back. No source fetch or LLM.
Do not use an unbounded sweep or remove rows. CLI output contains the durable affected-opportunity
list needed for recovery. Repeat apply creates no duplicate decisions/review tasks.

Score repair first creates new trend-v001 snapshots for all three windows at the audit timestamp,
then appends score-v001 at that same timestamp. It never forces an update of old snapshots or
scores. Repeat with the same original applied report reuses identical results. Each opportunity's
history is recoverable independently if a later opportunity fails. No formula coefficient changes.
Total score may rise versus an older historical score because the window/time changed; compare
same-time inputs to isolate semantic impact. Old snapshots/scores remain explicitly historical.

## Evaluation and limitations

40 curated real cases cover all34 local risk-category Signals plus six pain/workflow/distribution
controls, v001/v003 and video/comment sources. No active v002 example exists in that population.
Single-agent labels are a regression aid, not independent adjudication. A separate same-input live
v003/v004 comparison uses four persisted videos/eight calls, with raw output, hashes, model and token
audit in artifacts; it never writes product data or switches runtime. Buyer comment preservation is
covered by real-data deterministic tests, not by the metadata-only extractor benchmark.

Report precision with denominators and coverage/recall: conservative review can hide legitimate
buyer evidence pending review. Actor/role accuracy remains limited, particularly for multilingual
comments and third-party ownership. Regex rules are bounded recognition, not complete natural-
language understanding. New paraphrases may route to review; general grounding and atomicity still
require model/human quality work. v004 stays KEEP_EXPERIMENTAL because the small reused development
sample cannot establish production superiority and compound assertions remain.
