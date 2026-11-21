# Security scope and remaining boundaries

The public application isolates independent team workspaces. Coordinators are privileged only within their own memberships; contributors additionally need package ownership. All application queries, form choices, APIs, revision access, audit lists, deadline summaries and downloads enforce that scope. Removing membership blocks an existing session on the next request. Existing global Django groups do not grant access.

Implemented controls include email verification before workspace access, POST confirmation of expiring single-use invitations/verification, Django password recovery/change, CSRF, template autoescaping, safe login redirects, private files, bounded upload parsing, storage/count quotas, shared database throttles and row locks for concurrent quota/coordinator changes. Signup and recovery acknowledgements are generic. Password and SMTP/token-bearing content is not intentionally logged by application request handlers; proxy/function-provider logs need separate access/retention controls.

Original downloads remain untrusted. Validation is not antivirus, content disarm, OCR, or a promise that DOCX content will render identically in Office. Only supported body text/tables are extracted. Originals are never embedded as application-origin HTML. S3 attachment URLs are temporary bearer credentials; anyone receiving a valid URL can use it for up to 60 seconds. Keep the bucket private, block public listing/access, restrict credentials to the necessary prefix, and test actual provider permissions before launch.

Production must use DEBUG=0, HTTPS, private secrets, exact allowed hosts, trusted CSRF origins, secure cookies and a production server. Vercel refuses a production configuration that silently uses local SQLite/files. Remote PostgreSQL needs TLS. Compose trusts forwarded client-IP headers only because its app/edge ports are private and Caddy/Nginx overwrite them; do not copy that trust setting onto an exposed application server. Vercel uses its platform-supplied forwarded client-IP header. Test throttles through the actual public boundary.

Quotas guard normal authenticated usage and race conditions, not volumetric denial of service. SMTP/provider quotas, account-creation abuse, storage growth, report generation cost, and expected concurrency must be exercised on staging. Rate windows are bounded and pseudonymous counters are pruned by maintenance. No claim of constant-time identity handling or security certification is made.

Retained history is not a tamper-evident ledger. Database administrators and privileged maintenance tools can modify records. Deactivation disables sign-in and removes memberships but retains the account/email, package ownership, snapshots, reviews and audit records. Removing/replacing originals does not retain their previous bytes. Publish the applicable retention and support/contact policy before accepting real documents; the operator must handle identity/deletion requests consistently with that policy. `maintain_data` deletes expired security records after seven days and only deletes old audit events when an explicit retention period of at least 30 days is supplied. Original/revision deletion is not automatic.

The [staging record](records/staging-verification-2026-11-17.md) contains executed hosted
account/file isolation, SMTP, off-site recovery and alert-receipt evidence.
Production-specific verification remains separate in the
[rollout record](records/production-rollout-2026-11-18.md). A short-lived URL, file
validator, local test or settings check does not prove a complete deployment.

Optional service-wide workspace and daily SMTP-attempt caps bound a small pilot.
Their database locks/budgets have PostgreSQL concurrency tests. Email quota
exhaustion retains messages and triggers readiness/visible delay states; it does
not imply a delivery deadline or prevent a provider rejecting mail earlier.
Provider and personal-mail usage also consume the same Gmail account's allowance.
An initial five-workspace cap at 100 MiB per workspace bounds referenced originals
to 500 MiB; orphan files, restore copies, database growth and transfer still need
separate monitoring. Keep restore targets off production's storage budget.

Primary references: [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/), [Django authentication](https://docs.djangoproject.com/en/5.2/topics/auth/default/), [Vercel Django deployment](https://vercel.com/docs/frameworks/full-stack/django), [Vercel function limits](https://vercel.com/docs/functions/limitations).

## Browser and sign-in protections

Every response carries a strict Content-Security-Policy (`script-src 'none'`, no
plugins, same-origin styles, fonts, images and form targets, no framing or `<base>`)
and a Permissions-Policy that disables camera, microphone, geolocation, payment and
USB. The templates contain no scripts, inline styles or event handlers; keep it that
way or the policy will block them.

Failed sign-ins are limited per username and source IP (5 per 15 minutes), so
failures from one network cannot lock the account for everyone, and per username
across all sources (`ACCOUNT_RATE_LIMIT`, default 50 per 15 minutes) to stop
distributed guessing. Per-IP request limits apply as before.

