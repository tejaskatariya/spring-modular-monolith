# BOOK-2: Categories with browse-by-category

## 1. Problem

The bookstore has no grouping of any kind. A shopper who wants fantasy, or
classics, or thrillers has one route into the catalogue: the products page at
`/products`, which lists every product sorted by name, ten to a page, with
previous and next links. There is no way to ask for a subject area and see only
that.

How we know:

- `ProductWebController.showProducts` accepts a single `page` parameter. There
  is no other storefront entry point into the catalogue.
- `ProductService.getProducts` fetches every product that is not soft-deleted,
  sorted by name, ten per page. Nothing narrows that set.
- `ProductEntity` and the `catalog.products` table hold code, name,
  description, image URL, price, and `deleted_at`. No column groups a product
  with any other product.
- The site header in `layout.html` links to Sign In, Register, Cart, Orders,
  Admin, and Logout. It contains no link into any part of the catalogue.
- The seeded catalogue holds 15 books spanning fantasy, classics, young adult,
  and thrillers, so a shopper who wants one subject already has to scan past
  the others. Every product an admin adds makes that worse.

Two groups feel this. Shoppers who know the kind of book they want, rather than
the exact title, have to read the whole catalogue to find candidates. Admins
who add a product have no way to place it anywhere a shopper would look for it,
so a new book is only reachable by paging.

## 2. Goals and non-goals

### Goals

- The catalog schema holds categories, and a product can belong to more than
  one category.
- The site header shows category navigation on every storefront page, built
  from the categories in the database rather than from a fixed list in a
  template.
- A shopper can open a category and see a paged listing of only that category's
  products.
- Seed data ships with the change, so the header and the category pages are
  populated on a freshly deployed environment with no admin action. This item
  seeds five categories and links them to the 15 seeded products. Requirements
  R8 to R13 cover this.
- One seeded category holds more than one page of products, so paging is
  exercised by the seed data alone.
- All code changes stay inside the catalog module, and the existing Spring
  Modulith test keeps passing. Section 4.10 states the one file outside the
  catalog packages that changes and why.

### Non-goals

- Admin screens for creating, renaming, or deleting a category, and admin
  controls for assigning a product to a category. After this item, categories
  and product links come only from the seed migration. Open question 2 decides
  when management lands.
- Showing a product's categories on the product card, on the admin product
  page, or anywhere other than the header and the category listing page.
- Category hierarchy, meaning parent and child categories or nested subject
  areas. Categories are a flat list.
- Search, price filtering, and sort controls. That is BOOK-1, and the two items
  do not depend on each other. Section 5 covers the migration numbering
  interaction if both ship.
- A public REST or JSON API for categories. There is no product REST controller
  today and this item does not add one.
- Category pages for soft-deleted products, and any change to how soft delete
  works.
- Adding a `workspace_id` column to `catalog.products` or any other tenancy
  change to the catalog schema. Section 4.7 explains the reading taken.
- Changes to cart, checkout, orders, inventory, notifications, or users.

## 3. User stories

- A visitor who is not signed in can see a list of categories in the site
  header so that they can pick a subject area without knowing any book title.
- A visitor who is not signed in can open a category and see only that
  category's books so that they are not reading past subjects they do not care
  about.
- A signed-in shopper (`member`) can browse a category and page through it so
  that a large category stays readable.
- A shopper can copy the URL of a category page and open it later so that a
  subject area they want to come back to is shareable.
- A shopper who opens a category that has nothing visible in it can see that it
  is empty and get back to the full catalogue in one click so that they are not
  left on a blank page.
- A shopper who lands on a category link that no longer exists can see a clear
  not-found page so that a stale bookmark does not look like a broken site.
- An admin can browse categories in the storefront exactly as a shopper does so
  that they can check where a book appears, using the same pages a shopper
  sees.
- An admin can see that soft-deleted products stay out of every category page
  so that deleting a product removes it from the storefront everywhere, not
  just from the main listing.
- A release engineer can deploy the release to an environment that already
  contains products and get populated category navigation with no manual data
  step so that the rollout needs no database hand-holding.
