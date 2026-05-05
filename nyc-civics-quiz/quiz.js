import { MAIN_QUESTIONS, BONUS_QUESTIONS } from "./questions.js";

// Each play-through draws a fresh random subset from the larger question pool,
// so visiting twice gives you (mostly) different questions.
const MAIN_PER_RUN = 25;
const BONUS_PER_RUN = 5;
const BONUS_UNLOCK = 20; // out of MAIN_PER_RUN

const STORAGE_KEY = "nyc-civics-quiz-v2";
const root = document.getElementById("quiz-root");
const resumeMount = document.getElementById("resume-mount");

// ---------- helpers ----------
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function shuffled(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Shuffle real options (indexes 0..n-2), pin joke option (last) at the end.
// Returns { displayOptions, mapping } where mapping[displayIdx] = originalIdx.
function shuffleOptions(options) {
  const realIdx = options.slice(0, -1).map((_, i) => i);
  const shuffledReal = shuffled(realIdx);
  const mapping = [...shuffledReal, options.length - 1];
  const displayOptions = mapping.map(i => options[i]);
  return { displayOptions, mapping };
}

// Build a shuffled, sampled run of questions, each with its own option mapping.
function buildRun(questions, sampleSize) {
  const pool = shuffled(questions);
  const drawn = sampleSize ? pool.slice(0, Math.min(sampleSize, pool.length)) : pool;
  return drawn.map(q => {
    const { displayOptions, mapping } = shuffleOptions(q.options);
    return {
      ...q,
      displayOptions,
      mapping, // mapping[displayIdx] = originalIdx
      displayCorrect: mapping.indexOf(q.correct),
    };
  });
}

// ---------- state ----------
const state = {
  phase: "main", // 'main' | 'bonus' | 'results'
  mainRun: [],
  bonusRun: [],
  index: 0,
  answered: false,
  selectedDisplayIdx: null,
  mainCorrect: 0,
  mainAnswered: 0,
  bonusCorrect: 0,
  // category tracking, only counts main round
  byCategory: {}, // { catName: { correct, total } }
  bonusUnlocked: false,
};

function activeRun() {
  return state.phase === "bonus" ? state.bonusRun : state.mainRun;
}

// ---------- persistence ----------
function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) { /* ignore */ }
}

function loadPersisted() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.mainRun || !parsed.mainRun.length) return null;
    if (parsed.phase === "results") return null;
    return parsed;
  } catch (e) { return null; }
}

function clearPersisted() {
  try { localStorage.removeItem(STORAGE_KEY); } catch (e) {}
}

// ---------- start / resume ----------
function startFresh() {
  state.phase = "main";
  state.mainRun = buildRun(MAIN_QUESTIONS, MAIN_PER_RUN);
  state.bonusRun = buildRun(BONUS_QUESTIONS, BONUS_PER_RUN);
  state.index = 0;
  state.answered = false;
  state.selectedDisplayIdx = null;
  state.mainCorrect = 0;
  state.mainAnswered = 0;
  state.bonusCorrect = 0;
  state.byCategory = {};
  state.bonusUnlocked = false;
  resumeMount.innerHTML = "";
  persist();
  render();
}

function resumeFrom(saved) {
  Object.assign(state, saved);
  resumeMount.innerHTML = "";
  render();
}

function maybeOfferResume() {
  const saved = loadPersisted();
  if (!saved) {
    startFresh();
    return;
  }
  const total = saved.phase === "bonus" ? saved.bonusRun.length : saved.mainRun.length;
  const num = Math.min(saved.index + 1, total);
  resumeMount.innerHTML = `
    <div class="resume-banner" role="region" aria-label="Resume previous run">
      <p>You have a quiz in progress (${saved.phase === "bonus" ? "bonus" : "main"} round, question ${num} of ${total}). Pick up where you left off?</p>
      <div class="actions">
        <button class="btn" id="resume-yes">Resume</button>
        <button class="btn btn-secondary" id="resume-no">Start Over</button>
      </div>
    </div>
  `;
  document.getElementById("resume-yes").addEventListener("click", () => resumeFrom(saved));
  document.getElementById("resume-no").addEventListener("click", () => { clearPersisted(); startFresh(); });
  // Render an empty quiz mount in the meantime
  root.innerHTML = "";
}

// ---------- render ----------
function render() {
  if (state.phase === "results") return renderResults();
  if (state.phase === "bonus" && state.index === 0 && !state.answered && state._showedBonusIntro !== true) {
    state._showedBonusIntro = true;
    return renderBonusIntro();
  }
  renderQuestion();
}

