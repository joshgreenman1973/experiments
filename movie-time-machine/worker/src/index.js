// Cloudflare Worker: TMDB proxy for the Good Time Time Machine.
//
// Why this exists: the site is a static page on GitHub Pages, so anything the
// browser needs -- including an API key -- ends up readable in the published
// JavaScript. This Worker holds the TMDB key as an encrypted secret and makes
// the API calls itself, so the key never reaches the browser.
//
// It is deliberately narrow: only the three TMDB endpoints the app actually
// uses are allowed through, so it can't be repurposed as a general-purpose
// open proxy on someone else's TMDB quota.

const TMDB_BASE = 'https://api.themoviedb.org/3'

// Exact paths, plus one pattern for /movie/<numeric id>.
const ALLOWED_EXACT = new Set(['/discover/movie', '/search/movie'])
const ALLOWED_PATTERN = /^\/movie\/\d+$/

const PUBLIC_ORIGIN = 'https://joshgreenman1973.github.io'

// The published site, plus any local dev server port.
function isAllowedOrigin(origin) {
  return origin === PUBLIC_ORIGIN || /^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(origin)
}

// TMDB data for a given query changes slowly; cache at the edge to stay well
// inside the rate limit.
const CACHE_TTL_SECONDS = 60 * 60 * 6

function corsHeaders(request) {
  const origin = request.headers.get('Origin') || ''
  const allowed = isAllowedOrigin(origin) ? origin : PUBLIC_ORIGIN
  return {
    'Access-Control-Allow-Origin': allowed,
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    Vary: 'Origin',
  }
}

function json(body, status, request) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', ...corsHeaders(request) },
  })
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(request) })
    }
    if (request.method !== 'GET') {
      return json({ error: 'Method not allowed' }, 405, request)
    }
    if (!env.TMDB_API_KEY) {
      return json({ error: 'Proxy not configured: missing TMDB_API_KEY' }, 500, request)
    }

    const url = new URL(request.url)
    const path = url.pathname.replace(/\/$/, '')

    if (path === '' || path === '/') {
      return new Response(
        'Good Time Time Machine TMDB proxy. Allowed: /discover/movie, /search/movie, /movie/<id>',
        { status: 200, headers: { 'content-type': 'text/plain', ...corsHeaders(request) } }
      )
    }
    if (!ALLOWED_EXACT.has(path) && !ALLOWED_PATTERN.test(path)) {
      return json({ error: `Endpoint not allowed: ${path}` }, 403, request)
    }

    // Pass the client's query through, but never let it supply its own
    // credentials -- the key is ours to add.
    const params = new URLSearchParams(url.search)
    params.delete('api_key')
    params.delete('session_id')
    params.set('api_key', env.TMDB_API_KEY)

    let upstream
    try {
      upstream = await fetch(`${TMDB_BASE}${path}?${params}`, {
        cf: { cacheTtl: CACHE_TTL_SECONDS, cacheEverything: true },
      })
    } catch {
      return json({ error: 'Upstream request failed' }, 502, request)
    }

    if (!upstream.ok) {
      return json({ error: `TMDB error: ${upstream.status}` }, upstream.status, request)
    }

    const body = await upstream.text()
    return new Response(body, {
      status: 200,
      headers: {
        'content-type': 'application/json',
        'cache-control': `public, max-age=${CACHE_TTL_SECONDS}`,
        ...corsHeaders(request),
      },
    })
  },
}
