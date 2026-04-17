/**
 * Backfill Billboard Hot 100 top 5 for pre-1962 dates.
 * Uses the GitHub API directory listing to find the exact dates available.
 *
 * Usage: node scripts/backfill-pre1962.cjs
 */

const fs = require('fs')
const path = require('path')

const RAW_BASE = 'https://raw.githubusercontent.com/mhollingshead/billboard-hot-100/main/date'
const CHART_PATH = path.join(__dirname, '..', 'src', 'data', 'music-charts.json')

async function getAvailableDates() {
  const res = await fetch('https://api.github.com/repos/mhollingshead/billboard-hot-100/contents/date', {
    headers: { 'User-Agent': 'movie-time-machine-backfill' }
  })
  const files = await res.json()
  return files
    .map(f => f.name.replace('.json', ''))
    .filter(d => d < '1962-01-01')
    .sort()
}

async function fetchChart(dateStr) {
  const url = `${RAW_BASE}/${dateStr}.json`
  const res = await fetch(url)
  if (!res.ok) return null
  const data = await res.json()
  return data.data
    ?.filter(e => e.this_week <= 5)
    .map(e => ({
      rank: e.this_week,
      title: e.song,
      artist: e.artist,
    }))
}

async function main() {
  const existing = JSON.parse(fs.readFileSync(CHART_PATH, 'utf8'))
  console.log(`Existing charts: ${Object.keys(existing).length}`)

  const dates = await getAvailableDates()
  console.log(`Pre-1962 dates to fetch: ${dates.length}`)
  console.log(`Range: ${dates[0]} to ${dates[dates.length - 1]}`)

  let added = 0
  let skipped = 0

  for (const date of dates) {
    if (existing[date]) { skipped++; continue }

    const entries = await fetchChart(date)
    if (entries && entries.length > 0) {
      existing[date] = entries
      added++
      console.log(`  + ${date}: ${entries[0].title} — ${entries[0].artist}`)
    }

    await new Promise(r => setTimeout(r, 100))
  }

  console.log(`\nAdded ${added} charts, skipped ${skipped} already present`)

  const sorted = {}
  for (const key of Object.keys(existing).sort()) sorted[key] = existing[key]

  fs.writeFileSync(CHART_PATH, JSON.stringify(sorted, null, 2))
  console.log(`Total charts: ${Object.keys(sorted).length}`)
}

main().catch(console.error)
