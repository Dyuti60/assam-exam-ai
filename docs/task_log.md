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
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-002) |
| Scope | Add only the ordered Verification → Evidence audit link, constraints, migration, ORM traversal, and PostgreSQL-backed tests |
| Tests | `uv run pytest tests/test_verification_evidence.py -q`: 5 passed in 0.61s on the final review run. `uv run pytest -q`: 9 passed in 0.87s with one Starlette deprecation warning. |
| Migration checks | Dedicated `assam_exam_ai_t002_test`: upgrade, downgrade to `774778a8bb78`, re-upgrade, and `uv run alembic check` all exited 0; metadata produced no new operations |
| Lint | Changed-file Ruff check passed. `uv run ruff check .` failed with 12 pre-existing findings outside T-002. |
| Implementation commit | `e8d553a8816ba5d3968b96998caa8d6e9e507f99` |
| Documentation-review commit | This documentation update |
| Review result | Approved |
| Notes | PostgreSQL restricts deletion of evidence referenced by a verification; Verification deletion removes only its audit-link rows. No APIs, ingestion, embeddings, LLMs, review workflow, content generation, or PDF behavior added. |

### T-003 — Minimal end-to-end knowledge API

| Field | Value |
| --- | --- |
| Issued | 2026-09-03 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-003) and the user implementation request |
| Scope | Manual API flow from Source to Evidence to Claim to Verification with returned provenance |
| Tests | `uv run pytest tests/test_knowledge_api.py -q`: 4 passed in 0.74s with one Starlette deprecation warning. `uv run pytest -q`: 13 passed in 0.87s with the same warning. |
| Lint | Changed-file Ruff check passed. |
| Migration checks | No database schema migration required; existing migrations upgraded a fresh `assam_exam_ai_t003_test` database to head successfully. |
| Implementation commit | `603bddf260e9016e2db9215aec831ece7f018b50` |
| Documentation-review commit | This post-push documentation update |
| Review result | Approved |
| Notes | Added five internal API endpoints with schemas, repository, service, clear 404s, and request validation. Review coverage proves a missing Evidence reference creates neither a Verification nor an audit link. This is not an AI, ingestion, review, learner, or PDF feature. |

### T-004 — Synchronize Claim verification summary

| Field | Value |
| --- | --- |
| Issued | 2026-09-04 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-004) |
| Scope | Keep the Claim's current verification summary in sync when a new Verification is recorded |
| Tests | `uv run pytest tests/test_knowledge_api.py -q`: 4 passed in 1.17s with one Starlette deprecation warning on the final run. `uv run pytest -q`: 13 passed in 1.35s with the same warning. |
| Lint | Changed-file Ruff check passed. |
| Migration checks | No database schema migration required; existing migrations upgraded a fresh `assam_exam_ai_t004_test` database to head successfully. |
| Implementation commit | `e2f9d170c335f5ab9037749654bba9edb77938ba` |
| Documentation-review commit | This post-push documentation update |
| Review result | Approved |
| Notes | Verification creation now updates the Claim's latest verdict, confidence, and verification time in the same transaction. Failure leaves the summary unchanged. This summary is not human approval. |

### T-005 — Retrieve a Claim summary

| Field | Value |
| --- | --- |
| Issued | 2026-09-04 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-005) |
| Scope | Add one internal read endpoint for a Claim and its current latest-verification summary |
| Tests | `uv run pytest tests/test_knowledge_api.py -q`: 5 passed in 1.51s with one Starlette deprecation warning. `uv run pytest -q`: 14 passed in 1.01s with the same warning. |
| Lint | Changed-file Ruff check passed. |
| Migration checks | No database schema migration required; existing migrations upgraded a fresh `assam_exam_ai_t005_test` database to head successfully. |
| Implementation commit | `af76073a5ece57187f14540b519ec9606c2947a3` |
| Documentation-review commit | This post-push documentation update |
| Review result | Approved |
| Notes | Added only `GET /api/v1/claims/{claim_id}` through the existing route/service/repository layers, with success and missing-Claim API coverage. It returns the latest-verification summary, not Verification history or human approval. |

### T-006 — Link a Claim to relevant Evidence

| Field | Value |
| --- | --- |
| Issued | 2026-09-04 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-006) |
| Scope | Record Evidence relevant to a Claim separately from Verification audit evidence |
| Tests | Initial T-006 run: 7 focused and 16 full tests passed. Concurrency-correction run: `uv run pytest tests/test_knowledge_api.py -q`: 8 passed in 1.04s with one Starlette deprecation warning; `uv run pytest -q`: 17 passed in 1.10s with the same warning. |
| Lint | Changed-file Ruff check passed. |
| Migration checks | No database schema migration required. Initial T-006 checks upgraded `assam_exam_ai_t006_test` to head with no Alembic changes; the correction's `uv run alembic check` against `assam_exam_ai_t006_correction_test` exited 0 with no new upgrade operations detected. |
| Implementation commit | `0a335483285835db8d9d3a76180c02ba4dad91e2` |
| Documentation-review commit | This post-push documentation update |
| Review result | Approved |
| Notes | Added one Claim-to-Evidence link endpoint and stable ID-only retrieval, separate from Verification audit evidence. Idempotency under concurrent requests is guaranteed by the database composite key plus PostgreSQL `ON CONFLICT DO NOTHING`; the response uses a fresh eager reload. |