- A shopper on any page of the site, including cart and orders, can still use
  the header category links so that the navigation works from wherever they
  are.

Roles in the business context are `admin`, `member`, and `guest`. In this
codebase the storefront product listing is public, so a `guest` here means an
unauthenticated visitor. Section 4.6 states what each role can do and commits
to that reading.

## 4. Requirements

### 4.1 Category data

- **R1.** The `catalog` schema holds categories. Each category has a display
  name and a URL slug.
- **R2.** Category names are unique and category slugs are unique. An attempt
  to store a second category with an existing name or an existing slug fails.
- **R3.** A slug is stored in lower case and contains only letters, digits, and
  hyphens. An attempt to store a slug outside that shape fails.
- **R4.** A product can belong to any number of categories, and a category can
  hold any number of products. The link between the two is a separate table in
  the `catalog` schema.
- **R5.** A link row cannot reference a product that does not exist or a
  category that does not exist. An attempt to insert one fails.
- **R6.** The same product and category cannot be linked twice. A repeated
  insert of an existing link either fails or leaves exactly one link row, and
  the product appears once on that category's page either way.
- **R7.** A product that belongs to no category still appears on the full
  products listing at `/products`, in the same position it occupies today.

### 4.2 Seed data

- **R8.** The migration in section 4.9 seeds these five categories:

  | Name | Slug |
  | --- | --- |
  | Classics | `classics` |
  | Fantasy | `fantasy` |
  | Fiction | `fiction` |
  | Mystery and Thriller | `mystery-and-thriller` |
  | Young Adult | `young-adult` |

- **R9.** The same migration links the 15 seeded products to categories as
  follows, matching products by their existing code:

  | Code | Title | Categories |
  | --- | --- | --- |
  | P100 | The Hunger Games | Fiction, Young Adult |
  | P101 | To Kill a Mockingbird | Fiction, Classics |
  | P102 | The Chronicles of Narnia | Fiction, Fantasy, Young Adult |
  | P103 | Gone with the Wind | Fiction, Classics |
  | P104 | The Fault in Our Stars | Fiction, Young Adult |
  | P105 | The Giving Tree | Fiction, Classics |
  | P106 | The Da Vinci Code | Fiction, Mystery and Thriller |
  | P107 | The Alchemist | Fiction, Classics |
  | P108 | Charlotte's Web | Fiction, Young Adult |
  | P109 | The Little Prince | Fiction, Classics |
  | P110 | A Thousand Splendid Suns | Fiction |
  | P111 | A Game of Thrones | Fiction, Fantasy |
  | P112 | The Book Thief | Fiction, Young Adult |
  | P113 | One Flew Over the Cuckoo's Nest | Fiction, Classics |
  | P114 | Fifty Shades of Grey | Fiction |

- **R10.** At least one seeded product belongs to three categories. P102 is
  that product, so the many-to-many link is exercised by the seed data.
- **R11.** The Fiction category holds all 15 seeded products, which is more
  than one page at the page size in R34. Paging on a category page is therefore
  testable against a freshly seeded database with no extra fixtures.
- **R12.** The seed links are matched by product code and category slug. If a
  product code in the R9 table is absent from the target database, that link is
  skipped and the migration still completes. An environment where an admin
  deleted a seeded product does not block the release.
- **R13.** Running the deployment twice against the same database creates no
  duplicate category and no duplicate link. An automated test asserts the
  category count and the link count are unchanged after a second application
  attempt.
- **R14.** The seed migration writes only to the new category and link tables.
  It does not change any column of any existing row in `catalog.products`.
- **R15.** An automated test asserts that after the migration, the Fantasy
  category page returns exactly The Chronicles of Narnia and A Game of Thrones,
  and that The Chronicles of Narnia appears on the Fiction, Fantasy, and Young
  Adult pages.

### 4.3 Header navigation

- **R16.** Every storefront page rendered with the shared layout shows category
  navigation in the site header. This includes the products page, cart, orders,
  login, and registration.
