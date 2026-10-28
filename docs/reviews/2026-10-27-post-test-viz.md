# Post-test dashboard test view: viz-critique self-pass

Branch `s3/post-test`. Shots: `docs/design/shots-build/test-*-{1440,1728}.png` (real sealed test year, not a fixture), made by `web/tests/test-view-shots.spec.ts`. axe (WCAG 2.2 AA): 0 violations on the sealed control, ribbon, story-5 and method states. No Codex critic was run: it needs the owner's OK for credits.

| view | rubric item | severity | evidence | disposition |
|---|---|---|---|---|
| story 5 (test) | insight first: panel title was a label ("carbon schedule vs peak-aimed schedule") | major | test-story-5-1440 (before) | fixed: the title states the finding from extras.json (peak-aimed cuts rush-hour import to 0.32 MW; CO₂ cut falls 4.0% → 1.0%) |
| method drawer, drift | labels: kg rows showed tonnes | minor | test-method-drift-1440 (before) | fixed: "(kg" restated as "(t" when the cells are tonnes |
| story 5 (test) | type: lower-case sentence start after the rush-hour count | minor | test-story-5-1440 (before) | fixed |
| control (test) | wait-only dots sit under the row labels at ~0.8% | minor | test-control-1440 | deferred: same chart and behaviour as the validation view; not introduced here |
| ribbon (test) | toughest days are a table, not the validation day chart | minor | test-ribbon-1440 | deferred: the test extras carry no hourly day profile; labelled as such on the panel |
| story 4 (test) | the scenario map, toggle and flexibility budget have no test counterpart | minor | test-story-4-1440 | accepted: labelled "validation year · no test counterpart"; the test mobility check (3.2–3.9%) is in the text |
