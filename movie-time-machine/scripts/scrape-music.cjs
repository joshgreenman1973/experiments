/**
 * Scrape Billboard Hot 100 top 5 from musicchartsarchive.com
 * for every available week (Dec 1976 – present).
 *
 * Usage: node scripts/scrape-music.cjs
 */

const fs = require('fs')
const path = require('path')

const BASE = 'https://musicchartsarchive.com'

async function fetchWithRetry(url, retries = 2) {
  for (let i = 0; i <= retries; i++) {
    try {
      const res = await fetch(url)
      if (res.status === 404) return null
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return await res.text()
    } catch (e) {
      if (i === retries) throw e
      await new Promise(r => setTimeout(r, 1000))
    }
  }
}

function parseChart(html) {
  // Extract table rows with rank, title, artist
  const entries = []
  // Look for table rows with chart data
  // Pattern: <td>rank</td> ... <a href="/singles/...">Title</a> ... <a href="/artists/...">Artist</a>
  const rowRegex = /<tr[^>]*>([\s\S]*?)<\/tr>/gi
  let m
  while ((m = rowRegex.exec(html)) !== null) {
    const row = m[1]
    // Extract cells
    const cells = []
    const tdRegex = /<td[^>]*>([\s\S]*?)<\/td>/gi
    let cm
    while ((cm = tdRegex.exec(row)) !== null) {
      cells.push(cm[1].replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&#?\w+;/g, '').trim())
    }
    // Also check for links to extract clean title/artist
    const links = []
    const linkRegex = /<a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi
    while ((cm = linkRegex.exec(row)) !== null) {
      links.push({ href: cm[1], text: cm[2].replace(/<[^>]+>/g, '').trim() })
    }

    // Try to extract rank (first number cell), title and artist from links
    const rankCell = cells.find(c => /^\d+$/.test(c))
    if (!rankCell) continue
    const rank = parseInt(rankCell)
    if (rank > 5) continue // only top 5

    const titleLink = links.find(l => l.href.includes('/singles/') || l.href.includes('/songs/'))
    const artistLink = links.find(l => l.href.includes('/artists/'))

    if (titleLink && artistLink) {
      entries.push({
        rank,
        title: titleLink.text,
        artist: artistLink.text,
      })
    }
  }

  return entries.sort((a, b) => a.rank - b.rank)
}

async function getWeeksForYear(year) {
  const url = `${BASE}/singles-charts/${year}`
  const html = await fetchWithRetry(url)
  if (!html) return []

  // Extract date links like /singles-chart/1977-01-01
  const dates = []
  const linkRegex = /\/singles-chart\/(\d{4}-\d{2}-\d{2})/g
  let m
  while ((m = linkRegex.exec(html)) !== null) {
    if (!dates.includes(m[1])) dates.push(m[1])
  }
  return dates.sort()
}

async function main() {
  const allCharts = {}
  const startYear = 1977 // first full year
  const endYear = new Date().getFullYear()

  // First, get all available week dates for each year
  console.log('Phase 1: Collecting chart dates...')
  const allDates = []
  for (let y = startYear; y <= endYear; y++) {
    const dates = await getWeeksForYear(y)
    allDates.push(...dates)
    console.log(`  ${y}: ${dates.length} weeks`)
    await new Promise(r => setTimeout(r, 300))
  }

  console.log(`\nPhase 2: Scraping ${allDates.length} charts (top 5 only)...`)
  let count = 0
  for (const date of allDates) {
    const url = `${BASE}/singles-chart/${date}`
    try {
      const html = await fetchWithRetry(url)
      if (!html) continue
      const entries = parseChart(html)
      if (entries.length > 0) {
        allCharts[date] = entries
        count++
      }
    } catch (e) {
      console.warn(`  Failed: ${date} - ${e.message}`)
    }

    if (count % 100 === 0 && count > 0) {
      console.log(`  ... ${count} charts scraped`)
    }
    await new Promise(r => setTimeout(r, 200))
  }

  const outPath = path.join(__dirname, '..', 'src', 'data', 'music-charts.json')
  fs.writeFileSync(outPath, JSON.stringify(allCharts, null, 2))
  console.log(`\nWrote ${count} charts to ${outPath}`)
}

main().catch(console.error)
