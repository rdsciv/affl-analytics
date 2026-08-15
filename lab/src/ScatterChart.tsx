import { useMemo } from 'react'
import { defineChart, dot } from '@tanstack/charts'
import { Chart } from '@tanstack/charts/react'
import { scaleLinear } from '@tanstack/charts/scales/linear'
import { tooltip } from '@tanstack/charts/tooltip'
import type { PlayerWeek } from './types'

const POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const
const POS_COLORS = ['#dc2626', '#16a34a', '#2563eb', '#ea580c']

export function ScatterChart({ data }: { data: PlayerWeek[] }) {
  const chartData = useMemo(
    () => data.filter((d) => d.nfl_epa !== null),
    [data],
  )

  const definition = useMemo(
    () =>
      defineChart({
        marks: [
          dot(chartData, {
            id: 'epa',
            x: 'nfl_epa',
            y: 'fantasy_points',
            color: 'position',
            r: 4,
            fillOpacity: 0.72,
            stroke: 'currentColor',
            strokeOpacity: 0.25,
          }),
        ],
        x: {
          scale: scaleLinear,
          nice: true,
          grid: true,
          axis: { label: 'NFL EPA (pass + rush + rec)' },
        },
        y: {
          scale: scaleLinear,
          nice: true,
          grid: true,
          axis: { label: 'Started fantasy points' },
        },
        color: {
          domain: [...POSITIONS],
          range: [...POS_COLORS],
        },
        tooltip: {
          use: tooltip,
          items: [
            { field: 'player_name', label: 'Player' },
            { field: 'position', label: 'Pos' },
            { field: 'team_name', label: 'AFFL team' },
            { field: 'season', label: 'Season' },
            { field: 'week', label: 'Week' },
            { field: 'fantasy_points', label: 'Started pts' },
            { field: 'nfl_epa', label: 'EPA' },
          ],
        },
      }),
    [chartData],
  )

  if (chartData.length === 0) {
    return (
      <p className="empty">
        No joined player-weeks with EPA under the current filters.
        Weekly lineups exist 2018–2025 only.
      </p>
    )
  }

  return (
    <div>
      <div className="chart-shell">
        <Chart
          definition={definition}
          height={460}
          initialWidth={1100}
          ariaLabel="Started fantasy points versus NFL EPA. Each dot is a started player-week joined from AFFL rosters to nflverse via gsis_id."
        />
      </div>
      <div className="legend">
        {POSITIONS.map((pos, i) => (
          <div key={pos} className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: POS_COLORS[i] }} />
            <span>{pos}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