- **R17.** The entries in that navigation are read from the database when the
  page is rendered. Renaming a category directly in the database changes the
  header on the next page load, with no deployment and no restart.
- **R18.** Entries are ordered by category name ascending, so two page loads
  against unchanged data produce the same order. With the seed data the order
  is Classics, Fantasy, Fiction, Mystery and Thriller, Young Adult.
- **R19.** Each entry links to that category's listing page, using the URL
  shape in R24.
- **R20.** Header category links are ordinary links that load a full page. They
  are not htmx partial requests, because the header appears on pages such as
  cart and orders that do not contain the product grid the products page swaps
  into.
- **R21.** When the shopper is viewing a category page, that category's header
  entry is marked as the current one and is visually distinguishable from the
  others.
- **R22.** The header shows every category in the database, whatever number of
  visible products each one has. The reading chosen is that navigation
  reflecting the catalogue's structure is easier to reason about than
  navigation that appears and disappears as products are soft-deleted, and R38
  makes an empty category page a usable page rather than a dead end. Open
  question 3 revisits this if the category count grows.
- **R23.** Rendering one page issues at most one database query for the header
  categories, whatever else that page renders.
- **R24.** A page rendered against a database with no categories shows the
  header without a category area, and renders normally with no error.

### 4.4 Category listing page

The URL shape is a decision this section makes and commits to. The category
listing is served at `/products?category=<slug>`. Two things drive that. First,
`WebSecurityConfig` permits anonymous `GET /products` and requires
authentication for anything not explicitly listed, so a new path such as
`/categories/{slug}` would send unauthenticated shoppers to the login page
until that config is changed, and that file sits outside the catalog module
which the work item scopes this change to. Second, an optional parameter on an
existing public URL keeps every URL that works today working unchanged, so no
new API version is needed. Open question 1 covers adding a dedicated path
later.

- **R25.** `GET /products?category=<slug>` renders a paged listing of only the
  products linked to that category.
- **R26.** That page shows the category's display name as its heading.
- **R27.** That page shows the total number of products in the category that
  the shopper can see, counted under the same conditions as R30.
- **R28.** Product cards on the category page have the same content and the
  same Add to Cart behaviour as the cards on the full products listing.
- **R29.** Slug matching is case-insensitive, so `?category=fiction` and
  `?category=Fiction` reach the same page.
- **R30.** A product whose `deleted_at` is set never appears on a category page
  and is never included in the count in R27, for any role, including a
  signed-in admin. This matches the current storefront listing.
- **R31.** A product that belongs to more than one category appears on the page
  of each of those categories.
- **R32.** A request with no `category` parameter, an empty `category`, or a
  `category` of only whitespace renders the full catalogue exactly as
  `/products` does today, with the same order and the same page size.
- **R33.** A `category` value that matches no category renders the
  application's 404 page with the message `Category not found: <slug>` and an
  HTTP 404 status. The page does not render as an empty product grid, because a
  stale link and an empty category are different situations for the shopper.
- **R34.** Existing `/products` and `/products?page=N` URLs keep working
  unchanged. `category` is an optional addition, so nothing that works today
  breaks and no new API version is needed.

### 4.5 Paging

- **R35.** Category results are paged at 10 products per page, the size the
  products page uses today.
- **R36.** Pagination links carry the current category. Moving to page 2 of
  Fiction stays in Fiction.
- **R37.** The browser URL reflects the current category and page. Opening that
  URL directly reproduces the same result page.
- **R38.** A category with no visible products renders its heading, a count of
  0, the message `No products in this category yet`, and a link back to the
  full catalogue at `/products`.
- **R39.** A page number below 1 is treated as page 1, which is how the
  products page behaves today.
- **R40.** A page number above the last page renders an empty product grid with
  working pagination controls back to the earlier pages, and does not error.
- **R41.** Products on a category page are ordered by name ascending, matching
  the full listing, and ties are broken on the product code. Paging through a
  category never repeats a product and never skips one because two products
  share a name.
