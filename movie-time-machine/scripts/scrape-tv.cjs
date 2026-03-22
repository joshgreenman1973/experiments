/**
 * Scrape historical TV schedules from epguides.com past grids.
 * Structure: <table id='Sunday'> ... <table id='Monday'> etc.
 * Header row: day name + time slots (6:00, 6:30, 7:00, etc.)
 * Data rows: network name + show cells with colspan spanning time slots
 *
 * Usage: node scripts/scrape-tv.cjs
 */

const fs = require('fs')
const path = require('path')

const YEARS = []
for (let y = 1970; y <= 2011; y++) YEARS.push(y)

const BASE_URL = 'http://epguides.com/grid/pastgrids.asp?gridYear='
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

async function fetchPage(year) {
  const url = `${BASE_URL}${year}+fall`
  console.log(`Fetching ${year}...`)
  const res = await fetch(url)
  if (!res.ok) {
    console.warn(`  Failed: ${res.status}`)
    return null
  }
  return res.text()
}

function stripHtml(str) {
  return str
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&nbsp;/g, ' ')
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .trim()
}

function parseSchedule(html) {
  const schedule = {}

  for (const day of DAYS) {
    // Find the table for this day: <table id='Sunday'>
    const tableRegex = new RegExp(`<table[^>]*id=['"]${day}['"][^>]*>([\\s\\S]*?)</table>`, 'i')
    const tableMatch = html.match(tableRegex)
    if (!tableMatch) continue

    const tableHtml = tableMatch[1]

    // Extract all rows
    const rows = []
    const rowRegex = /<tr[^>]*>([\s\S]*?)<\/tr>/gi
    let m
    while ((m = rowRegex.exec(tableHtml)) !== null) {
      rows.push(m[1])
    }

    if (rows.length < 2) continue // need header + at least one network row

    // Parse header row for time slots
    const headerCells = []
    const thRegex = /<th[^>]*>([\s\S]*?)<\/th>/gi
    while ((m = thRegex.exec(rows[0])) !== null) {
      headerCells.push(stripHtml(m[1]))
    }
    // First header cell is the day name, rest are time slots
    const timeSlots = headerCells.slice(1)

    // Parse network rows
    const networks = []
    for (let r = 1; r < rows.length; r++) {
      const row = rows[r]
      // Extract all td cells with their colspan
      const cells = []
      const tdRegex = /<td[^>]*?>([\s\S]*?)<\/td>/gi
      const colspanRegex = /colspan=['"]?(\d+)['"]?/i
      // Also need to capture the full td tag for colspan extraction
      const tdFullRegex = /<td([^>]*)>([\s\S]*?)<\/td>/gi
      while ((m = tdFullRegex.exec(row)) !== null) {
        const attrs = m[1]
        const colMatch = attrs.match(colspanRegex)
        const colspan = colMatch ? parseInt(colMatch[1]) : 1
        const content = stripHtml(m[2])
        cells.push({ content, colspan })
      }

      if (cells.length < 2) continue

      // First cell is the network name
      const networkName = cells[0].content.toUpperCase()
      if (!['ABC', 'CBS', 'NBC', 'FOX'].includes(networkName)) continue

      // Remaining cells are shows mapped to time slots
      // Times from epguides are Central — convert to Eastern (+1 hour)
      const shows = []
      let slotIdx = 0
      for (let c = 1; c < cells.length; c++) {
        const startSlot = slotIdx
        const startTime = timeSlots[startSlot] || ''
        const durationSlots = cells[c].colspan
        const showName = cells[c].content

        // Convert Central to Eastern
        let easternTime = startTime
        if (startTime) {
          const [h, mn] = startTime.split(':').map(Number)
          easternTime = `${h + 1}:${String(mn).padStart(2, '0')}`
        }

        if (showName) {
          shows.push({
            show: showName,
            time: easternTime,
            duration: durationSlots * 30, // minutes
          })
        }
        slotIdx += durationSlots
      }

      if (shows.length > 0) {
        networks.push({ network: networkName, shows })
      }
    }

    if (networks.length > 0) {
      schedule[day.toLowerCase()] = networks
    }
  }

  return schedule
}

async function main() {
  const allSchedules = {}

  for (const year of YEARS) {
    const html = await fetchPage(year)
    if (!html) continue

    const schedule = parseSchedule(html)
    const dayCount = Object.keys(schedule).length

    if (dayCount > 0) {
      allSchedules[`${year}-${year + 1}`] = schedule
      console.log(`  ${year}: ${dayCount} days`)
    } else {
      console.log(`  ${year}: no data parsed`)
    }

    // Be polite
    await new Promise((r) => setTimeout(r, 400))
  }

  const outPath = path.join(__dirname, '..', 'src', 'data', 'tv-schedules.json')
  fs.mkdirSync(path.dirname(outPath), { recursive: true })
  fs.writeFileSync(outPath, JSON.stringify(allSchedules, null, 2))
  console.log(`\nWrote ${Object.keys(allSchedules).length} seasons to ${outPath}`)
}

main().catch(console.error)
