// TanStack Lab — Started Points vs NFL EPA
import { createColumnHelper } from '@tanstack/table-core';
import * as d3 from 'd3';

let allData = [];
let filteredData = [];
let table = null;

// Fetch data
async function loadData() {
  const response = await fetch('/started_vs_nfl.json');
  allData = await response.json();
  
  // Populate season filter
  const seasons = [...new Set(allData.map(d => d.season))].sort((a, b) => b - a);
  const seasonSelect = document.getElementById('seasonFilter');
  seasons.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s;
    opt.textContent = s;
    seasonSelect.appendChild(opt);
  });
  
  applyFilters();
}

// Apply filters
function applyFilters() {
  const season = document.getElementById('seasonFilter').value;
  const position = document.getElementById('posFilter').value;
  const minPoints = parseFloat(document.getElementById('minPoints').value) || 0;
  
  filteredData = allData.filter(d => {
    if (season && d.season !== parseInt(season)) return false;
    if (position && d.position !== position) return false;
    if (d.fantasy_points < minPoints) return false;
    return true;
  });
  
  renderChart();
  renderTable();
}

// Render scatter chart with D3
function renderChart() {
  const svg = d3.select('#chart');
  svg.selectAll('*').remove();
  
  const margin = { top: 20, right: 30, bottom: 50, left: 60 };
  const width = svg.node().clientWidth - margin.left - margin.right;
  const height = 500 - margin.top - margin.bottom;
  
  const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);
  
  // Filter to only rows with EPA data
  const data = filteredData.filter(d => d.nfl_epa !== null);
  
  if (data.length === 0) {
    g.append('text')
      .attr('x', width / 2)
      .attr('y', height / 2)
      .attr('text-anchor', 'middle')
      .attr('fill', '#a1a1aa')
      .text('No data to display with current filters');
    return;
  }
  
  // Scales
  const x = d3.scaleLinear()
    .domain(d3.extent(data, d => d.nfl_epa)).nice()
    .range([0, width]);
  
  const y = d3.scaleLinear()
    .domain([0, d3.max(data, d => d.fantasy_points)]).nice()
    .range([height, 0]);
  
  const color = d3.scaleOrdinal()
    .domain(['QB', 'RB', 'WR', 'TE'])
    .range(['#dc2626', '#16a34a', '#2563eb', '#ea580c']);
  
  // X axis
  g.append('g')
    .attr('transform', `translate(0,${height})`)
    .call(d3.axisBottom(x))
    .selectAll('text, line')
    .attr('stroke', '#52525b')
    .attr('fill', '#a1a1aa');
  
  g.append('text')
    .attr('x', width / 2)
    .attr('y', height + 40)
    .attr('text-anchor', 'middle')
    .attr('fill', '#d4d4d8')
    .text('NFL EPA');
  
  // Y axis
  g.append('g')
    .call(d3.axisLeft(y))
    .selectAll('text, line')
    .attr('stroke', '#52525b')
    .attr('fill', '#a1a1aa');
  
  g.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('x', -height / 2)
    .attr('y', -45)
    .attr('text-anchor', 'middle')
    .attr('fill', '#d4d4d8')
    .text('Fantasy Points');
  
  // Grid lines
  g.append('g')
    .attr('class', 'grid')
    .attr('opacity', 0.1)
    .call(d3.axisLeft(y).tickSize(-width).tickFormat(''));
  
  g.append('g')
    .attr('class', 'grid')
    .attr('transform', `translate(0,${height})`)
    .attr('opacity', 0.1)
    .call(d3.axisBottom(x).tickSize(-height).tickFormat(''));
  
  // Dots
  g.selectAll('circle')
    .data(data)
    .join('circle')
    .attr('cx', d => x(d.nfl_epa))
    .attr('cy', d => y(d.fantasy_points))
    .attr('r', 4)
    .attr('fill', d => color(d.position))
    .attr('opacity', 0.6)
    .attr('stroke', '#18181b')
    .attr('stroke-width', 1)
    .on('mouseover', function(event, d) {
      d3.select(this)
        .attr('r', 6)
        .attr('opacity', 1);
      
      // Simple tooltip
      const tooltip = g.append('g')
        .attr('class', 'tooltip')
        .attr('transform', `translate(${x(d.nfl_epa)}, ${y(d.fantasy_points) - 10})`);
      
      const text = `${d.player_name} (${d.position}) • ${d.fantasy_points} pts • ${d.nfl_epa.toFixed(1)} EPA`;
      const bbox = { width: text.length * 6.5, height: 20 };
      
      tooltip.append('rect')
        .attr('x', -bbox.width / 2)
        .attr('y', -bbox.height - 5)
        .attr('width', bbox.width)
        .attr('height', bbox.height)
        .attr('fill', '#27272a')
        .attr('stroke', '#3f3f46')
        .attr('rx', 4);
      
      tooltip.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', -10)
        .attr('fill', '#e4e4e7')
        .attr('font-size', '12px')
        .text(text);
    })
    .on('mouseout', function() {
      d3.select(this)
        .attr('r', 4)
        .attr('opacity', 0.6);
      g.selectAll('.tooltip').remove();
    });
  
  // Legend
  const legend = g.append('g')
    .attr('transform', `translate(${width - 100}, 20)`);
  
  ['QB', 'RB', 'WR', 'TE'].forEach((pos, i) => {
    const lg = legend.append('g')
      .attr('transform', `translate(0, ${i * 20})`);
    
    lg.append('circle')
      .attr('r', 4)
      .attr('fill', color(pos));
    
    lg.append('text')
      .attr('x', 10)
      .attr('y', 4)
      .attr('fill', '#d4d4d8')
      .attr('font-size', '12px')
      .text(pos);
  });
}

