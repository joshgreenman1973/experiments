// Public build configuration -- safe to commit.
//
// TMDB_PROXY is the URL of the Cloudflare Worker in ./worker, which holds the
// TMDB API key as an encrypted secret. It is a plain public URL, so keeping it
// here (rather than in .env) means any build -- local or CI -- produces a
// working site with no secrets involved.
//
// If this is ever emptied, the app falls back to calling TMDB directly with
// VITE_TMDB_API_KEY from .env -- which puts the key back in the bundle.
export const TMDB_PROXY = 'https://good-time-tmdb.josh-greenman.workers.dev'
