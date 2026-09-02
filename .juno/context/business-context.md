# Business context

We build a collaboration SaaS for small and mid-size product teams. The product is a
workspace: members share documents, tasks, and audit history. Plans are Free, Team, and
Enterprise; Enterprise adds SSO, audit exports, and priority support.

Constraints that apply to every feature:

- Multi-tenant Postgres; every table is scoped by `workspace_id`, and every query must be.
- Roles are `admin`, `member`, `guest`. Only admins change workspace membership or settings.
- All user-visible actions append to the audit log.
- Emails go through our transactional mail service; no feature may send mail synchronously
  from a request handler.
- The public API is versioned; breaking changes ship behind a new version, never in place.

When a requirement is ambiguous, prefer the reading that protects tenant isolation and
admin control, and say explicitly which reading you chose.
