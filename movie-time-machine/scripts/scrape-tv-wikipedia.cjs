/**
 * Scrape historical primetime TV grids from Wikipedia season pages.
 * Covers the years before epguides (~1946 through 1969).
 *
 * Source: https://en.wikipedia.org/wiki/{startYear}%E2%80%93{endYY}_United_States_network_television_schedule
 *
 * Each page has 7 wikitables, one per night (id="Sunday" ... id="Saturday").
 * Header row: a "Network" cell (colspan=2) followed by 30-min time slot
 *   headers (7:00 PM, 7:30 PM, ..., 10:30 PM).
 * Each network is one row OR two rows (Fall/Summer split). We always take
 * the Fall lineup — that's what aired during the school-year season our
 * dataset is keyed on.
 *
 * Usage: node scripts/scrape-tv-wikipedia.cjs
 */

const fs = require('fs')
const path = require('path')

const NETWORKS = ['ABC', 'CBS', 'NBC', 'FOX', 'DuMont']
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

// Years to fetch (start year of season). Skip ones that already exist in JSON.
const START_YEARS = []
for (let y = 1946; y <= 1969; y++) START_YEARS.push(y)

function url(startYear) {
  const endYY = String((startYear + 1) % 100).padStart(2, '0')
  return `https://en.wikipedia.org/wiki/${startYear}%E2%80%93${endYY}_United_States_network_television_schedule`
}

async function fetchHtml(u, attempts = 3) {
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetch(u, { headers: { 'User-Agent': 'movie-time-machine-scraper/1.0' } })
      if (!res.ok) {
        console.log(`  HTTP ${res.status} on attempt ${i + 1}`)
      } else {
        return await res.text()
      }
    } catch (e) {
      console.log(`  fetch error attempt ${i + 1}: ${e.message}`)
    }
    await new Promise(r => setTimeout(r, 1500 * (i + 1)))
  }
  return null
}

function stripHtml(s) {
  return s
    .replace(/<small>[\s\S]*?<\/small>/gi, '')
    .replace(/<sup[^>]*>[\s\S]*?<\/sup>/gi, '')
    .replace(/<br\s*\/?>(\s*)/gi, ' ')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&nbsp;/g, ' ')
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&ndash;|&#8211;/g, '-')
    .replace(/&mdash;|&#8212;/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
}

function decodeEntities(s) {
  return s
    .replace(/&amp;/g, '&')
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&ndash;|&#8211;/g, '-')
}

/** Find the section for a given day and return the first wikitable HTML after it. */
function extractDayTable(html, day) {
  const idRe = new RegExp(`id="${day}"`, 'i')
  const idMatch = idRe.exec(html)
  if (!idMatch) return null
  const after = html.slice(idMatch.index)
  const tableRe = /<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>([\s\S]*?)<\/table>/i
  const m = tableRe.exec(after)
  return m ? m[1] : null
}

/** Split table HTML into rows (just the inner HTML of each <tr>). */
function getRows(tableHtml) {
  const rows = []
  const re = /<tr[^>]*>([\s\S]*?)<\/tr>/gi
  let m
  while ((m = re.exec(tableHtml)) !== null) rows.push(m[1])
  return rows
}

/** Get time-slot headers from the header row. Returns array like ['7:00','7:30',...] (24h). */
function parseHeaderTimes(headerRowHtml) {
  const ths = []
  const re = /<th[^>]*>([\s\S]*?)<\/th>/gi
  let m
  while ((m = re.exec(headerRowHtml)) !== null) ths.push(stripHtml(m[1]))
  // Drop leading "Network" cell(s) — keep only those that look like a time
  return ths
    .map((t) => t.match(/(\d{1,2}):(\d{2})\s*(AM|PM)?/i))
    .filter(Boolean)
    .map((m) => {
      let h = parseInt(m[1])
      const min = m[2]
      const ampm = (m[3] || 'PM').toUpperCase()
      if (ampm === 'PM' && h < 12) h += 12
      if (ampm === 'AM' && h === 12) h = 0
      return `${String(h).padStart(2, '0')}:${min}`
    })
}

/** Tokenize a row into cells with role and colspan. */
function getCells(rowHtml) {
  const cells = []
  const re = /<(th|td)\b([^>]*)>([\s\S]*?)<\/\1>/gi
  let m
  while ((m = re.exec(rowHtml)) !== null) {
    const tag = m[1].toLowerCase()
    const attrs = m[2]
    const inner = m[3]
    const cs = attrs.match(/colspan\s*=\s*"?(\d+)"?/i)
    const rs = attrs.match(/rowspan\s*=\s*"?(\d+)"?/i)
    cells.push({
      tag,
      colspan: cs ? parseInt(cs[1]) : 1,
      rowspan: rs ? parseInt(rs[1]) : 1,
      inner,
      text: stripHtml(inner),
    })
  }
  return cells
}

/** Try to identify a network from a row's leading <th> cell. */
function identifyNetwork(cells) {
  for (const c of cells) {
    if (c.tag !== 'th') continue
    const t = c.text.toUpperCase()
    for (const net of NETWORKS) {
      if (t === net.toUpperCase() || t.startsWith(net.toUpperCase())) return net
    }
    // Stop scanning past the first non-time th
    if (/AM|PM/.test(t) || /^\d{1,2}:\d{2}/.test(t)) break
  }
  return null
}

function isFallLabel(text) {
  return /^fall\b/i.test(text.trim())
}
function isSummerLabel(text) {
  return /^(summer|spring|winter|midseason|mid-season)\b/i.test(text.trim())
}

