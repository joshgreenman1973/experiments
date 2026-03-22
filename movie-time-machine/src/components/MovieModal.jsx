import { useState, useEffect } from 'react'
import { getMovieDetails, posterUrl, backdropUrl } from '../lib/tmdb'

export default function MovieModal({ movieId, onClose }) {
  const [movie, setMovie] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!movieId) return
    setLoading(true)
    getMovieDetails(movieId)
      .then(setMovie)
      .catch(() => setMovie(null))
      .finally(() => setLoading(false))
  }, [movieId])

  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  if (!movieId) return null

  const backdrop = movie ? backdropUrl(movie.backdrop_path) : null
  const poster = movie ? posterUrl(movie.poster_path, 'w500') : null
  const year = movie?.release_date?.slice(0, 4)
  const hours = movie?.runtime ? Math.floor(movie.runtime / 60) : 0
  const mins = movie?.runtime ? movie.runtime % 60 : 0
  const directors = movie?.credits?.crew?.filter((c) => c.job === 'Director') || []
  const cast = movie?.credits?.cast?.slice(0, 8) || []
  const genres = movie?.genres?.map((g) => g.name) || []

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ animation: 'modalBg 0.25s ease-out', backgroundColor: 'rgba(0,0,0,0.85)' }}
      onClick={onClose}
    >
      <style>{`
        @keyframes modalBg { from { opacity: 0; } to { opacity: 1; } }
        @keyframes modalIn { from { opacity: 0; transform: scale(0.96) translateY(10px); } to { opacity: 1; transform: scale(1) translateY(0); } }
      `}</style>
      <div
        className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto bg-film-dark rounded-xl
                    border border-film-border/60 shadow-2xl"
        style={{ animation: 'modalIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {loading ? (
          <div className="p-16 text-center text-film-muted animate-pulse text-sm">
            Loading\u2026
          </div>
        ) : !movie ? (
          <div className="p-16 text-center text-red-400/70 text-sm">
            Couldn\u2019t load movie details
          </div>
        ) : (
          <>
            {backdrop && (
              <div className="relative h-48 sm:h-64 overflow-hidden rounded-t-xl">
                <img
                  src={backdrop}
                  alt=""
                  className="w-full h-full object-cover opacity-30"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-film-dark via-film-dark/40 to-transparent" />
              </div>
            )}

            <div className={`p-6 sm:p-8 ${backdrop ? '-mt-20 relative' : ''}`}>
              <div className="flex gap-6">
                {poster && (
                  <img
                    src={poster}
                    alt={movie.title}
                    className="w-28 sm:w-36 rounded-lg shadow-xl flex-shrink-0 hidden sm:block"
                  />
                )}
                <div className="flex-1 min-w-0">
                  <h2
                    className="text-2xl sm:text-3xl text-white leading-tight mb-1"
                    style={{ fontFamily: 'var(--font-display)' }}
                  >
                    {movie.title}
                  </h2>
                  {year && (
                    <p className="text-film-muted text-sm mb-3">{year}</p>
                  )}

                  <div className="flex flex-wrap gap-3 mb-4 text-xs text-film-muted">
                    {movie.runtime > 0 && (
                      <span>{hours}h {mins}m</span>
                    )}
                    {movie.vote_average > 0 && (
                      <span className="flex items-center gap-0.5">
                        <span className="text-film-gold">★</span>{' '}
                        {movie.vote_average.toFixed(1)}
                      </span>
                    )}
                  </div>

                  {genres.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-5">
                      {genres.map((g) => (
                        <span
                          key={g}
                          className="px-2 py-0.5 rounded text-[11px] bg-film-card border border-film-border/50 text-film-muted"
                        >
                          {g}
                        </span>
                      ))}
                    </div>
                  )}

                  {movie.overview && (
                    <p className="text-sm text-film-text/70 leading-relaxed mb-5 font-light">
                      {movie.overview}
                    </p>
                  )}

                  {directors.length > 0 && (
                    <p className="text-sm mb-1">
                      <span className="text-film-muted/60">Directed by </span>
                      <span className="text-film-text/90">
                        {directors.map((d) => d.name).join(', ')}
                      </span>
                    </p>
                  )}

                  {cast.length > 0 && (
                    <p className="text-sm">
                      <span className="text-film-muted/60">Starring </span>
                      <span className="text-film-text/80 font-light">
                        {cast.map((c) => c.name).join(', ')}
                      </span>
                    </p>
                  )}
                </div>
              </div>
            </div>
          </>
        )}

        <button
          onClick={onClose}
          className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center
                     rounded-full bg-black/40 text-white/50 hover:text-white hover:bg-black/60
                     transition-colors cursor-pointer text-sm"
        >
          ✕
        </button>
      </div>
    </div>
  )
}
