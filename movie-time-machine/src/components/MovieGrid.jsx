import MovieCard from './MovieCard'

export default function MovieGrid({ movies, loading, error, onMovieClick }) {
  if (error) {
    return (
      <div className="text-center py-20 text-red-400/70">
        <p className="text-base mb-1">Something went wrong</p>
        <p className="text-xs text-film-muted">{error}</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-5 px-5">
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="animate-pulse" style={{ animationDelay: `${i * 60}ms` }}>
            <div className="aspect-[2/3] bg-film-card/60 rounded-lg" />
            <div className="mt-2.5 h-3 bg-film-card/40 rounded w-3/4" />
            <div className="mt-1 h-2.5 bg-film-card/30 rounded w-1/2" />
          </div>
        ))}
      </div>
    )
  }

  if (!movies.length) {
    return (
      <div className="text-center py-20 text-film-muted">
        <p className="text-base">No movies found for this date</p>
        <p className="text-xs mt-1 text-film-muted/60">Try moving the slider to a different time</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-5 px-5">
      {movies.map((movie, i) => (
        <MovieCard key={movie.id} movie={movie} onClick={onMovieClick} index={i} />
      ))}
    </div>
  )
}
