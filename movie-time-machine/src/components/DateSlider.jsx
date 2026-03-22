import { useRef, useMemo } from 'react'

const MIN_YEAR = 1950
const DECADES = []
for (let y = 1950; y <= 2020; y += 10) DECADES.push(y)

export default function DateSlider({ value, onChange }) {
  const inputRef = useRef(null)

  const today = useMemo(() => {
    const d = new Date()
    return d.toISOString().slice(0, 10)
  }, [])

  const minDate = `${MIN_YEAR}-01-01`
  const minDays = dateToDays(minDate)
  const maxDays = dateToDays(today)
  const currentDays = dateToDays(value)

  function dateToDays(dateStr) {
    return Math.floor(new Date(dateStr).getTime() / 86400000)
  }

  function daysToDate(days) {
    return new Date(days * 86400000).toISOString().slice(0, 10)
  }

  function handleSlider(e) {
    onChange(daysToDate(Number(e.target.value)))
  }

  function handleDateInput(e) {
    const val = e.target.value
    if (val) onChange(val)
  }

  function randomDate() {
    const days = minDays + Math.floor(Math.random() * (maxDays - minDays))
    onChange(daysToDate(days))
  }

  const displayDate = new Date(value + 'T12:00:00')
  const weekday = displayDate.toLocaleDateString('en-US', { weekday: 'long' })
  const monthDay = displayDate.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })
  const year = displayDate.getFullYear()

  return (
    <div className="w-full max-w-3xl mx-auto px-6">
      <div className="text-center mb-8 mt-4">
        <p
          className="text-film-muted text-sm tracking-widest uppercase font-light mb-1"
        >
          {weekday}
        </p>
        <p
          className="text-4xl sm:text-5xl text-film-gold tracking-tight"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          {monthDay}
        </p>
        <p
          className="text-6xl sm:text-7xl text-white tracking-tight -mt-1"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          {year}
        </p>
      </div>

      <div className="mb-2 relative">
        <input
          ref={inputRef}
          type="range"
          min={minDays}
          max={maxDays}
          value={currentDays}
          onChange={handleSlider}
          className="w-full cursor-pointer"
        />
      </div>

      <div className="flex justify-between text-[10px] text-film-muted/60 mb-5 px-1 uppercase tracking-wider">
        {DECADES.map((y) => (
          <button
            key={y}
            onClick={() => onChange(`${y}-06-15`)}
            className="hover:text-film-gold transition-colors cursor-pointer py-1"
          >
            {y}
          </button>
        ))}
        <span>Now</span>
      </div>

      <div className="flex justify-center items-center gap-3">
        <input
          type="date"
          value={value}
          min={minDate}
          max={today}
          onChange={handleDateInput}
          className="bg-film-dark border border-film-border rounded-lg px-3 py-1.5 text-film-text
                     focus:outline-none focus:border-film-gold/50 transition-colors text-sm"
        />
        <button
          onClick={randomDate}
          className="px-3 py-1.5 rounded-lg border border-film-border text-film-muted text-sm
                     hover:border-film-gold/40 hover:text-film-gold transition-all cursor-pointer
                     bg-film-dark"
          title="Pick a random date"
        >
          Surprise me
        </button>
      </div>
    </div>
  )
}
