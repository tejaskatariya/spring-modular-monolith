# BOOK-1: Product search and filtering

## 1. Problem

Shoppers browsing the bookstore cannot look for a specific book. The storefront
listing at `/products` is the only way to reach a product, and it renders a fixed
page of products sorted by name with previous and next links. There is no text
input on the page, no way to narrow by price, and no way to change the sort
order.

How we know:

- `ProductWebController.showProducts` accepts a single `page` parameter and
  nothing else.
- `ProductService.getProducts` hard-codes a sort by name ascending and a page
  size of 10.
- The product listing template renders a card grid with pagination controls
  above and below it, and no search or filter controls.
- The seed data already contains 15 books, so a shopper looking for a known
  title pages through the catalogue to find it. Every book added afterwards
  makes that worse.

Two groups feel this. Shoppers who arrive knowing what they want have to scan
pages of unrelated books. Admins who add products have no way to confirm a
title is reachable by the name a shopper would type.

## 2. Goals and non-goals

### Goals

- Shoppers can search the catalogue by book title and by author.
- Shoppers can narrow results to a price range.
- Shoppers can sort results by price or by title, in either direction.
- Results stay paged, and the current search, filter, and sort survive paging.
- Search runs on a Postgres full-text index rather than a scan over every row.
- The database change ships safely to an environment whose products table
  already holds data.
- All code changes stay inside the catalog module.

### Non-goals

- Category browsing and category navigation. That is BOOK-2.
- Searching the product description. Only title and author are searchable.
- Search on the admin product list at `/admin/products`. That list keeps its
  current behaviour.
- Typo tolerance, fuzzy matching, synonyms, autocomplete, and search
  suggestions.
- A public REST or JSON API for search. There is no product REST controller
  today and this item does not add one.
- Search analytics, popular-search reporting, and search term storage.
- Adding a `workspace_id` column to `catalog.products` or any other tenancy
  change to the catalog schema. Section 4.7 explains the reading taken.
- Changes to cart, checkout, orders, inventory, notifications, or users.

## 3. User stories

- A visitor who is not signed in can type a title or author into a search box
  on the products page so that they reach the book they came for without
  paging through the catalogue.
- A signed-in shopper (`member`) can search, filter by price, and sort the
  results so that they can compare books within a budget.
- A shopper can clear the search box and see the full catalogue again so that
  they can go back to browsing without reloading the site or editing the URL.
- A shopper can page through search results so that a large result set stays
  readable.
- A shopper can copy the URL of a result page and open it later so that a
  search they want to keep is shareable.
- A shopper whose search matches nothing can see that it matched nothing and
  clear their criteria in one action so that they are not left on an empty
  page with no way forward.
- An admin can record an author on a product in the existing admin product
  form so that the product becomes reachable by an author search.
- An admin can deploy the release to an environment that already contains
  products and have the migration complete without a manual backfill step so
  that the rollout needs no database hand-holding.

Roles in the business context are `admin`, `member`, and `guest`. In this
codebase the storefront product list is public, so a `guest` here means an
unauthenticated visitor. Section 4.6 states what each role can do.

## 4. Requirements

### 4.1 Search

- **R1.** The products page shows a single search input that accepts free text
  and applies to product title and author.
- **R2.** A search whose text is empty, missing, or only whitespace returns the
  full catalogue, in the same order and with the same paging as the products
  page returns today.
- **R3.** A search matches a product when the text matches its title, its
  author, or a combination of words drawn from both fields.
- **R4.** Matching is case-insensitive. Searching `hunger games`,
  `Hunger Games`, and `HUNGER GAMES` returns the same products.
- **R5.** When a search contains more than one word, a product matches only if
  it matches every word. Searching `alchemist coelho` does not return books
  that match only `alchemist`.
- **R6.** The final word of a search is matched as a prefix, so `alchem`
  returns `The Alchemist` while the shopper is still typing.
- **R7.** Search runs against a stored `tsvector` column on
  `catalog.products` that is generated from title and author, backed by a GIN
  index. A reviewer can confirm this by running `EXPLAIN` on the search query
  and seeing an index scan rather than a sequential scan over `products`.
- **R8.** Searches never match on the product description, the product code, or
  the image URL.
- **R9.** A search longer than 200 characters is rejected. The page shows the
  message `Search is limited to 200 characters` and no results, and the search
  box keeps what the shopper typed.

### 4.2 Price filtering

- **R10.** The products page shows a minimum price input and a maximum price
  input. Both are optional and can be used on their own.
- **R11.** A minimum price returns products whose price is greater than or
  equal to that value. A maximum price returns products whose price is less
  than or equal to that value. Both bounds are inclusive.
- **R12.** A price bound that is not a number, or is negative, is rejected. The
  page shows the message `Enter a price of 0 or more` and no results.
- **R13.** A minimum price greater than the maximum price is rejected. The page
  shows the message `Minimum price must be less than or equal to maximum price`
  and no results.
- **R14.** Price filtering and search combine. A shopper who searches `narnia`
  with a maximum price of 40 sees only Narnia matches priced at 40 or less.

### 4.3 Sorting

