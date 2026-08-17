import type { ReactNode } from 'react'

type Accent = 'blue' | 'green' | 'amber' | 'rose'

const ACCENT_CLASSES: Record<Accent, { bg: string; fg: string }> = {
  blue: { bg: 'bg-accent-blue-soft', fg: 'text-accent-blue' },
  green: { bg: 'bg-accent-green-soft', fg: 'text-accent-green' },
  amber: { bg: 'bg-accent-amber-soft', fg: 'text-accent-amber' },
  rose: { bg: 'bg-accent-rose-soft', fg: 'text-accent-rose' },
}

export function StatCard({
  icon,
  label,
  value,
  sublabel,
  accent,
  loading,
}: {
  icon: ReactNode
  label: string
  value: string
  sublabel?: string
  accent: Accent
  loading?: boolean
}) {
  const colors = ACCENT_CLASSES[accent]
  return (
    <div className="flex items-center gap-4 rounded-2xl border border-border bg-surface p-5 shadow-[0_1px_2px_rgba(20,22,27,0.04)]">
      <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${colors.bg} ${colors.fg}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium text-muted">{label}</p>
        {loading ? (
          <div className="mt-1.5 h-7 w-20 animate-pulse rounded bg-canvas" />
        ) : (
          <p className="text-2xl font-bold tracking-tight text-ink">{value}</p>
        )}
        {sublabel && <p className="mt-0.5 text-xs text-faint">{sublabel}</p>}
      </div>
    </div>
  )
}
