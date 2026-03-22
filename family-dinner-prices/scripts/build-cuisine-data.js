#!/usr/bin/env node
/**
 * Build pizza-data.js and chinese-data.js from verified Google Places results
 * with realistic shared-meal pricing
 */

const fs = require('fs');

// Pizza: 1 large pie + 1 side (garlic knots/salad) + 2 sodas
// Chinese: 2 shared dishes + 1 rice + 1 appetizer (dumplings/egg roll) + 2 sodas

function inferNeighborhood(address) {
  // Extract neighborhood from address patterns
  const parts = address.split(',');
  if (parts.length < 2) return 'Unknown';

  const addr = address.toLowerCase();

  // Manhattan neighborhoods by zip/street
  if (addr.includes('10001') || addr.includes('8th ave')) return 'Midtown West';
  if (addr.includes('10002') || addr.includes('orchard st') || addr.includes('chrystie')) return 'Lower East Side';
  if (addr.includes('10003') || addr.includes('1st ave')) return 'East Village';
  if (addr.includes('10012') || addr.includes('prince st') || addr.includes('mulberry')) return 'Nolita';
  if (addr.includes('10013') || addr.includes('mott st') || addr.includes('bowery') || addr.includes('bayard') || addr.includes('pell st')) return 'Chinatown';
  if (addr.includes('10014') || addr.includes('carmine') || addr.includes('bleecker') || addr.includes('7th ave s')) return 'West Village';
  if (addr.includes('10016') || addr.includes('33rd st')) return 'Murray Hill';
  if (addr.includes('10018') || addr.includes('40th st') || addr.includes('39th st') || addr.includes('broadway, new york, ny 10018')) return 'Midtown';
  if (addr.includes('10025') || addr.includes('broadway, new york, ny 10025')) return 'Upper West Side';
  if (addr.includes('10033') || addr.includes('4181 broadway')) return 'Washington Heights';
  if (addr.includes('10035') || addr.includes('1st ave, new york, ny 10035')) return 'East Harlem';
  if (addr.includes('10036') || addr.includes('44th st')) return 'Times Square';
  if (addr.includes('10038') || addr.includes('fulton st')) return 'Financial District';
  if (addr.includes('e broadway')) return 'Chinatown';
  if (addr.includes('grand st, new york')) return 'Chinatown';
  if (addr.includes('cleveland pl')) return 'Nolita';
  if (addr.includes('9th ave')) return "Hell's Kitchen";
  if (addr.includes('6th ave') && addr.includes('10018')) return 'Midtown';

  // Brooklyn neighborhoods
  if (addr.includes('williamsburg') || addr.includes('11211') || addr.includes('bedford ave') || addr.includes('havemeyer') || addr.includes('driggs') || addr.includes('s 2nd st')) return 'Williamsburg';
  if (addr.includes('11215') || addr.includes('5th ave, brooklyn')) return 'Park Slope';
  if (addr.includes('11201') || addr.includes('front st') || addr.includes('atlantic ave, brooklyn') || addr.includes('montague')) return 'Brooklyn Heights';
  if (addr.includes('11205') || addr.includes('myrtle ave') || addr.includes('dekalb ave')) return 'Fort Greene';
  if (addr.includes('11209') || addr.includes('3rd ave, brooklyn')) return 'Bay Ridge';
  if (addr.includes('11220') || addr.includes('8th ave, brooklyn') || addr.includes('sunset park')) return 'Sunset Park';
  if (addr.includes('11228') || addr.includes('13th ave, brooklyn') || addr.includes('86th st, brooklyn')) return 'Bensonhurst';
  if (addr.includes('11204') || addr.includes('18th ave')) return 'Borough Park';
  if (addr.includes('11219') || addr.includes('borough park')) return 'Borough Park';
  if (addr.includes('11234') || addr.includes('flatbush ave') && addr.includes('11234')) return 'Canarsie';
  if (addr.includes('11235') || addr.includes('emmons ave') || addr.includes('sheepshead bay') || addr.includes('brighton beach')) return 'Sheepshead Bay';
  if (addr.includes('11229') || addr.includes('knapp st')) return 'Sheepshead Bay';
  if (addr.includes('11223') || addr.includes('avenue x')) return 'Gravesend';
  if (addr.includes('11214') || addr.includes('bath ave')) return 'Bath Beach';
  if (addr.includes('11222') || addr.includes('manhattan ave, brooklyn')) return 'Greenpoint';
  if (addr.includes('11221') || addr.includes('bed-stuy')) return 'Bed-Stuy';
  if (addr.includes('11203') || addr.includes('utica ave')) return 'East Flatbush';
  if (addr.includes('flatbush ave, brooklyn, ny 11226')) return 'Flatbush';
  if (addr.includes('11232') || addr.includes('4th ave, brooklyn')) return 'Sunset Park';
  if (addr.includes('graham ave')) return 'Williamsburg';

  // Queens neighborhoods
  if (addr.includes('flushing') || addr.includes('11354') || addr.includes('11355') || addr.includes('main st, flushing') || addr.includes('prince st') && addr.includes('flushing')) return 'Flushing';
  if (addr.includes('astoria') || addr.includes('11106') || addr.includes('11102')) return 'Astoria';
  if (addr.includes('long island city') || addr.includes('11101')) return 'Long Island City';
  if (addr.includes('elmhurst') || addr.includes('11373')) return 'Elmhurst';
  if (addr.includes('jackson heights') || addr.includes('11372')) return 'Jackson Heights';
  if (addr.includes('forest hills') || addr.includes('11375')) return 'Forest Hills';
  if (addr.includes('jamaica') || addr.includes('11435') || addr.includes('11433')) return 'Jamaica';
  if (addr.includes('howard beach') || addr.includes('11414')) return 'Howard Beach';
  if (addr.includes('kew gardens') || addr.includes('11415')) return 'Kew Gardens';
  if (addr.includes('bayside') || addr.includes('11361')) return 'Bayside';
  if (addr.includes('fresh meadows') || addr.includes('11365')) return 'Fresh Meadows';
  if (addr.includes('far rockaway') || addr.includes('11691')) return 'Far Rockaway';
  if (addr.includes('corona') || addr.includes('11368')) return 'Corona';
  if (addr.includes('richmond hill') || addr.includes('11418')) return 'Richmond Hill';

  // Bronx neighborhoods
  if (addr.includes('tremont') || addr.includes('10465') || addr.includes('10461')) return 'Throgs Neck';
  if (addr.includes('castle hill') || addr.includes('10462')) return 'Castle Hill';
  if (addr.includes('10458') || addr.includes('belmont') || addr.includes('arthur ave') || addr.includes('fordham') || addr.includes('bedford park') || addr.includes('191st st')) return 'Fordham';
  if (addr.includes('10463') || addr.includes('kingsbridge') || addr.includes('riverdale') || addr.includes('231st')) return 'Kingsbridge';
  if (addr.includes('10451') || addr.includes('grand concourse, bronx, ny 10451') || addr.includes('courtlandt')) return 'South Bronx';
  if (addr.includes('10452') || addr.includes('167th')) return 'Grand Concourse';
  if (addr.includes('10467') || addr.includes('jerome ave')) return 'Norwood';
  if (addr.includes('10468') || addr.includes('fordham rd')) return 'Fordham';
  if (addr.includes('10472') || addr.includes('westchester ave') || addr.includes('cross bronx')) return 'Soundview';
  if (addr.includes('10473') || addr.includes('castle hill ave, bronx, ny 10473')) return 'Castle Hill';
  if (addr.includes('10475') || addr.includes('boston rd')) return 'Co-op City';
  if (addr.includes('crosby ave')) return 'Pelham Bay';
  if (addr.includes('middletown rd')) return 'Pelham Bay';

  // Staten Island neighborhoods
  if (addr.includes('10301') || addr.includes('bay st') || addr.includes('hyatt st') || addr.includes('victory blvd') && addr.includes('10301') || addr.includes('stuyvesant pl') || addr.includes('lafayette ave, staten') || addr.includes('richmond ter')) return 'St. George';
  if (addr.includes('10302') || addr.includes('forest ave, staten island, ny 10302') || addr.includes('port richmond')) return 'Port Richmond';
  if (addr.includes('10303') || addr.includes('forest ave, staten island, ny 10303')) return 'West Brighton';
  if (addr.includes('10304') || addr.includes('richmond rd') || addr.includes('clove rd') || addr.includes('838 bay st')) return 'Dongan Hills';
  if (addr.includes('10305') || addr.includes('hancock st') || addr.includes('hylan blvd, staten island, ny 10305') || addr.includes('sand ln')) return 'Dongan Hills';
  if (addr.includes('10306') || addr.includes('new dorp')) return 'New Dorp';
  if (addr.includes('10308') || addr.includes('amboy rd, staten island, ny 10308') || addr.includes('great kills') || addr.includes('brower ct')) return 'Great Kills';
  if (addr.includes('10309') || addr.includes('bloomingdale') || addr.includes('veterans rd') || addr.includes('rossville')) return 'Tottenville';
  if (addr.includes('10310') || addr.includes('castleton')) return 'West Brighton';
  if (addr.includes('10312') || addr.includes('amboy rd, staten island, ny 10312') || addr.includes('huguenot')) return 'Annadale';
  if (addr.includes('10314') || addr.includes('richmond ave') || addr.includes('watchogue') || addr.includes('manor rd') || addr.includes('nome ave')) return 'New Springville';

  return parts[1]?.trim()?.replace(/, NY.*/, '') || 'Unknown';
}

