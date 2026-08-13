/* ============ AFFL Live Dashboard ============ */
(async function () {
  const WS_URL = 'ws://127.0.0.1:9876';
  
  let ws = null;
  let reconnectTimer = null;
  let currentYear = 2025;
  let currentChart = 'standings';
  let currentTeam = null;
  let season = null;  // from AFFL.data.seasons[year]
  let yearData = null;  // from years/{year}.json
  let chartInstance = null;

  const yearSelect = document.getElementById('yearSelect');
  const chartSelect = document.getElementById('chartSelect');
  const teamSelect = document.getElementById('teamSelect');
  const wsStatus = document.getElementById('wsStatus');
  const wsText = document.getElementById('wsText');
  const banner = document.getElementById('banner');
  const bannerText = document.getElementById('bannerText');
  const chartTitle = document.getElementById('chartTitle');
  const mainCanvas = document.getElementById('mainChart');
  const chartNotice = document.getElementById('chartNotice');
  const highlightInfo = document.getElementById('highlightInfo');
  const highlightTeam = document.getElementById('highlightTeam');

  // ============ INIT ============
  await AFFL.boot();
  AFFL.chartDefaults(Chart);

  const years = AFFL.years();
  yearSelect.innerHTML = years.map(y => `<option value="${y}">${y}</option>`).join('');
  yearSelect.value = currentYear;

  await loadYearData(currentYear);
  renderChart();
  connectWebSocket();

  // ============ EVENTS ============
  yearSelect.addEventListener('change', async () => {
    currentYear = +yearSelect.value;
    await loadYearData(currentYear);
    renderChart();
  });

  chartSelect.addEventListener('change', () => {
    currentChart = chartSelect.value;
    renderChart();
  });

  teamSelect.addEventListener('change', () => {
    currentTeam = teamSelect.value || null;
    renderChart();
  });

  // ============ WEBSOCKET ============
  function connectWebSocket() {
    if (ws) return;
    ws = new WebSocket(WS_URL);
    
    ws.onopen = () => {
      console.log('WS connected');
      wsStatus.classList.add('connected');
      wsText.textContent = 'Connected';
      banner.classList.remove('show');
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };

    ws.onmessage = (evt) => {
      try {
        const cmd = JSON.parse(evt.data);
        handleCommand(cmd);
      } catch (e) {
        console.error('WS parse error', e);
      }
    };

    ws.onerror = (e) => {
      console.error('WS error', e);
    };

    ws.onclose = () => {
      console.log('WS closed');
      ws = null;
      wsStatus.classList.remove('connected');
      wsText.textContent = 'Disconnected';
      banner.classList.add('show');
      bannerText.textContent = 'Start the AFFL viewer bridge (python3 mcp/bridge.py).';
      reconnectTimer = setTimeout(connectWebSocket, 3000);
    };
  }

  async function handleCommand(cmd) {
    console.log('Command:', cmd);
    switch (cmd.type) {
      case 'set_season':
        if (cmd.year) {
          currentYear = cmd.year;
          yearSelect.value = currentYear;
          await loadYearData(currentYear);
          renderChart();
        }
        break;
      case 'set_chart':
        if (cmd.chart) {
          currentChart = cmd.chart;
          chartSelect.value = currentChart;
          renderChart();
        }
        break;
      case 'highlight_team':
        currentTeam = cmd.team || null;
        teamSelect.value = currentTeam || '';
        renderChart();
        break;
      case 'state':
        // Catch up to server state on reconnect
        if (cmd.year) {
          currentYear = cmd.year;
          yearSelect.value = currentYear;
          await loadYearData(currentYear);
        }
        if (cmd.chart) {
          currentChart = cmd.chart;
          chartSelect.value = currentChart;
        }
        if (cmd.team !== undefined) {
          currentTeam = cmd.team || null;
          teamSelect.value = currentTeam || '';
        }
        renderChart();
        break;
    }
  }

  // ============ DATA ============
  async function loadYearData(year) {
    // Load season data from data.json
    season = AFFL.data.seasons[String(year)];
    if (!season) {
      season = { teams: [], regWeeks: [] };
    }
    
    // Load year-specific data from years/{year}.json
    yearData = await AFFL.loadYear(year);
    
    // Populate team selector with teams from season
    const teams = season.teams || [];
    teamSelect.innerHTML = '<option value="">All Teams</option>' +
      teams.map(t => `<option value="${t.id}">${t.name}</option>`).join('');
    if (currentTeam) teamSelect.value = currentTeam;
  }

  // ============ RENDER ============
  function renderChart() {
    if (chartInstance) {
      chartInstance.destroy();
      chartInstance = null;
    }
    chartNotice.style.display = 'none';
    mainCanvas.style.display = 'block';

    // Update highlight UI
    if (currentTeam) {
      const team = season.teams.find(t => 
        t.id === currentTeam || 
        t.abbrev === currentTeam || 
        t.name === currentTeam
      );
      highlightInfo.classList.remove('no-highlight');
      highlightTeam.textContent = team ? team.name : currentTeam;
    } else {
      highlightInfo.classList.add('no-highlight');
    }

    switch (currentChart) {
      case 'standings':
        chartTitle.textContent = `${currentYear} Standings`;
        renderStandings();
        break;
      case 'luck':
        chartTitle.textContent = `${currentYear} Luck`;
        renderLuck();
        break;
      case 'weekly':
        chartTitle.textContent = `${currentYear} Weekly Scoring`;
        renderWeekly();
        break;
      case 'lineup':
        chartTitle.textContent = `${currentYear} Lineup IQ`;
        if (currentYear < 2018) {
          showNotice('Lineup IQ data is only available from 2018 onwards.');
        } else {
          renderLineupIQ();
        }
        break;
      case 'draft':
        chartTitle.textContent = `${currentYear} Draft PAR`;
        renderDraftPAR();
        break;
      case 'payroll':
        chartTitle.textContent = `${currentYear} NFL Payroll`;
        renderPayroll();
        break;
    }
  }

  function showNotice(msg) {
    mainCanvas.style.display = 'none';
    chartNotice.style.display = 'block';
    chartNotice.textContent = msg;
  }

  // ============ CHART RENDERERS ============
  function renderStandings() {
    const teams = [...season.teams].sort((a, b) => (b.wins - a.wins) || (b.pf - a.pf));
    const labels = teams.map(t => t.abbrev || t.name.substring(0, 4).toUpperCase());
    const wins = teams.map(t => t.wins);
    const losses = teams.map(t => t.losses);
    
    const colors = teams.map((t) => 
      currentTeam && (t.id === currentTeam || t.abbrev === currentTeam || t.name === currentTeam)
        ? AFFL.C.orange 
        : AFFL.C.blue
    );

    chartInstance = new Chart(mainCanvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: 'Wins', data: wins, backgroundColor: colors, borderRadius: 6 },
          { label: 'Losses', data: losses, backgroundColor: AFFL.C.mut, borderRadius: 6 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true },
          tooltip: {
            callbacks: {
              afterLabel: (ctx) => {
                const team = teams[ctx.dataIndex];
                return `PF: ${AFFL.fmt(team.pf, 1)} | PA: ${AFFL.fmt(team.pa, 1)}`;
              }
            }
          }
        },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, beginAtZero: true }
        }
      }
    });
  }

  function renderLuck() {
    if (!season.teams[0] || season.teams[0].luck === undefined) {
      showNotice('Luck data is not available for this season.');
      return;
    }
    const teams = [...season.teams].sort((a, b) => (b.luck || 0) - (a.luck || 0));
    const labels = teams.map(t => t.abbrev || t.name.substring(0, 4).toUpperCase());
    const luck = teams.map(t => t.luck || 0);
    
    const colors = teams.map((t) => {
      if (currentTeam && (t.id === currentTeam || t.abbrev === currentTeam || t.name === currentTeam)) {
        return AFFL.C.orange;
      }
      return (t.luck || 0) >= 0 ? AFFL.C.green : AFFL.C.red;
    });

    chartInstance = new Chart(mainCanvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Luck',
          data: luck,
          backgroundColor: colors,
          borderRadius: 6
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const team = teams[ctx.dataIndex];
                return `Luck: ${AFFL.fmt(team.luck, 2)} | Record: ${team.wins}-${team.losses}`;
              }
            }
          }
        },
        scales: {
          x: { beginAtZero: true, grid: { color: AFFL.C.grid } },
          y: { grid: { display: false } }
        }
      }
    });
  }

  function renderWeekly() {
    const teams = season.teams || [];
    if (!teams.length || !teams[0].weekly) {
      showNotice('Weekly scoring data is not available for this season.');
      return;
    }

    const regWeeks = season.regWeeks || [];
    const labels = regWeeks.map(w => `Week ${w}`);
    
    let datasets;
    if (currentTeam) {
      const team = teams.find(t => 
        t.id === currentTeam || 
        t.abbrev === currentTeam || 
        t.name === currentTeam
      );
      if (!team) {
        showNotice(`Team "${currentTeam}" not found.`);
        return;
      }
      datasets = [{
        label: team.name,
        data: team.weekly,
        borderColor: AFFL.C.orange,
        backgroundColor: AFFL.C.orange + '33',
        borderWidth: 3,
        tension: 0.3,
        fill: true
      }];
    } else {
      // Show average, max, min
      const wkAvg = season.wkAvg || [];
      const wkMax = season.wkMax || [];
      const wkMin = season.wkMin || [];
      datasets = [
        { label: 'Avg', data: wkAvg, borderColor: AFFL.C.blue, borderWidth: 2, tension: 0.3 },
        { label: 'Max', data: wkMax, borderColor: AFFL.C.green, borderWidth: 2, tension: 0.3, borderDash: [5, 5] },
        { label: 'Min', data: wkMin, borderColor: AFFL.C.red, borderWidth: 2, tension: 0.3, borderDash: [5, 5] }
      ];
    }

    chartInstance = new Chart(mainCanvas, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: true } },
        scales: {
          x: { grid: { color: AFFL.C.grid } },
          y: { beginAtZero: true, grid: { color: AFFL.C.grid } }
        }
      }
    });
  }

  function renderLineupIQ() {
    if (!yearData.lineupIQ || !yearData.lineupIQ.length) {
      showNotice('Lineup IQ data is not available for this season.');
      return;
    }
    
    // Join lineupIQ with team names
    const data = yearData.lineupIQ.map(iq => {
      const team = season.teams.find(t => t.id === iq.teamId);
      return { ...iq, team };
    }).filter(d => d.team).sort((a, b) => (b.eff || 0) - (a.eff || 0));
    
    const labels = data.map(d => d.team.abbrev || d.team.name.substring(0, 4).toUpperCase());
    const efficiency = data.map(d => (d.eff || 0) * 100);
    
    const colors = data.map((d) => 
      currentTeam && (d.teamId === currentTeam || d.team.abbrev === currentTeam || d.team.name === currentTeam)
        ? AFFL.C.orange
        : AFFL.C.blue
    );

    chartInstance = new Chart(mainCanvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Efficiency %',
          data: efficiency,
          backgroundColor: colors,
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const d = data[ctx.dataIndex];
                return [
                  `Efficiency: ${AFFL.fmt(d.eff * 100, 1)}%`,
                  `Actual: ${AFFL.fmt(d.actual, 1)}`,
                  `Optimal: ${AFFL.fmt(d.optimal, 1)}`,
                  `Wasted: ${AFFL.fmt(d.wasted, 1)}`
                ];
              }
            }
          }
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, max: 100, grid: { color: AFFL.C.grid } }
        }
      }
    });
  }

  function renderDraftPAR() {
    if (!yearData.draftValue || !yearData.draftValue.teamEff || !yearData.draftValue.teamEff.length) {
      showNotice('Draft PAR data is not available for this season.');
      return;
    }
    
    const data = yearData.draftValue.teamEff.map(dv => {
      const team = season.teams.find(t => t.id === dv.teamId);
      return { ...dv, team };
    }).filter(d => d.team).sort((a, b) => (b.par || 0) - (a.par || 0));
    
    const labels = data.map(d => d.team.abbrev || d.team.name.substring(0, 4).toUpperCase());
    const par = data.map(d => d.par || 0);
    
    const colors = data.map((d) => {
      if (currentTeam && (d.teamId === currentTeam || d.team.abbrev === currentTeam || d.team.name === currentTeam)) {
        return AFFL.C.orange;
      }
      return (d.par || 0) >= 0 ? AFFL.C.green : AFFL.C.red;
    });

    chartInstance = new Chart(mainCanvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Draft PAR',
          data: par,
          backgroundColor: colors,
          borderRadius: 6
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const d = data[ctx.dataIndex];
                return [
                  `PAR: ${AFFL.fmt(d.par, 1)}`,
                  `Points: ${AFFL.fmt(d.pts, 1)}`,
                  `Spent: $${AFFL.fmt(d.spent, 0)}`
                ];
              }
            }
          }
        },
        scales: {
          x: { grid: { color: AFFL.C.grid } },
          y: { grid: { display: false } }
        }
      }
    });
  }

  function renderPayroll() {
    if (!yearData.nflCap || !yearData.nflCap.byTeam || !yearData.nflCap.byTeam.length) {
      showNotice('NFL payroll data is not available for this season.');
      return;
    }
    
    const data = yearData.nflCap.byTeam.map(cap => {
      const team = season.teams.find(t => t.id === cap.teamId);
      return { ...cap, team };
    }).filter(d => d.team).sort((a, b) => (b.totalCap || 0) - (a.totalCap || 0));
    
    const labels = data.map(d => d.team.abbrev || d.team.name.substring(0, 4).toUpperCase());
    const totalCap = data.map(d => (d.totalCap || 0) / 1000000);  // Convert to millions
    
    const colors = data.map((d) => 
      currentTeam && (d.teamId === currentTeam || d.team.abbrev === currentTeam || d.team.name === currentTeam)
        ? AFFL.C.orange
        : AFFL.C.blue
    );

    chartInstance = new Chart(mainCanvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Total Cap ($M)',
          data: totalCap,
          backgroundColor: colors,
          borderRadius: 6
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const d = data[ctx.dataIndex];
                return [
                  `Total: $${AFFL.fmt(d.totalCap / 1000000, 1)}M`,
                  `Avg: $${AFFL.fmt(d.avgCap / 1000000, 2)}M`,
                  `Max: $${AFFL.fmt(d.maxCap / 1000000, 2)}M`,
                  `Players: ${d.matched}`
                ];
              }
            }
          }
        },
        scales: {
          x: { beginAtZero: true, grid: { color: AFFL.C.grid } },
          y: { grid: { display: false } }
        }
      }
    });
  }

})();
