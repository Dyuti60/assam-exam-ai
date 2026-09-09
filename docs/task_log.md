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


---

## T-025 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only the controlled UNRELEASED/RELEASED/WITHDRAWN lifecycle and one release-decision endpoint for QuestionBankItem |
| Migration | `b3e7f1a9c462_add_question_bank_item_release.py`, parent `a6d1e8c3f247` |
| Tests | `uv run pytest tests/test_question_bank_items_api.py -q`: 52 passed, 1 warning in 3.45s. `uv run pytest -q`: 154 passed, 1 warning in 6.11s. |
| Ruff | Changed-file Ruff passed (`All checks passed!`). |
| Migration checks | Fresh upgrade through `b3e7f1a9c462` passed. Downgrade to `a6d1e8c3f247` and re-upgrade passed twice. A seeded pre-T-025 APPROVED candidate survived both cycles and became UNRELEASED with null timestamps/note, without inferred release. `uv run alembic check` reported no new upgrade operations. |
| Diff check | `git diff --check` passed; only line-ending normalization warnings were emitted. |
| Notes | Release requires a complete, currently approved stored candidate; withdrawal is one-way and preserves the original release time. PostgreSQL enforces lifecycle metadata and approved-release consistency. Released items lock DRAFT/REJECTED review changes until withdrawal. The existing approved-items endpoint remains approval-only. No released-items list, public/learner delivery, generation, personalization, dependency, configuration, Docker, AGENTS, README, or T-026 behavior was added. |


---

## T-025 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-025` |
| Implementation commit | `84e0b20fd81d9bf7b241a93686811db0ccd3e8dc` |
| Base/task-issuance commit | `91a9ecaa861a0ceba8d557bb1995f6d636bfcd8f` |
| Review state | **APPROVED** |
| Approved capability | Controlled UNRELEASED/RELEASED/WITHDRAWN lifecycle for complete, independently approved QuestionBankItem snapshots |
| Migration | `b3e7f1a9c462_add_question_bank_item_release.py`, parent `a6d1e8c3f247`; historical migrations unchanged |
| Validation evidence | Developer-recorded: `52 passed, 1 warning` focused; `154 passed, 1 warning` full suite; changed-file Ruff; fresh upgrade; downgrade/re-upgrade; seeded-record preservation; Alembic check; and diff check. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | Release requires the item's own APPROVED state and complete stored MCQ structure. Withdrawal preserves release time. Invalid transitions and released-item review changes fail with stable 409 and no mutation. Row locking serializes decisions, and stored content/provenance is not re-evaluated or changed. |
| Boundaries | Release remains distinct from review, Claim/NoteDraft approval, Verification, publication transport, and learner delivery. No released collection, T-026 implementation, AI, auth, personalization, mock, PDF, dependency, configuration, or Docker work was included. |


---

## T-026 issued — Add released QuestionBankItem read boundary

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add one read-only internal collection that returns only currently RELEASED stored QuestionBankItem snapshots in stable ID order |
| Architectural phase | Canonical Content / Controlled Release Foundation |
| Scope | Released canonical-question selection boundary only; no public/learner delivery, publication transport, generation, personalization, or mock assembly |
| Full implementation prompt | Appended to `docs/next_task.md` |


---

## T-026 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only `GET /api/v1/question-bank-items/released` as a read-only internal boundary for current RELEASED stored snapshots |
| Tests | `uv run pytest tests/test_released_question_bank_items_api.py tests/test_question_bank_items_api.py -q`: 54 passed, 1 warning in 4.11s. Required existing focused file: 52 passed, 1 warning in 3.97s. `uv run pytest -q`: 156 passed, 1 warning in 6.91s. |
| Ruff | Changed-file Ruff passed (`All checks passed!`). |
| Migration checks | No model/schema migration required. `uv run alembic heads` reported `b3e7f1a9c462 (head)` and `uv run alembic check` reported `No new upgrade operations detected.` |
| Notes | The repository filters exactly on current RELEASED state, orders by ascending item ID, and select-in loads ordered Claim links and options. The service returns stored `QuestionBankItemResponse` snapshots without writes or re-evaluation. UNRELEASED and WITHDRAWN candidates are excluded; the existing approved-items boundary remains approval-only. No delivery, publication transport, generation, personalization, dependency, configuration, Docker, AGENTS, README, migration, or T-027 behavior was added. |


---

## T-026 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-026` |
| Implementation commit | `d5c3b484b8268ae745da491617c56c02a1be3853` |
| Base/task-issuance commit | `3e630d9fd952dcb24a320295fbc281b6396b0e45` |
| Review state | **APPROVED** |
| Approved capability | Read-only internal collection of currently RELEASED stored QuestionBankItem snapshots in ascending item order |
| Validation evidence | Developer-recorded: `54 passed, 1 warning` combined focused tests; `52 passed, 1 warning` existing QuestionBankItem tests; `156 passed, 1 warning` full suite; changed-file Ruff; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The route is static and correctly ordered; the repository filters only RELEASED rows and eagerly loads ordered Claim/option relationships; the service returns stored snapshots without writes or re-evaluation. The approved boundary remains intact and distinct. |
| Boundaries | No model, schema, migration, delivery, publication transport, learner, personalization, mock, AI, dependency, configuration, Docker, or T-027 implementation was included. |


---

## T-027 issued — Bind new NoteDrafts to ContentVersion

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Require every newly persisted NoteDraft to belong to one exact same-Topic ContentVersion while preserving legacy drafts without inferred ownership |
| Architectural phase | Canonical Content / Versioned Note Foundation |
| Scope | ContentVersion ownership and migration-safe compatibility only; no NoteDraft release, publication, learner delivery, AI generation, or personalization |
| Full implementation prompt | Appended to `docs/next_task.md` |


---

## T-027 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Bind every newly persisted NoteDraft to one exact same-Topic ContentVersion while preserving legacy drafts with null ownership |
| Tests | `uv run pytest tests/test_note_drafts.py -q`: 22 passed, 1 warning in 1.93s. `uv run pytest tests/test_content_versions_api.py -q`: 12 passed, 1 warning in 0.96s. `uv run pytest -q`: 164 passed, 1 warning in 7.88s. |
| Ruff | Changed-file Ruff passed (`All checks passed!`). |
| Migration checks | Fresh upgrade through `c7a4e9d2f816`, downgrade to `b3e7f1a9c462`, and re-upgrade passed. A seeded legacy draft retained Markdown, Topic, approval metadata, and ordered Claim provenance with null ContentVersion ownership. `uv run alembic heads` reported `c7a4e9d2f816 (head)` and `uv run alembic check` reported no new upgrade operations. |
| Notes | Creation validates Topic, ContentVersion, same-Topic ownership, then approved Claims before atomically writing the draft and Claim links. PostgreSQL independently enforces the same-Topic composite reference and restricts deletion of referenced ContentVersions. Preview, legacy reads/review, QuestionBankItems, dependencies, configuration, Docker, AGENTS, README, release, delivery, AI, personalization, and T-028 behavior remain unchanged. |
---

