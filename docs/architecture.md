# Architecture

One application and one event team. Business rules are plain Python functions, independent of web requests and persistence.

![Application architecture](architecture.svg)

```mermaid
flowchart TD
    Browser["Browser: forms and reports"] --> Auth["Django sessions + CSRF"]
    Auth --> Access["Role and package authorization"]
    Access --> Services["Application services + transactions"]
    Services --> Engine["Deterministic checking engine"]
    Services --> DB[("SQLite local / PostgreSQL deployment")]
    Services --> Files["Private original files"]
    Files --> Download["Authorized attachment download"]
    Download --> Browser
```

The production network is HTTPS → Caddy → Nginx → Gunicorn/Django. Caddy manages TLS. Nginx caps request bodies and limits login requests. Only Caddy publishes host ports. Neither proxy serves private files. WhiteNoise serves collected CSS only.

```mermaid
erDiagram
    PARTNER ||--o{ REQUIREMENT : defines
    REQUIREMENT ||--o{ REQUIREMENT_REVISION : retains
    PARTNER ||--o{ PACKAGE : receives
    USER ||--o{ PACKAGE : owns
    PACKAGE ||--o{ ASSET : contains
    PACKAGE ||--o{ CHECK_RUN : checks
    PACKAGE ||--o{ MANUAL_REVIEW : receives
    REQUIREMENT ||--o{ MANUAL_REVIEW : qualifies
    USER ||--o{ AUDIT_EVENT : performs
```

Requirements and packages both carry a submission stage. A pre-event package uses only that partner's pre-event instructions. Each current asset occupies one unique `(package, slot)` pair. Requirement revisions are unique by `(requirement, number)`. Foreign-key protection prevents accidentally removing referenced partners, requirements or users through the ORM.

The current report is a retained check run keyed by a SHA-256 fingerprint of engine version, current requirement snapshots and validated asset metadata/content digests/availability. Requirements include approval state, source, revision and deadline. Replacing an asset includes its new record ID, conservatively invalidating even a same-content replacement. Manual reviews reference this exact fingerprint; old decisions stay in history but do not apply after inputs change.

Writes create the change and its audit event in the same database transaction. Package operations lock the package row in PostgreSQL. New file writes are cleaned up if their database transaction fails; replaced/removed files are deleted after commit. A process crash between storage and database operations can still leave orphaned files; reconciliation is a deployment follow-up.

No task queue, separate API server, frontend framework, tenant layer or external service is needed in v1. Reports run synchronously because each package has at most four bounded files and uses pre-extracted metadata. A queue becomes useful only if measured workload justifies it.
