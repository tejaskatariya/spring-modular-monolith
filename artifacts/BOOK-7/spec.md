# BOOK-7: Categories with browse-by-category

## 1. Problem

The catalogue has no grouping. A shopper who wants fantasy, or classics, or
thrillers has exactly one way into the catalogue, and it shows everything.

How we know, from the code as it stands today:

- `ProductWebController.showProducts` accepts a single `page` parameter and
  serves `GET /products`. There is no other storefront entry point into the
  catalogue, and `GET /` redirects to `/products`.
- `ProductService.getProducts` fetches every product whose `deleted_at` is
  null, sorted by name ascending, ten per page. Nothing narrows that set.
- `catalog.products` holds `code`, `name`, `description`, `image_url`, `price`,
  and `deleted_at`. No column relates one product to another.
- The site header in `layout.html` links to Sign In, Register, Cart, Orders,
  Admin, and Logout. It has no link into any part of the catalogue.
- The seed migration `V3__catalog_add_books_data.sql` loads 15 books that span
  fantasy, classics, young adult, and thrillers. A shopper looking for one
  subject already has to read past the others, across two pages.

Two groups feel this. Shoppers who know the kind of book they want, but not the
title, have to scan the whole catalogue to find candidates. Admins who add a
product through the admin screens have nowhere to place it that a shopper would
look, so a new book is reachable only by paging through everything.

## 2. Goals and non-goals

### Goals

- The `catalog` schema holds categories, and a product can belong to more than
  one category.
- The site header shows category navigation on every storefront page, built
  from the database at render time rather than from a fixed list in a template.
- A shopper can open a category and see a paged listing of only that category's
  products.
- Seed data ships with the change, so a freshly deployed environment has
  populated navigation and populated category pages with no admin action. This
  item seeds five categories, which satisfies the work item's "at least three".
  Requirements R8 to R15 cover the seed data.
- At least one seeded category holds more than one page of products, so paging
  on a category page is exercised by the seed data alone.
- All Java changes stay inside the catalog module and the existing
  `ModularityTests` keeps passing. Section 4.10 names the one file outside the
  catalog packages that changes, and why.

### Non-goals

- Admin screens for creating, renaming, or deleting a category, and admin
  controls for assigning a product to a category. After this item, categories
  and product links come only from the seed migration. Open question 2 decides
  when management lands.
- Showing a product's categories on the product card, on the admin product
  page, or anywhere other than the header and the category listing heading.
- Category hierarchy, meaning parent and child categories. Categories are a
  flat list.
- Search, price filtering, and sort controls.
- A REST or JSON API for categories. The catalogue has no product REST
  controller today and this item does not add one.
- Any change to how soft delete works, or to the admin product screens.
- Adding `workspace_id` to `catalog.products` or otherwise changing tenancy in
  the catalog schema. Section 4.7 states the reading taken and open question 6
  carries the follow-up.
- Changes to cart, checkout, orders, inventory, notifications, or users.

## 3. User stories

The business context names three roles: `admin`, `member`, and `guest`. This
codebase has `ROLE_ADMIN` and `ROLE_USER`, and `WebSecurityConfig` permits
anonymous `GET /products`. A `guest` here is an unauthenticated visitor.
Section 4.6 commits to what each role can do.

- A guest can see a list of categories in the site header so that they can pick
  a subject area without knowing any book title.
- A guest can open a category and see only that category's books so that they
  are not reading past subjects they do not want.
- A member can page through a category so that a large category stays readable.
- A member can copy the URL of a category page and open it later so that a
  subject area they want to return to is shareable.
- A guest who opens a category with nothing visible in it can see that it is
  empty and return to the full catalogue in one click so that they are not
  stranded on a blank page.
- A guest who follows a stale category link can see a clear not-found page so
  that an old bookmark does not look like a broken site.
- An admin can browse categories in the storefront exactly as a shopper does so
  that they can check where a book appears, using the same pages a shopper
  sees.
- An admin can confirm that a soft-deleted product disappears from every
  category page so that deleting a product removes it from the storefront
  everywhere, not just from the main listing.
