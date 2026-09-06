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

### T-018 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Record sourced previous papers and Topic-linked historical question occurrences |
| Tests | `uv run pytest tests/test_previous_papers_api.py -q`: 15 passed in 1.51s with one Starlette deprecation warning. `uv run pytest -q`: 82 passed in 3.44s with the same warning. |
| Ruff | Changed-file Ruff check passed. |
| Migration checks | Fresh upgrade through `a8c4e1d7f620`, downgrade to `f6b3c9a2d741`, re-upgrade, and `uv run alembic check` passed; no new upgrade operations were detected. |
| Diff check | `git diff --check` passed. |
| Notes | Added only sourced PreviousPaper records and exact Topic-linked PreviousQuestion occurrences with stable conflicts, atomic missing-reference handling, and restrictive provenance. No answers, explanations, ingestion, multi-Topic tagging, relevance bands/scores/percentages, probability, LLMs, or generated questions were added. |


## T-018 approval record

| Field | Value |
| --- | --- |
| Recorded | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Original task entry | T-018 above |
| Final status | Approved |
| Implementation commit | `c7d7b9f18d68c9da1aeea5747b5925bf5922ead8` |
| Documentation-review commit | Review update series beginning `588999a37e5e4b5bc70792e83bf784c162b6db64` |
| Review result | Approved |
| Notes | Sourced previous-paper question occurrences retain Exam, Source, Paper, Topic, position, exact text, and optional location provenance. Historical occurrence is evidence, not a guarantee of future appearance. |

## T-019 — Calculate an explainable Topic priority band

| Field | Value |
| --- | --- |
| Issued | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Status | Ready for VS Code Codex |
| Prompt source | `docs/next_task.md` (T-019) |
| Scope | Read-only deterministic Topic priority from one syllabus version and same-Exam previous-paper occurrences |
| Tests | Focused PostgreSQL/API tests, full suite, Ruff, Alembic check, and diff check required |
| Implementation commit | Pending |
| Documentation-review commit | Pending |
| Review result | Pending |
| Notes | This is an explainable priority aid only. It must not claim a percentage, likelihood, or appearance probability. |

### T-019 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add the read-only `topic-priority-v1` endpoint and deterministic reason codes |
| Tests | `uv run pytest tests/test_topic_priority_api.py -q`: 8 passed in 1.50s with one Starlette deprecation warning. `uv run pytest -q`: 90 passed in 4.76s with the same warning. |
| Ruff | Changed-file Ruff check passed. |
| Migration checks | No schema change or migration added. `uv run alembic check` passed with no new upgrade operations detected. |
| Diff check | `git diff --check` passed. |
| Notes | Counts only the selected version's Exam, separates question occurrences from distinct matched papers, returns sorted unique years, and performs no writes. No percentages, probabilities, configurable weights, AI, or generation behavior was added. |


## T-019 approval record

| Field | Value |
| --- | --- |
| Recorded | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Original task entry | T-019 above |
| Final status | Approved |
| Implementation commit | `ff326dc5334dfc41ec298d10551f8c5801ae21b1` |
| Documentation-review commit | Review update series beginning `fc8390b4974f550c3373431712212d7edd86d5c2` |
| Review result | Approved |
| Notes | The read-only fixed v1 rule returns syllabus coverage, same-Exam historical counts, years, deterministic reasons, and a HIGH/MEDIUM/LOW preparation priority. It is not a probability or prediction. |

## T-020 — Add canonical ContentVersion identity

| Field | Value |
| --- | --- |
| Issued | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Status | Ready for VS Code Codex |
| Prompt source | `docs/next_task.md` T-020 at `262fcda5ec96f9fe3fb16dcdcc7b7f45250beb4c` |
| Scope | Add minimal reusable ContentVersion identity for an exact SyllabusVersion and Topic |
| Tests | Focused PostgreSQL/API tests, migration cycle, full suite, Ruff, Alembic check, and diff check required |
| Implementation commit | Pending |
| Documentation-review commit | Pending |
| Review result | Pending |
| Notes | Identity only. NoteDraft binding, canonical assets, question bank, release lifecycle, AI, and learner personalization remain deferred. |

