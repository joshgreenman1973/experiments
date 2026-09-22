const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.join(__dirname,'..'),data=JSON.parse(fs.readFileSync(path.join(root,'data/indicators.json'))),guide=JSON.parse(fs.readFileSync(path.join(root,'data/guide.json')));
const src=fs.readFileSync(path.join(root,'app.js'),'utf8');
const context=vm.createContext({assert,data,guide,console,URLSearchParams});
vm.runInContext(src.slice(0,src.indexOf('/* --- small charts'))+'\n'+src.slice(src.indexOf('function relChange('),src.indexOf('/* ===========================================================================\n   Shared pieces'))+'\n'+fs.readFileSync(path.join(root,'explore.js'),'utf8'),context);
vm.runInContext(src.slice(src.indexOf('function searchRecords()'),src.indexOf('/* ===========================================================================\n   View: outliers')),context);
vm.runInContext(`
Object.assign(D,data); D.guide=guide; D.byId=Object.fromEntries(D.ind.map(r=>[r.id,r]));D.yi=Object.fromEntries(D.years.map((y,i)=>[y,i]));
state.fromYear=2025;state.toYear=2026;
assert.equal(normalizeSearch('Daycare childCare day care'),'child care child care child care');
assert.equal(normalizeSearch('PreK rats'),'pre-k rat');
for(const r of D.ind) r._search=normalizeSearch([r.n,r.d>=0?D.desc[r.d]:'',r.s>=0?D.svc[r.s]:''].join(' '));
state.q='daycare';assert.ok(searchRecords().length>0);assert.ok(normalizeSearch(searchRecords()[0].n).includes('child care'));state.q='';
assert.equal(guide.topics.length,6);
for (const topic of guide.topics) for (const q of topic.questions) {
 assert.ok(q.ids.length>=2 && q.ids.length<=4);
 for (const id of q.ids) {assert.ok(D.byId[id],id);assert.ok(!D.byId[id].gv,id);assert.ok(!D.byId[id].rt,id);}
}
for(const n of guide.sourceNotes) {assert.ok(n.page>0 && n.page<=544);for(const id of n.ids)assert.ok(D.byId[id]);}
assert.equal(validComparison(['__proto__','constructor','1832','1832','bogus','1816','1807','10871','10872']).join(','),'1832,1816,1807,10871');
assert.ok(guideQuestions('15275').some(q=>q.ids.includes('2900')));
assert.ok(targetAssessment(D.byId['15763']).endsWith('— met'));
assert.ok(targetAssessment(D.byId['15275']).endsWith('— met'),'pothole target met despite deterioration');
assert.ok(score(D.byId['15275'],2025,2026)<0);
assert.ok(targetAssessment({...D.byId['15275'],sus:{2026:'flag'}}).includes('not assessed'));
assert.equal(csvCell('=SUM(A1)'),String.fromCharCode(34,39)+'=SUM(A1)'+String.fromCharCode(34));assert.equal(csvCell(-12),'\"-12\"');
assert.equal(csvCell('a,\"b\"'),'\"a,\"\"b\"\"\"');
const csv=comparisonCSV(['5507','10562']);
assert.ok(csv.includes('original_open_data_value'));assert.ok(csv.includes('75932'));assert.ok(csv.includes('73641'));assert.ok(csv.includes('#page=371'));assert.ok(csv.includes('decimal minutes'));
assert.equal(csv.split('\\r\\n').length,1+2*D.years.length);
`,context);
console.log('Topic, comparison, target and CSV checks passed.');