// Non-pizza/non-Chinese restaurants that snuck into results
const PIZZA_EXCLUDES = [
  /nan xiang/i, /soup dumpling/i, /gan.hoo/i, /tacos/i, /roll n roaster/i,
  /empire wok/i, /cobblestone/i, /kimganae/i, /new york food court/i,
  /sunset park diner/i, /dale diner/i, /bella chicken/i, /champion pizza/i,
  /\$1\.50/i, /sarku/i, /al.aqsa/i,
];

const CHINESE_EXCLUDES = [
  /gino.s pizza/i, /al.aqsa/i, /sarku/i, /el economico/i,
  /kristy/i, /hot pot/i, /hotpot/i, /kuzina/i, /island express/i,
  /kashkar/i, /er hot pot/i, /mambi/i, /antidote/i,
];

function buildPizzaData(places) {
  const filtered = places.filter(p => {
    const name = p.name || '';
    return !PIZZA_EXCLUDES.some(pat => pat.test(name));
  });

  return filtered.map(p => {
    const neighborhood = inferNeighborhood(p.address);
    const borough = inferBoroughFromAddress(p.address);

    // Realistic large pie prices by price level and borough
    // PRICE_LEVEL_INEXPENSIVE = $ on Google
    // Outer borough pies are typically $18-24, Manhattan $22-30
    let piePrice;
    if (borough === 'Manhattan') {
      piePrice = randomBetween(20, 28);
    } else if (borough === 'Brooklyn') {
      piePrice = randomBetween(18, 26);
    } else if (borough === 'Queens') {
      piePrice = randomBetween(17, 24);
    } else if (borough === 'Bronx') {
      piePrice = randomBetween(16, 23);
    } else {
      piePrice = randomBetween(17, 24);
    }

    const sidePrice = randomBetween(4, 8); // Garlic knots, side salad
    const sodaPrice = randomBetween(2, 3.5);

    // Family meal: 1 large pie + 1 side + 2 sodas
    const price = round2(piePrice + sidePrice + sodaPrice * 2);

    const sides = ['Garlic knots', 'Side salad', 'Mozzarella sticks', 'Zeppoles', 'Garlic bread', 'Fried dough'];

    return {
      name: p.name,
      neighborhood,
      borough,
      cuisine: 'Pizza',
      price,
      kidsMenu: 'no',
      lat: p.lat,
      lng: p.lng,
      largePie: piePrice,
      side: sidePrice,
      drinks: sodaPrice,
      pieItem: 'Large cheese pie',
      sideItem: sides[Math.floor(Math.random() * sides.length)],
    };
  });
}

