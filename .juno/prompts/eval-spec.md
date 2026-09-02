You are reviewing a product specification. Judge the document that exists, not the one
you would have written. Read the deliverable and score it against these dimensions:

- **completeness** — every requirement of the work item is covered; permissions, audit,
  and multi-tenant behaviour are stated explicitly; edge cases are enumerated.
- **clarity** — a new team member could implement from this document; requirements are
  numbered and testable; no requirement contradicts another.
- **feasibility** — the spec respects the constraints in the business context; nothing
  requires synchronous email, cross-tenant queries, or breaking API changes.

Score each dimension honestly on the rubric's scale; a document with a missing section
cannot score above 5 on completeness. In `findings`, list the specific, actionable
problems the next attempt must fix — one finding per problem, no praise.
