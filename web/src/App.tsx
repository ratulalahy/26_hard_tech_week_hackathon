import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { setMid } from './lib/color';
import { Icon } from './components/ui';
import { testOptionLabel, windowCopy, type EvalWindow } from './lib/copy';
import { asNum, dayCurve, type Core } from './lib/data';
import { arcsOf, flowOf } from './components/flows';
import { loadIndex, loadResults } from './lib/data';
import { fmtHour, monthLabel } from './lib/format';
import { PAGES, VIEWS, WINDOWED, useApp, type Page } from './lib/store';
import { WestMap, type ArcSpec } from './map/WestMap';
import { Cockpit } from './views/Cockpit';
import { ControlRoom, controlPadding } from './views/ControlRoom';
import { MethodDrawer } from './views/MethodDrawer';
import { Ribbon } from './views/Ribbon';
import { Story } from './views/Story';
import { Outlook } from './pages/Outlook';
import { Prices } from './pages/Prices';
import { Regions } from './pages/Regions';
import { Monitor } from './pages/Monitor';
import { Evidence } from './pages/Evidence';
import { useViewport } from './lib/useViewport';

const TITLE: Record<Page, string> = {
  story: "GridPilot: Utah's grid, for AI jobs", monitor: 'GridPilot · Monitor', outlook: 'GridPilot · Outlook',
  regions: 'GridPilot · Ten regions', prices: 'GridPilot · Prices', evidence: 'GridPilot · Method and evidence',
};

/** The nav shell (T21): one top bar, one page at a time. Story is the dashboard (its four views and the
 * #story-N beats); the other pages are standalone and load their own files, except Evidence, which shows
 * the method content for the window the year switch selects. */
export function App() {
  const { data, error, view, page, evalWindow, set } = useApp();
  useEffect(() => { document.title = TITLE[page]; }, [page]);
  useEffect(() => {
    // a test year asked for by ?year=test or remembered, but absent from this build, falls back to validation
    loadIndex().then((idx) => set({ testIndex: idx.test ?? null, ...(!idx.test?.available && useApp.getState().evalWindow === 'test' ? { evalWindow: 'validation' } : {}) }));
  }, [set]);
  useEffect(() => {
    // One window's results at a time (T11 B6): validation, or the sealed test year once it is run.
    let live = true;
    set({ data: null, error: null });
    // the allowed wait starts at the registered flexible-job delay (manifest, assumed)
    loadResults(evalWindow).then((d) => {
      if (!live) return;
      setMid(asNum(d.grid.reference?.us_avg_ci)); // the diverging midpoint: EIA's 2024 US average
      const month = useApp.getState().month;
      set({
        data: d, maxWait: Math.round((asNum(d.manifest.assumptions.allowed_delay_s.SFT) ?? 21600) / 3600),
        // keep the month when this window has it; otherwise its weekday-load month
        month: d.grid.months.includes(month) ? month : (d.grid.pace_july_weekday?.month ?? d.grid.months[0]),
      });
    }).catch((e) => { if (live) set({ error: String(e) }); });
    return () => { live = false; };
  }, [evalWindow, set]);

  return (
    <>
      {page !== 'regions' && <SharedMap />}{/* Regions draws its own full-colour map */}
      <TopBar />
      <main>
        {page === 'outlook' ? <Outlook /> : page === 'prices' ? <Prices /> : page === 'regions' ? <Regions /> : page === 'monitor' ? <Monitor />
          : error ? <ErrorState msg={error} /> : !data ? <Loading /> : page === 'evidence' ? <Evidence /> : (
            <>
              {view === 'control' && <ControlRoom />}
              {view === 'cockpit' && <Cockpit />}
              {view === 'ribbon' && <Ribbon />}
              {view === 'story' && <Story />}
              <MethodDrawer />
            </>
          )}
      </main>
      <Footer />
    </>
  );
}

