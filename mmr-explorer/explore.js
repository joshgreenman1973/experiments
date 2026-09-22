/* Reader navigation, reviewed relationships and evidence exports.
   guide.json is editorial data; definitions and actuals remain in indicators.json. */
function normalizeSearch(text) {
  return String(text).toLowerCase().replace(/\b(daycare|day care|childcare)\b/g, 'child care')
    .replace(/\b(prekindergarten|pre kindergarten|pre k|prek)\b/g, 'pre-k')
    .replace(/\bnyc police\b/g, 'nypd').replace(/\brats\b/g, 'rat');
}
function guideQuestions(id) {
  return (D.guide.topics || []).flatMap(t => t.questions).filter(q => q.ids.includes(id));
}
function validComparison(ids) {
  return [...new Set(ids)].filter(id => Object.prototype.hasOwnProperty.call(D.byId,id)).slice(0,4);
}
function actionButton(label, action, cls) {
  const b = el('button', cls || 'guide-button', label); b.type = 'button';
  b.addEventListener('click', action); return b;
}
function saveCompareState() {
  const hash = $('#drawer').classList.contains('open') ? '#i/' + $('#drawer').dataset.indicator + comparisonQuery() : viewHash();
  history.replaceState(null, '', hash);
  drawCompareTray();
  $$('[data-compare-id]').forEach(b => {
    const selected = state.compare.includes(b.dataset.compareId);
    b.textContent = selected ? 'Remove from comparison' : 'Add to comparison';
    b.setAttribute('aria-pressed', String(selected));
  });
}
function compareAnnouncement(message) {
  let status=$('#compare-status');
  if ($('#drawer').classList.contains('open')) {
    status=$('#drawer-compare-status');
    if (!status) {status=el('p','note');status.id='drawer-compare-status';status.setAttribute('role','status');$('#dbody').prepend(status);}
  }
  status.textContent=message;
}
function toggleCompare(id) {
  if (state.compare.includes(id)) state.compare = state.compare.filter(x => x !== id);
  else if (state.compare.length < 4) state.compare.push(id);
  else {
    compareAnnouncement('Four indicators selected. Remove one before adding another.');
    return;
  }
  saveCompareState();
  compareAnnouncement(state.compare.length + ' of 4 indicators selected.');
  if (state.view === 'compare' && !$('#drawer').classList.contains('open')) go('compare');
}
function compareButton(id) {
  const selected = state.compare.includes(id);
  const b = actionButton(selected ? 'Remove from comparison' : 'Add to comparison', () => toggleCompare(id));
  b.dataset.compareId = id; b.setAttribute('aria-pressed', String(selected));
  return b;
}
function drawCompareTray() {
  const tray = $('#compare-tray'); tray.hidden = !state.compare.length;
  tray.replaceChildren();
  if (!state.compare.length) return;
  tray.appendChild(el('span', '', `${state.compare.length} of 4 indicators selected`));
  tray.appendChild(actionButton('View comparison', () => { if ($('#drawer').classList.contains('open')) closeDrawer(); go('compare'); }));
  tray.appendChild(actionButton('Clear selection', () => { state.compare = []; saveCompareState(); if (state.view === 'compare') go('compare'); }));
}
function startComparison(ids) {
  state.compare = validComparison(ids);
  if ($('#drawer').classList.contains('open')) closeDrawer();
  go('compare');
}
function viewTopics(host) {
  host.appendChild(sectionHead('What would you like to understand?', 'Explore by topic', '00'));
  const intro = el('div', 'pad');
  intro.appendChild(el('p', 'note', 'Start with a question, then follow the measures behind it. These are curated routes into the report, not comprehensive assessments of each topic.'));
  const search = el('form', 'guide-search');
  const input = el('input'); input.type = 'search'; input.placeholder = 'Try daycare, shelter, rats or response time'; input.setAttribute('aria-label','Search the report');
  const submit = el('button','guide-button','Search indicators'); submit.type = 'submit';
  search.append(input, submit);
  search.addEventListener('submit', e => { e.preventDefault(); state.q = input.value; state.filters = {agency:'',dir:'',mt:'',live:'live',critical:''}; go('search'); });
  intro.appendChild(search); host.appendChild(intro);
  const grid = el('div','topic-grid');
  (D.guide.topics || []).forEach(t => {
    const card = el('section','topic-card');
    card.appendChild(el('h3','',t.title)); card.appendChild(el('p','note',t.intro));
    t.questions.forEach(q => {
      const group = el('div','topic-question');
      group.appendChild(el('h4','',q.title)); group.appendChild(el('p','note',q.note));
      const list = el('ul','guide-links');
      q.ids.forEach(id => { const r = D.byId[id]; if (!r) return; const li = el('li'); li.appendChild(actionButton(r.n,()=>openIndicator(id),'text-button')); list.appendChild(li); });
      group.appendChild(list); group.appendChild(actionButton('Compare these measures',()=>startComparison(q.ids)));
      card.appendChild(group);
    });
    card.appendChild(actionButton('Search this topic',()=>{state.q=t.query;state.filters={agency:'',dir:'',mt:'',live:'live',critical:''};go('search');}));
    grid.appendChild(card);
  });
  host.appendChild(grid);
}
function targetAssessment(rec) {
  const year = D.pdfYear, value = rec.v[D.yi[year]], target = rec.tgt && rec.tgt.t26;
  if (target == null) return targetText(rec,'t26');
  if (value == null) return `${fmtVal(target,rec.mt,rec)} — actual not extracted`;
  if (rec.sus && rec.sus[String(year)]) return `${fmtVal(target,rec.mt,rec)} — actual flagged; not assessed`;
  const direction = directionFor(rec,year);
  if (!direction) return `${fmtVal(target,rec.mt,rec)} — no desired direction; not assessed`;
  return `${fmtVal(target,rec.mt,rec)} — ${(direction > 0 ? value >= target : value <= target) ? 'met' : 'missed'}`;
}
function readingUnit(rec) {
  if (rec.ts) return (rec.tu || 'minutes:seconds') + ' (clock format)';
  if (rec.tu) return rec.tu;
  const suffix = rec.n.match(/\(([^()]*)\)\s*$/);
  if (suffix && /%|\$|000|\b(per|units|days|years|minutes|hours|seconds|miles|tons)\b/i.test(suffix[1])) return suffix[1];
  return mtWord(rec.mt);
}
function readingBox(rec) {
  const box = el('section','reading-box'); box.appendChild(el('h4','','How to read this measure'));
  if (rec.d >= 0) box.appendChild(el('p','',D.desc[rec.d]));
  else box.appendChild(el('p','note','The dataset provides no definition. Check the source chapter before interpreting this measure.'));
  const period = rec.rp >= 0 ? D.rp[rec.rp] : 'Not stated';
  const verdict = score(rec,state.fromYear,state.toYear);
  const dl = el('dl','reading-facts');
  const values = [
    ['Reporting period',period + (period !== 'Fiscal Year' ? ' — fiscal labels identify report slots, not necessarily July–June observations.' : ' — July through June.')],
    ['Unit',readingUnit(rec)],
    [`Change, FY${state.fromYear} → FY${state.toYear}`,verdict == null ? 'Not scorable for these years' : verdict > 0 ? 'Improved in the city’s stated direction' : verdict < 0 ? 'Moved against the city’s stated direction' : 'No material change at the selected threshold'],
    [`Target, FY${D.pdfYear}`,targetAssessment(rec)]
  ];
  values.forEach(([label,value])=>{dl.append(el('dt','',label),el('dd','',value));}); box.appendChild(dl);
  if (rec.definitionNote) box.appendChild(el('p','warn',rec.definitionNote));
  else box.appendChild(el('p','note','No definition-break note has been added here. That is not a certification that the definition stayed unchanged; consult chapter notes before interpreting a long trend.'));
  return box;
}
function sourceContext(rec) {
  const wrap = el('section','source-context'); wrap.appendChild(el('h4','','Read alongside the report'));
  const notes = (D.guide.sourceNotes || []).filter(n=>n.ids.includes(rec.id));
  notes.forEach(n=>{
    wrap.appendChild(el('h5','',n.title));wrap.appendChild(el('p','',n.text));
    const a=el('a','',`FY2026 report · PDF page ${n.page}`);a.href=D.pdfPageBase+n.page;a.target='_blank';a.rel='noopener';wrap.appendChild(a);
  });
  if (!notes.length) wrap.appendChild(el('p','note','No chapter commentary has been curated for this measure. The linked chapter may contain additional explanations or qualifications.'));
  const a=el('a','guide-source',rec.pdf ? `Open the indicator’s table · PDF page ${rec.pdf.p}` : 'Open the agency chapter');
  a.href=rec.pdf ? D.pdfPageBase+rec.pdf.p : (D.agencies[rec.a].mmr ? D.mmrBase+D.agencies[rec.a].mmr : D.mmrPage);a.target='_blank';a.rel='noopener';wrap.appendChild(a);
  return wrap;
}
function relatedIndicators(rec) {
  const wrap=el('section','related');wrap.appendChild(el('h4','','Read these measures together'));
  const groups=guideQuestions(rec.id);
  const ids=[...new Set(groups.flatMap(q=>q.ids))].filter(id=>id!==rec.id);
  if (groups.length) groups.forEach(q=>wrap.appendChild(el('p','note',q.note)));
  else {
    ids.push(...D.ind.filter(r=>r.id!==rec.id && !r.rt && r.a===rec.a && r.g===rec.g && rec.g>=0).slice(0,3).map(r=>r.id));
    wrap.appendChild(el('p','note','Other measures under the same agency goal. This grouping follows the report; it does not establish matching populations or a causal relationship.'));
  }
  if (!ids.length) {wrap.appendChild(el('p','note','No related measures are listed yet. Add measures from search to build your own comparison.'));return wrap;}
  ids.slice(0,4).forEach(id=>{
    const r=D.byId[id];if(!r)return;
    const row=el('div','related-row');row.appendChild(actionButton(r.n,()=>openIndicator(id),'text-button'));row.appendChild(compareButton(id));wrap.appendChild(row);
  });
  wrap.appendChild(actionButton('Compare with this measure',()=>startComparison([rec.id,...ids].slice(0,4))));
  return wrap;
}
function csvCell(value) {
  let s=value==null?'':String(value);
  if (typeof value==='string' && /^[\s]*[=+\-@]/.test(s)) s="'"+s;
  return '"'+s.replace(/"/g,'""')+'"';
}
function comparisonCSV(ids) {
  const rows=[['indicator_id','agency','indicator','definition','unit','reporting_period','report_year','value','display_value','source','source_url','original_open_data_value','desired_direction','definition_note','flag','comparison_from','comparison_to']];
  validComparison(ids).forEach(id=>{
    const r=D.byId[id];
    D.years.forEach((y,i)=>{
      const printed=r.pdf && ((r.pdf.historyYears||[]).includes(y) || (y===D.pdfYear && r.pdf.valueSource!=='open-data' && r.v[i]!=null));
      rows.push([id,D.agencies[r.a].c,r.n,r.d>=0?D.desc[r.d]:'',(r.ts ? 'decimal '+(r.tu||'minutes:seconds').split(':')[0] : (r.tu || mtWord(r.mt))),r.rp>=0?D.rp[r.rp]:'',y,r.v[i],r.v[i]==null?'':fmtFiled(r.v[i],r.mt,r),r.v[i]==null?'Missing':printed?'FY2026 printed report':'NYC Open Data',printed?D.pdfPageBase+r.pdf.p:'https://data.cityofnewyork.us/resource/rbed-zzin.json?id='+id,r.pdf && r.pdf.original ? r.pdf.original[String(y)] : null,directionFor(r,y),r.definitionNote||'',(r.sus||{})[String(y)]||'',state.fromYear,state.toYear]);
    });
  });
  return rows.map(r=>r.map(csvCell).join(',')).join('\r\n');
}
function viewCompare(host) {
  host.appendChild(sectionHead('Read the measures together',`${state.compare.length} of 4 selected`,'00'));
  const intro=el('div','pad');intro.appendChild(el('p','note','Charts share the same years, but each has its own vertical scale and stated unit. Compare timing and context; heights across charts do not represent equivalent quantities. The controls above set the change assessment, not the chart history.'));
  host.appendChild(intro);
  if (!state.compare.length) {intro.appendChild(el('p','','Choose a topic or open an indicator and select “Add to comparison.”'));intro.appendChild(actionButton('Explore topics',()=>go('topics')));return;}
  const records=state.compare.map(id=>D.byId[id]);
  if (new Set(records.map(r=>r.rp)).size>1) intro.appendChild(el('p','warn','These measures use different reporting periods. A school or calendar year is not the same interval as a fiscal year, even under the same report-year label.'));
  const download=el('a','guide-button','Download values and sources (CSV)');
  download.href='data:text/csv;charset=utf-8,'+encodeURIComponent('\ufeff'+comparisonCSV(state.compare));
  download.download='mmr-comparison.csv';
  intro.appendChild(download);
  const share=el('input');share.readOnly=true;share.setAttribute('aria-label','Share this comparison');share.value=location.href.split('#')[0]+viewHash();
  const label=el('label','share-label','Share this comparison');label.appendChild(share);intro.appendChild(label);
  const grid=el('div','comparison-grid');
  records.forEach(r=>{
    const card=el('section','comparison-card');card.appendChild(el('p','eyebrow',D.agencies[r.a].n));
    const heading=el('h3');heading.appendChild(actionButton(r.n,()=>openIndicator(r.id),'text-button'));card.appendChild(heading);
    card.appendChild(compareButton(r.id));card.appendChild(lineChart(r,{h:235}));card.appendChild(readingBox(r));
    const table=el('table','vtable');table.innerHTML='<caption>Published values; — means no figure is available</caption><thead><tr><th>Report year</th>'+D.years.map(y=>'<th>'+y+'</th>').join('')+'</tr></thead><tbody><tr><th>Value</th>'+r.v.map(v=>'<td>'+esc(fmtFiled(v,r.mt,r))+'</td>').join('')+'</tr></tbody>';card.appendChild(table);
    const groups=guideQuestions(r.id);if(groups.length)card.appendChild(el('p','note',groups[0].note));
    card.appendChild(sourceContext(r));grid.appendChild(card);
  });
  host.appendChild(grid);
}
