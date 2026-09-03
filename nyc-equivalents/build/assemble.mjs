// Reads pairings-src.json (curated, with lon/lat per match), projects each pin
// with the same projection as world.mjs, computes gaps, writes ../data/pairings.json
import fs from 'node:fs';
import * as d3 from 'd3-geo';
const src = JSON.parse(fs.readFileSync('pairings-src.json','utf8'));
const W=1000,H=520;
const proj = d3.geoNaturalEarth1().fitExtent([[6,6],[W-6,H-6]], {type:'Sphere'});
const pt = (lon,lat)=>{const [x,y]=proj([lon,lat]);return {x:+x.toFixed(1),y:+y.toFixed(1)}};
const items = src.items.map((it,i)=>{
  const ratio = it.match_value/it.nyc_value;
  const gapPct = (ratio-1)*100;
  const {x,y} = pt(it.lon,it.lat);
  return {
    n:i+1, realm:it.realm, kind:it.kind, place:it.place, place_short:it.place_short||null, x, y,
    sentence:it.sentence, caveat:it.caveat||null,
    nyc_display:it.nyc_display, match_display:it.match_display,
    ratio:+ratio.toFixed(4),
    gap_display:(Math.abs(gapPct)<0.5?'Within half a percent':`${it.place_short||it.place} is ${Math.abs(gapPct).toFixed(gapPct<2?1:0)}% ${gapPct>0?'more':'less'}`),
    nyc_src:it.nyc_url, match_src:it.match_url, compare:it.compare,
    // the drawer shows a full dossier without a second page load
    nyc:{label:it.nyc_source, year:it.nyc_year, url:it.nyc_url, quote:it.nyc_quote, value:it.nyc_value},
    match:{label:it.match_source, year:it.match_year, url:it.match_url, quote:it.match_quote, value:it.match_value},
    note:it.note, confidence:it.confidence
  };
});
// attach each blind fact-check finding by the pair of URLs it actually checked
const fc = fs.existsSync('factcheck.json') ? JSON.parse(fs.readFileSync('factcheck.json','utf8')) : null;
// factcheck.json is the merged ledger and already holds every round, the final
// adversarial audit last. Prefer an audit row over an earlier round's verdict on
// the same pair of URLs: the earlier rounds ran against wording since rewritten.
const allFc = [...(fc?.items||[])];
const rank = r => r.round==='audit' ? 0 : 1;
for (const it of items) {
  const matches = allFc.filter(f=>f.checked_nyc_url===it.nyc.url && f.checked_match_url===it.match.url);
  matches.sort((a,b)=>rank(a)-rank(b));
  const row = matches[0];
  if (row) {
    // A URL pair alone is not enough to say a finding still applies: several
    // comparisons share one source URL (the IMF serves every country from one
    // file), so a swapped comparison can inherit a verdict written about the
    // country it replaced. If the figure checked is not the figure on the page,
    // the verdict is superseded and only the record of the change survives.
    const same = row.checked_match_value===undefined
      || (row.checked_match_value===it.match.value && row.checked_nyc_value===it.nyc.value);
    it.check = same
      ? {verdict:row.verdict, finding:row.finding, conflict:row.conflict||null, resolution:row.resolution||null}
      : {verdict:'SUPERSEDED', finding:'This pairing was changed after it was checked, so the earlier finding no longer describes it.'
           + (row.reverified? ' ' + row.reverified : ''), conflict:null, resolution:row.resolution||null};
  }
}
const gaps = items.map(i=>Math.abs(i.ratio-1)*100).sort((a,b)=>a-b);
const med = gaps[Math.floor(gaps.length/2)];
const maxGap = Math.max(...gaps);
const out = {
  realms: src.realms, nyc: pt(-74.006,40.7128), items,
  tolerance: `${Math.ceil(maxGap)}%`, years: src.years, median_gap: `${med.toFixed(1)}%`
};
fs.writeFileSync('../data/pairings.json', JSON.stringify(out,null,1));
console.log(items.length,'pairings; max gap',maxGap.toFixed(1),'median',med.toFixed(1));
items.forEach(i=>console.log(String(i.n).padStart(2), i.realm.padEnd(9), i.place.padEnd(28), (i.ratio).toFixed(3), i.gap_display));
