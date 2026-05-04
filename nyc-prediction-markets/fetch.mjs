// Fetch NYC/NYS political prediction markets from Polymarket, Kalshi, Manifold.
// Writes data/markets.json + data/history/YYYY-MM-DD-HH.json.

import fs from "node:fs/promises";
import path from "node:path";

const ROOT = path.dirname(new URL(import.meta.url).pathname);
const DATA_DIR = path.join(ROOT, "data");
const HISTORY_DIR = path.join(DATA_DIR, "history");

// ---------- keyword config ----------

// Strong NY signals — a hit on any of these alone qualifies a market.
const STRONG_KEYWORDS = [
  "Mamdani",
  "Hochul",
  "Cuomo",
  "Letitia James",
  "Tish James",
  "Jumaane Williams",
  "Brad Lander",
  "Zellnor Myrie",
  "Scott Stringer",
  "Ritchie Torres",
  "Dan Goldman",
  "Jessica Ramos",
  "Curtis Sliwa",
  "Sliwa",
  "Stefanik",
  "Gillibrand",
  "Schumer",
  "Ocasio-Cortez",
  "AOC",
  "New York City",
  "NYC",
  "New York State",
  "NY governor",
  "NY Governor",
  "NY-Gov",
  "NY Senate",
  "NY senate",
  "Albany",
  "MTA",
  "NYPD",
  "Rikers",
  "congestion pricing",
  "City Hall",
  "rent stabilization",
  "Bronx",
  "Brooklyn",
  "Queens DA",
  "Manhattan DA",
];

// Ambiguous tokens — must co-occur with a NY context keyword to qualify.
// Note: "James" deliberately excludes "New York" from context to avoid Knicks
// games (LeBron James + New York). Same idea for the others.
const AMBIGUOUS = [
  { token: "Adams", context: ["mayor", "Eric Adams", "City Hall"] },
  { token: "Lander", context: ["comptroller", "mayor", "Brad Lander"] },
  { token: "Stringer", context: ["comptroller", "Scott Stringer"] },
  { token: "James", context: ["Letitia", "Tish", "attorney general"] },
  { token: "Williams", context: ["Jumaane", "public advocate"] },
];

// Sports/entertainment exclusions — if any of these appear in the title, skip.
// "New York" alone shouldn't qualify a Knicks/Mets/Yankees market.
const EXCLUDE_RE =
  /\b(Knicks|Yankees|Mets|Giants|Jets|Rangers|Nets|Islanders|Liberty|Red Bulls|NYCFC|New York City FC|NY Marathon|NYC Marathon|MLS Cup|MLB|NBA|NHL|NFL|UFC|WNBA|NCAA|Champions League|Premier League|Bundesliga|La Liga|Super Bowl|World Series|Stanley Cup|Final Four|Eurovision|Oscars|Grammys|Emmys|box office|temperature|rainfall|snowfall|inches of (?:rain|snow))\b/i;

// Word-boundary regex for a list of literal phrases (case-insensitive).
function buildRegex(phrases) {
  const escaped = phrases.map((p) =>
    p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
  );
  return new RegExp(`\\b(?:${escaped.join("|")})\\b`, "i");
}

const STRONG_RE = buildRegex(STRONG_KEYWORDS);

// ---------- topic rules ----------
// Each rule: a question matching `pattern` gets tagged with `id` + human label.
// First matching rule wins. The dashboard groups markets sharing an id and
// surfaces those with 2+ platforms as side-by-side comparisons.
//
// Be conservative — these should describe the SAME outcome and the SAME time
// window. Different time windows on the same outcome get distinct ids.