## T-027 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-027` |
| Implementation commit | `bcff4c54a04f6ec3cdcb094f71d64241e87a3622` |
| Base/task-issuance commit | `a2e9f2ba19ba599255a18f3724e07482489b4b72` |
| Review state | **APPROVED** |
| Approved capability | Every newly persisted NoteDraft is bound to one exact same-Topic ContentVersion; legacy drafts remain compatible with null ownership and no inferred data |
| Validation evidence | Developer-recorded: 22 focused NoteDraft tests, 12 focused ContentVersion tests, and 164 full-suite tests, each with one existing warning; changed-file Ruff; fresh upgrade; seeded downgrade/re-upgrade; PostgreSQL mismatch/deletion checks; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The immutable commit is exactly one commit over the issued base. Route/schema/service/repository/PostgreSQL layering, validation order, atomicity, migration safety, same-Topic enforcement, stored-snapshot behavior, explicit new-ownership assertions, and legacy-null compatibility satisfy T-027. |
| Boundaries | No NoteDraft release, released collection, publication transport, learner delivery, PDF, AI, personalization, dependency, configuration, Docker, or T-028 implementation was included. |

---

## T-028 issued — Add controlled NoteDraft release lifecycle

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add an explicit UNRELEASED/RELEASED/WITHDRAWN lifecycle to stored NoteDrafts, requiring independent NoteDraft approval and non-null ContentVersion ownership before release |
| Architectural phase | Canonical Content / Controlled Note Release |
| Scope | Release and withdrawal state only; no released collection, publication transport, public/learner delivery, PDF, AI generation, or personalization |
| Full implementation prompt | Appended to `docs/next_task.md` |


---

## T-028 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only the controlled UNRELEASED/RELEASED/WITHDRAWN lifecycle and one release-decision endpoint for stored NoteDrafts |
| Migration | `d9e5b2a7c418_add_note_draft_release.py`, parent `c7a4e9d2f816` |
| Tests | `uv run pytest tests/test_note_drafts.py -q`: 41 passed, 1 warning in 3.56s. `uv run pytest -q`: 183 passed, 1 warning in 10.37s. |
| Ruff | Changed-file Ruff passed (`All checks passed!`). |
| Migration checks | Fresh upgrade through `d9e5b2a7c418`, downgrade to `c7a4e9d2f816`, and re-upgrade passed. Seeded version-owned and legacy-null drafts retained Topic, ownership, Markdown, approval metadata, creation time, and ordered Claim links; both became UNRELEASED with null release metadata without inference. Direct PostgreSQL probes rejected invalid status, non-approved release, and ownerless release. |
| Notes | Release requires the draft's own APPROVED state and non-null stored ContentVersion. Withdrawal is one-way and preserves the original release time. PostgreSQL enforces lifecycle metadata, approval, and ownership. Release and approval decisions lock the draft row. The existing approved-drafts endpoint remains approval-only. No released-draft list, delivery, publication transport, PDF, AI, personalization, dependency, configuration, Docker, AGENTS, README, or T-029 behavior was added. |
---

## T-028 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-028` |
| Implementation commit | `4974d87f90c08a5e39b3fe31a5cd1f7e1f9a4470` |
| Base/task-issuance commit | `ac5f19c54c637dba27c5e396641c9d6cc34896dd` |
| Review state | **APPROVED** |
| Approved capability | Controlled one-way UNRELEASED/RELEASED/WITHDRAWN lifecycle for stored, version-owned NoteDraft snapshots |
| Validation evidence | Developer-recorded: 41 focused NoteDraft tests and 183 full-suite tests, each with one existing warning; changed-file Ruff; fresh upgrade; seeded downgrade/re-upgrade; PostgreSQL lifecycle probes; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The immutable commit is exactly one commit over the issued base. It preserves route/schema/service/repository/PostgreSQL layering, uses row locks for conflicting decisions, enforces approval and ContentVersion eligibility, retains release provenance, protects legacy null-owned drafts, and keeps approval separate from release. |
| Boundaries | No released-draft collection, publication transport, public/learner delivery, PDF, AI, personalization, dependency, configuration, Docker, or T-029 implementation was included. |

---

## T-029 issued — Add released NoteDraft read boundary

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add one read-only internal endpoint returning only currently RELEASED stored NoteDraft snapshots in stable ID order |
| Architectural phase | Canonical Content / Released Note Read Boundary |
| Scope | Exact release-state filtering and stored-snapshot retrieval only; no publication transport, public/learner delivery, PDF, AI generation, or personalization |
| Full implementation prompt | Appended to `docs/next_task.md` |


---

## T-029 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only `GET /api/v1/note-drafts/released` as the read-only boundary for currently RELEASED stored NoteDraft snapshots |
| Migration | None; model and schema unchanged, with Alembic head retained at `d9e5b2a7c418` |
| Tests | `uv run pytest tests/test_released_note_drafts_api.py -q`: 2 passed, 1 warning in 1.47s. `uv run pytest tests/test_note_drafts.py -q`: 41 passed, 1 warning in 3.55s. `uv run pytest -q`: 185 passed, 1 warning in 10.29s. |
| Ruff | Changed-file Ruff passed (`All checks passed!`). |
| Notes | The repository filters exactly on RELEASED state, orders by draft ID, and eagerly loads Topic and ordered Claim links. Responses reuse stored NoteDraft serialization and perform no lock, write, regeneration, or current-state re-evaluation. The approved boundary remains approval-only. No publication, learner delivery, PDF, content package, mock assembly, AI, personalization, dependency, configuration, Docker, AGENTS, README, migration, or T-030 behavior was added. |


---

## T-029 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-029` |
| Implementation commit | `ee755cfc3a88700abababf2473bd8d615c16c871` |
| Base/task-issuance commit | `a351673bc242261640faa1468a33e395fe740e4b` |
| Review state | **APPROVED** |
| Approved capability | Read-only collection of currently RELEASED stored NoteDraft snapshots |
| Validation evidence | Developer-recorded: 2 focused released-draft tests, 41 focused NoteDraft tests, and 185 full-suite tests, each with one existing warning; changed-file Ruff; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The immutable commit is exactly one commit over the issued base and changes only the expected route, repository, service, focused tests, and documentation. It filters exact RELEASED state, preserves stable ordering and stored provenance, eagerly loads required relationships, performs no writes, and keeps approval separate from release. |
| Boundaries | No model, schema, migration, publication transport, public/learner delivery, PDF, content package, mock assembly, AI, personalization, dependency, configuration, Docker, or T-030 implementation was included. |

---

## T-030 issued — Add ContentVersion released-assets manifest

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add one read-only internal endpoint that returns the currently RELEASED NoteDraft and QuestionBankItem snapshots owned by one exact ContentVersion |
| Architectural phase | Canonical Content / Version Release Manifest |
| Scope | Exact ContentVersion ownership and release-state filtering with stored-snapshot assembly only; no package persistence, publication transport, PDF, public/learner delivery, AI generation, or personalization |
| Full implementation prompt | Appended to `docs/next_task.md` |


---

