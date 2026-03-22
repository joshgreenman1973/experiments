/**
 * Replace all chart data with billboard-hot-100 GitHub data.
 * Fetches top 5 for every available chart week from 1958 to present.
 *
 * Usage: node scripts/refresh-all-music.cjs
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
      peakPosition: e.peak_position,
      weeksOnChart: e.weeks_on_chart,
    }))
}

async function main() {
  // Load existing data to keep musicchartsarchive entries as fallback
  const existing = JSON.parse(fs.readFileSync(CHART_PATH, 'utf8'))
  const allCharts = {}
  let replaced = 0
  let kept = 0
  let added = 0

  // Generate candidate dates: every Saturday from 1958 to now
  const dates = []
  const end = new Date()
  for (let d = new Date('1958-01-04'); d <= end; d.setDate(d.getDate() + 7)) {
    dates.push(d.toISOString().slice(0, 10))
  }
  console.log(`Checking ${dates.length} Saturdays...`)

  for (let i = 0; i < dates.length; i++) {
    const date = dates[i]
    const entries = await fetchChart(date)

    if (entries && entries.length > 0) {
      allCharts[date] = entries
      if (existing[date]) replaced++
      else added++
    } else if (existing[date]) {
      // Keep existing musicchartsarchive data as fallback
      allCharts[date] = existing[date]
      kept++
    }

    if ((i + 1) % 200 === 0) {
      console.log(`  ... ${i + 1}/${dates.length} checked (${replaced} replaced, ${added} added, ${kept} kept)`)
    }

    await new Promise((r) => setTimeout(r, 80))
  }

  // Also keep any existing entries on non-Saturday dates
  for (const [date, entries] of Object.entries(existing)) {
    if (!allCharts[date]) {
      allCharts[date] = entries
      kept++
    }
  }

  // Sort by date
  const sorted = {}
  for (const key of Object.keys(allCharts).sort()) {
    sorted[key] = allCharts[key]
  }

  fs.writeFileSync(CHART_PATH, JSON.stringify(sorted, null, 2))
  console.log(`\nDone: ${Object.keys(sorted).length} total charts`)
  console.log(`  ${replaced} replaced with GitHub data`)
  console.log(`  ${added} new from GitHub`)
  console.log(`  ${kept} kept from musicchartsarchive`)
}

main().catch(console.error)