// Render table with TanStack Table
function renderTable() {
  const tbody = document.querySelector('#data-table tbody');
  tbody.innerHTML = '';
  
  // Sort by fantasy points desc by default
  const sorted = [...filteredData].sort((a, b) => b.fantasy_points - a.fantasy_points);
  
  sorted.forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.season}</td>
      <td>${row.week}</td>
      <td>${row.player_name}</td>
      <td><span class="pos pos-${row.position}">${row.position}</span></td>
      <td>${row.team_name}</td>
      <td class="num">${row.fantasy_points?.toFixed(1) ?? '—'}</td>
      <td class="num">${row.nfl_epa !== null ? row.nfl_epa.toFixed(2) : '—'}</td>
      <td class="num">${row.pass_yards || '—'}</td>
      <td class="num">${row.pass_tds || '—'}</td>
      <td class="num">${row.rush_yards || '—'}</td>
      <td class="num">${row.rush_tds || '—'}</td>
      <td class="num">${row.receptions || '—'}</td>
      <td class="num">${row.rec_yards || '—'}</td>
      <td class="num">${row.rec_tds || '—'}</td>
      <td class="num">${row.cap_hit_m !== null ? `$${row.cap_hit_m}M` : '—'}</td>
    `;
    tbody.appendChild(tr);
  });
  
  document.getElementById('row-count').textContent = filteredData.length.toLocaleString();
  
  // Add sort handlers
  document.querySelectorAll('th[data-col]').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      const currentOrder = th.dataset.order || 'desc';
      const newOrder = currentOrder === 'desc' ? 'asc' : 'desc';
      
      // Clear all other sort indicators
      document.querySelectorAll('th[data-col]').forEach(t => {
        t.dataset.order = '';
        t.textContent = t.textContent.replace(' ↑', '').replace(' ↓', '');
      });
      
      th.dataset.order = newOrder;
      th.textContent = th.textContent.replace(' ↑', '').replace(' ↓', '') + (newOrder === 'asc' ? ' ↑' : ' ↓');
      
      sortTable(col, newOrder);
    });
  });
}

function sortTable(col, order) {
  const tbody = document.querySelector('#data-table tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  
  const getColIndex = (colName) => {
    const headers = Array.from(document.querySelectorAll('th[data-col]'));
    return headers.findIndex(h => h.dataset.col === colName);
  };
  
  const colIndex = getColIndex(col);
  
  rows.sort((a, b) => {
    const aVal = a.children[colIndex].textContent.replace(/[^0-9.-]/g, '');
    const bVal = b.children[colIndex].textContent.replace(/[^0-9.-]/g, '');
    
    const aNum = parseFloat(aVal) || 0;
    const bNum = parseFloat(bVal) || 0;
    
    if (aNum === bNum) {
      return a.children[2].textContent.localeCompare(b.children[2].textContent);
    }
    
    return order === 'asc' ? aNum - bNum : bNum - aNum;
  });
  
  rows.forEach(row => tbody.appendChild(row));
}

// Initialize
loadData();

// Attach filter listeners
document.getElementById('seasonFilter').addEventListener('change', applyFilters);
document.getElementById('posFilter').addEventListener('change', applyFilters);
document.getElementById('minPoints').addEventListener('input', applyFilters);

// Handle window resize
window.addEventListener('resize', () => {
  if (filteredData.length > 0) renderChart();
});
