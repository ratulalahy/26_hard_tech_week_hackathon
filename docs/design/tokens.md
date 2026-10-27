# Design tokens: Utah palette (G2, owner 2026-10-27)

The owner's G2 feedback on round 3: "only more meaningful color would be helpful... redish is high or danger.. green is low or more positive... purple is taking over the landscape... make it utah orangish version". Round 4 applies three colour-theory rules, checked with the dataviz validator (`validate_palette.js`).

1. **Hue carries meaning.** Carbon follows the traffic-light code: green, then sand, then Utah orange, then canyon red.
2. **Lightness carries magnitude.** On each side of the midpoint, lightness is monotone, so the order survives colour blindness and greyscale. The red end (L 0.38) is darker than the green end (L 0.56).
3. **One complementary accent.** The router's action is deep blue, the complement of orange.

## Carbon intensity: a diverging scale, g CO₂/kWh

- **Midpoint** `CI_MID = 356` g/kWh: the 2024 US average CO₂ intensity of generation, from EIA, *United States Electricity Profile 2024*: 785 lb CO₂/MWh × 0.453592 = 356 g/kWh (https://www.eia.gov/electricity/state/unitedstates/). It is a national generation-basis annual average, used as a reference midpoint. The dashboard reads it from `results/grid-profile.json` (`reference.us_avg_ci`, observed); the legend reads "356 · US avg 2024 (EIA)".
- **Scale:** 0 → 356 → 750, nine OKLCH steps, interpolated in OKLab. Only the four core regions wear it on the map; other regions are a flat neutral sand.

| Step | 0 | 1 | 2 | 3 | 4 (mid, 356) | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| hex | `#298954` | `#59aa6d` | `#8fc990` | `#c3e2bc` | `#f7efe0` | `#f5c79f` | `#ed8b51` | `#c6481c` | `#7c1213` |

## Roles

| Token | Hex | Meaning |
|---|---|---|
| route | `#1157a4` (soft `#dfedfe`) | the router's action: move arc, job hours, chosen option. It is the only blue, and arcs carry a white casing. |
| rush | `#4a3a30`, fill `#eadfd3` | rush hour or grid stress. It is a neutral caution hatch, never a hue. |
| solar | `#f4d846`, mark `#ddbc1a` | solar generation: a fill only, always labelled. |
| ink | `#2d1d14` / `#5b493f` / `#6c594f` | text and the net-load line |
| ground | `#fdf9f4` / `#faf2ea` / `#f6ebdf` | salt-flat atmosphere. The relief is a warm sandstone duotone (`#8c6a4f` → `#fdf9f4`). |

## Validator results

The full text is in the gallery's Design system tab.

**Passes:**
- Each half of the scale is monotone in lightness and stays within one hue (15° for the greens, 36° for the reds).
- Route against every carbon step: colour-blind ΔE 21.8–48.7.

**Warnings, accepted because the item has a second cue:**
- The light steps near the midpoint have low contrast against the page (by design). Cells have gaps and labels.
- Orange against green: colour-blind ΔE 7.4. They are never adjacent, and cells are labelled.
- Solar against peach: ΔE 12.2. Solar is only ever a labelled area.

Generator scripts: `docs/design/concepts/src/oklch.mjs` and `div2.mjs`.

## Shared map as a backdrop

Owner feedback on round 4: the backdrop map "is taking too much focus".

- On every view except the map view (Control room), the shared relief and hex map is a watermark: opacity 0.14–0.18, `filter: saturate(.3) blur(1.5px)`.
- A view's own small map (for example the Decision cockpit's inset) stays at full colour.

## Type scale (owner, 2026-10-27; used by `web/`)

Funnel Sans carries the interface; Funnel Display carries the view title and the one hero number. Both are self-hosted with @fontsource. Every number uses tabular figures (`font-variant-numeric: tabular-nums`).

| Role | Size | Weight | Face | CSS class |
|---|---|---|---|---|
| Meta, evidence chips | 11 px | 400 / 500 | Funnel Sans | `.t-11` |
| Axis labels, secondary text | 12 px | 400 / 500 | Funnel Sans | `.t-12` |
| Body | 13 px, line-height 1.35 | 400 | Funnel Sans | `.t-13` |
| Panel title | 15 px | 600 | Funnel Sans | `.t-15` |
| View title | 20 px | 500 | Funnel Display | `.t-20` |
| Hero number (one per view) | 28–32 px (30 by default) | 500 | Funnel Display | `.t-hero` |

- Weights 400, 500 and 600 only. No other display-size text.
- Units sit in smaller, muted type after the number (`.unit`). Thousands take separators; the minus sign is U+2212.
- Font-weight classes are `fw-400`, `fw-500` and `fw-600`. Tailwind's `w-*` classes are widths, so never use them for weight.

## Space, radii and elevation (owner, 2026-10-27)

- **Grid:** 8 px. Panel padding 12–16 px; gutters 16 px.
- **Radii:** 8 px for controls and chips, 12 px for inner blocks and rows, 16 px for panels.
- **Elevation:** a 1 px hairline (`rgba(110,62,30,.14)`) plus soft, layered, warm shadows. Never one heavy grey drop.
- **Motion:** 120–200 ms on hover, focus and pressed states; camera moves and view changes at most 300 ms. All of it is off under `prefers-reduced-motion`.