## T-030 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only `GET /api/v1/content-versions/{content_version_id}/released-assets` as a computed read-only manifest of currently RELEASED stored NoteDraft and QuestionBankItem snapshots owned by one exact ContentVersion |
| Migration | None; models and persistence unchanged, with Alembic head retained at `d9e5b2a7c418` |
| Tests | `uv run pytest tests/test_content_version_released_assets_api.py -q`: 3 passed, 1 warning in 1.85s. `uv run pytest tests/test_content_versions_api.py -q`: 12 passed, 1 warning in 1.09s. `uv run pytest tests/test_released_note_drafts_api.py -q`: 2 passed, 1 warning in 1.38s. `uv run pytest tests/test_released_question_bank_items_api.py -q`: 2 passed, 1 warning in 1.21s. `uv run pytest -q`: 188 passed, 1 warning in 11.12s. |
| Ruff | Changed-file Ruff passed (`All checks passed!`). |
| Alembic | Fresh dedicated test database upgrade passed through `d9e5b2a7c418`; `uv run alembic heads` reported that single head and `uv run alembic check` reported no new upgrade operations. |
| Notes | Repository queries filter exact stored ContentVersion ownership plus RELEASED state, order each asset type by ID, and eagerly load stored nested provenance. The service reuses existing serializers. Missing versions retain the established 404; existing versions may return empty lists. The endpoint performs no locks, writes, transitions, regeneration, inference, or current-state re-evaluation. No package persistence, publication transport, public/learner delivery, PDF, AI, personalization, dependency, configuration, Docker, AGENTS, README, or T-031 work was added. |


---

## T-030 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-030` |
| Implementation commit | `3a81ce6cefdcc3bd0abd7a17ecc1472d5bb1d4d4` |
| Base/task-issuance commit | `f25c633b86648bf9958cdf317b72336a38dd5ca6` |
| Traceability correction | Empty commit `265f683b5180cde585d366fce17ffe53c11c1955` clarifies that `3a81ce6` implements T-030, not T-031; no tree change or history rewrite occurred. |
| Review state | **APPROVED** |
| Approved capability | Read-only exact-ContentVersion manifest of currently RELEASED stored NoteDraft and QuestionBankItem snapshots |
| Validation evidence | Developer-recorded: 3 focused manifest tests, 12 ContentVersion tests, 2 released-NoteDraft tests, 2 released-QuestionBankItem tests, and 188 full-suite tests, each with one existing warning; changed-file Ruff; fresh database upgrade; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The immutable implementation is exactly one commit over the issued base and changes only the expected route, schema, repository, service, focused tests, and documentation. It applies exact ownership plus RELEASED filtering in PostgreSQL, preserves ordering and stored snapshots, eagerly loads required relationships, and performs no writes. |
| Boundaries | No model, migration, dependency, configuration, Docker, package persistence, publication transport, public/learner delivery, PDF, AI, personalization, or actual T-031 implementation was included. |

---

## T-031 issued — Persist immutable ContentPackage membership snapshot

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add atomic creation of one immutable internal ContentPackage that captures the currently RELEASED NoteDraft and QuestionBankItem memberships for one exact ContentVersion |
| Architectural phase | Canonical Content / Immutable Package Snapshot |
| Scope | Package identity and ordered same-ContentVersion membership only; no package publication/release lifecycle, retrieval collection, PDF, export, download, public/learner delivery, AI generation, or personalization |
| Full implementation prompt | Appended to `docs/next_task.md` |


---

## T-031 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only atomic creation of an immutable internal ContentPackage membership snapshot for the currently RELEASED NoteDrafts and QuestionBankItems owned by one exact ContentVersion |
| Migration | `e2c6f8a1d943` follows `d9e5b2a7c418`; it adds ContentPackage identity, two ordered membership tables, and only the composite-foreign-key support constraints |
| Tests | `uv run pytest tests/test_content_packages_api.py -q`: 10 passed, 1 warning in 2.74s. Focused regressions: released-assets manifest 3 passed, ContentVersion 12 passed, NoteDraft 41 passed, released NoteDraft 2 passed, QuestionBankItem 52 passed, and released QuestionBankItem 2 passed. `uv run pytest -q`: 198 passed, 1 warning in 13.20s. |
| Migration validation | Fresh upgrade reached `e2c6f8a1d943`. A seeded database at `d9e5b2a7c418` preserved two NoteDrafts, two QuestionBankItems, and their Claim links through upgrade/downgrade/re-upgrade; no package was inferred. A representative package stored one released asset of each type in position 0 before downgrade. |
| Notes | The endpoint locks the exact ContentVersion and eligible exact-version RELEASED assets, stores independently ordered zero-based membership links, and commits once. Composite PostgreSQL constraints reject cross-version links, duplicates, invalid positions, and deletion of referenced assets/version. Later withdrawal does not rewrite membership; T-030 remains the dynamic current-release manifest. No retrieval/list, package lifecycle, publication, PDF, delivery, AI, personalization, dependency, configuration, Docker, AGENTS, README, or T-032 work was added. |


---

## T-031 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-031` |
| Implementation commit | `a261a36a539c40b718e2185eaed794f700dd4b77` |
| Base/task-issuance commit | `12ede1545988432045ea781587d0f09059ee2160` |
| Documentation correction | `67e80c29928eb7e913bca99f899082562e4c2cb1` corrects only the current architecture inventory after implementation |
| Review state | **APPROVED** |
| Approved capability | Atomic persistence of one immutable, exact-ContentVersion ContentPackage with independently ordered NoteDraft and QuestionBankItem membership snapshots |
| Validation evidence | Developer-recorded: 10 focused ContentPackage tests and 198 full-suite tests, each with one existing warning; required focused regressions; changed-file Ruff; fresh and seeded migration upgrade; downgrade/re-upgrade; PostgreSQL constraints; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The implementation is exactly one commit over the issued base. It uses explicit row locks, one transaction, exact RELEASED and ContentVersion filtering, stable zero-based ordering, rollback-safe persistence, and PostgreSQL-enforced same-version membership. The documentation correction closes the only review blocker and changes no implementation file. |
| Boundaries | No package retrieval/list, package approval/release/publication lifecycle, PDF/export, public/learner delivery, AI, mock assembly, personalization, dependency, configuration, or Docker behavior was included. |

---

## T-032 issued — Add individual ContentPackage retrieval boundary

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add one read-only internal endpoint returning the retained ordered membership snapshot for one exact ContentPackage ID |
| Architectural phase | Canonical Content / Immutable Package Read Boundary |
| Scope | Individual stored package retrieval only; no package list, mutation, lifecycle, publication, PDF/export, delivery, learner, AI, or personalization behavior |
| Full implementation prompt | Appended to `docs/next_task.md` |


---

