# Assam Exam AI — Task Log

## Register rules

This is an append-only task register. Add new entries without deleting or rewriting historical entries. Record test results and commit identifiers only when evidence is available.

## Entries

### T-001 — Documentation workflow baseline

| Field | Value |
| --- | --- |
| Issued | 2026-09-02 |
| Status | Approved |
| Prompt source | User request and supplied `architecture.md`, `workflow.md`, `task_log.md`, and `next_task.md`; supplied documents treated as reference content |
| Scope | Add the four living documentation files only |
| Tests | Not run; documentation-only task |
| Checks | `git diff --check` and `git status --short` required before handoff |
| Implementation commit | `de55bb16dd7d3a8a0a276812d1cddf35abb3ba9c` |
| Documentation-review commit | `de55bb16dd7d3a8a0a276812d1cddf35abb3ba9c` |
| Review result | Approved |
| Notes | No application code, models, migrations, dependencies, or tests may change in T-001 |

### T-002 — Record verification evidence provenance

| Field | Value |
| --- | --- |
| Issued | 2026-09-02 |
| Status | Ready for review |
| Prompt source | `docs/next_task.md` (T-002) |
| Scope | Add only the ordered Verification → Evidence audit link, constraints, migration, ORM traversal, and PostgreSQL-backed tests |
| Tests | `uv run pytest tests/test_verification_evidence.py -q`: 5 passed in 0.61s on the final review run. `uv run pytest -q`: 9 passed in 0.87s with one Starlette deprecation warning. |
| Migration checks | Dedicated `assam_exam_ai_t002_test`: upgrade, downgrade to `774778a8bb78`, re-upgrade, and `uv run alembic check` all exited 0; metadata produced no new operations |
| Lint | Changed-file Ruff check passed. `uv run ruff check .` failed with 12 pre-existing findings outside T-002. |
| Implementation commit | Pending — user requested no commit |
| Documentation-review commit | Pending |
| Review result | Pending |
| Notes | PostgreSQL restricts deletion of evidence referenced by a verification; Verification deletion removes only its audit-link rows. No APIs, ingestion, embeddings, LLMs, review workflow, content generation, or PDF behavior added. |

## Entry template

```markdown
### T-XXX — Short task title

| Field | Value |
| --- | --- |
| Issued | `<YYYY-MM-DD>` |
| Status | Ready / Implementing / Ready for review / Approved / Blocked |
| Prompt source | `docs/next_task.md` at `<commit SHA>` or other explicit source |
| Scope | Short description |
| Tests | Required commands and exact results, or Not run with reason |
| Implementation commit | `<full SHA>` or Pending |
| Documentation-review commit | `<full SHA>` or Pending |
| Review result | Approved / Changes requested / Blocked / Pending |
| Notes | Assumptions, risks, and follow-up |
```