### T-007 — Retrieve an Evidence record

| Field | Value |
| --- | --- |
| Issued | 2026-09-04 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-007) |
| Scope | Add one internal Evidence read endpoint so linked evidence IDs can be inspected |
| Tests | `uv run pytest tests/test_knowledge_api.py -q`: 10 passed in 0.93s with one Starlette deprecation warning. `uv run pytest -q`: 19 passed in 1.00s with the same warning. |
| Lint | Changed-file Ruff check passed. |
| Migration checks | No database schema migration required; existing migrations upgraded a fresh `assam_exam_ai_t007_test` database to head, and `uv run alembic check` reported no new upgrade operations. |
| Implementation commit | `fbb1555acfecdc0942c032727684bce9d5e1e3a5` |
| Documentation-review commit | This post-push documentation update |
| Review result | Approved |
| Notes | Added only `GET /api/v1/evidence/{evidence_id}` through the existing layers, returning `EvidenceResponse` with clear missing-Evidence handling. |

### T-008 — Add Claim human approval state

| Field | Value |
| --- | --- |
| Issued | 2026-09-04 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-008) |
| Scope | Add an explicit human approval decision separate from verification |
| Tests | Initial run: `uv run pytest tests/test_knowledge_api.py -q`: 16 passed in 1.02s; `uv run pytest -q`: 25 passed in 1.10s. Consistency correction: focused suite passed 17 tests in 1.29s; full suite passed 26 tests in 1.23s. Each successful run emitted one Starlette deprecation warning. An intervening full-suite invocation with `DEBUG=false` produced 1 failed and 25 passed because the existing configuration test expects the development value `true`; rerunning with `DEBUG=true` passed. |
| Lint | Changed-file Ruff check passed for both the initial implementation and consistency correction. |
| Migration checks | Initial fresh `assam_exam_ai_t008_test` upgrade, downgrade to `92b13f7c4e61`, and re-upgrade exited 0; a pre-existing Claim received `DRAFT` with null decision timestamp/note. For the correction, fresh `assam_exam_ai_t008_correction_test` upgrade to `c31a8f4d2b90` exited 0 and `uv run alembic check` reported no new upgrade operations. |
| Implementation commit | `262bb7db9226ef31f7d9e61e9c7323f9cbd512a8` |
| Documentation-review commit | This post-push documentation update |
| Review result | Approved |
| Notes | Added a constrained human approval state separate from verification, one decision endpoint, and Claim response fields. APPROVED/REJECTED record the current UTC decision time and supplied note; DRAFT clears both decision fields. Verification never changes approval state. No authentication, reviewer identity, decision history, AI, or content generation was added. |

### T-009 — Read approved knowledge

| Field | Value |
| --- | --- |
| Issued | 2026-09-04 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-009) |
| Scope | Return only human-approved Claims as safe future content input |
| Tests | `uv run pytest tests/test_knowledge_api.py -q`: 19 passed in 1.23s with one Starlette deprecation warning. `uv run pytest -q`: 28 passed in 1.62s with the same warning. |
| Lint | Changed-file Ruff check passed. |
| Migration checks | No database schema migration required. Fresh `assam_exam_ai_t009_test` upgrade to `c31a8f4d2b90` exited 0; `uv run alembic check` reported no new upgrade operations. |
| Implementation commit | Pending |
| Documentation-review commit | Pending |
| Review result | Pending |
| Notes | Added only `GET /api/v1/claims/approved`. PostgreSQL filters to `APPROVED` and orders by Claim ID; responses reuse `ClaimResponse` with relevant Evidence IDs and verification/approval summaries. No content generation was added. |

### T-010 — Add a Topic to Claims

| Field | Value |
| --- | --- |
| Issued | 2026-09-04 Asia/Kolkata (UTC+05:30) |
| Status | Ready for VS Code Codex |
| Prompt source | `docs/next_task.md` (T-010) |
| Scope | Introduce minimal topic classification for future topic-based approved knowledge |
| Tests | API, migration, and PostgreSQL tests required |
| Implementation commit | Pending |
| Documentation-review commit | Pending |
| Review result | Pending |
| Notes | No hierarchy or syllabus integration yet. |

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
