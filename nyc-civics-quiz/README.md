# Beat the Bureaucracy — NYC Civics Quiz

A personal-byline interactive quiz on New York City government, politics, and obscure laws.

## How it works

- 25 questions are drawn fresh each visit from a pool of ~55 in `questions.js`. Visit twice and you'll mostly see different questions.
- Score 20 of 25 to unlock a 5-question bonus round (drawn from a separate pool of ~10).
- Keyboard: `1`–`5` to answer, `Enter` to advance, `R` on the results screen to restart.
- Progress is saved to `localStorage` so you can close the tab and resume.
- Results screen breaks down accuracy by category and renders a downloadable score-card image.

## Editing questions

`questions.js` exports `MAIN_QUESTIONS` and `BONUS_QUESTIONS`. Each entry is:

```js
{
  category: "Land Use",
  question: "...",
  options: ["A", "B", "C", "D", "<joke option, always last>"],
  correct: 0,        // index 0–4 of the right answer
  explanation: '... <a href="...">source</a>.'
}
```

Convention: option index 4 is the running joke option. The engine pins it at the end even when other options are shuffled.

## Stack

Plain HTML/CSS/JS. No build step. Open `index.html` directly or serve with `python3 -m http.server`.
