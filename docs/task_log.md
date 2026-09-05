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
| Implementation commit | `1a8a1ed15a94c128c7fb89442aee605d3263cbf6` |
| Documentation-review commit | This post-push documentation update |
| Review result | Approved |
| Notes | Added only `GET /api/v1/claims/approved`. PostgreSQL filters to `APPROVED` and orders by Claim ID; responses reuse `ClaimResponse` with relevant Evidence IDs and verification/approval summaries. No content generation was added. |

### T-010 — Add a Topic to Claims

| Field | Value |
| --- | --- |
| Issued | 2026-09-04 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-010) |
| Scope | Introduce minimal topic classification for future topic-based approved knowledge |
| Tests | Initial T-010 run: 22 focused and 31 full tests passed. Duplicate-Topic correction: `uv run pytest tests/test_knowledge_api.py -q`: 23 passed in 1.54s with one Starlette deprecation warning; `uv run pytest -q`: 32 passed in 1.41s with the same warning. |
| Lint | Changed-file Ruff check passed for the initial implementation and duplicate-Topic correction. |
| Migration checks | Fresh `assam_exam_ai_t010_test` upgrade through `e4a6c8d1f203`, downgrade to `c31a8f4d2b90`, and re-upgrade exited 0. A pre-existing Claim retained null `topic_id`; downgrade removed `topics` and `claims.topic_id`. `uv run alembic check` reported no new upgrade operations. |
| Implementation commit | Pending |
| Documentation-review commit | Pending |
| Review result | Pending |
| Notes | Added one minimal unique-name Topic model/endpoint and nullable Claim assignment with clear missing-Topic handling. PostgreSQL remains the concurrency-safe unique-name authority; duplicate API creation rolls back and returns HTTP 409 with a stable detail. Topic deletion sets Claim references to null. No hierarchy, syllabus, search, or content generation was added. |

### T-011 — Read approved knowledge by Topic

| Field | Value |
| --- | --- |
| Issued | 2026-09-04 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-011) |
| Scope | Read only approved Claims for one Topic as future generation input |
| Tests | `uv run pytest tests/test_knowledge_api.py -q`: 26 passed in 2.23s with one Starlette deprecation warning. `uv run pytest -q`: 35 passed in 1.48s with the same warning. |
| Lint | Changed-file Ruff check passed. |
| Migration checks | No database schema migration required. Fresh `assam_exam_ai_t011_test` upgrade through `e4a6c8d1f203` exited 0; `uv run alembic check` reported no new upgrade operations. |
| Implementation commit | `209ea1678136030ba340b243c3735d1a9f65ee67` |
| Documentation-review commit | Review update series beginning `d2facb1af10826c5d79ce0e5bc99cd713c1d35be` |
| Review result | Approved |
| Notes | Added only the Topic-scoped approved Claim read. It distinguishes missing Topic from an empty result, filters exact Topic plus `APPROVED`, orders by Claim ID, and eagerly loads relevant Evidence. No generation or other Topic endpoint was added. |

### T-012 — Internal deterministic Topic note draft

| Field | Value |
| --- | --- |
| Issued | 2026-09-04 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-012) |
| Scope | Produce one non-persistent internal note draft using only one Topic's approved Claims |
| Tests | `uv run pytest tests/test_knowledge_api.py -q`: 29 passed in 1.33s with one Starlette deprecation warning. `uv run pytest -q`: 38 passed in 1.62s with the same warning. |
| Lint | Changed-file Ruff check passed. |
| Migration checks | No database schema migration required. Upgrade to existing head `e4a6c8d1f203` exited 0 on `assam_exam_ai_t012_test`; `uv run alembic check` reported no new upgrade operations. |
| Implementation commit | `1c33a89056eda9b04db2c71c9b60d17d3e8ccd0f` |
| Documentation-review commit | Review update series beginning `c0b2f17970c440f52070149b69a45f2fd0fe72b2` |
| Review result | Approved |
| Notes | Added one deterministic, non-persistent preview using only exact-Topic `APPROVED` Claims in ascending ID order. Missing Topic returns 404; no approved Claims returns the stable 409 detail. An initial check invocation used an outdated local database password and failed authentication before exercising the feature; rerunning with the repository-configured credential produced the recorded passing results. No LLM or publishing feature was added. |

