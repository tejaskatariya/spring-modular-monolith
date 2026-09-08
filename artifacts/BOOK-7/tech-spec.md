# BOOK-7: Categories with browse-by-category — technical spec

Source: `artifacts/BOOK-7/spec.md` (product spec, all requirements R1 to R80).

## 1. Approach

Categories are a new, small piece of read-mostly data next to `catalog.products`, reached
through the existing catalog service layer rather than through any new service that other
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
(`V5__catalog_add_categories.sql`). The controller resolves a `category` slug to a
category **before** asking for products (section 3 explains why), then asks
`ProductService` for a page of products optionally filtered by that category's id.
`ProductWebController` either renders the existing `products`/`partials/products`
templates with an added heading and empty-state, or lets `CategoryNotFoundException`
propagate to the existing `CatalogExceptionHandler`, the same way `ProductNotFoundException`
is handled today.

The header is populated by a new Thymeleaf fragment (`partials/category-nav.html`) that a
package-private `@ControllerAdvice` in `com.sivalabs.bookstore.catalog.web` supplies to
every request. `layout.html`, the one file outside the catalog module this item touches,
gains a single `th:replace` reference to that fragment (R74). The advice reads categories
from `CategoryRepository.findAllByOrderByNameAsc()`, and separates two outcomes that look
similar but are not: a database with zero categories (normal, nothing logged) and a
category query that throws (a failure, logged at `WARN` and hidden from the shopper).
Section 5 spells out that distinction, since it is easy to collapse the two into "the
advice returns an empty list" and miss that only one of them should produce a log line.
No admin screens, no REST endpoints, and no audit entries are added; every requirement in
the product spec that says "not in this item" is honored by simply not building it.

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

`workspace_id`: none, matching `catalog.products` (R50). No `deleted_at`. Nothing in the
product spec deletes a category (categories only ever come from a migration, per R47), so
a soft-delete column would be dead code.

### `catalog.product_categories`

| Column | Type | Notes |
| --- | --- | --- |
| `product_id` | `bigint` | `NOT NULL`, `REFERENCES catalog.products(id)` (R6) |
| `category_id` | `bigint` | `NOT NULL`, `REFERENCES catalog.categories(id)` (R6) |

`workspace_id`: none, for the same reason as above (R50, R51 — both foreign keys point at
tables inside the `catalog` schema only, so a later tenancy change can scope products,
categories, and this link table together).

Primary key is the pair `(product_id, category_id)`, which is what makes a repeated
insert fail outright rather than leave a duplicate row (R7). No `id` column is needed
since the pair is already unique and the table is never updated, only inserted into by
the seed migration. A product can hold any number of link rows, so one product appearing
in several categories (R31, exercised by P102 and P109 under R11) is just several rows
sharing a `product_id`, each of which the category-page query treats identically.

**Migration note.** One new file, `V5__catalog_add_categories.sql`, in
`src/main/resources/db/migration/catalog` (the next free version after V4, R61). It:

1. Creates `categories` and `product_categories` with the constraints above (R62). It adds,
   alters, and drops no column of `catalog.products` (R64, R67).
2. Inserts the five rows from spec R9 using `INSERT ... ON CONFLICT (slug) DO NOTHING`,
   so a second deployment of the same release inserts nothing new (R14, R65).
3. Inserts the R10 links by joining on `catalog.products.code` and `catalog.categories.slug`,
   using `INSERT ... SELECT ... ON CONFLICT (product_id, category_id) DO NOTHING`. A code
   absent from the target database simply matches no row in the join and is skipped, so a
   database missing a seeded product does not fail the migration (R13, R63).
4. Adds no column to `catalog.products`, so it takes no `ACCESS EXCLUSIVE` lock on that
   table. The foreign key on `product_categories.product_id` takes a `SHARE ROW EXCLUSIVE`
   lock on `catalog.products` only while the migration runs, which blocks concurrent writes
   (an admin saving a product edit) but not storefront reads (R67).

**Cost bound (R68).** The migration's cost is the size of the R10 table (15 codes,
32 links), not the size of `catalog.products`. The `INSERT ... SELECT` reads
`catalog.products` once to resolve 15 codes to ids; it does not scan or rewrite the whole
table. A test seeding 100,000 product rows and asserting the migration finishes within 60
seconds is described in section 4.

