# BOOK-1: Product search and filtering

## 1. Problem

Shoppers browsing the bookstore cannot look for a specific book. The storefront
listing at `/products` is the only way to reach a product, and it renders a
fixed page of products sorted by name with previous and next links. There is no
text input on the page, no way to narrow by price, and no way to change the
sort order.

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

- Shoppers can search the catalogue by book title.
- Shoppers can search the catalogue by author, and author search works against
  the seeded catalogue on the day this ships. This item fills in the author of
  each of the 15 seeded books, so author search is demonstrable at launch
  rather than only after an admin types an author in. Requirements R33 and R34
  cover the backfill.
- Shoppers can narrow results to a price range.
- Shoppers can sort results by price or by title, in either direction.
- Results stay paged, and the current search, filter, and sort survive paging.
- Search runs on a Postgres full-text index rather than a scan over every row,
  and an automated test keeps it that way.
- The database change ships safely to an environment whose products table
  already holds data, within a stated table-size ceiling.
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
- A low-lock migration path for catalogues above the ceiling in R52. Section
  4.9 states what such a path would require and why this item does not build
  it.
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
  clear their criteria in one action so that they are not left on an empty page
  with no way forward.
- A shopper can search for an author of a seeded book, such as `coelho`, on a
  freshly deployed environment so that author search is usable before any admin
  has edited a product.
- An admin can record an author on a product in the existing admin product form
  so that a newly added product becomes reachable by an author search.
- An admin can deploy the release to an environment that already contains
  products and have the migration complete without a manual backfill step so
  that the rollout needs no database hand-holding.
- A release engineer can check one number, the product row count, before
  applying the release so that they know whether the migration's table lock is
  acceptable for that environment.

Roles in the business context are `admin`, `member`, and `guest`. In this
codebase the storefront product list is public, so a `guest` here means an
unauthenticated visitor. Section 4.6 states what each role can do and commits
to that reading.

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
  it matches every word. Searching `alchemist coelho` returns `The Alchemist`,
  and searching `alchemist tolkien` returns nothing.
- **R6.** The final word of a search is matched as a prefix, so `alchem`
  returns `The Alchemist` while the shopper is still typing.
- **R7.** Search runs against a stored `tsvector` column on `catalog.products`
  that is generated from title and author, backed by a GIN index.
- **R8.** An automated test asserts that the search query uses that index. The
  test loads at least 5,000 products into `catalog.products`, runs `EXPLAIN` on
  the search query the application issues, and asserts that the plan contains a
  bitmap index scan on the GIN index and contains no sequential scan on
  `catalog.products`. The test must not set `enable_seqscan = off`, because
  that would let the assertion pass on a plan the application would never get.
  Dropping the index or rewriting the query as a `LIKE` scan must make this
  test fail. The test runs in the same pipeline as the rest of the test suite,
  so the index stays a regression check rather than a one-time review step.
- **R9.** Searches never match on the product description, the product code, or
  the image URL.
- **R10.** A search longer than 200 characters is rejected. The page shows the
  message `Search is limited to 200 characters` and no results, and the search
  box keeps what the shopper typed.

### 4.2 Price filtering

- **R11.** The products page shows a minimum price input and a maximum price
  input. Both are optional and can be used on their own.
- **R12.** A minimum price returns products whose price is greater than or
  equal to that value. A maximum price returns products whose price is less
  than or equal to that value. Both bounds are inclusive.
- **R13.** A price bound that is not a number, or is negative, is rejected. The
  page shows the message `Enter a price of 0 or more` and no results.
- **R14.** A minimum price greater than the maximum price is rejected. The page
  shows the message `Minimum price must be less than or equal to maximum price`
  and no results.
- **R15.** Price filtering and search combine. A shopper who searches `narnia`
  with a maximum price of 40 sees only Narnia matches priced at 40 or less.

### 4.3 Sorting

- **R16.** The products page offers these sort options and no others: price
  ascending, price descending, title ascending, title descending.
- **R17.** When the search box is empty, the default sort is title ascending.
  This matches the order the products page uses today.
