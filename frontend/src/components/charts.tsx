/* Theme-aware chart building blocks (Recharts).
 * Colour rules (validated with the data-viz palette checker against our light and dark surfaces):
 *   series-1 blue, series-2 orange, series-3 aqua - always assigned in this fixed order and
 *   always to the same entity (hits=1, misses=2; small=1, medium=2, large=3; actual=1, saved=3).
 * Thin marks, recessive grid, a legend for >= 2 series, hover tooltips on every chart. */
import { useReducedMotion } from 'framer-motion'
import type { ReactNode } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export const SERIES = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)'] as const
export const TIER_COLOR: Record<string, string> = { small: SERIES[0], medium: SERIES[1], large: SERIES[2] }

export interface SeriesDef { key: string; name: string; color: string; dashed?: boolean; stack?: string }

const axisProps = { tickLine: false, axisLine: false, tickMargin: 8, minTickGap: 16 } as const
const shortDate = (d: string) => (/^\d{4}-\d{2}-\d{2}$/.test(d) ? new Date(d + 'T00:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : d)

function ChartTooltip({ active, payload, label, format }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string; format: (v: number) => string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="card min-w-36 px-3 py-2 text-xs shadow-lg">
      <p className="mb-1.5 font-medium text-fg">{shortDate(String(label))}</p>
      {payload.map(p => (
        <p key={p.name} className="flex items-center justify-between gap-4 text-muted">
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: p.color }} />{p.name}</span>
          <span className="font-medium text-fg tabular">{p.value === null || p.value === undefined ? '—' : format(p.value)}</span>
        </p>
      ))}
    </div>
  )
}

function LegendRow({ series }: { series: SeriesDef[] }) {
  if (series.length < 2) return null
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-2 text-[11px] text-muted">
      {series.map(s => (
        <span key={s.key} className="flex items-center gap-1.5">
          <span className="h-0.5 w-3 rounded" style={{ background: s.color, opacity: s.dashed ? 0.7 : 1 }} />{s.name}
        </span>
      ))}
    </div>
  )
}

function Frame({ height, children, series }: { height: number; children: ReactNode; series: SeriesDef[] }) {
  return (
    <div>
      <div style={{ height }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">{children as React.ReactElement}</ResponsiveContainer>
      </div>
      <LegendRow series={series} />
    </div>
  )
}

export function TrendChart({ data, xKey, series, format, height = 220, area = true, yFormat }: {
  data: object[]; xKey: string; series: SeriesDef[]; format: (v: number) => string; height?: number; area?: boolean; yFormat?: (v: number) => string
}) {
  const reduce = useReducedMotion()
  const common = (
    <>
      <CartesianGrid vertical={false} strokeDasharray="0" />
      <XAxis dataKey={xKey} tickFormatter={shortDate} {...axisProps} />
      <YAxis width={68} tickFormatter={yFormat ?? format} {...axisProps} />
      <Tooltip content={<ChartTooltip format={format} />} cursor={{ stroke: 'var(--border-strong)', strokeWidth: 1 }} />
      <Legend content={() => null} />
    </>
  )
  if (area) {
    return (
      <Frame height={height} series={series}>
        <AreaChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          <defs>
            {series.map(s => (
              <linearGradient key={s.key} id={`g-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity={0.22} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          {common}
          {series.map(s => (
            <Area key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2}
              strokeDasharray={s.dashed ? '5 4' : undefined} fill={`url(#g-${s.key})`} dot={data.length === 1 ? { r: 4 } : false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }} isAnimationActive={!reduce} connectNulls />
          ))}
        </AreaChart>
      </Frame>
    )
  }
  return (
    <Frame height={height} series={series}>
      <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        {common}
        {series.map(s => (
          <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2}
            strokeDasharray={s.dashed ? '5 4' : undefined} dot={data.length === 1 ? { r: 4 } : false}
            activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }} isAnimationActive={!reduce} connectNulls />
        ))}
      </LineChart>
    </Frame>
  )
}

export function BarsChart({ data, xKey, series, format, height = 220, horizontal = false, yFormat }: {
  data: object[]; xKey: string; series: SeriesDef[]; format: (v: number) => string; height?: number; horizontal?: boolean; yFormat?: (v: number) => string
}) {
  const reduce = useReducedMotion()
  const stacked = series.some(s => s.stack)
  return (
    <Frame height={height} series={series}>
      <BarChart data={data} layout={horizontal ? 'vertical' : 'horizontal'} barCategoryGap="28%" barGap={2}
        margin={{ top: 6, right: 8, bottom: 0, left: horizontal ? 8 : 0 }}>
        <CartesianGrid vertical={horizontal} horizontal={!horizontal} />
        {horizontal ? (
          <>
            <XAxis type="number" tickFormatter={yFormat ?? format} {...axisProps} />
            <YAxis type="category" dataKey={xKey} width={120} {...axisProps} />
          </>
        ) : (
          <>
            <XAxis dataKey={xKey} tickFormatter={shortDate} {...axisProps} />
            <YAxis width={68} tickFormatter={yFormat ?? format} {...axisProps} />
          </>
        )}
        <Tooltip content={<ChartTooltip format={format} />} cursor={{ fill: 'var(--surface-2)' }} />
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} stackId={s.stack}
            radius={stacked ? (i === series.length - 1 ? (horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]) : 0) : (horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0])}
            stroke="var(--surface)" strokeWidth={stacked ? 1 : 0} maxBarSize={36} isAnimationActive={!reduce} />
        ))}
      </BarChart>
    </Frame>
  )
}

/** Proportion bar: one horizontal stacked bar with labelled segments (used instead of a pie). */
export function ShareBar({ items, format }: { items: { label: string; value: number; color: string }[]; format?: (v: number) => string }) {
  const total = items.reduce((a, b) => a + b.value, 0)
  if (!total) return null
  return (
    <div>
      <div className="flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full">
        {items.filter(i => i.value > 0).map(i => (
          <div key={i.label} title={`${i.label}: ${i.value}`} style={{ width: `${(i.value / total) * 100}%`, background: i.color }} className="h-full first:rounded-l-full last:rounded-r-full" />
        ))}
      </div>
      <div className="mt-3 grid gap-1.5">
        {items.map(i => (
          <div key={i.label} className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-2 text-muted"><span className="h-2 w-2 rounded-sm" style={{ background: i.color }} />{i.label}</span>
            <span className="tabular text-fg">{format ? format(i.value) : i.value} <span className="text-faint">· {((i.value / total) * 100).toFixed(0)}%</span></span>
          </div>
        ))}
      </div>
    </div>
  )
}
