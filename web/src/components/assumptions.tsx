// "Assumptions & what didn't work" (Stage 3 T17, D-068): the register, the negative results and the
// weather point from results/assumptions.json, which notebooks/40_assumptions_and_reality.ipynb builds
// from the other results files. Its sentences are pre-rendered there from enveloped numbers (each with
// a file#/json/pointer provenance, re-checked by lab/tests/test_assumptions.py); the evidence chips
// here are read from those envelopes.
import type { Evidence, Json } from '../lib/data';
import { pname, stripCodes } from '../lib/data';
import { Ev, ScrollX } from './ui';

const ORDER: Evidence[] = ['observed', 'measured', 'forecast', 'modeled', 'assumed', 'simulated'];

/** The evidence classes of every envelope inside `x`, in the canonical order. */
export function evidenceOf(x: Json): Evidence[] {
  const out = new Set<Evidence>();
  const walk = (v: Json) => {
    if (v && typeof v === 'object') {
      if (!Array.isArray(v) && 'value' in v && 'evidence' in v) { out.add(v.evidence); return; }
      for (const c of Array.isArray(v) ? v : Object.values(v)) walk(c);
    }
  };
  walk(x);
  return ORDER.filter((e) => out.has(e));
}

const plain = (s: string) => stripCodes(s).replace(/\s+([.;,])/g, '$1');

function Chips({ x }: { x: Json }) {
  return <>{evidenceOf(x).map((e) => <Ev key={e} e={e} />)}</>;
}

export function AssumptionsSection({ a }: { a: Json }) {
  const reg: Json[] = a.register ?? [], neg: Json[] = a.negative_results ?? [], w = a.weather;
  return (
    <div className="flex flex-col gap-3" data-testid="method-assumptions">
      <p className="t-12 ink-2" style={{ margin: 0 }}>
        What the result rests on, how the real world differs, and what we checked. Built only from the committed results (evidence notebook 40); no new simulation.
        A tested row gives the check's result, an untested one says why not. Savings are against {pname('U')}, with 95% intervals in brackets.
      </p>
      <ScrollX label="Assumptions register, table">
        <table className="tbl tbl-text" data-testid="assumptions-register">
          <thead>
            <tr><th style={{ width: '30%' }}>Assumption · our value</th><th style={{ width: '28%' }}>How reality differs</th><th>Tested? · result</th></tr>
          </thead>
          <tbody>
            {reg.map((r) => (
              <tr key={r.id}>
                <td data-label="Assumption · our value">
                  <div className="fw-500">{r.assumption}</div>
                  <div className="ink-2">{plain(r.value_text)}</div>
                  <div style={{ marginTop: 2 }}><Ev e={r.evidence} /></div>
                </td>
                <td className="ink-2" data-label="How reality differs">{r.reality}</td>
                <td data-label="Tested? · result">
                  <span className={r.tested ? 'chip-neutral fw-600' : 'chip-neutral'}>{r.tested ? 'tested' : 'not tested'}</span>{' '}
                  {plain(r.result_text)}
                  <div className="flex flex-wrap gap-2" style={{ marginTop: 2 }}><Chips x={r.results} /></div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollX>
      <div>
        <h4 className="t-13 fw-600" style={{ margin: '0 0 4px' }}>What didn't work, stated plainly</h4>
        <ul className="t-13" style={{ margin: 0, paddingLeft: 16 }} data-testid="assumptions-negative">
          {neg.map((n) => (
            <li key={n.id} style={{ marginBottom: 4 }}>
              <b className="fw-600">{n.title}.</b> <span className="ink-2">{plain(n.statement)}</span> <Chips x={n.values} />
            </li>
          ))}
        </ul>
      </div>
      {w ? <div className="well" style={{ padding: 12 }}>
        <h4 className="t-13 fw-600" style={{ margin: '0 0 4px' }}>Would weather-aware forecasts help?</h4>
        <p className="t-13" style={{ margin: 0 }} data-testid="assumptions-weather">
          <span className="ink-2">{plain(w.statement)}</span> <b className="fw-600">{w.conclusion}</b> <Chips x={w.values} />
        </p>
      </div> : null}
    </div>
  );
}
