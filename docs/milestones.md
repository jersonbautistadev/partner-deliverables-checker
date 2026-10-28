# Small working increments

Aim for a demonstrable local workflow in about two weeks of focused part-time work, then polish before internship applications. These are estimates, not commitments or measured completion times. The December 14, 2026 internship start leaves room to validate the project first.

| Milestone | Target effort | Demonstration / exit gate | State here |
| --- | --- | --- | --- |
| 1. Rules and data foundation | 2–3 sessions | Explain a rule, its boundary tests, four outcomes and the source link | Engine running; Django models written |
| 2. Accounts and private packages | 2–3 sessions | Both roles can sign in; Sam cannot read Alex's report/file; uploads reject invalid content | Source and integration tests written; runtime pending |
| 3. Requirements and reports | 2–3 sessions | Edit an instruction, retain old snapshot, refresh report, invalidate old manual decision | Source and integration tests written; runtime pending |
| 4. Dashboard and demo polish | 1–2 sessions | Manila deadlines, orphan stages, responsive screens, five-minute walkthrough | UI source and capture script written; browser QA pending |
| 5. CI, deployment and honest pilot | 2–3 sessions | Green SQLite/PostgreSQL CI, clean deployment, measured team exercise | Workflow, runbook and pilot protocol written; not executed |

Do not add a frontend framework, AI extraction or another cloud service while a milestone's gate is still failing. Shipping the agreed workflow is stronger portfolio evidence than a larger unfinished feature list.

The next session should run the Django tests on your computer, resolve any failures, and get both roles through one real local workflow. Only after that should we call the web MVP working. Freeze dependencies after a successful clean install, then verify the lockfile in a fresh environment.
