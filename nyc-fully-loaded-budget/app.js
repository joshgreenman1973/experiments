(function () {
  'use strict';

  var D = null;      // the whole file
  var Y = null;      // the fiscal year on screen
  var state = { mode: 'pub', sort: 'size', cutoff: 100000000, fy: null,
                lit: ['056', '057', '040', '071'] };
  var $ = function (id) { return document.getElementById(id); };

  // ---------- formatting ----------
  function money(v) {
    var a = Math.abs(v);
    if (a >= 1e9) return '$' + (v / 1e9).toFixed(a >= 1e10 ? 1 : 2) + 'B';
    if (a >= 1e6) return '$' + Math.round(v / 1e6) + 'M';
    return '$' + Math.round(v / 1e3) + 'K';
  }
  function moneyRound(v) {
    if (Math.abs(v) >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B';
    return money(v);
  }
  function moneyLong(v) {
    if (Math.abs(v) >= 1e9) return '$' + (v / 1e9).toFixed(1) + ' billion';
    return '$' + Math.round(v / 1e6) + ' million';
  }
  function dollars(v) { return '$' + Math.round(v).toLocaleString('en-US'); }
  function pct(v) { return (v * 100).toFixed(1) + '%'; }

  // ---------- ranking ----------
  function visible() {
    return Y.agencies.filter(function (a) { return a.published >= state.cutoff; });
  }
  function mult(a) { return a.published > 0 ? a.loaded / a.published : 1; }

  // Rows are made once and then kept. Reusing the elements is what lets the
  // segments grow and the ranking reshuffle instead of blinking to a new list.
  var rowEls = {};

  function makeRow(a) {
    var row = document.createElement('button');
    row.className = 'row';
    row.setAttribute('data-code', a.code);
    row.innerHTML =
      '<span class="nm" title="' + a.full + '">' + a.name + '</span>' +
      '<span class="track">' +
        '<i class="k base"></i><i class="k pen"></i><i class="k fri"></i><i class="k jud"></i>' +
      '</span>' +
      '<span class="amt"></span>';
    row.addEventListener('click', function () { openAgency(a); });
    rowEls[a.code] = row;
    return row;
  }

  function drawRank() {
    var list = visible().slice();
    var shown = function (a) { return state.mode === 'load' ? a.loaded : a.published; };
    if (state.sort === 'mult') list.sort(function (x, y) { return mult(y) - mult(x); });
    else list.sort(function (x, y) { return shown(y) - shown(x); });

    var scale = Math.max.apply(null, list.map(shown));
    var loaded = state.mode === 'load';
    var host = $('rank');

    // Where every row sits now, before anything moves.
    var before = {};
    Array.prototype.forEach.call(host.children, function (el) {
      before[el.getAttribute('data-code')] = el.getBoundingClientRect().top;
    });

    var frag = document.createDocumentFragment();
    list.forEach(function (a) {
      frag.appendChild(rowEls[a.code] || makeRow(a));
    });
    host.innerHTML = '';
    host.appendChild(frag);

    // Slide each surviving row from its old place to its new one.
    list.forEach(function (a) {
      var el = rowEls[a.code];
      var was = before[a.code];
      if (was == null) return;
      var dy = was - el.getBoundingClientRect().top;
      if (!dy) return;
      el.style.zIndex = '5';           // ride over the rows it passes
      // A backgrounded tab throttles animations to a standstill, so the lift
      // is always taken back on a timer as well as on the animation finishing.
      var done = function () { el.style.zIndex = ''; };
      setTimeout(done, 900);
      if (el.animate) {
        var anim = el.animate(
          [{ transform: 'translateY(' + dy + 'px)' }, { transform: 'none' }],
          { duration: 550, easing: 'cubic-bezier(.22,.7,.28,1)' });
        anim.onfinish = done;
        anim.oncancel = done;
      } else {
        el.style.transition = 'none';
        el.style.transform = 'translateY(' + dy + 'px)';
        requestAnimationFrame(function () {
          el.style.transition = 'transform .55s cubic-bezier(.22,.7,.28,1)';
          el.style.transform = '';
        });
        setTimeout(function () { el.style.transition = ''; done(); }, 600);
      }
    });

    // Then the widths and the numbers, which transition on their own.
    list.forEach(function (a) {
      var el = rowEls[a.code];
      var seg = el.querySelectorAll('.track i');
      var w = function (v) { return (100 * v / scale).toFixed(3) + '%'; };
      seg[0].style.width = w(a.published);
      seg[1].style.width = loaded ? w(a.add.pension) : '0%';
      seg[2].style.width = loaded ? w(a.add.fringe) : '0%';
      seg[3].style.width = loaded ? w(a.add.judgments) : '0%';
      el.querySelector('.amt').innerHTML = money(loaded ? a.loaded : a.published) +
        (loaded && mult(a) >= 1.02
          ? '<em class="up">' + mult(a).toFixed(2) + '× the line</em>'
          : '<em>' + (loaded ? 'fully loaded' : 'budget line') + '</em>');
    });

    var hidden = Y.agencies.length - list.length;
    var hiddenSum = Y.agencies.reduce(function (s, a) {
      return a.published >= state.cutoff ? s : s + (loaded ? a.loaded : a.published);
    }, 0);
    $('rest').textContent = hidden
      ? hidden + ' smaller offices not shown, ' + money(hiddenSum) + ' between them'
      : 'All ' + list.length + ' agencies shown';

    drawReadout(list);
  }

  function drawReadout(list) {
    var police = Y.agencies.filter(function (a) { return a.code === '056'; })[0];
    var fire = Y.agencies.filter(function (a) { return a.code === '057'; })[0];
    var doe = Y.agencies.filter(function (a) { return a.code === '040'; })[0];
    var el = $('readout');
    if (state.mode === 'pub') {
      el.innerHTML = 'This is the budget as the city publishes it, and as every chart of it ' +
        'gets drawn. The Police Department is a <b>' + moneyRound(police.published) + '</b> line, the ' +
        'Fire Department <b>' + moneyRound(fire.published) + '</b>. Neither figure includes a pension ' +
        'contribution or a dollar of health insurance. Switch to fully loaded.';
    } else {
      el.innerHTML = 'Now every pooled dollar sits with the agency that ran it up. Police: <b>' +
        moneyRound(police.loaded) + '</b>, up ' + Math.round((mult(police) - 1) * 100) + '&#37;. Fire: <b>' +
        moneyRound(fire.loaded) + '</b>, double its line. Education moves least, <b>' +
        moneyRound(doe.loaded) + '</b> against ' + moneyRound(doe.published) + ', because it already buys ' +
        'its own health insurance and payroll taxes out of its own budget. The agencies that ' +
        'barely move are the ones that spend on contracts rather than staff.';
    }
  }

  // ---------- pooled accounts ----------
  function drawPools() {
    var p = Y.pools;
    var poolTotal = p.pension.total - p.pension.unallocated + p.fringe.by_head +
      p.fringe.by_payroll + p.judgments.allocated;
    $('poolTot').textContent = money(poolTotal) + ' reassigned';

    var rows = [
      { cls: 'pen', label: 'Pension contributions', amount: p.pension.total - p.pension.unallocated,
        sub: moneyLong(p.pension.sourced) + ' named to a single workforce &middot; ' +
             moneyLong(p.pension.shared) + ' shared',
        note: 'The budget writes each retirement system on its own line. Teachers and the ' +
              'Board of Education system go to the schools, the Police Pension Fund to one ' +
              'department, the Fire Pension Fund to one department. Only the payment to the ' +
              'employees’ retirement system, which covers everyone else, has to be shared out.' },
      { cls: 'fri', label: 'Health insurance and payroll taxes',
        amount: p.fringe.by_head + p.fringe.by_payroll,
        sub: dollars(p.fringe.per_position) + ' a position, over ' +
             p.fringe.positions_in_base.toLocaleString('en-US') + ' positions',
        note: 'Coverage and welfare fund contributions follow people, so they are divided by ' +
              'budgeted positions. Payroll taxes follow wages, so they are divided by payroll. ' +
              'Education and the City University buy their own and are left out of the split.' },
      { cls: 'jud', label: 'Judgments and claims', amount: p.judgments.allocated,
        sub: 'Split on settled claims, ' + D.meta.claims_years,
        note: 'The comptroller records the agency named in every settled claim. The Police ' +
              'Department accounts for ' + pct(D.meta.claims_shares['Police']) + ' of settlement ' +
              'dollars, transportation ' + pct(D.meta.claims_shares['Transportation']) +
              ', sanitation ' + pct(D.meta.claims_shares['Sanitation']) + '.' }
    ];
    var scale = Math.max.apply(null, rows.map(function (r) { return r.amount; }));
    $('pools').innerHTML = rows.map(function (r) {
      return '<div class="pline ' + r.cls + '">' +
        '<div class="top"><b>' + r.label + '</b><u>' + money(r.amount) + '</u></div>' +
        '<div class="bar" style="width:' + (100 * r.amount / scale).toFixed(2) + '%"></div>' +
        '<div class="sub2">' + r.sub + '</div>' +
        '<p>' + r.note + '</p></div>';
    }).join('');
  }

  function drawUnalloc() {
    var total = Y.unallocated.reduce(function (s, u) { return s + u.amount; }, 0);
    $('unTot').textContent = money(total) + ', ' + pct(total / Y.total) + ' of the budget';
    var scale = Math.max.apply(null, Y.unallocated.map(function (u) { return u.amount; }));
    $('unalloc').innerHTML = Y.unallocated.map(function (u) {
      return '<div class="pline un">' +
        '<div class="top"><b>' + u.label + '</b><u>' + money(u.amount) + '</u></div>' +
        '<div class="bar" style="width:' + (100 * u.amount / scale).toFixed(2) + '%"></div>' +
        (u.note ? '<p>' + u.note + '</p>' : '') + '</div>';
    }).join('');
  }

  // ---------- agency drawer ----------
  // Say which part of the pension figure is the budget's own line and which
  // part is a share of the pooled payment, rather than calling all of it sourced.
  function pensionTier(a) {
    var named = a.pension_named || 0, shared = a.pension_shared || 0;
    var pooled = 'a share of the employees’ retirement system payment, by payroll';
    if (named && shared > named * 0.01) {
      return 'Named in the budget: ' + a.pension_note.toLowerCase() + ', ' +
        money(named) + ' &middot; plus ' + money(shared) + ', ' + pooled;
    }
    if (named) return 'Named in the budget: ' + a.pension_note.toLowerCase();
    return 'Entirely ' + pooled;
  }

  function openAgency(a) {
    var pop = D.meta.population;
    var per = function (v) { return '$' + Math.round(v / pop).toLocaleString('en-US'); };
    var rows = [
      ['<span class="swatch sw base"></span>Budget line, as published' +
        (a.self_health ? '<span class="tier">Includes ' + money(a.own_fringe) +
          ' of benefits this agency buys directly</span>' : ''), a.published],
      ['<span class="swatch sw pen"></span>Pension contribution' +
        '<span class="tier">' + pensionTier(a) + '</span>', a.add.pension],
      ['<span class="swatch sw fri"></span>Health insurance and payroll taxes' +
        '<span class="tier">' + (a.self_health
          ? 'Buys its own; this is the residual share of the central pool'
          : 'Shared by ' + a.positions.toLocaleString('en-US') + ' budgeted positions and payroll')
        + '</span>', a.add.fringe],
      ['<span class="swatch sw jud"></span>Judgments and claims' +
        '<span class="tier">Share of settled claims naming this agency</span>', a.add.judgments]
    ];
    var body =
      '<table class="calc"><tbody>' +
      rows.map(function (r) {
        return '<tr><td>' + r[0] + '</td><td class="n">' + dollars(r[1]) + '</td></tr>';
      }).join('') +
      '<tr class="sum"><td>Fully loaded cost</td><td class="n">' + dollars(a.loaded) +
      '</td></tr></tbody></table>' +
      '<dl class="f">' +
      '<div><dt>Understated by</dt><dd>' + moneyLong(a.loaded - a.published) + ', ' +
        mult(a).toFixed(2) + ' times the published line</dd></div>' +
      '<div><dt>Share of the budget</dt><dd>' + pct(a.published / Y.total) +
        ' as published, ' + pct(a.loaded / Y.total) + ' fully loaded</dd></div>' +
      '<div><dt>Per New Yorker</dt><dd>' + per(a.published) + ' as published, ' +
        per(a.loaded) + ' fully loaded</dd></div>' +
      '<div><dt>Budgeted positions</dt><dd>' + a.positions.toLocaleString('en-US') +
        ', payroll ' + moneyLong(a.payroll) + '</dd></div>' +
      '<div><dt>Payroll as a share</dt><dd>' + pct(a.payroll / a.published) +
        ' of the published line. The lower this is, the less the agency moves when the ' +
        'pooled money comes home.</dd></div>' +
      '<div><dt>Agency code</dt><dd>' + a.code + ' &middot; ' + a.full + '</dd></div>' +
      '</dl>';
    $('dLbl').textContent = 'Fiscal ' + Y.fy + ' adopted budget';
    $('dTitle').textContent = a.name;
    $('dBody').innerHTML = body;
    $('drawer').classList.add('open');
  }

  function closeDrawer() { $('drawer').classList.remove('open'); }

  // ---------- the multiple, year by year ----------
  var INKS = ['#2d4a86', '#b07326', '#4a6b52', '#8a4a6b', '#2b6f75', '#6d2b2b'];

  function drawTrend() {
    var years = D.meta.years;
    var W = 940, H = 330, L = 44, R = 172, T = 16, B = 34;
    var all = D.trend;
    var hi = 0;
    all.forEach(function (t) {
      t.m.forEach(function (v) { if (v && v > hi) hi = v; });
    });
    hi = Math.ceil(hi * 10) / 10;
    var x = function (i) { return L + i * (W - L - R) / (years.length - 1); };
    var y = function (v) { return T + (H - T - B) * (1 - (v - 1) / (hi - 1)); };
    var path = function (m) {
      return m.map(function (v, i) {
        return (i ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(v).toFixed(1);
      }).join(' ');
    };

    var lit = state.lit;
    var svg = ['<svg viewBox="0 0 ' + W + ' ' + H + '" class="trendsvg" ' +
               'preserveAspectRatio="xMidYMid meet" role="img" ' +
               'aria-label="Each agency’s fully loaded cost as a multiple of its published ' +
               'budget line, fiscal 2017 to ' + D.meta.current + '">'];

    // gridlines at every tenth
    for (var g = 1; g <= hi + 0.001; g += 0.2) {
      svg.push('<line x1="' + L + '" x2="' + (W - R) + '" y1="' + y(g).toFixed(1) +
               '" y2="' + y(g).toFixed(1) + '" stroke="' + (Math.abs(g - 1) < 0.001 ?
               '#1b1e1c' : '#d8dcd6') + '" stroke-width="1"/>');
      svg.push('<text x="' + (L - 8) + '" y="' + (y(g) + 3.5).toFixed(1) +
               '" class="tlab" text-anchor="end">' + g.toFixed(1) + '×</text>');
    }
    years.forEach(function (fy, i) {
      if (i % 2 && i !== years.length - 1) return;
      svg.push('<text x="' + x(i).toFixed(1) + '" y="' + (H - 12) +
               '" class="tlab" text-anchor="middle">’' + String(fy).slice(2) + '</text>');
    });

    all.forEach(function (t) {
      if (lit.indexOf(t.code) >= 0) return;
      svg.push('<path d="' + path(t.m) + '" fill="none" stroke="#c7ccc5" stroke-width="1.1" ' +
               'opacity=".8"/>');
    });
    lit.forEach(function (code, n) {
      var t = all.filter(function (a) { return a.code === code; })[0];
      if (!t) return;
      var ink = INKS[n % INKS.length];
      svg.push('<path d="' + path(t.m) + '" fill="none" stroke="' + ink +
               '" stroke-width="2.4" style="mix-blend-mode:multiply"/>');
      var last = t.m[t.m.length - 1];
      svg.push('<circle cx="' + x(years.length - 1).toFixed(1) + '" cy="' + y(last).toFixed(1) +
               '" r="3.2" fill="' + ink + '"/>');
      svg.push('<text x="' + (W - R + 10) + '" y="' + (y(last) + 4).toFixed(1) +
               '" class="tend" fill="' + ink + '">' + t.name + ' ' + last.toFixed(2) + '×</text>');
    });
    svg.push('</svg>');
    $('trend').innerHTML = svg.join('');

    // Chips are the biggest agencies, not the highest multiples, or the row
    // fills up with district attorneys and never offers Education or Sanitation.
    var bySize = all.slice().sort(function (x, y) { return y.published - x.published; });
    $('trendChips').innerHTML = bySize.slice(0, 14).map(function (t) {
      return '<button class="chip" data-trend="' + t.code + '" aria-pressed="' +
        (lit.indexOf(t.code) >= 0) + '">' + t.name + '</button>';
    }).join('');
    document.querySelectorAll('[data-trend]').forEach(function (b) {
      b.addEventListener('click', function () {
        var code = b.getAttribute('data-trend');
        var i = state.lit.indexOf(code);
        if (i >= 0) state.lit.splice(i, 1);
        else if (state.lit.length < 6) state.lit.push(code);
        drawTrend();
      });
    });
    $('trendNote').textContent = all.length + ' agencies over $100 million, ' +
      years[0] + ' to ' + D.meta.current;
  }

  // ---------- header numbers ----------
  function drawHeader() {
    var m = D.meta;
    var c = Y.checks;
    var safety = Y.agencies.filter(function (a) {
      return a.code === '056' || a.code === '057' || a.code === '072';
    });
    var sPub = safety.reduce(function (s, a) { return s + a.published; }, 0);
    var sLoad = safety.reduce(function (s, a) { return s + a.loaded; }, 0);

    $('fyStrip').textContent = Y.fy;
    $('fyCap').textContent = Y.fy;
    $('capTotal').textContent = moneyLong(Y.total);
    $('capPos').textContent = Y.positions.toLocaleString('en-US');
    $('capBasis').textContent = Y.fy === m.current
      ? 'the year now under way' : 'as adopted';
    $('cTotal').textContent = money(Y.total);
    $('cPool').textContent = money(c.reallocated);
    $('cUnalloc').textContent = money(c.unallocated);
    $('cSafety').textContent = money(sLoad);
    document.querySelector('#cSafety').nextElementSibling.textContent =
      'Police, fire and jails, printed as ' + moneyRound(sPub);

    var f = Y.pools.fringe;
    var self = f.self_funded;
    $('mSourced').textContent = moneyLong(Y.pools.pension.sourced);
    $('mRate').textContent = dollars(f.per_position);
    $('mDoe').textContent = dollars(self['Department Of Education']);
    $('mCuny').textContent = dollars(self['City University Of New York']);
    $('mClaims').textContent = m.claims_years;
    $('mMatch').textContent = pct(m.settlement_dollars_matched);
    $('mTotal').textContent = moneyLong(Y.total);
    $('mDrift').textContent = '$' + c.rounding_drift;
    $('mYears').textContent = m.years[0] + ' to ' + m.current;
  }

  // ---------- wiring ----------
  function setMode(mode) {
    state.mode = mode;
    $('tPub').setAttribute('aria-pressed', String(mode === 'pub'));
    $('tLoad').setAttribute('aria-pressed', String(mode === 'load'));
    drawRank();
  }

  function setYear(fy) {
    state.fy = fy;
    Y = D.years[String(fy)];
    rowEls = {};
    $('rank').innerHTML = '';
    drawHeader();
    drawPools();
    drawUnalloc();
    drawRank();
  }

  fetch('data.json?v=3').then(function (r) {
    if (!r.ok) throw new Error('data.json ' + r.status);
    return r.json();
  }).then(function (d) {
    D = d;
    $('year').innerHTML = d.meta.years.slice().reverse().map(function (fy) {
      return '<option value="' + fy + '">Fiscal ' + fy +
        (fy === d.meta.current ? ' — current' : '') + '</option>';
    }).join('');
    setYear(d.meta.current);
    drawTrend();

    $('year').addEventListener('change', function () {
      setYear(Number($('year').value));
    });
    $('tPub').addEventListener('click', function () { setMode('pub'); });
    $('tLoad').addEventListener('click', function () { setMode('load'); });
    document.querySelectorAll('[data-sort]').forEach(function (b) {
      b.addEventListener('click', function () {
        state.sort = b.getAttribute('data-sort');
        document.querySelectorAll('[data-sort]').forEach(function (o) {
          o.setAttribute('aria-pressed', String(o === b));
        });
        drawRank();
      });
    });
    $('cutoff').addEventListener('change', function () {
      state.cutoff = Number($('cutoff').value);
      drawRank();
    });
    document.querySelectorAll('[data-close]').forEach(function (e) {
      e.addEventListener('click', closeDrawer);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeDrawer();
    });
    $('aiBtn').addEventListener('click', function () {
      var open = $('aiPop').hidden;
      $('aiPop').hidden = !open;
      $('aiBtn').setAttribute('aria-expanded', String(open));
    });
  }).catch(function (err) {
    $('rank').innerHTML = '<p class="empty">Could not load the budget data: ' +
      err.message + '</p>';
  });
})();
