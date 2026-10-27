// The water footprint illustration (Stage 3 T14, D-063), from results/water.json: one compact panel for
// the method drawer and the one-line story fact. Illustrative and modeled; never the registered result.
import { Ev } from './ui';
import { CORE, REGION, pname, type Json } from '../lib/data';
import { fmt, MINUS } from '../lib/format';

const V = (e: Json): number => (e && typeof e.value === 'number' ? e.value : NaN);
const POL = ['U', 'S', 'W', 'L'];
/** million gallons, two decimals */
const mg = (g: number) => fmt(g / 1e6, 2);
/** signed million gallons, two decimals */
const smg = (g: number) => (g > 0 ? '+' : g < 0 ? MINUS : '') + fmt(Math.abs(g) / 1e6, 2);
/** "−0.61 to −0.60" or one value when both ends print the same */
const span = (r: number[]) => (smg(r[0]) === smg(r[1]) ? smg(r[0]) : `${smg(r[0])} to ${smg(r[1])}`);

export function waterFacts(w: Json) {
  const h = w.headline;
  return { exSpan: span(h.change_ex_hydro_gal.value), withSpan: span(h.change_with_hydro_gal.value), movers: h.policies as string[], days: Math.round(V(w.window.n_hours) / 24) };
}

/** The one line in story beat 6. */
export function WaterLine({ w }: { w: Json }) {
  const f = waterFacts(w);
  return (
    <span className="block t-12 ink-2" style={{ marginTop: 8 }} data-testid="story-water">
      Moving work also shifts its water footprint: {f.exSpan} million gallons over the {f.days}-day validation window on the fuel mix alone, but {f.withSpan} million if hydro reservoir evaporation is counted (illustrative).
    </span>
  );
}