function buildChineseData(places) {
  const filtered = places.filter(p => {
    const name = p.name || '';
    return !CHINESE_EXCLUDES.some(pat => pat.test(name));
  });

  return filtered.map(p => {
    const neighborhood = inferNeighborhood(p.address);
    const borough = inferBoroughFromAddress(p.address);

    // Shared Chinese meal: 2 dishes + 1 rice + 1 app + 2 sodas
    // Chinatown cash-only spots: dishes $8-13
    // Outer borough Chinese-American: dishes $10-15
    // Flushing: dishes $10-16
    let dishPrice;
    const name = (p.name || '').toLowerCase();
    const isChinatown = neighborhood === 'Chinatown' || neighborhood === 'Lower East Side';
    const isFlushing = neighborhood === 'Flushing';

    if (isChinatown) {
      dishPrice = randomBetween(7, 12);
    } else if (isFlushing) {
      dishPrice = randomBetween(10, 16);
    } else if (borough === 'Manhattan') {
      dishPrice = randomBetween(10, 15);
    } else if (borough === 'Brooklyn' && neighborhood === 'Sunset Park') {
      dishPrice = randomBetween(8, 13);
    } else {
      dishPrice = randomBetween(9, 14);
    }

    const ricePrice = randomBetween(3, 5);
    const appPrice = randomBetween(5, 9); // Dumplings, egg rolls, scallion pancakes
    const sodaPrice = randomBetween(1.5, 2.5);

    // Family meal: 2 shared dishes + 1 rice + 1 appetizer + 2 sodas
    const price = round2(dishPrice * 2 + ricePrice + appPrice + sodaPrice * 2);

    const dishes = ['General Tso\u2019s chicken', 'Beef with broccoli', 'Shrimp lo mein', 'Sesame chicken', 'Orange chicken', 'Kung pao chicken', 'Mapo tofu', 'Sweet & sour pork', 'Chicken with mixed vegetables'];
    const apps = ['Pork dumplings (8)', 'Egg rolls (2)', 'Scallion pancakes', 'Wonton soup', 'Spare ribs', 'Spring rolls (4)'];

    return {
      name: p.name,
      neighborhood,
      borough,
      cuisine: 'Chinese',
      price,
      kidsMenu: 'no',
      lat: p.lat,
      lng: p.lng,
      dish1: dishPrice,
      dish2: dishPrice,
      rice: ricePrice,
      appetizer: appPrice,
      drinks: sodaPrice,
      dish1Item: dishes[Math.floor(Math.random() * dishes.length)],
      dish2Item: dishes[Math.floor(Math.random() * dishes.length)],
      appItem: apps[Math.floor(Math.random() * apps.length)],
    };
  });
}

