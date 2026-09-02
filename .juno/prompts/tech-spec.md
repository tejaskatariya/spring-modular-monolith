You are writing a technical specification from the approved product spec in the context.
The deliverable is a Markdown document an engineer picks up cold.

Structure:

1. **Approach** — the design in three paragraphs or fewer, with the one decision that
   shapes everything else called out.
2. **Data model** — new or changed tables/columns, each with its `workspace_id` scoping
   and migration note.
3. **API** — endpoints or messages, request/response shapes, permission checks, and the
   API version they land in.
4. **Background work** — every async job, its trigger, its retry story, and its failure
   visibility.
5. **Audit and observability** — which audit events are appended and what gets logged.
6. **Risks** — what could go wrong in production and how the design bounds the damage.

Every statement must trace to the product spec or the business constraints. Mark any
deviation from the product spec explicitly as `DEVIATION:` with a reason.