- A release engineer can deploy this release to an environment that already
  holds products and get populated category navigation with no manual data
  step so that the rollout needs no database hand-holding.
- A member on any page of the site, including cart and orders, can still use
  the header category links so that navigation works from wherever they are.

## 4. Requirements

### 4.1 Category data

- **R1.** The `catalog` schema holds categories. Each category has a display
  name and a URL slug.
- **R2.** Category names are unique. Storing a second category with an existing
  name fails.
- **R3.** Category slugs are unique. Storing a second category with an existing
  slug fails.
- **R4.** A slug is stored in lower case and contains only letters, digits, and
  hyphens. Storing a slug outside that shape fails.
- **R5.** A product can belong to any number of categories, and a category can
  hold any number of products. The link between them is a separate table in the
  `catalog` schema.
- **R6.** A link row cannot reference a product that does not exist or a
  category that does not exist. Inserting one fails.
- **R7.** The same product and category cannot be linked twice. A repeated
  insert either fails or leaves exactly one link row, and the product appears
  once on that category's page either way.
- **R8.** A product that belongs to no category still appears on `/products`,
  in the same position it occupies today.

### 4.2 Seed data

- **R9.** The migration in section 4.9 seeds these five categories:

  | Name | Slug |
  | --- | --- |
  | Classics | `classics` |
  | Fantasy | `fantasy` |
  | Fiction | `fiction` |
  | Mystery and Thriller | `mystery-and-thriller` |
  | Young Adult | `young-adult` |

- **R10.** The same migration links the 15 products seeded by
  `V3__catalog_add_books_data.sql` to categories as follows, matching products
  by their existing code:

  | Code | Title | Categories |
  | --- | --- | --- |
  | P100 | The Hunger Games | Fiction, Young Adult |
  | P101 | To Kill a Mockingbird | Fiction, Classics |
  | P102 | The Chronicles of Narnia | Fiction, Fantasy, Young Adult |
  | P103 | Gone with the Wind | Fiction, Classics |
  | P104 | The Fault in Our Stars | Fiction, Young Adult |
  | P105 | The Giving Tree | Fiction, Young Adult |
  | P106 | The Da Vinci Code | Fiction, Mystery and Thriller |
  | P107 | The Alchemist | Fiction, Classics |
  | P108 | Charlotte's Web | Fiction, Young Adult |
  | P109 | The Little Prince | Fiction, Classics, Young Adult |
  | P110 | A Thousand Splendid Suns | Fiction |
  | P111 | A Game of Thrones | Fiction, Fantasy |
  | P112 | The Book Thief | Fiction, Young Adult |
  | P113 | One Flew Over the Cuckoo's Nest | Fiction, Classics |
  | P114 | Fifty Shades of Grey | Fiction |

- **R11.** Two seeded products, P102 and P109, belong to three categories each,
  so the many-to-many link is exercised by the seed data without extra
  fixtures.
- **R12.** Fiction holds all 15 seeded products, which is more than one page at
  the page size in R36. Paging on a category page is therefore testable against
  a freshly seeded database.
- **R13.** Seed links are matched by product code and category slug. If a code
  from the R10 table is absent from the target database, that link is skipped
  and the migration still completes. An environment where an admin deleted a
  seeded product does not block the release.
- **R14.** Deploying the same release twice against one database creates no
  duplicate category and no duplicate link. An automated test asserts the
  category count and the link count are unchanged after a second deployment.
- **R15.** An automated test asserts that after the migration the Fantasy page
  returns exactly The Chronicles of Narnia and A Game of Thrones, and that The
  Little Prince appears on the Fiction, Classics, and Young Adult pages.

### 4.3 Header navigation

- **R16.** Every storefront page rendered through `layout.html` shows category
  navigation in the site header. This includes the products page, cart, orders,
  login, and registration.
- **R17.** The entries are read from the database when the page is rendered.
  Renaming a category directly in the database changes the header on the next
  page load, with no deployment and no restart.
