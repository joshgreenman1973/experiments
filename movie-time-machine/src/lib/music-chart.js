import chartData from '../data/music-charts.json'

// Pre-sort the chart dates for binary search
const chartDates = Object.keys(chartData).sort()

/**
 * Find the Billboard Hot 100 chart closest to the given date.
 * Charts are weekly — we find the nearest one.
 */
export function getChartForDate(dateStr) {
  if (!chartDates.length) return null

  const targetMs = new Date(dateStr + 'T12:00:00').getTime()

  // Binary search for closest date
  let lo = 0
  let hi = chartDates.length - 1
  let closest = chartDates[0]
  let closestDiff = Infinity

  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    const midMs = new Date(chartDates[mid] + 'T12:00:00').getTime()
    const diff = Math.abs(midMs - targetMs)

    if (diff < closestDiff) {
      closestDiff = diff
      closest = chartDates[mid]
    }

    if (midMs < targetMs) lo = mid + 1
    else if (midMs > targetMs) hi = mid - 1
    else break
  }

  // Only return if within ~10 days of the target
  if (closestDiff > 10 * 86400000) return null

  return {
    chartDate: closest,
    entries: chartData[closest],
  }
}

/**
 * Search songs across all chart weeks. Returns first appearances with chart date.
 */
export function searchSongs(query) {
  const q = query.toLowerCase()
  const results = []
  const seen = new Set()

  for (const [date, entries] of Object.entries(chartData)) {
    for (const entry of entries) {
      if (
        entry.title.toLowerCase().includes(q) ||
        entry.artist.toLowerCase().includes(q)
      ) {
        const key = `${entry.title}|${entry.artist}`
        if (seen.has(key)) continue
        seen.add(key)
        results.push({
          title: entry.title,
          artist: entry.artist,
          rank: entry.rank,
          date,
          type: 'music',
        })
      }
    }
  }

  // Sort by date descending (most recent first)
  results.sort((a, b) => b.date.localeCompare(a.date))
  return results.slice(0, 8)
}
