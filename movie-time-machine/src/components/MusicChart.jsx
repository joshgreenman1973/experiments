import { getChartForDate } from '../lib/music-chart'

export default function MusicChart({ date }) {
  const chart = getChartForDate(date)

  if (!chart) {
    return (
      <div className="text-center py-20 text-film-muted">
        <p className="text-base">No chart data for this date</p>
        <p className="text-xs mt-1 text-film-muted/60">
          Billboard Hot 100 data available from 1977 onward
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
              </p>
            </div>
          </div>
        ))}
      </div>

      <p className="text-center text-[10px] text-film-muted/30 mt-10 tracking-wide">
        Data from musicchartsarchive.com
      </p>
    </div>
  )
}

function formatChartDate(dateStr) {
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
}
