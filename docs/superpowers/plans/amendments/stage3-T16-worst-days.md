# Stage 3 · T16: "Utah's toughest grid days" case study (D-066; validation only; illustrative; merges AFTER the test run)

Branch `s3/t16` from main. **Do not merge before the test run.** The seal holds: validation year only, pre-seal loaders only, and the F8 guard stays green. No new simulations.

## Day-selection rule (pre-registered in D-066 before looking at any day; do not change it)
- **Window:** validation days [2024-11-01, 2025-10-24), in the America/Denver calendar.
- **Stress:** PACE daily maximum hourly **net load**, i.e. adjusted demand − wind − solar from EIA-930, using the existing spike rule.
- **Pick:** the **top 3 days** by that maximum. Ties go to the earlier date.
- **Report:** each day's rank. Never substitute a "better-looking" day.

## Per day (from the registered run `runs/slice/20261027T160656Z`)
- Hourly PACE net load, demand, solar and wind: observed.
- Hourly PACE carbon intensity: modeled (EIA estimate; the F14.6-filled truth).
- The Utah cluster's hourly load under U vs S and W (simulated), and where the moved work ran that day (by site).
- That day's attributed CO₂ for U vs S and W (simulated), counting energy by execution hour that day. State that this is day-sliced accounting.
- Whether the router's moves lowered Utah cluster load during that day's net-load peak hour.

## External context (free, cited)
- For each date, look for a public source describing grid conditions: EIA "Today in Energy", NERC or WECC reports, utility or ISO notices, NOAA storm or heat records, or news.
- Record the URL, title and date, and add one factual sentence per day. If nothing credible is found, say "no public event record found".
- Label it **context**, not evidence for any result. Never infer causes not in the source.

## Export and UI
- **Export:** `results/case-days.json`. Every number is enveloped; context sources go in a `sources` list. Add it to the envelope and sealed-date tests and to `copy-data`.
- **UI:** a "Utah's toughest grid days" card in the Day ribbon view, a compact 3-day switcher. For each day:
  - the net-load curve over the carbon strip;
  - cluster load U vs S;
  - one sentence;
  - the cited context line.

  No new Story beat. Evidence chips follow tokens.md. Axe 0, offline test pass, screenshots at 1728 and 1440.

## Report
Write `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/s3-t16-report.md`.
