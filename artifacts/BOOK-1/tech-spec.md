# BOOK-1: Product search and filtering — technical spec

Source: `artifacts/BOOK-1/spec.md`. Requirement IDs below (R1, R33, etc.) refer to
that document.

## 1. Approach

The one decision that shapes everything else: search stays inside the existing
`catalog` module and runs through the existing `ProductService` /
`ProductRepository` layer, with no second query path to `catalog.products`. A
`tsvector` column is added to the table, generated automatically from `name`
and `author` and backed by a GIN index, so Postgres does the matching instead
of the application scanning rows. Because the generated column is
`GENERATED ALWAYS ... STORED`, it is recomputed by Postgres on every insert or
update in the same transaction as the write, which is what lets author search
work immediately after an admin saves a product with no reindex step (R36).

The query itself cannot be expressed as a Spring Data derived query or plain
JPQL, because JPQL has no `tsvector`, `@@`, `to_tsquery`, or `ts_rank`
operators. It is implemented as a native SQL query behind the same
`ProductRepository` interface (a repository-level concern, not a new module or
a new controller). The free-text box is parsed into a Postgres `tsquery` on
the Java side: the input is split on whitespace, each token has `tsquery`
operator characters stripped out, the tokens are joined with `AND`, and the
final token gets a `:*` prefix suffix. That string is passed to
`to_tsquery('simple', ?)` as a bind parameter, never concatenated into SQL, so
arbitrary punctuation, quotes, and boolean operators in shopper input become
ordinary search text instead of a syntax error or an injection vector (R62).
The `simple` text search configuration is used on both the column and the
query side, because it lowercases and tokenizes without stemming or a
stopword list, which keeps `coelho` matching only `coelho` rather than
Postgres silently expanding or dropping words.

Sorting adds a small fixed set of `ORDER BY` fragments (price ascending, price
descending, title ascending, title descending, and relevance-by-`ts_rank`),
selected from a whitelist keyed by a sort enum rather than built from request
text. Every fragment ends with the product code as a tie-breaker, which is
what keeps paging stable when many seeded books share a price (R20). No new
table, no new module, and no REST API are added; the change is new optional
query parameters on the existing `GET /products` route and a new `author`
field on the existing admin product form.

## 2. Data model

All changes are to the single existing table `catalog.products`
(schema `catalog`, entity `ProductEntity`, `src/main/java/com/sivalabs/bookstore/catalog/domain/ProductEntity.java`).

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `author` | `text` | yes | New. Free text, no DB-level length constraint, consistent with how every other text column in this table is defined today (`code`, `name`, `description`, `image_url` are all `text` with no `varchar(n)`). The 255-character limit from R31 is enforced in the admin form layer via Bean Validation (`@Size(max = 255)`), not in the schema. |
| `search_vector` | `tsvector` | n/a (generated) | New. `GENERATED ALWAYS AS (setweight(to_tsvector('simple', coalesce(name,'')), 'A') \|\| setweight(to_tsvector('simple', coalesce(author,'')), 'B')) STORED`. Title (`name`) and author only, per R7 and R9 — description, `code`, and `image_url` are never inputs to this column. |

New index: `idx_products_search_vector` — `GIN (search_vector)` on
`catalog.products` (R7).

**Workspace scoping.** `catalog.products` has no `workspace_id` column today,
and this migration does not add one.

DEVIATION: this departs from the standing business constraint that every
table is scoped by `workspace_id` and every query filters on it. The product
spec addresses this directly in section 4.7 and commits to the reading that
adding tenant scoping to the catalog is out of scope for this item (see the
spec's non-goals and open question 5). The design keeps that gap from getting
wider: search runs through the same `ProductService`/`ProductRepository` layer
the existing listing already uses (R43), returns strictly a subset of what
that listing would return across all pages (R44), and applies the same
`deleted_at is null` scoping condition the listing applies today (R45). If
`workspace_id` is added to the catalog in a future item, it lands once in that
shared layer and search inherits it automatically, with no separate change to
the search query.

**Migration note.** One new Flyway script,
`V5__catalog_add_search.sql`, in `src/main/resources/db/migration/catalog/`
(the existing folder; current latest is `V4__catalog_add_deleted_at_to_products.sql`).
It runs, in order, inside Flyway's default per-migration transaction (R61, no
new `.conf` file added):

