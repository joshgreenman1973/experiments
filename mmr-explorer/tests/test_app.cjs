const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const path = require('node:path'), root=path.join(__dirname,'..');
const src=fs.readFileSync(path.join(root,'app.js'),'utf8');
const data=JSON.parse(fs.readFileSync(path.join(root,'data/indicators.json'),'utf8'));
const context=vm.createContext({assert,data,URLSearchParams,console});
const prefix=src.slice(0,src.indexOf('/* --- small charts'));
const scoring=src.slice(src.indexOf('function relChange('),src.indexOf('/* ===========================================================================\n   Shared pieces'));
vm.runInContext(prefix+'\n'+scoring+`\nObject.assign(D,data);D.yi=Object.fromEntries(D.years.map((y,i)=>[y,i]));`,context);
vm.runInContext(`
 const fixture = (a,b,dir=1) => ({dir,v:D.years.map(y=>y===2025?a:y===2026?b:null)});
 state.flat=0;
 assert.equal(score(fixture(100,100),2025,2026),0,'exact equality must remain unchanged at zero threshold');
 assert.equal(score(fixture(100,90,-1),2025,2026),1);
 assert.equal(score(fixture(0,0),2025,2026),null,'zero percentage baseline is undefined');
 assert.equal(fmtTime(1.999),'2:00');
 assert.equal(fmtTime(-1.999),'-2:00');
 state.flat=.01;
 assert.equal(score(fixture(100,100.5),2025,2026),0);
 assert.equal(score({...fixture(100,120),dirs:{2025:1,2026:-1}},2025,2026),-1);
 assert.equal(score({...fixture(100,120),sus:{2026:'bad'}},2025,2026),null);
 assert.equal(score({...fixture(100,120),breaks:[2026]},2025,2026),null,'definition breaks must not be scored');
 const preK=D.ind.find(r=>r.id==='15763');
 assert.equal(score(preK,2025,2026),1,'fewer unfilled pre-K seats is an improvement');
 assert.equal(targetText(D.ind.find(r=>r.id==='3947'),'t26'),'Directional target: down');
 assert.equal(targetText({mt:0},'t26'),'Not extracted; check the chapter');
 const original=state.flat;state.flat=0;
 for(const r of D.ind.filter(r=>!r.rt && r.v[D.yi[2025]]===r.v[D.yi[2026]] && r.v[D.yi[2025]]>0 && directionFor(r,2026))) {
   assert.equal(score(r,2025,2026),0,r.id);
 }
 state.flat=original;
`,context);
console.log('App regression assertions passed.');