## T-032 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only `GET /api/v1/content-packages/{content_package_id}` for read-only retrieval of one retained ContentPackage identity and its two stored position-ordered membership ID lists |
| Migration | None; models, schemas, relationships, persistence, and Alembic head `e2c6f8a1d943` remain unchanged |
| Tests | `uv run pytest tests/test_content_packages_api.py -q`: 13 passed, 1 warning in 5.78s. T-032-only selection: 3 passed, 10 deselected. T-031 creation selection: 10 passed, 3 deselected. Required focused regressions passed: released-assets manifest 3, ContentVersion 12, NoteDraft 41, released NoteDraft 2, QuestionBankItem 52, and released QuestionBankItem 2 tests. `uv run pytest -q`: 201 passed, 1 warning in 32.75s. |
| Validation | Changed-file Ruff passed. A fresh dedicated test database upgrade reached the unchanged single Alembic head `e2c6f8a1d943`; Alembic reported no new upgrade operations. Diff and whitespace checks passed. |
| Notes | Retrieval uses the existing repository's fixed-query eager loading and shared stored package serializer. Membership IDs retain persisted association-position order even after withdrawal, review changes, or Claim changes; T-030 remains the separate dynamic current-release manifest. Missing packages retain the exact established 404. The endpoint performs no locks, writes, transitions, regeneration, or inference. No package list/mutation/lifecycle, publication, PDF/export, public/learner delivery, AI, mock assembly, personalization, dependency, configuration, Docker, AGENTS, README, or T-033 work was added. |


---

## T-032 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-032` |
| Implementation commit | `1a695d8a2335612ff4873df3a3c3bb51543d1591` |
| Base/task-issuance commit | `94cb1894a40e1736f9af39a41a849d8858965601` |
| Review state | **APPROVED** |
| Approved capability | Read-only retrieval of one retained ContentPackage identity and both immutable membership ID lists in persisted association-position order |
| Validation evidence | Developer-recorded: 13 complete ContentPackage tests and 201 full-suite tests, each with one existing warning; required focused regressions; changed-file Ruff; fresh database upgrade; unchanged Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The immutable commit is exactly one commit over the issued base and changes only the expected route, service, focused tests, and documentation. It reuses fixed-query repository eager loading and the stored serializer, returns the stable missing-package 404, preserves membership after later state changes, and performs no locks or writes. |
| Boundaries | No model, schema, repository, migration, dependency, configuration, Docker, package list/mutation/lifecycle, publication, PDF/export, public/learner delivery, AI, mock assembly, personalization, or T-033 behavior was included. |

---

## T-033 issued — Add expanded ContentPackage content boundary

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add one read-only internal endpoint returning the retained ContentPackage identity plus full stored NoteDraft and QuestionBankItem snapshots in package-membership order |
| Architectural phase | Canonical Content / Expanded Immutable Package Read Boundary |
| Scope | Expanded stored content retrieval only; no membership rebuilding, package list/mutation/lifecycle, publication, rendering, PDF/export, delivery, learner, AI, or personalization behavior |
| Full implementation prompt | Appended to `docs/next_task.md` |


---

## T-033 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only `GET /api/v1/content-packages/{content_package_id}/content`, returning the retained package plus full stored responses for exactly its ordered NoteDraft and QuestionBankItem members |
| Migration | None; models, relationships, persistence, and unchanged Alembic head `e2c6f8a1d943` remain intact |
| Tests | T-033 selection: 4 passed, 13 deselected, 1 warning in 2.52s. Complete ContentPackage suite: 17 passed, 1 warning in 4.72s. Required focused regressions passed: released-assets manifest 3, ContentVersion 12, NoteDraft 41, released NoteDraft 2, QuestionBankItem 52, and released QuestionBankItem 2 tests. Full suite: 205 passed, 1 warning in 14.33s. |
| Validation | Changed-file Ruff passed. A fresh dedicated `_test` database upgrade reached the unchanged single Alembic head `e2c6f8a1d943`; Alembic reported no new upgrade operations. Diff and whitespace checks passed. |
| Notes | PostgreSQL joins select exact package members and order them by persisted association positions. The service verifies resolved IDs against retained membership and reuses existing serializers. Withdrawn and post-withdrawal review-changed members remain visible; T-030 remains the separate dynamic current-release view. Reads use fixed-query eager loading and perform no locks, writes, transitions, regeneration, copying, or current-state re-evaluation. No package list/mutation/lifecycle, publication, rendering, PDF/export, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, AGENTS, README, or T-034 work was added. |


---

## T-033 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-033` |
| Implementation commit | `673b4ae62c4d2dd102986f3144ed8e30dea9116f` |
| Base/task-issuance commit | `23539a56f397202480e76aee42a0ade99424ddce` |
| Review state | **APPROVED** |
| Approved capability | Read-only expansion of one retained ContentPackage into exactly its position-ordered stored NoteDraft and QuestionBankItem member snapshots |
| Validation evidence | Developer-recorded: 4 focused T-033 tests, 17 complete ContentPackage tests, and 205 full-suite tests, each with one existing warning; required focused regressions; changed-file Ruff; fresh database upgrade; unchanged Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The implementation is exactly one commit over the issued base and changes only the expected route, schema, repository, service, focused tests, and documentation. Exact membership joins, stored-position ordering, complete-resolution checks, eager loading, retained-snapshot semantics, stable 404 behavior, and read-only execution match the task. |
| Boundaries | No model, relationship, migration, dependency, configuration, Docker, package list/mutation/lifecycle, publication, rendering, PDF/export, public/learner delivery, AI, source discovery, mock assembly, personalization, or T-034 behavior was included. |

---

## T-034 issued — Add independent ContentPackage human-review lifecycle

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add an explicit DRAFT/APPROVED/REJECTED human-review decision on ContentPackage itself while preserving immutable membership and keeping package release separate |
| Architectural phase | Canonical Content / Independent Package Review |
| Scope | Package review fields, constraints, migration, and one decision endpoint only; no package release, publication, rendering, PDF/export, delivery, learner, AI, or personalization behavior |
| Full implementation prompt | Appended to `docs/next_task.md` |


---

## T-034 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only independent DRAFT/APPROVED/REJECTED ContentPackage review metadata and `POST /api/v1/content-packages/{content_package_id}/approval`, preserving immutable ordered membership |
| Migration | `f7b3d1a8c529` after `e2c6f8a1d943`; existing packages become DRAFT with null decision metadata and no inferred approval |
| Tests | T-034 selection: 5 passed, 17 deselected, 1 warning in 1.80s. Complete ContentPackage suite: 22 passed, 1 warning in 4.40s. Required focused regressions passed: ContentVersion manifest 3, ContentVersion 12, NoteDraft 41, released NoteDraft 2, QuestionBankItem 52, and released QuestionBankItem 2. Full suite: 210 passed, 1 warning in 12.75s. |
| Validation | Changed-file Ruff passed. Fresh upgrade and seeded upgrade/downgrade/re-upgrade passed on dedicated `_test` databases. Package identity, creation time, member IDs, and positions were preserved; each upgrade produced DRAFT/null review metadata. PostgreSQL probes, Alembic head/check, diff, and whitespace checks passed. |
| Notes | Approval locks only the package row, commits once, and rolls back failures. APPROVED/REJECTED record UTC decision time and optional note; DRAFT clears both. Review is independent of member state and cannot mutate membership. No package release/list, publication, rendering, PDF/export, delivery, learner, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, AGENTS, README, or T-035 work was added. |


