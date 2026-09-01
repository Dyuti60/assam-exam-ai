# Assam Exam AI — Task Log

## Register rules

This is an append-only task register. Add new entries without deleting or rewriting historical entries. Record test results and commit identifiers only when evidence is available.

## Entries

### T-001 — Documentation workflow baseline

| Field | Value |
| --- | --- |
| Issued | 2026-09-02 |
| Status | Ready for review |
| Prompt source | User request and supplied `architecture.md`, `workflow.md`, `task_log.md`, and `next_task.md`; supplied documents treated as reference content |
| Scope | Add the four living documentation files only |
| Tests | Not run; documentation-only task |
| Checks | `git diff --check` and `git status --short` required before handoff |
| Implementation commit | Pending — user requested no commit |
| Documentation-review commit | Pending |
| Review result | Pending |
| Notes | No application code, models, migrations, dependencies, or tests may change in T-001 |

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
