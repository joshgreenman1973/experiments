import { getTVSchedule, formatTime } from '../lib/tv-schedule'

const NETWORK_STYLE = {
  ABC: { accent: '#4a90d9', label: 'ABC' },
  CBS: { accent: '#50b87a', label: 'CBS' },
  NBC: { accent: '#d4a843', label: 'NBC' },
  FOX: { accent: '#d45a5a', label: 'FOX' },
}

export default function TVSchedule({ date }) {
  const schedule = getTVSchedule(date)

  if (!schedule || !schedule.networks.length) {
    return (
      <div className="text-center py-20 text-film-muted">
        <p className="text-base">No TV schedule data for this date</p>
        <p className="text-xs mt-1 text-film-muted/60">
          Primetime schedules cover fall 1970 through 2012
        </p>
      </div>
    )
  }

  const dayLabel = schedule.day.charAt(0).toUpperCase() + schedule.day.slice(1)
  const seasonLabel = schedule.season.replace('-', '–')

  return (
    <div className="max-w-4xl mx-auto px-5">
      <p className="text-xs text-film-muted text-center mb-8 uppercase tracking-widest font-light">
        {dayLabel} night · {seasonLabel} season
      </p>

      <div className="grid gap-5 md:grid-cols-3">
        {schedule.networks.map(({ network, shows }) => {
          const style = NETWORK_STYLE[network] || NETWORK_STYLE.ABC
          return (
            <div
              key={network}
              className="rounded-lg bg-film-card/40 border border-film-border/60 p-5
                         hover:border-film-border transition-colors"
            >
              <div className="flex items-center gap-2 mb-5">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: style.accent }}
                />
                <h3
                  className="text-base font-semibold tracking-wide"
                  style={{ color: style.accent }}
                >
                  {style.label}
                </h3>
              </div>
              <div className="space-y-0">
                {shows.map((slot, i) => (
                  <div
                    key={i}
                    className="flex gap-3 items-baseline py-2 border-t border-film-border/30
                               first:border-t-0 first:pt-0"
                  >
                    <span className="text-[11px] text-film-muted/70 w-14 flex-shrink-0 tabular-nums">
                      {formatTime(slot.time)}
                    </span>
                    <p className="text-sm text-film-text leading-snug">
                      {slot.show}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      <p className="text-center text-[10px] text-film-muted/30 mt-10 tracking-wide">
        Primetime grid · Times Eastern · Data from epguides.com
      </p>
    </div>
  )
}
