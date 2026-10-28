import { useEffect, useMemo } from 'react';
import { setMid } from './lib/color';
import { Icon } from './components/ui';
import { testOptionLabel, windowCopy, type EvalWindow } from './lib/copy';
import { asNum, dayCurve, type Core } from './lib/data';
import { arcsOf, flowOf } from './components/flows';
import { loadIndex, loadResults } from './lib/data';
import { fmtHour, monthLabel } from './lib/format';
import { VIEWS, useApp } from './lib/store';
import { WestMap, type ArcSpec } from './map/WestMap';
import { Cockpit } from './views/Cockpit';
import { ControlRoom, controlPadding } from './views/ControlRoom';
import { MethodDrawer } from './views/MethodDrawer';
import { Ribbon } from './views/Ribbon';
import { Story } from './views/Story';
import { Outlook } from './pages/Outlook';
import { useViewport } from './lib/useViewport';

export function App() {
  const { data, error, view, evalWindow, set } = useApp();
  useEffect(() => {
    loadIndex().then((idx) => set({ testIndex: idx.test ?? null }));
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
      <SharedMap />
      <TopBar />
      <main>
        {/* T19 hook: the outlook is standalone (its own data), so it renders before the results load */}
        {view === 'outlook' ? <Outlook /> : error ? <ErrorState msg={error} /> : !data ? <Loading /> : (
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
  const { data, view, hour, month, arcPolicy, dest, scenario, set } = useApp();
  const vp = useViewport();
  const on = view === 'control';
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

function TopBar() {
  const { view, set } = useApp();
  return (
    <header className="panel over-map fixed z-30 flex items-center" style={{ top: 12, left: 16, right: 16, height: 48, padding: '0 8px 0 12px', borderRadius: 16 }}>
      <a href="#control" className="flex items-center gap-2" style={{ color: 'inherit', textDecoration: 'none' }}>
        <Mark />
        <span className="t-15" style={{ fontFamily: 'var(--font-display)', fontWeight: 600 }}>GridPilot</span>
        <span className="t-12 ink-3 whitespace-nowrap" style={{ marginLeft: 4 }}>Utah's grid, for AI jobs</span>
      </a>
      <nav className="tabs absolute" style={{ left: '50%', transform: 'translateX(-50%)' }} aria-label="Views">
        {VIEWS.map((v) => (
          <a key={v.id} href={`#${v.id}`} aria-current={view === v.id ? 'page' : undefined}>{v.label}</a>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-2">
        {view !== 'outlook' && <WindowSwitch />}{/* T19: the outlook reads its own file; the year switch does nothing there */}
        <button className="btn whitespace-nowrap" onClick={() => set({ drawer: true })}><Icon name="doc" />Method &amp; evidence</button>
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
        <Lock />{testOptionLabel(testIndex?.frozen_at)}
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

function Footer() {
  const { data, evalWindow } = useApp();
  const c = windowCopy(data ? evalWindow : 'validation', data?.manifest);
  return (
    <footer className="fixed z-20 flex gap-4 t-11 ink-3 whitespace-nowrap overflow-hidden" style={{ left: 24, right: 24, bottom: 4, height: 16 }}>
      <span className="min-[1600px]:hidden">{c.footShort}</span>
      <span className="hidden min-[1600px]:inline"><b className="fw-500 ink-2">Data:</b> {c.footLong} Jobs: simulated replay of a measured trace. Hours are America/Denver.</span>
      <span className="ml-auto">BA boundaries © Electricity Maps contributors (AGPL-3.0). BA codes: U.S. EIA Form EIA-930. Basemap: Natural Earth.</span>
    </footer>
  );
}

function Loading() {
  return (
    <div className="fixed z-10" style={{ top: 'var(--top)', left: 16, width: 360, bottom: 40 }} aria-busy="true" aria-label="Loading results">
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
