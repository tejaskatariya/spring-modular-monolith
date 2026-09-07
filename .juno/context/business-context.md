# Business context

This file describes what the application is for, who uses it, and the rules that hold across the domain. It is loaded into every agent session. Coding conventions, build tooling and formatting rules live in the engineering principles file rather than here.

## 1. What the product is

An online bookstore. Shoppers browse a catalogue of books, place an order, and receive a confirmation. Behind that, stock is adjusted and other systems are told that an order happened.

It is a single deployable Spring Boot application built as a modular monolith with Spring Modulith. One application, one database, several modules that own separate schemas and communicate through published APIs and events. The reason for the structure is that a module should be able to move out into its own service later without the rest of the application being rewritten around it. Every design decision should keep that possible.

## 2. Who uses it

- **Shopper.** Anonymous visitor browsing the catalogue. Can see products and prices.
- **Customer.** A shopper who places an order. Owns their own orders and can only see their own.
- **Administrator.** Manages products, stock and orders. Not present in the application yet.
- **External systems.** Consume order events from RabbitMQ. They are outside the application and cannot be changed by work done here, so any published event is a contract with them.

## 3. The domain

The nouns that matter, and who owns each one.

- **Product.** A book that can be sold. Owned by catalog. Carries title, author, price and description.
- **Order.** A customer's purchase, made up of one or more lines, each naming a product and a quantity. Owned by orders.
- **Stock.** How many units of a product are available. Owned by inventory.
- **Notification.** A message sent to a customer about something that happened to their order. Owned by notifications.

Use the class and field names already present in the codebase rather than inventing synonyms. If a concept exists under a different name in code, the name in code wins.

## 4. Modules

| Module | Owns | Schema | Publishes | Consumes |
|---|---|---|---|---|
| `common` | Shared types used everywhere. Declared OPEN, so all its types are exposed on purpose. | none | none | none |
| `catalog` | Products and their presentation. | `catalog` | none today | none today |
| `orders` | Order placement and the order record. | `orders` | `OrderCreatedEvent` | none today |
| `inventory` | Stock levels per product. | `inventory` | none today | `OrderCreatedEvent` |
| `notifications` | Outbound messages to customers. | `notifications` | none today | `OrderCreatedEvent` |

Each module owns its schema and nothing else reads or writes it. A module reaches another module's data through that module's published API or by reacting to an event it publishes. Cross-schema joins and repositories that read another module's tables are not allowed.

`OrderCreatedEvent` is externalised to RabbitMQ, so it is visible outside the application as well as inside it.

## 5. How modules talk to each other

Two mechanisms, chosen by what the calling module needs.

Use a **synchronous call to the other module's published API** when the caller cannot proceed without the answer. Orders validating that a product exists and getting its price is this case, because an order cannot be priced without it.

Use an **event** when the other module needs to know that something happened but the caller does not need anything back. Stock adjustment and sending a confirmation email are this case, because the order is already valid whether or not those succeed immediately.

Two rules follow from that:

- A module that publishes an event does not know or care who listens. Adding a new listener is never a change to the publishing module.
- If two modules would need to call each other synchronously, at least one direction becomes an event. Spring Modulith rejects cycles, and a cycle usually means the two modules are one module split in two.

Event handlers must tolerate being run more than once for the same event. The event publication registry can redeliver, and stock returning twice or a customer receiving two identical emails are both real defects.

## 6. The flow that exists today

1. A shopper browses the catalogue and places an order.
2. Orders asks catalog to confirm the products and prices on the order lines.
3. Orders saves the order and publishes `OrderCreatedEvent`.
4. Inventory receives the event and adjusts stock for each line.
5. Notifications receives the event and sends the customer a confirmation email.
6. The same event goes out to RabbitMQ for anything outside the application.

Nothing happens to an order after that. It has no further lifecycle, no payment, no dispatch and no cancellation.

## 7. Rules that must keep holding

These are the things a change should never quietly break.

- An order is only created from products that exist, at the price the catalogue holds at that moment.
- Stock never goes negative, and the same order never reduces stock twice.
- A customer sees only their own orders.
- A customer receives one message for each thing that happened, however many times the underlying event is delivered.
- Prices and totals recorded on an order do not change afterwards when the catalogue price changes.
- Every module keeps to its own schema.
- An event that has been published outside the application is a contract. Fields can be added to it. Removing or renaming a field, or changing what one means, breaks consumers that cannot be seen from this repository.

## 8. Where the product is going

Work planned on top of the current application, so that specs written today anticipate it rather than blocking it:

- **Customer identity.** A customers module owning registration, sign-in, profile and addresses. Orders will reference a customer by identifier and read addresses through the customers API.
- **Order lifecycle.** Orders will move through NEW, PAID, SHIPPED, DELIVERED and CANCELLED, with transitions validated in one place.
- **Payments.** A payments module that settles an order and reports back by event.
- **Shipping.** A shipping module that dispatches a paid order and reports shipment and delivery by event.
- **Returns and refunds.** Coordinated across returns, orders, inventory and payments.
- **Reviews, promotions, wishlist.** Further modules attached to catalog and orders through published APIs.
- **Reporting.** A read model built entirely from events, so it can be rebuilt from history and needs no change to the modules it reports on.
- **Administration.** Product, stock and order management behind an ADMIN role.
- **A public JSON API** alongside the server-rendered pages.
- **Extraction of notifications** into its own service consuming the externalised events.

When new behaviour is added, decide where it lives this way. A new noun with its own lifecycle and its own storage becomes a new module with its own schema. An extension of a noun that already exists belongs in the module that owns it. Something that only reads across several modules to present a combined view belongs in reporting, built from events.

## 9. Out of scope

State these as assumptions rather than building them unless a specific piece of work asks for them.

- Real payment provider integration. Payments are simulated.
- Real email or SMS delivery. Notifications are recorded and logged.
- Multiple tenants, multiple stores or multiple currencies.
- Search relevance tuning beyond what Postgres full-text search gives directly.
- Recommendation models. Related products come from recorded purchase history.

## 10. Vocabulary

Use these words consistently in code, in specs and in user-facing text.

- **Product** for something that can be bought. Avoid item, book and SKU as synonyms.
- **Order line**, for one product and quantity within an order.
- **Stock**, for the quantity available. **Reservation** is stock held for an order that has not completed.
- **Customer**, for a person with an account. **Shopper** is an anonymous visitor.
- **Notification**, for any outbound message, whatever the channel.
- **Event** always means an application module event published through Spring Modulith. Anything else is a message or a callback.