---

## T-034 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-034` |
| Implementation commit | `8bdd96a1931be638ad4c5a40ab22a34382e66812` |
| Base/task-issuance commit | `bf65890e89752624c93e9cfd355240dea6499fc9` |
| Review state | **APPROVED** |
| Approved capability | Independent DRAFT/APPROVED/REJECTED human review for ContentPackage with UTC/reset semantics and immutable ordered membership |
| Migration | `f7b3d1a8c529` follows `e2c6f8a1d943` and safely migrates existing packages to DRAFT with null decision metadata |
| Validation evidence | Developer-recorded: 5 focused T-034 tests, 22 complete ContentPackage tests, and 210 full-suite tests, each with one existing warning; focused regressions; Ruff; fresh and seeded migration cycles; PostgreSQL probes; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The implementation is exactly one commit over the issued base. Schema, model, migration, row locking, transaction rollback, fresh retrieval, response compatibility, database invariants, membership preservation, state independence, and scope match the task with no blocking finding. |
| Boundaries | No package list, release/withdrawal, publication, rendering, PDF/export, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-035 behavior was included. |

---

## T-035 issued — Add controlled ContentPackage release lifecycle

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add an explicit UNRELEASED/RELEASED/WITHDRAWN lifecycle to an approved immutable ContentPackage while retaining release provenance and preventing in-place re-release |
| Architectural phase | Canonical Content / Controlled Package Release |
| Scope | Package release fields, constraints, migration, and one decision endpoint only; no released-package collection, publication transport, rendering, PDF/export, delivery, learner, AI, or personalization behavior |
| Full implementation prompt | Appended to `docs/next_task.md` |


---

## T-035 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only controlled UNRELEASED/RELEASED/WITHDRAWN ContentPackage state and `POST /api/v1/content-packages/{content_package_id}/release`, preserving independent review and immutable ordered membership |
| Migration | `a8c4e2f9b671` after `f7b3d1a8c529`; existing packages become UNRELEASED with null release metadata and no inferred release |
| Tests | T-035 selection: 5 passed, 22 deselected, 1 warning in 1.37s. Complete ContentPackage suite: 27 passed, 1 warning in 5.59s. Required focused regressions: 112 passed, 1 warning in 7.09s. Full suite: 215 passed, 1 warning in 14.09s. |
| Validation | Fresh upgrade and seeded upgrade/downgrade/re-upgrade passed on dedicated `_test` databases, preserving package review, identity, creation time, and both member IDs/positions while producing UNRELEASED/null release metadata on each upgrade. PostgreSQL probes, changed-file Ruff, Alembic head/check, diff, and whitespace checks passed. |
| Notes | Release and conflicting approval decisions lock only the package row. Eligibility uses only stored package approval and retained membership; member state is not re-evaluated. Withdrawal retains release time and prevents re-release. No released-package collection, publication, rendering, PDF/export, delivery, learner, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, AGENTS, README, or T-036 work was added. |


---

## T-035 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-035` |
| Implementation commit | `632fb01e6566d3270ef82c0a47788e8eabeac229` |
| Base/task-issuance commit | `e2cef231108f8285365277ee35387a704c9f57c3` |
| Review state | **APPROVED** |
| Approved capability | Controlled one-way ContentPackage UNRELEASED/RELEASED/WITHDRAWN lifecycle with approval and non-empty-membership eligibility |
| Migration | `a8c4e2f9b671` follows `f7b3d1a8c529` and safely migrates existing packages to UNRELEASED with null metadata |
| Validation evidence | Developer-recorded: 5 focused T-035 tests, 27 complete ContentPackage tests, 112 combined regressions, and 215 full-suite tests, each with one existing warning; Ruff; fresh and seeded migration cycles; PostgreSQL probes; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The implementation is exactly one commit over the issued base. Transition ordering, stable conflicts, review lock, UTC provenance, empty-membership rejection, package-only locking, rollback, shared response compatibility, model/migration alignment, data preservation, and exclusions match the task with no blocking finding. |
| Boundaries | No released-package collection, publication, rendering, PDF/export, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-036 behavior was included. |

---

## T-036 issued — Add released ContentPackage read boundary

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add one read-only internal collection returning only currently RELEASED ContentPackage snapshots in stable package-ID order |
| Architectural phase | Canonical Content / Released Package Read Boundary |
| Scope | Exact package release-state filtering and stored membership response only; no expanded package bodies, publication, rendering, PDF/export, delivery, learner, AI, or personalization behavior |
| Full implementation prompt | Appended to `docs/next_task.md` |


---

## T-036 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only `GET /api/v1/content-packages/released`, returning currently RELEASED stored package responses in ascending package-ID order with both retained membership lists in persisted position order |
| Migration | None; models, schemas, persistence, constraints, and Alembic head `a8c4e2f9b671` remain unchanged |
| Tests | T-036 selection: 2 passed, 27 deselected, 1 warning in 1.79s. Complete ContentPackage suite: 29 passed, 1 warning in 6.09s. Required focused regressions: 112 passed, 1 warning in 6.56s. Full suite: 217 passed, 1 warning in 14.18s. |
| Validation | Fresh dedicated `_test` database upgrade reached unchanged head `a8c4e2f9b671`. Changed-file Ruff, Alembic head/check, diff, and whitespace checks passed. |
| Notes | PostgreSQL filters exactly current RELEASED package state and orders by package ID. Two select-in loads preserve both stored membership orders with a fixed three-query read. The endpoint performs no lock or write and does not inspect member or unrelated domain state. No approved-package list, expanded collection, publication, rendering, PDF/export, delivery, learner, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, AGENTS, README, or T-037 work was added. |


---

## T-036 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-036` |
| Implementation commit | `44446303944e946a1834b714ac02009bcd22e3b1` |
| Base/task-issuance commit | `0838f2c37b79b37380f7f1013df4e1b4d94625b0` |
| Review state | **APPROVED** |
| Approved capability | Read-only collection of currently RELEASED ContentPackage snapshots in ascending package-ID order with retained membership order |
| Migration | None; Alembic remains at `a8c4e2f9b671` |
| Validation evidence | Developer-recorded: 2 focused T-036 tests, 29 complete ContentPackage tests, 112 combined regressions, and 217 full-suite tests, each with one existing warning; Ruff; fresh upgrade; unchanged Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | Exact release filtering, static-route precedence, stable ordering, fixed-query eager loading, shared serialization, stored membership preservation, member-state independence, withdrawal behavior, no-lock/no-write execution, compatibility, and exclusions match the task with no blocking finding. |
| Boundaries | No schema/model/migration change, approved-package list, expanded collection, publication, rendering, PDF/export, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-037 behavior was included. |

---

## T-037 issued — Persist immutable render-ready ContentDocument snapshot

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Deterministically assemble and persist one immutable Markdown ContentDocument snapshot from exactly one currently RELEASED ContentPackage |
| Architectural phase | Canonical Content / Render-Ready Document Foundation |
| Scope | Internal document snapshot identity, deterministic Markdown, checksum, creation and response only; no PDF, HTML, publication, download, storage backend, delivery, learner, AI, or personalization behavior |
| Full implementation prompt | Appended to `docs/next_task.md` |

