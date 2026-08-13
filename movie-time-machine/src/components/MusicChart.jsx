import { getChartForDate, getChartCoverage } from '../lib/music-chart'

export default function MusicChart({ date }) {
  const chart = getChartForDate(date)

  if (!chart) {
    const coverage = getChartCoverage()
    let detail = 'No Billboard Hot 100 data is bundled yet.'
    if (coverage) {
      if (date < coverage.first) {
        detail = `The Hot 100 began in August 1958 -- charts here start with the week of ${formatChartDate(coverage.first)}.`
      } else if (date > coverage.last) {
        detail = `Charts here run through the week of ${formatChartDate(coverage.last)}. Later weeks haven't been added yet.`
      } else {
        detail = `Charts run from ${formatChartDate(coverage.first)} to ${formatChartDate(coverage.last)}, but this particular week is missing.`
      }
    }
    return (
      <div className="text-center py-20 text-film-muted">
        <p className="text-base">No chart data for this date</p>
        <p className="text-xs mt-1 text-film-muted/60 max-w-sm mx-auto px-6 leading-relaxed">
          {detail}
        </p>
      </div>
    )
  }

  return (
    <div className="max-w-xl mx-auto px-5">
      <p className="text-xs text-film-muted text-center mb-8 uppercase tracking-widest font-light">
        Billboard Hot 100 · Week of {formatChartDate(chart.chartDate)}
      </p>

      <div className="space-y-1">
        {chart.entries.map((entry, i) => (
          <div
            key={i}
            className={`card-enter flex items-center gap-5 px-5 py-4 rounded-lg transition-colors
                        ${i === 0
                          ? 'bg-film-gold/8 border border-film-gold/15'
                          : 'hover:bg-film-card/40'
                        }`}
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <span
              className={`w-8 text-right tabular-nums flex-shrink-0 font-light
                          ${i === 0 ? 'text-3xl text-film-gold' : 'text-2xl text-film-muted/40'}`}
              style={{ fontFamily: 'var(--font-display)' }}
            >
              {entry.rank}
            </span>
            <div className="min-w-0 flex-1">
              <p className={`font-medium leading-snug text-[15px]
                            ${i === 0 ? 'text-film-gold' : 'text-film-text'}`}>
                {entry.title}
              </p>
              <p className="text-sm text-film-muted mt-0.5 font-light">
                {entry.artist}
                {entry.weeksOnChart > 1 && (
                  <span className="text-film-muted/40 ml-2 text-xs">
                    · wk {entry.weeksOnChart}
                    {entry.peakPosition === entry.rank && entry.peakPosition <= 3 ? ' · peak' : ''}
                  </span>
                )}
              </p>
            </div>
          </div>
        ))}
      </div>

      <p className="text-center text-[10px] text-film-muted/30 mt-10 tracking-wide">
        Billboard Hot 100 data via mhollingshead/billboard-hot-100 and musicchartsarchive.com
      </p>
    </div>
  )
}

function formatChartDate(dateStr) {
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
}