**Ordering.** The header lists categories by `name` ascending (R18). The category-page
product query sorts by `catalog.products.name` ascending with `catalog.products.code` as
the tiebreak (R42) — no new sort column is needed, and this tiebreak is added only to the
category-filtered query (section 3); the unfiltered `/products` sort is unchanged.

## 3. API

There is no REST or JSON API for categories (product spec explicitly rules this out).
Everything below is a server-rendered page, matching the pattern `ProductWebController`
already uses. There is no API version scheme in this project (no versioned REST resource
exists for the catalogue today), so nothing here lands in a version; `GET /products`
simply gains an optional parameter.

### Category resolution: where it happens

The controller resolves the `category` slug to a category, and raises
`CategoryNotFoundException` there, **before** calling `ProductService` for a page of
products. `ProductService` never sees a slug: it takes a resolved `categoryId` (a `Long`)
or nothing at all. Two reasons drove this split rather than folding resolution into the
product query:

- It keeps the two failure/edge cases in section 4.4 of the product spec structurally
  separate in code, not just in prose. "No such category" (R33 — a 404) is raised by
  `CategoryService`/`CategoryRepository`, before any product query runs. "Category exists
  but has no visible products" (R39 — an empty grid, HTTP 200) is a normal, non-empty
  `Page` result with zero content rows, produced by `ProductService`. Because these come
  from two different calls, there is no shared code path where a bug could turn one into
  the other.
- `CategoryDto`'s display name (needed for the R26 heading) is already in hand from the
  resolution call, so the controller does not need a second lookup or a wrapper DTO to get
  it.

This costs one extra query compared to folding resolution into the product query: when a
category filter is active, the request issues one query to resolve the slug
(`CategoryRepository.findBySlug`) and one query to page the products
(`ProductRepository.findAllByCategoryIdAndDeletedAtIsNull`), against zero queries added
when `category` is absent. That second query's `Page` also carries `totalElements`, which
is what R27's product count uses directly, so no third, separate `COUNT` query is added.

**Case-insensitive slug matching (R29), the actual mechanism.** `CategoryService`
strips and lower-cases the incoming parameter (`category.strip().toLowerCase(Locale.ROOT)`)
before querying. The repository call is a plain equality lookup,
`CategoryRepository.findBySlug(normalizedSlug)`, not a case-insensitive SQL comparison or
`ILIKE`. This works because R4 already guarantees every stored slug is lower-case, so
normalizing only the incoming value is sufficient for an exact match; the database does no
case-folding work. `?category=Fiction` and `?category=fiction` both normalize to
`fiction` and hit the same row.

**Length guard (R80).** After normalizing, `CategoryService` checks
`normalizedSlug.length() > 100` and treats an over-length value as "no category found"
without issuing a query, so an arbitrarily long `category` value costs nothing beyond a
string comparison and still produces the R33 404, never a server error.

### `GET /products` (existing endpoint, extended)

File: `com.sivalabs.bookstore.catalog.web.ProductWebController`.

- New optional request parameter: `category` (String, no default).
- Behavior:
  - `category` absent, empty, or all-whitespace → identical to today's behavior: full
    catalogue, same order, same page size, by calling the existing `getProducts(int
    pageNo)` unchanged (R32).
  - `category` present and non-blank → resolved as described above. No match →
    `CategoryNotFoundException` propagates to `CatalogExceptionHandler` (already scoped to
    `com.sivalabs.bookstore.catalog` by `@ControllerAdvice(basePackages = ...)`), which
    gets one new `@ExceptionHandler` method alongside the existing ones, rendering
    `error/404` with `errorMessage = "Category not found: " + slug` (the raw, un-normalized
    value the shopper sent) and HTTP 404 (R33, R35).
  - Match found → `productService.getProductsByCategory(page, category.id())` is called.
    The returned `PagedResult<ProductDto>`, the resolved category's display name, and its
    `totalElements` are added to the model (R26, R27).