---

## T-037 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only immutable deterministic ContentDocument creation for one currently RELEASED ContentPackage through `POST /api/v1/content-packages/{content_package_id}/content-documents` |
| Migration | `c4d8f2a6b731` after `a8c4e2f9b671`; creates only `content_documents` and infers no documents |
| Tests | T-037 selection: 10 passed, 29 deselected, 1 warning in 1.95s. Complete ContentPackage suite: 39 passed, 1 warning in 7.26s. Required regressions: 112 passed, 1 warning in 6.84s. Full suite: 227 passed, 1 warning in 14.71s. |
| Validation | Fresh upgrade and seeded upgrade/downgrade/re-upgrade preserved package identity and both membership types with no inferred document. PostgreSQL constraints, changed-file Ruff, Alembic head/check, and diff checks passed. |
| Notes | Rendering uses retained membership order, stored snapshots, A-Z option/answer labels, one final newline, and SHA-256 of exact UTF-8 Markdown. Package-only locking, one successful commit, duplicate protection, and rollback are covered. No retrieval/list/lifecycle, PDF/HTML, publication, storage/download, delivery, learner, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, AGENTS, README, or T-038 work was added. |


---

## T-037 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-037` |
| Implementation commit | `e199b9b6b4698ad3df1c3bf60c7e82b1adc3e951` |
| Base/task-issuance commit | `180c3b9f7061ee2f4100faba71f91bb330c236fa` |
| Review state | **APPROVED** |
| Approved capability | Atomic creation of at most one immutable deterministic Markdown ContentDocument snapshot from one currently RELEASED ContentPackage |
| Migration | `c4d8f2a6b731` follows `a8c4e2f9b671`, creates only `content_documents`, and infers no document |
| Validation evidence | Developer-recorded: 10 focused T-037 tests, 39 complete ContentPackage tests, 112 combined regressions, and 227 full-suite tests, each with one existing warning; Ruff; fresh and seeded migration cycles; PostgreSQL probes; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The implementation is exactly one commit over the issued base. Deterministic rendering, exact UTF-8 checksum, ContentVersion integrity, one-document uniqueness, package-only locking, retained ordering, duplicate translation, rollback, data preservation, model/migration alignment, and scope exclusions match the task with no blocking finding. |
| Boundaries | No ContentDocument retrieval/list/lifecycle, PDF/HTML rendering, publication, storage/download, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-038 behavior was included. |

---

## T-038 issued — Add individual ContentDocument retrieval boundary

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add one read-only endpoint that retrieves one immutable stored ContentDocument by its own ID |
| Architectural phase | Canonical Content / Stored Document Read Boundary |
| Scope | Exact stored ContentDocument response and missing-resource handling only; no regeneration, checksum recomputation, lifecycle, list, PDF/HTML, publication, storage/download, delivery, learner, AI, or personalization behavior |
| Full implementation prompt | Appended to `docs/next_task.md` |

---

## T-038 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only `GET /api/v1/content-documents/{content_document_id}`, returning one exact immutable stored ContentDocument response by its own ID |
| Migration | None; models, schemas, constraints, registration, and Alembic head `c4d8f2a6b731` remain unchanged |
| Tests | T-038 selection: 2 passed, 39 deselected, 1 warning in 0.81s. Complete ContentPackage/ContentDocument suite: 41 passed, 1 warning in 7.14s. Required regressions: 112 passed, 1 warning in 6.55s. Full suite: 229 passed, 1 warning in 15.71s. |
| Validation | Fresh dedicated `_test` upgrade reached `c4d8f2a6b731`. Changed-file Ruff, Alembic head/check, diff, and whitespace checks passed. |
| Notes | Retrieval performs one no-autoflush ContentDocument SELECT, reuses the stored serializer, and does not load package members, lock, write, commit, regenerate Markdown, recalculate SHA-256, or inspect current related state. T-038 is Ready for review, not approved. No list/lifecycle, PDF/HTML, publication, storage/download, delivery, learner, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, AGENTS, README, or T-039 work was added. |


---

## T-038 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-038` |
| Implementation commit | `4e3adcf4da0c6a29f6d7ba4556b77e47e28e353a` |
| Base/task-issuance commit | `8c431484ca7814923a709c5b44136489ac4a81b9` |
| Review state | **APPROVED** |
| Approved capability | Read-only retrieval of one exact immutable stored ContentDocument by its own ID |
| Migration | None; Alembic remains at `c4d8f2a6b731` |
| Validation evidence | Developer-recorded: 2 focused T-038 tests, 41 complete ContentPackage/ContentDocument tests, 112 combined regressions, and 229 full-suite tests, each with one existing warning; Ruff; fresh upgrade; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The implementation is exactly one commit over the issued base. Exact 404 handling, one-row/no-autoflush query, shared stored serialization, state independence, repeatability, no-lock/no-write execution, row-count preservation, compatibility, documentation, and scope exclusions match the task with no blocking finding. |
| Boundaries | No model/schema/migration change, document list/review/release/lifecycle, PDF/HTML, publication, storage/download, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-039 behavior was included. |

---

## T-039 issued — Add independent ContentDocument human review

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add an independent DRAFT/APPROVED/REJECTED human-review decision to ContentDocument while keeping its stored payload immutable |
| Architectural phase | Canonical Content / Document Trust Boundary |
| Scope | Review metadata, one decision endpoint, response compatibility, database constraints, migration, and tests only; no release, list, PDF/HTML, publication, storage/download, delivery, learner, AI, or personalization behavior |
| Full implementation prompt | Appended to `docs/next_task.md` |

---

## T-039 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only independent DRAFT/APPROVED/REJECTED ContentDocument review metadata and `POST /api/v1/content-documents/{content_document_id}/approval`, preserving the immutable stored document payload |
| Migration | `b6f1d3a8e942` follows `c4d8f2a6b731`; existing documents become DRAFT with null decision metadata and no inferred approval |
| Tests | T-039 selection: 8 passed, 41 deselected, 1 warning in 1.25s. Complete ContentPackage/ContentDocument suite: 49 passed, 1 warning in 8.32s. Required regressions: 112 passed, 1 warning in 6.81s. Full suite: 237 passed, 1 warning in 15.71s. |
| Validation | Fresh and seeded upgrade/downgrade/re-upgrade, PostgreSQL constraints, changed-file Ruff, Alembic head/check, and diff checks passed against the dedicated T-039 PostgreSQL test database. |
| Notes | Approval locks only the target document, changes only review fields, commits once, rolls back failures, and preserves all stored content and related state. T-039 is Ready for review, not approved. No approved-document collection, release, PDF/HTML, publication, storage/download, delivery, learner, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, AGENTS, README, or T-040 work was added. |


---

