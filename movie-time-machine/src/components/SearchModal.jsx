import { useState, useEffect, useRef, useCallback } from 'react'
import { searchMovies } from '../lib/tmdb'
import { searchTVShows } from '../lib/tv-schedule'
import { searchSongs } from '../lib/music-chart'

export default function SearchModal({ open, onClose, onNavigate }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const inputRef = useRef(null)
  const debounceRef = useRef(null)

  useEffect(() => {
    if (open) {
      setQuery('')
      setResults([])
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [open])

  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    if (open) document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  const doSearch = useCallback(async (q) => {
    if (q.length < 2) {
      setResults([])
      return
    }
    setSearching(true)

    // Search all three sources in parallel
    const [movies, tvShows, songs] = await Promise.all([
      searchMovies(q).catch(() => []),
      Promise.resolve(searchTVShows(q)),
      Promise.resolve(searchSongs(q)),
    ])

    // Interleave results: movies first, then TV, then music (max 12 total)
    const combined = []
    const sources = [movies, tvShows, songs]
    for (let i = 0; combined.length < 12; i++) {
      let added = false
      for (const src of sources) {
        if (i < src.length && combined.length < 12) {
          combined.push(src[i])
          added = true
        }
      }
      if (!added) break
    }

    setResults(combined)
    setSearching(false)
  }, [])

  function handleInput(e) {
    const val = e.target.value
    setQuery(val)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(val), 250)
  }

  function handleSelect(result) {
    if (result.date) {
      onNavigate(result.date, result.type === 'tv' ? 'tv' : result.type === 'music' ? 'music' : 'movies')
    }
    onClose()
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.8)', animation: 'modalBg 0.2s ease-out' }}
      onClick={onClose}
    >
      <style>{`
        @keyframes modalBg { from { opacity: 0; } to { opacity: 1; } }
        @keyframes searchIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
      <div
        className="w-full max-w-lg bg-film-dark border border-film-border/60 rounded-xl shadow-2xl overflow-hidden"
        style={{ animation: 'searchIn 0.25s cubic-bezier(0.16, 1, 0.3, 1)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-film-border/40">
          <span className="text-film-muted/50 text-sm">Search</span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={handleInput}
            placeholder="Movie, TV show, or song…"
            className="flex-1 bg-transparent text-film-text text-base outline-none placeholder:text-film-muted/30"
          />
          <button
            onClick={onClose}
            className="text-film-muted/40 hover:text-film-muted text-xs cursor-pointer transition-colors"
          >
            ESC
          </button>
        </div>

        {/* Results */}
        <div className="max-h-[50vh] overflow-y-auto">
          {searching && (
            <div className="px-5 py-8 text-center text-film-muted/50 text-sm">
              Searching…
            </div>
          )}

          {!searching && query.length >= 2 && results.length === 0 && (
            <div className="px-5 py-8 text-center text-film-muted/40 text-sm">
              No results found
            </div>
          )}

          {!searching && results.length > 0 && (
            <div className="py-2">
              {results.map((r, i) => (
                <button
                  key={`${r.type}-${r.title}-${i}`}
                  onClick={() => handleSelect(r)}
                  className="w-full flex items-center gap-3 px-5 py-3 text-left cursor-pointer
                             hover:bg-film-card/60 transition-colors"
                >
                  {/* Type badge */}
                  <span className={`text-[10px] uppercase tracking-wider w-12 flex-shrink-0 font-medium
                    ${r.type === 'movie' ? 'text-film-gold/70' : r.type === 'tv' ? 'text-blue-400/70' : 'text-emerald-400/70'}`}>
                    {r.type === 'movie' ? 'Film' : r.type === 'tv' ? 'TV' : 'Song'}
                  </span>

                  {/* Poster thumbnail for movies */}
                  {r.type === 'movie' && r.poster && (
                    <img src={r.poster} alt="" className="w-8 h-12 rounded object-cover flex-shrink-0" />
                  )}

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-film-text truncate">{r.title}</p>
                    <p className="text-xs text-film-muted/60 truncate">
                      {r.type === 'movie' && r.year}
                      {r.type === 'tv' && `${r.network} · ${r.season} season`}
                      {r.type === 'music' && `${r.artist} · ${r.date}`}
                    </p>
                  </div>

                  {/* Arrow */}
                  <span className="text-film-muted/30 text-xs flex-shrink-0">→</span>
                </button>
              ))}
            </div>
          )}

          {!searching && query.length < 2 && (
            <div className="px-5 py-8 text-center text-film-muted/30 text-xs">
              Type to search across movies, TV shows, and Billboard charts
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
