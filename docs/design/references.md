# Design references (U0)

> **Internal reference only.** The screenshots in `docs/design/refs/` belong to their publishers. They were captured on 2026-10-27 with headless Chrome so the team can study them. They must not ship in the dashboard or the deck, or be posted anywhere public. Nothing behind a login was captured, and no bot check was bypassed.

This is the U0 output of plan v2. The three Claude mockups (B, C, A) and Astra's direction build from it, together with the shared brief in `docs/design/brief.md`.

## How to read an entry

- **Link** and **What**: the page and what it is.
- **Thumb**: the screenshot in `refs/`, or *none* with the reason.
  - *Viewed* means we rendered the page on 2026-10-27.
  - *Described* means the site blocks automated browsers (Cloudflare, Akamai, DataDome, or a "you're a robot" wall). The description comes from the publisher's own text or from prior knowledge of the page. Open it in a normal browser before copying anything from it.
- **Borrow**: the specific pattern to take. It is the reason the reference is here.
- **Skip**: what not to copy from it, where that matters.
- **Informs**: which of our views it feeds. The views are the grid clock, the load-curve story, the map with arcs, the move-vs-wait replay, the delay-budget slider, skeptic mode, the clean≠rush strips, "Plan my run", the "Tomorrow" card, and the evidence chips.

The ten strongest references are marked ★.

---

## 1. Energy products

### R01 ★ Electricity Maps (live map)
- **Link:** https://app.electricitymaps.com/map
- **What:** The open-core live carbon map of the world's grids. Our BA polygons come from its open-source repo (AGPL-3.0).
- **Thumb:** none (described; Cloudflare blocks headless Chrome).
- **Borrow:**
  - Zones filled on one sequential carbon scale. Animated exchange arrows show the flow's direction, and their size shows its magnitude.
  - A **production vs consumption toggle** for intensity. That toggle is the first step of our skeptic mode (average → consumption → marginal).
  - Zones whose numbers are modeled carry an **"estimated" badge**.
- **Skip:** the dark-first chrome, and the global zoom. We stay on the West.
- **Informs:** map with arcs, skeptic mode, evidence chips, grid clock.

### R02 Grid Status (live ISO dashboards)
- **Link:** https://www.gridstatus.io/live
- **What:** Live and historical data for every US ISO, the de-facto analyst view of the US grid.
- **Thumb:** none (described; Cloudflare).
- **Borrow:**
  - Sober, dense small multiples per ISO: fuel-mix stacked area, net load, prices. A light UI that grid people trust because it adds nothing.
  - "Record" annotations sit on the curve itself.
- **Skip:** the trader density. Our judges get one focal chart per screen.
- **Informs:** load-curve story, grid clock, Tomorrow card.

### R03 EIA Hourly Electric Grid Monitor
- **Link:** https://www.eia.gov/electricity/gridmonitor/dashboard/electric_overview/US48/US48
- **What:** The official US view of EIA-930: BAs as nodes on a map, interchange as edges, and an hour slider with play. It is our primary data source.
- **Thumb:** [refs/eia-grid-monitor.png](refs/eia-grid-monitor.png) (viewed).
- **Borrow:**
  - **BA as a node and interchange as an edge.** That is the honest geometry for our arcs, because BAs are not neat polygons.
  - The hour play control, and a diverging scale centred on 0% change.
- **Skip:** government chrome, 11 px type, a gear and a download icon on every panel, and node-and-line clutter over a flat gray US.
- **Informs:** map with arcs, grid clock, evidence chips (cite "EIA-930" by name).

### R04 ★ CAISO Today's Outlook
- **Link:** https://www.caiso.com/todays-outlook
- **What:** The California ISO's public page for today's demand, net demand (the duck curve), supply, emissions and prices.
- **Thumb:** [refs/caiso-todays-outlook.png](refs/caiso-todays-outlook.png) (viewed; cropped to the two trend charts).
- **Borrow:**
  - **Actual vs day-ahead vs hour-ahead forecast on one 24-hour axis.** Dotted lines are forecasts; the solid line is the measured value.
  - The **shaded ramp wedge with its own label** ("3-hour average ramp ~24,206 MW"): one annotation, placed at the insight.
  - The **"AS OF 23:20 PT"** stamp, a one-line "Grid status: Normal", and a "Tomorrow's forecasted peak" figure.
- **Skip:** the row of icon + number KPI tiles, and the gradient area fill on every chart.
- **Informs:** load-curve story, grid clock, Tomorrow card, evidence chips.

### R05 ★ Energy-Charts "Electricity traffic light" (Stromampel), Fraunhofer ISE
- **Links:**
  - traffic light: https://energy-charts.info/charts/consumption_advice/chart.htm?l=en&c=DE
  - generation chart: https://energy-charts.info/charts/power/chart.htm?l=en&c=DE
