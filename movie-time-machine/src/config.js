// Public build configuration -- safe to commit.
//
// TMDB_PROXY is the URL of the Cloudflare Worker in ./worker, which holds the
// TMDB API key as an encrypted secret. It is a plain public URL, so keeping it
// here (rather than in .env) means any build -- local or CI -- produces a
// working site with no secrets involved.
//
// Leave it empty until the Worker is deployed; the app falls back to calling
// TMDB directly with VITE_TMDB_API_KEY from .env in that case.
export const TMDB_PROXY = ''