- **R18.** Entries are ordered by category name ascending, so two loads against
  unchanged data give the same order. With the seed data that order is
  Classics, Fantasy, Fiction, Mystery and Thriller, Young Adult.
- **R19.** Each entry links to that category's listing page using the URL shape
  in section 4.4.
- **R20.** Header category links are ordinary links that load a full page. They
  are not htmx partial requests, because the header appears on pages such as
  cart and orders that contain no `#products` element for htmx to swap.
- **R21.** When the shopper is viewing a category page, that category's header
  entry is marked as current and is visually distinguishable from the others.
- **R22.** The header shows every category in the database, whatever number of
  visible products each holds. The reading chosen is that navigation reflecting
  the catalogue's structure is easier to reason about than navigation that
  appears and disappears as products are soft-deleted, and R39 makes an empty
  category page usable rather than a dead end. Open question 3 revisits this if
  the category count grows.
- **R23.** Rendering one page issues at most one database query for the header
  categories, whatever else that page renders.
- **R24.** A page rendered against a database with no categories shows the
  header without a category area and renders normally with no error.

### 4.4 Category listing page

The category listing is served at `/products?category=<slug>`. Two facts drive
that choice. First, `WebSecurityConfig` permits anonymous `GET /products` and
requires authentication for anything not explicitly listed, so a new path such
as `/categories/{slug}` would send guests to the login page until that file
changes, and that file sits in `com.sivalabs.bookstore.config`, outside the
catalog module this work item is scoped to. Second, an optional parameter on an
existing public URL leaves every URL that works today working unchanged, so the
public API rule about breaking changes is not engaged. Open question 1 covers
adding a dedicated path later.

- **R25.** `GET /products?category=<slug>` renders a paged listing of only the
  products linked to that category.
- **R26.** That page shows the category's display name as its heading.
- **R27.** That page shows the total number of products in the category that
  the shopper can see, counted under the same conditions as R30.
- **R28.** Product cards on a category page have the same content and the same
  Add to Cart behaviour as the cards on the full listing.
- **R29.** Slug matching is case-insensitive, so `?category=fiction` and
  `?category=Fiction` reach the same page.
- **R30.** A product whose `deleted_at` is set never appears on a category page
  and is never counted in R27, for every role including a signed-in admin. This
  matches the current storefront listing.
- **R31.** A product that belongs to more than one category appears on the page
  of each of those categories.
- **R32.** A request with no `category`, an empty `category`, or a `category`
  of only whitespace renders the full catalogue exactly as `/products` does
  today, with the same order and the same page size.
- **R33.** A `category` value matching no category renders the application's
  404 page with the message `Category not found: <slug>` and HTTP status 404.
  It does not render as an empty product grid, because a stale link and an
  empty category are different situations for the shopper.
- **R34.** Existing `/products` and `/products?page=N` URLs keep working
  unchanged. `category` is optional, so nothing that works today breaks and no
  new API version is needed.
- **R35.** The 404 in R33 is produced through the existing
  `CatalogExceptionHandler`, which already maps a not-found condition to
  `error/404` with the message in the model.

### 4.5 Paging

- **R36.** Category results are paged at 10 products per page, the size
  `ProductService` uses today.
- **R37.** Pagination links carry the current category. Moving to page 2 of
  Fiction stays in Fiction. The shared pagination fragment builds links as
  `/products?page=N` today, so it must carry the category when one is active.
- **R38.** The browser URL reflects the current category and page. Opening that
  URL directly reproduces the same result page.
- **R39.** A category with no visible products renders its heading, a count of
  0, the message `No products in this category yet`, and a link back to
  `/products`.
- **R40.** A page number below 1 is treated as page 1, which is how
  `ProductService.getProducts` behaves today.
- **R41.** A page number above the last page renders an empty product grid with
  working pagination controls back to the earlier pages, and does not error.
- **R42.** Products on a category page are ordered by name ascending, matching
  the full listing, with ties broken on product code. Paging through a category
  never repeats a product and never skips one because two products share a
  name.
- **R43.** Category listing and its paging work for a full page load and for an
  htmx partial request, because the products page swaps its grid through htmx
  today.