- **What:** A public "when to use power" traffic light for Germany and 11 more countries. Fraunhofer's release says users can move EV charging and **"data-heavy IT processes"** to green hours, which is our pitch in one sentence. It is also published as an Android app and an open API.
- **Thumbs:** [refs/energy-charts-traffic-light.png](refs/energy-charts-traffic-light.png), [refs/energy-charts-power.png](refs/energy-charts-power.png) (viewed).
- **Borrow:**
  - **Categorical day bands (green, yellow, red) behind a continuous line** (renewable share). It is the best existing form for our clean≠rush strips.
  - The band is graded **against a baseline**: the same month over the past five years. So "green" means good for this time of year, not good in absolute terms. That is an honest rule we can copy for PACE.
  - In the generation chart, the **forecast continues in a lighter tint after "now"**.
- **Skip:** the 20-entry legend with struck-through items, the default serif axis labels, and the dashboard side panel.
- **Informs:** clean≠rush strips, Tomorrow card, grid clock, load-curve story. It is the strongest precedent for direction A's metaphor.

### R06 UK Carbon Intensity API (NESO with EDF Europe, Oxford and WWF)
- **Link:** https://carbonintensity.org.uk/
- **What:** A national and regional carbon-intensity forecast 96+ hours ahead, built "to schedule and minimise CO₂ emissions at a local level".
- **Thumb:** [refs/carbon-intensity-uk.png](refs/carbon-intensity-uk.png) (viewed; cropped).
- **Borrow:**
  - **A day as three numbers**: average, max ↑, min ↓ (68 / 82 / 52 g). One current number sits above them. That is the minimum honest Tomorrow card.
  - It calls itself a forecast, outright.
- **Skip:** the centred marketing hero, plum + Poppins, and the cookie wall.
- **Informs:** Tomorrow card, Plan my run.

### R07 Octopus Agile
- **Link:** https://octopus.energy/smart/agile/
- **What:** A UK tariff with half-hourly prices. Tomorrow's prices are published every afternoon, and negative-price slots are branded "Plunge Pricing".
- **Thumb:** none kept. It was captured, but it is a dark marketing page with no chart.
- **Borrow:**
  - **The publication ritual:** "tomorrow's rates are out between 4 and 8 pm". We say "Tomorrow's report: issued 10:00 MT".
  - **Naming events** ("plunge"), so a forecast becomes something you act on.
- **Skip:** the whole skin. Purple on navy with a neon magenta CTA and mascots is the textbook AI-gradient look.
- **Informs:** Tomorrow card, Plan my run, clean≠rush strips.

### R08 ★ Ember Electricity Data Explorer, as presented by Our World in Data
- **Links:**
  - Ember: https://ember-energy.org/data/electricity-data-explorer/
  - OWID chart (Ember data): https://ourworldindata.org/grapher/carbon-intensity-electricity
- **What:** Ember publishes open electricity data by country and month. OWID's grapher shows it, with sources stated at chart level.
- **Thumb:** [refs/owid-grapher.png](refs/owid-grapher.png) (viewed; cropped). Ember's page was viewed but hidden behind its consent modal, so it is not kept.
- **Borrow:**
  - **Provenance on demand.** "Data source: Ember (2026) – Learn more about this data" under the chart, then an "About this data" block: source, "with major processing by…", last updated, next expected update, unit, date range. That is the content of our **evidence chips**: label + source + window + method link.
  - Table / Map / Line tabs on one dataset.
  - Ember's **metric toggle** (absolute / % share / per capita) as a segmented control.
- **Skip:** OWID's ALL-CAPS tracked labels ("CONFIGURE THE DATA"), and its serif + orange ramp, which edges toward cream + serif + terracotta.
- **Informs:** evidence chips, skeptic mode, map with arcs.

### R09 Tesla app, Powerwall energy views
- **Link:** https://www.tesla.com/powerwall
- **What:** Tesla's home-storage product. Its app shows live energy flow between solar, home, Powerwall and grid.
- **Thumb:** none (described; Akamai "Access Denied" to headless Chrome).
- **Borrow:**
  - **Flow animated along fixed paths, with speed tied to power.** It is cause-and-effect motion that storage people read instantly, and Torus is a storage company.
  - Use it only for things that really move: jobs and energy between regions.
- **Skip:** the dark glossy product render.
- **Informs:** move-vs-wait replay, map with arcs.

## 2. Data journalism

### R10 ★ NYT, "Giant Batteries Are Transforming the Way the U.S. Uses Electricity"
- **Link:** https://www.nytimes.com/interactive/2024/05/07/climate/battery-electricity-solar-california-texas.html
- **By:** Brad Plumer and Nadja Popovich, 2024-05-07.
- **What:** California's generation by source over a day, April 2021 vs April 2024. Batteries fill the evening after solar fades, peaking at 7,046 MW on 2024-04-30.
- **Thumb:** none (described; NYT robot wall).
- **Borrow:**
  - **The same day drawn twice on one axis (before / after), with one annotated moment.** It is the cleanest way to show "the router reshapes the load": run-now vs routed.
  - It is also the story closest to Torus's business: storage moving energy in time.
- **Informs:** load-curve story, move-vs-wait replay, Tomorrow card.

