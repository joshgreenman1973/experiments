// Shared helpers: tag a menu item into a homogeneous "core" category (for the
// BEC-style sub-index) and slugify item keys. Kept in one place so the panel
// builder and the history builder tag identically.

const CORE_RULES = [
  ['pizza_slice', /\b(plain|cheese|regular)\s+slice\b|\bslice of (cheese|plain)\b|\bpizza slice\b/],
  ['garlic_knots', /\bgarlic knots?\b/],
  // chicken over rice: require chicken tied directly to over-rice / rice-platter,
  // and never a soup. Avoids catching "chicken rice soup" or "grilled meat over rice".
  ['chicken_over_rice', /\bchicken\s+(over\s+(white\s+)?rice|rice\s+(platter|plate|bowl))\b(?!.*soup)/],
  ['fried_rice', /\bfried rice\b/],
  ['lo_mein', /\blo mein\b/],
  ['wonton_soup', /\bwonton soup\b/],
  ['spring_roll', /\bspring rolls?\b/],
  ['samosa', /\bsamosas?\b/],
  ['gyro', /\bgyros?\b/],
  ['falafel', /\bfalafel\b/],
  ['empanada', /\bempanadas?\b/],
  ['mozz_sticks', /\bmozzarella sticks?\b/],
  ['pho', /\bphở\b|\bpho\b/],
  ['quesadilla', /\bquesadillas?\b/],
  ['cheeseburger', /\bcheese ?burger\b/],
];

const CORE_LABELS = {
  pizza_slice: 'Plain pizza slice', garlic_knots: 'Garlic knots',
  chicken_over_rice: 'Chicken over rice', fried_rice: 'Fried rice',
  lo_mein: 'Lo mein', wonton_soup: 'Wonton soup', spring_roll: 'Spring roll',
  samosa: 'Samosa', gyro: 'Gyro', falafel: 'Falafel', empanada: 'Empanada',
  mozz_sticks: 'Mozzarella sticks', pho: 'Pho', quesadilla: 'Quesadilla',
  cheeseburger: 'Cheeseburger',
};

function coreCategory(itemName) {
  const s = String(itemName || '').toLowerCase();
  for (const [cat, re] of CORE_RULES) if (re.test(s)) return cat;
  return null;
}

function itemKey(itemName) {
  return String(itemName || '').toLowerCase().replace(/['’]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50);
}

module.exports = { coreCategory, itemKey, CORE_LABELS };