- **R42.** Category listing and its paging work for both a full page load and
  an htmx partial request, because the products page updates its grid through
  htmx today.

### 4.6 Permissions

The business context names `admin`, `member`, and `guest`. This codebase has
`ROLE_ADMIN` and `ROLE_USER` plus anonymous access to `GET /products`. The
reading chosen and committed to here is that category browsing is available to
unauthenticated visitors, because the products listing is public today and a
category page can only show a subset of what that listing already shows.
Putting a sign-in wall in front of a subset of public data would be a change to
the storefront's access model that this item was not asked to make. R43 to R48
are firm requirements on that basis, and no open question is left against them.

- **R43.** An unauthenticated visitor can see the header category navigation
  and open any category page.
- **R44.** A signed-in `member` sees exactly the same categories in the header
  and exactly the same products on a category page as an unauthenticated
  visitor. Nothing about the results depends on being signed in.
- **R45.** An `admin` browsing the storefront sees the same categories and the
  same products as everyone else. Soft-deleted products stay hidden from the
  storefront for an admin too, per R30.
- **R46.** No role can create, rename, or delete a category, or change which
  categories a product belongs to, through the application. In this item those
  changes are made only by a database migration. Open question 2 decides when
  admin management arrives.
- **R47.** The admin area under `/admin/**` keeps its current behaviour and
  gains no category controls. The admin product list, product page, and product
  form are unchanged.
- **R48.** This item makes no page that requires authentication today public,
  and makes no public page require authentication. The only access change is a
  new optional parameter on the already-public `GET /products`.

### 4.7 Tenancy

The business context requires every table to be scoped by `workspace_id` and
every query to filter on it. `catalog.products` has no `workspace_id` column
today, and the storefront listing does not scope by tenant. The reading chosen
here is the one that protects tenant isolation without inventing scope: the new
tables match the scoping of the table they hang off, and category browsing
cannot become a second way to read products that returns rows the existing
listing would withhold. Adding `workspace_id` to the new tables alone would
produce a column the application has no value to populate, and would let a
category be scoped to a workspace while the products inside it are not, which
is a weaker position than keeping both tables identical and changing them
together.

- **R49.** The category table and the link table live in the `catalog` schema
  alongside `catalog.products`, and carry no `workspace_id`, matching
  `catalog.products` as it stands.
- **R50.** Link rows reference only tables in the `catalog` schema, so when
  workspace scoping is added it can be applied to products, categories, and
  links in one change.
- **R51.** Category queries run through the same catalog repository and service
  layer that the current product listing uses. There is no separate query path
  to the products table.
- **R52.** The set of products on any category page is a subset of what the
  full storefront listing returns across all its pages. Category browsing can
  only narrow what a shopper can see.
- **R53.** Every scoping condition the storefront listing applies, today the
  `deleted_at is null` condition, applies to the category listing and to the
  count in R27. When tenant scoping is added to the catalog, it applies to
  category browsing through the same shared query path with no change to the
  category code.
- **R54.** No query added by this item reads a table outside the `catalog`
  schema.

### 4.8 Audit

The business context requires user-visible actions to append to the audit log.
Everything a user does in this item is a read: opening a category, paging
through it, and seeing the header. The reading chosen is that these append no
audit entries, because recording every category page view would add a large
volume of entries that say nothing about who changed what in the catalogue.
This repository has no audit log implementation yet, so the requirements below
say what must hold when one exists.

- **R55.** Rendering the header navigation, opening a category page, and paging
  within a category append no audit entry.
- **R56.** Seeding categories and product links is a migration step rather than
  a user action, so it appends no audit entry.
- **R57.** This item adds no user action that changes state, so it adds no new
  audited path. When admin category management is built under open question 2,
  creating, renaming, and deleting a category, and changing which categories a
  product belongs to, are each audited the way product edits are audited at
  that time, with no exemption for category changes.
- **R58.** No audit behaviour anywhere else in the application changes.

### 4.9 Migration

- **R59.** The change ships as a single new versioned migration in the catalog
  migration folder, following the existing `V<n>__catalog_*.sql` naming and
  taking the next version number not already used in that folder.
