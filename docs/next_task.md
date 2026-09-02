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