const TOPIC_RULES = [
  { id: "mamdani-rent-freeze-2026", label: "Mamdani freezes NYC rent in 2026",
    pattern: /mamdani.*(?:freeze|freezes).*rent.*(?:in 2026|2026)\b/i },
  { id: "mamdani-rent-freeze-before-2027", label: "Mamdani freezes NYC rent before 2027",
    pattern: /mamdani.*(?:freeze|freezes).*rent.*before 2027/i },
  { id: "mamdani-grocery-before-2028", label: "Mamdani opens city-owned grocery store before 2028",
    pattern: /mamdani.*(?:city-owned )?grocery.*(?:before 2028|in 2027|by 2028)/i },
  { id: "mamdani-min-wage-30-before-2027", label: "Mamdani raises minimum wage to $30 before 2027",
    pattern: /mamdani.*minimum wage.*\$?30.*before 2027/i },
  { id: "mamdani-reelected-2029", label: "Mamdani re-elected NYC mayor (2029)",
    pattern: /mamdani.*re-?elected/i },

  { id: "mamdani-2028-dem-nom", label: "Mamdani wins 2028 Democratic presidential nomination",
    pattern: /mamdani.*2028.*democratic.*(?:presidential )?nomination/i },
  { id: "mamdani-2028-president", label: "Mamdani wins 2028 US presidential election",
    pattern: /mamdani.*2028 us presidential election/i },

  { id: "aoc-2028-dem-nom", label: "Ocasio-Cortez wins 2028 Democratic presidential nomination",
    pattern: /(?:ocasio-cortez|\baoc\b).*2028.*democratic.*(?:presidential )?nomination/i },
  { id: "aoc-2028-president", label: "Ocasio-Cortez wins 2028 US presidential election",
    pattern: /(?:ocasio-cortez|\baoc\b).*(?:2028 us presidential election|elected (?:u\.s\.|us) president in 2028|be elected president in 2028)/i },
  { id: "aoc-runs-2028", label: "AOC runs for president in 2028",
    pattern: /\baoc\b.*run for president in 2028|aoc.*announce(?:s|d)? (?:a |her )?presidential run|alexandria ocasio-cortez announce a presidential run/i },
  { id: "aoc-senate-2028", label: "AOC runs for Senate in 2028",
    pattern: /(?:ocasio-cortez|\baoc\b).*(?:run for senate|senate run).*2028|alexandria ocasio-cortez run for senate in 2028/i },

  { id: "stefanik-2028-rep-nom", label: "Stefanik wins 2028 Republican presidential nomination",
    pattern: /stefanik.*2028.*republican.*(?:presidential )?nomination/i },

  { id: "ny-gov-2026-dem-primary", label: "Winner of 2026 NY Democratic gubernatorial primary",
    pattern: /(?:hochul|delgado|democratic).*2026.*new york.*(?:democratic )?gubernatorial primary|2026 new york democratic gubernatorial primary/i },
  { id: "ny-gov-2026-rep-primary", label: "Winner of 2026 NY Republican gubernatorial primary",
    pattern: /2026 new york governor republican primary/i },
  { id: "ny-gov-2026-general", label: "Democrats win 2026 NY governor's race",
    pattern: /(?:democrats win the new york governor race in 2026|2026 new york state gubernatorial election|next governor of new york after kathy hochul)/i },

  { id: "schumer-leader-before-end-2026", label: "Schumer steps down as Senate leader before end of 2026",
    pattern: /schumer.*(?:stop being|cease|out as).*(?:senate.*leader|leader.*senate|minority leader).*(?:before (?:the end of |nov 3,? )2026|end of 2026)/i },
  { id: "schumer-leader-before-end-2030", label: "Schumer steps down as Senate leader before 2030",
    pattern: /schumer.*(?:stop being|cease).*(?:senate.*leader|leader.*senate).*before 2030/i },

  { id: "congestion-pricing-ends-2027", label: "NYC congestion pricing ends before 2027",
    pattern: /congestion pricing.*(?:end|ends|ended).*(?:before 2027|in 2027)/i },
];

function tagTopic(question) {
  if (!question) return { topic_id: null, topic_label: null };
  for (const rule of TOPIC_RULES) {
    if (rule.pattern.test(question)) {
      return { topic_id: rule.id, topic_label: rule.label };
    }
  }
  return { topic_id: null, topic_label: null };
}

