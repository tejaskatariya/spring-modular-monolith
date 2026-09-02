# BOOK-2: Categories with browse-by-category — Technical Specification

Source: `artifacts/BOOK-2/spec.md` (product spec, requirements R1 to R78, open questions 1 to 7).

## 1. Approach

The one decision that shapes everything else is the URL shape: category browsing is
served at `GET /products?category=<slug>`, an optional parameter on the existing public
endpoint, rather than a new path such as `/categories/{slug}`. The product spec commits to
this in section 4.4 because `WebSecurityConfig` (outside the catalog module) would need a
new `permitAll()` entry for any new path, and R71 forbids touching that file. Reusing the
existing endpoint means `ProductWebController`, `ProductService`, and the existing
`products.html` / `partials/products.html` templates are extended, not replaced, and no
security configuration changes.

Two new tables carry the category data: `catalog.categories` and the many-to-many link
table `catalog.product_categories`. Both live in the `catalog` schema, both are seeded and
linked by a single new Flyway migration, and neither gets a `workspace_id` column, matching
`catalog.products` as it stands today (R49, R50). All reads go through the existing
`ProductRepository` / `ProductService` layer with new methods added alongside the existing
ones, so category browsing cannot become a second path to rows the main listing would
withhold (R51, R52).

The header category list is the one piece that has to reach templates the catalog module
does not control (cart, orders, login). It is populated by a global Spring
`@ControllerAdvice` with a `@ModelAttribute` method, declared in
`com.sivalabs.bookstore.catalog.web` with no `basePackages` restriction, so it runs for
every controller in the application without any other module's controller importing or
knowing about it. `layout.html` gets one new line referencing a category navigation
fragment; that is the only file outside the catalog packages this item changes, matching
R72.

## 2. Data model

### `catalog.categories` (new)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `bigint` | Primary key, sequence `category_id_seq` (same start/increment convention as `product_id_seq`). |
| `name` | `text not null unique` | Display name. Unique constraint enforces R2. |
| `slug` | `text not null unique` | Unique constraint enforces R2. A `check` constraint `slug ~ '^[a-z0-9-]+$'` enforces R3 at the database level, so a bad slug fails the insert regardless of which code path writes it. |

No `workspace_id` column (R49). No `deleted_at`: categories are not soft-deletable through
the application in this item (R46), so there is nothing to soft-delete.

### `catalog.product_categories` (new, link table)

| Column | Type | Notes |
| --- | --- | --- |
| `product_id` | `bigint not null references catalog.products(id)` | Enforces R5: a link cannot reference a missing product. |
| `category_id` | `bigint not null references catalog.categories(id)` | Enforces R5: a link cannot reference a missing category. |
| | `primary key (product_id, category_id)` | The composite primary key enforces R6: a repeated insert of the same pair fails or is absorbed by `on conflict do nothing`, and exactly one row exists per pair either way. |

No `workspace_id` column (R49, R50). No surrogate `id`: the table only needs to answer
"which categories for this product" and "which products for this category," and the
composite key is the natural one.

### Migration

New file `src/main/resources/db/migration/catalog/V5__catalog_add_categories.sql`, the next
version number after the existing `V4__catalog_add_deleted_at_to_products.sql` (R59).

The migration:

1. Creates `category_id_seq`, `catalog.categories`, and `catalog.product_categories` with
   the constraints above.
2. Seeds the five categories from R8 with `insert ... on conflict (slug) do nothing`.
3. Seeds the product-to-category links from R9 as a single statement, joining a literal
   `values` list of `(product_code, category_slug)` pairs against `catalog.products` and
   `catalog.categories` by code and slug, with `on conflict (product_id, category_id) do
   nothing`:

   ```sql
   insert into catalog.product_categories (product_id, category_id)
   select p.id, c.id
   from (values
       ('P100', 'fiction'), ('P100', 'young-adult'),
       ('P101', 'fiction'), ('P101', 'classics'),
       ('P102', 'fiction'), ('P102', 'fantasy'), ('P102', 'young-adult'),
       -- ... remaining pairs from the R9 table ...
       ('P114', 'fiction')
   ) as seed(product_code, category_slug)
   join catalog.products p on p.code = seed.product_code
   join catalog.categories c on c.slug = seed.category_slug
   on conflict (product_id, category_id) do nothing;
   ```

   A product code absent from the target database simply fails the `join` and is skipped
   (R12), and re-running the statement inserts nothing new (R13, R63).

