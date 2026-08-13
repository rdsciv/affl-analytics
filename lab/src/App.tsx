import { useState, useEffect, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  createColumnHelper,
  flexRender,
  SortingState,
} from '@tanstack/react-table';
import { ScatterChart } from './ScatterChart';

interface PlayerWeek {
  season: number;
  week: number;
  player_name: string;
  position: string;
  team_name: string;
  fantasy_points: number;
  nfl_epa: number | null;
  pass_yards: number | null;
  pass_tds: number | null;
  rush_yards: number | null;
  rush_tds: number | null;
  receptions: number | null;
  rec_yards: number | null;
  rec_tds: number | null;
  cap_hit_m: number | null;
}

const columnHelper = createColumnHelper<PlayerWeek>();

export default function App() {
  const [data, setData] = useState<PlayerWeek[]>([]);
  const [seasonFilter, setSeasonFilter] = useState('');
  const [posFilter, setPosFilter] = useState('');
  const [minPoints, setMinPoints] = useState(10);
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'fantasy_points', desc: true }
  ]);

  useEffect(() => {
    fetch('./started_vs_nfl.json')
      .then(res => res.json())
      .then(setData)
      .catch(err => console.error('Failed to load data:', err));
  }, []);

  const filteredData = useMemo(() => {
    return data.filter(d => {
      if (seasonFilter && d.season !== parseInt(seasonFilter)) return false;
      if (posFilter && d.position !== posFilter) return false;
      if (d.fantasy_points < minPoints) return false;
      return true;
    });
  }, [data, seasonFilter, posFilter, minPoints]);

  const seasons = useMemo(() => {
    const unique = [...new Set(data.map(d => d.season))].sort((a, b) => b - a);
    return unique;
  }, [data]);

  const columns = useMemo(() => [
    columnHelper.accessor('season', {
      header: 'Season',
      cell: info => info.getValue(),
    }),
    columnHelper.accessor('week', {
      header: 'Wk',
      cell: info => info.getValue(),
    }),
    columnHelper.accessor('player_name', {
      header: 'Player',
      cell: info => info.getValue(),
    }),
    columnHelper.accessor('position', {
      header: 'Pos',
      cell: info => (
        <span className={`pos pos-${info.getValue()}`}>{info.getValue()}</span>
      ),
    }),
    columnHelper.accessor('team_name', {
      header: 'Team',
      cell: info => info.getValue(),
    }),
    columnHelper.accessor('fantasy_points', {
      header: 'Pts',
      cell: info => info.getValue()?.toFixed(1) ?? '—',
      meta: { className: 'num' },
    }),
    columnHelper.accessor('nfl_epa', {
      header: 'EPA',
      cell: info => info.getValue() !== null ? info.getValue()?.toFixed(2) : '—',
      meta: { className: 'num' },
    }),
    columnHelper.accessor('pass_yards', {
      header: 'PaYd',
      cell: info => info.getValue() || '—',
      meta: { className: 'num' },
    }),
    columnHelper.accessor('pass_tds', {
      header: 'PaTD',
      cell: info => info.getValue() || '—',
      meta: { className: 'num' },
    }),
    columnHelper.accessor('rush_yards', {
      header: 'RuYd',
      cell: info => info.getValue() || '—',
      meta: { className: 'num' },
    }),
    columnHelper.accessor('rush_tds', {
      header: 'RuTD',
      cell: info => info.getValue() || '—',
      meta: { className: 'num' },
    }),
    columnHelper.accessor('receptions', {
      header: 'Rec',
      cell: info => info.getValue() || '—',
      meta: { className: 'num' },
    }),
    columnHelper.accessor('rec_yards', {
      header: 'ReYd',
      cell: info => info.getValue() || '—',
      meta: { className: 'num' },
    }),
    columnHelper.accessor('rec_tds', {
      header: 'ReTD',
      cell: info => info.getValue() || '—',
      meta: { className: 'num' },
    }),
    columnHelper.accessor('cap_hit_m', {
      header: 'Cap $M',
      cell: info => info.getValue() !== null ? `$${info.getValue()}M` : '—',
      meta: { className: 'num' },
    }),
  ], []);

  const table = useReactTable({
    data: filteredData,
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="container">
      <a href="../index.html" className="back-link">← Back to Dashboard</a>
      
      <header>
        <h1>TanStack Lab</h1>
        <p className="subtitle">Started Fantasy Points vs NFL EPA · 2018–2025</p>
      </header>

      <div className="note">
        <p><strong>This is the join proof.</strong> Each row joins AFFL roster data (who started, fantasy points) 
        to NFL data (EPA, stats) via <code>dim_player.gsis_id</code>. Chart and table query the same 
        <code>v_started_vs_nfl</code> view across both databases.</p>
      </div>

      <div className="card">
        <h2>Chart: Fantasy Points vs EPA</h2>
        <div className="filters">
          <div className="filter-group">
            <label htmlFor="seasonFilter">Season</label>
            <select 
              id="seasonFilter"
              value={seasonFilter}
              onChange={e => setSeasonFilter(e.target.value)}
            >
              <option value="">All seasons</option>
              {seasons.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="filter-group">
            <label htmlFor="posFilter">Position</label>
            <select 
              id="posFilter"
              value={posFilter}
              onChange={e => setPosFilter(e.target.value)}
            >
              <option value="">All positions</option>
              <option value="QB">QB</option>
              <option value="RB">RB</option>
              <option value="WR">WR</option>
              <option value="TE">TE</option>
            </select>
          </div>
          <div className="filter-group">
            <label htmlFor="minPoints">Min Fantasy Points</label>
            <input 
              type="number" 
              id="minPoints"
              value={minPoints}
              onChange={e => setMinPoints(parseFloat(e.target.value) || 0)}
              step="1"
            />
          </div>
        </div>
        <ScatterChart data={filteredData} />
      </div>

      <div className="card">
        <h2>Table: Started Player-Weeks</h2>
        <div style={{ overflowX: 'auto', maxHeight: '600px', overflowY: 'auto' }}>
          <table>
            <thead>
              {table.getHeaderGroups().map(headerGroup => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map(header => (
                    <th
                      key={header.id}
                      onClick={header.column.getToggleSortingHandler()}
                      className={header.column.columnDef.meta?.className}
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      {{
                        asc: ' ↑',
                        desc: ' ↓',
                      }[header.column.getIsSorted() as string] ?? null}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map(row => (
                <tr key={row.id}>
                  {row.getVisibleCells().map(cell => (
                    <td 
                      key={cell.id}
                      className={cell.column.columnDef.meta?.className}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="row-count">
          {filteredData.length.toLocaleString()} player-weeks shown
        </div>
      </div>
    </div>
  );
}
