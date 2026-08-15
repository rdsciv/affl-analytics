import { useEffect, useMemo, useState } from 'react'
import {
  createSortedRowModel,
  createTableHook,
  rowSortingFeature,
  sortFn_alphanumeric,
  sortFn_basic,
} from '@tanstack/react-table'
import { ScatterChart } from './ScatterChart'
import type { PlayerWeek } from './types'

const { useAppTable, createAppColumnHelper } = createTableHook({
  features: {
    rowSortingFeature,
    sortedRowModel: createSortedRowModel(),
    sortFns: { alphanumeric: sortFn_alphanumeric, basic: sortFn_basic },
  },
})

const columnHelper = createAppColumnHelper<PlayerWeek>()

const NUM = new Set([
  'season',
  'week',
  'fantasy_points',
  'nfl_epa',
  'pass_yards',
  'pass_tds',
  'rush_yards',
  'rush_tds',
  'receptions',
  'rec_yards',
  'rec_tds',
  'cap_hit_m',
])

export default function App() {
  const [data, setData] = useState<PlayerWeek[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [seasonFilter, setSeasonFilter] = useState('')
  const [posFilter, setPosFilter] = useState('')
  const [minPoints, setMinPoints] = useState(10)

  useEffect(() => {
    fetch('./started_vs_nfl.json')
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
        return res.json()
      })
      .then(setData)
      .catch((err: Error) => setLoadError(err.message))
  }, [])

  const filteredData = useMemo(
    () =>
      data.filter((d) => {
        if (seasonFilter && d.season !== parseInt(seasonFilter, 10)) return false
        if (posFilter && d.position !== posFilter) return false
        if (d.fantasy_points < minPoints) return false
        return true
      }),
    [data, seasonFilter, posFilter, minPoints],
  )

  const seasons = useMemo(
    () => [...new Set(data.map((d) => d.season))].sort((a, b) => b - a),
    [data],
  )

  const columns = useMemo(
    () =>
      columnHelper.columns([
        columnHelper.accessor('season', { header: 'Season' }),
        columnHelper.accessor('week', { header: 'Wk' }),
        columnHelper.accessor('player_name', { header: 'Player' }),
        columnHelper.accessor('position', {
          header: 'Pos',
          cell: (info) => (
            <span className={`pos pos-${info.getValue()}`}>{info.getValue()}</span>
          ),
        }),
        columnHelper.accessor('team_name', { header: 'Team' }),
        columnHelper.accessor('fantasy_points', {
          header: 'Pts',
          cell: (info) => info.getValue()?.toFixed(1) ?? '—',
        }),
        columnHelper.accessor('nfl_epa', {
          header: 'EPA',
          cell: (info) => (info.getValue() !== null ? info.getValue()!.toFixed(2) : '—'),
        }),
        columnHelper.accessor('pass_yards', {
          header: 'PaYd',
          cell: (info) => info.getValue() || '—',
        }),
        columnHelper.accessor('pass_tds', {
          header: 'PaTD',
          cell: (info) => info.getValue() || '—',
        }),
        columnHelper.accessor('rush_yards', {
          header: 'RuYd',
          cell: (info) => info.getValue() || '—',
        }),
        columnHelper.accessor('rush_tds', {
          header: 'RuTD',
          cell: (info) => info.getValue() || '—',
        }),
        columnHelper.accessor('receptions', {
          header: 'Rec',
          cell: (info) => info.getValue() || '—',
        }),
        columnHelper.accessor('rec_yards', {
          header: 'ReYd',
          cell: (info) => info.getValue() || '—',
        }),
        columnHelper.accessor('rec_tds', {
          header: 'ReTD',
          cell: (info) => info.getValue() || '—',
        }),
        columnHelper.accessor('cap_hit_m', {
          header: 'Cap $M',
          cell: (info) => (info.getValue() !== null ? `$${info.getValue()}M` : '—'),
        }),
      ]),
    [],
  )

  const table = useAppTable(
    {
      columns,
      data: filteredData,
      initialState: {
        sorting: [{ id: 'fantasy_points', desc: true }],
      },
    },
    (state) => state,
  )

  return (
    <div className="container">
      <a href="../index.html" className="back-link">
        ← Back to Dashboard
      </a>

      <header>
        <h1>TanStack Lab</h1>
        <p className="subtitle">Started fantasy points vs NFL EPA · 2018–2025</p>
      </header>

      <div className="note">
        <p>
          <strong>This is the join proof.</strong> Each row is{' '}
          <code>fact_roster_week</code> (AFFL) ⋈ <code>fact_nfl_week</code> (NFL)
          via <code>dim_player.gsis_id</code>, with cap from{' '}
          <code>v_player_cap</code>. Chart is TanStack Charts. Table is TanStack
          Table. 2014–2017 have no weekly lineups, so they are not in this view.
        </p>
      </div>

      {loadError && (
        <div className="note">
          <p>
            Could not load <code>started_vs_nfl.json</code> ({loadError}). Build
            the warehouse, then run <code>python3 export_lab.py</code>.
          </p>
        </div>
      )}

      <div className="card">
        <h2>Started points vs EPA</h2>
        <div className="filters">
          <div className="filter-group">
            <label htmlFor="seasonFilter">Season</label>
            <select
              id="seasonFilter"
              value={seasonFilter}
              onChange={(e) => setSeasonFilter(e.target.value)}
            >
              <option value="">All seasons with lineups</option>
              {seasons.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-group">
            <label htmlFor="posFilter">Position</label>
            <select
              id="posFilter"
              value={posFilter}
              onChange={(e) => setPosFilter(e.target.value)}
            >
              <option value="">All skill positions</option>
              <option value="QB">QB</option>
              <option value="RB">RB</option>
              <option value="WR">WR</option>
              <option value="TE">TE</option>
            </select>
          </div>
          <div className="filter-group">
            <label htmlFor="minPoints">Min fantasy points</label>
            <input
              type="number"
              id="minPoints"
              value={minPoints}
              onChange={(e) => setMinPoints(parseFloat(e.target.value) || 0)}
              step="1"
            />
          </div>
        </div>
        <ScatterChart data={filteredData} />
      </div>

      <div className="card">
        <h2>Same rows</h2>
        <div className="table-wrap">
          <table>
            <thead>
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th key={header.id}>
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        <table.FlexRender header={header} />
                        {header.column.getIsSorted() === 'asc'
                          ? ' ↑'
                          : header.column.getIsSorted() === 'desc'
                            ? ' ↓'
                            : ''}
                      </button>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getAllCells().map((cell) => (
                    <td
                      key={cell.id}
                      className={NUM.has(cell.column.id) ? 'num' : undefined}
                    >
                      <table.FlexRender cell={cell} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="row-count">
          {filteredData.length.toLocaleString()} started player-weeks
        </div>
      </div>
    </div>
  )
}
