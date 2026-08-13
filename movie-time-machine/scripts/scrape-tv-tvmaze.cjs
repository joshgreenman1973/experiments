/**
 * Scrape primetime TV schedules for 2012-2025 from TVMaze's free API.
 * Fetches a representative week (mid-October) for each season and
 * builds a day-of-week grid for ABC, CBS, NBC, and FOX.
 *
 * Usage: node scripts/scrape-tv-tvmaze.cjs
 */

const fs = require('fs')
const path = require('path')

const NETWORKS = ['ABC', 'CBS', 'NBC', 'FOX']
const PRIMETIME_START = 19 // 7 PM Eastern
const PRIMETIME_END = 23   // before 11 PM
const DAYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']

// Seasons to fetch: 2012-13 through the newest one that has actually started.
// Each season is sampled from a week in mid-October, so a year only becomes
// available once that week has aired -- asking earlier returns a half-empty
// grid. Seasons already present in the data file are skipped, so this is safe
// to re-run at any time.
const SEASON_YEARS = []
const now = new Date()
const newestSeasonYear =
  now.getMonth() > 9 || (now.getMonth() === 9 && now.getDate() >= 20)
    ? now.getFullYear()
    : now.getFullYear() - 1
for (let y = 2012; y <= newestSeasonYear; y++) SEASON_YEARS.push(y)

/** Find the first Sunday on or after Oct 1 of a given year */
function getRepresentativeSunday(year) {
  const d = new Date(`${year}-10-01T12:00:00`)
  while (d.getDay() !== 0) d.setDate(d.getDate() + 1)
  return d
}

/** Return an array of 7 date strings (Sun–Sat) for the rep week */
function getWeekDates(year) {
  const sunday = getRepresentativeSunday(year)
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(sunday)
    d.setDate(d.getDate() + i)
    return d.toISOString().slice(0, 10)
  })
}

async function fetchDaySchedule(dateStr) {
  const url = `https://api.tvmaze.com/schedule?country=US&date=${dateStr}`
  const res = await fetch(url)
  if (!res.ok) {
    console.warn(`  Failed ${dateStr}: ${res.status}`)
    return []
  }
  return res.json()
}

function parseDaySchedule(episodes) {
  // Group by network, filter to primetime major networks
  const byNetwork = {}

  for (const ep of episodes) {
    const netName = ep.show?.network?.name
    if (!NETWORKS.includes(netName)) continue

    const airtime = ep.airtime || ''
    if (!airtime) continue

    const [h] = airtime.split(':').map(Number)
    if (h < PRIMETIME_START || h >= PRIMETIME_END) continue

    const showName = ep.show?.name || ep.name
    const runtime = ep.runtime || 60

    if (!byNetwork[netName]) byNetwork[netName] = []

    // Only add if we don't already have this time slot (avoid double-listing repeat airs)
    const exists = byNetwork[netName].some(s => s.time === airtime)
    if (!exists) {
      byNetwork[netName].push({
        show: showName,
        time: airtime,
        duration: runtime,
      })
    }
  }

  // Sort shows within each network by airtime and build result array
  return NETWORKS
    .filter(n => byNetwork[n] && byNetwork[n].length > 0)
    .map(n => ({
      network: n,
      shows: byNetwork[n].sort((a, b) => a.time.localeCompare(b.time)),
    }))
}

async function main() {
  const outPath = path.join(__dirname, '..', 'src', 'data', 'tv-schedules.json')
  const existing = JSON.parse(fs.readFileSync(outPath, 'utf8'))
  console.log(`Existing seasons: ${Object.keys(existing).length}`)

  for (const year of SEASON_YEARS) {
    const seasonKey = `${year}-${year + 1}`

    if (existing[seasonKey]) {
      console.log(`Skipping ${seasonKey} (already present)`)
      continue
    }

    console.log(`\nFetching ${seasonKey}...`)
    const dates = getWeekDates(year)
    console.log(`  Week: ${dates[0]} through ${dates[6]}`)

    const season = {}

    for (const dateStr of dates) {
      const dayIndex = new Date(dateStr + 'T12:00:00').getDay()
      const dayName = DAYS[dayIndex]

      const episodes = await fetchDaySchedule(dateStr)
      const networks = parseDaySchedule(episodes)

      if (networks.length > 0) {
        season[dayName] = networks
        console.log(`  ${dayName}: ${networks.map(n => `${n.network}(${n.shows.length})`).join(' ')}`)
      } else {
        console.log(`  ${dayName}: no primetime data`)
      }

      // Be polite to TVMaze (free API, no auth needed, but be respectful)
      await new Promise(r => setTimeout(r, 300))
    }

    if (Object.keys(season).length > 0) {
      existing[seasonKey] = season
      console.log(`  -> Saved ${seasonKey}`)
    } else {
      console.log(`  -> No data for ${seasonKey}, skipping`)
    }
  }

  // Sort seasons by key
  const sorted = {}
  for (const key of Object.keys(existing).sort()) {
    sorted[key] = existing[key]
  }

  fs.writeFileSync(outPath, JSON.stringify(sorted, null, 2))
  console.log(`\nDone. Total seasons: ${Object.keys(sorted).length}`)
}

main().catch(console.error)