- **R18.** When the search box holds text and the shopper has not chosen a
  sort, results are ordered by full-text relevance, most relevant first.
- **R19.** A sort chosen by the shopper overrides the default in R17 and R18.
- **R20.** Every ordering breaks ties on the product code, so two books with
  the same price or the same title always come back in the same order. Paging
  through a result set never repeats a product and never skips one because of a
  tie.
- **R21.** An unrecognised sort value is ignored and the default sort from R17
  or R18 applies. The page renders normally and shows no error.

### 4.4 Paging

- **R22.** Results are paged at 10 products per page, the size the products
  page uses today.
- **R23.** The page shows the total number of matching products.
- **R24.** Pagination links carry the current search text, price bounds, and
  sort. Moving to page 2 of a search keeps the shopper in that search.
- **R25.** The browser URL reflects the current search, price bounds, sort, and
  page. Opening that URL directly reproduces the same result page.
- **R26.** A page number below 1 is treated as page 1, which is how the
  products page behaves today.
- **R27.** A page number above the last page renders an empty result grid with
  working pagination controls back to the earlier pages, and does not error.
- **R28.** A search that matches nothing renders a message that no products
  matched, together with a control that clears the search and filters and
  returns the shopper to the full catalogue.
- **R29.** Search, filtering, sorting, and paging all work for both a full page
  load and an htmx partial request, because the products page updates its grid
  through htmx today.

### 4.5 Author data

- **R30.** A product has an optional author. Products that have no author still
  appear in unfiltered results and can still be found by title.
- **R31.** An author is free text of up to 255 characters. The admin product
  form rejects a longer value with the message
  `Author is limited to 255 characters` and does not save the product.
- **R32.** An admin can set and change a product's author in the existing admin
  product create and edit forms.
- **R33.** The migration in section 4.9 sets the author on the 15 seeded
  products, matched by product code, to these values:

  | Code | Title | Author |
  | --- | --- | --- |
  | P100 | The Hunger Games | Suzanne Collins |
  | P101 | To Kill a Mockingbird | Harper Lee |
  | P102 | The Chronicles of Narnia | C. S. Lewis |
  | P103 | Gone with the Wind | Margaret Mitchell |
  | P104 | The Fault in Our Stars | John Green |
  | P105 | The Giving Tree | Shel Silverstein |
  | P106 | The Da Vinci Code | Dan Brown |
  | P107 | The Alchemist | Paulo Coelho |
  | P108 | Charlotte's Web | E. B. White |
  | P109 | The Little Prince | Antoine de Saint-Exupery |
  | P110 | A Thousand Splendid Suns | Khaled Hosseini |
  | P111 | A Game of Thrones | George R. R. Martin |
  | P112 | The Book Thief | Markus Zusak |
  | P113 | One Flew Over the Cuckoo's Nest | Ken Kesey |
  | P114 | Fifty Shades of Grey | E. L. James |

  The author of P109 is written without accents, so that searching `exupery`
  finds it without the `unaccent` extension. Open question 2 covers accented
  input more generally.

- **R34.** The backfill in R33 writes only to rows whose code appears in that
  table and whose author is currently empty. A row with an author already set,
  and any row whose code is not in the table, is left unchanged. An admin who
  edited a seeded product before the upgrade does not lose that edit.
- **R35.** An automated test asserts that after the migration runs, searching
  `coelho` returns exactly `The Alchemist`, and searching `martin` returns
  exactly `A Game of Thrones`.
- **R36.** A product's author is included in its full-text index as soon as the
  product is saved. An admin who adds an author and searches for it finds the
  product on the next search, with no reindex step and no scheduled job.

### 4.6 Permissions

The business context names `admin`, `member`, and `guest`. This codebase has
`ROLE_ADMIN` and `ROLE_USER` plus anonymous access to `GET /products`. The
reading chosen and committed to here is that search is available to
unauthenticated visitors, because the products page is public today and putting
a sign-in wall in front of it would be a change to the storefront's access
model that this item was not asked to make. Search cannot return a product the
existing public listing would withhold, so keeping it public widens nothing.
R37 to R41 are firm requirements on that basis, and no open question is left
against them.

