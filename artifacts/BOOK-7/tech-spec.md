# BOOK-7: Categories with browse-by-category — technical spec

Source: `artifacts/BOOK-7/spec.md` (product spec, all requirements R1 to R80).

## 1. Approach

Categories are a new small piece of read-mostly data next to `catalog.products`, reached
through the existing `ProductService` rather than through any new service that other
modules could depend on. The one decision that shapes everything else: category browsing
is implemented as an optional `category` query parameter on the existing `GET /products`
endpoint, not as a new path such as `/categories/{slug}`. This is forced by two existing
facts rather than chosen for style. `WebSecurityConfig` (`com.sivalabs.bookstore.config`)
permits anonymous `GET /products` today and requires authentication for anything not on
its explicit list, and that file sits outside the catalog module this item is scoped to
(R73). Adding a path would mean editing it. An optional parameter on a path already public
needs no security change and breaks no existing URL (R34, R49).

Two new tables live in the `catalog` schema: `categories` and `product_categories`, the
join table for the many-to-many link. Both are created, seeded with five categories, and
linked to the 15 existing seed products by a single new Flyway migration
(`V5__catalog_add_categories.sql`). `ProductService` gains a `getProducts(int pageNo,
@Nullable String categorySlug)` overload that both the header and the listing page use, so
there is exactly one query path into `catalog.products` (R52). `ProductWebController`
resolves `category`, delegates to that service method, and either renders the existing
`products`/`partials/products` templates with an added heading and empty-state, or throws
`CategoryNotFoundException`, caught by the existing `CatalogExceptionHandler` the same way
`ProductNotFoundException` is today.

The header is populated by a new Thymeleaf fragment (`partials/category-nav.html`) that a
package-private `CategoryNavController` (or a `@ModelAttribute`-style advice scoped to
catalog, see section 3) supplies to every request. `layout.html`, the one file outside the
catalog module this item touches, gains a single `th:replace` reference to that fragment
(R74). The controller behind the fragment reads categories from a new
`CategoryRepository.findAllByOrderByNameAsc()` call, catches any exception, logs it, and
falls back to an empty list so a database hiccup degrades the header rather than the page
(R76, R77). No admin screens, no REST endpoints, and no audit entries are added; every
requirement in the product spec that says "not in this item" is honored by simply not
building it.

## 2. Data model

All new tables live in the `catalog` schema, next to `catalog.products`, and carry no
`workspace_id`. That matches `catalog.products` as it stands today (it has none either)
and keeps every table category browsing touches inside one still-unscoped group, so a
future tenancy change can scope products, categories, and links together in one migration
instead of leaving categories scoped and products not (R50, spec section 4.7, open
question 6).

### `catalog.categories`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `bigint` | Primary key, sequence-generated, same pattern as `catalog.product_id_seq` |
| `name` | `varchar(100)` | `NOT NULL`, `UNIQUE` (R2) |
| `slug` | `varchar(100)` | `NOT NULL`, `UNIQUE` (R3), `CHECK (slug ~ '^[a-z0-9-]+$')` (R4) |

No `deleted_at`. Nothing in the product spec deletes a category (categories only ever
come from a migration, per R47), so a soft-delete column would be dead code.

### `catalog.product_categories`

| Column | Type | Notes |
| --- | --- | --- |
| `product_id` | `bigint` | `NOT NULL`, `REFERENCES catalog.products(id)` (R6) |
| `category_id` | `bigint` | `NOT NULL`, `REFERENCES catalog.categories(id)` (R6) |

Primary key is the pair `(product_id, category_id)`, which is what makes a repeated
insert fail outright rather than leave a duplicate row (R7). No `id` column is needed
since the pair is already unique and the table is never updated, only inserted into by
the seed migration.

**Migration note.** One new file, `V5__catalog_add_categories.sql`, in
`src/main/resources/db/migration/catalog` (the next free version after V4, R61). It:

1. Creates `categories` and `product_categories` with the constraints above.
2. Inserts the five rows from spec R9 using `INSERT ... ON CONFLICT (slug) DO NOTHING`,
   so a second deployment of the same release inserts nothing new (R14, R65).
3. Inserts the R10 links by joining on `catalog.products.code` and `catalog.categories.slug`,
   using `INSERT ... SELECT ... ON CONFLICT (product_id, category_id) DO NOTHING`. A code
   absent from the target database simply matches no row in the join and is skipped, so a
   database missing a seeded product does not fail the migration (R13).
4. Adds no column to `catalog.products`, so it takes no `ACCESS EXCLUSIVE` lock on that
   table. The foreign key on `product_categories.product_id` takes a `SHARE ROW EXCLUSIVE`
   lock on `catalog.products` only while the migration runs, which blocks concurrent writes
   (an admin saving a product edit) but not storefront reads (R67).

