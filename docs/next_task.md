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
