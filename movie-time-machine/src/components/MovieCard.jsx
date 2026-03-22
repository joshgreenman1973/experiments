import { posterUrl } from '../lib/tmdb'

export default function MovieCard({ movie, onClick, index }) {
  const poster = posterUrl(movie.poster_path)
  const year = movie.release_date?.slice(0, 4)
  const rating = movie.vote_average?.toFixed(1)

  return (
    <button
      onClick={() => onClick(movie.id)}
      className="card-enter group text-left cursor-pointer rounded-lg overflow-hidden
                 transition-all duration-300 hover:scale-[1.03]
                 focus:outline-none relative"
      style={{ animationDelay: `${(index || 0) * 40}ms` }}
    >
      {/* Poster */}
      <div className="aspect-[2/3] bg-film-dark overflow-hidden rounded-lg relative">
        {poster ? (
          <img
            src={poster}
            alt={movie.title}
            loading="lazy"
            className="w-full h-full object-cover transition-all duration-300
                       group-hover:brightness-110"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-film-muted text-xs p-3 text-center bg-film-card">
            {movie.title}
          </div>
        )}
        {/* Hover overlay with rating */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent
                        opacity-0 group-hover:opacity-100 transition-opacity duration-300
                        flex items-end p-3">
          {rating > 0 && (
            <span className="text-sm font-medium text-white flex items-center gap-1">
              <span className="text-film-gold">★</span> {rating}
            </span>
          )}
        </div>
      </div>
      {/* Title */}
      <div className="pt-2.5 pb-1">
        <h3 className="text-[13px] font-medium text-film-text leading-snug line-clamp-2
                       group-hover:text-white transition-colors">
          {movie.title}
        </h3>
        {year && (
          <p className="text-[11px] text-film-muted mt-0.5">{year}</p>
        )}
      </div>
    </button>
  )
}