- **R15.** The products page offers these sort options and no others: price
  ascending, price descending, title ascending, title descending.
- **R16.** When the search box is empty, the default sort is title ascending.
  This matches the order the products page uses today.
- **R17.** When the search box holds text and the shopper has not chosen a
  sort, results are ordered by full-text relevance, most relevant first.
- **R18.** A sort chosen by the shopper overrides the default in R16 and R17.
- **R19.** Every ordering breaks ties on the product code, so two books with
  the same price or the same title always come back in the same order. Paging
  through a result set never repeats a product and never skips one because of
  a tie.
- **R20.** An unrecognised sort value is ignored and the default sort from R16
  or R17 applies. The page renders normally and shows no error.

### 4.4 Paging

- **R21.** Results are paged at 10 products per page, the size the products
  page uses today.
- **R22.** The page shows the total number of matching products.
- **R23.** Pagination links carry the current search text, price bounds, and
  sort. Moving to page 2 of a search keeps the shopper in that search.
- **R24.** The browser URL reflects the current search, price bounds, sort, and
  page. Opening that URL directly reproduces the same result page.
- **R25.** A page number below 1 is treated as page 1, which is how the
  products page behaves today.
- **R26.** A page number above the last page renders an empty result grid with
  working pagination controls back to the earlier pages, and does not error.
- **R27.** A search that matches nothing renders a message that no products
  matched, together with a control that clears the search and filters and
  returns the shopper to the full catalogue.
- **R28.** Search, filtering, sorting, and paging all work for both a full page
  load and an htmx partial request, because the products page updates its grid
  through htmx today.

### 4.5 Author data

- **R29.** A product has an optional author. Products that have no author still
  appear in unfiltered results and can still be found by title.
- **R30.** An admin can set and change a product's author in the existing admin
  product create and edit forms.
- **R31.** A product's author is included in its full-text index as soon as the
  product is saved. An admin who adds an author and searches for it finds the
  product on the next search, with no reindex step and no scheduled job.

### 4.6 Permissions

- **R32.** Search, price filtering, and sorting are available to unauthenticated
  visitors, because `GET /products` is public today. This item does not change
  who can reach the products page.
- **R33.** A signed-in `member` sees exactly the same results as an
  unauthenticated visitor for the same criteria. Nothing about the results
  depends on being signed in.
- **R34.** Soft-deleted products, meaning rows where `deleted_at` is set, never
  appear in storefront search results, for any role, including an admin who is
  signed in. This matches the current storefront listing, which excludes them.
- **R35.** Only an admin can set a product's author, because product editing is
  already restricted to `/admin/**`. A member or a visitor who requests the
  admin product form is refused by the existing security rules.
- **R36.** The admin product list keeps showing all products including
  soft-deleted ones, and gains no search, filter, or sort controls in this
  item.
- **R37.** Existing `/products` and `/products?page=N` URLs keep working
  unchanged. The new parameters are optional additions, so nothing that works
  today breaks and no new API version is needed.

### 4.7 Tenancy

The business context requires every table to be scoped by `workspace_id` and
every query to filter on it. `catalog.products` has no `workspace_id` column
today, and the storefront listing does not scope by tenant. The reading chosen
here is the one that protects tenant isolation without inventing scope: search
must not create a second way to read products, so it cannot become a path that
returns rows the existing listing would withhold.

- **R38.** Search, price filtering, and sorting run through the same catalog
  repository and service layer that the current product listing uses. There is
  no separate query path to the products table.
- **R39.** The result set for any search is a subset of what the current
  storefront listing returns across all its pages. Search can only narrow what
  a shopper can see.
- **R40.** Every scoping condition the storefront listing applies, today the
  `deleted_at is null` condition, applies to search, filtering, and sorting as
  well. When tenant scoping is added to the catalog, it applies to search
  through the same shared query path with no change to the search code.
- **R41.** No query added by this item reads a table outside the `catalog`
  schema, and no code added by this item lives outside the catalog module. A
  reviewer can confirm this from the Spring Modulith module tests that already
  run in this repository.

### 4.8 Audit

The business context requires user-visible actions to append to the audit log.
Search, filtering, and sorting are read-only queries that change no state, and
the reading chosen is that they do not append audit entries. Recording every
shopper search would add a large volume of entries that say nothing about who
changed what in the catalogue.

- **R42.** Running a search, applying a price filter, changing the sort, or
  paging appends no audit entry.
- **R43.** Setting or changing a product's author is an admin edit to a
  product, so it is audited exactly the way other product edits are audited
  today. This repository has no audit log implementation yet, so this
  requirement means the author edit follows whatever the product edit path
  does, and does not get an exemption.
- **R44.** No audit behaviour anywhere else in the application changes.

### 4.9 Migration

- **R45.** The change ships as a new versioned migration in the catalog
  migration folder, following the existing `V<n>__catalog_*.sql` naming.
- **R46.** The migration adds the author column, the generated `tsvector`
  column, and the GIN index.
- **R47.** The migration completes without error against a database that
  already contains products, including the 15 seeded books.