- **R37.** Search, price filtering, and sorting are available to
  unauthenticated visitors. This item does not change who can reach the
  products page.
- **R38.** A signed-in `member` sees exactly the same results as an
  unauthenticated visitor for the same criteria. Nothing about the results
  depends on being signed in.
- **R39.** Soft-deleted products, meaning rows where `deleted_at` is set, never
  appear in storefront search results, for any role, including an admin who is
  signed in. This matches the current storefront listing, which excludes them.
- **R40.** Only an admin can set a product's author, because product editing is
  already restricted to `/admin/**`. A member or a visitor who requests the
  admin product form is refused by the existing security rules.
- **R41.** The admin product list keeps showing all products including
  soft-deleted ones, and gains no search, filter, or sort controls in this
  item.
- **R42.** Existing `/products` and `/products?page=N` URLs keep working
  unchanged. The new parameters are optional additions, so nothing that works
  today breaks and no new API version is needed.

### 4.7 Tenancy

The business context requires every table to be scoped by `workspace_id` and
every query to filter on it. `catalog.products` has no `workspace_id` column
today, and the storefront listing does not scope by tenant. The reading chosen
here is the one that protects tenant isolation without inventing scope: search
must not create a second way to read products, so it cannot become a path that
returns rows the existing listing would withhold.

- **R43.** Search, price filtering, and sorting run through the same catalog
  repository and service layer that the current product listing uses. There is
  no separate query path to the products table.
- **R44.** The result set for any search is a subset of what the current
  storefront listing returns across all its pages. Search can only narrow what
  a shopper can see.
- **R45.** Every scoping condition the storefront listing applies, today the
  `deleted_at is null` condition, applies to search, filtering, and sorting as
  well. When tenant scoping is added to the catalog, it applies to search
  through the same shared query path with no change to the search code.
- **R46.** No query added by this item reads a table outside the `catalog`
  schema, and no code added by this item lives outside the catalog module. A
  reviewer can confirm this from the Spring Modulith module tests that already
  run in this repository.

### 4.8 Audit

The business context requires user-visible actions to append to the audit log.
Search, filtering, and sorting are read-only queries that change no state, and
the reading chosen is that they do not append audit entries. Recording every
shopper search would add a large volume of entries that say nothing about who
changed what in the catalogue.

- **R47.** Running a search, applying a price filter, changing the sort, or
  paging appends no audit entry.
- **R48.** Setting or changing a product's author is an admin edit to a
  product, so it is audited exactly the way other product edits are audited
  today. This repository has no audit log implementation yet, so this
  requirement means the author edit follows whatever the product edit path
  does, and does not get an exemption.
- **R49.** The seed author backfill in R33 is a migration step rather than a
  user action, so it appends no audit entry.
- **R50.** No audit behaviour anywhere else in the application changes.

### 4.9 Migration, including its locking behaviour

- **R51.** The change ships as a single new versioned migration in the catalog
  migration folder, following the existing `V<n>__catalog_*.sql` naming. It
  adds the author column, backfills the seed authors from R33, adds the
  generated `tsvector` column, and adds the GIN index.
- **R52.** The migration completes without error against a database that
  already contains products, including the 15 seeded books.
- **R53.** After the migration, existing products are searchable by title and
  by the backfilled author with no separate backfill command and no application
  restart beyond the normal deployment.
- **R54.** Existing product rows keep their current code, name, description,
  image URL, price, and `deleted_at` values. The only column value the
  migration writes to an existing row is the author, under the conditions in
  R34.
- **R55.** The migration is forward-only and runs once. Running the deployment
  twice against the same database does not attempt the migration again.
- **R56.** If the migration fails, the application does not start against that
  database, the failure is visible in the startup logs, and the previously
  deployed version keeps serving traffic.

Locking behaviour. The `tsvector` column is `GENERATED ... STORED`, so adding
it rewrites every row of `catalog.products`, and the rewrite plus the index
build hold an `ACCESS EXCLUSIVE` lock on the table until the migration commits.
The requirements below state what is accepted and how it is checked.

