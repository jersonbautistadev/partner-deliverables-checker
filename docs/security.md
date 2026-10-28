# Security scope and limits

Assets: team drafts, original files, approved publishing instructions, account sessions, review decisions and audit history. Main threats: unauthorized package access, malicious uploads, forged requests, stale approvals, accidental instruction changes and credential guessing.

| Threat | Implemented control | Verification / remaining work |
| --- | --- | --- |
| Contributor reads or changes another person's package | Shared server query filter on all package/file/report routes | Integration tests written; must run locally and in CI |
| Password/session mistakes | Django password hashing/validation and session login; no public signup | Runtime verification pending; production HTTPS required |
| Forged changes | CSRF middleware; POST-only write routes | Integration tests written |
| Script injection through drafts or sources | Autoescaped templates; originals never rendered inline | Escaping test written; browser QA pending |
| Oversized uploads / decompression | Streaming 5 MiB handler, 6 MiB proxy request limit, bounded DOCX expansion and image pixels | Engine boundaries verified; proxy/runtime limits not exercised here |
| Spoofed file extensions | Parse file content and require supported format/slot match | Engine tests pass |
| Archive/XML abuse | No extraction, no entity/DTD acceptance, bounded archive parts/expansion; external relationships rejected | Engine tests pass |
| Public file disclosure | Private directory, random filenames, authorization before attachment response, nosniff/no-store | HTTP tests written; deployment paths require inspection |
| Stale report / manual approval | Input fingerprint includes revisions, config, digests, approval and availability; stale review returns 409 | Engine fingerprint tests pass; full lifecycle tests written |
| Unexplained instruction changes | Retained snapshots with actor/reason; audit events in change transaction | Integration tests written |
| Login guessing | Nginx limit: 5 requests/minute/client IP, burst 5, behind Caddy's overwritten client-IP header | Deployment check pending; local runserver has no login throttling |

The application is for invited users in one trusted event team. It is not a hardened public file-upload service. Validation is not antivirus or content-disarm technology; authorized users must still treat original downloads as untrusted. Rejecting external DOCX links is intentionally strict; plain text is the fallback. No malware-free badge is shown.

The audit trail is application append-only because no UI/API edits or deletes it. Requirement snapshots additionally reject instance updates. It is not a tamper-evident ledger: a database administrator, database compromise, bulk ORM update or maintenance script can alter records. Backups and administrator access controls matter.

File replacement retains previous digests and check history, not previous original bytes. Keep approved final deliverables separately if the event requires long-term original-file retention. Changes to bytes made outside the application are outside the normal workflow; existence is checked, but stored digests are not rehashed on every report request.

More pilot constraints: one event team; no cross-organization isolation; four slots per package; no per-user storage quotas; no MFA or account recovery UI; no account-administration UI; no rate limiting on local development login; no object storage; no archival/retention automation; no load test. Coordinators cannot submit a package or verify that a partner received it. All these limitations should remain visible in the portfolio explanation.

Before any public pilot: run the full suite and production deployment checks, set private environment secrets, use the included HTTPS boundary, test both roles with direct URLs, verify upload/download headers, exercise backups/restores and choose a retention policy. Keep deployment limited to invited test users until these gates pass.

Primary references reviewed for the design:

- Django authentication: https://docs.djangoproject.com/en/5.2/topics/auth/default/
- Django upload security: https://docs.djangoproject.com/en/6.1/topics/security/#user-uploaded-content
- Django deployment checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- Pillow image API / decompression limits: https://pillow.readthedocs.io/en/stable/reference/Image.html

These references inform controls; they are not a security audit of this repository.
