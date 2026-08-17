import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import type { TrendPoint } from '../lib/api'

function formatDay(day: string): string {
  const d = new Date(day + 'T00:00:00Z')
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' })
}

function TooltipContent({ active, payload }: { active?: boolean; payload?: { value: number; payload: TrendPoint }[] }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="rounded-xl border border-border bg-ink px-3 py-2 text-white shadow-lg">
      <p className="text-xs text-white/60">{formatDay(point.day)}</p>
      <p className="text-sm font-semibold">{point.count} email{point.count === 1 ? '' : 's'}</p>
    </div>
  )
}

export function TrendChart({ data, loading }: { data: TrendPoint[]; loading?: boolean }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-6 shadow-[0_1px_2px_rgba(20,22,27,0.04)]">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-ink">Email volume</h2>
          <p className="text-xs text-faint">Last 14 days</p>
        </div>
      </div>
      {loading ? (
        <div className="h-56 animate-pulse rounded-xl bg-canvas" />
      ) : data.length === 0 ? (
        <div className="flex h-56 items-center justify-center text-sm text-faint">No activity yet</div>
      ) : (
        <ResponsiveContainer width="100%" height={224}>
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
            <defs>
              <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#4F5DFF" stopOpacity={0.22} />
                <stop offset="100%" stopColor="#4F5DFF" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="day"
              tickFormatter={formatDay}
              tickLine={false}
              axisLine={false}
              tick={{ fill: '#9CA0AF', fontSize: 12 }}
              minTickGap={24}
            />
            <Tooltip content={<TooltipContent />} cursor={{ stroke: '#EBECF1', strokeWidth: 1 }} />
            <Area
              type="monotone"
              dataKey="count"
              stroke="#4F5DFF"
              strokeWidth={2.5}
              fill="url(#trendFill)"
              dot={false}
              activeDot={{ r: 5, fill: '#4F5DFF', stroke: '#fff', strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