function matchesNY(text, extraTags = []) {
  if (!text) return { match: false, hits: [] };
  const haystack = [text, ...extraTags].join(" ");
  if (EXCLUDE_RE.test(haystack)) return { match: false, hits: [] };
  const hits = [];

  // Tag-based catch-all (Polymarket/Kalshi categories sometimes say "New York")
  for (const tag of extraTags) {
    if (/new york/i.test(tag)) hits.push(`tag:${tag}`);
  }

  // Strong keywords
  const strong = haystack.match(STRONG_RE);
  if (strong) hits.push(strong[0]);

  // Ambiguous tokens (require co-occurring context)
  for (const { token, context } of AMBIGUOUS) {
    const tokenRe = new RegExp(`\\b${token}\\b`, "i");
    if (!tokenRe.test(haystack)) continue;
    const ctxRe = buildRegex(context);
    if (ctxRe.test(haystack)) hits.push(`${token}+context`);
  }

  return { match: hits.length > 0, hits: [...new Set(hits)] };
}

// ---------- helpers ----------

async function getJson(url, opts = {}) {
  const res = await fetch(url, {
    ...opts,
    headers: {
      "User-Agent": "nyc-prediction-markets/0.1 (github.com/joshgreenman1973)",
      Accept: "application/json",
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} for ${url}`);
  }
  return res.json();
}

function num(x) {
  if (x === null || x === undefined || x === "") return null;
  const n = typeof x === "number" ? x : Number(x);
  return Number.isFinite(n) ? n : null;
}

// ---------- Polymarket ----------

async function fetchPolymarket() {
  const out = [];
  const limit = 500;
  let offset = 0;
  // Cap pagination so we don't loop forever if the API misbehaves.
  for (let page = 0; page < 20; page++) {
    const url = `https://gamma-api.polymarket.com/markets?closed=false&limit=${limit}&offset=${offset}`;
    let batch;
    try {
      batch = await getJson(url);
    } catch (e) {
      console.error(`[polymarket] page ${page} error:`, e.message);
      break;
    }
    if (!Array.isArray(batch) || batch.length === 0) break;
    for (const m of batch) {
      const question = m.question || m.title || "";
      const tags = [];
      if (Array.isArray(m.events)) {
        for (const ev of m.events) {
          if (ev?.title) tags.push(ev.title);
          if (ev?.slug) tags.push(ev.slug);
        }
      }
      if (m.category) tags.push(m.category);
      const verdict = matchesNY(question, tags);
      if (!verdict.match) continue;

      // outcomePrices is a JSON-encoded string like "[\"0.42\", \"0.58\"]"
      let yesPrice = null;
      try {
        const prices = typeof m.outcomePrices === "string"
          ? JSON.parse(m.outcomePrices)
          : m.outcomePrices;
        const outcomes = typeof m.outcomes === "string"
          ? JSON.parse(m.outcomes)
          : m.outcomes;
        if (Array.isArray(prices) && prices.length > 0) {
          // For Yes/No markets, take the Yes price; else first outcome.
          if (Array.isArray(outcomes)) {
            const yi = outcomes.findIndex(
              (o) => typeof o === "string" && o.toLowerCase() === "yes",
            );
            if (yi >= 0) yesPrice = num(prices[yi]);
          }
          if (yesPrice === null) yesPrice = num(prices[0]);
        }
      } catch {
        /* ignore */
      }

      const eventSlug = m.events?.[0]?.slug || m.slug;
      const topic = tagTopic(question);
      out.push({
        source: "polymarket",
        id: String(m.id ?? m.slug ?? m.conditionId ?? ""),
        question,
        url: eventSlug ? `https://polymarket.com/event/${eventSlug}` : null,
        yes_price: yesPrice,
        volume_usd: num(m.volume),
        liquidity_usd: num(m.liquidity),
        open_interest_usd: null,
        close_date: m.endDate || m.end_date_iso || null,
        matched_keywords: verdict.hits,
        topic_id: topic.topic_id,
        topic_label: topic.topic_label,
      });
    }
    if (batch.length < limit) break;
    offset += limit;
  }
  return out;
}

// ---------- Kalshi ----------

// Kalshi uses /events with nested markets — much cleaner than the raw
// markets endpoint, which is dominated by sports parlay sub-markets.
async function fetchKalshi() {
  const out = [];
  let cursor = "";
  for (let page = 0; page < 60; page++) {
    const url = `https://api.elections.kalshi.com/trade-api/v2/events?status=open&limit=200&with_nested_markets=true${
      cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""
    }`;
    let body;
    try {
      body = await getJson(url);
    } catch (e) {
      console.error(`[kalshi] page ${page} error:`, e.message);
      // Brief pause and retry once on rate limit
      if (/429/.test(e.message)) {
        await new Promise((r) => setTimeout(r, 3000));
        try {
          body = await getJson(url);
        } catch (e2) {
          console.error(`[kalshi] retry failed:`, e2.message);
          break;
        }
      } else {
        break;
      }
    }
    const events = body?.events || [];
    if (events.length === 0) break;

    for (const ev of events) {
      const title = ev.title || "";
      const subtitle = ev.sub_title || "";
      const tags = [ev.category, ev.series_ticker, ev.event_ticker].filter(Boolean);

      // Skip obvious sports/entertainment series tickers
      if (
        /^(KXNFL|KXNBA|KXNHL|KXMLB|KXSOCCER|KXMVE|KXMVECROSSCATEGORY|KXMVESPORTS|KXUFC|KXTENNIS|KXGOLF|KXOSCAR|KXGRAMM|KXEMMY)/i.test(
          ev.event_ticker || "",
        )
      ) {
        continue;
      }

      const verdict = matchesNY(`${title} ${subtitle}`, tags);
      if (!verdict.match) continue;

      const markets = ev.markets || [];
      // For multi-outcome events (e.g. "NYC Mayor 2025 winner"), emit one row
      // per nested market so each candidate's contract is visible.
      for (const m of markets) {
        if (m.status && m.status !== "active") continue;
        const mTitle = m.yes_sub_title || m.subtitle || m.title || "";
        // New "_dollars" fields are already decimal probabilities (e.g. "0.42").
        // Fall back to legacy cents-based fields if missing.
        const yesPrice =
          num(m.last_price_dollars) ??
          num(m.yes_bid_dollars) ??
          num(m.yes_ask_dollars) ??
          (num(m.last_price) !== null ? num(m.last_price) / 100 : null);
        const volume = num(m.volume_fp) ?? num(m.volume);
        const oi = num(m.open_interest_fp) ?? num(m.open_interest);
        const fullQuestion = mTitle ? `${title} — ${mTitle}` : title;
        const topic = tagTopic(fullQuestion);
        out.push({
          source: "kalshi",
          id: m.ticker,
          question: fullQuestion,
          url: ev.event_ticker
            ? `https://kalshi.com/markets/${ev.event_ticker.toLowerCase()}`
            : null,
          yes_price: yesPrice,
          volume_usd: volume,
          liquidity_usd: num(m.liquidity_dollars),
          open_interest_usd: oi,
          close_date: m.close_time || ev.close_time || null,
          matched_keywords: verdict.hits,
          topic_id: topic.topic_id,
          topic_label: topic.topic_label,
        });
      }
    }

    cursor = body.cursor || "";
    if (!cursor) break;
    // Be polite — Kalshi rate limits aggressively.
    await new Promise((r) => setTimeout(r, 250));
  }
  return out;
}

// ---------- Manifold ----------

// Manifold's /v0/markets is huge; per-keyword search-markets is faster.
// We dedupe by id.
const MANIFOLD_QUERIES = [
  "Mamdani",
  "Hochul",
  "Eric Adams",
  "Cuomo",
  "Letitia James",
  "Tish James",
  "Jumaane Williams",
  "Brad Lander",
  "Stefanik",
  "Gillibrand",
  "Schumer",
  "AOC",
  "Ocasio-Cortez",
  "New York City",
  "New York State",
  "NYC mayor",
  "NY governor",
  "MTA",
  "NYPD",
  "Rikers",
  "congestion pricing",
  "rent stabilization",
];

async function fetchManifold() {
  const seen = new Map();
  for (const q of MANIFOLD_QUERIES) {
    const url = `https://api.manifold.markets/v0/search-markets?term=${encodeURIComponent(
      q,
    )}&limit=100`;
    let batch;
    try {
      batch = await getJson(url);
    } catch (e) {
      console.error(`[manifold] query "${q}" error:`, e.message);
      continue;
    }
    if (!Array.isArray(batch)) continue;
    for (const m of batch) {
      if (m.isResolved) continue;
      const text = `${m.question || ""} ${m.textDescription || ""}`;
      const tags = Array.isArray(m.groupSlugs) ? m.groupSlugs : [];
      const verdict = matchesNY(text, tags);
      if (!verdict.match) continue;
      if (seen.has(m.id)) {
        // merge any new hits
        const existing = seen.get(m.id);
        existing.matched_keywords = [
          ...new Set([...existing.matched_keywords, ...verdict.hits]),
        ];
        continue;
      }
      const topic = tagTopic(m.question);
      seen.set(m.id, {
        source: "manifold",
        id: m.id,
        question: m.question,
        url: m.url,
        yes_price: num(m.probability),
        volume_mana: num(m.volume),
        volume_usd: null, // Manifold uses play money
        liquidity_usd: null,
        open_interest_usd: null,
        close_date: m.closeTime ? new Date(m.closeTime).toISOString() : null,
        matched_keywords: verdict.hits,
        topic_id: topic.topic_id,
        topic_label: topic.topic_label,
      });
    }
  }
  return [...seen.values()];
}

// ---------- price history merge ----------

async function loadMostRecentBefore(targetMs) {
  let files;
  try {
    files = await fs.readdir(HISTORY_DIR);
  } catch {
    return null;
  }
  const candidates = files
    .filter((f) => f.endsWith(".json"))
    .map((f) => ({
      file: f,
      ms: Date.parse(f.replace(".json", "").replace(/-(\d{2})$/, "T$1:00:00Z")),
    }))
    .filter((c) => Number.isFinite(c.ms) && c.ms <= targetMs)
    .sort((a, b) => b.ms - a.ms);
  if (candidates.length === 0) return null;
  try {
    const raw = await fs.readFile(
      path.join(HISTORY_DIR, candidates[0].file),
      "utf8",
    );
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function priceKey(m) {
  return `${m.source}:${m.id}`;
}

// ---------- main ----------

async function main() {
  await fs.mkdir(HISTORY_DIR, { recursive: true });

  console.log("Fetching Polymarket...");
  const poly = await fetchPolymarket();
  console.log(`  ${poly.length} matched`);

  console.log("Fetching Kalshi...");
  const kalshi = await fetchKalshi();
  console.log(`  ${kalshi.length} matched`);

  console.log("Fetching Manifold...");
  const manifold = await fetchManifold();
  console.log(`  ${manifold.length} matched`);

  const all = [...poly, ...kalshi, ...manifold];

  // 24h price-change merge from history
  const yesterday = await loadMostRecentBefore(Date.now() - 23 * 3600 * 1000);
  const yMap = new Map();
  if (yesterday?.markets) {
    for (const m of yesterday.markets) {
      yMap.set(priceKey(m), m.yes_price);
    }
  }
  for (const m of all) {
    const prev = yMap.get(priceKey(m));
    m.price_24h_ago = typeof prev === "number" ? prev : null;
    m.price_change_24h =
      typeof prev === "number" && typeof m.yes_price === "number"
        ? +(m.yes_price - prev).toFixed(4)
        : null;
  }

  const now = new Date();
  const out = {
    updated_at: now.toISOString(),
    source_counts: {
      polymarket: poly.length,
      kalshi: kalshi.length,
      manifold: manifold.length,
    },
    markets: all,
  };

  await fs.writeFile(
    path.join(DATA_DIR, "markets.json"),
    JSON.stringify(out, null, 2),
  );

  // Snapshot file: YYYY-MM-DD-HH.json
  const yyyy = now.getUTCFullYear();
  const mm = String(now.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(now.getUTCDate()).padStart(2, "0");
  const hh = String(now.getUTCHours()).padStart(2, "0");
  const snapName = `${yyyy}-${mm}-${dd}-${hh}.json`;
  await fs.writeFile(
    path.join(HISTORY_DIR, snapName),
    JSON.stringify(out, null, 2),
  );

  console.log(
    `Wrote ${all.length} markets to data/markets.json and history/${snapName}`,
  );
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