### 4.6 Permissions

`WebSecurityConfig` permits anonymous `GET /products` today. The reading chosen
and committed to here is that category browsing is available to guests, because
a category page can only show a subset of what the already-public listing
shows. Putting a sign-in wall in front of a subset of public data would change
the storefront access model, which this item was not asked to do. R44 to R49
are firm on that basis and no open question is left against them.

- **R44.** A guest can see the header category navigation and open any category
  page.
- **R45.** A member sees exactly the same categories in the header and exactly
  the same products on a category page as a guest. No result depends on being
  signed in.
- **R46.** An admin browsing the storefront sees the same categories and the
  same products as everyone else. Soft-deleted products stay hidden from the
  storefront for an admin too, under R30.
- **R47.** No role can create, rename, or delete a category, or change which
  categories a product belongs to, through the application. Those changes come
  only from a database migration in this item. Open question 2 decides when
  admin management arrives.
- **R48.** The admin area under `/admin/**` keeps its current behaviour and
  gains no category controls. The admin product list, product page, and product
  form are unchanged.
- **R49.** This item makes no authenticated page public and no public page
  authenticated. The only access-surface change is a new optional parameter on
  the already-public `GET /products`.

### 4.7 Tenancy

The business context requires every table to be scoped by `workspace_id` and
every query to filter on it. `catalog.products` has no `workspace_id` column
today, and no table in the catalog schema has one. The reading chosen is the
one that protects tenant isolation without inventing scope. Adding
`workspace_id` to the new tables alone would create a column the application
has no value to populate, and would let a category be scoped to a workspace
while the products inside it are not, so a scoped category would still return
unscoped rows. The stronger position is to keep the new tables matching
`catalog.products` and to guarantee that category browsing cannot become a
second read path into products, so that scoping can be added to all three
tables in one change.

- **R50.** The category table and the link table live in the `catalog` schema
  alongside `catalog.products` and carry no `workspace_id`, matching
  `catalog.products` as it stands.
- **R51.** Link rows reference only tables in the `catalog` schema, so
  workspace scoping can later be applied to products, categories, and links
  together.
- **R52.** Category queries run through the same catalog repository and service
  layer that the current product listing uses. There is no second query path to
  the products table.
- **R53.** The set of products on any category page is a subset of what the
  full storefront listing returns across all of its pages. Category browsing
  can only narrow what a shopper sees, never widen it.
- **R54.** Every filter the storefront listing applies, today the `deleted_at
  is null` condition, applies to the category listing and to the count in R27.
  When tenant scoping is added to the catalog it reaches category browsing
  through that same shared query path, with no change to the category code.
- **R55.** No query added by this item reads a table outside the `catalog`
  schema.

### 4.8 Audit

The business context requires user-visible actions to append to the audit log.
Everything a user does in this item is a read: seeing the header, opening a
category, and paging within it. The reading chosen is that these append no
audit entries, because recording every category page view would produce a large
volume of entries that say nothing about who changed what in the catalogue.
This repository has no audit log implementation and no audit module, so the
requirements below state what must hold once one exists.

- **R56.** Rendering the header navigation, opening a category page, and paging
  within a category append no audit entry.
- **R57.** Seeding categories and links is a migration step rather than a user
  action, so it appends no audit entry.
- **R58.** This item adds no user action that changes state, so it adds no new
  audited path.
- **R59.** When admin category management is built under open question 2,
  creating, renaming, and deleting a category, and changing which categories a
  product belongs to, are each audited the way product edits are audited at
  that time, with no exemption for category changes.
- **R60.** No audit behaviour anywhere else in the application changes.

### 4.9 Migration

- **R61.** The change ships as a single new versioned migration in
  `src/main/resources/db/migration/catalog`, following the existing
  `V<n>__catalog_*.sql` naming and taking the next version number not already
  used in that folder. The folder holds V1 to V4 today.
- **R62.** That migration creates the category table, creates the link table,
  seeds the categories from R9, and seeds the links from R10.
