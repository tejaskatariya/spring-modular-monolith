You are decomposing the approved spec and tech spec (in the context) into implementable
stories. The deliverable is a YAML file, and it must parse.

Shape:

```yaml
stories:
  - title: short imperative title
    description: >
      what to build and how to verify it, in a paragraph
    acceptanceCriteria:
      - testable statement
    dependsOn: [] # titles of stories that must land first
    estimate: S | M | L
```

Rules:

- Each story is independently shippable once its `dependsOn` are done.
- No story larger than L; split anything bigger.
- Migrations, API changes, background jobs, and UI land as separate stories when they
  can ship separately.
- Cover everything in the tech spec; nothing in the stories may contradict it.
