# Explain the decisions in an interview

## Why Django and server-rendered pages?

The project needs secure accounts, forms, persistent records and private files. Django supplies established building blocks. A separate React app would add a build pipeline, API authentication choices and duplicated validation without improving this first workflow. The JSON report endpoint still demonstrates a clear HTTP boundary.

## Why separate rules from the web app?

`engine.evaluate(rule, asset)` accepts plain dictionaries and returns a finding. It does not read the database or inspect a request. That makes boundary tests fast and lets me explain one rule without tracing the entire website. `inspect_upload` produces validated metadata; services connect this engine to files, reports and transactions.

Read the code in this order: `engine.word_count`, `engine.validate_rule`, `engine.evaluate`, one test in `tests/test_engine.py`, `models.Requirement`, `services.ensure_report`, then `views.asset_upload` and `permissions.visible_packages`.

## Why source references and snapshots?

A failed check should explain the approved instruction it enforces. Revisions retain the old configuration, source, deadline, approval state, author and change reason. This lets a coordinator explain why a package that passed yesterday needs work today. Sources are manually reviewed references, not claims that the app verified an external document.

## Why fingerprints instead of a “checked” boolean?

A boolean cannot say which file or requirement was checked. The fingerprint captures all relevant inputs and the engine version. If any input changes, the old report cannot be reused. Manual reviews are tied to the same fingerprint, preventing an old logo-placement decision from approving a replacement poster.

This is conservative: changing a source label or deadline also invalidates reviews. At this team's scale, re-review is preferable to silently reusing a potentially stale decision. Later evidence could justify a narrower per-rule dependency fingerprint.

## Why do authorization checks filter the database query?

`visible_packages` returns all packages to coordinators and only owned packages to contributors. The same filter protects detail pages, JSON, upload, remove and download routes. Hiding a button would not prevent a direct HTTP request. A 404 for inaccessible package IDs also avoids revealing whether another contributor's package exists.

## Why private attachments instead of public media URLs?

A public URL would bypass role checks and expose original documents. Files use random names outside static assets and are opened only after authorization. Attachment downloads and disabled content sniffing reduce risks from active/polyglot content. This does not prove that a document is safe to open in a desktop program.

## What is atomic, and what is not?

Database changes and audit events commit together. Package row locks coordinate writes in PostgreSQL. Filesystem storage is not part of a database transaction; new files are cleaned up on caught failures and old files are deleted after commit. A sudden process crash can still leave orphaned storage objects. Backups and reconciliation remain operational responsibilities.

## Why no background jobs yet?

Each package has four bounded slots. Checks operate on metadata extracted at upload, so synchronous refresh is straightforward. A task queue adds processes, retries and eventual-consistency UI states. I would add one after measuring slow uploads or report latency under a realistic workload.

## What can I honestly claim now?

The pure Python engine passed the recorded automated tests, and its demo report was generated from actual fictional files. The Django workflow, CI and deployment are not yet runtime-verified in this workspace. No time savings, real omissions caught or pilot adoption has been measured. Add those claims only after collecting evidence.

## Practice changes to make yourself

1. Add a phrase boundary test and explain why substring matching may accept a phrase embedded in a longer word.
2. Change a word bound from 500 to 499. Predict which tests or demo inputs change before running them.
3. Trace a contributor's forbidden download from route to query filter.
4. Show why a manual decision cannot be reused after an image replacement.
5. Explain why a database backup alone cannot restore private original files.
