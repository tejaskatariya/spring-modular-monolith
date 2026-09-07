# Engineering principles

Technical rules for working in this repository. The domain, the module responsibilities and the business rules live in the business context file. This file covers how code is written, built and verified.

## 1. Toolchain

- Java 25. The repository ships an `.sdkmanrc`, so `sdk env install` selects the right JDK.
- Spring Boot 4.1 and Spring Modulith 2.1.
- Postgres 18, RabbitMQ 4.3 and the `grafana/otel-lgtm` image, all started by `compose.yml`.
- Docker must be running for anything beyond a compile, because the tests use Testcontainers.

Spring Boot 4 renamed several starters. Read the existing build file and copy the artifact ids from there before adding a dependency. In particular the web starter is `spring-boot-starter-webmvc`, and the Boot 3 name will not resolve. Do not guess a starter name from memory.

## 2. One build tool

Gradle is authoritative. Both `pom.xml` and `build.gradle` exist in the repository, and the pipeline runs Gradle. A dependency added only to the Maven file will not reach the build.

Change this line if you switch, but keep exactly one build file authoritative.

## 3. What done means

A change is finished when all four of these pass:

```
./gradlew build          # compiles and runs the full test suite
./gradlew spotlessCheck  # formatting
./gradlew test --tests '*ModularityTest*'   # module boundaries
```

The `Taskfile.yml` wraps the common ones, so `task test` and `task format` also work.

Run the full suite before opening a pull request. Do not report a change as complete on the basis of a compile.

## 4. Module structure

Each module is a direct subpackage of the application root package. Everything inside a module is internal to it unless it is deliberately exposed.

- Types other modules may use live in the module's top-level package or in a package marked as a named interface. Everything else goes in a subpackage, which Spring Modulith treats as internal.
- A module declares what it is allowed to depend on with `@ApplicationModule(allowedDependencies = ...)` in its `package-info.java`. Add a dependency there deliberately rather than discovering it when the modularity test fails.
- `common` is declared OPEN and its types are available everywhere. Do not add business logic to it. It holds shared value types and utilities.
- Never read or write another module's tables. Use that module's published API, or react to an event it publishes.
- Do not add a synchronous call in both directions between two modules. Spring Modulith rejects the cycle, and one direction should be an event.

When adding a module, the checklist is: package with `package-info.java` carrying the module declaration and the null-marking annotation, its own database schema, a Flyway migration creating that schema, a published API type for anything other modules need, and a module test.

## 5. Null-marking

ErrorProne runs with NullAway in JSpecify mode, and `RequireExplicitNullMarking` is set to error. Every package needs a `package-info.java` carrying `@NullMarked`, or the build fails.

This is the single most common cause of a first build failure on a new package. Add the file at the same time as the package, before writing any class in it.

Inside a null-marked package, a reference type is non-null by default. Mark a nullable field, parameter or return with `@Nullable` from JSpecify. Do not suppress the check.

## 6. Persistence and migrations

- JPA entities, with each module's entities in its own schema.
- Every schema change is a Flyway migration. Follow the numbering and naming already used in `src/main/resources/db/migration` and never edit a migration that has been merged.
- A migration must run against a database that already holds data. Adding a non-null column needs a default or a backfill step. Renaming or moving data needs the write and the drop in separate migrations so they can be reviewed and rolled forward independently.
- Creating a new module means a migration that creates its schema before any table in it.
- Do not rely on Hibernate schema generation for anything.

## 7. Events

- Publish application module events through Spring's event publisher. The Modulith event publication registry persists them, so a listener that fails will be retried.
- A listener must tolerate being called more than once with the same event. Make the effect idempotent, either by checking whether it has already been applied or by keying the effect on the event identifier.
- Events carry identifiers and the values the consumer needs. They do not carry entities.
- An externalised event is a contract with systems outside this repository. Adding a field is safe. Removing a field, renaming one, or changing what one means is a breaking change and needs to be raised rather than done quietly.
- Do not publish an event from inside a listener for the sole purpose of getting a return value back. That is a synchronous call written the long way round.

## 8. Web layer

- Server-rendered pages with Thymeleaf, with HTMX for partial updates. Bootstrap and the BootUI starter supply the styling.
- Controllers live in the module that owns the data they present. Do not collect controllers into a shared web package.
- An HTMX request returns a fragment. A full page request returns the whole page. Keep both paths working for any page that has a fragment.
- Validate request input with Bean Validation annotations and handle the failure in the controller.
- Never render a value straight from user input without escaping.

## 9. Configuration

- New settings go in `application.properties` or the profile-specific file, with a typed `@ConfigurationProperties` class in the owning module.
- Anything that differs between local and container runs is an environment variable read under the `docker` profile, following the pattern already in `compose.yml`.
- No secrets in the repository.

## 10. Testing

- Integration tests use Testcontainers for Postgres and RabbitMQ. Reuse the existing base test class or container configuration rather than starting containers per test class.
- Use `@ApplicationModuleTest` to test a module in isolation, including its event interactions with the modules it depends on.
- Every new module or boundary change must keep the modularity verification test passing.
- Cover the negative cases as well as the happy path. For anything that reads customer-owned data, include a test proving another customer cannot read it. For anything driven by an event, include a test proving a redelivered event does not apply the effect twice.
- Test behaviour through the module's public surface. Do not reach into a module's internal packages to set up a test more quickly.

## 11. Observability

- The application exports traces, logs and metrics over OTLP, and Spring Modulith contributes module-level observability.
- Actuator is on, with a Prometheus registry.
- Do not add a logging framework or a metrics facade. Use what is configured.
- Log at info for things an operator would want to see, and at debug for the rest. Do not log request bodies or customer contact details.

## 12. Formatting and static analysis

- Spotless with palantir-java-format decides formatting. Run `./gradlew spotlessApply` before committing and take its output as it is. Do not hand-adjust whitespace and do not add a formatter suppression.
- ErrorProne findings are errors. Fix them rather than suppressing them.
- OpenRewrite recipes for the Spring Boot 4 upgrade and Testcontainers are configured. Do not run them as part of a feature change, because the diff becomes unreviewable.

## 13. Pull requests

- One feature per branch, branched from `main`.
- Conventional Commits for commit messages.
- The pull request describes what changed and why, and names any new event or any change to an existing one.
- Do not commit generated files, IDE settings or local configuration.
- Do not bump the version or edit unrelated files.

## 14. Mistakes that break this build

Check these before reporting a change as complete.

- A new package with no `package-info.java` carrying `@NullMarked`.
- A Boot 3 starter name that does not resolve on Boot 4.1.
- A dependency added to `pom.xml` while the build runs Gradle.
- A migration that works on an empty database and fails on one with rows in it.
- A direct call or a cross-schema query between two modules instead of a published API or an event.
- A new module whose tables land in the default schema.
- Hand-formatted code that fails the Spotless check.
- An event listener that applies its effect twice on redelivery.
- A test suite run without Docker available, which fails for reasons unrelated to the change.