**Cost bound (R68).** The migration's cost is the size of the R10 table (15 codes,
32 links), not the size of `catalog.products`. The `INSERT ... SELECT` reads
`catalog.products` once to resolve 15 codes to ids; it does not scan or rewrite the whole
table. A test seeding 100,000 product rows and asserting the migration finishes within 60
seconds (R68) is described in section 4.

**Ordering:** category listing pages and the header both sort by `name` ascending (R18,
R42). Product ordering within a category ties back to `catalog.products.name` with
`catalog.products.code` as the tiebreak (R42) — no new sort column is needed.

## 3. API

There is no REST or JSON API for categories (product spec explicitly rules this out).
Everything below is a server-rendered page, matching the pattern `ProductWebController`
already uses.

### `GET /products` (existing endpoint, extended)

File: `com.sivalabs.bookstore.catalog.web.ProductWebController`.

- New optional request parameter: `category` (String, no default).
- Behavior:
  - `category` absent, empty, or all-whitespace → identical to today's behavior: full
    catalogue, same order, same page size (R32).
  - `category` present and non-blank → resolved case-insensitively against
    `catalog.categories.slug` (R29). Values longer than 100 characters are treated as no
    match before any query runs (R80), which also means no query parameter of unbounded
    length reaches the database.
  - No match → `CategoryNotFoundException` is thrown and caught by
    `CatalogExceptionHandler` (already scoped to `com.sivalabs.bookstore.catalog` by
    `@ControllerAdvice(basePackages = ...)`), rendering `error/404` with
    `errorMessage = "Category not found: " + slug` and HTTP 404 (R33, R35). This reuses
    the same handler method pattern as `ProductNotFoundException` — no new exception
    handler method is needed if `CategoryNotFoundException` also maps there, or one
    additional `@ExceptionHandler` method is added alongside the existing ones.
  - Match found → `productService.getProducts(page, slug)` is called instead of
    `productService.getProducts(page)`. The returned `PagedResult<ProductDto>` plus the
    resolved category's display name and total count are added to the model.
- Rendering: unchanged branching on `HtmxRequest.isHtmxRequest()` — full page `products`,
  htmx partial `partials/products`. Both templates gain a category heading and an
  empty-state block; the pagination fragment (`partials/pagination.html`) gains the
  `category` parameter on every link it builds so paging stays in the same category
  (R37, R43).
- Permission check: none beyond what exists today. `GET /products` is already
  `permitAll()` in `WebSecurityConfig`; this item adds no new security rule and touches
  no file under `com.sivalabs.bookstore.config` (R44 to R49, R73).
- API version: none. This is a Thymeleaf-rendered page behind an existing public route,
  not a versioned REST resource, so no version bump applies (R34).

### Header category navigation (new, server-rendered fragment)

- Fragment template: `src/main/resources/templates/partials/category-nav.html`,
  `th:fragment="category-nav"`, taking a list of categories as its model.
- Data supply mechanism: a package-private `@ControllerAdvice` class in
  `com.sivalabs.bookstore.catalog.web` (e.g. `CategoryNavModelAdvice`) that adds a
  `categories` attribute to every model, backed by `CategoryService.getAllCategories()`
  (a thin wrapper over `CategoryRepository.findAllByOrderByNameAsc()`). Using
  `@ControllerAdvice` rather than a new controller endpoint means `layout.html` renders the
  data with no change to any controller outside catalog and no controller in orders or
  cart needs to know categories exist (R75). `layout.html` itself only gains a
  `th:replace="~{partials/category-nav :: category-nav}"` reference (R74).
- One query per page render: `CategoryService.getAllCategories()` is called once per
  request by the advice; nothing in the fragment issues a second query (R23).
- Failure handling: the advice wraps the repository call in a try/catch, logs at `WARN`
  with the exception on failure, and supplies an empty list so the template renders the
  header with no category area rather than propagating the failure into a 500 for pages
  that don't otherwise need categories (R76, R77).
- Highlighting the active category: the advice (or the controller for `/products`) also
  adds the resolved `activeCategorySlug` to the model when one is present, and the
  fragment compares it against each entry to add a "current" CSS class (R21).
- No permission check: available to every request, matching R44 to R46.

## 4. Background work

There is no background job in this item. Category and link data are created once, by the
Flyway migration described in section 2, which runs synchronously at application startup
as part of the existing Flyway integration already wired into the project. There is no
new scheduler, queue consumer, or async task.

- **Trigger:** application startup, via Spring Boot's existing Flyway auto-migration.
- **Retry story:** none, matching every other migration in this project. Flyway does not
  retry a failed migration; a failed migration prevents the application context from
  starting (R66).