- **R60.** That migration creates the category table, creates the link table,
  seeds the categories from R8, and seeds the links from R9.
- **R61.** The migration completes without error against a database that
  already holds the 15 seeded products, and against a database whose products
  table is empty.
- **R62.** Existing product rows keep their current code, name, description,
  image URL, price, and `deleted_at` values. The migration writes no column of
  `catalog.products`.
- **R63.** The migration is forward-only and runs once. Running the deployment
  twice against the same database does not attempt it again.
- **R64.** If the migration fails, the application does not start against that
  database and the failure is visible in the startup logs. Whether the
  previously deployed version keeps serving traffic depends on the deployment
  mechanism in each environment rather than on anything this item builds, so
  that is an assumption about the surrounding setup and not a requirement on
  the catalog module.
- **R65.** The migration does not add, alter, or drop a column of
  `catalog.products`, so it does not rewrite that table and does not hold an
  `ACCESS EXCLUSIVE` lock on it. Creating the link table's foreign key to
  `catalog.products` takes a `SHARE ROW EXCLUSIVE` lock on that table for the
  duration of the migration, which blocks concurrent writes to products, such
  as an admin saving an edit, and does not block storefront reads. Blocked
  writes wait and then proceed.
- **R66.** The cost of the migration scales with the number of link rows it
  inserts, which is fixed at the R9 table, rather than with the number of
  products already in the database. An automated test seeds `catalog.products`
  with 100,000 rows, runs the migration against that table, and asserts it
  completes within 60 seconds. This test may be tagged as slow and must run in
  the pipeline that gates a merge to the main branch.
- **R67.** After the migration and a normal deployment, the header shows the
  five seeded categories and each category page returns its seeded products,
  with no separate backfill command and no manual data step.

### 4.10 Module boundary

- **R68.** Every Java class added or changed by this item lives under
  `com.sivalabs.bookstore.catalog`. No Java file in another module changes.
- **R69.** The existing `ModularityTests` module verification passes unchanged.
- **R70.** No module other than catalog depends on a category type, and the
  catalog module's public API surface changes only if another module needs
  categories, which none does in this item.
- **R71.** No file under `com.sivalabs.bookstore.config` changes, including
  `WebSecurityConfig`. The URL shape in section 4.4 is what makes this possible.
- **R72.** The one file changed outside the catalog packages is the shared
  layout template `layout.html`, which gains a reference to a header fragment.
  The fragment itself and the data behind it are owned by the catalog module. A
  reviewer can confirm the change to `layout.html` is limited to that
  reference.
- **R73.** Category data reaches the shared layout without a change to any
  controller outside the catalog module. A page served by the orders or cart
  code renders the category header without its controller knowing categories
  exist.

### 4.11 Errors and resilience

- **R74.** When the category query behind the header fails, for example because
  the database is unreachable, a page that does not itself depend on categories
  still renders with an HTTP 200 and shows the header without the category
  area. Cart, orders, and login do not turn into error pages because the
  category lookup failed.
- **R75.** A header category failure is logged at warning level with enough
  detail to identify the cause, and nothing about it is shown to the shopper.
- **R76.** When a category page cannot complete because the database is
  unreachable, the shopper sees the application's standard error page rather
  than a stack trace, and the message names no database objects.
- **R77.** No `category` value produces a server error. Punctuation, quotes,
  SQL fragments, percent-encoded bytes, and values longer than any stored slug
  all produce either a category page or the 404 from R33.
- **R78.** A `category` value longer than 100 characters is treated as no match
  and produces the R33 404 page.

## 5. Edge cases and failure modes

**Unknown or stale category slug.** A bookmark or an external link pointing at
a category that was renamed or removed gets the 404 page from R33 with the slug
in the message, rather than a blank grid that looks like an empty catalogue.

**Empty and whitespace category parameter.** Covered by R32. A link that ends
up as `?category=` behaves like plain `/products`, so a malformed link does not
blank the catalogue.

