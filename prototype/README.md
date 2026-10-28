# GridPilot · The Pilot Desk

**Open `index.html` in Chrome.** On a Mac, drag it into Chrome or right-click → Open With → Google Chrome. Copy the entire `prototype/` folder to the laptop; keep the files together. No server, install, internet, or build is needed to present it. Fonts and evidence are local.

A short interactive judge demo turns the project's key caveat into a decision:

1. **Move the work:** the registered fixed-ranking policy reduces attributed CO₂ by 22.3% in the simulated replay.
2. **Challenge the assumption:** restrict mobility to jobs requesting ≤ 8 GPUs; the recorded reduction falls to 3.2%.
3. **Give storage a job:** switch an illustrative battery between carbon and grid-rush schedules. Watch the tradeoff change, including its limitations.

Use the chapter buttons, **← / →**, or the guided buttons. **Restart** resets the demo. **Inspect evidence** shows source paths, run IDs, source hashes, scope, and original evidence envelopes; **Esc** closes it.

## Evidence boundaries

This is a presentation prototype over **committed outputs**, not a new experiment or a live router. It uses the existing published test-year replay; it never reads raw data, opens the seal, or changes model settings. The package is pinned to `source-commit.txt`, with hashes in `sources.json`.

Routing is simulated on a measured public workload and historical grid data, with assumed mobility and exact runtimes. It reports **attributed**, not avoided, emissions. Its 95% intervals are conditional on one replay. The ≤ 8 GPU scenario is secondary evidence. Storage is illustrative, has a separate 357-day window, and uses the Utah-only U workload; its savings are **not added** to routing. No Torus hardware performance is implied. The schedule ribbon shows allowed hours, not actual battery dispatch. There are no invented intermediate scenarios.

## Development checks (not needed to present)

From the repository root:

```sh
python3 prototype/tools/build-data.py
npm ci --prefix prototype --cache prototype/.npm-cache --ignore-scripts
npm --prefix prototype run check
```

The builder reads pinned Git objects and writes only into `prototype/`. Checks require Node and installed Chrome/Chromium; set `CHROME_PATH` if it is not found. They test `file://` with networking disabled, compare values and hashes with Git, exercise every state, check accessibility and layout at 1440×900, 1728×1117 and 390×844, and inject missing/malformed evidence. Screenshots and the machine report go into ignored `qa/` files. The demo itself uses no npm packages.

Verified in Linux Chromium, including offline operation; a physical MacBook check remains for the presenter. Review notes are in `qa/review.md`.