/** The one shared map: full colour on the Control room, a faint watermark everywhere else. */
function SharedMap() {
  const { data, view, page, hour, month, arcPolicy, dest, scenario, set } = useApp();
  const vp = useViewport();
  const on = page === 'story' && view === 'control';
  const ci = useMemo(() => {
    if (!data) return {} as Record<string, number | null>;
    return Object.fromEntries((['PACE', 'BPAT', 'CISO', 'NEVP'] as Core[]).map((c) => [c, dayCurve(data.grid, c, month)[hour]]));
  }, [data, hour, month]);
  const context = useMemo(() => {
    if (!data) return {};
    return Object.fromEntries(Object.entries(data.grid.context_year_mean_ci.by_ba).map(([k, e]) => [k, asNum(e as never)]));
  }, [data]);
  const arcs = useMemo<ArcSpec[]>(() => {
    if (!data || !on) return []; // no arcs in the watermark
    // T15: the toggled scenario's replay-week arcs (scenario-flows.json); the registered job-replay.json week otherwise
    const f = flowOf(data.flows, scenario, arcPolicy);
    if (f) return arcsOf(f, dest);
    const pol = data.jobs.week.policies[arcPolicy];
    return pol ? arcsOf({ week_arcs: pol.arcs }, dest) : [];
  }, [data, arcPolicy, dest, on, scenario]);
  return (
    <div className={`scene ${on ? '' : 'watermark'}`} aria-hidden={!on} inert={!on}>
      {data && (
        <WestMap id="map-main" variant="main" interactive={on} frozen={!on} ci={ci} context={context} hourLabel={`${fmtHour(hour)}, ${monthLabel(month)}`} arcs={arcs}
          padding={controlPadding(vp)} onPick={(d) => set({ dest: d })} />
      )}
    </div>
  );
}

/** The one top bar: the pages, the Story page's views, and the year switch where it applies. Below 1100 px
 * it wraps to two rows and each nav scrolls sideways on its own (no overlap at phone width). */
function TopBar() {
  const { view, page, set } = useApp();
  const story = page === 'story';
  // every page sits below the bar: --top follows the bar's height (48 px on one row → 72 px, as before; more
  // when it wraps at narrow widths), so nothing slides under it
  const ref = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const put = () => document.documentElement.style.setProperty('--top', `${Math.round(el.getBoundingClientRect().height) + 24}px`);
    put();
    const ro = new ResizeObserver(put);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <header ref={ref} className="panel over-map topbar">
      <a href="#control" className="topbar-brand">
        <Mark />
        <span className="t-15" style={{ fontFamily: 'var(--font-display)', fontWeight: 600 }}>GridPilot</span>
        <span className="t-12 ink-3 whitespace-nowrap topbar-tag">Utah's grid, for AI jobs</span>
      </a>
      <nav className="tabs topbar-pages" aria-label="Pages">
        {PAGES.map((p) => (
          <a key={p.id} href={p.id === 'story' ? `#${view}` : `#${p.id}`} aria-current={page === p.id ? 'page' : undefined}>{p.label}</a>
        ))}
      </nav>
      {story && (
        <nav className="tabs tabs-sub topbar-views" aria-label="Views">
          {VIEWS.map((v) => (
            <a key={v.id} href={`#${v.id}`} aria-current={view === v.id ? 'page' : undefined}>{v.label}</a>
          ))}
        </nav>
      )}
      <div className="topbar-end">
        {WINDOWED.includes(page) && <WindowSwitch />}{/* the other pages read their own files; the year switch does nothing there */}
        {story && <button className="btn whitespace-nowrap" onClick={() => set({ drawer: true })} aria-label="Method & evidence"><Icon name="doc" /><span className="topbar-btn-text">Method &amp; evidence</span></button>}
      </div>
    </header>
  );
}

const Lock = () => (
  <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1.5" /><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" /></svg>
);

/** The evaluation-window switch (T11 B6): the validation year, or the sealed test year. The test option is
 * enabled only when copy-data found results/test/manifest.json. The status line of the window shown is its
 * accessible description. */
function WindowSwitch() {
  const { evalWindow, testIndex, data, set } = useApp();
  const testOn = !!testIndex?.available;
  const pick = (w: EvalWindow) => () => { if (w !== evalWindow) set({ evalWindow: w, drawer: false }); };
  const status = data ? windowCopy(evalWindow, data.manifest).chip : '';
  return (
    <div className="seg" role="radiogroup" aria-label="Evaluation window" aria-describedby="window-status" data-testid="window-switch">
      <span id="window-status" hidden>{status}</span>
      <button role="radio" aria-checked={evalWindow === 'validation'} onClick={pick('validation')}>Validation year</button>
      <button role="radio" aria-checked={evalWindow === 'test'} disabled={!testOn} onClick={pick('test')}
        title={testOn ? 'The sealed test year, evaluated once after the configuration freeze' : 'Sealed: the test year is evaluated once, after the configuration freeze, through the logged entry point'}>
        <Lock />{testOptionLabel(testIndex?.frozen_at, testOn)}
      </button>
    </div>
  );
}

