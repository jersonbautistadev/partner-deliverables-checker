# HTTP contract

The website uses Django session cookies. All workspace routes require authentication and a team role. Mutations use standard form-encoded or multipart POST requests protected by CSRF. No tokens are stored in browser local storage.

## Versioned JSON reads

| Method and path | Result | Access |
| --- | --- | --- |
| `GET /api/v1/packages/` | `{ "packages": [{ "id", "title", "partner_id", "stage", "owner_id" }] }` | Coordinator: all. Contributor: own only. |
| `GET /api/v1/packages/{id}/report/` | Current run, fingerprint, engine version, checked timestamp and findings | Same package access filter |
| `GET /health/` | `{ "status": "ok" }` | Public liveness only; no database or private data |

Example shape (illustrative, not recorded pilot evidence):

```json
{
  "package_id": 1,
  "run_id": 4,
  "fingerprint": "<sha256>",
  "engine_version": "1.0.0",
  "checked_at": "<ISO-8601 timestamp>",
  "findings": [{
    "requirement_id": 7,
    "revision": 2,
    "title": "Square promotional image",
    "source": "Fictional brief §3",
    "kind": "dimensions",
    "slot": "image",
    "approved": true,
    "ambiguous": false,
    "status": "failed",
    "message": "Found 1000 × 1000 px. Required: 1080 × 1080 px (exact)."
  }]
}
```

The requirement detail is at `/requirements/{requirement_id}/`. A synthetic no-requirements finding has `requirement_id: null` and omits revision/source/slot/approval fields. Clients must handle that case. Findings do not contain extracted article text or private storage paths.

Unauthenticated JSON reads currently redirect to sign-in (`302`), matching the website. An authenticated nonmember gets `403`. An inaccessible or unknown package gets `404`, avoiding disclosure of another contributor's package. Methods other than GET get `405`. These are same-origin read APIs, not a public REST service.

## Browser writes

| POST path | Inputs | Permission and response |
| --- | --- | --- |
| `/partners/new/` | `name`, `notes` | Coordinator; redirect on success, form errors otherwise |
| `/requirements/new/` | Partner, stage, title, rule settings, source, approval, deadline, reason | Coordinator; saves revision 1 |
| `/requirements/{id}/edit/` | Settings, `version`, reason | Coordinator; stale version produces a form error; original partner/stage fixed |
| `/packages/new/` | Partner, stage, title, optional owner | Contributor owner is forced to self |
| `/packages/{id}/upload/` | `slot`, one `file` | Package access; validated before persistence; redirect with a success/error message |
| `/packages/{id}/assets/{asset_id}/remove/` | CSRF token | Package access; delete and refresh |
| `/packages/{id}/reviews/{requirement_id}/` | `fingerprint`, `decision` (`passed`/`failed`), `note` | Coordinator; stale/ineligible review `409`; invalid form `400` |
| `/accounts/logout/` | CSRF token | Signed-in user |

`GET /packages/{id}/assets/{asset_id}/download/` checks the same package access before opening storage, returns an attachment, and records a download event. Downloads and reports have `Cache-Control: private, no-store`.

No GET route changes submitted business content. A report read can populate its derived cache; a download adds an audit event. JSON mutation endpoints, pagination, OpenAPI and service-to-service authentication are deferred until there is a demonstrated client need.
