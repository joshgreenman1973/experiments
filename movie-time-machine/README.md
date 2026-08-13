# Good Time Time Machine

Pick a date from the last 50-odd years and see what was playing in movie theaters, on TV and on the radio.

Live: https://joshgreenman1973.github.io/experiments/movie-time-machine/dist/

## Where the three panels get their data

| Panel | Source | How it updates |
| --- | --- | --- |
| At the Movies | TMDB API, queried live | Always current; nothing to refresh |
| On TV | `src/data/tv-schedules.json` (Wikipedia, epguides.com, TVMaze) | One new primetime season each autumn |
| On the Radio | `src/data/music-charts.json` (Billboard Hot 100) | New chart week every Saturday |

TV and music data are bundled into the JavaScript at build time, so refreshing
either one means rebuilding the site and committing `dist/`.

## Keeping the data current

`.github/workflows/good-time-music-refresh.yml` (in the repo root) runs every
Sunday: it fetches any new chart weeks, adds the new TV season once one has
started, rebuilds, and commits. Both scripts fail loudly rather than exiting
quietly if a source has moved, so a silent rot shows up as a failed run.

To do it by hand:

```bash
node scripts/update-music.cjs      # new Billboard weeks since the last one stored
node scripts/scrape-tv-tvmaze.cjs  # adds a new primetime season if one has aired
npm run build                      # bake the data into dist/
```

## The TMDB key

The site is static, so anything the browser needs is readable in the published
JavaScript -- an API key included. The Cloudflare Worker in `worker/` exists to
avoid that: it holds the key as an encrypted secret and makes the TMDB calls
itself.

One-time setup:

```bash
cd worker
npx wrangler login
npx wrangler deploy
npx wrangler secret put TMDB_API_KEY
```

Then put the deployed URL in `src/config.js` as `TMDB_PROXY` and rebuild. From
that point no key is compiled into the site, and CI can rebuild without any
secrets at all.

Until that is done the app falls back to calling TMDB directly using
`VITE_TMDB_API_KEY` from `.env`, which does end up in the published bundle.

## Local development

```bash
npm install
npm run dev
```

The Vite `base` is set to the GitHub Pages path, so the dev server serves the
app at `/experiments/movie-time-machine/dist/`.
