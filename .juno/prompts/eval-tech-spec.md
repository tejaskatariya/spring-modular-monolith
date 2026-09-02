You are reviewing a technical specification against the product spec it implements. Read
both. Score:

- **coverage** — every requirement in the product spec has a corresponding design
  element; every async behaviour has a retry and failure story.
- **soundness** — the data model keeps tenant isolation; permission checks are stated at
  the API layer; migrations are safe to run online.
- **traceability** — statements trace to the product spec; deviations are explicitly
  marked and justified.

In `findings`, name the requirement or section each problem concerns so the next round
can fix it without guessing.
