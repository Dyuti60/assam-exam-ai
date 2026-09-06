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