function renderQuestion() {
  const run = activeRun();
  const q = run[state.index];
  const total = run.length;
  const num = state.index + 1;
  const progressPct = (num / total) * 100;
  const totalLabel = state.phase === "bonus" ? "Bonus" : "Question";

  const correctCount = state.phase === "bonus" ? state.bonusCorrect : state.mainCorrect;
  const incorrectCount = state.phase === "bonus"
    ? state.index + (state.answered ? 1 : 0) - state.bonusCorrect
    : state.mainAnswered - state.mainCorrect;

  const optionsHtml = q.displayOptions.map((opt, i) => {
    let cls = "option";
    if (state.answered) {
      if (i === q.displayCorrect) cls += " correct";
      else if (i === state.selectedDisplayIdx) cls += " incorrect";
      else cls += " dimmed";
    }
    return `
      <button class="${cls}" data-i="${i}" ${state.answered ? "disabled" : ""} aria-label="Option ${i + 1}: ${escapeHtml(opt)}">
        <span class="option-key">${i + 1}</span>
        <span class="option-text">${escapeHtml(opt)}</span>
      </button>
    `;
  }).join("");

  const explanationHtml = state.answered ? `
    <div class="explanation" aria-live="polite">
      <div class="explanation-label">${state.selectedDisplayIdx === q.displayCorrect ? "Correct" : "The right answer"}</div>
      <p class="explanation-text">${q.explanation}</p>
    </div>
  ` : "";

  let nextLabel = "Next question";
  if (num === total) {
    if (state.phase === "bonus") nextLabel = "See final score";
    else nextLabel = state.mainCorrect >= BONUS_UNLOCK ? "Continue to bonus round" : "See score";
  }

  const buttonHtml = state.answered ? `<button class="btn" id="next-btn">${nextLabel}</button>` : "";

  root.innerHTML = `
    <div class="meta-bar">
      <div class="progress-text">${totalLabel} ${num} of ${total}</div>
      <div class="score-badges">
        <span class="badge ok">✓ ${correctCount}</span>
        <span class="badge no">✗ ${incorrectCount}</span>
      </div>
    </div>
    <div class="progress-track"><div class="progress-fill" style="width:${progressPct}%"></div></div>
    <article class="card">
      <div class="cat-tag">${escapeHtml(q.category)}</div>
      <h2 class="q-text">${escapeHtml(q.question)}</h2>
      <div class="options">${optionsHtml}</div>
      ${explanationHtml}
      ${buttonHtml}
      <div class="kbd-hint">Press <kbd>1</kbd>–<kbd>5</kbd> to answer · <kbd>Enter</kbd> for next</div>
    </article>
  `;

  if (!state.answered) {
    document.querySelectorAll(".option").forEach(btn => {
      btn.addEventListener("click", () => answer(parseInt(btn.dataset.i, 10)));
    });
  } else {
    const btn = document.getElementById("next-btn");
    if (btn) {
      btn.addEventListener("click", advance);
      btn.focus();
    }
  }
}

function renderBonusIntro() {
  root.innerHTML = `
    <div class="card center-card">
      <div class="cat-tag" style="color: var(--orange);">Bonus round unlocked</div>
      <h2 class="q-text" style="font-family: var(--serif); font-size: 1.6rem; font-weight: 700;">You scored ${state.mainCorrect}/${MAIN_PER_RUN} on the main round.</h2>
      <p class="results-blurb">${BONUS_PER_RUN} extra questions on the truly obscure: dissolved bodies, dormant constitutional caps, and the procedural depths most New Yorkers will mercifully never know.</p>
      <button class="btn" id="start-bonus">Begin bonus round</button>
    </div>
  `;
  document.getElementById("start-bonus").addEventListener("click", () => {
    state._showedBonusIntro = true;
    renderQuestion();
    document.getElementById("start-bonus")?.blur();
  });
  document.getElementById("start-bonus").focus();
}

// ---------- actions ----------
function answer(displayIdx) {
  if (state.answered) return;
  const run = activeRun();
  const q = run[state.index];
  state.selectedDisplayIdx = displayIdx;
  state.answered = true;
  const isCorrect = displayIdx === q.displayCorrect;

  if (state.phase === "main") {
    state.mainAnswered++;
    if (isCorrect) state.mainCorrect++;
    const cat = q.category;
    if (!state.byCategory[cat]) state.byCategory[cat] = { correct: 0, total: 0 };
    state.byCategory[cat].total++;
    if (isCorrect) state.byCategory[cat].correct++;
  } else if (isCorrect) {
    state.bonusCorrect++;
  }
  persist();
  renderQuestion();
}

