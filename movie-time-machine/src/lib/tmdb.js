import { TMDB_PROXY } from '../config'

// All TMDB traffic goes through the Cloudflare Worker in ../../worker/, which
// holds the API key as an encrypted secret. There is deliberately no
// direct-to-TMDB path: a key referenced here would be compiled into this
// bundle and published, which is the problem the Worker exists to solve.
// VITE_TMDB_PROXY only exists so a dev can point at a different Worker.
const BASE = (import.meta.env.VITE_TMDB_PROXY || TMDB_PROXY || '').replace(/\/$/, '')
const IMG_BASE = 'https://image.tmdb.org/t/p'

export const isConfigured = Boolean(BASE)

export const posterUrl = (path, size = 'w342') =>
  path ? `${IMG_BASE}/${size}${path}` : null

export const backdropUrl = (path) =>
  path ? `${IMG_BASE}/w1280${path}` : null

/**
 * Fetch movies that were likely in theaters on the given date.
 * Strategy: find movies released in the ~6 weeks before this date,
 * sorted by popularity (so bigger films surface first).
 */
export async function discoverMoviesInTheaters(dateStr, { page = 1, includeLimited = true } = {}) {
  const target = new Date(dateStr)
  const windowStart = new Date(target)
  windowStart.setDate(windowStart.getDate() - 42) // 6 weeks back

  const params = new URLSearchParams({
    'primary_release_date.gte': fmt(windowStart),
    'primary_release_date.lte': fmt(target),
    'with_release_type': includeLimited ? '2|3' : '2', // 2 = wide, 3 = limited
    region: 'US',
    sort_by: 'popularity.desc',
    page: String(page),
  })

  const res = await fetch(`${BASE}/discover/movie?${params}`)
  if (!res.ok) throw new Error(`TMDB error: ${res.status}`)
  return res.json()
}

export async function getMovieDetails(movieId) {
  const params = new URLSearchParams({
    append_to_response: 'credits',
  })
  const res = await fetch(`${BASE}/movie/${movieId}?${params}`)
  if (!res.ok) throw new Error(`TMDB error: ${res.status}`)
  return res.json()
}

export async function searchMovies(query) {
  const params = new URLSearchParams({
    query,
    include_adult: 'false',
  })
  const res = await fetch(`${BASE}/search/movie?${params}`)
  if (!res.ok) throw new Error(`TMDB error: ${res.status}`)
  const data = await res.json()
  return (data.results || []).slice(0, 8).map((m) => ({
    id: m.id,
    title: m.title,
    date: m.release_date || '',
    year: m.release_date?.slice(0, 4) || '',
    poster: posterUrl(m.poster_path, 'w92'),
    type: 'movie',
  }))
}

function fmt(d) {
  return d.toISOString().slice(0, 10)
}
