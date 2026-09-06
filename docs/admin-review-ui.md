# Admin Review UI v0.1

## Purpose and API contract note

`/admin/review` is the admin-only workstation for inspecting, claiming, and resolving persisted
review tasks through the transactional Review Workflow API. The frontend never writes the database
directly and does not reproduce backend decision validation as an authority.

Before TASK-026, `ReviewTaskResult.context` exposed only persisted workflow identifiers for
normalization tasks. That was sufficient for transactional validation but insufficient for the
required human review of source signals, candidate opportunities, or merge sides. TASK-026 therefore
adds a minimal read-only presentation projection to the existing detail response. It does not add an
endpoint or alter stored context, lifecycle, authorization, decisions, or domain effects. The
projection contains safe Signal and Opportunity fields only and excludes AI raw output, provider
identifiers, extraction errors, and scoring internals.

## Queue layout and filters

The desktop workspace uses a fixed-width queue beside a flexible detail pane and collapses to one
column on smaller screens. `status`, `review_type`, `assigned_to`, `offset`, and `selected` are URL
state so filtered queues and selections can be bookmarked. Status defaults to `pending`; pages are
bounded to 25 tasks. The API does not return a total, so next-page availability is inferred only
from a full page.

## Claim and decision lifecycle

Pending tasks must be claimed before action. An in-review task exposes decisions only to its
assignee; tasks owned by another admin and terminal tasks are read-only. Claim and decision calls
wait for the backend response before changing domain-facing state. A successful decision refreshes
the queue and selects the next available task. `defer` returns the task to the pending queue.

The UI presents the decision matrix from the frozen workflow specification, while the backend
remains authoritative and revalidates every transition and target.

Activation reviews show the opportunity definition, six readiness checks, advisory recommendation,
and score/confidence/hype/momentum context. Actions are labeled Publish, Defer, and Invalid rather
than generic approve/reject. Publish requires a Radar-visibility confirmation; Invalid requires a
stronger rejected-state confirmation. Both use the existing review decision endpoint, and displayed
metrics explicitly do not control publication.

## Review context

Signal, match, creation, hype, and quality reviews show safe, human-readable signal evidence and
proposal fields. Match and creation reviews show the bounded candidate opportunities supplied by
the detail response. The interface does not edit scores, Hype Risk, stage, extraction output, or
canonical records.

Merge review presents source and canonical opportunity context side by side. A merge target can be
selected only from the task's bounded candidate context. Confirmation uses an explicit dialog that
warns that evidence and active links move to the canonical record while the source and historical
records are preserved.

## Errors, authorization, and privacy

The server layout and API both enforce the admin role; the client also fails closed if role lookup
does not return `admin`. A 409 is shown as a stale-task conflict and prompts a refresh, while 404 and
422 responses use safe API messages. Available request IDs remain visible for support correlation.
Submission controls are disabled while a request is running, preventing duplicate decisions.

Notes are optional audit text and bounded to 2,000 characters. Raw AI output, provider identifiers,
input hashes, extraction errors, score inputs, and arbitrary context JSON are never rendered.

## v0.1 limitations

The queue endpoint has no total count. `assigned_to` remains an exact admin UUID filter because no
admin-directory endpoint exists. Merge selection is intentionally limited to the candidates frozen
into the task context. PostgreSQL-backed projection coverage requires `TEST_DATABASE_URL` when the
integration suite is run.
