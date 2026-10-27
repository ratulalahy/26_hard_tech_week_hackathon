'use strict';
const D=window.PROTOTYPE_DATA;
const $=s=>document.querySelector(s);
const number=(x,n=1)=>Number(x).toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n});
const pct=x=>number(x*100);
const names={PACE:'Utah',BPAT:'Northwest',CISO:'California',NEVP:'Nevada'};
const colors={PACE:'#b95a36',BPAT:'#23744f',CISO:'#789c77',NEVP:'#d8c6a3'};
const project=([lon,lat])=>[(lon+128)*20+65,(51-lat)*22+12];
const svgEl=(name,attrs={},text)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',name);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e};
function geoPath(geometry){const polys=geometry.type==='Polygon'?[geometry.coordinates]:geometry.coordinates;return polys.map(p=>p.map(r=>r.map((c,i)=>(i?'L':'M')+project(c).map(x=>x.toFixed(1)).join(',')).join(' ')+'Z').join(' ')).join(' ')}
function makeMap(){
 const svg=$('#region-map');
 const defs=svgEl('defs');
 const gradient=svgEl('radialGradient',{id:'map-atmosphere'});gradient.append(svgEl('stop',{offset:'0%','stop-color':'#dfe8d5','stop-opacity':'.6'}),svgEl('stop',{offset:'100%','stop-color':'#eaf0df','stop-opacity':'0'}));defs.append(gradient);
 const marker=svgEl('marker',{id:'arrow',viewBox:'0 0 10 10',refX:8,refY:5,markerWidth:5,markerHeight:5,orient:'auto-start-reverse'});marker.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#265bc4'}));defs.append(marker);svg.append(defs);
 svg.append(svgEl('ellipse',{cx:350,cy:238,rx:260,ry:230,fill:'url(#map-atmosphere)'}));
 const g=svgEl('g',{'stroke-linejoin':'round'});
 D.geo.states.features.forEach(f=>g.append(svgEl('path',{d:geoPath(f.geometry),fill:'#e9eddf','fill-opacity':'.8',stroke:'#c9d1c0','stroke-width':'.8'})));
 D.geo.ba.features.forEach(f=>g.append(svgEl('path',{d:geoPath(f.geometry),fill:colors[f.properties.code],opacity:f.properties.code==='PACE'?'.55':'.43',stroke:'#6f8c69','stroke-width':'.8'})));
 svg.append(g);
 const stateLabels=[['OREGON',-120.7,44],['IDAHO',-114.5,44],['WYOMING',-107.6,43],['ARIZONA',-111.9,33.5],['COLORADO',-106.1,38.8]];
 stateLabels.forEach(([name,lon,lat])=>{const[x,y]=project([lon,lat]);svg.append(svgEl('text',{x,y,fill:'#5d735e','font-size':7,'letter-spacing':1.5,'text-anchor':'middle',opacity:'.85'},name))});
 const home=project([-111.89,40.76]);
 const sites=[['BPAT',-122.67,45.63],['CISO',-119.4,36.6],['NEVP',-115.14,36.17]];
 for(const[code,lon,lat]of sites){const[x,y]=project([lon,lat]);const d='M'+home.join(',')+' Q'+[(home[0]+x)/2+20,Math.min(home[1],y)-45].join(',')+' '+[x,y].join(',');svg.append(svgEl('path',{d,stroke:'#fff','stroke-width':6,fill:'none',opacity:'.8'}),svgEl('path',{d,stroke:'#265bc4','stroke-width':2,fill:'none','marker-end':'url(#arrow)',class:'route-path'}));svg.append(svgEl('circle',{cx:x,cy:y,r:5,fill:'#fff',stroke:'#265bc4','stroke-width':2}));svg.append(svgEl('text',{x:x+11,y:y-9,'font-size':10,fill:'#284d3a','font-weight':500},names[code]));}
 svg.append(svgEl('circle',{cx:home[0],cy:home[1],r:15,fill:'#fff','fill-opacity':'.38'}),svgEl('circle',{cx:home[0],cy:home[1],r:7,fill:'#fff',stroke:'#b95a36','stroke-width':2}),svgEl('text',{x:home[0]+14,y:home[1]+3,fill:'#533e2a','font-size':11,'font-weight':600},'Utah · PACE'));
}
function makeChart(){
 const svg=$('#day-chart'),width=Math.max(250,svg.clientWidth),left=37,right=width-12,top=13,bottom=164,max=800;
 svg.replaceChildren();svg.setAttribute('viewBox','0 0 '+width+' 198');
 const x=h=>left+(right-left)*h/24,y=v=>bottom-(bottom-top)*v/max;
 const defs=svgEl('defs');const grad=svgEl('linearGradient',{id:'utah-fill',x1:0,y1:0,x2:0,y2:1});grad.append(svgEl('stop',{offset:'0%','stop-color':'#c98f58','stop-opacity':'.14'}),svgEl('stop',{offset:'100%','stop-color':'#c98f58','stop-opacity':'0'}));defs.append(grad);svg.append(defs);
 [0,200,400,600,800].forEach(v=>{svg.append(svgEl('line',{x1:left,y1:y(v),x2:right,y2:y(v),stroke:'#dbe1d4','stroke-width':'.8'}),svgEl('text',{x:left-10,y:y(v)+3,'font-size':11,fill:'#53665d','text-anchor':'end'},v))});
 [0,6,12,18,24].forEach(h=>svg.append(svgEl('text',{x:x(h),y:bottom+21,'font-size':11,fill:'#53665d','text-anchor':h===0?'start':h===24?'end':'middle'},h===0?'12 AM':h===6?'6 AM':h===12?'12 PM':h===18?'6 PM':'12 AM')));
 ['PACE','BPAT','CISO'].forEach(code=>{const vals=D.ci[code].day.value;const points=[...vals,vals[0]].map((v,h)=>[x(h),y(v)]);const path=points.map((p,i)=>(i?'L':'M')+p.join(',')).join(' ');
 if(code==='PACE')svg.append(svgEl('path',{d:path+'L'+right+','+bottom+'L'+left+','+bottom+'Z',fill:'url(#utah-fill)'}));
 svg.append(svgEl('path',{d:path,fill:'none',stroke:colors[code],'stroke-width':code==='PACE'?2.6:2,'stroke-linejoin':'round','stroke-linecap':'round','data-series':code}));
 svg.append(svgEl('circle',{cx:x(12),cy:y(vals[12]),r:3,fill:colors[code],stroke:'#fff','stroke-width':1}));
 });
}
function selectSite(code){document.querySelectorAll('[data-site]').forEach(b=>{const on=b.dataset.site===code;b.classList.toggle('selected',on);b.setAttribute('aria-pressed',String(on))});$('#site-label').textContent=names[code].toUpperCase()+' / '+code;$('#site-ci').textContent=number(D.ci[code].year_mean.value,0)}
const descriptions={
 primary:'Eligible work can move before it starts. The simple, fixed clean-region rule performs as well as the forecast-driven policies in this validation replay.',
 small:'Mobility is the lever. Keeping large jobs in Utah sharply limits the benefit, even though many small jobs may still move.',
 capacity:'This is a different fleet scenario: more spare destination GPUs, not more electricity transmission capacity.'
};
function setScenario(id){const s=D.scenarios[id],c=s.contrast;
 document.querySelectorAll('[data-scenario]').forEach(b=>{const on=b.dataset.scenario===id;b.classList.toggle('selected',on);b.setAttribute('aria-pressed',String(on))});
 $('#saving').textContent=pct(c.saving.value);$('#place-saving').textContent=pct(c.saving.value)+'%';
 const ci=c.saving_ci95.value;$('#interval').textContent=pct(ci[0])+'–'+pct(ci[1])+'% · conditional 95% interval';
 $('#place-bar').style.width=(c.saving.value/.4*100)+'%';$('#bar-interval').style.left=(ci[0]/.4*100)+'%';$('#bar-interval').style.width=((ci[1]-ci[0])/.4*100)+'%';
 $('#scenario-label').textContent=s.label;$('#scenario-explanation').textContent=descriptions[id];
}
function evidenceContent(){return '<h2 id="dialog-title">A result you can question.</h2><p>This concept uses <strong>real exported validation results</strong>, rather than invented dashboard numbers. The headline is policy S: a fixed training-ranked clean-region rule. Learned forecasting has not shown an additional benefit in this replay.</p><ul><li><strong>Simulated:</strong> CO₂ reductions and interval estimates. The interval is conditional temporal block resampling; it does not include power-model uncertainty.</li><li><strong>Modeled:</strong> EIA consumption-based intensity. Annual means color the map; the curves are typical-day means, not issued forecasts.</li><li><strong>Assumed:</strong> spare GPUs, mobility, transfer overhead, power, exact declared runtimes and advance-known baseline reservations.</li><li>Deadlines are met by construction under baseline bookings. This does not establish production reliability or physically avoided emissions.</li></ul><p>Registered run: <code>'+D.run_id+'</code><br>Window: '+D.window+' · Nov 2024–Oct 2025, with the registered arrival cutoff and drain. Every scenario retains its source run and evidence envelopes in data.js.</p><div class="dialog-note"><p><strong>Source artifacts</strong><br>'+D.source_paths.join('<br>')+'<br>Map geometry: Electricity Maps contributors (AGPL-3.0), fitted to Natural Earth. Local license and attribution notices are bundled.</p></div>'}
function designContent(){return '<h2 id="dialog-title">Quiet materials. Clear meaning.</h2><p>One design direction: a light, editorial cockpit with a restrained glass surface and a stronger visual hierarchy. A single large number answers the question; the scenario controls reveal its limits.</p><div class="palette">'+[['#203f35','Forest ink','Reading & hierarchy'],['#23744f','Cleaner green','Lower carbon'],['#b95a36','Utah clay','Higher carbon'],['#265bc4','Route blue','Placement actions'],['#a58742','Stored energy','Concept only']].map(([c,n,r])=>'<div class="swatch"><i style="background:'+c+'"></i><strong>'+n+'</strong><br>'+r+'</div>').join('')+'</div><ul><li>Glass is limited to surfaces and controls. Chart marks and text remain opaque.</li><li>Color always has a label or shape cue. Blue identifies requests moving, never electricity flows.</li><li>Scenario buttons load discrete computed results. No slider interpolates an unrun experiment.</li><li>Proposed UX: put the surprising mobility restriction within one click of the headline, then expose the assumptions.</li></ul><p>This prototype is an alternative composition for review. It uses the existing GridPilot mark and local Funnel fonts.</p>'}
function storageContent(){return '<h2 id="dialog-title">Move the work.<br>Or shift its energy.</h2><p>For large jobs that must stay in Utah, storage is a complementary question. This panel previews how to explain it; <strong>no storage benefit is estimated here.</strong></p><div class="storage-flow"><span>Charge in a<br>cleaner window</span><b aria-hidden="true">→</b><span>Store energy<br>with losses</span><b aria-hidden="true">→</b><span>Serve work<br>that stays local</span></div><p>A valid illustration must account for round-trip losses, power and energy limits, state of charge, and comparable starting and ending inventory. Compare grid draw before and after charging, not just discharging.</p><div class="dialog-note"><p><strong>Proposed next view</strong><br>A synchronized load strip and storage state-of-charge trace, with the site-power peak and energy losses shown beside the attributed-carbon estimate. Add measured simulation output only after that analysis is verified.</p></div>'}
const dialog=$('#detail-dialog');
document.querySelectorAll('[data-open]').forEach(b=>b.addEventListener('click',()=>{const kind=b.dataset.open;$('#dialog-content').innerHTML=kind==='evidence'?evidenceContent():kind==='storage'?storageContent():designContent();dialog.showModal()}));
$('#close-dialog').addEventListener('click',()=>dialog.close());
dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close()}});
document.querySelectorAll('[data-site]').forEach(b=>b.addEventListener('click',()=>selectSite(b.dataset.site)));
document.querySelectorAll('[data-scenario]').forEach(b=>b.addEventListener('click',()=>setScenario(b.dataset.scenario)));
makeMap();makeChart();selectSite('PACE');
for(const id of Object.keys(D.scenarios))$('#'+id+'-number').textContent=pct(D.scenarios[id].contrast.saving.value)+'%';
$('#wait-saving').textContent=pct(D.time_contrast.saving.value)+'%';$('#wait-bar').style.width=(D.time_contrast.saving.value/.4*100)+'%';
setScenario('primary');

window.addEventListener('resize',()=>requestAnimationFrame(makeChart));