/** The method drawer's water panel. */
export function WaterPanel({ w }: { w: Json }) {
  const f = waterFacts(w);
  const p = w.policies, fac = w.factors, ib = w.intensity.by_ba;
  const u = p.U;
  const d = (k: string) => fac[k].median.value;
  return (
    <>
      <p className="t-13" style={{ margin: 0 }} data-testid="method-water">
        Generation-associated water: each hour's EIA-930 fuel mix in each region, weighted by NREL median operational water <i>consumption</i> per MWh, priced on the same hourly energy as the carbon accounting for {POL.map(pname).join(', ')}. Over the {f.days}-day validation window, moving work changes it by <b className="fw-600">{f.exSpan} million gallons</b> without hydro evaporation and <b className="fw-600">{f.withSpan} million</b> with it: the Northwest's hydro carries a large, uncertain evaporation allocation, so the sign depends on it. <span className="chip-neutral">illustrative</span> <Ev e="modeled">intensity</Ev> <Ev e="simulated">gallons</Ev>
      </p>
      <div style={{ overflowX: 'auto', marginTop: 8 }} tabIndex={0} role="region" aria-label="Water by policy">
        <table className="tbl" data-testid="water-table">
          <caption className="t-12 ink-3" style={{ captionSide: 'top', textAlign: 'left', paddingBottom: 4 }}>Million gallons over the {f.days}-day validation window (not annualised); change against {pname('U')}</caption>
          <thead><tr><th>Policy</th><th>Fuel mix, no hydro</th><th>Hydro evaporation</th><th>With hydro</th><th>Change, no hydro</th><th>Change, with hydro</th></tr></thead>
          <tbody>
            {POL.filter((k) => p[k]).map((k) => {
              const g = p[k].generation_gal, c = p[k].change_vs_U;
              return (
                <tr key={k}>
                  <td>{pname(k)}</td>
                  <td>{mg(V(g.ex_hydro))}</td>
                  <td>{mg(V(g.hydro_evap))}</td>
                  <td>{mg(V(g.with_hydro))}</td>
                  <td>{k === 'U' ? '–' : smg(V(c.ex_hydro_gal))}</td>
                  <td>{k === 'U' ? '–' : smg(V(c.with_hydro_gal))}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ overflowX: 'auto', marginTop: 8 }} tabIndex={0} role="region" aria-label="Water by site">
        <table className="tbl" data-testid="water-sites">
          <caption className="t-12 ink-3" style={{ captionSide: 'top', textAlign: 'left', paddingBottom: 4 }}>By site: million gallons, no hydro / with hydro (each move's transfer energy half at home, half at the destination)</caption>
          <thead><tr><th>Site</th>{POL.filter((k) => p[k]).map((k) => <th key={k}>{k}</th>)}<th>Mean intensity, gal/MWh</th></tr></thead>
          <tbody>
            {CORE.map((s) => (
              <tr key={s}>
                <td>{REGION[s].name}</td>
                {POL.filter((k) => p[k]).map((k) => { const b = p[k].generation_gal.by_site[s]; return <td key={k}>{mg(V(b.ex_hydro))} / {mg(V(b.with_hydro))}</td>; })}
                <td>{fmt(V(ib[s].mean_ex_hydro_gal_mwh))} / {fmt(V(ib[s].mean_with_hydro_gal_mwh))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="t-13 ink-2" style={{ margin: '8px 0 0', paddingLeft: 16 }}>
        <li>Factors, gal/MWh (NREL/TP-6A20-50900, Tables 1–2, medians): coal {fmt(d('coal_tower_generic'))} and nuclear {fmt(d('nuclear_tower'))} with cooling towers, gas combined cycle {fmt(d('gas_tower_cc'))}, solar PV {fmt(d('pv'))}, wind {fmt(d('wind'))}; hydro, in-stream and reservoir evaporation, {fmt(d('hydro'))} (published range {fmt(V(fac.hydro.min))}–{fmt(V(fac.hydro.max))}: with hydro, {pname('W')} would total {mg(V(p.W?.generation_gal.with_hydro_at_hydro_min))}–{mg(V(p.W?.generation_gal.with_hydro_at_hydro_max))} million). Which technology stands for each fuel is our choice; storage counts as zero, "other" takes the hour's average. <Ev e="observed">factors</Ev> <Ev e="assumed">mapping</Ev></li>
        <li>Direct cooling, shown separately: IT energy × {fmt(V(w.wue.low), 2)}–{fmt(V(w.wue.high), 2)} L/kWh, the U.S.-average site water use in 2023 <Ev e="observed">0.36</Ev> to the upper end of LBNL's 2028 scenario <Ev e="assumed">0.48, published scenario</Ev> (LBNL 2024 report, p. 48), one range for every site: {mg(V(u.direct_cooling_gal.low))}–{mg(V(u.direct_cooling_gal.high))} million gallons for {pname('U')}; moving changes it only through the transfer energy ({pname('W')}: +{fmt(V(p.W?.direct_cooling_gal.change_vs_U_low) / 1000)}–{fmt(V(p.W?.direct_cooling_gal.change_vs_U_high) / 1000)} thousand gallons). <Ev e="assumed">range</Ev></li>
        <li>For scale: LBNL puts the U.S. grid average at {fmt(V(w.context.lbnl_us_grid_l_per_kwh), 2)} L/kWh (about {fmt(Math.round(V(w.context.lbnl_us_grid_gal_per_mwh) / 10) * 10)} gal/MWh) by a different, consumption-flow method; Utah's mix here averages {fmt(V(ib.PACE.mean_ex_hydro_gal_mwh))} gal/MWh without hydro, {fmt(V(ib.PACE.mean_with_hydro_gal_mwh))} with. <Ev e="observed">LBNL</Ev></li>
      </ul>
      <h4 className="t-13 fw-600" style={{ margin: '12px 0 4px' }}>Caveats</h4>
      <ul className="t-13" style={{ margin: 0, paddingLeft: 16 }} data-testid="water-caveats">
        {(w.caveats as string[]).map((c) => <li key={c}>{c}</li>)}
      </ul>
    </>
  );
}