### T-020 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add immutable ContentVersion identity for one exact SyllabusVersion/Topic mapping |
| Tests | `uv run pytest tests/test_content_versions_api.py -q`: 12 passed in 1.18s with one Starlette deprecation warning. `uv run pytest -q`: 102 passed in 4.18s with the same warning. |
| Ruff | Changed-file Ruff check passed. |
| Migration checks | Fresh upgrade through `c5e7a9d2b814`, downgrade to `a8c4e1d7f620`, re-upgrade, and `uv run alembic check` passed; no new upgrade operations were detected. |
| Diff check | `git diff --check` passed. |
| Notes | Composite membership, positive versions, uniqueness, and restricted deletion are database-enforced. Creation is atomic and explicit; historical versions are retained. No dependencies, configuration, NoteDraft binding, content, release lifecycle, AI, or personalization was added. |

T-020 clarification (2026-09-05 Asia/Kolkata, UTC+05:30): “immutable” in the implementation record means that the current API exposes create and read operations with no update endpoint. Database-level prevention of direct ContentVersion updates or deletion is not implemented; the database guarantees are positive version, unique mapping/version identity, composite syllabus membership, and restricted deletion of the referenced syllabus-topic mapping.


## T-020 approval record

| Field | Value |
| --- | --- |
| Recorded | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Original task entry | T-020 above |
| Final status | Approved |
| Implementation commit | `c5d2010da24731387162020accc9030d6fcca01e` |
| Documentation-review commit | Review update series beginning `62a584f776eed7ab57119dce0d67ed2305169dc7` |
| Review result | Approved |
| Notes | ContentVersion now provides create/read-only retained identity for an exact syllabus/Topic mapping. PostgreSQL enforces membership, positive version, scoped uniqueness, and referenced-mapping deletion restriction. No content asset or review lifecycle was added. |

## T-021 — Add a grounded QuestionBankItem candidate

| Field | Value |
| --- | --- |
| Issued | 2026-09-05 Asia/Kolkata (UTC+05:30) |
| Status | Ready for VS Code Codex |
| Prompt source | `docs/next_task.md` T-021 at `601966a7fd5b39577944b9cb0fbbfac6a82b2e93` |
| Scope | Store a reusable internal question candidate with exact ordered approved-Claim provenance under ContentVersion |
| Tests | Focused PostgreSQL/API tests, migration cycle, full suite, Ruff, Alembic check, and diff check required |
| Implementation commit | Pending |
| Documentation-review commit | Pending |
| Review result | Pending |
| Notes | This is not yet a complete MCQ or approved content. Options, correct answer, review, AI generation, and learner delivery remain deferred. |

### T-021 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add a manually supplied internal QuestionBankItem with exact ordered approved-Claim provenance under ContentVersion |
| Tests | `uv run pytest tests/test_question_bank_items_api.py -q`: 17 passed in 2.03s with one Starlette deprecation warning. `uv run pytest -q`: 119 passed in 4.72s with the same warning. |
| Ruff | Changed-file Ruff check passed. |
| Migration checks | Fresh upgrade through `e9a4c2f7b163`, downgrade to `c5e7a9d2b814`, re-upgrade, and `uv run alembic check` passed; no new upgrade operations were detected. |
| Diff check | `git diff --check` passed. |
| Notes | Candidate creation validates all references and approved same-Topic grounding before atomically committing the item and ordered links. PostgreSQL enforces non-whitespace text, difficulty, Claim/position uniqueness, non-negative positions, and provenance deletion restrictions. Retrieval is a stored snapshot. No dependencies, configuration, complete MCQ, review, release, AI, NoteDraft binding, or learner-facing behavior was added. |


---

## T-021 — Grounded QuestionBankItem candidate

| Field | Value |
| --- | --- |
| Task ID | `T-021` |
| Implementation commit | `3b1c425158ca0932b6c8ea9fb80dbf9efd9b8278` |
| Review state | **APPROVED** |
| Documentation approval/task commit | `e0eb71211d42fc0b1424dcc8e8f8e668b4fed1c4` |
| Approved capability | Internal, manually supplied QuestionBankItem candidates with ordered approved same-Topic Claim provenance under ContentVersion |
| Migration | `e9a4c2f7b163_add_question_bank_items.py` |
| Validation evidence | `17 passed` focused; `119 passed` full suite; upgrade/downgrade/re-upgrade; Alembic check; changed-file Ruff; `git diff --check` |
| Dependencies/configuration/Docker | No new dependencies, environment variables, secrets, or Docker services required |

