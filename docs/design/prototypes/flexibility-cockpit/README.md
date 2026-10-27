# GridPilot — Flexibility cockpit, concept 01

One independent, locally authored design prototype. It is separate from the working dashboard in web/. No remote design generation or paid model call was used.

## Open

From this directory:

~~~sh
python3 -m http.server 4186 --bind 127.0.0.1
~~~

Open http://127.0.0.1:4186 in Chrome. This serves static files only: no API, installation, GPU or network connection is needed. The packaged ZIP contains the same source and local fonts. A localhost server is recommended for consistent font loading.

## Try

- Keep large jobs in Utah: the headline and conditional interval switch to the computed small-job-mobility scenario.
- Give destinations more room: load the separate computed capacity scenario.
- Select a region: inspect its modeled annual consumption-based intensity.
- Open Evidence: see the claim frame and data lineage.
- Explore the storage concept: a qualitative explanation only, with no invented storage result.

The comparison uses fixed clean-region policy S, not a claimed ML improvement. Headline reductions are simulated validation results. Deadlines are preserved by assumed advance-known baseline bookings, with exact declared runtimes; runtime uncertainty is untested.

## Visual direction

- Warm ivory and forest ink for a calm editorial hierarchy.
- Cleaner green, higher-carbon Utah clay, blue for placement actions.
- Restrained translucent surfaces; opaque marks and legible charts.
- One large outcome, one visible challenge, supporting evidence one click away.
- Real regional outlines; links show placement options rather than measured flows.
- Native buttons, keyboard focus, modal dialogs and reduced-motion support.
- Existing GridPilot mark and local Funnel fonts.

This is a proposed alternative composition, not a replacement for the approved dashboard. Palette and hierarchy changes can be adopted independently.

## Data snapshot

data.js preserves source metric envelopes and provenance IDs from:
- results/metrics.json: run 20261027T160656Z, policy S and time-only W contrasts.
- results/extensions.json: small-job mobility and 1,024-slot destination scenarios.
- results/grid-profile.json: modeled annual and typical-day intensity.
- web/public/data/geo/: derived BA geometry and Natural Earth state geometry.

No sealed values were accessed and no simulation was rerun for this prototype. Values are frozen to these validation artifacts, not connected to a live experiment.

## Verification

The local browser pass checked:
- primary 22.6%, small-job-mobility 3.2%, expanded-capacity 35.0%, each rounded from its source scalar;
- regional selection and storage dialog behavior;
- desktop screenshots at 1728×1117 and 1440×900;
- mobile at 390×844, with no horizontal overflow;
- blocked external requests: zero attempted;
- JavaScript page errors: zero;
- axe WCAG A/AA violations: zero in the audited main state.

Desktop and mobile screenshots are included. These checks do not establish actual-Mac performance or complete assistive-technology support.

## Review record

| View | Finding | Severity | Disposition |
|---|---|---|---|
| Mobile | Translucent offscreen layers disappeared in a full-page Chromium capture | major | Fixed: opaque mobile surfaces and no backdrop blur |
| Mobile | Decorative map annotation competed with placement links | minor | Fixed: annotation omitted on narrow screens |
| Shared | Secondary labels were too small | minor | Fixed: CSS labels raised to at least 10 px; chart uses viewport-width coordinates |
| Storage | A numerical curve would imply an unrun analysis | critical | Avoided: explicitly qualitative, with no storage benefit |
| Delivery | Actual MacBook offline rehearsal | minor | Deferred: concept review, not production release acceptance |

No independent paid critique was launched. This self-review is not the experiment's independent results audit.

## Licenses

Map provenance and notices: assets/ATTRIBUTION.txt and assets/MAP-LICENSE.md. The derived BA geometry remains under its upstream AGPL-3.0 terms. Natural Earth is public domain. Font license: assets/FONT-LICENSE.txt.