The migration writes no column of `catalog.products` (R14, R62, R65) and touches only the
two new tables. It does not alter `ProductEntity`, `ProductRepository`, or any existing
migration file.

**Trace for R7.** `ProductService.getProducts` and its backing query,
`ProductRepository.findAllByDeletedAtIsNull`, are unchanged by this design (they are not
listed anywhere in section 3's new or modified methods). A product with no row in
`catalog.product_categories` is invisible to the new category query path entirely, but it is
still selected by `findAllByDeletedAtIsNull` exactly as before, so it keeps appearing on
`/products` in its existing name-sorted position with no code change required to make that
true.

## 3. API

There is no versioned REST API in this application for catalog data (the storefront is
server-rendered Thymeleaf, and there is no product REST controller today), so this section
covers the one extended MVC endpoint. No new API version is introduced; R34 requires that
existing `/products` and `/products?page=N` URLs keep working unchanged, which an optional
parameter satisfies.

### `GET /products?category=<slug>&page=<n>` (extends the existing endpoint)

Handled by `ProductWebController.showProducts`, extended with a new `@RequestParam(required
= false) String category` argument.

Request handling, in order:

1. Trim `category`. If it is `null`, empty, or blank after trimming, behave exactly as
   `/products` does today: call `productService.getProducts(page)` with no category filter
   (R32).
2. If the trimmed value is longer than 100 characters, treat it as no match and go straight
   to step 4 (R78), avoiding a database round trip for clearly invalid input.
3. Otherwise, look up the category by slug, case-insensitively, via a new
   `CategoryService.findBySlug(String slug)` method (R29).
4. If no category matched, throw a new `CategoryNotFoundException` with the message
   `Category not found: <slug>` (using the trimmed value), caught by
   `CatalogExceptionHandler` and rendered as the existing `error/404` view with HTTP 404
   (R33), the same mechanism already used for `ProductNotFoundException`.
5. If a category matched, call a new `ProductService.getProductsByCategory(Long categoryId,
   int pageNo)` method, add the resulting `PagedResult<ProductDto>` to the model under the
   existing `productsPage` key, and add the matched `CategoryDto` to the model under a new
   key, **`category`**. That is the one attribute name for "the matched category," used
   identically in three places: `ProductWebController` sets `model.addAttribute("category",
   matchedCategory)`; `partials/products.html` reads `${category}` for the heading, count,
   and empty-state blocks in the template changes below; and `partials/category-nav.html`
   reads the same `${category}` attribute to compare against each header entry's slug for
   the current-category highlight (R21). When no category is selected (the R32 path in step
   1), the `category` attribute is not added to the model, so it is `null` in every template
   that reads it, and the highlight and heading/count/empty-state blocks all correctly no-op.
6. `getProductsByCategory` paging reuses the same clamping as `getProducts`:
   `int page = pageNo <= 1 ? 0 : pageNo - 1` (see section 2's `ProductService` note below),
   satisfying R39. For a `pageNo` past the last page, Spring Data's `Page` abstraction
   returns an empty `content` list with a valid `totalPages` and `totalElements`, no
   exception, so `partials/pagination.html` renders working links back to the earlier pages
   and the grid renders empty with no error, satisfying R40 with no extra guard in the
   catalog code.
7. Return `partials/products` for an htmx request or `products` otherwise, exactly as
   today (R42).

New repository method on the existing `ProductRepository`, a native query joining the link
table by category id (parameterized, no string concatenation, so no `category` value can
reach SQL as anything but a bind parameter, satisfying R77):

```java
@Query(value = """
    select p.* from catalog.products p
    join catalog.product_categories pc on pc.product_id = p.id
    where pc.category_id = :categoryId and p.deleted_at is null
    order by p.name asc, p.code asc
    """,
    countQuery = """
    select count(p.id) from catalog.products p
    join catalog.product_categories pc on pc.product_id = p.id
    where pc.category_id = :categoryId and p.deleted_at is null
    """,
    nativeQuery = true)
Page<ProductEntity> findByCategoryIdAndDeletedAtIsNull(Long categoryId, Pageable pageable);
```

The count for R27 comes from the same `Page` object's `getTotalElements()`, so the count and
the page of products are read together, matching the accepted race described in the product
spec's edge cases.

`ProductService` gains one new method wrapping that repository call, reusing the exact page
clamping already used by `getProducts` (see `ProductService.java` lines 26 to 32 quoted
above):

```java
@Transactional(readOnly = true)
public PagedResult<ProductDto> getProductsByCategory(Long categoryId, int pageNo) {
    Sort sort = Sort.by("name").ascending().and(Sort.by("code").ascending());
    int page = pageNo <= 1 ? 0 : pageNo - 1;
    Pageable pageable = PageRequest.of(page, PRODUCT_PAGE_SIZE, sort);
    Page<ProductDto> productsPage =
            repo.findByCategoryIdAndDeletedAtIsNull(categoryId, pageable).map(productMapper::mapToDto);
    return new PagedResult<>(productsPage);
}
```

This is the same `pageNo <= 1 ? 0 : pageNo - 1` expression `getProducts` already uses, so a
`page` of 0 or negative clamps to the first page (R39) with no new logic to test separately.
For `pageNo` past the last page, nothing above needs to guard against it: Spring Data's
`Page<T>` is well-defined for an out-of-range `PageRequest`, it returns an empty `content`
with `totalElements` and `totalPages` still populated from the count query, so
`partials/pagination.html` can still render links back to valid pages and
`partials/products.html` can still render an (empty) grid, satisfying R40 without a bounds
check in `ProductService` or `ProductWebController`.

**`CategoryService` and `CategoryRepository`.** Two new classes in
`com.sivalabs.bookstore.catalog.domain`, mirroring the shape of `ProductRepository` /
`ProductService`:

```java
interface CategoryRepository extends JpaRepository<CategoryEntity, Long> {
    Optional<CategoryEntity> findBySlugIgnoreCase(String slug);
    List<CategoryEntity> findAllByOrderByNameAsc();
}
```

- **R29 (case-insensitive slug match):** `findBySlugIgnoreCase` derives a
  `lower(slug) = lower(:slug)` comparison from the Spring Data `IgnoreCase` keyword. The
  stored `slug` column is already lower-case by construction (R3's check constraint requires
  it), but the query does not rely on that: it lower-cases both sides, so `?category=Fiction`
  and `?category=FICTION` match the stored `fiction` row the same way `?category=fiction`
  does, independent of whether every future writer of that column remembers to lower-case
  first.
- **R18 (header order):** `findAllByOrderByNameAsc` derives `order by name asc` directly from
  the method name, no `@Query` needed. Two calls against unchanged data return the same
  order because the ordering is expressed in SQL, not applied after the fact in Java.

```java
@Service
public class CategoryService {
    private final CategoryRepository repo;
    private final CategoryMapper categoryMapper;

    @Transactional(readOnly = true)
    public Optional<CategoryDto> findBySlug(String slug) {
        return repo.findBySlugIgnoreCase(slug).map(categoryMapper::mapToDto);
    }

    @Transactional(readOnly = true)
    public List<CategoryDto> getForHeader() {
        return repo.findAllByOrderByNameAsc().stream().map(categoryMapper::mapToDto).toList();
    }
}
```

`ProductWebController` calls `findBySlug` and, if empty, throws `CategoryNotFoundException`
per step 4 above. The `@ControllerAdvice` described in section 1 calls `getForHeader()` for
the model attribute that backs the header fragment; see section 5 for its failure handling.

**Permission checks.** None. `WebSecurityConfig` already permits anonymous `GET /products`;
the `category` parameter needs no new rule, so R43 to R48 and R71 hold with no config
change. An unauthenticated visitor, a `member`, and an `admin` all reach the same code path
and see the same result (R44, R45).

**Template changes** (all in the catalog module's existing storefront templates, which only
`ProductWebController` renders):

- `partials/products.html` gains a conditional heading and product count block, guarded by
  `th:if="${category != null}"` reading the same `category` model attribute
  `ProductWebController` sets (R26, R27), and a conditional empty-state block with the
  message `No products in this category yet` and a link to `/products` (R38), shown when
  `category != null` and `productsPage.data.isEmpty()`.
- `partials/pagination.html` gains a `category` query parameter on each generated link
  (`th:hx-get`, `th:hx-push-url`, and the plain `href` fallback), carried from the current
  category slug on the model, so paging within a category stays in that category (R36) and
  the browser URL reflects both category and page (R37).

**New template** `partials/category-nav.html` (fragment name `nav`), read by `layout.html`:

```html
<div th:if="${headerCategories != null and !headerCategories.isEmpty()}">
  <ul class="navbar-nav">
    <li th:each="cat : ${headerCategories}"
        th:classappend="${category != null and category.slug == cat.slug} ? 'active' : ''">
      <a th:href="@{/products(category=${cat.slug})}" th:text="${cat.name}"></a>
    </li>
  </ul>
</div>
```

The fragment reads `${category}`, the same model attribute `ProductWebController` sets in
step 5 above, not a separately named "current category" attribute. That is what makes the
highlight in R21 activate: the `@ControllerAdvice`-supplied `headerCategories` list and the
per-request `category` attribute are evaluated together in one fragment, and `category` is
only ever non-null on a rendered category page, so the highlight is on exactly when the
shopper is viewing that category and off everywhere else, including the plain `/products`
page where `category` is never added to the model.

`layout.html` changes by exactly one line, inside the existing `<ul class="navbar-nav ...">`:

```html
<div th:replace="~{partials/category-nav :: nav}"></div>
```

This satisfies R72: the fragment and the data behind it belong to the catalog module, and
`layout.html` only references it.

## 4. Background work

This item introduces no async job, no queue consumer, and no scheduled task. Every request
described in section 3 is a synchronous read within the existing request/response cycle.

The one process that runs outside a normal request is the Flyway migration `V5` itself, and
it runs synchronously during application startup, driven by Spring Boot's Flyway
autoconfiguration (the project already has `spring.modulith.runtime.flyway-enabled=true`).
It is not retried: Flyway does not re-attempt a failed migration automatically. If it fails,
the schema history table is left without that version recorded, the Spring application
context fails to start, and the failure appears as an exception and stack trace in the
startup logs, naming the failing script and its checksum (R64). Whether the previous
version of the application keeps serving traffic during that failure depends on the
deployment mechanism (rolling deploy, blue-green, and so on) in each environment, which is
outside anything this item builds.

**Test plan.** The product spec requires three specific automated tests: R66 (migration cost
at scale), R13 (rerunning the migration is a no-op), and R15 (the Fantasy/Narnia assertions).
All three live in a new test class,
`src/test/java/com/sivalabs/bookstore/catalog/CategoryMigrationTests.java`, using the
existing `TestcontainersConfiguration` Postgres
container so the real `V5` script runs against a real Postgres instance rather than a mock.

1. **`seedLinksMatchProductCodesAndSurviveRerun()` (R13, R15 combined fixture).** Start from
   the container already carrying the `V1` to `V5` migrations (the default Spring context for
   this test class), which means the 15 seeded products and the R8/R9 category and link data
   already exist. This one test asserts both R13 and R15 against that shared state:
   - **R15 assertion:** query `catalog.product_categories` joined to `catalog.categories` and
     `catalog.products` for the `fantasy` slug and assert the result is exactly
     `{"The Chronicles of Narnia", "A Game of Thrones"}`, no more and no fewer. Separately,
     query all category slugs linked to product code `P102` and assert the result is exactly
     `{"fiction", "fantasy", "young-adult"}`, confirming Narnia appears on all three pages.
   - **R13 assertion:** record `count(*)` from `catalog.categories` and from
     `catalog.product_categories` before the rerun. Re-invoke `Flyway.migrate()` directly
     against the same datasource (Flyway itself is idempotent for an already-applied version,
     since it checks the schema history table before re-running a script, but this test
     exercises the migration's own `on conflict do nothing` clauses in case a future edit to
     `V5` ever needs a manual re-apply path). Assert both counts are unchanged after the
     second call.
2. **`migrationCompletesInBoundedTimeAgainstLargeProductsTable()` (R66).** A separate test
   method, since it needs its own Postgres container pre-populated before any migration runs:
   start a fresh container with only `V1` to `V4` applied (no seed data reliance), batch-insert
   100,000 synthetic `catalog.products` rows via `JdbcTemplate`, then invoke `V5` and assert
   elapsed wall-clock time is under 60 seconds. Tag this method `@Tag("slow")` so it can be
   excluded from the fast local loop while still running in the class that CI executes.

**Closing the CI gate gap for R66.** `.github/workflows/maven.yml`, as it exists in this
repository today, triggers only on `push` to `main` and `package-by-*` branches; it has no
`pull_request` trigger. That means there is currently no CI run that blocks a bad merge
before it lands, for this test or for any other. R66 requires the slow test to "run in the
pipeline that gates a merge to the main branch," which does not exist yet, so this item adds
one: a `pull_request` trigger block targeting `main` in `maven.yml`, running the same
`./mvnw -ntp verify` step (which runs the full test suite including `@Tag("slow")` tests
unless a Surefire/Failsafe exclusion says otherwise; the module has no such exclusion today,
so no further Maven configuration change is needed). Adding a `pull_request` trigger is a
change to a GitHub Actions workflow file, not a Java class, so it does not touch
`com.sivalabs.bookstore.catalog` and is not a Modulith boundary violation, but it is a change
outside the catalog Java packages and a reviewer should treat it as a deliberate,
called-out part of this item's diff rather than stumble on it unexplained.

## 5. Audit and observability

**Audit.** Per R55 to R58, this item appends no audit entries. Every action it adds
(rendering the header, opening a category page, paging within a category) is a read, and
the product spec explains that logging every category page view would add volume without
recording who changed what. Seeding categories and links is a migration step, not a user
action, so it is not audited either (R56). This repository has no audit log implementation
yet; when one exists, R57 requires that admin category management (open question 2) be
audited the same way product edits are, with no exemption, but that is out of scope here.

**Logging.**

- `ProductWebController` logs the resolved category (or its absence) at info level for each
  request, following the existing `log.info("Fetching products for page: {}", page)`
  pattern.
- `CatalogExceptionHandler` logs a warning when `CategoryNotFoundException` is caught,
  following the existing pattern for `ProductNotFoundException`, including the requested
  slug.
- The new `@ModelAttribute` method backing the header navigation wraps its call to
  `CategoryService.getForHeader()` in a try/catch. On failure it logs at warning level with
  the exception (enough detail to identify the cause, per R75) and returns an empty list, so
  the page it decorates still renders with HTTP 200 and no category area (R74). Nothing
  about the failure reaches the shopper.
- A category page that fails because the database is unreachable (not just the header
  query) propagates to the application's standard error page, which does not name any
  database object (R76); no new exception-to-message mapping is needed beyond what already
  exists for that class of failure elsewhere in the app.

## 6. Risks

**Lock contention during migration.** Creating the foreign key from
`catalog.product_categories` to `catalog.products` takes a `SHARE ROW EXCLUSIVE` lock on
`catalog.products` for the duration of the migration (R65). That blocks concurrent writes,
such as an admin saving a product edit, until the migration finishes; storefront reads are
not blocked. The migration's own work (creating two small tables and inserting a fixed
number of seed rows) is quick regardless of how many products already exist, so the lock
window stays short even against a large table, which is what the R66 100,000-row test is
meant to confirm. If a deployment ever needs to run this migration against an unusually
large or heavily-written products table, running it in a low-traffic window is a reasonable
precaution, though nothing in the code requires it.

**Migration version collision with BOOK-1.** BOOK-1 also adds a migration to the same
catalog folder. This spec claims `V5`. If BOOK-1 merges a migration also numbered `V5`
before this item merges, whichever merges second must be renumbered before landing; a
Flyway checksum error at startup is the signal that this was missed, as the product spec's
edge cases section notes.

**Header query on every page.** The global `@ControllerAdvice` means every page in the
application, not only catalog pages, now issues one extra query per render (R23 keeps it to
one). If the database is slow rather than fully unreachable, that adds latency to pages like
cart, orders, and login that previously had no dependency on the catalog schema. The
try/catch in section 5 bounds the failure case to an empty header, but it does not bound
added latency from a slow-but-responding database. Open question 4 in the product spec
raises caching this if it becomes measurable; nothing in this item adds a cache.

**Hostile or oversized `category` values.** The native query in section 3 binds `category`
only as a parameter to `CategoryService.findBySlug`, never concatenated into SQL, and the
100-character cutoff in R78 rejects oversized input before any query runs. Between those
two, no `category` value reaches the database in a form that could change the query's
structure, satisfying R77.

**Race between count and page contents.** Because the count (R27) and the page of products
come from the same `Page` object read in one request, if a product is soft-deleted between
that read and when the shopper looks at the rendered page, the displayed count can be
briefly one higher than the number of cards shown. The product spec accepts this as matching
existing behavior on the main listing and not worth a locking scheme; this design does not
change that.

**Header growing past what fits.** R22 shows every category in the header regardless of
count, which is fine at five categories and would be crowded at a much larger number.
Nothing in this item can create that state, since categories are only added by the migration
in section 2, but open question 3 in the product spec flags that a rule is needed before any
future admin management screens make the category count grow.
