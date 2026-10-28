/* View-only replay: all scenario values come from the pinned data bundle. */
(() => {
  'use strict';
  const D = window.PILOT_DATA;
  const scenes = ['primary', 'limited', 'storage'];
  let scene = 'primary';
  let aim = 'peak';
  const $ = (id) => document.getElementById(id);
  const value = (field) => field && typeof field === 'object' && 'value' in field ? field.value : field;
  const pct = (field) => (value(field) * 100).toFixed(1);
  const num = (field, digits = 0) => Number(value(field)).toLocaleString('en-US', {minimumFractionDigits: digits, maximumFractionDigits: digits});
  const esc = (text) => String(text).replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const badge = (text = 'SIMULATED') => `<span class="badge">${text}</span>`;
  const interval = (c) => value(c.saving_ci95).map(x => pct(x)).join('–');
  function fail() {
    $('error').hidden = false;
    $('content').hidden = true;
    document.querySelectorAll('button').forEach(b => { b.disabled = true; });
    document.documentElement.dataset.ready = 'error';
  }
  // Missing or incomplete packaging must never produce plausible-looking zeroes.
  try {
    if (!D || !D.source_commit || !D.sources || !D.baseline || !D.storage) throw new Error('Missing bundle');
    for (const key of ['primary', 'limited', 'timing']) {
      const c = D.routing[key].contrast;
      if (!Number.isFinite(value(c.saving)) || !Array.isArray(value(c.saving_ci95)) || value(c.saving_ci95).length !== 2) throw new Error('Missing contrast');
    }
    for (const key of ['peak', 'carbon']) {
      const m = D.storage.schedules[key].metrics;
      for (const field of ['cut_frac','rush_import_before_mw','rush_import_after_mw','peak_import_after_mw','flat_marginal_cut_t']) {
        if (!Number.isFinite(value(m[field]))) throw new Error('Missing storage result');
      }
    }
  } catch (error) {
    fail();
    return;
  }
  function plot() {
    const rows = [['primary', 'Eligible jobs may move', 'Fixed ranking · policy S'], ['limited', 'Only ≤ 8 GPUs may move', 'Same ranking · policy S'], ['timing', 'Wait in Utah only', 'Forecast policy W_time']];
    return `<div class="plot" aria-label="Attributed carbon reduction versus staying in Utah, with 95 percent intervals">${rows.map(([key, label, sub]) => {
      const c = D.routing[key].contrast;
      const [lo, hi] = value(c.saving_ci95);
      return `<div class="plot-row ${scene === key ? 'selected' : ''}"><div class="plot-label">${label}<small>${sub}</small></div><div class="track" aria-hidden="true"><div class="bar" style="width:${value(c.saving)/.30*100}%"></div><div class="whisker" style="left:${lo/.30*100}%;width:${(hi-lo)/.30*100}%"></div></div><div class="plot-value">${pct(c.saving)}%<span class="sr-only">; 95 percent interval ${interval(c)} percent</span></div></div>`;
    }).join('')}<div class="axis" aria-hidden="true"><span>0</span><span>10</span><span>20</span><span>30%</span></div></div><p class="chart-caption">Less attributed CO₂ vs stay in Utah (U). Whiskers: 95% intervals, paired 4-week block bootstrap; conditional on this one replay.</p>`;
  }
  function routing() {
    const limited = scene === 'limited';
    const r = D.routing[scene], c = r.contrast;
    return `<div class="decision"><div class="hero"><div class="eyebrow">${limited ? 'THE MOBILITY STRESS TEST' : 'THE ROUTING OPPORTUNITY'}</div><div>${badge()} ${limited ? badge('SECONDARY SCENARIO') : badge('REGISTERED PRIMARY')}</div><h2>${limited ? 'Small jobs move.<br>Most of the saving stays.' : 'Same work.<br>Cleaner place to run it.'}</h2><div class="big-number" data-metric="saving">${pct(c.saving)}<small>%</small></div><p class="metric-label">less attributed CO₂</p><p class="interval">95% interval: ${interval(c)}% · vs stay in Utah</p><p class="hero-note">${limited ? '<strong>Only the mobility rule changes.</strong> Jobs requesting more than 8 GPUs must stay in Utah. The fixed clean-region ranking is unchanged.' : '<strong>A simple policy is enough.</strong> The fixed clean-region ranking (S) uses training-year averages. Dynamic forecast search showed no aggregate benefit over S.'}</p></div><div class="visual"><div class="visual-top"><h3>Place matters more than waiting.</h3><span class="badge light-badge">SIMULATED</span></div>${plot()}<div class="insight"><div class="insight-number">${pct(D.workload.top_1pct_jobs_by_declared_gpu_h.energy_share)}<small>%</small></div><p>of execution energy sits in the largest 1% of jobs.<small>Ranked by declared GPU-hours · simulated energy under constant power assumptions. Large GPU-hour jobs are not necessarily large GPU-count jobs.</small></p></div></div></div><div class="takeaway"><span class="label">PILOT QUESTION</span><p>${limited ? 'Can your largest energy users actually move their data and checkpoints?' : 'Which jobs can run elsewhere without breaking residency or deadlines?'}</p><button data-next="${limited ? 'storage' : 'limited'}">${limited ? 'Explore storage →' : 'Restrict mobility →'}</button></div><div class="conditions"><p><strong>Same work, with a caveat.</strong> ${num(D.cohort.n_jobs)} replayed jobs; ${num(r.metrics.late_jobs)} deadline misses. Deadlines are met by construction using baseline bookings. Declared runtimes are exact; overruns are untested.</p><p><strong>Assumed flexibility.</strong> Mobility, spare capacity and transfer costs are scenario inputs. Attributed emissions use EIA consumption accounting; this is not a measured reduction in grid emissions.</p></div>`;
  }
  function storage() {
    const s = D.storage.schedules[aim], m = s.metrics;
    const before = value(m.rush_import_before_mw), after = value(m.rush_import_after_mw);
    return `<div class="decision"><div class="hero"><div class="eyebrow">THE STORAGE TRADEOFF</div><div>${badge('SIMULATED')} ${badge('ILLUSTRATIVE STORAGE')}</div><h2>${aim === 'peak' ? 'Give the evening rush<br>some breathing room.' : 'Aim at carbon.<br>Ease less of the rush.'}</h2><div class="big-number" data-metric="rush">${after.toFixed(2)}<small> MW</small></div><p class="metric-label">average cluster draw in grid rush hours</p><p class="interval">From ${before.toFixed(2)} MW without storage · ${num(D.storage.rush.n_hours)} measured rush hours</p><p class="hero-note"><strong>A separate Utah-only comparison.</strong> The same stay-in-Utah workload (U), with or without a battery. Routing savings are not added to these results.</p></div><div class="visual"><div class="visual-top"><h3>One battery. Choose its job.</h3><span class="badge light-badge">ASSUMED</span></div><p class="battery-spec">${num(D.storage.headline.e_mwh)} MWh / 1 MW · ${num(value(D.storage.assumptions.eta_default)*100)}% round-trip efficiency · assumed</p><div class="toggle" aria-label="Battery dispatch objective"><button data-aim="peak" aria-pressed="${aim === 'peak'}">Ease the grid rush</button><button data-aim="carbon" aria-pressed="${aim === 'carbon'}">Lower attributed carbon</button></div><div class="storage-bars"><div><p class="mini-title">Draw in grid rush hours</p><div class="storage-value">${after.toFixed(2)} <span>/ ${before.toFixed(2)} MW before</span></div><div class="power-track" aria-hidden="true"><i style="width:${after/before*100}%"></i></div><p class="storage-baseline">Zero-based bar · simulated average<br>Rush threshold fixed from training years</p></div><div><p class="mini-title">Attributed CO₂ reduction</p><div class="storage-value" data-metric="storage-carbon">${pct(m.cut_frac)}% <span>vs no battery</span></div><div class="storage-baseline">${num(m.cut_t, 1)} tonnes over the storage window<br>Simulated · no uncertainty interval supplied</div></div></div><div class="schedule"><div class="schedule-title"><span>Fixed daily schedule · assumed</span><span>Hour · America/Denver</span></div><div class="hours" role="img" aria-label="Charge hours ${value(s.charge_hours).join(', ')}; discharge hours ${value(s.discharge_hours).join(', ')}; other hours idle. America/Denver.">${Array.from({length:24}, (_, h) => {const mode = value(s.charge_hours).includes(h) ? 'charge' : value(s.discharge_hours).includes(h) ? 'discharge' : '';return `<div class="hour ${mode}" aria-hidden="true">${mode === 'charge' ? '+' : mode === 'discharge' ? '−' : '·'}</div>`;}).join('')}</div><div class="hour-axis" aria-hidden="true"><span>00</span><span>06</span><span>12</span><span>18</span><span>23</span></div><div class="legend"><span>+ Charge</span><span>− Discharge</span><span>· Idle</span></div></div><p class="storage-caution"><strong>The limit:</strong> the period’s peak site draw rises from ${num(m.peak_import_before_mw,2)} to ${num(m.peak_import_after_mw,2)} MW. A flat marginal accounting sensitivity adds ${num(-value(m.flat_marginal_cut_t))} t CO₂. This is not evidence of avoided emissions.</p></div></div><div class="takeaway"><span class="label">PILOT QUESTION</span><p>For the Utah load that stays, is the priority carbon or relief during the grid’s rush?</p><button id="inspect-storage">See the assumptions ↗</button></div><div class="conditions"><p><strong>Illustrative, not a Torus product model.</strong> ${num(D.storage.headline.e_mwh)} MWh / 1 MW battery, ${num(value(D.storage.assumptions.eta_default)*100)}% round-trip efficiency. Fixed training-year schedules; no capex, degradation or seconds-scale buffering.</p><p><strong>A different window.</strong> Storage: Nov 1, 2025–Oct 23, 2026 (UTC, ${num(value(D.storage.window.n_hours)/24)} days). Rush means PACE net load above the training-derived threshold; it is not the site’s annual peak.</p></div>`;
  }
  function evidence() {
    const isStorage = scene === 'storage';
    const source = isStorage ? 'results/test/extras.json' : D.routing[scene].source;
    const field = isStorage ? `storage.schedule_comparison.schedules.${aim}.cases.U.4` : D.routing[scene].field;
    const raw = isStorage ? D.storage.schedules[aim] : D.routing[scene];
    $('evidence-body').innerHTML = `<p>These are already-published outputs from the sealed replay. This prototype only selects and formats committed values; it does not run the scheduler, fit a model, or reopen the test window.</p><h3>Current view</h3><table><tbody><tr><th scope="row">Evidence</th><td>${isStorage ? 'Simulated storage illustration; assumed battery and schedule' : 'Simulated policy outcome; assumed mobility'}</td></tr><tr><th scope="row">File</th><td><code>${esc(source)}</code></td></tr><tr><th scope="row">Field</th><td><code>${esc(field)}</code></td></tr><tr><th scope="row">Run</th><td><code>${esc(isStorage ? D.storage.run_id : D.routing[scene].run_id)}</code></td></tr><tr><th scope="row">Snapshot</th><td><code>${D.source_commit}</code></td></tr><tr><th scope="row">Source SHA-256</th><td><code>${D.sources[source].sha256}</code></td></tr></tbody></table><h3>What is real, and what is assumed?</h3><ul><li><strong>Observed:</strong> historical EIA grid data. The consumption-basis carbon signal is modeled.</li><li><strong>Measured:</strong> public Acme/Seren workload durations and GPU counts. The replayed schedule and its energy and emissions are simulated.</li><li><strong>Assumed:</strong> job flexibility, exact runtimes, spare destination GPUs, transfer energy and delay. Baseline bookings protect deadlines; runtime overruns and removing reservations were not tested.</li><li><strong>Not demonstrated:</strong> live operator savings, avoided grid emissions, a retail energy bill, or hardware performance.</li></ul><h3>Scope and uncertainty</h3><p>Routing covers the frozen 358-day grid window, Nov 1, 2025 through Oct 24, 2026 UTC. Arrivals stop at ${esc(D.covered.arrivals[1])}; ${num(D.cohort.n_excluded)} late-arriving jobs are excluded equally so deadlines fit. Routing intervals use 2,000 paired block-bootstrap draws with 4-week blocks and are conditional on one replay. The mobility scenario is pre-registered secondary evidence. Storage has its own 357-day window and no supplied uncertainty interval.</p><p style="margin-top:12px">The storage panel uses the U baseline only; it is not a combined routing-plus-storage estimate. Its battery assumptions are inherited from <code>results/storage.json</code>; schedules and outcomes are the committed test-year extras. The schedule ribbon shows permitted hours, not actual dispatch or state of charge.</p><h3>Original evidence envelopes</h3><details><summary>Inspect the selected result and provenance</summary><pre>${esc(JSON.stringify(raw, null, 2))}</pre></details><h3>Reproduce this bundle</h3><p>From the repository root: <code>python3 prototype/tools/build-data.py</code>. The builder reads only the pinned Git objects in <code>prototype/source-commit.txt</code>. All source hashes are also in <code>prototype/sources.json</code>.</p>`;
  }
  function openEvidence() { evidence(); $('evidence').showModal(); }
  function render() {
    $('content').innerHTML = scene === 'storage' ? storage() : routing();
    document.querySelectorAll('button[data-scene]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.scene === scene)));
    document.documentElement.dataset.scene = scene;
    document.documentElement.dataset.aim = aim;
    document.documentElement.dataset.ready = '1';
    $('announcement').textContent = scene === 'storage' ? `Storage aimed at ${aim === 'peak' ? 'the grid rush' : 'carbon'}. Average rush-hour draw ${value(D.storage.schedules[aim].metrics.rush_import_after_mw).toFixed(2)} megawatts.` : `${scene === 'primary' ? 'Primary routing' : 'Restricted mobility'}: ${pct(D.routing[scene].contrast.saving)} percent less attributed carbon dioxide.`;
  }
  function select(next) { if (!scenes.includes(next)) throw new Error('Unknown chapter'); scene = next; render(); }
  document.querySelectorAll('button[data-scene]').forEach(b => b.addEventListener('click', () => select(b.dataset.scene)));
  $('content').addEventListener('click', event => {
    const b = event.target.closest('button'); if (!b) return;
    if (b.dataset.next) { select(b.dataset.next); document.querySelector(`button[data-scene="${scene}"]`).focus(); }
    else if (b.dataset.aim) { aim = b.dataset.aim; render(); document.querySelector(`button[data-aim="${aim}"]`).focus(); }
    else if (b.id === 'inspect-storage') openEvidence();
  });
  $('evidence-open').addEventListener('click', openEvidence);
  $('evidence-close').addEventListener('click', () => $('evidence').close());
  $('restart').addEventListener('click', () => { aim = 'peak'; select('primary'); });
  document.addEventListener('keydown', event => {
    if ($('evidence').open || event.altKey || event.ctrlKey || event.metaKey) return;
    if (!['ArrowLeft','ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const direction = event.key === 'ArrowRight' ? 1 : -1;
    select(scenes[Math.max(0, Math.min(2, scenes.indexOf(scene) + direction))]);
    document.querySelector(`button[data-scene="${scene}"]`).focus();
  });
  render();
})();