- **R63.** The migration completes without error against a database that
  already holds the 15 seeded products, and against a database whose products
  table is empty.
- **R64.** Existing product rows keep their current `code`, `name`,
  `description`, `image_url`, `price`, and `deleted_at` values. The migration
  writes no column of `catalog.products`.
- **R65.** The migration is forward-only and runs once. Deploying the same
  release twice does not attempt it again.
- **R66.** If the migration fails, the application does not start against that
  database and the failure is visible in the startup logs. Whether the
  previously deployed version keeps serving traffic depends on each
  environment's deployment mechanism rather than on anything this item builds,
  so that is an assumption about the surrounding setup and not a requirement on
  the catalog module.
- **R67.** The migration adds, alters, and drops no column of
  `catalog.products`, so it does not rewrite that table and takes no `ACCESS
  EXCLUSIVE` lock on it. Creating the link table's foreign key to
  `catalog.products` takes a `SHARE ROW EXCLUSIVE` lock on products for the
  duration of the migration, which blocks concurrent writes such as an admin
  saving a product edit, and does not block storefront reads. Blocked writes
  wait and then proceed.
- **R68.** The cost of the migration scales with the number of link rows it
  inserts, fixed at the R10 table, rather than with the number of products
  already in the database. An automated test seeds `catalog.products` with
  100,000 rows, runs the migration, and asserts it completes within 60 seconds.
  This test may be tagged as slow and must run in the pipeline that gates a
  merge to the main branch.
- **R69.** After the migration and a normal deployment, the header shows the
  five seeded categories and each category page returns its seeded products,
  with no separate backfill command and no manual data step.

### 4.10 Module boundary

- **R70.** Every Java class added or changed by this item lives under
  `com.sivalabs.bookstore.catalog`. No Java file in another module changes.
- **R71.** The existing `ModularityTests` and `ArchitectureTests` pass
  unchanged.
- **R72.** No module other than catalog depends on a category type. The catalog
  module's published API in `com.sivalabs.bookstore.catalog` gains no category
  type, because no other module needs categories in this item.
- **R73.** No file under `com.sivalabs.bookstore.config` changes, including
  `WebSecurityConfig`. The URL shape in section 4.4 is what makes that
  possible.
- **R74.** The only file changed outside the catalog packages is the shared
  template `layout.html`, which gains a reference to a header fragment. The
  fragment and the data behind it are owned by the catalog module. A reviewer
  can confirm the `layout.html` change is limited to that reference.
- **R75.** Category data reaches the shared layout with no change to any
  controller outside the catalog module. A page served by the orders or cart
  code renders the category header without its controller knowing categories
  exist.

### 4.11 Errors and resilience

- **R76.** When the category query behind the header fails, for example because
  the database is unreachable, a page that does not itself depend on categories
  still renders with HTTP 200 and shows the header without the category area.
  Cart, orders, and login do not turn into error pages because a category
  lookup failed.
- **R77.** A header category failure is logged at warning level with enough
  detail to identify the cause, and nothing about it is shown to the shopper.
- **R78.** When a category page cannot complete because the database is
  unreachable, the shopper sees the application's standard error page rather
  than a stack trace, and the message names no database objects.
- **R79.** No `category` value produces a server error. Punctuation, quotes,
  SQL fragments, percent-encoded bytes, and values longer than any stored slug
  all produce either a category page or the 404 from R33.
- **R80.** A `category` value longer than 100 characters is treated as no match
  and produces the R33 404 page.

## 5. Edge cases and failure modes

**Unknown or stale slug.** A bookmark or external link pointing at a category
that was renamed or removed gets the 404 from R33 with the slug in the message,
rather than a blank grid that reads as an empty catalogue.

**Empty or whitespace category parameter.** Covered by R32. A link that ends up
as `?category=` behaves like plain `/products`, so a malformed link does not
blank the catalogue.

**Category whose products are all soft-deleted.** The category stays in the
header under R22, and its page renders the empty state from R39 with a way back
to the full catalogue, so a shopper who clicks it is not stranded.