**Category whose products are all soft-deleted.** The category stays in the
header under R22 and its page renders the empty state from R38 with a way back
to the full catalogue. A shopper who clicks it is not stranded.

**Product in several categories.** P102 is in three categories under R9. It
appears on all three pages under R31 and is counted once in each category's
total under R27. It appears once on each page, not three times, because R6
allows only one link row per product and category.

**Product soft-deleted between the count and the page query.** The count in R27
and the page of products are read in the same request. If a product is
soft-deleted in between, the count can be one higher than the number of cards
shown for that moment. The page renders normally and corrects itself on the
next load. This matches how the existing products listing behaves and is not
worth a locking scheme.

**Product soft-deleted or restored while a shopper pages.** The result set
shifts under the shopper, so a product can appear on two consecutive pages or
be skipped. R41's tie-break on product code removes the version of this caused
by equal sort keys. The version caused by rows genuinely appearing or
disappearing remains, and is the behaviour the products listing has today.

**Soft delete and restore of a linked product.** Soft-deleting a product leaves
its link rows in place, so restoring it puts it back in the same categories
with no re-linking step. R30 keeps it out of category pages while it is
deleted.

**Migration numbering collision with BOOK-1.** BOOK-1 also adds a migration to
the catalog folder. Whichever item merges second takes the next free version
number under R59. If both are prepared against the same version number, the
second one to merge is renumbered before it lands, and a Flyway checksum error
on startup is the signal that this was missed.

**Category count outgrowing the header.** Five categories fit a header
comfortably. R22 shows all of them, so a database with dozens of categories
would produce a crowded header. Nothing in this item can create that state,
because categories come only from the seed migration, and open question 3
decides the rule before management screens make it reachable.

**Database unavailable while rendering the header.** R74 and R75 keep the rest
of the site usable and keep the failure out of the shopper's view. The category
area is missing until the database recovers, with no deploy needed.

**Long or hostile slug input.** R77 and R78 keep any `category` value on the
path to either a category page or a 404. Nothing in this item concatenates the
slug into SQL.

**Second deployment of the same release.** R13 and R63 mean a repeated
deployment leaves the category and link data exactly as it was, so a redeploy
during an incident does not duplicate navigation entries.

## 6. Open questions

1. Decide whether category browsing should later get a dedicated URL such as
   `/categories/{slug}` instead of the `?category=` parameter this item ships.
   That change needs one entry added to the public path list in
   `WebSecurityConfig`, which is outside the catalog module, so it belongs to a
   separate item with its own scope. Someone needs to weigh cleaner URLs
   against the module boundary this item was given.

2. Decide which item builds admin management of categories, meaning create,
   rename, delete, and assigning products to categories, and confirm that it
   carries the audit requirements in R57. Until then categories change only
   through a migration, which means a product added by an admin belongs to no
   category and is reachable only from the full listing.

3. Decide the rule for how many categories the header shows once the number
   grows past what fits, for example showing the first N by name with an
   overflow menu, or showing only categories that have at least one visible
   product. R22 shows all of them today, which is right for five and wrong for
   fifty. This decision is needed before the management screens in open
   question 2 ship.

4. Decide whether the header category query should be cached and, if so, how
   stale it may be. R23 keeps it to one query per page render, which is
   acceptable for five rows on a page that already queries products. A measured
   cost at higher traffic would change that.

5. Decide whether category pages need search engine treatment, meaning
   canonical URLs, a sitemap entry, or crawlable links, given that the category
   is a query parameter under section 4.4. This is a marketing decision rather
   than an engineering one, and it may change the answer to open question 1.

6. Decide the plan for adding workspace scoping to the catalog schema as a
   single change covering products, categories, and the link table, and who
   owns it. Section 4.7 explains why this item follows what
   `catalog.products` does today rather than scoping the new tables on their
   own.

7. Decide whether a product's categories should be visible on the product card,
   on the admin product page, or on a product detail page. This item shows
   categories only in the header and as the heading of a category page, so an
   admin cannot see a product's categories anywhere in the application.