- **R48.** After the migration, existing products are searchable by title with
  no separate backfill command and no application restart beyond the normal
  deployment.
- **R49.** Existing product rows keep their current code, name, description,
  image URL, price, and `deleted_at` values. The migration adds columns and
  does not rewrite data.
- **R50.** The migration is forward-only and runs once. Running the deployment
  twice against the same database does not attempt the migration again.
- **R51.** If the migration fails, the application does not start against that
  database, the failure is visible in the startup logs, and the previously
  deployed version keeps serving traffic.

### 4.10 Errors

- **R52.** No shopper input, including punctuation, quotes, boolean operators
  such as `&`, `|`, and `!`, and SQL fragments, produces a server error. Such
  input is treated as ordinary search text and yields either matches or no
  matches.
- **R53.** When the search cannot complete because the database is unreachable
  or the query times out, the shopper sees the application's standard error
  page rather than a stack trace, and the message does not name database
  objects.

## 5. Edge cases and failure modes

**Empty and whitespace search.** Covered by R2. A search box holding only
spaces behaves the same as an empty one, so a stray space does not blank the
catalogue.

**Search text that breaks the query parser.** Postgres text search syntax
treats `&`, `|`, `!`, `:`, `*`, and quotes as operators. A shopper typing
`C++ & me` or `"` must get a result page rather than a server error. R52
covers this.

**Search that matches nothing.** R27 gives the shopper a message and a way
back to the full catalogue.

**Products with no author.** All 15 seeded books have no author today. They
must stay visible in the unfiltered catalogue and stay findable by title, and
an author search simply does not return them. R29 covers this.

**Both price bounds equal.** A minimum and maximum of 32.0 returns books
priced exactly 32.0, because both bounds are inclusive under R11.

**Price bounds outside the numeric range.** A value with more precision or
magnitude than the `price` column holds is rejected under R12 as a value that
is not a usable price, rather than reaching the database and failing there.

**Ties in the sort key.** Several seeded books share a price of 44.50 and
several share 14.50. Without the tiebreaker in R19, page 1 and page 2 can
return the same book or drop one. This is the most likely paging defect and
needs a test.

**Product soft-deleted between page render and click.** A shopper can be
looking at a result page listing a product an admin deletes a moment later.
Clicking through to that product hits the existing catalog not-found handling.
The result page itself is not refreshed, so the shopper sees the stale card
until they page or search again. That stale card is accepted behaviour.

**Product edited while a shopper pages.** An admin changing a price or a title
between page 1 and page 2 can shift a product across the page boundary, so a
shopper can see it twice or miss it. The total count can also change between
pages. This is accepted for a catalogue of this size, and no snapshot or
cursor paging is introduced.

**Concurrent admin writes during the migration.** Adding the generated column
and the index takes a lock on the products table. Admin product edits issued
during that window wait rather than fail. On the current data volume this is
brief. On a large catalogue the deployment should run the index build in a way
that does not block writes for the duration.

**Migration fails partway.** R51 states the outcome. The deployment fails
loudly and the previous version keeps serving, so shoppers see the old products
page rather than an error.

**Deployment where the index is present but the application is old.** The added
columns are nullable additions and the previous application version does not
reference them, so an older instance running against the migrated database
continues to work during a rolling deployment.

**Search issued as an htmx partial request.** The products page swaps its grid
through htmx. A partial request that loses the search criteria would silently
reset the shopper to the full catalogue, so R23, R24, and R28 need a test at
the partial level and not only at the full-page level.

## 6. Open questions

1. **Author backfill for the 15 seeded books.** Decide whether to add real
   authors to the existing seed data as part of this item, or ship the author
   column empty and let admins fill it in. Search by author returns nothing
   useful until one of these happens.
2. **Author on the storefront.** Decide whether the product card and product
   detail page show the author, or whether the author is only a search input
   for now. This spec requires the author to be searchable and admin-editable
   and does not require it to be displayed.
3. **Accent-insensitive matching.** Decide whether searching `garcia` should
   match `García`. This needs the `unaccent` extension installed in every
   environment including production, which is a database administration
   decision outside the catalog module.
4. **Page size.** Decide whether search results keep the existing page size of
   10 or whether the shopper can choose. This spec keeps 10.
5. **Admin list parity.** Decide whether admins get the same search on
   `/admin/products` in a follow-up item. This spec excludes it.
6. **Tenant scoping for the catalog.** Decide whether `catalog.products` is
   intentionally a single global catalogue, or whether the missing
   `workspace_id` column is a gap to close in a separate item. Section 4.7
   assumes the catalog stays as it is and requires search to inherit whatever
   scoping the listing applies. Confirming which of the two is intended before
   this ships avoids a second query path later.
7. **Role vocabulary.** The business context names `admin`, `member`, and
   `guest`. This codebase has `ROLE_ADMIN` and `ROLE_USER` plus anonymous
   access to the products page. Decide whether unauthenticated visitors keep
   search access, which R32 assumes, or whether search should require a
   sign-in.
8. **Search term telemetry.** Decide whether searches that return no results
   are worth counting so the team can see what shoppers look for and cannot
   find. R42 records no search activity today.