1. `ALTER TABLE catalog.products ADD COLUMN author text;`
2. An `UPDATE` that sets `author` for the 15 rows listed in R33, matched by
   `code`, restricted to rows where `author` is currently null or blank
   (R34), so a hand-edited author from before the upgrade is left alone.
3. `ALTER TABLE catalog.products ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (...) STORED;`
4. `CREATE INDEX idx_products_search_vector ON catalog.products USING GIN (search_vector);`

Step 3 rewrites every existing row because the generated column is `STORED`,
and step 4 builds the index against that rewritten table. Both happen while
the migration holds an `ACCESS EXCLUSIVE` lock on `catalog.products` (R57) —
see Risks. Steps 1–2 preserve every existing row's `code`, `name`,
`description`, `image_url`, `price`, and `deleted_at` unchanged; the only
value the migration writes to an existing row is `author`, and only under the
R34 condition (R54).

## 3. API

There is no REST controller and no API versioning scheme anywhere in this
codebase today (confirmed: zero `@RestController` usages, no `/api/v*`
paths). Every route, including this one, is an unversioned server-rendered
Thymeleaf + htmx route on a plain `@Controller`. R42 requires that this item
not need a new API version, which matches the codebase having no such concept
to bump — there is nothing to state as "the API version this lands in"
because the routes described below are the same routes that exist today, with
additional optional parameters.

### `GET /products` (storefront, `ProductWebController`)

Existing route, extended with new optional query parameters. Existing
`page`-only calls keep working unchanged (R42).

| Param | Type | Notes |
| --- | --- | --- |
| `q` | string, optional | Free text, matched against title and author. Blank, missing, or whitespace-only is treated as no search (R2). Longer than 200 characters is rejected (R10). |
| `minPrice` | decimal, optional | Inclusive lower bound (R12). Non-numeric or negative is rejected (R13). |
| `maxPrice` | decimal, optional | Inclusive upper bound (R12). Non-numeric or negative is rejected (R13); less than `minPrice` is rejected (R14). |
| `sort` | string, optional | One of `price_asc`, `price_desc`, `title_asc`, `title_desc` (R16). Unrecognized values are ignored, not rejected (R21). |
| `page` | int, default 1 | Unchanged from today. Values below 1 clamp to 1 (R26); values past the last page render an empty grid with working pagination (R27). |

Binding uses a small `@ModelAttribute` criteria object validated with
`@Valid`, the same `BindingResult` pattern the admin create/edit forms already
use (`AdminProductWebController`), so a validation failure re-renders the
current view (full page or, for an htmx request, the `partials/products`
fragment — same `HtmxRequest` check the controller already does) with the
message from R10/R13/R14, an empty result grid, and the search box holding
what the shopper typed. This is a rendered-page outcome, not a redirect or a
JSON error body, consistent with how this route behaves today.