**Product in several categories.** P102 and P109 are each in three categories
under R10. Each appears on all three of its pages under R31 and is counted once
per category under R27. It appears once on a page rather than three times,
because R7 allows only one link row per product and category.

**Product soft-deleted between the count and the page query.** The count in R27
and the page of products are read in the same request. If a product is
soft-deleted in between, the count can read one higher than the number of cards
shown for that moment. The page renders normally and corrects itself on the
next load. This is how the existing products listing already behaves and does
not justify a locking scheme.

**Product soft-deleted or restored while a shopper pages.** The result set
shifts under the shopper, so a product can appear on two consecutive pages or
be skipped. R42's tie-break on product code removes the version of this caused
by equal sort keys. The version caused by rows genuinely appearing or
disappearing remains, and matches the current products listing.

**Soft delete and restore of a linked product.** Soft-deleting a product leaves
its link rows in place, so `restoreByCode` puts it back in the same categories
with no re-linking step. R30 keeps it out of category pages while it is
deleted.

**Migration version collision.** Another item may add a migration to the
catalog folder in parallel. Whichever merges second takes the next free version
number under R61. If both are prepared against the same number, the second one
to merge is renumbered before it lands, and a Flyway checksum error at startup
is the signal that this was missed.

**Category count outgrowing the header.** Five categories fit a header
comfortably. R22 shows all of them, so a database with dozens of categories
would crowd the header. Nothing in this item can reach that state, because
categories come only from the seed migration, and open question 3 settles the
rule before management screens make it reachable.

**Database unavailable while rendering the header.** R76 and R77 keep the rest
of the site usable and keep the failure out of the shopper's view. The category
area is missing until the database recovers, with no deploy needed.

**Long or hostile slug input.** R79 and R80 route any `category` value to
either a category page or a 404. Nothing in this item concatenates the slug
into SQL.

**Second deployment of the same release.** R14 and R65 mean a repeated
deployment leaves category and link data exactly as it was, so a redeploy
during an incident does not duplicate navigation entries.

**htmx partial that arrives without the category.** The pagination fragment is
shared with the full listing. If a link drops the category, the request falls
under R32 and swaps in the full catalogue grid, which is visibly wrong to the
shopper rather than silently wrong. R37 and R43 are what a reviewer checks to
confirm this does not happen.

## 6. Open questions

1. Decide whether category browsing should later move to a dedicated URL such
   as `/categories/{slug}` instead of the `?category=` parameter this item
   ships. That change needs one entry added to the public path list in
   `WebSecurityConfig`, which is outside the catalog module, so it belongs to a
   separate item. Someone needs to weigh cleaner URLs against the module
   boundary this item was given.

2. Decide which item builds admin management of categories, meaning create,
   rename, delete, and assigning products to categories, and confirm it carries
   the audit requirements in R59. Until then, categories change only through a
   migration, so a product an admin adds belongs to no category and is
   reachable only from the full listing.

3. Decide the rule for how many categories the header shows once the number
   grows past what fits, for example the first N by name with an overflow menu,
   or only categories with at least one visible product. R22 shows all of them,
   which is right for five and wrong for fifty. This decision is needed before
   the management screens in open question 2 ship.

4. Decide whether the header category query should be cached and, if so, how
   stale it may be. R23 holds it to one query per page render, which is
   acceptable for five rows on a page that already queries products. A measured
   cost at higher traffic would change that.

5. Decide whether category pages need search engine treatment, meaning
   canonical URLs, a sitemap entry, or crawlable links, given that the category
   is a query parameter under section 4.4. This is a marketing decision, and it
   may change the answer to open question 1.

6. Decide the plan for adding workspace scoping to the catalog schema as a
   single change covering products, categories, and the link table, and who
   owns it. Section 4.7 explains why this item matches what `catalog.products`
   does today rather than scoping the new tables on their own.

7. Decide whether a product's categories should be visible on the product card,
   on the admin product page, or on a product detail page. This item shows
   categories only in the header and as the heading of a category page, so an
   admin cannot see a given product's categories anywhere in the application.
