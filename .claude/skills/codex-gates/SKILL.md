---
name: codex-gates
description: Use when a spec, plan, risky branch, result set or dashboard screenshot needs an independent Codex review. Covers which model to use (Sol or Astra), the commands, the prompt shape, and how to record dispositions.
---

# Codex gates

**Codex budget (owner, 2026-10-27, ~02:30 MT): at most 3 runs, pre-approved.** Each one spends the owner's limited credits.
1. **Spec soundness gate:** Astra on the `astrahigh` profile, once, after 03:14 MT.
2. **Code review of the leakage-sensitive forecast and simulator code:** Sol, Tue afternoon. Run it only if the Claude reviewer flags something it can't settle.
3. **Results audit before the 13:00 freeze:** Astra on the `astrahigh` profile, Wed morning.

Any other Codex run needs the owner's yes first. That covers re-checks, image critiques and `codex exec`. Without a yes, use a fresh-context Claude reviewer and record the substitution.

## Who

- **Sol 6.1** (the `review` profile) is the default reviewer, once the owner says yes. It is used for:
  - checking the implementation plan;
  - reviewing leakage- and metric-sensitive branches;
  - critiquing screenshots.
- **Astra** (the `astra` profile, always a fresh session) is used twice in this hackathon:
  - the spec soundness gate;
  - the results audit before the Wed 11 AM freeze.

  It is not used for iteration rounds.
- **The owner's interactive Codex session** works in `../26_hard_tech_week_hackathon-codex` on branch `codex/planning`. It is the planning partner: it writes its own version of the spec, reviews evidence, and drafts the narrative. Exchange with it through `docs/HANDOFF.md` and its pushed branch, never by editing its checkout.

## Review commands

Run these from the repo root. The branch under review must be pushed first.

| Purpose | Command |
|---|---|
| New review | `scripts/review.sh start <name> <branch> <prompt-file> [review\|astra] [--fresh]` |
| Re-check in the same session | `scripts/review.sh again <name> <prompt-file> [--branch <branch>]` |
| Review a branch's diff | `scripts/review.sh code <name> <branch> [base] [--prompt <file>]` |
| Ledger | `scripts/review.sh status` |

- Names use lower-case letters, digits and hyphens, for example `spec-astra`, `plan-sol`, `router-code`.
- The wrapper adds the read-only prefix, the pinned commit and the review contract (every finding with severity and confidence, then a verdict line). Prompts add only the task.
- Exit 0 means the review is valid, whatever it found. Any other exit is a failed run; the wrapper's header lists the codes.

## Image critique (not a branch review)

```
codex exec -p review --ephemeral --skip-git-repo-check -C <scratch dir> --image a.png,b.png --color never -o <out.md> "<role and rules>" < rubric.md
```

- Put another flag right after `--image`, because it is greedy.
- Run it in a scratch directory, never in a checkout with uncommitted work.

## Prompts

- Save them as `docs/reviews/prompts/<date>-<name>-r<n>.md`.
- Name the files to read and the lenses to answer.
- Ask for every finding, with severity and confidence. Never "only important issues".

## After a review

1. Save the output as `docs/reviews/<date>-<name>-r<n>-<model>.md`.
2. Verify each finding against the code or the data before acting; reviewers can be wrong.
3. Add a disposition table under it. Each finding is fixed (with the commit), rejected (with the reason) or deferred.
4. Re-check until no critical or major finding is open. That usually takes 2–3 rounds.
5. A gate passes only on `ready` or `ready_with_minor_fixes` with every finding dispositioned. Exit 0 means the review ran, not that it passed. Record the reviewed SHA, and re-review fixes on the final candidate.
