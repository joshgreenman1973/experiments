import { useEffect } from 'react'

export default function SourcesModal({ open, onClose }) {
  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    if (open) document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ animation: 'modalBg 0.25s ease-out', backgroundColor: 'rgba(0,0,0,0.85)' }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto bg-film-dark rounded-xl
                    border border-film-border/60 shadow-2xl p-8 sm:p-10"
        style={{ animation: 'modalIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          className="text-2xl text-white mb-6"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          About this data
        </h2>

        <div className="space-y-6 text-sm text-film-text/80 leading-relaxed">
          <section>
            <h3 className="text-film-gold text-xs uppercase tracking-widest mb-2 font-medium">
              Movies
            </h3>
            <p>
              Movie data comes from <a href="https://www.themoviedb.org/" target="_blank" rel="noopener noreferrer" className="text-film-gold/80 underline underline-offset-2 hover:text-film-gold">The Movie Database (TMDB)</a>, queried live via their API.
            </p>
            <p className="mt-2 text-film-muted text-xs">
              <strong className="text-film-text/60">What might not be right:</strong> "In theaters" is an approximation. We show movies with a U.S. release date in the 6 weeks before the selected date, which means some films may appear that had already left theaters, and short-run or regional releases may be missing. Before the 1970s, TMDB's release-date data gets spottier. Ratings and vote counts reflect present-day TMDB user scores, not contemporary reviews.
            </p>
          </section>

          <section>
            <h3 className="text-film-gold text-xs uppercase tracking-widest mb-2 font-medium">
              TV schedules
            </h3>
            <p>
              Primetime TV grids come from <a href="https://epguides.com/" target="_blank" rel="noopener noreferrer" className="text-film-gold/80 underline underline-offset-2 hover:text-film-gold">epguides.com</a>, covering the 1970-1971 through 2011-2012 seasons.
            </p>
            <p className="mt-2 text-film-muted text-xs">
              <strong className="text-film-text/60">What might not be right:</strong> Only ABC, CBS, NBC, and FOX are included -- no cable, no PBS, no CW/UPN/WB. Schedules reflect the planned primetime grid for each season, not what actually aired on a specific night (preemptions, specials, and mid-season replacements may not be captured). Time slots are Eastern. Some "movie" placeholders appear where networks ran rotating movie nights rather than a named series.
            </p>
          </section>

          <section>
            <h3 className="text-film-gold text-xs uppercase tracking-widest mb-2 font-medium">
              Music charts
            </h3>
            <p>
              Billboard Hot 100 rankings from January 1962 through March 2026, sourced from <a href="https://github.com/mhollingshead/billboard-hot-100" target="_blank" rel="noopener noreferrer" className="text-film-gold/80 underline underline-offset-2 hover:text-film-gold">mhollingshead/billboard-hot-100</a> and <a href="https://musicchartsarchive.com/" target="_blank" rel="noopener noreferrer" className="text-film-gold/80 underline underline-offset-2 hover:text-film-gold">musicchartsarchive.com</a>. We show the top 5 songs for the nearest chart week.
            </p>
            <p className="mt-2 text-film-muted text-xs">
              <strong className="text-film-text/60">What might not be right:</strong> Chart data before 1962 is not available. A small number of weeks have fewer than 5 entries. Peak position and weeks-on-chart figures are from the source datasets and may not match every published Billboard chart exactly. The Hot 100's methodology has changed over the decades (adding streaming, digital sales, etc.), so rankings from different eras aren't directly comparable.
            </p>
          </section>

          <section>
            <h3 className="text-film-gold text-xs uppercase tracking-widest mb-2 font-medium">
              General notes
            </h3>
            <p className="text-film-muted text-xs">
              This is a personal project for exploring cultural history, not a definitive reference. TV and music data are bundled snapshots that may contain transcription errors from their source datasets. Movie data is fetched live from TMDB and is only as accurate as their community-maintained database. If you spot an error, the issue is almost certainly upstream in one of these sources.
            </p>
          </section>
        </div>

        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center
                     rounded-full bg-black/40 text-white/50 hover:text-white hover:bg-black/60
                     transition-colors cursor-pointer text-sm"
        >
          x
        </button>
      </div>
    </div>
  )
}
