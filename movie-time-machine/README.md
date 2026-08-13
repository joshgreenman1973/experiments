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
JavaScript -- an API key included. So the app never sees the key: every TMDB
request goes through the Cloudflare Worker in `worker/`, which holds the key as
an encrypted secret, allows only the three endpoints the app uses, and is
deployed at https://good-time-tmdb.josh-greenman.workers.dev.

The app gets that URL from `TMDB_PROXY` in `src/config.js` -- a public URL, safe
to commit, which is why CI can rebuild the site with no secrets at all. There is
deliberately no way to supply a raw API key from the frontend.

To change the Worker or its key:

```bash
cd worker
npx wrangler deploy                    # after editing src/index.js
npx wrangler secret put TMDB_API_KEY   # to rotate the key
```

## Local development

```bash
npm install
npm run dev
```

The Vite `base` is set to the GitHub Pages path, so the dev server serves the
app at `/experiments/movie-time-machine/dist/`.