Sort resolution: an explicit, recognized `sort` always wins (R19). Otherwise,
if `q` is blank, sort is title ascending (R17, matching today's default).
Otherwise (non-blank `q`, no explicit sort), sort is relevance via
`ts_rank` against `search_vector`, most relevant first (R18). Every ordering
appends the product code ascending as a final tie-break (R20).

Permission: unchanged. `GET /products` is already `permitAll()` in
`WebSecurityConfig` (`src/main/java/com/sivalabs/bookstore/config/WebSecurityConfig.java:38-39`).
Search, filtering, and sorting inherit that same rule with no new security
configuration (R37). A signed-in member hits the same code path and gets the
same results as an anonymous visitor for the same parameters (R38); nothing
in this design branches on authentication.

Response: same two view names as today, `products` (full page) and
`partials/products` (htmx fragment), both extended with the search box, min
and max price inputs, a sort control, a total-match count (R23), and a
no-results state with a control that clears search/filter/sort back to the
full catalogue (R28). Pagination links in both views are extended to carry
`q`, `minPrice`, `maxPrice`, and `sort` alongside `page` (R24), and the
browser URL reflects the same four parameters so a copied URL reproduces the
page (R25). Both the full-page and htmx-fragment paths use the same
`ProductService` call, so search/filter/sort/paging behave identically for
both (R29).

### `GET /admin/catalog/products` (admin, `AdminProductWebController`)

Unchanged. No search, filter, or sort parameters are added to the admin list
(R41); it keeps listing all products including soft-deleted ones, unpaginated
by anything other than the existing page number.

### `POST /admin/catalog/products` and `POST /admin/catalog/products/{code}/edit`

Existing create and edit routes gain one new optional field.

`CreateProductCmd` and `UpdateProductCmd`
(`src/main/java/com/sivalabs/bookstore/catalog/domain/`) each gain:

```java
@Nullable @Size(max = 255, message = "Author is limited to 255 characters") String author
```

This is the first `@Size` constraint in the codebase; every other text field
on these commands is validated only for presence (`@NotBlank`/`@NotNull`),
not length, so this is a small, explicit addition rather than following an
existing pattern. Validation failure re-renders the form with the R31 message
via the existing `BindingResult` → `th:errors` flow the form already uses for
`code`, `name`, and `price`. The field is wired through `ProductMapper` into
`ProductEntity.author` and out through `ProductDto`.

Permission: unchanged. `/admin/**` is already `hasRole("ADMIN")` in
`WebSecurityConfig` (line 36-37). A member or anonymous visitor requesting
these routes is refused by that existing rule; this item adds no new check
(R40).

## 4. Background work

None. There is no new scheduled job, message, or queue consumer in this item.

- The search index is not maintained by a job. `search_vector` is a `STORED`
  generated column, so Postgres recomputes it synchronously, inside the same
  transaction, whenever a row's `name` or `author` changes — including an
  admin's save through the existing create/edit routes above. This is what
  makes R36 ("no reindex step, no scheduled job") true by construction rather
  than by a job that has to be triggered and could fail to run.
- The seed author backfill (R33) is a statement inside the V5 migration, not
  a job. It runs once, synchronously, at application startup, in the same
  Flyway-managed transaction as the rest of the migration.

**Migration execution, trigger, retry, and failure visibility** (applies to
the whole `V5` script, not a separate background process): triggered by
Flyway on application startup, the same mechanism already used for `V1`–`V4`.
Flyway does not automatically retry a migration that fails; a failed attempt
does not get silently reattempted on the next startup (R55), and re-running
the same already-applied migration a second time is a no-op via Flyway's
schema history table. Failure visibility is a fatal exception in the startup
logs, and the application does not become ready, so the previously deployed
version keeps serving traffic and health checks do not route to the failed
instance (R56). None of this is new configuration; it is the existing
Flyway/Spring Boot startup behavior this repository already relies on for
every prior catalog migration.

## 5. Audit and observability

**Audit.** This repository has no audit log implementation today — no audit
table, entity, or service exists anywhere in the codebase (confirmed by a
repo-wide search). Given that:

- Search, filtering, sorting, and paging append no audit entry (R47). There
  is nothing to append to, so this requires no new code.
- Setting or changing a product's author through the admin form is a product
  edit like any other field on that form, and today no product edit of any
  kind writes an audit entry. R48 requires the author field to be "audited
  exactly the way other product edits are audited today" and explicitly
  states this is not an exemption if that turns out to be nothing — so this
  item adds no audit entry for author edits either. If a general product-edit
  audit log is introduced in a later item, the author field is a product
  field like any other at that point and would be covered by whatever that
  item builds; this item does not build it.
- The R33 seed backfill runs as a migration step, not a user action, and
  appends no audit entry (R49).
- No other audit behavior in the application changes (R50).

**Observability / logging.** No new metrics or structured logging are added
by this item; none are required by the product spec. Two existing pieces of
behavior are relevant and are called out under Risks below because they need
a small check, not because they need new code:

- `CatalogExceptionHandler`
  (`src/main/java/com/sivalabs/bookstore/catalog/web/CatalogExceptionHandler.java`)
  already logs unexpected exceptions at `error` level and renders
  `error/500`. The search query flows through the same controller package,
  so a database-unreachable or timeout error during search is logged and
  rendered the same way an unexpected error in any other catalog route is
  today, satisfying the "logged, not a raw stack trace to the shopper" half
  of R63.
- The migration failure path (section 4) is the observability story for
  R56: a fatal Flyway exception in the startup logs, no separate log
  statement needed.

## 6. Risks

- **Migration lock window.** Adding the `STORED` generated column rewrites
  every row in `catalog.products`, and the rewrite plus the GIN index build
  hold an `ACCESS EXCLUSIVE` lock for the full duration. Concurrent
  storefront reads and admin edits queue behind the lock and complete
  afterward rather than failing (R57) — this is accepted for tables up to
  100,000 rows (R58), verified by a migration test seeding 100,000 rows and
  asserting completion within 60 seconds (R59). Damage is bounded by keeping
  this a pre-release gate: release notes must state the row-count check from
  R60, and open question 6 in the product spec, whether any real environment
  exceeds the ceiling, has to be answered before this ships to that
  environment. This spec does not build a lower-lock alternative (concurrent
  index build, trigger-based backfill); R61 fixes the single-transaction
  shape deliberately, for the reasons the product spec section 4.9 gives.
- **Error message leakage on unexpected exceptions.** The existing generic
  handler in `CatalogExceptionHandler` (`handle(Exception e)`) puts
  `e.getMessage()` into the model shown on `error/500`. R63 requires that a
  database-unreachable or timeout error not name database objects to the
  shopper. Today's generic handler was not written with a database-facing
  query in the catalog module in mind, and a raw JDBC/driver exception
  message can contain schema, table, or column names. This needs a
  concrete check as part of implementation: either the search code path
  catches `DataAccessException` specifically and rethrows a generic message
  before it reaches this handler, or the generic handler itself stops
  exposing `e.getMessage()` for unclassified exceptions. Left unaddressed,
  this is the one place R63 could silently fail.
- **`tsquery` construction bugs.** Building the `tsquery` string by hand
  (strip operator characters, join with `AND`, suffix the last token with
  `:*`) is the one piece of new, non-declarative logic in this item. A bug
  here could either throw on certain input (violating R62) or silently
  change what matches. Mitigated by keeping the string always passed as a
  bind parameter (never concatenated into SQL), by stripping `tsquery`
  operator characters before building the string rather than escaping them,
  and by a test suite that specifically exercises punctuation, quotes, and
  boolean-operator input (`&`, `|`, `!`) per R62's own examples.
- **Query plan regression.** A later change to the query, the generated
  column, or the index could quietly turn search back into a sequential
  scan while every functional test still passes, since a seq scan returns
  the same rows, just slower. R8's test is the guard: it seeds 5,000+ rows,
  asserts the plan contains a bitmap scan on the GIN index and no sequential
  scan on `catalog.products`, and must not set `enable_seqscan = off`. This
  test has to actually run in the pipeline that gates a merge, not just
  exist, or the regression it is meant to catch ships silently.
- **Backfill overwriting a hand-edited author.** The R33 backfill only
  updates rows matched by `code` from the 15-row table, and only when
  `author` is currently null or blank (R34). Getting that `WHERE` clause
  wrong is a plausible one-line mistake with real consequences (silently
  discarding an admin's data), which is why R35 requires a test that checks
  actual search results (`coelho` → exactly The Alchemist,
  `martin` → exactly A Game of Thrones) after the migration runs, not just
  that the `UPDATE` executed without error.
- **Dynamic `ORDER BY` stays a fixed whitelist.** The five sort options are
  implemented as five fixed SQL fragments selected by an enum, not built by
  interpolating the `sort` request parameter into SQL text. This has to stay
  true as a design constraint if this query is ever extended with more sort
  options; string-building an `ORDER BY` clause from request input would
  reopen the injection surface R62 closes for the search text itself.
- **Result drift under concurrent admin edits.** An admin editing a price or
  title, or soft-deleting a product, between a shopper's page loads can shift
  a result across a page boundary or make a listed product disappear on
  click-through. The product spec's edge cases section accepts this for a
  catalogue of this size and explicitly rules out snapshot or cursor paging
  as a fix for this item; no mitigation is built here.