## T-039 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-039` |
| Implementation commit | `5d954866cf18e5bbfeb89f0a465ce593645bdd45` |
| Base/task-issuance commit | `0c44c8e0fd2ea587339d18d4f9bf83f03103d882` |
| Review state | **APPROVED** |
| Approved capability | Independent DRAFT/APPROVED/REJECTED human review for ContentDocument while preserving its immutable payload |
| Migration | `b6f1d3a8e942` follows `c4d8f2a6b731`, adds only review metadata/constraints, and migrates existing documents to DRAFT without inferred approval |
| Validation evidence | Developer-recorded: 8 focused T-039 tests, 49 complete ContentPackage/ContentDocument tests, 112 combined regressions, and 237 full-suite tests, each with one existing warning; Ruff; fresh and seeded migration cycles; PostgreSQL probes; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The implementation is exactly one commit over the issued base. Model/migration alignment, safe legacy migration, response compatibility, UTC decisions, DRAFT reset, target-only locking, one-commit success, rollback, immutable-field preservation, state independence, tests, documentation, and exclusions match the task with no blocking finding. |
| Boundaries | No approved-document collection, document release/list/lifecycle, PDF/HTML, publication, storage/download, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-040 behavior was included. |

---

## T-040 issued — Add controlled ContentDocument release lifecycle

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add an independent one-way UNRELEASED/RELEASED/WITHDRAWN lifecycle to ContentDocument, requiring its own APPROVED review before release |
| Architectural phase | Canonical Content / Controlled Document Release |
| Scope | Release metadata, one decision endpoint, response compatibility, approval lock, database constraints, migration, and tests only; no released list, PDF/HTML, publication, storage/download, delivery, learner, AI, or personalization behavior |
| Full implementation prompt | Appended to `docs/next_task.md` |

---

## T-040 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only controlled UNRELEASED/RELEASED/WITHDRAWN ContentDocument state and `POST /api/v1/content-documents/{content_document_id}/release`, preserving independent review and immutable document payload |
| Migration | `d1a7c4e9f263` follows `b6f1d3a8e942`; existing documents become UNRELEASED with null release metadata and no inferred release |
| Tests | T-040 selection: 10 passed, 49 deselected, 1 warning in 1.86s. Complete ContentPackage/ContentDocument suite: 59 passed, 1 warning in 8.89s. Required regressions: 112 passed, 1 warning in 6.87s. Full suite: 247 passed, 1 warning in 17.49s. |
| Validation | Fresh and seeded upgrade/downgrade/re-upgrade, PostgreSQL constraints, changed-file Ruff, Alembic head/check, and diff checks passed against the dedicated T-040 PostgreSQL test database. |
| Notes | Release and conflicting approval decisions lock only the target document, commit once, roll back failures, and preserve the immutable stored payload and related state. T-040 is Ready for review, not approved. No document collection, PDF/HTML, publication, storage/download, delivery, learner, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, AGENTS, README, or T-041 work was added. |


---

## T-040 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-040` |
| Implementation commit | `9add651af5a8a07dd9d1a1739bbe90f6e6b19277` |
| Base/task-issuance commit | `426489d58513686871eb8a3315192cbdc03ea97c` |
| Review state | **APPROVED** |
| Approved capability | Controlled one-way ContentDocument UNRELEASED/RELEASED/WITHDRAWN lifecycle requiring the document’s own APPROVED review |
| Migration | `d1a7c4e9f263` follows `b6f1d3a8e942`, adds only release metadata/constraints, and migrates existing documents to UNRELEASED without inferred release |
| Validation evidence | Developer-recorded: 10 focused T-040 tests, 59 complete ContentPackage/ContentDocument tests, 112 combined regressions, and 247 full-suite tests, each with one existing warning; Ruff; fresh and seeded migration cycles; PostgreSQL probes; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The implementation is exactly one commit over the issued base. Transition ordering, stable errors, own-review eligibility, review lock, UTC provenance, document-only locking, one-commit success, rollback, database enforcement, immutable-field preservation, state independence, migration safety, tests, documentation, and exclusions match the task with no blocking finding. |
| Boundaries | No approved/released document collection, PDF/HTML, publication, storage/download, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-041 behavior was included. |

---

## T-041 issued — Add released ContentDocument read boundary

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add one read-only internal collection returning only currently RELEASED ContentDocument snapshots in stable document-ID order |
| Architectural phase | Canonical Content / Released Document Read Boundary |
| Scope | Exact document release-state filtering and stored response serialization only; no approved list, PDF/HTML, publication, storage/download, delivery, learner, AI, or personalization behavior |
| Full implementation prompt | Appended to `docs/next_task.md` |

---

## T-041 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only `GET /api/v1/content-documents/released`, returning currently RELEASED stored ContentDocument responses in ascending document-ID order |
| Migration | None; models, schemas, constraints, registration, and Alembic head `d1a7c4e9f263` remain unchanged |
| Tests | T-041 selection: 2 passed, 59 deselected, 1 warning in 1.44s. Complete ContentPackage/ContentDocument suite: 61 passed, 1 warning in 11.57s. Required regressions: 112 passed, 1 warning in 8.08s. Full suite: 249 passed, 1 warning in 23.68s. |
| Validation | Fresh dedicated `_test` upgrade reached `d1a7c4e9f263`. Changed-file Ruff, Alembic head/check, diff, and status checks passed. |
| Notes | The repository filters only RELEASED documents and orders by ID in one ContentDocument-only, no-autoflush, lock-free SELECT. Stored serialization performs no regeneration, checksum work, related-state evaluation, write, flush, or commit. T-041 is Ready for review, not approved. No approved list, PDF/HTML, publication, storage/download, delivery, learner, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, AGENTS, README, or T-042 work was added. |


---

## T-041 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-041` |
| Implementation commit | `210d3c7186ec8a5d344dfbbf99d669b7aa0d0292` |
| Base/task-issuance commit | `bb1db0872e444307501adb495418d24bd7f43091` |
| Review state | **APPROVED** |
| Approved capability | Read-only internal collection of currently RELEASED ContentDocument snapshots in ascending document-ID order |
| Validation evidence | Developer-recorded: 2 focused T-041 tests, 61 complete ContentPackage/ContentDocument tests, 112 combined regressions, and 249 full-suite tests, each with one existing warning; Ruff; fresh upgrade; Alembic head/check; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The implementation is exactly one commit over the issued base. Static-route precedence, exact release filtering, stable ordering, one-query behavior, shared stored serialization, related-state independence, zero-write behavior, tests, documentation, and exclusions match the task with no blocking finding. |
| Boundaries | No approved-document collection, PDF/HTML rendering, publication, storage/download, public/learner delivery, AI, source discovery, mock assembly, personalization, dependency, configuration, Docker, or T-042 behavior was included. |

---

## T-042 issued — Persist immutable deterministic PDF artifact

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Render and atomically persist at most one immutable PDF byte snapshot from one exact currently RELEASED ContentDocument |
| Architectural phase | Canonical Content / Deterministic PDF Artifact |
| Scope | Internal PDF generation, byte persistence, checksum, exact document ownership, and creation metadata only; no retrieval/download, publication, learner delivery, AI, or personalization |
| Full implementation prompt | Appended to `docs/next_task.md` |

