import tvData from '../data/tv-schedules.json'

const DAYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']

/**
 * Given a date string, find the matching TV season and return the
 * primetime lineup for that night of the week.
 *
 * TV seasons run roughly Sep–May. We map dates to the season that
 * was airing at the time.
 */
const SEASON_KEYS_SORTED = Object.keys(tvData).sort(
  (a, b) => parseInt(a.split('-')[0]) - parseInt(b.split('-')[0])
)

function nearestSeason(seasonKey) {
  if (!SEASON_KEYS_SORTED.length) return null
  if (tvData[seasonKey]) return seasonKey
  const target = parseInt(seasonKey.split('-')[0])
  const firstYear = parseInt(SEASON_KEYS_SORTED[0].split('-')[0])
  const lastYear = parseInt(SEASON_KEYS_SORTED[SEASON_KEYS_SORTED.length - 1].split('-')[0])
  if (target < firstYear) return SEASON_KEYS_SORTED[0]
  if (target > lastYear) return SEASON_KEYS_SORTED[SEASON_KEYS_SORTED.length - 1]
  // Find nearest by absolute year distance (ties prefer earlier)
  let best = SEASON_KEYS_SORTED[0]
  let bestDist = Infinity
  for (const k of SEASON_KEYS_SORTED) {
    const d = Math.abs(parseInt(k.split('-')[0]) - target)
    if (d < bestDist) {
      bestDist = d
      best = k
    }
  }
  return best
}

export function getTVSchedule(dateStr) {
  const date = new Date(dateStr + 'T12:00:00')
  const year = date.getFullYear()
  const month = date.getMonth() // 0-indexed

  // Determine which season: Sep–Dec = year–(year+1), Jan–Aug = (year-1)–year
  let seasonKey
  if (month >= 8) {
    seasonKey = `${year}-${year + 1}`
  } else {
    seasonKey = `${year - 1}-${year}`
  }

  const dayName = DAYS[date.getDay()]
  const resolvedKey = nearestSeason(seasonKey)
  if (!resolvedKey) return null

  const networks = tvData[resolvedKey][dayName] || []
  return {
    season: resolvedKey,
    day: dayName,
    networks,
    isFallback: resolvedKey !== seasonKey,
  }
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
