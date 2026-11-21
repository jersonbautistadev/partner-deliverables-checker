# Demo walkthrough

A ten-minute tour using the fictional seeded data. Run the app locally and seed it
first (see the [README](../README.md#run-it-locally)). Never seed known demo
credentials into a real deployment; `seed_demo` refuses to run outside debug mode.

1. **Worklist.** Sign in as `demo_coordinator`. The dashboard splits packages into
   "needs attention" and "resolved", with deadlines in Asia/Manila. Summaries are
   dated snapshots; opening a report re-checks current inputs.
2. **A failing report.** Open *Launch press kit*. The square image fails because it is
   1000 × 1000 px, not the required 1080 × 1080. Follow the finding to its requirement
   and revision history to show which approved instruction it enforces.
3. **Evidence review.** In the same report, *Publish the partner announcement* has
   submitted evidence from `demo_alex`. Record a pass with a note. Then, as
   `demo_alex`, update the evidence: only that obligation returns to "needs review".
4. **Stale decisions.** As the coordinator, record a pass for *Partner logo placement*,
   then upload a replacement image: that review no longer applies, while the evidence
   review from step 3 remains.
5. **Coverage.** Open *Obligation coverage*. The across-stage acknowledgement stays
   unresolved because the event-day and post-event packages don't exist yet; the
   conditional video obligation needs an explained decision rather than disappearing.
6. **Isolation.** Sign in as `demo_sam` (contributor) and try opening another
   contributor's package by URL or through `/api/v1/packages/<id>/report/`: both
   return 404. A coordinator of one workspace has no access to another.
7. **Ambiguity is never a pass.** *Post-event reach report format* is marked
   ambiguous; it cannot be approved or reviewed until clarified.
8. **Operations.** Show the CI run (SQLite and PostgreSQL suites) and explain why a
   database-only backup cannot restore private original files.