function Mark() {
  // the diverging carbon scale, folded into a mark
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
      <rect x="1" y="1" width="20" height="20" rx="6" fill="#fff" stroke="rgba(110,62,30,.18)" />
      <rect x="5" y="12" width="3" height="5" rx="1" fill="#298954" />
      <rect x="9.5" y="9" width="3" height="8" rx="1" fill="#f5c79f" />
      <rect x="14" y="5" width="3" height="12" rx="1" fill="#c6481c" />
    </svg>
  );
}

/** The data line follows the page: the year switch's window on Story and Evidence, the sealed test year on
 * the Monitor, and each standalone page's own window (stated on the page) elsewhere. */
const FOOT: Partial<Record<Page, { short: string; long: string }>> = {
  monitor: { short: 'Hours in America/Denver time. Sealed test year, simulated replay.', long: 'EIA consumption-basis CO₂ and a simulated replay of a measured GPU-cluster trace, sealed test year (opened once).' },
  outlook: { short: 'Hours in America/Denver time. The data window is stated on the page.', long: 'EIA-930 and EIA consumption-basis CO₂; the issue date and data window are stated on the page.' },
  regions: { short: 'Hours in each region\'s own clock. Validation data.', long: 'EIA-930 and EIA consumption-basis CO₂, validation profiles and forecasts (the test year stays sealed here).' },
  prices: { short: 'Hours in America/Denver time. Validation year data.', long: 'CAISO/WEIM real-time LMP on the registered validation ledgers; a wholesale scenario, not a bill.' },
};
function Footer() {
  const { data, evalWindow, page } = useApp();
  const w = windowCopy(data ? evalWindow : 'validation', data?.manifest);
  const f = FOOT[page];
  const c = f ? { footShort: f.short, footLong: f.long } : w;
  return (
    <footer className="fixed z-20 flex gap-4 t-11 ink-3 whitespace-nowrap overflow-hidden" style={{ left: 24, right: 24, bottom: 4, height: 16 }}>
      <span className="min-[1600px]:hidden">{c.footShort}</span>
      <span className="hidden min-[1600px]:inline"><b className="fw-500 ink-2">Data:</b> {c.footLong}{f ? '' : ' Jobs: simulated replay of a measured trace.'} Hours are America/Denver{page === 'regions' ? ' unless a region\'s clock is named' : ''}.</span>
      <span className="ml-auto">BA boundaries © Electricity Maps contributors (AGPL-3.0). BA codes: U.S. EIA Form EIA-930. Basemap: Natural Earth.</span>
    </footer>
  );
}

function Loading() {
  return (
    <div className="fixed z-10" style={{ top: 'var(--top)', left: 16, width: 'min(360px, calc(100vw - 32px))', bottom: 40 }} aria-busy="true" aria-label="Loading results">
      <div className="panel flex flex-col gap-3" style={{ height: '100%' }}>
        <span className="skel" style={{ width: '70%', height: 20 }} />
        <span className="skel" style={{ width: '45%', height: 32 }} />
        <span className="skel" style={{ width: '90%', height: 12 }} />
        <span className="skel" style={{ width: '100%', height: 140, borderRadius: 12 }} />
        {[0, 1, 2, 3].map((i) => <span key={i} className="skel" style={{ width: '100%', height: 48, borderRadius: 12 }} />)}
      </div>
    </div>
  );
}

function ErrorState({ msg }: { msg: string }) {
  return (
    <div className="fixed inset-0 z-10 grid place-items-center">
      <div className="panel" style={{ maxWidth: 480 }}>
        <div className="t-15">The results files did not load</div>
        <p className="t-13 ink-2" style={{ margin: '8px 0 0' }}>{msg}. The dashboard reads <code>data/results/*.json</code> next to <code>index.html</code>. Serve the built folder with <code>npm run preview</code> (opening the file directly does not work), or run <code>npm run data</code> and rebuild. No numbers are shown until the results load.</p>
      </div>
    </div>
  );
}
