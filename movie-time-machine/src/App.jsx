import { useState, useEffect, useCallback, useRef } from 'react'
import DateSlider from './components/DateSlider'
import ViewTabs from './components/ViewTabs'
import MovieGrid from './components/MovieGrid'
import MovieModal from './components/MovieModal'
import TVSchedule from './components/TVSchedule'
import MusicChart from './components/MusicChart'
import SearchModal from './components/SearchModal'
import SourcesModal from './components/SourcesModal'
import { discoverMoviesInTheaters } from './lib/tmdb'
import { getCatalogStats } from './lib/stats'

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

export default function App() {
  const [date, setDate] = useState(todayStr())
  const [view, setView] = useState('movies')
  const [movies, setMovies] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [totalResults, setTotalResults] = useState(0)
  const [selectedMovie, setSelectedMovie] = useState(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [includeLimited, setIncludeLimited] = useState(true)
  const debounceRef = useRef(null)
  const [viewKey, setViewKey] = useState(0)
  const catalogStats = getCatalogStats()

  const fetchMovies = useCallback(async (dateStr, limited) => {
    setLoading(true)
    setError(null)
    try {
      const data = await discoverMoviesInTheaters(dateStr, { includeLimited: limited })
      setMovies(data.results || [])
      setTotalResults(data.total_results || 0)
    } catch (err) {
      setError(err.message)
      setMovies([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (view !== 'movies') return
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      fetchMovies(date, includeLimited)
    }, 300)
    return () => clearTimeout(debounceRef.current)
  }, [date, view, includeLimited, fetchMovies])

  useEffect(() => {
    if (view === 'movies' && movies.length === 0 && !loading) {
      fetchMovies(date, includeLimited)
    }
  }, [view])

  // Keyboard shortcut: / to open search
  useEffect(() => {
    function handleKey(e) {
      if (e.key === '/' && !searchOpen && !e.ctrlKey && !e.metaKey) {
        const tag = e.target.tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA') return
        e.preventDefault()
        setSearchOpen(true)
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [searchOpen])

  function handleViewChange(v) {
    setView(v)
    setViewKey((k) => k + 1)
  }

  function handleSearchNavigate(newDate, newView) {
    setDate(newDate)
    handleViewChange(newView)
  }

  const hasKey = Boolean(import.meta.env.VITE_TMDB_API_KEY)

  return (
    <div className="min-h-screen pb-20 app-glow">
      <header className="pt-12 pb-2 text-center relative">
        <h1
          className="text-5xl sm:text-6xl tracking-tight text-white mb-3"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          Good Time Time Machine
        </h1>
        <p className="text-film-muted text-base tracking-wide font-light">
          Pick a date. See what was playing.
        </p>
      </header>

      <DateSlider value={date} onChange={setDate} />

      <div className="max-w-xl mx-auto my-6">
        <div className="deco-rule" />
      </div>

      <div className="mb-8 relative">
        <ViewTabs active={view} onChange={handleViewChange} />
        {/* Search button */}
        <div className="absolute right-4 sm:right-8 top-1/2 -translate-y-1/2">
          <button
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-film-border/50
                       text-film-muted/50 hover:text-film-muted hover:border-film-border
                       transition-colors cursor-pointer text-xs"
            title="Search (press /)"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <span className="hidden sm:inline">/</span>
          </button>
        </div>
      </div>

      {view === 'movies' && !hasKey && (
        <div className="max-w-xl mx-auto mb-8 p-4 bg-red-900/20 border border-red-800/30 rounded-lg text-center text-sm text-red-300/80">
          Add <code className="bg-red-900/30 px-1.5 py-0.5 rounded text-red-200/80 text-xs">VITE_TMDB_API_KEY</code> to
          a <code className="bg-red-900/30 px-1.5 py-0.5 rounded text-red-200/80 text-xs">.env</code> file and restart.
        </div>
      )}

      <div key={viewKey} className="view-enter">
        {view === 'movies' && (
          <div className="max-w-6xl mx-auto">
            {!loading && movies.length > 0 && (
              <div className="flex items-center justify-center gap-4 mb-5">
                <p className="text-xs text-film-muted uppercase tracking-widest font-light">
                  {totalResults} movies in theaters
                </p>
                <button
                  onClick={() => setIncludeLimited((v) => !v)}
                  className={`text-[11px] px-2.5 py-1 rounded border transition-colors cursor-pointer
                    ${includeLimited
                      ? 'border-film-gold/30 text-film-gold/80 bg-film-gold/5'
                      : 'border-film-border/50 text-film-muted/50 hover:text-film-muted'
                    }`}
                >
                  {includeLimited ? 'Wide + limited' : 'Wide release only'}
                </button>
              </div>
            )}
            <MovieGrid
              movies={movies}
              loading={loading}
              error={error}
              onMovieClick={setSelectedMovie}
            />
          </div>
        )}

        {view === 'tv' && <TVSchedule date={date} />}

        {view === 'music' && <MusicChart date={date} />}
      </div>

      <MovieModal movieId={selectedMovie} onClose={() => setSelectedMovie(null)} />
      <SearchModal
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onNavigate={handleSearchNavigate}
      />

      <footer className="text-center mt-20 pb-4 text-[10px] text-film-muted/30 tracking-wide space-y-1">
        <p>{catalogStats.tvShows.toLocaleString()} TV shows · {catalogStats.tvSeasons} seasons · {catalogStats.songEntries.toLocaleString()} chart entries · {catalogStats.chartWeeks.toLocaleString()} weeks</p>
        <p>Movies via TMDB · TV schedules via epguides.com · Charts via musicchartsarchive.com</p>
        <p>
          <button
            onClick={() => setSourcesOpen(true)}
            className="text-film-muted/40 hover:text-film-muted/60 underline underline-offset-2
                       transition-colors cursor-pointer"
          >
            About this data
          </button>
        </p>
      </footer>

      <SourcesModal open={sourcesOpen} onClose={() => setSourcesOpen(false)} />
    </div>
  )
}