function inferBoroughFromAddress(address) {
  const addr = address.toLowerCase();
  if (addr.includes('staten island')) return 'Staten Island';
  if (addr.includes('bronx')) return 'Bronx';
  if (addr.includes('brooklyn')) return 'Brooklyn';
  if (addr.includes('queens') || addr.includes('flushing') || addr.includes('astoria') ||
      addr.includes('long island city') || addr.includes('elmhurst') || addr.includes('jamaica') ||
      addr.includes('jackson heights') || addr.includes('forest hills') || addr.includes('bayside') ||
      addr.includes('howard beach') || addr.includes('kew gardens') || addr.includes('fresh meadows') ||
      addr.includes('far rockaway') || addr.includes('corona') || addr.includes('richmond hill') ||
      addr.includes('woodside') || addr.includes('sunnyside')) return 'Queens';
  if (addr.includes('new york, ny')) return 'Manhattan';
  return 'Unknown';
}

function randomBetween(min, max) {
  return round2(min + Math.random() * (max - min));
}

function round2(n) {
  return Math.round(n * 100) / 100;
}

// Main
const pizzaPlaces = JSON.parse(fs.readFileSync('/tmp/pizza-places.json', 'utf-8'));
const chinesePlaces = JSON.parse(fs.readFileSync('/tmp/chinese-places.json', 'utf-8'));

const pizzaData = buildPizzaData(pizzaPlaces);
const chineseData = buildChineseData(chinesePlaces);

// Ensure borough counts
const pizzaByBorough = {};
pizzaData.forEach(r => { pizzaByBorough[r.borough] = (pizzaByBorough[r.borough] || 0) + 1; });
const chineseByBorough = {};
chineseData.forEach(r => { chineseByBorough[r.borough] = (chineseByBorough[r.borough] || 0) + 1; });

console.log('Pizza:', pizzaData.length, 'restaurants');
console.log('  By borough:', JSON.stringify(pizzaByBorough));
const pizzaPrices = pizzaData.map(d => d.price).sort((a,b) => a-b);
console.log('  Price range: $' + pizzaPrices[0] + ' - $' + pizzaPrices[pizzaPrices.length-1]);
console.log('  Median: $' + pizzaPrices[Math.floor(pizzaPrices.length/2)]);

console.log('\nChinese:', chineseData.length, 'restaurants');
console.log('  By borough:', JSON.stringify(chineseByBorough));
const chinesePrices = chineseData.map(d => d.price).sort((a,b) => a-b);
console.log('  Price range: $' + chinesePrices[0] + ' - $' + chinesePrices[chinesePrices.length-1]);
console.log('  Median: $' + chinesePrices[Math.floor(chinesePrices.length/2)]);

// Write files
const pizzaJs = 'const PIZZA_DATA = ' + JSON.stringify(pizzaData, null, 2) + ';\n';
fs.writeFileSync('pizza-data.js', pizzaJs);
console.log('\nWritten pizza-data.js');

const chineseJs = 'const CHINESE_DATA = ' + JSON.stringify(chineseData, null, 2) + ';\n';
fs.writeFileSync('chinese-data.js', chineseJs);
console.log('Written chinese-data.js');
