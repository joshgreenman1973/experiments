import tvData from '../data/tv-schedules.json'

const DAYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']

/**
 * Given a date string, find the matching TV season and return the
 * primetime lineup for that night of the week.
 *
 * TV seasons run roughly Sep–May. We map dates to the season that
 * was airing at the time.
 */
export function getTVSchedule(dateStr) {
  const date = new Date(dateStr + 'T12:00:00')
  const year = date.getFullYear()
  const month = date.getMonth() // 0-indexed

  // Determine which season: Sep–Dec = year–(year+1), Jan–Aug = (year-1)–year
  let seasonKey
  if (month >= 8) {
    // Sep–Dec
    seasonKey = `${year}-${year + 1}`
  } else {
    // Jan–Aug
    seasonKey = `${year - 1}-${year}`
  }

  const season = tvData[seasonKey]
  if (!season) {
    // Try adjacent seasons
    const fallback1 = `${year}-${year + 1}`
    const fallback2 = `${year - 1}-${year}`
    const s = tvData[fallback1] || tvData[fallback2]
    if (!s) return null
    const dayName = DAYS[date.getDay()]
    return { season: fallback1 in tvData ? fallback1 : fallback2, day: dayName, networks: s[dayName] || [] }
  }

  const dayName = DAYS[date.getDay()]
  const networks = season[dayName] || []

  return { season: seasonKey, day: dayName, networks }
}

export function formatTime(timeStr) {
  if (!timeStr) return ''
  const [h, m] = timeStr.split(':').map(Number)
  // All primetime times are PM (7:00-11:00 range)
  const displayH = h > 12 ? h - 12 : h
  return `${displayH}:${String(m).padStart(2, '0')} PM`
}

/**
 * Returns the range of years covered by the TV data.
 */
export function getTVCoverage() {
  const keys = Object.keys(tvData)
  if (!keys.length) return null
  const firstYear = parseInt(keys[keys.length - 1].split('-')[0])
  const lastYear = parseInt(keys[0].split('-')[1])
  return { firstYear, lastYear }
}

/**
 * Search TV shows across all seasons. Returns matches with season/day/network info.
 */
export function searchTVShows(query) {
  const q = query.toLowerCase()
  const results = []
  const seen = new Set()

  for (const [season, days] of Object.entries(tvData)) {
    for (const [day, networks] of Object.entries(days)) {
      for (const { network, shows } of networks) {
        for (const { show, time } of shows) {
          if (show.toLowerCase().includes(q)) {
            const key = `${show}|${season}`
            if (seen.has(key)) continue
            seen.add(key)
            results.push({
              title: show,
              season,
              day,
              network,
              time,
              type: 'tv',
              // Approximate a date in the middle of this season for navigation
              date: `${season.split('-')[0]}-10-15`,
            })
          }
        }
      }
    }
  }

  return results.slice(0, 8)
}