### T-013 — Persist a Topic note draft with Claim provenance

| Field | Value |
| --- | --- |
| Issued | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-013) |
| Scope | Store a deterministic Topic note draft and the exact ordered approved Claims used to create it |
| Tests | Initial T-013 run: 4 focused tests passed in 0.85s and 42 full-suite tests passed in 1.63s. Duplicate-Claim constraint correction: `uv run pytest tests/test_note_drafts.py -q`: 4 passed in 0.87s with one Starlette deprecation warning; `uv run pytest -q`: 42 passed in 2.11s with the same warning. |
| Lint | Changed-file Ruff check passed. |
| Migration checks | Fresh upgrade through `b7d9e2f4a610` passed; downgrade to `e4a6c8d1f203` removed `note_drafts` and `note_draft_claims`; re-upgrade passed; `uv run alembic check` reported no new upgrade operations. |
| Implementation commit | `3aacf3d2b76098092cfae072c7cfa4ca40c88e3f` |
| Documentation-review commit | Review update series beginning `053f9354864fb6c3f533b55296e92d2620ea382c` |
| Review result | Approved |
| Notes | Added atomic storage of deterministic internal Markdown and exact ordered approved-Claim provenance. PostgreSQL enforces non-negative unique positions and unique draft/Claim pairs; the correction explicitly tests that the composite primary key rejects reuse of the same Claim at a different valid position. Referenced Topics and Claims are protected from deletion. Drafts have no approval/publish field and are not learner-ready. One initial downgrade invocation was rejected before migration execution because ambient `DEBUG=release` was not a valid boolean; the complete migration cycle was rerun successfully with `DEBUG=true`. |

### T-014 — Retrieve a stored internal note draft

| Field | Value |
| --- | --- |
| Issued | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-014) |
| Scope | Retrieve one stored internal NoteDraft with its exact ordered Claim provenance |
| Tests | `uv run pytest tests/test_note_drafts.py -q`: 6 passed in 1.01s with one Starlette deprecation warning. `uv run pytest -q`: 44 passed in 1.92s with the same warning. |
| Lint | Changed-file Ruff check passed. |
| Migration checks | No database schema migration required. Fresh upgrade through existing head `b7d9e2f4a610` passed; `uv run alembic check` reported no new upgrade operations. |
| Implementation commit | `c595da4e9ce8aedd60bf0f881d9bb59c6618881d` |
| Documentation-review commit | Review update series beginning `6e37789e74fb65a7f02c77e355690da2fdf5ee58` |
| Review result | Approved |
| Notes | Added eager, read-only retrieval of stored Markdown and position-ordered Claim IDs. The response remains unchanged after a linked Claim's approval state changes because retrieval does not regenerate or re-evaluate current approval. No edit, delete, approval, publication, or generation behavior was added. |

### T-015 — Add human approval state to NoteDrafts

| Field | Value |
| --- | --- |
| Issued | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Status | Approved |
| Prompt source | `docs/next_task.md` (T-015) |
| Scope | Record an explicit human decision on one stored internal NoteDraft |
| Tests | `uv run pytest tests/test_note_drafts.py -q`: 12 passed in 1.31s with one Starlette deprecation warning. `uv run pytest -q`: 50 passed in 2.10s with the same warning. |
| Lint | Changed-file Ruff check passed. |
| Migration checks | `d4f8a1c7e592` upgrade gave an existing draft `DRAFT` with null decision metadata; downgrade to `b7d9e2f4a610` removed the three fields; re-upgrade passed; `uv run alembic check` reported no new upgrade operations. |
| Implementation commit | `811f10af3ee63a22e253ff24e9450770e2cbbbc2` |
| Documentation-review commit | Review update series beginning `f99cb6e278e873e21d0f27e0be448ce3b2028f69` |
| Review result | Approved |
| Notes | Added a separate NoteDraft decision with APPROVED/REJECTED timestamp and note semantics plus DRAFT reset clearing. Tests confirm stored Markdown/provenance and Claim approval/verification state remain unchanged. This is human review without reviewer identity, history, or publication. |

### T-016 — Read approved internal note drafts

