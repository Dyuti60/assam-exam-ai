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