### R11 ★ NYT Upshot interactives: "Is It Better to Rent or Buy?" (2014) and "You Draw It" (2015)
- **Links:**
  - https://www.nytimes.com/interactive/2014/upshot/buy-rent-calculator.html
  - https://www.nytimes.com/interactive/2015/05/28/upshot/you-draw-it-how-family-income-affects-childrens-college-chances.html
- **What:** Two canonical reader-input pieces.
- **Thumb:** none (described; NYT robot wall).
- **Borrow:**
  - Rent-or-buy: **every slider carries a small chart of how the answer changes across that slider's range.** The reader sees the sensitivity before dragging. Our delay-budget slider should draw "CO₂ saved vs allowed wait (0–24 h)" on its own track, so the knee near 6 h is visible.
  - You Draw It: **the reader commits a guess, then the truth is revealed against it.** For example: "How much does waiting cut a Utah job's carbon?" The reader drags a guess, then we show 33% (average CI, perfect foresight) and the marginal caveat. It turns the judges' skepticism into participation.
- **Informs:** delay-budget slider, skeptic mode, Plan my run.

### R12 Washington Post, "Mapping how the United States generates its electricity"
- **Link:** https://www.washingtonpost.com/graphics/national/power-plants/
- **By:** John Muyskens, Dan Keating and Samuel Granados, 2015.
- **What:** Every US power plant as a proportional symbol, then one small map per fuel.
- **Thumb:** none (described; the page did not render headless).
- **Check:** the URL is from memory and was not confirmed; the pages that cite it are bot-walled too. The credits are confirmed by secondary coverage. Open it before citing it.
- **Borrow:** **Small-multiple maps per fuel** for the beat "why Utah is dirty at night": a thumbnail map of coal, one of solar and one of hydro across the West.
- **Informs:** map with arcs, load-curve story.

### R13 Bloomberg Graphics, "AI Needs So Much Power, It's Making Yours Worse"
- **Link:** https://www.bloomberg.com/graphics/2024-ai-power-home-appliances/
- **By:** Leonardo Nicoletti, Naureen Malik and Andre Tartar, Dec 2024. Bloomberg ran a second piece in 2024: "AI Is Already Wreaking Havoc on Global Power Systems".
- **What:** An investigation that ties data-centre locations to measured power quality in nearby homes.
- **Thumb:** none (described; "press & hold" bot wall).
- **Check:** the URL is confirmed by a citing presentation. The headline and byline are from memory.
- **Borrow:**
  - **A headline that states the finding.**
  - Data centres as their own point layer.
  - A **national-to-local zoom**: US first, then one region. Ours is US → the West → Utah.
- **Informs:** map with arcs, story beats.

### R14 FT, "The Climate Game"
- **Link:** https://ig.ft.com/climate-game/
- **What:** The Financial Times' 2022 game: reach net zero by 2050 through a series of energy-policy decisions.
- **Thumb:** [refs/ft-climate-game.png](refs/ft-climate-game.png) (viewed; cover only).
- **Borrow:**
  - **Decision → immediate consequence, with one persistent meter.** For Plan my run, the meter shows the job's tCO₂ and its deadline slack.
  - Advisers who argue the trade-offs are a model for skeptic mode's voice.
- **Skip:** the illustrated hero scene. Our hero is data.
- **Informs:** Plan my run, move-vs-wait replay, skeptic mode.

### R15 Reuters Graphics, "Buildings wrapped in solid gasoline"
- **Link:** https://www.reuters.com/graphics/BUILDING-FIRES/byprqyryzve/
- **By:** Mariano Zafra and Sudev Kiyada. Information is Beautiful Awards 2024, Bronze, Places, Spaces & Environment.
- **What:** A scroll-driven explainer in which one scene changes state step by step. Not energy, but it is Reuters' house craft at its best.
- **Thumb:** none (not captured).
- **Borrow:**
  - **A sticky stage with short step captions.** The chart stays put while overlays change: demand, then carbon, then the moved job.
  - Scroll is the timeline, and story-mode scrubbing is tied to it, as the viz-critique rubric requires.
- **Informs:** load-curve story, story mode in general.

### R16 The Pudding, "Climate Zones: How will your city feel in the future?"
- **Link:** https://pudding.cool/2024/06/climate-zones/
- **By:** Derek Taylor, June 2024. The Pudding won Outstanding Studio (Gold) at the 2024 Information is Beautiful Awards.
- **What:** Pick a city, and it becomes the protagonist. The answer comes as an analogy: "New York in 2070 will feel like Barcelona today".
- **Thumb:** [refs/pudding-climate-zones.png](refs/pudding-climate-zones.png) (viewed).
- **Borrow:**
  - **Personal input, then a plain-language analogy.** Plan my run could answer: "Run it at 2 AM in Utah and it's a coal-plant job; at noon it's half solar; in Oregon it's a hydro job."
  - A light, low-chroma basemap under a few saturated data colours.
- **Skip:** the novelty display title, which works for The Pudding and is wrong for a credibility demo.
- **Informs:** Plan my run, Tomorrow card, map with arcs.

## 3. Map and motion craft

