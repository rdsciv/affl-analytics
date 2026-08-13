import { useEffect, useRef } from 'react';
import { Chart } from '@tanstack/charts';

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

interface ScatterChartProps {
  data: PlayerWeek[];
}

const posColors: Record<string, string> = {
  QB: '#dc2626',
  RB: '#16a34a',
  WR: '#2563eb',
  TE: '#ea580c',
};

export function ScatterChart({ data }: ScatterChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<Chart<PlayerWeek> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Filter to only rows with EPA data
    const chartData = data.filter(d => d.nfl_epa !== null);

    if (chartData.length === 0) {
      containerRef.current.innerHTML = '<p style="text-align: center; color: #a1a1aa; padding: 2rem;">No data to display with current filters</p>';
      return;
    }

    // Clear previous chart
    if (chartRef.current) {
      chartRef.current.destroy();
    }

    // Create new chart
    const chart = new Chart({
      container: containerRef.current,
      data: chartData,
      primaryAxis: {
        getValue: (datum) => datum.nfl_epa as number,
        scaleType: 'linear',
        label: 'NFL EPA',
      },
      secondaryAxes: [{
        getValue: (datum) => datum.fantasy_points,
        scaleType: 'linear',
        label: 'Fantasy Points',
        min: 0,
      }],
      series: [
        {
          type: 'scatter',
          dataKey: 'points',
          primaryAxisKey: 'primary',
          secondaryAxisKey: 'secondary',
          getStyle: (datum) => ({
            fill: posColors[datum.position] || '#a1a1aa',
            opacity: 0.6,
            r: 4,
          }),
        },
      ],
      tooltip: {
        render: (datum) => {
          if (!datum) return null;
          return `
            <div style="background: #27272a; border: 1px solid #3f3f46; padding: 0.5rem; border-radius: 0.375rem; color: #e4e4e7; font-size: 0.875rem;">
              <strong>${datum.player_name}</strong> (${datum.position})<br/>
              Fantasy: ${datum.fantasy_points.toFixed(1)} pts<br/>
              EPA: ${datum.nfl_epa?.toFixed(2)}
            </div>
          `;
        },
      },
      theme: {
        backgroundColor: 'transparent',
        textColor: '#a1a1aa',
        gridColor: '#27272a',
        axisColor: '#52525b',
      },
    });

    chartRef.current = chart;

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
      }
    };
  }, [data]);

  return (
    <div>
      <div ref={containerRef} className="chart-container" />
      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
        {Object.entries(posColors).map(([pos, color]) => (
          <div key={pos} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ 
              width: '8px', 
              height: '8px', 
              borderRadius: '50%', 
              backgroundColor: color 
            }} />
            <span style={{ fontSize: '0.875rem', color: '#d4d4d8' }}>{pos}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
