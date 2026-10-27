---
name: hackathon-evidence
description: Use when inspecting data, running or logging an experiment (forecast models, router policies, sweeps), or writing any number into results/, the dashboard or the pitch. Covers the test-window seal, run directories, evidence labels, and what a claim needs before anyone repeats it.
---

# Hackathon evidence

Judges will ask "how do you know?". Every number we show must survive that question.

## Evidence labels

Every field that reaches `results/`, the dashboard or a slide carries exactly one label.

| Label | Meaning | Example |
|---|---|---|
| observed | historical grid or market data, as published | EIA-930 demand, CAISO day-ahead LMP |
| measured | a characteristic read from a real workload trace | job durations and GPU counts in a public trace |
| forecast | a model output issued before its target time | our day-ahead demand forecast |
| modeled | computed from observed data plus stated factors | carbon intensity from fuel mix × emission factors; energy per job |
| assumed | a parameter we chose, shown with its sensitivity range | allowed wait, deferrable share, PUE |
| simulated | the outcome of running a policy in the simulator | CO₂ and cost of a schedule |

## Inspecting data

- Call `gridpilot.splits.drop_sealed` before any summary, plot or fit.
- The sealed test window is [2025-11-01Z, 2026-11-01Z). Until the spec allows test evaluation, only its completeness may be looked at: row counts and missing hours.
- Analyze a fixed snapshot. Record the manifest sha256 of every input in the run's config.
- Keep timestamps in UTC internally. Convert only for display, and say which zone.
- Write down every cleaning rule, and how many rows it touched.

## Running an experiment

- **One run directory per run:** `runs/<experiment>/<UTC timestamp>-<name>/`. It holds:
  - `config.yaml`: every parameter, the seeds, and the input manifest hashes;
  - `git.txt`: the output of `git rev-parse HEAD` and `git status --porcelain`;
  - `metrics.json`;
  - the predictions or schedules, as Parquet.
- **Clean commits for results.** Exploratory runs may come from a dirty tree. Anything that reaches `results/` comes from a clean commit and can be rebuilt with a documented command.
- **Test reads.** The sealed window is read only through the test-evaluation entry point.
  - That entry point appends each read to `results/test_reads.jsonl`: the time, the git SHA, and what was evaluated.
  - Never tune on a test number.
  - If a test read exposes a bug: fix the bug, log the re-read, and say so in the results.

## A claim is ready when

- It is compared with the baselines on the same data, paired: same days, same jobs.
- It has an uncertainty estimate, with the method written next to it. Router results use a block bootstrap over weeks; forecasts use per-day error distributions.
- The sanity orderings hold:
  - on the objective, perfect hindsight ≥ our optimizer ≥ the baselines;
  - forecasts beat persistence on validation.
  If not, look for a bug before telling a story.
- It states its labels, its main assumptions, and how sensitive the result is to those assumptions.
- Its wording matches its evidence: "in simulation", "on 2025 data", "for these 10 regions". Never extrapolate without saying so.
