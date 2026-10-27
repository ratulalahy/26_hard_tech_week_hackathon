import { useEffect, useMemo } from 'react';
import { setMid } from './lib/color';
import { Ev, Icon, SEALED } from './components/ui';
import { DESTS, asNum, dayCurve, type Core } from './lib/data';
import { loadResults } from './lib/data';
import { fmtHour, monthLabel } from './lib/format';
import { VIEWS, useApp } from './lib/store';
import { WestMap, type ArcSpec } from './map/WestMap';
import { Cockpit } from './views/Cockpit';
import { ControlRoom, controlPadding } from './views/ControlRoom';
import { MethodDrawer } from './views/MethodDrawer';
import { Ribbon } from './views/Ribbon';
import { Story } from './views/Story';
import { useViewport } from './lib/useViewport';

export function App() {
  const { data, error, view, set } = useApp();
  useEffect(() => {
    // the allowed wait starts at the registered flexible-job delay (manifest, assumed)
    loadResults().then((d) => {
      setMid(asNum(d.grid.reference?.us_avg_ci)); // the diverging midpoint: EIA's 2024 US average
      set({ data: d, maxWait: Math.round((asNum(d.manifest.assumptions.allowed_delay_s.SFT) ?? 21600) / 3600) });
    }).catch((e) => set({ error: String(e) }));
  }, [set]);

  return (
    <>
      <SharedMap />
      <TopBar />
      <main>
        {error ? <ErrorState msg={error} /> : !data ? <Loading /> : (
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
  const { data, view, hour, month, arcPolicy, dest, set } = useApp();
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
    if (!data) return [];
    const pol = data.jobs.week.policies[arcPolicy];
    if (!pol) return [];
    if (!on) return []; // no arcs in the watermark
    const gh = (a: { gpu_h: { value: number } }) => a.gpu_h.value ?? 0;
    const max = Math.max(...pol.arcs.map(gh), 1), tot = pol.arcs.map(gh).reduce((x: number, y: number) => x + y, 0) || 1;
    return DESTS.flatMap((d) => {
      const a = pol.arcs.find((x: { to: string }) => x.to === d);
      const g = a ? gh(a) : 0;
      if (g / tot < 0.01) return []; // arcs under 1% of the week's moved GPU-hours are not drawn
      return [{ to: d, weight: Math.sqrt(g / max), label: `${Math.round(g).toLocaleString('en-US')} GPU-h`, selected: d === dest }];
    });
  }, [data, arcPolicy, dest, on]);
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
        <span className="t-11 ink-2 fw-500 inline-flex items-center gap-2 whitespace-nowrap" style={{ padding: '0 8px', height: 24, borderRadius: 8, boxShadow: 'inset 0 0 0 1px var(--hair)' }}>
          <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1.5" /><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" /></svg>
          {SEALED}
        </span>
        <button className="btn whitespace-nowrap" onClick={() => set({ drawer: true })}><Icon name="doc" />Method &amp; evidence</button>
      </div>
    </header>
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
  return (
    <footer className="fixed z-20 flex gap-4 t-11 ink-3 whitespace-nowrap overflow-hidden" style={{ left: 24, right: 24, bottom: 4, height: 16 }}>
      <span className="min-[1600px]:hidden">Hours in America/Denver time. Validation year data.</span>
      <span className="hidden min-[1600px]:inline"><b className="fw-500 ink-2">Data:</b> EIA-930 hourly balance and EIA consumption-basis CO₂, validation year (Nov 2024 – Oct 2025). Jobs: simulated replay of a measured trace. Hours are America/Denver.</span>
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
        <p className="t-13 ink-2" style={{ margin: '8px 0 0' }}>{msg}. The dashboard reads <code>data/results/*.json</code> next to <code>index.html</code>. Serve the built folder with <code>npm run preview</code> (opening the file directly does not work), or run <code>npm run data</code> and rebuild.</p>
        <div style={{ marginTop: 8 }}><Ev e="observed">no numbers are shown until the evidence loads</Ev></div>
      </div>
    </div>
  );
}
