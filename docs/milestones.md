# Release milestones

| Milestone | Exit evidence | Current scope |
| --- | --- | --- |
| Deterministic checks | Engine boundary tests | Included in full local suite |
| Workspace/account foundation | Tenant isolation, verification, invitations, recovery and membership tests | Implemented and exercised locally |
| Concurrent writes | PostgreSQL quota and last-coordinator races | Exercised on PostgreSQL 17.12 |
| Existing data upgrade | Temporary schema-0001 migration rehearsal | Executed; IDs, paths and history retained |
| Recovery | Encrypted paired restore and role/download checks | Executed for SQLite and PostgreSQL with local originals |
| UI | Real account/workspace browser exercise at phone/tablet/desktop widths | Executed using local mailbox and fictional data |
| Hosted staging | Vercel project + remote database/bucket/SMTP/scheduler | Not connected or deployed |
| Public launch | Hosted acceptance exercise, off-site restore, monitoring, capacity and explicit approval | Blocked on external setup and rehearsal |

See `release-readiness.md` for current evidence and `deployment.md` for the release gate. Do not equate local tests, a workflow file or configuration with a green hosted deployment.