- **R57.** The migration holds an `ACCESS EXCLUSIVE` lock on `catalog.products`
  from the moment it starts until it commits. Storefront reads and admin edits
  issued during that window wait for the lock and then proceed. They do not
  fail and they do not see a half-applied table.
- **R58.** This locking behaviour is accepted for a `catalog.products` table of
  up to 100,000 rows. Above that, the release must not be applied without the
  decision in open question 6.
- **R59.** An automated migration test seeds `catalog.products` with 100,000
  product rows, then runs the migration against that table and asserts that it
  completes successfully within 60 seconds. This test may be tagged as slow,
  and it must run in the pipeline that gates a merge to the main branch. It is
  the check that R58's ceiling holds, so testing only against the 15 seeded
  rows does not satisfy this requirement.
- **R60.** The release notes for this change state the ceiling from R58 and the
  command a release engineer runs before applying it,
  `select count(*) from catalog.products;`, together with the instruction to
  hold the release for that environment if the count exceeds 100,000. A
  reviewer can confirm this by reading the release notes.
- **R61.** The migration runs inside Flyway's default per-migration
  transaction, and this item adds no Flyway script configuration file. A
  reviewer can confirm this by seeing exactly one new `.sql` file and no new
  `.conf` file in the catalog migration folder.

R61 fixes the shape of the migration for a reason worth stating, because it
constrains any later change. The lower-lock alternatives are
`CREATE INDEX CONCURRENTLY` for the index, and adding a plain column with a
trigger and a chunked backfill instead of a `STORED` generated column. Neither
can run inside a transaction, and Flyway wraps each migration in one by
default. Adopting either would mean splitting the work into a separate
migration configured with `executeInTransaction=false`, which gives up
Flyway's automatic rollback on failure and makes R56's all-or-nothing outcome
something the migration has to handle itself. This item does not take that
trade, because no known environment is near the R58 ceiling. Open question 6 is
where that gets confirmed before release.

### 4.10 Errors

- **R62.** No shopper input, including punctuation, quotes, boolean operators
  such as `&`, `|`, and `!`, and SQL fragments, produces a server error. Such
  input is treated as ordinary search text and yields either matches or no
  matches.
- **R63.** When the search cannot complete because the database is unreachable
  or the query times out, the shopper sees the application's standard error
  page rather than a stack trace, and the message does not name database
  objects.

## 5. Edge cases and failure modes

**Empty and whitespace search.** Covered by R2. A search box holding only
spaces behaves the same as an empty one, so a stray space does not blank the
catalogue.

**Search text that breaks the query parser.** Postgres text search syntax
treats `&`, `|`, `!`, `:`, `*`, and quotes as operators. A shopper typing
`C++ & me` or `"` must get a result page rather than a server error. R62 covers
this.

**Search that matches nothing.** R28 gives the shopper a message and a way back
to the full catalogue.

**Products with no author.** Products added after this ships start with no
author until an admin fills one in, and the backfill in R33 covers only the 15
seeded codes. Such products stay visible in the unfiltered catalogue and stay
findable by title, and an author search does not return them. R30 covers this.

**An author already set before the upgrade.** If an environment has products
whose author was entered by hand, the backfill leaves them alone under R34, so
the upgrade does not overwrite an admin's data with the seed value.

**Accented author names.** `Antoine de Saint-Exupery` is stored without
accents under R33 so it is findable by typing `exupery`. An admin who types an
accented name into the admin form gets a product that is only findable by the
accented spelling. Open question 2 decides whether to fix this generally.

**Both price bounds equal.** A minimum and maximum of 32.0 returns books priced
exactly 32.0, because both bounds are inclusive under R12.

**Price bounds outside the numeric range.** A value with more precision or
magnitude than the `price` column holds is rejected under R13 as a value that
is not a usable price, rather than reaching the database and failing there.

**Ties in the sort key.** Several seeded books share a price of 44.50 and
several share 14.50. Without the tiebreaker in R20, page 1 and page 2 can
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
pages. This is accepted for a catalogue of this size, and no snapshot or cursor
paging is introduced.

