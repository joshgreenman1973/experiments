/**
 * Incremental Billboard Hot 100 update.
 *
 * Adds every chart week between the newest week already stored and today.
 * Unlike refresh-all-music.cjs (which re-checks all ~3,500 Saturdays), this
 * only fetches what's missing, so it's safe to run weekly from CI.
 *
 * Fails loudly (exit 1) if the source is unreachable or if weeks that should
 * exist come back empty -- a silent no-op would let the data quietly rot.
 *
 * Usage: node scripts/update-music.cjs
 */

const fs = require('fs')
const path = require('path')

const RAW_BASE = 'https://raw.githubusercontent.com/mhollingshead/billboard-hot-100/main/date'
const CHART_PATH = path.join(__dirname, '..', 'src', 'data', 'music-charts.json')

// A week older than this with no upstream data is a real gap, not just the
// chart not having been published yet.
const GRACE_DAYS = 14

async function fetchChart(dateStr, retries = 2) {
  const url = `${RAW_BASE}/${dateStr}.json`
  for (let i = 0; i <= retries; i++) {
    try {
      const res = await fetch(url)
      if (res.status === 404) return null
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      return data.data
        ?.filter((e) => e.this_week <= 5)
        .map((e) => ({
          rank: e.this_week,
          title: e.song,
          artist: e.artist,
          peakPosition: e.peak_position,
          weeksOnChart: e.weeks_on_chart,
        }))
    } catch (e) {
      if (i === retries) throw new Error(`${dateStr}: ${e.message}`)
      await new Promise((r) => setTimeout(r, 1500))
    }
  }
}

function daysAgo(dateStr) {
  return Math.floor((Date.now() - new Date(dateStr + 'T12:00:00').getTime()) / 86400000)
}

async function main() {
  const existing = JSON.parse(fs.readFileSync(CHART_PATH, 'utf8'))
  const dates = Object.keys(existing).sort()
  if (!dates.length) {
    throw new Error('music-charts.json is empty -- run refresh-all-music.cjs instead')
  }

  const last = dates[dates.length - 1]
  const today = new Date()
  const candidates = []
  for (const d = new Date(last + 'T12:00:00'); ; d.setDate(d.getDate() + 7)) {
    const str = d.toISOString().slice(0, 10)
    if (str === last) continue
    if (new Date(str + 'T12:00:00') > today) break
    candidates.push(str)
  }

  console.log(`Newest stored chart: ${last} (${daysAgo(last)} days old)`)
  if (!candidates.length) {
    console.log('Already current -- nothing to fetch.')
    return
  }
  console.log(`Fetching ${candidates.length} missing week(s)...`)

  const added = {}
  const missed = []
  for (const date of candidates) {
    const entries = await fetchChart(date)
    if (entries && entries.length > 0) {
      added[date] = entries
      console.log(`  ${date}  #1 ${entries[0].title} -- ${entries[0].artist}`)
    } else {
      missed.push(date)
      console.log(`  ${date}  no upstream data`)
    }
    await new Promise((r) => setTimeout(r, 120))
  }

  const staleMisses = missed.filter((d) => daysAgo(d) > GRACE_DAYS)
  if (Object.keys(added).length === 0) {
    throw new Error(
      `No charts returned for ${candidates.length} candidate week(s). ` +
        `The upstream feed may have moved or gone stale -- refusing to exit clean.`
    )
  }
  if (staleMisses.length) {
    throw new Error(
      `Missing upstream data for week(s) older than ${GRACE_DAYS} days: ${staleMisses.join(', ')}`
    )
  }

  const merged = {}
  for (const key of Object.keys({ ...existing, ...added }).sort()) {
    merged[key] = added[key] || existing[key]
  }
  fs.writeFileSync(CHART_PATH, JSON.stringify(merged, null, 2))

  const newest = Object.keys(merged).sort().pop()
  console.log(`\nAdded ${Object.keys(added).length} week(s). Newest chart is now ${newest}.`)
  console.log(`${Object.keys(merged).length} chart weeks total.`)
}

main().catch((err) => {
  console.error(`\nFAILED: ${err.message}`)
  process.exit(1)
})