- **Failure visibility:** a failed migration surfaces in the startup logs through Flyway's
  own error reporting, the same way a failure in V1 through V4 would today. Whether the
  previous version keeps serving traffic during that failure depends on the deployment
  mechanism (rolling deploy, blue-green, and so on), not on anything built in this item, so
  that is called out as an environmental assumption rather than a requirement (R66).

**Automated tests that exercise the migration** (not background jobs, but worth stating
here since they are the operational proof for section 4.9's requirements):

- A test that runs the migration against a database already holding the 15 seed products,
  then asserts the Fantasy category returns exactly The Chronicles of Narnia and A Game of
  Thrones, and that The Little Prince appears on Fiction, Classics, and Young Adult (R15).
- A test that runs the migration twice against the same database and asserts the category
  count and link count are unchanged after the second run (R14).
- A test, tagged as slow, that seeds `catalog.products` with 100,000 rows before running
  the migration and asserts completion within 60 seconds (R68). This test must run in the
  pipeline gating merges to `main`.

## 5. Audit and observability

**Audit.** Nothing in this item appends an audit entry. Every action a shopper takes here
is a read: viewing the header, opening a category, paging within one. The product spec
treats read traffic on the catalogue as not warranting an audit trail entry (recording
every page view would flood the log with entries that don't describe a change), and this
item introduces no state-changing action for a user to take. Seeding categories and links
is a migration, not a user action, so it is not audited either (R56 to R58, R60). When
admin category management is eventually built (open question 2), create, rename, delete,
and re-linking a product's categories must be audited the same way product edits are
audited at that time (R59) — this item does not build that, so it does not need to
implement it, only avoid precluding it.

**Logging.**

- The category-nav advice logs a single `WARN` line, including the exception, when the
  category lookup for the header fails (R77). No stack trace or database detail reaches
  the rendered page.
- A category page request that fails because the database is unreachable renders the
  application's standard error page (`error/500`, via the existing `Exception` handler in
  `CatalogExceptionHandler`) with a message that names no database objects (R78). No new
  logging is added here beyond what the existing generic exception handler already does,
  since it already logs unexpected exceptions before rendering `error/500`.
- No metrics, traces, or dashboards are added. The product spec does not call for any, and
  none of open questions 4 or 5 (caching, SEO treatment) are in scope for this item.

## 6. Risks

- **Migration takes a lock on `catalog.products`.** Creating the foreign key from
  `product_categories.product_id` to `catalog.products.id` takes a `SHARE ROW EXCLUSIVE`
  lock on `products` for the duration of the migration (R67). This blocks concurrent
  writes, meaning an admin editing a product at the exact moment of deployment waits
  rather than fails, and does not block storefront reads. Bounded by keeping the migration
  itself fast (R68) so the lock window is short.
- **Migration re-run or parallel migration version collision.** If another change lands a
  migration in the same catalog folder around the same time, whichever merges second must
  take the next free version number (R61); if both land on the same number, Flyway raises
  a checksum error at startup, which is the visible signal to fix the collision before
  redeploying. This is a process risk rather than a code risk, and it is called out
  explicitly in the product spec's edge cases so a reviewer catches it in code review.
- **Header failure risk is contained but not eliminated.** If the database is briefly
  unreachable, every page loses its category navigation, not just category pages. The
  design bounds the damage to that: the rest of each page still renders with HTTP 200
  (R76). The alternative, failing the whole page when the header can't load, was rejected
  because pages like cart and orders don't depend on categories to be useful.
- **Header could crowd out with more categories.** With five seeded categories, R22
  showing every category in the header is fine. Nothing in this item can grow that count,
  since categories only come from the seed migration (R47), so the crowding risk is
  deferred to whichever item builds admin category management (open question 3), not
  something this item needs to guard against today.
- **Empty catalogue for a fresh product with no category.** After this item ships, a
  product an admin adds through the existing admin screens belongs to no category, since
  category assignment is not built here (open question 2). It is still reachable from the
  full `/products` listing (R8), so it isn't lost, only absent from category browsing until
  admin management exists.
- **Slug injection or malformed input.** The `category` parameter is bound to a
  parameterized query through Spring Data (a derived repository method, not string
  concatenation), and length is capped before any query executes (R80). Combined with the
  case-insensitive exact match against a fixed slug format (R4), no value of `category` —
  quotes, SQL fragments, percent-encoded bytes — can reach the database as anything other
  than a bind parameter, and any non-matching value falls through to the R33 404 rather
  than a partial match or an error (R79).
- **Read-your-writes race between the count and the page.** The category count (R27) and
  the page of products are two reads in the same request; a product soft-deleted between
  them can make the count momentarily one higher than the visible cards. This mirrors
  existing behavior on `/products` today and self-corrects on the next page load, so it is
  accepted rather than fixed with locking, per the product spec's edge cases section.
