import { LayoutDashboard } from 'lucide-react'

export function Header({ lastUpdated }: { lastUpdated: Date | null }) {
  return (
    <header className="flex items-center justify-between gap-3">
      {/* The mobile top bar (Layout.tsx) already shows the logo/title, so
          this block -- which would otherwise duplicate it -- is desktop
          only. */}
      <div className="hidden items-center gap-3 md:flex">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-ink text-white">
          <LayoutDashboard size={20} strokeWidth={2} />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-ink">Accounts Payable</h1>
          <p className="text-xs text-faint">Automation dashboard</p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2 whitespace-nowrap rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-muted">
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-green opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-accent-green" />
        </span>
        {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : 'Connecting…'}
      </div>
    </header>
  )
}
