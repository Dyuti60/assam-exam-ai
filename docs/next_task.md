> Append-only task history: prior task prompts must not be deleted.

# T-001 — Documentation workflow baseline

## Goal

Establish the repository's living architecture, workflow/component register, append-only task log, and current-task record.

## Scope

Add only these documentation files:

- `docs/architecture.md`
- `docs/workflow.md`
- `docs/task_log.md`
- `docs/next_task.md`

Base implementation-status statements on the inspected repository. Keep planned behavior visibly separate from implemented behavior. Do not claim tests passed unless they were run.

## Constraints

This task only adds documentation. It must not change:

- application code;
- models;
- migrations;
- dependencies or lockfiles;
- tests.

Do not commit. Before handoff, run `git diff --check` and `git status --short`, then report the created files, concise result, command results, and any mismatch or concern.

## Status

Ready for review.

---

# T-002 — Record verification evidence provenance

Read AGENTS.md and the docs first.

Implement only the missing Verification → Evidence audit link.

- Create a new Alembic migration; do not edit the existing initial migration.
- Add a `verification_evidence` association model/table linking `Verification` and `Evidence`.
- Store `evidence_role` (`SUPPORTS`, `CONTRADICTS`, `CONTEXT`) and non-negative `position`.
- Add database constraints for valid roles and position.
- Add typed SQLAlchemy relationships needed to traverse Verification → used evidence.
- Add PostgreSQL-backed tests proving a verification retains its ordered evidence and invalid role/position is rejected.
- Do not add APIs, ingestion, embeddings, LLMs, review workflows, content generation, or PDFs.

Before handoff, update project documents:

- In `docs/workflow.md`, add the new model, migration, tests, and updated provenance flow diagram.
- In `docs/task_log.md`, retain T-001, mark its implementation commit as `de55bb16dd7d3a8a0a276812d1cddf35abb3ba9c`, append T-002 as “Ready for review,” and record exact test results.
- In `docs/architecture.md`, correct the trust rule and date, then update the data model and remove only gaps resolved by this task.
- Do not replace `docs/next_task.md` with a future task.

Run relevant tests, `uv run ruff check .`, migration checks against a safe test database, and `git diff --check`. Do not commit. Report changed files, exact command results, migration behavior, and any blocker.

---

# T-003 — Minimal end-to-end knowledge API

Read AGENTS.md and the docs first.

Build one small, manual internal API flow that works end to end:

Source → Evidence → Claim → Verification → returned verification provenance

- Add versioned API endpoints to create a Source, Evidence, Claim, and Verification, plus retrieve a Verification by id.
- Creating a Verification must accept ordered evidence items with evidence_id, evidence_role, and position.
- The returned Verification must include its Claim and ordered evidence provenance.
- Use Pydantic schemas, a service/use-case layer, and a repository layer; keep routes thin.
- Return clear 404/validation errors for missing source, claim, or evidence ids.
- Add API/integration tests covering the complete happy path and one invalid-reference case.
- Do not add LLMs, document ingestion, embeddings, human review, authentication, a UI, payments, or PDFs.

Before handoff, append this task's changed functions, flow, tests, and exact results to docs/workflow.md; append the outcome to docs/task_log.md; and update docs/architecture.md only for confirmed architectural changes. Keep this append-only task history and do not delete earlier prompts.

Run the relevant tests, uv run ruff check on changed files, and git diff --check. Do not commit. Report changed files and exact results.

Implementation note (2026-09-03 Asia/Kolkata, UTC+05:30): implemented the five-endpoint internal flow with Pydantic schemas, a knowledge service and repository, ordered provenance responses, and API integration coverage. Final results are recorded in `docs/task_log.md` and `docs/workflow.md`.

Review note (2026-09-04 Asia/Kolkata, UTC+05:30): added API coverage proving a missing Evidence reference returns 404 without creating a partial Verification or provenance link.


---

# T-004 — Synchronize Claim verification summary

Read `AGENTS.md` and the project documents first.

## Goal

Make the existing manual API flow internally consistent. When a Verification is successfully created, update the linked Claim's current verification summary in the same transaction:

- `verification_status` = the new Verification verdict;
- `confidence` = the new Verification confidence;
- `last_verified_at` = the new Verification's creation time.

The Verification remains the immutable attempt/audit record. The Claim fields are only the latest summary for this small MVP; this is **not** human approval.

## Scope

- Implement the summary update in the existing service/repository flow; keep routes thin.
- Ensure no Claim summary changes if Verification creation fails, including a missing Evidence reference.
- The existing create/get Verification response must show the updated Claim values.
- Add or adjust API/integration tests for a successful summary update and failure atomicity.
- Do not add a migration unless a database schema change is genuinely required.
- Do not add LLMs, ingestion, embeddings, human-review workflows, authentication, UI, payments, PDFs, or content generation.

## Documentation and checks

Before handoff, update `docs/architecture.md`, `docs/workflow.md`, and `docs/task_log.md` with confirmed changes, functions, tests, and exact results. Keep this `docs/next_task.md` history append-only; do not delete prior task prompts.

Run relevant tests, the full suite, Ruff on changed files, `git diff --check`, and migration checks if applicable. Do not commit or push. Report changed files, exact results, and any concern.

Implementation note: successful Verification creation now synchronizes the Claim's latest `verification_status`, `confidence`, and `last_verified_at` in the same transaction. Failed verification creation leaves the Claim summary unchanged. This is a latest-verification summary, not human approval. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-005 — Retrieve a Claim summary

Read `AGENTS.md` and the project documents first.

## Goal

Make the current internal workflow easier to inspect after data has been created. Add exactly one endpoint:

`GET /api/v1/claims/{claim_id}`

It must return the existing `ClaimResponse`, including the Claim statement and its current `verification_status`, `confidence`, and `last_verified_at` summary.

## Scope

- Add the thin route, service/use-case method, and repository lookup consistent with the T-003 layering.
- Return HTTP 404 with the existing clear missing-resource style when the Claim does not exist.
- Add API/integration coverage for successful retrieval after a Verification was created and for a missing Claim.
- Do not return a Verification history or add list/search endpoints in this task.
- Do not add a migration unless a database schema change is genuinely required.
- Do not add LLMs, ingestion, embeddings, human-review workflows, authentication, UI, payments, PDFs, or content generation.

## Documentation and checks

Before handoff, update `docs/architecture.md`, `docs/workflow.md`, and `docs/task_log.md` with confirmed changes, functions, tests, and exact results. Keep this `docs/next_task.md` history append-only; do not delete prior task prompts. Append a short implementation note beneath T-005.

Run relevant tests, the full suite, Ruff on changed files, `git diff --check`, and migration checks if applicable. Do not commit or push. Report changed files, exact results, and any concern.

Implementation note (2026-09-04 Asia/Kolkata, UTC+05:30): added `GET /api/v1/claims/{claim_id}` through the existing route, service, and repository layers. The response uses `ClaimResponse` to expose the current latest-verification summary, and a missing Claim returns the established clear 404. Exact verification results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-006 — Link a Claim to relevant Evidence

Read `AGENTS.md` and the project documents first.

Activate the existing `claim_evidence` association so the manual knowledge flow records Evidence relevant to a Claim. This is separate from `VerificationEvidence`, which records the exact evidence used by one verification attempt.

- Add exactly one endpoint: `POST /api/v1/claims/{claim_id}/evidence/{evidence_id}`.
- The operation must be idempotent: duplicate linking must not create another association row and must succeed.
- Extend `GET /api/v1/claims/{claim_id}` to return linked relevant evidence IDs in stable order; do not return full Evidence text.
- Return the existing clear 404 style for a missing Claim or Evidence.
- Add typed ORM traversal only if needed. Add a migration only for a genuine schema change.
- Add API/integration tests for success, idempotency, retrieval, and one missing-resource case.
- Do not add LLMs, ingestion, embeddings, human review, authentication, UI, payments, PDFs, content generation, search, or list endpoints.

Before handoff, update `docs/architecture.md`, `docs/workflow.md`, and `docs/task_log.md`; append a T-006 implementation note here without deleting history. Run relevant tests, the full suite, Ruff on changed files, `git diff --check`, and migration checks if applicable. Do not commit or push.

Implementation note (2026-09-04 Asia/Kolkata, UTC+05:30): added the idempotent `POST /api/v1/claims/{claim_id}/evidence/{evidence_id}` endpoint and extended Claim retrieval with stable, ID-only `relevant_evidence_ids`. Relevant Claim evidence remains separate from Verification audit evidence. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.

Correction note (2026-09-04 Asia/Kolkata, UTC+05:30): Claim–Evidence insertion now uses the existing composite primary key with PostgreSQL `ON CONFLICT DO NOTHING`, guaranteeing concurrent duplicate requests do not create another row or raise a uniqueness error. The Claim is freshly reloaded before its numerically sorted evidence IDs are returned.


---

# T-007 — Retrieve an Evidence record

Read `AGENTS.md` and project documents first.

Add exactly one endpoint: `GET /api/v1/evidence/{evidence_id}`. It must return the existing `EvidenceResponse` with the Evidence content, `source_id`, and optional location reference. Use the existing route → service → repository layering and clear 404 style. Add API/integration tests for successful retrieval and missing Evidence.

Do not add Source retrieval, lists, search, history, LLMs, ingestion, embeddings, human review, authentication, UI, payments, PDFs, or content generation. Do not add a migration unless a database schema change is genuinely required.

Update architecture, workflow, task log, and append a T-007 implementation note here. Run relevant tests, full suite, changed-file Ruff, git diff --check, and migration checks if applicable. Do not commit or push.

Implementation note (2026-09-04 Asia/Kolkata, UTC+05:30): added `GET /api/v1/evidence/{evidence_id}` through the existing route, service, and repository layers. It returns the existing `EvidenceResponse`, including content, `source_id`, and optional location reference, with the established clear 404 for missing Evidence. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-008 — Add Claim human approval state

Read `AGENTS.md` and all project documents first.

Add the smallest explicit human-approval boundary for Claims. Verification remains an evidence-based assessment; it must not automatically publish a Claim.

- Add a new migration and model fields on Claim for a human decision: `DRAFT`, `APPROVED`, or `REJECTED`; decision timestamp; optional reviewer note. Use appropriate PostgreSQL constraints/defaults.
- Add one endpoint to record the human decision for an existing Claim: `POST /api/v1/claims/{claim_id}/approval`.
- Extend Claim retrieval to return the approval state, timestamp, and reviewer note.
- A missing Claim returns the existing clear 404. Invalid approval state returns 422.
- Add PostgreSQL/API tests covering default DRAFT, approve, reject, and invalid/missing Claim cases.
- Do not add authentication yet: use a reviewer note only, not user identity. Do not add AI, ingestion, notes, MCQs, UI, payments, PDFs, or bulk/list/search endpoints.

Update all project documents and append an implementation note here. Run relevant tests, full suite, changed-file Ruff, migration upgrade/downgrade/checks, and `git diff --check`. Do not commit or push.

Implementation note (2026-09-04 Asia/Kolkata, UTC+05:30): Claims now have a constrained human approval state (`DRAFT`, `APPROVED`, or `REJECTED`), decision timestamp, and optional reviewer note. Added `POST /api/v1/claims/{claim_id}/approval`; verification remains a separate evidence assessment and never changes approval state. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-009 — Read approved knowledge

Read `AGENTS.md` and project documents first.

Add exactly one endpoint: `GET /api/v1/claims/approved`.

It returns a stable ID-ascending list of existing `ClaimResponse` objects only where `approval_status == APPROVED`. Each response must retain the Claim's relevant evidence IDs and verification/approval summaries. It is the first safe read boundary for future notes/MCQ generation.

- Keep routes thin and use the existing route → service → repository layering.
- Ensure this static route is registered before `GET /api/v1/claims/{claim_id}` so `approved` is not interpreted as an ID.
- Return an empty list when there are no approved Claims.
- Add API/integration tests proving DRAFT and REJECTED Claims are excluded, APPROVED Claims are included in ID order, and an empty result works.
- Do not add pagination, filtering, search, topic/syllabus, LLMs, ingestion, content generation, UI, authentication, payments, or PDFs.
- No migration unless a genuine database schema change is needed.

Update all four project documents and append an implementation note here. Run relevant tests, full suite, changed-file Ruff, git diff --check, and migration checks if applicable. Do not commit or push.

Implementation note (2026-09-04 Asia/Kolkata, UTC+05:30): added the static `GET /api/v1/claims/approved` route before `GET /api/v1/claims/{claim_id}`. It returns only explicitly approved Claims in stable ascending ID order using the existing route, service, repository, and `ClaimResponse` flow, retaining relevant Evidence IDs and verification/approval summaries. No migration or content-generation feature was added; exact verification results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-010 — Add a Topic to Claims

Read `AGENTS.md` and project documents first.

Add minimal topic classification needed before topic-based notes/MCQs.

- Add a `topics` table/model with only: id, unique name, and created_at.
- Add a nullable `topic_id` foreign key on Claim. No topic hierarchy, syllabus, tags, or search.
- Add `POST /api/v1/topics` to create a Topic.
- Extend Claim creation to accept optional `topic_id`, returning 404 when it does not exist.
- Extend ClaimResponse to include topic_id.
- Add one migration; do not edit prior migrations. Existing Claims must remain valid with null topic_id.
- Add API/PostgreSQL tests for Topic creation, Claim assignment, missing Topic, unique name, and migration upgrade/downgrade.
- Do not add LLMs, ingestion, notes/MCQs, content generation, UI, authentication, lists/search, topic hierarchy, syllabus management, payments, or PDFs.

Update all project docs and append an implementation note here. Run relevant tests, full suite, changed-file Ruff, migration upgrade/downgrade/check, and git diff --check. Do not commit or push.

Implementation note (2026-09-04 Asia/Kolkata, UTC+05:30): added the minimal unique-name `Topic` model and `POST /api/v1/topics`, plus nullable Claim `topic_id` assignment with clear missing-Topic handling. Migration `e4a6c8d1f203` preserves existing Claims with null `topic_id` and uses `ON DELETE SET NULL`; no hierarchy, syllabus, search, notes, MCQs, or content generation was added. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.

Correction note (2026-09-04 Asia/Kolkata, UTC+05:30): duplicate `POST /api/v1/topics` requests now rely on the PostgreSQL unique constraint, roll back the SQLAlchemy session after `IntegrityError`, and return HTTP 409 with `{"detail": "Topic name '<name>' already exists"}`. No Topic schema, migration, Claim behavior, or unrelated feature changed.


---

# T-011 — Read approved knowledge by Topic

Read `AGENTS.md` and project documents first.

Add exactly one endpoint: `GET /api/v1/topics/{topic_id}/claims/approved`.

It returns a stable ID-ascending list of `ClaimResponse` objects whose `topic_id` matches and whose approval state is exactly `APPROVED`. Keep relevant Evidence IDs and verification/approval summaries. This is the focused, safe input for a future Topic notes/MCQ draft generator.

- Return the existing clear 404 for a missing Topic.
- Return `[]` when the Topic exists but has no approved Claims.
- Use eager loading for relevant Evidence and avoid N+1 queries.
- Add API/integration tests for missing Topic, empty Topic, exclusion of DRAFT/REJECTED/wrong-topic Claims, and stable order of APPROVED Claims.
- Do not add a notes/MCQ generator, LLMs, prompts, ingestion, embeddings, topic listing/search, topic hierarchy, UI, authentication, payments, or PDFs.
- No migration unless a genuine schema change is necessary.

Update all four documents and append an implementation note here. Run relevant tests, full suite, changed-file Ruff, `git diff --check`, and migration checks if applicable. Do not commit or push.

Implementation note (2026-09-04 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/topics/{topic_id}/claims/approved` through the existing route, service, repository, and `ClaimResponse` flow. It returns exact-Topic, explicitly approved Claims in ascending ID order with eagerly loaded relevant Evidence IDs and existing summaries; missing Topic returns 404 and an existing empty Topic returns `[]`. No migration or generation feature was added; exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-012 — Preview a safe Topic note draft

Read `AGENTS.md` and all project documents first.

Build one small, deterministic internal note-preview flow that proves the working path from approved knowledge to a note-shaped draft:

`Topic → explicitly APPROVED Claims → internal Markdown draft`

- Add exactly one endpoint: `POST /api/v1/topics/{topic_id}/note-draft-preview`.
- It must first confirm the Topic exists and use only that Topic’s explicitly `APPROVED` Claims, in ascending Claim ID order.
- Return a new Pydantic response containing `topic_id`, `topic_name`, ordered `claim_ids`, and `markdown`.
- The Markdown must be deterministic: a Topic heading followed by the approved Claim statements as ordered bullet points. Do not invent, paraphrase, enrich, or add facts.
- It must not persist a note, change Claim/approval/verification data, or publish content.
- Missing Topic: use the established clear 404. Existing Topic with no approved Claims: return HTTP 409 with one stable, clear detail.
- Reuse existing approved-Claim retrieval where sensible; keep route → service → repository boundaries clear.
- Add API/integration tests for missing Topic, empty approved knowledge, only APPROVED/matching-Topic Claims, stable order, exact Markdown, and no persisted-state mutation.
- No LLM/provider credentials, prompts, ingestion, embeddings, source scraping, note storage/history, human approval of notes, MCQs, UI, auth, payments, or PDFs.
- No migration unless a genuine schema change is required.

Update all four documents and append an implementation note here. Run relevant tests, the full suite, changed-file Ruff, `git diff --check`, and migration checks if applicable. Do not commit or push.

Implementation note (2026-09-05 Asia/Kolkata, UTC+05:30): added only `POST /api/v1/topics/{topic_id}/note-draft-preview`. It confirms the Topic, reuses the ordered Topic-scoped approved-Claim query, and returns deterministic Markdown containing the Topic heading and unchanged approved Claim statements as bullets. Missing Topic returns 404, no approved Claims returns a stable 409, and the preview performs no persistence or state mutation. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-013 — Persist a Topic note draft with Claim provenance

Read `AGENTS.md` and all project documents first.

Turn the current deterministic preview into one traceable, stored internal draft. This is still not AI generation and not publication.

- Add a new migration, a `NoteDraft` model/table, and a `note_draft_claims` association that records the exact ordered Claims used by a draft.
- A NoteDraft must store only: id, topic_id, markdown, created_at. Its Claim association must preserve a non-negative `position`; use database constraints and uniqueness appropriate to the association.
- Add exactly one endpoint: `POST /api/v1/topics/{topic_id}/note-drafts`.
- It must confirm the Topic, load only that Topic’s explicitly `APPROVED` Claims in ascending Claim ID order, render exactly the same deterministic Markdown contract as T-012, and persist the NoteDraft plus ordered Claim links atomically.
- Return a new response with the draft id, topic id/name, created_at, ordered claim IDs, and markdown.
- Missing Topic: established 404. Existing Topic with no approved Claims: the same stable 409 detail as T-012.
- A persisted draft is always an internal **DRAFT** by meaning: do not add a draft approval/publish field or endpoint yet; do not imply it is ready for learners.
- Add PostgreSQL/API tests for migration upgrade/downgrade, successful persisted content/provenance/order, missing Topic, no approved Claims, exclusion of DRAFT/REJECTED/wrong-topic Claims, and atomicity (no NoteDraft or links on failure).
- Do not add an LLM/provider, prompts, ingestion, embeddings, source scraping, draft retrieval/listing/editing/deleting, note approval, MCQs, UI, auth, payments, or PDFs.
- Do not edit prior migrations.

Update all four documents and append an implementation note here. Run relevant tests, the full suite, changed-file Ruff, migration upgrade/downgrade/checks, and `git diff --check`. Do not commit or push.

Implementation note (2026-09-05 Asia/Kolkata, UTC+05:30): added only `POST /api/v1/topics/{topic_id}/note-drafts`, the `NoteDraft`/`NoteDraftClaim` persistence models, and migration `b7d9e2f4a610`. The endpoint reuses the exact T-012 Markdown renderer and Topic-scoped approved-Claim query, then atomically stores the internal draft and position-ordered Claim provenance. Missing/empty knowledge retains the established 404/409 behavior with no partial rows. Stored drafts have internal DRAFT meaning only; no approval, publication, retrieval, generation, or unrelated feature was added. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.

Correction note (2026-09-05 Asia/Kolkata, UTC+05:30): extended the T-013 PostgreSQL constraint coverage to prove the `note_draft_claims` composite primary key rejects a duplicate Claim within the same NoteDraft even when the attempted position is different and valid. No application code, model, migration, endpoint behavior, or task scope changed.


---

# T-014 — Retrieve a stored internal note draft

Read `AGENTS.md` and all project documents first.

Add exactly one endpoint: `GET /api/v1/note-drafts/{note_draft_id}`.

It returns the existing `NoteDraftResponse`: draft id, Topic id/name, created time, stored Markdown, and the exact Claim IDs in their stored `position` order.

- Use the existing route → service → repository layers.
- Eagerly load the Topic and Claim links; avoid N+1 queries.
- Missing draft returns the established clear 404 style: `{"detail": "NoteDraft <id> not found"}`.
- The result must be the stored snapshot: do not regenerate Markdown, re-query current approved Claims, or change any database state.
- Add API/integration tests for successful retrieval after persistence, exact stored Claim-link order, missing draft, and proof that changing a linked Claim’s approval state after draft creation does not alter the stored draft response.
- Do not add a migration unless a genuine schema change is necessary.
- Do not add draft editing, deletion, approval/publishing, an LLM, prompts, ingestion, embeddings, MCQs, UI, auth, payments, or PDFs.

Update all four documents and append an implementation note here. Run relevant tests, full suite, changed-file Ruff, `git diff --check`, and migration checks if applicable. Do not commit or push.

Implementation note (2026-09-05 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/note-drafts/{note_draft_id}` through the existing route, service, and repository layers. Retrieval eagerly loads the Topic and position-ordered Claim links, returns the stored `NoteDraftResponse`, and never regenerates Markdown, queries current approved Claims, or mutates state. A missing draft returns the established exact 404; changing a linked Claim's approval after creation leaves the stored response unchanged. No migration or unrelated draft operation was added. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-015 — Add human approval state to NoteDrafts

Read `AGENTS.md` and all project documents first.

Add the smallest explicit human-review decision for a stored NoteDraft. This is separate from approval of its individual Claims and still does not publish learner content.

- Add a new migration and NoteDraft fields for `approval_status` (`DRAFT`, `APPROVED`, `REJECTED`), `approval_decided_at`, and optional `reviewer_note`. Add appropriate PostgreSQL constraints/defaults. Existing drafts must become `DRAFT` with null decision metadata.
- Add exactly one endpoint: `POST /api/v1/note-drafts/{note_draft_id}/approval`.
- Reuse or add a clear Pydantic request schema. Extend `NoteDraftResponse` to include the draft approval fields.
- `APPROVED` and `REJECTED` set the current UTC decision time and preserve the supplied note. Setting `DRAFT` clears both decision time and note.
- A missing draft returns the established clear 404. Invalid status returns standard 422 validation.
- Draft approval must not change the stored Markdown, Claim links, Claim approval states, or Claim verification summary.
- Add PostgreSQL/API tests for default state, approve, reject, DRAFT reset semantics, missing/invalid input, migration upgrade/downgrade, and preserving the stored snapshot/provenance.
- Do not add authentication or reviewer identity yet; the reviewer note is not identity. Do not add publication/read-list endpoints for approved drafts, editing, LLMs, prompts, ingestion, embeddings, MCQs, UI, payments, or PDFs.
- Do not edit prior migrations.

Update all four documents and append an implementation note here. Run relevant tests, full suite, changed-file Ruff, migration upgrade/downgrade/checks, and `git diff --check`. Do not commit or push.

Implementation note (2026-09-05 Asia/Kolkata, UTC+05:30): added only the independent NoteDraft review fields, migration `d4f8a1c7e592`, and `POST /api/v1/note-drafts/{note_draft_id}/approval`. New drafts and migrated drafts default to DRAFT with null decision metadata; APPROVED/REJECTED record UTC time and the supplied note, while DRAFT clears both. Tests confirm the decision never changes stored Markdown, ordered Claim provenance, or Claim approval/verification state. This remains internal review, not publication; exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-016 — Read approved internal note drafts

Read `AGENTS.md` and all project documents first.

Add exactly one endpoint: `GET /api/v1/note-drafts/approved`.

It returns a stable ID-ascending list of `NoteDraftResponse` objects only where the NoteDraft's own `approval_status == APPROVED`. This is the safe internal downstream boundary for eventually rendering or packaging reviewed notes.

- Register this static route before `GET /api/v1/note-drafts/{note_draft_id}`.
- Eagerly load Topic and ordered Claim links; avoid N+1 queries.
- Return stored Markdown and stored ordered Claim IDs. Do not regenerate content or re-evaluate current Claim approvals.
- Return `[]` when no approved drafts exist.
- Add API/integration tests proving DRAFT and REJECTED drafts are excluded, APPROVED drafts are included in ID order, stored snapshots remain unchanged after linked Claim approval changes, and an empty result works.
- Do not add a migration unless a genuine schema change is necessary.
- Do not add publication/release state, PDFs, public or learner endpoints, drafts edits/deletes, LLMs, prompts, ingestion, embeddings, MCQs, UI, auth, payments, or relevance scoring.

Update all four documents and append an implementation note here. Run relevant tests, full suite, changed-file Ruff, `git diff --check`, and migration checks if applicable. Do not commit or push.

Implementation note (2026-09-05 Asia/Kolkata, UTC+05:30): added only the static `GET /api/v1/note-drafts/approved` route before the dynamic NoteDraft ID route. It returns NoteDrafts whose own approval state is exactly APPROVED in ascending ID order, with eagerly loaded Topic and stored ordered Claim provenance. Responses use stored Markdown and Claim IDs without regeneration or current Claim-approval evaluation; no migration or publication feature was added. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-017 — Record sourced syllabus versions and Topics

Read `AGENTS.md` and all project documents first.

Build the first data foundation for exam-relevance assessment. This task records what an official syllabus covers; it must not calculate relevance, likelihood, or exam probability.

- Add a new migration and minimal models/tables for:
  - `Exam`: id, unique short `code`, unique `name`, created_at.
  - `SyllabusVersion`: id, `exam_id`, `source_id`, unique per-Exam `label`, created_at.
  - `syllabus_version_topics`: ordered association between a SyllabusVersion and existing Topics, with non-negative `position`, unique position within a version, and one link per version/Topic.
- SyllabusVersion must reference the existing Source that documents the syllabus. Use deletion restrictions that protect a sourced syllabus record and its Topic mappings.
- Add `POST /api/v1/exams` to create an Exam.
- Add `POST /api/v1/syllabus-versions` to atomically create a SyllabusVersion with its ordered, non-empty `topic_ids` list.
- Return a response containing the persisted ids, source id, label, created_at, and Topic IDs in stored position order.
- Use existing route → schema → service → repository layering. Missing Exam, Source, or Topic must use the established clear 404 style; duplicate Exam code/name or duplicate syllabus label for one Exam must return stable HTTP 409; duplicate Topic IDs or invalid positions/input must return 422.
- Add PostgreSQL/API tests for successful ordered persistence, missing references with no partial rows, duplicate Exam and syllabus-version conflicts, association constraints, and migration upgrade/downgrade/re-upgrade.
- Do not add actual syllabus data, web scraping, PDF ingestion, past-paper questions, Topic hierarchy, exam relevance scores/percentages, LLMs, MCQs, UI, auth, payments, or PDFs.
- Do not edit prior migrations.

Update all four documents and append an implementation note here. Run relevant tests, full suite, changed-file Ruff, migration upgrade/downgrade/checks, and `git diff --check`. Do not commit or push.

Implementation note (2026-09-05 Asia/Kolkata, UTC+05:30): added only unique Exam identity plus sourced, labeled SyllabusVersion records and non-empty position-ordered Topic mappings through `POST /api/v1/exams` and `POST /api/v1/syllabus-versions`. Migration `f6b3c9a2d741` uses database uniqueness/position constraints and deletion restrictions to preserve syllabus provenance. Missing references remain atomic 404s, conflicts return stable 409s, and invalid Topic lists return 422. No actual syllabus data, relevance or probability calculation, past-paper data, or content feature was added. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-018 — Record sourced previous-paper question occurrences

Read `AGENTS.md` and all project documents first.

Add the smallest historical-evidence foundation needed for future exam-priority bands. Record what appeared in a sourced previous paper; do not calculate relevance or probability.

- Add one migration and minimal models:
  - `PreviousPaper`: id, `exam_id`, `source_id`, year, label, created_at; label is unique per Exam/year.
  - `PreviousQuestion`: id, `previous_paper_id`, `topic_id`, non-negative position, question text, optional source location reference, created_at.
- A paper must cite an existing Source. Each recorded question must belong to one paper and one existing Topic. Position must be unique within a paper.
- Protect referenced Exam, Source, Topic, PreviousPaper, and PreviousQuestion provenance with appropriate PostgreSQL constraints/deletion restrictions.
- Add `POST /api/v1/previous-papers`.
- Add `POST /api/v1/previous-questions`.
- Use the existing route → schema → service → repository layering. Missing references return the established 404 style; duplicate paper label/year or question position returns stable 409; invalid year, position, or blank text returns 422.
- Add PostgreSQL/API tests for successful creation, exact source/location/topic linkage, conflicts, missing references without partial rows, database constraints, and migration upgrade/downgrade/re-upgrade.
- Do not add answers or explanations, import/scraping, syllabus retrieval, multi-Topic tagging, relevance bands/scores/percentages, LLMs, generated MCQs, UI, auth, payments, or PDFs.
- Do not edit prior migrations.

Update `docs/architecture.md`, `docs/workflow.md`, and append-only records in `docs/task_log.md` and `docs/next_task.md`. Run focused tests, full suite, changed-file Ruff, migration upgrade/downgrade/checks, and `git diff --check`. Do not commit or push.

Implementation note (2026-09-05 Asia/Kolkata, UTC+05:30): added only sourced `PreviousPaper` records and exact Topic-linked `PreviousQuestion` occurrences through `POST /api/v1/previous-papers` and `POST /api/v1/previous-questions`. Migration `a8c4e1d7f620` enforces positive years, non-negative per-paper unique positions, non-blank question text, per-Exam/year paper-label uniqueness, and restrictive provenance foreign keys. Missing references remain atomic 404s, named uniqueness conflicts return stable 409s, and invalid inputs return 422. No answers, explanations, ingestion, relevance/probability calculation, or generated questions were added. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-019 — Calculate an explainable Topic priority band

Read `AGENTS.md` and all project documents first.

Add one read-only deterministic assessment that combines a selected sourced syllabus version with stored previous-paper occurrences. It is an exam-priority aid, never an appearance probability.

Add exactly one endpoint:

`GET /api/v1/syllabus-versions/{syllabus_version_id}/topics/{topic_id}/priority`

Return:

- `syllabus_version_id`, `exam_id`, and `topic_id`;
- `syllabus_covered`;
- `exam_paper_count`: all stored PreviousPapers for that Exam;
- `matched_question_count`, `matched_paper_count`, and sorted unique `matched_years`;
- `priority_band`: `HIGH`, `MEDIUM`, or `LOW`;
- `rule_version`: exactly `topic-priority-v1`;
- deterministic reason codes.

Use this exact v1 rule:

1. Topic absent from the selected SyllabusVersion → `LOW`.
2. Topic present and found in at least two distinct PreviousPapers for the same Exam → `HIGH`.
3. Topic present with fewer than two matched papers → `MEDIUM`.

Reason codes must distinguish:

- `DIRECT_SYLLABUS_COVERAGE`;
- `NOT_IN_SELECTED_SYLLABUS_VERSION`;
- `REPEATED_IN_PREVIOUS_PAPERS`;
- `APPEARED_IN_PREVIOUS_PAPER`;
- `NO_RECORDED_PREVIOUS_OCCURRENCE`; and
- `NO_PREVIOUS_PAPER_DATA`.

Requirements:

- Count only PreviousPapers belonging to the selected SyllabusVersion's Exam.
- Count distinct matched papers separately from question occurrences.
- Return the established 404 for a missing SyllabusVersion or Topic.
- Keep route → schema → service → repository layering and avoid N+1 queries.
- The endpoint must perform no writes.
- Add focused PostgreSQL/API tests for every rule branch, no-paper versus no-match reasons, distinct-paper counting, multiple questions in one paper, other-Exam exclusion, sorted unique years, missing resources, exact response, and no mutation.
- No migration unless genuinely required.
- Do not add percentages, probabilities, configurable weights, AI/LLMs, generated MCQs, ingestion, UI, auth, payments, or PDFs.

Update `docs/architecture.md`, `docs/workflow.md`, and append-only records in `docs/task_log.md` and `docs/next_task.md`. Run focused tests, full suite, changed-file Ruff, `uv run alembic check`, and `git diff --check`. Do not commit or push.

Implementation note (2026-09-05 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/syllabus-versions/{syllabus_version_id}/topics/{topic_id}/priority`. The read-only `topic-priority-v1` rule combines the selected version's direct Topic coverage with question occurrences from PreviousPapers belonging to that Exam, counting questions and distinct papers separately and returning sorted unique years plus deterministic reasons. It provides an explainable `HIGH`/`MEDIUM`/`LOW` aid, never a percentage or appearance probability. No migration or unrelated feature was added; exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-020 — Add canonical ContentVersion identity

Read `AGENTS.md` and all project documents first. Inspect the current repository before changing code.

## Goal

Add the smallest platform-owned version identity needed before canonical notes and question-bank items are stored.

A ContentVersion represents one reusable canonical-content version for one exact:

`SyllabusVersion + Topic`

It contains identity only. It is not content, approval, publication, AI generation, or learner personalization.

## Requirements

Add one migration and a minimal `ContentVersion` model/table with only:

- `id`;
- `syllabus_version_id`;
- `topic_id`;
- positive integer `version`;
- `created_at`.

Database rules:

- Enforce that `(syllabus_version_id, topic_id)` exists in `syllabus_version_topics` using a composite foreign key where supported by the current PostgreSQL/SQLAlchemy model.
- Use provenance-safe `ON DELETE RESTRICT`.
- Enforce `version > 0`.
- Enforce unique `(syllabus_version_id, topic_id, version)`.
- Historical versions must be retained; never overwrite or automatically calculate the next version.

Add exactly two endpoints:

- `POST /api/v1/content-versions`
- `GET /api/v1/content-versions/{content_version_id}`

The create request/response contains only the ContentVersion fields appropriate to input/output.

Behavior:

- missing SyllabusVersion → established 404;
- missing Topic → established 404;
- Topic not mapped to the selected SyllabusVersion → stable 409 with a clear detail;
- duplicate version → stable 409;
- non-positive version → 422;
- creation is atomic and PostgreSQL remains the concurrency-safe authority;
- retrieval returns the stored identity only; missing ContentVersion → established 404.

Use the existing route → schema → service → repository layering. Register the model for Alembic metadata.

## Important boundaries

- Do not modify NoteDraft or bind it to ContentVersion in T-020.
- Do not add version-history listing, release/superseding logic, approval fields, content bodies, Notes, QuestionBankItem, answer/options, user tables, personalization, AI/LLMs, prompts, ingestion, embeddings, payments, or PDFs.
- Do not modify `topic-priority-v1`.
- Do not add dependencies, environment variables, secrets, or Docker services; report that none were required.
- Do not edit prior migrations.

## Tests and documentation

Add focused PostgreSQL/API tests for:

- successful creation and retrieval;
- versions 1 and 2 for the same mapping;
- version 1 under different syllabus versions;
- missing SyllabusVersion, Topic, and ContentVersion;
- Topic outside the selected syllabus;
- non-positive version;
- duplicate conflict;
- database uniqueness, positive-version, composite-membership, and deletion-restriction constraints;
- failed creation leaving no partial row;
- migration upgrade, downgrade, and re-upgrade.

Preserve all T-001 through T-019 behavior.

Update `docs/architecture.md` and `docs/workflow.md`. Append, without rewriting history, the T-020 task/implementation records in `docs/task_log.md` and the implementation note in `docs/next_task.md`. Update `AGENTS.md` only if the canonical ownership rule is missing; do not duplicate it.

Run focused tests, full suite, changed-file Ruff, fresh migration upgrade/downgrade/re-upgrade, `uv run alembic check`, `git diff --check`, and `git status --short`. Do not commit or push.

Implementation note (2026-09-05 Asia/Kolkata, UTC+05:30): added only the identity-only `ContentVersion` model/migration plus `POST /api/v1/content-versions` and `GET /api/v1/content-versions/{content_version_id}`. PostgreSQL enforces positive explicit versions, unique version identity per exact SyllabusVersion/Topic mapping, composite syllabus membership, and restrictive provenance. Historical versions coexist without overwrite or automatic numbering. No dependency, configuration, NoteDraft, canonical asset, question-bank, release, AI, or learner-personalization change was added; exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-021 — Add a grounded QuestionBankItem candidate

Read `AGENTS.md` and all project documents first. Inspect repository conventions before changing code.

## Goal

Add the first reusable platform-owned question candidate under a ContentVersion, retaining the exact ordered approved Claims that ground it.

This task stores a manually supplied question stem and explanation. It does not yet create a complete MCQ, approved content, or learner-facing material.

## Data model

Add one migration and minimal models/tables:

- `QuestionBankItem`:
  - `id`;
  - `content_version_id`;
  - non-blank `question_text`;
  - non-blank `explanation`;
  - `difficulty`: `EASY`, `MEDIUM`, or `HARD`;
  - `created_at`.
- `question_bank_item_claims`:
  - `question_bank_item_id`;
  - `claim_id`;
  - non-negative `position`.

Database constraints must:

- restrict deletion of the referenced ContentVersion and Claims;
- reject blank question/explanation text;
- restrict difficulty to the three allowed values;
- allow each Claim only once per item;
- enforce unique, non-negative positions within an item.

## API

Add exactly:

- `POST /api/v1/question-bank-items`
- `GET /api/v1/question-bank-items/{question_bank_item_id}`

The create request contains `content_version_id`, question text, explanation, difficulty, and a non-empty ordered unique `claim_ids` list. Positions are derived from request order.

Creation rules:

- ContentVersion and every Claim must exist; missing resources use established 404 responses.
- Every Claim must be explicitly `APPROVED`.
- Every Claim must have the same `topic_id` as the ContentVersion.
- An unapproved or wrong-Topic Claim returns a stable 409.
- Invalid difficulty, blank text, empty/duplicate/non-positive Claim IDs return 422.
- Item and Claim links commit atomically with no partial rows.

Retrieval returns stored fields and Claim IDs in persisted position order. Missing item returns the established 404. Do not re-evaluate current Claim approval during retrieval; it is a stored provenance snapshot.

Use route → schema → service → repository layering and eager loading where appropriate.

## Boundaries

- `PreviousQuestion` remains sourced history and must not be merged with or converted into QuestionBankItem.
- QuestionBankItem is an internal unreviewed candidate. It is not canonical-approved or learner-ready.
- Do not add options, correct answers, review/approval fields, release state, AI generation, prompt/model metadata, NoteDraft binding, lists/search, users, personalization, mocks, payments, or PDFs.
- Do not add dependencies, secrets, environment variables, or Docker services.
- Do not edit prior migrations or change `topic-priority-v1`.

## Verification

Add focused PostgreSQL/API tests for successful atomic creation/retrieval, ordered Claim provenance, missing resources, empty/duplicate Claim IDs, invalid/blank fields, DRAFT/REJECTED Claims, wrong-Topic Claims, exclusion of partial rows, database constraints, deletion restrictions, and stored-snapshot retrieval after a Claim approval change.

Run the migration upgrade/downgrade/re-upgrade cycle, focused tests, full suite, changed-file Ruff, `uv run alembic check`, `git diff --check`, and `git status --short`.

Update `docs/architecture.md` and `docs/workflow.md`. Append T-021 records without rewriting history in `docs/task_log.md` and `docs/next_task.md`. Do not commit or push.

Implementation note (2026-09-05 Asia/Kolkata, UTC+05:30): added only the manually supplied internal `QuestionBankItem`, its position-ordered approved-Claim provenance, migration `e9a4c2f7b163`, and create/retrieve endpoints. PostgreSQL constrains non-whitespace text, difficulty, one Claim and one position per item, non-negative positions, and restricted deletion of referenced ContentVersions and Claims. Creation is atomic; retrieval returns the stored snapshot without re-evaluating Claim approval. No complete MCQ, review, release, AI, NoteDraft binding, dependency, configuration, or learner-facing feature was added. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## T-021 review outcome

- **APPROVED** after independent review of implementation commit `3b1c425158ca0932b6c8ea9fb80dbf9efd9b8278` (`feat: add grounded question bank candidates`).
- The implementation preserves the ContentVersion boundary, ordered approved same-Topic Claim provenance, PostgreSQL integrity constraints, transaction atomicity, and stored-snapshot retrieval. It does not add options, correct answers, review/release, AI, learner, mock, or historical-question behavior.
- Review evidence: the committed workflow records `17 passed` focused tests, `119 passed` full-suite tests, migration upgrade/downgrade/re-upgrade, `uv run alembic check`, changed-file Ruff, and `git diff --check`; GitHub exposes no separate CI status checks for the commit.

---
# T-022 — Add complete MCQ options and one correct answer to an internal QuestionBankItem candidate

Read `AGENTS.md` and all project documents first. Inspect the current repository, especially T-020 and T-021 implementation conventions, before changing code.

Do **not** commit, push, create a PR, self-approve, or implement T-023.

## Current context

The repository already has:

- `ContentVersion`: reusable version identity for one exact `SyllabusVersion + Topic`.
- `QuestionBankItem`: manually supplied internal candidate with question text, explanation, difficulty, and ordered approved same-Topic Claim provenance.
- `QuestionBankItem` is not yet a complete MCQ, approved canonical content, released content, or learner-facing material.

T-022 must complete only the internal MCQ structure.

## Goal

Extend a `QuestionBankItem` with a non-empty, ordered set of answer options and exactly one correct option at creation time.

The correct answer is an internal candidate answer key. It is not human approval, release, publication, AI generation, or learner delivery.

## Data model and database

Add one new Alembic migration. Do not edit historical migrations.

Add the smallest model/table(s) necessary to persist options. Prefer a design equivalent to `QuestionBankOption`:

- `id`;
- `question_bank_item_id`;
- non-negative `position`;
- non-blank `option_text`.

Use the existing `QuestionBankItem` as the parent. The correct option may be represented by a stored option position or option identity, but the persisted schema and service must guarantee that the declared correct answer belongs to the same `QuestionBankItem`.

PostgreSQL must enforce where it can do so cleanly:

- option text cannot be blank/whitespace;
- option position is non-negative;
- one option position is unique within a `QuestionBankItem`;
- an option cannot be linked to another item's answer reference;
- deleting a `QuestionBankItem` may delete only its dependent option rows;
- direct deletion of an option that is the persisted correct answer must not leave an invalid answer reference;
- existing `ContentVersion` and Claim deletion restrictions remain intact.

At the API/service level, require at least two options and exactly one correct answer for newly created complete MCQ candidates. Do not treat a correct-answer flag on multiple child rows as sufficient unless the database design also prevents invalid cross-item references.

Existing T-021 rows must remain migratable and retrievable. Do not make an unsafe non-null migration that breaks existing `QuestionBankItem` records.

## API

Modify only the existing internal QuestionBankItem create/read contract as needed:

- `POST /api/v1/question-bank-items`
- `GET /api/v1/question-bank-items/{question_bank_item_id}`

The create request must include:

- existing T-021 fields;
- `options`: ordered, non-empty option texts;
- a correct-option reference derived from request order, such as `correct_option_position`.

The response must return:

- existing T-021 fields;
- persisted options in stored position order;
- the stored correct-option reference.

Choose stable field names and document them.

Behavior:

- fewer than two options, blank options, duplicate/invalid positions, or invalid correct-option reference → HTTP 422;
- the correct option must refer to an option in the same request/item;
- missing `ContentVersion` or Claim → existing 404 behavior;
- unapproved or wrong-Topic Claim → existing stable 409 behavior;
- failed creation must be atomic: no `QuestionBankItem`, option, or Claim-link partial rows;
- retrieval returns the stored option/answer/provenance snapshot and must not re-evaluate current Claim approval;
- preserve backward compatibility for all unrelated routes and models.

Keep routes thin and preserve:

```text
Route
 ↓
Schema
 ↓
Service
 ↓
Repository
 ↓
PostgreSQL
```

Use eager loading/selectin loading as appropriate so retrieval does not cause obvious N+1 queries.

## Boundaries

Do not add:

- `QuestionBankItem` approval/rejection/review history;
- release/publication state;
- learner APIs, users, authentication, personalization, attempts, analytics, mocks;
- AI generation, prompts, providers, ingestion, RAG, embeddings;
- previous-paper conversion or merging with `QuestionBankItem`;
- multi-answer, assertion/reason, descriptive-question, or explanation-generation formats;
- lists/search;
- `NoteDraft` binding;
- dependencies, secrets, environment variables, Docker services, or infrastructure changes unless an actual implementation requirement proves one is needed.

`PreviousQuestion` remains a sourced historical occurrence. `QuestionBankItem` remains a reusable internal practice-question candidate.

## Required affected-component review

Inspect and update only where necessary:

- `app/models` and model registration;
- Alembic metadata/migration;
- Pydantic schemas;
- `KnowledgeRepository`;
- `KnowledgeService`;
- knowledge routes;
- focused API/database tests;
- migration tests;
- regression tests;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md`;
- append-only `docs/next_task.md`.

Inspect but leave unchanged unless genuinely needed:

- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

If no dependency, configuration, Docker, `AGENTS.md`, or README change is required, explicitly report that each was reviewed and left unchanged.

## Tests and validation

Add focused PostgreSQL/API tests for at least:

- successful atomic creation and retrieval with ordered options and one correct option;
- preservation of existing ordered Claim provenance;
- stored-snapshot retrieval after linked Claim approval later changes;
- fewer than two options;
- blank/whitespace options;
- invalid/missing/out-of-range correct-option reference;
- duplicate option positions if positions are externally persisted;
- database constraints for blank option text, non-negative/unique option position, and correct-answer-to-same-item integrity;
- deletion behavior for `QuestionBankItem`/options and restrictions that preserve a valid correct-answer reference;
- missing resources, wrong-Topic Claims, unapproved Claims, and no partial rows;
- migration upgrade, downgrade, and re-upgrade;
- regression coverage for T-021 retrieval and all previous tests.

Run and report exact results for:

- focused T-022 tests;
- full test suite;
- changed-file Ruff;
- fresh migration upgrade/downgrade/re-upgrade;
- `uv run alembic check`;
- `git diff --check`;
- `git status --short`.

## Documentation

Update `architecture.md` and `workflow.md` only for actual implemented behavior.

Append—never rewrite history:

- T-022 implementation note in `task_log.md`;
- T-022 implementation note in `next_task.md`.

Do not record T-022 as approved. Leave the working tree ready for independent review.

## Final report

Report:

1. files changed;
2. database design and constraints;
3. API contract;
4. atomicity/error behavior;
5. tests and exact results;
6. dependency/configuration/Docker/AGENTS/README review outcomes;
7. migration validation;
8. known boundaries retained;
9. git status;
10. explicit confirmation: no commit, push, PR, self-approval, or T-023 work.

Implementation note (2026-09-06 Asia/Kolkata, UTC+05:30): extended only the existing QuestionBankItem create/read contract with at least two ordered non-blank `options` and one `correct_option_position`. Migration `f2c8d4a6e915` adds ordered `QuestionBankOption` rows plus a nullable backward-compatible composite same-item correct-option reference. New item, Claim links, options, and answer commit atomically; retrieval returns the stored snapshot, while legacy T-021 rows remain readable with empty options and a null answer position. No review, release, AI, previous-paper conversion, NoteDraft binding, dependency, configuration, Docker, or learner-facing feature was added. Exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## T-022 review outcome

- **APPROVED** after independent review of implementation commit `4dc87a82a1d8695a6316debad03d7f3af43e28e2` (`feat: add complete question bank item options`).
- The implementation adds ordered non-blank `QuestionBankOption` records and a nullable, composite same-item correct-option reference. New API-created candidates require at least two options and one valid answer; migrated T-021 rows remain readable as legacy incomplete candidates.
- The review confirmed route → schema → service → repository → PostgreSQL layering, atomic creation, ordered stored-snapshot retrieval, existing Claim-provenance behavior, PostgreSQL constraints/deletion semantics, migration parity, and retained scope boundaries.
- Review evidence recorded by the implementation: `26 passed, 1 warning in 1.42s` focused; `128 passed, 1 warning in 4.88s` full suite; upgrade/downgrade/re-upgrade; `uv run alembic check`; changed-file Ruff; and `git diff --check`. GitHub exposes no separate CI status checks for this commit.

---
# T-023 — Add independent human review state to QuestionBankItem candidates

Read `AGENTS.md` and all project documents first. Inspect the current repository and the approved T-021/T-022 implementation before changing code.

Do **not** commit, push, create a PR, self-approve, or implement T-024.

## Goal

Add the smallest independent human-review state needed before a complete `QuestionBankItem` candidate can become eligible for a later approved-question read boundary.

This task records a review decision only. It does not release, publish, deliver, or personalize a question.

## Required model and database changes

Add one new Alembic migration. Do not edit prior migrations.

Extend `QuestionBankItem` with:

- `approval_status`: `DRAFT`, `APPROVED`, or `REJECTED`;
- `approval_decided_at`: nullable timezone-aware timestamp;
- `reviewer_note`: nullable text.

PostgreSQL must:

- restrict `approval_status` to exactly the three allowed values;
- make existing T-021/T-022 rows migrate to `DRAFT` with null decision fields;
- preserve the existing `ContentVersion`, Claim, option, and correct-answer constraints unchanged.

The migration must retain existing QuestionBankItem records and never infer approval.

## API

Add exactly one endpoint:

`POST /api/v1/question-bank-items/{question_bank_item_id}/approval`

Request:

- `approval_status`: `DRAFT`, `APPROVED`, or `REJECTED`;
- optional `reviewer_note`.

Response: the existing complete `QuestionBankItemResponse`, including stored Claim IDs, options, correct-option position, and approval fields.

Decision semantics:

- `APPROVED` or `REJECTED`: store the supplied optional reviewer note and set the decision time to current UTC.
- `DRAFT`: clear both `approval_decided_at` and `reviewer_note`.
- missing QuestionBankItem: established 404 behavior.
- approval does not modify QuestionBankItem text, explanation, difficulty, options, correct answer, Claim links, ContentVersion, or linked Claims.
- approval must not re-evaluate current Claim approval; QuestionBankItem provenance is a stored snapshot.

Eligibility rule:

- an incomplete legacy T-021 QuestionBankItem (fewer than two stored options or no valid stored correct option) may remain `DRAFT` or be `REJECTED`, but an attempt to mark it `APPROVED` must return stable HTTP 409 and leave all fields unchanged.
- a complete T-022 QuestionBankItem may be approved regardless of later changes to a linked Claim's current approval state.

Use route → Pydantic schema → service → repository → PostgreSQL. Keep routes thin. Commit/rollback semantics must remain atomic.

## Boundaries

Do not add:

- a list of approved QuestionBankItems;
- release/publication/superseding state;
- learner access, users, auth, attempts, mock assembly, analytics, or personalization;
- reviewer identity, user accounts, review history, reviewer assignment, or edit workflow;
- AI generation, providers, prompts, ingestion, RAG, embeddings;
- NoteDraft changes;
- PreviousQuestion conversion or probability semantics;
- dependencies, secrets, environment variables, Docker services, or infrastructure changes.

QuestionBankItem approval is distinct from Claim approval, NoteDraft approval, verification, release, and publication.

## Required review of affected components

Inspect and update only where necessary:

- models and model registration;
- Alembic migration;
- schemas;
- repository;
- service;
- knowledge routes;
- focused API/database/migration tests and regression tests;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md` and `docs/next_task.md`.

Inspect but leave unchanged unless genuinely needed:

- `pyproject.toml`, `uv.lock`;
- `.env.example`, `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

If unchanged, explicitly report each reviewed dependency/configuration/infrastructure/document decision.

## Required tests

Add focused tests for:

- a complete T-022 candidate starting as `DRAFT`;
- APPROVED and REJECTED decisions recording UTC time and optional note;
- reset to DRAFT clearing decision time and note;
- missing candidate 404;
- approval not mutating stored question, options, correct answer, Claim links, or ContentVersion;
- approval after a linked Claim later becomes DRAFT still preserving the QuestionBankItem stored snapshot;
- legacy incomplete candidate rejected for APPROVED with stable 409 and no mutation;
- complete candidate approval;
- database status constraint;
- migration upgrade, downgrade, and re-upgrade preserving existing records;
- all T-021/T-022 regression tests.

Run and report exact results for focused tests, the full suite, changed-file Ruff, fresh migration upgrade/downgrade/re-upgrade, `uv run alembic check`, `git diff --check`, and `git status --short`.

## Documentation and handoff

Update architecture/workflow only for implemented behavior. Append implementation notes without rewriting history in task_log/next_task. Do not state T-023 is approved.

Leave the implementation in the working tree for independent review. Do not commit or push.

## Final report

Report files changed, data/migration design, API/error semantics, atomicity, test results, dependency/configuration/Docker/AGENTS/README decisions, documentation updates, git status, and explicit confirmation that no commit, push, PR, self-approval, or T-024 work occurred.

Implementation note (2026-09-06 Asia/Kolkata, UTC+05:30): added only independent DRAFT/APPROVED/REJECTED human-review state and `POST /api/v1/question-bank-items/{question_bank_item_id}/approval`. APPROVED/REJECTED store current UTC decision time and the supplied note; DRAFT clears both. Approval requires a complete stored option/answer snapshot but does not re-evaluate current Claim approval or mutate content/provenance. Existing candidates migrate to DRAFT without inferred approval. No approved-item list, release, publication, learner, AI, dependency, configuration, Docker, or T-024 work was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## T-023 review outcome

T-023 implementation commit `1e84907906579c08d7218771669730b9855778d6` is independently approved. Documentation synchronization commit `145502a56a0d53a11fe9b6e80ce611847109a993` records the review. GitHub exposed no status contexts or check runs; the focused/full test, Ruff, migration, Alembic, and diff results remain accurately identified as developer-recorded evidence.


---

# T-024 — Add approved QuestionBankItem read boundary

Read `AGENTS.md` and all project documents first. Inspect the current repository and the approved T-021 through T-023 implementation conventions before changing code.

Do **not** commit, push, create a PR, self-approve, or implement T-025. Leave the complete T-024 working tree for independent review.

## Goal

Add the smallest read-only internal boundary that returns stored `QuestionBankItem` candidates whose own independent human-review state is exactly `APPROVED`.

This endpoint makes reviewed canonical question candidates available to later platform stages. It does not release, publish, deliver, generate, or personalize questions. Preserve the project rule: **Generate Once, Personalize Later**. T-024 performs neither generation nor personalization.

## Data model and persistence

No schema change is expected. Do not add a migration unless inspection proves a genuine persistence change is necessary; if that occurs, stop and report the architectural need before proceeding.

Preserve all existing QuestionBankItem identity, ContentVersion ownership, ordered Claim provenance, ordered options, same-item correct answer, approval metadata, and PostgreSQL constraints unchanged.

## API contract

Add exactly one endpoint:

`GET /api/v1/question-bank-items/approved`

Response:

- a list of the existing `QuestionBankItemResponse` objects;
- include only rows where the QuestionBankItem's own `approval_status` is exactly `APPROVED`;
- order results by ascending QuestionBankItem ID;
- retain each stored question, explanation, difficulty, ContentVersion ID, created time, ordered Claim IDs, ordered options, correct-option position, and approval metadata;
- return `[]` with HTTP 200 when no approved candidates exist.

Register the static `/question-bank-items/approved` route before `/question-bank-items/{question_bank_item_id}` so `approved` is never interpreted as an ID.

## Invariants and behavior

- Use route → Pydantic schema → service → repository → PostgreSQL layering and keep the route thin.
- Filter on the QuestionBankItem's own explicit approval state. Claim approval, NoteDraft approval, and Verification state must not substitute for it.
- Eagerly load ordered Claim links and ordered options for all returned items; avoid N+1 queries.
- Return the stored snapshot. Do not regenerate content, recalculate the correct answer, re-evaluate current Claim approval, or mutate database state.
- DRAFT and REJECTED candidates must be excluded.
- Preserve stable ascending item order and each item's persisted Claim/option position order.
- Preserve backward compatibility for all existing create, retrieve, and approval routes.
- No new error response is expected for the collection endpoint; an empty eligible set is a successful empty list.

## Affected components

Inspect and update only where necessary:

- `app/api/v1/routes/knowledge.py`;
- `app/repositories/knowledge.py`;
- `app/services/knowledge.py`;
- focused QuestionBankItem API/PostgreSQL tests;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md`;
- append-only `docs/next_task.md`.

Inspect model and schema definitions to confirm reuse, but do not change them unless a demonstrated requirement makes it necessary. Inspect `pyproject.toml`, `uv.lock`, `.env.example`, `app/core/config.py`, `docker-compose.yml`, `AGENTS.md`, and `README.md`; leave each unchanged unless a genuine T-024 requirement is found, and report the review outcome for each.

## Required tests

Add focused API/PostgreSQL coverage proving:

- an empty database or a database with no approved candidates returns `[]`;
- DRAFT and REJECTED QuestionBankItems are excluded;
- multiple APPROVED QuestionBankItems are included in stable ascending ID order;
- each returned item retains its stored ordered Claim IDs, ordered options, correct-option position, and approval metadata;
- changing a linked Claim's approval state after candidate creation/review does not change the returned stored candidate snapshot or eligibility;
- unrelated Topic, ContentVersion, Claim, NoteDraft, and Verification state cannot make an unapproved QuestionBankItem eligible;
- the endpoint performs no database mutation;
- existing T-021, T-022, and T-023 QuestionBankItem tests continue to pass.

Use the cleanest test level consistent with the existing PostgreSQL-backed setup. Do not weaken or delete existing tests.

## Exclusions

Do not add:

- QuestionBankItem release, publication, superseding, or version-history behavior;
- public or learner-facing endpoints;
- users, authentication, authorization, attempts, analytics, mock assembly, or learner personalization;
- AI/LLM providers, prompts, generation, ingestion, RAG, embeddings, or source scraping;
- list/search/filter/pagination endpoints other than the single exact approved collection required here;
- review history, reviewer identity, assignment, or edit/delete endpoints;
- NoteDraft binding or PreviousQuestion conversion;
- dependencies, secrets, environment variables, Docker services, deployment, payments, or PDFs.

QuestionBankItem approval remains separate from Claim approval, NoteDraft approval, Verification, release, and publication. `PreviousQuestion` remains sourced historical evidence and must not be merged with QuestionBankItem.

## Documentation and validation

Update `docs/architecture.md` and `docs/workflow.md` only for confirmed implemented behavior. Append—never rewrite or delete history—the T-024 task and implementation records in `docs/task_log.md` and an implementation note under this prompt in `docs/next_task.md`. Do not mark T-024 approved.

Run and report exact results for:

- focused T-024 QuestionBankItem tests;
- the full test suite;
- Ruff on every changed Python file;
- migration checks only if a genuine model/schema change was required;
- `uv run alembic check`;
- `git diff --check`;
- `git status --short`.

## Final report

Report:

1. files changed;
2. endpoint and exact response/filter/order behavior;
3. eager-loading and stored-snapshot behavior;
4. error and empty-result behavior;
5. focused and full test results;
6. Ruff, Alembic, migration, and diff-check results;
7. dependency/configuration/Docker/AGENTS/README review outcomes;
8. retained trust, provenance, approval, Generate Once/Personalize Later, and scope boundaries;
9. final git status;
10. explicit confirmation that no commit, push, PR, self-approval, T-025 work, release, publication, generation, or learner-personalization work occurred.

Leave T-024 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-06 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/question-bank-items/approved` through the existing route, service, repository, and `QuestionBankItemResponse` flow. It filters exactly on each candidate's own APPROVED state, returns stored snapshots in ascending ID order with ordered Claim and option provenance eagerly loaded, and returns `[]` when none qualify. It performs no writes, regeneration, Claim re-evaluation, release, publication, generation, or personalization. No migration or dependency/configuration/infrastructure change was required; exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## T-024 review outcome

- **APPROVED** after independent inspection of implementation commit `6dc8e9497fe55870173c584717e3ab78563baf3f` (`feat: add approved question bank item read boundary`) against its issued prompt and parent `e2c62be92006061b77ef2c260489ad5e0821f17b`.
- The implementation adds only the static, read-only approved QuestionBankItem collection; it filters on the item's own APPROVED state, preserves stable item/Claim/option order, eagerly loads both child collections, returns stored snapshots, returns an empty list when appropriate, and performs no writes.
- Developer-recorded evidence is `36 passed, 1 warning` focused and `138 passed, 1 warning` full suite, plus changed-file Ruff, fresh database upgrade, Alembic check, and diff check. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed.
- No model, schema, migration, dependency, configuration, release, publication, learner, generation, personalization, mock, or T-025 implementation was included.


---

# T-025 — Add controlled QuestionBankItem release lifecycle

Read `AGENTS.md` and all project documents first. Inspect the live repository and the approved T-020 through T-024 implementation conventions before changing code.

Do **not** commit, push, create a PR, self-approve, or implement T-026. Leave the complete T-025 working tree uncommitted and unpushed for independent review.

## Current context

The repository now has platform-owned `QuestionBankItem` candidates under an exact `ContentVersion`, with ordered approved-Claim provenance, complete MCQ options and one same-item answer, independent human review, and a read-only boundary for candidates whose own review state is `APPROVED`.

Approval remains an internal human-review result. It is not release, publication, public delivery, or learner access.

## Goal

Add the smallest controlled release lifecycle for a `QuestionBankItem` after its own review approval.

A release decision makes one stored, approved canonical question eligible for a later delivery boundary. T-025 must not add that delivery boundary. Preserve **Generate Once, Personalize Later**: release the stored canonical asset; never generate or copy a per-learner equivalent.

## Data model and migration

Add one new Alembic migration. Never edit historical migrations.

Extend `QuestionBankItem` with:

- `release_status`: `UNRELEASED`, `RELEASED`, or `WITHDRAWN`;
- `released_at`: nullable timezone-aware timestamp;
- `withdrawn_at`: nullable timezone-aware timestamp;
- `release_note`: nullable text.

Existing rows must migrate to `UNRELEASED` with all release metadata null. Migration must never infer release from `approval_status`.

PostgreSQL must constrain:

- `release_status` to exactly the three allowed values;
- `UNRELEASED` rows to have null `released_at` and `withdrawn_at`;
- `RELEASED` rows to have non-null `released_at`, null `withdrawn_at`, and `approval_status = 'APPROVED'`;
- `WITHDRAWN` rows to retain non-null `released_at` and have non-null `withdrawn_at`;
- existing ContentVersion, Claim, option, answer, and approval constraints unchanged.

Use database constraints for these persistence invariants. The downgrade must remove only T-025 release fields and constraints, retaining all T-021 through T-024 records and behavior.

## API

Add exactly one endpoint:

`POST /api/v1/question-bank-items/{question_bank_item_id}/release`

Request:

- `release_status`: exactly `RELEASED` or `WITHDRAWN`;
- optional `release_note`.

Do not accept `UNRELEASED` as a requested decision. It is the migration/default state only.

Response:

- reuse the existing complete `QuestionBankItemResponse`;
- add the four release fields to that response;
- preserve all stored question, ContentVersion, Claim provenance, option, answer, approval, and creation fields.

Register the route consistently with the existing QuestionBankItem routes so it cannot conflict with the static approved collection or dynamic item route.

## Transition and eligibility rules

- A new or migrated candidate begins `UNRELEASED` with null release metadata.
- `UNRELEASED → RELEASED` is allowed only when the candidate:
  - currently has its own `approval_status = APPROVED`;
  - is complete under the existing T-023 rule: at least two stored options and a valid same-item correct option.
- Releasing records current UTC in `released_at`, leaves `withdrawn_at` null, and stores the supplied optional note.
- `RELEASED → WITHDRAWN` records current UTC in `withdrawn_at`, preserves the original `released_at`, and stores the supplied optional note.
- `UNRELEASED → WITHDRAWN` is invalid.
- Releasing an already RELEASED item is invalid.
- Releasing or withdrawing an already WITHDRAWN item is invalid.
- A WITHDRAWN item cannot be re-released in place. A corrected future asset must use a new canonical item/version rather than overwriting release history.
- Missing item: established HTTP 404.
- Invalid request enum: HTTP 422.
- Invalid eligibility or transition: stable HTTP 409 with no mutation.
- While an item is RELEASED, the existing approval endpoint must reject changing its approval to DRAFT or REJECTED with stable HTTP 409 and no mutation. Withdrawal must occur first.
- WITHDRAWN items may subsequently have their review state changed through the existing approval endpoint.
- Release and withdrawal must not modify question text, explanation, difficulty, ContentVersion, Claim links, options, correct answer, linked Claims, or prior review timestamps/notes.
- Release eligibility must not re-evaluate current Claim approval, NoteDraft approval, or Verification state. The QuestionBankItem is a stored snapshot.

Keep routes thin and preserve:

`Route → Pydantic schema → Service → Repository → PostgreSQL`

All state changes must commit atomically and roll back fully on failure.

## Read-boundary behavior

Preserve `GET /api/v1/question-bank-items/approved` exactly as an approval boundary. Do not silently change it into a released-items endpoint. It must continue to return items based only on their own APPROVED review state, including UNRELEASED or WITHDRAWN items when they remain approved.

Do not add a released-items list in T-025. That is a separate future boundary.

## Affected components

Inspect and update only where necessary:

- `app/models/question_bank_item.py`;
- model registration and Alembic metadata;
- one new Alembic migration;
- `app/schemas/knowledge.py`;
- `app/repositories/knowledge.py`;
- `app/services/knowledge.py`;
- `app/api/v1/routes/knowledge.py`;
- focused QuestionBankItem API/PostgreSQL tests;
- migration and regression tests;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md`;
- append-only `docs/next_task.md`.

Inspect but leave unchanged unless a genuine T-025 requirement proves otherwise:

- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

Explicitly report each unchanged dependency, configuration, infrastructure, and governance file.

## Required tests

Add focused PostgreSQL/API coverage proving:

- new API-created candidates default to UNRELEASED with null release metadata;
- migrated T-021 through T-024 rows become UNRELEASED without inferred release;
- complete APPROVED candidate release succeeds and records a UTC release time and optional note;
- DRAFT and REJECTED candidates cannot be released and remain unchanged;
- incomplete legacy candidates cannot be released and remain unchanged;
- later Claim approval changes do not prevent release of an otherwise eligible stored APPROVED candidate;
- Claim, NoteDraft, and Verification state cannot substitute for the candidate's own approval;
- UNRELEASED cannot be withdrawn;
- RELEASED can be withdrawn, preserving `released_at` and recording `withdrawn_at`;
- duplicate release, duplicate withdrawal, release after withdrawal, and re-release after withdrawal return stable 409 without mutation;
- a RELEASED item cannot be moved to DRAFT or REJECTED until withdrawn;
- a WITHDRAWN item may later use the existing approval endpoint;
- release/withdrawal never changes stored content, ContentVersion, Claim order, option order, correct answer, linked Claims, or review metadata;
- missing item returns the established 404;
- invalid release status and attempts to request UNRELEASED return 422;
- PostgreSQL rejects invalid status/metadata combinations and RELEASED with non-APPROVED review state;
- migration upgrade, downgrade, and re-upgrade preserve existing candidate records;
- existing T-021 through T-024 create, retrieve, approval, and approved-list tests continue to pass.

Do not weaken or remove existing tests.

## Exclusions

Do not add:

- `GET /question-bank-items/released` or any released collection;
- public or learner-facing APIs;
- publication transport, PDF creation, exports, downloads, or deployment;
- users, authentication, reviewer/releaser identity, assignment, or decision history tables;
- editing or deleting released content;
- automatic release when approval becomes APPROVED;
- per-learner question copies, attempts, analytics, personalization, or mock assembly;
- AI/LLM providers, prompts, generation, ingestion, RAG, embeddings, or source scraping;
- NoteDraft release or ContentVersion release changes;
- PreviousQuestion conversion or prediction/probability semantics;
- dependencies, secrets, environment variables, Docker services, payments, or unrelated infrastructure.

Release is distinct from Claim approval, QuestionBankItem approval, NoteDraft approval, Verification, publication transport, and learner delivery. `PreviousQuestion` remains sourced historical evidence.

## Documentation and validation

Update `docs/architecture.md` and `docs/workflow.md` only for behavior actually implemented.

Append—never rewrite or delete history:

- the T-025 implementation record in `docs/task_log.md`;
- an implementation note under this T-025 prompt in `docs/next_task.md`.

Do not mark T-025 approved.

Run and report exact results for:

- focused T-025 QuestionBankItem tests;
- the full test suite;
- Ruff on every changed Python file;
- a fresh migration upgrade;
- downgrade to the T-024 Alembic head `a6d1e8c3f247`;
- re-upgrade to the new T-025 migration;
- seeded pre-T-025 candidate preservation across the migration cycle;
- `uv run alembic check`;
- `git diff --check`;
- `git status --short`.

## Final report

Report:

1. files changed;
2. release data model and PostgreSQL constraints;
3. migration and backward-compatibility behavior;
4. endpoint contract and stable 404/409/422 behavior;
5. release/withdrawal transition rules;
6. approval-lock and stored-snapshot behavior;
7. atomicity and rollback behavior;
8. focused and full test results;
9. Ruff, migration-cycle, Alembic, and diff-check results;
10. dependency/configuration/Docker/AGENTS/README review outcomes;
11. retained trust, provenance, versioning, Generate Once/Personalize Later, and scope boundaries;
12. final git status;
13. explicit confirmation that no commit, push, PR, self-approval, T-026, released-items list, public delivery, AI generation, or learner-personalization work occurred.

Leave T-025 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-06 Asia/Kolkata, UTC+05:30): added only the controlled QuestionBankItem release lifecycle, migration `b3e7f1a9c462`, and `POST /api/v1/question-bank-items/{question_bank_item_id}/release`. Existing and new candidates default to UNRELEASED without inferred release. Only a complete, currently approved stored candidate can be released; release records UTC time, withdrawal preserves that time and records its own, and withdrawn candidates cannot be re-released in place. PostgreSQL enforces status/metadata/approval consistency, while row locking and rollback-safe commits protect decisions. The approved-items endpoint remains approval-only. No released-items collection, public delivery, generation, personalization, or T-026 work was added; exact results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## T-025 review outcome

- **APPROVED** after independent inspection of implementation commit \`84e0b20fd81d9bf7b241a93686811db0ccd3e8dc\` (\`feat: add controlled question bank item release lifecycle\`) against its issued prompt and parent \`91a9ecaa861a0ceba8d557bb1995f6d636bfcd8f\`.
- The implementation adds only the constrained UNRELEASED/RELEASED/WITHDRAWN lifecycle and one release-decision endpoint. It safely defaults existing candidates without inferred release, preserves stored snapshots and review provenance, serializes approval/release decisions, and rejects invalid eligibility or transitions without mutation.
- Developer-recorded evidence is \`52 passed, 1 warning\` focused and \`154 passed, 1 warning\` full suite, plus changed-file Ruff, fresh migration upgrade, downgrade/re-upgrade, seeded-row preservation, Alembic check, and diff check. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed.
- No released-items collection, public or learner delivery, publication transport, generation, personalization, mock assembly, dependency, configuration, Docker, or T-026 implementation was included.


---

# T-026 — Add released QuestionBankItem read boundary

Read \`AGENTS.md\` and all project documents first. Inspect the live repository and the approved T-021 through T-025 implementation conventions before changing code.

Do **not** commit, push, create a PR, self-approve, or implement T-027. Leave the complete T-026 working tree uncommitted and unpushed for independent review.

## Current context

The repository has platform-owned QuestionBankItem candidates under an exact ContentVersion, ordered approved-Claim provenance, complete MCQ options with one same-item correct answer, independent human review, and a controlled release lifecycle.

T-025 is approved at implementation commit:

\`84e0b20fd81d9bf7b241a93686811db0ccd3e8dc\`

A QuestionBankItem can be UNRELEASED, RELEASED, or WITHDRAWN. Only a complete candidate with its own APPROVED review state can become RELEASED. Release is still separate from publication transport, public access, learner delivery, personalization, and mock assembly.

The existing \`GET /api/v1/question-bank-items/approved\` endpoint remains an approval-only boundary. It is not a release boundary and must remain unchanged in meaning.

## Goal

Add the smallest read-only internal boundary that returns stored QuestionBankItem snapshots whose current release state is exactly RELEASED.

This endpoint exposes released canonical assets to a later delivery or assembly stage. T-026 must not implement that later stage. Preserve **Generate Once, Personalize Later**: return the stored platform-owned canonical asset without regeneration or per-learner copying.

## Data model and migration

No model or database schema change is expected.

Do not add or edit a migration. Preserve migration head \`b3e7f1a9c462\` and all existing QuestionBankItem review/release fields and PostgreSQL constraints.

If inspection proves that a model, schema-persistence, or migration change is genuinely required, stop and report the architectural need before implementing it.

Preserve unchanged:

- ContentVersion ownership;
- ordered Claim provenance;
- ordered options;
- same-item correct answer;
- DRAFT/APPROVED/REJECTED review state and metadata;
- UNRELEASED/RELEASED/WITHDRAWN lifecycle and metadata;
- release/withdrawal transition history represented by stored state and timestamps;
- all PostgreSQL constraints from T-021 through T-025.

## API contract

Add exactly one endpoint:

\`GET /api/v1/question-bank-items/released\`

Response:

- HTTP 200;
- a list of the existing complete \`QuestionBankItemResponse\` objects;
- include only rows whose current \`release_status\` is exactly \`RELEASED\`;
- order results by ascending QuestionBankItem ID;
- return \`[]\` when no currently released candidates exist.

Each response item must retain:

- QuestionBankItem ID;
- ContentVersion ID;
- question text;
- explanation;
- difficulty;
- creation timestamp;
- ordered Claim IDs;
- ordered option text;
- correct-option position;
- review status, decision timestamp, and reviewer note;
- release status, released timestamp, withdrawn timestamp, and release note.

Register the static \`/question-bank-items/released\` route before \`/question-bank-items/{question_bank_item_id}\` so \`released\` cannot be interpreted as an item ID.

Do not add query parameters, search, filtering, pagination, or another endpoint.

## Eligibility and read behavior

- Eligibility depends only on the QuestionBankItem's current persisted \`release_status = RELEASED\`.
- UNRELEASED candidates must be excluded, including candidates whose review state is APPROVED.
- WITHDRAWN candidates must be excluded, even if their review state remains APPROVED.
- PostgreSQL already guarantees that a RELEASED row has its own APPROVED review state. Do not create a second release decision or recalculate eligibility in the route.
- Do not substitute Claim approval, NoteDraft approval, Verification state, or the approved-items collection for release state.
- Later Claim approval changes must not change released-item eligibility or the stored QuestionBankItem snapshot.
- Return stored question content and provenance. Do not regenerate content, recalculate the correct answer, rebuild Claim provenance, or mutate any database state.
- Eagerly load ordered Claim links and ordered options for every returned item. Avoid N+1 queries.
- Preserve stable ascending QuestionBankItem order and each item's persisted Claim and option position order.
- No eligible candidates is a successful HTTP 200 with an empty list.
- No new 404, 409, or other collection-specific error response is expected.

## Boundary compatibility

Preserve all existing QuestionBankItem behavior:

- creation;
- individual retrieval;
- approval decisions;
- approved-items collection;
- release and withdrawal decisions;
- released-item approval lock;
- stored-snapshot behavior;
- migration and PostgreSQL invariants.

\`GET /api/v1/question-bank-items/approved\` must continue to return items based only on their own APPROVED review state, including APPROVED UNRELEASED and APPROVED WITHDRAWN items.

The new released endpoint must exclude both UNRELEASED and WITHDRAWN items. Approval and release remain distinct boundaries.

## Layering and transaction behavior

Preserve:

\`Route → Pydantic schema → Service → Repository → PostgreSQL\`

Requirements:

- keep the route thin;
- reuse \`QuestionBankItemResponse\`;
- perform filtering, ordering, and eager-loading in the repository;
- serialize stored snapshots through the service;
- perform no database write, flush, commit, release transition, approval transition, or row lock for this read-only endpoint;
- do not re-evaluate current Claim, NoteDraft, or Verification state.

## Affected components

Inspect and update only where necessary:

- \`app/api/v1/routes/knowledge.py\`;
- \`app/repositories/knowledge.py\`;
- \`app/services/knowledge.py\`;
- focused QuestionBankItem API/PostgreSQL tests;
- \`docs/architecture.md\`;
- \`docs/workflow.md\`;
- append-only \`docs/task_log.md\`;
- append-only \`docs/next_task.md\`.

Inspect and reuse, but do not change unless a demonstrated T-026 requirement makes it necessary:

- QuestionBankItem models and relationships;
- \`app/schemas/knowledge.py\`;
- migration history and Alembic metadata;
- \`pyproject.toml\`;
- \`uv.lock\`;
- \`.env.example\`;
- \`app/core/config.py\`;
- \`docker-compose.yml\`;
- \`AGENTS.md\`;
- \`README.md\`.

Report the inspection outcome for every dependency, configuration, Docker, governance, model, schema, and migration component listed above.

## Required tests

Add focused PostgreSQL/API coverage proving:

- an empty database returns HTTP 200 with \`[]\`;
- a database with no RELEASED candidates returns \`[]\`;
- UNRELEASED candidates are excluded, including APPROVED UNRELEASED candidates;
- WITHDRAWN candidates are excluded, including APPROVED WITHDRAWN candidates;
- multiple RELEASED candidates are returned in stable ascending QuestionBankItem ID order;
- each returned item preserves its stored ordered Claim IDs;
- each returned item preserves its stored ordered options and correct-option position;
- each returned item preserves review and release metadata;
- later Claim approval changes do not change released-item eligibility or stored snapshots;
- Claim, NoteDraft, and Verification state cannot make an UNRELEASED item eligible;
- the endpoint performs no database mutation;
- the approved-items endpoint remains approval-only and distinct from the released-items endpoint;
- existing T-021 through T-025 create, retrieve, approval, approved-list, release, withdrawal, migration, and PostgreSQL-constraint tests continue to pass.

Where consistent with the existing test infrastructure, use multiple returned items to exercise eager loading and ordering. Do not weaken, rewrite, or remove existing tests.

## Exclusions

Do not add:

- public or learner-facing APIs;
- authentication, authorization, users, or learner profiles;
- publication transport;
- PDF generation, exports, downloads, or deployment;
- mock assembly, practice sessions, attempts, scoring, analytics, or personalization;
- per-learner QuestionBankItem copies;
- AI/LLM providers, prompts, generation, ingestion, RAG, embeddings, or scraping;
- release transitions beyond T-025;
- automatic release;
- release history or reviewer/releaser identity tables;
- editing or deleting released content;
- query parameters, search, filtering, pagination, or additional collections;
- NoteDraft or ContentVersion release behavior;
- PreviousQuestion conversion;
- probability, prediction, or likelihood semantics;
- dependencies, secrets, environment variables, Docker services, payments, or unrelated infrastructure.

A PreviousQuestion remains a sourced historical occurrence and must never be treated as a generated or released QuestionBankItem.

Release remains distinct from Claim approval, QuestionBankItem review, NoteDraft approval, Verification, publication transport, and learner delivery.

## Documentation

Update \`docs/architecture.md\` and \`docs/workflow.md\` only for behavior actually implemented.

Append—never rewrite, reorder, or delete history:

- the T-026 implementation record in \`docs/task_log.md\`;
- an implementation note beneath this T-026 prompt in \`docs/next_task.md\`.

Do not mark T-026 approved.

Do not define or implement T-027.

## Validation

Run and report exact results for:

\`\`\`bash
uv run pytest tests/test_question_bank_items_api.py -q
uv run pytest -q
uv run ruff check app/api/v1/routes/knowledge.py app/repositories/knowledge.py app/services/knowledge.py tests/test_question_bank_items_api.py
uv run alembic heads
uv run alembic check
git diff --check
git status --short
\`\`\`

No migration cycle is expected because T-026 must not change the model or database schema. Confirm that Alembic head remains \`b3e7f1a9c462\`.

If any unexpected migration or schema drift appears, stop and report it.

## Final report

Report:

1. files changed;
2. endpoint and exact release-status eligibility behavior;
3. result and nested provenance ordering;
4. eager-loading and N+1 avoidance;
5. stored-snapshot and no-mutation behavior;
6. empty-result and error behavior;
7. compatibility with approval, approved-list, release, and withdrawal behavior;
8. focused and full test results;
9. Ruff, Alembic-head, Alembic-check, and diff-check results;
10. model, schema, migration, dependency, configuration, Docker, AGENTS, and README inspection outcomes;
11. retained trust, provenance, review, release, versioning, and Generate Once/Personalize Later boundaries;
12. final git status;
13. explicit confirmation that no commit, push, PR, self-approval, T-027, public/learner delivery, publication transport, mock assembly, AI generation, or personalization work occurred.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-027.

Leave T-026 uncommitted and unpushed in the working tree for independent review.


---

## T-026 canonical prompt formatting correction

The preceding T-026 prompt is retained for append-only history but contains escaped Markdown backticks introduced by documentation tooling. The following prompt is the canonical T-026 implementation prompt with formatting corrected and no scope change.


# T-026 — Add released QuestionBankItem read boundary

Read `AGENTS.md` and all project documents first. Inspect the live repository and the approved T-021 through T-025 implementation conventions before changing code.

Do **not** commit, push, create a PR, self-approve, or implement T-027. Leave the complete T-026 working tree uncommitted and unpushed for independent review.

## Current context

The repository has platform-owned QuestionBankItem candidates under an exact ContentVersion, ordered approved-Claim provenance, complete MCQ options with one same-item correct answer, independent human review, and a controlled release lifecycle.

T-025 is approved at implementation commit:

`84e0b20fd81d9bf7b241a93686811db0ccd3e8dc`

A QuestionBankItem can be UNRELEASED, RELEASED, or WITHDRAWN. Only a complete candidate with its own APPROVED review state can become RELEASED. Release is still separate from publication transport, public access, learner delivery, personalization, and mock assembly.

The existing `GET /api/v1/question-bank-items/approved` endpoint remains an approval-only boundary. It is not a release boundary and must remain unchanged in meaning.

## Goal

Add the smallest read-only internal boundary that returns stored QuestionBankItem snapshots whose current release state is exactly RELEASED.

This endpoint exposes released canonical assets to a later delivery or assembly stage. T-026 must not implement that later stage. Preserve **Generate Once, Personalize Later**: return the stored platform-owned canonical asset without regeneration or per-learner copying.

## Data model and migration

No model or database schema change is expected.

Do not add or edit a migration. Preserve migration head `b3e7f1a9c462` and all existing QuestionBankItem review/release fields and PostgreSQL constraints.

If inspection proves that a model, schema-persistence, or migration change is genuinely required, stop and report the architectural need before implementing it.

Preserve unchanged:

- ContentVersion ownership;
- ordered Claim provenance;
- ordered options;
- same-item correct answer;
- DRAFT/APPROVED/REJECTED review state and metadata;
- UNRELEASED/RELEASED/WITHDRAWN lifecycle and metadata;
- release/withdrawal transition history represented by stored state and timestamps;
- all PostgreSQL constraints from T-021 through T-025.

## API contract

Add exactly one endpoint:

`GET /api/v1/question-bank-items/released`

Response:

- HTTP 200;
- a list of the existing complete `QuestionBankItemResponse` objects;
- include only rows whose current `release_status` is exactly `RELEASED`;
- order results by ascending QuestionBankItem ID;
- return `[]` when no currently released candidates exist.

Each response item must retain:

- QuestionBankItem ID;
- ContentVersion ID;
- question text;
- explanation;
- difficulty;
- creation timestamp;
- ordered Claim IDs;
- ordered option text;
- correct-option position;
- review status, decision timestamp, and reviewer note;
- release status, released timestamp, withdrawn timestamp, and release note.

Register the static `/question-bank-items/released` route before `/question-bank-items/{question_bank_item_id}` so `released` cannot be interpreted as an item ID.

Do not add query parameters, search, filtering, pagination, or another endpoint.

## Eligibility and read behavior

- Eligibility depends only on the QuestionBankItem's current persisted `release_status = RELEASED`.
- UNRELEASED candidates must be excluded, including candidates whose review state is APPROVED.
- WITHDRAWN candidates must be excluded, even if their review state remains APPROVED.
- PostgreSQL already guarantees that a RELEASED row has its own APPROVED review state. Do not create a second release decision or recalculate eligibility in the route.
- Do not substitute Claim approval, NoteDraft approval, Verification state, or the approved-items collection for release state.
- Later Claim approval changes must not change released-item eligibility or the stored QuestionBankItem snapshot.
- Return stored question content and provenance. Do not regenerate content, recalculate the correct answer, rebuild Claim provenance, or mutate any database state.
- Eagerly load ordered Claim links and ordered options for every returned item. Avoid N+1 queries.
- Preserve stable ascending QuestionBankItem order and each item's persisted Claim and option position order.
- No eligible candidates is a successful HTTP 200 with an empty list.
- No new 404, 409, or other collection-specific error response is expected.

## Boundary compatibility

Preserve all existing QuestionBankItem behavior:

- creation;
- individual retrieval;
- approval decisions;
- approved-items collection;
- release and withdrawal decisions;
- released-item approval lock;
- stored-snapshot behavior;
- migration and PostgreSQL invariants.

`GET /api/v1/question-bank-items/approved` must continue to return items based only on their own APPROVED review state, including APPROVED UNRELEASED and APPROVED WITHDRAWN items.

The new released endpoint must exclude both UNRELEASED and WITHDRAWN items. Approval and release remain distinct boundaries.

## Layering and transaction behavior

Preserve:

`Route → Pydantic schema → Service → Repository → PostgreSQL`

Requirements:

- keep the route thin;
- reuse `QuestionBankItemResponse`;
- perform filtering, ordering, and eager-loading in the repository;
- serialize stored snapshots through the service;
- perform no database write, flush, commit, release transition, approval transition, or row lock for this read-only endpoint;
- do not re-evaluate current Claim, NoteDraft, or Verification state.

## Affected components

Inspect and update only where necessary:

- `app/api/v1/routes/knowledge.py`;
- `app/repositories/knowledge.py`;
- `app/services/knowledge.py`;
- focused QuestionBankItem API/PostgreSQL tests;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md`;
- append-only `docs/next_task.md`.

Inspect and reuse, but do not change unless a demonstrated T-026 requirement makes it necessary:

- QuestionBankItem models and relationships;
- `app/schemas/knowledge.py`;
- migration history and Alembic metadata;
- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

Report the inspection outcome for every dependency, configuration, Docker, governance, model, schema, and migration component listed above.

## Required tests

Add focused PostgreSQL/API coverage proving:

- an empty database returns HTTP 200 with `[]`;
- a database with no RELEASED candidates returns `[]`;
- UNRELEASED candidates are excluded, including APPROVED UNRELEASED candidates;
- WITHDRAWN candidates are excluded, including APPROVED WITHDRAWN candidates;
- multiple RELEASED candidates are returned in stable ascending QuestionBankItem ID order;
- each returned item preserves its stored ordered Claim IDs;
- each returned item preserves its stored ordered options and correct-option position;
- each returned item preserves review and release metadata;
- later Claim approval changes do not change released-item eligibility or stored snapshots;
- Claim, NoteDraft, and Verification state cannot make an UNRELEASED item eligible;
- the endpoint performs no database mutation;
- the approved-items endpoint remains approval-only and distinct from the released-items endpoint;
- existing T-021 through T-025 create, retrieve, approval, approved-list, release, withdrawal, migration, and PostgreSQL-constraint tests continue to pass.

Where consistent with the existing test infrastructure, use multiple returned items to exercise eager loading and ordering. Do not weaken, rewrite, or remove existing tests.

## Exclusions

Do not add:

- public or learner-facing APIs;
- authentication, authorization, users, or learner profiles;
- publication transport;
- PDF generation, exports, downloads, or deployment;
- mock assembly, practice sessions, attempts, scoring, analytics, or personalization;
- per-learner QuestionBankItem copies;
- AI/LLM providers, prompts, generation, ingestion, RAG, embeddings, or scraping;
- release transitions beyond T-025;
- automatic release;
- release history or reviewer/releaser identity tables;
- editing or deleting released content;
- query parameters, search, filtering, pagination, or additional collections;
- NoteDraft or ContentVersion release behavior;
- PreviousQuestion conversion;
- probability, prediction, or likelihood semantics;
- dependencies, secrets, environment variables, Docker services, payments, or unrelated infrastructure.

A PreviousQuestion remains a sourced historical occurrence and must never be treated as a generated or released QuestionBankItem.

Release remains distinct from Claim approval, QuestionBankItem review, NoteDraft approval, Verification, publication transport, and learner delivery.

## Documentation

Update `docs/architecture.md` and `docs/workflow.md` only for behavior actually implemented.

Append—never rewrite, reorder, or delete history:

- the T-026 implementation record in `docs/task_log.md`;
- an implementation note beneath this T-026 prompt in `docs/next_task.md`.

Do not mark T-026 approved.

Do not define or implement T-027.

## Validation

Run and report exact results for:

```bash
uv run pytest tests/test_question_bank_items_api.py -q
uv run pytest -q
uv run ruff check app/api/v1/routes/knowledge.py app/repositories/knowledge.py app/services/knowledge.py tests/test_question_bank_items_api.py
uv run alembic heads
uv run alembic check
git diff --check
git status --short
```

No migration cycle is expected because T-026 must not change the model or database schema. Confirm that Alembic head remains `b3e7f1a9c462`.

If any unexpected migration or schema drift appears, stop and report it.

## Final report

Report:

1. files changed;
2. endpoint and exact release-status eligibility behavior;
3. result and nested provenance ordering;
4. eager-loading and N+1 avoidance;
5. stored-snapshot and no-mutation behavior;
6. empty-result and error behavior;
7. compatibility with approval, approved-list, release, and withdrawal behavior;
8. focused and full test results;
9. Ruff, Alembic-head, Alembic-check, and diff-check results;
10. model, schema, migration, dependency, configuration, Docker, AGENTS, and README inspection outcomes;
11. retained trust, provenance, review, release, versioning, and Generate Once/Personalize Later boundaries;
12. final git status;
13. explicit confirmation that no commit, push, PR, self-approval, T-027, public/learner delivery, publication transport, mock assembly, AI generation, or personalization work occurred.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-027.

Leave T-026 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-07 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/question-bank-items/released` through the existing route, service, repository, and `QuestionBankItemResponse` flow. It filters exactly on current RELEASED state, returns stored snapshots in ascending item ID order with ordered Claim and option provenance eagerly loaded, and returns `[]` when none qualify. UNRELEASED and WITHDRAWN candidates are excluded, while the existing approved-items endpoint remains approval-only. No model, schema, migration, write, regeneration, public/learner delivery, publication transport, mock assembly, AI, personalization, or T-027 work was added; exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## T-026 review outcome

- **APPROVED** after independent inspection of implementation commit `d5c3b484b8268ae745da491617c56c02a1be3853` (`feat: add released question bank item read boundary`) against its canonical prompt and parent `3e630d9fd952dcb24a320295fbc281b6396b0e45`.
- The implementation adds only `GET /api/v1/question-bank-items/released`; it filters exact current RELEASED state, preserves stable item and nested provenance order, returns stored snapshots, keeps the approved-items boundary distinct, and performs no writes or re-evaluation.
- Developer-recorded evidence is `54 passed, 1 warning` combined focused tests, `52 passed, 1 warning` existing QuestionBankItem tests, and `156 passed, 1 warning` full suite, plus changed-file Ruff, Alembic head/check, and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed.
- No model, schema, migration, dependency, configuration, delivery, publication transport, learner, personalization, mock, AI, or T-027 implementation was included.


---

# T-027 — Bind new NoteDrafts to ContentVersion

Read `AGENTS.md` and all project documents first. Inspect the live repository and the approved T-013 through T-026 implementation conventions before changing code.

Do **not** commit, push, create a PR, self-approve, or implement T-028. Leave the complete T-027 working tree uncommitted and unpushed for independent review.

## Current context

The platform has stored NoteDraft snapshots with ordered Claim provenance, individual retrieval, independent DRAFT/APPROVED/REJECTED review, and an approved-draft read boundary.

However, a NoteDraft currently belongs only to a Topic. It does not belong to the exact ContentVersion that identifies one Exam, sourced SyllabusVersion, Topic, and explicit version number.

QuestionBankItems already belong to ContentVersion. The canonical-content rule requires the same version ownership foundation for notes before any NoteDraft release, public delivery, learner access, generation, or personalization work.

T-026 is approved at implementation commit:

`d5c3b484b8268ae745da491617c56c02a1be3853`

## Goal

Require every newly persisted NoteDraft to belong to one exact ContentVersion whose Topic matches the NoteDraft Topic.

Preserve existing NoteDraft rows as readable legacy snapshots without guessing or inferring a ContentVersion.

This task establishes versioned canonical-note ownership only. It must not add NoteDraft release, publication, learner delivery, AI generation, or personalization.

## Data model and migration

Add exactly one new Alembic migration after current head:

`b3e7f1a9c462`

Never edit historical migrations.

Extend `NoteDraft` with:

- `content_version_id`: nullable integer at the database/model level for migration-safe legacy compatibility.

Migration behavior:

- existing NoteDraft rows must receive `content_version_id = null`;
- do not infer ContentVersion from Topic, current syllabus data, creation time, approval state, or any other field;
- existing Markdown, Topic ownership, Claim links and positions, approval status, approval timestamp, reviewer note, and creation timestamp must remain unchanged;
- new API-created NoteDrafts must always persist a non-null ContentVersion ID.

PostgreSQL must enforce that a non-null NoteDraft ContentVersion belongs to the same Topic as the NoteDraft.

Use a composite database invariant:

- add a named unique constraint on `content_versions(id, topic_id)` if PostgreSQL requires it as the referenced key;
- add a named composite foreign key from `note_drafts(content_version_id, topic_id)` to `content_versions(id, topic_id)`;
- use `ON DELETE RESTRICT`;
- allow the composite foreign key to remain satisfied for legacy rows whose `content_version_id` is null.

Do not make `note_drafts.content_version_id` globally non-null because historical rows have no source-backed basis for inferring ownership.

The downgrade must remove only the T-027 composite foreign key, ContentVersion composite uniqueness support added by T-027, and NoteDraft `content_version_id` column. It must preserve every legacy NoteDraft, Claim link, approval field, ContentVersion, QuestionBankItem, and T-013 through T-026 behavior.

Keep model metadata and migration constraint names aligned so `uv run alembic check` reports no drift.

## API contract

Change only the existing persisted NoteDraft creation endpoint:

`POST /api/v1/topics/{topic_id}/note-drafts`

Add a Pydantic request body:

```json
{
  "content_version_id": 1
}
```

Requirements:

- `content_version_id` is required;
- it must be a positive integer;
- missing or invalid input returns standard HTTP 422;
- no new NoteDraft-creation endpoint is added;
- the non-persistent NoteDraft preview endpoint remains unchanged.

Extend `NoteDraftResponse` with:

- `content_version_id: int | null`.

Response compatibility:

- newly created NoteDrafts return the supplied persisted ContentVersion ID;
- legacy NoteDrafts return `content_version_id: null`;
- individual retrieval, approval responses, and approved-list responses must all include this field;
- all existing Topic identity, Topic name, ordered Claim IDs, Markdown, creation time, approval status, approval timestamp, and reviewer note fields remain unchanged.

## Validation and error behavior

For persisted draft creation, validate in this order:

1. Resolve the path Topic.
   - Missing Topic returns the established HTTP 404.
2. Resolve the requested ContentVersion.
   - Missing ContentVersion returns the established HTTP 404 format for ContentVersion.
3. Confirm `ContentVersion.topic_id == topic_id`.
   - Mismatch returns stable HTTP 409.
   - Use a clear deterministic detail such as:
     `ContentVersion {content_version_id} does not belong to Topic {topic_id}`.
4. Load the Topic's currently approved Claims using the existing deterministic ordering.
   - No approved Claims returns the existing stable HTTP 409.

Every failure must occur without persisting a NoteDraft or NoteDraftClaim row.

Do not re-evaluate or alter SyllabusVersion mappings. ContentVersion creation already establishes the exact sourced SyllabusVersion/Topic membership.

## Creation and stored-snapshot behavior

For successful creation:

- persist `topic_id` and `content_version_id` together;
- retain the existing deterministic Markdown rendering;
- retain the exact ordered approved Claims used at creation;
- commit NoteDraft and NoteDraftClaim rows atomically;
- return the stored NoteDraft response with the ContentVersion ID;
- do not copy syllabus data into NoteDraft;
- do not mutate the ContentVersion, Topic, Claims, Evidence, Verification, or other drafts.

After creation:

- later Claim approval changes must not alter stored Markdown or ordered Claim provenance;
- later syllabus or priority reads must not alter the stored draft;
- retrieval and approval must use the stored `content_version_id` without recalculating or inferring it;
- legacy drafts with null ContentVersion must remain retrievable, reviewable, and eligible for the existing approved-draft collection based only on their own approval status.

Do not add an endpoint to retrofit, backfill, edit, or replace a legacy draft's ContentVersion.

## Boundary compatibility

Preserve unchanged:

- `POST /api/v1/topics/{topic_id}/note-draft-preview`;
- `GET /api/v1/note-drafts/{note_draft_id}`;
- `POST /api/v1/note-drafts/{note_draft_id}/approval`;
- `GET /api/v1/note-drafts/approved`;
- all ContentVersion creation/retrieval behavior;
- all QuestionBankItem creation, review, approval-list, release, and released-list behavior;
- all PreviousPaper, PreviousQuestion, and Topic-priority semantics.

The only intentional request-contract change is that persisted NoteDraft creation now requires the ContentVersion request body. Update existing tests and documentation accordingly.

NoteDraft approval remains separate from Claim approval, QuestionBankItem approval, Verification, release, publication, and learner access.

## Layering and atomicity

Preserve:

`Route → Pydantic schema → Service → Repository → PostgreSQL`

Requirements:

- keep the route thin;
- validate request shape in Pydantic;
- perform reference and same-Topic validation in the service;
- perform persistence through the repository;
- enforce same-Topic ownership again through PostgreSQL;
- keep NoteDraft and NoteDraftClaim creation atomic;
- roll back fully on every persistence failure;
- translate the new named constraint only if needed for stable API behavior;
- do not catch generic database errors as domain conflicts.

## Affected components

Inspect and update only where necessary:

- `app/models/note_draft.py`;
- `app/models/content_version.py` if composite referenced-key metadata is required;
- model registration and Alembic metadata;
- exactly one new Alembic migration;
- `app/schemas/knowledge.py`;
- `app/repositories/knowledge.py`;
- `app/services/knowledge.py`;
- `app/api/v1/routes/knowledge.py`;
- focused NoteDraft API/PostgreSQL tests;
- migration and regression tests;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md`;
- append-only `docs/next_task.md`.

Inspect but leave unchanged unless a genuine T-027 requirement proves otherwise:

- QuestionBankItem models, routes, schemas, services, repositories, and tests;
- PreviousPaper and PreviousQuestion components;
- Topic-priority components;
- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

Report the inspection result for every unchanged dependency, configuration, infrastructure, and governance file.

## Required tests

Add focused PostgreSQL/API coverage proving:

- the migration upgrades existing NoteDraft rows with `content_version_id = null`;
- migration downgrade and re-upgrade preserve legacy NoteDraft rows, ordered Claim links, Markdown, Topic, approval status, and approval metadata;
- no ContentVersion is inferred for legacy drafts;
- a new persisted NoteDraft request without `content_version_id` returns 422 with no persistence;
- zero, negative, non-integer, and otherwise invalid ContentVersion IDs return standard 422 where applicable;
- a missing path Topic returns the established 404 with no persistence;
- a missing ContentVersion returns the established ContentVersion 404 with no persistence;
- a ContentVersion belonging to another Topic returns the stable 409 with no persistence;
- PostgreSQL rejects a direct non-null mismatched NoteDraft ContentVersion/Topic pair;
- PostgreSQL rejects deletion of a ContentVersion referenced by a new NoteDraft;
- successful creation stores and returns the exact ContentVersion ID;
- successful creation retains deterministic Markdown and exact ordered approved-Claim provenance;
- creation remains atomic on failure;
- individual retrieval returns the stored ContentVersion ID;
- approval responses preserve the stored ContentVersion ID;
- the approved-drafts collection preserves the stored ContentVersion ID;
- legacy drafts with null ContentVersion remain retrievable and reviewable;
- legacy approved drafts remain included in the approved-drafts collection with `content_version_id: null`;
- later Claim approval changes do not alter ContentVersion ownership, Markdown, or ordered provenance;
- NoteDraft preview remains non-persistent and unchanged;
- existing T-013 through T-016 NoteDraft behavior continues after updating creation calls for the new request body;
- all T-017 through T-026 exam, version, question, review, release, and read-boundary tests continue to pass.

Do not weaken, delete, or silently skip existing tests.

## Exclusions

Do not add:

- NoteDraft release status, timestamps, notes, transitions, or released collection;
- public or learner-facing APIs;
- publication transport;
- PDF generation, exports, downloads, or deployment;
- users, authentication, authorization, reviewer identity, or history tables;
- edit, delete, retrofit, or backfill endpoints;
- automatic ContentVersion selection or inference;
- automatic next-version calculation;
- per-learner note copies;
- practice sessions, attempts, analytics, mock assembly, or personalization;
- AI/LLM providers, prompts, generation, ingestion, RAG, embeddings, or scraping;
- QuestionBankItem changes;
- PreviousQuestion conversion;
- prediction, probability, or likelihood semantics;
- dependencies, secrets, environment variables, Docker services, payments, or unrelated infrastructure.

A PreviousQuestion remains a sourced historical occurrence. It must never be converted into a generated question or treated as prediction evidence beyond the existing deterministic Topic-priority rules.

## Documentation

Update `docs/architecture.md` and `docs/workflow.md` only for behavior actually implemented.

Append—never rewrite, reorder, consolidate, or delete history:

- the T-027 implementation record in `docs/task_log.md`;
- an implementation note beneath this T-027 prompt in `docs/next_task.md`.

Do not mark T-027 approved.

Do not define or implement T-028.

## Validation

Run and report exact results for:

- focused NoteDraft tests;
- focused ContentVersion tests if affected;
- the full test suite;
- Ruff on every changed Python file;
- a fresh migration upgrade;
- downgrade to T-026 head `b3e7f1a9c462`;
- re-upgrade to the new T-027 migration;
- seeded legacy NoteDraft and NoteDraftClaim preservation across the migration cycle;
- database rejection of mismatched ContentVersion/Topic ownership;
- `uv run alembic heads`;
- `uv run alembic check`;
- `git diff --check`;
- `git status --short`.

Use a dedicated PostgreSQL test database. Never run destructive migration-cycle testing against a non-test database.

## Final report

Report:

1. files changed;
2. new NoteDraft ContentVersion field and database constraints;
3. migration revision, parent, upgrade, downgrade, and legacy-row behavior;
4. exact persisted-creation request and response contract;
5. stable 404/409/422 behavior;
6. same-Topic validation at service and PostgreSQL layers;
7. atomic creation and rollback behavior;
8. legacy retrieval, review, and approved-list compatibility;
9. stored Markdown, Claim provenance, and ContentVersion snapshot behavior;
10. focused, migration, and full-suite test results;
11. Ruff, Alembic-head, Alembic-check, and diff-check results;
12. dependency/configuration/Docker/AGENTS/README review outcomes;
13. retained trust, provenance, versioning, approval, release, and Generate Once/Personalize Later boundaries;
14. final git status;
15. explicit confirmation that no commit, push, PR, self-approval, T-028, NoteDraft release, public/learner delivery, publication transport, PDF, AI generation, mock assembly, or personalization work occurred.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-028.

Leave T-027 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-07 Asia/Kolkata, UTC+05:30): added nullable legacy-safe `NoteDraft.content_version_id` and migration `c7a4e9d2f816`, plus a required positive ContentVersion request for persisted draft creation. The service validates Topic, ContentVersion, same-Topic ownership, then approved Claims; PostgreSQL independently enforces the same-Topic composite reference and restricts deletion of referenced ContentVersions. Existing drafts retain null ownership without inference and remain retrievable, reviewable, and approval-list eligible. Preview, QuestionBankItem behavior, NoteDraft release, delivery, publication, AI, personalization, and T-028 were not added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.
---

## T-027 review outcome

- **APPROVED** after independent inspection of implementation commit `bcff4c54a04f6ec3cdcb094f71d64241e87a3622` against its canonical T-027 prompt and parent `a2e9f2ba19ba599255a18f3724e07482489b4b72`.
- The commit requires a positive ContentVersion for every newly persisted NoteDraft, preserves legacy null ownership without inference, validates Topic and same-Topic ContentVersion ownership before Claim eligibility, and enforces the ownership invariant in PostgreSQL.
- New and legacy ownership are preserved through individual retrieval, approval responses, and approved-list responses. The requested explicit non-null approval/list assertions and legacy-null assertions are present.
- Developer-recorded evidence is 22 focused NoteDraft tests, 12 focused ContentVersion tests, and 164 full-suite tests, each with one existing warning, plus successful Ruff, migration-cycle, PostgreSQL constraint, Alembic, and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed.
- No NoteDraft release, released collection, publication transport, learner delivery, PDF, AI, personalization, dependency, configuration, Docker, or T-028 implementation was included.

---

# T-028 — Add controlled NoteDraft release lifecycle

Read `AGENTS.md` and all project documents first. Inspect the live repository and the approved T-013 through T-027 implementation conventions before changing code.

Do **not** commit, push, create a PR, self-approve, or implement T-029. Leave the complete T-028 working tree uncommitted and unpushed for independent review.

## Current context

T-027 is approved at implementation commit:

`bcff4c54a04f6ec3cdcb094f71d64241e87a3622`

The platform now stores deterministic NoteDraft snapshots with:

- one Topic;
- one exact ContentVersion for every newly created draft;
- nullable ContentVersion ownership only for legacy drafts where ownership cannot be inferred;
- exact ordered approved-Claim provenance captured at creation;
- independent DRAFT/APPROVED/REJECTED human review;
- individual retrieval and an approval-only collection.

A reviewed NoteDraft still has no controlled release state. Approval must not automatically imply release, and a legacy draft without exact ContentVersion ownership must not become releasable.

## Goal

Add the smallest explicit release lifecycle for stored NoteDrafts:

`UNRELEASED → RELEASED → WITHDRAWN`

Release must remain a separate human-controlled decision from NoteDraft approval. A NoteDraft may be released only when:

- its own review state is exactly `APPROVED`; and
- it has a non-null stored `content_version_id`.

T-028 adds release and withdrawal state only. It must not add a released-drafts collection, publication transport, public or learner delivery, PDF generation, AI generation, or personalization.

## Data model and migration

Add exactly one new Alembic migration after current head:

`c7a4e9d2f816`

Never edit historical migrations.

Extend `NoteDraft` with:

- `release_status`: non-null string, defaulting to `UNRELEASED`;
- `released_at`: nullable timezone-aware timestamp;
- `withdrawn_at`: nullable timezone-aware timestamp;
- `release_note`: nullable text.

Migration behavior:

- every existing NoteDraft becomes `UNRELEASED`;
- `released_at`, `withdrawn_at`, and `release_note` remain null;
- do not infer release from NoteDraft approval, ContentVersion ownership, creation time, Claim state, or any other field;
- preserve every existing Topic, ContentVersion ownership value including legacy nulls, Markdown snapshot, ordered Claim link, review field, and creation timestamp;
- use a migration-safe temporary server default only if required, then keep model/migration metadata aligned and avoid unintended permanent database defaults.

Add named PostgreSQL constraints enforcing:

1. `release_status` is exactly one of:
   - `UNRELEASED`
   - `RELEASED`
   - `WITHDRAWN`

2. State/metadata consistency:
   - `UNRELEASED`: `released_at IS NULL`, `withdrawn_at IS NULL`, and `release_note IS NULL`;
   - `RELEASED`: `released_at IS NOT NULL`, `withdrawn_at IS NULL`, `approval_status = 'APPROVED'`, and `content_version_id IS NOT NULL`;
   - `WITHDRAWN`: `released_at IS NOT NULL`, `withdrawn_at IS NOT NULL`, and `content_version_id IS NOT NULL`.

The database must prevent a currently RELEASED NoteDraft from becoming DRAFT or REJECTED through direct persistence.

The downgrade must remove only the T-028 constraints and release columns. It must preserve all T-027 and earlier data and behavior, including NoteDraft ContentVersion ownership and legacy null ownership.

Keep model metadata and migration constraint names aligned so `uv run alembic check` reports no drift.

## API contract

Add exactly one endpoint:

`POST /api/v1/note-drafts/{note_draft_id}/release`

Add a Pydantic request schema accepting:

- `release_status`: exactly `RELEASED` or `WITHDRAWN`;
- `release_note`: optional string or null.

Do not accept `UNRELEASED` as an API decision. Invalid or missing release status must return standard HTTP 422.

Extend `NoteDraftResponse` with:

- `release_status`;
- `released_at`;
- `withdrawn_at`;
- `release_note`.

All existing NoteDraft response boundaries must return the stored release fields:

- persisted creation;
- individual retrieval;
- approval decisions;
- approved-draft collection;
- the new release decision endpoint.

New and migrated NoteDrafts return `UNRELEASED` with null release metadata until explicitly released.

## Allowed transitions

Allow only:

1. `UNRELEASED → RELEASED`
   - requires the NoteDraft's own `approval_status == 'APPROVED'`;
   - requires non-null stored `content_version_id`;
   - records the current UTC `released_at`;
   - keeps `withdrawn_at` null;
   - stores the optional release note.

2. `RELEASED → WITHDRAWN`
   - preserves the original `released_at`;
   - records the current UTC `withdrawn_at`;
   - replaces the release note with the optional withdrawal note supplied for this decision.

Reject every other transition with stable HTTP 409 and no mutation, including:

- `UNRELEASED → WITHDRAWN`;
- `RELEASED → RELEASED`;
- `WITHDRAWN → WITHDRAWN`;
- `WITHDRAWN → RELEASED`.

A WITHDRAWN NoteDraft cannot be re-released in place. A future corrected release must use a new canonical version/snapshot rather than silently reactivating historical content.

## Eligibility and independence

Release eligibility depends only on the stored NoteDraft's:

- own review state;
- own release state;
- stored ContentVersion ownership.

Do not re-evaluate current Claim approval, Verification, Evidence, Source, SyllabusVersion, Topic-priority, QuestionBankItem review, or QuestionBankItem release state.

Do not regenerate Markdown, recalculate Claim provenance, infer ContentVersion ownership, or mutate the Topic, ContentVersion, Claims, Claim links, Evidence, Verification, QuestionBankItems, or other NoteDrafts.

An approved legacy NoteDraft whose `content_version_id` is null:

- remains retrievable, reviewable, and eligible for the approval-only collection;
- cannot be released;
- must receive a stable HTTP 409 with no mutation when release is attempted;
- may remain DRAFT/APPROVED or be REJECTED according to the existing review behavior while it is UNRELEASED.

## Review-state interaction

While a NoteDraft is currently `RELEASED`:

- block attempts to change its approval state to `DRAFT` or `REJECTED`;
- return stable HTTP 409 without changing review or release metadata.

After it becomes `WITHDRAWN`:

- allow the existing approval transitions again;
- never clear or reactivate its historical release/withdrawal metadata;
- never permit in-place re-release.

Approval remains distinct from release. Approving an UNRELEASED NoteDraft must not release it.

## Error behavior

Use the established error shape and mappings:

- missing NoteDraft: HTTP 404 with the existing deterministic detail;
- release of a DRAFT or REJECTED NoteDraft: stable HTTP 409 with no mutation;
- release of an approved legacy NoteDraft with null ContentVersion: stable HTTP 409 with no mutation;
- invalid transition: stable HTTP 409 with no mutation;
- invalid request body or `UNRELEASED` decision: standard HTTP 422.

Use clear deterministic conflict details and assert them exactly in tests.

Do not expose raw database constraint names or convert generic persistence failures into misleading domain conflicts.

## Layering, locking, and atomicity

Preserve:

`Route → Pydantic schema → Service → Repository → PostgreSQL`

Requirements:

- keep the route thin;
- validate request shape in Pydantic;
- keep transition and eligibility rules in the service;
- perform persistence through the repository;
- enforce persistence invariants again in PostgreSQL;
- load the target NoteDraft with `SELECT ... FOR UPDATE` for both release decisions and approval decisions that can conflict with release state;
- perform each decision in one transaction;
- commit once on success;
- roll back fully on every failure;
- return the stored NoteDraft snapshot after the successful commit;
- avoid partial timestamp, note, review, or release mutations.

Reuse established error and transaction helpers where appropriate without weakening their behavior.

## Boundary compatibility

Preserve unchanged:

- `POST /api/v1/topics/{topic_id}/note-draft-preview`;
- `POST /api/v1/topics/{topic_id}/note-drafts`, including required ContentVersion ownership;
- `GET /api/v1/note-drafts/{note_draft_id}`;
- `POST /api/v1/note-drafts/{note_draft_id}/approval`, except for the required RELEASED-state guard and row lock;
- `GET /api/v1/note-drafts/approved`, which must remain approval-only and may include approved UNRELEASED, RELEASED, or WITHDRAWN drafts;
- all ContentVersion behavior;
- all QuestionBankItem creation, review, approval-list, release, and released-list behavior;
- all PreviousPaper, PreviousQuestion, and Topic-priority semantics.

Do not add `GET /api/v1/note-drafts/released` in T-028.

## Affected components

Inspect and update only where necessary:

- `app/models/note_draft.py`;
- model registration and Alembic metadata;
- exactly one new Alembic migration;
- `app/schemas/knowledge.py`;
- `app/repositories/knowledge.py`;
- `app/services/knowledge.py`;
- `app/api/v1/routes/knowledge.py`;
- focused NoteDraft API/PostgreSQL tests;
- migration and regression tests;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md`;
- append-only `docs/next_task.md`.

Inspect but leave unchanged unless a genuine T-028 requirement proves otherwise:

- ContentVersion models and APIs;
- QuestionBankItem models, schemas, repositories, services, routes, and tests;
- PreviousPaper and PreviousQuestion components;
- Topic-priority components;
- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

Report the inspection result for every unchanged dependency, configuration, infrastructure, and governance file.

## Required tests

Add focused PostgreSQL/API coverage proving:

- migration upgrades all existing NoteDrafts to `UNRELEASED` with null release metadata and without inferred release;
- migration downgrade to `c7a4e9d2f816` and re-upgrade preserve Topic, ContentVersion ownership including legacy nulls, Markdown, ordered Claim links, approval fields, and creation time;
- new NoteDrafts begin UNRELEASED with null release metadata;
- approval does not imply release;
- a complete version-owned APPROVED NoteDraft can transition UNRELEASED → RELEASED;
- release records a timezone-aware UTC timestamp and optional note;
- release preserves Topic, ContentVersion, Markdown, ordered Claim provenance, creation time, and approval metadata;
- later Claim approval changes do not affect release eligibility or the stored snapshot;
- Claim, Verification, QuestionBankItem, and other NoteDraft states cannot substitute for the target NoteDraft's own approval;
- DRAFT and REJECTED NoteDrafts cannot be released and remain unchanged;
- an approved legacy null-ContentVersion draft cannot be released and remains unchanged;
- UNRELEASED → WITHDRAWN returns the exact stable 409 with no mutation;
- duplicate release returns the exact stable 409 with no mutation;
- RELEASED → WITHDRAWN preserves `released_at`, records timezone-aware UTC `withdrawn_at`, and stores the optional withdrawal note;
- WITHDRAWN cannot be withdrawn again or re-released;
- DRAFT/REJECTED approval changes are blocked while RELEASED;
- approval changes are allowed again after withdrawal without changing historical release metadata;
- missing NoteDraft returns the established 404;
- missing, invalid, and UNRELEASED request decisions return standard 422;
- PostgreSQL rejects invalid release statuses and every invalid status/timestamp/note combination;
- PostgreSQL rejects RELEASED rows without APPROVED review;
- PostgreSQL rejects RELEASED or WITHDRAWN rows without ContentVersion ownership;
- decision failures are atomic and leave no partial mutation;
- the approved-drafts collection remains approval-only and preserves release metadata;
- preview, persisted creation, retrieval, and existing approval behavior remain compatible;
- all T-013 through T-027 regressions continue to pass.

Do not weaken, delete, or silently skip existing tests.

## Exclusions

Do not add:

- a released NoteDraft collection;
- publication transport or publication records;
- public or learner-facing APIs;
- PDF generation, export, download, storage, or deployment;
- users, authentication, authorization, reviewer/releaser identity, or decision-history tables;
- edit, delete, supersede, retrofit, or backfill endpoints;
- automatic ContentVersion selection or inference;
- automatic next-version calculation;
- per-learner note copies;
- practice sessions, attempts, analytics, mock assembly, or personalization;
- AI/LLM providers, prompts, generation, ingestion, RAG, embeddings, or scraping;
- QuestionBankItem changes;
- PreviousQuestion conversion;
- prediction, probability, or likelihood semantics;
- dependencies, secrets, environment variables, Docker services, payments, or unrelated infrastructure.

A PreviousQuestion remains a sourced historical occurrence and must never be converted into a generated question or represented as prediction.

## Documentation

Update `docs/architecture.md` and `docs/workflow.md` only for behavior actually implemented.

Append—never rewrite, reorder, consolidate, or delete history:

- the T-028 implementation record in `docs/task_log.md`;
- an implementation note beneath this T-028 prompt in `docs/next_task.md`.

Do not mark T-028 approved.

Do not define or implement T-029.

## Validation

Run and report exact results for:

- focused NoteDraft tests;
- the full test suite;
- Ruff on every changed Python file;
- fresh upgrade through the new T-028 migration;
- downgrade to T-027 head `c7a4e9d2f816`;
- re-upgrade to the new T-028 migration;
- seeded version-owned and legacy-null NoteDraft preservation across the migration cycle;
- direct PostgreSQL rejection of invalid release states and missing approval/ownership;
- `uv run alembic heads`;
- `uv run alembic check`;
- `git diff --check`;
- `git status --short`.

Use a dedicated PostgreSQL test database. Never run destructive migration-cycle testing against a non-test database.

## Final report

Report:

1. files changed;
2. release fields and PostgreSQL constraints;
3. migration revision, parent, upgrade, downgrade, and seeded-row behavior;
4. exact release request and response contract;
5. allowed transitions and stable 404/409/422 behavior;
6. approval and non-null ContentVersion eligibility;
7. review-state locking while RELEASED;
8. transaction locking, atomicity, and rollback behavior;
9. stored Markdown, ContentVersion, and ordered Claim-provenance preservation;
10. legacy null-ownership compatibility and release rejection;
11. approved-list compatibility;
12. focused, migration, and full-suite test results;
13. Ruff, Alembic-head, Alembic-check, and diff-check results;
14. dependency/configuration/Docker/AGENTS/README review outcomes;
15. retained trust, provenance, versioning, approval, release, and Generate Once/Personalize Later boundaries;
16. final git status;
17. explicit confirmation that no commit, push, PR, self-approval, T-029, released-draft collection, publication transport, public/learner delivery, PDF, AI generation, mock assembly, or personalization work occurred.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-029.

Leave T-028 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-07 Asia/Kolkata, UTC+05:30): added only the controlled NoteDraft `UNRELEASED`/`RELEASED`/`WITHDRAWN` lifecycle, migration `d9e5b2a7c418`, and `POST /api/v1/note-drafts/{note_draft_id}/release`. Release requires the draft's own APPROVED review and non-null stored ContentVersion; withdrawal preserves the original release time, and released drafts block DRAFT/REJECTED review changes until withdrawal. PostgreSQL independently enforces lifecycle metadata, approval, and ownership invariants. The approved-drafts collection remains approval-only, legacy null-owned drafts remain readable/reviewable but unreleasable, and no released collection, publication, learner delivery, PDF, AI, personalization, or T-029 work was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.
---

## T-028 review outcome

- **APPROVED** after independent inspection of implementation commit `4974d87f90c08a5e39b3fe31a5cd1f7e1f9a4470` against its canonical T-028 prompt and parent `ac5f19c54c637dba27c5e396641c9d6cc34896dd`.
- The immutable commit adds the controlled NoteDraft UNRELEASED/RELEASED/WITHDRAWN lifecycle, migration `d9e5b2a7c418`, stored response metadata, row-locked release and approval decisions, and exactly one release-decision endpoint.
- Release requires the target NoteDraft's own APPROVED review and non-null stored ContentVersion. Withdrawal preserves the original release time, and legacy null-owned drafts remain readable and reviewable but cannot be released.
- The corrected tests explicitly verify UTC release and withdrawal timestamps. Developer-recorded evidence is 41 focused NoteDraft tests and 183 full-suite tests, each with one existing warning, plus successful Ruff, migration-cycle, PostgreSQL constraint, Alembic, and diff checks.
- GitHub exposes no status contexts or workflow runs for the implementation commit, so no CI pass is claimed.
- No released-draft collection, publication transport, public/learner delivery, PDF, AI, personalization, dependency, configuration, Docker, or T-029 implementation was included.

---

# T-029 — Add released NoteDraft read boundary

Read `AGENTS.md` and all project documents first. Inspect the live repository and the approved T-013 through T-028 implementation conventions before changing code.

Do **not** commit, push, create a PR, self-approve, or implement T-030. Leave the complete T-029 working tree uncommitted and unpushed for independent review.

## Current context

T-028 is approved at implementation commit:

`4974d87f90c08a5e39b3fe31a5cd1f7e1f9a4470`

The platform now stores version-owned NoteDraft snapshots with:

- deterministic Markdown;
- exact ordered Claim provenance;
- independent DRAFT/APPROVED/REJECTED human review;
- independent UNRELEASED/RELEASED/WITHDRAWN release state;
- one-way release and withdrawal transitions;
- approval-only retrieval through `GET /api/v1/note-drafts/approved`.

There is no read boundary that returns only currently RELEASED NoteDrafts. T-029 adds only that internal read boundary.

## Goal

Add one read-only internal endpoint returning stored NoteDraft snapshots whose own current `release_status` is exactly `RELEASED`.

This boundary makes currently released canonical note snapshots available to later publication/assembly stages. It does not publish, transport, render, deliver, regenerate, personalize, or modify notes.

Preserve the project rule: **Generate Once, Personalize Later**.

## Data model and persistence

No model or database schema change is expected.

Do not add or modify a migration. Alembic head must remain:

`d9e5b2a7c418`

If inspection reveals a genuine persistence change is necessary, stop and report the architectural reason before making that change.

Preserve unchanged:

- NoteDraft identity and Topic ownership;
- nullable legacy-safe ContentVersion ownership;
- stored deterministic Markdown;
- ordered NoteDraftClaim provenance;
- approval state and metadata;
- release state and metadata;
- all PostgreSQL constraints;
- all existing migrations.

## API contract

Add exactly one endpoint:

`GET /api/v1/note-drafts/released`

Response:

- HTTP 200;
- `list[NoteDraftResponse]`;
- include only NoteDraft rows whose own `release_status` is exactly `RELEASED`;
- order results by ascending NoteDraft ID;
- return `[]` when no currently released drafts exist.

Each response must preserve the existing stored fields:

- NoteDraft ID;
- Topic ID and Topic name;
- ContentVersion ID;
- creation time;
- ordered Claim IDs;
- Markdown;
- approval status, decision timestamp, and reviewer note;
- release status, release timestamp, withdrawal timestamp, and release note.

Register the static `/note-drafts/released` route before `/note-drafts/{note_draft_id}` so `released` cannot be interpreted as an ID.

## Eligibility and boundary separation

Eligibility depends only on the target NoteDraft's own current persisted:

`release_status == 'RELEASED'`

Therefore:

- UNRELEASED drafts are excluded, including APPROVED UNRELEASED drafts;
- WITHDRAWN drafts are excluded, including APPROVED WITHDRAWN drafts;
- RELEASED drafts are included;
- current Claim approval or Verification state must not affect eligibility;
- QuestionBankItem approval/release state must not affect eligibility;
- other NoteDraft approval/release state must not affect eligibility;
- Topic-priority results must not affect eligibility.

The existing approved-drafts endpoint must remain approval-only:

`GET /api/v1/note-drafts/approved`

It must continue returning NoteDrafts based only on their own APPROVED review state, regardless of whether they are UNRELEASED, RELEASED, or WITHDRAWN.

Do not merge approval and release semantics.

## Stored-snapshot and read-only behavior

Return the stored NoteDraft snapshot.

Do not:

- regenerate or re-render Markdown;
- recalculate or reorder Claim provenance;
- infer or recalculate ContentVersion ownership;
- re-evaluate current Claim approval;
- re-evaluate Verification, Evidence, Source, syllabus, historical-question, or priority state;
- mutate any database row;
- acquire a row lock;
- flush or commit;
- perform a release, withdrawal, or approval transition.

Eagerly load the Topic and ordered Claim links for all returned NoteDrafts. Avoid per-draft Topic or Claim queries and any obvious N+1 query behavior.

Preserve ascending NoteDraft order and each draft's persisted Claim-link position order.

## Error and empty-result behavior

No new domain error is expected.

- An empty eligible set returns HTTP 200 with `[]`.
- The collection endpoint does not return 404 merely because no rows qualify.
- Existing individual retrieval, approval, release, creation, and preview error behavior must remain unchanged.

## Layering

Preserve:

`Route → Pydantic schema → Service → Repository → PostgreSQL`

Requirements:

- keep the route thin;
- reuse `NoteDraftResponse`;
- keep filtering, ordering, and eager-loading in the repository;
- keep response serialization in the service;
- perform no writes in any layer;
- do not duplicate serialization logic unnecessarily.

## Affected components

Inspect and update only where necessary:

- `app/api/v1/routes/knowledge.py`;
- `app/repositories/knowledge.py`;
- `app/services/knowledge.py`;
- focused NoteDraft API/PostgreSQL tests;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md`;
- append-only `docs/next_task.md`.

Inspect but leave unchanged unless a genuine T-029 requirement proves otherwise:

- `app/models/note_draft.py`;
- `app/schemas/knowledge.py`;
- model registration and Alembic metadata;
- all migration files;
- ContentVersion components;
- QuestionBankItem components and tests;
- PreviousPaper and PreviousQuestion components;
- Topic-priority components;
- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

Report the inspection outcome for every unchanged dependency, configuration, infrastructure, schema, model, migration, and governance file.

## Required tests

Add focused API/PostgreSQL coverage proving:

- an empty database returns HTTP 200 with `[]`;
- a database with no currently RELEASED drafts returns `[]`;
- DRAFT UNRELEASED drafts are excluded;
- APPROVED UNRELEASED drafts are excluded;
- APPROVED WITHDRAWN drafts are excluded;
- multiple RELEASED drafts are included in ascending NoteDraft-ID order;
- every returned draft preserves its stored Topic identity and name;
- every returned draft preserves its stored ContentVersion ID;
- every returned draft preserves its Markdown and creation timestamp;
- ordered Claim IDs retain persisted position order;
- approval metadata is preserved;
- release metadata is preserved;
- later Claim approval changes do not alter eligibility or the stored snapshot;
- Verification, QuestionBankItem, other NoteDraft, and Topic-priority state cannot make an UNRELEASED or WITHDRAWN draft eligible;
- the endpoint performs no database mutation;
- the existing approved-drafts endpoint remains approval-only and continues to include approved UNRELEASED and approved WITHDRAWN drafts;
- the static released route is not captured by the dynamic NoteDraft-ID route;
- existing NoteDraft creation, retrieval, approval, release, withdrawal, preview, and approved-list tests continue to pass;
- all T-017 through T-028 exam, version, question, priority, review, release, and read-boundary regressions continue to pass.

Use the cleanest PostgreSQL-backed test level consistent with the existing suite. Do not weaken, delete, or silently skip existing tests.

## Exclusions

Do not add:

- any model or database schema change;
- a migration;
- NoteDraft release or approval changes;
- publication records or publication transport;
- public or learner-facing endpoints;
- PDF generation, exports, downloads, storage, or deployment;
- content bundles, editions, packages, or mock assembly;
- users, authentication, authorization, reviewer/releaser identity, or history;
- edit, delete, supersede, retrofit, or backfill behavior;
- automatic ContentVersion selection or next-version calculation;
- per-learner note copies;
- practice sessions, attempts, analytics, or personalization;
- AI/LLM providers, prompts, generation, ingestion, RAG, embeddings, or scraping;
- QuestionBankItem changes;
- PreviousQuestion conversion;
- prediction, probability, likelihood, or guarantee semantics;
- dependencies, secrets, environment variables, Docker services, payments, or unrelated infrastructure.

A PreviousQuestion remains a sourced historical occurrence. It must never be converted into generated content or represented as a prediction.

## Documentation

Update `docs/architecture.md` and `docs/workflow.md` only for behavior actually implemented.

Append—never rewrite, reorder, consolidate, or delete history:

- the T-029 implementation record in `docs/task_log.md`;
- an implementation note beneath this T-029 prompt in `docs/next_task.md`.

Do not mark T-029 approved.

Do not define or implement T-030.

## Validation

Run and report exact results for:

- focused T-029 released-NoteDraft tests;
- the existing focused NoteDraft suite;
- the full test suite;
- Ruff on every changed Python file;
- `uv run alembic heads`;
- `uv run alembic check`;
- `git diff --check`;
- `git status --short`.

Confirm:

- Alembic head remains `d9e5b2a7c418`;
- no migration or schema drift exists;
- no dependency, configuration, environment, or Docker change occurred.

No migration downgrade/re-upgrade cycle is expected because T-029 must not change persistence.

## Final report

Report:

1. files changed;
2. endpoint and exact RELEASED eligibility behavior;
3. result and nested Claim ordering;
4. eager-loading and N+1 avoidance;
5. stored ContentVersion, Markdown, approval, and release metadata;
6. stored-snapshot and no-mutation behavior;
7. empty-result and error behavior;
8. compatibility with the approved-drafts boundary and existing transitions;
9. focused and full-suite test results;
10. Ruff, Alembic-head, Alembic-check, and diff-check results;
11. model, schema, migration, dependency, configuration, Docker, AGENTS, and README inspection outcomes;
12. retained trust, provenance, review, release, versioning, and Generate Once/Personalize Later boundaries;
13. final git status;
14. explicit confirmation that no commit, push, PR, self-approval, T-030, publication transport, public/learner delivery, PDF, content-package, mock-assembly, AI-generation, or personalization work occurred.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-030.

Leave T-029 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-07 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/note-drafts/released` through the existing route, service, repository, and `NoteDraftResponse` flow. It filters exactly on current RELEASED state, returns stored snapshots in ascending ID order with Topic and ordered Claim provenance eagerly loaded, and returns `[]` when none qualify. The approved-drafts boundary remains approval-only. No model, schema, migration, lock, write, regeneration, publication, learner delivery, PDF, content package, mock assembly, AI, personalization, or T-030 work was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## T-029 independent review outcome

T-029 is **APPROVED** at implementation commit `ee755cfc3a88700abababf2473bd8d615c16c871`, whose parent is the T-029 task-issuance commit `a351673bc242261640faa1468a33e395fe740e4b`.

The immutable commit adds only `GET /api/v1/note-drafts/released` through the existing route, service, repository, response schema, focused tests, and documentation. It filters exactly on current RELEASED state, orders by ascending NoteDraft ID, eagerly loads Topic and ordered Claim links, preserves stored ContentVersion and review/release metadata, performs no writes or regeneration, and leaves the approved-draft boundary approval-only.

Developer-recorded validation reported 2 focused released-draft tests, 41 focused NoteDraft tests, and 185 full-suite tests, each with one existing warning, plus successful Ruff, Alembic-head/check, and diff checks. GitHub exposes no status contexts or workflow runs for the implementation commit, so no CI pass is claimed.

No blocking finding was identified. No model, schema, migration, dependency, configuration, Docker, publication transport, public/learner delivery, PDF, content package, mock assembly, AI, personalization, or T-030 implementation was included.

---

# T-030 — Add ContentVersion released-assets manifest

## Role

You are the implementation engineer for `Dyuti60/assam-exam-ai`.

Implement only T-030. Follow `AGENTS.md`, the approved architecture, and the established route → schema → service → repository → PostgreSQL layering.

Start from the synchronized current `origin/main` containing the approved T-029 implementation commit `ee755cfc3a88700abababf2473bd8d615c16c871` and this T-030 issuance. Before editing, fetch, fast-forward, record `git rev-parse HEAD`, and confirm the working tree is clean. If the tree is not clean or the required history is absent, stop without changing files.

Do not rely on prior conversation summaries. Read the live repository and the complete task below.

## Current context

The approved system now has:

- immutable ContentVersion identity for one exact SyllabusVersion/Topic mapping;
- version-owned stored NoteDraft snapshots;
- version-owned stored QuestionBankItem snapshots;
- independent approval and controlled UNRELEASED/RELEASED/WITHDRAWN lifecycles for both asset types;
- read-only global collections for currently RELEASED NoteDrafts and QuestionBankItems;
- stored ordered Claim provenance for both asset types and stored ordered options/correct answer for QuestionBankItems.

The system still has no exact-ContentVersion view that assembles both kinds of currently released canonical assets. It also has no persisted package, edition, publication, PDF, transport, public delivery, learner delivery, AI generation, or personalization.

## Exact bounded goal

Add exactly one read-only internal endpoint:

`GET /api/v1/content-versions/{content_version_id}/released-assets`

It must return one manifest for the requested existing ContentVersion containing:

- the exact stored ContentVersion identity;
- all and only currently RELEASED NoteDraft snapshots owned by that ContentVersion;
- all and only currently RELEASED QuestionBankItem snapshots owned by that ContentVersion.

This is a computed read response only. Do not persist a manifest or introduce any package/publication entity.

## API contract

Add a response schema named `ContentVersionReleasedAssetsResponse` with exactly:

```json
{
  "content_version": {
    "id": 1,
    "syllabus_version_id": 1,
    "topic_id": 1,
    "version": 1,
    "created_at": "stored timestamp"
  },
  "note_drafts": [],
  "question_bank_items": []
}
```

Schema types:

- `content_version: ContentVersionResponse`
- `note_drafts: list[NoteDraftResponse]`
- `question_bank_items: list[QuestionBankItemResponse]`

Return HTTP 200 for an existing ContentVersion, including when one or both asset lists are empty.

If the ContentVersion does not exist, return the established resource error exactly:

- HTTP 404
- `{"detail": "ContentVersion <id> not found"}`

Path validation and all unrelated error behavior must remain consistent with the current API.

## Eligibility and ownership invariants

A NoteDraft is eligible only when both are true:

- `NoteDraft.content_version_id == content_version_id`
- `NoteDraft.release_status == "RELEASED"`

A QuestionBankItem is eligible only when both are true:

- `QuestionBankItem.content_version_id == content_version_id`
- `QuestionBankItem.release_status == "RELEASED"`

Therefore:

- UNRELEASED assets are excluded even when APPROVED;
- WITHDRAWN assets are excluded even when APPROVED;
- RELEASED assets belonging to another ContentVersion are excluded;
- no asset may be inferred from shared Topic, SyllabusVersion, Claims, approval, or any other state;
- current Claim, Verification, Evidence, Source, NoteDraft, QuestionBankItem, PreviousQuestion, or Topic-priority state must not substitute for exact stored ownership and RELEASED state.

Return each asset list in ascending asset-ID order. Preserve each NoteDraft's persisted Claim-link position order and each QuestionBankItem's persisted Claim-link and option position order.

## Stored-snapshot behavior

Return existing stored response snapshots without modification.

For NoteDrafts preserve:

- ID, Topic identity/name, ContentVersion ID, Markdown, creation timestamp;
- ordered Claim IDs;
- approval metadata;
- release metadata.

For QuestionBankItems preserve:

- ID, ContentVersion ID, question text, explanation, difficulty, creation timestamp;
- ordered Claim IDs;
- ordered options and correct-option position;
- approval metadata;
- release metadata.

Do not regenerate Markdown or questions, rebuild provenance, reorder stored nested data, infer ownership, or re-evaluate current Claim approval or verification state.

## Repository and query requirements

Keep ContentVersion existence lookup and release/ownership filtering in the repository.

Use fixed-query eager loading appropriate to the existing relationships:

- NoteDraft Topic must be eagerly loaded;
- NoteDraft Claim links must be eagerly loaded;
- QuestionBankItem Claim links and options must be eagerly loaded.

Avoid per-asset relationship queries and obvious N+1 behavior. Filtering must occur in PostgreSQL, not by loading the global released collections and filtering them in Python.

Reuse the existing stored serializers for `ContentVersionResponse`, `NoteDraftResponse`, and `QuestionBankItemResponse`. Do not duplicate response construction unnecessarily.

## Transaction, atomicity, and read-only requirements

This endpoint is read-only.

It must not:

- acquire `FOR UPDATE` or any row lock;
- add, update, or delete ORM objects;
- flush or commit;
- invoke approval, release, or withdrawal transitions;
- create a NoteDraft, QuestionBankItem, ContentVersion, package, or audit row;
- regenerate or personalize content.

A normal request must leave all relevant row counts and stored snapshots unchanged. No new write transaction or rollback-specific domain behavior is needed.

## Data model and migration requirements

No model or database schema change is expected or authorized.

Do not:

- add a model, table, column, index, constraint, relationship, enum, trigger, or extension;
- edit historical migrations;
- create a new Alembic revision.

Alembic head must remain exactly `d9e5b2a7c418`, and `uv run alembic check` must report no new upgrade operations.

A new response schema is expected because the manifest has a new composite response shape; request schemas and persisted schemas remain unchanged.

## Route ordering and compatibility

Register the endpoint in the ContentVersion route area so it remains compatible with the existing `GET /api/v1/content-versions/{content_version_id}` route.

Do not change the behavior or contract of:

- ContentVersion creation or individual retrieval;
- global approved/released NoteDraft collections;
- global approved/released QuestionBankItem collections;
- any approval, release, withdrawal, preview, creation, or retrieval transition.

The new endpoint is an internal assembly/read boundary, not publication and not learner delivery.

## Affected components

Inspect and update only where required:

- `app/schemas/knowledge.py`;
- `app/api/v1/routes/knowledge.py`;
- `app/repositories/knowledge.py`;
- `app/services/knowledge.py`;
- focused API/PostgreSQL tests for the manifest;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md`;
- append-only `docs/next_task.md`.

Inspect but leave unchanged unless a genuine T-030 requirement proves otherwise:

- all model files and model registration;
- every Alembic migration;
- ContentVersion, NoteDraft, and QuestionBankItem persistence definitions;
- existing transition behavior;
- PreviousPaper, PreviousQuestion, Topic-priority, Claim, Evidence, Verification, and Source components;
- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

Report the inspection outcome for all unchanged model, migration, dependency, configuration, infrastructure, and governance files.

## Required tests

Add focused PostgreSQL-backed API tests proving:

- a missing ContentVersion returns the exact established 404;
- an existing ContentVersion with no assets returns HTTP 200 with the exact ContentVersion response and two empty lists;
- an existing ContentVersion with only ineligible assets returns empty lists;
- APPROVED UNRELEASED NoteDrafts and QuestionBankItems are excluded;
- APPROVED WITHDRAWN NoteDrafts and QuestionBankItems are excluded;
- RELEASED assets belonging to another ContentVersion are excluded, including another version for the same Topic/Syllabus mapping where possible;
- multiple eligible NoteDrafts are returned in ascending NoteDraft-ID order;
- multiple eligible QuestionBankItems are returned in ascending QuestionBankItem-ID order;
- NoteDraft Topic identity/name, ContentVersion ownership, Markdown, creation time, ordered Claim IDs, approval metadata, and release metadata are preserved;
- QuestionBankItem ContentVersion ownership, question/explanation/difficulty, creation time, ordered Claim IDs, ordered options, correct answer, approval metadata, and release metadata are preserved;
- later Claim approval changes do not alter eligibility or stored snapshots;
- Verification, Evidence, Source, other released assets, PreviousQuestion, and Topic-priority state cannot substitute for exact ContentVersion ownership plus RELEASED state;
- the endpoint performs no database mutation and leaves relevant stored snapshots and row counts unchanged;
- existing individual ContentVersion retrieval remains compatible;
- existing global released and approved NoteDraft/QuestionBankItem boundaries retain their current independent semantics;
- all existing T-017 through T-029 regression tests continue to pass.

Use the cleanest focused test file consistent with repository conventions. Do not weaken, delete, or silently skip existing tests.

## Error behavior

Only the established missing-ContentVersion 404 is newly relevant.

Do not introduce a 404 for an existing ContentVersion with no eligible assets. Do not create new 409 behavior. Do not catch generic database exceptions and relabel them as domain conflicts.

## Documentation requirements

Update `docs/architecture.md` and `docs/workflow.md` only for behavior actually implemented.

Append—never rewrite, reorder, consolidate, or delete history:

- a T-030 implementation record in `docs/task_log.md` with status `Ready for review`;
- an implementation note beneath this T-030 prompt in `docs/next_task.md`.

Do not mark T-030 approved. Do not define or implement T-031.

## Dependency, configuration, and Docker review

Explicitly inspect `pyproject.toml`, `uv.lock`, `.env.example`, `app/core/config.py`, and `docker-compose.yml`.

No new dependency, secret, environment variable, configuration setting, Docker service, storage backend, or infrastructure change is expected. If any appears necessary, stop and report why instead of expanding scope.

## Required validation

Use a dedicated PostgreSQL test database whose name ends with `_test`.

Run and report exact output summaries for:

- focused T-030 manifest tests;
- existing ContentVersion tests;
- existing released NoteDraft tests;
- existing released QuestionBankItem tests;
- the full test suite;
- Ruff on every changed Python file;
- `uv run alembic heads`;
- `uv run alembic check`;
- `git diff --check`;
- `git status --short`.

Confirm:

- Alembic head remains `d9e5b2a7c418`;
- no migration or schema drift exists;
- no dependency, configuration, environment, Docker, model, or persistence change occurred.

No migration upgrade/downgrade cycle is required because T-030 must not change persistence, but the dedicated database must be upgraded to the current head before tests.

## Exclusions and retained boundaries

Do not add:

- a persisted manifest, content package, bundle, edition, publication, or release aggregate;
- publication status or publication transport;
- PDF, HTML export, download, object storage, CDN, email, or delivery behavior;
- public or learner-facing endpoints;
- users, authentication, authorization, reviewer/releaser identity, or decision history;
- learner copies, practice sessions, attempts, scoring, analytics, recommendations, or personalization;
- AI/LLM providers, prompts, generation, ingestion, RAG, embeddings, vector columns, or scraping;
- automatic ContentVersion selection, latest-version inference, or next-version calculation;
- content edits, deletion, supersession, retrofit, backfill, or copying between versions;
- new release or approval transitions;
- QuestionBankItem or NoteDraft model changes;
- PreviousQuestion conversion, prediction, probability, likelihood, or guarantee semantics;
- dependencies, secrets, configuration, Docker services, payments, or unrelated infrastructure.

A PreviousQuestion remains a sourced historical occurrence and must never be converted into generated content or represented as a prediction.

Preserve trust, source provenance, explicit human review, controlled release, immutable stored snapshots, exact ContentVersion ownership, and Generate Once/Personalize Later.

## Final report

Report:

1. exact starting HEAD;
2. files changed;
3. endpoint and response contract;
4. exact ContentVersion ownership and RELEASED eligibility behavior;
5. ordering and eager-loading behavior;
6. stored NoteDraft and QuestionBankItem snapshot preservation;
7. empty-result and 404 behavior;
8. no-mutation and transaction behavior;
9. compatibility with all existing approved/released boundaries and transitions;
10. focused and full-suite test results;
11. Ruff, Alembic-head, Alembic-check, and diff-check results;
12. model, migration, dependency, configuration, Docker, AGENTS, and README inspection outcomes;
13. retained architecture boundaries;
14. final `git status --short`;
15. explicit confirmation that no commit, push, PR, self-approval, T-031, package persistence, publication transport, public/learner delivery, PDF, AI generation, or personalization work occurred.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-031.

Leave T-030 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-07 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/content-versions/{content_version_id}/released-assets` through the existing route, schema, service, repository, and stored-response serializers. It resolves the exact ContentVersion, returns only its currently RELEASED NoteDraft and QuestionBankItem snapshots in ascending asset-ID order with required nested provenance eagerly loaded, and returns empty asset lists for an existing version with no eligible assets. It performs no locks, writes, transitions, regeneration, inference, or current-state re-evaluation. No model, migration, dependency, configuration, Docker, package persistence, publication transport, public/learner delivery, PDF, AI, personalization, or T-031 work was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## T-030 independent review outcome

T-030 is **APPROVED** at implementation commit `3a81ce6cefdcc3bd0abd7a17ecc1472d5bb1d4d4`, whose parent is the T-030 task-issuance commit `f25c633b86648bf9958cdf317b72336a38dd5ca6`.

The implementation commit was mistakenly titled `T-031 implemented`. Empty corrective commit `265f683b5180cde585d366fce17ffe53c11c1955` clarifies that it implements T-030, not T-031, without changing any file or rewriting history.

The immutable T-030 diff adds only `GET /api/v1/content-versions/{content_version_id}/released-assets` through the existing layering. It filters NoteDrafts and QuestionBankItems in PostgreSQL by exact ContentVersion ownership and current RELEASED state, orders each list by ascending asset ID, eagerly loads required nested provenance, reuses stored serializers, returns the established missing-version 404 or successful empty lists, and performs no locks, writes, regeneration, inference, or current-state re-evaluation.

Developer-recorded validation reported 3 focused manifest tests, 12 ContentVersion tests, 2 released-NoteDraft tests, 2 released-QuestionBankItem tests, and 188 full-suite tests, each with one existing warning, plus successful Ruff, fresh database upgrade, Alembic-head/check, and diff checks. GitHub exposes no status contexts or workflow runs for either pushed commit, so no CI pass is claimed.

No blocking finding remains. No model, migration, dependency, configuration, Docker, package persistence, publication transport, public/learner delivery, PDF, AI, personalization, or actual T-031 implementation was included.

---

# T-031 — Persist immutable ContentPackage membership snapshot

## Role

You are the implementation engineer for `Dyuti60/assam-exam-ai`.

Implement only T-031. Follow `AGENTS.md`, the live approved architecture, and the established route → schema → service → repository → PostgreSQL layering.

Before editing:

1. fetch `origin`;
2. fast-forward local `main`;
3. record `git rev-parse HEAD`;
4. confirm local HEAD equals `origin/main`;
5. confirm the working tree is clean;
6. confirm approved T-030 implementation commit `3a81ce6cefdcc3bd0abd7a17ecc1472d5bb1d4d4` and its empty traceability correction `265f683b5180cde585d366fce17ffe53c11c1955` exist in history;
7. read the complete live repository and this prompt.

If the branch, history, synchronization, or working tree is unexpected, stop without changing files.

Do not rely on previous conversation summaries. The live repository is authoritative.

## Current context

The approved system has:

- exact ContentVersion identity for one SyllabusVersion/Topic/version mapping;
- version-owned stored NoteDraft and QuestionBankItem snapshots;
- independent approval and controlled release lifecycles for both asset types;
- global read-only RELEASED collections;
- `GET /api/v1/content-versions/{content_version_id}/released-assets`, which computes the currently released assets for one exact ContentVersion without persistence.

The system does not yet freeze that computed membership into a retained package identity. It has no ContentPackage model, package retrieval API, package release/publication lifecycle, PDF generation, public/learner delivery, AI generation, or personalization.

## Exact bounded goal

Add only atomic creation of an immutable internal ContentPackage membership snapshot for one exact existing ContentVersion.

Add exactly one endpoint:

`POST /api/v1/content-versions/{content_version_id}/content-packages`

The endpoint takes no request body.

At one transaction boundary it must:

1. resolve the exact ContentVersion;
2. load all currently RELEASED NoteDrafts owned by that ContentVersion in ascending NoteDraft-ID order;
3. load all currently RELEASED QuestionBankItems owned by that ContentVersion in ascending QuestionBankItem-ID order;
4. reject creation when both eligible collections are empty;
5. persist one ContentPackage identity;
6. persist exact ordered membership links for both asset types;
7. commit once;
8. return the stored package membership response.

This task freezes membership only. Do not copy or regenerate educational content.

## API contract

Return HTTP 201 with a new response schema named `ContentPackageResponse`:

```json
{
  "id": 1,
  "content_version_id": 1,
  "created_at": "stored UTC timestamp",
  "note_draft_ids": [10, 11],
  "question_bank_item_ids": [20, 21]
}
```

Required field types:

- `id: int`
- `content_version_id: int`
- `created_at: datetime`
- `note_draft_ids: list[int]`
- `question_bank_item_ids: list[int]`

The two ID lists must reflect persisted association positions, which initially match ascending asset-ID order.

No create-request schema is needed because the endpoint accepts no body.

## Error behavior

If the ContentVersion does not exist, return the established error:

- HTTP 404
- `{"detail": "ContentVersion <id> not found"}`

If neither a RELEASED NoteDraft nor a RELEASED QuestionBankItem belongs to that ContentVersion, return:

- HTTP 409
- `{"detail": "ContentVersion <id> has no released assets to package"}`

The 409 must leave zero partial ContentPackage or membership rows.

A package may contain only NoteDrafts or only QuestionBankItems. It is invalid only when both collections are empty.

Do not introduce unrelated 404/409 behavior. Generic database exceptions must be rolled back and re-raised rather than mislabeled as domain conflicts.

## Eligibility and snapshot invariants

A NoteDraft may be captured only when both are true at selection time:

- `NoteDraft.content_version_id == content_version_id`
- `NoteDraft.release_status == "RELEASED"`

A QuestionBankItem may be captured only when both are true at selection time:

- `QuestionBankItem.content_version_id == content_version_id`
- `QuestionBankItem.release_status == "RELEASED"`

Therefore:

- UNRELEASED assets are excluded even if APPROVED;
- WITHDRAWN assets are excluded even if APPROVED;
- RELEASED assets owned by another ContentVersion are excluded;
- shared Topic, SyllabusVersion, Claims, approval, verification, priority, or other package state cannot substitute for exact ContentVersion ownership and RELEASED state;
- current Claim approval changes must not re-evaluate or invalidate an otherwise RELEASED stored asset during package creation.

Persist NoteDraft membership in ascending NoteDraft-ID order with zero-based contiguous positions.

Persist QuestionBankItem membership in ascending QuestionBankItem-ID order with zero-based contiguous positions.

After package creation, later asset withdrawal or review-state changes must not alter, delete, reorder, or recalculate the stored package membership. Do not add automatic synchronization.

## Data model

Add exactly these models and tables, using repository naming conventions.

### ContentPackage

Table: `content_packages`

Fields:

- `id`: integer primary key;
- `content_version_id`: non-null integer;
- `created_at`: non-null timezone-aware timestamp using the repository's normal UTC/server-time convention.

Constraints:

- foreign key from `content_version_id` to `content_versions.id`;
- `ON DELETE RESTRICT`;
- supporting uniqueness over `(id, content_version_id)` for composite membership references.

Relationships may expose position-ordered NoteDraft and QuestionBankItem membership links.

Do not add package name, label, version number, status, approval, release, publication, file, checksum, user, or mutable metadata.

### ContentPackageNoteDraft

Table: `content_package_note_drafts`

Fields:

- `content_package_id`: non-null integer;
- `content_version_id`: non-null integer;
- `note_draft_id`: non-null integer;
- `position`: non-null integer.

Constraints:

- one composite primary key or equivalent uniqueness preventing the same NoteDraft from appearing twice in one package;
- unique `(content_package_id, position)`;
- check `position >= 0`;
- composite foreign key `(content_package_id, content_version_id)` → `content_packages(id, content_version_id)`;
- composite foreign key `(note_draft_id, content_version_id)` → `note_drafts(id, content_version_id)`;
- package-link deletion may cascade only when its ContentPackage is deleted;
- deletion of a referenced NoteDraft must be restricted.

### ContentPackageQuestionBankItem

Table: `content_package_question_bank_items`

Fields:

- `content_package_id`: non-null integer;
- `content_version_id`: non-null integer;
- `question_bank_item_id`: non-null integer;
- `position`: non-null integer.

Constraints:

- one composite primary key or equivalent uniqueness preventing the same QuestionBankItem from appearing twice in one package;
- unique `(content_package_id, position)`;
- check `position >= 0`;
- composite foreign key `(content_package_id, content_version_id)` → `content_packages(id, content_version_id)`;
- composite foreign key `(question_bank_item_id, content_version_id)` → `question_bank_items(id, content_version_id)`;
- package-link deletion may cascade only when its ContentPackage is deleted;
- deletion of a referenced QuestionBankItem must be restricted.

Add only the supporting unique constraints required for those composite foreign keys:

- `note_drafts(id, content_version_id)`;
- `question_bank_items(id, content_version_id)`.

These supporting constraints do not change eligibility and do not make legacy null-owned NoteDrafts packageable.

PostgreSQL must independently reject cross-ContentVersion membership, duplicate asset membership, duplicate positions, and negative positions.

Database constraints cannot and should not require a linked asset to remain RELEASED forever; eligibility is checked and locked at package creation, while retained membership survives later withdrawal.

## Migration requirements

Create exactly one new Alembic revision whose parent is current head:

`d9e5b2a7c418`

The migration must:

- add only the required supporting unique constraints;
- create `content_packages`;
- create both ordered membership tables and constraints;
- preserve every existing row unchanged;
- create no package or membership row for existing data;
- infer no package from current releases;
- avoid permanent server defaults not represented by model metadata.

Downgrade must:

1. drop membership tables before `content_packages`;
2. remove only the supporting unique constraints added by T-031;
3. leave all pre-T-031 ContentVersion, NoteDraft, QuestionBankItem, approval, release, and provenance data unchanged.

Do not edit any historical migration.

Register the new models so Alembic metadata exactly matches the upgraded database.

## Concurrency, transaction, and atomicity

Package creation must use one database transaction.

Use row locking appropriate to the existing synchronous SQLAlchemy architecture:

- lock the target ContentVersion while assembling the package;
- load eligible NoteDraft and QuestionBankItem rows with `SELECT ... FOR UPDATE` or an equivalent explicit locking strategy before persisting membership;
- keep filtering and ordering in PostgreSQL;
- ensure a concurrent withdrawal cannot mutate a selected asset between eligibility selection and package-link persistence.

Successful creation must:

- insert one ContentPackage;
- insert all ordered membership links;
- flush as required;
- commit exactly once;
- return persisted IDs and positions.

Any validation or persistence failure must roll back the entire SQLAlchemy session. No partial package or link rows may remain.

Do not acquire locks in read-only existing endpoints. Do not change existing approval or release locking semantics.

## Repository requirements

Add focused repository methods for:

- loading the target ContentVersion for package creation with an appropriate lock;
- loading exact-ContentVersion RELEASED NoteDrafts for package creation in ascending ID order with the required lock;
- loading exact-ContentVersion RELEASED QuestionBankItems for package creation in ascending ID order with the required lock;
- adding/flushing a ContentPackage and its membership links;
- retrieving or refreshing the newly created package with position-ordered memberships only as needed to produce the creation response.

Do not call HTTP routes internally. Do not load global released collections and filter them in Python.

Avoid obvious N+1 behavior. Package creation does not require serializing full asset bodies, so do not eager-load unrelated Claim, Topic, or option content unless genuinely required by the implementation.

## Service requirements

The service must:

1. validate the ContentVersion exists;
2. retrieve and lock eligible asset rows using repository methods;
3. raise the stable empty-assets conflict before creating any package row;
4. construct zero-based, contiguous, independently ordered membership links;
5. persist atomically;
6. serialize only the stored package identity and ordered asset IDs.

Do not regenerate content, re-evaluate Claim approval, inspect Verification/Evidence/priority state, copy asset bodies, or modify any ContentVersion or asset.

## Route requirements

Keep the route thin:

- delegate to the service;
- return HTTP 201;
- map missing ContentVersion to the established 404;
- map the empty-assets domain conflict to 409;
- do not catch generic persistence exceptions as conflicts.

Register the route compatibly with the existing ContentVersion retrieval and released-assets manifest endpoints.

## Required tests

Add focused PostgreSQL-backed tests proving:

- missing ContentVersion returns the exact 404 and creates no rows;
- an existing ContentVersion with no released assets returns the exact 409 and creates no rows;
- a ContentVersion with only UNRELEASED or WITHDRAWN assets returns the same 409;
- a package may be created with only eligible NoteDrafts;
- a package may be created with only eligible QuestionBankItems;
- a package containing both asset types returns HTTP 201;
- only exact-ContentVersion RELEASED assets are captured;
- RELEASED assets from another ContentVersion are excluded, including another version of the same Topic/Syllabus mapping;
- APPROVED UNRELEASED and APPROVED WITHDRAWN assets are excluded;
- NoteDraft IDs are stored and returned in ascending order with positions `0..n-1`;
- QuestionBankItem IDs are stored and returned in ascending order with positions `0..n-1`;
- later Claim approval changes do not alter release eligibility or membership selection;
- unrelated Verification, Evidence, PreviousQuestion, priority, approval, package, or asset state cannot substitute for exact eligibility;
- response IDs, ContentVersion ownership, and creation timestamp match persisted database rows;
- later withdrawal of a captured asset does not alter or delete stored package membership;
- relevant row counts increase only by one package and its exact link counts;
- injected or constraint-triggered persistence failure rolls back the package and every link;
- PostgreSQL rejects cross-ContentVersion NoteDraft membership;
- PostgreSQL rejects cross-ContentVersion QuestionBankItem membership;
- PostgreSQL rejects duplicate membership, duplicate per-type positions, and negative positions;
- PostgreSQL restricts deletion of the package's ContentVersion and referenced assets while links exist;
- existing T-030 manifest behavior remains read-only and dynamically reflects current RELEASED state rather than package membership;
- all existing approval, release, withdrawal, approved-list, released-list, and ContentVersion regressions pass.

Use nested savepoints for expected PostgreSQL integrity failures. Do not weaken, delete, or silently skip existing tests.

Add migration validation using a dedicated disposable PostgreSQL database:

1. upgrade a fresh database through the new head;
2. upgrade a database at `d9e5b2a7c418` containing representative released and unreleased assets;
3. verify upgrade creates no inferred package and preserves every pre-existing row;
4. create and inspect a representative package;
5. downgrade to `d9e5b2a7c418`;
6. verify all pre-T-031 data survives;
7. re-upgrade to the new head;
8. confirm schema/model consistency and no inferred package.

## Affected components

Inspect and update only where required:

- new ContentPackage and membership models;
- model registration;
- `app/schemas/knowledge.py`;
- `app/repositories/knowledge.py`;
- `app/services/knowledge.py`;
- `app/api/v1/routes/knowledge.py`;
- one new Alembic migration;
- focused package API/PostgreSQL tests;
- existing tests only where response/model registration compatibility genuinely requires it;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md`;
- append-only `docs/next_task.md`.

Inspect but otherwise leave unchanged:

- Claim, Evidence, Verification, Source, Exam, SyllabusVersion, Topic, PreviousPaper, and PreviousQuestion behavior;
- existing NoteDraft and QuestionBankItem approval/release endpoints and response contracts;
- T-030 manifest behavior;
- all historical migrations;
- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

## Documentation requirements

Update `docs/architecture.md` and `docs/workflow.md` only for behavior actually implemented.

Append—never rewrite, reorder, consolidate, or delete history:

- a T-031 implementation record in `docs/task_log.md` with status `Ready for review`;
- an implementation note beneath this T-031 prompt in `docs/next_task.md`.

Document clearly that:

- ContentPackage freezes ordered membership, not copies of content;
- package creation uses currently RELEASED exact-version assets;
- later withdrawal does not rewrite membership;
- the T-030 manifest remains a dynamic current-release read;
- ContentPackage has no approval, release, publication, PDF, delivery, or learner behavior.

Do not mark T-031 approved. Do not define or implement T-032.

## Dependency, configuration, and Docker review

Explicitly inspect:

- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`.

No dependency, secret, environment variable, configuration setting, Docker service, storage backend, or infrastructure change is expected. If one appears necessary, stop and report why rather than expanding scope.

## Exact validation commands

Use a dedicated PostgreSQL test database whose name ends in `_test`.

Run and report exact results for:

- focused T-031 ContentPackage tests;
- existing ContentVersion released-assets manifest tests;
- existing ContentVersion tests;
- existing NoteDraft tests and released-NoteDraft tests;
- existing QuestionBankItem tests and released-QuestionBankItem tests;
- the full test suite;
- Ruff on every changed Python file;
- `uv run alembic heads`;
- `uv run alembic check`;
- fresh upgrade, seeded upgrade, downgrade to `d9e5b2a7c418`, and re-upgrade;
- `git diff --check`;
- whitespace checking for every untracked file;
- `git status --short`.

Confirm:

- exactly one new Alembic head exists;
- the new migration directly follows `d9e5b2a7c418`;
- no historical migration was edited;
- Alembic reports no additional upgrade operations;
- no dependency, configuration, environment, or Docker change occurred.

## Exclusions and retained boundaries

Do not add:

- package retrieval, list, update, edit, delete, supersession, or backfill endpoints;
- package approval, release, withdrawal, publication, or delivery status;
- PDF, HTML export, rendering, download, file storage, object storage, CDN, or email;
- public or learner-facing endpoints;
- users, authentication, authorization, reviewer/releaser identity, or history;
- learner copies, practice sessions, attempts, scoring, analytics, recommendations, mock assembly, or personalization;
- AI/LLM providers, prompts, generation, ingestion, RAG, embeddings, vector columns, or scraping;
- automatic ContentVersion selection, latest-version inference, or next-version calculation;
- content copying, editing, or regeneration;
- new NoteDraft or QuestionBankItem approval/release transitions;
- PreviousQuestion conversion;
- prediction, probability, likelihood, or guarantee semantics;
- dependencies, secrets, configuration, Docker services, payments, or unrelated infrastructure.

A PreviousQuestion remains a sourced historical occurrence and must never be converted into generated content or represented as a prediction.

Preserve trust, source provenance, explicit human review, controlled release, exact ContentVersion ownership, immutable ordered package membership, and Generate Once/Personalize Later.

## Final report

Report:

1. exact starting HEAD;
2. files changed and created;
3. migration revision and parent;
4. new models, tables, fields, relationships, and constraints;
5. endpoint and response contract;
6. exact eligibility and stable ordering;
7. ContentVersion and cross-version enforcement;
8. locking, transaction, commit, and rollback behavior;
9. immutable membership behavior after later withdrawal;
10. error and no-partial-write behavior;
11. focused and full-suite test results;
12. fresh/seeded upgrade, downgrade, re-upgrade, Alembic-head/check, and schema-drift results;
13. Ruff and diff/whitespace-check results;
14. dependency, configuration, environment, Docker, AGENTS, and README inspection outcomes;
15. retained architecture boundaries;
16. final `git status --short`;
17. explicit confirmation that no commit, push, PR, self-approval, T-032, package publication/release, retrieval collection, PDF, export, public/learner delivery, AI generation, mock assembly, or personalization work occurred.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-032.

Leave T-031 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-08 Asia/Kolkata, UTC+05:30): added only `POST /api/v1/content-versions/{content_version_id}/content-packages`, ContentPackage identity and ordered membership models, and migration `e2c6f8a1d943`. Creation locks the exact ContentVersion and its currently RELEASED exact-version NoteDraft and QuestionBankItem rows, then atomically stores independently ordered zero-based membership links. Composite PostgreSQL constraints preserve same-version provenance and ordering; later withdrawal changes the dynamic T-030 manifest without rewriting package membership. No package retrieval/list, approval/release/publication lifecycle, PDF, export, public/learner delivery, AI, mock assembly, personalization, dependency, configuration, or infrastructure change was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`; T-031 remains ready for independent review.


---

## T-031 independent review outcome

T-031 is **APPROVED** at implementation commit `a261a36a539c40b718e2185eaed794f700dd4b77`, whose parent is the T-031 task-issuance commit `12ede1545988432045ea781587d0f09059ee2160`.

Documentation-only correction commit `67e80c29928eb7e913bca99f899082562e4c2cb1` follows the implementation commit and corrects the current inspection date, migration count, ContentPackage model inventory, and verified test count. It changes only `docs/architecture.md`.

The implementation atomically creates an immutable internal ContentPackage for one exact ContentVersion, selecting and locking only its currently RELEASED NoteDrafts and QuestionBankItems in ascending ID order. It stores two independent, zero-based ordered membership lists. PostgreSQL composite foreign keys enforce exact same-ContentVersion membership; primary-key, unique-position, non-negative-position, and restricted-deletion constraints protect the retained snapshot. Later withdrawal changes the dynamic T-030 manifest without rewriting package membership.

Developer-recorded validation reported 10 focused ContentPackage tests and 198 full-suite tests, each with one existing warning, plus focused regressions, successful Ruff, fresh and seeded migration upgrade, downgrade/re-upgrade, PostgreSQL constraint probes, Alembic-head/check, and diff checks. GitHub exposes no status contexts or workflow runs for the implementation or correction commits, so no CI pass is claimed.

No blocking finding remains. No retrieval/list endpoint, mutable package state, package lifecycle, publication, PDF/export, public/learner delivery, AI generation, mock assembly, personalization, dependency, configuration, Docker, or T-032 implementation was included.

---

# T-032 — Add individual ContentPackage retrieval boundary

## Role

You are the implementation engineer for `Dyuti60/assam-exam-ai`.

Implement only T-032. Follow `AGENTS.md`, the live approved architecture, and the established route → schema → service → repository → PostgreSQL layering.

Before editing:

1. fetch `origin`;
2. fast-forward local `main`;
3. record `git rev-parse HEAD`;
4. confirm local HEAD equals `origin/main`;
5. confirm the working tree is clean;
6. confirm approved T-031 implementation commit `a261a36a539c40b718e2185eaed794f700dd4b77` and documentation correction commit `67e80c29928eb7e913bca99f899082562e4c2cb1` exist in history;
7. read the complete live repository and this prompt.

If the branch, history, synchronization, or working tree is unexpected, stop without changing files.

Do not rely on previous conversation summaries. The live repository is authoritative.

## Current context

The approved system has:

- exact ContentVersion identity for one SyllabusVersion/Topic/version mapping;
- version-owned stored NoteDraft and QuestionBankItem snapshots;
- independent human approval and controlled release lifecycles for both asset types;
- read-only approved and currently RELEASED asset boundaries;
- the dynamic T-030 exact-ContentVersion released-assets manifest;
- T-031 ContentPackage identity with two independently position-ordered membership tables;
- atomic package creation from currently RELEASED, exact-version assets;
- PostgreSQL-enforced exact ContentVersion agreement, unique membership, unique positions, non-negative positions, and restricted deletion.

A ContentPackage freezes asset membership IDs and their order. It does not copy asset bodies. Later asset withdrawal may change the dynamic T-030 manifest but does not alter the stored package links.

The system can create a package but has no public API for retrieving a retained package by ID. It has no package list, update, deletion, review, release, publication, file, PDF, delivery, learner, AI, or personalization behavior.

## Exact bounded goal

Add only one read-only internal endpoint:

`GET /api/v1/content-packages/{content_package_id}`

It must return the existing persisted ContentPackage identity and both membership ID lists exactly in their stored association-position order.

Reuse the existing `ContentPackageResponse` schema:

```json
{
  "id": 1,
  "content_version_id": 1,
  "created_at": "stored timestamp",
  "note_draft_ids": [10, 11],
  "question_bank_item_ids": [20, 21]
}
```

Do not return full NoteDraft or QuestionBankItem bodies. Do not recalculate membership from current release state.

## API contract

For an existing package, return HTTP 200 with:

- `id: int`;
- `content_version_id: int`;
- `created_at: datetime`;
- `note_draft_ids: list[int]`;
- `question_bank_item_ids: list[int]`.

The two membership lists must come from persisted association rows ordered by their stored `position`, not by current asset ID, current release status, current approval status, or Python-side resorting.

A package containing only one asset type must return an empty list for the other type.

## Error behavior

For a missing package, return exactly:

- HTTP 404;
- `{"detail": "ContentPackage <id> not found"}`.

Do not introduce a 409 path. Retrieval performs no validation transition and creates no data.

Generic database failures must be re-raised through the established application behavior and must not be mislabeled as missing resources or conflicts.

## Stored-snapshot invariants

Retrieval eligibility depends only on the requested persisted ContentPackage ID.

Therefore:

- retrieve membership even if a linked asset is later WITHDRAWN;
- do not require linked assets to remain RELEASED or APPROVED;
- do not inspect current Claim, Evidence, Verification, PreviousQuestion, priority, NoteDraft, QuestionBankItem, or other package state;
- do not regenerate NoteDraft Markdown, question content, options, answers, or provenance;
- do not rebuild membership from the T-030 manifest or global released collections;
- do not infer a different or latest ContentVersion;
- preserve the stored package ContentVersion ID, creation timestamp, membership IDs, and membership ordering exactly;
- repeated retrievals of an unchanged package must return the same stored response.

PostgreSQL already protects link validity and retained asset references. T-032 must not add synchronization, repair, backfill, or mutation behavior.

## Data-model and migration requirements

No model, relationship, table, column, index, constraint, model-registration, or Alembic migration change is expected.

The approved Alembic head must remain:

`e2c6f8a1d943`

Inspect the current models and migration history. If a persistence change appears necessary, stop and report why instead of expanding T-032.

Do not edit historical migrations.

## Repository requirements

Use or minimally adapt the existing focused ContentPackage retrieval method.

The repository query must:

- select exactly one ContentPackage by ID;
- eagerly load both membership-link collections with a fixed-query strategy;
- preserve each relationship's existing position order;
- return `None` for a missing package;
- acquire no row lock;
- perform no insert, update, delete, flush, commit, refresh-driven mutation, or release-state query.

Avoid obvious N+1 behavior. Retrieval should not load full linked NoteDraft or QuestionBankItem objects because the response needs only persisted membership IDs.

## Service requirements

Add a focused read-only service method that:

1. requests the package from the repository;
2. raises `ResourceNotFoundError("ContentPackage", content_package_id)` when missing;
3. serializes the existing stored package using the shared ContentPackage response serializer;
4. performs no commit, rollback, lock, transition, regeneration, inference, or current-state re-evaluation.

Do not duplicate serializer logic if the T-031 shared serializer is already appropriate.

## Route requirements

Add a thin route for:

`GET /api/v1/content-packages/{content_package_id}`

The route must:

- declare `response_model=ContentPackageResponse`;
- return HTTP 200 on success;
- delegate to the service;
- map only the established missing-resource exception to HTTP 404;
- contain no repository access or business logic.

Register it compatibly with all existing static and dynamic routes. Do not alter any existing route contract or ordering unnecessarily.

## Transaction and atomicity requirements

The endpoint is read-only:

- no `SELECT ... FOR UPDATE`;
- no flush;
- no commit;
- no update or delete;
- no package or membership creation;
- no asset-state transition;
- no regeneration.

A read failure must leave all database row counts and stored package/asset snapshots unchanged.

Existing T-031 package creation locking and atomicity must remain unchanged.

## Required focused tests

Add PostgreSQL-backed focused tests proving:

- an existing package returns HTTP 200 with the exact existing `ContentPackageResponse` contract;
- a missing package returns the exact stable 404;
- packages containing only NoteDraft membership return an empty question-item list;
- packages containing only QuestionBankItem membership return an empty NoteDraft list;
- a package containing both asset types returns both independently position-ordered lists;
- response ID, ContentVersion ID, and creation timestamp match persisted database values;
- each ID list follows stored association `position`, including a database fixture whose stored position order differs from ascending asset ID;
- later withdrawal of a captured NoteDraft does not remove or reorder stored membership;
- later withdrawal of a captured QuestionBankItem does not remove or reorder stored membership;
- allowed post-withdrawal review changes do not affect package retrieval;
- later Claim approval changes do not affect package membership;
- the dynamic T-030 manifest reflects current RELEASED state while T-032 continues returning retained membership;
- unrelated Evidence, Verification, PreviousQuestion, Topic-priority, another ContentVersion, another package, or current global released collections cannot change the returned snapshot;
- repeated retrieval returns the same response;
- retrieval causes no row-count or stored-state mutation;
- eager loading avoids an obvious per-link or per-package N+1 pattern;
- existing package creation behavior and all approval/release/retrieval boundaries remain compatible.

Use direct database fixtures only where needed to prove persisted position ordering. Preserve all approved PostgreSQL constraints and use nested savepoints for any expected integrity failure.

Do not weaken, delete, reorder, or silently skip existing tests.

## Required regression and database validation

Use a dedicated PostgreSQL test database whose name ends in `_test`.

Run and report exact results for:

- the new T-032 ContentPackage retrieval tests;
- existing T-031 ContentPackage creation tests;
- T-030 ContentVersion released-assets tests;
- existing ContentVersion tests;
- existing NoteDraft and released-NoteDraft tests;
- existing QuestionBankItem and released-QuestionBankItem tests;
- the full test suite;
- Ruff on every changed Python file;
- `uv run alembic heads`;
- `uv run alembic check`;
- a fresh database upgrade through `e2c6f8a1d943`;
- `git diff --check`;
- whitespace checking for every untracked file;
- `git status --short`.

Confirm:

- Alembic still reports exactly one head at `e2c6f8a1d943`;
- no migration is created or edited;
- Alembic reports no additional upgrade operations;
- no dependency, configuration, environment, or Docker change occurred.

A migration downgrade/re-upgrade cycle is not required because T-032 must not change persistence. If any schema drift appears, stop and report it.

## Affected components

Inspect and update only where required:

- `app/api/v1/routes/knowledge.py`;
- `app/services/knowledge.py`;
- `app/repositories/knowledge.py` only if the existing retrieval method requires a minimal correction;
- focused ContentPackage retrieval API tests;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md`;
- append-only `docs/next_task.md`.

Inspect but otherwise leave unchanged:

- ContentPackage and membership models;
- model registration;
- `app/schemas/knowledge.py`, because `ContentPackageResponse` already exists;
- every Alembic migration;
- ContentVersion, NoteDraft, QuestionBankItem, Claim, Evidence, Verification, Source, Exam, SyllabusVersion, Topic, PreviousPaper, and PreviousQuestion behavior;
- all existing approval and release endpoints;
- T-030 dynamic manifest behavior;
- T-031 package creation behavior;
- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

## Documentation requirements

Update `docs/architecture.md` and `docs/workflow.md` only for behavior actually implemented.

Append—never rewrite, reorder, consolidate, or delete history:

- a T-032 implementation record in `docs/task_log.md` with status `Ready for review`;
- an implementation note beneath this T-032 prompt in `docs/next_task.md`.

Document clearly that:

- T-031 creation freezes ordered membership;
- T-032 retrieves that retained membership by package ID;
- retrieval does not rebuild membership from current releases;
- later withdrawal changes T-030 but not T-032;
- the response contains membership IDs, not copied or regenerated asset bodies;
- no package list, mutation, lifecycle, publication, PDF, delivery, learner, or AI behavior exists.

Do not mark T-032 approved. Do not define or implement T-033.

## Dependency, configuration, Docker, and API-key review

Explicitly inspect:

- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`.

T-032 requires no external API key, dependency, secret, environment variable, configuration setting, Docker service, storage backend, or infrastructure change.

If any such change appears necessary, stop and report why rather than expanding scope.

## Exclusions and retained boundaries

Do not add:

- package list, update, edit, delete, supersession, clone, or backfill endpoints;
- package approval, release, withdrawal, publication, or delivery lifecycle;
- full embedded NoteDraft or QuestionBankItem bodies in the package response;
- PDF, HTML export, rendering, download, file storage, object storage, CDN, or email;
- public or learner-facing endpoints;
- users, authentication, authorization, reviewer/releaser identity, or history;
- learner copies, practice sessions, attempts, scoring, analytics, recommendations, mock assembly, or personalization;
- AI/LLM providers, API keys, prompts, generation, ingestion, RAG, embeddings, vector columns, or scraping;
- automatic ContentVersion selection or latest-version inference;
- content copying, editing, deletion, regeneration, or synchronization;
- new NoteDraft or QuestionBankItem approval/release transitions;
- PreviousQuestion conversion;
- prediction, probability, likelihood, or guarantee semantics;
- dependencies, configuration, Docker services, payments, or unrelated infrastructure.

A PreviousQuestion remains a sourced historical occurrence and must never be converted into generated content or represented as a prediction.

Preserve trust, provenance, explicit human review, controlled release, exact ContentVersion ownership, immutable ordered package membership, and Generate Once/Personalize Later.

## Final report

Report:

1. exact starting HEAD;
2. files changed and created;
3. endpoint and response contract;
4. missing-package error behavior;
5. stored membership ordering and exact ContentVersion preservation;
6. behavior after asset withdrawal, review changes, and Claim changes;
7. separation from the dynamic T-030 released-assets manifest;
8. eager-loading and no-N+1 behavior;
9. read-only transaction and no-mutation behavior;
10. compatibility with T-031 creation and every existing approval/release/read boundary;
11. focused and full-suite test results;
12. fresh upgrade, Alembic-head/check, and schema-drift results;
13. Ruff and diff/whitespace-check results;
14. dependency, configuration, environment, Docker, AGENTS, and README inspection outcomes;
15. retained architecture boundaries;
16. final `git status --short`;
17. explicit confirmation that no commit, push, PR, self-approval, T-033, package list/mutation/lifecycle, publication, PDF/export, public/learner delivery, AI generation, mock assembly, or personalization work occurred.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-033.

Leave T-032 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-08 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/content-packages/{content_package_id}` through the existing route, service, repository, and `ContentPackageResponse` flow. It retrieves the retained package identity and both membership ID lists in persisted association-position order, returning the established 404 when missing. Retrieval does not rebuild membership from current release or review state; later withdrawal changes T-030's dynamic manifest but not the T-032 snapshot. It performs no locks, writes, transitions, regeneration, or inference. No model, schema, migration, dependency, configuration, Docker, package list/mutation/lifecycle, publication, PDF/export, public/learner delivery, AI, mock assembly, personalization, or T-033 work was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## T-032 independent review outcome

T-032 is **APPROVED** at implementation commit `1a695d8a2335612ff4873df3a3c3bb51543d1591`, whose parent is the T-032 task-issuance commit `94cb1894a40e1736f9af39a41a849d8858965601`.

The immutable implementation adds only `GET /api/v1/content-packages/{content_package_id}` through a thin route and focused service method. It reuses the existing repository's fixed-query eager loading and the shared ContentPackage serializer. Both membership ID lists come from persisted association rows in stored position order; they are not rebuilt from current releases or sorted by asset ID.

Missing packages retain the exact `ContentPackage <id> not found` 404. Later asset withdrawal, permitted review changes, and Claim approval changes do not alter or hide package membership. The T-030 released-assets manifest continues to reflect current RELEASED state independently. Retrieval uses no row locks and performs no write, flush, commit, transition, regeneration, inference, or mutation.

Developer-recorded validation reported 13 complete ContentPackage tests and 201 full-suite tests, each with one existing warning, plus required focused regressions, successful Ruff, a fresh database upgrade, unchanged Alembic head/check, and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed.

No blocking finding remains. No model, schema, repository, migration, dependency, configuration, Docker, package list/mutation/lifecycle, publication, PDF/export, public/learner delivery, AI generation, mock assembly, personalization, or T-033 implementation was included.

---

# T-033 — Add expanded ContentPackage content boundary

## Role

You are the implementation engineer for `Dyuti60/assam-exam-ai`.

Implement only T-033. Follow `AGENTS.md`, the live approved architecture, and the established route → schema → service → repository → PostgreSQL layering.

Before editing:

1. fetch `origin`;
2. fast-forward local `main`;
3. record `git rev-parse HEAD`;
4. confirm local HEAD equals `origin/main`;
5. confirm the working tree is clean;
6. confirm approved T-032 implementation commit `1a695d8a2335612ff4873df3a3c3bb51543d1591` exists in history;
7. read the complete live repository and this prompt.

If the branch, history, synchronization, or working tree is unexpected, stop without changing files.

Do not rely on previous conversation summaries. The live repository is authoritative.

## Current context

The approved system has:

- exact ContentVersion identity for one SyllabusVersion/Topic/version mapping;
- version-owned stored NoteDraft and QuestionBankItem snapshots;
- independent approval and controlled release lifecycles for both asset types;
- global approved/released reads and the dynamic exact-ContentVersion T-030 released-assets manifest;
- immutable ContentPackage identity with two independently position-ordered membership tables;
- atomic package creation from currently RELEASED exact-version assets;
- individual package retrieval returning the retained package identity and ordered membership IDs;
- PostgreSQL-enforced same-ContentVersion membership, uniqueness, position validity, and deletion restrictions.

A package stores membership IDs and positions, not copied content bodies. T-032 exposes those retained IDs. The next internal inspection and rendering prerequisite is to resolve those exact stored members into their existing full stored asset responses while preserving package order.

The system has no package list, membership mutation, package review/release lifecycle, publication, render-ready document, PDF, download, learner, AI, or personalization behavior.

## Exact bounded goal

Add exactly one read-only internal endpoint:

`GET /api/v1/content-packages/{content_package_id}/content`

It must return:

1. the existing retained ContentPackage response;
2. full stored NoteDraft responses for exactly the package's NoteDraft memberships, in persisted NoteDraft membership-position order;
3. full stored QuestionBankItem responses for exactly the package's QuestionBankItem memberships, in persisted QuestionBankItem membership-position order.

Add one composite response schema named `ContentPackageContentResponse`:

```json
{
  "content_package": {
    "id": 1,
    "content_version_id": 1,
    "created_at": "stored timestamp",
    "note_draft_ids": [11, 10],
    "question_bank_item_ids": [21, 20]
  },
  "note_drafts": [
    {
      "id": 11,
      "content_version_id": 1,
      "topic_id": 2,
      "topic_name": "Stored topic",
      "created_at": "stored timestamp",
      "claim_ids": [4, 3],
      "markdown": "stored Markdown",
      "approval_status": "REJECTED",
      "approval_decided_at": "stored timestamp",
      "reviewer_note": "stored note",
      "release_status": "WITHDRAWN",
      "released_at": "stored timestamp",
      "withdrawn_at": "stored timestamp",
      "release_note": "stored release note"
    }
  ],
  "question_bank_items": [
    {
      "id": 21,
      "content_version_id": 1,
      "question_text": "stored question",
      "explanation": "stored explanation",
      "difficulty": "EASY",
      "claim_ids": [4, 3],
      "options": [
        {"position": 0, "option_text": "stored option"}
      ],
      "correct_option_position": 0,
      "created_at": "stored timestamp",
      "approval_status": "REJECTED",
      "approval_decided_at": "stored timestamp",
      "reviewer_note": "stored note",
      "release_status": "WITHDRAWN",
      "released_at": "stored timestamp",
      "withdrawn_at": "stored timestamp",
      "release_note": "stored release note"
    }
  ]
}
```

Use the existing `ContentPackageResponse`, `NoteDraftResponse`, and `QuestionBankItemResponse` schemas as nested field types. Do not duplicate their definitions.

The example statuses illustrate stored-snapshot independence; do not require or force those exact statuses.

## Error behavior

For a missing package, return exactly:

- HTTP 404;
- `{"detail": "ContentPackage <id> not found"}`.

Do not add a 409 path.

Because PostgreSQL restricts deletion of referenced assets, a valid stored package must resolve all membership rows. If an impossible integrity inconsistency is nevertheless detected, raise an internal error rather than silently omitting a member, rebuilding membership, or mislabeling it as a domain conflict.

Generic database failures must be re-raised through established behavior.

## Membership and ordering invariants

Eligibility depends only on persisted package membership.

Therefore:

- include every stored membership even when the linked asset is now WITHDRAWN;
- include every stored membership even when a permitted post-withdrawal review decision is now DRAFT or REJECTED;
- do not require linked assets to remain RELEASED or APPROVED;
- exclude assets that share ContentVersion, Topic, Claims, release state, or other context but are not package members;
- exclude members of another package;
- do not inspect current Claim approval, Evidence, Verification, PreviousQuestion, Topic-priority, global released collections, or the dynamic T-030 manifest for eligibility;
- do not infer latest ContentVersion or rebuild from current releases;
- preserve the package's stored ContentVersion ID and creation timestamp;
- preserve the NoteDraft list in `ContentPackageNoteDraft.position` order;
- preserve the QuestionBankItem list in `ContentPackageQuestionBankItem.position` order;
- preserve each NoteDraft's stored Claim order, Markdown, ContentVersion ownership, Topic, approval metadata, and release metadata;
- preserve each QuestionBankItem's stored Claim order, option order, correct-answer position, ContentVersion ownership, approval metadata, and release metadata;
- repeated reads of unchanged stored rows must return the same response.

Do not copy content into package tables or add automatic synchronization.

## Data-model and migration requirements

No database table, column, index, constraint, model registration, or Alembic migration change is expected.

ORM-only relationship changes are also not expected: repository joins can use the existing package membership models and asset IDs. If a model or persistence change appears necessary, stop and report why rather than expanding scope.

The Alembic head must remain:

`e2c6f8a1d943`

Do not edit any historical migration.

## Repository requirements

Add focused read-only repository queries that:

- retrieve NoteDraft members by joining through `content_package_note_drafts`;
- filter by the exact requested ContentPackage ID;
- order in PostgreSQL by `ContentPackageNoteDraft.position`;
- eagerly load each NoteDraft's Topic and ordered Claim links;
- retrieve QuestionBankItem members by joining through `content_package_question_bank_items`;
- filter by the exact requested ContentPackage ID;
- order in PostgreSQL by `ContentPackageQuestionBankItem.position`;
- eagerly load each QuestionBankItem's ordered Claim links and ordered options;
- return fixed-query collections without per-member relationship queries;
- acquire no row locks;
- perform no insert, update, delete, flush, commit, or refresh-driven mutation.

Do not load global released collections and filter them in Python. Do not use current release or approval predicates.

Continue using the existing T-032 package retrieval method for package identity and membership IDs. Avoid loading unrelated full Claims, Evidence, or Verification bodies because the existing asset responses require only stored Claim IDs.

## Service requirements

Add a focused read-only service method that:

1. loads the exact ContentPackage or raises the established missing-package error;
2. loads full stored members through the position-ordered repository queries;
3. verifies resolved member counts and IDs exactly match the package's retained membership lists;
4. raises an internal error on an impossible mismatch rather than omitting data;
5. reuses the existing package, NoteDraft, and QuestionBankItem stored-response serializers;
6. returns `ContentPackageContentResponse`.

Do not duplicate asset serialization logic.

The service must perform no lock, write, flush, commit, rollback-driven state change, transition, regeneration, current-state eligibility check, or ownership inference.

## Route requirements

Add a thin route for:

`GET /api/v1/content-packages/{content_package_id}/content`

It must:

- declare `response_model=ContentPackageContentResponse`;
- return HTTP 200 on success;
- delegate to the service;
- map only `ResourceNotFoundError` to the established 404;
- contain no repository access, assembly, or business logic.

Register it compatibly with the existing package-ID route. Do not alter any existing route contract.

## Transaction and atomicity requirements

The endpoint is entirely read-only:

- no `SELECT ... FOR UPDATE`;
- no flush;
- no commit;
- no package or membership creation;
- no asset-state transition;
- no regeneration or copied snapshot;
- no automatic repair.

A success, missing-package request, or database failure must leave all database row counts and stored states unchanged.

Existing package creation locking and transaction behavior must remain unchanged.

## Required focused tests

Add PostgreSQL-backed tests proving:

- missing package returns the exact 404 and changes no rows;
- a NoteDraft-only package returns its stored package response, ordered NoteDraft bodies, and an empty QuestionBankItem list;
- a QuestionBankItem-only package returns its stored package response, an empty NoteDraft list, and ordered question bodies;
- a mixed package returns both independently position-ordered asset lists;
- package response membership IDs align exactly with the returned asset IDs;
- database fixtures whose package positions differ from ascending asset IDs are returned strictly by stored membership position;
- non-member assets from the same ContentVersion are excluded;
- members of another package and another ContentVersion are excluded;
- later NoteDraft withdrawal does not remove or reorder it;
- later QuestionBankItem withdrawal does not remove or reorder it;
- permitted post-withdrawal DRAFT/REJECTED review changes do not hide members;
- later Claim approval changes do not alter membership or stored nested Claim order;
- unrelated Evidence, Verification, PreviousQuestion, Topic-priority, released collections, and the T-030 manifest do not affect eligibility;
- stored NoteDraft Topic, ContentVersion, Markdown, Claim order, creation time, approval metadata, and release metadata are preserved;
- stored QuestionBankItem ContentVersion, question text, explanation, difficulty, Claim order, option order, correct answer, creation time, approval metadata, and release metadata are preserved;
- the T-030 manifest dynamically excludes withdrawn assets while T-033 still returns them through retained package membership;
- repeated retrieval returns the same response when stored data is unchanged;
- retrieval performs no writes and leaves package, membership, asset, Claim, Verification, and related row counts unchanged;
- query behavior is fixed with respect to collection size and introduces no obvious per-member N+1;
- no generated SQL contains `FOR UPDATE`;
- existing T-031 creation and T-032 ID-only retrieval remain compatible.

Do not weaken, delete, reorder, or silently skip existing tests.

## Required regression and database validation

Use a dedicated PostgreSQL test database whose name ends in `_test`.

Run and report exact results for:

- new T-033 expanded-content tests;
- the complete ContentPackage test suite;
- T-030 ContentVersion released-assets tests;
- existing ContentVersion tests;
- existing NoteDraft and released-NoteDraft tests;
- existing QuestionBankItem and released-QuestionBankItem tests;
- the full test suite;
- Ruff on every changed Python file;
- `uv run alembic heads`;
- `uv run alembic check`;
- a fresh database upgrade through `e2c6f8a1d943`;
- `git diff --check`;
- whitespace checking for every untracked file;
- `git status --short`.

Confirm:

- Alembic still reports exactly one head at `e2c6f8a1d943`;
- no migration is created or edited;
- Alembic reports no additional upgrade operations;
- no dependency, configuration, environment, Docker, or API-key change occurred.

A downgrade/re-upgrade cycle is not required because T-033 must not change persistence.

## Affected components

Inspect and update only where required:

- `app/schemas/knowledge.py`;
- `app/repositories/knowledge.py`;
- `app/services/knowledge.py`;
- `app/api/v1/routes/knowledge.py`;
- focused ContentPackage expanded-content tests;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md`;
- append-only `docs/next_task.md`.

Inspect but otherwise leave unchanged:

- ContentPackage and membership models;
- model registration;
- every Alembic migration;
- ContentVersion, NoteDraft, QuestionBankItem, Claim, Evidence, Verification, Source, Exam, SyllabusVersion, Topic, PreviousPaper, and PreviousQuestion models and behavior;
- every existing approval and release endpoint;
- T-030 dynamic manifest;
- T-031 package creation;
- T-032 ID-only package retrieval;
- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

## Documentation requirements

Update `docs/architecture.md` and `docs/workflow.md` only for behavior actually implemented.

Append—never rewrite, reorder, consolidate, or delete history:

- a T-033 implementation record in `docs/task_log.md` with status `Ready for review`;
- an implementation note beneath this T-033 prompt in `docs/next_task.md`.

Document clearly that:

- T-032 returns retained membership IDs;
- T-033 expands only those exact members into existing stored asset responses;
- membership position determines top-level asset order;
- nested Claim and option positions remain stored;
- later asset withdrawal affects T-030 but not T-033;
- no content is copied, regenerated, or re-evaluated;
- no package list, mutation, lifecycle, publication, rendering, PDF, delivery, learner, or AI behavior exists.

Do not mark T-033 approved. Do not define or implement T-034.

## Dependency, configuration, Docker, and API-key review

Explicitly inspect:

- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`.

T-033 requires no external API key, dependency, secret, environment variable, configuration setting, Docker service, storage backend, or infrastructure change.

If any such change appears necessary, stop and report why instead of expanding scope.

## Exclusions and retained boundaries

Do not add:

- package list, update, edit, delete, reorder, supersession, clone, or backfill endpoints;
- package approval, release, withdrawal, publication, or delivery lifecycle;
- render-ready document models;
- PDF, HTML export, rendering, download, file storage, object storage, CDN, or email;
- public or learner-facing endpoints;
- users, authentication, authorization, reviewer/releaser identity, or decision history;
- learner copies, practice sessions, attempts, scoring, analytics, recommendations, mock assembly, or personalization;
- AI/LLM providers, API keys, prompts, generation, source discovery, ingestion, RAG, embeddings, vector columns, or scraping;
- automatic ContentVersion selection or latest-version inference;
- content copying, editing, deletion, regeneration, or synchronization;
- new NoteDraft or QuestionBankItem approval/release transitions;
- PreviousQuestion conversion;
- prediction, probability, likelihood, or guarantee semantics;
- dependencies, configuration, Docker services, payments, or unrelated infrastructure.

A PreviousQuestion remains a sourced historical occurrence and must never be converted into generated content or represented as a prediction.

Preserve trust, provenance, explicit human review, controlled release, exact ContentVersion ownership, immutable ordered package membership, and Generate Once/Personalize Later.

## Final report

Report:

1. exact starting HEAD;
2. files changed and created;
3. endpoint and composite response contract;
4. missing-package and impossible-integrity behavior;
5. package-membership ordering and exact-member selection;
6. nested NoteDraft and QuestionBankItem stored-snapshot preservation;
7. behavior after withdrawal, review changes, and Claim changes;
8. separation from the dynamic T-030 released-assets manifest;
9. eager loading and no-N+1 behavior;
10. read-only transaction and no-mutation behavior;
11. compatibility with T-031 creation, T-032 retrieval, and all existing approval/release/read boundaries;
12. focused and full-suite test results;
13. fresh upgrade, Alembic-head/check, and schema-drift results;
14. Ruff and diff/whitespace-check results;
15. dependency, configuration, environment, Docker, AGENTS, and README inspection outcomes;
16. retained architecture boundaries;
17. final `git status --short`;
18. explicit confirmation that no commit, push, PR, self-approval, T-034, package list/mutation/lifecycle, publication, rendering, PDF/export, public/learner delivery, AI generation, source discovery, mock assembly, or personalization work occurred.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-034.

Leave T-033 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-08 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/content-packages/{content_package_id}/content` through a composite response schema, thin route, read-only service assembly, and exact-package membership joins. It expands precisely the retained, position-ordered membership IDs into existing stored NoteDraft and QuestionBankItem responses, verifies complete resolution, and preserves nested Claim/option ordering. Withdrawal or later review/Claim changes do not hide members; T-030 remains the separate dynamic current-release manifest. The endpoint performs no locks, writes, transitions, copying, regeneration, inference, or current-state eligibility evaluation. No model, migration, dependency, configuration, Docker, package list/mutation/lifecycle, publication, rendering, PDF/export, public/learner delivery, AI, source discovery, mock assembly, personalization, or T-034 work was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## T-033 independent review outcome

T-033 is **APPROVED** at implementation commit `673b4ae62c4d2dd102986f3144ed8e30dea9116f`, whose parent is the T-033 task-issuance commit `23539a56f397202480e76aee42a0ade99424ddce`.

The immutable T-033 diff adds only `GET /api/v1/content-packages/{content_package_id}/content` through the expected route, composite response schema, service, repository queries, focused tests, and documentation. It expands precisely the package's two retained, position-ordered membership lists into the existing stored NoteDraft and QuestionBankItem response shapes. The repository joins through each association table, filters by exact package ID, orders by association position, and eagerly loads required nested relationships. The service rejects incomplete resolution internally instead of silently omitting or rebuilding members.

Later withdrawal, permitted post-withdrawal review changes, and Claim decisions do not alter the retained package view; T-030 remains the independent dynamic current-release manifest. The endpoint performs no locks, writes, flushes, commits, transitions, copying, regeneration, inference, repair, or current-state eligibility evaluation.

Developer-recorded validation reported 4 focused T-033 tests, 17 complete ContentPackage tests, and 205 full-suite tests, each with one existing warning, plus the required focused regressions, successful Ruff, a fresh database upgrade, unchanged Alembic head/check, and diff checks. GitHub exposes no status contexts or workflow runs for the implementation commit, so no CI pass is claimed.

No blocking finding remains. No model, relationship, migration, dependency, configuration, Docker, package list/mutation/lifecycle, publication, rendering, PDF/export, public/learner delivery, AI, source discovery, mock assembly, personalization, or T-034 implementation was included.

---

# T-034 — Add independent ContentPackage human-review lifecycle

## Role

You are the implementation engineer for `Dyuti60/assam-exam-ai`.

Implement only T-034. Follow `AGENTS.md`, the live approved architecture, and the established route → schema → service → repository → PostgreSQL layering.

Before editing:

1. fetch `origin` and fast-forward local `main`;
2. record `git rev-parse HEAD` and confirm it equals `origin/main`;
3. confirm the working tree is clean;
4. confirm approved T-033 commit `673b4ae62c4d2dd102986f3144ed8e30dea9116f` and the documentation commit that issued this task exist in history;
5. read the complete live repository and this prompt.

If branch, history, synchronization, or working tree is unexpected, stop without changing files. The live repository is authoritative.

## Current context and bounded goal

The approved system has exact ContentVersion identity; version-owned NoteDraft and QuestionBankItem snapshots with independent review and release; dynamic released-asset reads; immutable ContentPackage identities and ordered memberships; package creation; ID-only package retrieval; and exact-member expanded-content retrieval.

Add only an independent human-review lifecycle to ContentPackage itself:

- `DRAFT`
- `APPROVED`
- `REJECTED`

Every existing and new package begins DRAFT with no decision timestamp or reviewer note.

Add exactly one endpoint:

`POST /api/v1/content-packages/{content_package_id}/approval`

It records or resets only the target package's review decision. It must not inspect or change members, membership, Claims, Verification, priority, the T-030 manifest, or another package. Approval is not release, publication, rendering, export, download, or learner delivery.

## API contract

Add `ContentPackageApprovalCreate`:

- `approval_status`: DRAFT, APPROVED, or REJECTED only;
- `reviewer_note`: optional string or null.

Extend the existing `ContentPackageResponse` with stored:

- `approval_status`;
- `approval_decided_at`;
- `reviewer_note`.

Return those fields consistently from package creation, ID-only retrieval, the nested package object in expanded-content retrieval, and the new approval endpoint. Do not duplicate package response schemas.

Semantics:

- APPROVED and REJECTED record the requested state, current UTC decision timestamp, and optional note;
- DRAFT clears decision timestamp and reviewer note;
- decisions never change package identity, ContentVersion, creation time, membership IDs, association positions, or any member;
- missing package returns HTTP 404 with `{"detail": "ContentPackage <id> not found"}`;
- invalid or missing decisions return normal HTTP 422;
- add no unrelated 404/409 behavior;
- rollback and re-raise generic database exceptions rather than translating them to domain conflicts.

## Persistence and migration

Extend `ContentPackage` with exactly:

- `approval_status`: non-null string, default DRAFT;
- `approval_decided_at`: nullable timezone-aware timestamp;
- `reviewer_note`: nullable text.

PostgreSQL and model metadata must enforce:

1. status is exactly DRAFT, APPROVED, or REJECTED;
2. DRAFT has null decision timestamp and null reviewer note;
3. APPROVED/REJECTED have a non-null decision timestamp, with optional reviewer note.

Create exactly one Alembic revision whose parent is `e2c6f8a1d943`. It adds only these fields and constraints, migrates all existing packages to DRAFT/null without inference, preserves all packages, memberships, ordering, assets, ContentVersions, timestamps, and provenance, and edits no historical migration. Keep defaults aligned with model metadata and `alembic check`.

Downgrade drops only T-034 constraints and fields, leaving every pre-T-034 object and row intact.

Validate a seeded cycle:

`e2c6f8a1d943 → T-034 head → e2c6f8a1d943 → T-034 head`.

Prove seeded packages and both membership types retain IDs, ContentVersion, creation time, member IDs, and positions; every upgrade produces DRAFT/null review state with no inference.

Do not add reviewer identity, decision history, audit tables, package release/publication fields, labels, names, version numbers, files, checksums, or user ownership.

## Repository, service, locking, and atomicity

Approval must:

- load only the target ContentPackage with `SELECT ... FOR UPDATE`;
- not lock or rewrite members or memberships;
- update only the three review fields;
- commit exactly once on success;
- roll back the session on persistence failure;
- freshly retrieve and return the stored package response;
- preserve both membership lists in association-position order.

Ordinary package retrieval and expanded-content retrieval remain lock-free and read-only.

Package review is independent of member approval/release, later member withdrawal/review changes, Claim/Verification/priority state, T-030 results, other ContentVersions, and other packages.

## Required tests

Add PostgreSQL-backed tests proving:

- new and migrated packages default to DRAFT with null timestamp/note and no inferred approval;
- creation, ID-only retrieval, expanded-content retrieval, and decision responses expose the same stored review metadata;
- APPROVED and REJECTED record exact UTC-offset timestamps and optional notes;
- DRAFT reset clears timestamp and note;
- repeated valid decisions preserve identity, ContentVersion, creation time, membership IDs, and positions;
- review changes no package membership, asset, Claim, Verification, or related row counts;
- member withdrawal and permitted member review changes do not block package decisions;
- unrelated state cannot substitute for or alter the target package's decision;
- missing package returns the exact 404 without mutation;
- missing/invalid/unsupported decisions return 422;
- PostgreSQL rejects invalid status, DRAFT with timestamp or note, and APPROVED/REJECTED without timestamp;
- injected persistence failure rolls back and leaves the package unchanged;
- approval SQL contains FOR UPDATE on the package row;
- normal retrieval and expanded-content SQL contain no FOR UPDATE;
- T-030 through T-033 and all existing member approval/release/read behavior remain compatible.

Do not weaken, delete, reorder, or silently skip existing tests.

## Required validation

Use a dedicated PostgreSQL database ending in `_test`. Run and report exact results for:

- focused T-034 and complete ContentPackage tests;
- T-030 released-assets, ContentVersion, NoteDraft, released-NoteDraft, QuestionBankItem, and released-QuestionBankItem suites;
- the full suite;
- Ruff on every changed Python file;
- `uv run alembic heads` and `uv run alembic check`;
- fresh upgrade through the new head;
- seeded upgrade/downgrade/re-upgrade;
- direct PostgreSQL constraint probes;
- `git diff --check`, whitespace checks for untracked files, and `git status --short`.

Confirm one Alembic head whose parent is `e2c6f8a1d943`, no schema drift, no historical migration edits, and no dependency/configuration/environment/Docker/API-key/infrastructure change.

## Affected components

Update only where required:

- `app/models/content_package.py`;
- model registration only if the existing import structure requires it;
- `app/schemas/knowledge.py`;
- `app/repositories/knowledge.py`;
- `app/services/knowledge.py`;
- `app/api/v1/routes/knowledge.py`;
- exactly one new Alembic migration;
- focused ContentPackage tests;
- `docs/architecture.md` and `docs/workflow.md`;
- append-only `docs/task_log.md` and `docs/next_task.md`.

Inspect but otherwise leave unchanged: membership models/relationships; all other domain models and historical migrations; all existing approval/release endpoints; T-030 through T-033 behavior; `pyproject.toml`; `uv.lock`; `.env.example`; `app/core/config.py`; `docker-compose.yml`; `AGENTS.md`; and `README.md`.

## Documentation requirements

Document only implemented behavior. Keep task log and next-task history append-only. Add a T-034 implementation record with status `Ready for review` and an implementation note below this prompt.

State clearly that package review is independent of member review/release, cannot alter immutable membership, uses DRAFT-reset semantics, and is not release/publication/rendering/export/delivery. No approved-package or released-package collection exists.

Do not mark T-034 approved. Do not define or implement T-035.

## Dependency and scope gate

T-034 requires no API key, external service, dependency, secret, environment variable, configuration, Docker service, storage backend, or infrastructure change. If any appears necessary, stop and report why.

Do not add package lists; package release/withdrawal/publication/delivery; mutation, reorder, rebuild, clone, deletion, or backfill; rendered documents, HTML, PDF, export, download, files, object storage, CDN, or email; public/learner endpoints; users/auth/reviewer identity/history; learner sessions, scoring, analytics, recommendations, mocks, or personalization; AI/LLM providers, keys, prompts, generation, source discovery, ingestion, RAG, embeddings, vectors, or scraping; automatic version inference; content copying/regeneration; new member transitions; PreviousQuestion conversion; predictions; dependencies; configuration; Docker services; payments; or unrelated infrastructure.

Preserve trust, provenance, explicit human review, controlled member release, exact ContentVersion ownership, immutable ordered package membership, and Generate Once/Personalize Later.

## Final report

Report exact starting HEAD; changed/created files; migration revision/parent; model constraints; request/response contracts; decision/reset/errors; locking/transaction/rollback; immutable ordering; state independence; compatibility; focused/full tests; fresh and seeded migration results; PostgreSQL probes; Alembic/Ruff/diff results; dependency/config/Docker inspection; retained boundaries; final status; and explicit confirmation of no commit, push, PR, self-approval, T-035, package release/list/mutation, publication, rendering, PDF/export, delivery, AI, source discovery, mock assembly, or personalization.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-035.

Leave T-034 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-09 Asia/Kolkata, UTC+05:30): added independent DRAFT/APPROVED/REJECTED human review to ContentPackage through migration `f7b3d1a8c529` and exactly `POST /api/v1/content-packages/{content_package_id}/approval`. Existing and new packages begin DRAFT with null decision metadata. APPROVED and REJECTED record the current UTC decision time and optional note; DRAFT clears both. The decision locks and changes only the target package review fields, commits once, and preserves immutable ordered membership and every member. Package creation, ID-only retrieval, and expanded-content retrieval now expose the same stored review metadata. T-034 is Ready for review, not approved. No package release/list, publication, rendering, PDF/export, delivery, learner, AI, source discovery, mock assembly, personalization, or T-035 behavior was added.


---

## T-034 independent review outcome

T-034 is **APPROVED** at implementation commit `8bdd96a1931be638ad4c5a40ab22a34382e66812`, whose parent is the T-034 task-issuance commit `bf65890e89752624c93e9cfd355240dea6499fc9`.

The immutable diff adds only independent ContentPackage DRAFT/APPROVED/REJECTED review fields, migration `f7b3d1a8c529`, response compatibility, row-locked review persistence, one approval endpoint, focused tests, and accurate documentation. PostgreSQL constrains valid state/metadata combinations. Existing packages become DRAFT with null decision metadata and no inferred approval.

The approval path locks only the target package, updates only its three review fields, commits once, rolls back persistence errors, freshly retrieves stored ordered membership, and remains independent of member, Claim, Verification, priority, T-030, other package, and other ContentVersion state. Package creation, ID-only retrieval, and expanded-content retrieval consistently expose the stored review metadata and remain otherwise compatible.

Developer-recorded validation reported 5 focused T-034 tests, 22 complete ContentPackage tests, and 210 full-suite tests, each with one existing warning, plus required focused regressions, Ruff, fresh and seeded migration upgrade/downgrade/re-upgrade, PostgreSQL probes, Alembic head/check, and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed.

No blocking finding remains. No approved/released package collection, package release, publication, rendering, PDF/export, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-035 implementation was included.

---

# T-035 — Add controlled ContentPackage release lifecycle

## Role and synchronization gate

You are the implementation engineer for `Dyuti60/assam-exam-ai`. Implement only T-035 using the live repository, `AGENTS.md`, and the established route → schema → service → repository → PostgreSQL layering.

Before editing:

1. fetch `origin` and fast-forward local `main`;
2. record `git rev-parse HEAD` and confirm it equals `origin/main`;
3. confirm the working tree is clean;
4. confirm approved T-034 commit `8bdd96a1931be638ad4c5a40ab22a34382e66812` and the documentation commit issuing T-035 exist in history;
5. read the complete live repository and this prompt.

Stop without changing files if synchronization, history, branch, or working tree is unexpected. The live repository is authoritative.

## Current context and exact goal

ContentPackage already retains immutable ordered membership under one exact ContentVersion and has independent DRAFT/APPROVED/REJECTED review.

Add only its controlled release lifecycle:

- `UNRELEASED`
- `RELEASED`
- `WITHDRAWN`

Every existing and new package starts UNRELEASED with null release metadata. Approval must never imply release.

Add exactly:

`POST /api/v1/content-packages/{content_package_id}/release`

It accepts an explicit RELEASED or WITHDRAWN decision and optional release note. Do not add a released-package collection; that is a later task.

## API and response contract

Add:

- `ContentPackageReleaseStatus` for persisted UNRELEASED/RELEASED/WITHDRAWN state;
- `ContentPackageReleaseDecision` permitting only RELEASED/WITHDRAWN requests;
- `ContentPackageReleaseCreate` with required `release_status` and optional `release_note`.

Extend the shared `ContentPackageResponse` with:

- `release_status`;
- `released_at`;
- `withdrawn_at`;
- `release_note`.

Package creation, ID retrieval, expanded-content retrieval, approval responses, and release responses must expose identical stored release metadata without duplicating schemas.

Missing package returns HTTP 404 with `{"detail": "ContentPackage <id> not found"}`. Missing/invalid/UNRELEASED decisions return normal 422.

Use deterministic 409 details for rejected transitions and eligibility failures. At minimum:

- `ContentPackage <id> must be approved before release`;
- `ContentPackage <id> has no retained members to release`;
- `ContentPackage <id> cannot transition from <CURRENT> to <REQUESTED>`;
- `ContentPackage <id> must be withdrawn before changing approval`.

Do not mutate on 404, 409, or 422. Generic persistence exceptions must roll back and be re-raised, not mislabeled as conflicts.

## Transition and eligibility semantics

Allow only:

1. UNRELEASED → RELEASED;
2. RELEASED → WITHDRAWN.

UNRELEASED → RELEASED requires:

- the package's own `approval_status == APPROVED`;
- at least one retained NoteDraft or QuestionBankItem membership link.

Eligibility depends only on the package's stored review and retained membership. Do not re-evaluate current member approval/release, Claims, Verification, Topic priority, T-030 manifest, another package, or another ContentVersion.

On release:

- set RELEASED;
- record current UTC `released_at`;
- keep `withdrawn_at` null;
- store the optional release note.

On withdrawal:

- set WITHDRAWN;
- preserve the original `released_at`;
- record current UTC `withdrawn_at`;
- replace `release_note` with the withdrawal note.

Reject without mutation:

- UNRELEASED → WITHDRAWN;
- RELEASED → RELEASED;
- WITHDRAWN → WITHDRAWN;
- WITHDRAWN → RELEASED.

A withdrawn package cannot be re-released in place.

While RELEASED, DRAFT or REJECTED package-review decisions return 409 and do not mutate. After withdrawal, review decisions work again and preserve all release metadata. Approval and release remain independent.

## Persistence and PostgreSQL invariants

Extend `ContentPackage` with exactly:

- `release_status`: non-null string, default UNRELEASED;
- `released_at`: nullable timezone-aware timestamp;
- `withdrawn_at`: nullable timezone-aware timestamp;
- `release_note`: nullable text.

Model and database constraints must enforce:

1. release status is exactly UNRELEASED, RELEASED, or WITHDRAWN;
2. UNRELEASED has null released_at, withdrawn_at, and release_note;
3. RELEASED has non-null released_at, null withdrawn_at, and APPROVED package review;
4. WITHDRAWN has non-null released_at and withdrawn_at.

Cross-table non-empty membership cannot be encoded by a simple check constraint; enforce it transactionally in the service. Do not add triggers.

Create exactly one Alembic revision whose parent is `f7b3d1a8c529`. It adds only these fields and constraints, migrates existing packages to UNRELEASED/null without inference, preserves all review/membership/content/provenance data, and edits no historical migration. Keep defaults aligned with model metadata and `alembic check`.

Downgrade removes only T-035 constraints and columns, preserving every pre-T-035 package, review decision, membership, ordering, asset, ContentVersion, timestamp, and provenance row.

Validate a seeded cycle:

`f7b3d1a8c529 → T-035 head → f7b3d1a8c529 → T-035 head`.

Prove package review, membership IDs/positions, identity, ContentVersion, and creation time survive; each upgrade yields UNRELEASED/null with no inferred release.

## Locking, transactions, and repository behavior

Both package release and potentially conflicting package approval decisions must load the package using `SELECT ... FOR UPDATE` on the package row.

Do not lock or rewrite member assets. Membership links may be loaded to check non-empty retained membership but must not be mutated.

Release must:

- validate before field mutation;
- update only package release fields;
- commit exactly once;
- roll back the session on persistence failure;
- freshly retrieve and return the stored shared package response.

Ordinary ID-only and expanded-content reads remain lock-free.

## Required tests

Add PostgreSQL-backed tests proving:

- new and migrated packages default UNRELEASED with null release metadata;
- package approval does not imply release;
- all package response boundaries expose consistent stored release metadata;
- DRAFT and REJECTED packages cannot release and remain unchanged;
- an approved package with retained members can release even if members were later withdrawn or review-changed;
- Claims, Verification, priority, T-030, other packages, and member states cannot substitute for package approval;
- a directly seeded empty approved package receives the stable no-members 409 without mutation;
- successful release records exact UTC offset, optional note, and preserves identity/review/membership/order;
- withdrawal preserves released_at, records exact UTC withdrawn_at, and replaces the note;
- all invalid transitions return deterministic 409 with no mutation;
- WITHDRAWN cannot be re-released;
- RELEASED blocks DRAFT/REJECTED package review until withdrawal;
- post-withdrawal review changes preserve release metadata;
- missing package returns exact 404;
- missing/invalid/UNRELEASED requests return 422;
- PostgreSQL rejects invalid release status and every invalid timestamp/note/review combination;
- persistence failure rolls back and leaves the package unchanged;
- release and approval SQL lock only the package row;
- ordinary retrieval and expanded content remain lock-free;
- all T-030 through T-034 and member review/release behavior remain compatible.

Use exact UTC offset assertions. Do not weaken, delete, reorder, or silently skip existing tests.

## Required validation

Use dedicated PostgreSQL databases ending in `_test`. Run and report:

- focused T-035 and complete ContentPackage tests;
- T-030 released-assets and ContentVersion tests;
- NoteDraft/released-NoteDraft tests;
- QuestionBankItem/released-QuestionBankItem tests;
- full suite;
- Ruff on all changed Python;
- `uv run alembic heads` and `uv run alembic check`;
- fresh upgrade;
- seeded upgrade/downgrade/re-upgrade;
- direct PostgreSQL constraint probes;
- `git diff --check`, untracked-file whitespace checks, and final `git status --short`.

Confirm one head whose parent is `f7b3d1a8c529`, no schema drift or historical migration edits, and no dependency/config/environment/Docker/API-key/infrastructure change.

## Affected components

Update only where required: `app/models/content_package.py`; shared schemas; repository; service; knowledge routes; exactly one new migration; focused ContentPackage tests; architecture/workflow; append-only task log and next task.

Inspect but otherwise leave unchanged: membership models; other domain models and historical migrations; T-030 through T-034 behavior; `pyproject.toml`; `uv.lock`; `.env.example`; `app/core/config.py`; `docker-compose.yml`; `AGENTS.md`; `README.md`.

## Documentation and scope gate

Document only implemented behavior. Keep `docs/task_log.md` and `docs/next_task.md` append-only. Record T-035 only as `Ready for review` and do not define or implement T-036.

State explicitly that package release does not publish, render, export, deliver, or expose a released-package collection.

T-035 needs no external API key, dependency, secret, environment variable, configuration, Docker service, storage backend, or infrastructure change. Stop and report if one appears necessary.

Do not add package list/released collection; publication transport; rendering, HTML, PDF, export, files, storage, CDN, email; public/learner APIs; users/auth/reviewer/releaser identity/history; membership mutation/rebuild/reorder; package clone/delete/backfill; learner sessions/scoring/analytics/recommendations/mocks/personalization; AI/LLM providers, keys, prompts, source discovery, ingestion, RAG, embeddings, vectors, scraping; automatic version inference; content regeneration; new member transitions; PreviousQuestion conversion; predictions; dependencies; configuration; Docker services; payments; or unrelated infrastructure.

Preserve trust, provenance, explicit human review, controlled release, exact ContentVersion ownership, immutable ordered membership, and Generate Once/Personalize Later.

## Final report and handoff

Report starting HEAD; changed/created files; migration revision/parent; fields/constraints; request/response; transitions/errors; empty-membership behavior; locking/rollback; immutable membership/state independence; compatibility; focused/full tests; migration cycles/probes; Alembic/Ruff/diff; dependency/config inspection; retained boundaries; final status; and explicit confirmation of no commit, push, PR, self-approval, T-036, released-package collection, publication, rendering, PDF/export, delivery, AI, source discovery, mock assembly, or personalization.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-036.

Leave T-035 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-09 Asia/Kolkata, UTC+05:30): added only the controlled ContentPackage UNRELEASED/RELEASED/WITHDRAWN lifecycle through migration `a8c4e2f9b671` and `POST /api/v1/content-packages/{content_package_id}/release`. Existing and new packages begin UNRELEASED with null release metadata. Release requires the package's own APPROVED review plus retained membership, records UTC release time and an optional note, and never re-evaluates member state. Withdrawal preserves release time, records UTC withdrawal time, replaces the note, and prevents in-place re-release. Release and conflicting approval decisions lock only the package row; immutable membership remains unchanged. T-035 is Ready for review, not approved. No released-package collection, publication, rendering, PDF/export, delivery, learner, AI, source discovery, mock assembly, personalization, or T-036 behavior was added.


---

## T-035 independent review outcome

T-035 is **APPROVED** at implementation commit `632fb01e6566d3270ef82c0a47788e8eabeac229`, whose parent is the T-035 task-issuance commit `e2cef231108f8285365277ee35387a704c9f57c3`.

The immutable diff adds only ContentPackage UNRELEASED/RELEASED/WITHDRAWN persistence, migration `a8c4e2f9b671`, response metadata, row-locked approval/release decisions, one release endpoint, focused tests, and accurate documentation. Release requires the target package's own APPROVED review plus at least one retained member. Member and external state are not re-evaluated or locked.

The one-way lifecycle permits only UNRELEASED → RELEASED → WITHDRAWN. Withdrawal retains the original release timestamp and prevents in-place re-release. A currently RELEASED package blocks DRAFT/REJECTED review changes until withdrawal. PostgreSQL enforces status, metadata, and approval invariants. Existing packages migrate to UNRELEASED/null without inferred release, and the seeded downgrade/re-upgrade evidence preserves review, identity, ContentVersion, creation time, and both ordered memberships.

Developer-recorded validation reported 5 focused T-035 tests, 27 complete ContentPackage tests, 112 combined regressions, and 215 full-suite tests, each with one existing warning, plus Ruff, fresh and seeded migration cycles, PostgreSQL probes, Alembic head/check, and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed.

No blocking finding remains. No released-package collection, publication, rendering, PDF/export, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-036 implementation was included.

---

# T-036 — Add released ContentPackage read boundary

## Role and synchronization

You are the implementation engineer for `Dyuti60/assam-exam-ai`. Implement only T-036 using the live repository, `AGENTS.md`, and the established route → schema → service → repository → PostgreSQL layering.

Before editing:

1. fetch `origin` and fast-forward local `main`;
2. record `git rev-parse HEAD` and confirm it equals `origin/main`;
3. confirm the working tree is clean;
4. confirm approved T-035 commit `632fb01e6566d3270ef82c0a47788e8eabeac229` and the documentation commit issuing T-036 exist in history;
5. read the complete live repository and this prompt.

Stop without changing files if branch, synchronization, history, or working tree is unexpected. The live repository is authoritative.

## Current context and bounded goal

ContentPackage now has immutable, independently ordered exact-ContentVersion memberships; ID-only and expanded-content retrieval; independent human review; and controlled release/withdrawal.

Add exactly one endpoint:

`GET /api/v1/content-packages/released`

It returns a JSON list of existing `ContentPackageResponse` objects for packages whose current persisted `release_status` is exactly `RELEASED`.

This is an internal read boundary only. It is not publication, distribution, rendering, export, download, or learner delivery.

## Eligibility, ordering, and response

Eligibility is exactly:

`ContentPackage.release_status == "RELEASED"`

Therefore:

- exclude every UNRELEASED package, including APPROVED ones;
- exclude every WITHDRAWN package, including APPROVED ones;
- include every currently RELEASED package;
- do not independently filter by approval_status because PostgreSQL already requires RELEASED packages to remain APPROVED;
- do not inspect current member approval/release, Claims, Verification, priority, T-030 manifest, ContentVersion recency, other package state, or any external state.

Return packages ordered by ascending ContentPackage ID.

Return HTTP 200 with `[]` when no package qualifies, including an empty database.

Each item must use the existing shared `ContentPackageResponse` and preserve:

- package ID;
- exact ContentVersion ID;
- creation timestamp;
- NoteDraft member IDs in stored association-position order;
- QuestionBankItem member IDs in stored association-position order;
- approval status, timestamp, and reviewer note;
- release status, release timestamp, withdrawal timestamp, and release note.

Do not expand full member bodies in this endpoint. T-033 remains the explicit individual expanded-content boundary.

## Route safety and layering

Register the static `/content-packages/released` route before the dynamic `/content-packages/{content_package_id}` route so `released` is never parsed as an ID.

Implement through:

- one thin FastAPI route;
- one service method;
- one repository method.

The repository must:

- filter exactly on RELEASED in PostgreSQL;
- order by ContentPackage ID in PostgreSQL;
- eagerly load both ordered membership-link collections using a fixed-query strategy;
- avoid per-package membership N+1 queries;
- perform no `FOR UPDATE`.

The service must reuse the existing stored package serializer and add no mutation or eligibility inference.

## Read-only and compatibility requirements

The request must perform no:

- inserts, updates, deletes, flushes, commits, refresh mutation, or transitions;
- row locks;
- membership rebuilding, sorting by asset ID, synchronization, or repair;
- full member-body loading;
- regeneration, copying, AI, or current-state re-evaluation.

Membership order is the persisted association-position order, even if it differs from ascending member IDs.

Later member withdrawal, member review changes, or Claim decisions must not affect package eligibility or returned membership. Only the package's own current RELEASED state controls inclusion.

Withdrawing a package must remove it from this collection without deleting or changing it. A different approved UNRELEASED package remains excluded.

Existing T-030 dynamic assets, T-031 creation, T-032 ID retrieval, T-033 content expansion, T-034 review, and T-035 transitions must remain unchanged.

## Required tests

Add PostgreSQL-backed focused tests proving:

- empty database returns HTTP 200 and `[]`;
- a database containing only ineligible packages returns `[]`;
- DRAFT UNRELEASED, APPROVED UNRELEASED, REJECTED UNRELEASED, and APPROVED WITHDRAWN packages are excluded;
- multiple RELEASED packages are returned in ascending package-ID order;
- each response exactly preserves stored review and release metadata;
- both membership ID lists retain stored association-position order, including fixtures whose positions differ from asset ID order;
- packages containing only one asset type remain valid and serialize the other list empty;
- member withdrawal and permitted post-withdrawal member review changes do not remove the package or change membership;
- Claim, Verification, priority, T-030, another package, another ContentVersion, and global member collections do not determine package eligibility;
- withdrawing one package removes only that package from the collection;
- repeated reads return identical responses when stored state is unchanged;
- read leaves package, membership, assets, Claims, Verification, and related row counts unchanged;
- query count is fixed with respect to package count and introduces no obvious membership N+1;
- generated SQL contains no `FOR UPDATE`;
- static route precedence is correct;
- existing T-031 through T-035 package behavior remains compatible.

Do not weaken, delete, reorder, or silently skip existing tests.

## Validation

Use a dedicated PostgreSQL database ending in `_test`. Run and report exact results for:

- focused T-036 tests;
- complete ContentPackage tests;
- T-030 released-assets and ContentVersion tests;
- NoteDraft/released-NoteDraft tests;
- QuestionBankItem/released-QuestionBankItem tests;
- full suite;
- Ruff on every changed Python file;
- `uv run alembic heads`;
- `uv run alembic check`;
- fresh upgrade through `a8c4e2f9b671`;
- `git diff --check`;
- whitespace checks for untracked files;
- final `git status --short`.

Confirm Alembic remains exactly one head at `a8c4e2f9b671`, no migration/schema change, and no dependency/config/environment/Docker/API-key/infrastructure change. A downgrade/re-upgrade cycle is not required because T-036 changes no persistence.

## Affected components

Update only where required:

- `app/repositories/knowledge.py`;
- `app/services/knowledge.py`;
- `app/api/v1/routes/knowledge.py`;
- focused released-ContentPackage tests;
- `docs/architecture.md`;
- `docs/workflow.md`;
- append-only `docs/task_log.md`;
- append-only `docs/next_task.md`.

Inspect but leave unchanged:

- all schemas;
- ContentPackage and membership models;
- model registration;
- every migration;
- every other domain model;
- existing approval/release/create/read/content routes;
- `pyproject.toml`, `uv.lock`, `.env.example`, `app/core/config.py`, `docker-compose.yml`, `AGENTS.md`, and `README.md`.

## Documentation and scope gate

Document only implemented behavior. Keep task log and next-task history append-only. Record T-036 only as `Ready for review`; do not define or implement T-037.

T-036 needs no API key, external service, dependency, secret, configuration, Docker service, storage backend, or infrastructure change. Stop and report if one appears necessary.

Do not add approved-package lists; expanded collection bodies; package publication/delivery; rendering, HTML, PDF, export, files, storage, CDN, email; public/learner APIs; users/auth/identity/history; membership mutation/rebuild; learner sessions/scoring/analytics/recommendations/mocks/personalization; AI/LLM providers, keys, prompts, generation, source discovery, ingestion, RAG, embeddings, vectors, scraping; automatic version inference; content regeneration; new transitions; PreviousQuestion conversion; predictions; dependencies; configuration; Docker services; payments; or unrelated infrastructure.

Preserve trust, provenance, independent review, controlled release, exact ContentVersion ownership, immutable ordered package membership, and Generate Once/Personalize Later.

## Final report and handoff

Report starting HEAD; files changed/created; endpoint and response behavior; exact eligibility/order; membership preservation; route precedence; eager loading/query count; no-lock/no-write proof; compatibility; focused/full tests; Alembic/Ruff/diff results; unchanged dependency/config inspection; retained boundaries; final status; and explicit confirmation of no commit, push, PR, self-approval, T-037, approved-package list, expanded collection, publication, rendering, PDF/export, delivery, AI, source discovery, mock assembly, or personalization.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-037.

Leave T-036 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-09 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/content-packages/released` through the existing route, service, repository, and shared `ContentPackageResponse` flow. It filters exactly current RELEASED package state in PostgreSQL, orders by ascending package ID, and eagerly loads both retained membership lists in persisted association-position order using a fixed three-query strategy. It returns `[]` when none qualify and performs no locks, writes, transitions, membership rebuilding, member expansion, or current-state re-evaluation. T-036 is Ready for review, not approved. No model, schema, migration, approved-package list, expanded collection, publication, rendering, PDF/export, delivery, learner, AI, source discovery, mock assembly, personalization, or T-037 behavior was added.


---

## T-036 independent review outcome

T-036 is **APPROVED** at implementation commit `44446303944e946a1834b714ac02009bcd22e3b1`, whose parent is the T-036 task-issuance commit `0838f2c37b79b37380f7f1013df4e1b4d94625b0`.

The immutable diff adds only `GET /api/v1/content-packages/released` through the existing route, service, repository, tests, and documentation. The static route precedes the dynamic ID route. PostgreSQL filters exactly current RELEASED state, orders packages by ID, and uses two select-in loads for fixed-query retrieval of both persisted-position membership lists.

The shared serializer preserves package identity, ContentVersion, membership, review, and release metadata. Member withdrawal/review changes and Claim, Verification, priority, T-030, other package, or other ContentVersion state do not affect eligibility. Requests perform no locks, writes, flushes, commits, transitions, rebuilding, expansion, regeneration, or inference.

Developer-recorded validation reported 2 focused T-036 tests, 29 complete ContentPackage tests, 112 combined regressions, and 217 full-suite tests, each with one existing warning, plus Ruff, a fresh upgrade, unchanged Alembic head/check, and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed.

No blocking finding remains. No schema/model/migration change, approved-package list, expanded collection, publication, rendering, PDF/export, delivery, learner, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-037 implementation was included.

---

# T-037 — Persist immutable render-ready ContentDocument snapshot

## Role and synchronization gate

You are the implementation engineer for `Dyuti60/assam-exam-ai`. Implement only T-037 using the live repository, `AGENTS.md`, and the established route → schema → service → repository → PostgreSQL layering.

Before editing:

1. fetch `origin` and fast-forward local `main`;
2. record `git rev-parse HEAD` and confirm it equals `origin/main`;
3. confirm the working tree is clean;
4. confirm approved T-036 commit `44446303944e946a1834b714ac02009bcd22e3b1` and the documentation commit issuing T-037 exist in history;
5. read the complete live repository and this prompt.

Stop without changing files if synchronization, history, branch, or working tree is unexpected. The live repository is authoritative.

## Current context

The system has exact ContentVersion identity; version-owned reviewed/released NoteDraft and QuestionBankItem snapshots; immutable ordered ContentPackage membership; package review/release; individual package ID and expanded-content reads; and a collection of currently RELEASED packages.

There is no render-ready document identity or persisted assembled body. There is no HTML/PDF renderer, file or object storage, publication, download, public/learner delivery, AI generation, or personalization.

## Exact bounded goal

Add atomic creation of exactly one immutable internal ContentDocument snapshot for one currently RELEASED ContentPackage.

Add exactly:

`POST /api/v1/content-packages/{content_package_id}/content-documents`

The endpoint accepts no request body.

It must:

1. lock and resolve the exact ContentPackage;
2. require its current `release_status == RELEASED`;
3. resolve exactly all retained NoteDraft and QuestionBankItem members in stored membership-position order;
4. fail internally rather than omit, reorder, or rebuild unresolved membership;
5. deterministically assemble a title and Markdown body from those stored member snapshots;
6. compute a lowercase SHA-256 checksum of the exact UTF-8 Markdown bytes;
7. persist one immutable ContentDocument linked to the exact package and ContentVersion;
8. commit once and return the freshly stored response.

Only one ContentDocument may exist per ContentPackage. Do not regenerate or overwrite an existing document.

This is internal render-ready persistence, not PDF creation, publication, export, delivery, or learner access.

## Data model and API response

Add model/table `ContentDocument` / `content_documents` with exactly:

- `id`: integer primary key;
- `content_package_id`: non-null integer;
- `content_version_id`: non-null integer;
- `title`: non-null text;
- `markdown`: non-null text;
- `sha256`: non-null string of exactly 64 lowercase hexadecimal characters;
- `created_at`: non-null timezone-aware stored timestamp.

Required constraints:

- unique `content_package_id`, permitting only one document per package;
- composite foreign key `(content_package_id, content_version_id)` → `content_packages(id, content_version_id)`;
- deletion of a referenced package is restricted;
- non-blank title and Markdown checks;
- checksum format check equivalent to exactly 64 lowercase hexadecimal characters.

Reuse the existing supporting package uniqueness; add no unrelated constraints. Register the model for Alembic metadata.

Add `ContentDocumentResponse`:

- `id: int`;
- `content_package_id: int`;
- `content_version_id: int`;
- `title: str`;
- `markdown: str`;
- `sha256: str`;
- `created_at: datetime`.

Return HTTP 201.

Errors:

- missing package: HTTP 404, `{"detail": "ContentPackage <id> not found"}`;
- package not currently released: HTTP 409, `{"detail": "ContentPackage <id> must be released before document creation"}`;
- existing document: HTTP 409, `{"detail": "ContentPackage <id> already has a ContentDocument"}`;
- impossible retained-member resolution: internal error, not a 404/409 and not partial persistence.

Generic database exceptions must roll back and be re-raised.

## Deterministic document contract

Use no LLM and no external template engine.

Title must be exactly:

`Content Package <content_package_id>`

Markdown must be deterministic and end with exactly one newline.

Use this structure:

1. `# Content Package <content_package_id>`
2. blank line;
3. when NoteDraft members exist, `## Notes`, then each retained NoteDraft's stored Markdown in package order, separated predictably;
4. when QuestionBankItem members exist, `## Practice Questions`, then each item in package order as:
   - `### Question <1-based position>`;
   - stored question text;
   - options in stored option-position order labelled `A.`, `B.`, and so on;
   - `**Answer:** <label>. <stored correct option text>`;
   - `**Explanation:** <stored explanation>`;
5. omit a section only when that member type is absent.

Define the exact whitespace/newline joining in one small deterministic service helper and assert the complete expected Markdown in tests. Do not silently support more than 26 options; if stored data makes a deterministic label impossible, raise an internal integrity error before persistence.

Use only retained package membership for top-level ordering and only stored Claim/option/answer snapshots. Do not query current release or approval eligibility of members. Do not include reviewer notes, release notes, timestamps, internal IDs other than the package ID in the title, Claim IDs, source internals, confidence, predictions, or hidden metadata in Markdown.

Compute `sha256` from the final exact Markdown string encoded as UTF-8.

## Eligibility, integrity, locking, and atomicity

Package eligibility is its own current RELEASED state only. PostgreSQL already requires released packages to be approved and package creation already captured non-empty membership.

Member withdrawal, member review changes, Claim changes, Verification, priority, T-030, global collections, other packages, and other ContentVersions must not affect document creation.

Use one transaction:

- lock only the ContentPackage row with `SELECT ... FOR UPDATE`;
- do not lock or modify member assets or membership rows;
- check for an existing ContentDocument within the transaction;
- load exact members with the established eager-loading queries;
- verify resolved IDs exactly equal both retained membership lists;
- build and hash before adding the document;
- add, flush, and commit once;
- roll back on any exception;
- freshly retrieve the stored document for the response.

The database unique constraint is the concurrency-safe authority for one document per package. Translate only that specific uniqueness conflict to the stable existing-document 409 after rollback; re-raise other persistence errors.

Later package withdrawal or review changes must not alter, delete, or regenerate an existing ContentDocument.

## Migration requirements

Create exactly one Alembic revision whose parent is `a8c4e2f9b671`.

It must create only `content_documents` and its constraints, preserve all existing rows, infer/create no document, use no permanent default absent from model metadata, and edit no historical migration.

Downgrade drops only `content_documents` and leaves packages, review/release metadata, memberships, assets, ContentVersions, and provenance unchanged.

Validate:

`a8c4e2f9b671 → T-037 head → a8c4e2f9b671 → T-037 head`

with seeded packages and both membership types preserved and no inferred document on either upgrade.

## Required tests

Add PostgreSQL-backed tests proving:

- missing package returns exact 404 with no rows;
- DRAFT/APPROVED UNRELEASED and WITHDRAWN packages return the stable 409 without documents;
- a RELEASED NoteDraft-only package produces exact title, exact Markdown, checksum, IDs, and stored UTC timestamp;
- a RELEASED QuestionBankItem-only package produces exact labelled options, answer, explanation, ordering, checksum, and empty Notes section omission;
- a mixed package preserves independent package membership order and nested option order;
- complete Markdown equality including final newline;
- SHA-256 equals the exact UTF-8 Markdown digest;
- current member/Claim/Verification/priority/T-030/other state does not affect creation;
- later package withdrawal and review changes do not alter the stored document;
- repeated creation returns the stable existing-document 409 and does not overwrite;
- a concurrent duplicate is rejected through the database uniqueness authority;
- cross-ContentVersion document ownership, blank title/Markdown, malformed checksum, and duplicate package ownership are rejected by PostgreSQL;
- impossible membership resolution and more than 26 options fail before persistence;
- injected persistence failure rolls back all document rows;
- package row is locked while members/memberships are not;
- exactly one commit occurs on success;
- existing T-030 through T-036 behavior remains compatible.

Do not weaken, remove, reorder, or silently skip existing tests.

## Validation

Use dedicated PostgreSQL databases ending in `_test`. Run and report:

- focused ContentDocument tests;
- complete ContentPackage tests;
- T-030 released-assets and ContentVersion tests;
- NoteDraft/released-NoteDraft tests;
- QuestionBankItem/released-QuestionBankItem tests;
- full suite;
- Ruff on changed Python;
- `uv run alembic heads` and `uv run alembic check`;
- fresh upgrade;
- seeded upgrade/downgrade/re-upgrade;
- direct PostgreSQL constraint probes;
- `git diff --check`, untracked whitespace checks, and final `git status --short`.

Confirm one Alembic head whose parent is `a8c4e2f9b671`, no schema drift or historical migration edits, and no dependency/config/environment/Docker/API-key/storage/infrastructure change.

## Affected components

Update only where required:

- new ContentDocument model;
- model registration;
- shared schemas;
- repository;
- service;
- knowledge routes;
- exactly one new migration;
- focused ContentDocument tests and necessary package regressions;
- architecture/workflow;
- append-only task log and next task.

Inspect but otherwise leave unchanged: existing ContentPackage/membership and asset models; historical migrations; T-030 through T-036 behavior; `pyproject.toml`; `uv.lock`; `.env.example`; `app/core/config.py`; `docker-compose.yml`; `AGENTS.md`; `README.md`.

## Documentation and scope gate

Document only implemented behavior. Keep task history append-only. Record T-037 only as `Ready for review` and do not define or implement T-038.

T-037 needs no API key, external service, dependency, template engine, secret, configuration, Docker service, file/object storage, or infrastructure change. Stop and report if one appears necessary.

Do not add ContentDocument retrieval/list/review/release; PDF/HTML rendering; files, downloads, storage, CDN, email; package publication/delivery; public/learner APIs; users/auth/identity/history; membership mutation; learner sessions/scoring/analytics/recommendations/mocks/personalization; AI/LLM providers, keys, prompts, source discovery, ingestion, RAG, embeddings, vectors, scraping; automatic version inference; new package/member transitions; PreviousQuestion conversion; predictions; dependencies; configuration; Docker services; payments; or unrelated infrastructure.

Preserve trust, provenance, independent review, controlled release, exact ContentVersion ownership, immutable package membership, deterministic reproducibility, and Generate Once/Personalize Later.

## Final report and handoff

Report starting HEAD; files changed/created; migration revision/parent; model/constraints; endpoint/response/errors; exact deterministic Markdown and checksum; ordering; eligibility/state independence; locking/concurrency/rollback; migration cycles/probes; focused/full tests; Alembic/Ruff/diff; unchanged dependency/config inspection; boundaries; final status; and explicit confirmation of no commit, push, PR, self-approval, T-038, document retrieval/lifecycle, PDF/HTML, publication, download/storage, delivery, AI, source discovery, mock assembly, or personalization.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-038.

Leave T-037 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-09 Asia/Kolkata, UTC+05:30): added only `POST /api/v1/content-packages/{content_package_id}/content-documents` and migration `c4d8f2a6b731`. A currently RELEASED package is locked and its retained, independently ordered members are resolved into one deterministic Markdown snapshot with A-Z option/answer labels, exactly one final newline, and a lowercase SHA-256 digest of the exact UTF-8 content. PostgreSQL enforces one document per package, exact ContentVersion agreement, non-blank content, checksum format, and restricted package deletion. Creation commits once and rolls back fully on failure; current member and Claim state is not re-evaluated. T-037 is Ready for review, not approved. No ContentDocument retrieval/list/lifecycle, PDF/HTML, publication, file/storage/download, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-038 work was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## Independent review outcome — T-037

T-037 is **APPROVED** at immutable implementation commit `e199b9b6b4698ad3df1c3bf60c7e82b1adc3e951`, directly based on issuance commit `180c3b9f7061ee2f4100faba71f91bb330c236fa`.

The review found no blocker in the ContentDocument model and migration, exact package/ContentVersion constraint, deterministic Markdown contract, UTF-8 SHA-256 calculation, retained membership ordering, package-only locking, one-commit transaction, uniqueness-specific conflict mapping, rollback behavior, migration safety, tests, documentation, or scope boundaries. GitHub exposes no status contexts or workflow runs, so the reported local validation is developer evidence rather than CI evidence.

Do not modify or reinterpret T-037 while implementing the next task.

# T-038 — Add individual ContentDocument retrieval boundary

## Context

The repository now persists at most one immutable deterministic ContentDocument for a currently RELEASED ContentPackage. The document stores its package identity, exact ContentVersion ownership, title, Markdown, SHA-256 digest, and creation timestamp. Its content is already a retained snapshot and must remain independent of later package, member, Claim, Verification, priority, or dynamic-manifest state.

There is currently no API for retrieving a ContentDocument by its own ID. T-038 adds only that internal read boundary.

## Exact bounded goal

Add exactly:

`GET /api/v1/content-documents/{content_document_id}`

Return the existing `ContentDocumentResponse` with HTTP 200.

For a missing document, return HTTP 404 with exactly:

`{"detail": "ContentDocument <id> not found"}`

The endpoint must return the stored row exactly. It must not regenerate Markdown, recompute or repair SHA-256, resolve package members, load member bodies, inspect current package/member approval or release state, infer ownership, or mutate anything.

## Repository, service, and route behavior

Add one repository lookup by ContentDocument ID.

It must:

- select only the requested ContentDocument;
- require no eager loading of ContentPackage, membership, NoteDraft, QuestionBankItem, Claim, Verification, or ContentVersion bodies;
- use no `FOR UPDATE`;
- preserve the stored title, Markdown, digest, ContentVersion ID, package ID, and creation timestamp exactly.

Add one service method that:

- calls the repository lookup;
- raises `ResourceNotFoundError("ContentDocument", content_document_id)` when absent;
- otherwise reuses the existing stored ContentDocument serializer;
- performs no validation against current related state and no checksum calculation.

Add the route through the existing knowledge router and established 404 translation. Do not add a 409 path.

## Snapshot and state-independence contract

A successfully created document must remain retrievable without change after any later allowed changes to:

- the parent ContentPackage release or review state;
- retained NoteDraft or QuestionBankItem release/review state;
- Claims, Verifications, Topic priority, or T-030 released-assets results;
- unrelated packages, documents, ContentVersions, or collections.

The response must equal the original T-037 creation response field for field. Retrieval must not omit, rewrite, normalize, regenerate, validate, or repair stored content.

The database continues to restrict deletion of the referenced package. Do not add delete, update, replacement, regeneration, or repair behavior.

## Persistence and migration scope

T-038 requires no model, relationship, schema, model-registration, constraint, or migration change.

Alembic must remain at the single head `c4d8f2a6b731`, and `uv run alembic check` must report no new upgrade operations.

Do not edit historical migrations.

## Required tests

Add focused PostgreSQL-backed tests proving:

- a missing ContentDocument returns the exact 404;
- a created document is retrieved by its own ID with a response exactly equal to the T-037 creation response;
- title, Markdown including final newline, lowercase SHA-256, package ID, ContentVersion ID, and stored UTC creation timestamp are preserved;
- repeated retrieval returns the identical stored response;
- package withdrawal and a permitted post-withdrawal package review change do not alter or hide the document;
- later member release/review changes and Claim decisions do not alter or hide the document;
- retrieval performs no `FOR UPDATE`, insert, update, delete, flush, or commit;
- relevant row counts remain unchanged on successful and missing reads;
- no package-member expansion or current eligibility query is required;
- T-037 duplicate-creation behavior and T-030 through T-036 boundaries remain compatible.

Use a dedicated PostgreSQL database whose name ends in `_test`. Do not weaken, remove, reorder, or silently skip existing tests.

## Validation

Run and report:

- focused T-038 ContentDocument retrieval tests;
- complete ContentPackage/ContentDocument tests;
- T-030 released-assets and ContentVersion tests;
- NoteDraft and released-NoteDraft tests;
- QuestionBankItem and released-QuestionBankItem tests;
- full suite;
- Ruff on changed Python files;
- `uv run alembic heads`;
- `uv run alembic check`;
- a fresh upgrade through `c4d8f2a6b731`;
- `git diff --check`;
- final `git status --short`.

No migration cycle is required because persistence does not change. Confirm no schema drift, historical migration edit, dependency/configuration/environment/Docker/API-key/storage/infrastructure change, row lock, or write path.

## Affected components

Update only where required:

- knowledge repository;
- knowledge service;
- knowledge routes;
- focused ContentDocument retrieval tests;
- architecture and workflow documentation;
- append-only task log and next-task records.

Inspect but otherwise leave unchanged:

- all models and model registration;
- all schemas;
- all migrations;
- ContentPackage creation/read/content/review/release/list behavior;
- T-037 document creation and deterministic rendering behavior;
- other domain components;
- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

## Scope exclusions

Do not add:

- ContentDocument list, review, release, update, delete, replacement, regeneration, or repair;
- HTML or PDF rendering;
- file, object, blob, or CDN storage;
- download endpoints;
- publication or delivery;
- public or learner APIs;
- users, authentication, authorization, reviewer identity, or history;
- AI/LLM providers, API keys, prompts, source discovery, ingestion, RAG, embeddings, vectors, or scraping;
- mock assembly, learner sessions, scoring, analytics, recommendations, or personalization;
- dependencies, configuration, environment variables, Docker services, payments, or unrelated infrastructure;
- T-039 implementation.

Preserve trust, provenance, exact ContentVersion ownership, immutable package membership, deterministic reproducibility, the stored document checksum, independent review/release boundaries, and Generate Once/Personalize Later.

## Documentation and handoff

Document only implemented behavior. Keep task history append-only. Record T-038 only as `Ready for review`; do not approve it and do not define or implement T-039.

T-038 requires no API key, external service, dependency, secret, template engine, storage backend, configuration, Docker service, or infrastructure change. Stop and report if one appears necessary.

Report:

- starting HEAD and clean synchronized state;
- files changed;
- exact endpoint and 404;
- stored-field preservation;
- state independence;
- read-only/query behavior;
- focused and full validation;
- unchanged Alembic head/check;
- unchanged dependencies/configuration;
- final status;
- explicit confirmation that no commit, push, PR, self-approval, T-039, list/lifecycle, PDF/HTML, publication, storage/download, delivery, AI, source discovery, mock assembly, or personalization work occurred.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-039.

Leave T-038 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-09 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/content-documents/{content_document_id}` through one focused repository lookup, read-only service method, thin route, tests, and current-state documentation. It returns the existing stored ContentDocument response exactly and uses no autoflush, related-object loading, lock, write, commit, member resolution, regeneration, checksum calculation/repair, ownership inference, or current-state evaluation. Missing documents return the stable `ContentDocument <id> not found` 404. T-038 is Ready for review, not approved. Alembic remains `c4d8f2a6b731`; no model, schema, registration, migration, dependency, configuration, Docker, list/lifecycle, PDF/HTML, publication, storage/download, public/learner delivery, AI, source discovery, mock assembly, personalization, or T-039 work was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## Independent review outcome — T-038

T-038 is **APPROVED** at immutable implementation commit `4e3adcf4da0c6a29f6d7ba4556b77e47e28e353a`, directly based on issuance commit `8c431484ca7814923a709c5b44136489ac4a81b9`.

The review found no blocker in the exact missing-document 404, one-row/no-autoflush repository query, read-only service and route, shared stored serialization, package/member/Claim-state independence, repeated response equality, one-query behavior, zero-lock/write/flush/commit execution, row-count preservation, regression coverage, documentation, or scope boundaries. GitHub exposes no status contexts or workflow runs, so the reported local validation is developer evidence rather than CI evidence.

Do not modify or reinterpret T-038 while implementing the next task.

# T-039 — Add independent ContentDocument human review

## Context

T-037 persists at most one deterministic ContentDocument snapshot from a currently RELEASED ContentPackage. T-038 retrieves that exact stored document by its own ID without regeneration or related-state evaluation.

The document payload—package ID, ContentVersion ID, title, Markdown, SHA-256, and creation time—is immutable. Before any document release, PDF/HTML rendering, publication, or delivery boundary is introduced, the assembled document needs its own explicit human-review decision independent of the package and its retained members.

T-039 adds only that trust boundary.

## Exact bounded goal

Add exactly:

`POST /api/v1/content-documents/{content_document_id}/approval`

Request:

```json
{
  "approval_status": "DRAFT | APPROVED | REJECTED",
  "reviewer_note": "optional"
}
```

Return the existing ContentDocument response extended with stored review metadata.

Do not add an approved-document collection, document release, rendering, publication, storage, download, delivery, learner access, AI, or personalization.

## Data model and response

Extend ContentDocument with exactly:

- `approval_status`: non-null string, initially `DRAFT`;
- `approval_decided_at`: nullable timezone-aware timestamp;
- `reviewer_note`: nullable text.

The immutable payload fields must remain unchanged:

- `id`;
- `content_package_id`;
- `content_version_id`;
- `title`;
- `markdown`;
- `sha256`;
- `created_at`.

Add PostgreSQL constraints equivalent to:

- status is exactly `DRAFT`, `APPROVED`, or `REJECTED`;
- `DRAFT` requires null decision timestamp and null reviewer note;
- `APPROVED` and `REJECTED` require a non-null decision timestamp; reviewer note remains optional.

Extend `ContentDocumentResponse` with:

- `approval_status`;
- `approval_decided_at`;
- `reviewer_note`.

Use the existing approval-status enum when appropriate. Ensure T-037 creation and T-038 retrieval return the same review fields from stored state.

Add a request schema accepting only DRAFT, APPROVED, or REJECTED plus an optional reviewer note. Missing or invalid decisions must use standard HTTP 422 validation.

## Decision semantics

For `APPROVED` or `REJECTED`:

- store the requested status;
- record the current UTC decision timestamp;
- store the optional reviewer note.

For `DRAFT`:

- set status to DRAFT;
- clear `approval_decided_at`;
- clear `reviewer_note`, even when a note is supplied.

A missing ContentDocument returns HTTP 404 with exactly:

`{"detail": "ContentDocument <id> not found"}`

Do not introduce a 409 path in T-039.

Review is independent of:

- ContentPackage review or release state;
- NoteDraft and QuestionBankItem review/release state;
- Claims and Verifications;
- Topic priority and T-030 released-assets state;
- other documents, packages, or ContentVersions.

Changing review must never rewrite, normalize, regenerate, re-hash, or revalidate the immutable document payload.

## Repository, locking, and transaction behavior

Add a repository lookup for approval using:

- `SELECT ... FOR UPDATE OF content_documents`;
- only the target ContentDocument row;
- no package/member eager loading;
- no locks on ContentPackage, membership rows, NoteDrafts, QuestionBankItems, Claims, or other documents.

Add a focused repository update helper that changes only:

- `approval_status`;
- `approval_decided_at`;
- `reviewer_note`.

The service must:

1. load and lock the target document;
2. return the established 404 when absent;
3. calculate DRAFT versus decided metadata;
4. update only the three review fields;
5. commit exactly once;
6. roll back and re-raise generic persistence failures;
7. freshly retrieve and serialize the stored ContentDocument response.

Ordinary T-038 retrieval must remain lock-free and read-only.

## Migration requirements

Create exactly one Alembic revision whose parent is `c4d8f2a6b731`.

It must:

- add only the three ContentDocument review columns and their constraints;
- migrate every existing ContentDocument to DRAFT with null decision metadata;
- infer no approval from ContentPackage or member state;
- keep model metadata and database defaults aligned;
- preserve all existing document IDs, package/ContentVersion ownership, title, Markdown, SHA-256, and creation timestamps;
- edit no historical migration.

Downgrade must remove only the T-039 review constraints and columns while preserving every pre-T-039 document field and row.

Validate:

`c4d8f2a6b731 → T-039 head → c4d8f2a6b731 → T-039 head`

with at least one seeded ContentDocument and its referenced package/members preserved. Each upgrade must produce DRAFT with null decision metadata and must not modify the stored Markdown or checksum.

## Required tests

Add PostgreSQL-backed tests proving:

- newly created ContentDocuments default to DRAFT with null decision timestamp and note;
- T-038 retrieval returns stored review metadata;
- APPROVED and REJECTED record exact requested status, a UTC decision timestamp, and optional note;
- resetting to DRAFT clears timestamp and note;
- repeated decisions follow the defined semantics without changing immutable fields;
- missing document returns the exact 404;
- missing and invalid status values return standard 422;
- package/member/Claim/Verification/priority/T-030/other-document state cannot substitute for or block the target document’s own review decision;
- review changes leave package identity, ContentVersion identity, title, exact Markdown/final newline, SHA-256, creation timestamp, package membership, and member rows unchanged;
- approval locks only the target ContentDocument row;
- ordinary retrieval remains lock-free;
- exactly one commit occurs on a successful decision;
- injected persistence failure rolls back all review-field changes;
- PostgreSQL rejects invalid statuses and invalid status/timestamp/note combinations;
- migration upgrade/downgrade/re-upgrade preserves existing document payload and establishes DRAFT/null review metadata;
- T-037 creation/duplicate behavior, T-038 retrieval, and T-030 through T-036 boundaries remain compatible.

Use dedicated PostgreSQL databases whose names end in `_test`. Do not weaken, remove, reorder, or silently skip existing tests.

## Validation

Run and report:

- focused T-039 ContentDocument-review tests;
- complete ContentPackage/ContentDocument tests;
- T-030 released-assets and ContentVersion tests;
- NoteDraft and released-NoteDraft tests;
- QuestionBankItem and released-QuestionBankItem tests;
- full suite;
- Ruff on changed Python files;
- `uv run alembic heads`;
- `uv run alembic check`;
- fresh upgrade through the T-039 head;
- seeded upgrade/downgrade/re-upgrade;
- direct PostgreSQL constraint probes;
- `git diff --check`;
- untracked-file whitespace checks;
- final `git status --short`.

Confirm one Alembic head whose parent is `c4d8f2a6b731`, no schema drift or historical migration edits, and no dependency/configuration/environment/Docker/API-key/storage/infrastructure change.

## Affected components

Update only where required:

- ContentDocument model;
- shared schemas;
- knowledge repository;
- knowledge service;
- knowledge routes;
- exactly one new migration;
- focused ContentDocument/package tests;
- architecture and workflow documentation;
- append-only task log and next-task records.

Inspect but otherwise leave unchanged:

- model registration unless import mechanics genuinely require no change;
- ContentPackage and membership models;
- NoteDraft and QuestionBankItem models;
- historical migrations;
- T-030 through T-038 behavior;
- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

## Scope exclusions

Do not add:

- approved ContentDocument collection;
- ContentDocument release, withdrawal, list, update, delete, replacement, regeneration, or repair;
- HTML or PDF rendering;
- file/object/blob/CDN storage or download endpoints;
- publication or delivery;
- public or learner APIs;
- users, authentication, authorization, reviewer identity, review history, or audit-event infrastructure;
- AI/LLM providers, API keys, prompts, source discovery, ingestion, RAG, embeddings, vectors, or scraping;
- mock assembly, learner sessions, scoring, analytics, recommendations, or personalization;
- new package/member transitions;
- dependencies, configuration, environment variables, Docker services, payments, or unrelated infrastructure;
- T-040 implementation.

Preserve trust, provenance, exact ContentVersion ownership, immutable package membership, immutable document payload, deterministic reproducibility, stored checksum integrity, independent review/release boundaries, and Generate Once/Personalize Later.

## Documentation and handoff

Document only implemented behavior. Keep task history append-only. Record T-039 only as `Ready for review`; do not approve it and do not define or implement T-040.

T-039 needs no API key, external service, dependency, secret, renderer, storage backend, configuration, Docker service, or infrastructure change. Stop and report if one appears necessary.

Report:

- starting HEAD and clean synchronized state;
- files changed/created;
- migration revision and parent;
- model/constraint/default behavior;
- endpoint/request/response/errors;
- decision semantics and UTC metadata;
- immutable-field preservation and state independence;
- locking, commit, rollback, and concurrency behavior;
- migration cycle and PostgreSQL probes;
- focused/full validation;
- Alembic/Ruff/diff results;
- unchanged dependency/configuration inspection;
- final status;
- explicit confirmation that no commit, push, PR, self-approval, T-040, approved list, document release/lifecycle, PDF/HTML, publication, storage/download, delivery, AI, source discovery, mock assembly, or personalization work occurred.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-040.

Leave T-039 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-09 Asia/Kolkata, UTC+05:30): added only independent DRAFT/APPROVED/REJECTED ContentDocument review metadata, migration `b6f1d3a8e942`, and `POST /api/v1/content-documents/{content_document_id}/approval`. Approval decisions lock only the target document row, update only the three review fields, commit once, roll back failures, and freshly return the stored immutable document response. APPROVED/REJECTED record a UTC decision timestamp and optional note; DRAFT clears both. Existing documents migrate to DRAFT/null without inferred approval. T-039 is Ready for review, not approved. No approved-document collection, release, list, PDF/HTML, publication, storage/download, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-040 work was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## Independent review outcome — T-039

T-039 is **APPROVED** at immutable implementation commit `5d954866cf18e5bbfeb89f0a465ce593645bdd45`, directly based on issuance commit `0c44c8e0fd2ea587339d18d4f9bf83f03103d882`.

The review found no blocker in the ContentDocument review model/migration, safe DRAFT migration, PostgreSQL constraints, request/response compatibility, UTC decision metadata, DRAFT reset semantics, target-only row locking, one-commit success, rollback handling, lock-free retrieval, immutable-payload preservation, state independence, tests, documentation, or scope boundaries. GitHub exposes no status contexts or workflow runs, so the reported local validation is developer evidence rather than CI evidence.

Do not modify or reinterpret T-039 while implementing the next task.

# T-040 — Add controlled ContentDocument release lifecycle

## Context

T-037 persists one deterministic immutable ContentDocument snapshot from a released ContentPackage. T-038 retrieves it exactly by document ID. T-039 adds the document’s own independent DRAFT/APPROVED/REJECTED human-review decision without changing its payload.

The next trust boundary is explicit controlled release of the ContentDocument itself. Document approval must not imply release, and release must remain separate from released-document listing, PDF/HTML rendering, publication, file storage, download, or learner delivery.

## Exact bounded goal

Add exactly:

`POST /api/v1/content-documents/{content_document_id}/release`

Request:

```json
{
  "release_status": "RELEASED | WITHDRAWN",
  "release_note": "optional"
}
```

Return the existing ContentDocument response extended with stored release metadata.

Allowed transitions:

- `UNRELEASED → RELEASED`;
- `RELEASED → WITHDRAWN`.

All other transitions must return deterministic HTTP 409 without mutation. Do not expose UNRELEASED as an API decision. Missing, invalid, or UNRELEASED decisions return standard HTTP 422.

## Data model and response

Extend ContentDocument with exactly:

- `release_status`: non-null string, initially `UNRELEASED`;
- `released_at`: nullable timezone-aware timestamp;
- `withdrawn_at`: nullable timezone-aware timestamp;
- `release_note`: nullable text.

Extend `ContentDocumentResponse` with the same four fields.

Add PostgreSQL constraints equivalent to:

- status is exactly UNRELEASED, RELEASED, or WITHDRAWN;
- UNRELEASED requires null release timestamp, withdrawal timestamp, and release note;
- RELEASED requires a release timestamp, null withdrawal timestamp, and the document’s own current review state APPROVED;
- WITHDRAWN requires both timestamps; its review may change after withdrawal.

The immutable ID, ownership, title, exact Markdown, SHA-256, and creation timestamp must never change. Approval must not infer release. New and migrated documents begin UNRELEASED with null release metadata.

## Eligibility and stable errors

Release eligibility is only the target document’s own APPROVED state. Do not consult current package/member review or release, Claims, Verifications, priority, T-030, global collections, other documents, or other ContentVersions.

Errors:

- missing document: HTTP 404, `{"detail": "ContentDocument <id> not found"}`;
- unapproved release: HTTP 409, `{"detail": "ContentDocument <id> must be approved before release"}`;
- invalid transition: HTTP 409, `{"detail": "ContentDocument <id> cannot transition from <CURRENT> to <REQUESTED>"}`;
- review change while released: HTTP 409, `{"detail": "ContentDocument <id> must be withdrawn before changing approval"}`.

While currently RELEASED, DRAFT and REJECTED review changes are blocked. Re-applying APPROVED may retain existing review semantics without changing release metadata. After withdrawal, review changes work again and preserve release metadata.

## Decision semantics

Successful release records current UTC `released_at`, leaves `withdrawn_at` null, stores the optional note, and preserves payload/review metadata.

Successful withdrawal preserves original `released_at`, records current UTC `withdrawn_at`, replaces the optional note, and preserves payload/review metadata.

A withdrawn document cannot be re-released in T-040.

## Repository, locking, and atomicity

Release and potentially conflicting approval decisions must use `SELECT ... FOR UPDATE OF content_documents` and lock only the target document.

Do not lock or modify packages, memberships, assets, Claims, or other documents.

Add a focused repository helper that updates only the four release fields. The service must validate before mutation, commit exactly once, roll back and re-raise persistence failures, then freshly retrieve the stored response. Ordinary T-038 retrieval remains lock-free and read-only.

## Migration requirements

Create exactly one Alembic revision whose parent is `b6f1d3a8e942`.

It must add only the four release columns and named constraints, migrate every existing document to UNRELEASED/null metadata without inference, preserve all payload/review fields, keep model metadata/defaults aligned, and edit no historical migration.

Downgrade removes only T-040 release constraints/columns and preserves the row, immutable payload, and T-039 review state.

Validate `b6f1d3a8e942 → T-040 head → b6f1d3a8e942 → T-040 head` with seeded document payload and review metadata preserved. Each upgrade must produce UNRELEASED/null release metadata.

## Required tests

Add PostgreSQL-backed tests proving:

- new documents default to UNRELEASED/null release metadata and approval does not imply release;
- APPROVED documents release with exact UTC metadata and optional note;
- DRAFT/REJECTED documents return the stable approval conflict without mutation;
- package/member/Claim/Verification/priority/T-030/other-document state does not affect eligibility;
- premature withdrawal, duplicate release, repeated withdrawal, and withdrawn-to-release return exact conflicts without mutation;
- withdrawal preserves release time, records UTC withdrawal time, and replaces the note;
- RELEASED blocks DRAFT/REJECTED review changes; changes work after withdrawal while preserving release metadata;
- missing document returns exact 404; missing/invalid/UNRELEASED decisions return 422;
- release/conflicting approval lock only the target document;
- successful decisions commit exactly once and injected failures roll back;
- payload, review metadata, memberships, members, and Claims remain unchanged;
- PostgreSQL rejects invalid status/metadata combinations and RELEASED with non-APPROVED review;
- direct persistence cannot move a currently RELEASED document to DRAFT or REJECTED;
- migration cycle preserves payload/review data and infers no release;
- T-037 creation, T-038 retrieval, T-039 review, and T-030 through T-036 remain compatible.

Use dedicated PostgreSQL databases ending in `_test`. Do not weaken, remove, reorder, or silently skip existing tests.

## Validation

Run and report focused T-040 tests; complete ContentPackage/ContentDocument tests; T-030 released-assets and ContentVersion tests; NoteDraft/released-NoteDraft tests; QuestionBankItem/released-QuestionBankItem tests; full suite; changed-file Ruff; Alembic heads/check; fresh upgrade; seeded upgrade/downgrade/re-upgrade; direct PostgreSQL probes; diff and untracked whitespace checks; and final status.

Confirm one Alembic head whose parent is `b6f1d3a8e942`, no schema drift or historical migration edit, and no dependency/configuration/environment/Docker/API-key/storage/infrastructure change.

## Affected components

Update only where required: ContentDocument model, shared schemas, repository, service, routes, exactly one migration, focused tests, architecture/workflow, and append-only task records.

Inspect but otherwise leave unchanged: model registration unless import mechanics require no change; ContentPackage/membership and asset models; historical migrations; T-030 through T-039 behavior; `pyproject.toml`; `uv.lock`; `.env.example`; configuration; Docker; `AGENTS.md`; and `README.md`.

## Scope exclusions

Do not add released/approved ContentDocument collections; PDF/HTML rendering; storage/download; publication/delivery; public/learner APIs; users/auth/history; document update/delete/replacement/regeneration/repair or re-release; AI/LLM/API keys/source discovery/ingestion/RAG/embeddings/scraping; mocks/sessions/scoring/analytics/recommendations/personalization; package/member transitions; dependencies/config/environment/Docker/payments/infrastructure; or T-041.

Preserve trust, provenance, exact ContentVersion ownership, immutable package membership and document payload, deterministic reproducibility, stored checksum integrity, independent review and controlled release, and Generate Once/Personalize Later.

## Documentation and handoff

Document only implemented behavior. Keep task history append-only. Record T-040 only as `Ready for review`; do not approve it and do not define or implement T-041.

T-040 needs no API key, external service, dependency, secret, renderer, storage backend, configuration, Docker service, or infrastructure change. Stop and report if one appears necessary.

Report starting state; files and migration; model/default/constraints; endpoint/request/response/errors; transitions/UTC metadata; review lock/state independence; immutable preservation; locking/commit/rollback/PostgreSQL enforcement; migration cycle; tests/checks; unchanged configuration; final status; and explicit confirmation of no commit, push, PR, self-approval, T-041, collections, PDF/HTML, publication, storage/download, delivery, AI, source discovery, mock assembly, or personalization.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-041.

Leave T-040 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-09 Asia/Kolkata, UTC+05:30): added only controlled UNRELEASED/RELEASED/WITHDRAWN ContentDocument metadata, migration `d1a7c4e9f263`, and `POST /api/v1/content-documents/{content_document_id}/release`. Only the document's own APPROVED review state permits initial release; withdrawal retains the original release time, records a UTC withdrawal time, and prevents in-place re-release. Release and conflicting approval decisions lock only the target document row, commit once, roll back failures, and preserve the immutable payload and related state. Existing documents migrate to UNRELEASED/null without inferred release. T-040 is Ready for review, not approved. No approved/released document collection, PDF/HTML, publication, storage/download, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-041 work was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## Independent review outcome — T-040

T-040 is **APPROVED** at immutable implementation commit `9add651af5a8a07dd9d1a1739bbe90f6e6b19277`, directly based on issuance commit `426489d58513686871eb8a3315192cbdc03ea97c`.

The review found no blocker in model/migration alignment, safe UNRELEASED migration, transition ordering, stable conflicts, document-own approval eligibility, released-review lock, UTC provenance, document-only row locking, one-commit success, rollback handling, PostgreSQL enforcement, immutable-payload preservation, state independence, tests, documentation, or scope boundaries. GitHub exposes no status contexts or workflow runs, so the reported local validation is developer evidence rather than CI evidence.

Do not modify or reinterpret T-040 while implementing the next task.

# T-041 — Add released ContentDocument read boundary

## Context

T-037 persists one immutable deterministic ContentDocument, T-038 retrieves it by ID, T-039 records its independent review, and T-040 controls its UNRELEASED/RELEASED/WITHDRAWN lifecycle.

The next bounded capability is a read-only internal collection of only the documents whose current persisted release state is RELEASED. It is an internal downstream boundary, not PDF rendering, publication, download, or learner delivery.

## Exact bounded goal

Add exactly:

`GET /api/v1/content-documents/released`

Return `list[ContentDocumentResponse]` with HTTP 200.

The static `/released` route must be registered before `/content-documents/{content_document_id}` so it cannot be captured by the dynamic integer-ID route.

An empty database or an existing database with no currently RELEASED document returns HTTP 200 with `[]`.

## Eligibility and ordering

Eligibility depends exactly and only on:

`ContentDocument.release_status == "RELEASED"`

The repository must filter in PostgreSQL and order by ascending ContentDocument ID.

Do not add a separate approval filter. PostgreSQL already requires a currently RELEASED document to be APPROVED.

Exclude:

- all UNRELEASED documents, regardless of review state;
- all WITHDRAWN documents, regardless of review state.

Package/member/Claim/Verification/priority/T-030/current collection state must not substitute for or affect document eligibility. A document remains eligible while RELEASED even if its package or retained members are later withdrawn or review-changed.

## Stored response contract

Return the existing ContentDocumentResponse unchanged, including:

- document ID;
- ContentPackage ID;
- ContentVersion ID;
- title;
- exact stored Markdown;
- lowercase stored SHA-256;
- creation timestamp;
- review status, timestamp, and note;
- release status, release timestamp, null withdrawal timestamp, and release note.

Use the existing stored ContentDocument serializer. Do not regenerate Markdown, recompute/repair the checksum, normalize content, resolve package membership, load package/member bodies, or inspect related state.

## Read-only query behavior

The repository query must select only ContentDocument rows. It requires no eager loading because the response is self-contained.

The endpoint must perform no:

- `FOR UPDATE` or other lock;
- insert, update, or delete;
- flush or commit;
- transition;
- regeneration, hashing, repair, inference, or related-state evaluation.

The query count must remain fixed at one SELECT regardless of returned document count.

## Persistence and migration scope

T-041 requires no model, relationship, schema, model-registration, constraint, or migration change.

Alembic remains at the single head `d1a7c4e9f263`. Do not edit historical migrations.

## Required tests

Add focused PostgreSQL-backed tests proving:

- an empty database returns HTTP 200 and `[]`;
- a database with only UNRELEASED and WITHDRAWN documents returns `[]`;
- DRAFT, APPROVED, and REJECTED UNRELEASED documents are excluded;
- currently RELEASED documents are returned in ascending document-ID order;
- a WITHDRAWN document is excluded;
- complete returned responses equal the stored release responses field for field;
- exact Markdown/final newline, stored checksum, ownership, creation, review, and release metadata are preserved;
- package/member withdrawal and permitted review changes do not affect a document that remains RELEASED;
- Claim and unrelated domain state do not affect eligibility or snapshots;
- withdrawing one document removes only that document from later results;
- repeated reads are stable;
- successful and empty reads leave relevant row counts unchanged;
- each request executes one ContentDocument SELECT with no package/member query;
- no `FOR UPDATE`, write, flush, or commit occurs;
- static-route precedence is demonstrated;
- T-037 creation, T-038 retrieval, T-039 review, T-040 release, and T-030 through T-036 remain compatible.

Use a dedicated PostgreSQL database ending in `_test`. Do not weaken, remove, reorder, or silently skip existing tests.

## Validation

Run and report:

- focused T-041 released-document tests;
- complete ContentPackage/ContentDocument tests;
- T-030 released-assets and ContentVersion tests;
- NoteDraft and released-NoteDraft tests;
- QuestionBankItem and released-QuestionBankItem tests;
- full suite;
- Ruff on changed Python;
- `uv run alembic heads`;
- `uv run alembic check`;
- a fresh upgrade through `d1a7c4e9f263`;
- `git diff --check`;
- final `git status --short`.

No migration cycle is required because persistence does not change. Confirm no schema drift, historical migration edit, dependency/configuration/environment/Docker/API-key/storage/infrastructure change, row lock, or write path.

## Affected components

Update only where required:

- knowledge repository;
- knowledge service;
- knowledge routes;
- focused released-ContentDocument tests;
- architecture and workflow documentation;
- append-only task log and next-task records.

Inspect but otherwise leave unchanged:

- all models and model registration;
- all schemas;
- all migrations;
- ContentDocument creation/retrieval/review/release behavior;
- ContentPackage and asset behavior;
- T-030 through T-040 boundaries;
- `pyproject.toml`;
- `uv.lock`;
- `.env.example`;
- configuration;
- Docker;
- `AGENTS.md`;
- `README.md`.

## Scope exclusions

Do not add approved-document collection, PDF/HTML rendering, file/object/blob/CDN storage, download endpoints, publication/delivery, public/learner APIs, users/auth/history, document mutation/regeneration/repair, AI/LLM/API keys/source discovery/ingestion/RAG/embeddings/scraping, mock assembly/sessions/scoring/analytics/recommendations/personalization, package/member transitions, dependencies/config/environment/Docker/payments/infrastructure, or T-042.

Preserve trust, provenance, exact ContentVersion ownership, immutable package membership and document payload, stored checksum integrity, independent review, controlled release, and Generate Once/Personalize Later.

## Documentation and handoff

Document only implemented behavior. Keep task history append-only. Record T-041 only as `Ready for review`; do not approve it and do not define or implement T-042.

T-041 needs no API key, external service, dependency, secret, renderer, storage backend, configuration, Docker service, or infrastructure change. Stop and report if one appears necessary.

Report starting state; files changed; endpoint and filtering/order; stored response; state independence; fixed-query/no-write behavior; focused/full tests; Alembic/Ruff/diff; unchanged configuration; final status; and explicit confirmation of no commit, push, PR, self-approval, T-042, approved list, PDF/HTML, publication, storage/download, delivery, AI, source discovery, mock assembly, or personalization.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-042.

Leave T-041 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-09 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/content-documents/released` through the existing route, service, repository, and `ContentDocumentResponse` flow. PostgreSQL filters exactly current RELEASED state and orders by ascending document ID. Each request performs one ContentDocument-only, no-autoflush, lock-free SELECT and returns stored immutable payload, ownership, checksum, review, and release metadata without regeneration, recalculation, related-state evaluation, write, flush, or commit. UNRELEASED and WITHDRAWN documents are excluded; package/member/Claim/Verification/priority/manifest state cannot substitute for document release. T-041 is Ready for review, not approved. Alembic remains `d1a7c4e9f263`; no model, schema, registration, migration, dependency, configuration, Docker, approved-document list, PDF/HTML, publication, storage/download, public/learner delivery, AI, source discovery, mock assembly, personalization, or T-042 work was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

## Independent review outcome — T-041

T-041 is **APPROVED** at immutable implementation commit `210d3c7186ec8a5d344dfbbf99d669b7aa0d0292`, directly based on issuance commit `bb1db0872e444307501adb495418d24bd7f43091`.

The review found no blocker in static-route precedence, exact RELEASED filtering, ascending ordering, one-query/no-autoflush behavior, stored response preservation, related-state independence, absence of locks and writes, tests, documentation, or scope boundaries. GitHub exposes no status contexts or workflow runs, so the reported local validation is developer evidence rather than CI evidence.

Do not modify or reinterpret T-041 while implementing the next task.

# T-042 — Persist immutable deterministic PDF artifact

## Context

T-037 persists one immutable render-ready Markdown ContentDocument, T-038 retrieves it, T-039 reviews it, T-040 controls release and withdrawal, and T-041 lists only currently RELEASED documents.

The next bounded capability is to render one exact RELEASED ContentDocument into immutable PDF bytes and persist those bytes with checksum and ownership provenance. This remains an internal artifact-creation boundary. Retrieval/download, publication, learner delivery, AI generation, source discovery, and personalization are later tasks.

## Exact bounded goal

Add exactly:

`POST /api/v1/content-documents/{content_document_id}/pdf-artifacts`

The endpoint accepts no request body and returns HTTP 201 with a new `PdfArtifactResponse`.

Allow at most one PdfArtifact per ContentDocument. A repeated request must return a deterministic HTTP 409 and must not regenerate or replace the existing artifact.

## Eligibility and stable errors

Eligibility depends exactly on the target ContentDocument’s current persisted `release_status == "RELEASED"`.

Do not add a separate approval check; PostgreSQL already requires a RELEASED document to be APPROVED. Do not consult current package, retained members, Claims, Verifications, priority, T-030 manifests, global collections, other documents, or other ContentVersions.

Errors:

- missing document: HTTP 404, `{"detail": "ContentDocument <id> not found"}`;
- ineligible document: HTTP 409, `{"detail": "ContentDocument <id> must be released before PDF creation"}`;
- duplicate artifact: HTTP 409, `{"detail": "ContentDocument <id> already has a PdfArtifact"}`.

Validate eligibility and the ordinary duplicate path before rendering. Treat the named database uniqueness constraint as the concurrency authority and translate only that expected violation to the same duplicate 409. Roll back and re-raise unrelated persistence failures.

## PdfArtifact persistence model

Add one `PdfArtifact` model/table with exactly the immutable artifact data needed by this slice:

- integer primary-key `id`;
- non-null `content_document_id`;
- non-null copied `content_package_id`;
- non-null copied `content_version_id`;
- non-null `filename`;
- non-null `media_type`, exactly `application/pdf`;
- non-null PDF bytes in a PostgreSQL `bytea`/SQLAlchemy `LargeBinary` column;
- positive non-null `byte_size`;
- non-null lowercase 64-character hexadecimal `sha256`;
- non-null timezone-aware `created_at`.

Expose all metadata through `PdfArtifactResponse` except the raw PDF bytes. The response must include ID, all three ownership IDs, filename, media type, byte size, SHA-256, and creation timestamp.

Enforce one artifact per ContentDocument with a named unique constraint. Enforce exact document/package/ContentVersion agreement with a named composite foreign key to `content_documents(id, content_package_id, content_version_id)`; add only the supporting ContentDocument uniqueness required for that reference. Use `ON DELETE RESTRICT`.

Add named PostgreSQL checks for a nonblank filename ending in `.pdf`, exact media type, positive byte size, byte-size agreement with the stored bytes, and lowercase SHA-256 format. Keep model metadata and migration definitions aligned.

No update, delete, replacement, repair, or regeneration API is allowed.

## Deterministic renderer contract

Render only the exact stored ContentDocument `title` and `markdown`. Do not rebuild package membership, notes, questions, answers, explanations, or provenance.

Use one deterministic in-process PDF renderer. A renderer dependency may be added only if it is necessary; prefer a mature maintained Python library, pin it through the project’s normal `uv` workflow, and update `pyproject.toml` and `uv.lock` together. No network call, API key, browser, external conversion service, office suite, Docker service, or runtime binary may be required.

The PDF contract must be stable and explicitly versioned in code:

- A4 pages;
- fixed margins, typography, spacing, wrapping, and pagination;
- the stored title is rendered once as the document heading;
- the stored Markdown is rendered predictably without mutating the stored source;
- headings, paragraphs, blank lines, bullets, and the T-037 Notes/Practice Questions structure remain readable;
- fixed PDF metadata and deterministic object generation; never embed wall-clock creation time, random IDs, host paths, usernames, or environment-specific values inside the PDF bytes;
- identical title and Markdown under the same renderer version produce byte-identical PDF output;
- output begins with a valid PDF header and has a valid EOF marker;
- calculate `byte_size` and lowercase SHA-256 from the exact bytes persisted.

Keep the renderer isolated behind a small focused module/function and define a constant renderer version for future traceability. Do not expose renderer internals as an API field in T-042 unless a persistence field is genuinely required to reproduce or interpret the artifact; if so, stop and document the necessity before expanding the schema.

Unicode content must fail clearly before persistence if the chosen deterministic renderer cannot represent it; never silently replace, drop, or corrupt characters. Do not broaden T-042 into a general HTML/CSS renderer.

## Locking and atomicity

Load the target ContentDocument with `SELECT ... FOR UPDATE OF content_documents` and lock only that row.

After eligibility and duplicate validation:

1. render bytes in memory from the stored title and Markdown;
2. calculate byte size and SHA-256 from those exact bytes;
3. create the PdfArtifact with copied ownership IDs;
4. flush artifact constraints;
5. commit exactly once;
6. retrieve and return the stored metadata response.

On any rendering or persistence failure, leave zero partial PdfArtifact rows and do not modify the ContentDocument or related state.

Do not lock or modify the ContentPackage, membership associations, NoteDrafts, QuestionBankItems, Claims, or other documents.

## Migration requirements

Create exactly one Alembic revision whose parent is `d1a7c4e9f263`.

It must:

- add only the supporting ContentDocument unique constraint and the `pdf_artifacts` table with named constraints;
- create no artifact for existing documents;
- preserve every existing document and all earlier state;
- edit no historical migration.

Downgrade must drop only T-042 objects in safe dependency order and preserve ContentDocuments.

Validate `d1a7c4e9f263 -> T-042 head -> d1a7c4e9f263 -> T-042 head` with seeded ContentDocument payload/review/release metadata preserved and zero inferred artifacts on both upgrades.

## Required tests

Add focused PostgreSQL-backed tests proving:

- a RELEASED ContentDocument creates one artifact with HTTP 201;
- response metadata and stored row exactly match document/package/ContentVersion ownership;
- bytes start with a PDF header, end with a valid EOF marker, have positive size, and match stored `byte_size` and lowercase SHA-256;
- the PDF contains the document title and representative Notes, Practice Questions, options, answer, and explanation content in readable order;
- rendering the same title/Markdown twice through the renderer produces byte-identical output;
- the exact stored ContentDocument is the only rendering input; later package/member/Claim changes do not affect creation;
- UNRELEASED and WITHDRAWN documents return the exact eligibility 409 without rendering or persistence;
- a missing document returns the exact 404;
- a duplicate request returns the exact 409 without changing the stored artifact;
- a simulated uniqueness race maps only the named duplicate constraint to the duplicate 409;
- unrelated integrity/database errors are rolled back and re-raised;
- renderer failure or unsupported-character failure leaves zero artifact rows;
- the target document alone is row-locked;
- success commits exactly once; failures roll back;
- ContentDocument and all package/member/Claim/review/release data remain unchanged;
- PostgreSQL rejects mismatched ownership, duplicate document ownership, blank/non-PDF filenames, wrong media type, nonpositive/mismatched byte size, and malformed SHA-256;
- deletion of a referenced ContentDocument is restricted;
- migration cycle preserves prior data and infers no artifact;
- T-037 through T-041 and T-030 through T-036 remain compatible.

Use dedicated PostgreSQL databases ending in `_test`. Do not weaken, remove, reorder, or silently skip existing tests.

## Validation

Run and report:

- focused T-042 PdfArtifact tests;
- complete ContentPackage/ContentDocument tests;
- T-041 released-document tests;
- T-030 released-assets and ContentVersion tests;
- NoteDraft and released-NoteDraft tests;
- QuestionBankItem and released-QuestionBankItem tests;
- full suite;
- Ruff on all changed Python;
- `uv lock --check` or the repository-equivalent lock verification if dependencies change;
- `uv run alembic heads`;
- `uv run alembic check`;
- a fresh upgrade through the new head;
- seeded upgrade/downgrade/re-upgrade;
- direct PostgreSQL constraint probes;
- `git diff --check`;
- whitespace checks for every untracked file;
- final `git status --short`.

Confirm one Alembic head whose parent is `d1a7c4e9f263`, no schema drift or historical migration edit, and no external-service/API-key/configuration/environment/Docker/storage-backend/infrastructure change.

## Affected components

Update only where required:

- PdfArtifact model and model registration;
- ContentDocument supporting relationship/constraint only if required;
- shared schemas;
- knowledge repository, service, and routes;
- one focused deterministic renderer module;
- exactly one migration;
- focused tests;
- `pyproject.toml` and `uv.lock` only if a renderer dependency is required;
- architecture/workflow and append-only task records.

Inspect but otherwise leave unchanged:

- ContentPackage and membership models;
- NoteDraft and QuestionBankItem models;
- historical migrations;
- existing T-030 through T-041 APIs and behavior;
- `.env.example`;
- configuration;
- Docker;
- `AGENTS.md`;
- `README.md`.

## Scope exclusions

Do not add PdfArtifact retrieval/list/download endpoints; approved-document collection; HTML artifact persistence; object/file/blob/CDN storage; publication or delivery lifecycle; public/learner APIs; users/auth/history; artifact update/delete/replacement/regeneration/repair; asynchronous jobs/queues; AI/LLM/API keys/source discovery/ingestion/RAG/embeddings/scraping; mock assembly/sessions/scoring/analytics/recommendations/personalization; payments or infrastructure; or T-043.

Preserve trust, provenance, exact ContentVersion ownership, immutable package membership and ContentDocument payload, stored checksums, independent review, controlled release, deterministic reproducibility, and Generate Once/Personalize Later.

## Documentation and handoff

Document only implemented behavior. Keep task history append-only. Record T-042 only as `Ready for review`; do not approve it and do not define or implement T-043.

T-042 needs no API key, external service, secret, storage backend, configuration value, Docker service, or infrastructure change. A local deterministic renderer dependency is permitted only as described above.

Report starting state; files and migration; dependency decision; renderer version/contract; endpoint/errors; model/constraints; deterministic byte/checksum evidence; ownership; locking/atomicity; migration cycle; tests/checks; unchanged configuration; final status; and explicit confirmation of no commit, push, PR, self-approval, T-043, retrieval/download, publication, delivery, learner API, AI, source discovery, mock assembly, or personalization.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement T-043.

Leave T-042 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-09 Asia/Kolkata, UTC+05:30): added only `POST /api/v1/content-documents/{content_document_id}/pdf-artifacts`. Dependency-free renderer `deterministic-pdf-v1` creates fixed-layout A4 bytes solely from the exact stored title and Markdown; identical supported inputs are byte-identical and unsupported characters fail before persistence. `PdfArtifact` retains exact document/package/ContentVersion ownership, raw bytes, positive matching size, lowercase SHA-256, fixed PDF media type, filename, and creation time under named PostgreSQL constraints. Creation requires current RELEASED state, locks only the target document, rejects ordinary/concurrent duplicates deterministically, commits once, and rolls back renderer or persistence failure. T-042 is Ready for review, not approved. No artifact retrieval/download, publication, external storage, learner delivery, dependency, API key, AI, source discovery, mock assembly, personalization, or T-043 work was added. Exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-042 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-042` |
| Implementation commit | `e41ab090ee9b715e473a72c25474f8ca58deb424` |
| Base/task-issuance commit | `896cc7069a70faf1af31c37824019bcf2ffc6c1b` |
| Review result | **APPROVED** |
| Approved capability | One currently RELEASED ContentDocument can atomically create at most one immutable deterministic database-backed PdfArtifact with exact copied ownership, stored bytes, size, SHA-256, filename, media type, and creation time. |
| Independent review | Exact commit diff, model/registration, migration, renderer, schema, repository, service, route, tests, documentation, transaction behavior, constraints, exclusions, and developer-recorded validation were inspected. No blocking finding was identified. |
| CI evidence | GitHub exposes no status contexts or workflow runs for the implementation commit; local results recorded by the developer are evidence, not a claimed CI pass. |

# T-043 — Retrieve PDF artifact metadata and download exact stored bytes

## Role

You are implementing one bounded ASSAM_EXAM_AI task in the VS Code working tree. Read the repository before editing and follow `AGENTS.md`, `docs/architecture.md`, `docs/workflow.md`, `docs/task_log.md`, and this complete prompt.

Do not rely on handoff summaries when repository code differs. Preserve append-only history in `docs/task_log.md` and `docs/next_task.md`.

## Starting-state verification

Before editing:

1. Confirm branch `main` and a clean working tree.
2. Fetch and confirm `origin/main` is the documentation commit that approves T-042 and issues T-043.
3. Read the immutable T-042 implementation commit `e41ab090ee9b715e473a72c25474f8ca58deb424` and its base `896cc7069a70faf1af31c37824019bcf2ffc6c1b`.
4. Read the current PdfArtifact model, ContentDocument relationship, migration `e7b4c9d2a615`, schemas, knowledge repository/service/routes, deterministic renderer, and focused PDF tests.
5. Verify Alembic has one head, expected to remain `e7b4c9d2a615`.
6. Stop and report any repository divergence that materially changes this task.

## Goal

Add internal, read-only access to one already persisted immutable PdfArtifact:

- retrieve its stored metadata by artifact ID;
- download its exact stored PDF bytes by artifact ID with correct HTTP headers.

This task exposes the artifact persisted by T-042. It must never regenerate, transform, repair, replace, approve, release, publish, or re-evaluate the artifact.

## Required API

Add exactly these endpoints under `/api/v1`:

1. `GET /pdf-artifacts/{pdf_artifact_id}`
   - Return HTTP 200 using the existing PdfArtifact metadata response contract.
   - Do not include raw `pdf_bytes` in JSON.

2. `GET /pdf-artifacts/{pdf_artifact_id}/download`
   - Return HTTP 200 with the exact stored `pdf_bytes`, byte-for-byte.
   - Set `Content-Type` from the stored media type, which T-042 constrains to `application/pdf`.
   - Set `Content-Length` to the stored positive byte size.
   - Set `Content-Disposition` to attachment using the exact stored deterministic filename.
   - Do not render, encode, decode, normalize, stream from another store, or recalculate the payload.

For either endpoint, a missing artifact must return exactly:

`404 PdfArtifact <id> not found`

Use the repository's established FastAPI detail shape and error translation.

Ensure the `/download` route cannot be captured by the metadata route. Keep routes thin:

`Route -> Schema/response adaptation -> Service -> Repository -> PostgreSQL`

## Read semantics and invariants

- Query by `PdfArtifact.id`, not by ContentDocument ID.
- Return the exact stored artifact even if its ContentDocument or ContentPackage is later withdrawn or otherwise changes state.
- Do not check current ContentDocument approval/release state, package state, member state, Claim state, Verification state, Topic priority, or a dynamic manifest.
- Do not load or lock ContentDocument, ContentPackage, package memberships, NoteDraft, QuestionBankItem, Claim, Evidence, Source, or Verification rows.
- Use a PdfArtifact-only read query with `no_autoflush` and no row locks.
- Perform no insert, update, delete, flush, commit, refresh, regeneration, checksum recalculation, or related-state evaluation.
- Preserve the exact stored ownership and metadata returned by T-042.
- Do not add an endpoint keyed by ContentDocument ID.

The service may use a small internal immutable value object for download data if that keeps HTTP response construction out of the repository. Do not expose raw bytes through a Pydantic metadata schema.

## Header safety

The stored filename is created internally by T-042 and constrained to a non-blank `.pdf` value. Build a standards-compatible attachment header without accepting any user-supplied filename in T-043.

Do not add range requests, conditional requests, caching policy, ETag behavior, inline disposition, filename overrides, streaming infrastructure, or content negotiation.

## Persistence and migration boundary

No model, model registration, database constraint, or Alembic migration should be required. Alembic head must remain `e7b4c9d2a615`.

Do not edit any historical migration. If implementation appears to require a schema change, stop and report why instead of expanding T-043.

## Repository and service behavior

Add the smallest repository lookup needed to load one PdfArtifact by ID. Reuse it from both service operations where cleanly possible.

Metadata retrieval must serialize stored metadata only. Download retrieval must carry the exact stored bytes plus only the stored metadata needed for response headers.

Missing artifacts use the stable 404 above. Do not translate unrelated database or programming errors into 404 or 409 responses.

## Tests

Add focused PostgreSQL-backed API/service/repository tests that prove at minimum:

- metadata retrieval returns every stored metadata field exactly and excludes raw bytes;
- download returns byte-for-byte identical stored PDF data;
- download headers have exact stored media type, byte size, and attachment filename;
- a missing artifact returns the stable 404 from both endpoints;
- metadata and download remain available and unchanged after the owning ContentDocument is withdrawn;
- changes to package/member/Claim/Verification or other upstream state do not affect stored retrieval;
- neither endpoint invokes the PDF renderer or recalculates SHA-256;
- reads use no `FOR UPDATE`, flush, commit, or writes;
- the repository issues only a PdfArtifact query and does not load related rows;
- route ordering keeps `/download` reachable;
- existing T-042 creation behavior and all earlier ContentDocument, ContentPackage, NoteDraft, QuestionBankItem, and released-asset boundaries remain compatible.

Use a dedicated PostgreSQL database whose name ends in `_test`. Do not substitute SQLite for PostgreSQL constraint/query behavior.

## Validation

Run and report:

- focused T-043 PdfArtifact retrieval/download tests;
- complete PdfArtifact tests, including T-042 creation tests;
- complete ContentPackage/ContentDocument tests;
- T-041 released-document tests;
- T-030 released-assets and ContentVersion tests;
- NoteDraft and released-NoteDraft tests;
- QuestionBankItem and released-QuestionBankItem tests;
- full suite;
- Ruff on every changed Python file;
- `uv lock --check` or the repository-equivalent lock verification;
- `uv run alembic heads`;
- `uv run alembic check`;
- a fresh upgrade through unchanged head `e7b4c9d2a615`;
- `git diff --check`;
- whitespace checks for every untracked file;
- final `git status --short`.

Report developer-run results accurately. Do not describe them as GitHub CI.

## Affected components

Inspect and modify only where required:

- shared PdfArtifact schemas only if the existing metadata response cannot be reused unchanged;
- knowledge repository;
- knowledge service;
- knowledge routes;
- focused PdfArtifact tests;
- `docs/architecture.md` and `docs/workflow.md` for implemented current state;
- append-only implementation records in `docs/task_log.md` and `docs/next_task.md`.

Inspect but leave unchanged unless a genuine inconsistency is found:

- all models and model registration;
- migration `e7b4c9d2a615` and every historical migration;
- deterministic PDF renderer;
- `pyproject.toml` and `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`; 
- `AGENTS.md`;
- `README.md`.

No dependency, API key, environment variable, secret, configuration value, Docker service, renderer change, or storage backend is required. Leave those files unchanged and explicitly report that.

## Scope exclusions

Do not add artifact listing; lookup by ContentDocument ID; artifact review/approval/release/withdrawal/publication lifecycle; public or learner access; object/file/blob/CDN storage; presigned URLs; range or conditional downloads; HTML artifacts; artifact update/delete/replacement/regeneration/repair; background jobs/queues; users/auth/history; AI/LLM/API keys/source discovery/ingestion/RAG/embeddings/scraping; mock assembly/sessions/scoring/analytics/recommendations/personalization; payments; production infrastructure; or T-044.

Preserve trust, provenance, exact ContentVersion ownership, immutable package/document/artifact snapshots, stored checksums, controlled release boundaries, deterministic reproducibility, and Generate Once/Personalize Later.

## Documentation and handoff

Document only behavior actually implemented. Keep `docs/task_log.md` and `docs/next_task.md` append-only. Record T-043 only as `Ready for review`; do not approve it and do not define or implement T-044.

Report:

- starting and final Git state;
- exact files changed;
- both endpoints and stable errors;
- repository query and no-lock/no-write behavior;
- exact byte and header evidence;
- independence from current related state;
- tests and validation results;
- unchanged migration/dependency/configuration/Docker state;
- explicit scope exclusions.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not implement or define T-044.

Leave T-043 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-09 Asia/Kolkata, UTC+05:30): added only `GET /api/v1/pdf-artifacts/{pdf_artifact_id}` and `GET /api/v1/pdf-artifacts/{pdf_artifact_id}/download`. Both resolve one artifact by its own ID through a PdfArtifact-only, no-autoflush, lock-free query. Metadata reuses the stored response and excludes raw bytes; download returns the exact persisted bytes with stored media type, size, and deterministic attachment filename. Missing artifacts use the stable 404, and later document withdrawal or unrelated upstream state changes do not affect retrieval. No rendering, hashing, related-state evaluation, write, model/schema/migration change, dependency, external storage, publication, learner delivery, AI, personalization, or T-044 work was added. T-043 is Ready for review, not approved; exact validation results are recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-043 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-043` |
| Implementation commit | `b6ef5943536380ed8cf18a09133ad5cd68f603ad` |
| Base/task-issuance commit | `45f4c71ed41d4dabc56278281182bed45d1800c0` |
| Review result | **APPROVED** |
| Approved capability | Read-only internal retrieval of one PdfArtifact's stored metadata and exact immutable PDF bytes by artifact ID, with stored headers and no regeneration or related-state evaluation |
| Independent review | The exact parent/diff, routes, response behavior, repository query, service boundary, tests, documentation, unchanged persistence/dependency/configuration files, and excluded scope were inspected. No blocking finding was identified. |
| CI evidence | GitHub exposes no status contexts or workflow runs for the implementation commit. Developer-recorded local validation is retained as evidence and is not described as CI. |

# T-044 — Add independent PdfArtifact human review

## Role

You are implementing one bounded ASSAM_EXAM_AI task in the VS Code working tree. Read the live repository before editing and follow `AGENTS.md`, `docs/architecture.md`, `docs/workflow.md`, `docs/task_log.md`, and this complete prompt.

Repository code is authoritative. Preserve the append-only history in `docs/task_log.md` and `docs/next_task.md`.

## Starting-state verification

Before editing:

1. Confirm branch `main`, fetch `origin/main`, and confirm a clean working tree.
2. Confirm the checked-out HEAD is the documentation commit that approves T-043 and issues T-044.
3. Confirm T-043 implementation commit `b6ef5943536380ed8cf18a09133ad5cd68f603ad` is its implementation ancestor and its exact base is `45f4c71ed41d4dabc56278281182bed45d1800c0`.
4. Read the current PdfArtifact and ContentDocument models, model registration, migration `e7b4c9d2a615`, PdfArtifact schemas, repository/service/routes, renderer, and complete PdfArtifact tests.
5. Inspect the existing independent human-review implementations for QuestionBankItem, NoteDraft, ContentPackage, and ContentDocument. Reuse established vocabulary and transition/error conventions where they remain correct.
6. Confirm Alembic currently has one head: `e7b4c9d2a615`.
7. Stop and report any repository divergence that materially changes this task.

## Objective

Add an independent human-review lifecycle to each immutable PdfArtifact:

`DRAFT -> APPROVED`
`DRAFT -> REJECTED`
`APPROVED or REJECTED -> DRAFT`
`APPROVED <-> REJECTED`

Review applies to the stored artifact itself. It must not mutate or regenerate its PDF bytes, filename, media type, byte size, checksum, document/package/ContentVersion ownership, or creation time.

Verification, upstream approval, ContentDocument release, and PdfArtifact human approval remain distinct concepts. Do not infer artifact approval from any upstream state.

## Data model and PostgreSQL invariants

Add PdfArtifact review fields consistent with the approved repository patterns:

- `approval_status`: non-null, default `DRAFT`, allowed values exactly `DRAFT`, `APPROVED`, `REJECTED`;
- `approval_decided_at`: timezone-aware nullable timestamp;
- `reviewer_note`: nullable text.

PostgreSQL must independently enforce:

- only the three allowed approval states;
- `DRAFT` requires `approval_decided_at IS NULL` and `reviewer_note IS NULL`;
- `APPROVED` and `REJECTED` require a non-null `approval_decided_at`;
- the existing immutable payload, ownership, uniqueness, byte-size, checksum, and deletion constraints remain intact.

Use explicit named constraints following repository conventions. Application validation complements these constraints; it does not replace them.

Existing PdfArtifact rows must migrate to `DRAFT` with null decision time and null reviewer note. Do not infer review from ContentDocument approval/release or any other related state.

## Migration

Add exactly one Alembic revision whose parent is `e7b4c9d2a615`.

The migration must:

- add only the T-044 review columns and constraints;
- preserve every existing artifact byte-for-byte, including exact ownership, filename, media type, byte size, SHA-256, and creation timestamp;
- seed existing rows only as `DRAFT`/null/null;
- use safe upgrade and downgrade ordering;
- downgrade by removing only T-044 constraints/columns;
- never edit a historical migration.

Validate a seeded cycle:

`e7b4c9d2a615 -> T-044 head -> e7b4c9d2a615 -> T-044 head`

Prove existing artifacts retain their exact pre-T-044 fields and return to DRAFT/null/null on each upgrade.

## API contract

Add exactly:

`POST /api/v1/pdf-artifacts/{pdf_artifact_id}/approval`

Request body:

```json
{
  "approval_status": "APPROVED",
  "reviewer_note": "Optional reviewer note"
}
```

Use the existing approval enum/schema conventions where appropriate. Do not create duplicate concepts merely to rename them.

Behavior:

- Missing artifact: HTTP 404 with exact detail `PdfArtifact <id> not found`.
- `DRAFT`: clear `approval_decided_at` and clear `reviewer_note`, regardless of request note.
- `APPROVED` or `REJECTED`: set `approval_decided_at` to the current UTC time and store the optional reviewer note.
- A repeated or changed decision is allowed and records a fresh decision time for non-DRAFT states.
- Return the complete stored PdfArtifact metadata response including the new review fields, never raw PDF bytes.
- Invalid approval values use the established request-validation response.

Keep the route thin:

`Route -> Pydantic schema -> Service -> Repository -> PostgreSQL`

## Locking and atomicity

The decision operation must:

- lock only the target PdfArtifact row with a narrowly scoped `FOR UPDATE OF pdf_artifacts` query;
- update only the three review fields;
- commit exactly once on success;
- roll back every failure;
- reload and return stored metadata after commit using the ordinary lock-free PdfArtifact lookup.

Do not lock or mutate ContentDocument, ContentPackage, memberships, NoteDraft, QuestionBankItem, Claim, Evidence, Source, Verification, Exam, SyllabusVersion, Topic, or ContentVersion.

Do not re-evaluate document/package/member/Claim/Verification/current-release state. A stored PdfArtifact can be reviewed even if related state later changes.

## Existing API compatibility

Extend the existing PdfArtifact metadata response additively with:

- `approval_status`;
- `approval_decided_at`;
- `reviewer_note`.

The following must continue working:

- T-042 creation still returns HTTP 201 metadata, now with `DRAFT`, null, null;
- T-043 metadata retrieval returns the stored review fields and no raw bytes;
- T-043 download returns the exact unchanged bytes and existing headers regardless of review state;
- missing retrieval/download errors remain unchanged.

Review status must not gate download in T-044. Release/publication is a separate future boundary.

## Repository and service requirements

Add the smallest repository method needed to lock one PdfArtifact by ID for a decision. Reuse the existing ordinary PdfArtifact lookup after commit.

Business transition behavior belongs in the service. Persistence query construction belongs in the repository. Do not place review logic in the route.

Use the repository's established failure handling. Do not translate unrelated database/programming errors into 404 or 409.

## Required tests

Add focused PostgreSQL-backed tests proving at minimum:

- newly created artifacts are `DRAFT` with null decision time/note;
- migrated existing artifacts become `DRAFT`/null/null without payload or ownership changes;
- APPROVED records UTC decision time and optional note;
- REJECTED records UTC decision time and optional note;
- resetting to DRAFT clears both decision time and note;
- switching/repeating non-DRAFT decisions records the requested state and a fresh decision time;
- missing artifact returns the stable 404;
- invalid status is rejected by request validation;
- only the target PdfArtifact is locked and only its three review fields change;
- successful review commits exactly once;
- persistence failure rolls back without a partial decision;
- related ContentDocument/package/member/Claim/Verification state is neither loaded, locked, changed, nor used for eligibility;
- artifact bytes, byte size, SHA-256, filename, media type, ownership, and creation time never change;
- metadata retrieval exposes stored review fields without bytes;
- download bytes and headers remain identical in DRAFT, APPROVED, and REJECTED states;
- direct PostgreSQL writes violating allowed-state or temporal/note consistency constraints fail;
- existing T-042 creation and T-043 retrieval/download tests remain valid;
- all earlier content and provenance boundaries remain compatible.

Use a dedicated PostgreSQL database whose name ends in `_test`. Do not use SQLite as a substitute for PostgreSQL behavior.

## Validation

Run and report:

- focused T-044 review tests;
- complete PdfArtifact suite, including T-042 and T-043;
- complete ContentPackage/ContentDocument suite;
- T-041 released-document tests;
- T-030 released-assets and ContentVersion tests;
- NoteDraft and released-NoteDraft tests;
- QuestionBankItem and released-QuestionBankItem tests;
- full test suite;
- Ruff on every changed Python file;
- `uv lock --check` or repository-equivalent lock verification;
- `uv run alembic heads`;
- `uv run alembic check`;
- fresh upgrade through the new head;
- seeded upgrade/downgrade/re-upgrade evidence;
- direct PostgreSQL constraint probes;
- `git diff --check`;
- whitespace checks for every untracked file;
- final `git status --short`.

Confirm one Alembic head whose parent is `e7b4c9d2a615`, no schema drift, no historical migration edit, and no unrelated dependency/configuration/infrastructure change.

## Affected components

Inspect and modify only where required:

- PdfArtifact model;
- shared PdfArtifact/approval schemas;
- model metadata/registration only if actually required;
- knowledge repository;
- knowledge service;
- knowledge routes;
- exactly one new migration;
- focused PdfArtifact tests;
- `docs/architecture.md` and `docs/workflow.md` for implemented current state;
- append-only implementation records in `docs/task_log.md` and `docs/next_task.md`.

Inspect and leave unchanged unless a genuine inconsistency requires otherwise:

- ContentDocument, ContentPackage, membership, NoteDraft, QuestionBankItem, Claim, Evidence, Verification, exam/syllabus/topic models;
- deterministic PDF renderer;
- every historical migration;
- `pyproject.toml` and `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

No new dependency, API key, environment variable, secret, configuration value, Docker service, renderer change, external storage, or infrastructure is required. Leave those files unchanged and explicitly report that.

## Scope exclusions

Do not add PdfArtifact release/withdrawal/publication lifecycle; released/approved artifact collections; public/learner APIs; authentication; ContentDocument-keyed artifact lookup; artifact list; object/file/blob/CDN storage; presigned URLs; range/conditional requests; artifact update/delete/replacement/regeneration/repair; HTML artifacts; background jobs/queues; AI/LLM/API keys/source discovery/ingestion/RAG/embeddings/scraping; mock assembly/sessions/scoring/analytics/recommendations/personalization; payments; production infrastructure; end-to-end public delivery; or T-045.

Do not make artifact approval automatic. Human review is an explicit trust boundary.

## Documentation and handoff

Document only implemented behavior. Keep `docs/task_log.md` and `docs/next_task.md` append-only. Record T-044 only as `Ready for review`; do not approve it and do not define or implement T-045.

Report:

- starting and final Git state;
- exact files changed;
- migration revision and parent;
- model fields and PostgreSQL constraints;
- endpoint, request/response, and stable errors;
- locking, one-commit atomicity, and rollback behavior;
- immutable payload/ownership evidence;
- migration cycle and direct constraint evidence;
- focused/regression/full-suite results;
- unchanged dependencies/configuration/Docker/renderer state;
- explicit excluded scope.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not define or implement T-045.

Leave T-044 uncommitted and unpushed in the working tree for independent review.

Implementation note (2026-09-10 Asia/Kolkata, UTC+05:30): added only independent PdfArtifact DRAFT/APPROVED/REJECTED review metadata and `POST /api/v1/pdf-artifacts/{pdf_artifact_id}/approval`. Migration `f3c8a1d6e924` follows `e7b4c9d2a615` and migrates existing artifacts to DRAFT/null/null without inference or payload change. Decisions lock only the target artifact, update only review metadata, commit once, roll back failures, and reload stored metadata; DRAFT clears decision metadata while APPROVED/REJECTED record current UTC and an optional note. Exact bytes, checksum, ownership, creation metadata, retrieval, and ungated download remain unchanged. T-044 is Ready for review, not approved. No artifact release/list, publication, storage, learner, AI, personalization, dependency, configuration, Docker, or T-045 work was added; exact validation is recorded in `docs/task_log.md` and `docs/workflow.md`.


---

# T-044 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-044` |
| Issuance base | `f2f2e36dc8fae2c2008c3a457ce7a4d6b6a23612` |
| Implementation commit | `b8f519a1ed5adf017767562f78ae168226c300e6` |
| Test-correction commit | `592847b89b86bf0f9a744280dfa455562cefb70a` |
| Review result | **APPROVED** |
| Approved capability | Independent, atomic DRAFT/APPROVED/REJECTED human review of one immutable PdfArtifact with PostgreSQL lifecycle protection and target-only locking |
| Independent review | The complete two-commit range was inspected. The correction changes only the focused PdfArtifact test file and closes the target-only SQL and post-flush rollback coverage gaps. No blocking finding remains. |
| CI evidence | GitHub exposes no status contexts or workflow runs. Recorded local validation is developer evidence, not a claimed CI pass. |

# T-045 — Add controlled PdfArtifact release lifecycle

## Role

You are implementing one bounded ASSAM_EXAM_AI task in the VS Code working tree. Read the live repository before editing and follow `AGENTS.md`, `docs/architecture.md`, `docs/workflow.md`, `docs/task_log.md`, and this complete prompt.

Repository code is authoritative. Preserve the append-only history in `docs/task_log.md` and `docs/next_task.md`.

## Starting-state verification

Before editing:

1. Confirm branch `main`, fetch `origin/main`, and confirm a clean working tree.
2. Confirm HEAD is the documentation commit that approves T-044 and issues T-045.
3. Confirm the approved T-044 range consists of issuance base `f2f2e36dc8fae2c2008c3a457ce7a4d6b6a23612`, implementation `b8f519a1ed5adf017767562f78ae168226c300e6`, and correction `592847b89b86bf0f9a744280dfa455562cefb70a`.
4. Read PdfArtifact, its migrations, schemas, repository/service/routes, complete tests, and the approved ContentPackage and ContentDocument release implementations.
5. Confirm Alembic has one head: `f3c8a1d6e924`.
6. Stop and report repository divergence that materially changes this task.

## Objective

Add a controlled release lifecycle to the already immutable and independently reviewed PdfArtifact:

`UNRELEASED -> RELEASED -> WITHDRAWN`

Release is distinct from human approval. Initial release requires the PdfArtifact's own current approval state to be APPROVED. Do not infer artifact release from ContentDocument, ContentPackage, member, Claim, or Verification state.

Withdrawal is terminal for that artifact version. A withdrawn artifact cannot be re-released in place.

## Data model and PostgreSQL invariants

Add these PdfArtifact fields following established repository conventions:

- `release_status`: non-null, default `UNRELEASED`, allowed values exactly `UNRELEASED`, `RELEASED`, `WITHDRAWN`;
- `released_at`: timezone-aware nullable timestamp;
- `withdrawn_at`: timezone-aware nullable timestamp;
- `release_note`: nullable text.

PostgreSQL must independently enforce:

- only the three allowed release states;
- `UNRELEASED` requires `released_at IS NULL`, `withdrawn_at IS NULL`, and `release_note IS NULL`;
- `RELEASED` requires `released_at IS NOT NULL`, `withdrawn_at IS NULL`, and `approval_status = 'APPROVED'`;
- `WITHDRAWN` requires `released_at IS NOT NULL` and `withdrawn_at IS NOT NULL`;
- existing approval, ownership, uniqueness, byte-size, checksum, filename/media, and deletion invariants remain intact.

Use explicit named constraints. Application checks complement PostgreSQL; they do not replace it.

Existing PdfArtifact rows must migrate to UNRELEASED/null/null/null. Do not infer release from approval or related state.

## Migration

Add exactly one Alembic revision whose parent is `f3c8a1d6e924`.

The migration must add only the T-045 release fields and named constraints, preserve all existing artifact review and immutable fields exactly, and safely remove only T-045 objects on downgrade. Never edit a historical migration.

Validate a seeded cycle:

`f3c8a1d6e924 -> T-045 head -> f3c8a1d6e924 -> T-045 head`

Prove exact bytes, byte size, checksum, filename, media type, ownership, creation time, approval status/time/note remain unchanged and every upgrade produces UNRELEASED/null/null/null without inferred release.

## API contract

Add exactly:

`POST /api/v1/pdf-artifacts/{pdf_artifact_id}/release`

Request body:

```json
{
  "release_status": "RELEASED",
  "release_note": "Optional release note"
}
```

Accepted decisions are only RELEASED and WITHDRAWN.

Required behavior:

- Missing artifact: HTTP 404 with exact detail `PdfArtifact <id> not found`.
- `UNRELEASED -> RELEASED`: require the artifact's own `approval_status == APPROVED`; set current UTC `released_at`, keep `withdrawn_at` null, and store the optional release note.
- Non-approved initial release: HTTP 409 with exact detail `PdfArtifact <id> must be approved before release`.
- `RELEASED -> WITHDRAWN`: preserve the original `released_at`, set current UTC `withdrawn_at`, and replace the release note with the request note.
- Every other transition, including RELEASED to RELEASED, UNRELEASED to WITHDRAWN, and any transition from WITHDRAWN: HTTP 409 with exact detail `PdfArtifact <id> cannot transition from <current> to <requested>`.
- Invalid decision values use the established 422 validation response.
- Return complete stored PdfArtifact metadata including review and release fields; never return raw bytes.

Keep routes thin:

`Route -> Pydantic schema -> Service -> Repository -> PostgreSQL`

## Approval/release interaction

Update the existing PdfArtifact approval operation so that a currently RELEASED artifact cannot be reset to DRAFT or changed to REJECTED.

That conflict must return HTTP 409 with exact detail:

`PdfArtifact <id> must be withdrawn before changing approval`

Repeating APPROVED while RELEASED may remain allowed and must preserve a database-valid RELEASED state. Once WITHDRAWN, review changes may again follow the approved T-044 behavior.

Use the same target PdfArtifact lock for approval decisions. Do not introduce a second related-state query.

## Locking and atomicity

Release and conflicting approval operations must:

- lock only the target PdfArtifact row with `FOR UPDATE OF pdf_artifacts`;
- update only appropriate artifact lifecycle fields;
- commit exactly once on success;
- roll back every failure;
- reload stored metadata using the ordinary lock-free artifact lookup after commit.

Do not lock, load, or mutate ContentDocument, ContentPackage, memberships, NoteDraft, QuestionBankItem, Claim, Evidence, Verification, Exam, SyllabusVersion, Topic, or ContentVersion.

Failed transitions must not alter review, release, immutable payload, ownership, or related state.

## Existing API compatibility

Extend `PdfArtifactResponse` additively with:

- `release_status`;
- `released_at`;
- `withdrawn_at`;
- `release_note`.

Preserve:

- T-042 creation returns DRAFT review plus UNRELEASED/null/null/null release metadata;
- T-043 metadata returns stored review and release metadata without raw bytes;
- T-043 internal download continues returning exact stored bytes and existing headers regardless of review/release state;
- T-044 review transitions except the required currently-RELEASED conflict;
- all established missing errors and existing APIs.

Do not gate the existing internal download by release state in T-045. A released-only delivery boundary is a separate future task.

## Repository and service requirements

Reuse the existing target PdfArtifact `FOR UPDATE` lookup for release and approval decisions. Add only the smallest update method needed for release fields.

Business transition checks belong in the service. Persistence query construction and field assignment belong in the repository. Do not put lifecycle logic in routes.

Do not translate unrelated database/programming errors into 404 or 409.

## Required tests

Add focused PostgreSQL-backed tests proving at minimum:

- new and migrated artifacts are UNRELEASED/null/null/null without inferred release;
- an APPROVED UNRELEASED artifact can become RELEASED with UTC timestamp and optional note;
- DRAFT and REJECTED artifacts cannot be initially released;
- RELEASED becomes WITHDRAWN while preserving `released_at`, setting UTC `withdrawn_at`, and replacing the note;
- no-op, skipped, reverse, and post-withdrawal re-release transitions return exact stable 409 details and change nothing;
- missing and invalid requests return stable 404/422 behavior;
- while RELEASED, DRAFT/REJECTED approval changes return the exact conflict and do not mutate state;
- repeating APPROVED while RELEASED remains database-valid if supported;
- after withdrawal, approved T-044 review changes remain available;
- release and approval lock only the target PdfArtifact and access no related tables;
- success commits exactly once; injected failure after a flushed release UPDATE rolls back exactly once with no partial state;
- a second PdfArtifact and all related rows remain unchanged;
- direct PostgreSQL writes violating release values or lifecycle/approval consistency fail under named constraints;
- immutable bytes, checksum, byte size, filename, media type, ownership, creation time, and review metadata remain protected except for an explicitly requested review decision;
- metadata retrieval exposes stored release fields without bytes;
- internal download bytes and headers remain exact in UNRELEASED, RELEASED, and WITHDRAWN states;
- T-042 creation, T-043 retrieval/download, T-044 review, migration, and earlier content/provenance regressions remain compatible.

Use a dedicated PostgreSQL database whose name ends in `_test`. Do not substitute SQLite.

## Validation

Run and report:

- focused T-045 release tests;
- complete PdfArtifact suite;
- complete ContentPackage/ContentDocument suite;
- T-041 released-document tests;
- T-030 released-assets and ContentVersion tests;
- NoteDraft and released-NoteDraft tests;
- QuestionBankItem and released-QuestionBankItem tests;
- full suite;
- Ruff on all changed Python;
- `uv lock --check` or repository-equivalent verification;
- `uv run alembic heads`;
- `uv run alembic check`;
- fresh upgrade through the new head;
- seeded upgrade/downgrade/re-upgrade;
- direct PostgreSQL constraint probes;
- `git diff --check`;
- whitespace checks for every untracked file;
- final `git status --short`.

Confirm one Alembic head whose parent is `f3c8a1d6e924`, no schema drift, no historical migration edit, and no unrelated dependency/configuration/infrastructure change.

## Affected components

Inspect and modify only where required:

- PdfArtifact model;
- PdfArtifact release schemas and additive response fields;
- model registration only if genuinely required;
- knowledge repository;
- knowledge service, including the released-approval conflict;
- knowledge routes;
- exactly one migration;
- focused PdfArtifact tests;
- `docs/architecture.md` and `docs/workflow.md` for implemented current state;
- append-only implementation records in `docs/task_log.md` and `docs/next_task.md`.

Inspect and leave unchanged unless a genuine inconsistency requires otherwise:

- ContentDocument, ContentPackage, memberships, NoteDraft, QuestionBankItem, Claim, Evidence, Verification, Exam, SyllabusVersion, Topic, and ContentVersion models;
- deterministic PDF renderer;
- historical migrations;
- `pyproject.toml` and `uv.lock`;
- `.env.example`;
- `app/core/config.py`;
- `docker-compose.yml`;
- `AGENTS.md`;
- `README.md`.

No dependency, API key, environment variable, secret, configuration value, Docker service, renderer change, external storage, or infrastructure is required. Leave these files unchanged and report that.

## Scope exclusions

Do not add a released/approved artifact collection; released-only download endpoint; publication record; public/learner access; authentication; ContentDocument-keyed artifact lookup; artifact list; object/file/blob/CDN storage; presigned URLs; range/conditional requests; artifact update/delete/replacement/regeneration/repair; HTML artifacts; background jobs/queues; AI/LLM/API keys/source discovery/ingestion/RAG/embeddings/scraping; mock assembly/sessions/scoring/analytics/recommendations/personalization; payments; production infrastructure; or T-046.

Human approval and release remain explicit separate trust boundaries. Do not automatically publish or expose an artifact because it is approved or released.

## Documentation and handoff

Document only implemented behavior. Keep `docs/task_log.md` and `docs/next_task.md` append-only. Record T-045 only as `Ready for review`; do not approve it and do not define or implement T-046.

Report:

- starting/final Git state and exact files;
- migration revision and parent;
- fields and PostgreSQL constraints;
- endpoint, transitions, timestamps, notes, and exact errors;
- approval/release interaction;
- target-only locking, commit/rollback, and state preservation;
- migration-cycle and direct-constraint evidence;
- focused/regression/full-suite validation;
- unchanged dependencies/configuration/Docker/renderer state;
- explicit exclusions.

Do not commit.
Do not push.
Do not create a PR.
Do not self-approve.
Do not define or implement T-046.

Leave T-045 uncommitted and unpushed in the working tree for independent review.