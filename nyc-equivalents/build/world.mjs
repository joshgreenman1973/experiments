// Projects Natural Earth 110m countries to SVG paths (Natural Earth I projection)
// and writes ../data/world.json = {paths:[{name,d}], centroids:{name:[lon,lat]}, project fn params}
import fs from 'node:fs';
import * as d3 from 'd3-geo';
import * as tc from 'topojson-client';
const topo = JSON.parse(fs.readFileSync('countries-110m.json','utf8'));
const fc = tc.feature(topo, topo.objects.countries);
const W=1000,H=520;
const proj = d3.geoNaturalEarth1().fitExtent([[6,6],[W-6,H-6]], {type:'Sphere'});
const path = d3.geoPath(proj);
const paths = fc.features.filter(f=>f.properties.name!=='Antarctica').map(f=>({name:f.properties.name, d:path(f)}));
const centroids = {};
for (const f of fc.features) centroids[f.properties.name] = d3.geoCentroid(f).map(v=>+v.toFixed(3));
const sphere = path({type:'Sphere'});
const graticule = path(d3.geoGraticule().step([30,30])());
fs.writeFileSync('../data/world.json', JSON.stringify({W,H,sphere,graticule,paths,centroids}));
// expose projection for pins: dump a table of projected test points
const pt = (lon,lat)=>proj([lon,lat]).map(v=>+v.toFixed(1));
console.log('NYC', pt(-74.006,40.7128), 'Paris', pt(2.35,48.85), 'Singapore', pt(103.8,1.35));
fs.writeFileSync('../data/proj-params.json', JSON.stringify({scale:proj.scale(), translate:proj.translate(), W, H}));
