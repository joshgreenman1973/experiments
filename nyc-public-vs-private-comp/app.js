// NYC Public vs Private compensation dashboard
(function () {
  const D = window.DATA;
  const $ = (id) => document.getElementById(id);
  const fmt$ = (v, d = 0) => '$' + Number(v).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });
  const fmtN = (v) => Number(v).toLocaleString('en-US');

  // Colors
  const C = {
    pub: '#0f6b6b', pubLight: '#e6f2f0',
    priv: '#c2410c', privLight: '#fbe9dc',
    fed: '#4a5578', state: '#7c5dc7',
    ink: '#0a0a0f', muted: '#5b5e6b', paper: '#fbf8f2',
  };

  // Chart.js global defaults
  if (window.Chart) {
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = C.ink;
    Chart.defaults.borderColor = '#e6e3da';
    if (window['chartjs-plugin-annotation']) {
      Chart.register(window['chartjs-plugin-annotation']);
    }
  }

  // --- Tab switcher
  document.querySelectorAll('nav.tabs button').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('nav.tabs button').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('section.panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const tab = document.getElementById(btn.dataset.tab);
      tab.classList.add('active');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });

  // --- Today's date
  $('today').textContent = new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

  // --- QCEW data arrays
  const years = Object.keys(D.qcew).map(Number).sort((a,b)=>a-b);
  const sectors = ['Private', 'Local', 'State', 'Federal'];
  const sectorLabels = { Private: 'Private', Local: 'Local gov', State: 'State gov', Federal: 'Federal' };
  const sectorColor = { Private: C.priv, Local: C.pub, State: C.state, Federal: C.fed };

  function series(metric) {
    const out = {};
    sectors.forEach(s => {
      out[s] = years.map(y => {
        const row = D.qcew[y] && D.qcew[y][s];
        return row ? row[metric] : null;
      });
    });
    return out;
  }

  // --- HERO panel: total compensation framing
  const lastYr = years[years.length - 1];
  const hero = D.qcew[lastYr];
  const ececL = D.ecec_annual[Math.max(...Object.keys(D.ecec_annual).map(Number))];

  // Decompose benefits into components using national ECEC ratios, then apply to NYC salaries
  function decompose(nycWage, ececSide) {
    // ECEC publishes $/hr; we take ratios against wages and apply to NYC annual wage.
    const wageHr = ececSide.wages;
    const ratio = (k) => (ececSide[k] || 0) / wageHr;
    return {
      salary: nycWage,
      health: nycWage * ratio('health_insurance'),
      retirement: nycWage * ratio('retirement'),
      paid_leave: nycWage * ratio('paid_leave'),
      supp: nycWage * ratio('supp_pay') + nycWage * Math.max(0, ratio('insurance') - ratio('health_insurance')),
      legal: nycWage * ratio('legally_required'),
    };
  }
  const pubComp = decompose(hero.Local.avg_annual_wage, ececL.StateLocal);
  const privComp = decompose(hero.Private.avg_annual_wage, ececL.Private);
  const pubTotal = Object.values(pubComp).reduce((a,b)=>a+b,0);
  const privTotal = Object.values(privComp).reduce((a,b)=>a+b,0);
  const pubBenTotal = pubTotal - pubComp.salary;
  const privBenTotal = privTotal - privComp.salary;

  $('hero-pub-big').textContent = fmt$(Math.round(pubTotal));
  $('hero-priv-big').textContent = fmt$(Math.round(privTotal));
  $('pub-ben-pct').textContent = ((pubBenTotal / pubTotal) * 100).toFixed(0);
  $('priv-ben-pct').textContent = ((privBenTotal / privTotal) * 100).toFixed(0);

  $('s-pub-sal').textContent = fmt$(Math.round(pubComp.salary));
  $('s-priv-sal').textContent = fmt$(Math.round(privComp.salary));
  $('s-pub-bigben').textContent = fmt$(Math.round(pubComp.health + pubComp.retirement));
  $('s-priv-bigben').textContent = fmt$(Math.round(privComp.health + privComp.retirement));

  const totalGap = privTotal - pubTotal;
  const wageGap = hero.Private.avg_annual_wage - hero.Local.avg_annual_wage;
  $('total-gap').textContent = fmt$(Math.round(totalGap));
  $('wage-gap-reveal').textContent = fmt$(Math.round(wageGap));

  // Stacked comp bars
  const stackEl = $('stack-bars');
  const stackMax = Math.max(pubTotal, privTotal);
  const partMeta = [
    { k: 'salary',      label: 'Salary',        color: '#1a1d2e' },
    { k: 'health',      label: 'Health ins.',   color: '#0f6b6b' },
    { k: 'retirement',  label: 'Retirement',    color: '#7c5dc7' },
    { k: 'paid_leave',  label: 'Paid leave',    color: '#b78c2c' },
    { k: 'supp',        label: 'Supp. pay',     color: '#8a5a44' },
    { k: 'legal',       label: 'Payroll taxes', color: '#4a5578' },
  ];
  function stackBar(label, comp, total) {
    const segs = partMeta.map(p => {
      const v = comp[p.k];
      const w = (v / stackMax) * 100;
      if (w < 0.5) return '';
      return `<div style="width:${w}%; background:${p.color}; height:100%; display:flex; align-items:center; padding:0 6px; color:#fff; font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:600; overflow:hidden; white-space:nowrap;" title="${p.label}: ${fmt$(Math.round(v))}">${w > 6 ? '$' + Math.round(v/1000) + 'k' : ''}</div>`;
    }).join('');
    return `
      <div style="margin-bottom:18px;">
        <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px;">
          <div style="font-family:'JetBrains Mono',monospace; font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:#5b5e6b;">${label}</div>
          <div style="font-family:'Fraunces',serif; font-weight:700; font-size:20px;">${fmt$(Math.round(total))}</div>
        </div>
        <div style="display:flex; height:38px; background:#f3efe4; border:1px solid #1a1d2e;">${segs}</div>
      </div>
    `;
  }
  stackEl.innerHTML = stackBar('NYC Private total comp', privComp, privTotal) + stackBar('NYC Local gov total comp', pubComp, pubTotal);

  // --- WAGES panel
  let wagesChart;
  function drawWages(metric) {
    const s = series(metric);
    const isEmpl = metric === 'employment';
    const ctx = $('chart-wages').getContext('2d');
    if (wagesChart) wagesChart.destroy();
    wagesChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: years,
        datasets: sectors.map(sec => ({
          label: sectorLabels[sec],
          data: s[sec],
          borderColor: sectorColor[sec],
          backgroundColor: sectorColor[sec] + '22',
          borderWidth: sec === 'Private' || sec === 'Local' ? 3 : 2,
          pointRadius: 0,
          pointHoverRadius: 5,
          tension: 0.25,
          fill: false,
        })),
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0a0a0f', padding: 12, cornerRadius: 0,
            titleFont: { family: 'JetBrains Mono', size: 12 },
            bodyFont: { size: 13 },
            callbacks: {
              label: (c) => `${c.dataset.label}: ${isEmpl ? fmtN(c.raw) : fmt$(c.raw)}`,
            },
          },
        },
        scales: {
          y: {
            beginAtZero: isEmpl,
            ticks: { callback: (v) => isEmpl ? fmtN(v) : fmt$(v) },
            grid: { color: '#e6e3da' },
          },
          x: { grid: { display: false } },
        },
      },
    });
    const title = { avg_annual_wage: 'NYC average annual wage by sector', avg_weekly_wage: 'NYC average weekly wage by sector', employment: 'NYC employment by sector' };
    $('wages-title').textContent = title[metric];

    // pullquote wage ratio
    const latest = D.qcew[lastYr];
    const ratio = latest.Private.avg_annual_wage / latest.Local.avg_annual_wage;
    $('wage-ratio').innerHTML = '$' + ratio.toFixed(2);
  }
  drawWages('avg_annual_wage');
  document.querySelectorAll('[data-metric]').forEach(b => {
    b.addEventListener('click', () => {
      document.querySelectorAll('[data-metric]').forEach(x => x.classList.remove('on'));
      b.classList.add('on');
      drawWages(b.dataset.metric);
    });
  });

  // --- GROWTH panel: indexed
  const base = years[0];
  const baseVals = {};
  sectors.forEach(s => { baseVals[s] = D.qcew[base][s].avg_annual_wage; });
  const indexed = {};
  sectors.forEach(s => {
    indexed[s] = years.map(y => {
      const row = D.qcew[y][s];
      return row ? (row.avg_annual_wage / baseVals[s]) * 100 : null;
    });
  });

  // CPI-U approximate trajectory 2000->2024 (~85% cumulative). For display:
  // Use actual BLS CPI-U annual averages (2000=172.2, 2024=313.7 -> 182.2 indexed).
  const cpiAnchor = [
    [2000, 172.2], [2001, 177.1], [2002, 179.9], [2003, 184.0], [2004, 188.9],
    [2005, 195.3], [2006, 201.6], [2007, 207.3], [2008, 215.3], [2009, 214.5],
    [2010, 218.1], [2011, 224.9], [2012, 229.6], [2013, 233.0], [2014, 236.7],
    [2015, 237.0], [2016, 240.0], [2017, 245.1], [2018, 251.1], [2019, 255.7],
    [2020, 258.8], [2021, 271.0], [2022, 292.7], [2023, 304.7], [2024, 313.7],
  ];
  const cpiMap = Object.fromEntries(cpiAnchor);
  const cpiSeries = years.map(y => cpiMap[y] ? (cpiMap[y] / cpiMap[base]) * 100 : null);

  new Chart($('chart-growth').getContext('2d'), {
    type: 'line',
    data: {
      labels: years,
      datasets: [
        ...sectors.map(sec => ({
          label: sectorLabels[sec],
          data: indexed[sec],
          borderColor: sectorColor[sec],
          borderWidth: sec === 'Private' || sec === 'Local' ? 3 : 2,
          backgroundColor: 'transparent',
          pointRadius: 0, pointHoverRadius: 5,
          tension: 0.2,
          fill: false,
        })),
        {
          label: 'CPI-U (inflation)',
          data: cpiSeries,
          borderColor: C.muted,
          borderDash: [6, 4],
          borderWidth: 2,
          backgroundColor: 'transparent',
          pointRadius: 0,
          tension: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 14, font: { size: 11, family: 'JetBrains Mono' } } },
        tooltip: {
          backgroundColor: '#0a0a0f', padding: 12, cornerRadius: 0,
          callbacks: {
            label: (c) => `${c.dataset.label}: ${c.raw != null ? c.raw.toFixed(1) : '—'}`,
          },
        },
      },
      scales: {
        y: { ticks: { callback: (v) => v }, grid: { color: '#e6e3da' } },
        x: { grid: { display: false } },
      },
    },
  });

  // Growth bar & CAGR
  const growthBarData = sectors.map(sec => {
    const first = D.qcew[base][sec].avg_annual_wage;
    const last = D.qcew[lastYr][sec].avg_annual_wage;
    return { sec, pct: ((last / first) - 1) * 100, cagr: ((Math.pow(last / first, 1 / (lastYr - base))) - 1) * 100 };
  });
  // Plus CPI
  const cpiFirst = cpiMap[base], cpiLast = cpiMap[lastYr];
  growthBarData.push({ sec: 'CPI-U', pct: ((cpiLast / cpiFirst) - 1) * 100, cagr: ((Math.pow(cpiLast / cpiFirst, 1 / (lastYr - base))) - 1) * 100 });

  new Chart($('chart-growth-bar').getContext('2d'), {
    type: 'bar',
    data: {
      labels: growthBarData.map(r => r.sec === 'Private' ? 'Private' : (r.sec === 'CPI-U' ? 'CPI-U' : sectorLabels[r.sec] || r.sec)),
      datasets: [{
        data: growthBarData.map(r => r.pct),
        backgroundColor: growthBarData.map(r => r.sec === 'CPI-U' ? C.muted : (sectorColor[r.sec] || C.ink)),
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0a0a0f', padding: 10, cornerRadius: 0,
          callbacks: { label: (c) => `+${c.raw.toFixed(1)}%` },
        },
      },
      scales: {
        x: { ticks: { callback: v => '+' + v + '%' }, grid: { color: '#e6e3da' } },
        y: { grid: { display: false } },
      },
    },
  });

  new Chart($('chart-cagr').getContext('2d'), {
    type: 'bar',
    data: {
      labels: growthBarData.map(r => r.sec === 'Private' ? 'Private' : (r.sec === 'CPI-U' ? 'CPI-U' : sectorLabels[r.sec] || r.sec)),
      datasets: [{
        data: growthBarData.map(r => r.cagr),
        backgroundColor: growthBarData.map(r => r.sec === 'CPI-U' ? C.muted : (sectorColor[r.sec] || C.ink)),
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0a0a0f', padding: 10, cornerRadius: 0,
          callbacks: { label: (c) => c.raw.toFixed(2) + '% /yr' },
        },
      },
      scales: {
        x: { ticks: { callback: v => v + '%' }, grid: { color: '#e6e3da' } },
        y: { grid: { display: false } },
      },
    },
  });

  // --- BENEFITS panel
  const ecY = Object.keys(D.ecec_annual).map(Number).sort((a,b)=>a-b);
  const pubBen = ecY.map(y => D.ecec_annual[y]?.StateLocal?.benefits ?? null);
  const privBen = ecY.map(y => D.ecec_annual[y]?.Private?.benefits ?? null);

  new Chart($('chart-benefits').getContext('2d'), {
    type: 'line',
    data: {
      labels: ecY,
      datasets: [
        { label: 'State & local gov', data: pubBen, borderColor: C.pub, backgroundColor: C.pub + '20', borderWidth: 3, pointRadius: 0, pointHoverRadius: 5, fill: true, tension: 0.25 },
        { label: 'Private industry', data: privBen, borderColor: C.priv, backgroundColor: C.priv + '20', borderWidth: 3, pointRadius: 0, pointHoverRadius: 5, fill: true, tension: 0.25 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 14, font: { size: 11, family: 'JetBrains Mono' } } },
        tooltip: {
          backgroundColor: '#0a0a0f', padding: 12, cornerRadius: 0,
          callbacks: { label: c => `${c.dataset.label}: $${c.raw.toFixed(2)}/hr` },
        },
      },
      scales: {
        y: { beginAtZero: true, ticks: { callback: v => '$' + v }, grid: { color: '#e6e3da' } },
        x: { grid: { display: false } },
      },
    },
  });

  // Donuts
  function donut(canvasId, data, totalBenefits) {
    const labels = ['Paid leave', 'Supp. pay', 'Insurance', 'Retirement', 'Legally required'];
    const vals = [data.paid_leave, data.supp_pay, data.insurance, data.retirement, data.legally_required];
    const colors = ['#b78c2c', '#8a5a44', '#0f6b6b', '#7c5dc7', '#4a5578'];
    new Chart(document.getElementById(canvasId).getContext('2d'), {
      type: 'doughnut',
      data: { labels, datasets: [{ data: vals, backgroundColor: colors, borderColor: '#fff', borderWidth: 2 }] },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '62%',
        plugins: {
          legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: {
            backgroundColor: '#0a0a0f', padding: 12, cornerRadius: 0,
            callbacks: { label: c => `${c.label}: $${c.raw.toFixed(2)}/hr (${((c.raw / totalBenefits) * 100).toFixed(0)}%)` },
          },
        },
      },
    });
  }
  donut('chart-priv-donut', ececL.Private, ececL.Private.benefits);
  donut('chart-pub-donut', ececL.StateLocal, ececL.StateLocal.benefits);

  // --- PENSIONS panel
  function twoLine(canvasId, key, unit = '$') {
    const pub = ecY.map(y => D.ecec_annual[y]?.StateLocal?.[key] ?? null);
    const priv = ecY.map(y => D.ecec_annual[y]?.Private?.[key] ?? null);
    new Chart(document.getElementById(canvasId).getContext('2d'), {
      type: 'line',
      data: {
        labels: ecY,
        datasets: [
          { label: 'State & local gov', data: pub, borderColor: C.pub, backgroundColor: C.pub + '20', borderWidth: 3, pointRadius: 0, pointHoverRadius: 5, fill: true, tension: 0.25 },
          { label: 'Private industry', data: priv, borderColor: C.priv, backgroundColor: C.priv + '20', borderWidth: 3, pointRadius: 0, pointHoverRadius: 5, fill: true, tension: 0.25 },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 14, font: { size: 11, family: 'JetBrains Mono' } } },
          tooltip: {
            backgroundColor: '#0a0a0f', padding: 12, cornerRadius: 0,
            callbacks: { label: c => `${c.dataset.label}: ${unit}${c.raw.toFixed(2)}/hr` },
          },
        },
        scales: {
          y: { beginAtZero: true, ticks: { callback: v => unit + v }, grid: { color: '#e6e3da' } },
          x: { grid: { display: false } },
        },
      },
    });
  }
  twoLine('chart-retire', 'retirement');
  twoLine('chart-health', 'health_insurance');
  twoLine('chart-leave', 'paid_leave');

  // --- NYC PAYROLL panel
  const payY = D.payroll_yearly.map(r => ({
    yr: Number(r.fiscal_year),
    n: Number(r.n),
    mean: Number(r.mean_reg),
    median: Number(r.median_reg),
    ot: Number(r.mean_ot),
    other: Number(r.mean_other),
  })).filter(r => r.yr >= 2014).sort((a,b)=>a.yr-b.yr);

  new Chart($('chart-payroll-mm').getContext('2d'), {
    type: 'line',
    data: {
      labels: payY.map(r => 'FY' + r.yr),
      datasets: [
        { label: 'Mean regular gross', data: payY.map(r => r.mean), borderColor: C.pub, backgroundColor: 'transparent', borderWidth: 3, pointRadius: 3, tension: 0.2 },
        { label: 'Median regular gross', data: payY.map(r => r.median), borderColor: C.priv, backgroundColor: 'transparent', borderWidth: 3, pointRadius: 3, tension: 0.2 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 14, font: { size: 11, family: 'JetBrains Mono' } } },
        tooltip: { backgroundColor: '#0a0a0f', padding: 12, cornerRadius: 0, callbacks: { label: c => `${c.dataset.label}: ${fmt$(c.raw)}` } },
      },
      scales: {
        y: { beginAtZero: true, ticks: { callback: v => fmt$(v) }, grid: { color: '#e6e3da' } },
        x: { grid: { display: false } },
      },
    },
  });

  new Chart($('chart-payroll-n').getContext('2d'), {
    type: 'bar',
    data: {
      labels: payY.map(r => 'FY' + r.yr),
      datasets: [{ data: payY.map(r => r.n), backgroundColor: C.pub, borderWidth: 0 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: '#0a0a0f', padding: 12, cornerRadius: 0, callbacks: { label: c => fmtN(c.raw) + ' workers' } },
      },
      scales: {
        y: { beginAtZero: true, ticks: { callback: v => fmtN(v) }, grid: { color: '#e6e3da' } },
        x: { grid: { display: false } },
      },
    },
  });

  // Histogram
  const hist = D.payroll_histogram;
  $('hist-yr').textContent = hist.year;
  const bins = hist.bins;
  const labels = bins.map(b => b.hi ? `$${b.lo/1000}k–$${b.hi/1000}k` : `$${b.lo/1000}k+`);
  new Chart($('chart-hist').getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: bins.map(b => b.n),
        backgroundColor: bins.map(b => {
          // accent $100k range for city workers
          if (b.lo >= 80000 && b.lo < 120000) return C.pub;
          if (b.lo >= 40000 && b.lo < 80000) return '#1a9a9a';
          return C.pubLight.replace('#', '#') && '#8fbdb5';
        }),
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: '#0a0a0f', padding: 12, cornerRadius: 0, callbacks: { label: c => fmtN(c.raw) + ' employees' } },
      },
      scales: {
        y: { beginAtZero: true, ticks: { callback: v => fmtN(v) }, grid: { color: '#e6e3da' } },
        x: { grid: { display: false }, ticks: { autoSkip: false, maxRotation: 90, minRotation: 60, font: { size: 10 } } },
      },
    },
  });

  // --- AGENCIES panel
  $('ag-yr').textContent = D.payroll_agencies.year;
  const agencies = D.payroll_agencies.agencies
    .map(a => ({
      name: a.agency_name,
      n: Number(a.n),
      mean: Number(a.mean_reg),
      median: Number(a.median_reg),
      ot: Number(a.mean_ot),
      other: Number(a.mean_other),
      totalMean: Number(a.mean_reg) + Number(a.mean_ot) + Number(a.mean_other),
    }))
    .filter(a => a.n >= 500)
    .sort((a,b) => b.median - a.median)
    .slice(0, 20);

  new Chart($('chart-agencies').getContext('2d'), {
    type: 'bar',
    data: {
      labels: agencies.map(a => a.name),
      datasets: [
        { label: 'Base (mean)', data: agencies.map(a => a.mean), backgroundColor: C.pub, stack: 'a', borderWidth: 0 },
        { label: 'Overtime (mean)', data: agencies.map(a => a.ot), backgroundColor: '#1a9a9a', stack: 'a', borderWidth: 0 },
        { label: 'Other pay (mean)', data: agencies.map(a => a.other), backgroundColor: '#b78c2c', stack: 'a', borderWidth: 0 },
        { label: 'Median base', data: agencies.map(a => a.median), type: 'scatter', backgroundColor: C.priv, borderColor: C.priv, pointStyle: 'rectRot', pointRadius: 7, pointHoverRadius: 9 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11, family: 'JetBrains Mono' } } },
        tooltip: { backgroundColor: '#0a0a0f', padding: 10, cornerRadius: 0, callbacks: { label: c => `${c.dataset.label}: ${fmt$(c.raw)}` } },
      },
      scales: {
        x: { stacked: true, beginAtZero: true, ticks: { callback: v => fmt$(v) }, grid: { color: '#e6e3da' } },
        y: { stacked: true, grid: { display: false }, ticks: { font: { size: 10 } } },
      },
    },
  });

  // --- MATCHED OCCUPATIONS panel — 3 bars: NYC public, NYC private (ACS PUMS), MSA
  const matchedEl = $('matched-bars');
  if (matchedEl && D.matched) {
    const rowsM = D.matched.filter(r => r.nyc_public && r.nyc_public.n > 50);
    const vals = rowsM.flatMap(r => [
      r.nyc_public.median_reg,
      r.nyc_msa_all.median,
      r.nyc_private_pums && r.nyc_private_pums.median || 0,
    ]);
    const maxVal = Math.max(...vals);
    const publicDominated = new Set(['25-2021','33-3051','33-2011','21-1021']);
    matchedEl.innerHTML = rowsM.map(r => {
      const pub = r.nyc_public.median_reg;
      const msa = r.nyc_msa_all.median;
      const priv = r.nyc_private_pums && r.nyc_private_pums.median;
      const privN = r.nyc_private_pums && r.nyc_private_pums.n_records;
      const pubW = (pub / maxVal) * 100;
      const msaW = (msa / maxVal) * 100;
      const privW = priv ? (priv / maxVal) * 100 : 0;
      // Delta = NYC public vs NYC private (PUMS) when available; else vs MSA
      const base = priv != null ? priv : msa;
      const baseLabel = priv != null ? 'NYC priv' : 'MSA';
      const delta = pub - base;
      const deltaCls = delta >= 0 ? 'pub' : 'priv';
      const deltaTxt = (delta >= 0 ? '+' : '−') + '$' + Math.abs(Math.round(delta / 1000)) + 'k vs ' + baseLabel;
      const flag = publicDominated.has(r.soc) ? ' <small style="color:#b78c2c;">(NYC private sample may be thin or atypical for this occupation — see note)</small>' : '';
      const privBar = priv != null
        ? `<div class="bar" style="width:${privW}%; background:#c2410c;">NYC priv (PUMS) · ${fmt$(Math.round(priv))}  <span style="opacity:.75;margin-left:6px;">n=${fmtN(privN)}</span></div>`
        : `<div class="bar" style="width:100%; background:transparent; color:#5b5e6b; padding:0; font-style:italic;">NYC private — no reliable PUMS sample</div>`;
      const msaColor = priv != null ? '#d98a5a' : '#c2410c';
      return `
        <div class="occ-row">
          <div class="name">${r.name}${flag}<small>NYC public n=${fmtN(r.nyc_public.n)} · SOC ${r.soc}</small></div>
          <div class="bars">
            <div class="bar pub" style="width:${pubW}%">NYC public · ${fmt$(Math.round(pub))}</div>
            ${privBar}
            <div class="bar" style="width:${msaW}%; background:${msaColor};">NY-NJ MSA (all empl.) · ${fmt$(Math.round(msa))}</div>
          </div>
          <div class="delta ${deltaCls}">${deltaTxt}</div>
        </div>
      `;
    }).join('');
  }

  // Agency headcount
  const agN = D.payroll_agencies.agencies
    .map(a => ({ name: a.agency_name, n: Number(a.n) }))
    .sort((a,b) => b.n - a.n)
    .slice(0, 20);
  new Chart($('chart-agencies-n').getContext('2d'), {
    type: 'bar',
    data: {
      labels: agN.map(a => a.name),
      datasets: [{ data: agN.map(a => a.n), backgroundColor: C.pub, borderWidth: 0 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: '#0a0a0f', padding: 10, cornerRadius: 0, callbacks: { label: c => fmtN(c.raw) + ' employees' } },
      },
      scales: {
        x: { beginAtZero: true, ticks: { callback: v => fmtN(v) }, grid: { color: '#e6e3da' } },
        y: { grid: { display: false }, ticks: { font: { size: 10 } } },
      },
    },
  });
})();