- **`getProductsByCategory(int pageNo, Long categoryId)` reuses `getProducts(int pageNo)`'s
  bounds handling exactly (R40, R41).** Both methods use the identical clamping expression,
  `int page = pageNo <= 1 ? 0 : pageNo - 1;`, and build a `PageRequest`/`Page` the same way.
  Spring Data's paging already returns an empty `content` list with correct
  `totalPages`/`hasNext`/`hasPrevious` values when `pageNo` lands past the last page — that
  behavior is a property of `PageRequest` plus the query, not code specific to the
  unfiltered method, so the category-filtered method gets it for free by following the same
  pattern rather than by copying a special case. `getProductsByCategory` is new code, but
  its bounds behavior is not new logic to test independently; a reviewer confirms this by
  comparing the two method bodies line for line.
- **Where the join lives (addressing the `ProductDto` question).** `ProductDto` has no
  `id` field today and gains none. The category filter is a join between
  `catalog.products` and `catalog.product_categories`, expressed as a JPQL query on a new
  `ProductRepository` method operating on `ProductEntity` and a new `ProductCategoryEntity`
  (mapped to `catalog.product_categories`, composite key `(productId, categoryId)`, package-
  private, no other module sees it):

  ```java
  @Query("""
      select p from ProductEntity p
      where p.deletedAt is null
        and p.id in (select pc.id.productId from ProductCategoryEntity pc where pc.id.categoryId = :categoryId)
      order by p.name asc, p.code asc
      """)
  Page<ProductEntity> findAllByCategoryIdAndDeletedAtIsNull(Long categoryId, Pageable pageable);
  ```

  The join and the `deletedAt is null` filter (R30) run entirely inside the repository
  query against `ProductEntity`'s numeric `id`. `ProductMapper.mapToDto` maps the resulting
  `ProductEntity` rows to `ProductDto` exactly as it does today, unchanged; the id used for
  the join never reaches `ProductDto` or the template. `ProductEntity` itself is not
  changed — no `@ManyToMany` field is added to it — so the existing product-admin code
  paths that build and save a `ProductEntity` are untouched.
- **Product cards (R28).** The category page reuses `partials/products.html` and
  `products.html` unchanged for the product-grid markup; only a heading and an empty-state
  block are added around the existing `th:each` loop. Because the card markup (image, name,
  price, the `Add to Cart` form posting to `/buy`) is not duplicated or forked, a card on a
  category page is byte-for-byte the same fragment as a card on the full listing, so R28
  holds by construction rather than by a separate check.
- **Subset guarantee (R53, R54).** `findAllByCategoryIdAndDeletedAtIsNull` starts from the
  same `deletedAt is null` condition as `findAllByDeletedAtIsNull` and adds one more `AND`
  condition (category membership) on top. A product can only be excluded by that extra
  condition, never included by it, so the result of any category page is necessarily a
  subset of what paging through the full `/products` listing would eventually show (R53).
  When workspace scoping is eventually added to `catalog.products`, it is added as a further
  condition on this same query family, reaching category browsing with no change to the
  category code itself (R54). No query added by this item reaches outside the `catalog`
  schema (R55) — `ProductEntity`, `CategoryEntity`, and `ProductCategoryEntity` are the only
  entities involved.
- **Ordering.** `Sort.by("name").ascending().and(Sort.by("code").ascending())` (R42). This
  tiebreak is specific to the category-filtered query; `getProducts(int pageNo)` keeps its
  existing `Sort.by("name").ascending()` with no tiebreak, since the product spec does not
  ask for that method's behavior to change.
- **Page size.** `PRODUCT_PAGE_SIZE` (10), the same constant `getProducts(int pageNo)`
  already uses, is reused by `getProductsByCategory`, not redefined (R36).
- Rendering: unchanged branching on `HtmxRequest.isHtmxRequest()` — full page `products`,
  htmx partial `partials/products`. The pagination fragment (`partials/pagination.html`)
  gains the `category` parameter on every link it builds, so paging stays in the same
  category (R37, R43).
- **URL reproducibility (R38).** Category and page live only in the query string
  (`?category=<slug>&page=<n>`); nothing about the response depends on session or other
  server-side state. Opening the same URL later, in a different browser or an incognito
  window, issues the same GET request and reproduces the same result page.
- Permission check: none beyond what exists today. `GET /products` is already
  `permitAll()` in `WebSecurityConfig`; this item adds no new security rule and touches
  no file under `com.sivalabs.bookstore.config` (R44 to R49, R73).