**Admin writes during the migration.** R57 states the outcome. Admin edits and
storefront reads issued while the migration runs wait for the lock and then
proceed. R58 and R59 set and test the table size at which that wait stays
acceptable.

**An environment above the row ceiling.** If `catalog.products` holds more than
100,000 rows in some environment, the release is held for that environment
under R58 and R60, and open question 6 decides what to do about it. Applying
the release anyway would lock the storefront's product table for an unmeasured
period.

**Migration fails partway.** R56 states the outcome. The deployment fails
loudly and the previous version keeps serving, so shoppers see the old products
page rather than an error.

**Deployment where the index is present but the application is old.** The added
columns are nullable additions and the previous application version does not
reference them, so an older instance running against the migrated database
continues to work during a rolling deployment. The author backfill is also
invisible to the older version.

**Search issued as an htmx partial request.** The products page swaps its grid
through htmx. A partial request that loses the search criteria would silently
reset the shopper to the full catalogue, so R24, R25, and R29 need a test at
the partial level and not only at the full-page level.

**The index stops being used after a later change.** A future change to the
query, the column, or the index could quietly turn search back into a
sequential scan while all functional tests still pass. R8 is the test that
catches this, which is why it asserts on the plan rather than on the results.

## 6. Open questions

1. **Author on the storefront.** Decide whether the product card and product
   detail page show the author, or whether the author is only a search input
   for now. This spec requires the author to be searchable, admin-editable, and
   backfilled for the seeded books, and does not require it to be displayed.
2. **Accent-insensitive matching.** Decide whether searching `garcia` should
   match `García`. This needs the `unaccent` extension installed in every
   environment including production, which is a database administration
   decision outside the catalog module. R33 sidesteps the question for the
   seed data by storing unaccented author names.
3. **Page size.** Decide whether search results keep the existing page size of
   10 or whether the shopper can choose. This spec keeps 10.
4. **Admin list parity.** Decide whether admins get the same search on
   `/admin/products` in a follow-up item. This spec excludes it.
5. **Tenant scoping for the catalog.** Decide whether `catalog.products` is
   intentionally a single global catalogue, or whether the missing
   `workspace_id` column is a gap to close in a separate item. Section 4.7
   assumes the catalog stays as it is and requires search to inherit whatever
   scoping the listing applies. Confirming which of the two is intended before
   this ships avoids a second query path later.
6. **Whether any environment exceeds the 100,000-row ceiling.** Before the
   release goes out, whoever owns production data runs the count in R60 for
   every environment and decides one of two things: confirm every environment
   is under the ceiling and apply the release as specified, or commission the
   low-lock migration path described at the end of section 4.9 as a separate
   item. This is the only decision that blocks the release.
7. **Search term telemetry.** Decide whether searches that return no results
   are worth counting so the team can see what shoppers look for and cannot
   find. R47 records no search activity today.

## Appendix A: changes from the previous round

- **Guest access contradiction.** The spec now commits to the reading that
  search stays available to unauthenticated visitors, and says why at the top
  of section 4.6. The old open question 7 about role vocabulary is removed,
  and R37 to R41 are firm rather than provisional.
- **Author search goal.** This item now backfills the authors of all 15 seeded
  books, so the goal is demonstrable at launch. R33 lists the exact values, R34
  states that an existing author is never overwritten, and R35 requires a test
  that proves author search works after the migration. The old open question 1
  about the backfill is removed because the decision is made here.
- **Migration locking.** The old edge-case note is replaced by requirements
  R57 to R61: the lock and its effect on concurrent traffic, an accepted
  ceiling of 100,000 rows, an automated test that runs the migration against
  100,000 rows within a time budget, a release-notes check the deployer runs,
  and an explicit statement that the migration stays inside Flyway's
  transaction. Section 4.9 also explains why the lower-lock alternatives are
  incompatible with that transaction. Open question 6 is the decision that
  covers a larger environment.
- **Index usage as a test.** The manual `EXPLAIN` check is gone. R8 now
  requires an automated test that seeds enough rows for the planner to have a
  real choice, asserts on the query plan, and forbids `enable_seqscan = off`
  so the assertion cannot pass on a plan the application would never receive.