### R17 ★ Windy
- **Link:** https://www.windy.com/
- **What:** A weather-forecast map with particle animation, and the reference for time on a map.
- **Thumb:** [refs/windy.png](refs/windy.png) (viewed; it opened on Orem, Utah, showing the West).
- **Borrow:**
  - **One bottom timeline drives every layer.** It has day segments, a play button and an hour cursor in a flag ("12 AM"). That is our grid clock control.
  - A compact strip of the next four days at the top, each with a small curve: a Tomorrow card in miniature.
- **Skip:** the dark chrome, the rainbow scales and the ad strip.
- **Informs:** grid clock, Tomorrow card, map with arcs.

### R18 Flightradar24
- **Link:** https://www.flightradar24.com/
- **What:** Live aircraft on a map. Click one and you get its trail plus a detail panel: route, ETA, altitude profile.
- **Thumb:** none (described; Cloudflare).
- **Borrow:** **Click an entity to get its trace.** In the replay, clicking a job opens its decision trace: origin BA, decision (wait / move / run), destination, start time, tCO₂ vs run-now, and the deadline.
- **Skip:** the dark map, and the swarm of identical icons.
- **Informs:** move-vs-wait replay, map with arcs.

### R19 deck.gl ArcLayer example and kepler.gl
- **Links:**
  - https://deck.gl/examples/arc-layer
  - https://kepler.gl/demo
- **What:** The reference implementations of the stack we plan to use (deck.gl with MapLibre).
- **Thumb:** [refs/deckgl-arc-layer.png](refs/deckgl-arc-layer.png) (viewed). kepler.gl was viewed but opens on a data-loading modal, so it is not kept.
- **Borrow:**
  - **Two-colour arcs that run from a source colour to a target colour.** The arc's height encodes distance; width can encode MWh moved.
  - kepler's **time-window playback** over arcs.