- API version: none. This is a Thymeleaf-rendered page behind an existing public route,
  not a versioned REST resource, so no version bump applies (R34).

### Header category navigation (new, server-rendered fragment)

- Fragment template: `src/main/resources/templates/partials/category-nav.html`,
  `th:fragment="category-nav"`, taking a list of categories as its model.
- Data supply mechanism: a package-private `@ControllerAdvice` class in
  `com.sivalabs.bookstore.catalog.web` (`CategoryNavModelAdvice`) that adds a `categories`
  attribute to every model, backed by `CategoryService.getAllCategories()` (a thin wrapper
  over `CategoryRepository.findAllByOrderByNameAsc()`, R18). Using `@ControllerAdvice`
  rather than a new controller endpoint means `layout.html` renders the data with no change
  to any controller outside catalog, so a page served by the orders or cart controller
  renders the category header with that controller never referencing categories (R75).
  `layout.html` itself only gains a `th:replace="~{partials/category-nav :: category-nav}"`
  reference (R74) inside the existing `<nav class="sf-nav">` block, next to the existing
  Sign In / Cart / Orders links. Every template that decorates with `layout.html` —
  `products.html`, `cart.html`, `orders.html`, `order_details.html`, `login.html`,
  `registration.html`, `registration-success.html` — picks the fragment up automatically,
  which is how R16 is met without editing each of those templates individually.
- **Data freshness (R17).** The advice queries the database on every request; nothing is
  cached in the application. Renaming a category row directly in the database is visible
  on the next page load with no deploy and no restart.
- **Link shape and behavior (R19, R20).** Each entry renders as
  `<a th:href="@{/products(category=${cat.slug})}">`. Unlike the pagination fragment
  (`partials/pagination.html`), which uses `hx-get`/`hx-push-url` to swap `#products` in
  place, the header links carry **no** `hx-get`, `hx-target`, or `hx-boost` attribute. They
  are plain anchors that trigger a normal, full browser page load. This is deliberate, not
  an oversight: the header fragment renders on pages such as `cart.html` and `orders.html`
  that contain no `#products` element, so an `hx-get` targeting `#products` on those pages
  would find nothing to swap into. A full page load always works regardless of what the
  current page contains.
- **One query per page render (R23).** `CategoryService.getAllCategories()` is called
  exactly once per request, from the advice; nothing in the fragment or in any page template
  issues a second categories query.
- **Two distinct empty-list outcomes (R24 vs. R76/R77).** These are different states and
  are handled by different code paths, not collapsed into one:
  - **Normal empty state (R24).** `CategoryRepository.findAllByOrderByNameAsc()` returns
    successfully with zero rows (a database that genuinely holds no categories). This is
    not an error: the advice adds the empty list to the model as-is, logs nothing, and the
    fragment renders the header with no category area. A reviewer can confirm this by
    checking that the success path of the advice's try block contains no logging call.
  - **Failure state (R76, R77).** The repository call throws (for example, the database is
    unreachable). The advice catches the exception in that same try/catch, logs one line at
    `WARN` including the exception (enough detail to identify the cause, e.g. the exception
    message and type), and then supplies an empty list to the model so the page still
    renders with HTTP 200 and no category area. Nothing about the exception is shown to the
    shopper.
  Both branches end with the same empty-list model attribute and the same visual result
  (no category area), which is exactly why they need to be kept as two separate code
  branches: only the failure branch logs, and only the failure branch represents something
  an operator should investigate.
- Highlighting the active category (R21): the controller for `/products` adds the resolved
  `activeCategorySlug` to the model when a category match was found; the fragment compares
  it against each entry's slug to add a "current" CSS class.
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
- **Rollout with no manual step (R69).** After the migration runs and the application
  starts normally, `CategoryRepository.findAllByOrderByNameAsc()` already returns the five
  seeded rows and `product_categories` already holds the R10 links, so the header and every
  category page are populated on the very first request after deployment. Nothing in this
  item requires a separate backfill command.

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

- The category-nav advice logs one `WARN` line, including the exception, only when the
  category lookup for the header throws (R77) — see section 3's split between the normal
  empty case (R24, no log) and the failure case (R76, R77, one warning). No stack trace or
  database detail reaches the rendered page.