function advance() {
  const run = activeRun();
  if (state.index < run.length - 1) {
    state.index++;
    state.answered = false;
    state.selectedDisplayIdx = null;
    persist();
    renderQuestion();
    return;
  }
  // End of round
  if (state.phase === "main") {
    if (state.mainCorrect >= BONUS_UNLOCK) {
      state.bonusUnlocked = true;
      state.phase = "bonus";
      state.index = 0;
      state.answered = false;
      state.selectedDisplayIdx = null;
      state._showedBonusIntro = false;
      persist();
      renderBonusIntro();
    } else {
      finish();
    }
  } else {
    finish();
  }
}

function finish() {
  state.phase = "results";
  persist();
  renderResults();
}

// ---------- results ----------
function rankFor(mainScore, includedBonus) {
  // Thresholds scale with MAIN_PER_RUN (25): ≤5, ≤10, ≤15, ≤19, else Policy Expert.
  if (mainScore <= 5)  return { rank: "Tourist", blurb: "You might want to Google &ldquo;City Hall.&rdquo; The basics of how New York governs itself are still a foreign country to you — which makes you, statistically, a normal New Yorker." };
  if (mainScore <= 10) return { rank: "Transplant", blurb: "You're learning. You probably know the difference between a Council Member and a State Assemblymember most days. The agencies remain a blur." };
  if (mainScore <= 15) return { rank: "Engaged Resident", blurb: "You read the local news, follow local politics, and have opinions about ULURP. You're the kind of New Yorker the city actually depends on." };
  if (mainScore <= 19) return { rank: "Civic Wonk", blurb: "You probably work in or near government, journalism, or advocacy &mdash; or you're an unusually motivated civilian. Either way, the Charter is your beach read." };
  return {
    rank: "Policy Expert",
    blurb: includedBonus
      ? "You went the distance. You either work at City Hall, sue City Hall, or write about people who do."
      : "You've unlocked the bonus round. You either work at City Hall, sue City Hall, or write about people who do."
  };
}

function renderResults() {
  const mainTotal = MAIN_PER_RUN;
  const bonusTotal = BONUS_PER_RUN;
  const includedBonus = state.bonusUnlocked;
  const finalScore = state.mainCorrect + (includedBonus ? state.bonusCorrect : 0);
  const finalTotal = mainTotal + (includedBonus ? bonusTotal : 0);
  const { rank, blurb } = rankFor(state.mainCorrect, includedBonus);

  const cats = Object.entries(state.byCategory)
    .map(([name, v]) => ({ name, ...v, pct: v.correct / v.total }))
    .sort((a, b) => b.pct - a.pct);

  const catRows = cats.map(c => `
    <div class="cat-row">
      <div class="label">${escapeHtml(c.name)}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.round(c.pct * 100)}%"></div></div>
      <div class="pct">${c.correct}/${c.total}</div>
    </div>
  `).join("");

  root.innerHTML = `
    <div class="center-card">
      <div class="progress-text">Your score</div>
      <h2 class="results-score">${finalScore}<span class="divider"> / ${finalTotal}</span></h2>
      <h3 class="results-rank">You are a <span class="accent">${rank}</span></h3>
      <p class="results-blurb">${blurb}</p>

      <div class="cat-breakdown">
        <h3>Category breakdown (main round)</h3>
        ${catRows}
      </div>

      <div class="scorecard-preview" id="scorecard-preview">
        <canvas id="scorecard-canvas" width="1200" height="630" aria-label="Shareable score card"></canvas>
      </div>

      <div class="results-actions">
        <button class="btn" id="restart-btn">Take it again</button>
        <button class="btn btn-secondary" id="download-btn">Download score card</button>
        <button class="btn btn-secondary" id="share-btn">Share</button>
      </div>
    </div>
  `;

  drawScorecard({ finalScore, finalTotal, rank, cats });

  document.getElementById("restart-btn").addEventListener("click", () => {
    clearPersisted();
    startFresh();
  });

  document.getElementById("download-btn").addEventListener("click", downloadScorecard);
  document.getElementById("share-btn").addEventListener("click", () => share({ finalScore, finalTotal, rank }));
}