/**
 * Parse a day's table. Returns array of { network, shows: [{show, time}] }.
 * Strategy: walk rows, tracking pending network rowspans. For each row,
 * identify the network. If the row has a Fall/Summer label cell, prefer
 * the Fall row and skip Summer. Map the data <td> cells to time slots.
 */
function parseDay(tableHtml) {
  const rows = getRows(tableHtml)
  if (rows.length < 2) return []

  const headerCells = getCells(rows[0])
  const times = parseHeaderTimes(rows[0])
  if (!times.length) return []

  // For each network, accumulate {time: showName}. Last write wins, but we
  // process Fall first and skip Summer rows so Fall sticks.
  const byNetwork = {}

  // Track "carry" cells from rowspan>1 — but for this dataset we only need
  // the first row of each network (the Fall row when split). So a simpler
  // approach: process each row, identify the network, decide if it's Fall
  // or Summer, and if Summer, skip.

  let currentNetwork = null
  let currentSeasonLabel = null

  for (let i = 1; i < rows.length; i++) {
    const cells = getCells(rows[i])
    if (!cells.length) continue

    let idx = 0
    // Try network identification
    const net = identifyNetwork(cells)
    if (net) {
      currentNetwork = net
      currentSeasonLabel = null
      // Skip the network <th> cell (and any season label <th> right after)
      while (idx < cells.length && cells[idx].tag === 'th') {
        const t = cells[idx].text
        if (isFallLabel(t)) { currentSeasonLabel = 'fall'; idx++; break }
        if (isSummerLabel(t)) { currentSeasonLabel = 'summer'; idx++; break }
        idx++
        // Only skip the network th itself; if next isn't a season label, stop.
        if (idx < cells.length && cells[idx].tag !== 'th') break
      }
    } else {
      // Continuation row — likely Summer pair to a Fall row above
      // The first th is usually the season label
      if (cells[0].tag === 'th' && (isFallLabel(cells[0].text) || isSummerLabel(cells[0].text))) {
        currentSeasonLabel = isFallLabel(cells[0].text) ? 'fall' : 'summer'
        idx = 1
      } else if (!currentNetwork) {
        continue
      }
    }

    if (!currentNetwork) continue
    if (currentSeasonLabel === 'summer') continue // skip Summer lineups

    if (!byNetwork[currentNetwork]) byNetwork[currentNetwork] = {}

    // Walk data cells, mapping to time slots
    let slot = 0
    for (; idx < cells.length; idx++) {
      const c = cells[idx]
      if (c.tag !== 'td') continue
      if (slot >= times.length) break
      const time = times[slot]
      const text = c.text
      // Skip empty cells (often "no programming" placeholders)
      if (text && text.length > 0 && text.length < 200) {
        // Strip parenthetical annotations like "(B/W)", "(27/21.8)"
        let show = text.replace(/\s*\([^)]*\)/g, '').trim()
        // Strip leading "Local programming" variants — keep as is for transparency
        if (show && byNetwork[currentNetwork][time] === undefined) {
          byNetwork[currentNetwork][time] = show
        }
      }
      slot += c.colspan
    }
  }

  // Build result in preferred network order
  const out = []
  for (const net of NETWORKS) {
    const slots = byNetwork[net]
    if (!slots) continue
    const shows = Object.entries(slots)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([time, show]) => ({ show, time }))
    if (shows.length) out.push({ network: net, shows })
  }
  return out
}

async function main() {
  const outPath = path.join(__dirname, '..', 'src', 'data', 'tv-schedules.json')
  const existing = JSON.parse(fs.readFileSync(outPath, 'utf8'))
  console.log(`Existing seasons: ${Object.keys(existing).length}`)

  for (const startYear of START_YEARS) {
    const seasonKey = `${startYear}-${startYear + 1}`
    if (existing[seasonKey]) {
      console.log(`Skipping ${seasonKey} (already present)`)
      continue
    }

    const u = url(startYear)
    console.log(`\nFetching ${seasonKey} :: ${u}`)
    const html = await fetchHtml(u)
    if (!html) {
      console.log(`  Failed to fetch — skipping`)
      continue
    }

    const season = {}
    for (const Day of DAYS) {
      const tableHtml = extractDayTable(html, Day)
      if (!tableHtml) {
        console.log(`  ${Day}: no table`)
        continue
      }
      const networks = parseDay(tableHtml)
      if (networks.length) {
        season[Day.toLowerCase()] = networks
        console.log(`  ${Day}: ${networks.map(n => `${n.network}(${n.shows.length})`).join(' ')}`)
      } else {
        console.log(`  ${Day}: parsed nothing`)
      }
    }

    if (Object.keys(season).length > 0) {
      existing[seasonKey] = season
      // Persist incrementally so a crash doesn't lose work
      const sortedNow = {}
      for (const key of Object.keys(existing).sort()) sortedNow[key] = existing[key]
      fs.writeFileSync(outPath, JSON.stringify(sortedNow, null, 2))
      console.log(`  -> Saved ${seasonKey} (${Object.keys(season).length} days)`)
    }

    await new Promise(r => setTimeout(r, 800)) // be polite
  }

  // Final sort
  const sorted = {}
  for (const key of Object.keys(existing).sort()) sorted[key] = existing[key]

  fs.writeFileSync(outPath, JSON.stringify(sorted, null, 2))
  console.log(`\nDone. Total seasons: ${Object.keys(sorted).length}`)
}

main().catch(console.error)