| Field | Value |
| --- | --- |
| Issued | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Status | Ready for review |
| Prompt source | `docs/next_task.md` (T-016) |
| Scope | Return only human-APPROVED stored NoteDraft snapshots for internal downstream use |
| Tests | `uv run pytest tests/test_note_drafts.py -q`: 14 passed in 1.35s with one Starlette deprecation warning. `uv run pytest -q`: 52 passed in 2.31s with the same warning. |
| Lint | Changed-file Ruff check passed. |
| Migration checks | No database schema migration required. Fresh dedicated `assam_exam_ai_t016_test` upgraded through existing head `d4f8a1c7e592`; `uv run alembic check` reported no new upgrade operations. |
| Implementation commit | Pending |
| Documentation-review commit | Pending |
| Review result | Pending |
| Notes | Added the static approved-NoteDraft read before the dynamic ID route. It filters on the draft's own approval only, orders by ID, eagerly loads Topic and stored Claim links, and returns stored snapshots without re-evaluating Claim approval. Approved means internally reviewed, not published or learner-visible. |

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


## T-016 approval record

| Field | Value |
| --- | --- |
| Recorded | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Original task entry | T-016 above |
| Final status | Approved |
| Implementation commit | `611fcb87b38b8506b1a509bea1c0abb4f581c5a7` |
| Documentation-review commit | Review update series beginning `985219af5d60d0e3b8b52ba83632b75057d3d4db` |
| Review result | Approved |
| Notes | The approved-draft boundary filters only on NoteDraft approval, keeps stable ID order, and returns immutable stored snapshots. It is not public release. |

## T-017 — Record sourced syllabus versions and Topics

| Field | Value |
| --- | --- |
| Issued | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Status | Ready for VS Code Codex |
| Prompt source | `docs/next_task.md` (T-017) |
| Scope | Establish exam and sourced syllabus-version data with ordered Topic mappings |
| Tests | PostgreSQL/API integration tests and migration checks required |
| Implementation commit | Pending |
| Documentation-review commit | Pending |
| Review result | Pending |
| Notes | This establishes relevance inputs only; it must not claim or calculate exam probability. |

### T-017 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Establish exam and sourced syllabus-version data with ordered Topic mappings |
| Tests | `uv run pytest tests/test_syllabus_api.py -q`: 15 passed in 1.33s with one Starlette deprecation warning. `uv run pytest -q`: 67 passed in 3.57s with the same warning. |
| Ruff | Changed-file Ruff check passed. |
| Migration checks | Fresh upgrade through `f6b3c9a2d741`, downgrade to `d4f8a1c7e592`, re-upgrade, and `uv run alembic check` passed; no new upgrade operations were detected. |
| Diff check | `git diff --check` passed. |
| Notes | Added only Exam identity and sourced, labeled SyllabusVersion records with non-empty ordered Topic provenance. Database restrictions protect referenced Exams, Sources, Topics, and mapped versions. This establishes relevance inputs only; no relevance, likelihood, probability, past-paper, or content behavior was added. |


## T-017 approval record

| Field | Value |
| --- | --- |
| Recorded | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Original task entry | T-017 above |
| Final status | Approved |
| Implementation commit | `e1aea55991671679d1666f4e472a6ad7425310df` |
| Documentation-review commit | Review update series beginning `f3436fb61aee2183f28333c76a227bc769bbe55a` |
| Review result | Approved |
| Notes | Exam identity and sourced syllabus versions with ordered Topic coverage are now implemented. They establish traceable exam-scope input only and do not calculate relevance, likelihood, or probability. |

## T-018 — Record sourced previous-paper question occurrences

| Field | Value |
| --- | --- |
| Issued | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Status | Ready for VS Code Codex |
| Prompt source | `docs/next_task.md` T-018 at `1f4a2f95547e62b9dbef0c538c208d6496a36e2b` |
| Scope | Record sourced previous papers and Topic-linked historical question occurrences |
| Tests | PostgreSQL/API integration tests and migration checks required |
| Implementation commit | Pending |
| Documentation-review commit | Pending |
| Review result | Pending |
| Notes | This adds historical occurrence evidence only. It must not generate questions or claim relevance scores, percentages, or exam probability. |