// ---------- score-card canvas ----------
function drawScorecard({ finalScore, finalTotal, rank, cats }) {
  const canvas = document.getElementById("scorecard-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;

  // background
  ctx.fillStyle = "#fbfaf6";
  ctx.fillRect(0, 0, W, H);

  // top rule
  ctx.fillStyle = "#0b0b0d";
  ctx.fillRect(60, 60, W - 120, 4);

  // byline
  ctx.fillStyle = "#ff6b3d";
  ctx.font = "700 22px -apple-system, Helvetica Neue, Arial, sans-serif";
  ctx.textBaseline = "top";
  ctx.fillText("JOSH GREENMAN", 60, 80);
  ctx.fillStyle = "#6b6b73";
  ctx.fillText("·  NEW YORK CITY CIVICS QUIZ", 290, 80);

  // headline
  ctx.fillStyle = "#0b0b0d";
  ctx.font = "italic 900 96px Georgia, Times, serif";
  ctx.fillText("Beat the", 60, 130);

  // chartreuse highlight behind 'Bureaucracy'
  ctx.fillStyle = "#d8e240";
  ctx.fillRect(60, 240, 720, 50);
  ctx.fillStyle = "#0b0b0d";
  ctx.font = "900 96px Georgia, Times, serif";
  ctx.fillText("Bureaucracy.", 60, 220);

  // big score
  ctx.font = "italic 900 200px Georgia, Times, serif";
  ctx.fillStyle = "#0b0b0d";
  ctx.fillText(String(finalScore), 60, 350);

  // /total
  ctx.font = "300 64px Georgia, Times, serif";
  ctx.fillStyle = "#6b6b73";
  const scoreW = ctx.measureText(String(finalScore)).width;
  ctx.fillText(`/ ${finalTotal}`, 60 + measureBig(String(finalScore)) + 20, 480);

  // rank
  ctx.font = "700 44px -apple-system, Helvetica Neue, Arial, sans-serif";
  ctx.fillStyle = "#0b0b0d";
  ctx.fillText(rank.toUpperCase(), 600, 380);

  // top + bottom category
  if (cats && cats.length) {
    const top = cats[0];
    const bottom = cats[cats.length - 1];
    ctx.font = "700 18px -apple-system, Helvetica Neue, Arial, sans-serif";
    ctx.fillStyle = "#6b6b73";
    ctx.fillText("STRONGEST", 600, 460);
    ctx.fillText("WEAKEST", 600, 520);
    ctx.font = "600 24px -apple-system, Helvetica Neue, Arial, sans-serif";
    ctx.fillStyle = "#0b0b0d";
    ctx.fillText(`${top.name}  ·  ${top.correct}/${top.total}`, 760, 458);
    ctx.fillText(`${bottom.name}  ·  ${bottom.correct}/${bottom.total}`, 760, 518);
  }

  // bottom rule + footer
  ctx.fillStyle = "#0b0b0d";
  ctx.fillRect(60, H - 80, W - 120, 2);
  ctx.font = "700 18px -apple-system, Helvetica Neue, Arial, sans-serif";
  ctx.fillStyle = "#6b6b73";
  ctx.fillText("joshgreenman1973.github.io/nyc-civics-quiz", 60, H - 60);
}

function measureBig(text) {
  // approximate width of italic 900 200px Georgia
  return text.length * 110;
}

function downloadScorecard() {
  const canvas = document.getElementById("scorecard-canvas");
  if (!canvas) return;
  canvas.toBlob(blob => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "nyc-civics-quiz-score.png";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }, "image/png");
}

async function share({ finalScore, finalTotal, rank }) {
  const text = `I scored ${finalScore}/${finalTotal} on the New York City Civics Quiz. I'm a ${rank}.`;
  const canvas = document.getElementById("scorecard-canvas");
  // Try Web Share with file
  if (navigator.canShare && canvas) {
    try {
      const blob = await new Promise(res => canvas.toBlob(res, "image/png"));
      const file = new File([blob], "score.png", { type: "image/png" });
      if (navigator.canShare({ files: [file] })) {
        await navigator.share({ title: "New York City Civics Quiz", text, files: [file] });
        return;
      }
    } catch (e) { /* fall through */ }
  }
  if (navigator.share) {
    try { await navigator.share({ title: "New York City Civics Quiz", text }); return; } catch (e) {}
  }
  if (navigator.clipboard) {
    await navigator.clipboard.writeText(text);
    const btn = document.getElementById("share-btn");
    if (btn) {
      const orig = btn.textContent;
      btn.textContent = "Copied!";
      setTimeout(() => { btn.textContent = orig; }, 1500);
    }
  }
}

// ---------- keyboard ----------
document.addEventListener("keydown", e => {
  // ignore if typing in an input
  if (e.target && /input|textarea/i.test(e.target.tagName)) return;

  if (state.phase === "results") {
    if (e.key.toLowerCase() === "r") {
      e.preventDefault();
      clearPersisted();
      startFresh();
    }
    return;
  }

  if (!state.answered) {
    const n = parseInt(e.key, 10);
    const run = activeRun();
    const q = run[state.index];
    if (q && n >= 1 && n <= q.displayOptions.length) {
      e.preventDefault();
      answer(n - 1);
    }
  } else if (e.key === "Enter") {
    e.preventDefault();
    advance();
  }
});

// ---------- boot ----------
maybeOfferResume();