---

## T-042 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only `POST /api/v1/content-documents/{content_document_id}/pdf-artifacts`, rendering and persisting at most one deterministic immutable PDF byte snapshot from one exact currently RELEASED ContentDocument |
| Migration | `e7b4c9d2a615` after `d1a7c4e9f263`; adds the supporting ContentDocument composite key and `pdf_artifacts` with exact ownership, uniqueness, PDF metadata, byte-size, checksum, and restricted-deletion constraints |
| Renderer | Dependency-free in-process `deterministic-pdf-v1`: fixed A4 layout, typography, pagination, object order, and metadata; Windows-1252 input is supported and unsupported characters fail before persistence |
| Tests | Focused T-042: 16 passed, 1 warning in 3.89s. Complete ContentPackage/ContentDocument: 61 passed, 1 warning in 10.45s. T-041 selection: 2 passed, 59 deselected, 1 warning in 1.30s. Required regressions: 112 passed, 1 warning in 7.46s. Full suite: 265 passed, 1 warning in 21.50s. |
| Validation | Fresh upgrade, seeded upgrade/downgrade/re-upgrade with zero inferred artifacts, direct PostgreSQL probes, changed-file Ruff, Alembic head/check, and diff checks passed against dedicated `_test` databases. |
| Notes | Creation validates missing/release/ordinary duplicate state before rendering, locks only the target document, persists copied ownership plus exact bytes/size/SHA-256, commits once, reloads stored metadata, and rolls back renderer or persistence failures. T-042 is Ready for review, not approved. No dependency, API key, external service, storage/download, publication, delivery, learner, AI, source discovery, mock assembly, personalization, or T-043 work was added. |


---

## T-042 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-042` |
| Implementation commit | `e41ab090ee9b715e473a72c25474f8ca58deb424` |
| Base/task-issuance commit | `896cc7069a70faf1af31c37824019bcf2ffc6c1b` |
| Review state | **APPROVED** |
| Approved capability | Atomic persistence of at most one immutable deterministic database-backed PDF artifact from one exact currently RELEASED ContentDocument |
| Migration | `e7b4c9d2a615` after `d1a7c4e9f263` |
| Validation evidence | Developer-recorded: 16 focused T-042 tests, 61 complete ContentPackage/ContentDocument tests, 2 T-041 selection tests, 112 required regressions, and 265 full-suite tests, each with one existing warning; Ruff; dependency-lock verification; Alembic head/check; fresh upgrade; seeded migration cycle; direct PostgreSQL probes; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The immutable commit is exactly one commit over the issued base. Persistence constraints, ownership, deterministic rendering, release eligibility, narrow locking, duplicate handling, one-commit atomicity, rollback behavior, migration safety, tests, documentation, and exclusions match the canonical task with no blocking finding. |
| Boundaries | No artifact retrieval/download, publication, external storage, public/learner delivery, dependency, API key, AI, source discovery, mock assembly, personalization, or T-043 behavior was included. |

---

## T-043 issued — Retrieve PDF artifact metadata and download exact stored bytes

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add internal read-only retrieval of one PdfArtifact's stored metadata and exact immutable PDF bytes |
| Architectural phase | Canonical Content / Deterministic PDF Artifact |
| Scope | Metadata lookup and exact byte download only; no regeneration, lifecycle, publication, external storage, learner delivery, AI, or personalization |
| Full implementation prompt | Appended to `docs/next_task.md` |

---

## T-043 implementation record

| Field | Value |
| --- | --- |
| Status | Ready for review |
| Scope | Add only `GET /api/v1/pdf-artifacts/{pdf_artifact_id}` metadata retrieval and `/download` exact stored-byte retrieval |
| Migration | None; models, constraints, registration, and Alembic head `e7b4c9d2a615` remain unchanged |
| Tests | Focused T-043: 4 passed, 16 deselected, 1 warning in 1.08s. Complete PdfArtifact: 20 passed, 1 warning in 3.12s. ContentPackage/ContentDocument: 61 passed, 1 warning in 9.52s. T-041 selection: 2 passed, 59 deselected, 1 warning in 1.30s. ContentVersion/T-030: 15 passed, 1 warning in 1.63s. NoteDraft: 43 passed, 1 warning in 3.26s. QuestionBankItem: 54 passed, 1 warning in 3.24s. Full suite: 269 passed, 1 warning in 19.78s. |
| Validation | Fresh dedicated `_test` upgrade reached unchanged head `e7b4c9d2a615`; lock verification, changed-file Ruff, Alembic head/check, and diff checks passed. |
| Notes | Both reads use one PdfArtifact-only, no-autoflush, lock-free query by artifact ID. Metadata excludes bytes; download returns the exact stored bytes and stored headers without rendering, hashing, related-state evaluation, or mutation. T-043 is Ready for review, not approved. No model, migration, renderer, dependency, configuration, Docker, storage, list, lifecycle, publication, learner, AI, personalization, or T-044 work was added. |


---

## T-043 review outcome

| Field | Value |
| --- | --- |
| Task ID | `T-043` |
| Implementation commit | `b6ef5943536380ed8cf18a09133ad5cd68f603ad` |
| Base/task-issuance commit | `45f4c71ed41d4dabc56278281182bed45d1800c0` |
| Review state | **APPROVED** |
| Approved capability | Internal metadata retrieval and exact stored-byte download of one immutable PdfArtifact by artifact ID |
| Migration | None; Alembic head remains `e7b4c9d2a615` |
| Validation evidence | Developer-recorded: 4 focused T-043 tests, 20 complete PdfArtifact tests, 61 ContentPackage/ContentDocument tests, 2 T-041 selection tests, 15 ContentVersion/T-030 tests, 43 NoteDraft tests, 54 QuestionBankItem tests, and 269 full-suite tests, each with one existing warning; Ruff; lock verification; Alembic head/check; fresh upgrade; and diff checks. GitHub exposes no status contexts or workflow runs, so no CI pass is claimed. |
| Review findings | The immutable implementation is exactly one commit over the issued base. Route order, stored metadata serialization, exact byte/header response, stable errors, PdfArtifact-only query boundary, state independence, zero-lock/write/render/hash behavior, tests, documentation, and exclusions match the canonical task with no blocking finding. |
| Boundaries | No model, schema, migration, renderer, dependency, configuration, Docker, list, ContentDocument-keyed lookup, artifact lifecycle, publication, public/learner delivery, AI, mock assembly, personalization, or T-044 behavior was included. |

---

## T-044 issued — Add independent PdfArtifact human review

| Field | Value |
| --- | --- |
| Status | Ready for VS Code Codex; not implemented |
| Goal | Add an independent DRAFT/APPROVED/REJECTED human-review decision to each immutable PdfArtifact while preserving its bytes, checksum, ownership, and read behavior |
| Architectural phase | Canonical Content / Artifact Trust Boundary |
| Scope | PdfArtifact review metadata, database invariants, one approval endpoint, and tests only; no release, publication, public delivery, or T-045 |
| Full implementation prompt | Appended to `docs/next_task.md` |