- **Skip:** 300k unlabeled arcs on a spectral ramp. We draw ≤ 10 labeled arcs on a carbon scale.
- **Informs:** map with arcs, move-vs-wait replay.
- **Mapbox Customer Showcase** (https://www.mapbox.com/showcase) was also checked. It is a wall of client logos with nothing to borrow.

### R20 Mini Tokyo 3D
- **Link:** https://minitokyo3d.com/
- **By:** Akihiko Kusanagi.
- **What:** Tokyo's trains and planes in real time on a 3D map. Lighting follows the clock, and you can click a train for its timetable.
- **Thumb:** none. It loaded, but WebGL content had not finished rendering when the headless capture fired.
- **Borrow:**
  - **A light basemap with live moving entities.** Each entity has a timetable card.
  - The time of day is visible on the map itself. Ours: a soft daylight band crossing the West with the hour, because solar output follows daylight.
- **Informs:** move-vs-wait replay, grid clock, map with arcs.

### R21 ★ UDOT Traffic (Utah Department of Transportation)
- **Link:** https://udottraffic.utah.gov/
- **What:** Utah's own live traffic report: a red alerts bar, a road-weather index, layers, and routes.
- **Thumb:** [refs/udot-traffic.png](refs/udot-traffic.png) (viewed).
- **Borrow:**
  - **The advisory sentence.** "Road Weather: Both directions of SR-162 are closed … Delay travel or use an alternate route." That is exactly the structure of our two moves, wait and move. Example copy, with the hours to come from the data: "Grid: Utah's evening rush, 5–8 PM. Delay flexible jobs or route them to the Northwest."
  - The **four-level index** (Unknown / Low / Moderate / High).
  - This is the vocabulary a Salt Lake City judge already knows.
- **Skip:** the Google basemap noise, marker clusters, and the dense layer list.
- **Informs:** Tomorrow card, grid clock, map with arcs. It is direction A's home reference.

### R22 Natural Earth shaded relief (Tom Patterson, shadedrelief.com)
- **Links:**
  - https://shadedrelief.com/
  - https://www.naturalearthdata.com/downloads/50m-raster-data/50m-shaded-relief/
- **What:** The public-domain relief that our `relief.png` is built from (SR_50M), and its author's cartographic method.
- **Thumb:** none (described; Cloudflare).
- **Borrow:**
  - **Relief as a quiet ground.** Grayscale hillshade multiplied at low opacity under the data, with a warm-gray tint and no hypsometric colour. The Wasatch, the Great Basin and the Columbia Gorge read as place without competing with the carbon scale.
- **Informs:** map with arcs. It is direction C's base.

## 4. Explorable explanations

### R23 ★ Distill, "Why Momentum Really Works"
- **Link:** https://distill.pub/2017/momentum/
- **By:** Gabriel Goh, 2017.
- **Thumb:** [refs/distill-momentum.png](refs/distill-momentum.png) (viewed).
- **Borrow:**
  - **The sliders sit directly under the figure they control.** Each label carries the symbol and its live value ("Step-size α = 0.02"), and the figure redraws instantly.
  - A note beside the sliders tells the reader what to try.
  - Ours: "Allowed wait = 6 h" sits under the PACE curve, and the job's best start slot moves as you drag.
- **Informs:** delay-budget slider, skeptic mode.

### R24 ★ Bret Victor, "Up and Down the Ladder of Abstraction" and "Explorable Explanations"
- **Links:**
  - https://worrydream.com/LadderOfAbstraction/
  - https://worrydream.com/ExplorableExplanations/
- **Year:** 2011, both essays.
- **Thumb:** [refs/victor-ladder.png](refs/victor-ladder.png) (viewed).
- **Borrow:**
  - **Step up from one run to every parameter value at once.** One simulated job, then the whole sweep plotted as a curve, with the current setting as a dot. That is the honest form of the delay budget, and of the CO₂-per-GPU-hour sweep from 0.4 to 2.0 kWh.
  - **Reactive documents: numbers inside sentences that you scrub.** Plan my run as a sentence: "A **72-hour**, **512-GPU** run, due by **Friday 5 PM**, starting in **Utah**…", where every bold value is draggable.
- **Informs:** delay-budget slider, Plan my run, skeptic mode.

### R25 Nicky Case, "The Evolution of Trust"
- **Link:** https://ncase.me/trust/
- **Year:** 2017.
- **Thumb:** [refs/ncase-trust.png](refs/ncase-trust.png) (viewed).
- **Borrow:**
  - **Play first, explain after,** then end in a sandbox where you change the rules.
  - The replay can end with "Now you set the rules" (capacity cap, allowed wait).
  - Very few elements, drawn big.
- **Skip:** the hand-drawn style, which belongs to Case.
- **Informs:** move-vs-wait replay, skeptic mode, Plan my run.

### R26 Bartosz Ciechanowski, "Airfoil"
- **Link:** https://ciechanow.ski/airfoil/
- **Year:** 2024. The archive is at https://ciechanow.ski/archives/.
- **Thumb:** [refs/ciechanowski-airfoil.png](refs/ciechanowski-airfoil.png) (viewed).
- **Borrow:**
  - **One colour means one concept across the whole piece.** Yellow is always the airfoil; red and blue are always pressure. For us, solar yellow always means solar or clean hours, and the rush colour always means the demand peak, in every view.
  - Every figure gets its own small slider, on a light, quiet page.
- **Informs:** load-curve story, delay-budget slider, every view's colour discipline.

## 5. Award winners

### R27 Information is Beautiful Awards 2024
- **Winners page:** https://informationisbeautifulawards.com/news/680-announcing-the-2024-winners
- **Most relevant winner:** Radio-Canada, "Navigate the obstacles to transportation electrification" (Silver, Science, Technology & Health): https://ici.radio-canada.ca/info/2024/voitures-electriques/trajets-voyages-vehicules-quebec/
- **What:** EV adoption in Quebec told as trips and obstacles along a route.
- **Thumb:** none (described from the awards entry).
- **Finding:** the 2024 climate and energy winners are mostly illustrative or flowchart-led. None is a light, live data product. The Pudding took Outstanding Studio (see R16).
- **Borrow:** **the journey frame.** A job is a trip with stops (queue, wait, move, run). It suits Plan my run and the bounty's "navigation app for electricity".
- **Informs:** Plan my run, move-vs-wait replay.

### R28 Awwwards data-visualization picks
- **Links:**
  - https://www.awwwards.com/inspiration/energy-illustration-virya-energy (Virya Energy, by studio ruelle)
  - https://www.awwwards.com/inspiration/data-visualization-sunday (Sunday, by Standard Projects)
- **What:** Awwwards-curated energy and data-viz elements, Lottie- and scroll-driven.
- **Thumb:** none (described from the Awwwards listings).
- **Finding:** award-site data-viz leans to WebGL showpieces, Lottie illustration and scroll-jacking. It is mostly an anti-reference set for a credibility demo.
- **Borrow:** only **scroll-linked chart reveal timing**: one chart, revealed in steps, never hijacking the scroll speed.
- **Informs:** load-curve story (as a timing guide).

## 6. Figma Community

### R29 Figma Community scan (energy dashboards, data-viz kits, map dashboards)

**How the scan was done.** Figma Community returns HTTP 403 to automated fetches and headless Chrome. The names and links below come from search-index results, and the authors come from search snippets or third-party listings where available. **None of the canvases was opened.** Open each in Figma before relying on it.

| File | Author | Link | Use |
|---|---|---|---|
| (v11) Carbon Design System, with the Carbon Charts guidance at https://carbondesignsystem.com/data-visualization/chart-types | IBM (official; view-only) | https://www.figma.com/community/file/1157761560874207208 | **The one worth opening.** Chart anatomy (axes, legends, tooltips, annotations), accessible palettes, and empty / loading / error states. Borrow the anatomy, not the IBM Plex look. |
| Energy Management System Dashboard | not shown to automated tools. A Figma Make page with the same title credits "arshiya.senselive" (unverified) | https://www.figma.com/community/file/1539878898210265275/energy-management-system-dashboard | CC BY 4.0, ~14.2k users. Use it as a component inventory and a check for the "energy dashboard" clichés we avoid. |
| Duke Energy (open-source electricity-usage dashboard) | probably Mohd Suhel (per a ui4free listing; unverified) | https://www.figma.com/community/file/1081095982910037186/duke-energy | A consumer usage-tracking idiom (this period vs last). Low relevance. |
| Data Visualization Package (Community) | Tré Wilson (@tredadesigner) | https://www.figma.com/community/file/1130361890489454674/data-visualization-package-community | 13 charts, 2 cards and 2 dashboards, light and dark. Use as a checklist of chart states. |
| Chart UI Kit v2.0 | not retrievable | https://www.figma.com/community/file/1328496497617715352/chart-ui-kit-v2-0 | 20 chart types modelled on Chart.js 4.4.1, light and dark. Use for anatomy only. |
| LogiTrack – Logistics & Supply Chain Dashboard | not retrievable | https://www.figma.com/community/file/1618475519637916083/logistics-supply-chain-dashboard | A map-tracking dashboard layout. It is the generic "map in a card" pattern we avoid, because our map is the canvas. |

- **Finding.** Figma Community has no energy or grid work at the level of R01–R10. The shipped products and newsrooms above are the real references. Figma's value here is component anatomy (Carbon) and a list of clichés to avoid.
- **Informs:** evidence chips and chart states (from Carbon). The rest is avoid-list material.

## 7. Everyday forecast idioms

### R30 Google Flights "price insights" and Google Maps "typical traffic"
- **Links:**
  - https://www.google.com/travel/flights
  - Maps traffic help: https://support.google.com/maps/answer/3092439
- **What:** Two forecast idioms that hundreds of millions of people already read.
- **Thumb:** none (described; both need a live search).
- **Borrow:**
  - **"Prices are currently low / typical / high"** with a range bar and a marker. For the Tomorrow card: "Tomorrow's carbon in Utah is **typical for October**", with a P10–P90 bar (validation year) and tomorrow's marker.
  - **"Typical traffic: Tue 6 PM"** with a day-and-time picker. For the grid clock: typical carbon and load for any weekday and hour.
- **Informs:** Tomorrow card, grid clock, evidence chips.

---

## Coverage by view

The reference to start from comes first.

| View | References | Pattern to start from |
|---|---|---|
| Grid clock | R17, R04, R03, R30, R20 | One bottom time scrubber drives every layer, with an "as of" stamp. Forecast is dotted or lighter after "now". |
| Load-curve story | R04, R05, R10, R15, R02 | A sticky 24-h chart. Actual vs forecast on one axis. One annotated wedge (ramp or peak) per step. |
| Map with arcs | R01, R19, R03, R22, R13 | Relief ground with hairline BA outlines. ≤ 10 labelled two-colour arcs, width = MWh. "Estimated" badges. |
| Move-vs-wait replay | R18, R10, R09, R20, R25 | Run-now vs routed drawn as before/after on one axis. Click a job for its decision trace. End in a sandbox. |
| Delay-budget slider | R11, R24, R23, R26 | The slider's own track shows "CO₂ saved vs allowed wait", with the 6 h knee. The live value is in the label. |
| Skeptic mode | R01, R11, R08, R24 | A three-step toggle: average → consumption → marginal. The guess-then-reveal opener comes from You Draw It. |
| Clean≠rush strips | R05, R07, R06 | Two aligned 24-h bands for the same day (carbon band, rush band) with a line on top. The mismatch is labelled. |
| Plan my run | R24, R14, R16, R27 | A scrubbable sentence feeds a decision and its consequence meter, answered with a plain-language analogy. |
| Tomorrow card | R06, R21, R30, R05, R07 | Issue time, a verdict sentence, avg/max/min, a typical-range bar, and one advisory. |
| Evidence chips | R08, R01, R03, R29 (Carbon) | A chip shows the label, source, window and method link, and expands into an OWID-style "About this data". |

## Avoid list

### AI tells (never)

- **Purple or violet gradients, neon on navy, gradient text.** Seen live on Octopus Agile's marketing page (R07).
- **Card-kit sameness.** Grids of equal rounded white cards, each with an icon, a big number and a tiny delta. Also the sidebar + KPI row + chart grid "admin template" layout, and bento grids. CAISO's icon KPI tiles (R04) are a mild case.
- **ALL-CAPS tracked eyebrows** above headings. Even OWID does it (R08); we don't. Use sentence-case labels.
- **Cream + serif + terracotta** "editorial warmth". OWID's serif + orange ramp is near it.
- **Glassmorphism and frosted panels over maps, glows, heavy drop shadows, hover-lift on every card.**
- **Decorative icons.** Lightbulb, bolt and leaf icons next to numbers; sparkle "AI" icons; emoji bullets.
- **Count-up number animations, bouncy easing, staggered fade-ins** on every element, and parallax.
- **Inter or Poppins everywhere with a 16 px radius and soft shadows.** That is the template look; each direction has its own type for a reason.
- **Illustrated hero scenes and mascots** (Octopus, the FT Climate Game cover). Our hero is a real curve or a real map.
- **Donut or gauge charts for a single number.**

### Weak patterns seen in the references (do not copy)

- **Dark basemaps by default:** Windy, kepler.gl, Flightradar24. We are light only.
- **Rainbow and spectral ramps:** Windy's wind scale, deck.gl's migration demo.
  - Use one single-hue sequential scale for carbon.
  - Use a diverging scale only around a real midpoint, such as Δ vs run-now.
- **Legend overload:** Energy-Charts' 20 series with struck-through entries. Name at most five series, and label lines directly.
- **Government chrome:** EIA's gear, info and download icons on every panel, 11 px type, and node-and-line clutter.
- **A gradient area fill under every line** (CAISO). Use a fill once, where the area itself means something (solar, or energy moved).
- **Map in a card** (the Figma logistics kits). The map is the canvas, not a widget.
- **Modals and overlays over data:** cookie walls, kepler's add-data modal. The demo has no modal on load.
- **Centred marketing hero blocks:** Carbon Intensity API, the Mapbox showcase.
- **Novelty display titles** (Pudding Climate Zones) and **WebGL showpieces with scroll-jacking** (Awwwards picks).
- **Fake precision** ("12,345.67 kg saved") and **unlabelled estimates.** Every number carries its evidence label; savings are rounded and shown with intervals.

## Per-direction notes

All three palettes share one constraint, measured with WCAG contrast on 2026-10-27:

| Colour | vs white | vs salt `#F4F7F8` | Use |
|---|---:|---:|---|
| B solar `#FFB703` | 1.75 | 1.62 | fill only, with dark text or outline |
| C sunrise `#F2A900` | 2.01 | 1.87 | fill only |
| A advisory yellow `#FFC72C` | 1.56 | 1.45 | fill only; black text on it is 12.1:1 |
| B peak red `#E63946` | 4.17 | 3.87 | marks yes (≥ 3:1); small text no (< 4.5:1); darken for text |
| B cobalt `#1636D9` | 8.19 | 7.61 | text and marks |
| C lake `#0F6E8C` | 5.79 | 5.37 | text and marks |
| C ember `#C8102E` | 5.88 | 5.46 | text and marks |
| A interstate green `#00703C` | 6.21 | 5.77 | text and marks; white text on it is 6.2:1 |
| A express blue `#0060A9` | 6.47 | 6.01 | text and marks |

- **The yellows fail 3:1 as marks on a light background.** In every direction, solar, sunrise or advisory yellow is a **fill** (bands, areas, sign panels), never a thin line, a small dot or text.
- **A's green and blue have almost the same luminance:** the contrast between them is 1.04:1. They cannot encode two data categories without a second channel such as shape, pattern or label.
- Every data palette still goes through the dataviz validator at U1, as the plan requires.

### B, Live Load Curve
- **Supporting references:**
  - R04 CAISO, R05 Energy-Charts, R10 NYT batteries and R02 Grid Status: the curve as the instrument;
  - R23 Distill and R26 Bartosz: the slider under the curve, and one colour per concept;
  - R11 rent-or-buy: sensitivity drawn on the slider.
- **Gap:** the "where" story (insight 1), which needs a map act. Take C's relief-map treatment for it (see below).
- **Type:**
  - Archivo's width axis does the hierarchy: SemiExpanded or Expanded for the hero number and the curve's annotations, normal width for UI.
  - Check that Archivo's tabular figures (`tnum`) render. If they don't, pair it with a mono that has tabular digits. The rubric allows one family plus one mono.
  - Use sentence case only.
- **Colour:**
  - Cobalt means "ours": the forecast line and the routed schedule.
  - Solar yellow is the area under the curve during clean solar hours. It is a fill.
  - Peak red is used only for the demand rush window. Use a darker red for any red text.
  - **Carbon needs its own sequential scale, separate from peak red.** Insight 2 says the dirty hours (coal nights) are not the rush hours, so they must not share a colour. Suggest a cool slate-to-coal ramp for carbon.
  - Add an ink and a three-step neutral ramp, so that colour stays for data.
- **Motion:**
  - The curve draws hour by hour only when the grid clock plays. A "now" cursor sweeps.
  - Run-now morphs into routed: the load moves from night to midday in about 300 ms.
  - Story mode is scroll-scrubbed. Nothing animates on load just to animate.

### C, Basin & Range
- **Supporting references:**
  - R22 Natural Earth relief, R01 Electricity Maps, R19 deck.gl arcs, R20 Mini Tokyo 3D, R16 Pudding (a light map under a few saturated colours), and R12 WaPo small multiples;
  - R21 UDOT for Utah place-names and roads.
- **Gap:** most map craft we found is dark (Windy, kepler, Flightradar24), so a light map has fewer proven precedents and more execution risk.
- **Type:**
  - Big Shoulders only at display sizes (≥ 24 px): place labels such as GREAT BASIN in sentence or title case, and big numerals.
  - Public Sans for everything else, with its tabular figures for numbers.
  - Big Shoulders at small sizes reads as condensed noise.
- **Colour:**
  - Salt `#F4F7F8` is the ground. The relief is multiplied at about 12–18 % opacity with a warm-gray tint.
  - BA outlines are hairlines. Only the hero region (PACE) and the selected destination are filled.
  - Lake `#0F6E8C` is water and clean destinations (BPAT hydro). Sunrise is solar hours, as a fill. Ember is coal and dirty hours.
  - Arcs run from ember (origin) to lake (cleaner destination); width = MWh moved.
- **Motion:**
  - Arcs carry moving dashes, with speed tied to MWh (deck.gl). The arc count stays at 10 or fewer.
  - **A soft daylight band crosses the West with the clock.** It is a light veil, not a dark night overlay. It ties solar hours to geography and to the headline "Compute follows the sun".
  - The relief never moves.

### A, Highway Advisory
- **Supporting references:**
  - R21 UDOT: Utah's own advisory vocabulary;
  - R05 Stromampel: a traffic light for electricity, which already names IT workloads;
  - R06 Carbon Intensity: the three-number day;
  - R30 Google: low / typical / high, and typical traffic at a time;
  - R07 Octopus: the publication ritual.
- **Gap:** the risk is signage kitsch.
- **Type:**
  - Overpass, which descends from Highway Gothic, for sign panels and headings.
  - **Overpass Mono** for numbers. It is the same family's tabular companion, so it fits the one-family-plus-a-mono rule.
- **Colour:** follow the sign code, so meaning is free:
  - interstate green = guide (move here, the destination);
  - advisory yellow = warning (rush hour), as a panel fill with black text;
  - express blue = information, which suits evidence chips;
  - red = stop or regulatory only.
  - Never put green and blue side by side as data categories (1.04:1). Pair them with a shape or a label.
- **Refinement:** **limit the signage to two components.**
  - The Tomorrow card is an overhead message sign, written in sentence case even on the sign, for example "Rush 5–8 PM · Cleanest around midday". The real hours come from the data.
  - The move and wait recommendations are guide signs.
  - Everything else (curve, map, strips) stays a quiet data canvas.
- **Motion:**
  - The message sign changes frame every 2–3 s, and holds still under `prefers-reduced-motion`.
  - **Waiting is a ramp meter:** jobs hold at the on-ramp until the clean window, as on Utah's freeway on-ramps. **Moving is an exit** to another route, BPAT or CISO.

### Open lanes for Astra's direction
- These references are not claimed as the core of A, B or C:
  - R25 Nicky Case and R14 FT: play first, with a sandbox;
  - R15 Reuters and R16 Pudding: editorial scrollytelling;
  - R27 Radio-Canada: a journey frame.
- A direction built around "a job's trip through tomorrow's grid" would be distinct from the other three.

## What the evidence favours

**B, Live Load Curve, refined with C's relief map for the "where" act and A's advisory voice in its copy.**

- **The curve is the native grammar of every credible grid product we checked:** CAISO, Energy-Charts, Grid Status, EIA, and the NYT battery story. Torus's judges read a net-load curve without a legend. A one-screen insight in five seconds is most likely on a curve.
- **Insight 2 (clean ≠ rush in Utah) is a time-of-day insight.** It lives on a 24-h axis: two aligned bands, with the solar trough set against the evening peak. B's palette already maps to it, once carbon gets its own scale.
- **Light-theme precedents for B are many and strong.** For C they are fewer, because the best map craft is dark. That makes C the riskier build in about 24 hours. A's metaphor fits the bounty's own words ("a traffic report for tomorrow's grid") and has a Utah precedent. But A's literal signage risks kitsch, and its green/blue pair cannot carry data.
- **The caveat is insight 1 (moving beats waiting).** It is a "where" insight: moving PACE work to BPAT, CISO or NEVP cuts average intensity by 94%, 66% and 42%, against at most 33% for waiting ≤ 24 h. These are validation-year, production-basis, average-CI figures with perfect foresight (`docs/data-profile/grid.md` §8). B alone under-serves it. So B's second act is a map, built with C's relief ground, hairline BAs and ember-to-lake arcs.
- **Confidence: medium.** It rests on reference evidence, not on mockups. The owner picks at G2, after the four mockups exist.

## Method and limits

- **Searches.** WebSearch, standard mode first. Extended mode was used where results were thin: Figma Community, award sites and Reuters. Pages were checked with WebFetch where it was allowed.
- **Screenshots.** Taken with `google-chrome --headless=new --disable-gpu --hide-scrollbars --window-size=1440,900 --screenshot` plus `--virtual-time-budget`.
  - Some pages were shot at a taller size and cropped (CAISO, Carbon Intensity, OWID) to show the chart instead of a cookie banner.
  - All were downscaled to 1200 px wide and palette-compressed with Pillow: 15 files, 2.17 MB in total, the largest 376 KB.
- **Not captured, because of bot walls:**
  - Cloudflare: Electricity Maps, Grid Status, Flightradar24, shadedrelief.com;
  - NYT (robot page), Bloomberg ("press & hold"), Tesla (Akamai);
  - Figma Community (HTTP 403).
  - No bot check was bypassed. Those entries are marked *described*.
- **Dead link found:** FiveThirtyEight's "Hack Your Way to Scientific Glory" (p-hacking) now redirects to ABC News. It was dropped as a skeptic-mode reference.
