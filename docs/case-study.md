# Case study: tracking media-partner obligations for a student tech expo

## The problem

A student computer-science expo signed media partnerships with several publications.
Each agreement listed obligations in both directions: the expo team had to credit
partners in publicity, screen their videos and report follower growth; partners had to
publish press releases and promote announcements. The team tracked this in one
spreadsheet per partner, where a "Done" cell and an occasional link were the only
record. Nobody could say with confidence which obligations were actually proven, or
whether a deliverable that passed review last week still matched what was published.

## Constraints

- A small student team, so the tool had to be simple to run and cheap to host.
- Real partner material, so files and evidence had to stay private per team.
- Some checks are objective (word counts, image sizes) and many are not (logo
  placement, "promote one announcement"), so the tool could not pretend to automate
  judgement.

## Approach

1. **Model obligations, not files.** A requirement records partner, stage
   (pre-event, event-day, post-event, or across all stages), responsible party,
   whether it is required, optional or conditional, and the source it came from.
2. **Automate only what is deterministic.** A pure rules engine handles word bounds,
   phrases, exact image dimensions and required files. Anything else becomes a
   coordinator review with a mandatory explanation.
3. **Make evidence first-class.** Off-site work is proven by submitting a link and an
   explanation, kept in append-only history, then reviewed.
4. **Never let a decision go stale silently.** Reports and reviews are keyed by
   fingerprints of the exact inputs they covered.
5. **Show coverage honestly.** A coverage page lists every recorded obligation and keeps
   anything unproven unresolved, instead of reporting "100% done".

## What changed after real use

- **Reviews reset too eagerly.** The first design bound every review to a fingerprint
  of the whole package. It was safe, but once a package held a dozen evidence
  obligations, submitting evidence for one reset every other decision. Reviews are now
  bound to a per-requirement key that covers only the input they inspected. The fix
  came with regression tests and kept older reviews valid.
- **Stages needed confirming.** Transcribing real tracker rows showed many obligations
  without a clear stage. Rather than guess, the app stores them as "stage not
  confirmed" and refuses to approve them until a coordinator decides.
- **Source data was messier than expected.** Cross-checking tracker links against the
  actual posts found links that pointed to another partner's image and dates that did
  not match the stated stage. The evidence notes record these limits instead of hiding
  them.
- **Releases needed a gate.** Production releases are built with production settings
  without the public domain, smoke-tested, and only then promoted. One lesson: merging
  two stacked pull requests deployed the intermediate commit for about 20 seconds.
  Nothing was written in that window, and the takeaway is to merge stacked branches
  in a single step when the production branch auto-deploys.

## Results

The app runs in production for the expo team. The team's real obligations for three
media partners are recorded with their sources, and submitted evidence is awaiting
coordinator review. No claims are made about time saved; the honest outcome is that
the team can now see which obligations are proven, which are pending, and why.

## What I would do next

- Event-stage templates so recurring obligations don't have to be re-entered.
- Optional automatic checks of public links (availability, publication date), clearly
  labelled as hints rather than proof.
- Malware scanning for uploads before opening the tool to more teams.