- A category page request that fails because the database is unreachable renders the
  application's standard error page (`error/500`, via the existing generic `Exception`
  handler in `CatalogExceptionHandler`) with a message that names no database objects
  (R78). No new logging is added here beyond what that existing handler already does, since
  it already logs unexpected exceptions before rendering `error/500`.
- No metrics, traces, or dashboards are added. The product spec does not call for any, and
  open questions 4 and 5 (caching, SEO treatment) are out of scope for this item.

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
  parameterized query through Spring Data (`findBySlug`, not string concatenation), and
  length is capped before any query executes (R80). Combined with the case-insensitive
  exact match against a fixed slug format (R4), no value of `category` — quotes, SQL
  fragments, percent-encoded bytes — can reach the database as anything other than a bind
  parameter, and any non-matching value falls through to the R33 404 rather than a partial
  match or an error (R79).
- **Read-your-writes race between the count and the page.** The category count (R27) and
  the page of products come from the same `Page` returned by one query, so there is no
  window between a separate count query and a separate page query where this could drift —
  this item avoids the race the unfiltered listing has (a product soft-deleted between two
  separate reads) by construction, not by locking.
- **Module boundary and modularity tests (R70 to R72).** Every new or changed Java class —
  `CategoryEntity`, `ProductCategoryEntity`, `CategoryRepository`, `ProductRepository`'s new
  method, `CategoryService`, `CategoryNotFoundException`, `CategoryNavModelAdvice`, and the
  `ProductWebController`/`ProductService` changes — lives under
  `com.sivalabs.bookstore.catalog`. No category type is added to the catalog module's
  published top-level package (`com.sivalabs.bookstore.catalog`, where `ProductDto` and
  `ProductApi` live) or to `ProductApi`, so no other module gains a dependency on a category
  type (R72), and `ArchitectureTests`/`ModularityTests` need no new allowed-dependency entry
  and are expected to pass unchanged (R71). The one file outside the catalog packages,
  `layout.html`, gains only the single fragment reference described in section 3 (R74),
  which keeps this diff a one-line change for a reviewer to confirm.

## Requirement traceability appendix

Requirements not obviously tied to a single sentence above, called out explicitly so a
reviewer does not have to re-derive where each was considered.

| Requirement | Where it's addressed |
| --- | --- |
| R16 | Section 3, header design: `layout.html` is the shared decorator for every listed template, so the fragment appears on all of them with no per-template change. |
| R17 | Section 3, "Data freshness": advice queries the database on every request, nothing cached. |
| R19 | Section 3, "Link shape and behavior": anchor `href` built as `/products?category=<slug>`. |
| R20 | Section 3, "Link shape and behavior": explicit statement that header links carry no `hx-get`/`hx-boost`, unlike the pagination fragment, because cart/orders pages have no `#products` target. |
| R24 | Section 3 and section 5: normal empty-category-table case, no exception, no log line, explicitly separated from the failure case. |
| R28 | Section 3, "Product cards": category page reuses the unmodified product-card fragment. |
| R30 | Section 3, repository query: `deletedAt is null` is part of the category-filtered query, same as the unfiltered one. |
| R31 | Section 2, `product_categories` note: a product can hold several link rows, one per category, each returned by that category's independent query. |
| R36 | Section 3: `PRODUCT_PAGE_SIZE` constant reused, not redefined. |
| R38 | Section 3, "URL reproducibility": category and page live only in the query string, no session state involved. |
| R40, R41 | Section 3: `getProductsByCategory` uses the identical clamping expression and `PageRequest`/`Page` mechanics as `getProducts(int pageNo)`. |
| R51 | Section 2, `product_categories` table: both foreign keys reference tables inside `catalog` only. |
| R53–R55 | Section 3, "Subset guarantee": category filter is an added `AND` condition on the same base query, so results can only narrow, tenancy scoping reaches this path automatically later, and no entity outside `catalog` is touched. |
| R62–R64 | Section 2, migration note items 1–3: table creation, seeding, and "no column of `catalog.products` is touched." |
| R69 | Section 4, "Rollout with no manual step." |
| R70–R72 | Section 6, "Module boundary and modularity tests" risk entry. |
