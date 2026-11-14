# Turning a plan into a queue

For a written implementation plan (numbered tasks, usually with a spec) that is going to be built through the queue. Two runs on new applications are behind this: in each, the repository started empty and the first commit held only the spec and the plan.

## Why the repository has to be seeded

An empty repository has a default branch name and no branch. Three things then fail, none of them with a useful message:

- `git worktree add ... origin/main` has nothing to base a worktree on.
- A prompt that says "implement Task 4 of `docs/plans/<plan>.md`" points at a file no worker can read.
- A PR needs a base branch to be opened against.

So the first commit goes straight to the default branch. It is the one time this skill does that, which is why it is documents only and needs the owner's word. Check with `scan_queue.py` (it prints `default branch: none`) before filing anything.

```sh
git init -b main && git add docs/ && git commit -m "docs: add approved design and implementation plan"
git remote add origin <url> && git push -u origin main      # only when the owner has said so
```

Before the commit, in a public repository: read both documents for personal names, domains, hostnames and addresses, and replace them with placeholders. A design written in conversation carries details a public repo should not. The private originals stay wherever they were written.

## Until the scaffold task merges

The seeded repository has no rules file, no gate and no CI. The first task of a plan normally creates all three.

- Run the scaffold issue alone. Everything else imports from it or is tested by its gate.
- For step 0, take the rules from the plan's own constraints section, and say in the plan that you did.
- `ci_state.py ... ref:main` reports `NO_CI`. That is expected once, before the scaffold merges, and not after.
- When the scaffold PR is open, later issues that `Builds on` it can start from its branch. Their PRs go green only when the scaffold's workflow is on their base, which stacking gives them.

## Sizing: an issue is one PR's worth

The first of the two runs filed more issues than it opened PRs: several tasks were combined into one PR at run time. The second filed one issue per task and opened one PR per issue. The second is the rule, because the issue is the unit everything else hangs on: `Closes #N`, the worker's brief, the CI run, the row in the report that says what to check in review.

Combine tasks when writing the issues, not when running them:

- Combine two tasks that cannot pass the gate separately (a module and the only code that calls it).
- Combine tasks too small to be worth a review each.
- Split a task that has two independent halves, if that puts them in different lanes.

## Writing dependencies so the run can go wide

A plan lists tasks in an order that makes sense to read. That order is rarely the dependency graph. For each task ask two questions.

1. **What does it need to exist?** If the answer is code from task N, write `Builds on: #N`. If it is a decision, a measurement or a release, write `Runs after: #N`.
2. **What will it touch?** List the files it creates and the existing files it edits. Mark the files several tasks add to (the application's route registration, the schema, the README) as append points.

Then look for the shape. The usual one for a new application:

```
scaffold → shared helpers → feature A ┐
                          → feature B ├→ frontend → installer and deploy notes
                          → feature C ┘
```

The features each add a module and its tests, and append routes to the application file. They build on the helpers and not on each other, so they are three lanes that start together. Tasks at the edge of the plan are the easiest to miss: an installer or deployment task usually needs only the scaffold, and can run from the first minute instead of last.

A plan's file list understates what a task touches. In the second run every feature task also edited the rules file (a status line), the shared test fixtures and the application's route file, and the plan listed only the last. Count those three as append points for every task: parallel lanes are still safe, and the stack order resolves them, but a planner who trusts the plan's list will call two tasks disjoint when they are not.

Tasks that edit the same existing code do not parallelise, whatever the plan's order says. A frontend task that restyles pages written by an earlier frontend task builds on it. Say so with `Builds on`, and the run puts them in one lane.

If most tasks end up in one chain, the plan is sequential, and that is a fact about the plan. Say so when showing the list; the owner may prefer to restructure the plan over filing ten issues that run one at a time.