The candidate remains unreviewed, unreleased, and not learner-facing. It has no MCQ options or correct answer; that is T-022.

## T-022 — Complete MCQ candidate structure

- **State:** Issued; not implemented.
- **Goal:** Add ordered answer options and exactly one same-item correct answer to new internal QuestionBankItem candidates while retaining all T-021 provenance and atomicity boundaries.
- **Architectural phase:** Question / Mock Foundation.
- **Full implementation prompt:** appended in `docs/next_task.md`.

### T-022 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add ordered options and one same-item correct answer to newly created internal QuestionBankItem candidates |
| Tests | `uv run pytest tests/test_question_bank_items_api.py -q`: 26 passed in 1.42s with one Starlette deprecation warning. `uv run pytest -q`: 128 passed in 4.88s with the same warning. |
| Ruff | Changed-file Ruff check passed. |
| Migration checks | Fresh upgrade through `f2c8d4a6e915`, downgrade to `e9a4c2f7b163`, re-upgrade, and `uv run alembic check` passed; no new upgrade operations were detected. |
| Diff check | `git diff --check` passed. |
| Notes | New API-created items require at least two non-blank ordered options and one in-range correct position. PostgreSQL enforces option text/order and same-item answer integrity while nullable migration state keeps T-021 rows readable. Item creation remains atomic and retrieval remains a stored snapshot. No dependency, configuration, Docker, AGENTS, README, review, release, AI, NoteDraft binding, previous-paper conversion, or learner behavior changed. |


---

## T-022 — Complete internal MCQ structure

| Field | Value |
| --- | --- |
| Task ID | `T-022` |
| Implementation commit | `4dc87a82a1d8695a6316debad03d7f3af43e28e2` |
| Review state | **APPROVED** |
| Documentation approval/task commit | `265fee439ad9b11cc51800515349270095038f46` |
| Approved capability | Complete internal QuestionBankItem candidates with ordered options and one same-item correct answer |
| Migration | `f2c8d4a6e915_add_question_bank_options.py` |
| Validation evidence | `26 passed, 1 warning in 1.42s` focused; `128 passed, 1 warning in 4.88s` full suite; upgrade/downgrade/re-upgrade; Alembic check; changed-file Ruff; `git diff --check` |
| Dependencies/configuration/Docker | No new dependencies, environment variables, secrets, or Docker services required |

The QuestionBankItem remains an internal, unreviewed and unreleased candidate. T-023 will add its independent human-review decision; it will not add a release or learner-facing boundary.

## T-023 — Independent QuestionBankItem human review

- **State:** Issued; not implemented.
- **Goal:** Record DRAFT/APPROVED/REJECTED review decisions for complete QuestionBankItem candidates while preventing approval of legacy incomplete candidates.
- **Architectural phase:** Canonical Content / Question Foundation.
- **Full implementation prompt:** appended in `docs/next_task.md`.

### T-023 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add independent DRAFT/APPROVED/REJECTED review decisions for QuestionBankItem candidates, guarding approval of incomplete legacy rows |
| Tests | `uv run pytest tests/test_question_bank_items_api.py -q`: 34 passed in 2.28s with one Starlette deprecation warning. `uv run pytest -q`: 136 passed in 6.13s with the same warning. |
| Ruff | Changed-file Ruff check passed. |
| Migration checks | Fresh upgrade through `a6d1e8c3f247`, downgrade to `f2c8d4a6e915`, and re-upgrade passed. A seeded complete T-022 row remained present and became DRAFT with null decision metadata on each upgrade. `uv run alembic check` reported no new upgrade operations. |
| Diff check | `git diff --check` passed. |
| Notes | Candidate review is independent from Claim and NoteDraft approval. APPROVED/REJECTED record UTC decision metadata; DRAFT clears it. Incomplete legacy candidates cannot be approved and return stable 409 without mutation. No release, publication, learner, AI, dependency, configuration, Docker, AGENTS, or README behavior changed. |


---

