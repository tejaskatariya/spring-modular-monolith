---
name: juno-spec-writer
description: House rules for writing a product specification — structure, the requirement style, and what must never be left implicit. Use when drafting or revising a product spec.
---

# Writing a product specification

You are writing a spec another team implements without asking you questions.

## Structure

Use exactly these headings, in this order:

1. **Problem** — who hurts today, and the evidence.
2. **Goals / non-goals** — what this must do, and what it deliberately will not.
3. **User stories** — `<role> can <action> so that <outcome>`, one per role touched.
4. **Requirements** — numbered and individually testable.
5. **Edge cases and failure modes** — invalid input, races, partial failure.
6. **Open questions** — phrased as a decision someone must make.

## Requirement style

- One requirement per number. If it contains "and", consider splitting it.
- Write what is observable, not how it is built: "an admin sees a pending
  invite in settings", not "add a pending_invites table".
- Every requirement must be checkable by a reviewer who cannot read your mind.

## Never leave implicit

State these explicitly, even when they seem obvious:

- **Permissions** — which roles can do this, and what the others see.
- **Tenancy** — how the change stays scoped to one workspace.
- **Audit** — which actions append an audit entry.
- **Failure** — what the user sees when the operation cannot complete.

## Revising

When you are given findings from an earlier round, address each one directly
and say what changed. Do not restate the old text unchanged.
