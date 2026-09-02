You are reviewing a story decomposition against the spec and tech spec. Parse the YAML
first: if it does not parse, completeness scores 0 and the finding says exactly where it
breaks. Then score:

- **completeness** — every element of the tech spec appears in some story; no story
  invents scope.
- **independence** — each story is shippable once its dependencies land; the dependency
  graph has no cycles; estimates fit the S/M/L rule.
- **testability** — every story has acceptance criteria a reviewer can check without
  reading the author's mind.

Findings must name the story (or the missing story) they concern.