## T-023 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-023` |
| Implementation commit | `1e84907906579c08d7218771669730b9855778d6` |
| Review state | **APPROVED** |
| Base commit | `2f889fed9302c483c9065102953d4c1ca1fe2fe2` (approved T-022 documentation head) |
| Approved capability | Independent DRAFT/APPROVED/REJECTED human review for QuestionBankItem candidates, including DRAFT reset semantics and an incomplete-candidate approval guard |
| Migration | `a6d1e8c3f247_add_question_bank_item_approval.py`; prior migrations unchanged |
| Validation evidence | Developer-recorded: `34 passed` focused; `136 passed` full suite; changed-file Ruff; upgrade/downgrade/re-upgrade with seeded-row preservation; Alembic check; `git diff --check`. GitHub exposes no status contexts or check runs for this commit, so no CI pass is claimed. |
| Review findings | The implementation preserves stored content, ordered Claim/option provenance, correct answer, ContentVersion, and linked Claim state. It does not re-evaluate later Claim approval. Incomplete legacy candidates remain DRAFT or may be REJECTED, but APPROVED returns stable 409 without mutation. |
| Boundaries | Candidate approval remains separate from Claim approval, NoteDraft approval, verification, release, and publication. No T-024 capability is present. |


---

## T-023 documentation synchronization and T-024 issuance

| Field | Value |
| --- | --- |
| T-023 approval documentation commit | `145502a56a0d53a11fe9b6e80ce611847109a993` |
| T-023 implementation commit | `1e84907906579c08d7218771669730b9855778d6` |
| T-023 final review state | **APPROVED** |
| GitHub validation status | No status contexts or check runs were available; developer-recorded validation remains documented without a CI-pass claim |
| Next task | `T-024` — Add approved QuestionBankItem read boundary |
| T-024 status | Ready for VS Code Codex; not implemented |
| Architectural phase | Canonical Content / Question Foundation |
| Scope | Read only explicitly approved stored QuestionBankItem snapshots in stable ID order; no release, publication, learner delivery, generation, or personalization |
| Full implementation prompt | Appended to `docs/next_task.md` |


---

## T-024 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only `GET /api/v1/question-bank-items/approved` as a read-only internal boundary for explicitly approved stored candidate snapshots |
| Tests | `uv run pytest tests/test_question_bank_items_api.py -q`: 36 passed, 1 warning in 2.30s. `uv run pytest -q`: 138 passed, 1 warning in 5.51s. |
| Ruff | `uv run ruff check app/api/v1/routes/knowledge.py app/repositories/knowledge.py app/services/knowledge.py tests/test_question_bank_items_api.py`: passed (`All checks passed!`). |
| Migration checks | No model or database schema change was required. Existing migrations upgraded a fresh dedicated test database through `a6d1e8c3f247`; `uv run alembic check` reported `No new upgrade operations detected.` |
| Diff check | `git diff --check` passed; only line-ending normalization warnings were emitted. |
| Notes | The query filters exactly on QuestionBankItem APPROVED state, orders by ascending item ID, and select-in loads ordered Claim links and options. It returns stored snapshots without re-evaluating Claim approval or writing data. No release, publication, generation, learner, personalization, dependency, configuration, Docker, AGENTS, README, migration, or T-025 behavior was added. |


---

## T-024 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-024` |
| Implementation commit | `6dc8e9497fe55870173c584717e3ab78563baf3f` |
| Base/task-issuance commit | `e2c62be92006061b77ef2c260489ad5e0821f17b` |
| Review state | **APPROVED** |
| Approved capability | Read-only internal collection of explicitly approved stored QuestionBankItem snapshots in ascending item order |
| Validation evidence | Developer-recorded: `36 passed, 1 warning` focused; `138 passed, 1 warning` full suite; changed-file Ruff, fresh database upgrade, Alembic check, and diff check passed. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | Static route ordering, exact own-status filtering, eager ordered provenance loading, stored-snapshot serialization, empty-list behavior, no writes, and retained T-021–T-023 compatibility were confirmed. |
| Boundaries | No model/schema/migration change, release, publication, learner delivery, generation, personalization, mocks, or T-025 implementation. |

## T-025 — Controlled QuestionBankItem release lifecycle

- **State:** Issued; not implemented.
- **Goal:** Add a small, auditable release/withdrawal lifecycle for complete approved QuestionBankItems, separate from human approval, publication transport, and learner access.
- **Architectural phase:** Canonical Content / Controlled Release Foundation.
- **Full implementation prompt:** appended to `docs/next_task.md`.
