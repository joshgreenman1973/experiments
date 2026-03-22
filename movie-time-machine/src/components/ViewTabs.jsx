const TABS = [
  { id: 'movies', label: 'At the Movies' },
  { id: 'tv', label: 'On TV' },
  { id: 'music', label: 'On the Radio' },
]

export default function ViewTabs({ active, onChange }) {
  return (
    <div className="flex justify-center gap-6 sm:gap-10 px-4">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`
            relative pb-2 text-sm tracking-wide transition-colors cursor-pointer font-medium
            ${active === tab.id
              ? 'text-film-gold'
              : 'text-film-muted hover:text-film-text'
            }
          `}
        >
          {tab.label}
          {active === tab.id && (
            <span
              className="absolute bottom-0 left-0 right-0 h-[2px] bg-film-gold rounded-full"
              style={{ animation: 'tabLine 0.3s cubic-bezier(0.16, 1, 0.3, 1)' }}
            />
          )}
        </button>
      ))}
      <style>{`
        @keyframes tabLine {
          from { transform: scaleX(0); }
          to { transform: scaleX(1); }
        }
      `}</style>
    </div>
  )
}
