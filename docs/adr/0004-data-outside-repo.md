# ADR 0004: Never write to the user's repository

- Status: accepted
- Date: 2026-11-06

## Context

KnowYourDiff stores quiz sessions, scores and receipts. Storing them inside the repository
(for example in `.kyd/`) would dirty the working tree, risk being committed, and break the promise
that the MCP server is read-only on the repo.

## Decision

- History lives in SQLite under `platformdirs.user_data_dir("knowyourdiff")`, keyed by repository
  root path and index tree SHA.
- Receipts are printed or written only where the user explicitly asks (`kyd receipt --out ...`).
- The only git command that writes anything is `git write-tree`, which adds a tree object for the
  current index to the object database. This is the same object `git commit` would create, it does
  not change refs, the index or the working tree, and it gives a stable key for "this exact staged
  content".

## Consequences

- The MCP tools can honestly be annotated as read-only on the repository; local history writes are
  documented.
- Moving between machines does not carry history; that is acceptable for a personal log.
