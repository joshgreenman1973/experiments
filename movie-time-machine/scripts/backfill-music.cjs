/**
 * Backfill Billboard Hot 100 top 5 for 1958–1976 from
 * github.com/mhollingshead/billboard-hot-100
 *
 * Usage: node scripts/backfill-music.cjs
 */

const fs = require('fs')
const path = require('path')

const RAW_BASE = 'https://raw.githubusercontent.com/mhollingshead/billboard-hot-100/main/date'
const CHART_PATH = path.join(__dirname, '..', 'src', 'data', 'music-charts.json')

async function fetchChart(dateStr) {
  const url = `${RAW_BASE}/${dateStr}.json`
  const res = await fetch(url)
  if (!res.ok) return null
  const data = await res.json()
  return data.data
    ?.filter((e) => e.this_week <= 5)
    .map((e) => ({
      rank: e.this_week,
      title: e.song,
      artist: e.artist,
    }))
}

async function getAvailableDates() {
  // Fetch the repo's date directory listing via GitHub API
  // We'll paginate through all files from 1958 to 1976
  const dates = []
  const startYear = 1958
  const endYear = 1976

  for (let y = startYear; y <= endYear; y++) {
    // Fetch the year index page to find all chart dates
    // GitHub raw doesn't have directory listing, so we'll generate
    // dates weekly (Saturday) which is when Billboard charts are dated
    const start = new Date(`${y}-01-01`)
    const end = new Date(`${y}-12-31`)

    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      // Billboard charts are typically dated on Saturdays
      if (d.getDay() === 6) {
        dates.push(d.toISOString().slice(0, 10))
      }
    }
  }

  return dates
}

async function main() {
  const existing = JSON.parse(fs.readFileSync(CHART_PATH, 'utf8'))
  const existingCount = Object.keys(existing).length
  console.log(`Existing charts: ${existingCount}`)

  const dates = await getAvailableDates()
  console.log(`Candidate dates to check: ${dates.length}`)

  let added = 0
  let failed = 0

  for (const date of dates) {
    if (existing[date]) continue // already have it

    const entries = await fetchChart(date)
    if (entries && entries.length > 0) {
      existing[date] = entries
      added++
      if (added % 50 === 0) console.log(`  ... ${added} charts added`)
    } else {
      failed++
    }

    // Be polite to GitHub
    await new Promise((r) => setTimeout(r, 100))
  }

  console.log(`\nAdded ${added} charts, ${failed} dates had no data`)

  // Sort by date
  const sorted = {}
  for (const key of Object.keys(existing).sort()) {
    sorted[key] = existing[key]
  }

  fs.writeFileSync(CHART_PATH, JSON.stringify(sorted, null, 2))
  console.log(`Total charts: ${Object.keys(sorted).length}`)
}

main().catch(console.error)
