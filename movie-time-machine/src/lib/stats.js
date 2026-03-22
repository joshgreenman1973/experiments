import tvData from '../data/tv-schedules.json'
import chartData from '../data/music-charts.json'

let cached = null

export function getCatalogStats() {
  if (cached) return cached

  // Count unique TV shows across all seasons
  const tvShowNames = new Set()
  const tvSeasons = Object.keys(tvData).length
  for (const season of Object.values(tvData)) {
    for (const networks of Object.values(season)) {
      for (const { shows } of networks) {
        for (const { show } of shows) {
          tvShowNames.add(show.toLowerCase())
        }
      }
    }
  }

  // Count chart entries and weeks
  const chartWeeks = Object.keys(chartData).length
  const songNames = new Set()
  let songEntries = 0
  for (const entries of Object.values(chartData)) {
    songEntries += entries.length
    for (const { title, artist } of entries) {
      songNames.add(`${title}|${artist}`.toLowerCase())
    }
  }

  cached = {
    tvShows: tvShowNames.size,
    tvSeasons,
    uniqueSongs: songNames.size,
    songEntries,
    chartWeeks,
  }
  return cached
}
